r"""Reproduction script: channel (top) lever (book ch. 17, pp. 38-41).

One of the 20 third-class levers at the top of the machine: fulcrum
pivot at one end (Ø6.5 hole riding the common Ø6.35 fulcrum shaft - the
p.40 ball clevis is the shaft's END mount, mirroring the rocker-pivot
design), channel-spring pull from its rounded end (Ø4 hook hole at
175.05), driven in between by its amplitude bar pinned Ø2 at 127
(5"). Section 9.4 tall x 3.0 thick: 20 levers at the 7.62 (.300) channel
pitch cap the thickness (the M2 12.5 "width" violated the pitch), and
3.0 lets the bar's 3.15 top slot straddle the lever at the pin. The
owner's 2026-10-15 gray-iron ruling deepened the arm to 10.9; the
2026-11-03 ruling made it 1018 steel from 5/16 x 1 in flat, and the
2026-11-18 ruling (#3113) returns it to the original's 9.5 photo read
(.37) with the original's taper toward the spring tip, from a 5.50 station.

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
tip (50.8/9.5 = 5.3 fits; 127/9.5 = 13 does not). The p.39 close-up also
shows the bar running to a rounded end with the hook hole in it: the end
is a full round about the spring hole (the former 6.0 stepped tab left 0.98
of wall beside the hole), reached by straight edges tapering from the 5.50
taper start, outboard of the bar pin (#3113).

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
from _drawing_prefix import set_dimension_prefix
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
    ROOT_CORNER_PREFIX,
    ROOT_CORNER_R,
    ROOT_CORNER_X,
    root_corner_volume,
)
from ch_channel_lever_spec import (
    BAR_PIN_HOLE_SPEC,
    BAR_PIN_X,
    BAR_TALL,
    HUB_DIA,
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    LEVER_SPRING_X,
    LEVER_THICKNESS,
    LEVER_THICKNESS_TOLERANCE,
    PIVOT_HOLE_DIA,
    PLATE_OFFSET,
    PLATE_OFFSET_TOLERANCE,
    SPRING_EYE_HOLE_SPEC,
    SURFACE_FINISHES,
    TAPER_START_X,
    TIP_ARC_CX,
    TIP_RADIUS,
    UNIT,
    taper_tangent_point,
)

PART_NAME = "ch-channel-lever"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring

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


def outline_area() -> float:
    """Profile area: the nose half-disc, the full-depth bar to the taper
    start, the trapezoid to the tip tangents and the tip circle's segment
    beyond the tangent chord."""
    tangent_x, tangent_y = taper_tangent_point()
    chord_offset = tangent_x - TIP_ARC_CX
    segment = TIP_RADIUS**2 * math.acos(chord_offset / TIP_RADIUS) - chord_offset * math.sqrt(
        TIP_RADIUS**2 - chord_offset**2
    )
    return (
        math.pi * HALF_BAR**2 / 2.0
        + TAPER_START_X * BAR_TALL
        + (HALF_BAR + tangent_y) * (tangent_x - TAPER_START_X)
        + segment
    )


# The plate's location from one hub face prints from a hidden reference line
# (the ch_fulcrum_keeper pattern; no metal): on the Top plane (sketch u = model
# X, v = -model Z) at the hub's +X silhouette, from the hub's -Z face, which
# the top view shows uppermost (v = HUB_LENGTH/2), to the plate's -Z face
# (v = LEVER_THICKNESS/2). The plate and hub stay mid-plane extrudes, so its
# value is driven from their own globals.
PLATE_OFFSET_SKETCH = "PlateOffsetReference"
_PLATE_OFFSET_START = (HUB_DIA / 2.0, HUB_LENGTH / 2.0)
_PLATE_OFFSET_END = (HUB_DIA / 2.0, LEVER_THICKNESS / 2.0)


def plate_offset_reference(adapter) -> list[tuple[str, str]]:
    """Sketch the hub-face -> plate-face reference line; return its drives."""
    check(
        f"create_sketch {PLATE_OFFSET_SKETCH}", adapter.create_sketch("Top")
    )
    # Direct-to-DB: the line lies on the hub silhouette along the sketch's v
    # axis, so creation-time inference would over-define the sketch.
    set_sketch_direct_db(adapter, True)
    line = check(
        f"{PLATE_OFFSET_SKETCH} line",
        adapter.add_line(*_PLATE_OFFSET_START, *_PLATE_OFFSET_END),
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
        adapter.add_sketch_constraint(line, None, "vertical"),
    )
    dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        PLATE_OFFSET,
        PLATE_OFFSET_SKETCH,
    )
    anchor_point_to_origin(
        adapter, f"{line}.start", *_PLATE_OFFSET_START, PLATE_OFFSET_SKETCH
    )
    ensure_fully_defined(adapter, f"{PLATE_OFFSET_SKETCH} sketch")
    check(f"exit_sketch {PLATE_OFFSET_SKETCH}", adapter.exit_sketch())
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


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations): the lever's design constants. A GUI
    # fine-tune edits THESE globals -- never an auto "D1@Sketch1". The mm suffix
    # is load-bearing: this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 175.05 = 175.05 in, blowing
    # the part up 25.4x). The tip centre is driven by "LeverSpringX" itself, so
    # the full-round end stays concentric with the spring hole.
    set_global(adapter, "LeverSpringX", f"{LEVER_SPRING_X}mm")
    set_global(adapter, "BarTall", f"{BAR_TALL}mm")
    set_global(adapter, "TipRadius", f"{TIP_RADIUS}mm")
    set_global(adapter, "TaperStartX", f"{TAPER_START_X}mm")
    set_global(adapter, "LeverThickness", f"{LEVER_THICKNESS}mm")
    set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")
    set_global(adapter, "BarPinX", f"{BAR_PIN_X}mm")
    # (The old BarPinHoleDia/SpringHoleDia/BarPinX knobs are gone: the bar-pin and
    # spring holes are now native Hole Wizard features whose diameters come from
    # the #47/#21 drill standard, not equation-driven sketch dims.)

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims as the dims are created; the drives are collected here and
    # applied in one deferred batch at the end (every equation target must
    # resolve against the finished model + a rebuild).
    drive_jobs: list[tuple[str, str]] = []

    # Side profile: round fulcrum nose, full-depth bar to the taper start, straight
    # taper edges tangent to a full-round tip about the spring hole (two arcs
    # + four lines). The manual constraints/dims below define the sketch; each
    # driving dim is record()ed into ``outline`` in the exact order it is
    # added so naming/driving land structurally.
    tangent_x, tangent_y = taper_tangent_point()
    outline = SketchDims()
    check("create_sketch outline", adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    nose = check(
        "add_arc fulcrum nose",
        adapter.add_arc(0.0, 0.0, 0.0, HALF_BAR, 0.0, -HALF_BAR),
    )
    lower_bar, lower_taper = add_line_chain(
        adapter,
        [(0.0, -HALF_BAR), (TAPER_START_X, -HALF_BAR), (tangent_x, -tangent_y)],
        close=False,
    )
    tip = check(
        "add_arc full-round tip",
        adapter.add_arc(
            TIP_ARC_CX, 0.0, tangent_x, -tangent_y, tangent_x, tangent_y
        ),
    )
    upper_taper, upper_bar = add_line_chain(
        adapter,
        [(tangent_x, tangent_y), (TAPER_START_X, HALF_BAR), (0.0, HALF_BAR)],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    # Semantic scheme: the nose semicircle is pinned by its centre at the
    # origin and both ends on the Y axis, so the two horizontal bar edges sit
    # symmetric about the X axis. The taper starts are plumb with each other;
    # each taper edge is tangent to the tip arc, whose centre sits on the X
    # axis at TIP_ARC_CX. The bar height spans the two taper starts.
    for line in (lower_bar, upper_bar):
        check(f"horizontal {line}", adapter.add_sketch_constraint(line, None, "horizontal"))
    check(
        "nose centre -> origin",
        adapter.add_sketch_constraint(f"{nose}.center", "origin", "coincident"),
    )
    for point in (f"{nose}.start", f"{nose}.end"):
        check(
            f"{point} on Y axis",
            adapter.add_sketch_constraint(point, "origin", "vertical_points"),
        )
    # Dim 1 (emission order): tip-centre X (on the X axis, +TIP_ARC_CX, so an
    # unsigned distance that already evaluates positive). Driven by the spring
    # hole's own global: the tip stays concentric with the hole.
    anchor_point_to_origin(adapter, f"{tip}.center", TIP_ARC_CX, 0.0, "tip centre")
    outline.record("TipCentreX", '"LeverSpringX"')
    for taper in (lower_taper, upper_taper):
        check(f"{taper} tangent to tip", adapter.add_sketch_constraint(taper, tip, "tangent"))
    check(
        "taper starts plumb",
        adapter.add_sketch_constraint(
            f"{lower_taper}.start", f"{upper_taper}.end", "vertical_points"
        ),
    )
    # Dim 2: the taper start from the fulcrum axis, its own printed station
    # outboard of the bar pin.
    dimension_between(
        adapter, f"{lower_taper}.start", "origin", "horizontal_distance",
        TAPER_START_X, "taper start",
    )
    outline.record("TaperStartX", '"TaperStartX"')
    # Dim 3: bar height, across the two taper starts.
    dimension_between(
        adapter, f"{lower_taper}.start", f"{upper_taper}.end", "vertical_distance",
        BAR_TALL, "bar height",
    )
    outline.record("BarHeight", '"BarTall"')
    # Dim 4: the full-round tip's radius.
    check(
        "radial tip radius",
        adapter.add_sketch_dimension(tip, None, "radial", TIP_RADIUS),
    )
    outline.record("TipRadius", '"TipRadius"')
    ensure_fully_defined(adapter, "lever outline")
    check("exit_sketch outline", adapter.exit_sketch())
    name_last_feature(adapter, "LeverOutline")
    drive_jobs += outline.apply(adapter, "LeverOutline")
    check(
        "extrude lever",
        adapter.create_extrusion(
            ExtrusionParameters(depth=LEVER_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LeverBody")
    (lever_thick_dim,) = name_dimensions(adapter, "LeverBody", ["LeverThick"])
    drive_jobs.append((lever_thick_dim, '"LeverThickness"'))
    expected = outline_area() * LEVER_THICKNESS
    volume_check(adapter, "lever outline", expected, 0.005 * expected)

    # Integral fulcrum hub (2026-09-02, ch17 p.40): O12 boss on the origin,
    # HUB_LENGTH long mid-plane (= the station pitch). r 6 > the 5.50 half-bar,
    # so the boss also stands proud of the bar's edges in-plane: the added
    # volume is the full cylinder minus its overlap with the body (the r 5.50
    # nose half-disc on x < 0, the strip |y| < 5.50 clipped by the circle on
    # x >= 0).
    set_global(adapter, "HubDia", f"{HUB_DIA}mm")
    set_global(adapter, "HubLength", f"{HUB_LENGTH}mm")
    hub = SketchDims()
    check("create_sketch hub", adapter.create_sketch("Front"))
    define_circle(
        adapter, 0.0, 0.0, HUB_DIA / 2.0, "hub", dims=hub,
        names=("HubCx", "HubCz", "HubDia"),
        drives=(None, None, '"HubDia"'),
    )
    ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += hub.apply(adapter, "HubProfile")
    check(
        "extrude hub",
        adapter.create_extrusion(
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
    v_lever_hub = volume_check(adapter, "lever + hub", expected, 0.005 * expected)

    # The two roots where the bar's edges run into the hub, over the plate's
    # thickness: the outline cutter's own radius, printed 2X R.065
    # (ch_channel_lever_notes.ROOT_CORNER_R; owner ruling 2026-11-23, tool
    # audit Q9). The bottom corner's edge first: the sheet's radius lands
    # there. Under 0.01 % of the part, so its own volume is checked as the
    # change it makes.
    set_global(adapter, "RootCornerR", f"{ROOT_CORNER_R}mm")
    check(
        "fillet root corners",
        adapter.add_fillet(
            ROOT_CORNER_R,
            [[ROOT_CORNER_X, -HALF_BAR, 0.0], [ROOT_CORNER_X, HALF_BAR, 0.0]],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "RootCorners")
    (root_corner_dim,) = name_dimensions(adapter, "RootCorners", ["RootCornerR"])
    drive_jobs.append((root_corner_dim, '"RootCornerR"'))
    v_roots = root_corner_volume(ROOT_CORNER_R)
    volume_check(adapter, "root corners", v_lever_hub + v_roots, 0.2 * v_roots)
    expected += v_roots

    # Fulcrum hole (Ø.257 F drill, rides the fulcrum shaft): kept a plain
    # circle cut. On the origin, so only its diameter is a dim.
    fulcrum = SketchDims()
    check("create_sketch fulcrum hole", adapter.create_sketch("Front"))
    define_circle(
        adapter, 0.0, 0.0, PIVOT_HOLE_DIA / 2.0, "fulcrum hole", dims=fulcrum,
        names=("FulcrumCx", "FulcrumCz", "FulcrumDia"),
        drives=(None, None, '"PivotHoleDia"'),
    )
    ensure_fully_defined(adapter, "fulcrum hole sketch")
    check("exit_sketch fulcrum hole", adapter.exit_sketch())
    name_last_feature(adapter, "FulcrumProfile")
    drive_jobs += fulcrum.apply(adapter, "FulcrumProfile")
    check(
        "cut fulcrum hole",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FulcrumHole")
    v_fulcrum = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * HUB_LENGTH  # through the hub
    expected -= v_fulcrum
    volume_check(adapter, "fulcrum hole", expected, 0.005 * expected)

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
    volume_check(adapter, "bar-pin hole", expected, 0.005 * expected)

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
    volume_check(adapter, "spring-eye hole", expected, 0.005 * expected)

    drive_jobs += plate_offset_reference(adapter)

    # Named bore axes for assembly mates (view-independent name selection):
    # Axis1 = fulcrum bore (origin, rides the fulcrum shaft), Axis2 = bar-pin
    # bore (127, 0, the amplitude bar's top pin).
    name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "fulcrum bore")
    name_bore_axis(
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
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(adapter, "driven channel lever (equations neutral)", expected, 0.005 * expected)
    # Saved shown, the reference line would print in every assembly render.
    blank_reference_sketches(adapter, ("PlateOffsetReference",))

    # Bands ride natively on the model dimensions the print imports
    # (drawing-simplicity-policy.md): the plate the bar's top notch
    # straddles, the hub faces that set the station pitch, and the two gain
    # arms from the fulcrum bore. The bands are millimetres; UNIT prints them
    # in inches. The F-drilled fulcrum bore carries no band of its own: its
    # DRILL THRU callout takes the title block's DRILLED HOLES row.
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
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for feature_name, dimension_name in (
        ("Hub", "HubLength"),
        ("LeverBody", "LeverThick"),
        ("PlateOffsetReference", "PlateOffset"),
    ):
        tolerance_at_value_places(adapter, feature_name, dimension_name)

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The one printed root corner stands for both (2X R.065).
    set_dimension_prefix(adapter, "RootCorners", "RootCornerR", ROOT_CORNER_PREFIX)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    artefacts = save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        ("Number", "Material Specification", "Finish", "Quantity", "Isometric View Note"),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
