import pytest

from canarydata.generator import generate_canaries
from canarydata.registry import Registry


def test_registry_round_trip(tmp_path):
    db = tmp_path / "registry.db"
    with Registry(db) as reg:
        reg.add_recipient("Partner A")
        made = generate_canaries(reg, "Partner A", 3)
        reg.record_seed_event(
            reg.get_recipient("Partner A"), "customers.csv", "out_a.csv",
            [c.canary_id for c in made],
        )

    # Reopen from disk: everything must survive unchanged.
    with Registry(db) as reg:
        recipients = reg.list_recipients()
        assert [r.name for r in recipients] == ["Partner A"]
        loaded = reg.list_canaries("Partner A")
        assert len(loaded) == 3
        by_id = {c.canary_id: c for c in loaded}
        for original in made:
            got = by_id[original.canary_id]
            assert got.email == original.email
            assert got.record_id == original.record_id
            assert got.token == original.token
            assert got.phone == original.phone
            assert got.recipient_name == "Partner A"
            assert got.seeded_into == ["out_a.csv"]
        events = reg.list_seed_events()
        assert len(events) == 1
        assert events[0]["output_file"] == "out_a.csv"
        assert events[0]["canary_count"] == 3


def test_duplicate_recipient_rejected(registry):
    registry.add_recipient("Partner A")
    with pytest.raises(ValueError):
        registry.add_recipient("Partner A")


def test_unknown_recipient_canaries_empty(registry):
    assert registry.list_canaries("Ghost") == []
    assert registry.get_recipient("Ghost") is None
