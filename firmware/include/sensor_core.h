#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>
#include "protocol_guard.h"
namespace naseem {
constexpr uint32_t kSensorFreshMs = 10000;
constexpr uint32_t kPmsWarmMs = 30000;
struct PmsParser {
  uint8_t bytes[32] = {};
  unsigned used = 0;
  uint16_t pm1 = 0, pm25 = 0, pm10 = 0;
  uint32_t receivedAt = 0;
  bool received = false, latestError = false;
  unsigned rejected = 0;
  static uint16_t word(const uint8_t* p) { return (uint16_t(p[0]) << 8) | p[1]; }
  void shift() { memmove(bytes, bytes + 1, --used); }
  bool feed(uint8_t byte, uint32_t now) {
    bytes[used++] = byte;
    while (used && bytes[0] != 0x42) shift();
    if (used >= 2 && bytes[1] != 0x4d) { shift(); return false; }
    if (used >= 4 && word(bytes + 2) != 28) { ++rejected; latestError = true; shift(); return false; }
    if (used < 32) return false;
    uint16_t sum = 0;
    for (unsigned i = 0; i < 30; ++i) sum += bytes[i];
    if (sum != word(bytes + 30) || bytes[29] != 0) {
      ++rejected; latestError = true; shift(); return false;
    }
    pm1 = word(bytes + 10); pm25 = word(bytes + 12); pm10 = word(bytes + 14);
    receivedAt = now; received = true; latestError = false; used = 0;
    return true;
  }
  bool fresh(uint32_t now) const {
    return received && !latestError && !elapsed(now, receivedAt, kSensorFreshMs);
  }
};
inline bool allSupportFresh(uint8_t sentMask, uint8_t currentMask) {
  return sentMask != 0 && (currentMask & sentMask) == sentMask;
}
inline bool allowClassification(const char* status, const char* quality,
                                const char* sentQuality, uint8_t freshSupport) {
  if (strcmp(quality, sentQuality) || !strcmp(status, "NORMAL") ||
      !strcmp(quality, "VALID")) return false;
  if (!strcmp(status, "UNKNOWN")) return true;
  return (!strcmp(status, "WATCH") || !strcmp(status, "HIGH")) && freshSupport;
}
struct SgpSchedule {
  uint32_t lastAttempt = 0;
  void restart(uint32_t now) { lastAttempt = now; }
  bool due(uint32_t now) {
    if (!elapsed(now, lastAttempt, 1000)) return false;
    lastAttempt = now;
    return true;
  }
};
struct SgpReadiness {
  uint32_t initializedAt = 0, previousSample = 0, validAt = 0;
  bool initialized = false, valid = false;
  void reset(uint32_t now) {
    initializedAt = previousSample = now; initialized = true; valid = false;
  }
  bool missed(uint32_t now) const {
    return initialized && elapsed(now, previousSample, 1501);
  }
  bool sample(uint32_t now, bool success) {
    if (!initialized || missed(now) || !success) { valid = false; return false; }
    if (!elapsed(now, previousSample, 1000)) return false;
    previousSample = now;
    // Discard the first 15 seconds, plus the boundary sample conservatively.
    valid = elapsed(now, initializedAt, 16000);
    if (valid) validAt = now;
    return valid;
  }
  bool fresh(uint32_t now) const {
    return valid && !missed(now) && !elapsed(now, validAt, 1501);
  }
};
inline bool validBme(uint32_t chipId, float temperature, float humidity, float pressurePa) {
  return chipId == 0x60 && isfinite(temperature) && isfinite(humidity) &&
    isfinite(pressurePa) && temperature >= -40 && temperature <= 85 &&
    humidity >= 0 && humidity <= 100 && pressurePa >= 30000 && pressurePa <= 110000;
}
inline bool validSgp(uint16_t eco2, uint16_t tvoc) {
  return eco2 >= 400 && eco2 <= 60000 && tvoc <= 60000;
}
inline float pressureHpa(float pressurePa) { return pressurePa / 100.0f; }
} // namespace naseem
