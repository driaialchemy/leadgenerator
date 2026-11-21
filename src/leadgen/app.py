"""Class walkthrough. One prospect, from the ranked list to the outbox."""

import os
from pathlib import Path

import streamlit as st

from leadgen.approve import decide, latest_run
from leadgen.check_keys import main as check_keys_main
from leadgen.kill_switch import KillSwitchEngaged
from leadgen.llm import ConfigError, ProviderError, current_mode
from leadgen.loaders import load_prospects
from leadgen.pipeline import run_prospect
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.schemas import Prospect
from leadgen.search import remember_add, search
from leadgen.ui_data import (
    contact_channels,
    data_root,
    draft_fields,
    exclusion_label,
    funnel_view,
    kill_message,
    logbook,
    markdown_table,
    outbox_rows,
    profile_ids,
    profile_name,
    prospect_board,
    refresh_search,
    rendered_text,
    role_rows,
    run_status,
    run_steps,
    search_view,
    status_badge,
    summary_tiles,
    tier_label,
)
from leadgen.ui_theme import apply_theme, icon

STEPS = (
    "search",
    "shortlist",
    "run",
    "review",
    "outbox",
    "logbook",
    "funnel",
    "settings",
)
WIZARD = ("search", "shortlist", "run", "review", "outbox")
WIZARD_LABELS = {
    "search": "1 Find",
    "shortlist": "2 Shortlist",
    "run": "3 Draft",
    "review": "4 Review",
    "outbox": "5 Send",
}
LOCKS = {
    "run": (
        "Pick someone on the Shortlist first",
        "Pick someone on the Shortlist first",
        "shortlist",
        "unlock_run",
    ),
    "review": ("Nothing to review yet", "Go to Draft", "run", "unlock_review"),
    "outbox": ("Nothing sent yet", "Go to Review", "review", "unlock_outbox"),
}
FIELD_KIND = "field_kind"
FIELD_LOCATION = "field_location"
FIELD_FROM = "field_from"
FIELD_TO = "field_to"
FIELD_BUSINESS = "field_business"
FIELD_CONTACT = "field_contact"
FIELD_MAX = "field_max"


def main() -> None:
    st.set_page_config(page_title="Lead & Income Finder", layout="wide")
    apply_theme()
    _init_state()
    root = data_root()
    killed = kill_message(root)
    profile_id = _sidebar(killed)
    _consume_search(root, load_profile(profile_id))
    _consume_run(root, profile_id)
    _consume_decision(root, profile_id)
    st.markdown(
        '<div class="banner"><h1>Lead &amp; Income Finder</h1>'
        "<p>Find a business, draft a note from approved facts, and sign it before anything is saved.</p></div>",
        unsafe_allow_html=True,
    )
    _tiles(root, profile_id)
    _tracker()
    _lock_note()
    _hide_inactive()
    with _panel("search"):
        _search_tab(root, profile_id, killed)
    with _panel("shortlist"):
        _shortlist_tab(profile_id)
    with _panel("run"):
        _run_tab(root, profile_id, killed)
    with _panel("review"):
        _review_tab(root, profile_id, killed)
    with _panel("outbox"):
        _outbox_tab(root)
    with _panel("logbook"):
        _logbook_tab(root)
    with _panel("funnel"):
        _funnel_tab(profile_id)
    with _panel("settings"):
        _settings_tab(root)


def _init_state() -> None:
    st.session_state.setdefault("step", "search")
    st.session_state.setdefault("stages", [])
    st.session_state.setdefault("last_run", "")
    st.session_state.setdefault("last_status", "")
    st.session_state.setdefault("decision", None)
    st.session_state.setdefault("notice", "")
    st.session_state.setdefault("key_report", "")
    st.session_state.setdefault("added_people", [])
    st.session_state.setdefault("search_view", None)
    st.session_state.setdefault("fields_for", "")
    st.session_state.setdefault("furthest", "search")
    st.session_state.setdefault("lock_notice", "")
    if "data_mode" not in st.session_state:
        st.session_state.data_mode = "Practice data" if current_mode() == "offline" else "Live"


