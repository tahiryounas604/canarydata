"""Seeding: mix one recipient's canary rows into a copy of a CSV export.

Guarantees:
- The output has exactly the input's columns, in the same order.
- Every original record appears in the output with identical values
  (parsed CSV values are compared exactly by the test suite).
- Only the chosen recipient's canaries are added — never another
  recipient's — spread through the file rather than appended as a
  tell-tale block at the end.
"""
from __future__ import annotations

import csv
from pathlib import Path

from canarydata.models import Canary


def canary_to_row(canary: Canary, fieldnames: list[str]) -> dict[str, str]:
    """Map a canary onto whatever columns the export actually has.

    Unknown columns are left empty; recognised columns are matched by
    name (case-insensitive substring), so common export layouts —
    ``id,name,email,phone``, ``customer_id,full_name,email_address,...``
    — all work without configuration.
    """
    row: dict[str, str] = {}
    for col in fieldnames:
        lc = col.lower().strip()
        if "email" in lc:
            row[col] = canary.email
        elif "first" in lc and "name" in lc:
            row[col] = canary.first_name
        elif "last" in lc and "name" in lc:
            row[col] = canary.last_name
        elif "name" in lc:
            row[col] = canary.name
        elif "phone" in lc or "mobile" in lc or lc.startswith("tel"):
            row[col] = canary.phone
        elif "token" in lc or "canary" in lc or "ref" in lc:
            row[col] = canary.token
        elif lc == "id" or lc.endswith("_id") or "record" in lc:
            row[col] = canary.record_id
        elif "city" in lc:
            row[col] = canary.city
        elif "address" in lc or "street" in lc:
            row[col] = canary.address
        elif "company" in lc or "organi" in lc:
            row[col] = canary.company
        elif "country" in lc:
            row[col] = "United States"
        else:
            row[col] = ""
    return row


def _spread_positions(n_originals: int, n_canaries: int) -> list[int]:
    """Insertion offsets (in original-row index space), evenly spread."""
    if n_originals == 0:
        return [0] * n_canaries
    step = (n_originals + 1) / (n_canaries + 1)
    return [min(n_originals, int(step * (i + 1))) for i in range(n_canaries)]


def seed_csv(
    input_path: str | Path, output_path: str | Path, canaries: list[Canary]
) -> int:
    """Write ``output_path``: original rows untouched + canary rows mixed in.

    Returns the number of canary rows inserted.
    """
    with open(input_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"input CSV has no header row: {input_path}")
        fieldnames = list(reader.fieldnames)
        originals = [dict(row) for row in reader]

    canary_rows = [canary_to_row(c, fieldnames) for c in canaries]
    positions = _spread_positions(len(originals), len(canary_rows))

    merged: list[dict[str, str]] = []
    pending = sorted(zip(positions, canary_rows), key=lambda p: p[0])
    idx = 0
    for i, original in enumerate(originals):
        while idx < len(pending) and pending[idx][0] <= i:
            merged.append(pending[idx][1])
            idx += 1
        merged.append(original)
    while idx < len(pending):
        merged.append(pending[idx][1])
        idx += 1

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)
    return len(canary_rows)
