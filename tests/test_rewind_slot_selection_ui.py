# 验证倒带槽位草稿确认、显示分数与失效结果保护。
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QToolButton

from src.domain.rewind_loadout import RewindSlotReference, RewindSlotSummary
from src.features.toolbox.rewind_role_picker import _RoleSelectionDialog
from src.features.toolbox.rewind_slot_picker import RewindSlotPicker
from src.services.rewind_shape_recommendation_service import RewindTargetRole


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


def role_fixture(identifier=1004, name="安魂曲"):
    return RewindTargetRole(identifier, name, None, slots=tuple(
        RewindSlotSummary(RewindSlotReference(identifier, slot_id, slot_id + 10),
                          "很长的主力槽位名称" if slot_id == 1 else "备用",
                          "primary" if slot_id == 1 else "second", slot_id, 3, score,
                          "ready", "驱动完整")
        for slot_id, score in ((1, 260), (2, 230))
    ))


def picker(roles, selected=(), slots=None):
    return _RoleSelectionDialog(None, title="选择角色", description="选择推荐槽位",
                                roles=roles, selected_character_ids=set(selected), selected_slots=slots)


def test_card_score_is_selected_slot_not_highest_and_long_name_does_not_hide_score(application):
    role = role_fixture()
    dialog = picker((role,), (1004,), {1004: role.slots[1].reference})
    card = dialog.findChild(QToolButton, "rewindRoleSelectionCard")
    assert card.property("rewindCalculationScore") == 230
    assert "230" in card.findChild(QLabel, "rewindRoleCalculationScore").text()
    assert "备用" in card.toolTip()
    dialog.reject()


def test_role_order_uses_highest_slot_score_not_selected_slot_and_survives_filtering(application):
    from dataclasses import replace

    high = role_fixture(1004, "安魂曲")
    high = replace(high, slots=(replace(high.slots[0], score=300), replace(high.slots[1], score=100)))
    middle = role_fixture(1005, "达芙蒂尔")
    missing = replace(role_fixture(1006, "阿德勒"), slots=())
    zero = role_fixture(1007, "黑羽")
    zero = replace(zero, slots=(replace(zero.slots[0], score=0),))
    roles = (missing, zero, middle, high)
    dialog = picker(roles, (1004, 1005, 1006, 1007), {1004: high.slots[1].reference})
    assert dialog.selected_character_ids() == (1004, 1005, 1007, 1006)
    assert dialog.selected_slots()[1004] == high.slots[1].reference
    dialog.search_edit.setText("ahq")
    dialog.search_edit.clear()
    assert dialog.selected_character_ids() == (1004, 1005, 1007, 1006)
    dialog.reject()


def test_role_sort_has_stable_ties_and_does_not_treat_missing_scores_as_zero():
    from dataclasses import replace
    from src.features.toolbox.rewind_role_selection import rewind_role_sort_key

    lower_id = role_fixture(1004, "同名角色")
    higher_id = role_fixture(1005, "同名角色")
    unknown = role_fixture(1006, "无评分")
    unknown = replace(unknown, slots=(replace(unknown.slots[0], score=None),))
    invalid = role_fixture(1007, "异常评分")
    invalid = replace(invalid, slots=(replace(invalid.slots[0], score=float("nan")),))
    zero = role_fixture(1008, "零分")
    zero = replace(zero, slots=(replace(zero.slots[0], score=0),))
    ordered = sorted((higher_id, unknown, invalid, zero, lower_id), key=rewind_role_sort_key)
    assert [role.character_id for role in ordered[:3]] == [1004, 1005, 1008]
    assert {role.character_id for role in ordered[3:]} == {1006, 1007}


@pytest.mark.parametrize("theme", ("dark", "black", "light"))
@pytest.mark.parametrize("score", (274.25, 203.51, 117.8))
def test_numeric_score_and_rating_share_text_color(application, theme, score):
    from dataclasses import replace
    from PySide6.QtGui import QPalette

    previous_theme = application.property("nte_effective_theme")
    application.setProperty("nte_effective_theme", theme)
    dialog = None
    try:
        role = role_fixture()
        role = replace(role, slots=(replace(role.slots[0], score=score),))
        dialog = picker((role,))
        value = dialog.findChild(QLabel, "rewindRoleCalculationScore")
        grade = dialog.findChild(QLabel, "rewindRoleGrade")
        value.ensurePolished()
        grade.ensurePolished()
        assert grade.text()
        assert value.palette().color(QPalette.WindowText) == grade.palette().color(QPalette.WindowText)
    finally:
        if dialog is not None:
            dialog.reject()
        application.setProperty("nte_effective_theme", previous_theme)


def test_multiple_slots_prompt_and_cancel_preserves_unchecked_state(application, monkeypatch):
    from src.features.toolbox import rewind_role_picker
    role = role_fixture()
    dialog = picker((role,))
    previous = dialog.selected_slots()
    monkeypatch.setattr(rewind_role_picker.RewindSlotPicker, "exec", lambda self: QDialog.Rejected)
    card = dialog.findChild(QToolButton, "rewindRoleSelectionCard")
    card.click()
    assert dialog.selected_character_ids() == ()
    assert dialog.selected_slots() == previous
    dialog.reject()


