"""Terminal workflows: simulate, replay, USB serial, and CSV export."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys
import time
from .config import load_config
from .model import ValidationError
from .service import Processor, LineFramer
from .simulate import make_packet, SCENARIOS
from .storage import Journal, export_csv
from .transport import run_serial

NOTICE = "Academic prototype. Rules are illustrative, not official AQI or safety limits. MQ-7 is raw only; eCO2 is estimated, not measured CO2."


def positive_int(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Must be an integer") from exc
    if not 1 <= number <= 1000000:
        raise argparse.ArgumentTypeError("Must be between 1 and 1000000")
    return number


def build_parser():
    parser = argparse.ArgumentParser(description=NOTICE)
    commands = parser.add_subparsers(dest="command", required=True)
    sim = commands.add_parser("simulate", help="Generate explicitly synthetic classroom records")
    sim.add_argument("--scenario", choices=SCENARIOS, default="mixed")
    sim.add_argument("--samples", type=positive_int, default=72)
    sim.add_argument("--realtime", action="store_true", help="Wait five seconds per synthetic record")
    sim.add_argument("--jsonl", help="Also write synthetic input packets to a new JSONL file")
    replay = commands.add_parser("replay", help="Replay a local JSONL capture, preserving source labels")
    replay.add_argument("input", type=Path)
    live = commands.add_parser("serial", help="Read the explicitly selected local USB serial device")
    live.add_argument("--port", required=True)
    live.add_argument("--baud", type=positive_int, default=115200)
    live.add_argument("--samples", type=positive_int, help="Stop after this many valid records; otherwise Ctrl+C")
    for command in (sim, replay, live):
        command.add_argument("--db", required=True, type=Path, help="New or existing Naseem SQLite journal")
        command.add_argument("--config", type=Path)
        command.add_argument("--verbose", action="store_true", help="Print each result as JSON")
    export = commands.add_parser("export", help="Export records, labels, quality, and provenance to a new CSV")
    export.add_argument("--db", required=True, type=Path)
    export.add_argument("--csv", required=True, type=Path)
    export.add_argument("--run-id")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "export":
            count = export_csv(args.db, args.csv, args.run_id)
            print(json.dumps({"exported_records": count, "csv": str(args.csv)}))
            return 0
        print(NOTICE, file=sys.stderr)
        if args.command == "simulate":
            print("SYNTHETIC DEMO ONLY. Virtual five-second device time; not measured room data.", file=sys.stderr)
        config = load_config(args.config)
        with Journal(args.db, args.command, config) as journal:
            processor = Processor(journal, config, expected_source="hardware" if args.command == "serial" else "synthetic" if args.command == "simulate" else None)
            counts = Counter()
            output = None
            try:
                if args.command == "simulate":
                    if args.jsonl:
                        output = Path(args.jsonl).open("x", encoding="utf-8", newline="\n")
                    deadline = time.monotonic()
                    for index in range(args.samples):
                        line = json.dumps(make_packet(index, args.scenario, boot_id=journal.run_id), allow_nan=False)
                        if output:
                            output.write(line + "\n")
                        response = processor.process(line)
                        counts[response["prototype_status"]] += 1
                        if args.verbose:
                            print(json.dumps(response))
                        if args.realtime and index + 1 < args.samples:
                            deadline += 5
                            time.sleep(max(0, deadline - time.monotonic()))
                elif args.command == "replay":
                    framer = LineFramer()
                    with args.input.open("rb") as handle:
                        while chunk := handle.read(8192):
                            for line in framer.feed(chunk):
                                response = processor.reject("Oversized replay frame discarded") if line is None else processor.process(line)
                                counts[response["prototype_status"]] += 1
                                if args.verbose:
                                    print(json.dumps(response))
                        if framer.finish():
                            processor.reject("Incomplete final replay frame; newline required")
                else:
                    run_serial(args.port, args.baud, processor, args.samples or 0, args.verbose)
            except KeyboardInterrupt:
                journal.event("stopped", "User interrupted local session")
                print("Stopped. The device must treat the host as offline after its timeout.", file=sys.stderr)
            finally:
                if output:
                    output.close()
            print(json.dumps({"run_id": journal.run_id, "mode": args.command, "accepted": processor.accepted,
                              "rejected": processor.rejected, "status_counts": dict(counts), "db": str(args.db)}))
            return 1 if processor.rejected else 0
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print(f"Stopped: {exc}. No current safety assessment is available.", file=sys.stderr)
        return 2
