# 在导入任何界面模块之前激活界面语言，必要时先询问首次启动的语言选择。
"""Activate the interface language before any UI module is imported.

Module-level ``tr()`` resolves against whichever catalogue is active at import
time, so the language must be settled first. Keeping that here rather than in
``src/ui/app.py`` isolates the ordering-critical step and imports no feature
module, which is what makes the ordering safe.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.i18n import set_language
from src.services.global_language_settings_service import GlobalLanguageSettingsService


def activate_language(settings_path: str | Path) -> GlobalLanguageSettingsService:
    """Activate the interface language and return the settings service.

    ``NTE_UI_LANGUAGE`` pins the language for tests and the command line so the
    result never depends on the local preference file. The first-launch chooser
    only runs for a real GUI launch: tests import ``src.ui.app`` too, and a modal
    dialog there would hang the suite.
    """
    settings = GlobalLanguageSettingsService(settings_path)
    forced = os.environ.get("NTE_UI_LANGUAGE")
    if not forced and os.environ.get("NTE_GUI_LAUNCH"):
        from src.services.global_theme_settings_service import GlobalThemeSettingsService
        from src.ui.first_run_language import ensure_language_choice

        ensure_language_choice(
            settings,
            GlobalThemeSettingsService(settings_path).load(),
        )
    set_language(forced or settings.load())
    return settings
