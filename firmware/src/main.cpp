// Academic scaffold ONLY. Not hardware tested. Not a safety device.
// Sensor IO is disabled unless NASEEM_VERIFIED_WIRING=1. LCD/MQ7 stay disabled.
#include <Arduino.h>
#define ARDUINOJSON_USE_LONG_LONG 1
#include <ArduinoJson.h>
#include <esp_system.h>
#include <initializer_list>
#include "protocol_guard.h"
#include "sensor_adapters.h"

namespace {
// Actual proposed pin defaults and enable flags live in sensor_config.h.
constexpr size_t kInputCapacity = 512;
char input[kInputCapacity];
size_t inputLength = 0;
bool discardLine = false;
char bootId[33];
uint32_t nextSequence = 0;
uint32_t lastRecord = 0;
bool sequenceExhausted = false;
naseem::ReplyGuard replyGuard;
naseem::MonotonicUptime uptime;
naseem::SensorAdapters sensors;
uint8_t sentPollutants = 0, acceptedPollutants = 0;
const char* sentQuality = "MISSING";
char lcdLine1[17] = "UNKNOWN";
char lcdLine2[17] = "SENSORS MISSING";

void setUnknown(const char* detail) {
  snprintf(lcdLine1, sizeof(lcdLine1), "%s", "UNKNOWN");
  snprintf(lcdLine2, sizeof(lcdLine2), "%s", detail);
}

void displayTick() {
  // Deliberately no physical LCD writes. Adapt this hook only after verifying
  // interface, controller, address, voltage, and board; render both padded lines.
  // Never print LCD/debug text to Serial: that stream is newline JSON only.
}

void pollSgp30(uint32_t now) {
  sensors.sgpTick(now);
}

void emitReading(uint64_t uptimeMs) {
  if (sequenceExhausted) { setUnknown("RESTART NEEDED"); return; }
  StaticJsonDocument<1536> doc;
  doc["schema_version"] = 1;
  doc["type"] = "reading";
  doc["device_id"] = "esp32-naseem";
  doc["boot_id"] = bootId;
  doc["sequence"] = nextSequence;
  doc["uptime_ms"] = uptimeMs;
  doc["source"] = "hardware";
  JsonObject statuses = doc.createNestedObject("sensor_status");
  const uint32_t now = millis();
  statuses["pms7003"] = sensors.pmsStatus(now);
  statuses["sgp30"] = sensors.sgpStatus(now);
  statuses["bme280"] = sensors.bmeStatus(now);
  statuses["mq7"] = "missing";
  sentPollutants = sensors.pollutantMask(now);
  sentQuality = sensors.quality(now);
  JsonObject readings = doc.createNestedObject("readings");
  for (const char* name : {"pm1_ug_m3", "pm25_ug_m3", "pm10_ug_m3",
                          "tvoc_ppb", "eco2_ppm", "temperature_c",
                          "humidity_pct", "pressure_hpa", "mq7_adc_raw"})
    readings[name] = nullptr;
  if (sentPollutants & 1) {
    readings["pm1_ug_m3"] = sensors.pms.pm1;
    readings["pm25_ug_m3"] = sensors.pms.pm25;
    readings["pm10_ug_m3"] = sensors.pms.pm10;
  }
  if (sentPollutants & 2) {
    readings["tvoc_ppb"] = sensors.tvoc;
    readings["eco2_ppm"] = sensors.eco2;
  }
  if (!strcmp(sensors.bmeStatus(now), "ok")) {
    readings["temperature_c"] = sensors.temperature;
    readings["humidity_pct"] = sensors.humidity;
    readings["pressure_hpa"] = sensors.pressure;
  }
  serializeJson(doc, Serial);
  Serial.write('\n');
  replyGuard.onSent(nextSequence, millis());
  if (nextSequence == UINT32_MAX) sequenceExhausted = true;
  else ++nextSequence;
}

void consumeResponse(uint32_t now) {
  StaticJsonDocument<1024> doc;
  if (deserializeJson(doc, input, inputLength)) return;
  // Reject embedded NUL and non-ASCII protocol strings before C-string compares.
  for (const char* name : {"type", "device_id", "boot_id", "prototype_status", "data_quality"}) {
    if (!doc[name].is<const char*>()) return;
    JsonString value = doc[name].as<JsonString>();
    for (size_t i = 0; i < value.size(); ++i)
      if (value.c_str()[i] < 32 || value.c_str()[i] > 126) return;
  }
  if (!doc.is<JsonObject>() || !doc["schema_version"].is<int>() ||
      doc["schema_version"].as<int>() != 1 ||
      !doc["type"].is<const char*>() ||
      strcmp(doc["type"], "status") != 0 ||
      strcmp(doc["device_id"], "esp32-naseem") != 0 ||
      !doc["boot_id"].is<const char*>() ||
      strcmp(doc["boot_id"], bootId) != 0 ||
      !doc["sequence"].is<uint32_t>() ||
      !replyGuard.mayAccept(doc["sequence"].as<uint32_t>(), now)) return;
  if (!doc["prototype_status"].is<const char*>() ||
      !doc["data_quality"].is<const char*>() ||
      !naseem::validStatus(doc["prototype_status"]) ||
      !naseem::validQuality(doc["data_quality"])) return;
  for (const char* name : {"lcd_line_1", "lcd_line_2"}) {
    if (!doc[name].is<const char*>()) return;
    JsonString line = doc[name].as<JsonString>();
    if (!naseem::asciiLcd(line.c_str(), line.size())) return;
  }
  // MQ7 is always missing, so NORMAL/VALID must never be accepted. WATCH/HIGH
  // may reflect host rules only when ALL pollutants valid in the sent record
  // remain fresh locally (the protocol does not identify the triggering sensor). Rules/trends remain on the host; this is not an alarm.
  const char* status = doc["prototype_status"];
  const char* quality = doc["data_quality"];
  const bool elevated = !strcmp(status, "WATCH") || !strcmp(status, "HIGH");
  const uint8_t support = naseem::allSupportFresh(sentPollutants, sensors.pollutantMask(now))
    ? sentPollutants : 0;
  if (!naseem::allowClassification(status, quality, sentQuality, support)) return;
  replyGuard.onAccepted(now);
  acceptedPollutants = elevated ? support : 0;
  if (elevated) {
    snprintf(lcdLine1, sizeof(lcdLine1), "PROTOTYPE:%s", status);
    snprintf(lcdLine2, sizeof(lcdLine2), "%s", "PARTIAL DATA");
  } else setUnknown("CHECK SENSORS");

}

void pollHost() {
  // Bound work each loop even if the host continuously floods the input.
  for (unsigned count = 0; count < 128 && Serial.available(); ++count) {
    const int byte = Serial.read();
    if (byte < 0) break;
    if (byte == '\n') {
      if (!discardLine && inputLength) {
        input[inputLength] = '\0';
        consumeResponse(millis());
      }
      inputLength = 0;
      discardLine = false;
    } else if (!discardLine) {
      if (byte == 0 || inputLength >= kInputCapacity - 1) {
        discardLine = true;
      } else input[inputLength++] = static_cast<char>(byte);
    }
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  // Non-secret per-boot correlation ID; no network or persistent credentials.
  snprintf(bootId, sizeof(bootId), "%08lx%08lx%08lx%08lx",
           static_cast<unsigned long>(esp_random()),
           static_cast<unsigned long>(esp_random()),
           static_cast<unsigned long>(esp_random()),
           static_cast<unsigned long>(esp_random()));
  sensors.begin();
  lastRecord = millis();
  emitReading(uptime.sample(lastRecord));
}

void loop() {
  pollHost();
  const uint32_t now = millis();
  uptime.sample(now);
  sensors.poll(now);
  // The adapter owns the ONLY SGP scheduler; poll every loop after any I2C work.
  pollSgp30(millis());
  if (naseem::elapsed(now, lastRecord, naseem::kRecordMs)) {
    lastRecord = now;
    emitReading(uptime.milliseconds);
  }
  if (replyGuard.timedOut(now)) setUnknown("HOST OFFLINE");
  if (acceptedPollutants && !naseem::allSupportFresh(acceptedPollutants, sensors.pollutantMask(millis()))) {
    acceptedPollutants = 0;
    setUnknown("DATA STALE");
  }
  displayTick();
  yield();
}
