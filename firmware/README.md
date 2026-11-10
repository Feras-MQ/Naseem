# Naseem ESP32 firmware prototype

**NOT hardware tested. NOT a safety device.** No hardware has been connected,
flashed, or exercised. This is academic prototype firmware, not a certified gas,
CO, smoke, or air-quality alarm. It cannot establish whether a room is safe.

## Default and explicitly enabled builds

`pio run` selects `esp32-scaffold`, the default dry build. It initializes only USB
serial; all sensors report `missing` and all measurements are JSON `null`.
It does not initialize sensor UART, I2C, ADC, heaters, or LCD.

`pio run -e esp32-sensors-verified` is an **opt-in compile target**, defining
`NASEEM_VERIFIED_WIRING=1`. Its name is a required operator assertion before any
future hardware execution, not evidence that wiring has been verified here.
It explicitly enables PMS7003, BME280 and SGP30 adapters. All three per-sensor
flags default to zero, independently of the global wiring flag:
`NASEEM_ENABLE_BME280`, `NASEEM_ENABLE_PMS7003`, `NASEEM_ENABLE_SGP30`.
Enabling any sensor without `NASEEM_VERIFIED_WIRING=1` is a compile error.
For staged compile targets, use `esp32-bme-verified` (BME only), then
`esp32-bme-pms-verified` (BME + PMS), then `esp32-sensors-verified` (all three).
Pin defaults used by the adapters are centralized in `include/sensor_config.h`:
`NASEEM_PMS_RX_PIN=16`, `NASEEM_PMS_TX_PIN=17`, `NASEEM_I2C_SDA_PIN=21`,
`NASEEM_I2C_SCL_PIN=22`. Overrides do not establish electrical compatibility.
A disabled sensor stays missing/null. UART2 initializes only for enabled PMS;
Wire initializes only if BME or SGP is enabled. Do not treat these compile
profiles as permission to connect or upload unverified hardware. It must not be uploaded until the
actual board/module circuitry, supplies, logic levels and connections have been
reviewed. No upload command or wiring procedure is provided.

The provisional `esp32dev` target is for the reported HiLetgo ESP-WROOM-32
(ASIN B0718T232Z); the exact development-board revision remains unverified.
Other reported parts: TopHomer MQ-7 B08QHN6QFD, Hailege GY-SGP30 B0CJY2QKLL,
RELAND SUN BME280 labelled 5V B09WB3J9MC, OEM PMS7003 B0D2N3Y3MT. Marketplace
identifiers do not verify electrical behavior or module authenticity.

PlatformIO configuration pins Espressif32 6.9.0 and ArduinoJson 6.21.5; the enabled
build additionally uses Adafruit BME280 2.2.4 and Adafruit SGP30 2.0.3, with their
normal transitive dependencies. No installations or ESP32 compiler build were
performed for this revision. Host tests are not firmware compilation or hardware
validation.

## Optional adapters

- **PMS7003:** UART2 RX16/TX17, 9600 8N1. Receive-only software, no wake/sleep or
  mode commands; assumes the sensor is already in active reporting mode. Parser
  storage is 32 bytes and each poll consumes at most 128 UART bytes. It checks
  header, length=28, checksum, and nonzero sensor error byte. It uses atmospheric
  PM1/PM2.5/PM10 offsets 10/12/14, not factory CF=1 outputs. It excludes the first
  30 seconds after adapter startup; values older than 10 seconds become `error`
  and `null`. No frames after warm-up means `missing`, malformed frames mean
  `error` until a valid sample. A rejected length/checksum/error frame immediately invalidates prior data;
  only a later valid frame clears that error. Noise/header mismatches never
  refresh a prior sample, which expires at its normal 10-second TTL.
- **BME280:** shared I2C SDA21/SCL22, tries addresses 0x76 then 0x77, requires chip
  ID 0x60 (BMP280 substitutions are rejected). Live acknowledged chip-ID reads
  bracket library measurements; the cached library ID alone is not trusted.
  Reads about once per second and
  verifies finite values in sensor operating ranges: -40..85 C, 0..100% RH,
  30000..110000 Pa. Pressure is divided by 100 to report hPa. Failed validation
  produces `error` with nulls; valid samples expire after 10 seconds.
- **SGP30:** shared I2C, library address 0x58. Adafruit's driver performs protocol
  CRC handling. Samples outside eCO2 400..60000 or TVOC 0..60000 are rejected
  as errors, matching host sanity bounds. IAQ measurement runs about once per second independently of
  five-second JSON records. First 15 seconds and the boundary sample are excluded
  (earliest valid sample at 16 seconds). A failed measurement or cadence gap over
  1500 ms invalidates readings, then reinitializes IAQ and restarts warm-up. No
  catch-up bursts. The adapter is polled every loop and owns the only scheduler;
  reinitialization restarts that scheduler after the initialization command ends. This is a conservative scheduling guard, not a manufacturer
  specification for allowable jitter. TVOC is not a specific-gas measurement;
  eCO2 is estimated CO2 equivalent, **not measured CO2**.
- **Conditioning:** SGP30's startup gate is not calibration. Practical
  stabilization/baseline conditioning can take hours; this implementation does
  not persist/restore baselines and does not claim a calibrated baseline.
  Humidity compensation is **not implemented**, so values are uncompensated.
- **I2C:** shared Wire transaction timeout is 50 ms. The application contains no
  long delay calls or unbounded receive loops. Sensor libraries use their own
  bounded setup/conversion waits. Missing I2C sensors detected at boot are not
  automatically rediscovered; investigate and restart only after verification.
