# 按候选实际消费的来源核对解包失败清单，禁止把残缺 JSON 当作完整战斗证据晋升。
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path, PurePosixPath


def reviewed_blueprint_gaps(config: dict) -> dict[str, dict]:
    """例外绑定具体版本的文件哈希，仅允许隔离蓝图，不接受全局忽略开关。"""
    result = {}
    entries = config.get("reviewed_blueprint_gaps", [])
    if not isinstance(entries, list):
        raise ValueError("蓝图缺口审查必须是数组")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("蓝图缺口审查格式错误")
        path = entry.get("path", "")
        if not isinstance(path, str) or not path.startswith("Blueprints/") or not path.endswith(".json"):
            raise ValueError("缺口只允许确切的 Blueprint JSON 路径")
        if "\\" in path or ":" in path or ".." in PurePosixPath(path).parts:
            raise ValueError("蓝图缺口路径越界")
        digest, reason = entry.get("sha256", ""), entry.get("reason", "")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ValueError("蓝图缺口必须绑定来源 SHA-256")
        if not isinstance(reason, str) or not reason.strip() or path.casefold() in result:
            raise ValueError("蓝图缺口审查缺少原因或路径重复")
        result[path.casefold()] = {"path": path, "sha256": digest.lower(), "reason": reason,
                                   "status": "unknown", "disposition": "excluded_from_projection"}
    return result


def validate_export_quality(config: dict, content_root: Path, source_files,
                            database_path: Path | None = None) -> dict | None:
    reviewed = reviewed_blueprint_gaps(config)
    report_path = config.get("export_quality_report")
    if report_path is None:
        if reviewed:
            raise ValueError("蓝图缺口缺少解包审计报告")
        return None
    expected_hash = config.get("export_quality_report_sha256")
    if not isinstance(report_path, str) or not isinstance(expected_hash, str):
        raise ValueError("解包审计须同时登记报告路径和 SHA-256")
    raw = Path(report_path).read_bytes()
    if hashlib.sha256(raw).hexdigest().casefold() != expected_hash.casefold():
        raise ValueError("解包审计报告 SHA-256 不一致")
    report = json.loads(raw)
    if not isinstance(report, dict) or not isinstance(report.get("output"), str):
        raise ValueError("解包审计缺少输出目录身份")
    if (Path(report["output"]) / "HT" / "Content").resolve() != content_root.resolve():
        raise ValueError("解包审计与候选 Content 来源不一致")
    failures = report.get("affected_paths")
    file_errors = report.get("file_validation_errors")
    if not isinstance(failures, list) or not isinstance(file_errors, list):
        raise ValueError("解包审计缺少完整失败清单")
    if report.get("source_packages_unchanged") is not True:
        raise ValueError("解包期间源包稳定性未确认")

    def normalize(value: str, *, asset: bool = False) -> str:
        if not isinstance(value, str):
            raise ValueError("解包审计来源路径不是字符串")
        value = value.split("#", 1)[0].replace("\\", "/")
        value = value.removeprefix("combat_blueprint/").removeprefix("HT/Content/")
        path = PurePosixPath(value)
        if not value or path.is_absolute() or ":" in value or ".." in path.parts:
            raise ValueError("解包审计来源路径越界")
        if asset:
            if path.suffix.lower() != ".uasset":
                raise ValueError("解包失败资源后缀未支持")
            path = path.with_suffix(".json")
        return path.as_posix().casefold()

    consumed_hashes = {normalize(relative): digest.lower() for relative, digest in source_files}
    consumed = set(consumed_hashes)
    failed = {normalize(path, asset=True) for path in failures}
    for error in file_errors:
        if not isinstance(error, dict) or "path" not in error:
            raise ValueError("解包文件错误记录不完整")
        failed.add(normalize(error["path"]))
    overlap = sorted(consumed & failed)
    if set(reviewed) - set(overlap):
        raise ValueError("蓝图缺口例外未命中当前候选的失败来源")
    if set(overlap) - set(reviewed):
        raise ValueError("候选消费了解析不完整的来源，禁止晋升：" + "; ".join(overlap))
    if reviewed:
        if database_path is None:
            raise ValueError("蓝图缺口须核对实际候选隔离结果")
        connection = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            for path, entry in reviewed.items():
                if consumed_hashes[path] != entry["sha256"]:
                    raise ValueError("蓝图缺口来源哈希变化，须重新审查")
                asset = "/Game/" + path.removesuffix(".json")
                if connection.execute("SELECT 1 FROM combat_blueprint_asset WHERE asset_path = ?",
                                      (asset,)).fetchone():
                    raise ValueError("解析失败蓝图仍存在机制投影，禁止晋升")
                for table in ("combat_blueprint_reference", "combat_effect_buff_link"):
                    if connection.execute(f"SELECT 1 FROM {table} WHERE target_asset_path = ? "
                                          "AND target_available <> 0", (asset,)).fetchone():
                        raise ValueError("解析失败蓝图仍被标为可用，禁止晋升")
        finally:
            connection.close()
    return {"report_sha256": expected_hash, "failed_sources_outside_scope": len(failed - consumed),
            "status": "partial" if reviewed else "complete_for_consumed_scope",
            "known_gaps": list(reviewed.values())}
