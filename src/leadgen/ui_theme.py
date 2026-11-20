"""Dark theme for the demo page. Presentation only."""

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

from leadgen.paths import repo_root

# Processed photos. The originals live in assets/source/ and stay out of the public repo.
_PAGE = "bg_page.webp"
_SIDEBAR = "bg_sidebar.webp"
HERO_NAME = "hero_pipeline.webp"

_BASE = """
/* Chips name who is speaking: the model, the code, the log, or the person. */
.capex-label {
  display: inline-block;
  margin: 0.2rem 0 0.6rem 0;
  padding: 0.15rem 0.7rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #080C18;
}
.capex-ai { background: #B48CFF; }
.capex-code { background: #5BE3A1; }
.capex-record { background: #7FB8FF; }
.capex-human { background: #FFC56B; }

/* Large type for the back of the room. */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stSidebar"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] td {
  font-size: 1.25rem;
  color: #F5F7FB;
}
h1, h2, h3 { color: #FFFFFF; }
[data-testid="stMarkdownContainer"] table {
  width: 100%;
  border-collapse: collapse;
  font-size: 1.2rem;
}
[data-testid="stMarkdownContainer"] th,
[data-testid="stMarkdownContainer"] td {
  border: 1px solid rgba(80, 160, 230, 0.7);
  padding: 0.45rem 0.7rem;
  color: #F5F7FB;
  background: #141E34;
  text-align: left;
}
.stButton button { font-size: 1.15rem; color: #081018; }
.blocked-draft {
  background: #8C2F2F;
  color: #FFFFFF;
  padding: 0.5rem 0.7rem;
  border-radius: 8px;
}

/* The main column is a glass panel so the photo stays behind the words. */
[data-testid="stMain"] .block-container {
  background: rgba(12, 18, 34, 0.85);
  border: 1px solid rgba(90, 200, 255, 0.35);
  border-radius: 18px;
  padding: 1.5rem;
}

/* Tables and metric cards stay on a solid fill, not on the photograph. */
[data-testid="stDataFrame"],
[data-testid="stTable"],
[data-testid="stMetric"] {
  background: #141E34;
  border: 1px solid rgba(80, 160, 230, 0.6);
  border-radius: 12px;
}
"""


def _folder(assets_dir: Path | None) -> Path:
    if assets_dir is not None:
        return Path(assets_dir)
    return repo_root() / "assets"


def hero_path(assets_dir: Path | None = None) -> Path | None:
    """Banner file, or None when it has not been added yet."""
    path = _folder(assets_dir) / HERO_NAME
    return path if path.is_file() else None


@lru_cache(maxsize=None)
def _image_base64(path_str: str) -> str:
    """Read one image's base64 once. Later calls reuse the cached string."""
    return base64.b64encode(Path(path_str).read_bytes()).decode("ascii")


def _uri(path: Path) -> str | None:
    """Embed one image. A missing file returns None so that rule is skipped."""
    if not path.is_file():
        return None
    kind = "image/webp" if path.suffix.lower() == ".webp" else "image/png"
    return f"data:{kind};base64,{_image_base64(str(path.resolve()))}"


def _page_rule(uri: str) -> str:
    return f"""
.stApp {{
  background-color: #080C18;
  background-image: url("{uri}");
  background-size: cover;
  background-attachment: fixed;
  background-position: center;
}}
"""


def _sidebar_rule(uri: str) -> str:
    return f"""
[data-testid="stSidebar"] {{
  background-image: linear-gradient(rgba(8, 12, 24, 0.55), rgba(8, 12, 24, 0.55)), url("{uri}");
  background-size: cover;
  background-position: center;
}}
"""


def apply_theme(assets_dir: Path | None = None) -> str:
    """Inject the theme CSS and return it. Missing images are left out."""
    folder = _folder(assets_dir)
    parts = [_BASE]
    page = _uri(folder / _PAGE)
    sidebar = _uri(folder / _SIDEBAR)
    if page:
        parts.append(_page_rule(page))
    if sidebar:
        parts.append(_sidebar_rule(sidebar))
    css = "\n".join(parts)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    return css
