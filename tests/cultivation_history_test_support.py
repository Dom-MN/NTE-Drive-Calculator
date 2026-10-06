# 将新增养成历史的 pytest 行为测试显式接入项目 unittest 质量入口。
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


def module_load_tests(module_name: str, module_file: str):
    """仅桥接调用模块；子进程用 pytest 执行真实函数与标准 fixtures，不伪造发现成功。"""
    test_file = Path(module_file).resolve()
    root = test_file.parent.parent

    def run_test(case):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-rA", str(test_file)],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=180,
        )
        case.assertEqual(result.returncode, 0, result.stdout)
        if result.stdout:
            print(result.stdout, end="")

    case_type = type("CultivationModuleRegression", (unittest.TestCase,), {
        "__module__": module_name, "runTest": run_test, "__test__": False,
    })

    def load_tests(_loader, _tests, _pattern):
        return unittest.TestSuite([case_type()])

    return load_tests
