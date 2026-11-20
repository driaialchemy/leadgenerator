"""Kill switch is off unless the env var, a .env file, or a KILL_SWITCH file says otherwise."""

import pytest

from leadgen.kill_switch import KillSwitchEngaged, assert_not_engaged, is_engaged


def _isolate(monkeypatch, tmp_path):
    """Stay inside tmp_path so the test never opens the repo .env."""
    monkeypatch.chdir(tmp_path)


def _unset_switch(monkeypatch):
    """Drop the switch variable, and delete it again on teardown.

    load_dotenv writes os.environ itself. setenv records a teardown that
    removes the name when this test created it.
    """
    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "0")
    monkeypatch.delenv("LEADGEN_KILL_SWITCH")


def test_off_by_default(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _unset_switch(monkeypatch)
    assert is_engaged(tmp_path) is False


def test_on_with_env_var(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "1")
    assert is_engaged(tmp_path) is True


def test_on_with_kill_switch_file(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _unset_switch(monkeypatch)
    (tmp_path / "KILL_SWITCH").write_text("", encoding="utf-8")
    assert is_engaged(tmp_path) is True


def test_dotenv_file_turns_switch_on(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _unset_switch(monkeypatch)
    (tmp_path / ".env").write_text("LEADGEN_KILL_SWITCH=1\n", encoding="utf-8")
    assert is_engaged(tmp_path) is True


def test_dotenv_does_not_override_existing_environment(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "0")
    (tmp_path / ".env").write_text("LEADGEN_KILL_SWITCH=1\n", encoding="utf-8")
    assert is_engaged(tmp_path) is False


def test_assert_not_engaged_raises_when_on(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "1")
    with pytest.raises(KillSwitchEngaged):
        assert_not_engaged(tmp_path)
