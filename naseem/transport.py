"""USB serial runner. pyserial is optional; there is no network transport."""
import json
import sys
import time
from .service import LineFramer


def wire_response(response):
    keys = ("schema_version", "type", "device_id", "boot_id", "sequence", "prototype_status", "data_quality", "lcd_line_1", "lcd_line_2")
    wire = json.dumps({k: response[k] for k in keys}, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
    if len(wire) > 511:
        raise ValueError("Response exceeds firmware buffer")
    return wire


def run_serial(port, baud, processor, limit=0, verbose=False):
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("Serial mode needs pyserial: python -m pip install '.[serial]'") from exc
    framer = LineFramer()
    last_valid = time.monotonic()
    stale_reported = False
    # No auto-reconnect: the user selects the exact device, and a disconnect stops.
    with serial.Serial(port=port, baudrate=baud, timeout=1, write_timeout=1) as device:
        while not limit or processor.accepted < limit:
            chunk = device.read(512)
            for line in framer.feed(chunk):
                before = processor.accepted
                if line is None:
                    response = processor.reject("Oversized serial frame discarded")
                else:
                    response = processor.process(line)
                device.write(wire_response(response))
                if processor.accepted > before:
                    last_valid = time.monotonic()
                    stale_reported = False
                if verbose:
                    print(json.dumps(response, ensure_ascii=True), flush=True)
            if time.monotonic() - last_valid >= 15 and not stale_reported:
                processor.engine.reset()
                processor.journal.event("stale_stream", "No valid record for 15 seconds; status UNKNOWN")
                print("UNKNOWN: no valid record for 15 seconds. Check the device; old readings are not current.", file=sys.stderr, flush=True)
                stale_reported = True
        if framer.finish():
            processor.reject("Incomplete serial frame at session end")
