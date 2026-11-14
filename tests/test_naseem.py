import copy
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from naseem.cli import main
from naseem.config import DEFAULT, load_config, validate_config, config_hash
from naseem.engine import RuleEngine
from naseem.model import parse_line, ValidationError, SENSORS, BOUNDS
from naseem.service import Processor, LineFramer
from naseem.simulate import make_packet
from naseem.storage import Journal, export_csv
from naseem.transport import wire_response


def packet(index=10):
    return make_packet(index, "stable")


def reading(index=10):
    return parse_line(json.dumps(packet(index)))


class ValidationTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(reading().source, "synthetic")

    def test_all_warmup_scenarios_parse(self):
        for i in range(12):
            parse_line(json.dumps(make_packet(i)))

    def test_malformed_and_oversized(self):
        for raw in ("{}", "[]", "not json", b"\xff", " " * 4097, '{"a":1,"a":2}', "null"):
            with self.subTest(raw=str(raw)[:40]), self.assertRaises(ValidationError):
                parse_line(raw)

    def test_invalid_values(self):
        for field, value in (("pm25_ug_m3", -1), ("tvoc_ppb", float("nan")), ("eco2_ppm", 399),
                             ("humidity_pct", 101), ("pressure_hpa", 200), ("temperature_c", True),
                             ("mq7_adc_raw", 4096), ("tvoc_ppb", 12.5), ("pm10_ug_m3", None)):
            obj = packet()
            obj["readings"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                parse_line(json.dumps(obj))

    def test_sensor_status_mismatch(self):
        obj = packet()
        obj["sensor_status"]["sgp30"] = "missing"
        with self.assertRaises(ValidationError): parse_line(json.dumps(obj))

    def test_early_sgp_ok_rejected(self):
        obj = packet()
        obj["uptime_ms"] = 14999
        with self.assertRaises(ValidationError): parse_line(json.dumps(obj))

    def test_missing_nulls_accepted(self):
        obj = packet()
        obj["sensor_status"] = {s: "missing" for s in SENSORS}
        obj["readings"] = {f: None for f in BOUNDS}
        self.assertEqual(parse_line(json.dumps(obj)).sensor_status["mq7"], "missing")

    def test_no_co_ppm_field(self):
        obj = packet()
        obj["readings"]["co_ppm"] = 10
        with self.assertRaises(ValidationError): parse_line(json.dumps(obj))

    def test_strict_metadata(self):
        for key, value in (("schema_version", True), ("sequence", True), ("uptime_ms", -1), ("device_id", "bad\n"), ("source", "measured"), ("boot_id", "a" * 65)):
            obj = packet(); obj[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError): parse_line(json.dumps(obj))


class RuleTests(unittest.TestCase):
    def setUp(self): self.engine = RuleEngine(load_config())
    def test_normal_is_not_safety_claim(self):
        result = self.engine.evaluate(reading())
        self.assertEqual((result.prototype_status, result.data_quality), ("NORMAL", "VALID"))
        self.assertTrue(any("does not establish" in reason for reason in result.reasons))

    def test_threshold_boundaries(self):
        for value, expected in ((24.99, "NORMAL"), (25, "WATCH"), (74.99, "WATCH"), (75, "HIGH")):
            obj = packet(); obj["readings"]["pm25_ug_m3"] = value
            self.engine.reset()
            self.assertEqual(self.engine.evaluate(parse_line(json.dumps(obj))).prototype_status, expected)

    def test_any_missing_or_warming_never_normal(self):
        for sensor in SENSORS:
            for status in ("missing", "warming_up", "error"):
                obj = packet(); obj["sensor_status"][sensor] = status
                for field in SENSORS[sensor]: obj["readings"][field] = None
                with self.subTest(sensor=sensor, status=status):
                    self.assertEqual(self.engine.evaluate(parse_line(json.dumps(obj))).prototype_status, "UNKNOWN")

    def test_partial_does_not_hide_high(self):
        obj = packet(); obj["readings"]["pm25_ug_m3"] = 80
        obj["sensor_status"]["mq7"] = "uncalibrated"
        result = self.engine.evaluate(parse_line(json.dumps(obj)))
        self.assertEqual((result.prototype_status, result.data_quality), ("HIGH", "PARTIAL"))

    def test_mq_raw_not_co_rule(self):
        obj = packet(); obj["readings"]["mq7_adc_raw"] = 4095
        self.assertEqual(self.engine.evaluate(parse_line(json.dumps(obj))).prototype_status, "NORMAL")

    def test_rising_below_threshold(self):
        results = []
        for i in range(4):
            obj = packet(10 + i); obj["readings"]["pm25_ug_m3"] = 8 + i * 2
            results.append(self.engine.evaluate(parse_line(json.dumps(obj))))
        self.assertEqual(results[-1].prototype_status, "WATCH")
        self.assertEqual(results[-1].trends["pm25_ug_m3"]["slope_per_minute"], 24)

    def test_gap_and_reboot_clear_history(self):
        for i in range(3): self.engine.evaluate(reading(10 + i))
        result = self.engine.evaluate(reading(30))
        self.assertEqual(result.trends, {})
        for i in range(3): self.engine.evaluate(reading(31 + i))
        obj = packet(34); obj["boot_id"] = "new-boot"
        self.assertEqual(self.engine.evaluate(parse_line(json.dumps(obj))).trends, {})

    def test_sensor_failure_clears_its_history(self):
        for i in range(3): self.engine.evaluate(reading(10 + i))
        obj = packet(13); obj["sensor_status"]["sgp30"] = "missing"
        for field in SENSORS["sgp30"]: obj["readings"][field] = None
        self.engine.evaluate(parse_line(json.dumps(obj)))
        self.assertNotIn("tvoc_ppb", self.engine.evaluate(reading(14)).trends)

    def test_lcd_and_wire_bounded(self):
        for scenario in ("stable", "high", "missing", "warming_up"):
            obj = parse_line(json.dumps(make_packet(10, scenario)))
            result = self.engine.evaluate(obj)
            self.assertLessEqual(len(result.lcd_line_1), 16)
            self.assertLessEqual(len(result.lcd_line_2), 16)
            self.assertLessEqual(len(wire_response(result.response(obj))), 511)


class ConfigTests(unittest.TestCase):
    def test_default_and_hash(self):
        self.assertEqual(len(config_hash(load_config())), 64)
        obj = load_config(); obj["thresholds"]["pm25_ug_m3"]["watch"] = 10
        self.assertNotEqual(config_hash(obj), config_hash(load_config()))

    def test_invalid_configs(self):
        for key, value in (("trend_window", 2), ("trend_min_samples", 7), ("max_trend_gap_seconds", 1), ("record_interval_seconds", 1)):
            obj = copy.deepcopy(DEFAULT); obj[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError): validate_config(obj)
        obj = load_config(); obj["thresholds"]["pm25_ug_m3"]["high"] = 20
        with self.assertRaises(ValidationError): validate_config(obj)
        obj = load_config(); obj["thresholds"]["mq7_adc_raw"] = {"watch": 10, "high": 100}
        with self.assertRaises(ValidationError): validate_config(obj)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "journal.sqlite3"
        self.journal = Journal(self.path, "test", load_config()); self.addCleanup(self.journal.close)
        self.processor = Processor(self.journal, load_config())

    def test_persistence_export_provenance(self):
        self.processor.process(json.dumps(packet()))
        row = self.journal.connection.execute("SELECT source, prototype_status, data_quality FROM records").fetchone()
        self.assertEqual(row, ("synthetic", "NORMAL", "VALID"))
        output = self.path.with_suffix(".csv")
        self.assertEqual(export_csv(self.path, output), 1)
        with output.open() as f: rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["source"], "synthetic")
        self.assertEqual(rows[0]["pm25_ug_m3"], "8.0")
        self.assertEqual(len(rows[0]["config_sha256"]), 64)
        with self.assertRaises(FileExistsError): export_csv(self.path, output)

    def test_duplicate_and_out_of_order_rejected(self):
        self.processor.process(json.dumps(packet(10)))
        for obj in (packet(10), packet(9)):
            result = self.processor.process(json.dumps(obj))
            self.assertEqual(result["data_quality"], "INVALID")
        self.assertEqual(self.processor.accepted, 1)
        self.assertEqual(self.processor.rejected, 2)

    def test_reboot_accepts_and_old_boot_rejects(self):
        self.processor.process(json.dumps(packet(10)))
        obj = packet(1); obj["boot_id"] = "new-boot"
        # A reboot must warm up its sensor data too.
        obj = make_packet(1, "stable", "new-boot")
        self.processor.process(json.dumps(obj))
        self.assertEqual(self.processor.accepted, 2)
        self.assertEqual(self.processor.process(json.dumps(packet(11)))["data_quality"], "INVALID")

    def test_hardware_mode_refuses_simulation(self):
        processor = Processor(self.journal, load_config(), expected_source="hardware")
        self.assertEqual(processor.process(json.dumps(packet()))["prototype_status"], "UNKNOWN")
        self.assertEqual(processor.accepted, 0)

    def test_invalid_persists_and_resets_history(self):
        for i in range(3): self.processor.process(json.dumps(packet(10 + i)))
        self.processor.process("bad json")
        self.assertEqual(self.processor.process(json.dumps(packet(13)))["trends"], {})
        self.assertEqual(self.journal.connection.execute("SELECT count(*) FROM events").fetchone()[0], 1)

    def test_duplicate_surrogate_key_is_logged_and_stream_recovers(self):
        # Escaped lone surrogates are legal input to Python's JSON decoder but
        # cannot be encoded by SQLite. Error messages must escape the key.
        malformed = json.dumps(packet())[:-1] + r',"\ud800":1,"\ud800":2}'
        result = self.processor.process(malformed.encode("ascii"))
        self.assertEqual(result["data_quality"], "INVALID")
        self.assertEqual(self.processor.rejected, 1)
        event = self.journal.connection.execute("SELECT kind, message FROM events").fetchone()
        self.assertEqual(event[0], "invalid_record")
        self.assertIn(r"\ud800", event[1])
        self.assertNotIn(chr(0xD800), event[1])
        # The next valid packet must still be accepted in the same session.
        self.assertEqual(self.processor.process(json.dumps(packet()))["data_quality"], "VALID")
        self.assertEqual(self.processor.accepted, 1)

    def test_mixed_device_or_source_rejected(self):
        self.processor.process(json.dumps(packet()))
        for key, value in (("device_id", "other"), ("source", "hardware")):
            obj = packet(11); obj[key] = value
            self.assertEqual(self.processor.process(json.dumps(obj))["data_quality"], "INVALID")

    def test_database_not_overwritten_by_export(self):
        with self.assertRaises(ValueError): export_csv(self.path, self.path)


