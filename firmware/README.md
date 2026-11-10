# Naseem ESP32 dry firmware scaffold

**NOT hardware tested. NOT a safety device.** This is a compile-oriented Arduino
starting point for an academic prototype, not completed sensor firmware. It must
not be used to decide whether a room is safe, detect dangerous gas, or replace
certified alarms. No hardware has been wired, flashed, or exercised.

## What this version does

- Emits bounded, newline-delimited schema-v1 JSON over USB serial at 115200 baud,
  on boot and about every five seconds. `source: "hardware"` identifies the device
  transport, **not a claim that measurements exist**. Every sensor is `missing`
  and every reading is JSON `null`; it never fabricates clean-air values.
- Parses bounded host responses (maximum 511 bytes before newline), rejecting
  malformed fields, wrong device/boot IDs, unknown enums, stale sequences,
  duplicates, replies older than five seconds, and non-printable/overlength LCD
  lines. An oversized line is discarded through its newline.
- Accepts only `UNKNOWN` + `MISSING` in this dry build. Host text cannot override
  the local missing-sensor gate. Internal display lines are `UNKNOWN` /
  `SENSORS MISSING`; no fresh accepted reply for 15 seconds yields `UNKNOWN` /
  `HOST OFFLINE`. Before the first reply the host is offline.
- Has a separate one-second **empty** SGP30 acquisition hook, not a five-second
  measurement loop. No long delays or unbounded receive loops are used.
- Does not initialize UART2, I2C, ADC, LCD, heater, outputs, Wi-Fi, Bluetooth, or
  persistent storage. `displayTick()` is deliberately empty. There is currently
  **no physical LCD output and no sensor acquisition**, even with connected parts.

The `esp32dev` PlatformIO target is provisional, not identification of your board.
`platformio.ini` pins the Espressif platform and ArduinoJson library. Neither
PlatformIO nor arduino-cli was available in the authoring environment, so the
firmware was **not compiled for ESP32**. Host-only tests cover the standalone
sequence/timing/LCD guard, not ArduinoJson, USB behavior or electronics.

## Protocol

Device record example (boot ID varies; sequence begins at zero):

```json
{"schema_version":1,"type":"reading","device_id":"esp32-naseem","boot_id":"0123456789abcdef0123456789abcdef","sequence":0,"uptime_ms":30,"source":"hardware","sensor_status":{"pms7003":"missing","sgp30":"missing","bme280":"missing","mq7":"missing"},"readings":{"pm1_ug_m3":null,"pm25_ug_m3":null,"pm10_ug_m3":null,"tvoc_ppb":null,"eco2_ppm":null,"temperature_c":null,"humidity_pct":null,"pressure_hpa":null,"mq7_adc_raw":null}}
```

Expected host response, echoing this record's device ID, boot ID and sequence:

```json
{"schema_version":1,"type":"status","device_id":"esp32-naseem","boot_id":"0123456789abcdef0123456789abcdef","sequence":0,"prototype_status":"UNKNOWN","data_quality":"MISSING","lcd_line_1":"UNKNOWN","lcd_line_2":"SENSORS MISSING"}
```

Send one JSON object per line, no debug chatter. Both LCD strings must contain
at most 16 printable ASCII characters. Future adapters may use sensor states
`missing`, `warming_up`, `ok`, `error`; MQ-7 stays `missing` or `uncalibrated`
until hardware verification. Host status enums are `NORMAL`, `WATCH`, `HIGH`,
`UNKNOWN`; quality enums are `VALID`, `PARTIAL`, `WARMING_UP`, `MISSING`, `INVALID`.
This build intentionally rejects non-missing classification. Sequence exhaustion
stops records rather than wrapping. Emitted `uptime_ms` is a 64-bit monotonic
accumulator updated each loop with unsigned 32-bit elapsed differences, so it
continues increasing across the roughly 49.7-day `millis()` rollover. Sampling
must continue at least once per 49.7 days; this scaffold samples every loop.
Short-duration timer guards retain unsigned 32-bit elapsed arithmetic. Host
tests cover two uptime rollovers as well as response-timer rollover. Boot IDs are random correlation
values, not authentication; use only a trusted local serial host.

## Before any hardware implementation

Have a qualified person verify the exact board, sensor modules, supply and signal
voltages, grounding, and manufacturer documentation. The intended software pin
mapping is PMS7003 UART2 RX=16/TX=17, shared SGP30/BME280 I2C SDA=21/SCL=22,
MQ-7 raw ADC=34. These are **reference constants, not verified wiring advice**;
some ESP32 variants use these pins differently. LCD interface/address/controller
and board/OS remain unknown. Never assume a 5 V module's output is ADC-safe.

To implement adapters in a later revision:

1. PMS7003: bound UART reads and frame buffering, check header, length, checksum
   and freshness; distinguish atmospheric from factory CF=1 outputs. Follow
   manufacturer warm-up requirements and emit `null` until verified valid.
2. SGP30: run IAQ measurement once per second, independent of JSON output. Its
   first 15 seconds after initialization contain fixed startup values, not useful
   measurements; mark `warming_up` and emit `null`. Passing 15 seconds alone is
   not calibration. Follow manufacturer/library conditioning and baseline
   guidance; practical stabilization can take hours and baseline handling needs
   a documented plan. Reset validity after communication errors or cadence gaps.
   eCO2 is an estimate, **not measured CO2**; TVOC is not a specific-gas diagnosis.
3. BME280: verify identity/address, reject non-finite/out-of-range readings,
   timestamp valid samples, and convert pressure from Pa to hPa explicitly.
4. MQ-7: keep disabled. Verify heater cycling circuitry and timing, heater power,
   analog voltage conditioning and ADC calibration, warm-up/burn-in and reference
   calibration before exposing even diagnostic readings. Raw ADC is not CO ppm;
   this project must not infer CO concentration or safe air from it. Never power
   a sensor heater from an ESP32 GPIO.
5. LCD: verify interface and voltage first, then implement bounded display writes
   that pad both 16-character lines. Preserve local UNKNOWN/freshness gates.
6. Add adapter-level hardware tests, error injection, stale-sample tests and
   protocol integration tests before loosening the dry-build classification gate.

## Local checks (no upload)

Run host-only guards from this directory with an existing C++ compiler:

```sh
g++ -std=c++11 -Wall -Wextra -Werror -Iinclude test/test_protocol_guard.cpp -o /tmp/naseem-protocol-test
/tmp/naseem-protocol-test
```

If PlatformIO is already installed, `pio run` performs a compile, not an upload.
Review dependency downloads and the board selection first. No upload command or
wiring procedure is included because the hardware has not been identified.
