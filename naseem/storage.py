"""Transactional local data journal with provenance and error records."""
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid
from .config import config_json, config_hash
from .model import BOUNDS, SENSORS

APPLICATION_ID = 0x4E415345
SCHEMA_VERSION = 1

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Journal:
    def __init__(self, path, mode, config):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=5)
        self.connection.execute("PRAGMA foreign_keys=ON")
        app = self.connection.execute("PRAGMA application_id").fetchone()[0]
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        tables = self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if (tables and app != APPLICATION_ID) or version not in (0, SCHEMA_VERSION):
            self.connection.close()
            raise ValueError("Database is not an empty or compatible Naseem journal; use a new path")
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, started_at_utc TEXT NOT NULL, ended_at_utc TEXT,
                mode TEXT NOT NULL, config_sha256 TEXT NOT NULL, config_json TEXT NOT NULL,
                software_version TEXT NOT NULL, disclaimer TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
                received_at_utc TEXT NOT NULL, device_id TEXT NOT NULL, boot_id TEXT NOT NULL,
                sequence INTEGER NOT NULL, uptime_ms INTEGER NOT NULL, source TEXT NOT NULL,
                prototype_status TEXT NOT NULL, data_quality TEXT NOT NULL,
                readings_json TEXT NOT NULL, sensor_status_json TEXT NOT NULL,
                reasons_json TEXT NOT NULL, trends_json TEXT NOT NULL, raw_json TEXT NOT NULL,
                UNIQUE(run_id, device_id, boot_id, sequence)
            );
            CREATE INDEX IF NOT EXISTS records_run_id ON records(run_id, id);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
                received_at_utc TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL,
                raw_excerpt TEXT
            );
        ''')
        self.connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
        self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        self.run_id = uuid.uuid4().hex
        self.connection.execute("INSERT INTO runs VALUES (?, ?, NULL, ?, ?, ?, ?, ?)",
            (self.run_id, utc_now(), mode, config_hash(config), config_json(config), "0.1.0",
             "Academic prototype; thresholds illustrative; no official AQI or CO safety inference; synthetic records are not observations"))
        self.connection.commit()

    def save(self, reading, result, raw):
        dump = lambda value: json.dumps(value, sort_keys=True, allow_nan=False)
        self.connection.execute('''INSERT INTO records
            (run_id, received_at_utc, device_id, boot_id, sequence, uptime_ms, source,
             prototype_status, data_quality, readings_json, sensor_status_json, reasons_json,
             trends_json, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (self.run_id, utc_now(), reading.device_id, reading.boot_id, reading.sequence,
             reading.uptime_ms, reading.source, result.prototype_status, result.data_quality,
             dump(reading.readings), dump(reading.sensor_status), dump(result.reasons),
             dump(result.trends), raw))
        self.connection.commit()

    def event(self, kind, message, raw=None):
        self.connection.execute("INSERT INTO events (run_id, received_at_utc, kind, message, raw_excerpt) VALUES (?, ?, ?, ?, ?)",
            (self.run_id, utc_now(), kind, message[:1000], raw[:4096] if raw else None))
        self.connection.commit()

    def close(self):
        try:
            self.connection.execute("UPDATE runs SET ended_at_utc=? WHERE run_id=?", (utc_now(), self.run_id))
            self.connection.commit()
        finally:
            self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def export_csv(database, output, run_id=None):
    database, output = Path(database), Path(output)
    if database.resolve() == output.resolve():
        raise ValueError("CSV destination must not be the database")
    # Read-only URI prevents accidental creation of an empty DB on a mistyped path.
    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise ValueError("Not a Naseem journal")
        connection.row_factory = sqlite3.Row
        sql = '''SELECT records.*, runs.mode, runs.config_sha256 FROM records
                 JOIN runs ON records.run_id=runs.run_id'''
        params = ()
        if run_id:
            sql += " WHERE records.run_id=?"
            params = (run_id,)
        sql += " ORDER BY records.id"
        columns = ["run_id", "mode", "source", "received_at_utc", "device_id", "boot_id", "sequence", "uptime_ms",
                   "prototype_status", "data_quality", "config_sha256", *BOUNDS,
                   *(f"{s}_status" for s in SENSORS), "reasons_json", "trends_json"]
        output.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        # Exclusive create protects an existing export from accidental replacement.
        with output.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in connection.execute(sql, params):
                values = {key: row[key] for key in columns if key in row.keys()}
                values.update(json.loads(row["readings_json"]))
                values.update({f"{key}_status": value for key, value in json.loads(row["sensor_status_json"]).items()})
                # Defense against spreadsheet formula interpretation of external identifiers.
                for key, value in values.items():
                    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                        values[key] = "'" + value
                writer.writerow(values)
                count += 1
        return count
