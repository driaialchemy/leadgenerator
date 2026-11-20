"""Find the repo root."""

from pathlib import Path


def repo_root() -> Path:
    """Directory that contains pyproject.toml, walking up from this file."""
    start = Path(__file__).resolve().parent
    for folder in (start, *start.parents):
        if (folder / "pyproject.toml").is_file():
            return folder
    return Path.cwd()
