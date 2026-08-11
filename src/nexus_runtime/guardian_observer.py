from __future__ import annotations

from collections import Counter
import copy
from dataclasses import dataclass
import queue
import threading
import time
from typing import Any

from .guardian import GuardianError, GuardianOfSubstrate


GUARDIAN_OBSERVER_QUEUE_CAPACITY = 64
GUARDIAN_OBSERVER_READ_DRAIN_SECONDS = 1.0


@dataclass(frozen=True)
class _PendingObservation:
    request: dict[str, Any]
    response: dict[str, Any]


class GuardianObserver:
    """Bounded nonblocking handoff from runtime responses to Guardian storage."""

    def __init__(
        self,
        guardian: GuardianOfSubstrate,
        *,
        queue_capacity: int = GUARDIAN_OBSERVER_QUEUE_CAPACITY,
    ) -> None:
        if not isinstance(guardian, GuardianOfSubstrate):
            raise TypeError("GuardianObserver requires GuardianOfSubstrate")
        if type(queue_capacity) is not int or queue_capacity < 1:
            raise ValueError("Guardian observer queue_capacity must be a positive exact integer")
        self.guardian = guardian
        self._queue_capacity = queue_capacity
        self._pending: queue.Queue[_PendingObservation] = queue.Queue(maxsize=queue_capacity)
        self._state = threading.Condition()
        self._pending_count = 0
        self._gap_lock = threading.Lock()
        self._gap_count = 0
        self._gap_reasons: Counter[str] = Counter()
        self._worker_lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def mark_gap(self, reason: object) -> None:
        safe = (
            reason
            if isinstance(reason, str)
            and reason
            in {
                "guardian_store_unavailable",
                "guardian_store_corrupt",
                "guardian_lineage_corrupt",
                "guardian_observer_queue_full",
                "guardian_internal_observer_error",
            }
            else "guardian_internal_observer_error"
        )
        with self._gap_lock:
            self._gap_count += 1
            self._gap_reasons[safe] += 1

    @property
    def pending_observations(self) -> int:
        with self._state:
            return self._pending_count

    def _ensure_worker(self) -> None:
        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                return
            worker = threading.Thread(
                target=self._observer_loop,
                name="nexus-guardian-observer",
                daemon=True,
            )
            self._worker = worker
            worker.start()

    def _observer_loop(self) -> None:
        while True:
            pending = self._pending.get()
            try:
                self.guardian.observe(pending.request, pending.response)
            except GuardianError as exc:
                self.mark_gap(exc.code)
            except Exception:
                self.mark_gap("guardian_internal_observer_error")
            finally:
                with self._state:
                    self._pending_count -= 1
                    self._state.notify_all()
                self._pending.task_done()

    def submit(self, request: dict[str, Any], response: dict[str, Any]) -> bool:
        self._ensure_worker()
        pending = _PendingObservation(copy.deepcopy(request), copy.deepcopy(response))
        with self._state:
            try:
                self._pending.put_nowait(pending)
            except queue.Full:
                accepted = False
            else:
                self._pending_count += 1
                accepted = True
        if not accepted:
            self.mark_gap("guardian_observer_queue_full")
        return accepted

    def wait_for_idle(
        self,
        timeout_seconds: float = GUARDIAN_OBSERVER_READ_DRAIN_SECONDS,
    ) -> bool:
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds < 0:
            raise ValueError("Guardian observer timeout_seconds must be non-negative")
        deadline = time.monotonic() + float(timeout_seconds)
        with self._state:
            while self._pending_count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._state.wait(remaining)
            return True

    def shutdown(
        self,
        timeout_seconds: float = GUARDIAN_OBSERVER_READ_DRAIN_SECONDS,
    ) -> bool:
        return self.wait_for_idle(timeout_seconds)

    def status(self) -> dict[str, Any]:
        with self._gap_lock:
            gap_count = self._gap_count
            reasons = dict(sorted(self._gap_reasons.items()))
        return {
            "nonblocking": True,
            "queue_capacity": self._queue_capacity,
            "pending_observations": self.pending_observations,
            "gap_count": gap_count,
            "gap_reasons": reasons,
        }


__all__ = [
    "GUARDIAN_OBSERVER_QUEUE_CAPACITY",
    "GUARDIAN_OBSERVER_READ_DRAIN_SECONDS",
    "GuardianObserver",
]
