from canarydata.generator import generate_canaries


def test_canaries_never_collide_across_many_recipients(registry):
    all_canaries = []
    for i in range(20):
        name = f"Recipient {i}"
        registry.add_recipient(name)
        all_canaries.extend(generate_canaries(registry, name, 20))

    assert len(all_canaries) == 400
    for attr in ("email", "record_id", "token", "phone", "canary_id"):
        values = [getattr(c, attr) for c in all_canaries]
        assert len(set(values)) == len(values), f"collision in {attr}"


def test_each_canary_traces_to_exactly_one_recipient(registry):
    registry.add_recipient("Partner A")
    registry.add_recipient("Partner B")
    a = generate_canaries(registry, "Partner A", 5)
    b = generate_canaries(registry, "Partner B", 5)
    assert all(c.recipient_name == "Partner A" for c in a)
    assert all(c.recipient_name == "Partner B" for c in b)
    a_emails = {c.email for c in a}
    assert not a_emails & {c.email for c in b}


def test_generate_rejects_unknown_recipient_and_bad_count(registry):
    registry.add_recipient("Partner A")
    for bad in (lambda: generate_canaries(registry, "Nobody", 1),
                lambda: generate_canaries(registry, "Partner A", 0)):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")
