#include "sensor_core.h"
#include <assert.h>
#include <stdio.h>
#include <limits>
#include <initializer_list>
using namespace naseem;
void checksum(uint8_t* f) {
  unsigned sum = 0;
  for (unsigned i = 0; i < 30; ++i) sum += f[i];
  f[30] = sum >> 8; f[31] = sum & 255;
}
bool frame(PmsParser& p, const uint8_t* f, uint32_t time) {
  bool result = false;
  for (unsigned i = 0; i < 32; ++i) result = p.feed(f[i], time) || result;
  return result;
}
int main() {
  uint8_t f[32] = {0x42, 0x4d, 0, 28};
  f[4] = 0x12; f[5] = 0x34; // CF1 deliberately differs from atmosphere.
  f[10] = 1; f[11] = 2; f[12] = 3; f[13] = 4; f[14] = 5; f[15] = 6;
  checksum(f);
  PmsParser p;
  assert(!p.fresh(0));
  assert(frame(p, f, 100));
  assert(p.pm1 == 258 && p.pm25 == 772 && p.pm10 == 1286);
  assert(p.fresh(10099) && !p.fresh(10100));
  f[29] = 1; checksum(f);
  assert(!frame(p, f, 200));
  assert(!p.fresh(201)); // Sensor errors immediately revoke prior valid data.
  f[29] = 0; checksum(f);
  assert(frame(p, f, 202) && p.fresh(203));
  PmsParser bad;
  f[0] = 0x41; assert(!frame(bad, f, 1)); f[0] = 0x42;
  f[3] = 27; checksum(f); assert(!frame(bad, f, 2)); f[3] = 28;
  checksum(f); f[31] ^= 1; assert(!frame(bad, f, 3)); f[31] ^= 1;
  f[29] = 1; checksum(f); assert(!frame(bad, f, 4));
  f[29] = 0; checksum(f);
  // Resynchronizes after errors, noise and a truncated false header.
  for (uint8_t byte : {uint8_t(0), uint8_t(0x42), uint8_t(0x42), uint8_t(0x4d)})
    bad.feed(byte, 5);
  assert(frame(bad, f, 6));
  assert(bad.pm25 == 772 && bad.rejected >= 2);
  // Header embedded inside a malformed frame survives sliding-window recovery.
  PmsParser overlap;
  for (unsigned i = 0; i < 12; ++i) overlap.feed(f[i], 7);
  assert(frame(overlap, f, UINT32_MAX - 100));
  assert(overlap.fresh(100));
  assert(!overlap.fresh(10000));
  // Deterministic noise stress: bounded parser state and eventual recovery.
  uint32_t random = 1234567;
  for (unsigned i = 0; i < 100000; ++i) {
    random = random * 1664525u + 1013904223u;
    overlap.feed(static_cast<uint8_t>(random >> 24), i);
    assert(overlap.used < 32);
  }
  assert(frame(overlap, f, 100001));
  assert(allSupportFresh(3, 3));
  assert(!allSupportFresh(3, 1)); // SGP lost, PMS fresh: revoke HIGH/WATCH.
  assert(!allSupportFresh(3, 2)); // PMS lost, SGP fresh: same conservative gate.
  assert(!allSupportFresh(0, 3));
  assert(allSupportFresh(1, 3));
  assert(allowClassification("HIGH", "PARTIAL", "PARTIAL", 1));
  assert(allowClassification("WATCH", "WARMING_UP", "WARMING_UP", 2));
  assert(!allowClassification("HIGH", "PARTIAL", "PARTIAL", 0));
  assert(!allowClassification("NORMAL", "PARTIAL", "PARTIAL", 3));
  assert(!allowClassification("NORMAL", "VALID", "VALID", 3));
  assert(!allowClassification("HIGH", "MISSING", "PARTIAL", 1));
  assert(allowClassification("UNKNOWN", "MISSING", "MISSING", 0));
  // Delayed IAQinit completion must not cause an outer-scheduler skip loop.
  SgpSchedule schedule;
  SgpReadiness recovery;
  schedule.restart(2010); recovery.reset(2010); // Init took 10 ms.
  assert(!schedule.due(3000));
  assert(schedule.due(3010));
  assert(!recovery.missed(3010));
  assert(!recovery.sample(3010, true));
  for (uint32_t t = 4010; t <= 18010; t += 1000) {
    assert(schedule.due(t));
    assert(!recovery.missed(t));
    recovery.sample(t, true);
  }
  assert(recovery.fresh(18010));
  SgpReadiness sgp;
  assert(!sgp.fresh(0)); sgp.reset(0);
  for (uint32_t t = 1000; t <= 15000; t += 1000) assert(!sgp.sample(t, true));
  assert(sgp.sample(16000, true)); assert(sgp.fresh(17000));
  assert(!sgp.fresh(17501)); assert(sgp.missed(17501));
  assert(!sgp.sample(18000, true));
  sgp.reset(18000); assert(!sgp.sample(19000, false));
  assert(!sgp.fresh(19000));
  sgp.reset(UINT32_MAX - 500);
  assert(!sgp.sample(499, true)); // 1000 ms across wrap, still conditioning.
  assert(!sgp.missed(999)); assert(sgp.missed(2000));
  assert(validSgp(400, 0) && validSgp(60000, 60000));
  assert(!validSgp(399, 0) && !validSgp(60001, 0) && !validSgp(400, 60001));
  assert(validBme(0x60, 25, 45, 101325));
  assert(fabs(pressureHpa(101325) - 1013.25) < .001);
  assert(!validBme(0x58, 25, 45, 101325)); // Reject BMP280 substitutions.
  assert(!validBme(0x60, 25, 101, 101325));
  assert(!validBme(0x60, -41, 45, 101325));
  assert(!validBme(0x60, 25, 45, 1013)); // Pa vs hPa confusion rejected.
  assert(!validBme(0x60, std::numeric_limits<float>::quiet_NaN(), 45, 101325));
  assert(!validBme(0x60, 25, 45, std::numeric_limits<float>::infinity()));
  puts("Sensor-core assertions passed (host-only; no ESP32/hardware test).");
}
