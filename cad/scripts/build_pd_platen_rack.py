r"""Purchased SDP/SI brass rack on the accepted platen backer envelope.

The pure-data ``pd_platen_rack_spec`` owns the purchased stock identity and
the finished composite dimensions. Cut the strip to the native length, keep
its teeth as supplied, soft-solder it to the backer centred in depth and with
ends flush, then mount/set the actual mesh at assembly. No tooth manufacture
or end-cut indexing is required; the CAD retains nominal rack teeth.

The rack is centred across the backer's depth and sits on its upper edge.
The part's +Y teeth become teeth-down under the assembly's Rx180 pose.
Purchased PA20 rack flanks match the shifted 12T feed sleeve, not the
reducer's tooth form. Profile shift changes axis distance, not rack geometry.

Commercial stock identity is NOT a pitch/form accuracy certificate. Incoming
height/width and every-usable-gap index are distinct from complete form
admission and the ASSEMBLED rigid face/running-axis lead requirement.
The station manifest is physical, not ``FIRST_GAP_X``/``GAP_COUNT``. Verify
actual one-millimetre gauge pins seat on
both full flanks clear of the root; correct each certified diameter using
``rack_over_pins_span_mm`` and measure parallel to rack X, not between unequal
pin heights. The assembly receiving procedure owns all stations, adjacent
and 20-pitch spans, paid calibration uncertainty and separate loaded-travel
height/service-cock acceptance. Reject excess; never infer a vendor grade.
The stock-section receiving helper pays each dimension's OWN calibrated
uncertainty; angular/index measurement uncertainty is not a dimension gage.
Position-only over-pin spans are NOT both-flank or material-envelope admission.
``require_rack_form_admission_mm`` requires complete working-flank, crest and
whole-root POINT envelopes, ONE independent physical datum and total method
uncertainties at least the canonical source compound instrument-only floors.
The source independently maps mic X/actual wire diameter and indicator Y/root
readings. Qualified extrusion or actual functional
roll evidence must justify all material over every feature and actual face;
a roll scalar, finite pins or filtered cloud cannot supply that envelope.
No rack-normal/C1/derivative control is inferred. The receiving allocation
remains PROVISIONAL / NOT SHOP-RELEASED until canonical status changes.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_platen_rack.py
"""

from __future__ import annotations

