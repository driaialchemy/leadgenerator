"""Find businesses, draft a note from approved facts, and sign it before it is saved."""

from datetime import datetime
import json
import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from leadgen.approve import decide, latest_run
from leadgen.check_keys import main as check_keys_main
from leadgen.cloud import SHARED_NOTE, is_cloud, load_streamlit_secrets, mailto_url, prepare_cloud
from leadgen.paths import repo_root
from leadgen.guide import HOW_IT_WORKS, TOPICS
from leadgen.reset import clear_everything
from leadgen.profiles import load_sender, save_sender
from leadgen.directory import available as directory_available, search_directory
from leadgen.industry import BANDS, BAND_IDS, ids_for_labels, labels_for, sic_options_for, suggest
from leadgen.kill_switch import KillSwitchEngaged
from leadgen.llm import ConfigError, ProviderError, scrub
from leadgen.mail import (
    NO_EMAIL,
    connect_account,
    connection_status,
    deliver,
    disconnect_account,
    refusal_reason,
)
from leadgen.pipeline import _log, run_prospect
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.schemas import Prospect
from leadgen.shortlist import add_shortlist, load_shortlist, replace_shortlist
from leadgen.search import remember_add, search
from leadgen.ui_data import (
    contact_channels,
    data_root,
    draft_fields,
    exclusion_label,
    kill_message,
    logbook,
    markdown_table,
    outbox_rows,
    profile_ids,
    profile_name,
    _limit_view,
    rendered_text,
    role_rows,
    run_status,
    run_steps,
    search_view,
    status_badge,
    summary_tiles,
    tier_label,
)
from leadgen.ui_theme import apply_theme, copy_button_html, header_html, icon

STEPS = (
    "search",
    "shortlist",
    "run",
    "review",
    "outbox",
    "logbook",
    "settings",
)
WIZARD = ("search", "shortlist", "run", "review", "outbox")
WIZARD_LABELS = {
    "search": "1 Find",
    "shortlist": "2 Previous Searches",
    "run": "3 Draft",
    "review": "4 Review",
    "outbox": "5 Send",
}
LOCKS = {
    "run": (
        "Run a search first",
        "Go to Find",
        "search",
        "unlock_run",
    ),
    "review": ("Nothing to review yet", "Go to Draft", "run", "unlock_review"),
    "outbox": ("Nothing sent yet", "Go to Review", "review", "unlock_outbox"),
}
SHOWN_ROWS = 25


def main() -> None:
    try:
        _page()
    except Exception as exc:
        _screen_error(exc)


def _screen_error(exc: Exception) -> None:
    try:
        _log(data_root(), "screen", "error", "screen", "error", scrub(str(exc))[:500])
    except Exception:
        pass
    st.error("Something went wrong. Details saved to the logbook.")


def _page() -> None:
    st.set_page_config(page_title=load_profile(profile_ids()[0]).display_name, layout="wide")
    apply_theme()
    load_streamlit_secrets()
    _init_state()
    root = data_root()
    prepare_cloud(root)
    killed = kill_message(root)
    profile_id = _sidebar(killed)
    _consume_adds(root, profile_id)
    _consume_search(root, load_profile(profile_id))
    _consume_run(root, profile_id)
    _consume_decision(root, profile_id)
    _consume_mail(root)
    _header(profile_id)
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
        _outbox_tab(root, killed)
    with _panel("logbook"):
        _logbook_tab(root)
    with _panel("settings"):
        _settings_tab(root)


def _header(profile_id: str) -> None:
    profile = load_profile(profile_id)
    st.markdown(header_html(profile.brand, profile.display_name), unsafe_allow_html=True)


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
    st.session_state.setdefault("demo_safety", True)
    st.session_state.setdefault("mail_destination", "Practice")
    st.session_state.setdefault("mail_action", "Save as draft")
    st.session_state.setdefault("mail_result", None)
    st.session_state.setdefault("show_no_named_contact", True)
def _sidebar(killed: str) -> str:
    profile_id = profile_ids()[0]
    st.sidebar.markdown(profile_name(profile_id))
    if killed:
        st.sidebar.error(killed)
    st.sidebar.button("Search", key="side_search", on_click=_go, args=("search",))
    st.sidebar.button("Previous Searches", key="side_previous", on_click=_go, args=("shortlist",))
    st.sidebar.markdown("More")
    st.sidebar.button("Logbook", key="nav_logbook", on_click=_go, args=("logbook",))
    st.sidebar.button("Settings", key="nav_settings", on_click=_go, args=("settings",))
    _clear_controls()
    _how_it_works()
    _guide()
    return profile_id


