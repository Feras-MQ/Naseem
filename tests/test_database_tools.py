"""Operator database tests: provenance, preservation, and consistent snapshots."""
from contextlib import closing
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from naseem.cli import main
from naseem.config import load_config
from naseem.service import Processor
from naseem.simulate import make_packet
from naseem.storage import (APPLICATION_ID, SCHEMA_VERSION, Journal, backup_database,
                            export_csv, initialize_database, inspect_database)


class DatabaseToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'local journal نسيم.sqlite3'

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def populate(self):
        with Journal(self.db, 'simulate', load_config()) as journal:
            processor = Processor(journal, load_config())
            for i in range(13):
                processor.process(json.dumps(make_packet(i, boot_id=journal.run_id)))
            processor.process('malformed fixture')
            return journal.run_id

    def test_init_empty_idempotent_and_does_not_make_run(self):
        self.assertEqual(initialize_database(self.db)['runs'], 0)
        before = self.digest(self.db)
        self.assertEqual(initialize_database(self.db)['records'], 0)
        self.assertEqual(self.digest(self.db), before)
        result = inspect_database(self.db)
        self.assertEqual(result['totals'], dict(runs=0, records=0, events=0))
        self.assertEqual(result['schema_version'], SCHEMA_VERSION)

    def test_init_preserves_existing_runs(self):
        run = self.populate()
        before = self.digest(self.db)
        self.assertEqual(initialize_database(self.db)['runs'], 1)
        self.assertEqual(self.digest(self.db), before)
        self.assertEqual(inspect_database(self.db)['runs'][0]['run_id'], run)

    def test_read_missing_never_creates(self):
        for operation in (lambda: inspect_database(self.db),
                          lambda: backup_database(self.db, self.root / 'copy.sqlite3'),
                          lambda: export_csv(self.db, self.root / 'copy.csv')):
            with self.assertRaises(sqlite3.Error): operation()
        self.assertFalse(self.db.exists())
        self.assertFalse((self.root / 'copy.sqlite3').exists())
        self.assertFalse((self.root / 'copy.csv').exists())

    def test_foreign_database_unchanged(self):
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute('CREATE TABLE important (value TEXT)')
            con.execute('INSERT INTO important VALUES (?)', ('keep',))
        before = self.digest(self.db)
        for operation in (lambda: initialize_database(self.db), lambda: inspect_database(self.db),
                          lambda: Journal(self.db, 'test', load_config()),
                          lambda: backup_database(self.db, self.root / 'copy.sqlite3')):
            with self.assertRaises(ValueError): operation()
            self.assertEqual(self.digest(self.db), before)

    def test_empty_foreign_app_id_not_claimed(self):
        with closing(sqlite3.connect(self.db)) as con, con: con.execute('PRAGMA application_id=9876')
        before = self.digest(self.db)
        with self.assertRaises(ValueError): initialize_database(self.db)
        self.assertEqual(self.digest(self.db), before)

    def test_future_schema_not_silently_downgraded(self):
        initialize_database(self.db)
        with closing(sqlite3.connect(self.db)) as con, con: con.execute('PRAGMA user_version=999')
        before = self.digest(self.db)
        for operation in (lambda: initialize_database(self.db), lambda: inspect_database(self.db),
                          lambda: export_csv(self.db, self.root / 'wrong.csv')):
            with self.assertRaises(ValueError): operation()
        self.assertEqual(self.digest(self.db), before)
        self.assertFalse((self.root / 'wrong.csv').exists())

    def test_partial_schema_not_silently_repaired(self):
        initialize_database(self.db)
        with closing(sqlite3.connect(self.db)) as con, con: con.execute('DROP TABLE events')
        before = self.digest(self.db)
        with self.assertRaises(ValueError): initialize_database(self.db)
        self.assertEqual(self.digest(self.db), before)

    def test_corrupt_database_preserved(self):
        self.db.write_bytes(b'not sqlite at all')
        for operation in (lambda: initialize_database(self.db), lambda: inspect_database(self.db),
                          lambda: backup_database(self.db, self.root / 'copy.sqlite3')):
            with self.assertRaises(sqlite3.Error): operation()
        self.assertEqual(self.db.read_bytes(), b'not sqlite at all')

    def test_inspection_is_bounded_filtered_and_read_only(self):
        first = self.populate()
        second = self.populate()
        before = self.digest(self.db)
        result = inspect_database(self.db, first, limit=2)
        self.assertEqual(result['totals'], dict(runs=1, records=13, events=1))
        self.assertEqual(result['source_counts'], {'synthetic': 13})
        self.assertEqual(result['status_counts'], {'UNKNOWN': 6, 'NORMAL': 7})
        self.assertEqual(len(result['recent_records']), 2)
        self.assertTrue(all(row['run_id'] == first for row in result['recent_records']))
        self.assertEqual(result['runs'][0]['session_state'], 'closed')
        self.assertEqual(result['recent_events'][0]['kind'], 'invalid_record')
        self.assertEqual(self.digest(self.db), before)
        self.assertEqual(inspect_database(self.db, second)['totals']['records'], 13)

    def test_unknown_run_fails_export_and_inspection(self):
        self.populate()
        for run_id in ('not-a-run', "' OR 1=1 --", ''):
            with self.assertRaises(ValueError): inspect_database(self.db, run_id)
            with self.assertRaises(ValueError): export_csv(self.db, self.root / 'unknown.csv', run_id)
        self.assertFalse((self.root / 'unknown.csv').exists())

    def test_unclosed_run_not_claimed_live(self):
        with Journal(self.db, 'serial', load_config()):
            state = inspect_database(self.db)['runs'][0]['session_state']
            self.assertIn('may be active or interrupted', state)

    def test_backup_contains_committed_wal_while_writer_open(self):
        with Journal(self.db, 'test', load_config()) as journal:
            journal.connection.execute('PRAGMA journal_mode=WAL')
            processor = Processor(journal, load_config())
            processor.process(json.dumps(make_packet(10)))
            copy = self.root / 'backup.sqlite3'
            report = backup_database(self.db, copy)
            self.assertEqual(report['integrity'], 'ok')
            result = inspect_database(copy)
            self.assertEqual(result['totals']['records'], 1)
            self.assertEqual(result['runs'][0]['run_id'], journal.run_id)
            # Snapshot is independent: a subsequent reading does not enter it.
            processor.process(json.dumps(make_packet(11)))
            self.assertEqual(inspect_database(copy)['totals']['records'], 1)
            self.assertEqual(inspect_database(self.db)['totals']['records'], 2)

    def test_backup_existing_and_same_path_protected(self):
        self.populate()
        before = self.digest(self.db)
        with self.assertRaises(ValueError): backup_database(self.db, self.db)
        output = self.root / 'old.sqlite3'
        output.write_bytes(b'keep existing')
        with self.assertRaises(FileExistsError): backup_database(self.db, output)
        self.assertEqual(output.read_bytes(), b'keep existing')
        self.assertEqual(self.digest(self.db), before)

    def test_broken_foreign_key_detected(self):
        self.populate()
        with closing(sqlite3.connect(self.db)) as con, con: con.execute("UPDATE records SET run_id='missing'")
        with self.assertRaisesRegex(ValueError, 'broken run'): inspect_database(self.db)

    def test_initialization_failure_rolls_back_and_can_retry(self):
        from naseem.storage import _prepare_schema
        with closing(sqlite3.connect(":memory:")) as con, con:
            def deny_events(action, name, *_):
                return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TABLE and name == "events" else sqlite3.SQLITE_OK
            con.set_authorizer(deny_events)
            with self.assertRaises(sqlite3.Error): _prepare_schema(con)
            con.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
            self.assertEqual(con.execute("SELECT name FROM sqlite_master").fetchall(), [])
            self.assertEqual(con.execute("PRAGMA application_id").fetchone()[0], 0)
            _prepare_schema(con)
            self.assertEqual(con.execute("SELECT count(*) FROM runs").fetchone()[0], 0)
            self.assertEqual(con.execute("PRAGMA application_id").fetchone()[0], APPLICATION_ID)

    def test_run_metadata_uses_explicit_columns(self):
        from naseem import __version__
        initialize_database(self.db)
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("DROP TABLE runs")
            con.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, started_at_utc TEXT NOT NULL, ended_at_utc TEXT, mode TEXT NOT NULL, config_sha256 TEXT NOT NULL, config_json TEXT NOT NULL, disclaimer TEXT NOT NULL, software_version TEXT NOT NULL)")
        with Journal(self.db, "simulate", load_config()) as journal:
            row = journal.connection.execute("SELECT software_version, disclaimer FROM runs").fetchone()
            self.assertEqual(row[0], __version__)
            self.assertIn("Academic prototype", row[1])

    def test_history_limit_validation(self):
        initialize_database(self.db)
        for limit in (0, 101, True, '5'):
            with self.assertRaises(ValueError): inspect_database(self.db, limit=limit)

    def test_operator_cli_pipeline(self):
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            self.assertEqual(main(['init-db', '--db', str(self.db)]), 0)
            self.assertEqual(main(['inspect', '--db', str(self.db)]), 0)
            self.assertEqual(main(['backup', '--db', str(self.db), '--output', str(self.root / 'cli-copy.sqlite3')]), 0)
            self.assertEqual(main(['inspect', '--db', str(self.db), '--limit', '101']), 2)
            self.assertEqual(main(['inspect', '--db', str(self.root / 'typo.sqlite3')]), 2)
        self.assertIn('"integrity": "ok"', output.getvalue())
        self.assertFalse((self.root / 'typo.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
