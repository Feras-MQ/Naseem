"""Operator preflight tests with no physical device access."""
import json
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from naseem.diagnostics import doctor, list_ports


def fake_serial():
    return SimpleNamespace(Serial=Mock(side_effect=AssertionError("Must never open a port")), VERSION="3.5")


def fake_import(serial, ports):
    def load(name):
        if name == "serial":
            return serial
        if name == "serial.tools.list_ports":
            return ports
        raise AssertionError(f"Unexpected dependency: {name}")
    return load


class DiagnosticsTests(unittest.TestCase):
    def test_ports_are_sorted_and_metadata_is_json_safe_without_opening(self):
        serial = fake_serial()
        backend = SimpleNamespace(comports=Mock(return_value=[
            SimpleNamespace(device="COM10", description="Ten", vid=4660, pid=22136,
                            serial_number="sample-10", manufacturer="Example", product="USB", location="1-2", hwid="USB"),
            SimpleNamespace(device="COM2", description="Two", vid=None, pid=None),
            SimpleNamespace(device=None),
        ]))
        with patch("naseem.diagnostics.import_module", side_effect=fake_import(serial, backend)):
            ports = list_ports()
        self.assertEqual([port["device"] for port in ports], ["COM2", "COM10"])
        self.assertEqual(ports[0]["hwid"], None)
        self.assertEqual(ports[1]["vid"], 4660)
        self.assertEqual(ports[1]["serial_number"], "sample-10")
        self.assertEqual(json.loads(json.dumps(ports)), ports)
        serial.Serial.assert_not_called()
        backend.comports.assert_called_once_with()

    def test_no_ports_is_successful_empty_list(self):
        serial = fake_serial()
        backend = SimpleNamespace(comports=Mock(return_value=[]))
        with patch("naseem.diagnostics.import_module", side_effect=fake_import(serial, backend)):
            self.assertEqual(list_ports(), [])
        serial.Serial.assert_not_called()

    def test_missing_pyserial_explains_optional_installation(self):
        with patch("naseem.diagnostics.import_module", side_effect=ModuleNotFoundError("serial")):
            with self.assertRaisesRegex(RuntimeError, r"requires pyserial.*pip install"):
                list_ports()
            report = doctor()
        self.assertFalse(report["serial_available"])
        self.assertTrue(report["software_ready"])
        self.assertIn("pip install", report["serial_setup"])

    def test_incompatible_serial_package_is_not_reported_ready(self):
        with patch("naseem.diagnostics.import_module", return_value=SimpleNamespace()):
            with self.assertRaisesRegex(RuntimeError, "not usable pyserial"):
                list_ports()
            report = doctor()
        self.assertFalse(report["serial_available"])

    def test_enumeration_failure_explains_no_port_opened(self):
        serial = fake_serial()
        backend = SimpleNamespace(comports=Mock(side_effect=PermissionError("access denied")))
        with patch("naseem.diagnostics.import_module", side_effect=fake_import(serial, backend)):
            with self.assertRaisesRegex(RuntimeError, "Could not enumerate.*No port was opened"):
                list_ports()
        serial.Serial.assert_not_called()

    def test_doctor_checks_memory_database_without_enumerating_ports(self):
        serial = fake_serial()
        backend = SimpleNamespace(comports=Mock(side_effect=AssertionError("No enumeration in doctor")))
        with patch("naseem.diagnostics.import_module", side_effect=fake_import(serial, backend)), \
             patch("naseem.diagnostics.sqlite3.connect", wraps=sqlite3.connect) as connect:
            report = doctor()
        connect.assert_called_once_with(":memory:")
        self.assertTrue(report["software_ready"])
        self.assertTrue(report["serial_available"])
        self.assertEqual(report["serial_version"], "3.5")
        self.assertEqual(report["sqlite_memory_check"], "ok")
        self.assertFalse(report["hardware_verified"])
        self.assertEqual(json.loads(json.dumps(report)), report)
        serial.Serial.assert_not_called()
        backend.comports.assert_not_called()

    def test_sqlite_failure_is_reported_as_not_ready(self):
        with patch("naseem.diagnostics.import_module", return_value=fake_serial()), \
             patch("naseem.diagnostics.sqlite3.connect", side_effect=sqlite3.OperationalError("unavailable")):
            report = doctor()
        self.assertFalse(report["software_ready"])
        self.assertEqual(report["sqlite_memory_check"], "failed")
        self.assertEqual(report["sqlite_error"], "unavailable")
        self.assertFalse(report["hardware_verified"])


if __name__ == "__main__":
    unittest.main()
