r"""Reproduction script: channel (top) lever (book ch. 17, pp. 38-41).

One of the 20 cast third-class levers at the top of the machine: fulcrum
pivot at one end (Ø6.5 hole riding the common Ø6.35 fulcrum shaft - the
p.40 ball clevis is the shaft's END mount, mirroring the rocker-pivot
design), channel-spring pull from its rounded end (Ø4 hook hole at
175.05), driven in between by its amplitude bar pinned Ø2 at 127
(5"). Section 11.0 tall x 3.0 thick: 20 levers at the 7.0565 channel
pitch cap the thickness (the M2 12.5 "width" violated the pitch), and
3.0 lets the bar's 3.15 top slot straddle the lever at the pin. The
height was 9.5; the owner ruled the lever gray cast iron and its arm
deepened in-plane while staying under the O12 hub (2026-10-15).

The earlier 254 (10", "clean 2:1") length is REFUTED by the calibrated
ch. 30 front view: the lever bank ends at x ~ -30 (not +54), the
summing-lever plate (44.45 wide, pivot bolt read at x ~ +13..17) sits
directly under the tab line, and the 32 mm channel springs can only
bridge lever tab -> plate if the tab holes are at x ~ -22. The reach is
now pinned EXACTLY by that bridge: the hook hole must sit plumb over the
summing-lever anchor, |x| 24.85 (spring_mount_geom.CHANNEL_ANCHOR_XY, the
solver frame's mirror of this paragraph's photo signs), so c2c = 175.05
from the |x| 199.9 fulcrum (motion ratio 175.05/127 = 1.378). The
photo-read 7" (177.8) left the spring 2.75 mm off plumb at neutral.
The p.39 close-up also shows the bar pin only ~4-5 bar-heights from the
tip (50.8/9.5 = 5.3 fits; 127/9.5 = 13 does not; the read predates the
deepened 11.0 arm). The p.39 close-up also
shows the bar running full height to its rounded end with the hook hole in
it: the bar ends in a full round about the spring hole (the former 6.0
stepped tab left 0.98 of wall beside the hole).

Dimensions: cad/DIMENSIONS.md "Chapter 17" - lengths/section derived in
M6.3/M6.4 (med), hole diameters low.

Layout: lever length along +X from the pivot axis at the origin, bar
height in Y, thickness extruded mid-plane in Z. Through-holes use
mid-plane blind cuts (MCP issue #38 workaround).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_channel_lever.py
"""

from __future__ import annotations

import math

import _config
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_holes
from _com import _early_bound
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
import _telemetry
from ch_channel_lever_notes import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
)
from ch_channel_lever_spec import (
    BAR_PIN_HOLE_SPEC,
    BAR_PIN_X,
    BAR_PIN_X_TOLERANCE,
    BAR_TALL,
    HUB_DIA,
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    LEVER_SPRING_X,
    LEVER_SPRING_X_TOLERANCE,
    LEVER_THICKNESS,
    LEVER_THICKNESS_TOLERANCE,
    PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA,
    PLATE_OFFSET,
    PLATE_OFFSET_TOLERANCE,
    SPRING_EYE_HOLE_SPEC,
    SURFACE_FINISHES,
    TIP_ARC_CX,
    UNIT,
)

PART_NAME = "ch-channel-lever"
MATERIAL = "Gray Cast Iron"  # see _appearance.apply_material docstring

# Every nominal above comes from ch_channel_lever_spec -- the ONE source the
# drawing reads too (DIMENSIONS.md ch17; the reach is set by the plumb spring
# axis, see the spec's comment).  Standard native drill holes for the
# amplitude-bar pin and spring eye are part-owned by the spec as well.
if abs(HUB_LENGTH - _config.machine("channels", "station_pitch_mm")) > 1e-6:
    raise AssertionError("ch_channel_lever_spec.HUB_LENGTH must equal the channel station pitch")
