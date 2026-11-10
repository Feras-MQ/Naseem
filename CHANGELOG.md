# Changes

## 0.2.0: Optional sensor integration

- Added supplied hardware inventory and verified sensor-level technical references.
- Added bounded PMS7003 parsing/acquisition with atmospheric PM fields, checksum/error handling, warm-up and freshness gates.
- Added optional BME280 acquisition with live acknowledged identity checks, numeric bounds and Pa-to-hPa conversion.
- Added optional SGP30 acquisition with a single one-second scheduler, excluded startup outputs, range checks and recovery after failure or cadence gaps.
- Kept default firmware dry. Added independently enabled sensor flags and staged bring-up profiles, requiring an explicit wiring-verification guard.
- Kept MQ-7 and physical LCD disabled. No CO ppm, official AQI or physical-safety claims added.
- Preserved version-1 serial protocol, five-second records, 64-bit uptime and stale/duplicate host guards. Local elevated status requires every supporting pollutant sensor to remain fresh; incomplete data cannot become NORMAL.
- Added host parser/readiness/configuration tests and Python compatibility/provenance tests. Refreshed synthetic demonstration files using version 0.2.0.

No ESP32 compilation, installation, wiring, flashing, actual sensor measurements or physical validation occurred. Host tests do not establish hardware readiness.

## 0.1.0: Initial software baseline

Local Python simulator, replay/serial adapter, configurable illustrative rules/trends, SQLite/CSV, input validation, tests and dry firmware scaffold.
