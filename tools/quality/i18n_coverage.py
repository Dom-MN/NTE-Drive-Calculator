# 报告尚未本地化的中文界面文案，用于每次同步上游后的检查。
"""Report Chinese UI strings that never reach the translation layer.

The test suite fails when a ``tr()`` key is missing from ``locales/en.json``. It
cannot fail on a string that was never wrapped at all, so an upstream merge can
add hardcoded Chinese that silently renders untranslated in English. This tool
closes that gap: run it after every upstream sync.

Two scopes are reported separately because they need different fixes:

* ``ui``       - text handed to a widget. Wrap it in ``tr()``.
* ``service``  - text raised or returned by ``src/services`` and ``src/optimizer``.
                 Wrap it only when it can reach a dialog; pure argument contracts
                 stay Chinese.

Known blind spot: text assembled through a helper before reaching a widget is
invisible to static analysis. A clean report is not proof of full coverage.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CJK = re.compile(r"[一-鿿]")

# Calls whose argument is shown to a person.
UI_SINKS = frozenset({
    "QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QGroupBox", "QAction",
    "QToolButton", "setText", "setWindowTitle", "setToolTip", "setPlaceholderText",
    "setTitle", "setTabText", "addTab", "setStatusTip", "addItem", "information",
    "warning", "question", "critical", "about", "setItemText", "setHeaderLabels",
    "setLabelText", "addAction",
})
# Logging text stays Chinese by repository convention.
LOG_CALLS = frozenset({
    "info", "warning", "error", "debug", "exception", "log_event", "critical",
    "success", "operation_scope",
})
LOG_RECEIVERS = frozenset({"logger", "log", "_logger"})
TRANSLATORS = frozenset({"tr", "display_term", "display_text", "display_localized"})

UI_ROOTS = ("src/features", "src/ui")
SERVICE_ROOTS = ("src/services", "src/optimizer", "src/integrations", "src/storage")


def _translated_constants(node: ast.AST) -> set[int]:
    """Ids of constants already inside a translation call."""
    covered: set[int] = set()
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call) and getattr(inner.func, "id", "") in TRANSLATORS:
            for constant in ast.walk(inner):
                if isinstance(constant, ast.Constant):
                    covered.add(id(constant))
    return covered


def _is_logging(call: ast.Call) -> bool:
    name = getattr(call.func, "attr", "") or getattr(call.func, "id", "")
    if name not in LOG_CALLS:
        return False
    receiver = getattr(getattr(call.func, "value", None), "id", "")
    return name == "operation_scope" or receiver in LOG_RECEIVERS or not receiver


def scan_ui(path: Path) -> list[tuple[int, str]]:
    """Chinese literals that reach a widget without passing through tr()."""
    findings: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
        if name not in UI_SINKS or _is_logging(node):
            continue
        covered = _translated_constants(node)
        for argument in node.args:
            for constant in ast.walk(argument):
                if (
                    isinstance(constant, ast.Constant)
                    and isinstance(constant.value, str)
                    and id(constant) not in covered
                    and CJK.search(constant.value)
                ):
                    findings.append((constant.lineno, constant.value))
    return findings


def scan_service(path: Path) -> list[tuple[int, str]]:
    """Chinese literals raised by a service, which may surface in a dialog."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    covered: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            if name in TRANSLATORS or _is_logging(node):
                covered |= {
                    id(c) for c in ast.walk(node) if isinstance(c, ast.Constant)
                }
        if isinstance(node, ast.Dict):
            covered |= {id(k) for k in node.keys if isinstance(k, ast.Constant)}
        if isinstance(node, ast.Compare):
            covered |= {
                id(c) for c in [node.left, *node.comparators]
                if isinstance(c, ast.Constant)
            }
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if ast.get_docstring(node, clean=False):
                covered.add(id(node.body[0].value))

    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise):
            continue
        for constant in ast.walk(node):
            if (
                isinstance(constant, ast.Constant)
                and isinstance(constant.value, str)
                and id(constant) not in covered
                and CJK.search(constant.value)
            ):
                findings.append((constant.lineno, constant.value))
    return findings


def collect(roots: tuple[str, ...], scanner) -> dict[str, list[tuple[int, str]]]:
    results: dict[str, list[tuple[int, str]]] = {}
    for root in roots:
        for path in sorted((ROOT / root).rglob("*.py")):
            hits = scanner(path)
            if hits:
                results[path.relative_to(ROOT).as_posix()] = hits
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--scope", choices=("ui", "service", "all"), default="ui",
        help="ui（默认，硬门禁）、service（人工判断）或 all",
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    parser.add_argument(
        "--strict", action="store_true",
        help="service 结果也计入退出码；默认只有 ui 会让命令失败",
    )
    arguments = parser.parse_args()

    report: dict[str, dict[str, list[tuple[int, str]]]] = {}
    if arguments.scope in ("ui", "all"):
        report["ui"] = collect(UI_ROOTS, scan_ui)
    if arguments.scope in ("service", "all"):
        report["service"] = collect(SERVICE_ROOTS, scan_service)

    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for scope, files in report.items():
            count = sum(len(v) for v in files.values())
            label = "界面文案（应当 tr()）" if scope == "ui" else "服务异常（可能进入弹窗）"
            print(f"[{scope}] {label}: {count} 条，{len(files)} 个文件")
            for name, hits in files.items():
                for lineno, text in hits:
                    print(f"  {name}:{lineno}  {text[:70]}")
        if not any(report.values()):
            print("[OK] 未发现遗漏的中文界面文案")
        print()
        print("提示：经由辅助函数拼接后才写入控件的文案，静态分析看不到；结果为 0 不等于全覆盖。")

    failing = len(report.get("ui", {}))
    if arguments.strict:
        failing += len(report.get("service", {}))
    return 1 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
