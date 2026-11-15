import csv

import pytest

from canarydata.registry import Registry

BASE_ROWS = [
    {"id": "1", "name": "Alice Real", "email": "alice.real@gmail.com",
     "phone": "+1-212-555-0101", "city": "New York"},
    {"id": "2", "name": "Bob Genuine", "email": "bob.genuine@yahoo.com",
     "phone": "+1-415-555-0102", "city": "San Francisco"},
    {"id": "3", "name": "Carol Actual", "email": "carol.actual@outlook.com",
     "phone": "+1-312-555-0103", "city": "Chicago"},
    {"id": "4", "name": "David True", "email": "david.true@gmail.com",
     "phone": "+1-206-555-0104", "city": "Seattle"},
]
FIELDNAMES = ["id", "name", "email", "phone", "city"]


@pytest.fixture()
def registry(tmp_path):
    with Registry(tmp_path / "registry.db") as reg:
        yield reg


@pytest.fixture()
def base_csv(tmp_path):
    path = tmp_path / "customers.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(BASE_ROWS)
    return path


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames), [dict(r) for r in reader]
