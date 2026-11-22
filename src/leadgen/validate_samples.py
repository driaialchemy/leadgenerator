"""Load every profile YAML and its sample files.

Profiles are discovered from config/profiles/*.yaml so this file does not name one.
"""

from leadgen.loaders import load_outcomes, load_prospects
from leadgen.paths import repo_root
from leadgen.profiles import load_pipeline_config, load_profile


def main() -> int:
    root = repo_root()
    failures = 0
    profile_dir = root / "config" / "profiles"
    profile_paths = sorted(profile_dir.glob("*.yaml"))
    if not profile_paths:
        print("FAIL config/profiles: no profile files found")
        failures += 1

    for path in profile_paths:
        profile_id = path.stem
        relative = path.relative_to(root).as_posix()
        try:
            profile = load_profile(profile_id)
        except Exception as exc:
            failures += 1
            _fail(relative, exc)
            for name in ("prospects.csv", "outcomes.csv"):
                failures += 1
                _fail(f"sample_data/{profile_id}/{name}", "profile did not load")
            continue
        _pass(relative)
        for name, loader in (
            ("prospects.csv", load_prospects),
            ("outcomes.csv", load_outcomes),
        ):
            data_path = root / "sample_data" / profile.profile_id / name
            label = data_path.relative_to(root).as_posix()
            if not data_path.is_file():
                _pass(f"{label} not required")
                continue
            try:
                loader(profile)
            except Exception as exc:
                failures += 1
                _fail(label, exc)
            else:
                _pass(label)

    pipeline = root / "config" / "pipeline.yaml"
    label = pipeline.relative_to(root).as_posix()
    try:
        load_pipeline_config()
    except Exception as exc:
        failures += 1
        _fail(label, exc)
    else:
        _pass(label)

    return 1 if failures else 0


def _pass(label: str) -> None:
    print(f"PASS {label}")


def _fail(label: str, reason: object) -> None:
    text = " ".join(str(reason).splitlines())
    print(f"FAIL {label}: {text}")


if __name__ == "__main__":
    raise SystemExit(main())
