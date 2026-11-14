# Naseem software and SQLite guide

## What runs where

The ESP32 sends one newline-terminated JSON reading every five seconds over USB.
Python validates it, applies the configured explanatory rules/trends, commits it
to SQLite, then sends the bounded status/display response. Missing or invalid
signals remain visible. No trained AI model or validated accuracy result is
included; the current intelligence is an explainable rule engine.

The demo replaces the physical device with generated packets. It exercises the
same validation, rules and database code. The HTML report is a **static export**
for that synthetic run, not a live monitor. The firmware's display candidate is
separate and remains disabled until the actual panel is identified.

## Installation

Python 3.10+ supplies SQLite, so simulation, replay, reports, inspection and export
need no additional packages. Extract all project files together. You can run
`python scripts/start.py` from any working directory by giving the script's full
path. Explicit relative CLI paths are relative to your terminal's current folder;
the no-argument demo always writes under this project's `data/demos/`.

Windows:

- `Start-Naseem.cmd` with no arguments creates a fresh demo and keeps the window open.
- `Start-Naseem.cmd --help` lists commands.
- `Setup-USB.cmd` explicitly creates/reuses an isolated `.venv` and installs this
  local project with its optional pyserial dependency. Internet/package-index
  access may be needed. It does not install drivers, configure Windows or flash a board.
- Once present, the launchers use `.venv\Scripts\python.exe` automatically.

Linux/macOS optional USB setup: `python3 scripts/setup_usb.py`, then use
`.venv/bin/python scripts/start.py ports`. No shell activation is required.
If setup is interrupted, an incomplete `.venv` stays visible; investigate the
error instead of deleting unrelated folders or installing globally.

## Everyday commands

Run these from the project folder; replace `python` with `py` on Windows or use
`Start-Naseem.cmd` followed by the same command arguments.

| Task | Command |
|---|---|
| Software preflight; opens no device | `python scripts/start.py doctor` |
| New, isolated demo bundle | `python scripts/start.py demo --output data/demo-01` |
| Prepare empty recording database | `python scripts/start.py init-db --db data/hardware.sqlite3` |
| Inspect stored history | `python scripts/start.py inspect --db data/hardware.sqlite3 --limit 5` |
| Inspect one run | `python scripts/start.py inspect --db data/hardware.sqlite3 --run-id RUN_ID` |
| Back up a journal | `python scripts/start.py backup --db data/hardware.sqlite3 --output data/backups/recording-01.sqlite3` |
| CSV for all runs | `python scripts/start.py export --db data/hardware.sqlite3 --csv data/recording-01.csv` |
| CSV for one run | `python scripts/start.py export --db data/hardware.sqlite3 --csv data/run-01.csv --run-id RUN_ID` |
| Port metadata; opens no device | `python scripts/start.py ports` |
| Replay a saved capture | `python scripts/start.py replay data/demo-01/SYNTHETIC_packets.jsonl --db data/replay.sqlite3` |

`RUN_ID` is the value printed after recording or shown by `inspect`; it is not a
literal example to reuse. Exports and backups require a **new file**. Demo needs a
**new directory**. Use another output name when one already exists.

## Recording later, after hardware validation

1. Confirm the actual boards, power/logic levels and display pins using
   [the hardware handoff](HARDWARE_HANDOFF.md). Build/flash only the agreed profile.
2. Run `ports` and identify the actual device. The list is not proof of safe wiring.
3. Close Arduino/PlatformIO serial monitors so one process owns the port.
4. Start a bounded test, replacing the placeholder with the confirmed port:

   ```powershell
   .\Start-Naseem.cmd serial --port CONFIRMED_PORT --db data/hardware.sqlite3 --samples 12 --verbose
   ```

5. Remove `--samples 12` for continuous recording. Stop with Ctrl+C, then inspect,
   back up and export. A disconnect stops the run; reconnect explicitly. Opening
   some ESP32 USB ports resets the board. Warm-up must finish again after a reboot.

