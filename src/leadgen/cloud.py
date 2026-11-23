"""Streamlit Community Cloud support: detect it, read its secrets, and build a mailto link.

Settings load order for every key: environment variable, then Streamlit secrets, then the local key file.
This module never prints a key value.
"""

import json
import os
from pathlib import Path
from urllib.parse import quote

from leadgen.paths import repo_root

# Every name the app reads. Secrets may supply any of these; an environment variable that is set wins.
SECRET_NAMES = (
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "LEADGEN_LLM_MODE",
    "SAM_API_KEY",
    "CENSUS_API_KEY",
    "LEADGEN_EDGAR_USER_AGENT",
    "LEADGEN_TAILOR_PROVIDER",
    "LEADGEN_TAILOR_MODEL",
    "LEADGEN_DRAFTER_PROVIDER",
    "LEADGEN_DRAFTER_MODEL",
    "LEADGEN_EVALUATOR_PROVIDER",
    "LEADGEN_EVALUATOR_MODEL",
)
SHARED_NOTE = "Shared copy: searches and drafts reset when the app restarts."
CLOUD_ROOT = "/mount/src/"


def is_cloud() -> bool:
    """True on Community Cloud. LEADGEN_CLOUD=1 or 0 overrides the path check."""
    flag = os.environ.get("LEADGEN_CLOUD", "").strip()
    if flag in {"0", "1"}:
        return flag == "1"
    return repo_root().as_posix().startswith(CLOUD_ROOT)


def load_streamlit_secrets() -> None:
    """Copy known secrets into the environment where nothing is set yet. Never raises."""
    if os.environ.get("LEADGEN_SKIP_SECRETS", "").strip() == "1":
        return
    try:
        import streamlit as st

        secrets = st.secrets
        for name in SECRET_NAMES:
            if os.environ.get(name, "").strip():
                continue
            value = secrets.get(name, "")
            if isinstance(value, str) and value.strip():
                os.environ[name] = value.strip()
    except Exception:
        return


def prepare_cloud(root: Path) -> None:
    """On Cloud: live model mode by default, and the folders the app writes to."""
    if not is_cloud():
        return
    os.environ.setdefault("LEADGEN_LLM_MODE", "live")
    for name in ("runs", "outbox"):
        (Path(root) / name).mkdir(parents=True, exist_ok=True)


def mailto_url(recipient: str, subject: str, body: str) -> str:
    """A mailto link with the recipient, subject, and body percent-encoded."""
    return f"mailto:{quote(recipient.strip(), safe='@')}?subject={quote(subject, safe='')}&body={quote(body, safe='')}"


def clipboard_html(text: str, border: str, fill: str, ink: str, note: str) -> str:
    """One button that copies `text`. The text is embedded as JSON, so quotes and tags are safe."""
    payload = json.dumps(text).replace("</", "<\\/")
    return f"""
<button id="copy" style="font:600 14px sans-serif;padding:.5rem 1rem;border-radius:.5rem;border:1px solid {border};
background:{fill};color:{ink};cursor:pointer">Copy email</button>
<span id="done" style="font:14px sans-serif;color:{note};margin-left:.6rem"></span>
<script>
const text = {payload};
document.getElementById("copy").onclick = async () => {{
  let ok = false;
  try {{ await navigator.clipboard.writeText(text); ok = true; }} catch (e) {{
    const box = document.createElement("textarea");
    box.value = text; document.body.appendChild(box); box.select();
    try {{ ok = document.execCommand("copy"); }} catch (e2) {{}}
    box.remove();
  }}
  document.getElementById("done").textContent = ok ? "Copied." : "Select the text above and copy it.";
}};
</script>
"""