def _how_it_works() -> None:
    choice = st.sidebar.selectbox(
        "How it works",
        sorted(HOW_IT_WORKS, key=str.casefold),
        index=None,
        placeholder="Choose a topic",
        key="how_it_works",
    )
    if choice:
        st.sidebar.markdown(HOW_IT_WORKS[choice])


def _guide() -> None:
    answers = {title: answer for title, _keywords, answer in TOPICS}
    choice = st.sidebar.selectbox(
        "Usage guide",
        sorted(answers, key=str.casefold),
        index=None,
        placeholder="Choose a topic",
        key="usage_guide",
    )
    if choice:
        st.sidebar.markdown(answers[choice])


def _clear_controls() -> None:
    if st.session_state.get("confirm_clear"):
        st.sidebar.warning("Clear all searches, drafts, approvals and Practice sends? This can't be undone.")
        yes, no = st.sidebar.columns(2)
        yes.button("Yes, clear", key="clear_yes", on_click=_clear_all)
        no.button("Cancel", key="clear_no", on_click=_cancel_clear)
    else:
        st.sidebar.button("Clear everything", key="clear_all", on_click=_ask_clear)
    if st.session_state.pop("cleared_note", ""):
        st.sidebar.success("Everything was cleared.")


def _ask_clear() -> None:
    st.session_state.confirm_clear = True


def _cancel_clear() -> None:
    st.session_state.confirm_clear = False


