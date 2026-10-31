r"""Reproduction script: crank keeper-chain anchor eye (book ch. 11, p. 14).

The small brass wire eye clamped under the slotted anchor screw on the crank
arm's front face (page001_img02). A straight TAIL_LEN tail lies on the face
with its end trapped under the screw head, and the wire runs tangent off the
tail into a closed LOOP_R loop turned 90 deg up off the face, like the
photographed hook. The loop's hole axis runs across the arm width, and the
keeper chain (MHA-DT-VN-65) threads it. See ``dt_crank_pin_eye_spec`` for the frame.

Modelled as a torus about an X-parallel axis LOOP_R along -Z from the origin
(loop in the YZ plane, through the origin tangent to Y) plus a tail cylinder
along +Y from the origin. Both bodies share the Top-plane wire circle at the
origin.

``EyeReference`` (blanked, on the Right plane, the eye's own plane): a circle
on the loop's inside edge and the tail's axis, whose diameter and whose
loop-centre-to-tail-end height carry the eye's controlling sizes, since a
torus has no edge to dimension; the drawing's side view prints them
(``dt_crank_pin_eye_notes``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_pin_eye.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from dt_crank_pin_eye_notes import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    LOOP_ID,
)
from dt_crank_pin_eye_spec import LOOP_R, TAIL_LEN, V_LOOP, V_TAIL, WIRE_DIA

PART_NAME = "dt-crank-pin-eye"
MATERIAL = "Brass"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
)

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
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
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

    # REFERENCE sketch, in the eye's own (Right) plane: a Right-plane sketch
    # maps (x, y) -> global (-Z, Y), so the loop centre (Z = -LoopR) is at
    # sketch (LoopR, 0) and the tail runs up the sketch's y axis from the
    # origin. The loop's inside circle and the tail's axis carry the side
    # view's two sizes; the tail is measured from the loop centre, the eye's
    # one real feature centre.
    ref = SketchDims()
    check("create_sketch eye reference", await adapter.create_sketch("Right"))
    loop_inside = await define_circle(
        adapter,
        LOOP_R,
        0.0,
        LOOP_ID / 2.0,
        "loop inside",
        dims=ref,
        names=("LoopCx", None, "LoopID"),
        drives=('"LoopR"', None, '2 * "LoopR" - "WireDia"'),
    )
    set_sketch_direct_db(adapter, True)
    tail_axis = check(
        "tail axis", await adapter.add_centerline(0.0, 0.0, 0.0, TAIL_LEN)
    )
    set_sketch_direct_db(adapter, False)
    check(
        "tail axis vertical",
        await adapter.add_sketch_constraint(tail_axis, None, "vertical"),
    )
    await anchor_point_to_origin(adapter, f"{tail_axis}.start", 0.0, 0.0, "tail root")
    await dimension_between(
        adapter,
        f"{loop_inside}.center",
        f"{tail_axis}.end",
        "vertical_distance",
        TAIL_LEN,
        "eye TailLen",
    )
    ref.record("TailLen", '"TailLen"')
    await ensure_fully_defined(adapter, "eye reference sketch")
    check("exit_sketch eye reference", await adapter.exit_sketch())
    name_last_feature(adapter, "EyeReference")
    drive_jobs += ref.apply(adapter, "EyeReference")

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven eye (equations neutral)", got, 0.001 * got)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    blank_reference_sketches(adapter, ("EyeReference",))
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
