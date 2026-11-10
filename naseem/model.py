"""Strict, versioned JSON-lines protocol. No carry-forward of absent readings."""
from dataclasses import dataclass
import json
import math
import re

MAX_LINE_BYTES = 4096
SENSORS = {
    "pms7003": ("pm1_ug_m3", "pm25_ug_m3", "pm10_ug_m3"),
    "sgp30": ("tvoc_ppb", "eco2_ppm"),
    "bme280": ("temperature_c", "humidity_pct", "pressure_hpa"),
    "mq7": ("mq7_adc_raw",),
}
# Transport sanity checks, NOT health thresholds or accuracy specifications.
BOUNDS = {
    "pm1_ug_m3": (0, 65535), "pm25_ug_m3": (0, 65535), "pm10_ug_m3": (0, 65535),
    "tvoc_ppb": (0, 60000), "eco2_ppm": (400, 60000),
    "temperature_c": (-40, 85), "humidity_pct": (0, 100), "pressure_hpa": (300, 1100),
    "mq7_adc_raw": (0, 4095),
}
STATUSES = {"ok", "missing", "warming_up", "error", "uncalibrated"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

class ValidationError(ValueError):
    """Malformed or unsafe-to-interpret packet."""

@dataclass(frozen=True)
class Reading:
    device_id: str
    boot_id: str
    sequence: int
    uptime_ms: int
    source: str
    sensor_status: dict
    readings: dict

    def packet(self):
        return {"schema_version": 1, "type": "reading", **self.__dict__}


def _no_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValidationError(f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def strict_json(text):
    def reject(value):
        raise ValidationError(f"Non-finite JSON constant: {value}")
    try:
        return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=reject)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValidationError(str(exc)) from exc


def parse_line(line):
    if isinstance(line, bytes):
        if len(line) > MAX_LINE_BYTES:
            raise ValidationError("Record exceeds 4096-byte limit")
        try:
            line = line.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValidationError("Invalid UTF-8") from exc
    if not isinstance(line, str) or len(line.encode("utf-8")) > MAX_LINE_BYTES:
        raise ValidationError("Record exceeds 4096-byte limit or is not text")
    obj = strict_json(line)
    expected = {"schema_version", "type", "device_id", "boot_id", "sequence", "uptime_ms", "source", "sensor_status", "readings"}
    if not isinstance(obj, dict) or set(obj) != expected:
        raise ValidationError("Expected exactly the version-1 reading fields")
    if type(obj["schema_version"]) is not int or obj["schema_version"] != 1 or obj["type"] != "reading":
        raise ValidationError("Unsupported schema_version or type")
    for key in ("device_id", "boot_id"):
        if not isinstance(obj[key], str) or not IDENTIFIER.fullmatch(obj[key]):
            raise ValidationError(f"Invalid {key}")
    for key in ("sequence", "uptime_ms"):
        if type(obj[key]) is not int or not 0 <= obj[key] <= 2**63 - 1:
            raise ValidationError(f"{key} must be a non-negative signed-64-bit integer")
    if obj["source"] not in ("hardware", "synthetic"):
        raise ValidationError("source must be hardware or synthetic")
    statuses, values = obj["sensor_status"], obj["readings"]
    if not isinstance(statuses, dict) or set(statuses) != set(SENSORS):
        raise ValidationError("All four sensor statuses are required")
    if not isinstance(values, dict) or set(values) != set(BOUNDS):
        raise ValidationError("All nine readings are required; use null for unavailable data")
    for sensor, status in statuses.items():
        if not isinstance(status, str) or status not in STATUSES:
            raise ValidationError(f"Invalid status for {sensor}")
        if status == "uncalibrated" and sensor != "mq7":
            raise ValidationError("uncalibrated applies only to MQ-7 raw diagnostics")
        for field in SENSORS[sensor]:
            value = values[field]
            if value is None:
                if status == "ok":
                    raise ValidationError(f"{field} cannot be null when {sensor} is ok")
                continue
            low, high = BOUNDS[field]
            if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
                raise ValidationError(f"{field} is outside transport sanity bounds")
            if field in ("tvoc_ppb", "eco2_ppm", "mq7_adc_raw") and type(value) is not int:
                raise ValidationError(f"{field} must be an integer")
            if status != "ok" and not (sensor == "mq7" and status == "uncalibrated"):
                raise ValidationError(f"{sensor} is {status}: its readings must be null")
    # Initial SGP30 outputs are algorithm startup defaults, not measured room conditions.
    if statuses["sgp30"] == "ok" and obj["uptime_ms"] < 15000:
        raise ValidationError("SGP30 cannot be ok during the first 15 seconds")
    return Reading(**{k: obj[k] for k in Reading.__dataclass_fields__})
