"""Ask each vendor for one short reply. Prints yes/no, never a key."""

import os

from leadgen.kill_switch import KillSwitchEngaged, assert_not_engaged
from leadgen.llm import call_model, load_project_env, one_line, role_config, scrub


def main(argv: list[str] | None = None) -> int:
    try:
        assert_not_engaged()
    except KillSwitchEngaged as exc:
        print(str(exc))
        return 1
    path = load_project_env()
    print(f"Env file: {path if path else 'none'}")
    failed = False
    for role in ("tailor", "drafter", "evaluator"):
        provider, _model, key_name = role_config(role)
        found = bool(os.environ.get(key_name, "").strip())
        if not found:
            print(f"{provider}: key no, call fail")
            failed = True
            continue
        try:
            call_model(role, "Reply with ok")
        except Exception as exc:
            print(f"{provider}: key yes, call fail: {scrub(one_line(str(exc)))}")
            failed = True
            continue
        print(f"{provider}: key yes, call ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