import sys
from typing import Any

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
    SketchDims,
)
from _sketch_chains import define_polygon_chain, define_rectilinear_chain
from _drawing_marks import (
    _named_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _simplified_part import save_simplified_part
from _visibility import blank_reference_geometry
from pd_platen_rack_spec import (
    BACKER_HEIGHT,
    BAR_HEIGHT,
    BAR_LENGTH,
    BAR_THICKNESS,
    CUT_TOP_Y,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRAWING_REFERENCE_DIMENSIONS,
    ENLARGED_END_VIEW_NOTE,
    FIRST_GAP_X,
    GAP_AREA,
    GAP_COUNT,
    GEAR_DATA,
    INCOMING_RACK_INSPECTION_NOTE,
    ISOMETRIC_VIEW_NOTE,
    PITCH,
    PITCH_LINE_Y,
    PURCHASED_RACK_MATERIAL,
    PURCHASED_RACK_NOTE,
    RACK_HEIGHT,
    RACK_THICKNESS,
    RACK_FLANK_INSPECTION_PROPERTY,
    RACK_Z0,
    ROOT_Y,
    half_width,
    rack_flank_inspection_callout_text,
)

PART_NAME = "pd-platen-rack"
MATERIAL = PURCHASED_RACK_MATERIAL


async def _drawing_witnesses(adapter: Any) -> list[tuple[str, str]]:
    """Native sizes and seam witnesses; these sketches add no solid geometry."""
    drives: list[tuple[str, str]] = []

    # Right-plane sketch X is model -Z, Y is model Y. The rectangle coincides
    # with the strip's actual end outline. Its bottom edge shows the permanent
    # joint that the merged brass solid cannot retain as a topological edge.
    end = SketchDims()
    check("create rack end witness", await adapter.create_sketch("Right"))
    points = [
        (-RACK_Z0, BACKER_HEIGHT),
        (-RACK_Z0 - RACK_THICKNESS, BACKER_HEIGHT),
        (-RACK_Z0 - RACK_THICKNESS, BAR_HEIGHT),
        (-RACK_Z0, BAR_HEIGHT),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="rack end witness",
        dims=end,
        names=["RackDepth", "RackHeight", "RackInset", "SeamHeight"],
        drives=[
            '"RackThickness"',
            '"RackHeight"',
            '("BarThickness" - "RackThickness") / 2',
            '"BarHeight" - "RackHeight"',
        ],
    )
    await ensure_fully_defined(adapter, "rack end witness")
    check("exit rack end witness", await adapter.exit_sketch())
    name_last_feature(adapter, "EndStockProfile")
    drives += end.apply(adapter, "EndStockProfile")

    # The overall height runs between actual end-edge vertices, not a note
    # that types the sum of the backer and strip into the drawing.
    overall = SketchDims()
    check("create overall height witness", await adapter.create_sketch("Front"))
    line = (
        await add_line_chain(
            adapter,
            [(0.0, 0.0), (0.0, BAR_HEIGHT)],
            close=False,
        )
    )[0]
    await anchor_point_to_origin(adapter, f"{line}.start", 0.0, 0.0, "bottom corner")
    check(
        "overall witness vertical",
        await adapter.add_sketch_constraint(
            line,
            None,
            "vertical",
        ),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        BAR_HEIGHT,
        "overall height",
    )
    overall.record("OverallHeight", '"BarHeight"')
    await ensure_fully_defined(adapter, "overall height witness")
    check("exit overall height witness", await adapter.exit_sketch())
    name_last_feature(adapter, "OverallHeightReference")
    drives += overall.apply(adapter, "OverallHeightReference")

    # BlankRefGeom left these sketches shown (farm run 20261009T214031408Z);
    # BlankSketch, read back per sketch, hides them.
    blank_reference_sketches(adapter, ("EndStockProfile", "OverallHeightReference"))
    return drives


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        LinearPatternParameters,
    )

    check("create_part", await adapter.create_part())

    # The backer and square rack retain the accepted envelope. Tooth pitch and
    # flank geometry remain literal-numeric, from the shared pure-data spec.
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 269.64 is inches,
    # blowing the part up 25.4x).
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarThickness", f"{BAR_THICKNESS}mm")
    await set_global(adapter, "RackHeight", f"{RACK_HEIGHT}mm")
    await set_global(adapter, "RackThickness", f"{RACK_THICKNESS}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bar blank: origin-cornered rectangle (the ORDINARY sketch -- fully driven).
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    bar_rect = [
        (0.0, 0.0),
        (BAR_LENGTH, 0.0),
        (BAR_LENGTH, BACKER_HEIGHT),
        (0.0, BACKER_HEIGHT),
    ]
    bar_lines = await add_line_chain(adapter, bar_rect)
    # Emission order (anchor vertex 0 at origin = 0 anchor dims; then the kept
    # per-segment distance dims in line order, skipping the last of each
    # direction): line0 horizontal span = BarLength, line1 vertical span =
    # BarHeight; lines 2/3 close.
    await define_rectilinear_chain(
        adapter, bar_lines, bar_rect, label="bar", dims=bar,
        names=["Length", "Height"],
        drives=['"BarLength"', '"BarHeight" - "RackHeight"'],
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(ExtrusionParameters(depth=BAR_THICKNESS)),
    )
    name_last_feature(adapter, "Bar")
    backer_depth = name_dimensions(adapter, "Bar", ["BackerDepth"])[0]
    drive_jobs.append((backer_depth, '"BarThickness"'))
    v_backer = BAR_LENGTH * BACKER_HEIGHT * BAR_THICKNESS
    volume = await volume_check(adapter, "backer blank", v_backer, 0.005 * v_backer)

    # Catalog-sized square rack blank, soft-soldered on the backer's upper edge.
    # Model the permanent brass union while retaining the distinct strip
    # cross-section; only the rack's depth carries the tooth cuts.
    check(
        "create rack seat plane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Front Plane",
                offset=RACK_Z0,
            )
        ),
    )
    name_last_feature(adapter, "RackSeatPlane")
    check("create_sketch rack stock", await adapter.create_sketch("RackSeatPlane"))
    stock_pts = [
        (0.0, BACKER_HEIGHT),
        (BAR_LENGTH, BACKER_HEIGHT),
        (BAR_LENGTH, BAR_HEIGHT),
        (0.0, BAR_HEIGHT),
    ]
    set_sketch_direct_db(adapter, True)
    stock_lines = await add_line_chain(adapter, stock_pts)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter,
        stock_lines,
        stock_pts,
        label="rack stock",
    )
    await ensure_fully_defined(adapter, "rack stock sketch")
    check("exit_sketch rack stock", await adapter.exit_sketch())
    name_last_feature(adapter, "RackStockProfile")
    check(
        "extrude rack stock",
        await adapter.create_extrusion(ExtrusionParameters(depth=RACK_THICKNESS)),
    )
    name_last_feature(adapter, "RackStock")
    v_bar = v_backer + BAR_LENGTH * RACK_HEIGHT * RACK_THICKNESS
    volume = await volume_check(adapter, "rack and backer", v_bar, 0.005 * v_bar)
    blank_reference_geometry(adapter, (("RackSeatPlane", "PLANE"),))

    # Seed tooth gap at the left end (AddToDB: corners sit near the top edge,
    # where inferencing would snap them onto model vertices -- see the
    # cylinder-gear notch finding).
    check("create_sketch gap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    gap_pts = [
        (FIRST_GAP_X - half_width(ROOT_Y), ROOT_Y),
        (FIRST_GAP_X - half_width(CUT_TOP_Y), CUT_TOP_Y),
        (FIRST_GAP_X + half_width(CUT_TOP_Y), CUT_TOP_Y),
        (FIRST_GAP_X + half_width(ROOT_Y), ROOT_Y),
    ]
    gap = await add_line_chain(adapter, gap_pts)
    set_sketch_direct_db(adapter, False)
    # Nominal representation of the purchased rack's standard straight flanks,
    # not a tooth-cutting operation or a separate shop-editable form.
    await define_polygon_chain(adapter, gap, gap_pts, label="gap")
    await ensure_fully_defined(adapter, "gap sketch")
    check("exit_sketch gap", await adapter.exit_sketch())
    name_last_feature(adapter, "GapProfile")
    gap_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=BAR_THICKNESS + 1.0)
    )
    check("cut seed gap", gap_cut)
    gap_cut_name = name_last_feature(adapter, "SeedGap")
    v_gap = GAP_AREA * RACK_THICKNESS
    volume = await volume_check(adapter, "seed gap", volume - v_gap, 0.02 * v_gap)

    # Pattern along +X from the seed at the left end. The direction edge is
    # resolved geometrically (the straight bar edge along +X nearest the
    # point) and FlipDir1 follows from direction_vector, so the active view no
    # longer decides the sense: a top view once picked the -X top edge and an
    # isometric one the back face, sending every gap off the bar. A pattern
    # whose instances all miss now fails loudly in the adapter; the volume
    # check below still catches a partial miss.
    res = await adapter.linear_pattern_feature(
        LinearPatternParameters(
            direction_point=[BAR_LENGTH / 2.0, 0.0, 0.0],
            direction_vector=[1.0, 0.0, 0.0],
            features=[gap_cut_name],
            count=GAP_COUNT,
            spacing=PITCH,
        )
    )
    check("linear pattern gaps", res)
    tooth_pattern_name = name_last_feature(adapter, "ToothPattern")
    v_rack = v_bar - GAP_COUNT * v_gap
    await volume_check(adapter, "toothed rack", v_rack, 0.01 * GAP_COUNT * v_gap)
    drive_jobs += await _drawing_witnesses(adapter)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: each equation evaluates to the value just built, so
    # the geometry (including the patterned mesh) must not move. The drawing
    # witnesses are neutral too; the gap is intentionally undriven.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven rack (equations neutral)", v_rack, 0.01 * GAP_COUNT * v_gap
    )

    await apply_material(adapter, MATERIAL)

    # Named pitch-line axis (local X at y = pitch line, mid-thickness) so the
    # assembly's rack-pinion mate references the RACK's own engagement line --
    # not the platen it happens to be locked to (2026-07-07 field report).
    await name_bore_axis(
        adapter, "Front Plane", BAR_THICKNESS / 2.0,
        "Top Plane", PITCH_LINE_Y, "pitch axis",
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        for dimension_name in dimension_names & DRAWING_REFERENCE_DIMENSIONS:
            display, _dimension = _named_dimension(
                adapter, feature_name, dimension_name
            )
            display.ShowParenthesis = True
            if not bool(display.ShowParenthesis):
                raise RuntimeError(
                    f"{dimension_name}: stock/composite reference did not persist"
                )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Gear Data": GEAR_DATA,
            "Purchased Rack": PURCHASED_RACK_NOTE,
            "Incoming Rack Inspection": INCOMING_RACK_INSPECTION_NOTE,
            RACK_FLANK_INSPECTION_PROPERTY: rack_flank_inspection_callout_text(),
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Enlarged End View Note": ENLARGED_END_VIEW_NOTE,
        },
    )

    await report_mass_properties(adapter)
    # Assembly views at 1:2 or smaller print the rack's "<cfg> Simplified":
    # the seed gap and its pattern suppressed, a plain bar.
    return await save_simplified_part(adapter, PART_NAME, (gap_cut_name, tooth_pattern_name))


if __name__ == "__main__":
    sys.exit(run_build(build))
