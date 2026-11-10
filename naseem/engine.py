"""Explainable classroom rules; observed signals never prove that air is safe."""
from collections import deque
from dataclasses import dataclass, asdict
from .model import SENSORS

FIELD_SENSOR = {field: sensor for sensor, fields in SENSORS.items() for field in fields}

@dataclass(frozen=True)
class Result:
    prototype_status: str
    data_quality: str
    reasons: list
    trends: dict
    lcd_line_1: str
    lcd_line_2: str

    def response(self, reading=None):
        return {"schema_version": 1, "type": "status",
                "device_id": reading.device_id if reading else None,
                "boot_id": reading.boot_id if reading else None,
                "sequence": reading.sequence if reading else None,
                **asdict(self)}


def invalid_result(reason):
    return Result("UNKNOWN", "INVALID", [reason], {}, "PROTOTYPE:CHECK", "INVALID DATA")


def unknown_result(reason):
    return Result("UNKNOWN", "MISSING", [reason], {}, "PROTOTYPE:CHECK", "NO FRESH DATA")


class RuleEngine:
    def __init__(self, config):
        self.config = config
        self.history = {}
        self.last_device_boot = None

    def reset(self):
        self.history.clear()
        self.last_device_boot = None

    def evaluate(self, reading):
        identity = (reading.device_id, reading.boot_id)
        if identity != self.last_device_boot:
            self.reset()
            self.last_device_boot = identity
        reasons, trends = [], {}
        statuses = reading.sensor_status
        bad = {k: v for k, v in statuses.items() if v != "ok"}
        if not bad:
            quality = "VALID"
        elif "error" in bad.values():
            quality = "PARTIAL"
        elif "warming_up" in bad.values():
            quality = "WARMING_UP"
        elif len(bad) == len(SENSORS) and all(v == "missing" for v in bad.values()):
            quality = "MISSING"
        else:
            quality = "PARTIAL"
        reasons.extend(f"{sensor}: {status}; unavailable for classification" for sensor, status in bad.items())
        rank = 0
        for field, limits in self.config["thresholds"].items():
            if statuses[FIELD_SENSOR[field]] != "ok":
                continue
            value = reading.readings[field]
            if value >= limits["high"]:
                rank = 2
                reasons.append(f"{field}={value:g} reaches illustrative HIGH threshold {limits['high']:g}")
            elif value >= limits["watch"]:
                rank = max(rank, 1)
                reasons.append(f"{field}={value:g} reaches illustrative WATCH threshold {limits['watch']:g}")
        now = reading.uptime_ms
        for field, limits in self.config["trends"].items():
            history = self.history.setdefault(field, deque(maxlen=self.config["trend_window"]))
            if statuses[FIELD_SENSOR[field]] != "ok":
                history.clear()
                continue
            if history and (now <= history[-1][0] or now - history[-1][0] > self.config["max_trend_gap_seconds"] * 1000):
                history.clear()
            history.append((now, reading.readings[field]))
            if len(history) < self.config["trend_min_samples"]:
                continue
            # OLS slope uses elapsed device time, never processing speed or sample index.
            xs = [(t - history[0][0]) / 1000 for t, _ in history]
            ys = [v for _, v in history]
            xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
            denom = sum((x - xm) ** 2 for x in xs)
            slope = 60 * sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / denom
            previous_mean = sum(ys[:-1]) / (len(ys) - 1)
            trends[field] = {"slope_per_minute": round(slope, 6), "previous_mean": round(previous_mean, 6), "samples": len(ys)}
            if slope >= limits["per_minute"] and ys[-1] - previous_mean >= limits["above_previous_mean"]:
                rank = max(rank, 1)
                reasons.append(f"{field} rising {slope:.1f}/min above recent mean; illustrative trend rule")
        status = "HIGH" if rank == 2 else "WATCH" if rank == 1 else "UNKNOWN" if bad else "NORMAL"
        if not reasons:
            reasons.append("Configured signals below illustrative thresholds; this does not establish air safety")
        reasons.append("MQ-7 raw signal is diagnostic only; no CO concentration or CO safety conclusion")
        line1 = {"NORMAL": "PROTO:NORMAL", "WATCH": "PROTOTYPE:WATCH", "HIGH": "PROTOTYPE:HIGH", "UNKNOWN": "PROTOTYPE:CHECK"}[status]
        line2 = "CHECK SENSORS" if bad else "DEMO RULES ONLY"
        return Result(status, quality, reasons, trends, line1, line2)