def _sidebar(killed: str) -> str:
    ids = profile_ids()
    profile_id = st.sidebar.selectbox(
        "Business",
        ids,
        format_func=profile_name,
        key="profile",
    )
    st.sidebar.radio(
        "Data mode",
        ["Practice data", "Live"],
        key="data_mode",
        on_change=_apply_mode,
        help="Practice data uses saved examples. Live calls the accounts.",
    )
    if killed:
        st.sidebar.error(killed)
    st.sidebar.markdown("More")
    st.sidebar.button("Logbook", key="nav_logbook", on_click=_go, args=("logbook",))
    st.sidebar.button("Funnel", key="nav_funnel", on_click=_go, args=("funnel",))
    st.sidebar.button("Settings", key="nav_settings", on_click=_go, args=("settings",))
    return profile_id


def _apply_mode() -> None:
    choice = st.session_state.get("data_mode")
    os.environ["LEADGEN_LLM_MODE"] = "offline" if choice == "Practice data" else "live"


def _tiles(root: Path, profile_id: str) -> None:
    view = st.session_state.get("search_view") or {}
    shown = len(view.get("rows") or []) if view.get("profile_id") == profile_id else 0
    parts = []
    for tile in summary_tiles(root, profile_id, shown):
        parts.append(
            f'<div class="tile tile-{tile["tone"]}">'
            f'<span class="tile-value">{tile["value"]}</span>'
            f'<span class="tile-label">{tile["label"]}</span></div>'
        )
    st.markdown(f'<div class="tiles">{"".join(parts)}</div>', unsafe_allow_html=True)


def _tracker() -> None:
    columns = st.columns(len(WIZARD))
    for column, name in zip(columns, WIZARD):
        state = _marker(name)
        with column:
            st.markdown(
                f'<span class="tracker-state" data-step="{name}" data-state="{state}">'
                f"{icon(state)}</span>",
                unsafe_allow_html=True,
            )
            st.button(
                WIZARD_LABELS[name],
                key=f"nav_{name}",
                on_click=_try_go,
                args=(name,),
            )


def _lock_note() -> None:
    step = st.session_state.get("lock_notice") or ""
    if step and _ready(step):
        st.session_state.lock_notice = ""
        return
    spec = LOCKS.get(step)
    if not spec:
        return
    reason, label, dest, key = spec
    st.markdown(reason)
    st.button(label, key=key, on_click=_go, args=(dest,))


def _try_go(step: str) -> None:
    if _ready(step):
        _go(step)
        return
    st.session_state.lock_notice = step


def _ready(step: str) -> bool:
    if step in {"search", "shortlist", "logbook", "funnel", "settings"}:
        return True
    profile_id = st.session_state.get("profile") or ""
    if step == "run":
        return bool(profile_id) and bool(prospect_board(profile_id)["eligible_ids"])
    if step == "review":
        return bool(st.session_state.get("last_run"))
    if step == "outbox":
        return bool(outbox_rows(data_root()))
    return True


def _marker(step: str) -> str:
    if st.session_state.step == step:
        return "current"
    if not _ready(step):
        return "locked"
    anchor = st.session_state.step
    if anchor not in WIZARD:
        anchor = st.session_state.get("furthest", "search")
    if anchor in WIZARD and WIZARD.index(step) < WIZARD.index(anchor):
        return "done"
    return "ready"


def _kind(step: str, chosen: bool) -> str:
    if st.session_state.step == step and chosen:
        return "primary"
    return "secondary"


def _go(step: str) -> None:
    st.session_state.lock_notice = ""
    st.session_state.step = step
    if step not in WIZARD:
        return
    current = st.session_state.get("furthest", "search")
    if current not in WIZARD or WIZARD.index(step) > WIZARD.index(current):
        st.session_state.furthest = step


def _hide_inactive() -> None:
    rules = []
    for name in STEPS:
        if name == st.session_state.step:
            continue
        rules.append(
            'div[data-testid="stVerticalBlock"]:has(> div span.panel-mark[data-panel="%s"])'
            ":not(:has(> div [data-testid='stVerticalBlock'] span.panel-mark[data-panel='%s']))"
            "{display:none !important;}" % (name, name)
        )
    if rules:
        st.markdown(f"<style>{''.join(rules)}</style>", unsafe_allow_html=True)


def _panel(name: str):
    box = st.container()
    with box:
        st.markdown(
            f'<span class="panel-mark" data-panel="{name}"></span>',
            unsafe_allow_html=True,
        )
    return box


