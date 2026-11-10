# Supplied hardware inventory

The following product names and identifiers were supplied for this project. They narrow the intended device families but do not establish the exact PCB revision, installed voltage regulator, I2C pull-up voltage, connector pin order or genuine sensor identity.

| Component | Supplied product reference | Software status |
|---|---|---|
| ESP32 | HiLetgo ESP-WROOM-32, B0718T232Z | Classic ESP32 Arduino target assumed; exact board/pin layout still to verify |
| Particles | OEM PMS7003, B0D2N3Y3MT | Optional UART receive adapter, default disabled |
| VOC/eCO2 | Hailege GY-SGP30, B0CJY2QKLL | Optional 1 Hz IAQ adapter, default disabled |
| Environmental | RELAND SUN BME280 labelled “5V”, B09WB3J9MC | Optional I2C adapter with sensor-ID check, default disabled |
| Gas raw diagnostics | TopHomer MQ-7, B08QHN6QFD | Disabled; heater circuitry, timing and ADC protection unverified |
| LCD | Not yet identified | Physical output disabled; LCD text/protocol guards remain available |

## Important distinction: sensor and breakout board

The BME280 silicon is not a 5 V I2C device. A seller's “5V” label may refer only to a regulator input; it does not prove safe pull-up or logic levels. Similarly, a GY-SGP30 breakout requires verification of its regulator, level shifting and pull-ups because the SGP30 silicon itself has a much lower supply voltage than the ESP32 board supply.

The PMS7003 sensor supply and UART logic use different voltage domains. Do not infer connector pin order from a similarly named adapter cable. ESP32 GPIOs and its ADC must be protected from unsuitable voltages. MQ-7 heater power cannot be supplied by an ESP32 GPIO.

A module photograph/schematic, actual pin labels and voltage measurements reviewed by a competent person are still needed before enabling physical acquisition. None of those checks, wiring changes or measurements has been performed by this software work.

## What the supplied hardware enables now

It is sufficient to prepare modular software for the named sensor families and deterministic parser/state tests. It is not sufficient to establish electrical safety, calibrate measurements, assert CO concentration, or authorize flashing to an actual board. See `HARDWARE_HANDOFF.md` and the firmware README for the remaining gates.