def _clear_all() -> None:
    root = data_root()
    removed = clear_everything(root)
    _log(
        root,
        "system",
        "clear_everything",
        "human",
        "ok",
        f"Cleared {removed['runs']} drafts, {removed['files']} saved lists, {removed['outbox']} Practice sends.",
    )
    for key, value in (
        ("search_view", None),
        ("last_run", ""),
        ("last_status", ""),
        ("decision", None),
        ("prospect", None),
        ("stages", []),
        ("mail_result", None),
        ("furthest", "search"),
        ("step", "search"),
        ("confirm_clear", False),
        ("cleared_note", "done"),
    ):
        st.session_state[key] = value


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
    if step in {"search", "shortlist", "logbook", "settings"}:
        return True
    if step == "run":
        return bool(_load_current(data_root()) or load_shortlist(data_root()))
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
    if is_cloud():
        st.caption(SHARED_NOTE)
    profile = load_profile(profile_id)
    st.text_input(
        "Your occupation or service field",
        key="sender_field",
        placeholder="e.g. Social media marketing",
    )
    _industry_picker(profile)
    st.checkbox(
        "Include businesses without a named contact",
        key="show_no_named_contact",
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
        return
    if view.get("search_notice"):
        st.info(view["search_notice"])
    if view.get("summary"):
        st.markdown(view["summary"])
    rows = view.get("rows") or []
    if not st.session_state.get("show_no_named_contact", True):
        rows = [row for row in rows if row.get("label") == "Named contact"]
    if rows:
        has_size = any("employees" in str(row.get("size") or "") for row in rows)
        columns = ["Business", "Industry", "NAICS", "Contact", "City", "Score"]
        if has_size:
            columns.insert(4, "Size")
        columns += ["Source"]
        table = []
        for row in rows:
            item = {
                "Business": row["business"],
                "Industry": row.get("industry") or "",
                "NAICS": row.get("naics") or "",
                "Contact": row.get("contact_text") or row["label"],
                "City": row.get("city") or "",
                "Size": row.get("size") or "",
                "Score": row.get("score") or 0,
                "Source": row["source"],
            }
            table.append(item)
        st.markdown(markdown_table(table, columns))
        for row in rows:
            with st.expander(row["business"]):
                st.markdown(row["why"] or "No reason was recorded.")
                if row.get("url"):
                    st.markdown(f"[Website]({row['url']})")
    else:
        if not view.get("search_notice"):
            st.info("No new businesses match. Clear Previous Searches to see earlier matches again.")
    if view.get("remaining"):
        st.button(
            f"Show {min(SHOWN_ROWS, int(view['remaining']))} more",
            key="next_results",
            disabled=bool(killed),
            on_click=_queue_more,
        )
    if view.get("summary"):
        st.button("Next", key="next_search", on_click=_go, args=("shortlist",), type=_kind("search", True))


def _industry_picker(profile) -> None:
    st.text_input(
        "Target company industry",
        key="industry_query",
        placeholder="e.g. Restaurants",
        on_change=_industry_query_changed,
    )
    query = str(st.session_state.get("industry_query") or "")
    matches = suggest(query) if query.strip() and not st.session_state.get("industry_suggestions_hidden") else []
    if query.strip() and not matches and not st.session_state.get("industry_suggestions_hidden"):
        st.caption("No match. Try a broader word.")
    for index, match in enumerate(matches):
        st.button(
            f"{match.title} · {match.code}",
            key=f"suggest_{index}",
            on_click=_add_chip,
            args=(match.code, match.title),
        )
    chips = list(st.session_state.get("industry_chips") or [])
    for chip in chips:
        st.button(
            f"✕ {chip['title']} · {chip['code']}",
            key=f"chip_{chip['code']}",
            on_click=_drop_chip,
            args=(chip["code"],),
        )
    selected_codes = [str(item.get("code", "")) for item in st.session_state.get("industry_chips") or []]
    sic_options = sic_options_for(selected_codes)
    if sic_options:
        st.selectbox(
            "Related SEC SIC code",
            options=[""] + [code for code, _title in sic_options],
            format_func=lambda code: "Select a related SIC code" if not code else f"{code} — {dict(sic_options)[code]}",
            key="selected_sic_code",
        )
    st.multiselect(
        "Employee size",
        options=labels_for(list(BAND_IDS)),
        key="size_bands",
        placeholder="Any size",
        on_change=_touch_sizes,
    )
    st.checkbox(
        "Only show businesses with a known size",
        key="known_size_only",
        on_change=_invalidate_search,
    )
    names = [metro.name for metro in profile.search.metros]
    if names and "metros" not in st.session_state:
        st.session_state.metros = list(names)
    if names:
        st.multiselect(
            "Metro areas",
            names,
            key="metros",
            on_change=_invalidate_search,
        )


def _market_card(market: dict | None) -> None:
    if not market:
        return
    st.subheader("Market size")
    st.markdown(market["note"])
    for industry in market["industries"]:
        counts = ", ".join(
            f"{band['label']}: {band['count']} establishments" for band in industry["bands"]
        )
        st.markdown(f"{industry['title']} ({industry['code']}). {counts}")
    st.markdown(f"{market['year']} County Business Patterns. [Source]({market['url']})")


def _add_chip(code: str, title: str) -> None:
    chips = [item for item in st.session_state.get("industry_chips") or [] if item.get("code") != code]
    chips.append({"code": code, "title": title})
    st.session_state.industry_chips = chips
    st.session_state.industry_suggestions_hidden = True
    st.session_state.selected_sic_code = ""
    st.session_state.search_view = None


def _drop_chip(code: str) -> None:
    st.session_state.industry_chips = [
        item for item in st.session_state.get("industry_chips") or [] if item.get("code") != code
    ]
    st.session_state.selected_sic_code = ""
    st.session_state.search_view = None


def _industry_query_changed() -> None:
    st.session_state.industry_chips = []
    st.session_state.industry_suggestions_hidden = False
    st.session_state.search_view = None


def _invalidate_search() -> None:
    st.session_state.search_view = None


def _touch_sizes() -> None:
    st.session_state.size_bands_touched = True
    st.session_state.search_view = None


def _chosen_sizes():
    selected = ids_for_labels(list(st.session_state.get("size_bands") or []))
    if selected:
        return selected
    if st.session_state.get("size_bands_touched"):
        return []
    return None


def _queue_search(text: str | None = None) -> None:
    st.session_state.pending_search = ""
    st.session_state.pending_search_ready = True
    st.session_state.pending_search_more = False


def _queue_more() -> None:
    _queue_search()
    st.session_state.pending_search_more = True


def _queue_run() -> None:
    st.session_state.pending_run = True


def _consume_run(root: Path, profile_id: str) -> None:
    if not st.session_state.pop("pending_run", False):
        return
    choices = [row["prospect_id"] for row in _draft_rows(root, profile_id)]
    prospect_id = st.session_state.get("prospect")
    if prospect_id not in choices and choices:
        prospect_id = choices[0]
        st.session_state.prospect = choices[0]
    if prospect_id:
        _start_run(root, profile_id, prospect_id)


def _queue_add(prospect_id: str) -> None:
    pending = list(st.session_state.get("pending_adds") or [])
    if prospect_id not in pending:
        pending.append(prospect_id)
    st.session_state.pending_adds = pending
    st.session_state.pending_add_mode = "append"


def _queue_add_all() -> None:
    view = st.session_state.get("search_view") or {}
    st.session_state.pending_adds = [row["prospect_id"] for row in view.get("rows") or []]
    st.session_state.pending_add_mode = "replace"


def _consume_adds(root: Path, profile_id: str) -> None:
    wanted = st.session_state.pop("pending_adds", None)
    mode = st.session_state.pop("pending_add_mode", "append")
    if wanted is None or (not wanted and mode != "replace"):
        return
    view = st.session_state.get("search_view") or {}
    prospects = {item["prospect_id"]: item for item in view.get("prospects") or []}
    rows = []
    for row in view.get("rows") or []:
        if row.get("prospect_id") not in wanted:
            continue
        item = prospects.get(row["prospect_id"]) or {}
        if not item.get("prospect"):
            continue
        prospect_data = dict(item["prospect"])
        attributes = dict(prospect_data.get("attributes") or {})
        sender_field = str(view.get("sender_field") or "").strip()
        if sender_field:
            attributes["sender_field"] = sender_field[:120]
        target_market = str(row.get("industry") or "").strip()
        if target_market:
            attributes["target_market"] = target_market[:120]
        prospect_data["attributes"] = attributes
        rows.append(
            {
                "profile_id": profile_id,
                "prospect_id": row["prospect_id"],
                "prospect": prospect_data,
                "business": row.get("business") or "",
                "city": row.get("city") or "",
                "industry": row.get("industry") or "",
                "contact_name": row.get("contact_name") or "",
                "contact_title": row.get("contact_title") or "",
                "channels": row.get("channels") or "",
                "score": row.get("score") or 0,
                "fit": row.get("fit") or "",
                "searched_at": view.get("searched_at") or "",
                "search_label": view.get("search_label") or "",
            }
        )
    if mode == "current":
        _save_current(root, _load_current(root) + rows)
    elif mode == "replace":
        replace_shortlist(root, rows)
    elif rows:
        add_shortlist(root, rows)
    for row in rows:
        remember_add(root, Prospect.model_validate(row["prospect"]))


def _current_path(root: Path) -> Path:
    return Path(root) / "runs" / "current_search.json"


def _load_current(root: Path) -> list[dict]:
    path = _current_path(root)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in data if isinstance(row, dict) and row.get("prospect_id")] if isinstance(data, list) else []


