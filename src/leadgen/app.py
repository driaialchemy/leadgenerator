"""Class walkthrough. One prospect, from the ranked list to the outbox."""

import html
import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import streamlit as st

from leadgen.approve import decide, latest_run
from leadgen.check_keys import main as check_keys_main
from leadgen.kill_switch import KillSwitchEngaged
from leadgen.llm import ProviderError
from leadgen.loaders import load_prospects
from leadgen.pipeline import _log, run_prospect
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.ui_data import (
    attempt_comparison,
    data_root,
    draft_fields,
    evaluation_view,
    funnel_view,
    kill_message,
    logbook,
    markdown_table,
    outbox_rows,
    profile_ids,
    prospect_board,
    rendered_text,
    role_rows,
    run_status,
)
from leadgen.ui_theme import apply_theme, hero_path


def main() -> None:
    st.set_page_config(page_title="Lead and income", layout="wide")
    apply_theme()
    _init_state()
    root = data_root()
    killed = kill_message(root)
    profile_id = _sidebar(root, killed)
    if killed:
        st.error(killed)
    hero = hero_path()
    if hero is not None:
        st.image(str(hero))
    prospects, run, review, outbox, log, funnel = st.tabs(
        ["Prospects", "Run", "Review", "Outbox", "Logbook", "Funnel"]
    )
    with prospects:
        _prospects_tab(profile_id)
    with run:
        _run_tab(root, profile_id, killed)
    with review:
        _review_tab(root, profile_id, killed)
    with outbox:
        _outbox_tab(root)
    with log:
        _logbook_tab(root)
    with funnel:
        _funnel_tab(profile_id)


def _init_state() -> None:
    st.session_state.setdefault("stages", [])
    st.session_state.setdefault("last_run", "")
    st.session_state.setdefault("last_status", "")
    st.session_state.setdefault("decision", None)
    st.session_state.setdefault("notice", "")
    st.session_state.setdefault("key_report", "")


def _sidebar(root: Path, killed: str) -> str:
    st.sidebar.header("Setup")
    ids = profile_ids()
    profile_id = st.sidebar.selectbox("Profile", ids, key="profile")
    mode = role_rows()[0]["mode"]
    badge = "Live" if mode == "live" else "Offline"
    st.sidebar.markdown(f"**Mode: {badge}**")
    for row in role_rows():
        st.sidebar.markdown(f"{row['role']}: {row['provider']} · {row['model']}")
    st.sidebar.checkbox("Red-team toggle", key="red_team")
    if killed:
        st.sidebar.error(killed)
    else:
        st.sidebar.markdown("Kill switch: off")
    if st.sidebar.button("Check keys", key="check_keys"):
        buffer = StringIO()
        with redirect_stdout(buffer):
            check_keys_main()
        st.session_state.key_report = buffer.getvalue()
    if st.session_state.key_report:
        st.sidebar.code(st.session_state.key_report)
    return profile_id


def _prospects_tab(profile_id: str) -> None:
    st.header("Prospects")
    st.markdown('<span class="capex-label capex-code">Code</span>', unsafe_allow_html=True)
    board = prospect_board(profile_id)
    st.markdown(
        markdown_table(
            [
                {
                    "prospect_id": row["prospect_id"],
                    "score": row["score"],
                    "tier": row["tier"],
                    "draft": "yes" if row["draft_eligible"] else "no",
                }
                for row in board["ranked"]
            ],
            ["prospect_id", "score", "tier", "draft"],
        )
    )
    for row in board["ranked"]:
        with st.expander(f"Rules {row['prospect_id']}"):
            for hit in row["rule_hits"]:
                mark = "yes" if hit["matched"] else "no"
                st.markdown(f"{hit['field']}: {hit['points']} points, matched {mark}")
    st.subheader("Excluded")
    st.markdown(markdown_table(board["excluded"], ["prospect_id", "reason"]))
    st.subheader("Findings")
    st.markdown(
        markdown_table(board["findings"], ["prospect_id", "check_id", "message"])
    )


