"""Example thresholds only. This module does not implement an official AQI."""
import copy
import hashlib
import json
import math
from pathlib import Path
from .model import strict_json, ValidationError

DEFAULT = {
    "label": "Illustrative classroom rules v1; not health or official AQI limits",
    "record_interval_seconds": 5,
    "max_trend_gap_seconds": 15,
    "trend_window": 6,
    "trend_min_samples": 4,
    "thresholds": {
        "pm25_ug_m3": {"watch": 25, "high": 75},
        "pm10_ug_m3": {"watch": 75, "high": 150},
        "tvoc_ppb": {"watch": 300, "high": 1000},
        "eco2_ppm": {"watch": 1000, "high": 2000},
    },
    "trends": {
        "pm25_ug_m3": {"per_minute": 12, "above_previous_mean": 3},
        "tvoc_ppb": {"per_minute": 120, "above_previous_mean": 30},
        "eco2_ppm": {"per_minute": 120, "above_previous_mean": 30},
    },
}

def _positive(value):
    return type(value) in (int, float) and 0 < value <= 1_000_000_000 and math.isfinite(value)


def validate_config(config):
    if not isinstance(config, dict) or set(config) != set(DEFAULT):
        raise ValidationError("Configuration must contain exactly the documented keys")
    if not isinstance(config["label"], str) or not config["label"].strip() or len(config["label"]) > 240:
        raise ValidationError("Configuration requires a concise label")
    if type(config["record_interval_seconds"]) is not int or config["record_interval_seconds"] != 5:
        raise ValidationError("This protocol uses five-second records")
    if not _positive(config["max_trend_gap_seconds"]) or config["max_trend_gap_seconds"] < 5:
        raise ValidationError("max_trend_gap_seconds must be at least 5")
    for field in ("trend_window", "trend_min_samples"):
        if type(config[field]) is not int or not 3 <= config[field] <= 120:
            raise ValidationError(f"{field} must be an integer between 3 and 120")
    if config["trend_min_samples"] > config["trend_window"]:
        raise ValidationError("trend_min_samples cannot exceed trend_window")
    supported = set(DEFAULT["thresholds"])
    for group, keys in (("thresholds", {"watch", "high"}), ("trends", {"per_minute", "above_previous_mean"})):
        rules = config[group]
        if not isinstance(rules, dict) or not rules or not set(rules) <= supported:
            raise ValidationError(f"{group} supports only PM2.5, PM10, TVOC and eCO2")
        for field, rule in rules.items():
            if not isinstance(rule, dict) or set(rule) != keys or not all(_positive(v) for v in rule.values()):
                raise ValidationError(f"Invalid {group} rule for {field}")
            if group == "thresholds" and rule["watch"] >= rule["high"]:
                raise ValidationError(f"watch must be below high for {field}")
    return copy.deepcopy(config)


def load_config(path=None):
    return validate_config(strict_json(Path(path).read_text(encoding="utf-8")) if path else DEFAULT)


def config_json(config):
    return json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)


def config_hash(config):
    return hashlib.sha256(config_json(config).encode()).hexdigest()