def _save_current(root: Path, rows: list[dict]) -> None:
    unique, seen = [], set()
    for row in rows:
        if row.get("prospect_id") and row["prospect_id"] not in seen:
            unique.append(row)
            seen.add(row["prospect_id"])
    path = _current_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(unique, indent=2), encoding="utf-8")


def _current_rows(root: Path, profile_id: str) -> list[dict]:
    return [row for row in _load_current(root) if row.get("profile_id") == profile_id]


def _shortlist_rows(root: Path, profile_id: str) -> list[dict]:
    return [row for row in load_shortlist(root) if row.get("profile_id") == profile_id]


def _consume_search(root: Path, profile) -> None:
    if st.session_state.pop("pending_search_ready", False):
        _run_search(root, profile, "")


def _run_search(root: Path, profile, request: str) -> None:
    st.session_state.notice = ""
    chips = list(st.session_state.get("industry_chips") or [])
    typed = str(st.session_state.get("industry_query") or "").strip()
    if not chips and typed:
        matches = suggest(typed)
        if not matches:
            st.session_state.notice = "No industry matches that word. Try a broader word."
            return
        chips = [{"code": matches[0].code, "title": matches[0].title}]
        st.session_state.industry_chips = chips
        st.session_state.industry_suggestions_hidden = True
    if kill_message(root):
        st.session_state.notice = kill_message(root)
        return
    if not directory_available(repo_root()):
        st.session_state.notice = "The company directory is missing from sample_data/az_companies."
        return
    chosen = set(_chosen_sizes() or [])
    sizes = [(band.low, band.high) for band in BANDS if band.id in chosen]
    previous_view = st.session_state.get("search_view") or {}
    if not (st.session_state.get("pending_search_more") and previous_view.get("searched_at")):
        moving = _load_current(root)
        if moving:
            add_shortlist(root, moving)
        _save_current(root, [])
    exclude = {row["prospect_id"] for row in _shortlist_rows(root, profile.profile_id)}
    exclude |= {row["prospect_id"] for row in _current_rows(root, profile.profile_id)}
    result = search_directory(
        profile,
        [item["code"] for item in chips],
        sizes,
        _chosen_cities(profile),
        exclude,
        root=repo_root(),
    )
    previous = st.session_state.get("search_view") or {}
    more = bool(st.session_state.pop("pending_search_more", False)) and previous.get("searched_at")
    industries = ", ".join(item["title"] for item in chips) or "All industries"
    view = {
        "searched_at": previous["searched_at"] if more else datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        "search_label": previous.get("search_label") if more else industries,
        "profile_id": profile.profile_id,
        "request": request,
        "sender_field": str(st.session_state.get("sender_field") or "").strip(),
        "summary": result["summary"],
        "rows": result["rows"],
        "prospects": result["prospects"],
        "remaining": result["remaining"],
        "search_notice": result["search_notice"],
    }
    st.session_state.search_view = view
    _log(
        root,
        "search",
        "search",
        "search",
        "ok",
        scrub(
            "directory naics {naics} sizes {sizes} new {new} shown {shown}".format(
                naics=",".join(item["code"] for item in chips),
                sizes=",".join(sorted(chosen)) or "any",
                new=result["total_new"],
                shown=len(result["rows"]),
            )
        )[:240],
    )
    if result["rows"]:
        st.session_state.pending_adds = [row["prospect_id"] for row in result["rows"]]
        st.session_state.pending_add_mode = "current"
        _consume_adds(root, profile.profile_id)