def _search_tab(root: Path, profile_id: str, killed: str) -> None:
    st.markdown('<div class="step-card step-card-search"><p>1 · Find</p></div>', unsafe_allow_html=True)
    st.header("Find")
    st.markdown("Describe the businesses you want. Press an example, or type your own and press Search.")
    profile = load_profile(profile_id)
    example = profile.search.examples[0] if profile.search.examples else "Registered firms in Phoenix"
    st.info(f"Try this: press “{example}”. The list should name a business, how to reach them, and why they fit.")
    st.text_input(
        "Request",
        key="search_query",
        placeholder=example,
        help="Example: Registered firms in Phoenix",
    )
    for index, text in enumerate(profile.search.examples):
        st.button(
            text,
            key=f"example_{index}",
            disabled=bool(killed),
            on_click=_queue_search,
            args=(text,),
        )
    view = st.session_state.get("search_view") or {}
    searched = view.get("profile_id") == profile_id and bool(view.get("summary"))
    st.button(
        "Search",
        key="search",
        disabled=bool(killed),
        on_click=_queue_search,
        type=_kind("search", not searched),
    )
    if st.session_state.get("notice"):
        st.error(st.session_state.notice)
    view = st.session_state.get("search_view") or {}
    if view.get("profile_id") != profile_id:
        st.info("No matches yet. Press an example or change the request.")
        return
    _search_fields(profile, view)
    for message in view.get("messages") or []:
        st.warning(message)
    if view.get("field_error"):
        st.warning(view["field_error"])
    for line in view.get("unsupported") or []:
        st.info(line)
    if view.get("summary"):
        st.markdown(view["summary"])
    rows = view.get("rows") or []
    if rows:
        st.markdown(
            markdown_table(
                [
                    {
                        "Business": row["business"],
                        "Contact": row["label"],
                        "Freshness": row["stale"],
                        "Source": row["source"],
                        "Why it fits": row["why"],
                    }
                    for row in rows
                ],
                ["Business", "Contact", "Freshness", "Source", "Why it fits"],
            )
        )
        for row in rows:
            with st.expander(row["business"]):
                st.markdown(row["why"] or "No reason was recorded.")
                if row.get("url"):
                    st.markdown(f"[Open the public record]({row['url']})")
                else:
                    st.markdown("No source link on this record.")
    else:
        st.info("No matches yet. Press an example or change a field, then press Update results.")
    if view.get("held_back_note"):
        st.markdown(view["held_back_note"])
    for item in view.get("prospects") or []:
        if st.button("Add to pipeline", key=f"add_{item['prospect_id']}"):
            _add_person(root, profile_id, item)
    view = st.session_state.get("search_view") or {}
    if view.get("profile_id") == profile_id and view.get("summary"):
        st.button("Next", key="next_search", on_click=_go, args=("shortlist",), type=_kind("search", True))


def _queue_search(text: str | None = None) -> None:
    if text is not None:
        st.session_state.search_query = text
    st.session_state.pending_search = st.session_state.get("search_query") or text or ""


def _queue_update() -> None:
    st.session_state.pending_update = True


def _queue_run() -> None:
    st.session_state.pending_run = True


def _consume_run(root: Path, profile_id: str) -> None:
    if not st.session_state.pop("pending_run", False):
        return
    added = [
        item["prospect_id"]
        for item in st.session_state.get("added_people") or []
        if item["profile_id"] == profile_id
    ]
    board = prospect_board(profile_id)
    choices = list(board["eligible_ids"]) + [
        item for item in added if item not in board["eligible_ids"]
    ]
    prospect_id = st.session_state.get("prospect")
    if prospect_id not in choices and choices:
        prospect_id = choices[0]
        st.session_state.prospect = choices[0]
    if prospect_id:
        _start_run(root, profile_id, prospect_id)


def _consume_search(root: Path, profile) -> None:
    pending = st.session_state.pop("pending_search", "")
    if pending:
        _run_search(root, profile, pending)
        _seed_fields(st.session_state.get("search_view") or {})
        return
    if st.session_state.pop("pending_update", False):
        previous = st.session_state.get("search_view") or {}
        if previous.get("profile_id") == profile.profile_id:
            view = refresh_search(profile, previous, _edits(), root)
            st.session_state.search_view = view
            st.session_state.fields_for = _token(view)
        return
    view = st.session_state.get("search_view") or {}
    if view.get("profile_id") == profile.profile_id and st.session_state.get("fields_for") != _token(view):
        _seed_fields(view)


