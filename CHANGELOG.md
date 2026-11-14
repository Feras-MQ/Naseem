# Changes

## 0.3.0: Display candidate and repeatable verification

- Added disabled-by-default ILI9341 SPI candidate output, with explicit wiring/pin gates and padded changed-row rendering. The purchased 2.8-inch screen is still unidentified.
- Added two compile-only display environments with upload guards; default sensor and display behavior stays dry.
- Fixed escaped duplicate JSON keys crashing SQLite error logging; malformed input is rejected and the next valid packet can recover.
- Latched sensor warm-up completion and sensor/host expiry so stale state does not revive at a 32-bit timer wrap.
- Added real pyserial testing through an operating-system virtual port, a single check runner and CI build/test definitions. No physical serial device was used.
- Updated the hardware inventory and added a concise Arabic/English getting-started guide.
- See `TEST_RESULTS.txt` and `docs/VALIDATION.md` for the final verification record.

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
