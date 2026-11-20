"""Print the ranked list, exclusions, findings, and funnel. Writes no files."""

import argparse
from pathlib import Path

from leadgen.findings import run_note_checks
from leadgen.kill_switch import KillSwitchEngaged, assert_not_engaged
from leadgen.loaders import load_outcomes, load_prospects
from leadgen.metrics import funnel
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.scoring import qualify


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m leadgen.qualify")
    parser.add_argument(
        "--profile",
        required=True,
        help="Profile id of the YAML file in config/profiles.",
    )
    args = parser.parse_args(argv)
    try:
        assert_not_engaged(root)
    except KillSwitchEngaged as exc:
        print(str(exc))
        return 1
    try:
        profile = load_profile(args.profile)
        pipeline = load_pipeline_config()
        prospects = load_prospects(profile)
        outcomes = load_outcomes(profile)
    except Exception as exc:
        print(str(exc))
        return 1
    ranked, excluded = qualify(prospects, profile, pipeline)
    _print_report(profile, ranked, excluded, prospects, outcomes)
    return 0


def _print_report(profile, ranked, excluded, prospects, outcomes) -> None:
    print(f"profile: {profile.profile_id}")
    print()
    print("Ranked")
    print(f"{'prospect_id':<12}{'score':<7}{'tier':<6}draft")
    for row in ranked:
        draft = "yes" if row.draft_eligible else "no"
        print(f"{row.prospect_id:<12}{row.total:<7}{row.tier:<6}{draft}")
    print()
    print("Excluded")
    for item in excluded:
        print(f"{item.prospect_id:<12}{item.reason}")
    print()
    print("Findings")
    for prospect in sorted(prospects, key=lambda item: item.prospect_id):
        for finding in run_note_checks(prospect, profile):
            print(f"{finding.prospect_id:<12}{finding.check_id:<20}{finding.message}")
    print()
    print("Funnel")
    stats = funnel(outcomes)
    print(f"sent {stats.sent}")
    print(f"replied {stats.replied}")
    print(f"meeting {stats.meeting}")
    print(f"won {stats.won}")
    print(f"won_value {stats.won_value}")
    print(f"reply_rate {_format_rate(stats.reply_rate)}")
    print(f"meeting_rate {_format_rate(stats.meeting_rate)}")
    print(f"win_rate {_format_rate(stats.win_rate)}")
    print(f"avg_deal {stats.avg_deal:.2f}")


def _format_rate(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"


if __name__ == "__main__":
    raise SystemExit(main())
