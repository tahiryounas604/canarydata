"""Command-line interface for canarydata.

Examples:
    canarydata recipient add "Partner A"
    canarydata generate --recipient "Partner A" --count 5
    canarydata seed --recipient "Partner A" --in customers.csv --out customers_partnerA.csv
    canarydata check leaked.csv
    canarydata recipients
    canarydata canaries --recipient "Partner A"
"""
from __future__ import annotations

import argparse
import os
import sys

from canarydata.detection import format_report, report_json, scan_file
from canarydata.generator import generate_canaries
from canarydata.registry import Registry
from canarydata.seeding import seed_csv

DEFAULT_DB = os.environ.get("CANARYDATA_DB", "canarydata.db")


def _add_db(parser: argparse.ArgumentParser, suppress: bool = False) -> None:
    # Sub-parsers use SUPPRESS so an absent --db there does not overwrite
    # a --db given before the subcommand (argparse applies sub-parser
    # defaults over the already-parsed namespace otherwise).
    parser.add_argument(
        "--db",
        default=argparse.SUPPRESS if suppress else None,
        help=f"registry database path (default: {DEFAULT_DB})",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="canarydata",
        description="Per-recipient canary records for data-leak attribution.",
    )
    _add_db(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    p_recipient = sub.add_parser("recipient", help="manage recipients")
    _add_db(p_recipient, suppress=True)
    rec_sub = p_recipient.add_subparsers(dest="recipient_command", required=True)
    p_add = rec_sub.add_parser("add", help="add a recipient")
    p_add.add_argument("name")
    _add_db(p_add, suppress=True)
    p_rlist = rec_sub.add_parser("list", help="list recipients")
    _add_db(p_rlist, suppress=True)

    p_recipients = sub.add_parser("recipients", help="list recipients")
    _add_db(p_recipients, suppress=True)

    p_gen = sub.add_parser("generate", help="generate canaries for a recipient")
    p_gen.add_argument("--recipient", required=True)
    p_gen.add_argument("--count", type=int, default=5)
    _add_db(p_gen, suppress=True)

    p_canaries = sub.add_parser("canaries", help="list canaries")
    p_canaries.add_argument("--recipient", default=None)
    _add_db(p_canaries, suppress=True)

    p_seed = sub.add_parser("seed", help="seed a CSV export with a recipient's canaries")
    p_seed.add_argument("--recipient", required=True)
    p_seed.add_argument("--in", dest="input", required=True)
    p_seed.add_argument("--out", dest="output", required=True)
    _add_db(p_seed, suppress=True)

    p_check = sub.add_parser("check", help="scan a suspect dataset for canary markers")
    p_check.add_argument("file")
    p_check.add_argument("--json", action="store_true", help="output JSON")
    _add_db(p_check, suppress=True)

    return parser


def _db_path(args: argparse.Namespace) -> str:
    return getattr(args, "db", None) or DEFAULT_DB


def _list_recipients(reg: Registry) -> int:
    recipients = reg.list_recipients()
    if not recipients:
        print("No recipients yet.")
        return 0
    for r in recipients:
        count = len(reg.list_canaries(r.name))
        print(f"{r.id}: {r.name} ({count} canaries, added {r.created_at})")
    return 0


def _list_canaries(reg: Registry, recipient: str | None) -> int:
    canaries = reg.list_canaries(recipient)
    if not canaries:
        print("No canaries found.")
        return 0
    for c in canaries:
        seeded = f" seeded into: {', '.join(c.seeded_into)}" if c.seeded_into else ""
        print(
            f"{c.record_id}  {c.email}  {c.phone}  {c.token}  "
            f"-> {c.recipient_name}{seeded}"
        )
    print(f"Total: {len(canaries)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with Registry(_db_path(args)) as reg:
            if args.command == "recipient":
                if args.recipient_command == "add":
                    recipient = reg.add_recipient(args.name)
                    print(f"Added recipient #{recipient.id}: {recipient.name}")
                    return 0
                return _list_recipients(reg)

            if args.command == "recipients":
                return _list_recipients(reg)

            if args.command == "generate":
                canaries = generate_canaries(reg, args.recipient, args.count)
                for c in canaries:
                    print(f"{c.record_id}  {c.email}  {c.phone}  {c.token}")
                print(f"Generated {len(canaries)} canaries for {args.recipient}.")
                return 0

            if args.command == "canaries":
                return _list_canaries(reg, args.recipient)

            if args.command == "seed":
                recipient = reg.get_recipient(args.recipient)
                if recipient is None:
                    print(f"error: unknown recipient: {args.recipient}", file=sys.stderr)
                    return 2
                canaries = reg.list_canaries(args.recipient)
                if not canaries:
                    print(
                        f"error: no canaries for {args.recipient}; "
                        "run `canarydata generate` first",
                        file=sys.stderr,
                    )
                    return 2
                inserted = seed_csv(args.input, args.output, canaries)
                reg.record_seed_event(
                    recipient, args.input, args.output,
                    [c.canary_id for c in canaries],
                )
                print(
                    f"Seeded {inserted} canaries for {args.recipient} "
                    f"into {args.output} (from {args.input})."
                )
                return 0

            if args.command == "check":
                report = scan_file(args.file, reg.list_canaries())
                print(report_json(report) if args.json else format_report(report))
                return 0

    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2  # unreachable: argparse enforces a command


if __name__ == "__main__":
    raise SystemExit(main())
