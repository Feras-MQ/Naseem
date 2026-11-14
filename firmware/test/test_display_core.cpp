#include "display_adapter.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

struct FakeDisplay {
  char rows[2][17] = {};
  unsigned calls[2] = {};
  bool failSecond = false;
  bool writeRow(uint8_t row, const char* text) {
    assert(row < 2 && strlen(text) == 16);
    ++calls[row];
    if (row == 1 && failSecond) return false;
    memcpy(rows[row], text, 17);
    return true;
  }
};

int main() {
  static_assert(NASEEM_ENABLE_ILI9341 == 0, "host adapter test must stay dry");
  naseem::DisplayAdapter dry;
  dry.begin(); dry.tick("UNKNOWN", "SENSORS MISSING");

  FakeDisplay sink;
  naseem::DisplayRows rows;
  assert(rows.render(sink, "PROTOTYPE:HIGH", "PARTIAL DATA") == 2);
  assert(!strcmp(sink.rows[0], "PROTOTYPE:HIGH  "));
  assert(!strcmp(sink.rows[1], "PARTIAL DATA    "));
  assert(rows.render(sink, "PROTOTYPE:HIGH", "PARTIAL DATA") == 0);
  assert(sink.calls[0] == 1 && sink.calls[1] == 1);

  // Timeout and stale transitions overwrite all remnants of a longer status.
  assert(rows.render(sink, "UNKNOWN", "HOST OFFLINE") == 2);
  assert(!strcmp(sink.rows[0], "UNKNOWN         "));
  assert(rows.render(sink, "UNKNOWN", "DATA STALE") == 1);
  assert(!strcmp(sink.rows[1], "DATA STALE      "));
  assert(sink.calls[0] == 2 && sink.calls[1] == 3);

  assert(rows.render(sink, "0123456789ABCDEF", "") == 2);
  assert(!strcmp(sink.rows[0], "0123456789ABCDEF"));
  assert(!strcmp(sink.rows[1], "                "));
  assert(rows.render(sink, "0123456789ABCDEFG", "NORMAL") == 2);
  assert(!strcmp(sink.rows[0], "UNKNOWN         "));
  assert(!strcmp(sink.rows[1], "DISPLAY ERROR   "));
  assert(rows.render(sink, nullptr, "NORMAL") == 0);
  assert(rows.render(sink, "NORMAL", "bad\ntext") == 0);
  assert(rows.render(sink, "NORMAL", "bad\x7f") == 0);
  assert(rows.render(sink, "NORMAL", "bad\xff") == 0);
  const char unterminated[17] = {'a','a','a','a','a','a','a','a','a',
                                'a','a','a','a','a','a','a','a'};
  assert(rows.render(sink, unterminated, "NORMAL") == 0);

  // A failed sink write is retried; a successful unchanged row is not.
  sink.failSecond = true;
  assert(rows.render(sink, "UNKNOWN", "CHECK SENSORS") == 0);
  sink.failSecond = false;
  assert(rows.render(sink, "UNKNOWN", "CHECK SENSORS") == 1);
  assert(!strcmp(sink.rows[1], "CHECK SENSORS   "));
  rows.invalidate();
  assert(rows.render(sink, "UNKNOWN", "CHECK SENSORS") == 2);
  puts("Display row and dry-adapter assertions passed (host-only).");
}
