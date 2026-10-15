r"""Build the rocker arm's outline template (MHA-CH-006-TL-13; shop gauge).

An annealed O1 plate cut to the rocker arm's finished outline about its pivot
hole, aimed at the middle of the rocker's arc zone
(``ch_rocker_arm_tl_outline_template_spec``).

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
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fit_deviations import deviations
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_outline_template_spec import (
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
    v_measured = await volume_check(
        adapter, "plate less pivot hole", PLATE_VOLUME, 0.002 * v_plate
    )
    _require_one_solid_body(adapter, label="plate")

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
    # The reference sketch owns printed dimensions but no geometry: hide it
    # so no assembly renders it; the drawing shows it in the view that
    # imports its dimensions (_drawing_hidden_sketches).
    blank_sketch(adapter, "ApexReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
