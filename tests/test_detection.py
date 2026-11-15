import json

from canarydata.detection import scan_file, scan_text
from canarydata.generator import generate_canaries
from canarydata.seeding import seed_csv


def _setup(registry):
    registry.add_recipient("Partner A")
    registry.add_recipient("Partner B")
    a = generate_canaries(registry, "Partner A", 4)
    b = generate_canaries(registry, "Partner B", 4)
    return a, b


def test_detection_positive_on_seeded_file(registry, base_csv, tmp_path):
    a, _ = _setup(registry)
    out = tmp_path / "leaked.csv"
    seed_csv(base_csv, out, a)
    report = scan_file(out, registry.list_canaries())
    assert report.recipients == ["Partner A"]
    assert len(report.matches) == len(a)
    fired_ids = {m.record_id for m in report.matches}
    assert fired_ids == {c.record_id for c in a}
    assert all(m.total >= 1 for m in report.matches)


def test_detection_negative_on_original_data(registry, base_csv):
    _setup(registry)
    report = scan_file(base_csv, registry.list_canaries())
    assert report.matches == []
    assert report.recipients == []


def test_cross_recipient_isolation(registry, base_csv, tmp_path):
    a, b = _setup(registry)
    out_b = tmp_path / "for_b.csv"
    seed_csv(base_csv, out_b, b)

    # A's canaries do not appear anywhere in B's file.
    text_b = out_b.read_text(encoding="utf-8")
    for canary in a:
        for marker in canary.markers().values():
            assert marker not in text_b

    report = scan_file(out_b, registry.list_canaries())
    assert report.recipients == ["Partner B"]
    assert len(report.matches) == len(b)


def test_detection_in_json_and_plain_text(registry):
    a, _ = _setup(registry)
    target = a[0]
    json_text = json.dumps([{"email": target.email, "id": target.record_id}])
    report = scan_text(json_text, registry.list_canaries(), source="dump.json")
    assert report.recipients == ["Partner A"]
    assert len(report.matches) == 1
    assert report.matches[0].marker_counts["email"] == 1
    assert report.matches[0].marker_counts["record_id"] == 1

    text_report = scan_text(
        f"found this token in a paste: {target.token}",
        registry.list_canaries(), source="paste.txt",
    )
    assert text_report.recipients == ["Partner A"]
    assert text_report.matches[0].marker_counts == {"token": 1}


def test_detection_is_case_insensitive_for_email(registry):
    a, _ = _setup(registry)
    report = scan_text(a[1].email.upper(), registry.list_canaries())
    assert len(report.matches) == 1
    assert report.matches[0].canary_id == a[1].canary_id
