# 定位和核对独立 Rust 分析组件，保持采集 Core 路径不变。
"""Resolve the optional independently packaged analysis executable."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
from pathlib import Path

from src.integrations.bundled_resources import bundled_root
from src.integrations.nte_analysis_core import (
    SUPPORTED_ENGINE_VERSIONS, NativeAnalysisError, NteAnalysisCoreClient,
)


def create_bundled_analysis_client(
    *, static_database_path: Path | None,
    cancelled: Callable[[], bool] | None = None,
) -> NteAnalysisCoreClient | None:
    """Bind once to the packaged engine; a broken installation is an error."""
    if static_database_path is None:
        return None
    root = bundled_root()
    locations = (
        (root / "nte-analysis-core.exe", root / "analysis-core-meta/component.json"),
        (root / "third_party/analysis-core/bin/nte-analysis-core.exe",
         root / "third_party/analysis-core/component.json"),
    )
    for executable, manifest_path in locations:
        if not executable.exists() and not manifest_path.exists():
            continue
        if not executable.is_file() or not manifest_path.is_file():
            raise NativeAnalysisError("独立分析组件不完整，请重新部署")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                manifest["engine"] != "nte-analysis-core"
                or manifest["engine_version"] not in SUPPORTED_ENGINE_VERSIONS
                or manifest["sha256"] != hashlib.sha256(executable.read_bytes()).hexdigest()
            ):
                raise NativeAnalysisError("独立分析组件版本或哈希不匹配")
            capabilities = manifest.get("capabilities", [])
            if not isinstance(capabilities, list) or any(not isinstance(item, str) for item in capabilities):
                raise NativeAnalysisError("独立分析组件能力清单无效")
            static_manifest = json.loads(
                (Path(static_database_path).parent / "manifest.json").read_text(encoding="utf-8")
            )
            dataset_version = str(static_manifest["database"]["dataset_id"])
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise NativeAnalysisError("独立分析组件或静态数据集清单无效") from error
        return NteAnalysisCoreClient(
            executable, dataset_version=dataset_version, cancelled=cancelled,
            engine_version=manifest["engine_version"],
            capabilities=frozenset(capabilities),
        )
    return None