def _run_tab(root: Path, profile_id: str, killed: str) -> None:
    st.header("Run")
    board = prospect_board(profile_id)
    eligible = board["eligible_ids"]
    if not eligible:
        st.info("No draft-eligible prospect.")
        return
    if st.session_state.get("prospect") not in eligible:
        st.session_state.prospect = eligible[0]
    prospect_id = st.selectbox("Prospect", eligible, key="prospect")
    if st.button("Run", key="run", disabled=bool(killed)):
        _start_run(root, profile_id, prospect_id)
    if st.session_state.notice:
        st.error(st.session_state.notice)
    if st.session_state.last_status:
        st.markdown(f"Status: {st.session_state.last_status}")
    for stage in st.session_state.stages:
        _show_stage(stage)
    if st.session_state.last_run:
        _show_attempts(Path(st.session_state.last_run))


def _start_run(root: Path, profile_id: str, prospect_id: str) -> None:
    st.session_state.stages = []
    st.session_state.notice = ""
    st.session_state.decision = None
    st.session_state.last_status = ""
    st.session_state.last_run = ""
    profile = load_profile(profile_id)
    prospect = next(item for item in load_prospects(profile) if item.prospect_id == prospect_id)
    pipeline = load_pipeline_config()
    if st.session_state.get("red_team"):
        os.environ["LEADGEN_DEMO_TEMPT"] = "1"
    else:
        os.environ.pop("LEADGEN_DEMO_TEMPT", None)
    try:
        result = run_prospect(
            profile, prospect, pipeline, root, on_progress=_push_stage
        )
    except ProviderError as exc:
        _log(
            root,
            prospect_id,
            "error",
            exc.role,
            "fail",
            exc.line(),
            provider=exc.provider,
            model=exc.model,
        )
        st.session_state.notice = (
            f"{exc.role} {exc.provider}: {exc.line()}. switch to Offline or fix the account"
        )
        return
    except KillSwitchEngaged as exc:
        st.session_state.notice = str(exc)
        return
    finally:
        os.environ.pop("LEADGEN_DEMO_TEMPT", None)
    st.session_state.last_status = result.status
    if result.run_dir is not None:
        st.session_state.last_run = str(result.run_dir)


def _push_stage(payload: dict) -> None:
    st.session_state.stages.append(payload)


def _show_stage(stage: dict) -> None:
    seconds = stage.get("seconds")
    clock = "" if seconds is None else f"{seconds}s"
    mark = "pass" if stage.get("passed") else "fail"
    provider = stage.get("provider") or ""
    model = stage.get("model") or ""
    line = " ".join(
        part for part in (str(stage.get("role") or ""), provider, model, clock, mark) if part
    )
    st.markdown(line)
    if stage.get("stage") in {"verifier", "retry", "gate", "evaluator"} and not stage.get("passed"):
        st.markdown(str(stage.get("detail") or ""))


def _show_attempts(run_dir: Path) -> None:
    attempts = attempt_comparison(run_dir)
    if len(attempts) < 2:
        for row in attempts:
            st.markdown(f"Attempt {row['attempt']}")
        return
    columns = st.columns(len(attempts))
    for column, row in zip(columns, attempts):
        with column:
            st.markdown(f"Attempt {row['attempt']}")
            _attempt_body(row)


def _attempt_body(row: dict) -> None:
    if row["passed"]:
        st.markdown("pass")
        st.markdown(row["hook"])
        st.markdown(row["bridge"])
        return
    codes = ", ".join(row["codes"])
    st.markdown(f"Blocked: {codes}")
    st.markdown(
        f'<div class="blocked-draft">{html.escape(row["hook"])}<br>{html.escape(row["bridge"])}</div>',
        unsafe_allow_html=True,
    )


