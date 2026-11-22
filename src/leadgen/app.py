"""Find businesses, draft a note from approved facts, and sign it before it is saved."""

import json
import os
from pathlib import Path

import streamlit as st

from leadgen.approve import decide, latest_run
from leadgen.check_keys import main as check_keys_main
from leadgen.industry import BAND_IDS, ids_for_labels, labels_for, live_size_note, suggest, title_for
from leadgen.kill_switch import KillSwitchEngaged
from leadgen.llm import ConfigError, ProviderError, current_mode, scrub
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
from leadgen.shortlist import add_shortlist, load_shortlist
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
    _limit_view,
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
    st.set_page_config(page_title="Acme Plumbing", layout="wide")
    apply_theme()
    _init_state()
    root = data_root()
    killed = kill_message(root)
    profile_id = _sidebar(killed)
    _consume_adds(root, profile_id)
    _consume_search(root, load_profile(profile_id))
    _consume_run(root, profile_id)
    _consume_decision(root, profile_id)
    _consume_mail(root)
    st.markdown(
        '<div class="banner"><h1>Acme Plumbing</h1>'
        "<p>Find a business in the service area, draft a note from approved facts, and sign it before anything is saved.</p></div>",
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
        _outbox_tab(root, killed)
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
    st.session_state.setdefault("demo_safety", True)
    st.session_state.setdefault("mail_destination", "Practice")
    st.session_state.setdefault("mail_action", "Save as draft")
    st.session_state.setdefault("mail_result", None)
def _sidebar(killed: str) -> str:
    profile_id = profile_ids()[0]
    st.sidebar.markdown(profile_name(profile_id))
    if killed:
        st.sidebar.error(killed)
    st.sidebar.markdown("More")
    st.sidebar.button("Logbook", key="nav_logbook", on_click=_go, args=("logbook",))
    st.sidebar.button("Funnel", key="nav_funnel", on_click=_go, args=("funnel",))
    st.sidebar.button("Settings", key="nav_settings", on_click=_go, args=("settings",))
    return profile_id


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
    if step == "run":
        return bool(load_shortlist(data_root()))
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
    st.markdown("Pick a metro and, if you want, an industry and a size. Press Search. A written request is optional.")
    profile = load_profile(profile_id)
    example = profile.search.examples[0] if profile.search.examples else ""
    st.text_input(
        "Request",
        key="search_query",
        placeholder=example,
        help="Leave this blank to search from the fields below. Words here are read only when the box has text.",
    )
    _industry_picker(profile)
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
    for line in view.get("statuses") or []:
        st.markdown(line)
    for message in view.get("messages") or []:
        st.warning(message)
    if view.get("field_error"):
        st.warning(view["field_error"])
    for line in view.get("unsupported") or []:
        st.info(line)
    if view.get("summary"):
        st.markdown(view["summary"])
        if len(view.get("rows") or []) < int(view.get("shown") or 0):
            st.caption("The table shows the best matches first. Change Max results to see more.")
    markets = view.get("markets") or []
    if markets:
        for market in markets:
            _market_card(market)
    else:
        _market_card(view.get("market"))
    rows = view.get("rows") or []
    if rows:
        st.markdown(
            markdown_table(
                [
                    {
                        "Business": row["business"],
                        "Industry": row.get("industry") or "",
                        "Size": row.get("size") or "Size not in public record",
                        "Contact": row["label"],
                        "Freshness": row["stale"],
                        "Source": row["source"],
                        "Why it fits": row["why"],
                    }
                    for row in rows
                ],
                ["Business", "Industry", "Size", "Contact", "Freshness", "Source", "Why it fits"],
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
    if rows:
        st.button("Add all shown", key="add_all", on_click=_queue_add_all)
    for row in rows:
        st.button("Add", key=f"add_{row['prospect_id']}", on_click=_queue_add, args=(row["prospect_id"],))
    view = st.session_state.get("search_view") or {}
    if view.get("profile_id") == profile_id and view.get("summary"):
        st.button("Next", key="next_search", on_click=_go, args=("shortlist",), type=_kind("search", True))


def _industry_picker(profile) -> None:
    st.text_input(
        "What kind of business are you looking for?",
        key="industry_query",
        placeholder="Type a business, then pick a suggestion",
        help="The search uses the official code you pick. The words you type are not sent.",
    )
    query = str(st.session_state.get("industry_query") or "")
    matches = suggest(query) if query.strip() else []
    if matches and matches[0].confident:
        st.caption("Did you mean")
    elif query.strip():
        st.caption("No close match. Closest broader categories:")
    for index, match in enumerate(matches):
        st.button(
            match.title,
            key=f"suggest_{index}",
            help=match.code,
            on_click=_add_chip,
            args=(match.code, match.title),
        )
        st.caption(match.code)
    for chip in list(st.session_state.get("industry_chips") or []):
        st.button(
            chip["title"],
            key=f"chip_{chip['code']}",
            help="Remove this industry",
            on_click=_drop_chip,
            args=(chip["code"],),
        )
        st.caption(chip["code"])
    st.multiselect(
        "Employee size",
        options=labels_for(list(BAND_IDS)),
        key="size_bands",
        placeholder="Any size",
        help="Census size classes. Leave this empty for any size.",
        on_change=_touch_sizes,
    )
    st.checkbox(
        "Only show businesses with a known size",
        key="known_size_only",
        help="A record with no headcount stays in the list until this is on. No size is estimated.",
    )
    names = [metro.name for metro in profile.search.metros]
    if names and "metros" not in st.session_state:
        st.session_state.metros = list(names)
    if names:
        st.multiselect(
            "Metro areas",
            names,
            key="metros",
            help="SAM.gov is queried once for Arizona. These cities are kept in code.",
        )
    note = live_size_note(current_mode())
    if note:
        st.caption(note)


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


def _drop_chip(code: str) -> None:
    st.session_state.industry_chips = [
        item for item in st.session_state.get("industry_chips") or [] if item.get("code") != code
    ]


def _touch_sizes() -> None:
    st.session_state.size_bands_touched = True


def _chosen_sizes():
    selected = ids_for_labels(list(st.session_state.get("size_bands") or []))
    if selected:
        return selected
    if st.session_state.get("size_bands_touched"):
        return []
    return None


def _queue_search(text: str | None = None) -> None:
    if text is not None:
        st.session_state.search_query = text
        st.session_state.industry_chips = []
    request = text if text is not None else (st.session_state.get("search_query") or "")
    st.session_state.pending_search = request
    st.session_state.pending_search_ready = True


def _queue_update() -> None:
    st.session_state.pending_update = True


def _queue_run() -> None:
    st.session_state.pending_run = True


def _consume_run(root: Path, profile_id: str) -> None:
    if not st.session_state.pop("pending_run", False):
        return
    choices = [row["prospect_id"] for row in _shortlist_rows(root, profile_id)]
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


def _queue_add_all() -> None:
    view = st.session_state.get("search_view") or {}
    st.session_state.pending_adds = [row["prospect_id"] for row in view.get("rows") or []]


def _consume_adds(root: Path, profile_id: str) -> None:
    wanted = st.session_state.pop("pending_adds", None)
    if not wanted:
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
        rows.append(
            {
                "profile_id": profile_id,
                "prospect_id": row["prospect_id"],
                "prospect": item["prospect"],
                "business": row.get("business") or "",
                "city": row.get("city") or "",
                "industry": row.get("industry") or "",
                "contact_name": row.get("contact_name") or "",
                "contact_title": row.get("contact_title") or "",
                "channels": row.get("channels") or "",
                "score": row.get("score") or 0,
                "fit": row.get("fit") or "",
            }
        )
    if rows:
        add_shortlist(root, rows)
        for row in rows:
            remember_add(root, Prospect.model_validate(row["prospect"]))


def _shortlist_rows(root: Path, profile_id: str) -> list[dict]:
    return [row for row in load_shortlist(root) if row.get("profile_id") == profile_id]


def _consume_search(root: Path, profile) -> None:
    if st.session_state.pop("pending_search_ready", False):
        pending = st.session_state.pop("pending_search", "") or ""
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
        "sizes": _chosen_sizes(),
        "known_size_only": bool(st.session_state.get("known_size_only")),
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
    st.session_state[FIELD_MAX] = str(SHOWN_ROWS)
    codes = [item.strip() for item in str(values.get("naics") or "").split(",") if item.strip()]
    st.session_state.industry_chips = [
        {"code": code, "title": title_for(code) or code} for code in codes
    ]
    st.session_state.size_bands = labels_for(list(values.get("sizes") or []))
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
        chips = list(st.session_state.get("industry_chips") or [])
        outcome = search(
            profile,
            request,
            root,
            chosen_naics=[item["code"] for item in chips] or None,
            chosen_sizes=_chosen_sizes(),
            known_size_only=bool(st.session_state.get("known_size_only")),
            chosen_cities=_chosen_cities(profile),
        )
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
    _limit_view(view, {"max_results": str(SHOWN_ROWS)})
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
    st.markdown('<div class="step-card step-card-shortlist"><p>2 · Shortlist</p></div>', unsafe_allow_html=True)
    st.header("Shortlist")
    st.markdown("Businesses you added from Find. A refresh keeps this list.")
    rows = _shortlist_rows(data_root(), profile_id)
    if not rows:
        st.info("No businesses yet. On Find, press Add or Add all shown.")
    else:
        st.markdown(
            markdown_table(
                [
                    {
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
                ["Business", "City", "Industry", "Contact", "Channels", "Score", "Fit"],
            )
        )
        st.button("Next", key="next_shortlist", on_click=_go, args=("run",), type=_kind("shortlist", True))


def _run_tab(root: Path, profile_id: str, killed: str) -> None:
    st.markdown('<div class="step-card step-card-run"><p>3 · Draft</p></div>', unsafe_allow_html=True)
    st.header("Draft")
    st.markdown("Pick a business and press Run. The steps below say what happened.")
    rows = _shortlist_rows(root, profile_id)
    choices = [row["prospect_id"] for row in rows]
    names = {row["prospect_id"]: row.get("business") or row["prospect_id"] for row in rows}
    if not choices:
        st.info("No business is ready for a draft. Add one from Find.")
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
    for item in load_shortlist(data_root()):
        if item.get("profile_id") == profile.profile_id and item.get("prospect_id") == prospect_id:
            return Prospect.model_validate(item["prospect"])
    raise LookupError(prospect_id)


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


def _outbox_tab(root: Path, killed: str) -> None:
    st.markdown('<div class="step-card step-card-outbox"><p>5 · Send</p></div>', unsafe_allow_html=True)
    st.header("Send")
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
    st.markdown("Check keys does not show a key.")
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
