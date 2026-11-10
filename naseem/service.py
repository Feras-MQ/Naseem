"""Single-stream processing with fail-closed freshness and ordering checks."""
import json
from .engine import RuleEngine, invalid_result
from .model import parse_line, ValidationError, MAX_LINE_BYTES


class Processor:
    def __init__(self, journal, config, expected_source=None):
        self.journal = journal
        self.engine = RuleEngine(config)
        self.expected_source = expected_source
        self.last = None
        self.seen_boots = set()
        self.accepted = 0
        self.rejected = 0

    def reject(self, reason, raw=None, reading=None):
        self.engine.reset()
        self.journal.event("invalid_record", reason, raw)
        self.rejected += 1
        return invalid_result(reason).response(reading)

    def process(self, line):
        raw = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
        reading = None
        try:
            reading = parse_line(line)
            if self.expected_source and reading.source != self.expected_source:
                raise ValidationError(f"This input requires source={self.expected_source}; synthetic data cannot enter hardware mode")
            if self.last:
                if reading.device_id != self.last.device_id:
                    raise ValidationError("One device per run; start a new run for another device")
                if reading.source != self.last.source:
                    raise ValidationError("Mixed hardware and synthetic data requires separate runs")
                if reading.boot_id == self.last.boot_id:
                    if reading.sequence <= self.last.sequence or reading.uptime_ms <= self.last.uptime_ms:
                        raise ValidationError("Duplicate or out-of-order sequence/uptime")
                elif reading.boot_id in self.seen_boots:
                    raise ValidationError("Replayed old boot_id; generate a new ID on each boot")
                if reading.boot_id != self.last.boot_id and len(self.seen_boots) >= 1024:
                    raise ValidationError("Boot tracking limit reached; start a new run")
            result = self.engine.evaluate(reading)
        except ValidationError as exc:
            return self.reject(str(exc), raw, reading)
        # Commit first: do not report success to the ESP32 if persistence failed.
        self.journal.save(reading, result, raw)
        self.last = reading
        self.seen_boots.add(reading.boot_id)
        self.accepted += 1
        return result.response(reading)


class LineFramer:
    """Streaming newline decoder; oversized frames are dropped up to the next LF."""
    def __init__(self):
        self.buffer = bytearray()
        self.overflow = False

    def feed(self, data):
        result = []
        for byte in data:
            if byte == 10:
                if self.overflow:
                    result.append(None)
                elif self.buffer:
                    result.append(bytes(self.buffer).rstrip(b"\r"))
                self.buffer.clear()
                self.overflow = False
            elif not self.overflow:
                self.buffer.append(byte)
                if len(self.buffer) > MAX_LINE_BYTES:
                    self.buffer.clear()
                    self.overflow = True
        return result

    def finish(self):
        """EOF with a partial frame is rejected, never interpreted as complete."""
        partial = bool(self.buffer) or self.overflow
        self.buffer.clear()
        self.overflow = False
        return partial