Hardware mode refuses synthetic packets. Device source labels are provenance,
not cryptographic proof. A high status can coexist with incomplete data. Because
MQ-7 remains disabled, the current real three-sensor setup cannot claim
NORMAL/VALID; it may report UNKNOWN/PARTIAL or WATCH/HIGH with partial quality.
Do not mistake that expected behavior for a wiring fault.

## Database design

SQLite application ID is `0x4E415345`; database schema version stays **1**.
The new software accepts compatible existing journals without migrating them.
`init-db` creates tables and indexes atomically, with no fake runs or readings.
An incompatible, incomplete or future-version database is rejected, not reset.

| Table | What it records |
|---|---|
| `runs` | Run ID, start/end UTC, mode, exact configuration JSON/hash, software version and interpretation notice |
| `records` | Device/boot/sequence, device uptime, host receive UTC, source, status, data quality, readings, sensor states, reasons, trends and original JSON |
| `events` | Rejected frames, stale streams and other session events, with bounded diagnostic text |

Foreign keys link records/events to a run. A unique constraint protects duplicate
(run, device, boot, sequence) entries. Each accepted record is committed before
Python sends a success response. Missing readings use JSON `null`, never fabricated
zeroes. CSV includes source, mode, quality, units in field names and rule hash.

`inspect` is read-only, verifies SQLite integrity and run references, and returns
at most 100 recent runs/records/events per list (default 10), with counts across
the selected history. An unclosed run may be active **or interrupted**. The newest
stored reading is still history; inspection does not establish current air status.

`backup` uses SQLite's backup API, including committed data in a WAL sidecar, and
checks the copied database. Use it instead of copying only `.sqlite3` while a
writer is active. Destinations are exclusive and cannot replace the source.
To restore, stop recording first and point future commands at the chosen backup;
keep the old journal until you have checked the restored history.

## Demo files and troubleshooting

Every complete demo contains:

- `report.html`: offline charts, timeline, provenance and per-record explanations.
- `SYNTHETIC_demo.sqlite3`: one closed run and 72 synthetic records.
- `SYNTHETIC_packets.jsonl`: newline-terminated input, suitable for replay.
- `SYNTHETIC_records.csv`: the same 72 records with labels/quality.
- `summary.json`: counts, configuration, version, file list and provenance.

The first sample has virtual uptime 0 seconds and the last 355 seconds, at
five-second spacing. Host UTC timestamps show fast execution, not six minutes of
real collection. An `INCOMPLETE.txt` marker means generation failed or was
interrupted; preserve it for troubleshooting and retry into a new folder.

| Symptom | Next step |
|---|---|
| Python not found | Install Python 3.10+ and reopen the launcher |
| USB dependency missing | Run the explicit optional Setup-USB helper |
| No ports listed | Check USB cable/driver/Device Manager; don't guess a port |
| Port busy or access denied | Close other serial software and verify the selected port |
| Database incompatible | Check the path; preserve the file and choose a new journal |
| Output already exists | Choose a new output filename/folder |
| UNKNOWN / partial quality | Read sensor states and reasons; expected for warm-up or missing MQ-7 |
| Stale stream | Check serial/power; old saved readings are not current |

## Verification and remaining work

Run `python -m unittest discover -s tests -v` for Python tests. Full developer
checks use `python scripts/check.py` and require a GCC-compatible C++ compiler.
`--firmware` additionally requires PlatformIO 6.1.18; it compiles, never uploads.
The virtual serial test runs on POSIX with pyserial and is explicitly skipped on
Windows. See TEST_RESULTS.txt and the corresponding CI run for actual results.

Still physical work: delivered board/panel identification, electrical checks,
staged sensor and display bring-up, USB disconnect/reboot tests on the ESP32,
and reference-based calibration/measurement evaluation. MQ-7 heater control and
CO calibration remain unimplemented; no software-only result can validate those.
