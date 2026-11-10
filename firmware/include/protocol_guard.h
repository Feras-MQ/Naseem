#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace naseem {
constexpr uint32_t kRecordMs = 5000;
constexpr uint32_t kSgp30Ms = 1000;
constexpr uint32_t kHostTimeoutMs = 15000;
constexpr uint32_t kReplyWindowMs = 5000;

inline bool elapsed(uint32_t now, uint32_t since, uint32_t interval) {
  return static_cast<uint32_t>(now - since) >= interval;
}

struct MonotonicUptime {
  uint32_t previous = 0;
  uint64_t milliseconds = 0;

  // Call each loop and once in setup. Each sampling gap must be < 2^32 ms;
  // unsigned subtraction then extends ordinary millis() rollovers into 64 bits.
  uint64_t sample(uint32_t now) {
    milliseconds += static_cast<uint32_t>(now - previous);
    previous = now;
    return milliseconds;
  }
};

inline bool asciiLcd(const char* value, size_t length) {
  if (!value || length > 16) return false;
  for (size_t i = 0; i < length; ++i) {
    const unsigned char ch = static_cast<unsigned char>(value[i]);
    if (ch < 32 || ch > 126) return false;
  }
  return true;
}

inline bool validStatus(const char* value) {
  return value && (!strcmp(value, "NORMAL") || !strcmp(value, "WATCH") ||
                   !strcmp(value, "HIGH") || !strcmp(value, "UNKNOWN"));
}
inline bool validQuality(const char* value) {
  return value && (!strcmp(value, "VALID") || !strcmp(value, "PARTIAL") ||
                   !strcmp(value, "WARMING_UP") || !strcmp(value, "MISSING") ||
                   !strcmp(value, "INVALID"));
}

struct ReplyGuard {
  uint32_t latestSequence = 0;
  uint32_t sentAt = 0;
  uint32_t acceptedAt = 0;
  bool sent = false;
  bool accepted = false;
  bool latestConsumed = false;

  void onSent(uint32_t sequence, uint32_t now) {
    latestSequence = sequence;
    sentAt = now;
    sent = true;
    latestConsumed = false;
  }
  bool mayAccept(uint32_t sequence, uint32_t now) const {
    return sent && !latestConsumed && sequence == latestSequence &&
           !elapsed(now, sentAt, kReplyWindowMs);
  }
  void onAccepted(uint32_t now) {
    latestConsumed = true;
    accepted = true;
    acceptedAt = now;
  }
  bool timedOut(uint32_t now) const {
    return !accepted || elapsed(now, acceptedAt, kHostTimeoutMs);
  }
};
}  // namespace naseem
