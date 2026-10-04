# 确认能进入同步状态行的每条中文提示都有英文译文，防止英文界面露出中文。
"""Every Chinese string that can reach the game-data sync status line is translated.

The status line renders ``tr(state.message)``, and that message is fed from
three places no coverage scan follows:

* literals published through ``InventorySyncService._publish``;
* a native status dict's ``"message"`` / ``"native_character_error"`` value,
  which the runtime republishes;
* the text of any ``NativeSnapshotPending``, which the native lease turns into
  that dict's message with ``str(error)``.

The exceptions stay Chinese because they are also logged; only the catalogue
needs the key. A new message anywhere on these paths fails here rather than
showing up untranslated in English.
"""

from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

NTE_TEST_TIER = "core"
ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "locales"
CJK = re.compile(r"[一-鿿]")

STATUS_MODULES = (
    "src/services/inventory_sync_runtime.py",
    "src/services/inventory_sync_service.py",
    "src/services/native_inventory_lease.py",
)
STATUS_KEYS = {"message", "native_character_error"}
PENDING_EXCEPTION = "NativeSnapshotPending"


def _chinese_constants(node: ast.AST) -> list[str]:
    return [
        child.value for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
        and CJK.search(child.value)
    ]


def _messages_reaching_status() -> dict[str, str]:
    found: dict[str, str] = {}
    for relative in STATUS_MODULES:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "_publish"
                    and len(node.args) >= 2):
                for text in _chinese_constants(node.args[1]):
                    found.setdefault(text, f"{relative}:{node.lineno}")
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value in STATUS_KEYS:
                        for text in _chinese_constants(value):
                            found.setdefault(text, f"{relative}:{node.lineno}")
    for path in sorted((ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and getattr(node.func, "id", "") == PENDING_EXCEPTION and node.args):
                for text in _chinese_constants(node.args[0]):
                    found.setdefault(text, f"{path.relative_to(ROOT).as_posix()}:{node.lineno}")
    return found


class SyncStatusMessagesAreTranslatedTests(unittest.TestCase):
    def test_every_status_message_has_an_english_translation(self) -> None:
        catalog = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
        messages = _messages_reaching_status()
        self.assertGreater(len(messages), 10, "the scan no longer finds the status paths")
        missing = sorted(
            f"{where}  {text}" for text, where in messages.items() if text not in catalog
        )
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
