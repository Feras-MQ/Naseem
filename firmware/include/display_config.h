#pragma once
#include "sensor_config.h"

#ifndef NASEEM_ENABLE_ILI9341
#define NASEEM_ENABLE_ILI9341 0
#endif
#ifndef NASEEM_VERIFIED_DISPLAY_WIRING
#define NASEEM_VERIFIED_DISPLAY_WIRING 0
#endif
#if (NASEEM_ENABLE_ILI9341 != 0 && NASEEM_ENABLE_ILI9341 != 1) || \
    (NASEEM_VERIFIED_DISPLAY_WIRING != 0 && NASEEM_VERIFIED_DISPLAY_WIRING != 1)
#error "Display configuration flags must be 0 or 1"
#endif

#if NASEEM_ENABLE_ILI9341
#if !NASEEM_VERIFIED_DISPLAY_WIRING
#error "ILI9341 output requires explicit NASEEM_VERIFIED_DISPLAY_WIRING=1"
#endif
#if !defined(NASEEM_TFT_SCK_PIN) || !defined(NASEEM_TFT_MOSI_PIN) || \
    !defined(NASEEM_TFT_CS_PIN) || !defined(NASEEM_TFT_DC_PIN) || \
    !defined(NASEEM_TFT_RST_PIN)
#error "Define every TFT pin explicitly; RST=-1 means verified reset wiring without a GPIO"
#else
#if defined(ARDUINO) && (!defined(CONFIG_IDF_TARGET_ESP32) || !CONFIG_IDF_TARGET_ESP32)
#error "This display pin guard supports classic ESP32 only"
#endif
namespace naseem {
namespace display_config {
// Conservative classic-ESP32 output subset: exclude serial, flash/PSRAM,
// boot straps, JTAG and input-only pins. Board-specific use still needs review.
constexpr bool outputPin(int pin) {
  return pin == 4 || pin == 18 || pin == 19 || pin == 21 || pin == 22 ||
         pin == 23 || pin == 25 || pin == 26 || pin == 27 ||
         pin == 32 || pin == 33;
}
constexpr bool availablePin(int pin) {
  return outputPin(pin) &&
    (!(NASEEM_ENABLE_BME280 || NASEEM_ENABLE_SGP30) ||
      (pin != NASEEM_I2C_SDA_PIN && pin != NASEEM_I2C_SCL_PIN)) &&
    (!NASEEM_ENABLE_PMS7003 ||
      (pin != NASEEM_PMS_RX_PIN && pin != NASEEM_PMS_TX_PIN));
}
static_assert(availablePin(NASEEM_TFT_SCK_PIN), "TFT SCK pin invalid or used by a sensor");
static_assert(availablePin(NASEEM_TFT_MOSI_PIN), "TFT MOSI pin invalid or used by a sensor");
static_assert(availablePin(NASEEM_TFT_CS_PIN), "TFT CS pin invalid or used by a sensor");
static_assert(availablePin(NASEEM_TFT_DC_PIN), "TFT DC pin invalid or used by a sensor");
static_assert(NASEEM_TFT_RST_PIN == -1 || availablePin(NASEEM_TFT_RST_PIN),
              "TFT RST pin invalid or used by a sensor");
static_assert(NASEEM_TFT_SCK_PIN != NASEEM_TFT_MOSI_PIN &&
              NASEEM_TFT_SCK_PIN != NASEEM_TFT_CS_PIN &&
              NASEEM_TFT_SCK_PIN != NASEEM_TFT_DC_PIN &&
              NASEEM_TFT_SCK_PIN != NASEEM_TFT_RST_PIN &&
              NASEEM_TFT_MOSI_PIN != NASEEM_TFT_CS_PIN &&
              NASEEM_TFT_MOSI_PIN != NASEEM_TFT_DC_PIN &&
              NASEEM_TFT_MOSI_PIN != NASEEM_TFT_RST_PIN &&
              NASEEM_TFT_CS_PIN != NASEEM_TFT_DC_PIN &&
              NASEEM_TFT_CS_PIN != NASEEM_TFT_RST_PIN &&
              NASEEM_TFT_DC_PIN != NASEEM_TFT_RST_PIN,
              "Each TFT signal must have its own pin");
}  // namespace display_config
}  // namespace naseem
#endif  // all explicit pin definitions
#endif  // NASEEM_ENABLE_ILI9341
