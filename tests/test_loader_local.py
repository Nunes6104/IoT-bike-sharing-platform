"""Quick local test of loader logic using SQLite."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

from sqlalchemy import create_engine, text

from processor.offline_loader import OfflineLoader
from processor.validation import load_station_ids


def test_local_sqlite():
    """Test loader with SQLite to verify logic without Docker/MySQL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create in-memory SQLite engine
        engine = create_engine("sqlite:///:memory:", echo=False)

        # Create minimal schema for SQLite compatibility
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS stations (
                    station_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY,
                    type TEXT NOT NULL,
                    ts_utc DATETIME NOT NULL,
                    payload TEXT NOT NULL,
                    validation_status TEXT NOT NULL DEFAULT 'valid',
                    validation_reason TEXT,
                    source_line_number INTEGER
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rejected_lines (
                    source_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    raw_text TEXT NOT NULL,
                    issues TEXT NOT NULL,
                    PRIMARY KEY (source_path, line_number)
                )
            """))
            conn.commit()

        # Load stations
        station_ids = load_station_ids(Path("dataset-IdC-2627/stations.json"))
        print("[OK] Loaded {} station IDs".format(len(station_ids)))

        # Test dry-run loader (no actual writes)
        loader = OfflineLoader(engine, dry_run=True)
        rc = loader.load_stations(Path("dataset-IdC-2627/stations.json"))
        print("[OK] Station load dry-run: exit code {}, loaded {}".format(rc, loader.stats['stations_loaded']))

        # Test event loading
        loader = OfflineLoader(engine, dry_run=False)
        loader.load_events(Path("dataset-IdC-2627/stage1_offline.jsonl"), station_ids)
        print("[OK] Event load complete:")
        print("  - Records read: {}".format(loader.stats['records_read']))
        print("  - Records processed: {}".format(loader.stats['records_processed']))
        print("  - Records with warnings: {}".format(loader.stats['records_with_warnings']))
        print("  - Records rejected: {}".format(loader.stats['records_rejected']))
        print("  - Errors: {}".format(loader.stats['errors']))
        exit_code = loader.report()
        print("[OK] Exit code: {}".format(exit_code))

        # Verify counts
        with engine.connect() as conn:
            events_count = conn.execute(text("SELECT COUNT(*) FROM events")).scalar()
            warnings_count = conn.execute(
                text("SELECT COUNT(*) FROM events WHERE validation_status = 'warning'")
            ).scalar()
            rejected_count = conn.execute(text("SELECT COUNT(*) FROM rejected_lines")).scalar()
            print("[OK] Database verification:")
            print("  - Events in DB: {}".format(events_count))
            print("  - Warnings in DB: {}".format(warnings_count))
            print("  - Rejected lines in DB: {}".format(rejected_count))

        assert loader.stats['records_processed'] == 53724, "Expected 53724 processed, got {}".format(loader.stats['records_processed'])
        assert loader.stats['records_with_warnings'] == 126, "Expected 126 warnings, got {}".format(loader.stats['records_with_warnings'])
        assert loader.stats['errors'] == 0, "Expected 0 errors, got {}".format(loader.stats['errors'])
        assert exit_code == 0, "Expected exit code 0, got {}".format(exit_code)
        print("\n[OK] All assertions passed!")


if __name__ == '__main__':
    test_local_sqlite()
