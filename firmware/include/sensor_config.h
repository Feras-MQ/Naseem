#pragma once
#ifndef NASEEM_VERIFIED_WIRING
#define NASEEM_VERIFIED_WIRING 0
#endif
#ifndef NASEEM_ENABLE_PMS7003
#define NASEEM_ENABLE_PMS7003 0
#endif
#ifndef NASEEM_ENABLE_BME280
#define NASEEM_ENABLE_BME280 0
#endif
#ifndef NASEEM_ENABLE_SGP30
#define NASEEM_ENABLE_SGP30 0
#endif
#if (NASEEM_ENABLE_PMS7003 || NASEEM_ENABLE_BME280 || NASEEM_ENABLE_SGP30) && !NASEEM_VERIFIED_WIRING
#error "Sensor enable requires explicit NASEEM_VERIFIED_WIRING=1"
#endif
#if (NASEEM_VERIFIED_WIRING != 0 && NASEEM_VERIFIED_WIRING != 1) || \
    (NASEEM_ENABLE_PMS7003 != 0 && NASEEM_ENABLE_PMS7003 != 1) || \
    (NASEEM_ENABLE_BME280 != 0 && NASEEM_ENABLE_BME280 != 1) || \
    (NASEEM_ENABLE_SGP30 != 0 && NASEEM_ENABLE_SGP30 != 1)
#error "Naseem configuration flags must be 0 or 1"
#endif

// Proposed pin mapping only; verify the actual board and module wiring first.
#ifndef NASEEM_PMS_RX_PIN
#define NASEEM_PMS_RX_PIN 16
#endif
#ifndef NASEEM_PMS_TX_PIN
#define NASEEM_PMS_TX_PIN 17
#endif
#ifndef NASEEM_I2C_SDA_PIN
#define NASEEM_I2C_SDA_PIN 21
#endif
#ifndef NASEEM_I2C_SCL_PIN
#define NASEEM_I2C_SCL_PIN 22
#endif
