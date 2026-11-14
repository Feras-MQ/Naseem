"""Explicit optional USB dependency setup, confined to this project's .venv."""
import argparse
import json
from pathlib import Path
import subprocess
import stat
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def environment_python(environment):
    return environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def verify_environment(environment):
    """Refuse a foreign directory, a shared site-packages env, or a system Python."""
    # Python 3.10 has no Path.is_junction(), but Windows marks junctions and
    # symlinks as reparse points. Never install through either kind of link.
    attributes = getattr(environment.lstat(), "st_file_attributes", 0)
    reparse_point = bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    if reparse_point or environment.is_symlink() or not environment.is_dir():
        raise RuntimeError(f"Refusing to modify a linked or non-directory environment: {environment}")
    config = environment / "pyvenv.cfg"
    if not config.is_file():
        raise RuntimeError(f"Existing {environment} is not a Python virtual environment; nothing was replaced")
    settings = {}
    for line in config.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            settings[key.strip().lower()] = value.strip().lower()
    if settings.get("include-system-site-packages") != "false":
        raise RuntimeError("Use an isolated .venv with include-system-site-packages = false")
    interpreter = environment_python(environment)
    if not interpreter.is_file():
        raise RuntimeError(f"Virtual-environment Python is missing: {interpreter}")
    probe = subprocess.run(
        [str(interpreter), "-I", "-c", "import json,sys; print(json.dumps({'prefix':sys.prefix,'base_prefix':sys.base_prefix,'version':list(sys.version_info[:3])}))"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    try:
        info = json.loads(probe.stdout)
        valid = (Path(info["prefix"]).resolve() == environment.resolve()
                 and Path(info["base_prefix"]).resolve() != environment.resolve()
                 and tuple(info["version"]) >= (3, 10))
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Could not validate the existing virtual environment") from exc
    if not valid:
        raise RuntimeError("Refusing to install: .venv does not identify itself as this project's isolated Python 3.10+ environment")
    return interpreter


def setup(root=ROOT):
    root = Path(root).resolve()
    if sys.version_info < (3, 10):
        raise RuntimeError("Install Python 3.10 or newer before running USB setup")
    if not (root / "pyproject.toml").is_file():
        raise RuntimeError("Project metadata is missing; extract the complete Naseem folder first")
    environment = root / ".venv"
    if not environment.exists() and not environment.is_symlink():
        # Exclusive creation prevents the builder overwriting an existing directory.
        environment.mkdir()
        print(f"Creating isolated Python environment: {environment}", flush=True)
        venv.EnvBuilder(with_pip=True, system_site_packages=False, clear=False).create(environment)
    interpreter = verify_environment(environment)
    print("Installing Naseem and its optional pyserial dependency into .venv only.", flush=True)
    print("This step may download packages from the configured Python package index; it does not connect to an ESP32.", flush=True)
    subprocess.run([str(interpreter), "-I", "-m", "pip", "--isolated", "--require-virtualenv",
                    "--disable-pip-version-check", "--no-input", "install", str(root) + "[serial]"],
                   cwd=root, check=True)
    print("USB software ready. Run Start-Naseem.cmd ports to list ports without opening them.")
    print("Select a port explicitly only after the board and wiring are confirmed.")
    return 0


def main(argv=None):
    # Windows redirects commonly default to a legacy code page. Keep paths and
    # machine-readable output UTF-8 even when stdout/stderr are captured.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        return setup()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"USB setup stopped: {exc}\nNo global Python or device settings were changed. Any incomplete .venv is left in place for inspection.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
