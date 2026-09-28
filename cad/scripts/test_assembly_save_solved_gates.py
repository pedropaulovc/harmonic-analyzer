r"""SolidWorks-free contract for ``save_assembly_and_images(solved_gates=...)``.

The drive-train builder certifies its freed DOF, interference and 64T
clearance on the model solved by save's final deep rebuild instead of paying a
deep rebuild of its own before the explode. That is sound only if:

* the ``resolve=False`` gates read AFTER that rebuild (a stale pre-solve
  constrained status would certify the wrong free set), and the whole save
  pays ONE deep rebuild when no gate dirties the model;
* a gate that dirties the solve state is re-run on the re-solved model, so no
  rebuild ever lands between certification and save -- and a gate that dirties
  it every time refuses the save;
* the gates never read an exploded presentation;
* the DOF manifest is published only beside an assembly that was saved: a
  failed gate or save leaves none.

The save pipeline after the gates is stubbed EXCEPT the conditional
``rebuild_if_needed_before_save``, which runs for real on the fake model.

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
ASM = "drive-train"


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
    """Constrained statuses read stale until the first deep rebuild; a deep
    rebuild clears ``NeedsRebuild2``."""

    def __init__(self, components):
        self.components = components
        for comp in components:
            comp.model = self
        self.rebuilds = 0
        self.exploded = False
        self.Extension = NS(NeedsRebuild2=0)

    def ForceRebuild3(self, _top_only):
        self.rebuilds += 1
        self.Extension.NeedsRebuild2 = 0
        return True

    def GetComponents(self, _top_level):
        return list(self.components)

    def IsExploded(self):
        return self.exploded


@pytest.fixture
def save_steps(tmp_path, monkeypatch):
    """Stub the save pipeline after the gates; record what ran."""
    steps: list[str] = []
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    _assembly.reset_dof_manifest()
    _assembly._record_dof_spec(
        "crank_angle",
        "angle",
        [
            _assembly.named_ref("Right Plane@arm-1", "PLANE"),
            _assembly.named_ref("Right Plane", "PLANE"),
        ],
    )
    yield steps
    _assembly.reset_dof_manifest()


@pytest.fixture(autouse=True)
def _stub_pipeline(save_steps, monkeypatch):
    def record(name):
        def step(*_args, **_kwargs):
            save_steps.append(name)

        return step

    async def arecord(name, result):
        save_steps.append(name)
        return result

    for attr, name in (
        ("assert_model_healthy", "health"),
        ("assert_pose_ledger", "pose_ledger"),
        ("audit_flip_seeds", "flip_seeds"),
        ("assert_reference_geometry_hidden", "ref_hidden"),
        ("set_isometric_view", "iso"),
        ("_save_new_assembly_as_copy", "save"),
        ("_discard_copy_source", "discard"),
    ):
        monkeypatch.setattr(_assembly, attr, record(name))
    monkeypatch.setattr(_assembly, "_export_assembly_images", lambda *_a: arecord("images", {}))
    monkeypatch.setattr(
        _assembly, "reconcile_saved_rebuild_state", lambda *_a: arecord("reconcile", None)
    )
    monkeypatch.setattr(_assembly, "assembly_geometry_digest", lambda *_a: arecord("digest", "sha"))


def _drive_train_like(solved_rod_status=UNDER):
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


def _save(adapter, gates):
    return asyncio.run(
        _assembly.save_assembly_and_images(
            adapter, ASM, [], solved_gates=gates, dof_manifest=True
        )
    )


def test_gates_read_the_final_rebuild_and_the_save_pays_one_rebuild(save_steps):
    adapter, model = _drive_train_like()
    seen = []

    def gates(solved):
        seen.append(model.rebuilds)
        _free_dof_gate(solved)

    _save(adapter, gates)
    assert seen == [1]
    assert model.rebuilds == 1
    assert _assembly.dof_manifest_path(ASM).exists()


def test_a_gate_that_dirties_the_model_is_recertified_on_the_resolved_model(save_steps):
    adapter, model = _drive_train_like()
    seen = []

    def dirtying_gate(solved):
        seen.append(model.rebuilds)
        _free_dof_gate(solved)
        if len(seen) == 1:  # e.g. interference detection marks the solve dirty
            model.Extension.NeedsRebuild2 = 1

    _save(adapter, dirtying_gate)
    # Re-run on the re-solved model; nothing re-solves between it and the save.
    assert seen == [1, 2]
    assert model.rebuilds == 2
    assert "save" in save_steps


def test_a_gate_that_always_dirties_the_model_refuses_the_save(save_steps):
    adapter, model = _drive_train_like()

    def always_dirty(solved):
        _free_dof_gate(solved)
        model.Extension.NeedsRebuild2 = 1

    with pytest.raises(RuntimeError, match="NeedsRebuild2=1"):
        _save(adapter, always_dirty)
    assert "save" not in save_steps
    assert not _assembly.dof_manifest_path(ASM).exists()


def test_gates_refuse_an_exploded_presentation(save_steps):
    adapter, model = _drive_train_like()
    model.exploded = True
    with pytest.raises(RuntimeError, match="collapsed"):
        _save(adapter, _free_dof_gate)
    assert "save" not in save_steps


def test_failing_gate_stops_the_save_and_publishes_no_manifest(save_steps):
    adapter, _model = _drive_train_like(FULLY)  # the freed DOF is pinned
    with pytest.raises(RuntimeError, match="free operational DOF"):
        _save(adapter, _free_dof_gate)
    assert "save" not in save_steps
    assert not _assembly.dof_manifest_path(ASM).exists()


def test_failed_save_retires_the_old_manifest_and_publishes_none(save_steps, monkeypatch):
    adapter, _model = _drive_train_like()
    stale = _assembly.dof_manifest_path(ASM)
    stale.write_text('{"stem": "drive-train", "specs": ["previous build"]}')

    def failing_save(*_args):
        raise RuntimeError("SaveAs3 produced no file")

    monkeypatch.setattr(_assembly, "_save_new_assembly_as_copy", failing_save)
    with pytest.raises(RuntimeError, match="no file"):
        _save(adapter, _free_dof_gate)
    assert not stale.exists()
