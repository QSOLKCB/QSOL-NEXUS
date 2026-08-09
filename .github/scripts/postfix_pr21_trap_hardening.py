#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "src/nexus_runtime/trap/controller.py"
text = TARGET.read_text(encoding="utf-8")

old = '''        with self._lock:
            if self._active is not None:
                raise TrapError("trap_incident_already_active", "a trap incident is already active")
            if not self._controller_lease.try_acquire():
                raise TrapError("trap_controller_alive", "another live Trap Base controller owns this trap root")
            if self.registry.active_incident() is not None:
                self._controller_lease.release()
                raise TrapError("trap_incident_already_active", "a trap incident is already active")
            roster = _normalize_defender_roster(
'''
new = '''        with self._lock:
            if self._active is not None or self.registry.active_incident() is not None:
                raise TrapError("trap_incident_already_active", "a trap incident is already active")
            roster = _normalize_defender_roster(
'''
if text.count(old) != 1:
    raise SystemExit("activation preflight anchor did not match exactly once")
text = text.replace(old, new, 1)

old = '''            try:
                activation = self.gate.begin_activation(request)
'''
new = '''            try:
                if not self._controller_lease.try_acquire():
                    raise TrapError("trap_controller_alive", "another live Trap Base controller owns this trap root")
                if self.registry.active_incident() is not None:
                    raise TrapError("trap_incident_already_active", "a trap incident is already active")
                activation = self.gate.begin_activation(request)
'''
if text.count(old) != 1:
    raise SystemExit("activation try anchor did not match exactly once")
text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")
print("PR21 activation lease cleanup hardened")