class FramingTests(unittest.TestCase):
    def test_split_crlf_and_multiple_lines(self):
        frame = LineFramer()
        self.assertEqual(frame.feed(b"ab"), [])
        self.assertEqual(frame.feed(b"c\r\nxyz\n"), [b"abc", b"xyz"])
        self.assertFalse(frame.finish())

    def test_overflow_recovers(self):
        frame = LineFramer()
        self.assertEqual(frame.feed(b"x" * 10000 + b"\nok\n"), [None, b"ok"])
        self.assertEqual(len(frame.buffer), 0)

    def test_incomplete_final_frame(self):
        frame = LineFramer(); frame.feed(b"unfinished")
        self.assertTrue(frame.finish())
        self.assertFalse(frame.finish())


class CliTests(unittest.TestCase):
    def test_demo_replay_export(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            temp = Path(temp); db = temp / "demo.sqlite3"; packets = temp / "synthetic.jsonl"
            self.assertEqual(main(["simulate", "--db", str(db), "--samples", "72", "--jsonl", str(packets)]), 0)
            with sqlite3.connect(db) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM records").fetchone()[0], 72)
                statuses = {r[0] for r in con.execute("SELECT DISTINCT prototype_status FROM records")}
                self.assertEqual(statuses, {"NORMAL", "WATCH", "HIGH", "UNKNOWN"})
                times = [r[0] for r in con.execute("SELECT uptime_ms FROM records ORDER BY id")]
                self.assertTrue(all(b-a == 5000 for a,b in zip(times, times[1:])))
            self.assertEqual(main(["replay", str(packets), "--db", str(temp / "replay.sqlite3")]), 0)
            self.assertEqual(main(["export", "--db", str(db), "--csv", str(temp / "demo.csv")]), 0)

    def test_bad_replay_nonzero(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            temp = Path(temp); source = temp / "bad.jsonl"; source.write_text("garbage\npartial")
            self.assertEqual(main(["replay", str(source), "--db", str(temp / "bad.sqlite3")]), 1)

    def test_existing_export_protected(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            temp = Path(temp); db = temp / "demo.sqlite3"; out = temp / "x.csv"; out.write_text("keep")
            self.assertEqual(main(["simulate", "--db", str(db), "--samples", "1"]), 0)
            self.assertEqual(main(["export", "--db", str(db), "--csv", str(out)]), 2)
            self.assertEqual(out.read_text(), "keep")



class SerialAdapterTests(unittest.TestCase):
    def test_mock_usb_roundtrip_and_compact_response(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from naseem.transport import run_serial
        class FakeSerial:
            def __init__(self): self.writes = []; self.calls = 0
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self, size):
                self.calls += 1
                obj = packet(10 + self.calls); obj["source"] = "hardware"
                return json.dumps(obj).encode() + b"\n"
            def write(self, data): self.writes.append(data); return len(data)
        with tempfile.TemporaryDirectory() as temp:
            with Journal(Path(temp) / "x.sqlite3", "serial", load_config()) as journal:
                processor = Processor(journal, load_config(), expected_source="hardware")
                fake = FakeSerial()
                with patch.dict("sys.modules", {"serial": SimpleNamespace(Serial=lambda **kw: fake)}):
                    run_serial("FAKE-NOT-A-DEVICE", 115200, processor, limit=2)
                self.assertEqual(processor.accepted, 2)
                self.assertEqual(len(fake.writes), 2)
                response = json.loads(fake.writes[-1])
                self.assertEqual(response["sequence"], 12)
                self.assertNotIn("reasons", response)
                self.assertLessEqual(len(fake.writes[-1]), 511)

    def test_mock_stale_stream_logged(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from naseem.transport import run_serial
        class FakeSerial:
            calls = 0
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self, size):
                self.calls += 1
                if self.calls > 1: raise KeyboardInterrupt
                return b""
        with tempfile.TemporaryDirectory() as temp:
            with Journal(Path(temp) / "x.sqlite3", "serial", load_config()) as journal:
                processor = Processor(journal, load_config())
                with patch.dict("sys.modules", {"serial": SimpleNamespace(Serial=lambda **kw: FakeSerial())}), patch("naseem.transport.time.monotonic", side_effect=[0, 16]), redirect_stderr(io.StringIO()), self.assertRaises(KeyboardInterrupt):
                    run_serial("FAKE", 115200, processor)
                self.assertEqual(journal.connection.execute("SELECT kind FROM events").fetchone()[0], "stale_stream")

    def test_large_uptime_retains_slope_precision(self):
        engine = RuleEngine(load_config())
        for i in range(4):
            obj = packet(10 + i)
            obj["uptime_ms"] = 2**63 - 20000 + i * 5000
            obj["readings"]["pm25_ug_m3"] = 8 + i * 2
            result = engine.evaluate(parse_line(json.dumps(obj)))
        self.assertEqual(result.trends["pm25_ug_m3"]["slope_per_minute"], 24)


class NumericRobustnessTests(unittest.TestCase):
    def test_huge_integer_reading_is_rejected_without_crashing(self):
        obj = packet(); obj["readings"]["pm25_ug_m3"] = 10**400
        with self.assertRaises(ValidationError): parse_line(json.dumps(obj))
        with tempfile.TemporaryDirectory() as temp:
            with Journal(Path(temp) / "huge.sqlite3", "test", load_config()) as journal:
                processor = Processor(journal, load_config())
                self.assertEqual(processor.process(json.dumps(obj))["data_quality"], "INVALID")
                self.assertEqual(processor.rejected, 1)

    def test_huge_configuration_number_is_rejected(self):
        obj = load_config(); obj["thresholds"]["pm25_ug_m3"]["high"] = 10**400
        with self.assertRaises(ValidationError): validate_config(obj)




class EnabledHardwareContractTests(unittest.TestCase):
    """Synthetic packet fixtures, not observations from real hardware."""
    def test_three_ready_sensors_still_cannot_claim_normal_without_mq7(self):
        obj = packet(); obj["source"] = "hardware"
        obj["sensor_status"]["mq7"] = "missing"; obj["readings"]["mq7_adc_raw"] = None
        engine = RuleEngine(load_config())
        result = engine.evaluate(parse_line(json.dumps(obj)))
        self.assertEqual((result.prototype_status, result.data_quality), ("UNKNOWN", "PARTIAL"))
        obj["readings"]["pm25_ug_m3"] = 80
        result = engine.evaluate(parse_line(json.dumps(obj)))
        self.assertEqual((result.prototype_status, result.data_quality), ("HIGH", "PARTIAL"))

    def test_midrun_sgp_reinitialization_excludes_its_values(self):
        obj = packet(100); obj["source"] = "hardware"
        obj["sensor_status"]["sgp30"] = "warming_up"
        obj["readings"]["tvoc_ppb"] = None; obj["readings"]["eco2_ppm"] = None
        result = RuleEngine(load_config()).evaluate(parse_line(json.dumps(obj)))
        self.assertEqual((result.prototype_status, result.data_quality), ("UNKNOWN", "WARMING_UP"))

    def test_journal_records_current_software_version(self):
        from naseem import __version__
        with tempfile.TemporaryDirectory() as temp:
            with Journal(Path(temp) / "version.sqlite3", "test", load_config()) as journal:
                self.assertEqual(journal.connection.execute("SELECT software_version FROM runs").fetchone()[0], __version__)

if __name__ == "__main__": unittest.main()
