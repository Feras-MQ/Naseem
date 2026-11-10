# Version-1 local serial protocol

115200 baud by default, UTF-8 JSON, one newline per object. Input maximum 4096 bytes; oversized input is discarded through the next newline and logged. No serial debug prose on this stream. Both sides use bounded buffers. The physical firmware has a 512-byte reply buffer; the host sends a compact reply excluding long explanations/trend details (these remain in SQLite and verbose terminal output).

## ESP32 → Python

Every packet includes exactly these keys. Missing values are JSON `null`, never zero, stale carry-forward values, NaN or Infinity.

```json
{
  "schema_version": 1,
  "type": "reading",
  "device_id": "esp32-naseem",
  "boot_id": "new-id-for-each-boot",
  "sequence": 0,
  "uptime_ms": 0,
  "source": "hardware",
  "sensor_status": {
    "pms7003": "missing", "sgp30": "missing",
    "bme280": "missing", "mq7": "missing"
  },
  "readings": {
    "pm1_ug_m3": null, "pm25_ug_m3": null, "pm10_ug_m3": null,
    "tvoc_ppb": null, "eco2_ppm": null, "temperature_c": null,
    "humidity_pct": null, "pressure_hpa": null, "mq7_adc_raw": null
  }
}
```

`device_id`/`boot_id`: 1–64 ASCII letters, digits, underscore, dot, colon or hyphen. `sequence` and `uptime_ms` are nonnegative integers up to signed 64-bit. Sequence and uptime must strictly increase within a boot; boot IDs must change after reset and cannot revert within a run. One device/source per run. The ESP32 scaffold extends 32-bit `millis()` into a 64-bit uptime accumulator, sampled every loop, so normal clock wrap (~49.7 days) does not reset wire time. This assumes the loop samples at least once within each complete 32-bit period. Sequence exhaustion still requires restart with a new boot ID. Long-duration hardware behavior is not physically validated.

`source`: `hardware` or `synthetic`, preserved in all records and exports. Hardware serial mode refuses `synthetic`. Replay is a distinct run mode even when source is `hardware`.

Sensor status is `ok`, `warming_up`, `missing` or `error`; MQ-7 also accepts `uncalibrated` with an optional raw ADC diagnostic. Every `ok` sensor must supply all its numeric fields. Other statuses require nulls, except MQ-7 uncalibrated raw diagnostics. Firmware must report individual sensor failure without reusing the previous measurement.

Transport sanity limits are in `naseem/model.py`. They screen numeric form and broad bounds only, **not** sensor accuracy/health or physical calibration. TVOC/eCO2/ADC counts must be integers. SGP30 cannot be `ok` during the first 15 seconds of device uptime. A real driver must enforce warm-up after every IAQ reinitialization and missed cadence as well; the host cannot infer sensor reinitialization from uptime alone.

Use the PMS7003 atmospheric-environment mass concentration fields for ambient observations; do not interchange them with its CF=1 factory-reference fields. Record this field selection in actual experiments. No `co_ppm` input is supported.

## Python → ESP32

```json
{"schema_version":1,"type":"status","device_id":"esp32-naseem","boot_id":"new-id-for-each-boot","sequence":0,"prototype_status":"UNKNOWN","data_quality":"MISSING","lcd_line_1":"PROTOTYPE:CHECK","lcd_line_2":"CHECK SENSORS"}
```

Reply echoes device/boot/sequence; firmware must accept only the newest outstanding packet, once, within five seconds. Reject a mismatched device/boot/sequence and any invalid status or LCD text. LCD lines are printable ASCII, at most 16 characters. Do not display NORMAL if locally missing/warming/error sensors disagree with the host. Dry scaffold accepts only UNKNOWN/MISSING and renders its own non-reassuring text.

Malformed frames without usable identity receive an UNKNOWN/INVALID reply with null identifiers. Firmware ignores these uncorrelated replies and independently times out. Complete but invalid packets may receive correlated UNKNOWN/INVALID responses; the dry scaffold's local missing-state gate remains conservative.

## Timing and storage

SGP30 needs independent **one-second IAQ measurement cadence**. That is not the same as **five-second serial/database records**. The code has separate firmware scheduling hooks; actual acquisition is not implemented. Do not run SGP30 only when writing a record. Initial ~15-second algorithm defaults must not be interpreted as room readings. Further conditioning and baseline handling depend on the verified vendor instructions/module history.

SQLite tables:
- `runs`: start/end UTC, mode, software version, full rule configuration/hash, disclaimer.
- `records`: receipt UTC, device/boot/sequence/uptime/source, original JSON, sensor values/statuses, rule state, data quality, reasons and trend details.
- `events`: malformed/rejected/stale/stopped input with bounded raw excerpt when applicable.

No missing data interpolation. Record receipt UTC is the host clock; uptime is device time. Neither establishes a trustworthy wall-clock measurement timestamp by itself. No timezone conversion or backdated fake measurements. Runs are separate; trend state deliberately does not survive a host restart. CSV carries source/mode/quality/hash; textual formula prefixes are escaped for safer spreadsheet opening. CSV is a convenience export, while the database retains full provenance and raw input.
