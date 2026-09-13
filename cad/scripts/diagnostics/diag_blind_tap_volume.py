"""Focused native probe for an interrupted #10-32 base cross tap."""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad" / "scripts"))

import dodo  # noqa: E402
from _common import _early_bound, check, run_build  # noqa: E402
from _holes import DRILL_POINT_H, HoleSpec, wizard_holes  # noqa: E402

DIA = 4.0386
DEPTH = 48.0
THREAD_DEPTH = 46.0
SOCKET_DIA = 25.5
SOCKET_DEPTH = 25.4
BLOCK_X = 430.0
BLOCK_FRONT_Z = -21.35
BLOCK_REAR_Z = 40.0
SEAT_Z = -21.0
BLOCK_HEIGHT = 50.8
HOLE_Y = 38.1


async def _volume(adapter) -> float:
    result = await adapter.get_mass_properties()
    if not result.is_success or result.data is None:
        raise RuntimeError(f"mass properties failed: {result.error}")
    return float(result.data.volume)


def _analytic(hole_dia: float, depth: float, socket_dia: float, step: float) -> float:
    hole_r = hole_dia / 2.0
    socket_r = socket_dia / 2.0
    volume = 0.0
    x = -hole_r
    while x < hole_r:
        dx = x + step / 2.0
        hole_chord = 2.0 * math.sqrt(max(0.0, hole_r**2 - dx**2))
        socket_span = 2.0 * math.sqrt(max(0.0, socket_r**2 - dx**2))
        volume += hole_chord * (depth - socket_span) * step
        x += step
    return volume + math.pi / 3.0 * hole_r**3 * DRILL_POINT_H


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create part", await adapter.create_part())
    check("create block sketch", await adapter.create_sketch("Top"))
    check(
        "create block rectangle",
        await adapter.add_rectangle(
            -BLOCK_X / 2.0,
            -BLOCK_REAR_Z,
            BLOCK_X / 2.0,
            -BLOCK_FRONT_Z,
        ),
    )
    check("exit block sketch", await adapter.exit_sketch())
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )

    plane = check(
        "create socket mouth plane",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=BLOCK_HEIGHT)
        ),
    )
    check("create socket sketch", await adapter.create_sketch(str(plane.name)))
    for x in (-197.0, 197.0):
        check(
            f"create socket circle {x:+.0f}",
            await adapter.add_circle(x, 0.0, SOCKET_DIA / 2.0),
        )
    check("exit socket sketch", await adapter.exit_sketch())
    check(
        "cut socket",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SOCKET_DEPTH, reverse_direction=False)
        ),
    )

    spot_plane = check(
        "create spotface plane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Front Plane",
                offset=BLOCK_FRONT_Z,
            )
        ),
    )
    check("create spotface sketch", await adapter.create_sketch(str(spot_plane.name)))
    for x in (-197.0, 197.0):
        check(
            f"create spotface circle {x:+.0f}",
            await adapter.add_circle(x, HOLE_Y, 9.0 / 2.0),
        )
    check("exit spotface sketch", await adapter.exit_sketch())
    check(
        "cut spotface",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SEAT_Z - BLOCK_FRONT_Z, reverse_direction=True)
        ),
    )

    before = await _volume(adapter)
    result = wizard_holes(
        adapter,
        HoleSpec(
            "tapped_bottoming",
            "#10-32",
            end="blind",
            depth_mm=DEPTH,
            thread_class="2B",
            overrides_mm={"ThreadDepth": THREAD_DEPTH},
        ),
        [[x, HOLE_Y, SEAT_Z] for x in (-197.0, 197.0)],
        (0.0, 0.0, -1.0),
        "focused interrupted blind tap",
        name="FocusedInterruptedTap",
        expect_dia_mm=DIA,
    )
    after = await _volume(adapter)
    removed = before - after

    body = _early_bound(
        (_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or [None])[0],
        "IBody2",
    )
    surfaces: list[
        tuple[str, float, tuple[float, ...], tuple[float, ...]]
    ] = []
    for raw_face in body.GetFaces() or []:
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        box = tuple(float(v) * 1000.0 for v in face.GetBox())
        if surface.IsCone():
            surfaces.append(
                (
                    "cone",
                    float(face.GetArea()) * 1.0e6,
                    tuple(float(v) for v in surface.ConeParams),
                    box,
                )
            )
        elif surface.IsCylinder():
            surfaces.append(
                (
                    "cylinder",
                    float(face.GetArea()) * 1.0e6,
                    tuple(float(v) for v in surface.CylinderParams),
                    box,
                )
            )

    expected_1um = 2.0 * _analytic(
        result.hole_dia_mm, result.depth_mm, SOCKET_DIA, 0.001
    )
    expected_10nm = 2.0 * _analytic(
        result.hole_dia_mm, result.depth_mm, SOCKET_DIA, 0.00001
    )
    print(
        {
            "readback_dia_mm": result.hole_dia_mm,
            "readback_depth_mm": result.depth_mm,
            "removed_mm3": removed,
            "analytic_step_1um_mm3": expected_1um,
            "analytic_step_10nm_mm3": expected_10nm,
            "actual_minus_10nm_mm3": removed - expected_10nm,
            "surfaces": surfaces,
        }
    )
    return {}


if __name__ == "__main__":
    with dodo._com_seat("diag interrupted #10-32 tap volume"):
        sys.exit(run_build(build))