def _set_result_page(view: dict, offset: int) -> None:
    all_rows = list(view.get("_all_rows", view.get("rows") or []))
    all_prospects = list(view.get("_all_prospects", view.get("prospects") or []))
    if not st.session_state.get("show_no_named_contact", True):
        all_rows = [row for row in all_rows if row.get("label") == "Named contact"]
    total = len(all_rows)
    offset = max(0, offset)
    if total and offset >= total:
        offset = ((total - 1) // SHOWN_ROWS) * SHOWN_ROWS
    page = all_rows[offset : offset + SHOWN_ROWS]
    visible_ids = {row.get("prospect_id") for row in page}
    view["rows"] = page
    view["prospects"] = [item for item in all_prospects if item.get("prospect_id") in visible_ids]
    view["page_offset"] = offset
    view["display_total"] = total
    view["has_more"] = offset + SHOWN_ROWS < total
    _limit_view(view, {})


def _move_results_page(amount: int) -> None:
    view = st.session_state.get("search_view") or {}
    _set_result_page(view, int(view.get("page_offset") or 0) + amount)
    st.session_state.search_view = view


def _chosen_cities(profile) -> list[str] | None:
    if not profile.search.metros:
        return None
    selected = set(st.session_state.get("metros") or [])
    cities = []
    for metro in profile.search.metros:
        if metro.name in selected:
            for city in metro.cities:
                if city not in cities:
                    cities.append(city)
    return cities


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
    st.markdown('<div class="step-card step-card-shortlist"><p>2 · Previous Searches</p></div>', unsafe_allow_html=True)
    st.header("Previous Searches")
    rows = _shortlist_rows(data_root(), profile_id)
    if not rows:
        st.info("No previous results.")
        return
    st.markdown(
        markdown_table(
            [
                {
                    "Searched": _when(row.get("searched_at") or ""),
                    "Business": row.get("business") or "",
                    "City": row.get("city") or "",
                    "Industry": row.get("industry") or "",
                    "Contact": " ".join(
                        part for part in (row.get("contact_name"), row.get("contact_title")) if part
                    ),
                    "Channels": row.get("channels") or "",
                    "Score": row.get("score") or 0,
                    "Fit": row.get("fit") or "",
                }
                for row in rows
            ],
            ["Searched", "Business", "City", "Industry", "Contact", "Channels", "Score", "Fit"],
        )
    )
    left, right = st.columns(2)
    with left:
        st.button("Next", key="next_shortlist", on_click=_go, args=("run",), type=_kind("shortlist", True))
    with right:
        st.button("Clear previous results", key="clear_previous", on_click=_clear_previous)


def _clear_previous() -> None:
    replace_shortlist(data_root(), [])
    st.session_state.search_view = None
    st.session_state.prospect = None


def _run_tab(root: Path, profile_id: str, killed: str) -> None:
    st.markdown('<div class="step-card step-card-run"><p>3 · Draft</p></div>', unsafe_allow_html=True)
    st.header("Draft")
    rows = _draft_rows(root, profile_id, show_picker=True)
    choices = [row["prospect_id"] for row in rows]
    names = {row["prospect_id"]: row.get("business") or row["prospect_id"] for row in rows}
    if not choices:
        st.info("No businesses here yet. Run a search on Find.")
        st.button("Run", key="run", disabled=True, type=_kind("run", True))
        return
    if st.session_state.get("prospect") not in choices:
        st.session_state.prospect = choices[0]
    st.selectbox("Business", choices, format_func=lambda item: names.get(item, item), key="prospect")
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


def _search_batches(root: Path, profile_id: str) -> list[tuple[str, str, int]]:
    """Each previous search: (time, industries, count), newest first."""
    batches: dict[str, list] = {}
    for row in _shortlist_rows(root, profile_id):
        stamp = row.get("searched_at") or ""
        entry = batches.setdefault(stamp, [row.get("search_label") or row.get("industry") or "", 0])
        entry[1] += 1
    return sorted(((stamp, label, count) for stamp, (label, count) in batches.items()), reverse=True)


def _draft_rows(root: Path, profile_id: str, show_picker: bool = False) -> list[dict]:
    """The current Find results by default. Previous searches can be picked by date."""
    older = _search_batches(root, profile_id)
    options = ["Current search"] + (["Previous searches"] if older else [])
    if st.session_state.get("draft_source") not in options:
        st.session_state.draft_source = "Current search"
    stamps = [batch[0] for batch in older]
    if stamps and st.session_state.get("draft_search") not in stamps:
        st.session_state.draft_search = stamps[0]
    if show_picker:
        st.radio("Pull from", options, key="draft_source", horizontal=True)
        if st.session_state.draft_source == "Previous searches":
            labels = {stamp: f"{_when(stamp)} · {label} · {count} businesses" for stamp, label, count in older}
            st.selectbox("Search date", stamps, format_func=lambda item: labels.get(item, item), key="draft_search")
    if st.session_state.get("draft_source") == "Previous searches":
        chosen = st.session_state.get("draft_search") or ""
        return [row for row in _shortlist_rows(root, profile_id) if (row.get("searched_at") or "") == chosen]
    return _current_rows(root, profile_id)


def _when(stamp: str) -> str:
    try:
        return datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S.%f").strftime("%b %d, %Y %I:%M %p")
    except ValueError:
        return stamp or "Earlier search"


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
        line = exc.line()
        if line == "The model reply could not be read.":
            st.session_state.notice = line
        else:
            st.session_state.notice = (
                f"{exc.role} {exc.provider}: {line}. switch to Offline or fix the account"
            )
        return
    except ConfigError as exc:
        st.session_state.notice = str(exc)
        return
    except Exception as exc:
        try:
            _log(root, "screen", "error", "screen", "error", scrub(str(exc))[:500])
        except Exception:
            pass
        st.session_state.notice = "Something went wrong. Details saved to the logbook."
        return
    finally:
        os.environ.pop("LEADGEN_DEMO_TEMPT", None)
    st.session_state.last_status = result.status
    if result.run_dir is not None:
        st.session_state.last_run = str(result.run_dir)


def _lookup_prospect(profile, prospect_id: str):
    for item in _load_current(data_root()) + load_shortlist(data_root()):
        if item.get("profile_id") == profile.profile_id and item.get("prospect_id") == prospect_id:
            return Prospect.model_validate(item["prospect"])
    raise LookupError(prospect_id)


def _review_tab(root: Path, profile_id: str, killed: str) -> None:
    st.markdown('<div class="step-card step-card-review"><p>4 · Review</p></div>', unsafe_allow_html=True)
    st.header("Review")
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
    if findings:
        st.checkbox("I've read the findings", key="ack")
    if not st.session_state.get("approver"):
        st.session_state.approver = load_sender().get("name", "")
    st.text_input("Your name (signs this decision)", key="approver", placeholder="Your name")
    fields = draft_fields(run_dir)
    if st.session_state.get("edit_run") != run_dir.name:
        st.session_state.edit_hook = fields["hook"]
        st.session_state.edit_bridge = fields["bridge"]
        st.session_state.edit_run = run_dir.name
    with st.expander("Edit the wording"):
        st.text_area("Opening", key="edit_hook")
        st.text_area("Middle", key="edit_bridge")
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
    edit.button("Approve with my edits", key="edit", disabled=disabled, on_click=_queue_decision, args=("EDITED",))
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
        str(st.session_state.get("approver") or "").strip() or load_sender().get("name", ""),
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
        found = Path(last)
    elif not prospect_id:
        return None
    else:
        try:
            found = latest_run(root, prospect_id)
        except FileNotFoundError:
            return None
    # A run that stopped before it wrote its status has nothing to review.
    return found if (found / "status.json").is_file() else None


def _outbox_tab(root: Path, killed: str) -> None:
    st.markdown('<div class="step-card step-card-outbox"><p>5 · Send</p></div>', unsafe_allow_html=True)
    st.header("Send")
    if is_cloud():
        st.markdown("Copy the approved note, or open it in your own email app and send it from there.")
    else:
        st.markdown(
            "Practice saves a file. Gmail and Outlook can save a draft or send the approved note."
        )
    rows = outbox_rows(root)
    if not rows:
        st.info("No emails yet. Approve a note on Review and it will show up here.")
        st.button("Go to Review", key="send_back", on_click=_go, args=("review",), type=_kind("outbox", True))
        return
    for row in rows:
        who = row["approver"] or "a person"
        st.markdown(f'<span class="badge-ok">Approved by {who}</span>', unsafe_allow_html=True)
        st.code(row["text"])
    run_dir = _send_run(root)
    if is_cloud():
        _cloud_send(run_dir)
        st.button("Find another", key="find_another", on_click=_go, args=("search",), type=_kind("outbox", True))
        return
    st.radio("Where", ["Practice", "Gmail", "Outlook"], key="mail_destination")
    st.radio("What to do", ["Save as draft", "Send now"], key="mail_action")
    _mail_actions(root, run_dir, killed)
    result = st.session_state.get("mail_result") or {}
    if result.get("message"):
        if result.get("ok"):
            st.success(result["message"])
        else:
            st.error(result["message"])
    if result.get("reconnect"):
        st.button("Reconnect", key="reconnect_mail", on_click=_reconnect)
    st.button("Find another", key="find_another", on_click=_go, args=("search",), type=_kind("outbox", True))


def _cloud_send(run_dir: Path | None) -> None:
    """On Cloud nothing is sent from the server. The person copies the note or opens their own email app."""
    if run_dir is None:
        return
    from leadgen.mail import _split

    rendered = rendered_text(run_dir)
    subject, body = _split(rendered)
    email = ""
    prospect = run_dir / "prospect.json"
    if prospect.is_file():
        email = str(json.loads(prospect.read_text(encoding="utf-8")).get("email") or "").strip()
    if not email:
        st.info(NO_EMAIL)
    left, right = st.columns(2)
    with left:
        components.html(copy_button_html(f"Subject: {subject}\n\n{body}".strip()), height=48)
    with right:
        st.link_button("Open in my email app", mailto_url(email, subject, body), key="open_mailto")


def _mail_actions(root: Path, run_dir: Path | None, killed: str) -> None:
    if run_dir is None:
        return
    destination = st.session_state.get("mail_destination", "Practice")
    action = st.session_state.get("mail_action", "Save as draft")
    email = ""
    prospect = run_dir / "prospect.json"
    if prospect.is_file():
        email = str(json.loads(prospect.read_text(encoding="utf-8")).get("email") or "").strip()
    if not email:
        st.info(NO_EMAIL)
        for line in contact_channels(run_dir):
            st.markdown(line)
        return
    if action == "Send now" and destination == "Practice":
        st.info("Practice saves a file. It does not email.")
        return
    if action == "Save as draft":
        st.button(
            "Save as draft",
            key="save_draft",
            disabled=bool(killed),
            on_click=_queue_mail,
            args=("draft", False),
        )
        return
    account = connection_status(destination).get("address", "")
    reason = refusal_reason(
        root,
        run_dir,
        destination,
        "send",
        demo_safety=bool(st.session_state.get("demo_safety", True)),
        confirmed=True,
        account=account,
    )
    subject = ""
    rendered = (run_dir / "rendered.txt").read_text(encoding="utf-8") if (run_dir / "rendered.txt").is_file() else ""
    if rendered.startswith("Subject:"):
        subject = rendered.splitlines()[0].split(":", 1)[1].strip()
    who = account or connection_status(destination)["label"]
    st.markdown(f"To: {email}")
    st.markdown(f"Subject: {subject}")
    st.markdown(f"From: {who}")
    if reason:
        st.info(reason)
    st.button(
        "Confirm send",
        key="confirm_send",
        disabled=bool(killed) or bool(reason),
        on_click=_queue_mail,
        args=("send", True),
    )


def _send_run(root: Path) -> Path | None:
    run_dir = _selected_run(root)
    if run_dir is not None and (root / "outbox" / f"{run_dir.name}.txt").is_file():
        return run_dir
    rows = outbox_rows(root)
    if not rows:
        return None
    return root / "runs" / Path(rows[-1]["file"]).stem


def _queue_mail(action: str, confirmed: bool) -> None:
    st.session_state.pending_mail = (action, confirmed)


def _consume_mail(root: Path) -> None:
    pending = st.session_state.pop("pending_mail", None)
    if not pending:
        return
    action, confirmed = pending
    run_dir = _send_run(root)
    if run_dir is None:
        st.session_state.mail_result = {
            "ok": False,
            "message": "Approve a note first.",
            "reconnect": False,
        }
        return
    result = deliver(
        root,
        run_dir,
        st.session_state.get("mail_destination", "Practice"),
        action,
        confirmed,
        demo_safety=bool(st.session_state.get("demo_safety", True)),
    )
    st.session_state.mail_result = {
        "ok": result.ok,
        "message": result.message,
        "reconnect": result.reconnect,
    }


def _connect_mailbox(destination: str) -> None:
    connect_account(destination)


def _disconnect_mailbox(destination: str) -> None:
    disconnect_account(destination)


def _reconnect() -> None:
    destination = st.session_state.get("mail_destination", "Gmail")
    status = connect_account(destination)
    st.session_state.mail_result = {
        "ok": status["state"] == "connected",
        "message": status["label"],
        "reconnect": status["state"] != "connected",
    }


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
            "What happened": _event_sentence(row),
            "Attempt": row.get("attempt_number") or "",
        }
        for row in rows
    ]
    st.markdown(markdown_table(plain, ["What happened", "Attempt"]))


