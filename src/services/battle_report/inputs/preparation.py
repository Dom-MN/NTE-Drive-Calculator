# 以局部场景与配置修订触发战报快照预备，缓存仅供首击证据核验。
from copy import deepcopy
from time import monotonic

from src.services.battle_report.inputs.scopes import team_configuration_unchanged, validate_first_hit
from src.services.battle_report.capture.build_context import PANEL_DOMAINS, native_equipment_projection


def first_hit_snapshot_ready(snapshot, attempt, record):
    """仅完整读取且匹配本次首击证据的输入可以冻结。"""
    return (snapshot.get("state") == "observed" and {"character", "team"} <= (snapshot.get("domains") or {}).keys()
            and "character_projection" in snapshot and native_equipment_projection(snapshot) is not None
            and validate_first_hit(snapshot, attempt, record) is None)


def retain_scope_pending_snapshot(previous, candidate, attempt, record):
    """后续半场读取不覆盖当前半场尚未证实的观测。"""
    def matches_first_domain(snapshot, domain):
        actual = (snapshot.get("domains") or {}).get(domain) or {}
        reference = (attempt.get("firstSnapshotRefs") or {}).get(domain) or {}
        expected = reference or (attempt.get("firstChanges") or {}).get(domain) or {}
        return (bool(expected.get("revision")) and actual.get("revision") == expected["revision"]
                and actual.get("providerId") == (record.get("native_capture") or {}).get("providerId")
                and (not reference or all(actual.get(k) == reference.get(k)
                                         for k in ("providerId", "domain", "domainKey"))))

    if (previous and previous.get("state") == "observed"
            and (candidate.get("state") != "observed"
                 or (any(matches_first_domain(previous, domain) and not matches_first_domain(candidate, domain)
                     for domain in ("character", "team")))
                 or ("character_projection" in previous and team_configuration_unchanged(previous, attempt, record)
                     and not team_configuration_unchanged(candidate, attempt, record)))):
        # 暂时读不到不抹去已有局部证据；保留只供后续核验，不把缺项提升为完整。
        return deepcopy(previous)
    return candidate


class NativeBattlePreparation:
    def __init__(self):
        self.key = None
        self.snapshot = None
        self.retry_at = 0.0
        self.prior_character = None

    def prepare(self, record, attempts, read):
        # 仅在租约还缺范围证据时预备读取；
        # 已完成范围保留各自不可变的快照。
        native = record.get("native_capture") or {}
        context = next((row for row in reversed(native.get("contextEvents") or [])
                        if row.get("kind") == "combat_context"), None)
        if context is None or not all((context.get("roots") or {}).get(k) for k in ("world", "controller", "ps")):
            return
        key = (native.get("providerId"), deepcopy(context.get("roots")),
               {domain: deepcopy((context.get("snapshotChanges") or {}).get(domain))
                for domain in (*PANEL_DOMAINS, "environment")},
               deepcopy(context.get("environment")), deepcopy(native.get("cloneAttempt")))
        if key == self.key and (self.snapshot is not None or monotonic() < self.retry_at):
            return
        previous = (self.snapshot or {}).get("domains", {}).get("character") or self.prior_character
        self.prior_character = previous
        self.key, self.snapshot = key, None
        frozen = read()
        self.retry_at = monotonic() + 2.0
        domains = frozen.get("domains") or {}
        if (frozen.get("state") == "observed" and {"character", "team"} <= domains.keys()
                and "character_projection" in frozen and native_equipment_projection(frozen) is not None):
            if previous and previous.get("revision") != domains["character"].get("revision"):
                frozen["prior_character_observation"] = deepcopy(previous)
            self.snapshot = frozen
        return frozen

    def take_matching(self, attempt, record):
        if self.snapshot is not None and first_hit_snapshot_ready(self.snapshot, attempt, record):
            return deepcopy(self.snapshot)
        return None


def observe_pinned_scopes(lease, record, attempts, final, stop_requested):
    """租约持有待确认观测；每次尝试只发布一次冻结输入或结算缺项证据。"""
    changed = False
    for scope in tuple(lease._scope_snapshots):
        if scope not in attempts or lease._scope_snapshots[scope]["attempt_id"] != attempts[scope]["attemptId"]:
            changed |= lease._scope_snapshots[scope]["snapshot"].get("binding") != "pending_first_hit"
            del lease._scope_snapshots[scope]
    for scope, attempt in attempts.items():
        previous = lease._scope_snapshots.get(scope, {}).get("snapshot")
        # 已发布事实不随后续上下文重新读取；可用性由结算校验独立判断。
        # 新尝试已在上方按身份清理，不会沿用前次冻结内容。
        if previous and previous.get("binding") != "pending_first_hit":
            continue
        if previous and first_hit_snapshot_ready(previous, attempt, record):
            frozen = deepcopy(previous)
        else:
            references = attempt.get("configurationSnapshotRefs") or attempt.get("firstSnapshotRefs") or {}
            frozen = lease._read_battle_snapshot(stop_requested, references=references)
        # 首击可能早于角色域完成读取；局部 pinned 响应不能永久阻止补齐。
        # 仅消费修订与首击证据一致的完整预备输入，不用结算背包冒充首击。
        if not first_hit_snapshot_ready(frozen, attempt, record):
            prepared = lease._preparation.take_matching(attempt, record)
            if prepared is not None:
                frozen = prepared
        if previous is not None:
            frozen = retain_scope_pending_snapshot(previous, frozen, attempt, record)
        frozen = deepcopy(frozen)
        ready = first_hit_snapshot_ready(frozen, attempt, record)
        # 停止时仍缺项可保存实测逐击和缺失原因，但不能标成已确认首击配置。
        frozen["binding"] = ("first_hit_revision" if ready else
                             "unresolved_first_hit" if final else "pending_first_hit")
        if frozen != previous:
            lease._scope_snapshots[scope] = {"attempt_id": attempt["attemptId"], "snapshot": frozen}
            changed |= ready or final
    # 为下一次首击预热当前缓存，不替换已 pinned 的尝试；
    # 预备读取完成也不是本次采集启动的前提。
    if not final:
        lease._preparation.prepare(record, attempts, lambda: lease._read_battle_snapshot(
            stop_requested, require_current=True))
    published = {scope: entry for scope, entry in lease._scope_snapshots.items()
                 if entry["snapshot"].get("binding") != "pending_first_hit"}
    return {"state": "scoped", "scopes": deepcopy(published)} if changed else None
