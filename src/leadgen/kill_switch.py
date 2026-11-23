"""Stop the pipeline when the kill switch is on."""

import os
from pathlib import Path

from dotenv import load_dotenv

from leadgen.paths import repo_root


class KillSwitchEngaged(RuntimeError):
    """Raised when the pipeline is asked to run with the kill switch on."""


def is_engaged(root: Path | None = None) -> bool:
    """True when LEADGEN_KILL_SWITCH=1 or a KILL_SWITCH file is present.

    Loads `.env` from the repo root, or from `root` when given.
    A variable already set in the environment is not replaced.
    Only that folder is read. An explicit path does not search parent directories.
    """
    folder = Path(root) if root is not None else repo_root()
    repository = repo_root()
    load_dotenv(repository / ".env", override=False)
    if folder.resolve() != repository.resolve():
        load_dotenv(folder / ".env", override=False)
    if os.environ.get("LEADGEN_KILL_SWITCH") == "1":
        return True
    return (repository / "KILL_SWITCH").is_file() or (folder / "KILL_SWITCH").is_file()


def assert_not_engaged(root: Path | None = None) -> None:
    if is_engaged(root):
        raise KillSwitchEngaged(
            "Kill switch is engaged. Refusing to run. "
            "Unset LEADGEN_KILL_SWITCH or remove the KILL_SWITCH file."
        )