def _edits() -> dict:
    return {
        "kind": st.session_state.get(FIELD_KIND, ""),
        "location": st.session_state.get(FIELD_LOCATION, ""),
        "date_from": st.session_state.get(FIELD_FROM, ""),
        "date_to": st.session_state.get(FIELD_TO, ""),
        "business_type": st.session_state.get(FIELD_BUSINESS, ""),
        "contact": st.session_state.get(FIELD_CONTACT, ""),
        "max_results": st.session_state.get(FIELD_MAX, ""),
    }


def _token(view: dict) -> str:
    values = view.get("filter_values") or {}
    return "|".join(
        str(values.get(key) or "")
        for key in ("naics", "permit_type", "city", "state", "date_from", "date_to", "business_type", "area")
    )


def _seed_fields(view: dict) -> None:
    values = view.get("filter_values") or {}
    kind = values.get("naics") or values.get("permit_type") or ""
    location = values.get("city") or values.get("area") or ""
    st.session_state[FIELD_KIND] = kind
    st.session_state[FIELD_LOCATION] = location
    st.session_state[FIELD_FROM] = values.get("date_from") or ""
    st.session_state[FIELD_TO] = values.get("date_to") or ""
    st.session_state[FIELD_BUSINESS] = values.get("business_type") or ""
    st.session_state[FIELD_CONTACT] = "Any"
    st.session_state[FIELD_MAX] = "10"
    st.session_state.fields_for = _token(view)


def _search_fields(profile, view: dict) -> None:
    st.markdown("Change a field, then press Update results.")
    kind_help = "A NAICS code such as 541512, or a permit type such as Building."
    kind_example = (profile.search.naics[:1] or profile.search.permit_types[:1] or ["541512"])[0]
    st.text_input(
        "Industry or permit type",
        key=FIELD_KIND,
        placeholder=kind_example,
        help=kind_help,
    )
    st.text_input(
        "Location",
        key=FIELD_LOCATION,
        placeholder="Phoenix",
        help="A city or area such as Phoenix.",
    )
    st.text_input(
        "Date from",
        key=FIELD_FROM,
        placeholder="2026-05-24",
        help="Example: 2026-05-24. Leave blank when the source has no date.",
    )
    st.text_input(
        "Date to",
        key=FIELD_TO,
        placeholder="2026-11-20",
        help="Example: 2026-11-20. Leave blank when the source has no date.",
    )
    st.text_input(
        "Business size or type",
        key=FIELD_BUSINESS,
        placeholder="For Profit Organization",
        help="Example: For Profit Organization.",
    )
    st.text_input(
        "Contact needed",
        key=FIELD_CONTACT,
        placeholder="Named contact",
        help="Type Named contact to keep only records with a person's name. Any keeps the full list.",
    )
    st.text_input(
        "Max results",
        key=FIELD_MAX,
        placeholder="10",
        help="Example: 10.",
    )
    st.button("Update results", key="update_results", on_click=_queue_update)


def _run_search(root: Path, profile, request: str) -> None:
    st.session_state.notice = ""
    try:
        outcome = search(profile, request, root)
    except KillSwitchEngaged as exc:
        st.session_state.notice = str(exc)
        return
    except ProviderError as exc:
        st.session_state.notice = (
            f"{exc.role} {exc.provider}: {exc.line()}. switch to Offline or fix the account"
        )
        return
    except ConfigError as exc:
        st.session_state.notice = str(exc)
        return
    view = search_view(outcome)
    view["profile_id"] = profile.profile_id
    view["request"] = request
    st.session_state.search_view = view


def _add_person(root: Path, profile_id: str, item: dict) -> None:
    prospect = Prospect.model_validate(item["prospect"])
    people = [
        row
        for row in st.session_state.added_people
        if row["prospect_id"] != prospect.prospect_id
    ]
    people.append(
        {
            "profile_id": profile_id,
            "prospect_id": prospect.prospect_id,
            "prospect": prospect.model_dump(mode="json"),
        }
    )
    st.session_state.added_people = people
    remember_add(root, prospect)


