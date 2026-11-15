import json

from canarydata.cli import main

from conftest import read_rows


def _run(db, *argv):
    return main(["--db", str(db), *argv])


def test_cli_full_flow(tmp_path, base_csv, capsys):
    db = tmp_path / "cli.db"
    assert _run(db, "recipient", "add", "Partner A") == 0
    assert _run(db, "recipient", "add", "Partner B") == 0
    assert _run(db, "generate", "--recipient", "Partner A", "--count", "3") == 0
    assert _run(db, "generate", "--recipient", "Partner B", "--count", "3") == 0

    out_a = tmp_path / "for_a.csv"
    assert _run(db, "seed", "--recipient", "Partner A",
                "--in", str(base_csv), "--out", str(out_a)) == 0
    _, rows = read_rows(out_a)
    assert len(rows) == 7  # 4 originals + 3 canaries

    capsys.readouterr()  # drain
    assert _run(db, "check", str(out_a)) == 0
    out = capsys.readouterr().out
    assert "Partner A" in out
    assert "Partner B" not in out

    assert _run(db, "check", "--json", str(out_a)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["recipients"] == ["Partner A"]
    assert payload["canaries_fired"] == 3

    assert _run(db, "check", str(base_csv)) == 0
    assert "No canary markers found" in capsys.readouterr().out

    assert _run(db, "recipients") == 0
    listing = capsys.readouterr().out
    assert "Partner A" in listing and "Partner B" in listing

    assert _run(db, "canaries", "--recipient", "Partner A") == 0
    assert "Total: 3" in capsys.readouterr().out


def test_cli_db_flag_after_subcommand(tmp_path, monkeypatch):
    # --db must be honoured wherever it appears, and must not fall back
    # to a default database in the working directory.
    monkeypatch.chdir(tmp_path)
    db = tmp_path / "chosen.db"
    assert main(["recipient", "add", "Solo", "--db", str(db)]) == 0
    assert db.exists()
    assert not (tmp_path / "canarydata.db").exists()
    assert main(["--db", str(db), "generate",
                 "--recipient", "Solo", "--count", "2"]) == 0
    assert not (tmp_path / "canarydata.db").exists()


def test_cli_seed_unknown_recipient_fails(tmp_path, base_csv):
    db = tmp_path / "cli.db"
    code = main(["--db", str(db), "seed", "--recipient", "Ghost",
                 "--in", str(base_csv), "--out", str(tmp_path / "x.csv")])
    assert code == 2
