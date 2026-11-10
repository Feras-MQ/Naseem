# Sensor implementation references

These documents were checked for sensor-level software requirements. They do not verify the purchased breakout boards' circuitry or the physical wiring. No module was electrically inspected.

## PMS7003

[Plantower-authored PMS7003 series data manual V1.0K, hosted by a third-party distributor](https://empere.in/wp-content/uploads/2025/12/PTQ3015-2016-PMS7003-series-data-manua-English_V1.0K.pdf)

- UART 9600 baud, 8 data bits, no parity, 1 stop bit.
- 32-byte frame, header `42 4D`, big-endian frame length 28 at offsets 2–3.
- Checksum at offsets 30–31 equals the sum of bytes 0–29.
- Atmospheric PM1.0, PM2.5, PM10 concentrations are big-endian words at offsets 10, 12, 14; CF=1 fields at 4, 6, 8 are different outputs.
- Version/error bytes are offsets 28/29. Nonzero sensor error rejects the frame.
- Manual calls for at least 30 seconds after wake for stable output; the software applies the same duration conservatively at startup.
- Native sensor supply is 4.5–5.5 V and UART logic is 3.3 V. Adapter cable and module pinout still need checking.

## SGP30

[Sensirion SGP30 manufacturer datasheet](https://sensirion.com/media/documents/984E0DD5/61644B8B/Sensirion_Gas_Sensors_Datasheet_SGP30.pdf)

- I2C address 0x58. IAQ initialization command 0x2003; measurement command 0x2008.
- The IAQ algorithm needs measurement every second. Logging every five seconds is a separate concern.
- The first 15 seconds return fixed startup values (400 ppm CO2-equivalent and 0 ppb TVOC), not valid environmental observations.
- Each 16-bit response word is CRC-protected (CRC-8 polynomial 0x31, initial 0xFF). The Arduino library handles word CRC verification; the integration preserves error status.
- Bare-chip supply/hotplate supply range is 1.62–1.98 V. The GY-SGP30 regulator and level shifting have not been verified.
- Humidity compensation is optional and uses absolute humidity, not percent relative humidity. Only fresh, valid BME280 values could support it. This version does not enable compensation or persist baselines; those are explicit future validation steps.
- CO2-equivalent is an algorithm-derived estimate, not a direct CO2 measurement.

## BME280

[Bosch manufacturer product page](https://www.bosch-sensortec.com/en/products/environmental-sensors/humidity-sensors-bme280)

[Bosch SensorAPI definitions](https://github.com/boschsensortec/BME280_SensorAPI/blob/master/bme280_defs.h)

[Adafruit Arduino BME280 API](https://adafruit.github.io/Adafruit_BME280_Library/html/class_adafruit___b_m_e280.html)

- Bosch specifies VDD 1.71–3.6 V and VDDIO 1.2–3.6 V. A breakout's “5V” listing is not evidence of 5V-safe I2C logic.
- Chip ID is 0x60 at register 0xD0; I2C addresses are 0x76/0x77.
- `Adafruit_BME280::readPressure()` returns pascals. Convert to hectopascals by dividing by 100, once.
- Driver checks and broad sanity bounds do not constitute calibration or establish measurement accuracy.

## Deliberately deferred

The named MQ-7 module is not enough to establish heater control circuitry, thermal cycle, analog voltage range or calibration. Its adapter stays disabled. LCD controller, backpack address and voltage are not identified; physical LCD writes stay disabled. Neither the source documents nor software tests replace an electrical review or real-device testing.
