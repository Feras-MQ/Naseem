#include <stdint.h>
#include <assert.h>
#include <stdio.h>
// Host-only clock stand-in; dry adapter must require no Arduino/driver headers.
uint32_t millis() { return 123; }
#include "sensor_adapters.h"
int main() {
  static_assert(NASEEM_ENABLE_BME280 == 0, "dry test requires defaults");
  static_assert(NASEEM_ENABLE_PMS7003 == 0, "dry test requires defaults");
  static_assert(NASEEM_ENABLE_SGP30 == 0, "dry test requires defaults");
  naseem::SensorAdapters s;
  s.begin(); s.poll(1000); s.sgpTick(1000);
  assert(!strcmp(s.pmsStatus(1000), "missing"));
  assert(!strcmp(s.bmeStatus(1000), "missing"));
  assert(!strcmp(s.sgpStatus(1000), "missing"));
  assert(!strcmp(s.quality(1000), "MISSING"));
  assert(s.pollutantMask(1000) == 0);
  puts("Disabled adapter assertions passed (host-only, stub clock).");
}
