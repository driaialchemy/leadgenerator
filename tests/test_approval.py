"""Approval refuses a bad sign-off and writes the outbox only after a yes."""

import ast
import json

from leadgen.approve import main
from leadgen.pipeline import run_prospect
from leadgen.loaders import load_prospects
from leadgen.profiles import load_pipeline_config, load_profile


def test_approval_refuses_bad_signoffs(tmp_path, capsys):
    blocked = tmp_path / "runs" / "B2B-009-20261119T000000000000Z"
    blocked.mkdir(parents=True)
    (blocked / "status.json").write_text(
        json.dumps(
            {
                "prospect_id": "B2B-009",
                "profile_id": "b2b_services",
                "status": "BLOCKED",
                "evaluator_below_bar": False,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    assert _approve(tmp_path, "b2b_services", "B2B-009", "APPROVED", "Ada") == 1
    assert "BLOCKED" in capsys.readouterr().out

    _run(tmp_path, "b2b_services", "B2B-004")
    assert _approve(tmp_path, "b2b_services", "B2B-004", "APPROVED", "Ada") == 1
    assert "acknowledged" in capsys.readouterr().out.lower()

    _run(tmp_path, "home_services", "HOME-001")
    assert _approve(tmp_path, "home_services", "HOME-001", "APPROVED", "   ") == 1
    assert "name" in capsys.readouterr().out.lower()
    assert _approve(tmp_path, "home_services", "HOME-001", "REJECTED", "Ada") == 0
    assert not (tmp_path / "outbox").exists() or list((tmp_path / "outbox").glob("*.txt")) == []
    assert _approve(tmp_path, "home_services", "HOME-001", "APPROVED", "Ada") == 1
    assert "already" in capsys.readouterr().out.lower()


def test_edit_with_a_percent_is_refused(tmp_path, capsys):
    _run(tmp_path, "home_services", "HOME-001")
    code = main(
        [
            "--profile",
            "home_services",
            "--prospect",
            "HOME-001",
            "--latest",
            "--name",
            "Ada",
            "--decision",
            "EDITED",
            "--hook",
            "Save 50% this month on a tune-up.",
            "--bridge",
            "A same-week look can come before any work:",
        ],
        root=tmp_path,
    )
    assert code == 1
    assert "verification" in capsys.readouterr().out.lower()
    assert not (tmp_path / "outbox").exists() or list((tmp_path / "outbox").glob("*.txt")) == []


def test_draft_changed_on_disk_is_refused(tmp_path, capsys):
    result = _run(tmp_path, "home_services", "HOME-001")
    draft_path = result.run_dir / "draft.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["hook"] = draft["hook"] + " today"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    code = _approve(tmp_path, "home_services", "HOME-001", "APPROVED", "Ada")
    assert code == 1
    assert "changed" in capsys.readouterr().out.lower()


def test_approved_run_writes_one_outbox_file(tmp_path):
    result = _run(tmp_path, "home_services", "HOME-001")
    assert _approve(tmp_path, "home_services", "HOME-001", "APPROVED", "Ada") == 0
    files = list((tmp_path / "outbox").glob("*.txt"))
    assert len(files) == 1
    assert files[0].name == result.run_dir.name + ".txt"
    assert "Subject:" in files[0].read_text(encoding="utf-8")


def test_outbox_imports_no_send_library():
    source = (Path_of_outbox()).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module.split(".")[0])
    for name in ("smtplib", "socket", "requests", "httpx", "email"):
        assert name not in imported


def _run(root, profile_id, prospect_id):
    profile = load_profile(profile_id)
    prospect = next(item for item in load_prospects(profile) if item.prospect_id == prospect_id)
    return run_prospect(profile, prospect, load_pipeline_config(), root)


def _approve(root, profile_id, prospect_id, decision, name, ack=False):
    args = [
        "--profile",
        profile_id,
        "--prospect",
        prospect_id,
        "--latest",
        "--name",
        name,
        "--decision",
        decision,
    ]
    if ack:
        args.append("--ack-findings")
    return main(args, root=root)


def Path_of_outbox():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "src" / "leadgen" / "outbox.py"