def _review_tab(root: Path, profile_id: str, killed: str) -> None:
    st.header("Review")
    st.markdown('<span class="capex-label capex-human">Person</span>', unsafe_allow_html=True)
    run_dir = _selected_run(root)
    if run_dir is None:
        st.info("Run a prospect first.")
        st.button("Approve", key="approve", disabled=True)
        return
    status = run_status(run_dir)
    st.markdown(f"Status: {status['status']}")
    if status.get("evaluator_below_bar"):
        st.markdown("Evaluator is still under the bar.")
    st.subheader("Email")
    st.code(rendered_text(run_dir))
    st.subheader("Attempts")
    attempts = attempt_comparison(run_dir)
    if attempts:
        columns = st.columns(len(attempts))
        for column, row in zip(columns, attempts):
            with column:
                st.markdown(f"Attempt {row['attempt']}")
                _attempt_body(row)
    scores = evaluation_view(run_dir)
    if scores:
        st.subheader("Evaluator")
        bar = scores["bar"]
        for name in ("relevance", "specificity", "clarity", "tone"):
            st.markdown(f"{name}: {scores[name]} (bar {bar})")
        for suggestion in scores.get("suggestions") or []:
            st.markdown(suggestion)
    st.subheader("Findings")
    findings = status.get("findings") or []
    if findings:
        for finding in findings:
            st.markdown(f"{finding['check_id']}: {finding['message']}")
    else:
        st.markdown("None.")
    st.checkbox("Acknowledge findings", key="ack")
    name = st.text_input("Approver", key="approver")
    fields = draft_fields(run_dir)
    if st.session_state.get("edit_run") != run_dir.name:
        st.session_state.edit_hook = fields["hook"]
        st.session_state.edit_bridge = fields["bridge"]
        st.session_state.edit_run = run_dir.name
    hook = st.text_area("Hook", key="edit_hook")
    bridge = st.text_area("Bridge", key="edit_bridge")
    disabled = bool(killed)
    prospect_id = st.session_state.get("prospect") or status["prospect_id"]
    approve, edit, reject = st.columns(3)
    if approve.button("Approve", key="approve", disabled=disabled):
        _store_decision(root, profile_id, prospect_id, "APPROVED", name, hook, bridge)
    if edit.button("Edit", key="edit", disabled=disabled):
        _store_decision(root, profile_id, prospect_id, "EDITED", name, hook, bridge)
    if reject.button("Reject", key="reject", disabled=disabled):
        _store_decision(root, profile_id, prospect_id, "REJECTED", name, hook, bridge)
    _show_decision()


def _store_decision(root, profile_id, prospect_id, decision, name, hook, bridge) -> None:
    code, message = decide(
        root,
        profile_id,
        prospect_id,
        decision,
        name,
        bool(st.session_state.get("ack")),
        hook,
        bridge,
    )
    st.session_state.decision = (code, message)


def _show_decision() -> None:
    decision = st.session_state.decision
    if not decision:
        return
    code, message = decision
    if code == 0:
        st.success(message)
    else:
        st.error(message)


def _selected_run(root: Path) -> Path | None:
    prospect_id = st.session_state.get("prospect")
    last = st.session_state.get("last_run") or ""
    if last and prospect_id and Path(last).name.startswith(prospect_id + "-"):
        return Path(last)
    if not prospect_id:
        return None
    try:
        return latest_run(root, prospect_id)
    except FileNotFoundError:
        return None


def _outbox_tab(root: Path) -> None:
    st.header("Outbox")
    rows = outbox_rows(root)
    if not rows:
        st.info("No emails yet.")
        return
    for row in rows:
        st.markdown(f"{row['file']} approved by {row['approver']}")
        st.code(row["text"])


def _logbook_tab(root: Path) -> None:
    st.header("Logbook")
    st.markdown('<span class="capex-label capex-record">Record</span>', unsafe_allow_html=True)
    run_dir = _selected_run(root)
    if run_dir is None:
        st.info("No run selected.")
        return
    rows = logbook(root, run_dir.name)
    if not rows:
        st.info("No events for this run.")
        return
    st.markdown(
        markdown_table(
            rows,
            [
                "event_type",
                "attempt_number",
                "retry_of",
                "retry_reason",
                "red_team",
                "provider",
                "model",
                "duration_ms",
            ],
        )
    )


def _funnel_tab(profile_id: str) -> None:
    st.header("Funnel")
    stats = funnel_view(profile_id)
    for key, value in stats.items():
        st.markdown(f"{key}: {value}")


main()
