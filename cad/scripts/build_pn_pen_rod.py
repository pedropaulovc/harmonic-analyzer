r"""Reproduction script: pen square rod (book ch. 24, pp. 64-65).

The square brass rod of the pen carriage: it slides in the pen hanger's two U
guides, its turned pivot end drops into the v-block's pivot bore with the
square shoulder resting on the block top, and the adjuster stud (with its
#0-80 jam nut and wire eye) threads into the tapped top face. The shoulder's
internal root carries a modelled tool radius, banded as a single MAX limit.

Frame (``pn_pen_rod_spec`` docstring; the assembly places the part by it):
origin on the rod axis at the SHOULDER. The square runs +Y from the shoulder to
the top face and is centred on the Y axis in both X and Z (Front-plane sketch,
mid-plane extrusion); the pivot runs -Y from the shoulder (Top-plane circle,
reversed boss). Top Plane is the shoulder face; Front and Right Planes contain
the rod axis; ``Axis1`` (the part's only reference axis) is the rod axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_rod.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _single_limit_tolerance import set_single_limit
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fit_deviations import deviations
from _saved_part_guard import require_saved_drawing_properties
from _holes import blind_hole_volume_mm3, wizard_holes
from pn_pen_rod_spec import (
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    END_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    PIVOT_DIA,
    PIVOT_LENGTH,
    ROD_SECTION,
    SHOULDER_FILLET_BAND,
    SHOULDER_FILLET_R,
    SHOULDER_FILLET_TOL_TYPE,
    SQUARE_LENGTH,
    STUD_TAP_DRILL_DIA,
    STUD_TAP_SPEC,
    TAP_WALL_MIN_BAND,
    TAP_WALL_MIN_MM,
    TAP_WALL_MIN_TOL_TYPE,
    TAP_WALL_START_R,
    UNIT,
)

PART_NAME = "pn-pen-rod"
MATERIAL = "Brass"  # see _appearance.apply_material docstring
# The assembly mates the rod line to ``Axis1@pn-pen-rod-1``: the slide axis
# must be the first (and only) reference axis the part creates.
SLIDE_AXIS = "Axis1"


def _shoulder_fillet_max_limit(adapter) -> None:
    """ShoulderRadius as a MAX single limit carrying the band's deviations
    (build_pd_transgear_front_bushing._chamfer_max_limit's recipe)."""
    lower, upper = deviations(SHOULDER_FILLET_BAND)
    _, dimension = _named_dimension(adapter, "ShoulderFillet", "ShoulderRadius")
    label = "ShoulderRadius@ShoulderFillet"
    value = float(dimension.SystemValue)
    if not math.isclose(value, SHOULDER_FILLET_R / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max "
            f"{SHOULDER_FILLET_R}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = SHOULDER_FILLET_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != SHOULDER_FILLET_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {SHOULDER_FILLET_R:g} MAX")


async def _tap_wall_reference(adapter) -> None:
    """RV-01's accepted tap wall, stated on the sheet natively (rule 20): a
    hidden construction line on the Top plane (the shoulder; sketch x = model
    X, sketch y = model -Z, as the end view looks) running +Z from the stud
    tap's thread major on the rod axis toward a flat, as long as the printed
    minimum, so its driving dimension prints ".067 MIN" once set_single_limit
    types it (build_pn_pen_frame's _tap_wall_reference)."""
    check("create_sketch tap wall reference", await adapter.create_sketch("Top"))
    # Direct-to-DB: the line starts on the axis, where creation-time inference
    # would snap it to the origin or the pivot's circle.
    set_sketch_direct_db(adapter, True)
    start = (0.0, -TAP_WALL_START_R)
    line = check(
        "tap wall reference line",
        await adapter.add_line(*start, start[0], start[1] - TAP_WALL_MIN_MM),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("tap wall reference line did not take the construction flag")
    check(
        "tap wall reference vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        TAP_WALL_MIN_MM,
        "tap wall reference",
    )
    await anchor_point_to_origin(adapter, f"{line}.start", *start, "tap wall reference")
    await ensure_fully_defined(adapter, "tap wall reference sketch")
    check("exit_sketch tap wall reference", await adapter.exit_sketch())
    name_last_feature(adapter, "TapWallReference")
    name_dimensions(adapter, "TapWallReference", ["TapWallMin", "TapWallStart"])
    blank_reference_sketches(adapter, ("TapWallReference",))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 112 = 112 in, blowing the part up 25.4x).
    await set_global(adapter, "RodSection", f"{ROD_SECTION}mm")
    await set_global(adapter, "SquareLength", f"{SQUARE_LENGTH}mm")
    await set_global(adapter, "PivotDia", f"{PIVOT_DIA}mm")
    await set_global(adapter, "PivotLength", f"{PIVOT_LENGTH}mm")
    await set_global(adapter, "ShoulderRadius", f"{SHOULDER_FILLET_R}mm")

    drive_jobs: list[tuple[str, str]] = []

    # 1. Square: Front-plane outline x -S/2..S/2, y 0..SQUARE_LENGTH (shoulder
    #    to top face; not origin-centred in Y, so keep the rectilinear chain).
    #    Emission order: the kept per-segment distance dims (one horizontal
    #    width, one vertical length; the closing horizontal/vertical are
    #    redundant), THEN the anchor dims at the bottom-left corner (-S/2, 0):
    #    only X is non-zero, so one anchor dim.
    section = SketchDims()
    check("create_sketch section", await adapter.create_sketch("Front"))
    section_rect = [
        (-ROD_SECTION / 2.0, 0.0),
        (ROD_SECTION / 2.0, 0.0),
        (ROD_SECTION / 2.0, SQUARE_LENGTH),
        (-ROD_SECTION / 2.0, SQUARE_LENGTH),
    ]
    lines = await add_line_chain(adapter, section_rect)
    await define_rectilinear_chain(
        adapter,
        lines,
        section_rect,
        label="rod",
        dims=section,
        names=["Section", "Length", "CornerX"],
        drives=['"RodSection"', '"SquareLength"', '"RodSection" / 2'],
    )
    await ensure_fully_defined(adapter, "rod outline")
    check("exit_sketch section", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += section.apply(adapter, "RodProfile")
    # Mid-plane: Depth is the TOTAL depth, S/2 each side of the Front Plane, so
    # the square is centred on the rod axis in Z as well as X.
    check(
        "extrude rod",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=ROD_SECTION, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Rod")
    depth_dim = name_dimensions(adapter, "Rod", ["Depth"])
    drive_jobs += [(depth_dim[0], '"RodSection"')]
    v_square = ROD_SECTION * ROD_SECTION * SQUARE_LENGTH
    volume = await volume_check(adapter, "rod square", v_square, 0.005 * v_square)

    # 2. Pivot: Top-plane circle on the axis, boss extruded REVERSED (-Y) from
    #    the shoulder. A Top-plane boss runs +Y by default (into the square);
    #    reverse_direction=True drops it below, as fr_top_frame's HubBoss.
    pivot = SketchDims()
    check("create_sketch pivot", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        PIVOT_DIA / 2.0,
        "rod pivot end",
        dims=pivot,
        names=("PivotCx", "PivotCz", "PivotDia"),
        drives=(None, None, '"PivotDia"'),
    )
    await ensure_fully_defined(adapter, "rod pivot sketch")
    check("exit_sketch pivot", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotProfile")
    drive_jobs += pivot.apply(adapter, "PivotProfile")
    check(
        "extrude pivot",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PIVOT_LENGTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Pivot")
    pivot_length_dim = name_dimensions(adapter, "Pivot", ["PivotLength"])
    drive_jobs += [(pivot_length_dim[0], '"PivotLength"')]
    v_pivot = math.pi * (PIVOT_DIA / 2.0) ** 2 * PIVOT_LENGTH
    volume = await volume_check(
        adapter, "rod pivot end", volume + v_pivot, 0.005 * v_pivot
    )

    # 3. Shoulder root: the internal corner where the pivot turns down from the
    #    square's bottom (seat) face gets the tool-nose radius the print allows
    #    (R MAX). Picked on the circular shoulder edge at +X: the only edge
    #    through that point.
    check(
        "fillet shoulder root",
        await adapter.add_fillet(SHOULDER_FILLET_R, [[PIVOT_DIA / 2.0, 0.0, 0.0]]),
    )
    name_last_feature(adapter, "ShoulderFillet")
    fillet_dim = name_dimensions(adapter, "ShoulderFillet", ["ShoulderRadius"])
    drive_jobs += [(fillet_dim[0], '"ShoulderRadius"')]
    # Pappus: the corner spandrel r^2 (1 - pi/4), its centroid r (10 - 3 pi) /
    # (3 (4 - pi)) out from the pivot surface, revolved about the rod axis.
    spandrel = SHOULDER_FILLET_R**2 * (1.0 - math.pi / 4.0)
    spandrel_r = PIVOT_DIA / 2.0 + SHOULDER_FILLET_R * (10.0 - 3.0 * math.pi) / (
        3.0 * (4.0 - math.pi)
    )
    v_fillet = 2.0 * math.pi * spandrel_r * spandrel
    volume = await volume_check(
        adapter, "shoulder root fillet", volume + v_fillet, 0.005 * v_pivot
    )

    # 4. Adjuster stud tap: one blind #0-80 Hole Wizard tap in the top face on
    #    the axis (the placement point coincident with the projected origin).
    stud_tap = wizard_holes(
        adapter,
        STUD_TAP_SPEC,
        [[0.0, SQUARE_LENGTH, 0.0]],
        (0.0, 1.0, 0.0),
        "adjuster stud tap (#0-80)",
        name="StudTap",
        expect_dia_mm=STUD_TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += stud_tap.placement_drive_jobs
    v_tap = blind_hole_volume_mm3(stud_tap.hole_dia_mm, STUD_TAP_SPEC.depth_mm)
    volume = await volume_check(
        adapter, "adjuster stud tap", volume - v_tap, 0.03 * v_tap
    )

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # then re-check: every equation evaluates to the value just built, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pen rod (equations neutral)", volume, 0.005 * v_square
    )

    # 5. Named slide axis (local Y through the origin = Front Plane ∩ Right
    #    Plane, the rod axis): the rod line the assembly mates to as
    #    ``Axis1@<rod>``. No feature above creates a reference axis, so this is
    #    Axis1; fail loud if SolidWorks named it anything else.
    slide_axis = await name_bore_axis(
        adapter,
        "Front Plane",
        0.0,
        "Right Plane",
        0.0,
        "slide axis",
    )
    if slide_axis != SLIDE_AXIS:
        raise RuntimeError(
            f"pen-rod slide axis is {slide_axis!r}; the assembly mates {SLIDE_AXIS!r}"
        )
    _blank_ref_axis(adapter, slide_axis)
    await _tap_wall_reference(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for (feature_name, dimension_name), band in DRAWING_BANDS.items():
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band), display_unit=UNIT
        )
    set_single_limit(
        adapter,
        "TapWallReference",
        "TapWallMin",
        limit=TAP_WALL_MIN_MM,
        band=TAP_WALL_MIN_BAND,
        tol_type=TAP_WALL_MIN_TOL_TYPE,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _shoulder_fillet_max_limit(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "End View Note": END_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "End View Note",
            "Isometric View Note",
        ),
    )
    return artefacts


def _blank_ref_axis(adapter, name: str) -> None:
    """Keep the assembly-mating axis out of saved part renders."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name,
        "AXIS",
        0,
        0,
        0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(f"cannot select {name!r} to hide reference geometry")
    model.BlankRefGeom()
    model.ClearSelection2(True)


if __name__ == "__main__":
    sys.exit(run_build(build))
