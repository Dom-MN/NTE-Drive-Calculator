# 验证保存成功与使用教程中的支持和求助入口。
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from src.app.constants import SUPPORT_US_URL
from src.app.theme import theme_color
from src.features.allocation.execute_page import _build_result_card
from src.features.allocation.runner import AllocationController
from src.features.allocation.save_workflow import show_allocation_save_success
from src.features.onboarding.guide import OnboardingGuide
from src.features.scanning.controller import ScanningController


class SupportEntryPointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_saved_plan_success_contains_clickable_support_link(self) -> None:
        captured = []

        def inspect(dialog):
            captured.append(dialog)
            return QDialog.Accepted

        with patch.object(QDialog, "exec", inspect):
            show_allocation_save_success(None, 2)

        dialog = captured[0]
        link = dialog.findChild(QLabel, "allocationSaveSupportLink")
        self.assertIsNotNone(link)
        self.assertIn("觉得计算器好用？支持我们吧", link.text())
        self.assertIn(SUPPORT_US_URL, link.text())
        self.assertTrue(link.openExternalLinks())
        headline = dialog.findChild(QLabel, "allocationSaveSuccessHeadline")
        self.assertEqual("已保存 2 个方案", headline.text())
        self.assertEqual("✓", dialog.findChild(QLabel, "allocationSaveSuccessMark").text())
        self.assertLessEqual(dialog.width(), 400)
        self.assertGreaterEqual(dialog.layout().itemAt(2).spacerItem().sizeHint().height(), 12)
        dialog.deleteLater()

    def test_result_header_matches_role_badge_and_clear_is_separate(self) -> None:
        page = QWidget()
        cleared = []
        owner = SimpleNamespace(
            _save_alloc=lambda: None,
            clear_calculation=lambda: cleared.append(True),
        )
        _build_result_card(owner, QVBoxLayout(page))
        self.assertEqual("allocationSaveButton", owner.btn_save.objectName())
        self.assertEqual("保存配装", owner.btn_save.text())
        self.assertEqual("清空计算", owner.btn_clear_result.text())
        title = owner.result_card.findChild(QLabel, "allocationResultTitle")
        self.assertEqual(title.size(), owner.btn_save.size())
        self.assertEqual(title.size(), owner.btn_clear_result.size())
        for button, color in ((owner.btn_clear_result, "#f85149"), (owner.btn_save, "#3fb950")):
            expected = theme_color(color)
            self.assertIn(f"color:{expected}", button.styleSheet())
            self.assertIn(f"border:1px solid {expected}", button.styleSheet())
            self.assertIn("background:rgba(", button.styleSheet())
        owner.btn_clear_result.click()
        self.assertEqual([True], cleared)
        self.assertEqual("计算结果", title.text())
        badge_color = theme_color("#4dd0e1")
        self.assertIn(f"color:{badge_color}", title.styleSheet())
        self.assertIn(f"border:1px solid {badge_color}", title.styleSheet())
        page.deleteLater()

    def test_clear_preview_drops_frozen_result_without_touching_inputs(self) -> None:
        cleared = []
        owner = SimpleNamespace(
            final_plan={"role": {}}, allocation_plan_diff={"role": {}},
            _allocation_dirty=True, _pending_allocation_snapshot_id=7,
            _pending_allocation_static_identity=("dataset",),
            _allocation_lock_snapshot=object(), _selected_locked_role_names=frozenset({"role"}),
            _allocation_custom_weapons={"role": "fork"}, _pending_sel=["role"],
            _equipment_presentation=SimpleNamespace(clear=lambda: cleared.append(True)),
        )
        AllocationController.clear_preview(owner)
        self.assertEqual({}, owner.final_plan)
        self.assertIsNone(owner._pending_allocation_snapshot_id)
        self.assertFalse(owner._allocation_dirty)
        self.assertEqual(["role"], owner._pending_sel)
        self.assertEqual([True], cleared)

    def test_clear_calculation_requires_confirmation_and_only_discards_preview(self) -> None:
        cleared = []
        owner = SimpleNamespace(
            dialog_parent=QWidget(),
            is_running=lambda: False,
            _allocation_controller=SimpleNamespace(clear_preview=lambda: cleared.append(True)),
        )
        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            ScanningController.clear_calculation(owner)
        self.assertEqual([], cleared)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            ScanningController.clear_calculation(owner)
        self.assertEqual([True], cleared)
        owner.dialog_parent.deleteLater()

    def test_tutorial_help_uses_the_injected_group_chat_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            guide_dir = root / "guide"
            guide_dir.mkdir()
            self.assertTrue(QImage(2, 2, QImage.Format_RGB32).save(str(guide_dir / "1.png")))
            context = SimpleNamespace(
                paths=SimpleNamespace(template_dir=root),
                account=SimpleNamespace(user_config_dir=root / "account"),
            )
            parent = QWidget()
            opened = []
            guide = OnboardingGuide(
                app_context=context, parent=parent,
                on_help=lambda: opened.append("group_chat"),
            )

            def click_help(dialog):
                help_button = dialog.findChild(QPushButton, "onboardingHelpButton")
                confirm = dialog.findChild(QPushButton, "onboardingConfirmButton")
                self.assertIsNotNone(help_button)
                self.assertIsNotNone(confirm)
                self.assertEqual("确定", confirm.text())
                actions = dialog.layout().itemAt(dialog.layout().count() - 1).layout()
                self.assertIs(actions.itemAt(1).widget(), help_button)
                self.assertIs(actions.itemAt(2).widget(), confirm)
                self.assertEqual(help_button.styleSheet(), confirm.styleSheet())
                help_button.click()
                self.assertEqual([], opened)
                return QDialog.Accepted

            with patch.object(QDialog, "exec", click_help):
                guide.show()
            self.app.processEvents()
            self.assertEqual(["group_chat"], opened)
            parent.deleteLater()
