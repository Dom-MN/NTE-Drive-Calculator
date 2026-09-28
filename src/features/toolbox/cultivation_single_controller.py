# 在后台计算单角色材料与体力，并丢弃过期的草稿结果。
"""One-worker owner for single-character cultivation calculations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from src.app.workers import WorkerThread
from src.services.cultivation_planner_service import (
    CultivationPlan, CultivationPlannerService, CultivationRequest, CultivationStaminaPlan,
)


_DRAINING_WORKERS: set[WorkerThread] = set()


@dataclass(frozen=True, slots=True)
class SingleCalculationRequest:
    target: CultivationRequest
    owned_quantities: tuple[tuple[str, int], ...]
    hunter_level: int
    identification_level: int | None


@dataclass(frozen=True, slots=True)
class SingleCalculationResult:
    request: SingleCalculationRequest
    plan: CultivationPlan
    stamina: CultivationStaminaPlan | None


class CultivationSingleController(QObject):
    result_ready = Signal(object)
    error = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, service: CultivationPlannerService, *,
                 context_identity: Callable[[], object] | None, parent: QObject) -> None:
        super().__init__(parent)
        self._service = service
        self._context_identity = context_identity
        self._worker: WorkerThread | None = None
        self._active: tuple[int, object] | None = None
        self._pending: tuple[int, SingleCalculationRequest, object] | None = None
        self._revision = 0
        self._closed = False

    def submit(self, request: SingleCalculationRequest, identity: object) -> None:
        if self._closed:
            return
        self._revision += 1
        submission = (self._revision, request, identity)
        if self._worker is not None:
            self._pending = submission
            return
        self._start(submission)

    def invalidate(self) -> None:
        if not self._closed:
            self._revision += 1
            self._pending = None

    def close(self) -> None:
        self._closed = True
        self._revision += 1
        self._pending = None
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            if not worker.wait(5_000):
                worker.setParent(None)
                _DRAINING_WORKERS.add(worker)
                worker.finished.connect(lambda running=worker: _DRAINING_WORKERS.discard(running))
                self._worker = None
                self._active = None

    def _calculate(self, request: SingleCalculationRequest) -> SingleCalculationResult:
        plan = self._service.calculate(request.target)
        calculate_stamina = getattr(self._service, "calculate_stamina", None)
        try:
            stamina = calculate_stamina(
                plan, owned_quantities=dict(request.owned_quantities),
                hunter_level=request.hunter_level,
                effective_identification_level=request.identification_level,
            ) if callable(calculate_stamina) else None
        except (TypeError, ValueError):
            stamina = None
        return SingleCalculationResult(request, plan, stamina)

    def _start(self, submission: tuple[int, SingleCalculationRequest, object]) -> None:
        revision, request, identity = submission
        worker = WorkerThread(target=lambda: self._calculate(request), parent=self)
        self._worker = worker
        self._active = (revision, identity)
        worker.result_ready.connect(self._on_result, Qt.ConnectionType.QueuedConnection)
        worker.error.connect(self._on_error, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(worker.deleteLater)
        self.busy_changed.emit(True)
        worker.start()

    @Slot(object)
    def _on_result(self, result: object) -> None:
        if self._is_current() and QThread.currentThread() == self.thread():
            self.result_ready.emit(result)

    @Slot(str)
    def _on_error(self, message: str) -> None:
        if self._is_current() and QThread.currentThread() == self.thread():
            self.error.emit(message)

    @Slot()
    def _on_finished(self) -> None:
        self._worker = None
        self._active = None
        if self._closed:
            return
        pending = self._pending
        self._pending = None
        if pending is not None:
            self._start(pending)
        else:
            self.busy_changed.emit(False)

    def _is_current(self) -> bool:
        if self._closed or self._active is None or self._active[0] != self._revision:
            return False
        return (self._context_identity is None
                or self._context_identity() == self._active[1])