def _shortlist_tab(profile_id: str) -> None:
    st.markdown('<div class="step-card step-card-shortlist"><p>2 · Shortlist</p></div>', unsafe_allow_html=True)
    st.header("Shortlist")
    st.markdown("These are the people the rules ranked. Continue to Draft when you want a note.")
    board = prospect_board(profile_id)
    if not board["ranked"] and not board["excluded"]:
        st.info("No one to show yet.")
    else:
        rows = [
            {
                "Person": row["prospect_id"],
                "Score": row["score"],
                "Fit": tier_label(row["tier"]),
                "Ready": "Yes" if row["draft_eligible"] else "No",
            }
            for row in board["ranked"]
        ]
        st.markdown(markdown_table(rows, ["Person", "Score", "Fit", "Ready"]))
        for row in board["ranked"]:
            with st.expander(f"Rules {row['prospect_id']}"):
                for hit in row["rule_hits"]:
                    mark = "yes" if hit["matched"] else "no"
                    st.markdown(f"{hit['field']}: {hit['points']} points, matched {mark}")
    st.subheader("Excluded")
    excluded = [
        {"Person": item["prospect_id"], "Reason": exclusion_label(item["reason"])}
        for item in board["excluded"]
    ]
    st.markdown(markdown_table(excluded, ["Person", "Reason"]))
    st.subheader("Findings")
    findings = [
        {"Person": item["prospect_id"], "Note": item["message"]}
        for item in board["findings"]
    ]
    st.markdown(markdown_table(findings, ["Person", "Note"]))
    if board["eligible_ids"]:
        st.button("Next", key="next_shortlist", on_click=_go, args=("run",), type=_kind("shortlist", True))


def _run_tab(root: Path, profile_id: str, killed: str) -> None:
    st.markdown('<div class="step-card step-card-run"><p>3 · Draft</p></div>', unsafe_allow_html=True)
    st.header("Draft")
    st.markdown("Pick a person and press Run. The steps below say what happened.")
    added = [
        item
        for item in st.session_state.get("added_people") or []
        if item["profile_id"] == profile_id
    ]
    if added:
        st.subheader("Added this session")
        st.markdown(
            markdown_table(
                [{"Person": item["prospect_id"]} for item in added],
                ["Person"],
            )
        )
    else:
        st.info("No one added yet. Search, then click Add to pipeline.")
    board = prospect_board(profile_id)
    eligible = list(board["eligible_ids"])
    extra = [item["prospect_id"] for item in added if item["prospect_id"] not in eligible]
    choices = eligible + extra
    if not choices:
        st.info("No one is ready for a draft.")
        st.button("Run", key="run", disabled=True, type=_kind("run", True))
        return
    if st.session_state.get("prospect") not in choices:
        st.session_state.prospect = choices[0]
    st.selectbox("Person", choices, key="prospect")
    drafted = bool(st.session_state.last_run)
    st.button(
        "Run",
        key="run",
        disabled=bool(killed),
        on_click=_queue_run,
        type=_kind("run", not drafted),
    )
    if st.session_state.notice:
        st.error(st.session_state.notice)
    if st.session_state.last_run:
        _show_run(root, Path(st.session_state.last_run))
        st.button("Next", key="next_run", on_click=_go, args=("review",), type=_kind("run", True))


def _show_run(root: Path, run_dir: Path) -> None:
    if not run_dir.is_dir():
        return
    status = run_status(run_dir)
    badge = status_badge(status.get("status", ""))
    kind = "badge-wait"
    if status.get("status") == "BLOCKED":
        kind = "badge-stop"
    elif status.get("status") == "APPROVED":
        kind = "badge-ok"
    st.markdown(f'<span class="{kind}">{badge}</span>', unsafe_allow_html=True)
    for line in run_steps(root, run_dir):
        if line[:1].isdigit() or line.startswith("Attempt") or line.startswith("Trying"):
            st.markdown(line)
        else:
            st.caption(line)
    st.button("Review", key="to_review", on_click=_go, args=("review",))


