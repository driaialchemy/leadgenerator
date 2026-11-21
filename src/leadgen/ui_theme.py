"""Light theme for the class page. Presentation only."""

import streamlit as st

# Text on a surface. Each pair is checked for a contrast ratio of at least 4.5.
PAIRS = (
    ("page", "#1B2430", "#FFFFFF"),
    ("panel", "#1B2430", "#F4F6F8"),
    ("muted", "#243140", "#FFFFFF"),
    ("input", "#1B2430", "#FFFFFF"),
    ("primary", "#FFFFFF", "#0D47A1"),
    ("secondary", "#1B2430", "#E6EBF1"),
    ("approved", "#FFFFFF", "#0D6B3D"),
    ("warning", "#1B2430", "#FFE08A"),
    ("blocked", "#FFFFFF", "#9B1C1C"),
    ("chip", "#1B2430", "#D6E4FF"),
    ("table", "#1B2430", "#FFFFFF"),
    ("table_head", "#1B2430", "#E4EAF2"),
    ("expander", "#1B2430", "#F4F6F8"),
)

_CSS = """
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stSidebar"], [data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li, [data-testid="stMarkdownContainer"] td,
[data-testid="stCaptionContainer"] {
  color: #1B2430;
  font-family: "Segoe UI", "Helvetica Neue", sans-serif;
}
h1, h2, h3 { color: #1B2430; letter-spacing: 0; }
[data-testid="stMain"] .block-container {
  background: #FFFFFF;
  padding-top: 1.5rem;
}
[data-testid="stSidebar"] {
  background: #F4F6F8;
  border-right: 1px solid #D5DDE6;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stNumberInput"] input {
  color: #1B2430 !important;
  -webkit-text-fill-color: #1B2430 !important;
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
  background: #E4EAF2;
  color: #1B2430;
  text-align: left;
  padding: 0.55rem 0.7rem;
}
[data-testid="stMarkdownContainer"] td {
  background: #FFFFFF;
  color: #1B2430;
  padding: 0.55rem 0.7rem;
  border-top: 1px solid #D5DDE6;
}
.stButton button[kind="primary"], .stButton button[data-testid="stBaseButton-primary"] {
  background: #0D47A1;
  color: #FFFFFF;
  border: none;
  border-radius: 10px;
}
.stButton button[kind="secondary"], .stButton button[data-testid="stBaseButton-secondary"] {
  background: #E6EBF1;
  color: #1B2430;
  border: 1px solid #C5D0DC;
  border-radius: 10px;
}
div[data-testid="stExpander"] {
  background: #F4F6F8;
  border: 1px solid #D5DDE6;
  border-radius: 12px;
}
.step-strip {
  color: #243140;
  letter-spacing: 0.04em;
  font-weight: 600;
  margin-bottom: 0.6rem;
}
.badge-wait {
  display: inline-block;
  background: #0D47A1;
  color: #FFFFFF;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.badge-ok {
  display: inline-block;
  background: #0D6B3D;
  color: #FFFFFF;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.badge-warn {
  display: inline-block;
  background: #FFE08A;
  color: #1B2430;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.badge-stop {
  display: inline-block;
  background: #9B1C1C;
  color: #FFFFFF;
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-weight: 700;
}
.model-note { color: #243140; font-size: 0.9rem; }
"""


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio for two #RRGGBB colors."""
    lighter = max(_luminance(foreground), _luminance(background))
    darker = min(_luminance(foreground), _luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def apply_theme() -> str:
    """Inject the light theme and return the CSS."""
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
