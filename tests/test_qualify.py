"""The qualify command prints a report and writes no files."""

from leadgen.qualify import main


def test_b2b_report_is_printed(capsys):
    assert main(["--profile", "b2b_services"]) == 0
    out = capsys.readouterr().out
    line = next(item for item in out.splitlines() if item.startswith("B2B-001"))
    assert "100" in line
    assert "hot" in line
    assert "yes" in line
    assert "do_not_contact" in out
    assert "pricing_question" in out
    assert "Prospect asked about price" in out
    assert "won_value 42000" in out


def test_kill_switch_exits_without_writing(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "1")
    assert main(["--profile", "b2b_services"], root=tmp_path) == 1
    assert "Kill switch" in capsys.readouterr().out
