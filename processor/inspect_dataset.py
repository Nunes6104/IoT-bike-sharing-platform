"""Stream dataset validation findings as JSON Lines and a summary to stderr."""

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from processor.validation import Issue, load_station_ids, parse_json_record, validate_event


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stations", type=Path, required=True, help="station reference JSON")
    parser.add_argument("files", type=Path, nargs="+", help="event JSONL files")
    args = parser.parse_args()
    try:
        station_ids = load_station_ids(args.stations)
    except (OSError, ValueError) as exc:
        print(f"Cannot load stations from {args.stations}: {exc}", file=sys.stderr)
        return 2

    totals: Counter[str] = Counter()
    try:
        for path in args.files:
            with path.open(encoding="utf-8-sig") as source:
                for line_number, line in enumerate(source, 1):
                    totals["records"] += 1
                    try:
                        event = parse_json_record(line)
                    except (ValueError, RecursionError) as exc:
                        issues = [Issue("error", "json", str(exc))]
                    else:
                        issues = validate_event(event, station_ids)
                    if issues:
                        severities = {issue.severity for issue in issues}
                        for severity in severities:
                            totals[f"records_with_{severity}s"] += 1
                        print(json.dumps({
                            "file": str(path),
                            "line": line_number,
                            "issues": [asdict(issue) for issue in issues],
                            "raw": line.rstrip("\r\n"),
                        }, ensure_ascii=True))
    except (OSError, UnicodeError) as exc:
        print(f"Cannot read event file: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "stations": len(station_ids),
        "records": totals["records"],
        "records_with_errors": totals["records_with_errors"],
        "records_with_warnings": totals["records_with_warnings"],
    }), file=sys.stderr)
    return 1 if totals["records_with_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