def _start_run(root: Path, profile_id: str, prospect_id: str) -> None:
    st.session_state.stages = []
    st.session_state.notice = ""
    st.session_state.decision = None
    st.session_state.last_status = ""
    st.session_state.last_run = ""
    if st.session_state.get("red_team"):
        os.environ["LEADGEN_DEMO_TEMPT"] = "1"
    else:
        os.environ.pop("LEADGEN_DEMO_TEMPT", None)
    profile = load_profile(profile_id)
    prospect = _lookup_prospect(profile, prospect_id)
    pipeline = load_pipeline_config()
    try:
        result = run_prospect(profile, prospect, pipeline, root)
    except KillSwitchEngaged as exc:
        st.session_state.notice = str(exc)
        return
    except ProviderError as exc:
        st.session_state.notice = (
            f"{exc.role} {exc.provider}: {exc.line()}. switch to Offline or fix the account"
        )
        return
    except ConfigError as exc:
        st.session_state.notice = str(exc)
        return
    finally:
        os.environ.pop("LEADGEN_DEMO_TEMPT", None)
    st.session_state.last_status = result.status
    if result.run_dir is not None:
        st.session_state.last_run = str(result.run_dir)


def _lookup_prospect(profile, prospect_id: str):
    for item in st.session_state.get("added_people") or []:
        if item["profile_id"] == profile.profile_id and item["prospect_id"] == prospect_id:
            return Prospect.model_validate(item["prospect"])
    return next(item for item in load_prospects(profile) if item.prospect_id == prospect_id)


def _review_tab(root: Path, profile_id: str, killed: str) -> None:
    st.markdown('<div class="step-card step-card-review"><p>4 · Review</p></div>', unsafe_allow_html=True)
    st.header("Review")
    st.markdown("Read the note. Type your name, acknowledge any findings, then approve, edit, or reject.")
    run_dir = _selected_run(root)
    if run_dir is None:
        st.info("Run a prospect first.")
        st.button("Approve", key="approve", disabled=True, type=_kind("review", True))
        return
    status = run_status(run_dir)
    st.markdown(status_badge(status.get("status", "")))
    if status.get("evaluator_below_bar"):
        st.markdown('<span class="badge-warn">The quality score is still under the bar.</span>', unsafe_allow_html=True)
    st.subheader("Email")
    st.code(rendered_text(run_dir))
    channels = contact_channels(run_dir)
    if channels:
        st.subheader("Contact channels")
        for line in channels:
            st.markdown(line)
    st.subheader("Findings")
    findings = status.get("findings") or []
    if findings:
        for finding in findings:
            st.markdown(f'<span class="badge-warn">{finding["message"]}</span>', unsafe_allow_html=True)
    else:
        st.markdown("No findings.")
    st.checkbox("Acknowledge findings", key="ack")
    name = st.text_input(
        "Approver",
        key="approver",
        placeholder="Ada",
        help="Example: Ada",
    )
    fields = draft_fields(run_dir)
    if st.session_state.get("edit_run") != run_dir.name:
        st.session_state.edit_hook = fields["hook"]
        st.session_state.edit_bridge = fields["bridge"]
        st.session_state.edit_run = run_dir.name
    hook = st.text_area(
        "Hook",
        key="edit_hook",
        placeholder="You mentioned the backlog.",
        help="Example: You mentioned the backlog.",
    )
    bridge = st.text_area(
        "Bridge",
        key="edit_bridge",
        placeholder="A person reviews the work for {{organization}}:",
        help="Example: A person reviews the work before it goes out.",
    )
    disabled = bool(killed)
    prospect_id = st.session_state.get("prospect") or status["prospect_id"]
    approve, edit, reject = st.columns(3)
    approve.button(
        "Approve",
        key="approve",
        disabled=disabled,
        type=_kind("review", True),
        on_click=_queue_decision,
        args=("APPROVED",),
    )
    edit.button("Edit", key="edit", disabled=disabled, on_click=_queue_decision, args=("EDITED",))
    reject.button("Reject", key="reject", disabled=disabled, on_click=_queue_decision, args=("REJECTED",))
    _show_decision()
    if st.session_state.decision and st.session_state.decision[0] == 0:
        st.button("Next", key="next_review", on_click=_go, args=("outbox",))


def _queue_decision(decision: str) -> None:
    st.session_state.pending_decision = decision


