"""Host preprocessor checks only, not an ESP32 firmware build."""
from pathlib import Path
import subprocess
import unittest

INCLUDE = Path(__file__).resolve().parents[1] / "include"
FLAGS = ["NASEEM_ENABLE_BME280", "NASEEM_ENABLE_PMS7003", "NASEEM_ENABLE_SGP30"]

class SensorConfig(unittest.TestCase):
    def preprocess(self, *definitions):
        return subprocess.run(
            ["g++", "-E", "-x", "c++", f"-I{INCLUDE}",
             *[f"-D{value}" for value in definitions], "-"],
            input='#include "sensor_config.h"\n', text=True,
            capture_output=True).returncode

    def test_default_and_verified_combinations(self):
        self.assertEqual(self.preprocess(), 0)
        for mask in range(8):
            definitions = [f"{flag}={(mask >> i) & 1}" for i, flag in enumerate(FLAGS)]
            self.assertEqual(self.preprocess("NASEEM_VERIFIED_WIRING=1", *definitions), 0)

    def test_unverified_enables_rejected(self):
        for flag in FLAGS:
            self.assertNotEqual(self.preprocess(f"{flag}=1"), 0)

    def test_non_boolean_flags_rejected(self):
        for flag in ["NASEEM_VERIFIED_WIRING", *FLAGS]:
            self.assertNotEqual(self.preprocess(f"{flag}=2"), 0)

if __name__ == "__main__":
    unittest.main()
