# 全局异常兜底：记录未捕获异常并提示用户，避免闪退。
"""Last-resort handler for uncaught exceptions.

Split out of ``src/ui/app.py`` so the composition root stays within the review
threshold. Importing this module has no side effects; ``run_gui`` installs the
handler explicitly.
"""

from __future__ import annotations

from src.i18n import tr
from src.utils.logger import logger


def global_exception_handler(exc_type, exc_value, exc_tb) -> None:
    """Log an uncaught exception and show it, instead of exiting silently."""
    import traceback as tb

    error_msg = "".join(tb.format_exception(exc_type, exc_value, exc_tb))
    logger.error(f"未捕获异常:\n{error_msg}")
    try:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(
            None, tr("程序异常"), tr("发生未捕获的异常:\n\n{error}", error=error_msg[:1000])
        )
    except Exception as exc:
        logger.error(f"显示全局异常弹窗失败: {exc}")
