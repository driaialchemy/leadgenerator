"""Colorful theme for the class page. Presentation only."""

import streamlit as st

# Text on a surface. Each pair is checked for a contrast ratio of at least 4.5.
# White text failed on the bright teal, green, amber, and coral, so those fills
# are a darker shade of the same hue. Amber chips keep the bright fill and use dark text.
PAIRS = (
    ("page", "#0F172A", "#FFFFFF"),
    ("canvas", "#0F172A", "#F8FAFC"),
    ("banner_start", "#FFFFFF", "#2563EB"),
    ("banner_end", "#FFFFFF", "#0B857A"),
    ("step_current", "#FFFFFF", "#2563EB"),
    ("step_done", "#FFFFFF", "#12883E"),
    ("step_ready", "#0F172A", "#FFFFFF"),
    ("step_locked", "#475569", "#F8FAFC"),
    ("primary", "#FFFFFF", "#2563EB"),
    ("primary_disabled", "#FFFFFF", "#2563EB"),
    ("secondary", "#0F172A", "#E2E8F0"),
    ("secondary_disabled", "#475569", "#E2E8F0"),
    ("chip_wait", "#0F172A", "#F59E0B"),
    ("chip_ok", "#FFFFFF", "#12883E"),
    ("chip_stop", "#FFFFFF", "#C35305"),
    ("tile_found", "#2563EB", "#FFFFFF"),
    ("tile_shortlist", "#0B857A", "#FFFFFF"),
    ("tile_waiting", "#A46A06", "#FFFFFF"),
    ("tile_approved", "#12883E", "#FFFFFF"),
    ("tile_sent", "#7C3AED", "#FFFFFF"),
    ("card_find", "#2563EB", "#FFFFFF"),
    ("card_shortlist", "#0B857A", "#FFFFFF"),
    ("card_draft", "#7C3AED", "#FFFFFF"),
    ("card_review", "#A46A06", "#FFFFFF"),
    ("card_send", "#12883E", "#FFFFFF"),
    ("input", "#0F172A", "#FFFFFF"),
    ("muted", "#334155", "#FFFFFF"),
    ("table", "#0F172A", "#FFFFFF"),
    ("table_head", "#0F172A", "#E2E8F0"),
    ("expander", "#0F172A", "#F8FAFC"),
)

_ICONS = {
    "done": (
        '<svg class="tracker-icon" viewBox="0 0 24 24" aria-hidden="true">'
        '<circle cx="12" cy="12" r="10" fill="#12883E"/>'
        '<path d="M7 12.5 l3 3 l7-7" fill="none" stroke="#FFFFFF" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "current": (
        '<svg class="tracker-icon" viewBox="0 0 24 24" aria-hidden="true">'
        '<circle cx="12" cy="12" r="10" fill="#2563EB"/>'
        '<circle cx="12" cy="12" r="4" fill="#FFFFFF"/></svg>'
    ),
    "locked": (
        '<svg class="tracker-icon" viewBox="0 0 24 24" aria-hidden="true">'
        '<rect x="6" y="11" width="12" height="9" rx="2" fill="#475569"/>'
        '<path d="M8.5 11 V8.5 a3.5 3.5 0 0 1 7 0 V11" fill="none" stroke="#475569" '
        'stroke-width="2"/></svg>'
    ),
    "ready": (
        '<svg class="tracker-icon" viewBox="0 0 24 24" aria-hidden="true">'
        '<circle cx="12" cy="12" r="9" fill="none" stroke="#0F172A" stroke-width="2"/></svg>'
    ),
}

