"""Run one prospect or every prospect in a profile. Offline replay is the default."""

import argparse
from pathlib import Path

from leadgen.kill_switch import KillSwitchEngaged, assert_not_engaged
from leadgen.llm import ProviderError
from leadgen.loaders import load_prospects
from leadgen.paths import repo_root
from leadgen.pipeline import _log, run_prospect
from leadgen.profiles import load_pipeline_config, load_profile


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m leadgen.run")
    parser.add_argument("--profile", required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--prospect")
    choice.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    folder = Path(root) if root is not None else repo_root()
    try:
        assert_not_engaged(folder)
    except KillSwitchEngaged as exc:
        _log(folder, "kill-switch", "kill_switch_block", "system", "blocked", str(exc))
        print(str(exc))
        return 1
    profile = load_profile(args.profile)
    pipeline = load_pipeline_config()
    prospects = load_prospects(profile)
    if args.prospect:
        prospects = [item for item in prospects if item.prospect_id == args.prospect]
        if not prospects:
            print(f"No prospect {args.prospect}.")
            return 1
    for prospect in prospects:
        try:
            result = run_prospect(profile, prospect, pipeline, folder)
        except ProviderError as exc:
            _log(
                folder,
                prospect.prospect_id,
                "error",
                exc.role,
                "fail",
                exc.line(),
                provider=exc.provider,
                model=exc.model,
            )
            print(
                f"{exc.role} {exc.provider}: {exc.line()}. "
                "switch to Offline or fix the account"
            )
            return 1
        place = result.run_dir.name if result.run_dir else "-"
        print(f"{prospect.prospect_id} {result.status} {place}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
