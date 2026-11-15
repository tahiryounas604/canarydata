"""Detection: scan a suspect dataset for canary markers.

The scan is format-agnostic: the file (CSV, JSON, or plain text) is
read as text and searched for each canary's markers — email alias,
record ID, unique token, and phone. Matching is case-insensitive for
the alphanumeric markers. A hit attributes that canary, and therefore
its recipient, to the suspect dataset.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from canarydata.models import Canary


@dataclass
class CanaryMatch:
    canary_id: str
    recipient_name: str
    email: str
    record_id: str
    marker_counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.marker_counts.values())


@dataclass
class DetectionReport:
    source: str
    matches: list[CanaryMatch] = field(default_factory=list)

    @property
    def recipients(self) -> list[str]:
        return sorted({m.recipient_name for m in self.matches})

    def counts_by_recipient(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in self.matches:
            counts[m.recipient_name] = counts.get(m.recipient_name, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "recipients": self.recipients,
            "canaries_fired": len(self.matches),
            "counts_by_recipient": self.counts_by_recipient(),
            "matches": [
                {
                    "canary_id": m.canary_id,
                    "recipient": m.recipient_name,
                    "email": m.email,
                    "record_id": m.record_id,
                    "marker_counts": m.marker_counts,
                    "total_matches": m.total,
                }
                for m in self.matches
            ],
        }


def scan_text(text: str, canaries: list[Canary], source: str = "<text>") -> DetectionReport:
    haystack = text.lower()
    report = DetectionReport(source=source)
    for canary in canaries:
        counts: dict[str, int] = {}
        for marker_type, value in canary.markers().items():
            if not value:
                continue
            n = haystack.count(value.lower())
            if n:
                counts[marker_type] = n
        if counts:
            report.matches.append(
                CanaryMatch(
                    canary_id=canary.canary_id,
                    recipient_name=canary.recipient_name,
                    email=canary.email,
                    record_id=canary.record_id,
                    marker_counts=counts,
                )
            )
    return report


def scan_file(path: str | Path, canaries: list[Canary]) -> DetectionReport:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return scan_text(text, canaries, source=str(path))


def format_report(report: DetectionReport) -> str:
    if not report.matches:
        return f"No canary markers found in {report.source}."
    lines = [
        f"LEAK DETECTED in {report.source}",
        f"Recipients identified: {', '.join(report.recipients)}",
        f"Canaries fired: {len(report.matches)}",
    ]
    for name, count in sorted(report.counts_by_recipient().items()):
        lines.append(f"  {name}: {count} canary record(s)")
    lines.append("Detail:")
    for m in report.matches:
        markers = ", ".join(f"{k} x{v}" for k, v in sorted(m.marker_counts.items()))
        lines.append(
            f"  - {m.record_id} ({m.email}) -> {m.recipient_name} [{markers}]"
        )
    return "\n".join(lines)


def report_json(report: DetectionReport) -> str:
    return json.dumps(report.to_dict(), indent=2)
