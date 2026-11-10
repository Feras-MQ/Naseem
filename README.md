# Naseem local prototype baseline

A runnable **academic software baseline**, based on the supplied *Indoor Air Quality Monitoring System with AI* report and slides. It implements local Python processing, a deterministic simulator, USB serial ingestion, SQLite journaling, explainable configurable rules, trend detection and CSV export. **No web/mobile dashboard or cloud service.**

## What is and is not complete

- **Implemented and tested locally:** JSON protocol validation, synthetic simulation, replay, Python rule engine, SQLite/CSV, serial adapter using a fake device, and firmware timing/response guard tests.
- **Scaffold only:** ESP32 acquisition and physical LCD output. The firmware intentionally sends all-null/missing readings and remains UNKNOWN. It does not initialize sensor buses, GPIO outputs or MQ-7 heaters.
- **Not verified:** real serial hardware, ESP32 compilation, any actual sensor, wiring, calibration, electrical behavior, or measurement accuracy. No firmware was flashed. No device was connected.
- **No measured experimental results are included.** Every example data row is labelled `synthetic`. Demo output is not evidence of physical performance.

**This is not a certified smoke/CO alarm, medical instrument or safety device.** NORMAL means only “the available configured signals are below illustrative rules.” It does not establish that air is safe. HIGH means a classroom threshold was exceeded, not an official hazardous-air determination. eCO2 is an estimated equivalent-CO2 signal, **not measured CO2**. MQ-7 ADC counts are raw diagnostics, never converted to ppm or used for a CO safety claim. Continue to use certified alarms. Do not create smoke, CO, hazardous gases, dust clouds or chemical exposures for testing this project.

## Quick start (no dependencies, Python 3.10+)

Run these commands from this folder in a terminal. On Windows, use `py` if `python` is not the Python 3 launcher on your machine.

```sh
python -m naseem simulate --scenario mixed --samples 72 --db demo.sqlite3 --jsonl demo_synthetic.jsonl
python -m naseem export --db demo.sqlite3 --csv demo_synthetic.csv
python -m unittest discover -s tests -v
```

The demo runs quickly using **virtual device time**, advancing 5,000 ms per record. Seventy-two records span six minutes of synthetic samples, with the final timestamp at 355 seconds. The host receive timestamps reflect actual execution, not those virtual times. Add `--realtime` to wait five seconds between records. It does not turn the data into measurements.

The mixed demo contains initial warm-up, stable signals, a rise, a high-threshold event, a missing sensor and recovery. Available scenarios: `stable`, `rising`, `high`, `missing`, `warming_up`, `mixed`. Add `--verbose` to print per-record explanations and two 16-character LCD lines. The terminal is the only desktop display.

Examples under `examples/` are pre-generated **synthetic demonstrations**, not real room data. CSV/JSONL outputs use exclusive creation: choose a new filename if it already exists. SQLite can append a new, separately identified run to the same compatible journal.

## Replay a capture

```sh
python -m naseem replay examples/SYNTHETIC_mixed.jsonl --db replay.sqlite3
```

Input must be newline-terminated UTF-8 JSON, exactly one version-1 reading per line. Replay preserves each source label and uses a separate run mode so it cannot be mistaken for live acquisition. One device and one source per run. Partial final lines, malformed/oversized JSON, duplicates, old boot IDs and out-of-order packets are rejected and journaled. A run with rejected input exits with code 1. Startup, I/O or database errors exit with code 2. Successful runs exit with code 0.

## USB serial, after hardware is confirmed

Install the optional dependency in a virtual environment using your normal Python package workflow:

```sh
python -m venv .venv
# Activate .venv for your operating system, then:
python -m pip install '.[serial]'
python -m naseem serial --port YOUR_CONFIRMED_PORT --db hardware.sqlite3 --verbose
```

Port examples are `COM3` on Windows or `/dev/ttyUSB0` on Linux, but **neither is assumed to be your device**. Select the exact port yourself; close any serial monitor using it. Default baud is 115200. Opening a serial port can reset some ESP32 boards through the USB adapter. Ctrl+C stops recording; there is no automatic reconnect or network connection. A changed port/device needs a new explicit run. `--samples 10` can bound a test run.

Hardware mode refuses packets marked `synthetic`. Source labels are provenance supplied by the device, not cryptographic attestation. Both sides must enforce timeouts: the Python adapter reports UNKNOWN after 15 seconds without a valid record; the dry firmware rejects mismatched/stale/duplicate host responses and falls back to UNKNOWN on a 15-second host timeout. A fresh packet with missing sensors is still UNKNOWN. Database commits happen before sending a success response. On an I/O/database failure the process stops; the device must honor its timeout.

## Rules and data quality

`config/illustrative_rules.json` contains the example settings, selectable with `--config`. **These numbers are invented classroom settings**, not official AQI breakpoints, health limits, calibration recommendations or validated indoor standards. The supplied report gives qualitative rules, not enough detail to justify numeric limits.

| Signal | Example WATCH | Example HIGH |
|---|---:|---:|
| PM2.5, µg/m³ | 25 | 75 |
| PM10, µg/m³ | 75 | 150 |
| TVOC indicator, ppb | 300 | 1000 |
| eCO2 estimate, ppm | 1000 | 2000 |

Threshold comparison is inclusive. Any valid measured channel reaching HIGH wins over WATCH. Missing/failed/warming sensors never produce NORMAL: if no valid channel already reaches WATCH/HIGH, the result is UNKNOWN. Data quality remains separately visible (`VALID`, `PARTIAL`, `WARMING_UP`, `MISSING`, `INVALID`) so a high reading cannot hide a missing sensor. MQ-7 `ok` means raw diagnostics are available, **not calibrated CO**; real firmware must not assert this until its heater/timing/electrical behavior is verified. An uncalibrated MQ-7 keeps quality partial. Synthetic scenarios use synthetic raw-diagnostic readiness solely to exercise every software state.

Trends use linear-regression slope over up to six samples, a minimum of four, and current value above the previous sample mean. Rates are normalized to actual device elapsed time, not PC processing speed. Default examples: PM2.5 slope ≥12 µg/m³/min and +3 above previous mean; TVOC/eCO2 slope ≥120 units/min and +30. Histories reset on reboot, invalid input, a sensor not ready, or a gap over 15 seconds. There is no trained ML model, prediction-accuracy claim or automatic intervention.

Each run stores the full rule configuration and SHA-256 hash, software version and source/mode. See [protocol](docs/PROTOCOL.md), [validation](docs/VALIDATION.md), [hardware handoff](docs/HARDWARE_HANDOFF.md) and [firmware limitations](firmware/README.md).

## Assumptions and next step

Assumptions: local desktop Python 3.10+, one ESP32 stream per run, PMS7003/SGP30/BME280/MQ-7 and 16×2 I2C LCD as named in the report. Exact board/module variants, power arrangement, OS and ports were not supplied. The Python baseline is OS-neutral and was tested here on Linux/Python 3.12.14. Firmware board `esp32dev` is a provisional compile target, not verified hardware selection.

To turn this into a real prototype, first confirm exact board and sensor module photographs/part numbers, LCD backpack voltage/controller and operating system. Then implement and verify one sensor driver at a time using the checklists. No account, cloud, dashboard, dataset download or Kaggle claim is needed for this baseline.