- **MQ-7:** remains disabled and `missing`, even in the enabled build. No ADC read,
  heater control, CO ppm conversion, or CO-based classification is implemented.
  GPIO34 is only a planned raw-input reference. Heater cycling circuitry, power,
  analog conditioning, ADC calibration, burn-in and reference calibration must
  be documented first. Never power the heater from an ESP32 GPIO.
- **LCD:** physical writes remain unimplemented; `displayTick()` is a hook only.
  The interface, controller, address and voltage remain unidentified. Internal
  16-character display buffers are not evidence of actual LCD output.

PMS7003 uses a nominal 5 V supply and 3.3 V UART in its manufacturer specification.
The bare SGP30 has a 1.62–1.98 V supply; BME280 bare-chip limits are VDD 1.71–3.6 V
and VDDIO 1.2–3.6 V. A breakout labelled “5V” does not prove safe I2C or ADC logic.
**These facts are not validated wiring instructions for the listed modules.**

## Version 1 serial protocol and local gates

USB serial is 115200 baud, newline JSON only, on boot and about every five
seconds. Sensor states are `missing`, `warming_up`, `ok`, `error`; readings are
numbers only when their sensor is `ok`, otherwise JSON `null`. `source: hardware`
identifies the device transport, not proof of valid measurements.

```json
{"schema_version":1,"type":"reading","device_id":"esp32-naseem","boot_id":"0123456789abcdef0123456789abcdef","sequence":0,"uptime_ms":30,"source":"hardware","sensor_status":{"pms7003":"missing","sgp30":"missing","bme280":"missing","mq7":"missing"},"readings":{"pm1_ug_m3":null,"pm25_ug_m3":null,"pm10_ug_m3":null,"tvoc_ppb":null,"eco2_ppm":null,"temperature_c":null,"humidity_pct":null,"pressure_hpa":null,"mq7_adc_raw":null}}
```

Host responses echo the exact device ID, boot ID and latest sequence:

```json
{"schema_version":1,"type":"status","device_id":"esp32-naseem","boot_id":"0123456789abcdef0123456789abcdef","sequence":0,"prototype_status":"UNKNOWN","data_quality":"MISSING","lcd_line_1":"UNKNOWN","lcd_line_2":"SENSORS MISSING"}
```

Responses are limited to 511 bytes before newline. Overflow discards through the
next newline. Invalid JSON/types/enums, non-printable ASCII, LCD strings exceeding
16 characters, mismatched identities, duplicate or older sequences, and replies
five seconds or more after transmission are rejected. Random boot IDs are
correlation values, not authentication; use a trusted local serial host.

The host owns illustrative thresholds and trend rules. Firmware independently
rejects `NORMAL` and `VALID` because planned MQ-7 remains missing. `WATCH`/`HIGH`
are accepted only when at least one pollutant sensor was valid in the record
and **all** pollutant sensors valid in that record remain fresh locally, and response quality exactly matches the record's
computed quality. The response does not identify which sensor triggered it, so
losing either of two previously valid pollutant sensors revokes the display. `WARMING_UP` quality can coexist with a valid pollutant from
another sensor. These statuses do not establish danger or safety; they are host
prototype classifications. The internal display uses fixed prototype labels,
not arbitrary host text. It returns to UNKNOWN if supporting data becomes stale
or there is no fresh accepted host response for 15 seconds.

`uptime_ms` is a 64-bit monotonic accumulator updated each loop using unsigned
32-bit elapsed differences. It continues across 49.7-day `millis()` rollovers,
provided no sampling gap itself reaches 49.7 days. Timer guards remain unsigned
32-bit. Sequence exhaustion stops transmission instead of reusing sequence IDs.

## Verification

Only host-side deterministic tests have run. They cover protocol timing,
identity-independent sequence gates, duplicates, LCD bounds, two uptime
rollovers; PMS headers/length/checksum/error flags, atmospheric fields, overlap
resynchronization, freshness and 100,000 noise bytes; SGP startup/cadence/error, delayed-initialization recovery
and rollover guards; BME chip/range/non-finite/pressure conversion checks; and
local classification gates. They do **not** test ArduinoJson integration,
Adafruit drivers, ESP32 compilation, serial devices, electrical correctness,
sensor calibration, physical LCD output, or sensor accuracy.

From this directory with an existing C++ compiler:

```sh
for test in protocol_guard sensor_core disabled_adapters; do
  g++ -std=c++11 -Wall -Wextra -Werror -Iinclude test/test_${test}.cpp -o /tmp/naseem-${test}-test
  /tmp/naseem-${test}-test
done
python3 test/test_sensor_config.py
```

Address/undefined-behavior sanitizer runs also passed with leak detection
explicitly disabled because LeakSanitizer is unsupported under this environment's
tracing. No memory-leak verification is claimed.

Before hardware use: compile both targets in a suitable toolchain; verify wiring
and board revision; add actual sensor-disconnect/corrupt-frame/bus-stall tests;
check boot/reset and USB reconnect handling; measure timing and compare readings
against references. Keep missing/invalid values null and retain local UNKNOWN
and host-timeout gates.

## Technical references

- Plantower PMS7003 manufacturer manual (mirror):
  https://empere.in/wp-content/uploads/2025/12/PTQ3015-2016-PMS7003-series-data-manua-English_V1.0K.pdf
- Sensirion SGP30 datasheet:
  https://sensirion.com/media/documents/984E0DD5/61644B8B/Sensirion_Gas_Sensors_Datasheet_SGP30.pdf
- Bosch BME280 driver chip/register definitions:
  https://github.com/boschsensortec/BME280_SensorAPI/blob/master/bme280_defs.h
- Adafruit BME280 pressure-unit API:
  https://adafruit.github.io/Adafruit_BME280_Library/html/class_adafruit___b_m_e280.html
