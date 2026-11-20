"""Funnel math from past outcomes."""

from leadgen.loaders import load_outcomes
from leadgen.metrics import funnel
from leadgen.profiles import load_profile


def test_b2b_funnel():
    stats = funnel(load_outcomes(load_profile("b2b_services")))
    assert stats.sent == 8
    assert stats.replied == 6
    assert stats.meeting == 4
    assert stats.won == 2
    assert stats.won_value == 42000
    assert stats.reply_rate == 0.75
    assert stats.meeting_rate == 0.5
    assert stats.win_rate == 0.25
    assert stats.avg_deal == 21000.00


def test_home_funnel():
    stats = funnel(load_outcomes(load_profile("home_services")))
    assert stats.sent == 8
    assert stats.replied == 5
    assert stats.meeting == 4
    assert stats.won == 3
    assert stats.won_value == 17050
    assert stats.reply_rate == 0.625
    assert stats.meeting_rate == 0.5
    assert stats.win_rate == 0.375
    assert stats.avg_deal == 5683.33


def test_empty_outcomes_are_zero():
    stats = funnel([])
    assert stats.sent == 0
    assert stats.replied == 0
    assert stats.meeting == 0
    assert stats.won == 0
    assert stats.won_value == 0
    assert stats.reply_rate == 0
    assert stats.meeting_rate == 0
    assert stats.win_rate == 0
    assert stats.avg_deal == 0
