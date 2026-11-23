# 验证原生作废尝试同时退出整场伤害和时间分母，且不重复扣除重叠时停。
from types import SimpleNamespace

import pytest

from src.services.battle_report.analysis.metrics import project_report_metrics
from src.domain.battle_report.timeline.events import BattleObservedTimeStopInterval


def case():
    summary = SimpleNamespace(total_damage=100.0, total_damage_taken=99.0,
                              duration_seconds=10.0, dps_time_mode="elapsed")
    analysis = SimpleNamespace(battle_start_us=0, battle_end_us=10_000_000,
        range_start_us=0, range_end_us=10_000_000, effective_damage=60.0,
        hits=(SimpleNamespace(direction="outgoing", damage=60.0),
              SimpleNamespace(direction="incoming", damage=9.0)),
        axis_complete=False, time_stop_intervals=((4_000_000, 7_000_000),),
        time_stop_source_kind="nte_core", discarded_attempt_intervals=((2_000_000, 6_000_000),),
        timeline_damage_correction_total=0.0)
    return summary, analysis


def test_whole_report_uses_valid_hits_and_union_of_void_time_and_time_stop():
    summary, analysis = case()
    result = project_report_metrics(summary, analysis)
    assert (result.damage, result.damage_taken) == (60.0, 9.0)
    assert (result.duration, result.real_duration) == (5.0, 6.0)
    assert result.dps == pytest.approx(12.0)
    assert summary.total_damage == 100.0


def test_valid_half_does_not_subtract_void_time_outside_its_range():
    summary, analysis = case()
    analysis.range_start_us = 7_000_000
    result = project_report_metrics(summary, analysis)
    assert (result.duration, result.real_duration) == (3.0, 3.0)


def test_partial_time_stop_still_excludes_proven_void_attempt():
    summary, analysis = case()
    analysis.time_stop_source_kind = "nte_core_partial"
    result = project_report_metrics(summary, analysis)
    assert result.duration == result.real_duration == 6.0
    assert result.partial_clock


def test_no_confirmed_void_attempt_preserves_existing_summary_policy():
    summary, analysis = case()
    analysis.discarded_attempt_intervals = ()
    result = project_report_metrics(summary, analysis)
    assert (result.damage, result.damage_taken) == (100.0, 99.0)


def test_menu_is_excluded_from_real_and_effective_metrics_without_double_subtraction():
    summary, analysis = case()
    analysis.discarded_attempt_intervals = ()
    analysis.observed_typed_time_stop_intervals = (BattleObservedTimeStopInterval(2_000_000, 6_000_000, 2),)
    result = project_report_metrics(summary, analysis)
    assert (result.duration, result.real_duration) == (5.0, 6.0)
    analysis.time_stop_source_kind = "nte_core_partial"
    result = project_report_metrics(summary, analysis)
    assert result.duration == result.real_duration == 6.0