def _consume_decision(root: Path, profile_id: str) -> None:
    decision = st.session_state.pop("pending_decision", "")
    if not decision:
        return
    run_dir = _selected_run(root)
    if run_dir is None:
        return
    status = run_status(run_dir)
    prospect_id = st.session_state.get("prospect") or status.get("prospect_id") or ""
    _store_decision(
        root,
        profile_id,
        prospect_id,
        decision,
        st.session_state.get("approver", ""),
        st.session_state.get("edit_hook", ""),
        st.session_state.get("edit_bridge", ""),
    )


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
    st.markdown('<div class="step-card step-card-outbox"><p>5 · Send</p></div>', unsafe_allow_html=True)
    st.header("Send")
    st.markdown("Approved notes are saved here. Nothing is emailed.")
    rows = outbox_rows(root)
    if not rows:
        st.info("No emails yet. Approve a note on Review and it will show up here.")
        st.button("Go to Review", key="send_back", on_click=_go, args=("review",), type=_kind("outbox", True))
        return
    for row in rows:
        who = row["approver"] or "a person"
        st.markdown(f'<span class="badge-ok">Approved by {who}</span>', unsafe_allow_html=True)
        st.code(row["text"])
    st.button("Find another", key="find_another", on_click=_go, args=("search",), type=_kind("outbox", True))


def _logbook_tab(root: Path) -> None:
    st.header("Logbook")
    st.markdown("This is the record of the latest run.")
    run_dir = _selected_run(root)
    if run_dir is None:
        st.info("No run selected. Run someone first.")
        return
    rows = logbook(root, run_dir.name)
    if not rows:
        st.info("No events for this run.")
        return
    plain = [
        {
            "What happened": _event_label(row.get("event_type")),
            "Attempt": row.get("attempt_number") or "",
        }
        for row in rows
    ]
    st.markdown(markdown_table(plain, ["What happened", "Attempt"]))


def _event_label(event_type: str | None) -> str:
    labels = {
        "model_call": "Model call",
        "gate": "Claim check",
        "verification": "Draft check",
        "evaluation": "Quality score",
        "retry": "Trying again",
        "approval": "Approval",
        "outbox": "Saved note",
        "refusal": "Not sent",
        "error": "Problem",
        "search": "Search",
        "source_call": "Public record lookup",
        "add_to_pipeline": "Added to the pipeline",
    }
    return labels.get(event_type or "", "Recorded step")


def _funnel_tab(profile_id: str) -> None:
    st.header("Funnel")
    st.markdown("These are the past results for this business.")
    stats = funnel_view(profile_id)
    labels = {
        "sent": "Sent",
        "replied": "Replied",
        "meeting": "Meetings",
        "won": "Won",
        "won_value": "Won value",
        "reply_rate": "Reply rate",
        "meeting_rate": "Meeting rate",
        "win_rate": "Win rate",
        "avg_deal": "Average deal",
    }
    for key, value in stats.items():
        st.markdown(f"{labels.get(key, key)}: {value}")


def _settings_tab(root: Path) -> None:
    st.header("Settings")
    st.markdown("Practice data uses saved examples. Live calls the accounts. Check keys does not show a key.")
    labels = {
        "tailor": "Tailor the pitch",
        "drafter": "Write the email",
        "evaluator": "Quality score",
        "translator": "Read the request",
        "reason": "Why this fits",
    }
    providers = {"google": "Google", "anthropic": "Anthropic", "openai": "OpenAI"}
    for row in role_rows():
        provider = providers.get(row["provider"], row["provider"])
        st.markdown(f"{labels.get(row['role'], 'Step')}: {provider}, {row['model']}")
    st.checkbox(
        "Red-team toggle",
        key="red_team",
        help="On the next Run only, the first draft is tempted to offer a discount.",
    )
    if st.button("Check keys", key="check_keys"):
        from contextlib import redirect_stdout
        from io import StringIO

        buffer = StringIO()
        with redirect_stdout(buffer):
            check_keys_main()
        st.session_state.key_report = buffer.getvalue()
    if st.session_state.key_report:
        st.code(st.session_state.key_report)
    mode = "Practice data" if current_mode() == "offline" else "Live"
    st.caption(f"Data mode: {mode}")


main()
