"""The kill switch stops a run and an approval before any model call."""

import json

from leadgen.approve import main as approve_main
from leadgen.run import main as run_main


def test_kill_switch_blocks_run_and_approve(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "1")
    assert (
        run_main(["--profile", "b2b_services", "--prospect", "B2B-001"], root=tmp_path) == 1
    )
    assert (
        approve_main(
            [
                "--profile",
                "b2b_services",
                "--prospect",
                "B2B-001",
                "--latest",
                "--name",
                "Ada",
                "--decision",
                "APPROVED",
            ],
            root=tmp_path,
        )
        == 1
    )
    path = tmp_path / "runs" / "flight_recorder.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert any(row["event_type"] == "kill_switch_block" for row in rows)
    assert not any(row["event_type"] == "model_call" for row in rows)
    assert not (tmp_path / "outbox").exists()
