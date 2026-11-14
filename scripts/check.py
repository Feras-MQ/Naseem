"""Repeatable software checks; never opens a physical serial port or uploads firmware."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    print("+ " + " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware", action="store_true", help="Also cross-compile all declared ESP32 profiles using installed PlatformIO")
    args = parser.parse_args()
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise RuntimeError("Host firmware tests require g++ (or CXX set to a compatible compiler)")
    with tempfile.TemporaryDirectory(prefix="naseem-check-") as tmp:
        for source in sorted((ROOT / "firmware/test").glob("test_*.cpp")):
            executable = Path(tmp) / (source.stem + (".exe" if os.name == "nt" else ""))
            run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-Ifirmware/include", source, "-o", executable])
            run([executable])
    for source in sorted((ROOT / "firmware/test").glob("test_*.py")):
        run([sys.executable, source])
    if args.firmware:
        pio = shutil.which("pio")
        if not pio:
            raise RuntimeError("Install PlatformIO 6.1.18 into your development environment first")
        # Explicit targets from config, including compile-only display fixtures.
        import configparser
        config = configparser.ConfigParser(interpolation=None)
        config.read(ROOT / "firmware/platformio.ini")
        command = [pio, "run", "-d", "firmware", "-j", "4"]
        for section in config.sections():
            if section.startswith("env:"):
                command.extend(["-e", section[4:]])
        run(command)
    print("Software checks passed. Physical wiring, sensors and display are not verified.")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError, OSError) as exc:
        print(f"Check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
