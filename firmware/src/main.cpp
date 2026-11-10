// Academic scaffold ONLY. Not hardware tested. Not a safety device.
// No sensors, LCD, heater, relays, or GPIO outputs are initialized by this build.
#include <Arduino.h>
#define ARDUINOJSON_USE_LONG_LONG 1
#include <ArduinoJson.h>
#include <esp_system.h>
#include <initializer_list>
#include "protocol_guard.h"

namespace {
// Reference mapping only, NOT validated wiring instructions.
constexpr int kPmsRx = 16, kPmsTx = 17, kI2cSda = 21, kI2cScl = 22;
constexpr int kMq7Adc = 34;
constexpr size_t kInputCapacity = 512;
char input[kInputCapacity];
size_t inputLength = 0;
bool discardLine = false;
char bootId[33];
uint32_t nextSequence = 0;
uint32_t lastRecord = 0, lastSgpTick = 0;
bool sequenceExhausted = false;
naseem::ReplyGuard replyGuard;
naseem::MonotonicUptime uptime;
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

void sgp30OneSecondTick(uint32_t now) {
  (void)now;
  // Acquisition extension point; intentionally absent, not simulated hardware.
  // An actual SGP30 adapter must measure at 1 Hz independently of record output,
  // invalidate its first >=15 s after IAQinit, and invalidate on missed cadence.
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
  for (const char* name : {"pms7003", "sgp30", "bme280", "mq7"})
    statuses[name] = "missing";
  JsonObject readings = doc.createNestedObject("readings");
  for (const char* name : {"pm1_ug_m3", "pm25_ug_m3", "pm10_ug_m3",
                          "tvoc_ppb", "eco2_ppm", "temperature_c",
                          "humidity_pct", "pressure_hpa", "mq7_adc_raw"})
    readings[name] = nullptr;
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
  // Independent local safety gate: this build has no actual measurements.
  // Do not let a malformed/misconfigured host turn absent sensors into NORMAL.
  if (strcmp(doc["prototype_status"], "UNKNOWN") != 0 ||
      strcmp(doc["data_quality"], "MISSING") != 0) return;
  replyGuard.onAccepted(now);
  setUnknown("SENSORS MISSING");  // Do not display arbitrary reassuring host text.
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
  lastRecord = lastSgpTick = millis();
  emitReading(uptime.sample(lastRecord));
}

void loop() {
  pollHost();
  const uint32_t now = millis();
  uptime.sample(now);
  if (naseem::elapsed(now, lastSgpTick, naseem::kSgp30Ms)) {
    lastSgpTick = now; // Never burst multiple delayed measurements as catch-up.
    sgp30OneSecondTick(now);
  }
  if (naseem::elapsed(now, lastRecord, naseem::kRecordMs)) {
    lastRecord = now;
    emitReading(uptime.milliseconds);
  }
  if (replyGuard.timedOut(now)) setUnknown("HOST OFFLINE");
  displayTick();
  yield();
}