def test_confirm_slot_and_switch_do_not_require_deselecting_role(application, monkeypatch):
    from src.features.toolbox import rewind_role_picker
    role = role_fixture()
    dialog = picker((role,))
    monkeypatch.setattr(rewind_role_picker.RewindSlotPicker, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(rewind_role_picker.RewindSlotPicker, "selected_reference", lambda self: role.slots[1].reference)
    card = dialog.findChild(QToolButton, "rewindRoleSelectionCard")
    card.click()
    assert dialog.selected_character_ids() == (1004,)
    assert card.property("rewindCalculationScore") == 230
    monkeypatch.setattr(rewind_role_picker.RewindSlotPicker, "selected_reference", lambda self: role.slots[0].reference)
    dialog.findChild(QPushButton, "rewindSwitchSlot").click()
    assert dialog.selected_character_ids() == (1004,)
    assert card.property("rewindCalculationScore") == 260
    assert "260" in card.findChild(QLabel, "rewindRoleCalculationScore").text()
    assert "很长的主力槽位名称" in card.toolTip()
    dialog.reject()


def test_single_slot_click_avoids_popup_and_filtered_select_all_preserves_hidden_selection(application, monkeypatch):
    from dataclasses import replace
    role = role_fixture()
    role = replace(role, slots=role.slots[:1])
    other = role_fixture(1005, "达芙蒂尔")
    dialog = picker((role, other), (1005,))
    monkeypatch.setattr(RewindSlotPicker, "exec", lambda self: pytest.fail("单槽位和全选不应打开选择窗"))
    cards = {key: card for card, key, _ in dialog._cards}
    cards[1004].click()
    assert set(dialog.selected_character_ids()) == {1004, 1005}
    dialog._apply_filter("ahq")
    dialog._set_visible_checked(False)
    assert dialog.selected_character_ids() == (1005,)
    dialog._set_visible_checked(True)
    assert set(dialog.selected_character_ids()) == {1004, 1005}
    assert dialog.selected_slots()[1005] == other.slots[0].reference
    dialog.reject()


class UiService:
    asset_root = None

    def __init__(self):
        self.saved = {"saved_rewind_shape_ids": ["original"], "unrelated_setting": 1}

    def load_preferences(self):
        return dict(self.saved)

    def save_preferences(self, value, **kwargs):
        self.saved = dict(value)


def recommendation_dialog(monkeypatch, **kwargs):
    from src.features.toolbox import page
    monkeypatch.setattr(page.QTimer, "singleShot", lambda *_: None)
    service = UiService()
    # Not a real shape: avoid static I/O and keep only the persistent fact under test.
    service.saved["saved_rewind_shape_ids"] = []
    dialog = page._RewindRecommendationDialog(service, None, **kwargs)
    role = role_fixture()
    dialog._on_roles_loaded((role,))
    return dialog, service, role


def test_recommendation_has_no_manual_catalog_refresh_button(application, monkeypatch):
    dialog, _, role = recommendation_dialog(monkeypatch)
    assert dialog.findChild(QPushButton, "rewindRefreshCatalog") is None
    assert dialog._selected_slots[role.character_id] == role.slots[0].reference
    dialog.reject()


def test_overall_cancel_keeps_shared_mapping_and_confirm_updates_both_summaries(application, monkeypatch):
    dialog, service, role = recommendation_dialog(monkeypatch)
    dialog._target_character_ids = dialog._main_character_ids = {1004}
    before = dict(dialog._selected_slots)

    def simulate_draft(popup):
        popup._slots[1004] = role.slots[1].reference
        return QDialog.Rejected

    monkeypatch.setattr(_RoleSelectionDialog, "exec", simulate_draft)
    dialog._choose_target_roles()
    assert dialog._selected_slots == before
    assert "selected_slots" not in service.saved

    def confirm(popup):
        popup._slots[1004] = role.slots[1].reference
        return QDialog.Accepted

    monkeypatch.setattr(_RoleSelectionDialog, "exec", confirm)
    dialog._choose_main_roles()
    assert dialog._selected_slots[1004] == role.slots[1].reference
    assert dialog._target_summary.text() == role.name
    assert dialog._main_summary.text() == role.name
    assert dialog._target_summary.toolTip() == role.name
    assert dialog._main_summary.toolTip() == role.name
    assert service.saved["selected_slots"]["1004"] == 2
    dialog.reject()


def test_changed_input_disables_old_result_save_and_ignores_old_callback(application, monkeypatch):
    from src.services.rewind_shape_recommendation_service import RewindShapeAnalysis
    dialog, service, role = recommendation_dialog(monkeypatch)
    result = RewindShapeAnalysis(9, "nte_core", 1, 8, ())
    old_token = object()
    dialog._analysis_token = old_token
    dialog._generated_analysis = result
    dialog._target_character_ids = {1004}
    dialog._selected_slots[1004] = role.slots[1].reference
    dialog._save_preferences()
    assert dialog._recommendation_invalidated
    assert not dialog._save_plan_button.isEnabled()
    dialog._on_analysis_ready(old_token, result)
    assert dialog._recommendation_invalidated
    dialog.reject()


def test_account_change_or_close_discards_read_results_and_never_saves(application, monkeypatch):
    generation = [1]
    dialog, service, _ = recommendation_dialog(monkeypatch, operation_generation=lambda: generation[0])
    before = dict(service.saved)
    generation[0] = 2
    assert dialog._save_preferences() is False
    assert service.saved == before
    dialog.reject()
    dialog._load_roles_async()  # A queued initial callback after close is harmless.
    dialog._on_roles_loaded((role_fixture(2000, "过期"),))
    assert set(dialog._role_names) == {1004}


def test_slot_popup_keeps_incomplete_options_visible_and_keyboard_selectable(application):
    from dataclasses import replace
    role = role_fixture()
    role = replace(role, slots=(role.slots[0], replace(role.slots[1], state="incomplete", reason="驱动未装满")))
    popup = RewindSlotPicker(None, role, role.slots[0].reference)
    buttons = {button.property("slotId"): button for button in popup.group.buttons()}
    assert buttons[2].isEnabled()
    assert "未装满" in buttons[2].toolTip()
    buttons[2].setFocus()
    buttons[2].click()
    assert popup.selected_reference() == role.slots[1].reference
    popup.reject()


def test_single_slot_can_correct_an_invalid_saved_choice_without_a_popup(application, monkeypatch):
    from dataclasses import replace
    role = role_fixture()
    role = replace(role, slots=role.slots[:1])
    dialog = picker((role,), slots={1004: None})
    monkeypatch.setattr(RewindSlotPicker, "exec", lambda self: pytest.fail("唯一槽位不应弹窗"))
    dialog.findChild(QToolButton, "rewindRoleSelectionCard").click()
    assert dialog.selected_slots()[1004] == role.slots[0].reference
    dialog.reject()


def test_unselected_defaults_are_not_saved_as_explicit_choices_and_clearing_starts_manual_draft(application, monkeypatch):
    dialog, service, _ = recommendation_dialog(monkeypatch)
    dialog._save_preferences()
    assert service.saved["selected_slots"] == {}
    dialog._generated_analysis = object()
    dialog._recommendation_invalidated = True
    dialog._clear_rewind_slots()
    assert dialog._generated_analysis is None
    assert not dialog._recommendation_invalidated
    assert service.saved["saved_rewind_shape_ids"] == []
    dialog.reject()


def test_card_slot_entry_keeps_real_slot_name_even_when_equal_to_role_name(application):
    from dataclasses import replace
    from src.features.toolbox.rewind_role_selection import rewind_role_card_presentation
    role = role_fixture()
    role = replace(role, slots=(replace(role.slots[0], slot_name=role.name), role.slots[1]))
    dialog = picker((role,), (1004,))
    entry = dialog.findChild(QPushButton, "rewindSwitchSlot")
    assert rewind_role_card_presentation(role, role.slots[0].reference).slot_text == role.name
    assert role.name in entry.toolTip()
    assert dialog.selected_slots()[1004] == role.slots[0].reference
    dialog.reject()


def test_in_card_slot_entry_preserves_selection_and_can_view_incomplete_slots(application, monkeypatch):
    from dataclasses import replace
    role = role_fixture()
    role = replace(role, slots=(replace(role.slots[0], state="incomplete", reason="驱动未装满"),))
    dialog = picker((role,), (1004,))
    entry = dialog.findChild(QPushButton, "rewindSwitchSlot")
    assert entry.isEnabled()
    assert "未装满" in entry.toolTip()
    monkeypatch.setattr(RewindSlotPicker, "exec", lambda self: QDialog.Rejected)
    entry.click()
    assert dialog.selected_character_ids() == (1004,)
    dialog.reject()


def test_missing_slot_entry_is_disabled_without_disabling_role_selection(application):
    role = RewindTargetRole(9001, "自建角色", None, is_custom=True)
    dialog = picker((role,))
    card = dialog.findChild(QToolButton, "rewindRoleSelectionCard")
    entry = dialog.findChild(QPushButton, "rewindSwitchSlot")
    assert not entry.isEnabled()
    assert "无可用配装" in entry.text()
    assert "暂无方案" in card.findChild(QLabel, "rewindRoleCalculationScore").text()
    card.click()
    assert dialog.selected_character_ids() == (9001,)
    dialog.reject()


def test_bulk_selection_and_keyboard_toggle_keep_accessible_check_state_in_sync(application):
    from dataclasses import replace
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    role = role_fixture()
    role = replace(role, slots=role.slots[:1])
    dialog = picker((role,))
    card = dialog.findChild(QToolButton, "rewindRoleSelectionCard")
    mark = card.findChild(QLabel, "rewindRoleCheck")
    dialog._set_visible_checked(True)
    assert card.isChecked()
    assert mark.accessibleName() == "已选"
    dialog._set_visible_checked(False)
    assert mark.accessibleName() == "未选"
    QTest.keyClick(card, Qt.Key_Space)
    assert dialog.selected_character_ids() == (1004,)
    assert mark.accessibleName() == "已选"
    dialog.reject()
