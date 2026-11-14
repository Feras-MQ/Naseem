#pragma once
#include "sensor_core.h"
#include "sensor_config.h"
#if NASEEM_ENABLE_BME280 || NASEEM_ENABLE_SGP30
#include <Wire.h>
#endif
#if NASEEM_ENABLE_BME280
#include <Adafruit_BME280.h>
#endif
#if NASEEM_ENABLE_SGP30
#include <Adafruit_SGP30.h>
#endif
namespace naseem {
struct SensorAdapters {
  PmsParser pms;
  WarmupGate pmsWarmup;
  SgpReadiness sgpReady;
  SgpSchedule sgpSchedule;
  uint32_t startedAt = 0, bmeAt = 0, lastBmeAttempt = 0;
  bool bmeFound = false, bmeValid = false, sgpFound = false, sgpError = false;
  float temperature = 0, humidity = 0, pressure = 0;
  uint16_t tvoc = 0, eco2 = 0;
#if NASEEM_ENABLE_BME280
  uint8_t bmeAddress = 0x76;
  Adafruit_BME280 bme;
  bool liveBmeId() {
    Wire.beginTransmission(bmeAddress);
    Wire.write(0xD0);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(bmeAddress, uint8_t(1)) != 1) return false;
    return Wire.read() == 0x60;
  }
#endif
#if NASEEM_ENABLE_SGP30
  Adafruit_SGP30 sgp;
#endif
  void begin() {
#if NASEEM_ENABLE_BME280 || NASEEM_ENABLE_SGP30
    Wire.begin(NASEEM_I2C_SDA_PIN, NASEEM_I2C_SCL_PIN);
    Wire.setTimeOut(50);
#endif
#if NASEEM_ENABLE_PMS7003
    Serial2.begin(9600, SERIAL_8N1, NASEEM_PMS_RX_PIN, NASEEM_PMS_TX_PIN);
#endif
#if NASEEM_ENABLE_BME280
    bmeFound = bme.begin(bmeAddress, &Wire);
    if (!bmeFound) { bmeAddress = 0x77; bmeFound = bme.begin(bmeAddress, &Wire); }
    bmeFound = bmeFound && bme.sensorID() == 0x60;
#endif
#if NASEEM_ENABLE_SGP30
    sgpFound = sgp.begin(&Wire);
#endif
    startedAt = lastBmeAttempt = millis();
    pmsWarmup.reset(startedAt);
    sgpSchedule.restart(startedAt);
    if (sgpFound) sgpReady.reset(startedAt);
  }
  void poll(uint32_t now) {
    (void)now;
#if NASEEM_ENABLE_PMS7003
    pmsWarmup.poll(now, kPmsWarmMs);
    pms.expire(now);
    for (unsigned i = 0; i < 128 && Serial2.available(); ++i) {
      int byte = Serial2.read();
      if (byte >= 0) pms.feed(static_cast<uint8_t>(byte), now);
    }
#endif
#if NASEEM_ENABLE_BME280
    if (bmeFound && elapsed(now, lastBmeAttempt, 1000)) {
      lastBmeAttempt = now;
      bmeValid = false;
      // sensorID() is cached; verify a real acknowledged register transaction
      // around each library acquisition, not only the cached identity at boot.
      if (!liveBmeId()) return;
      temperature = bme.readTemperature();
      if (!liveBmeId()) return;
      humidity = bme.readHumidity();
      if (!liveBmeId()) return;
      const float pa = bme.readPressure();
      bmeValid = liveBmeId() && validBme(0x60, temperature, humidity, pa);
      if (bmeValid) { pressure = pressureHpa(pa); bmeAt = millis(); }
    }
#endif
  }
  void sgpTick(uint32_t now) {
    (void)now;
#if NASEEM_ENABLE_SGP30
    if (!sgpFound || !sgpSchedule.due(now)) return;
    if (sgpReady.missed(now) || sgpError) {
      sgpError = !sgp.IAQinit();
      if (!sgpError) {
        const uint32_t initializedAt = millis();
        sgpReady.reset(initializedAt);
        sgpSchedule.restart(initializedAt);
      }
      return;
    }
    const bool success = sgp.IAQmeasure() && validSgp(sgp.eCO2, sgp.TVOC);
    sgpError = !success;
    // Timestamp at acquisition start to preserve the 1 Hz scheduling contract.
    sgpReady.sample(now, success);
    if (sgpReady.valid) { tvoc = sgp.TVOC; eco2 = sgp.eCO2; }
#endif
  }
  const char* pmsStatus(uint32_t now) const {
#if NASEEM_ENABLE_PMS7003
    if (!pmsWarmup.complete) return "warming_up";
    if (!pms.received) return pms.rejected ? "error" : "missing";
    return pms.fresh(now) ? "ok" : "error";
#else
    (void)now; return "missing";
#endif
  }
  const char* sgpStatus(uint32_t now) const {
#if NASEEM_ENABLE_SGP30
    if (!sgpFound) return "missing";
    if (sgpError || sgpReady.missed(now)) return "error";
    return sgpReady.fresh(now) ? "ok" : "warming_up";
#else
    (void)now; return "missing";
#endif
  }
  const char* bmeStatus(uint32_t now) const {
#if NASEEM_ENABLE_BME280
    if (!bmeFound) return "missing";
    return bmeValid && !elapsed(now, bmeAt, kSensorFreshMs) ? "ok" : "error";
#else
    (void)now; return "missing";
#endif
  }
  const char* quality(uint32_t now) const {
    const char* a = pmsStatus(now);
    const char* b = sgpStatus(now);
    const char* c = bmeStatus(now);
    if (!strcmp(a, "error") || !strcmp(b, "error") || !strcmp(c, "error"))
      return "PARTIAL";
    if (!strcmp(a, "warming_up") || !strcmp(b, "warming_up")) return "WARMING_UP";
    if (!strcmp(a, "missing") && !strcmp(b, "missing") && !strcmp(c, "missing"))
      return "MISSING";
    return "PARTIAL"; // MQ7 deliberately missing, never VALID.
  }
  uint8_t pollutantMask(uint32_t now) const {
    return (!strcmp(pmsStatus(now), "ok") ? 1 : 0) |
           (!strcmp(sgpStatus(now), "ok") ? 2 : 0);
  }
};
} // namespace naseem
