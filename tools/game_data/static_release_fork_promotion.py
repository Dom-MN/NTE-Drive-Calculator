# 隔离弧盘重投影候选的基线配置与晋升前复核。
"""Fork-specific static release gate, kept outside the general promoter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .fork_reprojection_provenance import (
        PROVENANCE_FILENAME as FORK_REPROJECTION_PROVENANCE_FILENAME,
        validate_fork_reprojection_provenance,
    )
except ImportError:
    from fork_reprojection_provenance import (
        PROVENANCE_FILENAME as FORK_REPROJECTION_PROVENANCE_FILENAME,
        validate_fork_reprojection_provenance,
    )


def validate_fork_candidate(
    database_path: Path, candidate_dir: Path, config: dict[str, Any],
) -> dict[str, Any]:
    baseline_database = config.get("baseline_database_path")
    baseline_manifest = config.get("baseline_manifest_path")
    if not isinstance(baseline_database, str) or not isinstance(baseline_manifest, str):
        raise ValueError("弧盘重投影缺少基线库和清单配置")
    return validate_fork_reprojection_provenance(
        candidate_database=database_path,
        provenance_path=candidate_dir / FORK_REPROJECTION_PROVENANCE_FILENAME,
        baseline_database=Path(baseline_database).expanduser().resolve(),
        baseline_manifest=Path(baseline_manifest).expanduser().resolve(),
    )


def check_fork_baseline(candidate_dir: Path, target_dir: Path) -> None:
    provenance_path = candidate_dir / FORK_REPROJECTION_PROVENANCE_FILENAME
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    target = target_dir / "game_static.sqlite3"
    if not target.is_file():
        raise ValueError("正式静态库不存在，弧盘候选不能晋升")
    digest = hashlib.sha256()
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().upper() != provenance.get("baseline_database_sha256"):
        raise ValueError("正式库已变化，弧盘候选必须重新生成")
