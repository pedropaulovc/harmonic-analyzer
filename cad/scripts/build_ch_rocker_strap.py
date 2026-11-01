r"""Reproduction script: rocker strap (MHA-CH-13; 20 used, one per rocker arm).

The flat 1018 strap of the built-up rocker arm MHA-CH-06
(``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``): the finished part's outline
-- the top edge on the R31.5 arc, the concentric bottom edge, the tip lands
radial to their shared centre and the tapered end faces
(``build_ch_rocker_arm``'s strap profile) -- at the finished thickness, with
the Ø.400 reamed hole the
MHA-CH-12 hub is pressed into (``ch_rocker_hub_fit``). The #47 rod-pin hole is
drilled after joining, so it is not here (``ch_rocker_strap_spec``).

Layout: the MHA-CH-06 frame (origin on the bottom arc's midpoint, +X the rod
side, the hub hole PIVOT_MID_Y up), extruded mid-plane in Z. ONE sketch,
``StrapProfile``, holds the outline and the hole, so every printed location
runs from the hole's centre: a construction line on the mirror axis, from the
bottom edge through the hole's centre to the top edge, carries both edges'
heights from the hole and puts the arcs' centre on that axis (the bottom radius is
then derived, never printed); the tip lands' outer corners and the taper feet
are dimensioned across from the hole's centre.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_strap.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from ch_rocker_hub_fit import STRAP_HOLE_BAND
from ch_rocker_strap_notes import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    TIP_LAND_PREFIX,
)
from ch_rocker_strap_spec import (
    ARM_DEPTH,
    ARM_THICKNESS,
    ARM_THICKNESS_BAND,
    BOT_END_X,
    BOT_END_Y,
    BOTTOM_EDGE_BAND,
    BOTTOM_EDGE_BELOW_PIVOT,
    CENTER_Y,
    CURVE_RADIUS,
    HOLE_DIA,
    PIVOT_MID_Y,
    R_TOP,
    ROD_TIP_X,
    ROD_TIP_Y,
    TIP_FACE,
    TOP_EDGE_ABOVE_PIVOT,
    TOP_EDGE_BAND,
    TOP_END_X,
    TOP_END_Y,
    UNIT,
    strap_area,
)

PART_NAME = "ch-rocker-strap"
MATERIAL = "Plain Carbon Steel"  # AISI 1018 flat
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

V_STRAP = (strap_area() - math.pi * (HOLE_DIA / 2.0) ** 2) * ARM_THICKNESS


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations); the mm suffix is load-bearing (INCH
    # document). The tip and taper offsets are the trig-derived vertices of
    # ch_rocker_arm_spec, folded in here as numbers (build_ch_rocker_arm: a
    # live sin() in the equation manager re-evaluates to a broken value).
    await set_global(adapter, "CurveRadius", f"{CURVE_RADIUS}mm")
    await set_global(adapter, "ArmDepth", f"{ARM_DEPTH}mm")
    await set_global(adapter, "ArmThickness", f"{ARM_THICKNESS}mm")
    await set_global(adapter, "TipFaceLen", f"{TIP_FACE}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")
    await set_global(adapter, "TopAbovePivot", f"{TOP_EDGE_ABOVE_PIVOT}mm")
    await set_global(adapter, "BottomBelowPivot", f"{BOTTOM_EDGE_BELOW_PIVOT}mm")
    await set_global(adapter, "TipX", f"{ROD_TIP_X}mm")
    await set_global(adapter, "BottomEndX", f"{BOT_END_X}mm")
    await set_global(adapter, "RTop", '"CurveRadius"')

    drive_jobs: list[tuple[str, str]] = []

    tail_b = (-BOT_END_X, BOT_END_Y)
    rod_b = (BOT_END_X, BOT_END_Y)
    tail_t = (-TOP_END_X, TOP_END_Y)
    rod_t = (TOP_END_X, TOP_END_Y)
    rod_tip = (ROD_TIP_X, ROD_TIP_Y)
    tail_tip = (-ROD_TIP_X, ROD_TIP_Y)

    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = [
        check(
            "strap bottom arc",
            await adapter.add_arc(0.0, CENTER_Y, *tail_b, *rod_b),
        ),
        check(
            "strap top arc",
            await adapter.add_arc(0.0, CENTER_Y, *tail_t, *rod_t),
        ),
        # Each tip: a short radial land square to the top edge, then the
        # tapered end face down to the bottom arc (build_ch_rocker_arm).
        check("strap rod tip", await adapter.add_line(*rod_t, *rod_tip)),
        check("strap rod end", await adapter.add_line(*rod_tip, *rod_b)),
        check("strap tail tip", await adapter.add_line(*tail_t, *tail_tip)),
        check("strap tail end", await adapter.add_line(*tail_tip, *tail_b)),
        # The mirror axis from the bottom edge, through the hole's centre, to
        # the top edge: its two parts are the edges' printed heights.
        check(
            "edge reference centerline",
            await adapter.add_centerline(
                0.0, 0.0, 0.0, PIVOT_MID_Y + TOP_EDGE_ABOVE_PIVOT
            ),
        ),
    ]
    set_sketch_direct_db(adapter, False)
    bottom_arc, top_arc, rod_tip_line, _rod_end, tail_tip_line, _tail_end, axis = (
        entities
    )
    # Dimension EMISSION ORDER (SketchDims renames by it): the hole's centre
    # height (on-axis: one dim) and Ø, the top edge's height over the hole,
    # the bottom edge's depth under it, the top radius, the taper feet's and
    # the tip corners' offsets from the hole's centre, then the two land
    # lengths. Every other tie is a relation.
    hole = await define_circle(
        adapter,
        0.0,
        PIVOT_MID_Y,
        HOLE_DIA / 2.0,
        "hub hole",
        dims=strap,
        names=(None, "HoleY", "HoleDia"),
        drives=(None, '"ArmDepth" / 2', '"HoleDia"'),
    )
    hole_centre = f"{hole}.center"
    check(
        "mirror axis vertical",
        await adapter.add_sketch_constraint(axis, None, "vertical"),
    )
    check(
        "hole centre on the mirror axis",
        await adapter.add_sketch_constraint(hole_centre, axis, "coincident"),
    )
    check(
        "mirror axis foot on the bottom edge",
        await adapter.add_sketch_constraint(f"{axis}.start", bottom_arc, "coincident"),
    )
    check(
        "mirror axis head on the top edge",
        await adapter.add_sketch_constraint(f"{axis}.end", top_arc, "coincident"),
    )
    check(
        "arc centre on the mirror axis",
        await adapter.add_sketch_constraint(f"{top_arc}.center", axis, "coincident"),
    )
    check(
        "concentric arcs",
        await adapter.add_sketch_constraint(
            f"{top_arc}.center", f"{bottom_arc}.center", "coincident"
        ),
    )
    await dimension_between(
        adapter,
        hole_centre,
        f"{axis}.end",
        "vertical_distance",
        TOP_EDGE_ABOVE_PIVOT,
        "top edge above the hole",
    )
    strap.record("TopAbovePivot", '"TopAbovePivot"')
    await dimension_between(
        adapter,
        f"{axis}.start",
        hole_centre,
        "vertical_distance",
        BOTTOM_EDGE_BELOW_PIVOT,
        "bottom edge below the hole",
    )
    strap.record("BottomBelowPivot", '"BottomBelowPivot"')
    check(
        "top radius",
        await adapter.add_sketch_dimension(top_arc, None, "radial", R_TOP),
    )
    strap.record("TopRadius", '"RTop"')
    # Offsets across from the hole's centre: horizontal_distance shows the
    # magnitude, so each drives POSITIVE against its shared global.
    for ref, name, value, expr in (
        (f"{bottom_arc}.start", "BottomTailX", BOT_END_X, '"BottomEndX"'),
        (f"{bottom_arc}.end", "BottomRodX", BOT_END_X, '"BottomEndX"'),
        (f"{tail_tip_line}.end", "TailTipX", ROD_TIP_X, '"TipX"'),
        (f"{rod_tip_line}.end", "RodTipX", ROD_TIP_X, '"TipX"'),
    ):
        await dimension_between(
            adapter, ref, hole_centre, "horizontal_distance", value, f"strap {name}"
        )
        strap.record(name, expr)
    # Tip lands square to the top edge: the top arc's centre on each land
    # line (=> radial => normal to the arc), then its length.
    for line, name in ((rod_tip_line, "RodTipLen"), (tail_tip_line, "TailTipLen")):
        check(
            f"{name} radial",
            await adapter.add_sketch_constraint(
                f"{top_arc}.center", line, "coincident"
            ),
        )
        check(
            f"{name} length",
            await adapter.add_sketch_dimension(line, None, "linear", TIP_FACE),
        )
        strap.record(name, '"TipFaceLen"')
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    check(
        "extrude strap",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=ARM_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Strap")
    thickness_dim = name_dimensions(adapter, "Strap", ["StrapThickness"])
    drive_jobs.append((thickness_dim[0], '"ArmThickness"'))
    v_measured = await volume_check(adapter, "strap", V_STRAP, 0.01 * V_STRAP)

    # Axis1: the hub hole's axis (Right Plane x Top Plane + PIVOT_MID_Y).
    await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", PIVOT_MID_Y, "hub hole"
    )

    # Deferred drive equations; each evaluates to the value just built, so the
    # volume must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven strap (equations neutral)", v_measured, 0.005 * V_STRAP
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Native bands: the thickness (the finished part's, the faces are not cut
    # again), the hub hole's press band, the top edge's one-sided plus over the
    # hole and the bottom edge's one-sided minus under it.
    strap_lower, strap_upper = deviations(ARM_THICKNESS_BAND)
    if strap_lower != -strap_upper:
        raise AssertionError("ch_rocker_arm_spec.ARM_THICKNESS_BAND must be symmetric")
    set_dimension_symmetric_tolerance(
        adapter, "Strap", "StrapThickness", strap_upper, display_unit=UNIT
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "StrapProfile",
        "HoleDia",
        *deviations(STRAP_HOLE_BAND),
        display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "StrapProfile",
        "TopAbovePivot",
        *deviations(TOP_EDGE_BAND),
        display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "StrapProfile",
        "BottomBelowPivot",
        *deviations(BOTTOM_EDGE_BAND),
        display_unit=UNIT,
    )
    set_dimension_prefix(adapter, "StrapProfile", "RodTipLen", TIP_LAND_PREFIX)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
