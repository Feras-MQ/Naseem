#pragma once
#include "display_config.h"
#include "display_core.h"

#if NASEEM_ENABLE_ILI9341
#include <SPI.h>
#include <Adafruit_ILI9341.h>
#endif

namespace naseem {
#if NASEEM_ENABLE_ILI9341
// Candidate driver only: an ILI9341 SPI module must be identified and its
// electrical interface reviewed before use. Size alone does not identify it.
class DisplayAdapter {
 public:
  DisplayAdapter()
      : bus_(VSPI), screen_(&bus_, NASEEM_TFT_DC_PIN, NASEEM_TFT_CS_PIN,
                           NASEEM_TFT_RST_PIN) {}

  void begin() {
    // Write-only hardware SPI. Explicit pins prevent library/board defaults
    // from silently choosing wiring. Touch, SD and backlight IO are not used.
    bus_.begin(NASEEM_TFT_SCK_PIN, -1, NASEEM_TFT_MOSI_PIN, NASEEM_TFT_CS_PIN);
    screen_.begin(10000000);
    screen_.setRotation(1);  // 320 x 240 landscape for this controller.
    screen_.fillScreen(ILI9341_BLACK);
    screen_.setTextWrap(false);
    screen_.setTextColor(ILI9341_CYAN, ILI9341_BLACK);
    screen_.setTextSize(3);
    screen_.setCursor(16, 18);
    screen_.print("NASEEM");
    screen_.setTextSize(1);
    screen_.setTextColor(ILI9341_WHITE, ILI9341_BLACK);
    screen_.setCursor(16, 52);
    screen_.print("LOCAL AIR-QUALITY INDICATOR");
    screen_.setCursor(16, 206);
    screen_.print("NOT A CERTIFIED ALARM");
    rows_.invalidate();
    begun_ = true;
    tick("UNKNOWN", "WAITING FOR HOST");
  }

  void tick(const char* first, const char* second) {
    if (begun_) rows_.render(*this, first, second);
  }

  bool writeRow(uint8_t row, const char* padded) {
    if (!begun_ || row > 1) return false;
    const int16_t top = 84 + row * 42;
    // Clear the whole row, including glyph background, before shorter text.
    // No full-screen clearing in the sampling loop; at most two small rows.
    screen_.fillRect(16, top, 288, 24, ILI9341_BLACK);
    screen_.setCursor(16, top);
    screen_.setTextSize(2);
    screen_.setTextColor(ILI9341_WHITE, ILI9341_BLACK);
    screen_.write(reinterpret_cast<const uint8_t*>(padded), kDisplayColumns);
    return true;  // Write sent; SPI has no acknowledgement of visible pixels.
  }

 private:
  SPIClass bus_;
  Adafruit_ILI9341 screen_;
  DisplayRows rows_;
  bool begun_ = false;
};
#else
// Default build has no Arduino display dependencies and never touches SPI/IO.
class DisplayAdapter {
 public:
  void begin() {}
  void tick(const char*, const char*) {}
};
#endif
}  // namespace naseem
