# 首次启动时询问界面语言，必须在导入界面模块之前完成。
"""First-launch language chooser.

The language is activated at import time so that module-level ``tr()`` resolves
against the right catalogue, which means the question has to be answered before
any UI module is imported. This module therefore depends only on PySide6 and the
preference service — importing a feature module here would defeat the ordering it
exists to protect.

The dialog is bilingual on purpose: the reader has not chosen a language yet, so
neither one can be assumed.
"""

from __future__ import annotations

from src.i18n import LANGUAGE_LABELS, LANGUAGES, SOURCE_LANGUAGE


_PROMPT_TITLE = "选择语言 / Choose language"
_PROMPT_BODY = "请选择界面语言。\nChoose your interface language."
_PROMPT_FOOTER = "之后可在「设置」中更改。\nYou can change this later in Settings."


def prompt_for_language(theme: str | None = None) -> str | None:
    """Ask which language to use and return it, or ``None`` if Qt is unavailable.

    ``theme`` styles the dialog so first launch does not flash an unthemed
    window before the main one appears.
    """
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QDialog,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QVBoxLayout,
        )
    except ImportError:
        return None

    app = QApplication.instance()
    if app is None:
        if hasattr(Qt, "AA_DontUseNativeDialogs"):
            QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, True)
        app = QApplication([])
        app.setStyle("Fusion")
    if theme is not None:
        try:
            from src.app.theme import apply_app_theme

            apply_app_theme(app, theme)
        except Exception:
            # Styling is cosmetic; never block first launch on it.
            pass

    dialog = QDialog()
    dialog.setWindowTitle(_PROMPT_TITLE)
    dialog.setModal(True)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(14)

    body = QLabel(_PROMPT_BODY)
    body.setAlignment(Qt.AlignCenter)
    layout.addWidget(body)

    chosen: dict[str, str] = {}
    buttons = QHBoxLayout()
    buttons.setSpacing(10)
    for language in LANGUAGES:
        button = QPushButton(LANGUAGE_LABELS.get(language, language))
        button.setMinimumWidth(150)
        button.setMinimumHeight(38)
        button.setCursor(Qt.PointingHandCursor)

        def _choose(_checked: bool = False, value: str = language) -> None:
            chosen["language"] = value
            dialog.accept()

        button.clicked.connect(_choose)
        buttons.addWidget(button)
    layout.addLayout(buttons)

    footer = QLabel(_PROMPT_FOOTER)
    footer.setAlignment(Qt.AlignCenter)
    footer.setEnabled(False)
    layout.addWidget(footer)

    dialog.exec()
    # Closing the window is a deliberate answer too: keep the source language and
    # record it, so the question is not repeated on every launch.
    return chosen.get("language", SOURCE_LANGUAGE)


def ensure_language_choice(settings, theme: str | None = None) -> str:
    """Record a language choice on first launch and return the active language.

    A stored choice is returned untouched, so the dialog is shown exactly once.
    """
    if settings.has_stored_choice():
        return settings.load()
    language = prompt_for_language(theme)
    if language is None:
        return settings.load()
    return settings.save(language)
