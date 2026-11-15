from canarydata.generator import generate_canaries
from canarydata.seeding import canary_to_row, seed_csv

from conftest import BASE_ROWS, FIELDNAMES, read_rows


def test_seeding_preserves_originals_and_columns(registry, base_csv, tmp_path):
    registry.add_recipient("Partner A")
    canaries = generate_canaries(registry, "Partner A", 3)
    out = tmp_path / "seeded.csv"
    inserted = seed_csv(base_csv, out, canaries)
    assert inserted == 3

    fieldnames, rows = read_rows(out)
    assert fieldnames == FIELDNAMES
    assert len(rows) == len(BASE_ROWS) + 3

    # Every original row present, values exactly unchanged.
    for original in BASE_ROWS:
        assert original in rows

    # Remaining rows are exactly this recipient's canaries, mapped onto
    # the export's columns.
    canary_rows = [r for r in rows if r not in BASE_ROWS]
    expected = [canary_to_row(c, FIELDNAMES) for c in canaries]
    assert sorted(r["email"] for r in canary_rows) == sorted(
        r["email"] for r in expected
    )
    for row in canary_rows:
        assert row in expected


def test_seeding_with_no_original_rows(registry, tmp_path):
    import csv as csv_mod

    registry.add_recipient("Partner A")
    canaries = generate_canaries(registry, "Partner A", 2)
    empty = tmp_path / "empty.csv"
    with open(empty, "w", newline="", encoding="utf-8") as fh:
        csv_mod.DictWriter(fh, fieldnames=FIELDNAMES).writeheader()
    out = tmp_path / "out.csv"
    assert seed_csv(empty, out, canaries) == 2
    _, rows = read_rows(out)
    assert len(rows) == 2
