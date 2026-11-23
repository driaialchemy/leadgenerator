"""AI Lead Finder presentation theme. Every color lives here and in .streamlit/config.toml."""

import base64
import io
from pathlib import Path

import streamlit as st

from leadgen.paths import repo_root

# Palette: midnight navy with neon blue, violet, and cyan, like the brand imagery.
BG = "#070B1F"  # page
SKY = "#0F1733"  # panels and cards
SKY_DARK = "#18234D"  # raised panels, hover
BAR = "#050816"  # the top bar
CYAN = "#22D3EE"  # accent line, highlights
BLUE = "#3B5BDB"  # primary buttons
BLUE_DARK = "#2F4AC0"
BLUE_TEXT = "#7AA2FF"  # headings on dark
VIOLET = "#6D3FE0"
VIOLET_TEXT = "#A78BFA"
WHITE = "#FFFFFF"
SLATE = "#E8ECF8"  # body text on dark
INK = BG  # dark text on bright chips
MUTED = "#A9B4D6"
LOCKED = "#8792B8"
LINE = "#2A3A73"
GREEN = "#22C55E"  # approved
GREEN_TEXT = "#4ADE80"
AMBER = "#F5B942"  # findings
AMBER_TEXT = "#FBBF24"
RED = "#C53030"  # blocked only
def copy_button_html(text: str) -> str:
    """The Cloud-only Copy email button, drawn in the page palette."""
    from leadgen.cloud import clipboard_html

    return clipboard_html(text, BLUE, SKY, SLATE, MUTED)


HERO_FROM = "#0B1440"
HERO_TO = "#2A1060"

# Dark overlay on the hero banner. The lightest it ever gets is OVERLAY_MIN, so white
# text is checked against the worst case: a white image under that alpha.
OVERLAY_MAX = 0.85
OVERLAY_MIN = 0.60
HERO_SOURCE = Path("assets") / "source" / "hero_banner.png"
HERO_WEB = Path("assets") / "hero_banner_web.jpg"
HERO_MAX_BYTES = 150 * 1024
HERO_WIDTH = 1600
SHOWCASE = (
    ("show_find.jpg", "1 · Find", "Search 50,000 Arizona businesses by industry, size, and city."),
    ("show_draft.jpg", "2 · Draft", "AI writes your introduction. Code checks every claim."),
    ("show_approve.jpg", "3 · Approve", "You read, sign, and send. Nothing leaves without you."),
)