if abs(PLATE_OFFSET - (HUB_LENGTH - LEVER_THICKNESS) / 2.0) > 1e-9:
    raise AssertionError("the plate must sit central on the hub (both are mid-plane)")

HALF_BAR = BAR_TALL / 2.0
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > extrude width
if TIP_ARC_CX != LEVER_SPRING_X:
    raise AssertionError("the full-round tip must be concentric with the spring hole")


# The plate's location from one hub face prints from a hidden reference line
# (the ch_fulcrum_keeper pattern; no metal): on the Top plane (sketch u = model
# X, v = -model Z) at the hub's +X silhouette, from the hub's -Z face, which
# the top view shows uppermost (v = HUB_LENGTH/2), to the plate's -Z face
# (v = LEVER_THICKNESS/2). The plate and hub stay mid-plane extrudes, so its
# value is driven from their own globals.
PLATE_OFFSET_SKETCH = "PlateOffsetReference"
_PLATE_OFFSET_START = (HUB_DIA / 2.0, HUB_LENGTH / 2.0)
_PLATE_OFFSET_END = (HUB_DIA / 2.0, LEVER_THICKNESS / 2.0)


async def plate_offset_reference(adapter) -> list[tuple[str, str]]:
    """Sketch the hub-face -> plate-face reference line; return its drives."""
    check(
        f"create_sketch {PLATE_OFFSET_SKETCH}", await adapter.create_sketch("Top")
    )
    # Direct-to-DB: the line lies on the hub silhouette along the sketch's v
    # axis, so creation-time inference would over-define the sketch.
    set_sketch_direct_db(adapter, True)
    line = check(
        f"{PLATE_OFFSET_SKETCH} line",
        await adapter.add_line(*_PLATE_OFFSET_START, *_PLATE_OFFSET_END),
    )
    set_sketch_direct_db(adapter, False)
    # ConstructionGeometry is declared on ISketchSegment, not the ISketchLine
    # the registry binds.
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{line} did not take the construction flag")
    check(
        f"{PLATE_OFFSET_SKETCH} vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        PLATE_OFFSET,
        PLATE_OFFSET_SKETCH,
    )
    await anchor_point_to_origin(
        adapter, f"{line}.start", *_PLATE_OFFSET_START, PLATE_OFFSET_SKETCH
    )
    await ensure_fully_defined(adapter, f"{PLATE_OFFSET_SKETCH} sketch")
    check(f"exit_sketch {PLATE_OFFSET_SKETCH}", await adapter.exit_sketch())
    name_last_feature(adapter, PLATE_OFFSET_SKETCH)
    full = name_dimensions(
        adapter,
        PLATE_OFFSET_SKETCH,
        ["PlateOffset", "PlateOffsetAnchorX", "PlateOffsetAnchorZ"],
    )
    measured = (
        float(_early_bound(adapter.currentModel.Parameter(full[0]), "IDimension").SystemValue)
        * 1000.0
    )
    if abs(measured - PLATE_OFFSET) > 1e-6:
        raise RuntimeError(
            f"{full[0]} measures {measured:g} mm, expected {PLATE_OFFSET:g} mm"
        )
    drives = (
        '("HubLength" - "LeverThickness") / 2',
        '"HubDia" / 2',
        '"HubLength" / 2',
    )
    return list(zip(full, drives, strict=True))


