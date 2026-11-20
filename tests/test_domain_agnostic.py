"""Industry words stay in profile YAML and sample data."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = (
    "dental",
    "hvac",
    "copperline",
    "desert peak",
    "home_services",
    "b2b_services",
)


def test_package_does_not_name_an_industry():
    folder = ROOT / "src" / "leadgen"
    offenders = []
    for path in sorted(folder.rglob("*.py")):
        text = path.read_text(encoding="utf-8").casefold()
        for word in FORBIDDEN:
            if word.casefold() in text:
                offenders.append(f"{path.relative_to(ROOT).as_posix()}: {word}")
    assert offenders == []
