r"""Build the oblique-trammel jig's end bracket (MHA-CH-06-TL-28; shop fixture).

A 6061-T6511 1/2 x 1 in flat on edge, 2.71 long, two off: each carries one of the
leadscrew feed's KP08 pillow blocks on base bar 1's top
(``ch_rocker_arm_tl_oblique_end_bracket_spec``).

Layout (the spec's model frame, +Z up): ONE Front-plane rectangle from the
inner end face (model x 0) about the mid-width line, extruded +Z by the stock
thickness; the four #8-32 UNC base-bar taps and the two #6-32 UNC KP08 taps are
two native Hole Wizard features tapped THRU from the top face on the row y 0.
The row's printed station (.250 from the -Y side face) lives on a hidden
reference sketch, ``HoleRowReference`` (build_ch_rocker_arm_tl_oblique_base_bar's
``RailRowReference``); the stock thickness the end view prints lives on another,
``BracketThickReference`` (a drawing view cannot attach the extrusion's depth).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_end_bracket.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _holes import wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _metric_vendor_dimension import set_metric_vendor_units
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from ch_rocker_arm_tl_oblique_end_bracket_spec import (
    BAR_TAP_DRILL,
    BAR_TAP_SPEC,
    BAR_TAP_X,
    BRACKET_LENGTH,
    BRACKET_THICK,
    BRACKET_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HALF_WIDTH,
    HOLE_ROW_Y,
    ISOMETRIC_VIEW_NOTE,
    KP08_TAP_DRILL,
    KP08_TAP_SPEC,
    KP08_TAP_X,
    METRIC_DIMENSIONS,
)

PART_NAME = "ch-rocker-arm-tl-oblique-end-bracket"
MATERIAL = "6061 Alloy"  # the registry row's example aluminium flat bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

V_BRACKET = BRACKET_LENGTH * BRACKET_WIDTH * BRACKET_THICK
V_BAR_TAPS = len(BAR_TAP_X) * math.pi * (BAR_TAP_DRILL / 2.0) ** 2 * BRACKET_THICK
V_KP08_TAPS = len(KP08_TAP_X) * math.pi * (KP08_TAP_DRILL / 2.0) ** 2 * BRACKET_THICK
# Tight enough that a missing tap (about 146 mm^3 the smaller) fails.
_V_TOL = 20.0


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
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("BracketLength", BRACKET_LENGTH),
        ("BracketWidth", BRACKET_WIDTH),
        ("BracketThick", BRACKET_THICK),
        *((f"BarTapX{k}", x) for k, x in enumerate(BAR_TAP_X, start=1)),
        ("KP08TapX1", KP08_TAP_X[0]),
        ("KP08TapX2", KP08_TAP_X[1]),
    ):
        await set_global(adapter, name, f"{value}mm")

    # --- Bracket: Front-plane rectangle about the mid-width line, +Z ---------
    profile = SketchDims()
    check("create_sketch bracket", await adapter.create_sketch("Front"))
    points = [
        (0.0, -HALF_WIDTH),
        (BRACKET_LENGTH, -HALF_WIDTH),
        (BRACKET_LENGTH, HALF_WIDTH),
        (0.0, HALF_WIDTH),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="bracket profile",
        dims=profile,
        names=["BracketLength", "BracketWidth", "BracketHalfWidth"],
        drives=['"BracketLength"', '"BracketWidth"', '"BracketWidth" / 2'],
    )
    await ensure_fully_defined(adapter, "bracket profile")
    check("exit_sketch bracket", await adapter.exit_sketch())
    name_last_feature(adapter, "BracketProfile")
    drive_jobs = profile.apply(adapter, "BracketProfile")
    check(
        "extrude bracket",
        await adapter.create_extrusion(ExtrusionParameters(depth=BRACKET_THICK)),
    )
    name_last_feature(adapter, "Bracket")
    # The depth stays off the print: the stock thickness prints from
    # BracketThickReference (below), which a drawing view can attach to.
    drive_jobs.append(
        (name_dimensions(adapter, "Bracket", ["BracketDepth"])[0], '"BracketThick"')
    )
    volume = await volume_check(adapter, "bracket", V_BRACKET, _V_TOL)

    # --- Base-bar taps: ONE #8-32 UNC wizard feature, THRU from the top -----
    # The wizard sets the row on y 0 by an origin relation (a zero coordinate
    # takes no dimension); each station is a dimension from the inner end.
    bar_taps = wizard_holes(
        adapter,
        BAR_TAP_SPEC,
        [[x, 0.0, BRACKET_THICK] for x in BAR_TAP_X],
        (0.0, 0.0, 1.0),
        "base-bar screw taps (#8-32 through)",
        name="BarTaps",
        expect_dia_mm=BAR_TAP_DRILL,
        placement_dims=[
            ((f"BarTap{k}X", f'"BarTapX{k}"'), (None, None))
            for k in range(1, len(BAR_TAP_X) + 1)
        ],
    )
    drive_jobs += bar_taps.placement_drive_jobs
    volume = await volume_check(
        adapter, "bracket with base-bar taps", volume - V_BAR_TAPS, _V_TOL
    )

    # --- KP08 taps: ONE #6-32 UNC wizard feature, THRU from the top ---------
    # The size token is checked by the cut diameter (a wrong token fails).
    kp08_taps = wizard_holes(
        adapter,
        KP08_TAP_SPEC,
        [[x, 0.0, BRACKET_THICK] for x in KP08_TAP_X],
        (0.0, 0.0, 1.0),
        "KP08 screw taps (#6-32 through)",
        name="KP08Taps",
        expect_dia_mm=KP08_TAP_DRILL,
        placement_dims=[
            ((f"KP08Tap{k}X", f'"KP08TapX{k}"'), (None, None))
            for k in range(1, len(KP08_TAP_X) + 1)
        ],
    )
    drive_jobs += kp08_taps.placement_drive_jobs
    volume = await volume_check(
        adapter, "bracket with KP08 taps", volume - V_KP08_TAPS, _V_TOL
    )

    # --- The row's station: a reference sketch -------------------------------
    # One line down the inner end face from the origin to the -Y side, driven
    # by the width that side itself reads. It lies on the end face's edge and
    # stays a plain sketch line: a construction line prints its dash font
    # over the drawing's outline (machinist review mr4: the end view's bottom
    # edge printed broken).
    row_station = SketchDims()
    check("create_sketch hole row reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    row_line = check(
        "hole row station line", await adapter.add_line(0.0, 0.0, 0.0, -HOLE_ROW_Y)
    )
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{row_line}.start", 0.0, 0.0, "hole row")
    await anchor_point_to_origin(
        adapter, f"{row_line}.end", 0.0, -HOLE_ROW_Y, "hole row station HoleRowY"
    )
    row_station.record("HoleRowY", '"BracketWidth" / 2')
    await ensure_fully_defined(adapter, "hole row reference sketch")
    check("exit_sketch hole row reference", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleRowReference")
    drive_jobs += row_station.apply(adapter, "HoleRowReference")

    # --- The stock thickness: a reference sketch ------------------------------
    # Farm r1 (#290): the extrusion's imported depth has no sound drawing-view
    # attachment, so _supplier_dimensions refuses to dress it as the STOCK
    # reference; a sketch dimension attaches to its witness line (the base
    # bar's BarWidth, _supplier_washer_model's thickness witness). One plain
    # sketch line up the inner end face's -Y edge on the Right plane (on the
    # edge, as the row's line), sketch (u, v) = model (-Z, Y)
    # (_oblique_pivot_block_model), the end view's plane.
    thick = SketchDims()
    check("create_sketch thickness reference", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    witness = check(
        "thickness witness line",
        await adapter.add_line(0.0, -HALF_WIDTH, -BRACKET_THICK, -HALF_WIDTH),
    )
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(
        adapter, f"{witness}.start", 0.0, -HALF_WIDTH, "thickness witness foot"
    )
    thick.record("ThickWitnessY", '"BracketWidth" / 2')
    check(
        "thickness witness along Z",
        await adapter.add_sketch_constraint(witness, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{witness}.start",
        f"{witness}.end",
        "distance",
        BRACKET_THICK,
        "BracketThick",
    )
    thick.record("BracketThick", '"BracketThick"')
    await ensure_fully_defined(adapter, "thickness reference sketch")
    check("exit_sketch thickness reference", await adapter.exit_sketch())
    name_last_feature(adapter, "BracketThickReference")
    drive_jobs += thick.apply(adapter, "BracketThickReference")
    _require_one_solid_body(adapter, label="end bracket")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven end bracket (equations neutral)", volume, _V_TOL
    )
    _require_one_solid_body(adapter, label="driven end bracket")

    # Every model edit -- material, marked set, model-owned places -- precedes
    # the save. The bar taps and row print at three places, so the title
    # block's ±.005 governs them; the KP08 taps print exact millimetres with
    # their own band (owner ruling 4; spec module docstring).
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for (feature_name, dimension_name), (places, band) in METRIC_DIMENSIONS.items():
        set_dimension_symmetric_tolerance(
            adapter, feature_name, dimension_name, band, display_unit="mm"
        )
        set_metric_vendor_units(adapter, feature_name, dimension_name, places=places)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    # The reference sketches own printed dimensions but no geometry: hide
    # them so no assembly renders them; the drawing shows each in the view
    # that imports its dimension (_drawing_hidden_sketches).
    blank_sketch(adapter, "HoleRowReference")
    blank_sketch(adapter, "BracketThickReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
