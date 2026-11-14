"""Local software preflight; never opens a serial device or changes machine settings."""
from importlib import import_module
import platform
import re
import sqlite3
import sys

from . import __version__

SERIAL_INSTALL_HINT = "Install USB support with: python -m pip install '.[serial]'"


def _load_serial():
    try:
        module = import_module("serial")
    except ImportError as exc:
        raise RuntimeError(f"USB serial support requires pyserial. {SERIAL_INSTALL_HINT}") from exc
    if not callable(getattr(module, "Serial", None)):
        raise RuntimeError(f"The installed 'serial' module is not usable pyserial. {SERIAL_INSTALL_HINT}")
    return module


def _text(value):
    return None if value is None else str(value)


def _usb_id(value):
    return value if type(value) is int and 0 <= value <= 0xFFFF else None


def _port_key(port):
    # Natural ordering keeps COM2 before COM10. The final full name breaks case ties.
    device = port["device"]
    return ([int(part) if index % 2 else part.casefold()
             for index, part in enumerate(re.split(r"([0-9]+)", device))], device)


def list_ports():
    """Return discovered port metadata without connecting, probing or choosing a device.

    An empty list means enumeration found no ports, not that a sensor failed.
    VID/PID and product descriptions do not verify an ESP32's identity or wiring.
    """
    _load_serial()
    try:
        port_module = import_module("serial.tools.list_ports")
        ports = port_module.comports()
        result = []
        for port in ports:
            device = _text(getattr(port, "device", None))
            if not device:
                continue
            result.append({
                "device": device,
                "description": _text(getattr(port, "description", None)),
                "hwid": _text(getattr(port, "hwid", None)),
                "vid": _usb_id(getattr(port, "vid", None)),
                "pid": _usb_id(getattr(port, "pid", None)),
                "serial_number": _text(getattr(port, "serial_number", None)),
                "manufacturer": _text(getattr(port, "manufacturer", None)),
                "product": _text(getattr(port, "product", None)),
                "location": _text(getattr(port, "location", None)),
            })
        return sorted(result, key=_port_key)
    except (ImportError, OSError) as exc:
        raise RuntimeError(f"Could not enumerate serial ports: {exc}. No port was opened.") from exc


def doctor():
    """Check this interpreter and an in-memory SQLite transaction, with no hardware I/O.

    Serial support is optional. The simulator/database workflows work without it.
    A successful report is not validation of drivers, permissions, wiring or sensors.
    """
    report = {
        "software_version": __version__,
        "python_version": platform.python_version(),
        "python_supported": sys.version_info[:2] >= (3, 10),
        "platform": platform.system(),
        "sqlite_version": sqlite3.sqlite_version,
        "sqlite_memory_check": "failed",
        "serial_available": False,
        "serial_version": None,
        "hardware_verified": False,
        "notes": [
            "No serial port was opened or enumerated; no files or settings were changed.",
            "Simulation and database workflows do not require pyserial.",
            "Port drivers, access permissions, delivered parts and wiring still need verification.",
        ],
    }
    connection = None
    try:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE preflight (value INTEGER NOT NULL)")
        connection.execute("INSERT INTO preflight VALUES (?)", (1,))
        connection.commit()
        value = connection.execute("SELECT value FROM preflight").fetchone()
        integrity = connection.execute("PRAGMA quick_check").fetchone()
        if value == (1,) and integrity == ("ok",):
            report["sqlite_memory_check"] = "ok"
        else:
            report["sqlite_error"] = "In-memory SQLite read/write or integrity check failed"
    except sqlite3.Error as exc:
        report["sqlite_error"] = str(exc)
    finally:
        if connection is not None:
            connection.close()
    try:
        serial = _load_serial()
        report["serial_available"] = True
        report["serial_version"] = _text(getattr(serial, "VERSION", None))
    except RuntimeError as exc:
        report["serial_setup"] = str(exc)
    report["software_ready"] = report["python_supported"] and report["sqlite_memory_check"] == "ok"
    return report
