from contextlib import closing
import csv
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from naseem.config import load_config, config_hash
from naseem.demo import create_demo, render_report, FILES
from naseem.engine import RuleEngine
from naseem.model import parse_line
from naseem.simulate import make_packet


class DemoTests(unittest.TestCase):
    def test_bundle_contains_matching_closed_run_records_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "demo"
            summary = create_demo(output)
            self.assertTrue(summary["complete"])
            self.assertEqual((summary["accepted"], summary["rejected"]), (72, 0))
            self.assertEqual(summary["status_counts"], {"UNKNOWN": 12, "NORMAL": 45, "WATCH": 9, "HIGH": 6})
            self.assertEqual(set(path.name for path in output.iterdir()), set(FILES))
            self.assertFalse(summary["hardware_verified"])
            self.assertEqual(summary["config_sha256"], config_hash(load_config()))
            self.assertEqual(json.loads((output / "summary.json").read_text()), summary)
            packets = [json.loads(line) for line in (output / "SYNTHETIC_packets.jsonl").read_text().splitlines()]
            self.assertEqual([row["sequence"] for row in packets], list(range(72)))
            self.assertEqual([row["uptime_ms"] for row in packets], list(range(0, 360000, 5000)))
            self.assertEqual({row["source"] for row in packets}, {"synthetic"})
            self.assertEqual({row["boot_id"] for row in packets}, {summary["run_id"]})
            with closing(sqlite3.connect(output / "SYNTHETIC_demo.sqlite3")) as db, db:
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone(), ("ok",))
                self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone(), (0,))
                run = db.execute("SELECT run_id, ended_at_utc, mode, config_sha256, software_version FROM runs").fetchone()
                self.assertEqual(run[0], summary["run_id"])
                self.assertIsNotNone(run[1])
                self.assertEqual(run[2:], ("simulate", summary["config_sha256"], summary["software_version"]))
                records = db.execute("SELECT sequence, uptime_ms, source, prototype_status, data_quality FROM records ORDER BY id").fetchall()
            with (output / "SYNTHETIC_records.csv").open(newline="") as handle:
                exported = list(csv.DictReader(handle))
            self.assertEqual(len(exported), 72)
            self.assertEqual([(int(row["sequence"]), int(row["uptime_ms"]), row["source"], row["prototype_status"], row["data_quality"]) for row in exported], records)
            report = (output / "report.html").read_text()
            self.assertIn("SYNTHETIC DATA", report)
            self.assertIn("355s", report)
            self.assertIn(summary["config_sha256"], report)
            self.assertIn("<svg", report)
            self.assertNotIn("<script", report.lower())
            self.assertNotIn("https://", report)
            self.assertNotIn("http://", report)
            self.assertNotIn("src=", report)

    def test_existing_directory_and_file_are_never_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "existing"
            folder.mkdir()
            keep = folder / "keep.txt"
            keep.write_text("untouched")
            for target in (folder, keep):
                with self.subTest(target=target), self.assertRaises(FileExistsError):
                    create_demo(target)
            self.assertEqual(keep.read_text(), "untouched")
            self.assertEqual(list(folder.iterdir()), [keep])

    def test_failure_leaves_explicit_incomplete_marker_and_preserves_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "failed"
            with patch("naseem.demo.export_csv", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    create_demo(folder)
            self.assertIn("INCOMPLETE", (folder / "INCOMPLETE.txt").read_text())
            self.assertFalse((folder / "summary.json").exists())
            with closing(sqlite3.connect(folder / "SYNTHETIC_demo.sqlite3")) as db, db:
                self.assertEqual(db.execute("SELECT count(*) FROM records").fetchone(), (72,))
                self.assertIsNotNone(db.execute("SELECT ended_at_utc FROM runs").fetchone()[0])

    def test_report_escapes_provenance_and_explanations(self):
        config = load_config()
        config["label"] = '<img src=x onerror="alert(1)">'
        packet = make_packet(10)
        result = RuleEngine(config).evaluate(parse_line(json.dumps(packet))).response()
        result["reasons"] = ['<script>alert("x")</script>']
        summary = {"accepted": 1, "rejected": 0, "status_counts": {"NORMAL": 1}, "quality_counts": {"VALID": 1},
                   "software_version": '<b>version</b>', "run_id": '<a href="evil">id</a>', "config_sha256": "hash"}
        report = render_report(summary, [{"packet": packet, "result": result}], config)
        self.assertNotIn("<script>", report)
        self.assertNotIn("<img", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn("&lt;img src=x", report)
        self.assertIn("&lt;b&gt;version&lt;/b&gt;", report)


if __name__ == "__main__":
    unittest.main()
