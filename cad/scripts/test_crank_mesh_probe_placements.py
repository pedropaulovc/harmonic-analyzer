"""The SolidWorks crank-mesh probes place the 16T and 64T where the drive-train
assembly does.

``diagnostics/probe_live_crank_mesh.py`` and ``probe_crank_post_phase.py``
rebuild the pair in a throwaway assembly to read exact interference, so a
probe that places either gear anywhere else measures a mesh the machine does
not have.  Codex on #960 (T_LAU): R1 moved the 16T onto the MHA-149 fit-up
axis (``X_CRANK_FIT``/``Y_CRANK_FIT``) while both probes still placed it on the
frame crank axis, a 0.603 mm centre-distance error; the live probe also still
placed the 64T at the unshifted ``GEAR64_STATION``.

Each probe's ``build`` runs against a recording ``place_component`` and stops
once both gears are placed; the assembly's own placements come from its
single ``place_component("crank-pinion", ...)`` and
``_place_on_shaft(adapter, "crank-drive-gear", ...)`` call sites.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_drive_train_assembly as drive
from diagnostics import probe_crank_post_phase, probe_live_crank_mesh

ASSEMBLY = Path(drive.__file__)
GEARS = ("crank-drive-gear", "crank-pinion")


class _Placed(Exception):
    """Both gears are placed; the rest of the probe needs a seat."""


class _Adapter:
    async def create_assembly(self):
        return SimpleNamespace(is_success=True, data=None, error=None)


def _recorder(placed: dict[str, list[float]], stop_when_both: bool):
    async def place_component(adapter, part, position, *args, **kwargs):
        placed[part] = [float(value) for value in position]
        if stop_when_both and all(gear in placed for gear in GEARS):
            raise _Placed
        return f"{part}-1"

    return place_component


def _probe_placements(probe, monkeypatch) -> dict[str, list[float]]:
    placed: dict[str, list[float]] = {}
    monkeypatch.setattr(probe, "place_component", _recorder(placed, True))
    with pytest.raises(_Placed):
        asyncio.run(probe.build(_Adapter()))
    return placed


def _assembly_call(function: str, part: str) -> ast.Call:
    tree = ast.parse(ASSEMBLY.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == function
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == part
    ]
    assert len(calls) == 1, f"{part}: expected one {function} call site"
    return calls[0]


def _module_eval(expr: ast.expr):
    code = compile(ast.Expression(expr), str(ASSEMBLY), "eval")
    return eval(code, dict(vars(drive)))


def _assembly_placements(monkeypatch) -> dict[str, list[float]]:
    pinion = _assembly_call("place_component", "crank-pinion")
    placed = {"crank-pinion": [float(v) for v in _module_eval(pinion.args[2])]}
    gear = _assembly_call("_place_on_shaft", "crank-drive-gear")
    monkeypatch.setattr(drive, "place_component", _recorder(placed, False))
    station, face = (_module_eval(arg) for arg in gear.args[2:4])
    asyncio.run(drive._place_on_shaft(None, "crank-drive-gear", station, face))
    return placed


def _max_delta(a: list[float], b: list[float]) -> float:
    return max(abs(x - y) for x, y in zip(a, b, strict=True))


@pytest.mark.parametrize(
    "probe",
    [probe_live_crank_mesh, probe_crank_post_phase],
    ids=lambda probe: probe.__name__.rsplit(".", 1)[-1],
)
@pytest.mark.parametrize("gear", GEARS)
def test_probe_places_the_gear_where_the_assembly_does(probe, gear, monkeypatch):
    expected = _assembly_placements(monkeypatch)[gear]
    monkeypatch.undo()
    placed = _probe_placements(probe, monkeypatch)[gear]
    delta = _max_delta(placed, expected)
    assert delta < 1e-9, (
        f"{probe.__name__} places {gear} at {placed}, {delta:.6f} mm off the "
        f"assembly's {expected}"
    )


def test_the_frame_crank_axis_is_not_the_fit_up_axis(monkeypatch):
    # Positive control: the pre-R1 pinion origin, on the frame crank axis,
    # sits measurably off the placement the probes are pinned to.
    stale = [
        drive.X_CRANK,
        drive.Y_CRANK,
        drive.PINION_TOOTH_Z - drive.PINION_FACE / 2.0,
    ]
    expected = _assembly_placements(monkeypatch)["crank-pinion"]
    assert _max_delta(stale, expected) > 1e-3
