"""Database URL and TLS connection configuration tests."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from processor.db import apply_schema, create_secure_connection


class SecureConnectionTests(unittest.TestCase):
    def test_mysql_connection_requires_ca_file(self):
        with tempfile.TemporaryDirectory() as directory:
            empty_ca = Path(directory) / "ca.crt"
            empty_ca.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "missing or empty"):
                create_secure_connection(
                    "mysql+pymysql://user:password@database/bike_sharing",
                    empty_ca,
                )

    def test_sqlite_and_non_mysql_urls_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ca = Path(directory) / "ca.crt"
            ca.write_text("test certificate", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "mysql\\+pymysql"):
                create_secure_connection("sqlite:///:memory:", ca)

    def test_pymysql_driver_receives_identity_verification_options(self):
        with tempfile.TemporaryDirectory() as directory:
            ca = Path(directory) / "ca.crt"
            ca.write_text("test certificate", encoding="ascii")
            with patch("processor.db.create_engine", return_value=object()) as factory:
                create_secure_connection(
                    "mysql+pymysql://user:password@database/bike_sharing",
                    ca,
                )
            options = factory.call_args.kwargs["connect_args"]
            self.assertEqual(options["client_flag"], 0)
            self.assertEqual(options["ssl_ca"], str(ca))
            self.assertTrue(options["ssl_verify_cert"])
            self.assertTrue(options["ssl_verify_identity"])

    def test_versioned_migrations_are_idempotent_and_preserve_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            migration_dir = root / "migrations"
            migration_dir.mkdir()
            schema = root / "schema.sql"
            schema.write_text(
                "CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY, description TEXT);"
                "INSERT OR IGNORE INTO schema_versions VALUES (1, 'base');"
                "CREATE TABLE IF NOT EXISTS event_conflicts (seq INTEGER, new_hash TEXT);",
                encoding="utf-8",
            )
            (migration_dir / "002_online.sql").write_text(
                "CREATE TABLE IF NOT EXISTS rejected_messages (message_hash TEXT PRIMARY KEY);"
                "CREATE UNIQUE INDEX uq_event_conflict_seq_new_hash "
                "ON event_conflicts (seq, new_hash);",
                encoding="utf-8",
            )
            engine = create_engine("sqlite:///:memory:")
            try:
                apply_schema(engine, schema)
                with engine.begin() as connection:
                    connection.execute(
                        text("INSERT INTO event_conflicts VALUES (1, 'old')")
                    )
                apply_schema(engine, schema)
                with engine.connect() as connection:
                    versions = connection.execute(
                        text("SELECT COUNT(*) FROM schema_versions")
                    ).scalar_one()
                    conflicts = connection.execute(
                        text("SELECT COUNT(*) FROM event_conflicts")
                    ).scalar_one()
                self.assertEqual(versions, 2)
                self.assertEqual(conflicts, 1)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
