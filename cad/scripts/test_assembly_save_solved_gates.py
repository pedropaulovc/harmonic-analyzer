r"""SolidWorks-free contract for ``save_assembly_and_images(solved_gates=...)``.

The drive-train builder certifies its freed DOF, interference and 64T
clearance on the model solved by save's final deep rebuild instead of paying a
deep rebuild of its own before the explode. That is sound only if those
``resolve=False`` gates read AFTER that rebuild (a stale pre-solve constrained
status would certify the wrong free set), the whole save pays exactly ONE deep
rebuild before the gates, and a failing gate still stops the save.

Run: ``uv run python -m pytest cad/scripts/test_assembly_save_solved_gates.py -q``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _assembly  # noqa: E402

FULLY, UNDER = 3, 2


def _attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class Component:
    def __init__(self, name, *, fixed=False, stale, solved):
        self.Name2 = name
        self.IsFixed = fixed
        self._stale = stale
        self._solved = solved
        self.model = None

    def IsPatternInstance(self):
        return False

    def GetConstrainedStatus(self):
        return self._solved if self.model.rebuilds else self._stale


class Model:
    """Constrained statuses read stale until the first deep rebuild."""

    def __init__(self, components):
        self.components = components
        for comp in components:
            comp.model = self
        self.rebuilds = 0
        self.Extension = NS(NeedsRebuild2=0)

    def ForceRebuild3(self, _top_only):
        self.rebuilds += 1
        return True

    def GetComponents(self, _top_level):
        return list(self.components)


@pytest.fixture
def save_steps(tmp_path, monkeypatch):
    """Stub every save step after the gates; record what ran."""
    steps: list[str] = []
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)

    def record(name, result=None):
        def step(*_args, **_kwargs):
            steps.append(name)
            return result

        return step

    async def arecord(name, result):
        steps.append(name)
        return result

    monkeypatch.setattr(_assembly, "assert_model_healthy", record("health"))
    monkeypatch.setattr(_assembly, "assert_pose_ledger", record("pose_ledger"))
    monkeypatch.setattr(_assembly, "audit_flip_seeds", record("flip_seeds"))
    monkeypatch.setattr(_assembly, "assert_reference_geometry_hidden", record("ref_hidden"))
    monkeypatch.setattr(_assembly, "set_isometric_view", record("iso"))
    monkeypatch.setattr(_assembly, "rebuild_if_needed_before_save", record("rebuild_if_needed"))
    monkeypatch.setattr(_assembly, "_save_new_assembly_as_copy", record("save"))
    monkeypatch.setattr(_assembly, "_discard_copy_source", record("discard"))
    monkeypatch.setattr(
        _assembly, "_export_assembly_images", lambda *_a: arecord("images", {})
    )
    monkeypatch.setattr(
        _assembly, "reconcile_saved_rebuild_state", lambda *_a: arecord("reconcile", None)
    )
    monkeypatch.setattr(
        _assembly, "assembly_geometry_digest", lambda *_a: arecord("digest", "sha")
    )
    return steps


def _drive_train_like(solved_rod_status):
    # The freed rod reads FULLY before the solve and its real status after it.
    model = Model(
        [
            Component("base-1", fixed=True, stale=FULLY, solved=FULLY),
            Component("rod-1", stale=FULLY, solved=solved_rod_status),
        ]
    )
    return NS(currentModel=model, _attempt=_attempt), model


def _free_dof_gate(adapter):
    _assembly.assert_free_dof_necessity(adapter, 1, resolve=False, required_stems=("rod",))


def test_solved_gates_read_the_final_rebuild_and_the_save_pays_one_rebuild(save_steps):
    adapter, model = _drive_train_like(UNDER)
    gate_rebuilds = []

    def gates(solved):
        gate_rebuilds.append(model.rebuilds)
        _free_dof_gate(solved)

    asyncio.run(_assembly.save_assembly_and_images(adapter, "drive-train", [], solved_gates=gates))
    assert gate_rebuilds == [1]
    assert model.rebuilds == 1
    assert save_steps.index("health") < save_steps.index("save")


def test_failing_solved_gate_stops_the_save(save_steps):
    adapter, model = _drive_train_like(FULLY)  # the freed DOF is pinned
    with pytest.raises(RuntimeError, match="free operational DOF"):
        asyncio.run(
            _assembly.save_assembly_and_images(
                adapter, "drive-train", [], solved_gates=_free_dof_gate
            )
        )
    assert model.rebuilds == 1
    assert "save" not in save_steps
