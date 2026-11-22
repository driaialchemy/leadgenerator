"""Acme Plumbing look. Presentation only. Every color on the page lives here and in .streamlit/config.toml."""

import base64
import io
from pathlib import Path

import streamlit as st

from leadgen.paths import repo_root

# Palette.
CYAN = "#06B6D4"  # accent line under the bar. Too light for white text.
BAR = "#0E7490"  # the top bar. A darker cyan so white text reads.
BLUE = "#1D4ED8"  # primary buttons and headings
BLUE_DARK = "#1E40AF"
SKY = "#E0F2FE"  # panels
SKY_DARK = "#BAE6FD"
WHITE = "#FFFFFF"
SLATE = "#0F172A"  # text
MUTED = "#334155"
LOCKED = "#475569"
LINE = "#CBD5E1"
GREEN = "#16A34A"  # approved
GREEN_TEXT = "#166534"
AMBER = "#F59E0B"  # findings
AMBER_TEXT = "#92400E"
RED = "#B91C1C"  # blocked only
HERO_FROM = BLUE
HERO_TO = BAR

# Dark overlay on the hero photo. The lightest it ever gets is OVERLAY_MIN, so white
# text is checked against the worst case: a white photo under that alpha.
OVERLAY_MAX = 0.82
OVERLAY_MIN = 0.62
HERO_SOURCE = Path("assets") / "source" / "hero_shower.jpg"
HERO_WEB = Path("assets") / "hero_shower_web.jpg"
HERO_MAX_BYTES = 150 * 1024
HERO_WIDTH = 1600


