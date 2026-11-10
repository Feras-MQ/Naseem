# Validation and scope

## Source alignment

The supplied report proposes ESP32 → USB serial → Python → SQLite/rules → ESP32/LCD (software design pp.23–25), qualitative rule-based classification and trends (pp.26–28), JSON (p.31), and an academic validation plan (pp.32–34). Its tables name PMS7003, SGP30, BME280 and MQ-7. The supplied slide deck repeats this architecture and explicitly places web/mobile work in future scope.

This baseline deliberately corrects two misleading interpretations: the classroom state is called **prototype status**, not official AQI; SGP30's independent one-second IAQ cadence is separated from five-second records. MQ-7 is kept raw-only and the real driver is disabled. The report's numeric example is illustrative; it is not calibration evidence or a measured dataset. No external dataset has been downloaded or analyzed.

## Automated checks

From project root:

```sh
python -m unittest discover -s tests -v
python -m compileall -q naseem tests
c++ -std=c++11 -Wall -Wextra -Werror -Ifirmware/include firmware/test/test_protocol_guard.cpp -o /tmp/naseem_protocol_guard_test
/tmp/naseem_protocol_guard_test
```

Python tests cover strict JSON, duplicated keys, non-finite/negative/bool/out-of-range values, missing/null fields, SGP30 startup, uncalibrated diagnostics, threshold boundaries, incomplete-data precedence, timestamp-normalized trends, resets/gaps, LCD/response bounds, out-of-order/duplicate and old-boot replay, source separation, SQLite persistence, CSV provenance/overwrite protection, bounded framing and recovery, malformed/truncated capture exit status, fake USB round trips, stale-stream logging and complete simulate/replay/export workflow.

Firmware host C++ tests cover elapsed timing including unsigned clock wrap and two-rollover 64-bit uptime extension, expected response sequence, duplicate/stale rejection, host timeout and allowed display/status strings. They test isolated protocol helpers, **not the full Arduino build or real serial hardware**.

## Tested / not tested

- Python and host protocol tests: see `TEST_RESULTS.txt` for exact final run.
- Python CLI synthetic mixed scenario: 72 labelled records, 5,000 ms virtual intervals; see example summary.
- Actual USB serial device: **not tested**. The serial adapter was exercised using a fake serial object.
- ESP32 toolchain compilation: **not run**; PlatformIO/arduino-cli are not installed here.
- ESP32 flashing, GPIO power, sensor drivers, LCD output, sensor accuracy, calibration: **not performed**.
- Real-room experiment or comparison against reference instrument: **not performed**.
- Official AQI, CO detection reliability, health/safety efficacy, model accuracy: **not established**.

The next defensible project result is a verified hardware integration log, not a claim of experimental success based on the synthetic files.
