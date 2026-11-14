# Validation and scope

## Source alignment

The supplied report proposes ESP32 → USB serial → Python → SQLite/rules → ESP32/LCD (software design pp.23–25), qualitative rule-based classification and trends (pp.26–28), JSON (p.31), and an academic validation plan (pp.32–34). Its tables name PMS7003, SGP30, BME280 and MQ-7. The supplied slide deck repeats this architecture and explicitly places web/mobile work in future scope.

This baseline deliberately corrects two misleading interpretations: the classroom state is called **prototype status**, not official AQI; SGP30's independent one-second IAQ cadence is separated from five-second records. MQ-7 is kept raw-only and the real driver is disabled. The report's numeric example is illustrative; it is not calibration evidence or a measured dataset. No external dataset has been downloaded or analyzed.

## Automated checks

From project root, run `python scripts/check.py`. It runs the Python tests,
four native C++ suites and sensor/display configuration checks. A GCC-compatible
C++ compiler is required (default `g++`, or set `CXX` to its executable).
The optional pyserial dependency enables the POSIX virtual-port integration test.
Without that dependency, or on Windows, that one test is explicitly skipped.

`python scripts/check.py --firmware` additionally compiles all six PlatformIO
profiles with a locally installed PlatformIO 6.1.18. It never uploads a binary.
The default profile remains dry. The two display compile fixtures use explicit
arbitrary test pins, not a proposed wiring diagram, and block PlatformIO upload
and program targets. GitHub Actions definitions run the same checks; a prepared
workflow is not evidence that a hosted CI run has passed.

Python tests cover strict JSON, duplicated keys, non-finite/negative/bool/out-of-range values, missing/null fields, SGP30 startup, uncalibrated diagnostics, threshold boundaries, incomplete-data precedence, timestamp-normalized trends, resets/gaps, LCD/response bounds, out-of-order/duplicate and old-boot replay, source separation, SQLite persistence, CSV provenance/overwrite protection, bounded framing and recovery, malformed/truncated capture exit status, fake USB round trips, stale-stream logging and complete simulate/replay/export workflow.

Firmware host C++ tests also cover the portable PMS7003 frame parser and sensor-readiness helpers. They do not instantiate the Arduino sensor libraries. Protocol tests cover elapsed timing including unsigned clock wrap and two-rollover 64-bit uptime extension, expected response sequence, duplicate/stale rejection, host timeout and allowed display/status strings. They test isolated protocol helpers, **not execution of the full Arduino firmware or real serial hardware**.

## Tested / not tested

- Python and host protocol tests: see `TEST_RESULTS.txt` for exact final run.
- Python CLI synthetic mixed scenario: 72 labelled records, 5,000 ms virtual intervals; see example summary.
- Actual USB serial device: **not tested**. In addition to fake-object unit tests, real pyserial ran through an OS pseudo-terminal; fragmented input, duplicate rejection, recovery, bounded responses and SQLite persistence passed with emulated packets.
- ESP32 toolchain compilation: **all six profiles passed**: dry, BME, BME+PMS, all three sensors, display-only fixture, and sensors+display fixture. See `TEST_RESULTS.txt` for the exact build summary. This is cross-compilation, not physical execution.
- ESP32 flashing, GPIO power, physical sensor-driver behavior, LCD output, sensor accuracy, calibration: **not performed**.
- Real-room experiment or comparison against reference instrument: **not performed**.
- Official AQI, CO detection reliability, health/safety efficacy, model accuracy: **not established**.

The next physical milestone is a verified wiring and hardware integration log. Synthetic files and compiler results do not establish measurement accuracy.

## Historical version 0.2 changes

Supplied product references informed optional PMS7003, SGP30 and BME280 adapters. Manufacturer requirements are recorded in `SENSOR_SOURCES.md`. In that release, acquisition stayed disabled by default and MQ-7/LCD implementation was deferred. No PlatformIO/Arduino installation or dependency download was performed for that update; ESP32 compilation was explicitly unverified at that time. Python contract tests additionally cover three-sensor readiness with MQ-7 absent, SGP30 mid-run reinitialization and software-version provenance.

## Version 0.3 checks

- Escaped duplicate JSON keys are logged safely and do not stop subsequent input.
- Display tests cover shortened/padded rows, redraw suppression, invalid input,
  fake sink failures and pin/wiring gates. Display startup occurs before sensors.
- Warm-up completion and PMS/host expiry remain latched across repeated 32-bit
  clock values. The SGP regression runs a full timer cycle using consecutive
  simulated samples; no real 49-day soak test has been performed.
- The source CLI and an isolated installed wheel both completed a 72-record
  synthetic mixed run: 72 accepted, 0 rejected. The export contains 72 records.
- Display upload guards were exercised with actual SCons target lists without
  invoking device discovery or an upload. Upload/program targets raised errors;
  normal build targets were allowed.

The test log states the final build results and limits explicitly. Hardware
identity, power, wiring, physical drivers, timing under real IO and calibration
remain unverified. A photo/order review is needed before selecting a display
driver or enabling physical acquisition. MQ-7 remains disabled.
