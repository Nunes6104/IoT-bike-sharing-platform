"""Processor CLI entry point for offline loading."""

import argparse
import sys
from pathlib import Path

from processor.db import create_secure_connection, apply_schema
from processor.offline_loader import OfflineLoader
from processor.validation import load_station_ids


def main() -> int:
    parser = argparse.ArgumentParser(
        prog='processor',
        description='Load bike-sharing events into the data platform'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Offline load command
    load_parser = subparsers.add_parser('load-offline', help='Load stage 1 offline dataset')
    load_parser.add_argument('--stations', type=Path, required=True, help='Station reference JSON')
    load_parser.add_argument('--db-url', required=True, help='SQLAlchemy database URL')
    load_parser.add_argument('--ca-cert', type=Path, help='CA certificate for TLS verification')
    load_parser.add_argument('--schema', type=Path, help='Path to schema.sql')
    load_parser.add_argument('--dry-run', action='store_true', help='Validate but do not write to database')
    load_parser.add_argument('files', type=Path, nargs='+', help='Event JSONL files')

    args = parser.parse_args()

    if args.command == 'load-offline':
        try:
            engine = create_secure_connection(
                args.db_url,
                ca_cert_path=args.ca_cert,
                verify_cert=bool(args.ca_cert),
            )

            # Apply schema if provided
            if args.schema:
                try:
                    apply_schema(engine, str(args.schema))
                except Exception as exc:
                    print(f"Failed to apply schema: {exc}", file=sys.stderr)
                    return 2

            # Validate stations
            try:
                station_ids = load_station_ids(args.stations)
            except (OSError, ValueError) as exc:
                print(f"Cannot load stations: {exc}", file=sys.stderr)
                return 2

            loader = OfflineLoader(engine, dry_run=args.dry_run)

            # Load stations
            rc = loader.load_stations(args.stations)
            if rc != 0:
                return rc

            # Load events
            for path in args.files:
                try:
                    loader.load_events(path, station_ids)
                except Exception as exc:
                    print(f"Failed to load {path}: {exc}", file=sys.stderr)
                    return 2

            return loader.report()

        except KeyboardInterrupt:
            print("Interrupted", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"Unexpected error: {exc}", file=sys.stderr)
            return 2
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
