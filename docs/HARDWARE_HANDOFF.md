# Hardware handoff: not performed

This baseline stops before physical work. The default firmware is deliberately dry; optional adapters are now present behind a wiring-confirmation build gate. No purchase, wiring, connection, upload, calibration or physical experiment was performed.

## Confirm before changing the scaffold

1. Exact ESP32 board revision and Arduino target, USB bridge and operating system.
2. Exact sensor breakout/module variants and datasheets, rather than sensor names alone.
3. Power budget, regulated supplies, grounds, logic levels and level shifting. An ESP32 GPIO/ADC must not receive a 5 V module output. Do not power heaters from a GPIO.
4. I2C addresses and pull-up voltage for sensors; actual 2.8-inch display controller, interface, power and logic levels. The optional ILI9341 SPI path is only a candidate. Confirm the delivered module before selecting it; neither the original 16×2 LCD assumption nor a similar listing proves compatibility.
5. PMS7003 framing, atmospheric field selection, checksum, expected warm-up and fresh-data timeout.
6. SGP30 one-second measurement schedule, initial invalid period, longer conditioning/baseline process and humidity compensation using verified absolute-humidity conversion. Driver reinitialization must restart its warm-up flag; missed cadence must be treated explicitly. No saved baseline reuse without verified manufacturer conditions.
7. BME280 address, actual sensor identity, pressure conversion from Pa to hPa, plausibility and stale-reading checks.
8. MQ-7 heater waveform/timing and supply circuitry, ADC scaling/reference/attenuation, initial conditioning and known module variant. Keep disabled until verified. Raw ADC trends alone do not quantify or reliably identify CO. No ppm conversion or safety classification is supplied.
9. Physical display testing: confirm the disabled-by-default candidate driver matches the actual screen. Check cleared/padded rows, host disconnect, sensor failure, and timing under display updates. See `DISPLAY.md`.

The report's proposed GPIOs (UART2 RX16/TX17, I2C SDA21/SCL22, MQ-7 ADC34) are reference choices, not verified wiring instructions. Other ESP32 variants can have different pin constraints.

## Safe staged integration

- Start with the dry serial scaffold and verify UNKNOWN/MISSING end to end.
- Enable and validate BME280 alone in a reviewed configuration. Other sensors remain missing, so no NORMAL.
- Enable PMS7003 and physically verify its checksum/error/freshness behavior and documented warm-up.
- Enable SGP30 at 1 Hz and verify real timing, keeping five-second records and startup/missed-cadence flags separate.
- Add LCD only after its interface is verified. Unplug host, corrupt frames, reset board and simulate a stale host response to check failure displays.
- Keep MQ-7 disabled unless a competent hardware reviewer has verified its heater/ADC design. Use synthetic packets to exercise alert logic; never produce CO or harmful test exposures.
- Log a normal ambient run without intentionally releasing pollutants. Report missing data, resets and actual elapsed intervals, and compare against an appropriate reference if available. Do not claim sensor accuracy or validated thresholds from software tests.

Always use a suitable certified CO alarm for CO safety. If there is an actual alarm or suspected CO exposure, follow emergency guidance and leave the area; this prototype is not a diagnostic check.

The supplied product identifiers and voltage uncertainties are recorded in `HARDWARE_INVENTORY.md`; verified sensor-level references are in `SENSOR_SOURCES.md`. Host parser/state tests do not validate the electronics or the Arduino integration.
