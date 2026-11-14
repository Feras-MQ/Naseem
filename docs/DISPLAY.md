# Display integration

A 2.8-inch screen has been purchased. Its controller, interface, pin labels,
power requirements and relationship to the earlier order are still unverified.
Screen size does not identify an ILI9341 or establish ESP32 compatibility.
The soldered sensor's exact chip identity also remains unverified.

## What the software provides

- A fixed-buffer renderer for the two existing 16-character status lines.
  Rows are space-padded, shorter text clears old characters, and only changed
  rows are redrawn. Invalid or oversized input becomes UNKNOWN / DISPLAY ERROR.
- A dry default adapter that initializes no display library, SPI bus or pins.
- An optional driver for a **confirmed ILI9341 SPI display** on classic ESP32.
  It presents the guarded status on a 320 by 240 landscape view with a Naseem
  heading. It uses write-only hardware SPI at 10 MHz, not an automatic pin map.
- Main firmware continues to own classification and host/sensor timeouts.
  The renderer cannot turn missing measurements into NORMAL. USB serial remains
  newline JSON only; neither the renderer nor adapter sends display/debug text.

This is a candidate driver, not a statement that the purchased screen is an
ILI9341. There is no touch, SD-card, backlight control, controller autodetection
or physical display acknowledgement. ST7789 and parallel-interface screens are
not implemented. A successful compile does not establish visible output,
correct colour/orientation, electrical safety or performance on the actual unit.

## Configuration after identification

Output is disabled unless both `NASEEM_ENABLE_ILI9341=1` and
`NASEEM_VERIFIED_DISPLAY_WIRING=1` are explicitly defined. No signal has a
built-in pin assignment. All five definitions are required:

- `NASEEM_TFT_SCK_PIN`
- `NASEEM_TFT_MOSI_PIN`
- `NASEEM_TFT_CS_PIN`
- `NASEEM_TFT_DC_PIN`
- `NASEEM_TFT_RST_PIN` (explicit `-1` only for a reviewed reset arrangement
  requiring no ESP32 reset output)

The compile guard rejects duplicate signals, configured sensor-bus conflicts
and pins outside a conservative classic-ESP32 output subset. This guard excludes
boot straps, serial, flash/PSRAM, JTAG and input-only pins. It does not replace
review of the actual board or connected circuitry. The host tests use arbitrary
nonconflicting pin fixtures; they are not instructions to wire those pins.

The candidate library dependencies are `adafruit/Adafruit ILI9341@1.7.0` and
`adafruit/Adafruit GFX Library@1.12.4`. Keep the default environment dry and use a
separate opt-in build for this driver. `esp32-ili9341-compile-check` and
`esp32-sensors-ili9341-compile-check` are compile fixtures only. Their explicit
pins are arbitrary test inputs and their PlatformIO upload targets are blocked
by `scripts/block_fixture_upload.py`. Do not upload compile-fixture binaries by
other means. Physical wiring needs its own reviewed configuration.

Initialize `DisplayAdapter.begin()` **before** `SensorAdapters.begin()` because
the ILI9341 driver has blocking startup reset/init waits. During the main loop,
call `display.tick(lcdLine1, lcdLine2)` after the existing host/sensor freshness
gates update those lines. Row redraws are bounded to two small rectangles; real
worst-case redraw timing and SGP30 cadence still require measurement on hardware.

## Tests and physical checks

`test_display_core.cpp` exercises row changes, exact-width/padded strings,
shorter-string clearing, invalid input fallback, retry after a fake sink failure,
cache invalidation and the library-free default adapter.
`test_display_config.py` checks mandatory flags/pins, collisions, sensor-bus
conflicts, output-pin restrictions and the classic-ESP32 target guard.
These are host tests, not evidence of a screen working.

Before physical use, record the delivered module's controller and front/back pin
labels, confirm power/logic/backlight/reset details, and review the complete
wiring. Then check startup UNKNOWN, valid local status, a shorter replacement
line, host removal, sensor staleness, reset and actual timing. No hazardous gas
exposure is needed for display verification; use synthetic software tests for
classification scenarios.

## Implementation references

- [Adafruit ILI9341 1.7.0 driver](https://github.com/adafruit/Adafruit_ILI9341/tree/1.7.0)
- [Adafruit GFX 1.12.4 SPI display implementation](https://github.com/adafruit/Adafruit-GFX-Library/blob/1.12.4/Adafruit_SPITFT.cpp)
- [Espressif classic-ESP32 GPIO restrictions](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/gpio.html)
- [Arduino ESP32 2.0.17 SPI initialization](https://github.com/espressif/arduino-esp32/blob/2.0.17/libraries/SPI/src/SPI.cpp)
