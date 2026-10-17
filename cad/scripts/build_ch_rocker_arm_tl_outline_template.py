r"""Build the rocker arm's outline template (MHA-CH-006-TL-13; shop gauge).

An annealed O1 plate cut to the rocker arm's finished outline about its pivot
hole, aimed at the middle of the rocker's arc zone, with a radial slot at the
arm's rod-pin hole that clocks it (``ch_rocker_arm_tl_outline_template_spec``).

Layout (the spec's frame): the pivot hole on the origin, the arcs' common
centre straight up the Y axis, the outline sketched on the Front plane and
extruded +Z by the plate thickness. The outline sketch mirrors
``build_ch_rocker_arm``'s strap sketch: two concentric arcs, a radial tip land
square to the top arc at each end, and a tapered end down to the bottom arc.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_outline_template.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_basic_tolerance,
    set_dimension_bilateral_tolerance,
)
from _fit_deviations import deviations
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_outline_template_spec import (
    BASIC_DIMENSIONS,
    BOT_END_X,
    BOT_END_Y,
    BOTTOM_BELOW_PIVOT,
    CENTER_Y,
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PIVOT_HOLE_DIA,
    PLATE_VOLUME,
    ROD_SLOT_AREA,
    ROD_SLOT_FLAT,
    ROD_SLOT_WIDTH,
    ROD_SLOT_X,
    ROD_SLOT_Y,
    R_BOTTOM,
    R_TOP,
    THICK,
    TIP_FACE,
    TIP_X,
    TIP_Y,
    TOP_ABOVE_PIVOT,
    TOP_END_X,
    TOP_END_Y,
    outline_area,
    rod_slot_points,
)

PART_NAME = "ch-rocker-arm-tl-outline-template"
MATERIAL = "Plain Carbon Steel"  # the registry row names the O1 ground flat stock
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)
THROUGH_CUT_DEPTH = 4.0 * THICK  # mid-plane total; > thickness


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (rebind to the
    base ISketchSegment, which declares ``ConstructionGeometry``)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units. The apex heights are the printed values; the arcs'
    # shared centre derives from the top one, and the bottom apex from the
    # centre, so the two arcs stay concentric.
    await set_global(adapter, "RTop", f"{R_TOP}mm")
    await set_global(adapter, "RBottom", f"{R_BOTTOM}mm")
    await set_global(adapter, "TopAbovePivot", f"{TOP_ABOVE_PIVOT}mm")
    await set_global(adapter, "CenterY", '"TopAbovePivot" + "RTop"')
    await set_global(adapter, "TopEndX", f"{TOP_END_X}mm")
    await set_global(adapter, "BottomEndX", f"{BOT_END_X}mm")
    await set_global(adapter, "TipFaceLen", f"{TIP_FACE}mm")
    await set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")
    await set_global(adapter, "PlateThickness", f"{THICK}mm")
    await set_global(adapter, "RodSlotX", f"{ROD_SLOT_X}mm")
    await set_global(adapter, "RodSlotY", f"{ROD_SLOT_Y}mm")
    await set_global(adapter, "RodSlotWidth", f"{ROD_SLOT_WIDTH}mm")
    await set_global(adapter, "RodSlotFlat", f"{ROD_SLOT_FLAT}mm")

    drive_jobs: list[tuple[str, str]] = []

    tail_b = (-BOT_END_X, BOT_END_Y)
    rod_b = (BOT_END_X, BOT_END_Y)
    tail_t = (-TOP_END_X, TOP_END_Y)
    rod_t = (TOP_END_X, TOP_END_Y)
    rod_tip = (TIP_X, TIP_Y)
    tail_tip = (-TIP_X, TIP_Y)

    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = [
        check(
            "outline bottom arc", await adapter.add_arc(0.0, CENTER_Y, *tail_b, *rod_b)
        ),
        check("outline top arc", await adapter.add_arc(0.0, CENTER_Y, *tail_t, *rod_t)),
        check("outline rod tip", await adapter.add_line(*rod_t, *rod_tip)),
        check("outline rod end", await adapter.add_line(*rod_tip, *rod_b)),
        check("outline tail tip", await adapter.add_line(*tail_t, *tail_tip)),
        check("outline tail end", await adapter.add_line(*tail_tip, *tail_b)),
    ]
    set_sketch_direct_db(adapter, False)
    bottom_arc, top_arc, rod_tip_line, _rod_end, tail_tip_line, _tail_end = entities
    # Dim EMISSION ORDER (SketchDims renames by it): centre height, bottom
    # radius, top radius, bottom-tail x, bottom-rod x, top-tail x, top-rod x,
    # rod-tip length, tail-tip length. Concentricity and the radial tip lands
    # are relations, not dims.
    await anchor_point_to_origin(
        adapter, f"{bottom_arc}.center", 0.0, CENTER_Y, "arc centre"
    )
    outline.record("CenterY", '"CenterY"')
    check(
        "concentric arcs",
        await adapter.add_sketch_constraint(
            f"{top_arc}.center", f"{bottom_arc}.center", "coincident"
        ),
    )
    check(
        "bottom radius",
        await adapter.add_sketch_dimension(bottom_arc, None, "radial", R_BOTTOM),
    )
    outline.record("BottomRadius", '"RBottom"')
    check(
        "top radius", await adapter.add_sketch_dimension(top_arc, None, "radial", R_TOP)
    )
    outline.record("TopRadius", '"RTop"')
    for name, point, value, drive in (
        ("BottomTailX", f"{bottom_arc}.start", BOT_END_X, '"BottomEndX"'),
        ("BottomRodX", f"{bottom_arc}.end", BOT_END_X, '"BottomEndX"'),
        ("TopTailX", f"{top_arc}.start", TOP_END_X, '"TopEndX"'),
        ("TopRodX", f"{top_arc}.end", TOP_END_X, '"TopEndX"'),
    ):
        check(
            name,
            await adapter.add_sketch_dimension(
                point, "origin", "horizontal_distance", value
            ),
        )
        outline.record(name, drive)
    # Tip lands square to the top arc: the arc centre on each land line makes
    # it radial; then its length.
    for name, line in (("RodTipLen", rod_tip_line), ("TailTipLen", tail_tip_line)):
        check(
            f"{name} radial",
            await adapter.add_sketch_constraint(
                f"{top_arc}.center", line, "coincident"
            ),
        )
        check(name, await adapter.add_sketch_dimension(line, None, "linear", TIP_FACE))
        outline.record(name, '"TipFaceLen"')
    await ensure_fully_defined(adapter, "outline sketch")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "OutlineProfile")
    drive_jobs += outline.apply(adapter, "OutlineProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICK)),
    )
    name_last_feature(adapter, "Plate")
    drive_jobs.append(
        (name_dimensions(adapter, "Plate", ["Thick"])[0], '"PlateThickness"')
    )
    v_plate = outline_area() * THICK
    await volume_check(adapter, "outline plate", v_plate, 0.01 * v_plate)

    pivot = SketchDims()
    check("create_sketch pivot hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        PIVOT_HOLE_DIA / 2.0,
        "pivot hole",
        dims=pivot,
        names=("PivotX", "PivotY", "PivotDia"),
        drives=(None, None, '"PivotHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pivot hole sketch")
    check("exit_sketch pivot hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotHoleProfile")
    drive_jobs += pivot.apply(adapter, "PivotHoleProfile")
    check(
        "cut pivot hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotHole")
    # The tolerance (0.2 % of the plate, ~29 mm^3) stays well under the hole's
    # own ~105 mm^3, so a missing or partial cut still fails.
    v_hole = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * THICK
    if 0.002 * v_plate >= 0.5 * v_hole:
        raise AssertionError("the volume gate can no longer see the pivot hole")
    v_slot = ROD_SLOT_AREA * THICK
    v_measured = await volume_check(
        adapter, "plate less pivot hole", PLATE_VOLUME + v_slot, 0.002 * v_plate
    )
    _require_one_solid_body(adapter, label="plate")

    # Rod-pin slot: a radial stadium at the rocker's rod-pin hole station,
    # one closed contour (build_fr_top_frame's dowel-slot recipe, turned to
    # the radial). A construction ray from the pivot to the slot's centre
    # holds the station; the slot's construction axis has that point as its
    # midpoint and runs parallel to the ray, so the slot is radial. The
    # printed BASIC station lives in RodSlotReference, below.
    slot = SketchDims()
    check("create_sketch rod slot", await adapter.create_sketch("Front"))
    p1, p2, p3, p4, outer, inner = rod_slot_points()
    set_sketch_direct_db(adapter, True)
    ray = check(
        "rod slot ray", await adapter.add_line(0.0, 0.0, ROD_SLOT_X, ROD_SLOT_Y)
    )
    axis = check("rod slot axis", await adapter.add_line(*inner, *outer))
    side_a = check("rod slot side a", await adapter.add_line(*p1, *p2))
    outer_end = check("rod slot outer end", await adapter.add_arc(*outer, *p2, *p3))
    side_b = check("rod slot side b", await adapter.add_line(*p3, *p4))
    inner_end = check("rod slot inner end", await adapter.add_arc(*inner, *p4, *p1))
    set_sketch_direct_db(adapter, False)
    for line in (ray, axis):
        _as_construction(adapter, line)
    for join, a, b in (
        ("side a - outer end", f"{side_a}.end", f"{outer_end}.start"),
        ("outer end - side b", f"{outer_end}.end", f"{side_b}.start"),
        ("side b - inner end", f"{side_b}.end", f"{inner_end}.start"),
        ("inner end - side a", f"{inner_end}.end", f"{side_a}.start"),
        ("outer centre on the axis", f"{outer_end}.center", f"{axis}.end"),
        ("inner centre on the axis", f"{inner_end}.center", f"{axis}.start"),
    ):
        check(
            f"rod slot {join}",
            await adapter.add_sketch_constraint(a, b, "coincident"),
        )
    # Tangency closes the shape; parallel sides make both ends one radius.
    for a, b in (
        (side_a, outer_end),
        (outer_end, side_b),
        (side_b, inner_end),
        (inner_end, side_a),
    ):
        check(
            f"rod slot {a} tangent {b}",
            await adapter.add_sketch_constraint(a, b, "tangent"),
        )
    check(
        "rod slot sides parallel",
        await adapter.add_sketch_constraint(side_a, side_b, "parallel"),
    )
    check(
        "rod slot centre at the axis midpoint",
        await adapter.add_sketch_constraint(f"{ray}.end", axis, "midpoint"),
    )
    check(
        "rod slot radial",
        await adapter.add_sketch_constraint(axis, ray, "parallel"),
    )
    # Emission order: the station (x, y), the width across the outer end's
    # tangent points (its witness lines run outboard, clear of the slot),
    # then the run between the two end centres (the axis's ends), so its
    # witness lines rise from the centres the detail marks (mr-tl13-4: off
    # side a they read as lines below the slot).
    await anchor_point_to_origin(adapter, f"{ray}.start", 0.0, 0.0, "rod slot ray foot")
    await dimension_between(
        adapter,
        f"{ray}.start",
        f"{ray}.end",
        "horizontal_distance",
        ROD_SLOT_X,
        "rod slot station x",
    )
    slot.record("RodSlotCentreX", '"RodSlotX"')
    await dimension_between(
        adapter,
        f"{ray}.start",
        f"{ray}.end",
        "vertical_distance",
        ROD_SLOT_Y,
        "rod slot station y",
    )
    slot.record("RodSlotCentreY", '"RodSlotY"')
    await dimension_between(
        adapter,
        f"{side_a}.end",
        f"{side_b}.start",
        "distance",
        ROD_SLOT_WIDTH,
        "rod slot width",
    )
    slot.record("RodSlotWidth", '"RodSlotWidth"')
    await dimension_between(
        adapter,
        f"{axis}.start",
        f"{axis}.end",
        "distance",
        ROD_SLOT_FLAT,
        "rod slot run",
    )
    slot.record("RodSlotFlat", '"RodSlotFlat"')
    await ensure_fully_defined(adapter, "rod slot sketch")
    check("exit_sketch rod slot", await adapter.exit_sketch())
    name_last_feature(adapter, "RodSlotProfile")
    drive_jobs += slot.apply(adapter, "RodSlotProfile")
    check(
        "cut rod slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RodSlot")
    # The slot (~15 mm^3) is under the plate gate's tolerance, so it is
    # checked against the measured plate with a tolerance it can fail.
    v_measured = await volume_check(
        adapter, "plate less rod slot", v_measured - v_slot, 0.05 * v_slot
    )
    if abs(v_measured - PLATE_VOLUME) > 0.002 * v_plate:
        raise RuntimeError("plate less pivot hole and rod slot left PLATE_VOLUME")
    _require_one_solid_body(adapter, label="plate with rod slot")

    # REFERENCE sketch: the print gives each arc's height on the mirror line
    # from the pivot hole, yet no outline dimension carries it (the arcs hang
    # from their shared centre). Construction lines from the pivot centre to
    # each apex; their lengths ARE the printed values. Direct-to-DB keeps
    # inference from adding relations the explicit ones would over-define.
    apex = SketchDims()
    check("create_sketch apex reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    top_line = check(
        "top apex line", await adapter.add_line(0.0, 0.0, 0.0, TOP_ABOVE_PIVOT)
    )
    bottom_line = check(
        "bottom apex line", await adapter.add_line(0.0, 0.0, 0.0, -BOTTOM_BELOW_PIVOT)
    )
    set_sketch_direct_db(adapter, False)
    for name, line, value, drive, label in (
        (
            "TopAbovePivot",
            top_line,
            TOP_ABOVE_PIVOT,
            '"TopAbovePivot"',
            "top apex above the pivot",
        ),
        (
            "BottomBelowPivot",
            bottom_line,
            BOTTOM_BELOW_PIVOT,
            '"RBottom" - "CenterY"',
            "bottom apex below the pivot",
        ),
    ):
        _as_construction(adapter, line)
        check(
            f"{label} vertical",
            await adapter.add_sketch_constraint(line, None, "vertical"),
        )
        await anchor_point_to_origin(
            adapter, f"{line}.start", 0.0, 0.0, f"{label} foot"
        )
        await dimension_between(
            adapter, f"{line}.start", f"{line}.end", "vertical_distance", value, label
        )
        apex.record(name, drive)
    await ensure_fully_defined(adapter, "apex reference sketch")
    check("exit_sketch apex reference", await adapter.exit_sketch())
    name_last_feature(adapter, "ApexReference")
    drive_jobs += apex.apply(adapter, "ApexReference")

    # REFERENCE sketch for the rod slot's BASIC station, the same form: one
    # construction ray from the pivot centre to the slot's centre, its x and
    # y the printed values, driven by the globals the slot itself reads.
    slot_station = SketchDims()
    check("create_sketch rod slot reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    station_ray = check(
        "rod slot station ray",
        await adapter.add_line(0.0, 0.0, ROD_SLOT_X, ROD_SLOT_Y),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, station_ray)
    await anchor_point_to_origin(
        adapter, f"{station_ray}.start", 0.0, 0.0, "rod slot station foot"
    )
    for name, kind, value in (
        ("RodSlotX", "horizontal_distance", ROD_SLOT_X),
        ("RodSlotY", "vertical_distance", ROD_SLOT_Y),
    ):
        await dimension_between(
            adapter,
            f"{station_ray}.start",
            f"{station_ray}.end",
            kind,
            value,
            f"rod slot BASIC {name}",
        )
        slot_station.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "rod slot reference sketch")
    check("exit_sketch rod slot reference", await adapter.exit_sketch())
    name_last_feature(adapter, "RodSlotReference")
    drive_jobs += slot_station.apply(adapter, "RodSlotReference")

    # Apply the deferred drive equations after the whole model exists; each
    # evaluates to the value just built, so the geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven outline template (equations neutral)",
        v_measured,
        0.002 * v_plate,
    )
    _require_one_solid_body(adapter, label="driven plate")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for (feature_name, dimension_name), band in DRAWING_BANDS.items():
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band)
        )
    for feature_name, dimension_name in BASIC_DIMENSIONS:
        set_dimension_basic_tolerance(adapter, feature_name, dimension_name)
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
    # The reference sketches own printed dimensions but no geometry: hide
    # them so no assembly renders them; the drawing shows each in the view
    # that imports its dimensions (_drawing_hidden_sketches).
    blank_sketch(adapter, "ApexReference")
    blank_sketch(adapter, "RodSlotReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
