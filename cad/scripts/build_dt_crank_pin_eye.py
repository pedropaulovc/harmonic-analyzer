r"""Reproduction script: crank keeper-chain anchor eye (book ch. 11, p. 14).

The small brass wire eye clamped under the slotted anchor screw on the crank
arm's front face (page001_img02). A straight TAIL_LEN tail lies on the face
with its end trapped under the screw head, and the wire runs tangent off the
tail into a closed LOOP_R loop turned 90 deg up off the face, like the
photographed hook. The loop's hole axis runs across the arm width, and the
keeper chain (MHA-VN-035) threads it. See ``dt_crank_pin_eye_spec`` for the frame.

Modelled as a torus about an X-parallel axis LOOP_R along -Z from the origin
(loop in the YZ plane, through the origin tangent to Y) plus a tail cylinder
along +Y from the origin. Both bodies share the Top-plane wire circle at the
origin.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_pin_eye.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from dt_crank_pin_eye_spec import LOOP_R, TAIL_LEN, V_LOOP, V_TAIL, WIRE_DIA

PART_NAME = "dt-crank-pin-eye"
MATERIAL = "Brass"

def _tail_loop_overlap(steps: int = 64) -> float:
    """Volume the tail shares with the loop, by midpoint integration.

    The tail runs tangent into the loop, so the two tubes overlap until their
    centrelines part by a wire diameter (about 1.7 mm along the tail).
    """
    r = WIRE_DIA / 2.0
    cell = 2.0 * r / steps
    dy = TAIL_LEN / steps
    shared = 0.0
    for iy in range(steps):
        y = (iy + 0.5) * dy
        for ix in range(steps):
            x = -r + (ix + 0.5) * cell
            for iz in range(steps):
                z = -r + (iz + 0.5) * cell
                if x * x + z * z > r * r:
                    continue
                ring = math.hypot(y, z + LOOP_R) - LOOP_R
                if ring * ring + x * x <= r * r:
                    shared += cell * cell * dy
    return shared


V_EYE = V_LOOP + V_TAIL - _tail_loop_overlap()


async def _wire_circle(adapter, dims: SketchDims, names: tuple[str, str, str]) -> None:
    await define_circle(
        adapter, 0.0, 0.0, WIRE_DIA / 2.0, "wire", dims=dims,
        names=names, drives=(None, None, '"WireDia"'),
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "LoopR", f"{LOOP_R}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    await set_global(adapter, "TailLen", f"{TAIL_LEN}mm")
    drive_jobs: list[tuple[str, str]] = []

    # Loop: a Top-plane sketch maps (x, y) -> global (X, -Z), so a horizontal
    # centerline at sketch y = LoopR is the X-parallel line at global
    # z = -LoopR, and the wire circle at the origin revolves about it into a
    # torus in the YZ plane standing off the arm face.
    prof = SketchDims()
    check("create_sketch wire", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    centerline = check("axis", await adapter.add_centerline(0.0, LOOP_R, LOOP_R, LOOP_R))
    set_sketch_direct_db(adapter, False)
    check("axis horizontal", await adapter.add_sketch_constraint(centerline, None, "horizontal"))
    await anchor_point_to_origin(adapter, f"{centerline}.start", 0.0, LOOP_R, "axis start")
    prof.record("AxisOffset", '"LoopR"')
    check("axis length", await adapter.add_sketch_dimension(centerline, None, "linear", LOOP_R))
    prof.record("AxisLen", '"LoopR"')
    await _wire_circle(adapter, prof, ("WireCx", "WireCz", "WireDia"))
    await ensure_fully_defined(adapter, "wire sketch")
    check("exit_sketch wire", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += prof.apply(adapter, "WireProfile")
    check("revolve loop", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Loop")
    await volume_check(adapter, "loop", V_LOOP, 0.01 * V_LOOP)

    # Tail: the same Top-plane wire circle, extruded along the plane normal
    # (+Y) from the loop's tangent point toward the screw.
    tail = SketchDims()
    check("create_sketch tail", await adapter.create_sketch("Top"))
    await _wire_circle(adapter, tail, ("TailCx", "TailCz", "TailDia"))
    await ensure_fully_defined(adapter, "tail sketch")
    check("exit_sketch tail", await adapter.exit_sketch())
    name_last_feature(adapter, "TailProfile")
    drive_jobs += tail.apply(adapter, "TailProfile")
    check("extrude tail", await adapter.create_extrusion(ExtrusionParameters(depth=TAIL_LEN)))
    name_last_feature(adapter, "Tail")
    got = await volume_check(adapter, "eye", V_EYE, 0.01 * V_EYE)
    # The loop is symmetric in Y about the origin, so only the tail moves the
    # centre of mass along Y: a tail extruded into -Y lands it below zero.
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"eye: get_mass_properties failed: {mass.error}")
    if float(mass.data.center_of_mass[1]) <= 0.0:
        raise RuntimeError("tail extruded along -Y, away from the screw -- flip the extrude")

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven eye (equations neutral)", got, 0.001 * got)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
