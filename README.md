# canarydata

Data-leak attribution with per-recipient canary records: **which
recipient's copy leaked?**

You share the same customer export with several partners. One of the
copies surfaces somewhere it shouldn't. canarydata plants a handful of
unique, realistic fake customer rows ("canaries") into each recipient's
copy — a different set per recipient — keeps the mapping in a local
SQLite registry, and later scans a suspect dataset for those markers.
Any canary that fires names exactly one recipient.

## Features

- **Per-recipient canary generation** — realistic fake customer rows
  (name, unique email alias, phone, record ID) plus a unique hidden
  token per canary. Every marker is globally unique across all
  recipients (random generation, collision-checked against the
  registry, and enforced by SQLite `UNIQUE` constraints).
- **Subtle per-recipient variation** — each recipient is assigned a
  phone area-code / city / street pool, so seeded rows differ in
  plausible low-key ways beyond the unique markers themselves.
- **SQLite registry** — recipient ↔ canary mapping, plus a seed-event
  history recording which export each canary was seeded into, and when.
- **`seed` command** — writes a new CSV containing the original records
  unchanged (same values, same columns) with only that recipient's
  canary rows mixed in, spread through the file rather than appended
  as a block. Canary fields are mapped onto the export's own column
  names (`id`/`customer_id`, `name`/`full_name`, `email`/`email_address`,
  `phone`, `city`, …); unknown columns are left empty.
- **`check` command** — scans a suspect dataset (CSV, JSON, or plain
  text — the scan is format-agnostic) for canary markers (email alias,
  record ID, token, phone) and reports which recipient's copy leaked,
  which specific canaries fired, and per-marker match counts.
  Human-readable output by default, `--json` for machine-readable.
- **Management commands** — add/list recipients, generate and list
  canaries.
- **Standard library only.** No third-party dependencies, no network,
  no live external services.

## Install

Python 3.11 or 3.12. Standard library only.

```bash
git clone https://github.com/tahiryounas604/canarydata.git
cd canarydata
pip install .
# or run without installing:
PYTHONPATH=src python3 -m canarydata --help
```

## Usage

```bash
# 1. Register the people/partners you share exports with
canarydata recipient add "Partner A"
canarydata recipient add "Partner B"
canarydata recipients            # list

# 2. Generate a unique canary set for each recipient
canarydata generate --recipient "Partner A" --count 5
canarydata canaries --recipient "Partner A"   # list

# 3. Seed each recipient's copy of an export
canarydata seed --recipient "Partner A" --in customers.csv --out customers_partnerA.csv
canarydata seed --recipient "Partner B" --in customers.csv --out customers_partnerB.csv

# 4. Later: a dataset surfaces somewhere it shouldn't — scan it
canarydata check leaked.csv
canarydata check leaked.json --json
```

Example `check` output:

```
LEAK DETECTED in customers_partnerA.csv
Recipients identified: Partner A
Canaries fired: 3
  Partner A: 3 canary record(s)
Detail:
  - CUST-C2115BD0 (noah.singh.0a77f79eed@example.com) -> Partner A [email x1, phone x1, record_id x1]
  ...
```

If nothing fires: `No canary markers found in <file>.`

The registry defaults to `./canarydata.db` (override with the global
`--db PATH` option before the subcommand, or the `CANARYDATA_DB`
environment variable). Keep the registry private and backed up — it is
the only thing that links a canary to a recipient.

An example export is in [`examples/customers.csv`](examples/customers.csv).

## Architecture

```
src/canarydata/
├── models.py      Recipient and Canary dataclasses; canary marker set
├── registry.py    SQLite registry: recipients, canaries, seed events
├── generator.py   Fake-row generation; uniqueness + per-recipient pools
├── seeding.py     CSV seeding: column mapping, originals untouched,
│                  canaries spread through the output
├── detection.py   Format-agnostic text scan for markers; reports
└── cli.py         argparse CLI: recipient / generate / canaries /
                   seed / check
```

Flow: `generate` stores canaries in the registry → `seed` reads the
registry, maps that recipient's canaries onto the export's columns and
records a seed event → `check` loads every canary's markers from the
registry and counts occurrences in the suspect file.

## Tests

```bash
python -m pytest -q
```

16 tests, covering: uniqueness across 20 recipients × 20 canaries
(emails, record IDs, tokens, phones never collide); seeding correctness
(original rows exactly unchanged, column structure preserved, exactly
the right recipient's canaries added); detection positive on a seeded
file; detection negative on the original un-seeded data; cross-recipient
isolation (A's canaries never appear in B's file and never attribute
B's file to A); detection in JSON and plain text; registry round-trip
through a reopened database; and the full CLI flow end to end.

## Honest limits

- **No live monitoring in v0.1.** canarydata does not watch canary
  email inboxes, paste sites, or any external service. Detection works
  only by scanning a suspect dataset you already have. (The canary
  email domain is `example.com`, a reserved domain — these addresses
  are synthetic markers, not monitored mailboxes.)
- **Attribution requires a canary to survive.** If a leaked copy has
  the canary rows removed — or is transformed so no marker (email,
  record ID, token, phone) survives, e.g. re-typed or heavily
  normalised data — the scan finds nothing. More canaries per copy
  raise the chance that at least one survives.
- **A hit proves the copy, not the person.** A fired canary shows the
  data came from that recipient's seeded export; it does not by itself
  prove who at that recipient leaked it, or that the recipient leaked
  it deliberately (their copy could itself have been stolen).
- **CSV seeding only.** `seed` handles CSV exports; `check` scans CSV,
  JSON, and plain text because it searches the raw text for markers.
- **Phone numbers use the fictional 555 range** and all rows are
  synthetic — canaries are fake customers by design, and should be
  excluded from any real outreach, billing, or analytics run on a
  seeded export.
- **Local, single-user tool.** The registry is a local SQLite file
  with no access control of its own; protect it with filesystem
  permissions.

## License

GPL-3.0 — see [LICENSE](LICENSE).

## Author

Tahir Younas — Tytechlabs — https://www.linkedin.com/in/tahiryounas604