def tolerance_at_value_places(adapter, feature_name: str, dimension_name: str) -> int:
    """Print one dimension's band at the dimension's own decimal places.

    The shared setters print a band at the fewest places that hold it, so a
    two-place 127.00 would read "127.00 +/-0.1".  The places come from
    DRAWING_PRECISION, the entry that sets the value's places, and are set on
    the model so the drawing imports them verbatim (as
    build_dt_pinion_bracket does for PinSeatCz)."""
    places = DRAWING_PRECISION[feature_name][dimension_name]
    display, _dimension = _named_dimension(adapter, feature_name, dimension_name)
    display = _early_bound(display, "IDisplayDimension")
    do_not_change = -1  # swDimensionPrecisionSettings_e
    display.SetPrecision3(do_not_change, do_not_change, places, do_not_change)
    applied = int(display.GetPrimaryTolPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: tolerance places did not persist: "
            f"requested {places}, dimension reports {applied}"
        )
    _telemetry.success(
        f"tolerance places {dimension_name}@{feature_name}: {places} decimals"
    )
    return places


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations): the lever's design constants. A GUI
    # fine-tune edits THESE globals -- never an auto "D1@Sketch1". The mm suffix
    # is load-bearing: this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 175.05 = 175.05 in, blowing
    # the part up 25.4x). The tip centre is driven by "LeverSpringX" itself, so
    # the full-round end stays concentric with the spring hole.
    await set_global(adapter, "LeverSpringX", f"{LEVER_SPRING_X}mm")
    await set_global(adapter, "BarTall", f"{BAR_TALL}mm")
    await set_global(adapter, "LeverThickness", f"{LEVER_THICKNESS}mm")
    await set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")
    await set_global(adapter, "BarPinX", f"{BAR_PIN_X}mm")
    # (The old BarPinHoleDia/SpringHoleDia/BarPinX knobs are gone: the bar-pin and
    # spring holes are now native Hole Wizard features whose diameters come from
    # the #47/#21 drill standard, not equation-driven sketch dims.)

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims as the dims are created; the drives are collected here and
    # applied in one deferred batch at the end (every equation target must
    # resolve against the finished model + a rebuild).
    drive_jobs: list[tuple[str, str]] = []

    # Side profile: round fulcrum nose, full-height bar, full-round tip about
    # the spring hole (two arcs + two lines). The manual constraints/dims below
    # define the sketch; each driving dim is record()ed into ``outline`` in the
    # exact order it is added so naming/driving land structurally.
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    nose = check(
        "add_arc fulcrum nose",
        await adapter.add_arc(0.0, 0.0, 0.0, HALF_BAR, 0.0, -HALF_BAR),
    )
    (lower_bar,) = await add_line_chain(
        adapter, [(0.0, -HALF_BAR), (TIP_ARC_CX, -HALF_BAR)], close=False
    )
    tip = check(
        "add_arc full-round tip",
        await adapter.add_arc(
            TIP_ARC_CX, 0.0, TIP_ARC_CX, -HALF_BAR, TIP_ARC_CX, HALF_BAR
        ),
    )
    await add_line_chain(adapter, [(TIP_ARC_CX, HALF_BAR), (0.0, HALF_BAR)], close=False)
    set_sketch_direct_db(adapter, False)
    # Semantic scheme: the nose semicircle is pinned by its centre at the
    # origin and both ends on the Y axis; the tip arc by its centre on the X
    # axis at TIP_ARC_CX and both ends plumb with that centre, so it is a full
    # round tangent to the bar edges. The lower edge is horizontal; the upper
    # one follows from the two arcs (a relation there would be redundant). The
    # bar height spans the tip's ends.
    check(
        f"horizontal {lower_bar}",
        await adapter.add_sketch_constraint(lower_bar, None, "horizontal"),
    )
    check(
        "nose centre -> origin",
        await adapter.add_sketch_constraint(f"{nose}.center", "origin", "coincident"),
    )
    for point in (f"{nose}.start", f"{nose}.end"):
        check(
            f"{point} on Y axis",
            await adapter.add_sketch_constraint(point, "origin", "vertical_points"),
        )
    # Dim 1 (emission order): tip-centre X (on the X axis, +TIP_ARC_CX, so an
    # unsigned distance that already evaluates positive). Driven by the spring
    # hole's own global: the tip stays concentric with the hole.
    await anchor_point_to_origin(adapter, f"{tip}.center", TIP_ARC_CX, 0.0, "tip centre")
    outline.record("TipCentreX", '"LeverSpringX"')
    for point in (f"{tip}.start", f"{tip}.end"):
        check(
            f"{point} above/below tip centre",
            await adapter.add_sketch_constraint(point, f"{tip}.center", "vertical_points"),
        )
    # Dim 2: bar height, across the tip's two ends.
    await dimension_between(
        adapter, f"{tip}.start", f"{tip}.end", "vertical_distance", BAR_TALL, "bar height"
    )
    outline.record("BarHeight", '"BarTall"')
    await ensure_fully_defined(adapter, "lever outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "LeverOutline")
    drive_jobs += outline.apply(adapter, "LeverOutline")
    check(
        "extrude lever",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LEVER_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LeverBody")
    (lever_thick_dim,) = name_dimensions(adapter, "LeverBody", ["LeverThick"])
    drive_jobs.append((lever_thick_dim, '"LeverThickness"'))
    # Bar plus the two half-discs: the nose and the full-round tip.
    area = TIP_ARC_CX * BAR_TALL + math.pi * HALF_BAR**2
    expected = area * LEVER_THICKNESS
    await volume_check(adapter, "lever outline", expected, 0.005 * expected)

    # Integral fulcrum hub (2026-09-02, ch17 p.40): O12 boss on the origin,
    # HUB_LENGTH long mid-plane (= the station pitch). r 6 > the 5.50 half-bar,
    # so the boss also stands proud of the bar's edges in-plane: the added
    # volume is the full cylinder minus its overlap with the body (the r 5.50
    # nose half-disc on x < 0, the strip |y| < 5.50 clipped by the circle on
    # x >= 0).
    await set_global(adapter, "HubDia", f"{HUB_DIA}mm")
    await set_global(adapter, "HubLength", f"{HUB_LENGTH}mm")
    hub = SketchDims()
    check("create_sketch hub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HUB_DIA / 2.0, "hub", dims=hub,
        names=("HubCx", "HubCz", "HubDia"),
        drives=(None, None, '"HubDia"'),
    )
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += hub.apply(adapter, "HubProfile")
    check(
        "extrude hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HUB_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Hub")
    (hub_length_dim,) = name_dimensions(adapter, "Hub", ["HubLength"])
    drive_jobs.append((hub_length_dim, '"HubLength"'))
    _r, _h = HUB_DIA / 2.0, HALF_BAR
    _half_strip = _h * math.sqrt(_r**2 - _h**2) + _r**2 * math.asin(_h / _r)
    _overlap = _half_strip + math.pi * _h**2 / 2.0
    v_hub = math.pi * _r**2 * HUB_LENGTH - _overlap * LEVER_THICKNESS
    expected += v_hub
    await volume_check(adapter, "lever + hub", expected, 0.005 * expected)

    # Fulcrum hole (Ø.256 reamed, rides the fulcrum shaft): a bearing bore, kept
    # a plain circle cut. On the origin, so only its diameter is a dim.
    fulcrum = SketchDims()
    check("create_sketch fulcrum hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, PIVOT_HOLE_DIA / 2.0, "fulcrum hole", dims=fulcrum,
        names=("FulcrumCx", "FulcrumCz", "FulcrumDia"),
        drives=(None, None, '"PivotHoleDia"'),
    )
    await ensure_fully_defined(adapter, "fulcrum hole sketch")
    check("exit_sketch fulcrum hole", await adapter.exit_sketch())
    name_last_feature(adapter, "FulcrumProfile")
    drive_jobs += fulcrum.apply(adapter, "FulcrumProfile")
    check(
        "cut fulcrum hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FulcrumHole")
    v_fulcrum = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * HUB_LENGTH  # through the hub
    expected -= v_fulcrum
    await volume_check(adapter, "fulcrum hole", expected, 0.005 * expected)

    # Native Hole Wizard through-holes drilled +Z through the lever.
    bar_dia = blind_cut_dia_mm(BAR_PIN_HOLE_SPEC)
    bar_pin_cut = wizard_holes(
        adapter,
        BAR_PIN_HOLE_SPEC,
        [[BAR_PIN_X, 0.0, LEVER_THICKNESS / 2.0]],
        (0.0, 0.0, 1.0),
        f"bar-pin hole ({BAR_PIN_HOLE_SPEC.size})",
        name="BarPinHole",
        expect_dia_mm=bar_dia,
        placement_dims=[(("BarPinCx", '"BarPinX"'), (None, None))],
    )
    drive_jobs += bar_pin_cut.placement_drive_jobs
    expected -= math.pi * (bar_dia / 2.0) ** 2 * LEVER_THICKNESS
    await volume_check(adapter, "bar-pin hole", expected, 0.005 * expected)

    spring_dia = blind_cut_dia_mm(SPRING_EYE_HOLE_SPEC)
    spring_cut = wizard_holes(
        adapter,
        SPRING_EYE_HOLE_SPEC,
        [[LEVER_SPRING_X, 0.0, LEVER_THICKNESS / 2.0]],
        (0.0, 0.0, 1.0),
        f"spring-eye hole ({SPRING_EYE_HOLE_SPEC.size})",
        name="SpringHole",
        expect_dia_mm=spring_dia,
        placement_dims=[(("SpringCx", '"LeverSpringX"'), (None, None))],
    )
    drive_jobs += spring_cut.placement_drive_jobs
    expected -= math.pi * (spring_dia / 2.0) ** 2 * LEVER_THICKNESS
    await volume_check(adapter, "spring-eye hole", expected, 0.005 * expected)

    drive_jobs += await plate_offset_reference(adapter)

    # Named bore axes for assembly mates (view-independent name selection):
    # Axis1 = fulcrum bore (origin, rides the fulcrum shaft), Axis2 = bar-pin
    # bore (127, 0, the amplitude bar's top pin).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "fulcrum bore")
    await name_bore_axis(
        adapter,
        "Right Plane",
        BAR_PIN_X,
        "Top Plane",
        0.0,
        "bar pin bore",
        drive_a='"BarPinX"',
        drive_jobs=drive_jobs,
    )

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven channel lever (equations neutral)", expected, 0.005 * expected)
    # Saved shown, the reference line would print in every assembly render.
    blank_reference_sketches(adapter, ("PlateOffsetReference",))

    # Bands ride natively on the model dimensions the print imports
    # (drawing-simplicity-policy.md): the reamed fulcrum bore, the plate the
    # bar's top notch straddles, the hub faces that set the station pitch, and
    # the two gain arms from the fulcrum bore. The bands are millimetres; UNIT
    # prints them in inches.
    set_dimension_bilateral_tolerance(
        adapter, "FulcrumProfile", "FulcrumDia", *deviations(PIVOT_HOLE_BAND),
        display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter, "Hub", "HubLength", *deviations(HUB_LENGTH_BAND), display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "LeverBody", "LeverThick", LEVER_THICKNESS_TOLERANCE, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "PlateOffsetReference", "PlateOffset", PLATE_OFFSET_TOLERANCE,
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter, "BarPinHole", "BarPinCx", BAR_PIN_X_TOLERANCE, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "SpringHole", "SpringCx", LEVER_SPRING_X_TOLERANCE, display_unit=UNIT
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for feature_name, dimension_name in (
        ("FulcrumProfile", "FulcrumDia"),
        ("Hub", "HubLength"),
        ("LeverBody", "LeverThick"),
        ("PlateOffsetReference", "PlateOffset"),
        ("BarPinHole", "BarPinCx"),
        ("SpringHole", "SpringCx"),
    ):
        tolerance_at_value_places(adapter, feature_name, dimension_name)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        ("Number", "Material Specification", "Finish", "Quantity", "Isometric View Note"),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