def _blend(top: str, alpha: float, under: str) -> str:
    top_rgb = [int(top.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    under_rgb = [int(under.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    mixed = [round(alpha * a + (1 - alpha) * b) for a, b in zip(top_rgb, under_rgb)]
    return "#" + "".join(f"{value:02X}" for value in mixed)


HERO_WORST = _blend(SLATE, OVERLAY_MIN, WHITE)

# Text on a surface. Each pair is checked for a contrast ratio of at least 4.5.
PAIRS = (
    ("page", SLATE, WHITE),
    ("canvas", SLATE, SKY),
    ("topbar", WHITE, BAR),
    ("hero_title", WHITE, HERO_WORST),
    ("hero_subtitle", WHITE, HERO_WORST),
    ("banner_start", WHITE, HERO_FROM),
    ("banner_end", WHITE, HERO_TO),
    ("heading", BLUE, WHITE),
    ("heading_on_panel", BLUE, SKY),
    ("step_current", WHITE, BLUE),
    ("step_done", SLATE, GREEN),
    ("step_ready", SLATE, WHITE),
    ("step_locked", LOCKED, WHITE),
    ("primary", WHITE, BLUE),
    ("primary_hover", WHITE, BLUE_DARK),
    ("primary_disabled", WHITE, BLUE),
    ("secondary", SLATE, SKY),
    ("secondary_hover", SLATE, SKY_DARK),
    ("secondary_disabled", LOCKED, SKY),
    ("chip_wait", SLATE, AMBER),
    ("chip_ok", SLATE, GREEN),
    ("chip_stop", WHITE, RED),
    ("tile_found", BLUE, WHITE),
    ("tile_shortlist", BAR, WHITE),
    ("tile_waiting", AMBER_TEXT, WHITE),
    ("tile_approved", GREEN_TEXT, WHITE),
    ("tile_sent", SLATE, WHITE),
    ("card_find", BLUE, WHITE),
    ("card_shortlist", BAR, WHITE),
    ("card_draft", BLUE_DARK, WHITE),
    ("card_review", AMBER_TEXT, WHITE),
    ("card_send", GREEN_TEXT, WHITE),
    ("input", SLATE, WHITE),
    ("muted", MUTED, WHITE),
    ("table", SLATE, WHITE),
    ("table_head", SLATE, SKY),
    ("expander", SLATE, SKY),
)

# Icons and large marks need 3:1. These pairs are the colors the SVGs use.
ICON_PAIRS = (
    ("icon_done", WHITE, GREEN_TEXT),
    ("icon_current", WHITE, BLUE),
    ("icon_locked", LOCKED, WHITE),
    ("icon_ready", SLATE, WHITE),
    ("wordmark_drop", WHITE, BAR),
)

DROP = "M12 2 C12 2 5 10.2 5 15 a7 7 0 0 0 14 0 C19 10.2 12 2 12 2 Z"

_ICONS = {
    "done": (
        '<svg class="tracker-icon" viewBox="0 0 24 24" aria-hidden="true">'
        f'<circle cx="12" cy="12" r="10" fill="{GREEN_TEXT}"/>'
        f'<path d="M7 12.5 l3 3 l7-7" fill="none" stroke="{WHITE}" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "current": (
        '<svg class="tracker-icon" viewBox="0 0 24 24" aria-hidden="true">'
        f'<circle cx="12" cy="12" r="10" fill="{BLUE}"/>'
        f'<circle cx="12" cy="12" r="4" fill="{WHITE}"/></svg>'
    ),
    "locked": (
        '<svg class="tracker-icon" viewBox="0 0 24 24" aria-hidden="true">'
        f'<rect x="6" y="11" width="12" height="9" rx="2" fill="{LOCKED}"/>'
        f'<path d="M8.5 11 V8.5 a3.5 3.5 0 0 1 7 0 V11" fill="none" stroke="{LOCKED}" '
        'stroke-width="2"/></svg>'
    ),
    "ready": (
        '<svg class="tracker-icon" viewBox="0 0 24 24" aria-hidden="true">'
        f'<circle cx="12" cy="12" r="9" fill="none" stroke="{SLATE}" stroke-width="2"/></svg>'
    ),
}

_CSS = """
.stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
  color: @SLATE@;
  font-family: "Segoe UI", "Helvetica Neue", sans-serif;
}
[data-testid="stHeader"] { background: @BAR@; }
[data-testid="stHeader"] *, [data-testid="stToolbar"] * {
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
}
h1, h2, h3 { color: @BLUE@; letter-spacing: 0; }
[data-testid="stMain"] .block-container {
  background: @SKY@;
  padding: 3.75rem 2rem 2rem;
  max-width: 100%;
}
[data-testid="stSidebar"] {
  background: @SKY@;
  border-right: 1px solid @SKY_DARK@;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] input {
  color: @SLATE@ !important;
  -webkit-text-fill-color: @SLATE@ !important;
  background: @WHITE@ !important;
  border-radius: 10px;
}
[data-testid="stMarkdownContainer"] table {
  width: 100%;
  border-collapse: collapse;
  background: @WHITE@;
  border-radius: 12px;
}
[data-testid="stMarkdownContainer"] th {
  background: @SKY@;
  color: @SLATE@;
  text-align: left;
  padding: 0.55rem 0.7rem;
}
[data-testid="stMarkdownContainer"] td {
  background: @WHITE@;
  color: @SLATE@;
  padding: 0.55rem 0.7rem;
  border-top: 1px solid @SKY@;
}
.stButton button[kind="primary"],
.stButton button[data-testid="stBaseButton-primary"],
.stButton button[kind="primary"]:disabled,
.stButton button[data-testid="stBaseButton-primary"]:disabled {
  background: @BLUE@ !important;
  color: @WHITE@ !important;
  border: none !important;
  border-radius: 10px;
  opacity: 1 !important;
}
.stButton button[kind="primary"]:hover:not(:disabled),
.stButton button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {
  background: @BLUE_DARK@ !important;
}
.stButton button[kind="primary"] *,
.stButton button[data-testid="stBaseButton-primary"] * {
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
}
.stButton button[kind="secondary"],
.stButton button[data-testid="stBaseButton-secondary"] {
  background: @SKY@;
  color: @SLATE@;
  border: 1px solid @SKY_DARK@;
  border-radius: 10px;
}
.stButton button[kind="secondary"]:hover:not(:disabled),
.stButton button[data-testid="stBaseButton-secondary"]:hover:not(:disabled) {
  background: @SKY_DARK@;
}
.stButton button[kind="secondary"] *,
.stButton button[data-testid="stBaseButton-secondary"] * {
  color: @SLATE@;
  -webkit-text-fill-color: @SLATE@;
}
.stButton button[kind="secondary"]:disabled,
.stButton button[data-testid="stBaseButton-secondary"]:disabled {
  background: @SKY@ !important;
  opacity: 1 !important;
}
.stButton button[kind="secondary"]:disabled *,
.stButton button[data-testid="stBaseButton-secondary"]:disabled * {
  color: @LOCKED@ !important;
  -webkit-text-fill-color: @LOCKED@ !important;
}
div[data-testid="stExpander"] {
  background: @WHITE@;
  border: 1px solid @SKY_DARK@;
  border-radius: 12px;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  background: @BAR@;
  border-bottom: 4px solid @CYAN@;
  margin: -1rem -2rem 1rem;
  padding: 0.6rem 2rem;
}
.topbar span {
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
}
.topbar .topbar-name { font-weight: 800; font-size: 1.15rem; }
.topbar .topbar-line { font-size: 0.95rem; }
.hero {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  min-height: 220px;
  margin-bottom: 1rem;
  background-size: cover;
  background-position: center;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
}
.hero-fallback {
  background-image: linear-gradient(110deg, @HERO_FROM@ 0%, @HERO_TO@ 100%);
}
.hero-fallback .hero-overlay { background: none; }
.hero-overlay h1 a, .hero-overlay h1 svg { display: none; }
.hero-drops {
  position: absolute;
  right: 2rem;
  top: 1rem;
  width: 150px;
  height: 190px;
  opacity: 0.3;
}
.hero-overlay {
  position: relative;
  min-height: 220px;
  padding: 1.4rem 1.8rem;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  background: linear-gradient(90deg, rgba(15, 23, 42, @OVERLAY_MAX@) 0%, rgba(15, 23, 42, @OVERLAY_MIN@) 100%);
}
.hero-overlay h1, .hero-overlay p, .hero-overlay .wordmark-text {
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
  margin: 0;
}
.hero-overlay h1 { font-size: 2.6rem; font-weight: 800; line-height: 1.1; }
.hero-overlay p { margin-top: 0.4rem; font-size: 1.3rem; }
.wordmark { display: flex; align-items: center; gap: 0.5rem; margin-bottom: auto; }
.wordmark svg { width: 28px; height: 28px; }
.wordmark-text { font-weight: 800; letter-spacing: 0.12em; font-size: 0.95rem; }
.tiles { display: flex; gap: 0.7rem; margin: 0.2rem 0 0.9rem; }
.tile {
  flex: 1;
  background: @WHITE@;
  border: 1px solid @SKY_DARK@;
  border-radius: 14px;
  padding: 0.7rem 0.8rem;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}
.tile-value { display: block; font-size: 1.6rem; font-weight: 800; line-height: 1.1; }
.tile-label { display: block; color: @MUTED@; font-size: 0.85rem; margin-top: 0.2rem; }
.tile-found .tile-value { color: @BLUE@; }
.tile-shortlist .tile-value { color: @BAR@; }
.tile-waiting .tile-value { color: @AMBER_TEXT@; }
.tile-approved .tile-value { color: @GREEN_TEXT@; }
.tile-sent .tile-value { color: @SLATE@; }
.tracker-icon { width: 22px; height: 22px; display: block; margin-bottom: 0.25rem; }
div[data-testid="stColumn"]:has(span.tracker-state[data-state="current"]) button {
  background: @BLUE@ !important;
  border-color: @BLUE@ !important;
  opacity: 1 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="current"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="current"]) button * {
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
  font-weight: 700 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="done"]) button {
  background: @GREEN@ !important;
  border-color: @GREEN@ !important;
  opacity: 1 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="done"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="done"]) button * {
  color: @SLATE@ !important;
  -webkit-text-fill-color: @SLATE@ !important;
  font-weight: 700 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="locked"]) button {
  background: @WHITE@ !important;
  border-color: @SKY_DARK@ !important;
  opacity: 1 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="locked"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="locked"]) button * {
  color: @LOCKED@ !important;
  -webkit-text-fill-color: @LOCKED@ !important;
  font-weight: 500 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="ready"]) button {
  background: @WHITE@ !important;
  border-color: @LINE@ !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="ready"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="ready"]) button * {
  color: @SLATE@ !important;
  -webkit-text-fill-color: @SLATE@ !important;
  font-weight: 600 !important;
}
.step-card {
  background: @WHITE@;
  border: 1px solid @SKY_DARK@;
  border-top: 6px solid @BLUE@;
  border-radius: 14px;
  padding: 0.65rem 1rem;
  margin-bottom: 0.7rem;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}
.step-card p { margin: 0; font-weight: 800; font-size: 1.15rem; }
.step-card-search { border-top-color: @BLUE@; }
.step-card-search p { color: @BLUE@ !important; -webkit-text-fill-color: @BLUE@ !important; }
.step-card-shortlist { border-top-color: @CYAN@; }
.step-card-shortlist p { color: @BAR@ !important; -webkit-text-fill-color: @BAR@ !important; }
.step-card-run { border-top-color: @BLUE_DARK@; }
.step-card-run p { color: @BLUE_DARK@ !important; -webkit-text-fill-color: @BLUE_DARK@ !important; }
.step-card-review { border-top-color: @AMBER@; }
.step-card-review p { color: @AMBER_TEXT@ !important; -webkit-text-fill-color: @AMBER_TEXT@ !important; }
.step-card-outbox { border-top-color: @GREEN@; }
.step-card-outbox p { color: @GREEN_TEXT@ !important; -webkit-text-fill-color: @GREEN_TEXT@ !important; }
.badge-wait, .badge-warn {
  display: inline-block;
  background: @AMBER@;
  color: @SLATE@ !important;
  -webkit-text-fill-color: @SLATE@ !important;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.badge-ok {
  display: inline-block;
  background: @GREEN@;
  color: @SLATE@ !important;
  -webkit-text-fill-color: @SLATE@ !important;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.badge-stop {
  display: inline-block;
  background: @RED@;
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.model-note { color: @MUTED@; font-size: 0.9rem; }
"""

_VALUES = {
    "SLATE": SLATE, "BAR": BAR, "WHITE": WHITE, "BLUE": BLUE, "BLUE_DARK": BLUE_DARK,
    "SKY": SKY, "SKY_DARK": SKY_DARK, "MUTED": MUTED, "LOCKED": LOCKED, "LINE": LINE,
    "GREEN": GREEN, "GREEN_TEXT": GREEN_TEXT, "AMBER": AMBER, "AMBER_TEXT": AMBER_TEXT,
    "RED": RED, "CYAN": CYAN, "HERO_FROM": HERO_FROM, "HERO_TO": HERO_TO,
    "OVERLAY_MAX": str(OVERLAY_MAX), "OVERLAY_MIN": str(OVERLAY_MIN),
}


def _css() -> str:
    text = _CSS
    for name, value in _VALUES.items():
        text = text.replace(f"@{name}@", value)
    return text


def icon(name: str) -> str:
    """Inline SVG. The page does not fetch a font or an image."""
    return _ICONS[name]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio for two #RRGGBB colors."""
    lighter = max(_luminance(foreground), _luminance(background))
    darker = min(_luminance(foreground), _luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def build_hero_image(root: Path | None = None) -> Path | None:
    """Shrink the owner's photo to a web copy under 150 KB. None when there is no photo."""
    base = Path(root) if root is not None else repo_root()
    source = base / HERO_SOURCE
    target = base / HERO_WEB
    if not source.is_file():
        return None
    if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
        if target.stat().st_size <= HERO_MAX_BYTES:
            return target
    try:
        from PIL import Image

        with Image.open(source) as image:
            image = image.convert("RGB")
            width = min(HERO_WIDTH, image.width)
            while width >= 400:
                height = max(1, round(image.height * width / image.width))
                scaled = image.resize((width, height))
                for quality in (80, 70, 60, 50, 40):
                    buffer = io.BytesIO()
                    scaled.save(buffer, "JPEG", quality=quality, optimize=True)
                    if buffer.tell() <= HERO_MAX_BYTES:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(buffer.getvalue())
                        return target
                width = int(width * 0.75)
    except Exception:
        return None
    return None


@st.cache_resource(show_spinner=False)
def _hero_uri(stamp: float) -> str:
    path = build_hero_image()
    if path is None:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def hero_uri() -> str:
    source = repo_root() / HERO_SOURCE
    stamp = source.stat().st_mtime if source.is_file() else 0.0
    return _hero_uri(stamp) if stamp else ""


def wordmark() -> str:
    return (
        '<div class="wordmark">'
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        f'<path d="{DROP}" fill="{WHITE}"/>'
        f'<path d="M9 15 a3 3 0 0 0 3 3" fill="none" stroke="{BAR}" stroke-width="1.6" stroke-linecap="round"/>'
        "</svg>"
        '<span class="wordmark-text">ACME PLUMBING</span></div>'
    )


def header_html(brand, display_name: str, uri: str | None = None) -> str:
    """Top bar and hero. Words come from the profile. A missing photo gives a gradient."""
    uri = hero_uri() if uri is None else uri
    title = brand.hero_title or display_name
    bar = (
        '<div class="topbar">'
        f'<span class="topbar-name">{display_name}</span>'
        f'<span class="topbar-line">{brand.service_line}</span></div>'
    )
    if uri:
        css = f'<style>.hero{{background-image:url("{uri}");}}</style>'
        kind = "hero"
        drops = ""
    else:
        css = ""
        kind = "hero hero-fallback"
        drops = (
            '<svg class="hero-drops" viewBox="0 0 48 60" aria-hidden="true">'
            f'<path d="M24 2 C24 2 4 24 4 38 a20 20 0 0 0 40 0 C44 24 24 2 24 2 Z" fill="{WHITE}"/></svg>'
        )
    hero = (
        f'<div class="{kind}">{drops}<div class="hero-overlay">{wordmark()}'
        f"<h1>{title}</h1><p>{brand.hero_subtitle}</p></div></div>"
    )
    return css + bar + hero


def apply_theme() -> str:
    """Inject the Acme theme and return the CSS."""
    css = _css()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    return css


def _luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[index : index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = [linear(channel) for channel in channels]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue
