"""Transactional local data journal with provenance and error records."""
import csv
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid
from . import __version__
from .config import config_json, config_hash
from .model import BOUNDS, SENSORS

APPLICATION_ID = 0x4E415345
SCHEMA_VERSION = 1

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _prepare_schema(connection):
    app = connection.execute("PRAGMA application_id").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    objects = connection.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    if objects or app or version:
        _validate_schema(connection)
        return
    try:
        connection.executescript('''
                BEGIN IMMEDIATE;
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
        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


_REQUIRED_COLUMNS = {
    "runs": {"run_id", "started_at_utc", "ended_at_utc", "mode", "config_sha256", "config_json", "software_version", "disclaimer"},
    "records": {"id", "run_id", "received_at_utc", "device_id", "boot_id", "sequence", "uptime_ms", "source", "prototype_status", "data_quality", "readings_json", "sensor_status_json", "reasons_json", "trends_json", "raw_json"},
    "events": {"id", "run_id", "received_at_utc", "kind", "message", "raw_excerpt"},
}


def _validate_schema(connection):
    if (connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
            or connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
        raise ValueError("Not a compatible Naseem journal; use a new path")
    for table, required in _REQUIRED_COLUMNS.items():
        actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if actual != required:
            raise ValueError(f"Incomplete or incompatible Naseem table: {table}")


@contextmanager
def read_database(database):
    # No accidental database creation, and a stable read snapshot across queries.
    connection = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        _validate_schema(connection)
        yield connection
    finally:
        connection.close()


def initialize_database(database):
    """Create an empty journal or validate one; never insert a fictitious run."""
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=5)
    try:
        _prepare_schema(connection)
        return {"db": str(database), "schema_version": SCHEMA_VERSION,
                "runs": connection.execute("SELECT count(*) FROM runs").fetchone()[0],
                "records": connection.execute("SELECT count(*) FROM records").fetchone()[0]}
    finally:
        connection.close()


def _require_run(connection, run_id):
    if run_id is not None and not connection.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
        raise ValueError("Run ID not found in this journal")


def inspect_database(database, run_id=None, limit=10):
    """Read bounded history. Unclosed sessions are not asserted to be running."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("History limit must be between 1 and 100")
    with read_database(database) as connection:
        _require_run(connection, run_id)
        check = [row[0] for row in connection.execute("PRAGMA quick_check")]
        if check != ["ok"]:
            raise ValueError("SQLite integrity check failed; preserve this file and use a backup")
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Naseem journal has broken run references")
        where = " WHERE run_id=?" if run_id is not None else ""
        params = (run_id,) if run_id is not None else ()
        def counts(table, field):
            return {row[0]: row[1] for row in connection.execute(
                f"SELECT {field}, count(*) FROM {table}{where} GROUP BY {field}", params)}
        runs = []
        for row in connection.execute("SELECT * FROM runs" + where + " ORDER BY started_at_utc DESC, rowid DESC LIMIT ?", (*params, limit)):
            item = dict(row)
            item["config"] = json.loads(item.pop("config_json"))
            item["session_state"] = "closed" if item["ended_at_utc"] else "unclosed (may be active or interrupted)"
            item["records"] = connection.execute("SELECT count(*) FROM records WHERE run_id=?", (row["run_id"],)).fetchone()[0]
            runs.append(item)
        records = []
        for row in connection.execute("SELECT * FROM records" + where + " ORDER BY id DESC LIMIT ?", (*params, limit)):
            item = dict(row)
            item.pop("raw_json")
            for key in ("readings", "sensor_status", "reasons", "trends"):
                item[key] = json.loads(item.pop(key + "_json"))
            records.append(item)
        events = [dict(row) for row in connection.execute(
            "SELECT id,run_id,received_at_utc,kind,message FROM events" + where + " ORDER BY id DESC LIMIT ?", (*params, limit))]
        totals = {table: connection.execute(f"SELECT count(*) FROM {table}" + where, params).fetchone()[0]
                  for table in ("runs", "records", "events")}
        return {"db": str(database), "schema_version": SCHEMA_VERSION, "integrity": "ok",
                "notice": "Stored history only, not a live assessment. Synthetic records are not measurements.",
                "selected_run": run_id, "totals": totals, "source_counts": counts("records", "source"),
                "status_counts": counts("records", "prototype_status"), "quality_counts": counts("records", "data_quality"),
                "limit_per_list": limit, "runs": runs, "recent_records": records, "recent_events": events}


def backup_database(database, output):
    """SQLite snapshot, including committed WAL data, to a new file only."""
    output = Path(output)
    if Path(database).resolve() == output.resolve():
        raise ValueError("Backup destination must not be the source database")
    with read_database(database) as source:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb"):
            pass
        try:
            destination = sqlite3.connect(output)
            try:
                source.backup(destination)
                _validate_schema(destination)
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup failed SQLite integrity check")
            finally:
                destination.close()
        except BaseException:
            # Only our newly-created, incomplete destination is removed.
            output.unlink(missing_ok=True)
            raise
    return {"db": str(database), "backup": str(output), "bytes": output.stat().st_size, "integrity": "ok"}


class Journal:
    def __init__(self, path, mode, config):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=5)
        try:
            self.connection.execute("PRAGMA foreign_keys=ON")
            _prepare_schema(self.connection)
        except BaseException:
            self.connection.close()
            raise
        self.run_id = uuid.uuid4().hex
        self.connection.execute("INSERT INTO runs (run_id, started_at_utc, ended_at_utc, mode, config_sha256, config_json, software_version, disclaimer) VALUES (?, ?, NULL, ?, ?, ?, ?, ?)",
            (self.run_id, utc_now(), mode, config_hash(config), config_json(config), __version__,
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
    with read_database(database) as connection:
        _require_run(connection, run_id)
        sql = '''SELECT records.*, runs.mode, runs.config_sha256 FROM records
                 JOIN runs ON records.run_id=runs.run_id'''
        params = ()
        if run_id is not None:
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
