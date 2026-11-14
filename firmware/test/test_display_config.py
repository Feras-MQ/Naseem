"""Compile display configuration guards; no board or display is connected."""
from pathlib import Path
import os
import subprocess
import unittest

INCLUDE = Path(__file__).resolve().parents[1] / "include"
# Compiler fixtures only. These are not wiring instructions for a real board.
PINS = {
    "NASEEM_TFT_SCK_PIN": 18, "NASEEM_TFT_MOSI_PIN": 23,
    "NASEEM_TFT_CS_PIN": 25, "NASEEM_TFT_DC_PIN": 26,
    "NASEEM_TFT_RST_PIN": 27,
}
BASE = {"NASEEM_ENABLE_ILI9341": 1, "NASEEM_VERIFIED_DISPLAY_WIRING": 1, **PINS}


class DisplayConfig(unittest.TestCase):
    def compile(self, definitions):
        return subprocess.run(
            [os.environ.get("CXX", "g++"), "-std=c++11", "-fsyntax-only", "-x", "c++", f"-I{INCLUDE}",
             *[f"-D{key}={value}" for key, value in definitions.items()], "-"],
            input='#include "display_config.h"\n', text=True,
            capture_output=True).returncode

    def test_default_has_no_required_pins(self):
        self.assertEqual(self.compile({}), 0)
        self.assertEqual(self.compile({"NASEEM_VERIFIED_DISPLAY_WIRING": 1}), 0)

    def test_verified_fixture_and_optional_reset(self):
        self.assertEqual(self.compile(BASE), 0)
        self.assertEqual(self.compile({**BASE, "NASEEM_TFT_RST_PIN": -1}), 0)

    def test_unverified_or_missing_pin_is_rejected(self):
        self.assertNotEqual(self.compile({**BASE, "NASEEM_VERIFIED_DISPLAY_WIRING": 0}), 0)
        for pin in PINS:
            with self.subTest(pin=pin):
                self.assertNotEqual(self.compile({k: v for k, v in BASE.items() if k != pin}), 0)

    def test_flags_require_boolean_values(self):
        for key in ("NASEEM_ENABLE_ILI9341", "NASEEM_VERIFIED_DISPLAY_WIRING"):
            for value in (-1, 2):
                self.assertNotEqual(self.compile({**BASE, key: value}), 0)

    def test_all_pin_collisions_are_rejected(self):
        names = list(PINS)
        for i, pin in enumerate(names):
            for other in names[i + 1:]:
                with self.subTest(pin=pin, other=other):
                    self.assertNotEqual(self.compile({**BASE, pin: PINS[other]}), 0)

    def test_invalid_output_pins_are_rejected(self):
        for pin in PINS:
            for value in (-2, 0, 1, 2, 3, 5, 6, 11, 12, 15, 16, 17, 20, 24, 28, 31, 34, 39, 40):
                with self.subTest(pin=pin, value=value):
                    self.assertNotEqual(self.compile({**BASE, pin: value}), 0)

    def test_enabled_sensor_conflicts_are_rejected(self):
        for sensor in ("NASEEM_ENABLE_BME280", "NASEEM_ENABLE_SGP30"):
            config = {**BASE, "NASEEM_VERIFIED_WIRING": 1, sensor: 1}
            self.assertEqual(self.compile(config), 0)
            for pin in PINS:
                for i2c_pin in (21, 22):
                    self.assertNotEqual(self.compile({**config, pin: i2c_pin}), 0)
        # Also check overridden UART pins, not just default GPIO16/17.
        config = {**BASE, "NASEEM_VERIFIED_WIRING": 1,
                  "NASEEM_ENABLE_PMS7003": 1,
                  "NASEEM_PMS_RX_PIN": 19, "NASEEM_PMS_TX_PIN": 32}
        self.assertEqual(self.compile(config), 0)
        for pin in PINS:
            for uart_pin in (19, 32):
                self.assertNotEqual(self.compile({**config, pin: uart_pin}), 0)

    def test_nonclassic_arduino_target_is_rejected(self):
        self.assertNotEqual(self.compile({**BASE, "ARDUINO": 10819}), 0)
        self.assertNotEqual(self.compile({**BASE, "ARDUINO": 10819, "CONFIG_IDF_TARGET_ESP32": 0}), 0)
        self.assertEqual(self.compile({**BASE, "ARDUINO": 10819, "CONFIG_IDF_TARGET_ESP32": 1}), 0)


if __name__ == "__main__":
    unittest.main()