def _event_sentence(row: dict) -> str:
    kind = row.get("event_type") or ""
    detail = str(row.get("detail") or "").strip()
    model = row.get("model") or ""
    seconds = ""
    duration = row.get("duration_ms")
    if isinstance(duration, int):
        seconds = f" ({duration / 1000:.1f} s)"
    if kind == "model_call":
        names = {
            "tailor": "Wrote the pitch",
            "drafter": "Wrote the email draft",
            "evaluator": "Checked the draft",
            "translator": "Read the request",
            "reason": "Wrote the reason",
        }
        who = f" with {model}" if model else ""
        return f"{names.get(row.get('actor') or '', 'Finished a step')}{who}{seconds}"
    if kind == "verifier":
        if row.get("status") == "ok":
            return "Checked the draft: passed"
        return "Checked the draft: needs changes"
    if kind == "evaluator":
        return detail or "Checked the draft"
    if kind == "error":
        return "A step failed. Details saved to the logbook."
    if detail:
        return detail
    return "Saved a step"


def _save_sender() -> None:
    save_sender(
        {
            field: st.session_state.get(f"sender_{field}", "")
            for field in ("name", "company", "phone", "postal_address")
        }
    )
    st.session_state.sender_saved = True


def _settings_tab(root: Path) -> None:
    st.header("Settings")
    st.subheader("Your details")
    saved = load_sender()
    for field, label in (
        ("name", "Your name"),
        ("company", "Your company"),
        ("phone", "Your phone"),
        ("postal_address", "Your mailing address"),
    ):
        st.session_state.setdefault(f"sender_{field}", saved.get(field, ""))
        st.text_input(label, key=f"sender_{field}")
    st.button("Save my details", key="save_sender", on_click=_save_sender)
    if st.session_state.pop("sender_saved", False):
        st.success("Saved. New drafts will be signed with these details.")
    st.subheader("Connections")
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
    if is_cloud():
        st.caption("Gmail and Outlook are off on the shared copy. Approved notes are copied or opened in your own email app.")
        return
    st.checkbox(
        "Allowlist only",
        key="demo_safety",
        help="When this is on, Send now only reaches an allowlisted address or your own account.",
    )
    if not st.session_state.demo_safety:
        st.warning("Allowlist only is off. Send now can reach addresses that are not on the allowlist.")
    for destination, title in (("gmail", "Gmail"), ("outlook", "Outlook")):
        status = connection_status(destination)
        st.markdown(f"{title}: {status['label']}")
        st.button("Connect", key=f"connect_{destination}", on_click=_connect_mailbox, args=(destination,))
        st.button(
            "Disconnect",
            key=f"disconnect_{destination}",
            on_click=_disconnect_mailbox,
            args=(destination,),
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


main()
