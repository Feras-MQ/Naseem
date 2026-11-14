"""Real pyserial/OS transport test using a virtual port, never physical sensors."""
import importlib.util
import json
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from naseem.simulate import make_packet

AVAILABLE = os.name == "posix" and importlib.util.find_spec("serial") is not None


@unittest.skipUnless(AVAILABLE, "Requires POSIX pseudo-terminals and optional pyserial")
class SerialPtyTests(unittest.TestCase):
    def test_real_serial_framing_rejection_and_recovery(self):
        import pty
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "virtual-port-test.sqlite3"
            # Signal only after real pyserial.open() finishes its input flush.
            # Raw PTY mode alone is not a barrier: sending then can lose bytes.
            harness = """
import serial
import sys
from naseem.cli import main
RealSerial = serial.Serial
class ReadySerial(RealSerial):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print("VIRTUAL_PORT_READY", flush=True)
serial.Serial = ReadySerial
raise SystemExit(main(sys.argv[1:]))
"""
            child = subprocess.Popen(
                [sys.executable, "-u", "-c", harness, "serial", "--port", os.ttyname(slave),
                 "--db", str(database), "--samples", "2"],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertTrue(select.select([child.stdout], [], [], 10)[0],
                                "Timed out waiting for virtual port readiness")
                self.assertEqual(child.stdout.readline().strip(), "VIRTUAL_PORT_READY")
                # These are emulated hardware-format packets, NOT observations.
                high = make_packet(10, "high", "virtual-port-fixture")
                high["device_id"] = "EMULATED-ESP32"
                high["source"] = "hardware"
                high["sensor_status"]["mq7"] = "missing"
                high["readings"]["mq7_adc_raw"] = None
                low = make_packet(11, "stable", "virtual-port-fixture")
                low.update(device_id=high["device_id"], source="hardware")
                low["sensor_status"]["mq7"] = "missing"
                low["readings"]["mq7_adc_raw"] = None
                first = (json.dumps(high) + "\n").encode("ascii")
                os.write(master, first[:57])
                os.write(master, first[57:])
                # Duplicate sequence must be rejected without stopping the stream.
                os.write(master, first + (json.dumps(low) + "\n").encode("ascii"))
                stdout, stderr = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 1, stderr)  # one rejected frame
                summary = json.loads(stdout.strip().splitlines()[-1])
                self.assertEqual((summary["accepted"], summary["rejected"]), (2, 1))
                received = bytearray()
                while select.select([master], [], [], 0.2)[0]:
                    received.extend(os.read(master, 4096))
                responses = [json.loads(line) for line in received.splitlines()]
                self.assertEqual(len(responses), 3)
                self.assertEqual([r["prototype_status"] for r in responses], ["HIGH", "UNKNOWN", "UNKNOWN"])
                self.assertEqual([r["data_quality"] for r in responses], ["PARTIAL", "INVALID", "PARTIAL"])
                self.assertEqual(responses[-1]["sequence"], 11)
                self.assertEqual(responses[-1]["boot_id"], "virtual-port-fixture")
                self.assertTrue(all(len(line) < 512 for line in received.splitlines()))
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM records").fetchone()[0], 2)
                    self.assertEqual(db.execute("SELECT count(*) FROM events WHERE kind='invalid_record'").fetchone()[0], 1)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
