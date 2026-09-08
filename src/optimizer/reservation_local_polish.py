# 在递进保护成功后进行有预算的局部候选精修。
"""Bounded refinement for a reservation-feasible progressive result."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from src.models.equipment import Drive
from src.optimizer.deferred_drive_reservations import DeferredDriveReservationState
from src.optimizer.reservation_recovery_support import ProtectedDriveScreenCache
from src.utils.logger import logger

LOCAL_POLISH_MIN_SCORE_LOSS = 3.0
LOCAL_POLISH_MAX_SHAPES = 3
LOCAL_POLISH_FALLBACKS_PER_ROLE_SHAPE = 5
LOCAL_POLISH_MAX_COLUMNS_PER_SHAPE = 80


def improve_progressive_result(
    strategy: Any,
    group: list[str],
    ordinary: dict,
    progressive: dict,
    current_pool: list[Drive],
    custom_sets: dict[str, str],
    assigned_tapes: dict,
    configs: dict[str, dict],
    crit_caps: dict[str, float],
    reservations: DeferredDriveReservationState,
    protected_uids: set[str],
    occupied_uids: set[str],
    cache: ProtectedDriveScreenCache,
) -> dict:
    """Return a strictly better feasible local result, otherwise ``progressive``.

    The normal optimizer remains the only rule evaluator, including stat-priority,
    blacklist and crit floor/cap checks.  This function merely bounds columns to
    the affected drive types, selected drives and cached successors.
    """

    started = perf_counter()
    progressive_score = _score(progressive)
    shapes = {reservations.shape_for_uid(uid) for uid in protected_uids}
    shapes.discard(None)
    if not _should_attempt_local_polish(ordinary, progressive, shapes):
        _log_local_polish(group, "未触发", {}, progressive_score, progressive_score, started)
        return progressive
    unavailable = occupied_uids | reservations.consumed_uids
    candidates = {drive.uid: drive for drive in current_pool if drive.shape_id not in shapes}
    for plan in progressive.values():
        for field in ("assigned_set_drives", "assigned_extra_drives"):
            for drive in plan.get(field, ()):
                candidates[drive.uid] = drive
    for role in group:
        for shape in shapes:
            for drive in cache.fallback_candidates(
                role, shape, LOCAL_POLISH_FALLBACKS_PER_ROLE_SHAPE, unavailable,
            ):
                candidates[drive.uid] = drive
    for slot in reservations.remaining_slots:
        if slot.shape_id in shapes:
            for uid in slot.candidate_uids:
                drive = reservations.drive_for_uid(uid)
                if drive is not None and uid not in unavailable:
                    candidates[uid] = drive
    by_shape = {shape: sum(drive.shape_id == shape for drive in candidates.values()) for shape in shapes}
    if any(count > LOCAL_POLISH_MAX_COLUMNS_PER_SHAPE for count in by_shape.values()):
        _log_local_polish(group, "列数超预算跳过", by_shape, progressive_score, progressive_score, started)
        return progressive
    trial = strategy._find_best_group_fit(
        group, list(candidates.values()), custom_sets, assigned_tapes, configs, crit_caps,
    )
    if not all(trial.get(role, {}).get("valid") for role in group):
        _log_local_polish(group, "已尝试无完整方案", by_shape, progressive_score, progressive_score, started)
        return progressive
    used = strategy._allocated_drive_uids(trial)
    if not reservations.can_consume(used) or _quality(trial) <= _quality(progressive):
        _log_local_polish(group, "已尝试无提升", by_shape, progressive_score, progressive_score, started)
        return progressive
    _log_local_polish(group, "已提升", by_shape, progressive_score, _score(trial), started)
    return trial


def _should_attempt_local_polish(
    ordinary: dict,
    progressive: dict,
    shapes: set[str],
) -> bool:
    """Use only the frozen absolute score loss as the quality trigger."""

    return bool(
        shapes
        and len(shapes) <= LOCAL_POLISH_MAX_SHAPES
        and _score(ordinary) - _score(progressive) >= LOCAL_POLISH_MIN_SCORE_LOSS
    )


def _log_local_polish(
    group: list[str],
    result: str,
    columns: dict[str, int],
    before_score: float,
    after_score: float,
    started: float,
) -> None:
    """Write one compact, UID-free diagnostic for the bounded refinement."""

    summary = "/".join(f"{shape}×{count}" for shape, count in sorted(columns.items())) or "无"
    logger.info(
        "同分精修：角色/组={}，结果={}，候选列数={}，排序分={:.2f}->{:.2f}，耗时={:.3f}s",
        ",".join(group), result, summary, before_score, after_score,
        perf_counter() - started,
    )


def _score(allocation: dict) -> float:
    return sum(float(plan.get("score", 0.0)) for plan in allocation.values())


def _quality(allocation: dict) -> tuple:
    return (
        tuple(tuple(plan.get("stat_priority_key", ()) or ()) for _, plan in sorted(allocation.items())),
        sum(float(plan.get("rank_score", plan.get("score", 0.0))) for plan in allocation.values()),
        _score(allocation),
    )
