r"""Reproduction script: oblique-trammel hub clamp washer (MHA-CH-06-TL-52).

The turned brass top-hat washer under the common #8-32 x 3/4 SHCS at HUB
(``ch_rocker_arm_tl_oblique_hub_washer_spec``): the owner's Ø11 flange (Ø.433
on the sheet's grid), .06 thick, over a Ø.391 ±.002 spigot about .35 mm long
that locates in the
strap's hub hole, and a 13/64 drilled bore through both.

Layout (the spec's frame): the flange and spigot are one turned profile on
the Right plane, sketch (u, v) = model (-Z, Y), revolved about the washer
axis, so the side view carries both diameters and both lengths (rule 11).
The flange's seat face is the Front Plane (z = 0, u = 0); the flange runs to
the head-side face at z = THICK (u = -THICK) and the spigot down to its end
at z = -SPIGOT_LENGTH (u = SPIGOT_LENGTH).  Both lengths run from the seat
face, along the profile's +Y corners so the side view's extension lines
rise off the part.  The bore is a Front-plane circle cut mid-plane through
both, so the face view keeps its DRILL THRU callout.  ``Axis1`` is the bore
axis (Top Plane x Right Plane, the local Z axis).  The local edge limits
(flange BREAK EDGES .005 MAX, sharp spigot end, R.003 MAX root) are drawing
requirements at the spec's sizes; the model keeps those edges sharp.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_hub_washer.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_oblique_hub_washer_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HEIGHT,
    ID,
    OD,
    SPIGOT_DIA,
    SPIGOT_DIA_PLACES,
    SPIGOT_DIA_TOL,
    SPIGOT_LENGTH,
    THICK,
    UNIT,
)

PART_NAME = "ch-rocker-arm-tl-oblique-hub-washer"
MATERIAL = "Brass"  # C36000 free-machining brass rod

_OD_R = OD / 2.0
_SPIGOT_R = SPIGOT_DIA / 2.0
_BORE_R = ID / 2.0
V_TURNED = math.pi * (_OD_R**2 * THICK + _SPIGOT_R**2 * SPIGOT_LENGTH)
V_BORE = math.pi * _BORE_R**2 * HEIGHT
V_WASHER = V_TURNED - V_BORE
# The mid-plane bore cut reaches HEIGHT each side of the seat face, past both
# the head-side face (THICK) and the spigot's end (SPIGOT_LENGTH).
BORE_CUT_DEPTH = 2.0 * HEIGHT

# Right-plane (u, v) = model (-Z, Y): head-side face on the axis, up the
# head-side face, along the flange O.D. to the seat face, down the seat face
# to the spigot, along the spigot O.D. to its end, down the end to the axis,
# and back along the axis.
PROFILE_POINTS = [
    (-THICK, 0.0),
    (-THICK, _OD_R),
    (0.0, _OD_R),
    (0.0, _SPIGOT_R),
    (SPIGOT_LENGTH, _SPIGOT_R),
    (SPIGOT_LENGTH, 0.0),
]


def _z_extreme_mm(adapter, sign: float) -> float:
    """The solid's extreme model Z (mm) toward ``sign`` (+1 / -1).

    ``IBody2::GetExtremePoint`` is exact; the early-bound wrapper returns
    (ok, x, y, z) in metres (build_pd_transgear_disc_hub).
    """
    doc = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, False)) or []
    if len(bodies) != 1:
        raise RuntimeError(f"hub washer: expected one solid body, found {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    res = adapter._attempt(lambda: body.GetExtremePoint(0.0, 0.0, sign), default=None)
    if not res or len(res) < 4:
        raise RuntimeError("hub washer: GetExtremePoint failed")
    return float(res[3]) * 1000.0


def _check_z_span(adapter) -> None:
    """The frame's promise: the flange's head-side face at z = THICK, the
    spigot's end at z = -SPIGOT_LENGTH (into the strap's hole)."""
    low, high = _z_extreme_mm(adapter, -1.0), _z_extreme_mm(adapter, 1.0)
    if abs(high - THICK) > 1e-3 or abs(low + SPIGOT_LENGTH) > 1e-3:
        raise RuntimeError(
            f"hub washer spans z {low:.4f}..{high:.4f}, "
            f"not {-SPIGOT_LENGTH:g}..{THICK:g}"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("WasherOd", OD),
        ("WasherThickness", THICK),
        ("SpigotDia", SPIGOT_DIA),
        ("SpigotLength", SPIGOT_LENGTH),
        ("WasherBore", ID),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch washer profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "washer axis centerline",
        await adapter.add_centerline(-THICK, 0.0, SPIGOT_LENGTH, 0.0),
    )
    lines = await add_line_chain(adapter, PROFILE_POINTS)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        v0 = PROFILE_POINTS[index][1]
        v1 = PROFILE_POINTS[(index + 1) % len(PROFILE_POINTS)][1]
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"washer profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    flange_od, seat_face, spigot_od, spigot_end = lines[1], lines[2], lines[3], lines[4]
    # The head-side face's axis point on the axis, the seat face on the
    # Front Plane (u = 0).
    check(
        "head-side face centre on the axis",
        await adapter.add_sketch_constraint(
            f"{lines[0]}.start", "origin", "horizontal_points"
        ),
    )
    check(
        "seat face on the Front Plane",
        await adapter.add_sketch_constraint(
            f"{seat_face}.start", "origin", "vertical_points"
        ),
    )
    # Both lengths from the seat face, between +Y corners.
    await dimension_between(
        adapter,
        f"{flange_od}.start",
        f"{flange_od}.end",
        "horizontal_distance",
        THICK,
        "flange thickness",
    )
    profile.record("WasherThickness", '"WasherThickness"')
    await dimension_between(
        adapter,
        f"{seat_face}.start",
        f"{spigot_end}.start",
        "horizontal_distance",
        SPIGOT_LENGTH,
        "spigot length",
    )
    profile.record("SpigotLength", '"SpigotLength"')
    await add_diametric_linear_dimension(
        adapter, axis, flange_od, (-THICK / 2.0, _OD_R + 3.0), "WasherOd"
    )
    profile.record("WasherOd", '"WasherOd"')
    await add_diametric_linear_dimension(
        adapter, axis, spigot_od, (SPIGOT_LENGTH + 3.0, _SPIGOT_R), "SpigotDia"
    )
    profile.record("SpigotDia", '"SpigotDia"')
    await ensure_fully_defined(adapter, "washer profile")
    check("exit_sketch washer profile", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    drive_jobs += profile.apply(adapter, "WasherProfile")
    check("revolve washer", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Washer")
    await volume_check(adapter, "flange + spigot", V_TURNED, 0.005 * V_TURNED)
    await bbox_extent_check(adapter, "washer height", "z", HEIGHT)
    await bbox_extent_check(adapter, "washer O.D.", "x", OD)
    _check_z_span(adapter)

    # The 13/64 bore: a Front-plane circle cut mid-plane through both.
    bore = SketchDims()
    check("create_sketch washer bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        _BORE_R,
        "washer bore",
        dims=bore,
        names=("BoreCx", "BoreCy", "WasherBore"),
        drives=(None, None, '"WasherBore"'),
    )
    await ensure_fully_defined(adapter, "washer bore sketch")
    check("exit_sketch washer bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut washer bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    await volume_check(adapter, "washer bore", V_WASHER, 0.005 * V_WASHER)

    # Axis1: the bore axis, model Z (Top Plane x Right Plane).
    axis_name = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "washer bore axis"
    )
    if axis_name != "Axis1":
        raise RuntimeError(f"washer bore axis came back {axis_name!r}, not Axis1")
    blank_reference_geometry(adapter, ((axis_name, "AXIS"),))

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven washer (equations neutral)", V_WASHER, 0.005 * V_WASHER
    )
    _check_z_span(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The spigot carries the owner's explicit band, printed in inch; every
    # other size takes the title block's rows: the O.D. and spigot length
    # .XXX, the thickness .XX, the drilled bore DRILLED HOLES.
    set_dimension_symmetric_tolerance(
        adapter,
        "WasherProfile",
        "SpigotDia",
        SPIGOT_DIA_TOL,
        places=SPIGOT_DIA_PLACES,
        display_unit=UNIT,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=())
    apply_drawing_properties(adapter, PART_NAME)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter, ("Number", "Material Specification", "Finish", "Quantity")
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