def _blend(top: str, alpha: float, under: str) -> str:
    top_rgb = [int(top.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    under_rgb = [int(under.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    mixed = [round(alpha * a + (1 - alpha) * b) for a, b in zip(top_rgb, under_rgb)]
    return "#" + "".join(f"{value:02X}" for value in mixed)


HERO_WORST = _blend(BG, OVERLAY_MIN, WHITE)

# Text on a surface. Each pair is checked for a contrast ratio of at least 4.5.
PAIRS = (
    ("page", SLATE, BG),
    ("canvas", SLATE, SKY),
    ("topbar", WHITE, BAR),
    ("hero_title", WHITE, HERO_WORST),
    ("hero_subtitle", WHITE, HERO_WORST),
    ("banner_start", WHITE, HERO_FROM),
    ("banner_end", WHITE, HERO_TO),
    ("heading", BLUE_TEXT, BG),
    ("heading_on_panel", BLUE_TEXT, SKY),
    ("step_current", WHITE, BLUE),
    ("step_done", INK, GREEN),
    ("step_ready", SLATE, SKY_DARK),
    ("step_locked", LOCKED, SKY),
    ("primary", WHITE, BLUE),
    ("primary_hover", WHITE, BLUE_DARK),
    ("primary_disabled", WHITE, BLUE),
    ("secondary", SLATE, SKY_DARK),
    ("secondary_hover", WHITE, VIOLET),
    ("secondary_disabled", LOCKED, SKY),
    ("chip_wait", INK, AMBER),
    ("chip_ok", INK, GREEN),
    ("chip_stop", WHITE, RED),
    ("tile_found", CYAN, SKY),
    ("tile_shortlist", BLUE_TEXT, SKY),
    ("tile_waiting", AMBER_TEXT, SKY),
    ("tile_approved", GREEN_TEXT, SKY),
    ("tile_sent", VIOLET_TEXT, SKY),
    ("card_find", CYAN, SKY),
    ("card_shortlist", BLUE_TEXT, SKY),
    ("card_draft", VIOLET_TEXT, SKY),
    ("card_review", AMBER_TEXT, SKY),
    ("card_send", GREEN_TEXT, SKY),
    ("input", SLATE, SKY_DARK),
    ("muted", MUTED, SKY),
    ("table", SLATE, SKY),
    ("table_head", SLATE, SKY_DARK),
    ("expander", SLATE, SKY),
    ("showcase_title", WHITE, SKY),
    ("showcase_text", MUTED, SKY),
)

# Icons and large marks need 3:1. These pairs are the colors the SVGs use.
ICON_PAIRS = (
    ("icon_done", INK, GREEN),
    ("icon_current", WHITE, BLUE),
    ("icon_locked", LOCKED, BG),
    ("icon_ready", SLATE, BG),
    ("wordmark_drop", CYAN, BAR),
)

MARK = "M12 2 L21 7 V17 L12 22 L3 17 V7 Z"

_ICONS = {
    "done": (
        '<svg class="tracker-icon" viewBox="0 0 24 24" aria-hidden="true">'
        f'<circle cx="12" cy="12" r="10" fill="{GREEN}"/>'
        f'<path d="M7 12.5 l3 3 l7-7" fill="none" stroke="{INK}" stroke-width="2.2" '
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
.stApp, [data-testid="stAppViewContainer"] {
  background: radial-gradient(1200px 600px at 85% -10%, rgba(109, 63, 224, 0.25), transparent 60%),
              radial-gradient(900px 500px at -10% 10%, rgba(34, 211, 238, 0.12), transparent 60%),
              @BG@;
  color: @SLATE@;
  font-family: "Segoe UI", "Helvetica Neue", sans-serif;
}
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, @BAR@ 0%, @SKY@ 100%);
  border-right: 1px solid @LINE@;
  color: @SLATE@;
}
[data-testid="stSidebar"] * { color: @SLATE@; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stHeader"] *, [data-testid="stToolbar"] * {
  color: @SLATE@ !important;
  -webkit-text-fill-color: @SLATE@ !important;
}
h1, h2, h3 { color: @BLUE_TEXT@; letter-spacing: 0; }
p, li, label, span { color: @SLATE@; }
[data-testid="stCaptionContainer"], small { color: @MUTED@ !important; }
[data-testid="stMain"] .block-container {
  background: transparent;
  padding: 3.75rem 2rem 2rem;
  max-width: 100%;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] input {
  color: @SLATE@ !important;
  -webkit-text-fill-color: @SLATE@ !important;
  background: @SKY_DARK@ !important;
  border: 1px solid @LINE@ !important;
  border-radius: 10px;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
  color: @LOCKED@ !important;
  -webkit-text-fill-color: @LOCKED@ !important;
}
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li {
  background: @SKY_DARK@ !important;
  color: @SLATE@ !important;
}
[data-testid="stMarkdownContainer"] table {
  width: 100%;
  border-collapse: collapse;
  background: @SKY@;
  border-radius: 12px;
  overflow: hidden;
}
[data-testid="stMarkdownContainer"] th {
  background: @SKY_DARK@;
  color: @SLATE@;
  text-align: left;
  padding: 0.55rem 0.7rem;
}
[data-testid="stMarkdownContainer"] td {
  background: @SKY@;
  color: @SLATE@;
  padding: 0.55rem 0.7rem;
  border-top: 1px solid @LINE@;
}
[data-testid="stDataFrame"] { border: 1px solid @LINE@; border-radius: 12px; }
[data-testid="stAlert"] { background: @SKY_DARK@ !important; border: 1px solid @LINE@; border-radius: 12px; }
[data-testid="stAlert"] * { color: @SLATE@ !important; }
.stButton button[kind="primary"],
.stButton button[data-testid="stBaseButton-primary"],
.stButton button[kind="primary"]:disabled,
.stButton button[data-testid="stBaseButton-primary"]:disabled {
  background: linear-gradient(90deg, @BLUE@ 0%, @BLUE_DARK@ 100%) !important;
  color: @WHITE@ !important;
  border: none !important;
  border-radius: 10px;
  opacity: 1 !important;
  box-shadow: 0 0 18px rgba(59, 91, 219, 0.55);
}
.stButton button[kind="primary"]:hover:not(:disabled),
.stButton button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {
  background: @BLUE_DARK@ !important;
  box-shadow: 0 0 24px rgba(34, 211, 238, 0.55);
}
.stButton button[kind="primary"] *,
.stButton button[data-testid="stBaseButton-primary"] * {
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
}
.stButton button[kind="secondary"],
.stButton button[data-testid="stBaseButton-secondary"] {
  background: @SKY_DARK@;
  color: @SLATE@;
  border: 1px solid @LINE@;
  border-radius: 10px;
}
.stButton button[kind="secondary"]:hover:not(:disabled),
.stButton button[data-testid="stBaseButton-secondary"]:hover:not(:disabled) {
  background: @VIOLET@;
  border-color: @VIOLET@;
}
.stButton button[kind="secondary"]:hover:not(:disabled) * {
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
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
  background: @SKY@;
  border: 1px solid @LINE@;
  border-radius: 12px;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  background: @BAR@;
  border-bottom: 2px solid transparent;
  border-image: linear-gradient(90deg, @CYAN@, @BLUE@, @VIOLET@) 1;
  margin: -1rem -2rem 1rem;
  padding: 0.6rem 2rem;
}
.topbar span {
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
}
.topbar .topbar-name { font-weight: 800; font-size: 1.15rem; letter-spacing: 0.04em; }
.topbar .topbar-line { font-size: 0.95rem; }
.hero {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  min-height: 260px;
  margin-bottom: 1rem;
  background-size: cover;
  background-position: center;
  border: 1px solid @LINE@;
  box-shadow: 0 0 40px rgba(59, 91, 219, 0.35);
}
.hero-fallback {
  background-image: linear-gradient(110deg, @HERO_FROM@ 0%, @HERO_TO@ 100%);
}
.hero-fallback .hero-overlay { background: none; }
.hero-overlay h1 a, .hero-overlay h1 svg { display: none; }
.hero-drops {
  position: absolute;
  right: 2rem;
  top: 1.5rem;
  width: 160px;
  height: 180px;
  opacity: 0.35;
}
.hero-overlay {
  position: relative;
  min-height: 260px;
  padding: 1.4rem 1.8rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  background: radial-gradient(ellipse at center, rgba(7, 11, 31, @OVERLAY_MAX@) 0%, rgba(7, 11, 31, @OVERLAY_MIN@) 70%);
}
.hero-overlay h1, .hero-overlay p, .hero-overlay .wordmark-text {
  color: @WHITE@ !important;
  -webkit-text-fill-color: @WHITE@ !important;
  margin: 0;
}
.hero-overlay h1 { font-size: 2.8rem; font-weight: 800; line-height: 1.1; text-shadow: 0 0 24px rgba(34, 211, 238, 0.45); }
.hero-overlay p { margin-top: 0.5rem; font-size: 1.25rem; }
.wordmark { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.8rem; }
.wordmark svg { width: 26px; height: 26px; }
.wordmark-text { font-weight: 800; letter-spacing: 0.18em; font-size: 0.9rem; }
.showcase { display: flex; gap: 0.9rem; margin: 0 0 1rem; }
.showcase-card {
  flex: 1;
  background: @SKY@;
  border: 1px solid @LINE@;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 0 22px rgba(109, 63, 224, 0.22);
}
.showcase-card img { width: 100%; height: 150px; object-fit: cover; display: block; }
.showcase-card .showcase-body { padding: 0.65rem 0.85rem 0.8rem; }
.showcase-card .showcase-title {
  display: block; font-weight: 800; font-size: 1.05rem;
  color: @WHITE@ !important; -webkit-text-fill-color: @WHITE@ !important;
}
.showcase-card .showcase-text {
  display: block; font-size: 0.9rem; margin-top: 0.2rem;
  color: @MUTED@ !important; -webkit-text-fill-color: @MUTED@ !important;
}
.tiles { display: flex; gap: 0.7rem; margin: 0.2rem 0 0.9rem; }
.tile {
  flex: 1;
  background: @SKY@;
  border: 1px solid @LINE@;
  border-radius: 14px;
  padding: 0.7rem 0.8rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.tile-value { display: block; font-size: 1.6rem; font-weight: 800; line-height: 1.1; }
.tile-label { display: block; color: @MUTED@ !important; font-size: 0.85rem; margin-top: 0.2rem; }
.tile-found .tile-value { color: @CYAN@; }
.tile-shortlist .tile-value { color: @BLUE_TEXT@; }
.tile-waiting .tile-value { color: @AMBER_TEXT@; }
.tile-approved .tile-value { color: @GREEN_TEXT@; }
.tile-sent .tile-value { color: @VIOLET_TEXT@; }
.tracker-icon { width: 22px; height: 22px; display: block; margin-bottom: 0.25rem; }
div[data-testid="stColumn"]:has(span.tracker-state[data-state="current"]) button {
  background: @BLUE@ !important;
  border-color: @CYAN@ !important;
  box-shadow: 0 0 16px rgba(34, 211, 238, 0.5);
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
  color: @INK@ !important;
  -webkit-text-fill-color: @INK@ !important;
  font-weight: 700 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="locked"]) button {
  background: @SKY@ !important;
  border-color: @LINE@ !important;
  opacity: 1 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="locked"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="locked"]) button * {
  color: @LOCKED@ !important;
  -webkit-text-fill-color: @LOCKED@ !important;
  font-weight: 500 !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="ready"]) button {
  background: @SKY_DARK@ !important;
  border-color: @LINE@ !important;
}
div[data-testid="stColumn"]:has(span.tracker-state[data-state="ready"]) button,
div[data-testid="stColumn"]:has(span.tracker-state[data-state="ready"]) button * {
  color: @SLATE@ !important;
  -webkit-text-fill-color: @SLATE@ !important;
  font-weight: 600 !important;
}
.step-card {
  background: @SKY@;
  border: 1px solid @LINE@;
  border-left: 5px solid @CYAN@;
  border-radius: 14px;
  padding: 0.65rem 1rem;
  margin-bottom: 0.7rem;
}
.step-card p { margin: 0; font-weight: 800; font-size: 1.15rem; }
.step-card-search { border-left-color: @CYAN@; }
.step-card-search p { color: @CYAN@ !important; -webkit-text-fill-color: @CYAN@ !important; }
.step-card-shortlist { border-left-color: @BLUE@; }
.step-card-shortlist p { color: @BLUE_TEXT@ !important; -webkit-text-fill-color: @BLUE_TEXT@ !important; }
.step-card-run { border-left-color: @VIOLET@; }
.step-card-run p { color: @VIOLET_TEXT@ !important; -webkit-text-fill-color: @VIOLET_TEXT@ !important; }
.step-card-review { border-left-color: @AMBER@; }
.step-card-review p { color: @AMBER_TEXT@ !important; -webkit-text-fill-color: @AMBER_TEXT@ !important; }
.step-card-outbox { border-left-color: @GREEN@; }
.step-card-outbox p { color: @GREEN_TEXT@ !important; -webkit-text-fill-color: @GREEN_TEXT@ !important; }
.badge-wait, .badge-warn {
  display: inline-block;
  background: @AMBER@;
  color: @INK@ !important;
  -webkit-text-fill-color: @INK@ !important;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.badge-ok {
  display: inline-block;
  background: @GREEN@;
  color: @INK@ !important;
  -webkit-text-fill-color: @INK@ !important;
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
.model-note { color: @MUTED@ !important; font-size: 0.9rem; }
"""

_VALUES = {
    "BG": BG, "SLATE": SLATE, "BAR": BAR, "WHITE": WHITE, "BLUE": BLUE, "BLUE_DARK": BLUE_DARK,
    "BLUE_TEXT": BLUE_TEXT, "VIOLET": VIOLET, "VIOLET_TEXT": VIOLET_TEXT, "INK": INK,
    "SKY": SKY, "SKY_DARK": SKY_DARK, "MUTED": MUTED, "LOCKED": LOCKED, "LINE": LINE,
    "GREEN": GREEN, "GREEN_TEXT": GREEN_TEXT, "AMBER": AMBER, "AMBER_TEXT": AMBER_TEXT,
    "RED": RED, "CYAN": CYAN, "HERO_FROM": HERO_FROM, "HERO_TO": HERO_TO,
    "OVERLAY_MAX": str(OVERLAY_MAX), "OVERLAY_MIN": str(OVERLAY_MIN),
}


def _css() -> str:
    text = _CSS
    for name, value in sorted(_VALUES.items(), key=lambda item: -len(item[0])):
        text = text.replace(f"@{name}@", value)
    return text


def icon(name: str) -> str:
    """Inline SVG. The page does not fetch a font."""
    return _ICONS[name]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio for two #RRGGBB colors."""
    lighter = max(_luminance(foreground), _luminance(background))
    darker = min(_luminance(foreground), _luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def build_hero_image(root: Path | None = None) -> Path | None:
    """Shrink the banner to a web copy under 150 KB. None when there is no source image."""
    base = Path(root) if root is not None else repo_root()
    source = base / HERO_SOURCE
    target = base / HERO_WEB
    if not source.is_file():
        return target if target.is_file() and target.stat().st_size <= HERO_MAX_BYTES and root is None else None
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
def _file_uri(path_text: str, stamp: float) -> str:
    path = Path(path_text)
    if not path.is_file():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def hero_uri() -> str:
    path = build_hero_image()
    if path is None:
        return ""
    return _file_uri(str(path), path.stat().st_mtime)


def showcase_html() -> str:
    """Three image cards under the hero, shown on the Find step. Empty when images are missing."""
    cards = []
    for name, title, text in SHOWCASE:
        path = repo_root() / "assets" / name
        if not path.is_file():
            return ""
        uri = _file_uri(str(path), path.stat().st_mtime)
        cards.append(
            f'<div class="showcase-card"><img src="{uri}" alt=""/>'
            f'<div class="showcase-body"><span class="showcase-title">{title}</span>'
            f'<span class="showcase-text">{text}</span></div></div>'
        )
    return '<div class="showcase">' + "".join(cards) + "</div>"


def wordmark(display_name: str) -> str:
    return (
        '<div class="wordmark">'
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        f'<path d="{MARK}" fill="none" stroke="{CYAN}" stroke-width="1.8" stroke-linejoin="round"/>'
        f'<circle cx="12" cy="12" r="3.2" fill="{CYAN}"/>'
        "</svg>"
        f'<span class="wordmark-text">{display_name.upper()}</span></div>'
    )


def header_html(brand, display_name: str, uri: str | None = None) -> str:
    """Top bar and hero. Words come from the profile. A missing banner gives a gradient."""
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
            '<svg class="hero-drops" viewBox="0 0 24 24" aria-hidden="true">'
            f'<path d="{MARK}" fill="none" stroke="{CYAN}" stroke-width="1.2"/></svg>'
        )
    hero = (
        f'<div class="{kind}">{drops}<div class="hero-overlay">{wordmark(display_name)}'
        f"<h1>{title}</h1><p>{brand.hero_subtitle}</p></div></div>"
    )
    try:
        on_find = st.session_state.get("step", "search") == "search"
    except Exception:
        on_find = False
    show = showcase_html() if on_find and uri else ""
    return css + bar + hero + show


def apply_theme() -> str:
    """Inject the theme and return the CSS."""
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
