"""Deterministic SYNTHETIC signals. Values here are not measured experiment results."""
from .model import BOUNDS
SCENARIOS = ("stable", "rising", "high", "missing", "warming_up", "mixed")


def make_packet(index, scenario="mixed", boot_id="synthetic-demo"):
    seconds = index * 5
    values = {"pm1_ug_m3": 5.0, "pm25_ug_m3": 8.0, "pm10_ug_m3": 15.0,
              "tvoc_ppb": 100, "eco2_ppm": 500, "temperature_c": 24.0,
              "humidity_pct": 45.0, "pressure_hpa": 1013.0, "mq7_adc_raw": 420}
    statuses = {"pms7003": "ok", "sgp30": "ok", "bme280": "ok", "mq7": "ok"}
    phase = scenario
    if scenario == "mixed":
        phase = "stable" if seconds < 90 else "rising" if seconds < 150 else "high" if seconds < 180 else "missing" if seconds < 210 else "stable"
    if phase == "rising" and seconds >= 30:
        step = max(0, (seconds - (90 if scenario == "mixed" else 30)) / 5)
        values["pm25_ug_m3"] += 1.5 * step
        values["pm10_ug_m3"] += 2 * step
        values["pm1_ug_m3"] += step
        values["tvoc_ppb"] += int(15 * step)
        values["eco2_ppm"] += int(20 * step)
    if phase == "high" and seconds >= 30:
        values.update(pm25_ug_m3=85.0, pm10_ug_m3=160.0, tvoc_ppb=1100, eco2_ppm=2100)
    if phase == "missing" and seconds >= 30:
        statuses["pms7003"] = "missing"
        for key in ("pm1_ug_m3", "pm25_ug_m3", "pm10_ug_m3"):
            values[key] = None
    # Independent hypothetical sensor readiness. Physical warm-up must be verified.
    if seconds < 30 or phase == "warming_up":
        statuses["pms7003"] = "warming_up"
        for key in ("pm1_ug_m3", "pm25_ug_m3", "pm10_ug_m3"):
            values[key] = None
    if seconds < 15 or phase == "warming_up":
        statuses["sgp30"] = "warming_up"
        values["tvoc_ppb"] = values["eco2_ppm"] = None
    return {"schema_version": 1, "type": "reading", "device_id": "SYNTHETIC-NOT-HARDWARE",
            "boot_id": boot_id, "sequence": index, "uptime_ms": seconds * 1000,
            "source": "synthetic", "sensor_status": statuses, "readings": values}
