#include "protocol_guard.h"
#include <assert.h>
#include <stdio.h>

int main() {
  using namespace naseem;
  assert(asciiLcd("UNKNOWN", 7));
  assert(asciiLcd("1234567890123456", 16));
  assert(!asciiLcd("12345678901234567", 17));
  assert(!asciiLcd("bad\n", 4));
  assert(!asciiLcd("a\0b", 3));
  assert(validStatus("UNKNOWN") && !validStatus("GOOD"));
  assert(validQuality("MISSING") && !validQuality("safe"));
  ReplyGuard guard;
  assert(guard.timedOut(0));
  assert(!guard.mayAccept(0, 0));
  guard.onSent(0, 100);
  assert(guard.mayAccept(0, 100));
  assert(!guard.mayAccept(1, 101));
  assert(!guard.mayAccept(0, 5100));
  assert(guard.mayAccept(0, 5099));
  guard.onAccepted(5099);
  assert(!guard.mayAccept(0, 5099)); // Duplicate cannot refresh host liveness.
  assert(!guard.timedOut(20098));
  assert(guard.timedOut(20099));
  guard.onSent(1, 5100);
  assert(!guard.mayAccept(0, 5101));
  assert(guard.mayAccept(1, 5101));
  guard.onSent(2, UINT32_MAX - 100);
  assert(guard.mayAccept(2, 100)); // millis() rollover remains bounded.
  assert(!guard.mayAccept(2, 5000));
  assert(elapsed(50, UINT32_MAX - 50, 100));
  MonotonicUptime uptime;
  assert(uptime.sample(30) == 30); // Includes setup time since boot.
  assert(uptime.sample(30) == 30); // Same-tick sampling does not invent time.
  assert(uptime.sample(UINT32_MAX - 100) == UINT32_MAX - 100ULL);
  const uint64_t beforeWrap = uptime.milliseconds;
  assert(uptime.sample(100) == (1ULL << 32) + 100);
  assert(uptime.milliseconds - beforeWrap == 201);
  assert(uptime.sample(5100) == (1ULL << 32) + 5100);
  assert(uptime.sample(UINT32_MAX - 100) == (2ULL << 32) - 101);
  assert(uptime.sample(0) == (2ULL << 32)); // A second rollover also extends.
  assert(uptime.sample(5000) == (2ULL << 32) + 5000);
  puts("Protocol guard assertions passed (host C++; not ESP32 or hardware tests).");
}
