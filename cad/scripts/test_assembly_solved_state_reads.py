r"""SolidWorks-free contract for the solved-state read shortcuts in ``_assembly``.

The free-DOF gate and the geometry digest skip a deep re-solve when SolidWorks
already reports a solved model. That is only sound if the skip can never make
a gate read a STALE value: a mated component's ``GetConstrainedStatus`` must be
read after the re-solve, and a dirty model's mass properties must still go
through the adapter's rebuilding read. The fast mass-property read must also
produce exactly the adapter's units, or every digest silently moves.

Run: ``uv run python -m pytest cad/scripts/test_assembly_solved_state_reads.py -q``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _assembly  # noqa: E402
from solidworks_mcp.adapters.base import (  # noqa: E402
    AdapterResult,
    AdapterResultStatus,
    MassProperties,
)

FULLY, UNDER = 3, 2


def _attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class Model:
    """An assembly whose constrained statuses are stale until a re-solve."""

    def __init__(self, components):
        self.components = components
        self.rebuilds = 0

    def ForceRebuild3(self, _top_only):
        self.rebuilds += 1
        for comp in self.components:
            comp.solved = True
        return True

    def GetComponents(self, _top_level):
        return list(self.components)


class Component:
    def __init__(self, name, *, fixed=False, pattern=False, stale=UNDER, solved=FULLY):
        self.Name2 = name
        self.IsFixed = fixed
        self._pattern = pattern
        self._stale = stale
        self._solved = solved
        self.solved = False

    def IsPatternInstance(self):
        return self._pattern

    def GetConstrainedStatus(self):
        return self._solved if self.solved else self._stale


def _dof_adapter(components):
    model = Model(components)
    return NS(currentModel=model, _attempt=_attempt), model


def test_mated_component_is_read_after_the_resolve():
    # Stale pre-solve status says UNDER; the solved status is FULLY. Reading
    # before the re-solve would be a false failure (and the converse a false pass).
    adapter, model = _dof_adapter(
        [Component("base", fixed=True), Component("rod"), Component("pat", pattern=True)]
    )
    _assembly.assert_components_fully_defined(adapter)
    assert model.rebuilds == 1


def test_mated_component_still_fails_when_solved_under_constrained():
    adapter, model = _dof_adapter([Component("base", fixed=True), Component("rod", solved=UNDER)])
    with pytest.raises(RuntimeError, match=r"rod \(under\)"):
        _assembly.assert_components_fully_defined(adapter)
    assert model.rebuilds == 1


def test_all_fixed_or_pattern_skips_the_resolve():
    adapter, model = _dof_adapter(
        [Component(f"sub-{i}", fixed=True) for i in range(9)] + [Component("p", pattern=True)]
    )
    _assembly.assert_components_fully_defined(adapter)
    assert model.rebuilds == 0


class Span:
    def __init__(self):
        self.attrs = {}

    def set_attribute(self, key, value):
        self.attrs[key] = value


def _mass_adapter(needs_rebuild):
    calls = []
    native = NS(
        Volume=1.25e-6,
        SurfaceArea=3.5e-3,
        Mass=0.0123,
        CenterOfMass=(0.001, -0.002, 0.003),
        GetMomentOfInertia=lambda _about: tuple(float(i) for i in range(1, 10)),
    )
    model = NS(
        Extension=NS(
            NeedsRebuild2=needs_rebuild,
            CreateMassProperty=lambda: calls.append("native") or native,
        )
    )

    async def get_mass_properties():
        calls.append("adapter")
        return AdapterResult(
            status=AdapterResultStatus.SUCCESS,
            data=MassProperties(
                volume=0, surface_area=0, mass=0, center_of_mass=[0, 0, 0],
                moments_of_inertia={},
            ),
        )

    return NS(currentModel=model, _attempt=_attempt, get_mass_properties=get_mass_properties), calls


def test_solved_model_reads_mass_properties_in_adapter_units():
    adapter, calls = _mass_adapter(needs_rebuild=0)
    data = asyncio.run(_assembly._solved_mass_properties(adapter, Span())).data
    assert calls == ["native"]
    assert data.volume == pytest.approx(1250.0)  # m^3 -> mm^3
    assert data.surface_area == pytest.approx(3500.0)  # m^2 -> mm^2
    assert data.mass == 0.0123
    assert data.center_of_mass == pytest.approx([1.0, -2.0, 3.0])  # m -> mm
    assert data.moments_of_inertia == {
        "Ixx": 1.0, "Iyy": 5.0, "Izz": 9.0, "Ixy": 2.0, "Ixz": 3.0, "Iyz": 6.0,
    }


def test_dirty_model_uses_the_rebuilding_adapter_read():
    adapter, calls = _mass_adapter(needs_rebuild=1)
    asyncio.run(_assembly._solved_mass_properties(adapter, Span()))
    assert calls == ["adapter"]