_CSS = """
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stSidebar"] {
  color: #0F172A;
  font-family: "Segoe UI", "Helvetica Neue", sans-serif;
}
h1, h2, h3 { color: #0F172A; letter-spacing: 0; }
[data-testid="stMain"] .block-container {
  background: #F8FAFC;
  padding-top: 1.2rem;
}
[data-testid="stSidebar"] {
  background: #F8FAFC;
  border-right: 1px solid #E2E8F0;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] input {
  color: #0F172A !important;
  -webkit-text-fill-color: #0F172A !important;
  background: #FFFFFF !important;
  border-radius: 10px;
}
[data-testid="stMarkdownContainer"] table {
  width: 100%;
  border-collapse: collapse;
  background: #FFFFFF;
  border-radius: 12px;
}
[data-testid="stMarkdownContainer"] th {
  background: #E2E8F0;
  color: #0F172A;
  text-align: left;
  padding: 0.55rem 0.7rem;
}
[data-testid="stMarkdownContainer"] td {
  background: #FFFFFF;
  color: #0F172A;
  padding: 0.55rem 0.7rem;
  border-top: 1px solid #E2E8F0;
}
.stButton button[kind="primary"],
.stButton button[data-testid="stBaseButton-primary"],
.stButton button[kind="primary"]:disabled,
.stButton button[data-testid="stBaseButton-primary"]:disabled {
  background: #2563EB !important;
  color: #FFFFFF !important;
  border: none !important;
  border-radius: 10px;
  opacity: 1 !important;
}
.stButton button[kind="primary"] *,
.stButton button[data-testid="stBaseButton-primary"] *,
.stButton button[kind="primary"]:disabled *,
.stButton button[data-testid="stBaseButton-primary"]:disabled * {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}
.stButton button[kind="secondary"],
.stButton button[data-testid="stBaseButton-secondary"] {
  background: #E2E8F0;
  color: #0F172A;
  border: 1px solid #CBD5E1;
  border-radius: 10px;
}
.stButton button[kind="secondary"] *,
.stButton button[data-testid="stBaseButton-secondary"] * {
  color: #0F172A;
  -webkit-text-fill-color: #0F172A;
}
.stButton button[kind="secondary"]:disabled,
.stButton button[data-testid="stBaseButton-secondary"]:disabled {
  background: #E2E8F0 !important;
  opacity: 1 !important;
}
.stButton button[kind="secondary"]:disabled *,
.stButton button[data-testid="stBaseButton-secondary"]:disabled * {
  color: #475569 !important;
  -webkit-text-fill-color: #475569 !important;
}
div[data-testid="stExpander"] {
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
}
.banner {
  background: linear-gradient(90deg, #2563EB 0%, #0B857A 100%);
  border-radius: 16px;
  padding: 1.3rem 1.5rem;
  margin-bottom: 0.8rem;
}
.banner h1, .banner p {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
  margin: 0;
}
.banner h1 { font-size: 2rem; font-weight: 800; }
.banner p { margin-top: 0.35rem; font-size: 1.05rem; }
.tiles { display: flex; gap: 0.7rem; margin: 0.2rem 0 0.9rem; }
.tile {
  flex: 1;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 14px;
  padding: 0.7rem 0.8rem;
}
.tile-value { display: block; font-size: 1.6rem; font-weight: 800; line-height: 1.1; }
.tile-label { display: block; color: #334155; font-size: 0.85rem; margin-top: 0.2rem; }
.tile-found .tile-value { color: #2563EB; }
.tile-shortlist .tile-value { color: #0B857A; }
.tile-waiting .tile-value { color: #A46A06; }
.tile-approved .tile-value { color: #12883E; }
.tile-sent .tile-value { color: #7C3AED; }
.tracker-icon { width: 22px; height: 22px; display: block; margin-bottom: 0.25rem; }
div[data-testid="stColumn"]:has(span.tracker-state[data-state="current"]) button {
  background: #2563EB !important;
  border-color: #2563EB !important;
  opacity: 1 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="current"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="current"]) button * {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
  font-weight: 700 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="done"]) button {
  background: #12883E !important;
  border-color: #12883E !important;
  opacity: 1 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="done"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="done"]) button * {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
  font-weight: 700 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="locked"]) button {
  background: #F8FAFC !important;
  border-color: #E2E8F0 !important;
  opacity: 1 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="locked"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="locked"]) button * {
  color: #475569 !important;
  -webkit-text-fill-color: #475569 !important;
  font-weight: 500 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="ready"]) button {
  background: #FFFFFF !important;
  border-color: #CBD5E1 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="ready"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="ready"]) button * {
  color: #0F172A !important;
  -webkit-text-fill-color: #0F172A !important;
  font-weight: 600 !important;
}
.step-card {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-top: 6px solid #2563EB;
  border-radius: 14px;
  padding: 0.65rem 1rem;
  margin-bottom: 0.7rem;
}
.step-card p { margin: 0; font-weight: 800; font-size: 1.15rem; }
.step-card-search { border-top-color: #2563EB; }
.step-card-search p { color: #2563EB !important; -webkit-text-fill-color: #2563EB !important; }
.step-card-shortlist { border-top-color: #0B857A; }
.step-card-shortlist p { color: #0B857A !important; -webkit-text-fill-color: #0B857A !important; }
.step-card-run { border-top-color: #7C3AED; }
.step-card-run p { color: #7C3AED !important; -webkit-text-fill-color: #7C3AED !important; }
.step-card-review { border-top-color: #F59E0B; }
.step-card-review p { color: #A46A06 !important; -webkit-text-fill-color: #A46A06 !important; }
.step-card-outbox { border-top-color: #12883E; }
.step-card-outbox p { color: #12883E !important; -webkit-text-fill-color: #12883E !important; }
.badge-wait, .badge-warn {
  display: inline-block;
  background: #F59E0B;
  color: #0F172A !important;
  -webkit-text-fill-color: #0F172A !important;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.badge-ok {
  display: inline-block;
  background: #12883E;
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.badge-stop {
  display: inline-block;
  background: #C35305;
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.model-note { color: #334155; font-size: 0.9rem; }
"""


def icon(name: str) -> str:
    """Inline SVG. Practice data does not fetch a font."""
    return _ICONS[name]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio for two #RRGGBB colors."""
    lighter = max(_luminance(foreground), _luminance(background))
    darker = min(_luminance(foreground), _luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def apply_theme() -> str:
    """Inject the colorful theme and return the CSS."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
    return _CSS


def _luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[index : index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = [linear(channel) for channel in channels]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue
