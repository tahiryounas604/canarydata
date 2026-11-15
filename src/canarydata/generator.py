"""Canary generation: realistic fake customer rows, globally unique.

Uniqueness strategy: every marker (email alias, record ID, phone, token)
embeds fresh randomness from ``secrets``/``uuid`` and is checked against
every value already in the registry; on a collision the value is
regenerated. The registry's UNIQUE constraints are a second line of
defence — a canary that somehow collided could not be stored twice.

Subtle per-recipient variation: each recipient is assigned a phone
area code and a city/address pool by its registry index, so rows seeded
for different recipients differ in plausible, low-key ways beyond the
unique markers themselves.
"""
from __future__ import annotations

import secrets
import uuid

from canarydata.models import Canary
from canarydata.registry import Registry, utcnow

FIRST_NAMES = [
    "Amelia", "Noah", "Priya", "Marcus", "Sofia", "Daniel", "Aisha",
    "Tom", "Ingrid", "Carlos", "Mei", "Jonas", "Fatima", "Oliver",
    "Nadia", "Peter", "Lena", "Ravi", "Grace", "Omar",
]
LAST_NAMES = [
    "Sharma", "Johnson", "Garcia", "Novak", "Kim", "Haddad", "Brown",
    "Okafor", "Larsen", "Petrov", "Nguyen", "Ali", "Smith", "Kowalski",
    "Tanaka", "Meyer", "Costa", "Dubois", "Singh", "Fischer",
]
# (area code, city, street) pools — one pool per recipient index, cycled.
POOLS = [
    ("212", "New York", "Madison Avenue"),
    ("415", "San Francisco", "Mission Street"),
    ("312", "Chicago", "State Street"),
    ("206", "Seattle", "Pine Street"),
    ("617", "Boston", "Boylston Street"),
    ("303", "Denver", "Colfax Avenue"),
    ("512", "Austin", "Congress Avenue"),
    ("404", "Atlanta", "Peachtree Street"),
]
COMPANIES = [
    "Northwind Traders", "Blue Peak LLC", "Harbor Lane Co",
    "Summit Retail Group", "Cedar Works", "Bright Path Ltd",
]
EMAIL_DOMAIN = "example.com"  # reserved domain: rows are clearly synthetic


def _unique(make, taken: set[str], attempts: int = 100) -> str:
    for _ in range(attempts):
        value = make()
        if value not in taken:
            taken.add(value)
            return value
    raise RuntimeError("could not generate a unique value after 100 attempts")


def generate_canaries(
    registry: Registry, recipient_name: str, count: int
) -> list[Canary]:
    """Generate and store ``count`` new canaries for one recipient."""
    if count < 1:
        raise ValueError("count must be at least 1")
    recipient = registry.get_recipient(recipient_name)
    if recipient is None:
        raise ValueError(f"unknown recipient: {recipient_name}")

    existing = registry.existing_values()
    # Pool assignment is stable per recipient (based on registry order).
    recipients = registry.list_recipients()
    index = [r.id for r in recipients].index(recipient.id)
    area, city, street = POOLS[index % len(POOLS)]

    canaries: list[Canary] = []
    for _ in range(count):
        first = secrets.choice(FIRST_NAMES)
        last = secrets.choice(LAST_NAMES)
        name = f"{first} {last}"

        email = _unique(
            lambda: f"{first.lower()}.{last.lower()}."
                    f"{secrets.token_hex(5)}@{EMAIL_DOMAIN}",
            existing["email"],
        )
        record_id = _unique(
            lambda: f"CUST-{secrets.token_hex(4).upper()}",
            existing["record_id"],
        )
        token = _unique(
            lambda: f"cnry_{secrets.token_hex(8)}",
            existing["token"],
        )
        phone = _unique(
            lambda: f"+1-{area}-555-"
                    f"{secrets.randbelow(9000) + 1000}",
            existing["phone"],
        )
        canary = Canary(
            canary_id=str(uuid.uuid4()),
            recipient_id=recipient.id,
            recipient_name=recipient.name,
            name=name,
            email=email,
            phone=phone,
            record_id=record_id,
            token=token,
            city=city,
            address=f"{secrets.randbelow(900) + 100} {street}",
            company=secrets.choice(COMPANIES),
            created_at=utcnow(),
        )
        registry.add_canary(canary)
        canaries.append(canary)
    return canaries
