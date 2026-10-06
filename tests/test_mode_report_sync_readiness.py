# 验证检测报告只在开启条件已核对且无阻断项时提供同步强引导。
import os
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from src.domain.work_mode import (
    CheckState, FeatureCheck, NativeFeatureProbe, WorkMode, WorkModeProbe,
    WorkModeReport, WorkModeSettings,
)
from src.features.settings.work_mode_card import ModeReportDialog
from src.services.work_mode_checks import build_work_mode_report


def native_report(**changes):
    native = NativeFeatureProbe(files=True)
    probe = WorkModeProbe(
        analysis_available=True, component_update_state=CheckState.AVAILABLE,
        game_path_valid=True, core_available=True, input_available=True,
        native_load=native, native_battle=native, native_equipment=native,
        native_character=native, native_inventory=native, native_team=native,
        native_environment=native,
    )
    settings = WorkModeSettings(mode=WorkMode.MEDIUM, risk_confirmed=True, pending_cleanup=False)
    return build_work_mode_report(settings, replace(probe, **changes))


def test_verified_components_allow_sync_before_game_and_snapshots_are_ready():
    report = native_report()
    assert not report.ready
    assert report.can_offer_sync_enable
    checks = {item.feature: item for item in report.features}
    assert checks["native_inventory"].state == CheckState.WAITING


@pytest.mark.parametrize("changes", (
    {"native_load": NativeFeatureProbe(files=False)},
    {"native_load": NativeFeatureProbe(files=None)},
    {"native_inventory": NativeFeatureProbe(files=None)},
    {"core_available": False},
    {"core_available": None},
    {"game_path_valid": False},
    {"game_path_valid": None},
    {"analysis_available": False},
    {"component_update_state": CheckState.FAULT},
    {"component_update_state": CheckState.MISSING},
    {"component_update_state": CheckState.CLEANUP_PENDING},
    {"component_update_state": CheckState.WAITING},
    {"native_diagnostic": "本次业务检测尚未完成"},
))
def test_missing_or_unverified_conditions_do_not_offer_sync(changes):
    assert not native_report(**changes).can_offer_sync_enable


def test_missing_components_remain_a_shared_cause_with_deployment_action():
    native = NativeFeatureProbe(files=False)
    report = native_report(**{name: native for name in (
        "native_load", "native_battle", "native_equipment", "native_character",
        "native_inventory", "native_team", "native_environment",
    )})
    blocked = [item for item in report.features if item.state == CheckState.MISSING]
    assert len(blocked) == 7
    assert len({item.detail for item in blocked}) == 1
    assert all("manual_deploy" in item.actions for item in blocked)
    assert not report.can_offer_sync_enable


@pytest.mark.parametrize("npcap", (False, None))
def test_low_mode_requires_verified_capture_dependencies(npcap):
    settings = WorkModeSettings(mode=WorkMode.LOW, risk_confirmed=True, pending_cleanup=False)
    report = build_work_mode_report(settings, WorkModeProbe(
        analysis_available=True, core_available=True, input_available=True, npcap_available=npcap,
    ))
    assert not report.can_offer_sync_enable


def test_low_mode_allows_starting_listener_before_login():
    settings = WorkModeSettings(mode=WorkMode.LOW, risk_confirmed=True, pending_cleanup=False)
    report = build_work_mode_report(settings, WorkModeProbe(
        analysis_available=True, core_available=True, input_available=True, npcap_available=True,
    ))
    assert report.can_offer_sync_enable


@pytest.mark.parametrize("feature,state,facts", (
    ("sync", CheckState.MISSING, ()),
    ("sync", CheckState.FAULT, ()),
    ("sync", CheckState.CLEANUP_PENDING, ()),
    ("sync", CheckState.WARNING, ()),
    ("cleanup", CheckState.WAITING, ()),
    ("sync", CheckState.WAITING, (("inspection_incomplete", True),)),
    ("native_inventory", CheckState.WAITING, (("files", None),)),
))
def test_dialog_hides_sync_even_if_provider_would_offer_it(feature, state, facts):
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    provider = Mock(return_value=Mock())
    dialog = ModeReportDialog(parent, SimpleNamespace(check=Mock()), sync_action_provider=provider)
    try:
        dialog.begin("medium")
        report = WorkModeReport(WorkMode.MEDIUM, (
            FeatureCheck(feature, "同步条件", state, "请查看检测详情", facts=facts),
        ), sync_enable_ready=True)
        dialog.set_report(report)
        provider.assert_not_called()
        assert not any(button.text() == "开启自动同步" and not button.isHidden()
                       for button in dialog.findChildren(QPushButton))
    finally:
        dialog.close()
        parent.close()
        app.processEvents()


def test_unverified_report_defaults_to_not_offering_sync():
    report = WorkModeReport(WorkMode.MEDIUM, (
        FeatureCheck("sync", "同步", CheckState.WAITING, "待核对"),
    ))
    assert not report.can_offer_sync_enable


def test_login_wait_can_keep_sync_guidance_when_environment_is_verified():
    report = WorkModeReport(WorkMode.MEDIUM, (
        FeatureCheck("native_inventory", "DLL 完整背包库存", CheckState.WAITING_LOGIN,
                     "请登录并等待完整数据", facts=(("files", True),)),
    ), sync_enable_ready=True)
    assert report.can_offer_sync_enable
