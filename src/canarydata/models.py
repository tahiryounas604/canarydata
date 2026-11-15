"""Data models for recipients and canary records."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Recipient:
    id: int | None
    name: str
    created_at: str


@dataclass
class Canary:
    """One fake customer row, unique to exactly one recipient.

    Every identifying field (email, record_id, phone, token) is globally
    unique across all recipients, enforced both by generation (random
    tokens, collision-checked against the registry) and by UNIQUE
    constraints in the SQLite registry.
    """

    canary_id: str
    recipient_id: int
    recipient_name: str
    name: str
    email: str
    phone: str
    record_id: str
    token: str
    city: str = ""
    address: str = ""
    company: str = ""
    created_at: str = ""
    seeded_into: list[str] = field(default_factory=list)

    @property
    def first_name(self) -> str:
        return self.name.split(" ", 1)[0] if self.name else ""

    @property
    def last_name(self) -> str:
        parts = self.name.split(" ", 1)
        return parts[1] if len(parts) > 1 else ""

    def markers(self) -> dict[str, str]:
        """Values a leak scan looks for, by marker type."""
        return {
            "email": self.email,
            "record_id": self.record_id,
            "token": self.token,
            "phone": self.phone,
        }
