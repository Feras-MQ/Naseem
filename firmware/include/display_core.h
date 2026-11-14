#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace naseem {
constexpr size_t kDisplayColumns = 16;

// A row input must be a valid C string or an accessible 17-byte buffer.
// Never scan beyond the protocol's 16 characters plus terminator.
inline bool paddedDisplayRow(const char* text, char (&output)[17]) {
  memset(output, ' ', kDisplayColumns);
  output[kDisplayColumns] = '\0';
  if (!text) return false;
  for (size_t i = 0; i <= kDisplayColumns; ++i) {
    const unsigned char ch = static_cast<unsigned char>(text[i]);
    if (ch == 0) return true;
    if (i == kDisplayColumns || ch < 32 || ch > 126) return false;
    output[i] = static_cast<char>(ch);
  }
  return false;
}

// Renderer for the two existing guarded firmware status lines. Does not
// interpret sensor data or accept raw host messages; classification stays in
// main.cpp. A sink supplies bool writeRow(uint8_t, const char[17]).
class DisplayRows {
 public:
  void invalidate() { shown_[0] = shown_[1] = false; }

  template <typename Sink>
  uint8_t render(Sink& sink, const char* first, const char* second) {
    char next[2][17];
    const bool firstValid = paddedDisplayRow(first, next[0]);
    const bool secondValid = paddedDisplayRow(second, next[1]);
    if (!firstValid || !secondValid) {
      paddedDisplayRow("UNKNOWN", next[0]);
      paddedDisplayRow("DISPLAY ERROR", next[1]);
    }
    uint8_t writes = 0;
    for (uint8_t row = 0; row < 2; ++row) {
      if ((!shown_[row] || memcmp(previous_[row], next[row], 17) != 0) &&
          sink.writeRow(row, next[row])) {
        memcpy(previous_[row], next[row], 17);
        shown_[row] = true;
        ++writes;
      }
    }
    return writes;
  }

 private:
  char previous_[2][17] = {};
  bool shown_[2] = {false, false};
};
}  // namespace naseem
