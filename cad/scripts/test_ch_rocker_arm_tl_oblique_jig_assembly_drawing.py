"""Offline contract for the oblique-trammel jig drawing package (TL-00).

The sheet text comes from the jig spec, the BOM prints every family made and
bought with its registry number, numbered as the steps cite it, every BOM row
carries a balloon, and each sheet's budgeted regions stay inside the border,
out of the title block and clear of one another. Actual view creation and the
shared finalizer must leave every physical sheet linked to the live source.
"""

from __future__ import annotations

import asyncio
import dataclasses
import math
import re
from pathlib import Path
from types import SimpleNamespace
from contextlib import nullcontext

import pytest

import _com
import _config
import _drawing_balloons
import _component_references
import _drawing_tables
import _drawing_common
import _drawing_detail_crop
import _drawing_dimensions
import _drawing_projection
import _drawing_sections
import _drawing_selection
import _section_axis
import _drawing_view_configuration
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
import draw_ch_rocker_arm_tl_oblique_jig_assembly as drawing
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _paths import CAD_ROOT
from machinist_exceptions import load_exceptions


# Default-format note text: about 2.8 mm a character and 4.5 mm a line on the
# farm's templates (draw_pd_paper_drive_assembly fits 68 characters in 0.192).
CHAR_M = 0.0029
LINE_M = drawing.NOTE_LINE_M
ROW_PITCH_M = 0.00615
ISO = math.sqrt(2.0 / 3.0)  # an isometric view's foreshortening


def _note_box(text: str, xy: tuple[float, float]) -> tuple[float, float, float, float]:
    lines = text.split("\n")
    width = max(len(line) for line in lines) * CHAR_M
    return xy[0], xy[1] - len(lines) * LINE_M, xy[0] + width, xy[1]


def _view_box(center, width_mm, height_mm, scale, margin=0.0):
    w = width_mm / 1000.0 * scale[0] / scale[1] / 2.0 + margin
    h = height_mm / 1000.0 * scale[0] / scale[1] / 2.0 + margin
    return center[0] - w, center[1] - h, center[0] + w, center[1] + h


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _inside_sheet(box) -> bool:
    left, bottom, right, top = drawing.SHEET_INNER_BORDER
    return (
        box[0] >= left
        and box[1] >= bottom
        and box[2] <= right
        and box[3] <= top
        and not _overlap(box, drawing.TITLE_BLOCK)
    )


# jig-r5 read the exploded isometric's outline (IView.GetOutline) at 127.4 x
# 113.2 mm at 1:8, against the 116.3 x 101.6 the -3 tree's extent projects:
# SolidWorks' outline is looser than the parts' silhouette. The layout tests
# grow the projected size by that measured ratio.
OUTLINE_GROWTH = (1.10, 1.12)


def _iso_size(lift_mm: float, plan_mm: float = 0.0) -> tuple[float, float]:
    (x0, x1), (y0, y1), (z0, z1) = spec.MODEL_EXTENT
    plan = (x1 - x0) + (y1 - y0) + plan_mm
    return (
        plan * math.cos(math.pi / 4.0) * OUTLINE_GROWTH[0],
        (plan * ISO / 2.0 + (z1 - z0 + lift_mm) * ISO) * OUTLINE_GROWTH[1],
    )


def _nut_bracket(dx: float = 0.0, dy: float = 0.0) -> list[tuple[float, float]]:
    feed = spec.leadscrew
    corners = feed.rect(
        spec.CARRIAGE_STATION + feed.NUT_BRACKET_X[0],
        spec.CARRIAGE_STATION + feed.NUT_BRACKET_X[1],
        feed.BLOCK_SIDE_LATERAL,
        feed.BLOCK_SIDE_LATERAL + feed.NUT_BRACKET_DEPTH,
    )
    return [(x + dx, y + dy) for x, y in corners]


def _exploded_part_points(stem, bounds, indices=None):
    """Conservative part-box corners under each actual occurrence transform."""
    points = []
    for index, (origin, rows) in enumerate(spec.PLACEMENTS[stem]):
        if indices is not None and index not in indices:
            continue
        shift = tuple(spec.explode_shift(spec.instance_name(stem, index), axis) for axis in "xyz")
        for x in bounds[0]:
            for y in bounds[1]:
                for z in bounds[2]:
                    local = (x, y, z)
                    points.append(tuple(
                        origin[axis] + shift[axis]
                        + sum(local[k] * rows[k][axis] for k in range(3))
                        for axis in range(3)
                    ))
    return points


def _capture_cluster_extent(support=None):
    retention, hardware = spec.retention, spec.retention_hardware
    cotter, wire = spec.pivot_cotter, spec.pivot_wire
    wire_controls = [
        point for segment in wire.installed_wire_segments() for point in segment
    ]
    wire_bounds = tuple(
        (min(p[axis] for p in wire_controls) - wire.WIRE_DIA / 2.0,
         max(p[axis] for p in wire_controls) + wire.WIRE_DIA / 2.0)
        for axis in range(3)
    )
    prong_outer = cotter.PRONG_GAP / 2.0 + cotter.PRONG_THICK
    screw = spec.cap_screw.DIMS
    boxes = {
        spec.PIVOT_BLOCK: (
            (spec.pivot_block.BLOCK_X0, spec.pivot_block.BLOCK_X1),
            (-retention.BLOCK_WING_HALF_WIDTH, retention.BLOCK_WING_HALF_WIDTH),
            (0.0, spec.pivot_block.BLOCK_HEIGHT),
        ),
        spec.PIVOT_PIN: (
            (-retention.PIN_FLANGE_DIA / 2.0, retention.PIN_FLANGE_DIA / 2.0),
            (-retention.PIN_FLANGE_DIA / 2.0, retention.PIN_FLANGE_DIA / 2.0),
            (0.0, spec.pivot_pin.OVERALL_LENGTH),
        ),
        spec.BEARING: (
            (-spec.bearing.OD / 2.0, spec.bearing.OD / 2.0),
            (0.0, spec.bearing.WIDTH),
            (-spec.bearing.OD / 2.0, spec.bearing.OD / 2.0),
        ),
        spec.PIVOT_CAP: (
            (-retention.CAP_WIDTH / 2.0, retention.CAP_WIDTH / 2.0),
            (-retention.CAP_LENGTH / 2.0, retention.CAP_LENGTH / 2.0),
            (0.0, retention.CAP_HEIGHT),
        ),
        spec.PIVOT_RETAINER: (
            (-retention.TOP_WASHER_OD / 2.0, retention.TOP_WASHER_OD / 2.0),
            (-retention.TOP_WASHER_OD / 2.0, retention.TOP_WASHER_OD / 2.0),
            (0.0, spec.pivot_retainer.THICKNESS),
        ),
        spec.PIVOT_CAP_SCREW: (
            (-screw.head_dia / 2.0, screw.head_dia / 2.0),
            (-screw.head_dia / 2.0, screw.head_dia / 2.0),
            (-screw.length, screw.head_h),
        ),
        spec.PIVOT_CLEVIS_PIN: (
            (-hardware.CLEVIS_HEAD_HEIGHT_MAX, hardware.CLEVIS_LENGTH_MAX),
            (-hardware.CLEVIS_HEAD_DIA_MAX / 2.0, hardware.CLEVIS_HEAD_DIA_MAX / 2.0),
            (-hardware.CLEVIS_HEAD_DIA_MAX / 2.0, hardware.CLEVIS_HEAD_DIA_MAX / 2.0),
        ),
        spec.PIVOT_COTTER: (
            (min(-cotter.EYE_OUTER_RADIUS, -prong_outer - cotter.SHORT_TAIL),
             max(cotter.EYE_OUTER_RADIUS, prong_outer + cotter.LONG_TAIL)),
            (-cotter.COTTER_WIDTH / 2.0, cotter.COTTER_WIDTH / 2.0),
            (cotter.EYE_CENTER - cotter.EYE_OUTER_RADIUS,
             cotter.PRONG_BEND + cotter.PRONG_THICK),
        ),
        spec.PIVOT_LOCK_WIRE: wire_bounds,
    }
    points = [
        point for stem, bounds in boxes.items()
        for point in _exploded_part_points(
            stem, bounds,
            None if support is None else range(
                support * (spec.QUANTITIES[stem] // 2),
                (support + 1) * (spec.QUANTITIES[stem] // 2),
            ),
        )
    ]
    return [(x, y) for x, y, _z in points], (
        min(z for _x, _y, z in points), max(z for _x, _y, z in points)
    )


def _cluster_extent(sheet: str):
    """A cluster's exploded plan points and Z range (mm): its families' plan
    outlines where the spec draws them, each slid as its explode slides it,
    and its lowest and highest exploded faces."""
    lift, feed = spec.explode_lift, spec.leadscrew
    radius = spec.flange_nut.FLANGE_DIA / 2.0
    if sheet == "RAIL BARS EXPLODED":
        points = [p for outline in spec.fixed_outlines().values() for p in outline]
        points += [
            (x + dx, y + dy)
            for x, y in spec.STUD_XY
            for dx in (-radius, radius)
            for dy in (-radius, radius)
        ]
        z = (
            spec.STUD_BOTTOM_Z + lift(spec.T_NUT),
            max(
                origin[2] + spec.carriage_screw.DIMS.head_h
                + lift(spec.CARRIAGE_SCREW)
                for origin, _rows in spec.CARRIAGE_SCREW_PLACEMENTS
            ),
        )
    elif sheet == "PIVOTCAPTUREEXPLODED":
        return _capture_cluster_extent()
    elif sheet == "LEADSCREW FEED EXPLODED":
        points = [p for outline in spec.feed_outlines().values() for p in outline]
        points += [
            (x + spec.explode_shift(spec.HANDWHEEL, "x"), y)
            for x, y in feed.rect(*feed.HANDWHEEL_BOX)
        ]
        points += _nut_bracket()
        points += _nut_bracket(dx=spec.explode_shift(spec.NUT_SCREW, "x"))
        points += _nut_bracket(dy=spec.explode_shift(spec.BLOCK_SCREW, "y"))
        # Rail 1's pivot block, shown for the nut bracket to mate to.
        block = spec.pivot_block
        points += feed.rect(
            spec.CARRIAGE_STATION + block.BLOCK_X0,
            spec.CARRIAGE_STATION + block.BLOCK_X1,
            -spec.retention.BLOCK_WING_HALF_WIDTH,
            spec.retention.BLOCK_WING_HALF_WIDTH,
        )
        z = (
            -feed.BAR_SCREW_LENGTH_MM + lift(spec.BRACKET_SCREW),
            max(
                feed.NUT_BRACKET_TOP_Z + lift(spec.NUT_BRACKET),
                spec.trammel.PIVOT_BLOCK_TOP_Z + lift(spec.PIVOT_BLOCK),
            ),
        )
    else:
        assert sheet == "CARRIER EXPLODED"
        points = [
            spec.POSE.to_machine(p)
            for outline in spec.CARRIER_OUTLINES.values()
            for p in outline
        ]
        z = (
            spec.HUB_HEAD_BOTTOM_Z + lift(spec.HUB_PIN),
            spec.MODEL_EXTENT[2][1] + lift(spec.LEVER_SCREW),
        )
    return points, z


def _cluster_outline(cluster, center=(0.2, 0.15), *, scale=None):
    """The estimated native outline at an initial or fitted scale (sheet metres)."""
    points, (z0, z1) = _cluster_extent(cluster.sheet)
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    plan = (max(xs) - min(xs)) + (max(ys) - min(ys))
    width = plan * math.cos(math.pi / 4.0) * OUTLINE_GROWTH[0]
    height = (plan * ISO / 2.0 + (z1 - z0) * ISO) * OUTLINE_GROWTH[1]
    return _view_box(center, width, height, scale or cluster.scale)


def test_sheets_are_landscape_with_their_scales() -> None:
    assert len(drawing.SHEET_NAMES) == len(set(drawing.SHEET_NAMES))
    assert drawing.SHEET_NAMES[6:11] == (
        drawing.STEPS_SHEET, drawing.STEPS_CONTINUED_SHEET,
        drawing.CARTRIDGE_SHEET, drawing.TOP_CAPTURE_SHEET, drawing.CAPTURE_SHEET,
    )
    assert len(drawing.SHEET_NAMES) == 11
    assert set(drawing.SHEET_LAYOUTS.values()) == {drawing.DrawingLayout.LANDSCAPE}
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert drawing.SHEET_SCALES[drawing.ASSEMBLED_SHEET] == drawing.ASSEMBLED_SCALE
    assert drawing.SHEET_SCALES[drawing.BOM_SHEET] == drawing.REFERENCE_SCALE
    assert drawing.SHEET_SCALES[drawing.CAPTURE_SHEET] == drawing.ISOMETRIC_SCALE
    assert drawing.SHEET_SCALES[drawing.STEPS_SHEET] == drawing.NOTES_REFERENCE_SCALE
    assert (
        drawing.SHEET_SCALES[drawing.STEPS_CONTINUED_SHEET]
        == drawing.NOTES_REFERENCE_SCALE
    )
    assert drawing.SHEET_SCALES[drawing.CARTRIDGE_SHEET] == drawing.NOTES_REFERENCE_SCALE
    assert drawing.SHEET_SCALES[drawing.TOP_CAPTURE_SHEET] == drawing.NOTES_REFERENCE_SCALE
    assert all(
        drawing.SHEET_SCALES[cluster.sheet] in drawing.CLUSTER_SCALE_LADDER
        for cluster in drawing.CLUSTERS
    )
    assert drawing.SHEET_SCALE == drawing.ASSEMBLED_SCALE
    assert drawing.SPEC.source_kind == "assembly"


def test_fitted_cluster_scales_reach_finalize_in_sheet_order() -> None:
    fitted = {cluster.sheet: (1.0, 8.0) for cluster in drawing.CLUSTERS}
    scales = drawing.package_sheet_scales(fitted)
    assert tuple(scales) == drawing.SHEET_NAMES
    assert all(scales[sheet] == (1.0, 8.0) for sheet in fitted)
    assert scales["BILL OF MATERIALS"] == drawing.REFERENCE_SCALE
    with pytest.raises(ValueError):
        drawing.package_sheet_scales({"RAIL BARS EXPLODED": (1.0, 5.0)})


def test_clusters_partition_the_bom() -> None:
    clustered = [stem for cluster in drawing.CLUSTERS for stem in cluster.stems]
    assert sorted(clustered) == sorted(spec.BOM_ORDER)
    assert len(clustered) == len(set(clustered))
    for cluster in drawing.CLUSTERS:
        # Each sheet balloons in item order.
        assert list(cluster.stems) == [s for s in spec.BOM_ORDER if s in cluster.stems]
    # The screws review r4 could not tell apart share the feed's sheet.
    feed = {cluster.sheet: cluster for cluster in drawing.CLUSTERS}[
        "LEADSCREW FEED EXPLODED"
    ]
    for stem in (spec.BRACKET_SCREW, spec.PILLOW_BLOCK_SCREW, spec.NUT_SCREW):
        assert stem in feed.stems
    # Review full-bought: the feed sheet shows the nut bracket on its pivot
    # block (rail 1's), ballooned only on the rail bars' sheet.
    assert feed.context == (spec.instance_name(spec.PIVOT_BLOCK, 0),)
    assert spec.lock_parent(spec.NUT_BRACKET, 0) in feed.context
    capture = next(
        cluster for cluster in drawing.CLUSTERS
        if cluster.sheet == "PIVOTCAPTUREEXPLODED"
    )
    assert capture.context == tuple(
        spec.instance_name(spec.PIVOT_BLOCK, index) for index in (0, 1)
    )
    assert set(capture.stems) == {
        spec.PIVOT_PIN, spec.BEARING, spec.PIVOT_CAP, spec.PIVOT_RETAINER,
        spec.PIVOT_CAP_SCREW, spec.PIVOT_CLEVIS_PIN, spec.PIVOT_COTTER,
        spec.PIVOT_LOCK_WIRE,
    }
    assert all(
        not cluster.context for cluster in drawing.CLUSTERS
        if cluster not in (feed, capture)
    )
    inventory = {
        spec.instance_name(stem, index)
        for stem, count in spec.QUANTITIES.items() for index in range(count)
    }
    assert all(set(cluster.context) <= inventory for cluster in drawing.CLUSTERS)


def test_capture_support_views_partition_the_exact_occurrences() -> None:
    capture = next(
        cluster for cluster in drawing.CLUSTERS
        if cluster.sheet == drawing.PIVOT_CAPTURE_SHEET
    )
    supports = [
        drawing.capture_support_instances(capture, support) for support in (0, 1)
    ]
    assert not supports[0] & supports[1]
    assert supports[0] | supports[1] == {
        spec.instance_name(stem, index)
        for stem in (*capture.stems, spec.PIVOT_BLOCK)
        for index in range(spec.QUANTITIES[stem])
    }
    for support, instances in enumerate(supports):
        block = spec.instance_name(spec.PIVOT_BLOCK, support)
        assert block in instances
        for stem in capture.stems:
            assert stem not in instances  # a family would show both supports
            for index in range(spec.QUANTITIES[stem]):
                name = spec.instance_name(stem, index)
                if name not in instances:
                    continue
                parent = spec.lock_parent(stem, index)
                while parent != block:
                    assert parent in instances
                    parent_stem, parent_index = parent.rsplit("-", 1)
                    parent = spec.lock_parent(parent_stem, int(parent_index) - 1)


def test_instruction_groups_print_in_bench_feed_cap_carrier_order() -> None:
    bench = "\n".join(
        (drawing.CARTRIDGE_LAYOUT.steps, drawing.CARTRIDGE_LAYOUT.continued)
    )
    caps = "\n".join(
        (drawing.TOP_CAPTURE_LAYOUT.steps, drawing.TOP_CAPTURE_LAYOUT.continued)
    )
    assert bench.startswith("CARTRIDGE BENCH WORK: C2A, C1-C2\nC2A.")
    labels = ("C2A.", "C1.", "C2.", "FEED FIT-UP CHECKS (F1-F2):", "F1.", "F2.")
    assert [bench.index(label) for label in labels] == sorted(
        bench.index(label) for label in labels
    )
    assert "C3." not in bench and "C4." not in bench
    assert caps.startswith("CAP SEATING AND WIRING: C3-C3C\nC3.")
    labels = (
        "C3.", "C3A.", "C3B.", "C3C.",
        "CARRIER AND TOP RETAINERS (C4-C5D):", "C4.", "C4A.",
        "C5.", "C5A.", "C5B.", "C5C.", "C5D.",
    )
    assert [caps.index(label) for label in labels] == sorted(
        caps.index(label) for label in labels
    )


_PROCEDURE_LAYOUTS = {
    9: drawing.CARTRIDGE_LAYOUT,
    10: drawing.TOP_CAPTURE_LAYOUT,
    spec.OPERATION_SHEET_NUMBER: drawing.CAPTURE_LAYOUT,
}


def _sheet_zone(x: float, y: float) -> str:
    """The template's zone (row D-A from the top, column 4-1 from the left)."""
    width, height = drawing._TEMPLATE.width_m, drawing._TEMPLATE.height_m
    return "DCBA"[int((height - y) / (height / 4.0))] + str(4 - int(x / (width / 4.0)))


def _printed_blocks(layout):
    """Each printed text block with its top-left corner."""
    return (
        (layout.steps, drawing.STEPS_XY),
        (layout.continued, drawing.STEPS_CONTINUED_XY),
        (layout.checks, layout.checks_xy),
    )


def test_procedure_pointers_name_the_sheet_and_zone_each_heading_prints_in() -> None:
    assert [
        drawing.SHEET_NAMES.index(sheet) + 1
        for sheet in (drawing.CARTRIDGE_SHEET, drawing.TOP_CAPTURE_SHEET, drawing.CAPTURE_SHEET)
    ] == list(_PROCEDURE_LAYOUTS)
    for label, (sheet, zone) in spec.PROCEDURE_PLACES.items():
        if label in ("A-A", "B-B"):
            assert sheet == drawing.SHEET_NAMES.index(drawing.PIVOT_CAPTURE_SHEET) + 1
            x0, y0, x1, y1 = drawing.CAPTURE_VIEW_REGIONS[2 if label == "A-A" else 3]
            assert _sheet_zone((x0 + x1) / 2.0, (y0 + y1) / 2.0) == zone, label
            continue
        found = [
            _sheet_zone(x, y - (index + 0.5) * drawing.NOTE_LINE_M)
            for text, (x, y) in _printed_blocks(_PROCEDURE_LAYOUTS[sheet])
            for index, line in enumerate(text.split("\n"))
            if line.startswith(f"{label}. ")
        ]
        assert found == [zone], label
    # The main sequence points at every procedure it sends the fitter to.
    for step, pointers in (
        ("2.", ("HD1",)), ("4.", ("C2A",)), ("7C.", ("F1",)), ("8.", ("F2",)),
        ("9.", ("C4",)), ("13A.", ("C6", "HD1")), ("13B.", ("HD2",)),
    ):
        text = next(line for line in spec.ASSEMBLY_STEPS if line.startswith(step))
        for label in pointers:
            assert spec._at(label) in text, (step, label)


def test_procedures_print_as_short_sub_steps_under_their_headings() -> None:
    label = re.compile(r"[A-Z]+\d+[A-Z]?(?:\.\d+)? |[A-Z]+\d+[A-Z]?\. ")
    for layout in _PROCEDURE_LAYOUTS.values():
        for text, _xy in _printed_blocks(layout):
            block = []
            for line in [*text.split("\n"), ""]:
                if line and not label.match(line) and line.startswith(" "):
                    block.append(line)
                    continue
                # One action and its acceptance: three printed lines at most.
                assert len(block) <= 3, block
                if block and drawing._SUB_STEP.fullmatch(block[0].split(" ", 1)[0]):
                    hang = " " * (len(block[0].split(" ", 1)[0]) + 1)
                    assert all(row.startswith(hang) and row[len(hang)] != " " for row in block[1:])
                block = [line] if line and not line.endswith(":") else []


def test_sub_steps_hang_under_their_label_and_stay_in_their_group() -> None:
    text = drawing._wrapped(
        ("C4. GROUP HEADING:", "C4.1 " + "WORD " * 20, "C4A. NEXT:", "C4A.1 SHORT.",
         "C5. OTHER.", "C5A.1 SEE C4 (SHEET 10, ZONE C4) AND ITEM 3."),
        width=40, spaced=True,
    )
    assert text.split("\n") == [
        "C4. GROUP HEADING:",
        "C4.1 WORD WORD WORD WORD WORD WORD WORD",
        "     WORD WORD WORD WORD WORD WORD WORD",
        "     WORD WORD WORD WORD WORD WORD",
        "C4A. NEXT:",
        "C4A.1 SHORT.",
        "",
        "C5. OTHER.",
        "C5A.1 SEE C4 (SHEET 10, ZONE C4) AND",
        "      ITEM 3.",
    ]


def test_instruction_heading_moves_with_first_step_at_column_boundary(monkeypatch) -> None:
    # Three lines fit on the left, but the four-line group does not. Without
    # heading co-location, FEED CHECKS would be left behind its first step.
    monkeypatch.setattr(
        drawing, "STEPS_FLOOR",
        drawing.STEPS_XY[1] - 3.5 * drawing.NOTE_LINE_M,
    )
    layout = drawing.steps_sheet_layout(
        ("1. INSTALL.", "FEED CHECKS:", "F1. CHECK FEED."),
        (),
        heading="BUILD ORDER",
    )
    assert layout.steps.splitlines() == ["BUILD ORDER", "1. INSTALL."]
    assert layout.continued.splitlines() == ["FEED CHECKS:", "F1. CHECK FEED."]


def test_exploded_wire_stays_near_its_heads_and_apart_from_the_cotter() -> None:
    right, up, _sight = spec.VIEW_AXES[spec.ISOMETRIC_VIEW]
    ratio = 1.0 / 4000.0  # the reviewed capture sheet's 1:4 paper projection

    def project(stem, point, index=0):
        origin, rows = spec.PLACEMENTS[stem][index]
        world = tuple(
            origin[axis] + spec.explode_shift(spec.instance_name(stem, index), "xyz"[axis])
            + sum(point[k] * rows[k][axis] for k in range(3))
            for axis in range(3)
        )
        return tuple(sum(p * a for p, a in zip(world, axis)) * ratio
                     for axis in (right, up))

    wire = spec.pivot_wire
    wire_points = [
        project(spec.PIVOT_LOCK_WIRE, point)
        for segment in wire.installed_wire_segments() for point in segment
    ]
    cotter = spec.pivot_cotter
    cotter_points = [
        project(spec.PIVOT_COTTER, (x, y, z))
        for x in (cotter.INSTALLED_X_MIN, cotter.INSTALLED_X_MAX)
        for y in (-cotter.INSTALLED_Y_HALF_WIDTH, cotter.INSTALLED_Y_HALF_WIDTH)
        for z in (cotter.INSTALLED_Z_MIN, cotter.INSTALLED_Z_MAX)
    ]
    # Cf3's two bodies met at their leader tips. Their projected envelopes now
    # have daylight, including the formed wire's whole tube radius.
    assert max(p[0] for p in wire_points) + wire.WIRE_DIA / 2.0 * ratio < min(
        p[0] for p in cotter_points
    )
    wire_center = project(spec.PIVOT_LOCK_WIRE, (0.0, 0.0, wire.WIRE_AXIS_Z))
    heads = [
        project(spec.PIVOT_CAP_SCREW, (0.0, 0.0, wire.WIRE_AXIS_Z), index)
        for index in (0, 2)
    ]
    head_center = tuple(sum(p[axis] for p in heads) / 2.0 for axis in (0, 1))
    assert wire_center[1] > head_center[1]
    assert math.dist(wire_center, head_center) < drawing.BALLOON_RADIUS



def test_exploded_captions_fit_their_text_region() -> None:
    for cluster in drawing.CLUSTERS:
        if cluster.sheet == drawing.PIVOT_CAPTURE_SHEET:
            continue  # Sheet 4's four views have independent measured fields.
        scale = drawing.cluster_ring_scale(
            _cluster_outline(cluster), cluster.scale, label=cluster.sheet
        )
        caption = drawing.exploded_caption(cluster, scale)
        assert max(map(len, caption.split("\n"))) <= drawing.EXPLODED_CAPTION_WIDTH
        assert _inside_sheet(_note_box(caption, drawing.EXPLODED_CAPTION_XY))


def test_sheet_text_wraps_within_its_layout_width() -> None:
    # Split only between complete labelled steps or sub-steps.
    steps = drawing.STEPS_LAYOUT
    if steps.continued:
        label = steps.continued.split(". ", 1)[0]
        assert drawing._STEP_LABEL.fullmatch(label)
    texts = [
        (drawing.ASSEMBLED_CAPTION, drawing.CAPTION_WIDTH),
        (drawing.ALIGNMENT_NOTE, drawing.ALIGNMENT_WIDTH),
    ]
    for layout in (
        steps, drawing.STEPS_CONTINUED_LAYOUT, drawing.CARTRIDGE_LAYOUT,
        drawing.TOP_CAPTURE_LAYOUT, drawing.CAPTURE_LAYOUT,
    ):
        for text in (layout.steps, layout.continued, layout.checks):
            if text:
                texts.append((text, drawing.STEPS_LINE_WIDTH))
    for text, width in texts:
        assert max(len(line) for line in text.split("\n")) <= width
    # Each alignment station prints whole on one line.
    for line in spec.ALIGNMENT_NOTE_LINES[1:]:
        assert line in drawing.ALIGNMENT_NOTE.split("\n")


def test_a_blank_line_parts_each_top_level_step() -> None:
    text = drawing._wrapped(
        ("1. FIRST.", "7A. SUB A.", "7B. SUB B.", "GROUP:", "C3. THIRD.",
         "C3A. SUB.", "C4. FOURTH.", "CHECK: LOOSE."),
        width=drawing.STEPS_LINE_WIDTH, heading="HEAD", spaced=True,
    )
    assert text.split("\n") == [
        "HEAD", "1. FIRST.", "", "7A. SUB A.", "7B. SUB B.", "", "GROUP:",
        "C3. THIRD.", "C3A. SUB.", "", "C4. FOURTH.", "CHECK: LOOSE.",
    ]


def test_sequence_continues_whole_with_step_13_over_its_checks() -> None:
    first, cont = drawing.STEPS_LAYOUT, drawing.STEPS_CONTINUED_LAYOUT
    heading = f"{drawing.STEPS_HEADING} (CONT.)"
    assert not first.checks
    assert cont.steps.startswith(f"{heading}\n13A.")
    # 13C cites "THE CHECKS BELOW": they print under step 13, not beside it.
    assert cont.checks_xy[0] == drawing.STEPS_XY[0]
    assert cont.checks_xy[1] < drawing.STEPS_XY[1] - _lines(cont.steps) * LINE_M
    printed = "\n".join((first.steps, first.continued, cont.steps, cont.checks))
    printed = printed.removeprefix(drawing.STEPS_HEADING).replace(heading, "")
    assert printed.split() == " ".join(
        (*spec.ASSEMBLY_STEPS, *spec.ASSEMBLY_CHECKS)
    ).split()


def test_assembled_sheet_regions_fit_apart() -> None:
    (x0, x1), (y0, y1), (z0, z1) = spec.MODEL_EXTENT
    plan = _view_box(drawing.PLAN_CENTER, x1 - x0, y1 - y0, drawing.ASSEMBLED_SCALE)
    elevation = _view_box(
        drawing.ELEVATION_CENTER, x1 - x0, z1 - z0, drawing.ASSEMBLED_SCALE
    )
    caption = _note_box(drawing.ASSEMBLED_CAPTION, drawing.CAPTION_XY)
    alignment = _note_box(drawing.ALIGNMENT_NOTE, drawing.ALIGNMENT_XY)
    plan_title = _note_box(spec.PLAN_VIEW_LABEL, drawing.PLAN_LABEL_XY)
    elevation_title = _note_box(spec.ELEVATION_VIEW_LABEL, drawing.ELEVATION_LABEL_XY)
    regions = (plan, elevation, caption, alignment, plan_title, elevation_title)
    assert all(_inside_sheet(box) for box in regions)
    for index, a in enumerate(regions):
        for b in regions[index + 1 :]:
            assert not _overlap(a, b)
    # Third-angle: the plan above the elevation on one vertical.
    assert drawing.PLAN_CENTER[0] == drawing.ELEVATION_CENTER[0]
    assert plan[1] > elevation[3]
    # Each title centred under its own view.
    for title, view in ((plan_title, plan), (elevation_title, elevation)):
        assert (title[0] + title[2]) / 2.0 == pytest.approx((view[0] + view[2]) / 2.0)
        assert title[3] < view[1]
    assert plan_title[1] > elevation[3]


def _plan_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet metres of a machine plan point, the plan centred on the extent."""
    (x0, x1), (y0, y1), _z = spec.MODEL_EXTENT
    ratio = drawing.ASSEMBLED_SCALE[0] / drawing.ASSEMBLED_SCALE[1] / 1000.0
    return (
        drawing.PLAN_CENTER[0] + (x_mm - (x0 + x1) / 2.0) * ratio,
        drawing.PLAN_CENTER[1] + (y_mm - (y0 + y1) / 2.0) * ratio,
    )


def _captured_capture_callout(label, note_xy=None):
    """Native 2f1b2c01 capture sheet: actual PDF rows and registered leader."""
    from _layout_geometry import AnnotationGeometry, Box, Segment

    # PDF SHA256 33298ca5...; native JSON 869af329... . These measured
    # Century Gothic rows retain their printed heights, not nominal font boxes.
    measurements = {
        "C5A FLAT PIN END": (
            (0.305, 0.216),
            ((0.3051439, 0.2135337, 0.3278642, 0.215571),
             (0.3050640, 0.2105337, 0.3360759, 0.212571)),
            (0.3362056, 0.2122206, 0.3209239, 0.181),
        ),
        "C3A CAP / BLOCK LAND": (
            (0.279, 0.2235),
            ((0.2791439, 0.2208203, 0.3102947, 0.223071),
             (0.2790853, 0.2180337, 0.2908703, 0.220071)),
            (0.3107404, 0.2193691, 0.3875625, 0.2419),
        ),
        "C5B COTTER EYE / PRONGS": (
            (0.282, 0.257),
            ((0.2821440, 0.2543203, 0.3165099, 0.256571),
             (0.2820853, 0.2515337, 0.2927014, 0.253571),
             (0.2820347, 0.2485337, 0.3213904, 0.250571)),
            (0.281432, 0.2557663, 0.25535, 0.2402265),
        ),
    }
    position, rows, registered = measurements[label]
    dx, dy = (0.0, 0.0) if note_xy is None else (
        note_xy[0] - position[0], note_xy[1] - position[1],
    )
    leader = Segment(
        registered[0] + dx, registered[1] + dy,
        registered[2], registered[3], "leader",
    )
    # Translate only the native junction offset. The physical landing and
    # measured 3.556 mm arrow length stay fixed; this is not native qualification.
    length = math.hypot(leader.x0 - leader.x1, leader.y0 - leader.y1)
    arrow = Segment(
        leader.x1, leader.y1,
        leader.x1 + 0.003556 * (leader.x0 - leader.x1) / length,
        leader.y1 + 0.003556 * (leader.y0 - leader.y1) / length, "arrow",
    )
    return AnnotationGeometry(
        label=label, kind="note", owner="captured TL-00",
        text_boxes=tuple(Box(row[0] + dx, row[1] + dy, row[2] + dx, row[3] + dy) for row in rows),
        segments=(leader, arrow),
    )


def _captured_capture_sheet(*annotations):
    from _layout_geometry import DrawableRegion, SheetGeometry

    return SheetGeometry(
        name=drawing.PIVOT_CAPTURE_SHEET, width=0.4318, height=0.2794,
        region=DrawableRegion.whole_sheet(0.4318, 0.2794), annotations=annotations,
    )


def _captured_cotter_glyph(note_xy):
    # Native IDisplayData: three measured rows, 39.5611 mm maximum width,
    # lower-left 9 mm below the annotation point, upper edge 1 mm below it.
    x, y = note_xy
    return (x, y - 0.009, x + 0.0395611, y - 0.001)


def test_capture_measured_callout_rows_clear_cap_and_relocated_cotter():
    from _layout_audit import ROW_PITCH_HEIGHTS, find_merged_blocks, text_height

    flat, cap, cotter = "C5A FLAT PIN END", "C3A CAP / BLOCK LAND", "C5B COTTER EYE / PRONGS"
    before = [_captured_capture_callout(label) for label in (flat, cap, cotter)]
    baseline = find_merged_blocks(_captured_capture_sheet(*before))
    assert any({finding.a, finding.b} == {flat, cap} for finding in baseline)
    authored = {reading.text.splitlines()[0]: reading.text_xy for reading in drawing.capture_readings()}
    after = [
        _captured_capture_callout(label, authored[label]) for label in (flat, cap, cotter)
    ]
    assert find_merged_blocks(_captured_capture_sheet(*after)) == []
    for old, moved in zip(before, after, strict=True):
        assert [box.height for box in moved.text_boxes] == pytest.approx(
            [box.height for box in old.text_boxes], abs=1e-12,
        )
    for other in (after[1], after[2]):
        a, b = after[0].text_boxes[0], other.text_boxes[0]
        for box in after[0].text_boxes[1:]:
            a = a.union(box)
        for box in other.text_boxes[1:]:
            b = b.union(box)
        # C5A now stands in the right column, beside rather than above them.
        gap = max(a.ymin - b.ymax, b.ymin - a.ymax, a.xmin - b.xmax, b.xmin - a.xmax)
        assert gap >= ROW_PITCH_HEIGHTS * min(text_height(after[0]), text_height(other))


# Run 20261027T154139713Z-566cad5ab (69818ca95), sheet 4: the right column's
# C5A (three rows) and C4 MOUTH blocks as printed (PDF glyph rows) and their
# native leaders (layout-audit JSON DetailItem374/370), at the authored anchors.
_NATIVE_RIGHT_COLUMN = {
    "C5A FLAT PIN END": (
        (0.365, 0.2025),
        ((0.3651439, 0.2000337, 0.3878641, 0.2020710),
         (0.3650640, 0.1970337, 0.3960759, 0.1990710),
         (0.3652320, 0.1940337, 0.4043818, 0.1960710)),
        (0.3640972, 0.2014001, 0.313, 0.178),
    ),
    "C4 MOUTH / FLAT LAND": (
        (0.365, 0.1908),
        ((0.3651439, 0.1881203, 0.3948891, 0.1903710),
         (0.3652319, 0.1853337, 0.3966403, 0.1873710),
         (0.3650800, 0.1821577, 0.3899821, 0.1843710)),
        (0.3640903, 0.1899625, 0.3181, 0.1698391),
    ),
}


def test_capture_native_three_row_c5a_clears_the_c4_mouth_block_below():
    from _layout_audit import (
        ROW_PITCH_HEIGHTS, find_leader_through_text, find_merged_blocks, text_height,
    )
    from _layout_geometry import AnnotationGeometry, Box, Segment

    authored = {reading.text_xy: reading.text for reading in drawing.capture_readings()}
    blocks = []
    for label, (anchor, rows, leader) in _NATIVE_RIGHT_COLUMN.items():
        # The snapshot stands where the recipe still authors the block, row for row.
        assert authored[anchor].splitlines()[0] == label
        assert len(authored[anchor].splitlines()) == len(rows)
        blocks.append(AnnotationGeometry(
            label=label, kind="note", owner="Section View A-A",
            text_boxes=tuple(Box(*row) for row in rows),
            segments=(Segment(*leader, "leader"),),
        ))
    sheet = _captured_capture_sheet(*blocks)
    assert find_merged_blocks(sheet) == []
    assert find_leader_through_text(sheet) == []
    c5a, c4 = blocks
    gap = min(box.ymin for box in c5a.text_boxes) - max(box.ymax for box in c4.text_boxes)
    assert gap >= ROW_PITCH_HEIGHTS * min(text_height(c5a), text_height(c4))


def test_capture_measured_cotter_leader_clears_both_native_cut_lines():
    from _layout_audit import find_leader_across_lines
    from _layout_geometry import AnnotationGeometry, Segment

    cuts = tuple(
        AnnotationGeometry(
            label=f"section-line {letter}", kind="section-line", owner="Drawing View9",
            segments=(Segment(*coordinates, "line"),),
        )
        for letter, coordinates in (
            ("A", (0.2346284, 0.2403916, 0.2671284, 0.2403916)),
            ("B", (0.2659427, 0.2497668, 0.2337767, 0.2451200)),
        )
    )
    label = "C5B COTTER EYE / PRONGS"
    old = _captured_capture_callout(label)
    baseline = find_leader_across_lines(_captured_capture_sheet(old, *cuts))
    assert any(
        finding.kind == "leader-crosses-section-line" and finding.b == "section-line A"
        for finding in baseline
    )
    reading = next(reading for reading in drawing.capture_readings() if reading.text.startswith(label))
    candidate = _captured_capture_callout(label, reading.text_xy)
    assert find_leader_across_lines(_captured_capture_sheet(candidate, *cuts)) == []


def test_capture_measured_cotter_air_rejects_neighboring_leaders_caption_and_model():
    from _layout_geometry import Box, Segment, segment_box_distance

    authored = {reading.text.splitlines()[0]: reading.text_xy for reading in drawing.capture_readings()}
    # Retired routes (old C5A at (0.305, 0.216), old C4A junction) are only the
    # negative controls; the current-layout checks use run 11's native leaders
    # (layout-audit JSON DetailItem374 C5A, DetailItem375 C4A, DetailItem377 C5B).
    flat = _captured_capture_callout("C5A FLAT PIN END")
    cross_hole = Segment(0.2545473, 0.2122206, 0.3184239, 0.17925, "leader")
    flat_now = Segment(*_NATIVE_RIGHT_COLUMN["C5A FLAT PIN END"][2], "leader")
    cross_hole_now = Segment(0.2545473, 0.2103143, 0.308, 0.1745, "leader")
    cotter_now = Segment(0.287412, 0.2037175, 0.25535, 0.2402265, "leader")
    locator_caption = (0.224, 0.2154743, 0.2705646, 0.2189743)
    section_a = (0.2924833, 0.1402120, 0.3495167, 0.1897880)
    assert drawing._segment_crosses_box(cross_hole, _captured_cotter_glyph((0.280, 0.205)), inset=0.0)
    assert drawing._segment_crosses_box(flat.segments[0], _captured_cotter_glyph((0.291, 0.205)), inset=0.0)
    assert drawing._capture_overlap(_captured_cotter_glyph((0.250, 0.219)), locator_caption)
    assert drawing._capture_overlap(_captured_cotter_glyph((0.288, 0.198)), section_a)
    glyph = _captured_cotter_glyph(authored["C5B COTTER EYE / PRONGS"])
    assert drawing._capture_inside(glyph, drawing.CAPTURE_READING_REGION)
    for neighbor in (cross_hole_now, flat_now):
        assert not drawing._segment_crosses_box(neighbor, glyph, inset=0.0)
        assert segment_box_distance(neighbor, Box(*glyph)) > 0.0
    for obstacle in (locator_caption, section_a):
        assert not drawing._capture_overlap(glyph, obstacle)
        assert not drawing._segment_crosses_box(cotter_now, obstacle, inset=0.0)
    leaders = [
        LeaderSegment(label=label, kind="note", x0=segment.x0, y0=segment.y0,
                      x1=segment.x1, y1=segment.y1)
        for label, segment in (
            ("cotter", cotter_now), ("flat pin", flat_now), ("cross-hole", cross_hole_now),
        )
    ]
    assert find_leader_leader_crossings(leaders) == []


def _captured_left_capture_column(moved: bool, mouth_junction=None):
    """Native b49db6fb (#1949 proof, source e926afd0c) left capture column:
    measured PDF rows and COM leaders at the notes' then (0.224, y) points.
    ``moved`` translates each note's rows and leader junction to its authored
    point; the physical landing stays. A replay budget, not native proof."""
    from _layout_geometry import AnnotationGeometry, Box, Segment

    measured = {
        "C4A UPPER CROSS-HOLE EDGE": (
            0.216,
            ((0.224144, 0.2135337, 0.263304, 0.215571),
             (0.2242293, 0.2105337, 0.2544796, 0.212571)),
            (0.2545473, 0.2122206, 0.3184239, 0.17925),
        ),
        "C4 MOUTH / FLAT LAND": (
            0.199,
            ((0.224144, 0.1963203, 0.2538891, 0.198571),
             (0.2242319, 0.1935337, 0.2556403, 0.195571),
             (0.22408, 0.1903577, 0.2489821, 0.192571)),
            (0.2491779, 0.1920641, 0.3183739, 0.1769195),
        ),
        "C5B HEAD / SHANK REGIONS": (
            0.190,
            ((0.224144, 0.1873203, 0.2605988, 0.189571),
             (0.2240853, 0.1845337, 0.2507479, 0.186571)),
            (0.2509223, 0.1860093, 0.3136492, 0.1761163),
        ),
        "C4 COMMON SHANK / LAND": (
            0.184,
            ((0.224144, 0.1813203, 0.261128, 0.183571),
             (0.2240347, 0.1785337, 0.2559832, 0.180571),
             (0.22408, 0.1753577, 0.2489821, 0.177571)),
            (0.2491779, 0.1768139, 0.3165864, 0.17475),
        ),
    }
    authored = {
        reading.text.splitlines()[0]: reading.text_xy
        for reading in drawing.capture_readings()
        if reading.text_xy[0] == 0.224
    }
    notes = [
        AnnotationGeometry(
            label="locator caption", kind="note", owner="captured TL-00",
            text_boxes=(Box(0.224112, 0.2164082, 0.2704386, 0.2199736),),
        )
    ]
    for label, (native_y, rows, leader) in measured.items():
        dy = authored[label][1] - native_y if moved else 0.0
        x0, y0 = (mouth_junction if label.startswith("C4 MOUTH") and mouth_junction
                  else leader[:2])
        notes.append(AnnotationGeometry(
            label=label, kind="note", owner="captured TL-00",
            text_boxes=tuple(Box(row[0], row[1] + dy, row[2], row[3] + dy) for row in rows),
            segments=(Segment(x0, y0 + dy, leader[2], leader[3], "leader"),),
        ))
    return notes


def test_capture_left_column_mouth_leader_clears_c5b_head_text():
    from _layout_audit import (
        find_leader_through_text, find_merged_blocks, find_text_clearance,
        find_text_separation,
    )
    from _layout_geometry import segment_box_distance

    # 2056e3344's native leaf: the mouth leader left (249.3,191.8) mm and ran
    # 0.78 mm through C5B's first row; #1949's leaf missed it by 0.04 mm.
    struck = _captured_capture_sheet(*_captured_left_capture_column(False, (0.2493, 0.1918)))
    assert any(
        (finding.kind, finding.a.startswith("C4 MOUTH"), finding.b) ==
        ("leader-through-text", True, "C5B HEAD / SHANK REGIONS")
        for finding in find_leader_through_text(struck)
    )
    assert find_text_clearance(struck)
    for junction in (None, (0.2493, 0.1918)):
        notes = _captured_left_capture_column(True, junction)
        sheet = _captured_capture_sheet(*notes)
        assert find_leader_through_text(sheet) == []
        assert find_text_clearance(sheet) == []
        assert find_merged_blocks(sheet) == []
        assert find_text_separation(sheet) == []
        by_label = {note.label: note for note in notes}
        mouth = by_label["C4 MOUTH / FLAT LAND"].segments[0]
        assert segment_box_distance(mouth, by_label["C5B HEAD / SHANK REGIONS"].text_boxes[0]) > 0.002
        leaders = [
            LeaderSegment(label=note.label, kind="note", x0=s.x0, y0=s.y0, x1=s.x1, y1=s.y1)
            for note in notes for s in note.segments
        ]
        assert find_leader_leader_crossings(leaders) == []


def test_plan_tags_stand_apart_inside_the_sheet() -> None:
    boxes = [_note_box(tag.text, _plan_xy(*tag.text_xy)) for tag in spec.PLAN_TAGS]
    others = (
        _note_box(drawing.ASSEMBLED_CAPTION, drawing.CAPTION_XY),
        _note_box(drawing.ALIGNMENT_NOTE, drawing.ALIGNMENT_XY),
        _note_box(spec.PLAN_VIEW_LABEL, drawing.PLAN_LABEL_XY),
    )
    assert all(_inside_sheet(box) for box in boxes)
    for index, a in enumerate(boxes):
        for b in boxes[index + 1 :] + list(others):
            assert not _overlap(a, b)
    # Two tags one above the other stand a row pitch apart, or the layout
    # audit reads them as one block (6.15 mm at their text height, jig-r7).
    for index, a in enumerate(boxes):
        for b in boxes[index + 1 :]:
            if a[0] < b[2] and b[0] < a[2]:
                assert max(b[1] - a[3], a[1] - b[3]) >= ROW_PITCH_M
    # No tag's text sits on the carrier (its plan outline at the pose).
    corners = [spec.POSE.to_machine(p) for p in spec.CARRIER_OUTLINES["carrier"]]
    (cx0, cy0), (cx1, cy1) = (
        _plan_xy(min(x for x, _ in corners), min(y for _, y in corners)),
        _plan_xy(max(x for x, _ in corners), max(y for _, y in corners)),
    )
    for box in boxes:
        assert not _overlap(box, (cx0, cy0, cx1, cy1))


def test_no_base_bar_edge_runs_through_a_plan_tag() -> None:
    """c3-r6 (rule 14): the 1/2 x 6 bars' operator-side edges ran through the
    A1 and B1 texts. Sampled along every bar edge, no point lands in a tag's
    text box, 1 mm (sheet) of air kept round it."""
    air = 0.001
    boxes = {
        tag.text.split("\n")[0]: _note_box(tag.text, _plan_xy(*tag.text_xy))
        for tag in spec.PLAN_TAGS
    }
    for rail in spec.RAILS:
        near_op, near_col, far_op, far_col = spec._bar_corners(rail)
        for a, b in (
            (near_op, far_op),
            (near_col, far_col),
            (near_op, near_col),
            (far_op, far_col),
        ):
            for k in range(401):
                t = k / 400.0
                x, y = _plan_xy(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                for name, (x0, y0, x1, y1) in boxes.items():
                    inside = x0 - air < x < x1 + air and y0 - air < y < y1 + air
                    assert not inside, (name, rail)


# The BOM's budget: a header and one line a row at the set row height.
BOM_HEIGHT = (len(spec.BOM_ORDER) + 1) * drawing.BOM_ROW_HEIGHT
BOM_WIDTH = sum(drawing.BOM_COLUMN_WIDTHS.values())


def _center(region):
    return ((region[0] + region[2]) / 2.0, (region[1] + region[3]) / 2.0)


def _inside(box, region) -> bool:
    return (
        region[0] <= box[0]
        and region[1] <= box[1]
        and box[2] <= region[2]
        and box[3] <= region[3]
    )


def test_bom_sheet_regions_fit_apart() -> None:
    reference = _view_box(
        _center(drawing.REFERENCE_REGION), *_iso_size(0.0), drawing.REFERENCE_SCALE
    )
    bom = (
        drawing.BOM_ANCHOR[0],
        drawing.BOM_ANCHOR[1] - BOM_HEIGHT,
        drawing.BOM_ANCHOR[0] + BOM_WIDTH,
        drawing.BOM_ANCHOR[1],
    )
    assert _inside_sheet(reference) and _inside_sheet(bom)
    assert not _overlap(reference, bom)
    # One unsplit table stays on paper without a global height restriction
    # from the title block on the other side of the sheet.
    assert not drawing.bom_extent_violations(drawing.BOM_ANCHOR, BOM_WIDTH, BOM_HEIGHT)
    assert bom[2] <= drawing.TITLE_BLOCK_KEEP_OUT[0]
    # The reference view stays in the room the drawing asserts at run time,
    # which keeps out of the title block.
    region = drawing.REFERENCE_REGION
    assert _inside(reference, region) and _inside_sheet(region)
    assert region[0] >= bom[2] + drawing.REGION_GAP
    assert bom[0] - drawing.SHEET_INNER_BORDER[0] >= drawing.BOM_SHEET_CLEARANCE
    assert drawing.SHEET_INNER_BORDER[3] - bom[3] >= drawing.BOM_SHEET_CLEARANCE


def test_bom_extent_rejects_border_title_and_reserved_content_intrusions() -> None:
    left, bottom, right, top = drawing.SHEET_INNER_BORDER
    clearance = drawing.BOM_SHEET_CLEARANCE
    assert not drawing.bom_extent_violations(drawing.BOM_ANCHOR, BOM_WIDTH, BOM_HEIGHT)
    # Touching either border failed the printed cf3 sheet even without a spill.
    assert drawing.bom_extent_violations(
        (left, drawing.BOM_ANCHOR[1]), BOM_WIDTH, BOM_HEIGHT,
    )
    assert drawing.bom_extent_violations(
        (drawing.BOM_ANCHOR[0], top), BOM_WIDTH, BOM_HEIGHT,
    )
    table_top = drawing.TITLE_BLOCK[3]
    table_height = (table_top - bottom - clearance) / 2.0
    assert drawing.bom_extent_violations(
        (drawing.TITLE_BLOCK[0], table_top),
        (right - drawing.TITLE_BLOCK[0]) / 2.0, table_height,
    )
    assert drawing.bom_extent_violations(
        (left - clearance, drawing.BOM_ANCHOR[1]), BOM_WIDTH, BOM_HEIGHT,
    )
    assert drawing.bom_extent_violations(
        (left, top + clearance), BOM_WIDTH, BOM_HEIGHT,
    )
    assert drawing.bom_extent_violations(
        drawing.BOM_ANCHOR, BOM_WIDTH, drawing.BOM_ANCHOR[1] - bottom,
    )
    assert drawing.bom_extent_violations(
        drawing.BOM_ANCHOR, BOM_WIDTH + drawing.REGION_GAP, BOM_HEIGHT,
    )
    assert drawing.bom_extent_violations(
        drawing.BOM_ANCHOR, right - left + clearance, BOM_HEIGHT,
    )


def test_each_cluster_rings_inside_its_sheet() -> None:
    for cluster in drawing.CLUSTERS:
        if cluster.sheet == drawing.PIVOT_CAPTURE_SHEET:
            continue  # Sheet 4 uses its local, independent view fitter.
        initial = _cluster_outline(cluster)
        scale = drawing.cluster_ring_scale(initial, cluster.scale, label=cluster.sheet)
        # Fit at the returned scale, not the initial placement scale. Every
        # larger ladder rung must fail the same physical ring budget.
        for larger in drawing.CLUSTER_SCALE_LADDER[
            :drawing.CLUSTER_SCALE_LADDER.index(scale)
        ]:
            assert drawing.cluster_ring_fit(
                _cluster_outline(cluster, scale=larger)
            )[1]
        outline = _cluster_outline(cluster, scale=scale)
        shift, overflows, slide = drawing.cluster_ring_fit(outline)
        assert not overflows and slide <= 0.0
        placed = (
            outline[0] + shift[0],
            outline[1] + shift[1],
            outline[2] + shift[0],
            outline[3] + shift[1],
        )
        assert drawing.cluster_ring_violations(placed) == []
        ring = (
            placed[0] - drawing.BALLOON_RING_REACH,
            placed[1] - drawing.BALLOON_RING_REACH,
            placed[2] + drawing.BALLOON_RING_REACH,
            placed[3] + drawing.BALLOON_RING_REACH,
        )
        assert _inside(ring, drawing.CLUSTER_RING_REGION)
        caption = _note_box(
            drawing.exploded_caption(cluster, scale),
            drawing.EXPLODED_CAPTION_XY,
        )
        assert _inside_sheet(caption)
        assert caption[3] < drawing.CLUSTER_RING_REGION[1]
        # The ring holds the cluster's balloons at _drawing_balloons' spacing
        # without the even-spacing fallback, on its smaller semi-axis.
        semi = min(placed[2] - placed[0], placed[3] - placed[1]) / 2.0
        gap = _drawing_balloons._min_angular_gap(
            semi + drawing.BALLOON_MARGIN,
            drawing.BALLOON_RADIUS,
            clearance=_drawing_balloons._BALLOON_CLEARANCE_M,
        )
        assert len(cluster.stems) * gap <= 2.0 * math.pi


def test_a_low_ring_slides_left_of_the_title_block() -> None:
    # Wide and tall enough that its low arc dips beside the title block.
    outline = (0.0, 0.0, 0.160, 0.150)
    shift, overflows, slide = drawing.cluster_ring_fit(outline)
    assert not overflows and slide < 0.0
    centred = drawing.ring_fit_shift(
        outline, drawing.CLUSTER_RING_REGION, grow=drawing.BALLOON_RING_REACH
    )[0]
    unslid = (
        outline[0] + centred[0],
        outline[1] + centred[1],
        outline[2] + centred[0],
        outline[3] + centred[1],
    )
    assert drawing.cluster_ring_violations(unslid) == [
        "its low arc reaches the title block"
    ]
    placed = (
        outline[0] + shift[0],
        outline[1] + shift[1],
        outline[2] + shift[0],
        outline[3] + shift[1],
    )
    assert drawing.cluster_ring_violations(placed) == []


def test_cluster_ring_scale_walks_the_whole_ladder() -> None:
    # A small outline placed at 1:10 steps UP to the ladder's top; one too
    # big at every rung names each rung's overflow.
    small = (0.0, 0.0, 0.010, 0.010)
    placed = drawing.CLUSTER_SCALE_LADDER[-1]
    assert drawing.cluster_ring_scale(small, placed, label="t") == (
        drawing.CLUSTER_SCALE_LADDER[0]
    )
    huge = (0.0, 0.0, 0.400, 0.300)
    with pytest.raises(ValueError) as error:
        drawing.cluster_ring_scale(huge, placed, label="t")
    for scale in drawing.CLUSTER_SCALE_LADDER:
        assert f"{drawing._scale_text(scale)}:" in str(error.value)
    with pytest.raises(ValueError, match="not on the ladder"):
        drawing.cluster_ring_scale(small, (1.0, 7.0), label="t")


def test_ring_right_slack_follows_the_low_balloons() -> None:
    keep_out = (0.200, 0.0, 0.400, 0.070)
    outline = (0.050, 0.100, 0.150, 0.200)
    # Every balloon high: the view goes back the whole cap.
    high = [(0.180, 0.150, 0.005), (0.300, 0.100, 0.005)]
    assert drawing.ring_right_slack(
        high, outline, keep_out=keep_out, cap=0.040
    ) == pytest.approx(0.040)
    # A low balloon 15 mm short of the keep-out allows 15 mm.
    low = [*high, (0.180, 0.060, 0.005)]
    assert drawing.ring_right_slack(
        low, outline, keep_out=keep_out, cap=0.040
    ) == pytest.approx(0.015)
    # A low outline binds too; one already beside it allows nothing.
    low_outline = (0.050, 0.060, 0.170, 0.200)
    assert drawing.ring_right_slack(
        high, low_outline, keep_out=keep_out, cap=0.040
    ) == pytest.approx(0.030)
    beside = [(0.199, 0.060, 0.005)]
    assert (
        drawing.ring_right_slack(beside, outline, keep_out=keep_out, cap=0.040) == 0.0
    )


def test_keep_out_overshoot_measures_the_low_balloons() -> None:
    keep_out = (0.200, 0.0, 0.400, 0.070)
    outline = (0.050, 0.100, 0.150, 0.200)
    high = [(0.300, 0.100, 0.005)]
    assert drawing.keep_out_overshoot(high, outline, keep_out=keep_out) == -math.inf
    # Farm r9: a T-nut balloon carried 0.3 past the keep-out's left edge.
    low = [*high, (0.1983, 0.060, 0.005)]
    assert drawing.keep_out_overshoot(low, outline, keep_out=keep_out) == pytest.approx(
        0.0033
    )


def _steps_sheet_boxes(layout):
    boxes = [_note_box(layout.steps, drawing.STEPS_XY)]
    if layout.checks:
        boxes.append(_note_box(layout.checks, layout.checks_xy))
    if layout.continued:
        boxes.append(_note_box(layout.continued, drawing.STEPS_CONTINUED_XY))
    return boxes


def _assert_steps_sheet_fits(layout) -> None:
    boxes = _steps_sheet_boxes(layout)
    assert all(_inside_sheet(box) for box in boxes)
    for index, a in enumerate(boxes):
        for b in boxes[index + 1 :]:
            assert not _overlap(a, b)
    # The left column ends over its floor at the farm's measured line pitch.
    steps_lines = _lines(layout.steps)
    assert drawing.STEPS_XY[1] - steps_lines * drawing.NOTE_LINE_M >= (
        drawing.STEPS_FLOOR
    )


def _lines(text: str) -> int:
    return text.count("\n") + 1 if text else 0


def test_steps_sheet_regions_fit_apart() -> None:
    _assert_steps_sheet_fits(drawing.STEPS_LAYOUT)
    _assert_steps_sheet_fits(drawing.STEPS_CONTINUED_LAYOUT)
    _assert_steps_sheet_fits(drawing.CARTRIDGE_LAYOUT)
    _assert_steps_sheet_fits(drawing.TOP_CAPTURE_LAYOUT)


@pytest.mark.parametrize(
    "sheet,layout",
    (
        (drawing.STEPS_SHEET, drawing.STEPS_LAYOUT),
        (drawing.STEPS_CONTINUED_SHEET, drawing.STEPS_CONTINUED_LAYOUT),
        (drawing.CARTRIDGE_SHEET, drawing.CARTRIDGE_LAYOUT),
        (drawing.TOP_CAPTURE_SHEET, drawing.TOP_CAPTURE_LAYOUT),
    ),
)
def test_instruction_reference_and_caption_fit_without_moving_notes(sheet, layout) -> None:
    region = drawing.NOTES_REFERENCE_REGIONS[sheet]
    view = _view_box(
        _center(region), *_iso_size(0.0), drawing.NOTES_REFERENCE_SCALE
    )
    text = "REFERENCE 1:20"
    caption = _note_box(
        text,
        ((view[0] + view[2] - len(text) * CHAR_M) / 2.0,
         view[1] - drawing.VIEW_LABEL_GAP),
    )
    assert drawing.NOTES_REFERENCE_SCALE == (1.0, 20.0)
    assert _inside_sheet(region)
    assert _inside(view, region)
    assert _inside_sheet(view) and _inside_sheet(caption)
    assert not _overlap(view, caption)
    for note in _steps_sheet_boxes(layout):
        assert not _overlap(view, note)
        assert not _overlap(caption, note)


def test_c2a_schematic_signed_tip_and_paper_regions_are_unambiguous() -> None:
    region = drawing.PIN_TIP_INSPECTION_REGION
    reference = drawing.NOTES_REFERENCE_REGIONS[drawing.CARTRIDGE_SHEET]
    assert _inside_sheet(region) and _inside_sheet(reference)
    assert not _overlap(region, reference)
    lines = drawing.pin_tip_inspection_lines()
    datum_y, tip_y = drawing.PIN_TIP_SECTION_DATUM_Y, drawing.PIN_TIP_SECTION_TIP_Y
    # +Z into the block is above the mounting plane, never into the carriage.
    assert tip_y > datum_y
    datum = max(
        (line for line in lines if line[0][1] == line[1][1] == datum_y),
        key=lambda line: line[1][0] - line[0][0],
    )
    x = region[0]
    pin_tip = ((x + 0.049, tip_y), (x + 0.057, tip_y))
    assert pin_tip in lines
    assert datum[0][0] < pin_tip[0][0] < pin_tip[1][0] < datum[1][0]
    positive_z = min(
        (line for line in lines if line[0][0] == line[1][0]),
        key=lambda line: line[0][0],
    )
    assert positive_z[0][1] == datum_y and positive_z[1][1] > tip_y
    labels = dict(drawing.pin_tip_inspection_labels())
    assert {"SCHEMATIC - NOT TO SCALE", "+Z INTO BLOCK", "Z=0 MOUNTING PLANE"} <= labels.keys()
    assert f"{spec.retention.PIN_TIP_CARRIAGE_CLEARANCE_MIN:.2f} MIN" in labels
    note_boxes = [_note_box(text, xy) for text, xy in labels.items()]
    instruction_boxes = _steps_sheet_boxes(drawing.CARTRIDGE_LAYOUT)
    for index, box in enumerate(note_boxes):
        assert _inside(box, region) and _inside_sheet(box)
        assert not _overlap(box, reference)
        assert all(not _overlap(box, other) for other in note_boxes[index + 1:])
        assert all(not _overlap(box, other) for other in instruction_boxes)
    for start, end in lines:
        box = (
            min(start[0], end[0]), min(start[1], end[1]),
            max(start[0], end[0]), max(start[1], end[1]),
        )
        assert _inside(box, region) and _inside_sheet(box)
        assert all(not _overlap(box, note) for note in note_boxes + instruction_boxes)


def test_c2a_feature_labels_point_at_features_and_value_sits_on_the_bracket() -> None:
    labels = dict(drawing.pin_tip_inspection_labels())
    lines = drawing.pin_tip_inspection_lines()
    pointers = {text: (start, end)
                for text, start, end in drawing.pin_tip_inspection_leaders()}
    assert pointers.keys() == {
        "PIN", "BLOCK", "FEELER", "Z=0 MOUNTING PLANE",
        "GROUND BRIDGE", "NO PROUD CARRIAGE FEATURE",
    }
    x, _bottom, _right, top = drawing.PIN_TIP_INSPECTION_REGION
    datum, tip = drawing.PIN_TIP_SECTION_DATUM_Y, drawing.PIN_TIP_SECTION_TIP_Y
    assert pointers["PIN"][1] == (x + 0.057, top - 0.032)
    assert pointers["BLOCK"][1] == (x + 0.111, top - 0.027)
    assert pointers["FEELER"][1] == (x + 0.048, datum + 0.003)
    assert pointers["Z=0 MOUNTING PLANE"][1] == (x + 0.020, datum)
    assert pointers["GROUND BRIDGE"][1] == (x + 0.093, datum - 0.003)
    for text, segment in pointers.items():
        assert text in labels and segment in lines
    assert ((x + 0.070, datum), (x + 0.070, tip)) in lines
    value = _note_box(spec.PIN_TIP_MIN_RECESS_CALLOUT,
                      labels[spec.PIN_TIP_MIN_RECESS_CALLOUT])
    assert value[0] > x + 0.0715
    assert value[1] < (datum + tip) / 2.0 < value[3]
    assert ((x + 0.057, tip), (x + 0.072, tip)) in lines
    assert not find_leader_leader_crossings([
        LeaderSegment(text, "note", *start, *end)
        for text, (start, end) in pointers.items()
    ])


def test_capture_operation_notes_and_finished_view_fit_their_sheet() -> None:
    layout = drawing.CAPTURE_LAYOUT
    _assert_steps_sheet_fits(layout)
    assert drawing.CAPTURE_SHEET != drawing.STEPS_SHEET
    assert drawing.CAPTURE_SHEET in drawing.SHEET_NAMES
    # Retain the finished view's specified readable scale, using only this
    # sheet's filled text bounds to determine its available room.
    assert drawing.ISOMETRIC_SCALE == (1.0, 15.0)
    finished = _view_box(
        _center(drawing.FINISHED_REGION), *_iso_size(0.0), drawing.ISOMETRIC_SCALE
    )
    assert _inside(finished, drawing.FINISHED_REGION)
    assert _inside_sheet(drawing.FINISHED_REGION)
    assert _inside_sheet(finished)
    for note in _steps_sheet_boxes(layout):
        assert not _overlap(finished, note)
    # The native 1:15 outline measured 77.3 x 56.8 mm (farm run
    # 20261027T090456098Z, cad66b4d6), taller than the estimate above: the
    # room must hold the measured extent too.
    region = drawing.FINISHED_REGION
    assert region[3] - region[1] >= 0.0568
    assert region[2] - region[0] >= 0.0773


@pytest.mark.parametrize("outside_room", (False, True))
def test_finished_native_view_belongs_to_capture_sheet_and_must_fit(
    monkeypatch, outside_room
) -> None:
    region = drawing.FINISHED_REGION
    center = _center(region)
    outline = _view_box(center, *_iso_size(0.0), drawing.ISOMETRIC_SCALE)
    if outside_room:
        outline = (*outline[:3], region[3] + drawing.REGION_GAP)
    view = SimpleNamespace(GetOutline=lambda: outline, ScaleRatio=(1.0, 17.0))
    sheets, placements, configurations, detail_checks, captions = [], [], [], [], []
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        drawing, "_activate_sheet", lambda _adapter, sheet: sheets.append(sheet)
    )

    def place(_adapter, name, xy, scale, *, label):
        placements.append((name, xy, scale))
        return view

    monkeypatch.setattr(drawing, "_place_named_view", place)
    monkeypatch.setattr(
        drawing, "set_high_quality_shaded_with_edges",
        lambda _adapter, _view, *, label: None,
    )

    def configure(_adapter, configured_view, *, role, label):
        assert configured_view is view
        assert role is drawing.ViewRole.FULL_DETAIL
        return drawing.ASSEMBLY_VIEW_CONFIGURATION

    monkeypatch.setattr(drawing, "apply_view_configuration", configure)
    monkeypatch.setattr(
        drawing, "set_view_exploded_state",
        lambda _adapter, _view, exploded, *, configuration, label:
        configurations.append((exploded, configuration)),
    )
    monkeypatch.setattr(
        drawing, "_center_view_outline",
        lambda _adapter, _view, xy, *, label: None,
    )
    monkeypatch.setattr(
        drawing, "assert_full_detail_view",
        lambda _adapter, *, label: detail_checks.append(label),
    )
    monkeypatch.setattr(
        drawing, "_add_note_block",
        lambda _adapter, sheet, text, xy, *, label:
        captions.append((sheet, text, xy)),
    )
    # Keep the real guard: it must use the returned native GetOutline, not
    # assume the estimated or requested view fits its capture-sheet room.
    if outside_room:
        with pytest.raises(RuntimeError, match="leaves"):
            drawing._place_finished_view(_ADAPTER)
        assert not detail_checks
    else:
        drawing._place_finished_view(_ADAPTER)
        assert detail_checks
        [(sheet, caption, xy)] = captions
        assert sheet == drawing.CAPTURE_SHEET
        assert caption.endswith("1:17")  # measured native scale, not a typed 1:15
        assert _inside_sheet(_note_box(caption, xy))
        assert not _overlap(_note_box(caption, xy), outline)
    assert sheets == [drawing.CAPTURE_SHEET]
    assert placements == [(spec.ISOMETRIC_VIEW, center, drawing.ISOMETRIC_SCALE)]
    assert configurations == [(False, drawing.ASSEMBLY_VIEW_CONFIGURATION)]


def test_every_bom_row_carries_one_balloon() -> None:
    assert set(drawing.BALLOON_ANCHORS) == set(spec.BOM_ORDER)
    walked = {
        stem: anchor
        for stem, anchor in drawing.BALLOON_ANCHORS.items()
        if stem not in {spec.BASE_BAR, spec.RAIL} and stem not in spec.KIT_IDENTITIES
    }
    assert all(
        anchor.instance is None and anchor.point_mm is None
        for anchor in walked.values()
    )
    # Review r5: balloon 1 lands on the bar's operator-side long edge, part
    # frame, mid-span between the spindle end and the far hold-down slot.
    bar = drawing.BALLOON_ANCHORS[spec.BASE_BAR]
    assert bar.instance is None
    assert bar.point_mm == (200.0, base_bar.HIGH_SIDE_Y, base_bar.BAR_THICK)
    assert base_bar.NEAR_SLOT_X < bar.point_mm[0] < base_bar.FAR_SLOT_X
    assert 0.0 < bar.point_mm[0] < base_bar.BAR_LENGTH
    rail = drawing.BALLOON_ANCHORS[spec.RAIL]
    assert rail.instance == spec.instance_name(spec.RAIL, 0)
    x, y, z = rail.point_mm
    assert spec.guide_rail.HOLE_X[-2] < x < spec.guide_rail.HOLE_X[-1]
    assert (y, z) in spec.guide_rail.SECTION
    assert z == spec.guide_rail.HEIGHT
    nut = drawing.BALLOON_ANCHORS[spec.T_NUT]
    assert nut.instance == spec.instance_name(spec.T_NUT, len(spec.T_NUT_PLACEMENTS) - 1)
    assert nut.instance != spec.instance_name(spec.T_NUT, 0)
    assert nut.point_mm == (0.0, spec.t_nut.FOOT_HEIGHT, spec.t_nut.FOOT_WIDTH / 2.0)
    assert drawing.BALLOON_RING_REACH == (
        drawing.BALLOON_MARGIN + drawing.BALLOON_RADIUS
    )


def test_crossed_leaders_swap_ring_slots() -> None:
    # Each balloon's leader runs to the attachment under the other's circle.
    centres = [(0.0, 0.01), (0.01, 0.01), (0.03, 0.01)]
    attachments = [(0.01, 0.0), (0.0, 0.0), (0.03, 0.0)]
    assert drawing.uncrossed_ring_slots(centres, attachments) == [1, 0, 2]
    assert drawing.uncrossed_ring_slots(centres, centres) == [0, 1, 2]
    with pytest.raises(ValueError):
        drawing.uncrossed_ring_slots(centres, attachments[:2])


def test_a_leader_ending_on_another_still_swaps() -> None:
    # jig-r8's balloons 1 and 2 (sheet metres): balloon 2's attachment lies
    # on balloon 1's leader, a "touch" to the audit's crossing test, and the
    # rebuild left it 0.5 mm across. Run past the attachment, it crosses.
    centres = [(0.1582, 0.1165), (0.1489, 0.1047)]
    attachments = [(0.1092, 0.1448), (0.1187, 0.1393)]
    segments = [
        LeaderSegment(str(i), "balloon", *centre, *attach)
        for i, (centre, attach) in enumerate(zip(centres, attachments))
    ]
    assert not find_leader_leader_crossings(segments)
    assert drawing.uncrossed_ring_slots(centres, attachments) == [1, 0]


def test_leaders_converging_under_the_run_on_do_not_toggle() -> None:
    # c4-r4: two leaders ending 1 mm apart cross once run on whichever slots
    # they take; the crossed pair swaps once and the near pair stays put.
    centres = [(0.0, 0.02), (0.02, 0.02)]
    attachments = [(0.0105, 0.0), (0.0095, 0.0)]
    assert drawing.uncrossed_ring_slots(centres, attachments) == [1, 0]


def test_bom_identity_is_the_registry() -> None:
    for stem in spec.BOM_ORDER:
        physical, _configuration = spec.COMPONENT_IDENTITIES[stem]
        assert drawing.BOM_PART_NUMBERS[stem] == _config.parts(physical)["number"]
    assert set(drawing.BOM_PART_NUMBERS) == set(spec.BOM_ORDER)
    assert drawing.BOM_COMPONENT_IDENTITIES == spec.COMPONENT_IDENTITIES
    assert {drawing.BOM_PART_NUMBERS[family] for family in spec.KIT_IDENTITIES} == {
        "MHA-SH-VN-57"
    }
    assert drawing.BOM_ITEM_NUMBERS == {
        stem: str(item) for item, stem in enumerate(spec.BOM_ORDER, 1)
    }
    longest_number = max(len(number) for number in drawing.BOM_PART_NUMBERS.values())
    assert drawing.BOM_COLUMN_WIDTHS["part"] - drawing.BOM_CELL_PADDING_M >= (
        longest_number * drawing.BOM_CHAR_M
    )
    # Every description prints whole on one line of its column.
    longest = max(len(text) for text in drawing.BOM_DESCRIPTIONS.values())
    assert longest <= drawing.BOM_DESCRIPTION_MAX_CHARS
    assert drawing.BOM_COLUMN_WIDTHS["description"] - drawing.BOM_CELL_PADDING_M >= (
        longest * drawing.BOM_CHAR_M
    )
    assert set(drawing.BOM_COLUMN_WIDTHS) == {"item", "part", "description", "quantity"}


def test_steps_cite_every_screw_by_item_number() -> None:
    screws = [stem for stem in spec.BOM_ORDER if stem.endswith("-screw")]
    steps = "\n".join(
        text
        for layout in (
            drawing.STEPS_LAYOUT, drawing.STEPS_CONTINUED_LAYOUT,
            drawing.CARTRIDGE_LAYOUT, drawing.TOP_CAPTURE_LAYOUT,
            drawing.CAPTURE_LAYOUT,
        )
        for text in (layout.steps, layout.continued)
    )
    for stem in screws:
        assert f"(ITEM {drawing.BOM_ITEM_NUMBERS[stem]})" in steps
    # A citation never breaks across a line.
    for line in steps.split("\n"):
        assert not line.rstrip().endswith(("ITEM", "(ITEM"))


@pytest.fixture
def native_bom_bindings(monkeypatch, tmp_path):
    # Fake COM owners must not resolve a live build's concurrently published
    # source. Keep a saved, test-owned identity for the real occurrence proof.
    source = tmp_path / drawing.SOURCE.name
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(_com, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        _component_references, "_early_bound", lambda value, _interface: value
    )
    monkeypatch.setattr(
        _drawing_tables._sw_type_info,
        "early_bound_or_flag",
        lambda value, *_interfaces: value,
    )


def _native_component(family, index=0, *, simplified=True):
    physical, member = spec.COMPONENT_IDENTITIES[family]
    configuration = member or "Default"
    if simplified:
        configuration += " Simplified"
    return SimpleNamespace(
        Name2=f"{family}-{501 - index * 17}",
        ComponentReference=f"{member}:{index + 1}" if member else "",
        ReferencedConfiguration=configuration,
        GetPathName=lambda: f"C:/native/{physical}.SLDPRT",
        GetParent=lambda: None,
        GetModelDoc2=lambda: SimpleNamespace(
            GetCustomInfoValue=lambda _member, _property: drawing.BOM_PART_NUMBERS[
                family
            ]
        ),
        GetTotalTransform=lambda _include_explode: SimpleNamespace(
            ArrayData=(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
        ),
    )


@pytest.mark.parametrize("simplified", (False, True))
def test_component_census_distinguishes_shared_file_members(
    native_bom_bindings, simplified
):
    for family in spec.KIT_IDENTITIES:
        component = _native_component(family, simplified=simplified)
        assert drawing._component_stem(component) == family


@pytest.mark.parametrize(
    "configuration", ("Default", "WrongMember", "TNut OtherSuffix")
)
def test_component_census_refuses_unknown_kit_configuration(
    native_bom_bindings, configuration
):
    component = _native_component(spec.T_NUT)
    component.ReferencedConfiguration = configuration
    with pytest.raises(RuntimeError, match="unexpected jig identity"):
        drawing._component_stem(component)


def test_source_census_proves_all_twelve_native_kit_references(native_bom_bindings):
    components = [
        _native_component(family, index, simplified=False)
        for family, quantity in spec.QUANTITIES.items()
        for index in range(quantity)
    ]
    source = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(
                Name=drawing.ASSEMBLY_VIEW_CONFIGURATION
            )
        ),
        GetComponents=lambda _top_only: tuple(reversed(components)),
        GetExplodedViewNames2=lambda owner: (drawing.EXPLODED_VIEW_NAMES[owner],),
    )
    drawing._validate_source(source)
    [first_stud] = [
        component
        for component in components
        if component.ComponentReference == "HoldDownStud:1"
    ]
    first_stud.ComponentReference = ""
    with pytest.raises(RuntimeError, match="missing native component references"):
        drawing._validate_source(source)


def test_cap_seating_steps_cite_the_sourced_cap_screw_sku() -> None:
    steps = "\n".join(
        (drawing.TOP_CAPTURE_LAYOUT.steps, drawing.TOP_CAPTURE_LAYOUT.continued)
    )
    assert hardware.SCREW_SKU in steps


def test_c3b_states_the_owner_accepted_engagement_shortfall() -> None:
    # Owner ruling 2026-10-27: the 3/4 screw stays; its worst-case complete
    # thread engagement is a minor exception (RV-04), C3B a plain statement.
    engagement = spec.retention.cap_screw_complete_engagement_estimate()
    minimum = spec.retention.CAP_MIN_COMPLETE_THREAD_ENGAGEMENT
    assert 0.0 < engagement < minimum
    c3b = next(step for step in spec.CAP_SEATING_STEPS if step.startswith("C3B."))
    assert f"{engagement:.2f}" in c3b and f"{minimum:.2f}" in c3b
    # Rule 20: a plain fact, no measurement algebra and no approval wording.
    assert "MIN(" not in c3b and "MAX(" not in c3b and "ACCEPT" not in c3b
    # No NAS or supplier limit backs the runouts: printed as an estimate, never a MIN.
    assert "ESTIMATED" in c3b and f"{engagement:.2f} MIN" not in c3b
    exceptions = {
        e.id: e
        for e in load_exceptions(
            CAD_ROOT / "config", "ch_rocker_arm_tl_oblique_jig_assembly", "assembly"
        )
    }
    shortfall = exceptions["RV-04"]
    assert shortfall.kind == "minor"
    assert f"{engagement:.2f}" in shortfall.finding
    assert f"{minimum:.2f}" in shortfall.finding
    assert "owner ruling 2026-10-27" in shortfall.reason
    assert hardware.SCREW_SKU in shortfall.where


class _Table:
    """A BOM in SolidWorks' order, with the edits and measures the recipe uses."""

    def __init__(self, native_order):
        self.cells = [["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY."]]
        self.cells += [
            [
                str(item),
                drawing.BOM_PART_NUMBERS[stem],
                drawing.BOM_DESCRIPTIONS[stem],
                str(spec.QUANTITIES[stem]),
            ]
            for item, stem in enumerate(native_order, 1)
        ]
        self.widths: dict[int, float] = {}
        self.heights: dict[int, float] = {}
        self.row_hidden = {}
        self.position = (*drawing.BOM_ANCHOR, 0.0)
        self.native_members = [
            tuple(
                _native_component(family, index)
                for index in range(spec.QUANTITIES[family])
            )
            for family in native_order
        ]
        self.association_configurations = []
        self.column_types = [
            (202, "", 0),
            (204, '$PRP:"Number"', 0),
            (204, "", 0),
            (203, "", 0),
            (201, "", 0),
        ]
        self.hidden = [False] * 4 + [True]
        self.number_property = "Number"
        # One Quantity column per configuration; the jig binds "Default Simplified"
        # (k=1), so "Default"'s Quantity column is latent.
        self.configurations = ("Default", "Default Simplified")
        self.selected_configuration = "Default Simplified"
        self.BomFeature = SimpleNamespace(
            GetConfigurations=lambda _only_visible, _unused: (
                self.configurations,
                tuple(
                    name == self.selected_configuration
                    for name in self.configurations
                ),
            )
        )

    @property
    def RowCount(self):
        return len(self.cells)

    @property
    def TotalRowCount(self):
        return self.RowCount

    def RowHidden(self, row):
        if not 0 <= row < self.TotalRowCount:
            raise IndexError(row)
        return self.row_hidden.get(row, False)

    @property
    def ColumnCount(self):
        return self.hidden.count(False)

    @property
    def TotalColumnCount(self):
        return len(self.column_types) + len(self.configurations) - 1

    def _visibility_physical(self, column):
        """Map a 0-based visibility index to typed storage; None for latent/out-of-range."""
        quantity = next(i for i, t in enumerate(self.column_types) if t[0] == 203)
        before = self.configurations.index(self.selected_configuration)
        if 0 <= column < quantity:
            return column
        if quantity <= column < quantity + before:
            return None
        physical = column - before
        return physical if physical < len(self.column_types) else None

    def _physical_column(self, column, include_hidden=True):
        columns = [
            index
            for index, hidden in enumerate(self.hidden)
            if include_hidden or not hidden
        ]
        return columns[column] if 0 <= column < len(columns) else None

    def DisplayedText(self, row, column):
        return self.DisplayedText2(row, column, False)

    def DisplayedText2(self, row, column, include_hidden):
        physical = self._physical_column(column, include_hidden)
        if physical is None:
            return ""
        if physical < len(self.cells[row]):
            return self.cells[row][physical]
        return "PART NUMBER" if row == 0 else self.cells[row][1]

    def GetColumnTitle2(self, column, include_hidden):
        return self.DisplayedText2(0, column, include_hidden)

    def GetColumnType3(self, column, include_hidden):
        physical = self._physical_column(column, include_hidden)
        return (-1, None, 0) if physical is None else self.column_types[physical]

    def ColumnHidden(self, column):
        # Native visibility indices are 0-based and include latent Quantity columns.
        physical = self._visibility_physical(column)
        return False if physical is None else self.hidden[physical]

    def GetColumnCustomProperty(self, column):
        if not 0 <= column < len(self.column_types):
            return ""
        if column == 1 and self.column_types[column][0] == 204:
            return self.number_property
        return ""

    def SetText2(self, *_args):
        raise AssertionError("Number cells must stay natively property-linked")

    def GetComponents2(self, row, configuration):
        self.association_configurations.append(configuration)
        return self.native_members[row - 1]

    def SetColumnWidth(self, column, width, options):
        assert options == 0
        physical = self._physical_column(column, False)
        if physical is None:
            raise IndexError(column)
        self.widths[physical] = width
        return width

    def SetRowHeight(self, row, height, options):
        assert options == 0
        self.heights[row] = height
        return height

    def GetColumnWidth(self, column):
        physical = self._physical_column(column, False)
        if physical is None:
            return 0.0
        return self.widths.get(physical, 0.02)

    def GetRowHeight(self, row):
        return self.heights[row]

    def GetAnnotation(self):
        return SimpleNamespace(GetPosition=lambda: self.position)


@pytest.mark.parametrize("hidden", (True, None, 0, 1, ""))
@pytest.mark.parametrize("row", (0, 1))
def test_bom_cells_requires_exact_visible_row_before_physical_text(hidden, row) -> None:
    reads = []
    table = SimpleNamespace(
        RowCount=2,
        ColumnCount=1,
        RowHidden=lambda index: hidden if index == row else False,
        DisplayedText2=lambda *args: reads.append(args) or "TEXT",
    )
    with pytest.raises(RuntimeError):
        drawing._bom_cells(table)
    assert reads == ([(0, 0, True)] if row == 1 else [])


_ADAPTER = SimpleNamespace(
    currentModel=SimpleNamespace(
        EditRebuild3=lambda: True, GraphicsRedraw2=lambda: None
    )
)


@pytest.mark.parametrize(
    "fault",
    (
        "native-column",
        "number-column",
        "number-property",
        "visible-prefix",
        "displayed-number",
        "member",
        "quantity",
        "hidden-row",
        "unreadable-row",
    ),
)
def test_package_settled_checks_reread_native_bom_without_mutating_layout(
    monkeypatch, native_bom_bindings, fault
) -> None:
    from _test_stubbed_build import stub_seat

    table = _Table(spec.BOM_ORDER)
    column_types = table.column_types
    hidden = table.hidden
    seat = stub_seat(
        monkeypatch,
        drawing,
        keep=("_place_package", "validate_bom_number_property"),
    )
    sheet = SimpleNamespace(properties=[0, 0, 1.0, 1.0])

    def set_scale(numerator, denominator, _positions, _text):
        sheet.properties[2:4] = [numerator, denominator]
        return True

    sheet.SetScale = set_scale
    sheet.GetProperties2 = lambda: tuple(sheet.properties)
    seat._activate_sheet.return_value = sheet
    reference = SimpleNamespace(ReferencedConfiguration="Default Simplified")
    seat._place_reference_view.return_value = reference
    seat.insert_bom_table.return_value = table
    seat._validate_bom.return_value = tuple(
        (stem, str(item)) for item, stem in enumerate(spec.BOM_ORDER, 1)
    )
    seat._place_assembled_sheet.return_value = lambda: None
    seat._place_kit_bom_note.return_value = lambda: None
    seat._place_pin_tip_inspection.return_value = lambda: None
    seat._place_notes_reference_views.return_value = {
        name: drawing.NOTES_REFERENCE_SCALE for name in drawing.NOTES_REFERENCE_REGIONS
    }
    capture_views = tuple(object() for _ in range(4))
    capture_scales = ((1, 4), (1, 4), (1, 1), (1, 1))
    capture_profiles = tuple(object() for _ in range(3))
    seat._place_capture_sheet.return_value = (
        capture_views, capture_scales, (), capture_profiles,
    )
    seat._place_cluster_view.side_effect = lambda _adapter, cluster: (
        object(),
        drawing.SHEET_SCALES[cluster.sheet],
    )
    seat._balloon_cluster.side_effect = (
        lambda _adapter, _view, cluster, _items, _bom_name: [
            SimpleNamespace(stem=stem)
            for stem in (
                (*cluster.stems, spec.BEARING)
                if cluster.sheet == drawing.PIVOT_CAPTURE_SHEET else cluster.stems
            )
        ]
    )
    monkeypatch.setattr(drawing, "_bom_feature_name", lambda _table: "offline BOM")
    _scales, checks = drawing._place_package(object())
    expected_configurations = [reference.ReferencedConfiguration] * len(spec.BOM_ORDER)
    assert table.association_configurations == expected_configurations
    table.association_configurations.clear()
    for check in checks:
        check()
    assert table.association_configurations == expected_configurations

    if fault == "native-column":
        column_types[-1] = (204, "", 0)
    elif fault == "number-column":
        column_types[1] = (201, "", 0)
    elif fault == "number-property":
        table.number_property = "Description"
    elif fault == "visible-prefix":
        hidden[2] = True
    elif fault == "displayed-number":
        table.cells[1][1] = "UNLINKED"
    elif fault == "quantity":
        table.cells[1][3] = str(int(table.cells[1][3]) + 1)
    elif fault == "hidden-row":
        table.row_hidden[1] = True
    elif fault == "unreadable-row":
        table.row_hidden[1] = None
    else:
        stud_row = int(spec.ITEM_NUMBERS[spec.HOLD_DOWN_STUD])
        t_nut_member = spec.COMPONENT_IDENTITIES[spec.T_NUT][1]
        table.native_members[stud_row - 1][
            0
        ].ReferencedConfiguration = f"{t_nut_member} Simplified"
    with pytest.raises(RuntimeError):
        for check in checks:
            check()
    seat.insert_bom_table.assert_called_once()
    seat._validate_bom.assert_called_once()
    seat.assert_balloon_landings.assert_called_once()
    assert table.widths == {} and table.heights == {}


def test_bom_prints_registry_numbers_one_line_a_row(
    monkeypatch, native_bom_bindings
) -> None:
    events = []
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    table = _Table(spec.BOM_ORDER)
    items = drawing._validate_bom(_ADAPTER, table)
    assert items == tuple(
        (stem, str(item)) for item, stem in enumerate(spec.BOM_ORDER, 1)
    )
    assert table.cells[0] == ["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY."]
    assert table.DisplayedText2(0, 3, True) == "QTY."
    assert table.DisplayedText(0, 3) == "QTY."
    assert table.GetColumnType3(3, True)[0] == 203
    assert table.GetColumnType3(3, False)[0] == 203
    # Visibility domain: typed 0-2, latent "Default" QTY at 3, QTY at 4, hidden 201 at 5.
    assert table.ColumnHidden(5) is True
    assert table.ColumnHidden(4) is False
    proof = drawing.validate_bom_number_property(
        table,
        configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        label="jig",
        expected_rows=1 + len(spec.BOM_ORDER),
        occurrence_quantities=True,
    )
    assert [(row, number, quantity) for row, _members, number, quantity in proof] == [
        (row, drawing.BOM_PART_NUMBERS[stem], str(spec.QUANTITIES[stem]))
        for row, stem in enumerate(spec.BOM_ORDER, 1)
    ]
    for row, stem in enumerate(spec.BOM_ORDER, 1):
        assert table.DisplayedText2(row, 1, False) == drawing.BOM_PART_NUMBERS[stem]
        assert table.DisplayedText2(row, 3, False) == str(spec.QUANTITIES[stem])
    for row, stem in zip(table.cells[1:], spec.BOM_ORDER, strict=True):
        assert row[1:] == [
            drawing.BOM_PART_NUMBERS[stem],
            drawing.BOM_DESCRIPTIONS[stem],
            str(spec.QUANTITIES[stem]),
        ]
    assert table.widths == dict(enumerate(drawing.BOM_COLUMN_WIDTHS.values()))
    assert table.heights == {
        row: drawing.BOM_ROW_HEIGHT for row in range(len(spec.BOM_ORDER) + 1)
    }
    [(name, attrs)] = events
    assert name == "drawing.bom_piece"
    assert attrs["rows"] == len(spec.BOM_ORDER) + 1 and attrs["violations"] == ()
    assert set(table.association_configurations) == {
        drawing.SIMPLIFIED_VIEW_CONFIGURATION
    }
    kit_rows = [
        table.cells[int(spec.ITEM_NUMBERS[family])] for family in spec.KIT_IDENTITIES
    ]
    assert [row[1] for row in kit_rows] == ["MHA-SH-VN-57"] * 3
    assert [row[3] for row in kit_rows] == ["4"] * 3
    assert attrs["anchor_mm"] == pytest.approx(
        tuple(value * 1000.0 for value in drawing.BOM_ANCHOR)
    )
    assert attrs["width_mm"] == pytest.approx(BOM_WIDTH * 1000.0)
    assert attrs["height_mm"] == pytest.approx(BOM_HEIGHT * 1000.0)


def test_bom_refuses_items_numbered_off_the_steps(native_bom_bindings) -> None:
    with pytest.raises(RuntimeError, match="spec.BOM_ORDER"):
        drawing._validate_bom(_ADAPTER, _Table(tuple(reversed(spec.BOM_ORDER))))


def test_bom_refuses_a_wrong_quantity(native_bom_bindings) -> None:
    table = _Table(spec.BOM_ORDER)
    table.cells[1][3] = "1"  # the base bar row grouped per configuration
    with pytest.raises(RuntimeError, match="quantity"):
        drawing._validate_bom(_ADAPTER, table)


def test_bom_refuses_an_unlinked_part_number(native_bom_bindings) -> None:
    table = _Table(spec.BOM_ORDER)
    table.cells[int(spec.ITEM_NUMBERS[spec.T_NUT])][1] = spec.T_NUT
    with pytest.raises(RuntimeError, match="associative part number"):
        drawing._validate_bom(_ADAPTER, table)


def test_bom_rechecks_number_after_rebuild(native_bom_bindings) -> None:
    table = _Table(spec.BOM_ORDER)

    def rebuild():
        table.cells[-1][1] = "unlinked-file-name"
        return True

    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=rebuild))
    with pytest.raises(RuntimeError, match="part number for"):
        drawing._validate_bom(adapter, table)


def test_bom_refuses_wrong_dedicated_number_binding_despite_raw_expression(
    native_bom_bindings,
) -> None:
    table = _Table(spec.BOM_ORDER)
    assert table.column_types[1][1] == '$PRP:"Number"'
    table.number_property = "Description"
    with pytest.raises(RuntimeError):
        drawing._validate_bom(_ADAPTER, table)


@pytest.mark.parametrize("fault", ("quantity", "native-count", "same-number-member"))
def test_bom_refuses_rebuild_drift_before_capturing_settled_baseline(
    native_bom_bindings, fault
) -> None:
    table = _Table(spec.BOM_ORDER)
    stud_row = int(spec.ITEM_NUMBERS[spec.HOLD_DOWN_STUD])
    rebuilds = []

    def rebuild():
        rebuilds.append(True)
        if fault == "quantity":
            table.cells[stud_row][3] = str(int(table.cells[stud_row][3]) - 1)
        elif fault == "native-count":
            table.native_members[stud_row - 1] = table.native_members[stud_row - 1][:-1]
        else:
            table.native_members[stud_row - 1][
                0
            ].ReferencedConfiguration = (
                f"{spec.COMPONENT_IDENTITIES[spec.T_NUT][1]} Simplified"
            )
        return True

    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=rebuild))
    message = (
        "native occurrence count"
        if fault != "same-number-member"
        else "merged distinct members"
    )
    with pytest.raises(RuntimeError, match=message):
        drawing._validate_bom(adapter, table)
    assert rebuilds == [True]


@pytest.mark.parametrize("fault", ("wrong-member", "merged-members", "missing-member"))
def test_bom_refuses_ambiguous_native_kit_rows(native_bom_bindings, fault):
    table = _Table(spec.BOM_ORDER)
    stud_row = int(spec.ITEM_NUMBERS[spec.HOLD_DOWN_STUD]) - 1
    nut_row = int(spec.ITEM_NUMBERS[spec.T_NUT]) - 1
    if fault == "wrong-member":
        for member in table.native_members[nut_row]:
            member.ReferencedConfiguration = "FlangeNut Simplified"
    elif fault == "merged-members":
        table.native_members[nut_row] += table.native_members[stud_row]
    else:
        table.native_members[nut_row] = ()
    with pytest.raises(RuntimeError):
        drawing._validate_bom(_ADAPTER, table)


def test_bom_refuses_native_row_growth_past_the_bottom_border(
    native_bom_bindings,
) -> None:

    class Wrapping(_Table):
        def GetRowHeight(self, row):
            return 2.0 * super().GetRowHeight(row)  # every description wrapped

    with pytest.raises(RuntimeError):
        drawing._validate_bom(_ADAPTER, Wrapping(spec.BOM_ORDER))


def test_kit_bom_key_uses_registry_identity_and_native_item_mapping(
    native_bom_bindings,
):
    # Reversed native rows prove the citations are not copied from spec item 18-20.
    order = tuple(reversed(spec.BOM_ORDER))
    table = _Table(order)
    text = drawing._kit_bom_note_text(
        table, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
    )
    registry = _config.parts(spec.CLAMPING_KIT)
    assert registry["number"] in text
    assert str(registry["supplier"]).upper() in text
    assert all(sku in text for sku in registry["supplier_skus"])
    for family, (_physical, member) in spec.KIT_IDENTITIES.items():
        [citation] = [line for line in text.splitlines() if member in line]
        assert f"ITEM {order.index(family) + 1}:" in citation
        assert f"({registry['configuration_quantities'][member]})" in citation
    assert "CONFIGURATIONS" in text and "INSTALLED QTY." in text
    assert "MEMBERS, NOT KITS" in text


class _KitBomNote:
    """Native-style note geometry with a nonzero insertion-to-extent offset."""

    def __init__(self, text, xy, *, width, move):
        self.text = text
        self.position = (*xy, 0.0)
        self.width = width
        self.move = move
        self.OwnerType = 1
        self.Visible = 1
        self.leaders = 0

    def GetAnnotation(self):
        return self

    def GetPosition(self):
        return self.position

    def GetExtent(self):
        x, y, _z = self.position
        return x + 0.005, y - 0.036, 0.0, x + 0.005 + self.width, y + 0.002, 0.0

    def GetText(self):
        return self.text.replace("\n", "\r\n")

    def GetLeaderCount(self):
        return self.leaders

    def SetPosition2(self, *position):
        if self.move == "refused":
            return False
        if self.move != "ignored":
            self.position = position
        return True


@pytest.fixture
def kit_bom_note_state(monkeypatch, native_bom_bindings):
    table = _Table(spec.BOM_ORDER)
    table.widths = dict(enumerate(drawing.BOM_COLUMN_WIDTHS.values()))
    table.heights = {
        row: drawing.BOM_ROW_HEIGHT for row in range(len(spec.BOM_ORDER) + 1)
    }
    rx0, ry0, rx1, ry1 = drawing.REFERENCE_REGION
    state = SimpleNamespace(
        table=table,
        outline=(rx0 + 0.010, ry0 + 0.070, rx1 - 0.010, ry1 - 0.010),
        notes=[],
        width=0.145,
        move="applied",
        active=None,
    )
    state.reference = SimpleNamespace(
        ReferencedConfiguration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        GetOutline=lambda: state.outline,
    )

    def add_native_note(_adapter, text, x, y):
        assert state.active == drawing.BOM_SHEET
        note = _KitBomNote(text, (x, y), width=state.width, move=state.move)
        state.notes.append(note)
        return note

    monkeypatch.setattr(drawing, "add_note", add_native_note)
    monkeypatch.setattr(
        drawing, "_activate_sheet",
        lambda _adapter, sheet: setattr(state, "active", sheet),
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    return state


def test_kit_bom_key_measured_extent_clears_native_neighbors(kit_bom_note_state):
    state = kit_bom_note_state
    settled = drawing._place_kit_bom_note(_ADAPTER, state.table, state.reference)
    [note] = state.notes
    extent = drawing._kit_bom_note_extent(note)
    bom = drawing._bom_bounds(state.table)
    field = drawing.kit_bom_note_region(bom, state.outline)
    assert _inside(extent, field) and _inside_sheet(extent)
    assert state.outline[1] - extent[3] >= 0.004
    assert extent[0] - bom[2] >= 0.004
    assert extent[1] - drawing.TITLE_BLOCK[3] >= 0.004
    assert extent[0] > note.position[0]  # placement used ink, not the annotation origin
    settled()
    for family in spec.KIT_IDENTITIES:
        row = state.table.cells[int(spec.ITEM_NUMBERS[family])]
        assert row[1] == drawing.BOM_PART_NUMBERS[family] and row[3] == "4"


@pytest.mark.parametrize("fault", ("oversized", "ignored", "refused"))
def test_kit_bom_key_refuses_a_native_note_that_does_not_fit(kit_bom_note_state, fault):
    state = kit_bom_note_state
    if fault == "oversized":
        state.width = 0.250
    else:
        state.move = fault
    with pytest.raises(RuntimeError):
        drawing._place_kit_bom_note(_ADAPTER, state.table, state.reference)


@pytest.mark.parametrize(
    "fault",
    (
        "bom-moved",
        "reference-moved",
        "wrong-text",
        "wrong-member",
        "wrong-quantity",
        "wrong-number",
        "view-owned",
        "hidden",
        "leader",
        "empty-extent",
        "nonfinite-extent",
    ),
)
def test_kit_bom_key_rechecks_content_and_clearance_after_final_rebuild(
    kit_bom_note_state, fault
):
    state = kit_bom_note_state
    settled = drawing._place_kit_bom_note(_ADAPTER, state.table, state.reference)
    [note] = state.notes
    extent = drawing._kit_bom_note_extent(note)
    member_row = int(spec.ITEM_NUMBERS[spec.T_NUT])
    if fault == "bom-moved":
        state.table.position = (extent[0] - BOM_WIDTH - 0.003, state.table.position[1], 0.0)
    elif fault == "reference-moved":
        left, _bottom, right, top = state.outline
        state.outline = left, extent[3] + 0.003, right, top
    elif fault == "wrong-text":
        note.text += "\nUNRELATED KIT"
    elif fault == "wrong-member":
        for component in state.table.native_members[member_row - 1]:
            component.ReferencedConfiguration = "FlangeNut Simplified"
    elif fault == "wrong-quantity":
        state.table.cells[member_row][3] = "12"
    elif fault == "wrong-number":
        state.table.cells[member_row][1] = "UNRELATED-PURCHASE"
    elif fault == "view-owned":
        note.OwnerType = 0
    elif fault == "hidden":
        note.Visible = 3
    elif fault == "leader":
        note.leaders = 1
    elif fault == "empty-extent":
        note.width = 0.0
    else:
        note.width = math.nan
    with pytest.raises(RuntimeError):
        settled()


def test_bom_refuses_native_column_growth_into_the_reference_room(
    native_bom_bindings,
) -> None:

    class Widened(_Table):
        def GetColumnWidth(self, column):
            width = super().GetColumnWidth(column)
            return width + 2.0 * drawing.REGION_GAP if column == 1 else width

    with pytest.raises(RuntimeError):
        drawing._validate_bom(_ADAPTER, Widened(spec.BOM_ORDER))


class _Manager:
    def __init__(self, source: _Source) -> None:
        self._source = source

    @property
    def ActiveConfiguration(self) -> SimpleNamespace:
        return SimpleNamespace(Name=self._source.active)


class _Source:
    """A source assembly whose ShowConfiguration2 switches its active one."""

    def __init__(self, *, refuse: frozenset[str] = frozenset()) -> None:
        self.active = drawing.ASSEMBLY_VIEW_CONFIGURATION
        self.shown: list[str] = []
        self.refuse = refuse
        self.ConfigurationManager = _Manager(self)

    def ShowConfiguration2(self, name: str) -> bool:
        self.shown.append(name)
        if name in self.refuse:
            return False
        self.active = name
        return True


def _exploded_view(source: _Source) -> SimpleNamespace:
    return SimpleNamespace(
        ReferencedConfiguration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        ReferencedDocument=source,
        IsExploded=lambda: True,
    )


def test_balloons_read_the_explode_in_the_source_s_active_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _Source()
    with drawing._source_configuration_active(_exploded_view(source), label="t"):
        assert source.active == drawing.SIMPLIFIED_VIEW_CONFIGURATION
    assert source.active == drawing.ASSEMBLY_VIEW_CONFIGURATION
    assert source.shown == [
        drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        drawing.ASSEMBLY_VIEW_CONFIGURATION,
    ]


def test_source_configuration_is_restored_when_the_balloons_fail(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _Source()
    with pytest.raises(RuntimeError, match="balloon"):
        with drawing._source_configuration_active(_exploded_view(source), label="t"):
            raise RuntimeError("balloon")
    assert source.active == drawing.ASSEMBLY_VIEW_CONFIGURATION


def test_source_configuration_switch_is_read_back(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _Source(refuse=frozenset({drawing.SIMPLIFIED_VIEW_CONFIGURATION}))
    with pytest.raises(RuntimeError, match="did not activate"):
        with drawing._source_configuration_active(_exploded_view(source), label="t"):
            pass
    restore = _Source(refuse=frozenset({drawing.ASSEMBLY_VIEW_CONFIGURATION}))
    with pytest.raises(RuntimeError, match="did not re-activate"):
        with drawing._source_configuration_active(_exploded_view(restore), label="t"):
            pass


def test_cl_tip_reference_is_the_placed_dowel_over_the_riser() -> None:
    """#1619: the elevation's (1.6) is the CL dowel's modelled round tip above
    the riser top, up the dowel's axis, a reference inside the fitter's band."""
    cl_dowel = spec.cl_dowel
    (x, riser_top), (tip_x, tip_z) = spec.CL_TIP_LINE
    origin, rows = spec.CL_DOWEL_PLACEMENTS[0]
    assert rows[1] == pytest.approx((0.0, 0.0, 1.0))  # the dowel's axis up Z
    assert (x, tip_x) == pytest.approx((origin[0], origin[0]))
    assert riser_top == spec.trammel.CARRIER_TOP_Z + spec.trammel.RISER_THICK
    assert tip_z == pytest.approx(origin[2] + cl_dowel.LENGTH)
    assert tip_z - riser_top == pytest.approx(cl_dowel.TIP_HEIGHT)
    assert cl_dowel.TIP_SET_MIN < cl_dowel.TIP_HEIGHT < cl_dowel.TIP_SET_MAX
    assert spec.DRAWING_DIMENSIONS == {spec.CL_TIP_FEATURE: {spec.CL_TIP_DIMENSION}}
    assert spec.DRAWING_PRECISION == {
        spec.CL_TIP_FEATURE: {spec.CL_TIP_DIMENSION: spec.CL_TIP_PRECISION}
    }


def _elevation_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet metres of a machine X-Z point, the elevation centred on the extent."""
    (x0, x1), _y, (z0, z1) = spec.MODEL_EXTENT
    ratio = drawing.ASSEMBLED_SCALE[0] / drawing.ASSEMBLED_SCALE[1] / 1000.0
    return (
        drawing.ELEVATION_CENTER[0] + (x_mm - (x0 + x1) / 2.0) * ratio,
        drawing.ELEVATION_CENTER[1] + (z_mm - (z0 + z1) / 2.0) * ratio,
    )


def test_cl_tip_text_stands_clear_outboard_of_the_riser() -> None:
    """The (1.6) text, centred on its point: on the sheet, left of the dowel
    and the riser's -X end, above the tip, clear of the plan and every note."""
    tx, _ty, tz = drawing.CL_TIP_TEXT_MODEL_MM
    cx, cy = _elevation_xy(tx, tz)
    half_w, half_h = len("(1.6)") * CHAR_M / 2.0, LINE_M / 2.0
    text = (cx - half_w, cy - half_h, cx + half_w, cy + half_h)
    (x, _riser_top), (_x, tip_z) = spec.CL_TIP_LINE
    riser_end = spec.POSE.to_machine(spec.riser.BLANK_ORIGIN)[0]
    assert riser_end < x
    assert text[2] < _elevation_xy(riser_end, tip_z)[0]
    assert text[1] > _elevation_xy(x, tip_z)[1]
    (x0, x1), (y0, y1), _z = spec.MODEL_EXTENT
    others = (
        _view_box(drawing.PLAN_CENTER, x1 - x0, y1 - y0, drawing.ASSEMBLED_SCALE),
        _note_box(spec.PLAN_VIEW_LABEL, drawing.PLAN_LABEL_XY),
        _note_box(spec.ELEVATION_VIEW_LABEL, drawing.ELEVATION_LABEL_XY),
        _note_box(drawing.ASSEMBLED_CAPTION, drawing.CAPTION_XY),
        _note_box(drawing.ALIGNMENT_NOTE, drawing.ALIGNMENT_XY),
    )
    assert _inside_sheet(text)
    for other in others:
        assert not _overlap(text, other)


@pytest.mark.parametrize("defect", (
    None, "ignored-offset", "line-follows-text", "inherited-offset", "line-off-sheet-x",
))
def test_cl_tip_native_reference_offsets_without_replacing_its_model_value(
    monkeypatch, defect,
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        _drawing_dimensions._sw_type_info, "early_bound_or_flag",
        lambda value, *_interface: value,
    )
    monkeypatch.setattr(
        _drawing_dimensions, "dimension_name", lambda *_args: spec.CL_TIP_DIMENSION
    )
    for module in (drawing, _drawing_dimensions):
        monkeypatch.setattr(module, "rebuild_drawing", lambda *a, **kw: None)
    line_target, text_target = (0.217, 0.1382), (0.206, 0.146)
    # SetPosition2's z is not the sheet: the imported dimension kept its own
    # z -0.03273 after curation and SetPosition2 asked 0.0 (farm source
    # 9e0cccd61), so the double ignores the requested z the same way.
    native_z = -0.03273400182554304
    position = [0.220, 0.139, native_z]
    line_position = position.copy()
    dimension = SimpleNamespace(
        SystemValue=spec.cl_dowel.TIP_HEIGHT / 1000.0,
        Tolerance=SimpleNamespace(Type=0),
    )
    display = SimpleNamespace(
        OffsetText=defect == "inherited-offset",
        GetDimension2=lambda _configuration: dimension,
        GetText=lambda part: "(" if part == 1 else ")",
        GetPrimaryPrecision2=lambda: spec.CL_TIP_PRECISION,
    )

    def move(x, y, _z):
        # A real sheet miss, unlike the native z, still refuses the placement.
        miss = 0.0001 if defect == "line-off-sheet-x" and not display.OffsetText else 0.0
        if not (display.OffsetText and defect == "ignored-offset"):
            position[:] = (x + miss, y, native_z)
        if not display.OffsetText or defect == "line-follows-text":
            line_position[:] = (x + miss, y, native_z)
        return True

    annotation = SimpleNamespace(
        SetPosition2=move, GetPosition=lambda: tuple(position),
        GetSpecificAnnotation=lambda: display,
    )
    display.GetAnnotation = lambda: annotation
    display.GetDisplayData = lambda: SimpleNamespace(
        GetArrowHeadCount=lambda: 2,
        GetArrowHeadAtIndex2=lambda index: (
            line_position[0], line_position[1] + (-0.0002, 0.0002)[index], native_z,
            0.0, 1.0, 0.0, 0.001, 0.003, 0.0, 0.0, 0.0, 1.0,
        ),
    )
    imports = []

    def curate(_adapter, _view, **kwargs):
        imports.append(kwargs["keep"])
        # Real curation moves the whole dimension while OffsetText is false.
        # Returning an untouched annotation concealed the ordering regression.
        move(*kwargs["keep"][spec.CL_TIP_DIMENSION], 0.0)
        return [annotation]

    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda *a, label, **kw: line_target if label.endswith(" line") else text_target,
    )
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda *a, **kw: [(0.220, 0.138), (0.220, 0.1384)],
    )
    monkeypatch.setattr(drawing, "_show_base_view_sketches", lambda *a, **kw: None)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "assert_imported_precision", lambda *a, **kw: None)
    monkeypatch.setattr(drawing, "set_reference_dimension", lambda *a, **kw: display)
    adapter = SimpleNamespace(
        currentModel=_ADAPTER.currentModel, _attempt=lambda callback: callback()
    )
    refusal = {
        "ignored-offset": "native offset text",
        "line-follows-text": "native dimension line lost arrow",
        "line-off-sheet-x": "native dimension-line anchor",
    }.get(defect)
    if refusal is not None:
        with pytest.raises(RuntimeError, match=refusal):
            drawing._cl_tip_setting(adapter, object())
    else:
        settled = drawing._cl_tip_setting(adapter, object())
        assert imports == [{spec.CL_TIP_DIMENSION: line_target}]
        assert position == [*text_target, native_z]
        assert line_position == [*line_target, native_z]
        assert dimension.SystemValue == spec.cl_dowel.TIP_HEIGHT / 1000.0
        settled()
        line_position[0] += 0.003
        with pytest.raises(RuntimeError, match="native dimension line"):
            settled()
        line_position[:] = (*line_target, native_z)
        position[1] -= 0.003
        with pytest.raises(RuntimeError, match="native offset text"):
            settled()


class _InspectionTransform:
    """Nonidentity drawing-sketch transform: scale, rotation and origin."""

    def __init__(self, scale, angle=math.pi / 2.0, origin=(0.031, -0.023, 0.0)):
        self.scale, self.angle, self.origin = scale, angle, origin

    @property
    def ArrayData(self):
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (c, s, 0.0, -s, c, 0.0, 0.0, 0.0, 1.0,
                *self.origin, self.scale, 0.0, 0.0, 0.0)

    def apply(self, xyz):
        x, y, z = xyz
        c, s = math.cos(self.angle), math.sin(self.angle)
        ox, oy, oz = self.origin
        return (ox + self.scale * (c * x - s * y),
                oy + self.scale * (s * x + c * y),
                oz + self.scale * z)

    def Inverse(self):
        c, s = math.cos(self.angle), math.sin(self.angle)
        ox, oy, oz = self.origin
        return _InspectionTransform(
            1.0 / self.scale, -self.angle,
            (-(c * ox + s * oy) / self.scale,
             (s * ox - c * oy) / self.scale, -oz / self.scale),
        )


class _InspectionMathPoint:
    def __init__(self, coordinates):
        self.ArrayData = tuple(coordinates)

    def MultiplyTransform(self, transform):
        return _InspectionMathPoint(transform.apply(self.ArrayData))


class _InspectionSheetSketch:
    def __init__(self, sheet):
        self.sheet = sheet

    @property
    def ModelToSketchTransform(self):
        numerator, denominator = self.sheet.properties[2:4]
        return _InspectionTransform(denominator / numerator)


class _CaptureViewTransform:
    """Native math-boundary double, retaining 3-D projection and view rotation."""

    def __init__(self, view):
        self.view = view

    def apply(self, xyz):
        view = self.view
        delta = tuple(xyz[i] - view.model_origin[i] for i in range(3))
        x = sum(delta[i] * view.right[i] for i in range(3))
        y = sum(delta[i] * view.up[i] for i in range(3))
        c, s = math.cos(view.Angle), math.sin(view.Angle)
        ratio = view.ScaleRatio[0] / view.ScaleRatio[1]
        return (view.Position[0] + ratio * (c*x - s*y),
                view.Position[1] + ratio * (s*x + c*y), 0.0)


class _CaptureViewSketch:
    def __init__(self, view, *, sketch_origin=None, scale_ratio=None):
        self.view = view
        self.segments = []
        self.sketch_origin = sketch_origin
        self.scale_ratio = scale_ratio
        self.angle = 0.37

    def GetSketchSegments(self):
        return tuple(self.segments)

    @property
    def ModelToSketchTransform(self):
        numerator, denominator = self.scale_ratio or self.view.ScaleRatio
        scale = denominator / numerator
        rotation = _InspectionTransform(scale, angle=self.angle, origin=(0.0, 0.0, 0.0))
        position = rotation.apply((*self.view.Position, 0.0))
        if self.sketch_origin is None:
            # The first native read retains the nonidentity authored transform.
            self.sketch_origin = tuple(
                position[i] + (-0.013, 0.021, 0.0)[i] for i in range(3)
            )
        # Absorbed crop owners retain their authored scale but follow position.
        origin = tuple(self.sketch_origin[i] - position[i] for i in range(3))
        return _InspectionTransform(scale, angle=self.angle, origin=origin)


class _CaptureNativeTextData:
    """Independent native glyph runs; never inferred from whole-note extents."""

    def __init__(self, runs):
        self.runs = runs

    def _get(self, index, key):
        value = self.runs[index][key]
        if isinstance(value, Exception):
            raise value
        return value

    def GetTextCount(self):
        return len(self.runs)

    def GetTextAtIndex(self, index):
        return self._get(index, "t")

    def GetTextInBoxWidthAtIndex(self, index):
        return self._get(index, "w")

    def GetTextHeightAtIndex(self, index):
        return self._get(index, "h")

    def GetTextPositionAtIndex(self, index):
        return self._get(index, "pos")

    def GetTextRefPositionAtIndex(self, index):
        return self._get(index, "ref")

    def GetTextAngleAtIndex(self, index):
        return self._get(index, "ang")


def _native_glyph_note(runs):
    data = _CaptureNativeTextData(runs)
    annotation = SimpleNamespace(GetDisplayData=lambda: data)
    return SimpleNamespace(
        GetAnnotation=lambda: annotation, display_data=data,
        GetExtent=lambda: (0.08, 0.17, 0.0, 0.14, 0.23, 0.0),
    )


class _CaptureNativeDrawingComponent(SimpleNamespace):
    @property
    def Visible(self):
        # Generated section trees may report every node visible even after the
        # native view's independent hidden-component collection was updated.
        return True if self.view.generated_visibility_all_true else self._visible

    @Visible.setter
    def Visible(self, value):
        self._visible = value
        self._hidden = not value


class _CaptureNativeView(SimpleNamespace):
    def __setattr__(self, name, value):
        if name == "ScaleRatio" and getattr(self, "cropped", False):
            self.post_crop_scale_writes.append(tuple(value))
        if name == "ReferencedConfiguration":
            suffix = " Simplified" if value.endswith(" Simplified") else ""
            for leaf in getattr(self, "components", ()):
                component = leaf.Component
                member = _component_references.member_configuration(component.ReferencedConfiguration)
                component.ReferencedConfiguration = member + suffix
        super().__setattr__(name, value)


@pytest.fixture
def native_property_package(monkeypatch, native_bom_bindings):
    """Double the COM boundary, not recipe view placement or property linking.

    The real place_view, configuration policy, iter_views and finalizer operate
    on these sheet-owned views. Export is an explicit stop, never a fake success.
    """
    physical_names = (
        "ASSEMBLED AT INNER PASS",
        "BILL OF MATERIALS",
        "RAIL BARS EXPLODED",
        "PIVOTCAPTUREEXPLODED",
        "LEADSCREW FEED EXPLODED",
        "CARRIER EXPLODED",
        "ASSEMBLY STEPS",
        "ASSEMBLY STEPS CONTINUED",
        "CARTRIDGEASSEMBLY",
        "TOPCAPTUREFIT",
        "CAPTUREANDOPERATION",
    )
    properties = {
        name: f"live {name}"
        for name in (
            *_drawing_common.TITLE_BLOCK_TOLERANCE_PROPERTIES,
            _drawing_common.TITLE_BLOCK_COPYRIGHT_PROPERTY,
            "Number", "Title",
        )
    }
    properties["Revision"] = _config.release_revision()
    source = SimpleNamespace(
        properties=properties,
        GetCustomInfoValue=lambda _configuration, name: properties[name],
    )
    # The source assembly as a section view's native owner root (jig-retention
    # 1772: owner Name2 'ch-rocker-arm-tl-oblique-jig-1/<part>-1'). Its name is
    # deliberately NOT derivable from SOURCE's file stem, and the drawing's
    # synthetic section root below ('Draw54-SectionAssembly-1-1') is NOT it:
    # only the native parent chain, read through IComponent2, names the root.
    source_root = SimpleNamespace(
        Name2="jig-source-occurrence-7",
        GetPathName=lambda: str(drawing.SOURCE),
        GetParent=lambda: None,
    )
    doc = SimpleNamespace(
        active=physical_names[0], sheets={}, notes=[], oversized=None,
        sketch_lines=[], sketch_segments=[], paper_edits=[], balloon_landings=[],
        display_scale=1.0, display_shift=(0.0, 0.0), hidden_line=None,
        inspection_fit_denominator=20.0,
        active_view=None, selected=[], crop_circles=[], crop_calls=[], section_segments=[],
        attached_notes=[], events=[], bom_inserted=False, crop_status=1,
        bad_crop=False, bad_section=False, bad_pick=False, bad_attachment=False,
        capture_fit_denominator=4.0,
        capture_edge_defect=None,
        generated_section_flags_all_true=False,
        selected_types=[], pick_slots=[], reselections=[], binding_calls=[],
        coordinate_picks=[], zoom_centre=None,
        edge_first=False, raw_picks=True, zoomed=False,
    )
    for name in physical_names:
        sheet = SimpleNamespace(
            name=name, views=[], CustomPropertyView="",
            properties=[0, 0, 1.0, 1.0, True, 0.4318, 0.2794, True],
        )
        sheet.GetName = lambda sheet=sheet: sheet.name
        sheet.GetViews = lambda sheet=sheet: tuple(sheet.views)
        sheet.GetProperties2 = lambda sheet=sheet: tuple(sheet.properties)
        sheet.SetProperties2 = lambda *values, sheet=sheet: setattr(
            sheet, "properties", list(values)
        )

        def set_scale(numerator, denominator, _positions, _text, *, sheet=sheet):
            sheet.properties[2:4] = [numerator, denominator]
            return True

        sheet.SetScale = set_scale
        doc.sheets[name] = sheet
        sheet.sketch = _InspectionSheetSketch(sheet)

    def activate(name):
        if name not in doc.sheets:
            return False
        doc.active = name
        doc.active_view = None
        return True

    def create_view(model_path, orientation, x, y, z):
        sheet = doc.sheets[doc.active]
        index = len(sheet.views)
        view = _CaptureNativeView(
            model_path=model_path, Sheet=sheet, Position=(x, y),
            ScaleRatio=(1.0, 1.0), ReferencedDocument=source,
            ReferencedConfiguration=drawing.ASSEMBLY_VIEW_CONFIGURATION,
            exploded=False, Angle=0.0, cropped=False, crop=None, notes=[],
            crop_scale=None, crop_outline_size=None, post_crop_scale_writes=[],
            mode=_drawing_common._SW_SHADED_EDGES, section=None,
            model_origin=tuple(v / 1000.0 for v in spec.PIVOT_PIN_ORIGINS[0]),
            right=spec.VIEW_AXES[orientation][0], up=spec.VIEW_AXES[orientation][1],
        )
        if sheet.name == drawing.CARTRIDGE_SHEET:
            # Native view insertion may auto-drift the requested sheet scale.
            # The failing e9 run shrank its sheet sketch 4x at finalization.
            sheet.properties[2:4] = [1.0, 5.0]
        view.GetName2 = lambda: f"DrawingView-{sheet.name}-{index}"
        view.GetOrientationName = lambda: orientation
        view.GetDisplayMode2 = lambda: view.mode
        view.IsExploded = lambda: view.exploded
        view.UpdateViewDisplayGeometry = lambda: None
        view.GetNextView = lambda: (
            sheet.views[index + 1] if index + 1 < len(sheet.views) else None
        )
        view.GetUseParentDisplayMode = lambda: False
        view.GetSection = lambda: view.section
        view.GetNotes = lambda: tuple(view.notes)
        view.IsCropped = lambda: view.cropped
        view.ModelToViewTransform = _CaptureViewTransform(view)
        view.sketch = _CaptureViewSketch(view)
        view.GetSketch = lambda: view.sketch
        leaves = []
        for stem, count in spec.QUANTITIES.items():
            for occurrence in range(count):
                component = _native_component(stem, occurrence, simplified=False)
                physical, member = spec.COMPONENT_IDENTITIES[stem]
                component.Name2 = (
                    f"{physical}-{501 + len(leaves) * 17}" if member
                    else spec.instance_name(stem, occurrence)
                )
                section_owner = sheet.name == drawing.PIVOT_CAPTURE_SHEET and index in (2, 3)
                native_owner = SimpleNamespace(**vars(component))
                native_owner.Name2 = (
                    f"{source_root.Name2}/{component.Name2}" if section_owner else component.Name2
                )
                native_owner.GetParent = lambda: source_root if section_owner else None
                leaves.append(_CaptureNativeDrawingComponent(
                    Name=(f"Draw54-SectionAssembly-1-1/{component.Name2}"
                          if section_owner else component.Name2),
                    Component=component, Visible=True, view=view,
                    native_owner=native_owner, GetChildren=lambda: (),
                ))
        view.components = leaves
        view.generated_visibility_all_true = (
            doc.generated_section_flags_all_true
            and sheet.name == drawing.PIVOT_CAPTURE_SHEET and index in (2, 3)
        )
        view.GetHiddenComponents = lambda: tuple(
            leaf.native_owner for leaf in leaves if leaf._hidden
        )
        view.RootDrawingComponent2 = lambda _resolve: SimpleNamespace(GetChildren=lambda: tuple(leaves))

        def select_entity(entity, append):
            assert append is False and doc.selected == []
            selected = entity
            selected.world = entity.world_endpoints[0]
            defect = doc.capture_edge_defect if entity.c2 else None
            if defect == "reselect-substitute":
                selected = SimpleNamespace(**vars(entity))
            doc.selected[:] = [selected]
            doc.selected_types[:] = [12 if defect == "reselect-type" else 1]
            if defect == "reselect-count":
                doc.selected.append(entity)
                doc.selected_types.append(1)
            doc.reselections.append((entity, tuple(doc.selected), tuple(doc.selected_types)))
            return True

        view.SelectEntity = select_entity

        def crop(_jagged, _no_outline, _intensity):
            assert (_jagged, _no_outline, _intensity) == (False, False, 1)
            circle, = doc.selected
            assert any(circle is segment for segment in view.sketch.segments)
            assert circle.GetType() == 1 and circle.IsCircle() == 1
            assert not circle.ConstructionGeometry
            inverse = circle.GetSketch().ModelToSketchTransform.Inverse()
            centre = inverse.apply(circle.centre)
            edge = inverse.apply((circle.centre[0] + circle.radius,
                                  circle.centre[1], circle.centre[2]))
            radius = math.dist(centre, edge)
            ratio = view.ScaleRatio[0] / view.ScaleRatio[1]
            view.crop = (tuple((centre[i] - view.Position[i]) / ratio for i in (0, 1)), radius / ratio)
            view.crop_scale = tuple(view.ScaleRatio)
            view.crop_outline_size = (2.0 * radius, 2.0 * radius)
            if sheet.name == drawing.PIVOT_CAPTURE_SHEET and index == 1:
                # d1c: the selected 1:4 locator's native padded outline was
                # 43.8842 x 41.5158 mm, unchanged by later reported 1:5/1:6.
                view.crop_outline_size = (2.0 * radius + 0.0163842,
                                          2.0 * radius + 0.0140158)
            owner = _CaptureViewSketch(
                view, sketch_origin=view.sketch.sketch_origin,
                scale_ratio=view.crop_scale,
            )
            owner.segments.append(circle)
            view.sketch.segments.remove(circle)
            circle.owner = owner
            doc.crop_calls.append((view, circle))
            view.cropped = not doc.bad_crop
            return doc.crop_status

        view.Crop2 = crop

        def show_exploded(show):
            view.exploded = show
            return True

        def move(position, move_children):
            assert move_children is False
            view.Position = tuple(position)
            return True

        def outline():
            (x0, x1), (y0, y1), (z0, z1) = spec.MODEL_EXTENT
            if orientation == spec.PLAN_VIEW:
                size = (x1 - x0, y1 - y0)
            elif orientation == spec.ELEVATION_VIEW:
                size = (x1 - x0, z1 - z0)
            else:
                size = _iso_size(0.0)
            box = _view_box(view.Position, *size, view.ScaleRatio)
            if sheet.name == drawing.PIVOT_CAPTURE_SHEET and index == 0:
                plan, (bottom, top) = _capture_cluster_extent(0)
                span = max(p[0] for p in plan) - min(p[0] for p in plan) + max(p[1] for p in plan) - min(p[1] for p in plan)
                size = (span * math.sqrt(0.5) * OUTLINE_GROWTH[0],
                        (span * ISO / 2.0 + (top-bottom) * ISO) * OUTLINE_GROWTH[1])
                box = _view_box(view.Position, *size, view.ScaleRatio)
                if view.ScaleRatio[1] < doc.capture_fit_denominator:
                    box = (box[0], box[1], box[2] + 0.3, box[3])
            if view.crop is not None:
                offset, _radius = view.crop
                ratio = view.crop_scale[0] / view.crop_scale[1]
                centre = tuple(view.Position[i] + ratio * offset[i] for i in (0, 1))
                width, height = view.crop_outline_size
                box = (centre[0] - width / 2.0, centre[1] - height / 2.0,
                       centre[0] + width / 2.0, centre[1] + height / 2.0)
            if (doc.oversized == sheet.name
                    or (sheet.name == drawing.CARTRIDGE_SHEET
                        and view.ScaleRatio[1] < doc.inspection_fit_denominator)):
                # A native outline larger than the recipe's estimated room.
                return (box[0], box[1], box[2], box[3] + 0.3)
            return box

        view.ShowExploded = show_exploded
        view.SetViewPosition = move
        view.GetOutline = outline
        sheet.views.append(view)
        doc.events.append(("view", view.GetName2(), doc.bom_inserted))
        return view

    doc.ActivateSheet = activate
    doc.GetCurrentSheet = lambda: doc.sheets[doc.active]
    doc.GetSheetNames = lambda: physical_names
    doc.Sheet = lambda name: doc.sheets[name]
    def first_view():
        sheet = doc.sheets[doc.active]
        display_origin, display_scale = (0.017, -0.011), 0.25

        def lines(_crosshatch):
            result = []
            inverse = sheet.sketch.ModelToSketchTransform.Inverse()
            for index, (owner, a, b) in enumerate(doc.sketch_lines):
                if owner != sheet.name or index == doc.hidden_line:
                    continue
                points = []
                for raw in (a, b):
                    x, y, z = inverse.apply(raw)
                    x = x * doc.display_scale + doc.display_shift[0]
                    y = y * doc.display_scale + doc.display_shift[1]
                    points.extend(((x - display_origin[0]) / display_scale,
                                   (y - display_origin[1]) / display_scale, z))
                result.extend((0.0, 0.0, 0.0, 0.0, 0.0, 0.0, *points))
            return tuple(result)

        return SimpleNamespace(
            GetNextView=lambda: sheet.views[0] if sheet.views else None,
            GetSketch=lambda: sheet.sketch,
            GetLines4=lines,
            GetXform=lambda: (*display_origin, display_scale),
        )

    doc.GetFirstView = first_view
    doc.CreateDrawViewFromModelView3 = create_view
    def clear_selection(_all):
        doc.selected.clear()
        doc.selected_types.clear()

    doc.ClearSelection2 = clear_selection

    def zoom_to(x0, y0, _z0, x1, y1, _z1):
        doc.zoomed = True
        doc.zoom_centre = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)

    doc.ViewZoomTo2 = zoom_to
    doc.ViewZoomtofit2 = lambda: setattr(doc, "zoomed", False)
    doc.EditRebuild3 = lambda: True
    doc.GraphicsRedraw2 = lambda: None
    doc.EditSheet = lambda: doc.paper_edits.append(doc.active)

    def activate_view(name):
        views = doc.sheets[doc.active].views
        doc.active_view = next((v for v in views if v.GetName2() == name), None)
        return doc.active_view is not None

    doc.ActivateView = activate_view

    def select_segment(segment, append, data):
        if data.View is not doc.active_view or segment.GetSketch() is not doc.active_view.sketch:
            return False
        if not append:
            doc.selected.clear()
        doc.selected.append(segment)
        return True

    def create_circle(*coordinates):
        view = doc.active_view
        assert view is not None and doc.SketchManager.AddToDB is True
        centre, edge = (tuple(coordinates[i:i+3]) for i in (0, 3))
        circle = SimpleNamespace(
            centre=centre, radius=math.dist(centre, edge),
            ConstructionGeometry=False, GetType=lambda: 1, IsCircle=lambda: 1,
            owner=view.sketch,
        )
        circle.GetSketch = lambda: circle.owner
        circle.GetCenterPoint2 = lambda: SimpleNamespace(
            X=circle.centre[0], Y=circle.centre[1], Z=circle.centre[2],
        )
        circle.GetRadius = lambda: circle.radius
        circle.Select4 = lambda append, data: select_segment(circle, append, data)
        view.sketch.segments.append(circle)
        doc.crop_circles.append(circle)
        return circle

    def native_note(text, view, *, entity=None, world=None, linked=""):
        note = SimpleNamespace(text=text, position=[0.0, 0.0, 0.0],
                               PropertyLinkedText=linked, entity=entity,
                               world=world, view=view, landing_shift=(0.0, 0.0),
                               IsBomBalloon=lambda: False)
        format_ = SimpleNamespace(CharHeight=0.0035)
        annotation = SimpleNamespace(
            OwnerType=0, GetTextFormat=lambda _index: format_,
            GetAttachedEntities3=lambda: () if note.entity is None else (note.entity,),
            GetAttachedEntityCount3=lambda: int(note.entity is not None),
            GetAttachedEntityTypes=lambda: () if note.entity is None else (1,),
            GetLeaderCount=lambda: int(note.entity is not None),
            IsDangling=lambda: False, GetPosition=lambda: tuple(note.position),
            SetLeader3=lambda *_args: 0,
        )

        def set_position(x, y, z):
            note.position[:] = (x, y, z)
            return True

        def set_format(_index, _use_doc, value):
            format_.CharHeight = value.CharHeight
            return True

        def extent():
            lines = text.splitlines()
            h = format_.CharHeight
            return (note.position[0], note.position[1] - len(lines)*h*1.2, 0.0,
                    note.position[0] + max(map(len, lines))*h*0.55, note.position[1], 0.0)

        def leader(_index):
            point = view.ModelToViewTransform.apply(note.world)
            point = (point[0]+note.landing_shift[0], point[1]+note.landing_shift[1], 0.0)
            bounds = extent()
            label = text.splitlines()[0]
            if label in ("C3A CAP / BLOCK LAND", "C5B COTTER EYE / PRONGS"):
                # The 2f1b2c01 native capture registers the actual text-side
                # junction. Keep the physical transformed landing (and defect
                # shift) live: only the measured junction offset is replayed.
                # C5A now sits in the right column with its landing to the
                # left, where native attaches at the nearest (left) end
                # (5d622b853), the generic rule below.
                captured = _captured_capture_callout(label, note.position[:2])
                junction = captured.segments[0]
                return (junction.x0, junction.y0, 0.0, *point)
            x = bounds[3]+0.001 if point[0] > bounds[3] else bounds[0]-0.001
            return (x, note.position[1]-format_.CharHeight*0.6, 0.0, *point)

        annotation.SetPosition2 = set_position
        annotation.SetTextFormat = set_format
        annotation.GetLeaderPointsAtIndex = leader
        def glyph_data():
            height = format_.CharHeight
            return _CaptureNativeTextData([
                {
                    "t": line, "w": len(line) * height * 0.55, "h": height * 1.2,
                    "pos": (note.position[0], note.position[1] - index * height * 1.2, 0.0),
                    "ref": 0, "ang": 0.0,
                }
                for index, line in enumerate(note.text.splitlines())
            ])

        annotation.GetDisplayData = glyph_data
        note.GetAnnotation = lambda: annotation
        note.GetExtent = extent
        note.GetText = lambda: note.text
        note.annotation = annotation
        view.notes.append(note)
        return note

    def native_edge(component, stem, occurrence, endpoints, *, c2=False):
        """A finite physical segment in the occurrence's part-local metres."""
        a, b = (tuple(value / 1000.0 for value in point) for point in endpoints)
        origin, rows = spec.PLACEMENTS[stem][occurrence]
        # A model IComponent2: native reports the part file with Windows
        # separators; the leaf component's spelling differs only there.
        part_file = component.GetPathName().replace("/", "\\")
        edge = SimpleNamespace(
            GetComponent=lambda: raw(edge.owner), endpoints=(a, b), c2=c2,
            owner=SimpleNamespace(
                Name2=component.Name2,
                GetPathName=lambda: part_file,
                GetParent=lambda: None,
            ),
        )

        def closest(x, y, z):
            point = (x, y, z)
            direction = tuple(b[i] - a[i] for i in range(3))
            fraction = max(0.0, min(1.0,
                sum((point[i] - a[i]) * direction[i] for i in range(3))
                / sum(value * value for value in direction)
            ))
            local = tuple(a[i] + fraction * direction[i] for i in range(3))
            edge.world = tuple(
                origin[i] / 1000.0 + sum(local[k] * rows[k][i] for k in range(3))
                for i in range(3)
            )
            return (*local, fraction, 0.0)

        edge.GetClosestPointOn = closest
        closest(*a)
        edge.world_endpoints = tuple(
            tuple(origin[i] / 1000.0 + sum(p[k] * rows[k][i] for k in range(3))
                  for i in range(3))
            for p in (a, b)
        )
        return edge

    def reading_edges(view, component):
        if not any(leaf.Component is component and leaf.Visible for leaf in view.components):
            return ()
        index = doc.sheets[view.Sheet.name].views.index(view)
        edges = []
        for reading in drawing.capture_readings():
            if (reading.view_index != index
                    or spec.instance_name(reading.stem, reading.index) != component.Name2):
                continue
            c2 = reading.stem == spec.PIVOT_PIN and reading.text.startswith("C2 ")
            if c2:
                # A-A cuts the actual modeled flange flat from the Ø12.70
                # boss to R18. The drawing's edge-break limit is not a CAD cut.
                outer = spec.pivot_pin.FLANGE_DIA / 2.0
                boss = spec.retention.PIN_BOSS_DIAMETER / 2.0
                station = (spec.pivot_pin.FLANGE_BOTTOM_STATION
                           if reading.text.startswith("C2 LOWER")
                           else spec.pivot_pin.FLANGE_TOP_STATION)
                endpoints = ((-outer, 0.0, station), (-boss, 0.0, station))
                if doc.capture_edge_defect == "no-exact-point":
                    # Keep the real outer cylindrical wall, not a manufactured
                    # closest-point response at the requested flat-face point.
                    endpoints = (
                        (-outer, 0.0, spec.pivot_pin.FLANGE_BOTTOM_STATION),
                        (-outer, 0.0, spec.pivot_pin.FLANGE_TOP_STATION),
                    )
            elif reading.stem == spec.PIVOT_RETAINER and reading.text.startswith("C4 MOUTH"):
                # A-A cuts the retainer's bore as one vertical wall from the
                # washer floor to its top corner (jig-retention 1772 worker
                # 15, GENERATED section edges 126/127: (±5.1, 0, 0) to
                # (±5.1, 0, 4.1641) retainer mm). The top corner is the C4
                # criterion; the row's mid-height point is only where the
                # coordinate pick acquires the wall.
                x, y, top = reading.local_mm
                endpoints = ((x, y, 0.0), (x, y, top))
                if doc.capture_edge_defect == "short-mouth-wall":
                    # The retainer's own wall still runs through the
                    # mid-height acquisition point but stops below the top
                    # corner: the unchanged strict criterion must refuse it.
                    endpoints = ((x, y, 0.0), (x, y, 0.75 * top))
            elif reading.stem == spec.PIVOT_PIN and reading.text.startswith("C4A UPPER CROSS-HOLE"):
                # A-A cuts the pin's upper cross-hole boundary as one line
                # from the text-side journal wall to the far wall
                # (jig-retention 1772 worker 15, 58e34c: (-5, 0, 59.5) to
                # (+5, 0, 59.5) pin mm) and exposes the outer journal wall
                # rising from that corner to the lead chamfer. The corner is
                # the C4A criterion; the row's mid-wall point is only where
                # the coordinate pick acquires the wall.
                x, y, hole_top = reading.local_mm
                chamfer = spec.pivot_pin.OVERALL_LENGTH - spec.pivot_pin.LEAD_CHAMFER
                edges.append(native_edge(
                    component, reading.stem, reading.index,
                    ((x, y, hole_top), (-x, y, hole_top)),
                ))
                endpoints = ((x, y, hole_top), (x, y, chamfer))
                if doc.capture_edge_defect == "short-cross-hole-wall":
                    # The pin's own wall still runs through the mid-wall
                    # acquisition point but starts above the corner: the
                    # unchanged strict criterion must refuse it.
                    endpoints = ((x, y, hole_top + 0.25 * (chamfer - hole_top)), (x, y, chamfer))
            else:
                x, y, z = reading.local_mm
                endpoints = ((x - 0.25, y, z), (x + 0.25, y, z))
            if reading.view_index == 1 or (
                c2 and doc.capture_edge_defect == "wrong-section-depth"
            ):
                # The measured cotter prong shares the eye's projected XY,
                # but is 7.67055 mm away in depth. A section cannot do this.
                depth_mm = 7.67055 if reading.view_index == 1 else 1.0
                normal = (
                    view.right[1] * view.up[2] - view.right[2] * view.up[1],
                    view.right[2] * view.up[0] - view.right[0] * view.up[2],
                    view.right[0] * view.up[1] - view.right[1] * view.up[0],
                )
                _origin, rows = spec.PLACEMENTS[reading.stem][reading.index]
                delta = tuple(depth_mm * sum(normal[i] * row[i] for i in range(3))
                              for row in rows)
                if reading.view_index == 1:
                    tangent = tuple(sum(view.right[i] * row[i] for i in range(3))
                                    for row in rows)
                    endpoints = tuple(
                        tuple(reading.local_mm[i] + sign * 0.25 * tangent[i]
                              for i in range(3))
                        for sign in (-1.0, 1.0)
                    )
                endpoints = tuple(tuple(p[i] + delta[i] for i in range(3))
                                  for p in endpoints)
            edge = native_edge(component, reading.stem, reading.index, endpoints, c2=c2)
            edges.append(edge)
        if index == 2 and component.Name2 == spec.instance_name(spec.PIVOT_CLEVIS_PIN, 0):
            # A-A also cuts the clevis shank resting on the retainer: its lower
            # section line (clevis z = -R, from the head bearing face x = 0 to
            # the 1-1/4 length) lies at the retainer top's world height and
            # runs through both mouth corners (jig-retention 1772 worker 15:
            # centre z 98.86955, R2.33045, bottom 96.5391 = retainer top).
            radius = hardware.CLEVIS_DIA / 2.0
            edges.append(native_edge(
                component, spec.PIVOT_CLEVIS_PIN, 0,
                ((0.0, 0.0, -radius), (hardware.CLEVIS_LENGTH, 0.0, -radius)),
            ))
            # Loaded up through the pin's cross hole, the source geometry puts
            # its upper section line (clevis z = +R) at the pin's upper hole
            # boundary height, so it also runs through the C4A corner. Native
            # observed only the wrong CLEVIS owner at the row's old midpoint
            # (0, 0, hole top) (jig-retention 1772 worker 5, 650a9308; the
            # selected clevis curve was not logged). The fixture models that
            # adverse choice at the corner; it is not native-proven there.
            edges.append(native_edge(
                component, spec.PIVOT_CLEVIS_PIN, 0,
                ((0.0, 0.0, radius), (hardware.CLEVIS_LENGTH, 0.0, radius)),
            ))
        return tuple(edges)

    def select_edge(_name, kind, x, y, _z, _append, _mark, _callout, _option):
        assert kind == "EDGE"
        view = doc.active_view
        candidates = []
        index = doc.sheets[doc.active].views.index(view)
        components = []
        for reading in drawing.capture_readings():
            if reading.view_index != index:
                continue
            component = next(
                leaf.Component for leaf in view.components
                if leaf.Component.Name2 == spec.instance_name(reading.stem, reading.index)
            )
            if not any(known is component for known in components):
                components.append(component)
        for component in components:
            leaf = next(leaf for leaf in view.components if leaf.Component is component)
            for edge in reading_edges(view, component):
                owner = edge.owner
                if index in (2, 3):
                    # Section views own parts through the source assembly's
                    # own occurrence, one level up; its drawing component is
                    # named under a synthetic section root instead.
                    owner.Name2 = f"{source_root.Name2}/{component.Name2}"
                    owner.GetParent = lambda: raw(source_root)
                defect = doc.capture_edge_defect
                foreign_part = spec.COMPONENT_IDENTITIES[spec.PIVOT_BLOCK][0]
                if edge.c2:
                    if defect == "wrong-parent":
                        owner.Name2 = f"foreign-parent/{component.Name2}"
                    elif defect == "wrong-root":
                        # Same root name, but the parent is another assembly file.
                        owner.GetParent = lambda: raw(SimpleNamespace(
                            **{**vars(source_root), "GetPathName": lambda: str(
                                drawing.SOURCE.with_name(f"foreign-{drawing.SOURCE.name}")
                            )},
                        ))
                    elif defect == "wrong-occurrence":
                        owner.Name2 += "-2"
                    elif defect == "wrong-case":
                        owner.Name2 = owner.Name2.upper()
                    elif defect == "owner-backslashes":
                        owner.Name2 = owner.Name2.replace("/", "\\")
                    elif defect == "model-path":
                        owner.Name2 = component.Name2
                    elif defect == "drawing-name":
                        owner.Name2 = leaf.Name
                    elif defect == "null-owner":
                        edge.GetComponent = lambda: None
                    elif defect == "wrong-part-file":
                        owner.GetPathName = lambda: f"C:/native/{foreign_part}.SLDPRT"
                    elif defect == "empty-owner-path":
                        owner.GetPathName = lambda: ""
                    elif defect == "empty-leaf-path":
                        component.GetPathName = lambda: ""
                    elif defect == "null-parent":
                        owner.GetParent = lambda: None
                    elif defect == "extra-ancestor":
                        owner.GetParent = lambda: raw(SimpleNamespace(
                            **{**vars(source_root), "GetParent": lambda: raw(source_root)},
                        ))
                    elif defect == "parent-cycle":
                        cycle = SimpleNamespace(**vars(source_root))
                        cycle.GetParent = lambda cycle=cycle: raw(cycle)
                        owner.GetParent = lambda cycle=cycle: raw(cycle)
                    elif defect == "empty-parent-name":
                        owner.Name2 = f"/{component.Name2}"
                        owner.GetParent = lambda: raw(SimpleNamespace(
                            **{**vars(source_root), "Name2": ""},
                        ))
                    elif defect == "empty-parent-path":
                        owner.GetParent = lambda: raw(SimpleNamespace(
                            **{**vars(source_root), "GetPathName": lambda: ""},
                        ))
                    elif defect == "parent-read-error":
                        def failing_parent():
                            raise OSError("native parent dispatch failed")
                        owner.GetParent = failing_parent
                    if doc.bad_pick:
                        owner.Name2 = spec.instance_name(spec.PIVOT_BLOCK, 1)
                elif index == 1:
                    if defect == "plan-parent":
                        owner.GetParent = lambda: raw(source_root)
                    elif defect == "plan-qualified":
                        owner.Name2 = f"{source_root.Name2}/{component.Name2}"
                    elif defect == "plan-wrong-part-file":
                        owner.GetPathName = lambda: f"C:/native/{foreign_part}.SLDPRT"
                # A coordinate pick hits the nearest projected physical
                # segment; no reading's intended point enters the choice.
                pa, pb = (view.ModelToViewTransform.apply(p)[:2] for p in edge.world_endpoints)
                direction = (pb[0] - pa[0], pb[1] - pa[1])
                fraction = (
                    ((x - pa[0]) * direction[0] + (y - pa[1]) * direction[1])
                    / (direction[0] ** 2 + direction[1] ** 2)
                )
                clamped = max(0.0, min(1.0, fraction))
                hit = (pa[0] + clamped * direction[0], pa[1] + clamped * direction[1])
                interior = min(math.dist(hit, pa), math.dist(hit, pb)) > 1e-8
                candidates.append((math.dist((x, y), hit), interior, edge))
        nearest = min(distance for distance, _interior, _edge in candidates)
        tied = [item for item in candidates if item[0] - nearest <= 1e-8]
        # A vertex-shared pick resolves as jig-retention 1772 worker 9 did at
        # the retainer's top bore corner: the CLEVIS section line running
        # through that corner won over the retainer wall ending there.
        distance, _interior, edge = next((item for item in tied if item[1]), tied[0])
        doc.coordinate_picks.append(((x, y), doc.zoom_centre, tuple(candidates)))
        if doc.capture_edge_defect != "no-exact-point":
            assert distance < 1e-8
        if edge.c2 and doc.capture_edge_defect == "coordinate-foreign-owner":
            edge.owner.Name2 = spec.instance_name(spec.PIVOT_BLOCK, 0)
        assert doc.zoomed and doc.selected == []
        slots = [view, edge]
        types = [12, 1]
        if doc.edge_first:
            slots.reverse()
            types.reverse()
        defect = doc.capture_edge_defect if edge.c2 else None
        edge_slot = types.index(1)
        view_slot = types.index(12)
        if defect == "foreign-view":
            slots[view_slot] = doc.sheets[doc.active].views[0]
        elif defect == "wrong-context-type":
            types[view_slot] = 2
        elif defect == "extra-foreign-view":
            slots.append(doc.sheets[doc.active].views[0])
            types.append(12)
        elif defect == "multiple-edge-slots":
            slots.append(SimpleNamespace(**vars(edge)))
            types.append(1)
        elif defect == "null-edge":
            slots[edge_slot] = None
        elif defect == "no-edge":
            slots, types = [view], [12]
        elif defect == "duplicate-visible-leaf":
            leaf = next(leaf for leaf in view.components
                        if leaf.Component.Name2 == spec.instance_name(spec.PIVOT_PIN, 0))
            view.components.append(SimpleNamespace(**vars(leaf)))
        elif defect == "hidden-visible-leaf":
            next(leaf for leaf in view.components
                 if leaf.Component.Name2 == spec.instance_name(spec.PIVOT_PIN, 0)).Visible = False
        doc.selected[:] = [raw(item) if item is not None else None for item in slots]
        doc.selected_types[:] = types
        doc.pick_slots.append((tuple(slots), tuple(types)))
        return True

    def selection_point(index, mark, x, y, z):
        assert (index, mark, z) == (1, -1, 0.0)
        doc.selection_point = (x, y)
        entity, = doc.selected
        a, b = entity.world_endpoints
        view = doc.active_view
        pa, pb = (view.ModelToViewTransform.apply(p) for p in (a, b))
        direction = (pb[0] - pa[0], pb[1] - pa[1])
        fraction = max(0.0, min(1.0,
            ((x - pa[0]) * direction[0] + (y - pa[1]) * direction[1])
            / sum(value * value for value in direction)
        ))
        entity.world = tuple(a[i] + fraction * (b[i] - a[i]) for i in range(3))
        return True

    def insert_note(text):
        entity, = doc.selected
        note = native_note(text, doc.active_view, entity=entity, world=entity.world)
        if doc.bad_attachment:
            note.entity = object()
        if doc.capture_edge_defect == "plan-wrong-paper" and text.startswith("C5B COTTER"):
            note.landing_shift = (0.001, 0.0)
        doc.attached_notes.append(note)
        return note

    doc.Extension = SimpleNamespace(SelectByID2=select_edge)
    doc.SelectionManager = SimpleNamespace(
        CreateSelectData=lambda: SimpleNamespace(View=None),
        GetSelectedObjectCount2=lambda _mark: len(doc.selected),
        GetSelectedObject6=lambda index, _mark: (
            raw(unraw(doc.selected[index-1])) if doc.selected_types else doc.selected[index-1]
        ),
        GetSelectedObjectType3=lambda index, _mark: (
            doc.selected_types[index-1] if doc.selected_types else 1
        ),
        SetSelectionPoint2=selection_point,
    )
    doc.InsertNote = insert_note

    def create_section(x, y, z, letter, options, excluded, depth):
        assert doc.bom_inserted is False
        assert options == 0x1 | 0x8 | 0x10
        assert excluded is None and depth == 0.0
        if doc.bad_section:
            return None
        line, = doc.selected
        parent = doc.active_view
        inverse = parent.sketch.ModelToSketchTransform.Inverse()
        a, b = (inverse.apply(point)[:2] for point in line.points)
        dx, dy = b[0]-a[0], b[1]-a[1]
        axis = tuple(dx*parent.right[i] + dy*parent.up[i] for i in range(3))
        length = math.sqrt(sum(v*v for v in axis))
        view = create_view(parent.model_path, spec.PLAN_VIEW, x, y, z)
        view.right, view.up = tuple(v/length for v in axis), (0.0, 0.0, 1.0)
        view.ReferencedConfiguration = parent.ReferencedConfiguration
        section = SimpleNamespace(label=letter, hatch=False, partial=True,
                                  cut_only=False, reversed=False, ExcludeFasteners=False,
                                  line_shift=(0.0, 0.0, 0.0), parent=parent, line=line)
        section.GetAutoHatch = lambda: section.hatch
        section.SetAutoHatch = lambda value: setattr(section, "hatch", value)
        section.GetLabel = lambda: section.label
        def set_label(value):
            section.label = value
            return 0
        section.SetLabel2 = set_label
        section.GetView = lambda: section.parent
        section.GetPartialSection = lambda: section.partial
        section.GetDisplayOnlySurfaceCut = lambda: section.cut_only
        section.SetDisplayOnlySurfaceCut = lambda value: setattr(section, "cut_only", value)
        section.GetReversedCutDirection = lambda: section.reversed
        section.SetReversedCutDirection = lambda value: setattr(section, "reversed", value)
        # GetLineInfo exposes the actual CreateLine sketch coordinates. Only
        # arrow/text annotations below use the inverse-to-paper endpoints.
        section.GetLineInfo = lambda: tuple(
            point[i] + section.line_shift[i] for point in line.points for i in range(3)
        )
        section.GetArrowInfo = lambda: (*a, 0.0, a[0], a[1]+0.002, 0.0,
                                       *b, 0.0, b[0], b[1]+0.002, 0.0)
        section.GetTextInfo = lambda: (a[0]+0.002, a[1], 0.0, b[0]+0.002, b[1], 0.0)
        view.section = section
        native_note(f"SECTION {letter}-{letter}", view, linked="<VLLABEL> <VLSCALEV>")
        return view

    doc.CreateSectionViewAt5 = create_section

    def create_line(x0, y0, z0, x1, y1, z1):
        if doc.active_view is not None:
            assert doc.SketchManager.AddToDB is True
            points = ((x0, y0, z0), (x1, y1, z1))
            view = doc.active_view
            segment = SimpleNamespace(
                points=points, GetType=lambda: 0, ConstructionGeometry=False,
                GetSketch=lambda: view.sketch,
            )
            segment.GetStartPoint2 = lambda: SimpleNamespace(
                X=segment.points[0][0], Y=segment.points[0][1], Z=segment.points[0][2],
            )
            segment.GetEndPoint2 = lambda: SimpleNamespace(
                X=segment.points[1][0], Y=segment.points[1][1], Z=segment.points[1][2],
            )
            segment.Select4 = lambda append, data: select_segment(segment, append, data)
            view.sketch.segments.append(segment)
            doc.section_segments.append(segment)
            return segment
        assert doc.paper_edits[-1] == doc.active
        assert doc.SketchManager.AddToDB is True
        index = len(doc.sketch_lines)
        sheet = doc.sheets[doc.active]
        doc.sketch_lines.append((doc.active, (x0, y0, z0), (x1, y1, z1)))

        def endpoint(which):
            x, y, z = doc.sketch_lines[index][which]
            return SimpleNamespace(X=x, Y=y, Z=z)

        segment = SimpleNamespace(
            GetSketch=lambda: sheet.sketch,
            GetType=lambda: 0,
            ConstructionGeometry=False,
            GetStartPoint2=lambda: endpoint(1),
            GetEndPoint2=lambda: endpoint(2),
        )
        doc.sketch_segments.append(segment)
        return segment

    doc.SketchManager = SimpleNamespace(AddToDB=False, CreateLine=create_line, CreateCircle=create_circle)

    def member(obj, name):
        value = getattr(obj, name)
        return value() if callable(value) else value

    adapter = SimpleNamespace(
        currentModel=doc, _attempt=lambda callback, **_kwargs: callback(), _get_attr_or_call=member,
        swApp=SimpleNamespace(
            GetMathUtility=lambda: SimpleNamespace(CreatePoint=_InspectionMathPoint),
            IsSame=lambda a, b: 1 if unraw(a) is unraw(b) else 0,
        ),
    )
    class RawDispatch:
        """Selection dispatch exposes no typed members before native binding."""
        def __init__(self, value):
            self.value = value

    def raw(value):
        return RawDispatch(value) if doc.raw_picks else value

    def unraw(value):
        return value.value if isinstance(value, RawDispatch) else value

    def bind(value, interface):
        doc.binding_calls.append((value, interface))
        return unraw(value)

    monkeypatch.setattr(drawing, "_bind", bind)
    for module in (drawing, _drawing_common, _drawing_view_configuration,
                   _drawing_sections, _drawing_selection, _drawing_balloons,
                   _drawing_detail_crop, _section_axis):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        _drawing_common._sw_type_info, "early_bound_or_flag",
        lambda value, *_interface: value,
    )
    monkeypatch.setattr(
        _drawing_common._sw_type_info, "early_bound", lambda value, _interface: value
    )
    for module in (drawing, _drawing_common._sw_drawing, _drawing_projection, _drawing_sections):
        monkeypatch.setattr(module, "double_array", lambda values: values)
    monkeypatch.setattr(
        _drawing_projection, "_com_invoke",
        lambda obj, _interface, name, *args: getattr(obj, name)(*args)
        if callable(getattr(obj, name)) else getattr(obj, name),
    )
    for module in (drawing, _drawing_common):
        monkeypatch.setattr(
            module, "set_high_quality_shaded_with_edges", lambda *args, **kwargs: None
        )
    for module in (drawing, _drawing_common, _drawing_view_configuration, _drawing_sections, _drawing_balloons, _section_axis):
        monkeypatch.setattr(module, "rebuild_drawing", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda _adapter, view: setattr(view, "mode", 2))
    for name in ("_create_package_sheets", "_require_view_axes", "_add_plan_tags"):
        monkeypatch.setattr(drawing, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "_cl_tip_setting", lambda *_args: lambda: None)
    monkeypatch.setattr(
        drawing, "_fit_cluster_view",
        lambda _adapter, _view, cluster, _configuration, *, label: cluster.scale,
    )
    def insert_bom(*_args, **_kwargs):
        doc.bom_inserted = True
        doc.events.append(("bom", None, True))
        return _Table(spec.BOM_ORDER)
    monkeypatch.setattr(drawing, "insert_bom_table", insert_bom)
    monkeypatch.setattr(drawing, "_bom_feature_name", lambda _table: "JigBOM")

    def balloons(_adapter, view, cluster, _items, _bom):
        centre = drawing._region_center(view.GetOutline())
        stems = (*cluster.stems, spec.BEARING) if cluster.sheet == drawing.PIVOT_CAPTURE_SHEET else cluster.stems
        used_bearings = 0
        landings = []
        for stem in stems:
            occurrence = used_bearings if stem == spec.BEARING else 0
            if stem == spec.BEARING:
                used_bearings += 1
            landings.append(SimpleNamespace(
                stem=stem, instance=spec.instance_name(stem, occurrence), view=view,
                note=SimpleNamespace(
                    circle=(*centre, drawing.BALLOON_RADIUS),
                    IsBomBalloon=lambda: True,
                    GetBomBalloonText=lambda _upper, stem=stem: str(spec.ITEM_NUMBERS[stem]),
                ),
            ))
            view.notes.append(landings[-1].note)
        doc.balloon_landings.extend(landings)
        return landings

    monkeypatch.setattr(drawing, "_balloon_cluster", balloons)
    monkeypatch.setattr(
        drawing, "rendered_balloon_circle", lambda note, **_kwargs: note.circle
    )

    def note(_adapter, text, x, y, *, height=None):
        doc.notes.append((doc.active, text, (x, y)))
        if doc.active == drawing.BOM_SHEET and text.startswith("PURCHASED KIT IDENTITY:"):
            doc.kit_note = _KitBomNote(text, (x, y), width=0.145, move="applied")
            return doc.kit_note
        if doc.active_view is None:
            return SimpleNamespace(GetText=lambda: text)
        result = native_note(text, doc.active_view)
        annotation = result.GetAnnotation()
        annotation.GetTextFormat(0).CharHeight = height or 0.0035
        annotation.SetPosition2(x, y, 0.0)
        return result

    monkeypatch.setattr(drawing, "add_note", note)
    monkeypatch.setattr(
        _drawing_common, "apply_custom_properties", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        _drawing_common, "assert_asme_b_sheet", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(_drawing_common, "_build_id", lambda: "offline-property-contract")

    class SaveBoundary(Exception):
        pass

    def stop_before_save(*args, **kwargs):
        raise SaveBoundary

    monkeypatch.setattr(_drawing_common, "save_drawing", stop_before_save)
    return SimpleNamespace(
        adapter=adapter, doc=doc, source=source, source_root=source_root,
        save_boundary=SaveBoundary,
    )


def test_every_physical_sheet_links_to_its_actual_live_model_view(
    native_property_package,
) -> None:
    package = native_property_package
    scales, _settled = drawing._place_package(package.adapter)
    assert tuple(scales) == tuple(package.doc.sheets) == drawing.SHEET_NAMES
    bom_reference, = package.doc.sheets[drawing.BOM_SHEET].views
    kit_extent = drawing._kit_bom_note_extent(package.doc.kit_note)
    assert _inside_sheet(kit_extent)
    assert kit_extent[1] - drawing.TITLE_BLOCK[3] >= drawing.REGION_GAP
    assert bom_reference.GetOutline()[1] - kit_extent[3] >= drawing.REGION_GAP
    with pytest.raises(package.save_boundary):
        asyncio.run(drawing.finalize_drawing(
            package.adapter,
            drawing.OUTPUTS,
            layout=drawing.SPEC.layout,
            pdf_title="offline property association",
            scale=drawing.SHEET_SCALE,
            expected_sheet_names=drawing.SHEET_NAMES,
            sheet_layouts=drawing.SHEET_LAYOUTS,
            sheet_scales=scales,
        ))
    links = []
    for name, sheet in package.doc.sheets.items():
        assert len(sheet.views) == (
            4 if name == drawing.PIVOT_CAPTURE_SHEET
            else 2 if name == drawing.ASSEMBLED_SHEET else 1
        )
        # Read what the real finalizer wrote, resolving the name against this
        # physical sheet's real placement results, not a recipe-owned mapping.
        linked = next(
            view for view in sheet.views
            if view.GetName2() == sheet.CustomPropertyView
        )
        assert linked is sheet.views[0]
        assert linked.Sheet is sheet
        assert linked.model_path == str(drawing.SOURCE)
        assert linked.ReferencedDocument is package.source
        assert sheet.properties[7] is False  # no inherited template source
        assert linked.ReferencedConfiguration == (
            drawing.ASSEMBLY_VIEW_CONFIGURATION if name == drawing.CAPTURE_SHEET
            else drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
        assert linked.IsExploded() == (name in {c.sheet for c in drawing.CLUSTERS})
        links.append(linked)
    # A source-property edit is seen through every native association. No
    # snapshot of today's Title (or its other model properties) is substituted.
    package.source.properties["Title"] = "changed after property association"
    assert all(
        view.ReferencedDocument.GetCustomInfoValue("", "Title")
        == "changed after property association"
        for view in links
    )
    for sheet, region in drawing.NOTES_REFERENCE_REGIONS.items():
        view = package.doc.sheets[sheet].views[0]
        assert tuple(view.ScaleRatio) == drawing.NOTES_REFERENCE_SCALE
        assert _inside(view.GetOutline(), region)
        assert [text for name, text, _xy in package.doc.notes
                if name == sheet and text.startswith("REFERENCE ")] == ["REFERENCE 1:20"]


@pytest.mark.parametrize(
    "sheet",
    (
        drawing.STEPS_SHEET, drawing.STEPS_CONTINUED_SHEET, drawing.CARTRIDGE_SHEET,
        drawing.TOP_CAPTURE_SHEET, drawing.CAPTURE_SHEET,
    ),
)
def test_placed_instruction_notes_and_visible_source_view_stay_on_clear_paper(
    native_property_package, sheet,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    view, = package.doc.sheets[sheet].views
    outline = view.GetOutline()
    notes = [
        _note_box(text, xy)
        for name, text, xy in package.doc.notes
        if name == sheet
    ]
    assert notes
    assert _inside_sheet(outline)
    for index, box in enumerate(notes):
        assert _inside_sheet(box)
        assert not _overlap(box, outline)
        assert all(not _overlap(box, other) for other in notes[index + 1:])
    assert tuple(view.ScaleRatio) == (
        drawing.ISOMETRIC_SCALE if sheet == drawing.CAPTURE_SHEET
        else drawing.NOTES_REFERENCE_SCALE
    )
    assert view.IsExploded() is False


def test_c2a_section_is_real_sheet_ink_beside_the_live_source_view(
    native_property_package,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    assert package.doc.paper_edits == [drawing.CARTRIDGE_SHEET]
    assert package.doc.SketchManager.AddToDB is False
    sheet = package.doc.sheets[drawing.CARTRIDGE_SHEET]
    transform = sheet.sketch.ModelToSketchTransform
    assert transform.scale == 20.0
    assert package.doc.sketch_lines == [
        (drawing.CARTRIDGE_SHEET,
         transform.apply((*start, 0.0)), transform.apply((*end, 0.0)))
        for start, end in drawing.pin_tip_inspection_lines()
    ]
    view, = package.doc.sheets[drawing.CARTRIDGE_SHEET].views
    assert view.model_path == str(drawing.SOURCE)
    for sheet, start, end in package.doc.sketch_lines:
        inverse = transform.Inverse()
        start, end = inverse.apply(start), inverse.apply(end)
        box = (
            min(start[0], end[0]), min(start[1], end[1]),
            max(start[0], end[0]), max(start[1], end[1]),
        )
        assert _inside(box, drawing.PIN_TIP_INSPECTION_REGION)
        assert not _overlap(box, view.GetOutline())
        for owner, text, xy in package.doc.notes:
            if owner == sheet:
                assert not _overlap(box, _note_box(text, xy))
    drawing._assert_pin_tip_inspection(package.adapter, package.doc.sketch_segments)


@pytest.mark.parametrize("defect", (
    "scaled-endpoints", "shifted-endpoints", "changed-sheet-scale",
    "scaled-display", "shifted-display", "missing-display-line", "wrong-owner",
))
def test_c2a_settled_proof_refuses_scaled_displaced_or_missing_native_ink(
    native_property_package, defect,
) -> None:
    package = native_property_package
    sheet = package.doc.sheets[drawing.CARTRIDGE_SHEET]
    sheet.SetScale(1.0, 20.0, False, False)
    settled = drawing._place_pin_tip_inspection(package.adapter)
    if defect in {"scaled-endpoints", "shifted-endpoints"}:
        transform = sheet.sketch.ModelToSketchTransform
        inverse = transform.Inverse()
        lines = []
        for owner, start, end in package.doc.sketch_lines:
            points = []
            for raw in (start, end):
                x, y, z = inverse.apply(raw)
                if defect == "scaled-endpoints":
                    x, y = x / 20.0, y / 20.0  # the observed false-green size
                else:
                    x += 0.001  # still inside the region: bounds alone miss it
                points.append(transform.apply((x, y, z)))
            lines.append((owner, *points))
        package.doc.sketch_lines[:] = lines
    elif defect == "changed-sheet-scale":
        sheet.SetScale(1.0, 25.0, False, False)
    elif defect == "scaled-display":
        package.doc.display_scale = 1.0 / 20.0
    elif defect == "shifted-display":
        package.doc.display_shift = (0.001, 0.0)
    elif defect == "missing-display-line":
        package.doc.hidden_line = 0
    else:
        package.doc.sketch_segments[0].GetSketch = lambda: object()
    with pytest.raises(RuntimeError, match="C2A functional inspection"):
        settled()


@pytest.mark.parametrize("previous_add_to_db", (False, True))
def test_c2a_native_sketch_refusal_restores_database_mode(
    native_property_package, previous_add_to_db,
) -> None:
    package = native_property_package
    manager = package.doc.SketchManager
    manager.AddToDB = previous_add_to_db
    manager.CreateLine = lambda *_coordinates: None
    with pytest.raises(RuntimeError, match="C2A functional inspection"):
        drawing._place_pin_tip_inspection(package.adapter)
    assert manager.AddToDB is previous_add_to_db
    assert package.doc.paper_edits == [drawing.CARTRIDGE_SHEET]
    assert not package.doc.notes


@pytest.mark.parametrize("denominator", (20.0, 25.0, 30.0))
def test_c2a_is_authored_at_fitted_scale_before_real_finalizer_repins_it(
    native_property_package, denominator,
) -> None:
    package = native_property_package
    package.doc.inspection_fit_denominator = denominator
    scales, settled = drawing._place_package(package.adapter)
    sheet = package.doc.sheets[drawing.CARTRIDGE_SHEET]
    assert scales[drawing.CARTRIDGE_SHEET] == (1.0, denominator)
    assert sheet.properties[2:4] == [1.0, denominator]
    before = list(package.doc.sketch_lines)
    with pytest.raises(package.save_boundary):
        asyncio.run(drawing.finalize_drawing(
            package.adapter, drawing.OUTPUTS, layout=drawing.SPEC.layout,
            pdf_title="C2A scale lifecycle", scale=drawing.SHEET_SCALE,
            expected_sheet_names=drawing.SHEET_NAMES,
            sheet_layouts=drawing.SHEET_LAYOUTS, sheet_scales=scales,
            settled_checks=(settled[-2],),
        ))
    assert sheet.properties[2:4] == [1.0, denominator]
    assert package.doc.sketch_lines == before


@pytest.mark.parametrize(
    "sheet",
    (
        drawing.STEPS_SHEET, drawing.STEPS_CONTINUED_SHEET,
        drawing.CARTRIDGE_SHEET, drawing.TOP_CAPTURE_SHEET,
    ),
)
def test_instruction_reference_refuses_a_native_outline_outside_its_room(
    native_property_package, sheet,
) -> None:
    package = native_property_package
    package.doc.oversized = sheet
    with pytest.raises(RuntimeError, match="leaves"):
        drawing._place_package(package.adapter)


def test_capture_places_four_real_views_before_bom_with_one_exploded_balloon_owner(
    native_property_package,
) -> None:
    package = native_property_package
    scales, settled = drawing._place_package(package.adapter)
    sheet = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET]
    exploded, locator, main, bolt = sheet.views
    assert [view.IsExploded() for view in sheet.views] == [True, False, False, False]
    assert [view.ReferencedConfiguration for view in sheet.views] == [
        drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        drawing.ASSEMBLY_VIEW_CONFIGURATION,
        drawing.ASSEMBLY_VIEW_CONFIGURATION,
        drawing.ASSEMBLY_VIEW_CONFIGURATION,
    ]
    assert tuple(exploded.ScaleRatio) == scales[sheet.name] == (1.0, 4.0)
    assert tuple(locator.ScaleRatio) == (1, 4)
    assert tuple(main.ScaleRatio) == (1, 1)
    assert tuple(bolt.ScaleRatio) == (1, 1)
    cluster = next(c for c in drawing.CLUSTERS if c.sheet == sheet.name)
    installed = drawing.capture_support_instances(cluster, 0) | {spec.instance_name(spec.CARRIER, 0)}
    for index, view in enumerate(sheet.views):
        shown = {leaf.Component.Name2 for leaf in view.components if leaf.Visible}
        assert shown == (drawing.capture_support_instances(cluster, 0) if index == 0 else installed)
        assert _inside(view.GetOutline(), drawing.CAPTURE_VIEW_REGIONS[index])
    assert not exploded.IsCropped()
    assert all(view.IsCropped() for view in (locator, main, bolt))
    assert len(package.doc.section_segments) == 2
    assert len(package.doc.crop_circles) == len(package.doc.crop_calls) == 3
    for index, model_radius in ((1, 0.055), (2, 0.030), (3, 0.014)):
        view = sheet.views[index]
        circle = package.doc.crop_circles[index - 1]
        assert package.doc.crop_calls[index - 1] == (view, circle)
        owner = circle.GetSketch()
        assert owner is not view.sketch and owner.view is view
        assert any(segment is circle for segment in owner.GetSketchSegments())
        assert not any(segment is circle for segment in view.GetSketch().GetSketchSegments())
        assert tuple(view.ScaleRatio) == view.crop_scale
        assert view.post_crop_scale_writes == []
        assert circle.GetType() == circle.IsCircle() == 1
        assert circle.ConstructionGeometry is False
        point = circle.GetCenterPoint2()
        assert (point.X, point.Y, point.Z) == circle.centre
        assert circle.GetRadius() == circle.radius
        assert view.crop[1] == pytest.approx(model_radius)
    assert [segment.GetType() for segment in locator.sketch.GetSketchSegments()] == [0, 0]
    assert package.doc.SketchManager.AddToDB is False
    for section, letter in ((main.GetSection(), "A"), (bolt.GetSection(), "B")):
        assert section.GetView() is locator
        assert section.GetAutoHatch() and section.GetPartialSection()
        assert not section.ExcludeFasteners and not section.GetDisplayOnlySurfaceCut()
        assert section.GetLabel() == letter
    assert all(not after_bom for event, _name, after_bom in package.doc.events if event == "view")
    landings = [item for item in package.doc.balloon_landings if item.stem in cluster.stems]
    assert len(landings) == 9 and all(item.view is exploded for item in landings)
    assert len(package.doc.balloon_landings) == len(spec.BOM_ORDER) + 1
    bearings = [item for item in landings if item.stem == spec.BEARING]
    assert {item.instance for item in bearings} == {spec.instance_name(spec.BEARING, i) for i in (0, 1)}
    assert all(item.note.GetBomBalloonText(True) == "14" for item in bearings)
    assert len(package.doc.attached_notes) == len(drawing.capture_readings())
    for note, reading in zip(package.doc.attached_notes, drawing.capture_readings(), strict=True):
        wanted = spec.instance_name(reading.stem, reading.index)
        assert wanted in installed
        leaf, = (leaf for leaf in note.view.components if leaf.Component.Name2 == wanted)
        owner = drawing._bind(note.entity.GetComponent(), "IComponent2")
        root = package.source_root
        parent = drawing._bind(owner.GetParent(), "IComponent2")
        if reading.view_index == 1:
            assert owner.Name2 == wanted and parent is None
        else:
            # Owned through the source assembly's own occurrence, never the
            # drawing's synthetic section root.
            assert owner.Name2 == f"{root.Name2}/{wanted}"
            assert parent.Name2 == root.Name2 and parent.GetParent() is None
            assert parent.GetPathName() == str(drawing.SOURCE)
            assert leaf.Name != owner.Name2 and not leaf.Name.startswith(f"{root.Name2}/")
        assert Path(owner.GetPathName()).resolve() == Path(leaf.Component.GetPathName()).resolve()
        assert owner.GetPathName() != leaf.Component.GetPathName()
    targets = []
    for reading in drawing.capture_readings():
        view = sheet.views[reading.view_index]
        world = drawing._capture_world_point(reading)
        targets.append((reading.view_index, world))
        point = drawing.model_point_in_view(package.adapter, view, world, label="capture crop reading")
        ratio = view.ScaleRatio[0] / view.ScaleRatio[1]
        offset, radius = view.crop
        centre = tuple(view.Position[i] + ratio * offset[i] for i in (0, 1))
        assert math.dist(point, centre) < ratio * radius
    # A carrier point shared by C4 and C5A needs one combined attached label,
    # not stacked arrows ending at precisely the same physical location.
    assert len(set(targets)) == len(targets)
    settled[-1]()


@pytest.mark.parametrize("view_index,scale,model_radius,paper_radius,region", (
    (2, (1, 1), 0.030, 0.030, (0.264, 0.106, 0.362, 0.200)),
    (3, (1, 1), 0.014, 0.014, (0.352, 0.219, 0.416, 0.266)),
))
def test_capture_sections_native_scale_precedes_crop_without_shrinking_model_fence(
    native_property_package, view_index, scale, model_radius, paper_radius, region,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    section = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[view_index]
    profile = package.doc.crop_circles[view_index - 1]
    assert tuple(section.ScaleRatio) == section.crop_scale == scale
    assert section.post_crop_scale_writes == []
    assert profile.GetRadius() == pytest.approx(model_radius)
    assert section.crop[1] == pytest.approx(model_radius)
    inverse = profile.GetSketch().ModelToSketchTransform.Inverse()
    centre = inverse.apply(profile.centre)
    rim = inverse.apply((profile.centre[0] + profile.GetRadius(), *profile.centre[1:]))
    assert math.dist(centre, rim) == pytest.approx(paper_radius)
    assert drawing.CAPTURE_VIEW_REGIONS[view_index] == region
    drawing._assert_capture_crop(package.adapter, section, view_index, profile)


@pytest.mark.parametrize("view_index,scale,native_outline,refusal", (
    (2, (1, 1), (
        0.27083100196371956, 0.24606200349283217,
        0.3737219227586998, 0.3340379981999397,
    ), "width 102[.]9 mm > 98[.]0 mm"),
    (3, (1, 1), (0.355, 0.215, 0.414, 0.265), "height 50[.]0 mm > 47[.]0 mm"),
))
def test_capture_sections_still_refuse_oversized_native_extents(
    native_property_package, view_index, scale, native_outline, refusal,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    section = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[view_index]
    # The actual 4e7 A-A extent at its former 39 mm crop stays a refusal in
    # the 1:1 field, and B-B's 1:1 field never licenses a box taller than it.
    section.GetOutline = lambda: native_outline
    with pytest.raises(RuntimeError, match=refusal):
        drawing._fit_capture_view(
            package.adapter, section, drawing.CAPTURE_VIEW_REGIONS[view_index], (scale,),
            crop_profile=package.doc.crop_circles[view_index - 1], label="jig capture section",
        )
    assert tuple(section.ScaleRatio) == scale
    assert section.post_crop_scale_writes == []


def test_capture_bolt_section_field_holds_the_observed_native_1_to_1_extent(
    native_property_package,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    section = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[3]
    region = drawing.CAPTURE_VIEW_REGIONS[3]
    # 49385: B-B's native padded 1:1 extent was 42.076 x 44.776 mm; centred,
    # it fits the top-right field that replaced the 43 x 35 mm 1:2 one.
    width, height = 0.3904130000444241 - 0.34833699958956615, 0.3798879901473522 - 0.3351120025212765
    cx, cy = (region[0] + region[2]) / 2.0, (region[1] + region[3]) / 2.0
    section.GetOutline = lambda: (cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0)
    assert drawing._fit_capture_view(
        package.adapter, section, region, ((1, 1),),
        crop_profile=package.doc.crop_circles[2], label="jig capture section",
    ) == (1, 1)
    caption_x, caption_y = drawing.CAPTURE_SECTION_CAPTIONS[1]
    assert caption_x == pytest.approx(cx)
    # The caption's top-centre point (its text tops about 1.9 mm lower)
    # stands beneath the measured extent.
    assert cy - height / 2.0 - caption_y > 0.0



def test_capture_sections_use_actual_distinct_longitudinal_and_bolt_planes() -> None:
    def distance_to_plane(point, letter):
        a, b = drawing.capture_cut_points(letter)
        dx, dy = b[0]-a[0], b[1]-a[1]
        return abs((point[0]-a[0])*dy - (point[1]-a[1])*dx) / math.hypot(dx, dy)

    for origin in (spec.PIVOT_PIN_ORIGINS[0], spec.PIVOT_CLEVIS_PIN_PLACEMENTS[0][0]):
        assert distance_to_plane(tuple(v/1000.0 for v in origin), "A") < 1e-12
    for reading in drawing.capture_readings():
        if reading.view_index not in (2, 3):
            continue
        point = drawing._capture_world_point(reading)
        letter = "A" if reading.view_index == 2 else "B"
        assert distance_to_plane(point, letter) < 1e-12
        if reading.stem == spec.PIVOT_CAP_SCREW:
            # The real underhead footprint is NOT on the pivot/clevis plane.
            assert distance_to_plane(point, "A") > 0.001
            assert reading.local_mm[2] == 0.0
        if reading.stem == spec.CARRIER:
            assert point[2]*1000.0 == pytest.approx(spec.trammel.CARRIER_TOP_Z)
        if reading.stem == spec.PIVOT_CLEVIS_PIN:
            # The attachment is on the represented head, not its larger
            # purchased-envelope limits, which lie outside the actual body.
            x, y, z = reading.local_mm
            assert x == pytest.approx(-spec.clevis_pin.CLEVIS_HEAD_HEIGHT)
            assert y*y + z*z == pytest.approx((spec.clevis_pin.CLEVIS_HEAD_DIA / 2.0)**2)
        if reading.stem == spec.PIVOT_RETAINER and reading.local_mm[2] == spec.pivot_retainer.THICKNESS:
            # The native retainer is a square-edged annulus. Shop relief is
            # inspected at that real mouth, not projected from an unmodelled
            # maximum edge-break envelope.
            x, y, _z = reading.local_mm
            assert x*x + y*y == pytest.approx((spec.pivot_retainer.BORE_DIA / 2.0)**2)


def test_capture_exploded_fit_does_not_shrink_assembled_reading_scales(native_property_package) -> None:
    package = native_property_package
    package.doc.capture_fit_denominator = 8.0
    scales, settled = drawing._place_package(package.adapter)
    exploded, locator, main, _bolt = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views
    assert tuple(exploded.ScaleRatio) == scales[drawing.PIVOT_CAPTURE_SHEET] == (1.0, 8.0)
    assert tuple(locator.ScaleRatio) == (1, 4)
    assert tuple(main.ScaleRatio) == (1, 1)
    settled[-1]()


@pytest.mark.parametrize("defect, refusal", (
    ("bad_section", "failed to create section view"),
    ("crop_status", "native crop failed"),
    ("bad_crop", "native crop failed"),
    ("bad_pick", "own edge"),
    ("bad_attachment", "lost its edge attachment"),
))
def test_capture_refuses_real_creation_crop_and_attachment_failures(
    native_property_package, defect, refusal,
) -> None:
    package = native_property_package
    setattr(package.doc, defect, 0 if defect == "crop_status" else True)
    with pytest.raises(RuntimeError, match=refusal):
        drawing._place_package(package.adapter)
    assert not package.doc.bom_inserted


@pytest.mark.parametrize("edge_first", (False, True))
@pytest.mark.parametrize("raw_picks", (False, True))
@pytest.mark.parametrize("owner_form", (None, "owner-backslashes"))
def test_capture_native_two_slot_pick_reselects_only_the_exact_edge(
    native_property_package, edge_first, raw_picks, owner_form,
) -> None:
    package = native_property_package
    package.doc.edge_first = edge_first
    package.doc.raw_picks = raw_picks
    package.doc.capture_edge_defect = owner_form
    _scales, settled = drawing._place_package(package.adapter)
    notes = [note for note in package.doc.attached_notes if note.text.startswith("C2 ")]
    flange_notes = [note for note in notes if note.text.startswith(("C2 LOWER", "C2 UPPER"))]
    assert len(flange_notes) == 2
    origin, rows = spec.PLACEMENTS[spec.PIVOT_PIN][0]
    for note, station in zip(flange_notes, (
        spec.pivot_pin.FLANGE_BOTTOM_STATION, spec.pivot_pin.FLANGE_TOP_STATION,
    )):
        # The native leader lands on the A-A flange flat at R17.5, not the
        # R18 source rim or the neighbor's floor/roof 0.15 mm away.
        local = (-spec.retention.PIN_STOP_FACE_MEASUREMENT_DIAMETER / 2.0, 0.0, station)
        physical = tuple(
            (origin[i] + sum(local[k] * rows[k][i] for k in range(3))) / 1000.0
            for i in range(3)
        )
        owner = drawing._bind(note.entity.GetComponent(), "IComponent2")
        leaf = next(leaf for leaf in note.view.components
                    if leaf.Component.Name2 == spec.instance_name(spec.PIVOT_PIN, 0))
        # The accepted owner is the source assembly's own occurrence path
        # (jig-retention 1772's actual_owner shape), whatever its separators.
        expected = f"{package.source_root.Name2}/{leaf.Component.Name2}"
        assert owner.Name2.replace("\\", "/") == expected
        assert ("\\" in owner.Name2) == (owner_form == "owner-backslashes")
        assert owner.Name2 != leaf.Name
        assert note.world == pytest.approx(physical, abs=1e-12)
        leader = note.annotation.GetLeaderPointsAtIndex(0)
        assert leader[-3:-1] == pytest.approx(
            note.view.ModelToViewTransform.apply(physical)[:2], abs=1e-12,
        )
    assert len(package.doc.pick_slots) == len(drawing.capture_readings())
    for (slots, types), (edge, selected, selected_types) in zip(
        package.doc.pick_slots, package.doc.reselections, strict=True,
    ):
        assert types == ((1, 12) if edge_first else (12, 1))
        assert slots[types.index(1)] is edge
        assert selected == (edge,) and selected_types == (1,)
        assert slots[types.index(12)] is next(
            note.view for note in package.doc.attached_notes if note.entity is edge
        )
    if raw_picks:
        assert {"IEntity", "IEdge", "IComponent2", "IView"} <= {
            interface for _value, interface in package.doc.binding_calls
        }
    settled[-1]()


@pytest.mark.parametrize("edge_first", (False, True))
@pytest.mark.parametrize("defect", (
    "foreign-view",
    "extra-foreign-view",
    "wrong-context-type",
    "multiple-edge-slots",
    "null-edge",
    "no-edge",
    "wrong-parent",
    "wrong-root",
    "wrong-occurrence",
    "wrong-case",
    "null-owner",
    "model-path",
    "drawing-name",
    "wrong-part-file",
    "empty-owner-path",
    "empty-leaf-path",
    "null-parent",
    "extra-ancestor",
    "parent-cycle",
    "empty-parent-name",
    "empty-parent-path",
    "parent-read-error",
    "duplicate-visible-leaf",
    "hidden-visible-leaf",
    "coordinate-foreign-owner",
    "no-exact-point",
    "wrong-section-depth",
    "reselect-substitute",
    "reselect-count",
    "reselect-type",
))
def test_capture_native_pick_refuses_actual_context_owner_geometry_and_reselection_counterexamples(
    native_property_package, defect, edge_first,
) -> None:
    package = native_property_package
    package.doc.capture_edge_defect = defect
    package.doc.edge_first = edge_first
    with pytest.raises(RuntimeError):
        drawing._place_package(package.adapter)
    assert package.doc.attached_notes == []
    assert not package.doc.bom_inserted


@pytest.mark.parametrize("raw_picks", (False, True))
def test_capture_c4_mouth_acquires_the_retainer_wall_inside_and_lands_on_its_top_corner(
    native_property_package, raw_picks,
) -> None:
    """The two C4 MOUTH rows pick the retainer's bore wall at mid-height,
    where it is the only segment, and still identify, attach and land at the
    unchanged top-corner criterion, which the clevis shank's coincident lower
    section line also runs through (jig-retention 1772 workers 9 and 15).
    """
    package = native_property_package
    package.doc.raw_picks = raw_picks
    _scales, settled = drawing._place_package(package.adapter)
    readings = drawing.capture_readings()
    # Only the two C4 MOUTH rows and the C4A UPPER CROSS-HOLE row separate
    # acquisition from criterion.
    assert [reading.pick_local_mm is not None for reading in readings] == [
        reading.text.startswith(("C4 MOUTH", "C4A UPPER CROSS-HOLE")) for reading in readings
    ]
    mouth = [(index, reading) for index, reading in enumerate(readings)
             if reading.text.startswith("C4 MOUTH")]
    bore = spec.pivot_retainer.BORE_DIA / 2.0
    top = spec.pivot_retainer.THICKNESS
    root = package.source_root.Name2
    retainer = f"{root}/{spec.instance_name(spec.PIVOT_RETAINER, 0)}"
    clevis = f"{root}/{spec.instance_name(spec.PIVOT_CLEVIS_PIN, 0)}"
    for (index, reading), side in zip(mouth, (-1.0, 1.0), strict=True):
        assert reading.stem == spec.PIVOT_RETAINER
        assert reading.local_mm == (side * bore, 0.0, top)
        assert reading.pick_local_mm == (side * bore, 0.0, top / 2.0)
        note = package.doc.attached_notes[index]
        assert note.text == reading.text
        view = note.view
        criterion = drawing._capture_world_point(reading)
        acquisition = drawing._capture_world_point(reading, local_mm=reading.pick_local_mm)
        paper_criterion = view.ModelToViewTransform.apply(criterion)[:2]
        paper_acquisition = view.ModelToViewTransform.apply(acquisition)[:2]
        ratio = view.ScaleRatio[0] / view.ScaleRatio[1]
        assert math.dist(paper_acquisition, paper_criterion) == pytest.approx(
            ratio * top / 2000.0, abs=1e-12,
        )
        # The zoom aperture and the coordinate pick see the acquisition only.
        pick_xy, zoom_centre, candidates = package.doc.coordinate_picks[index]
        assert pick_xy == pytest.approx(paper_acquisition, abs=1e-12)
        assert zoom_centre == pytest.approx(paper_acquisition, abs=1e-12)
        # Mid-height, the retainer's own wall is the one segment at the pick.
        touching = [edge for distance, _interior, edge in candidates if distance <= 1e-8]
        assert [edge.owner.Name2 for edge in touching] == [retainer]
        wall, = touching
        assert note.entity is wall
        floor, ceiling = wall.endpoints
        assert floor == pytest.approx((side * bore / 1000.0, 0.0, 0.0), abs=1e-15)
        assert ceiling == pytest.approx(tuple(v / 1000.0 for v in reading.local_mm), abs=1e-15)
        # The clevis line is a real separate candidate: it runs through the
        # top corner in model space, half a thickness above the pick.
        lower, = [
            edge for _distance, _interior, edge in candidates
            if edge.owner.Name2 == clevis
            and all(abs(point[2] - criterion[2]) < 1e-12 for point in edge.world_endpoints)
        ]
        a, b = lower.world_endpoints
        axis = tuple(b[i] - a[i] for i in range(3))
        along = sum((criterion[i] - a[i]) * axis[i] for i in range(3)) / sum(v * v for v in axis)
        assert 0.0 < along < 1.0
        assert math.dist(criterion, tuple(a[i] + along * axis[i] for i in range(3))) < 1e-12
        clevis_distance, = [d for d, _interior, edge in candidates if edge is lower]
        assert clevis_distance == pytest.approx(ratio * top / 2000.0, abs=1e-12)
        # Identification, attachment and landing stay at the top corner.
        owner = drawing._bind(note.entity.GetComponent(), "IComponent2")
        assert owner.Name2 == retainer
        assert note.world == pytest.approx(criterion, abs=1e-12)
        landing = note.annotation.GetLeaderPointsAtIndex(0)[-3:-1]
        assert landing == pytest.approx(paper_criterion, abs=1e-12)
        assert math.dist(landing, paper_acquisition) > 1e-4
        closest = wall.GetClosestPointOn(*ceiling)
        assert math.dist(closest[:3], ceiling) < 1e-12 and closest[3] == pytest.approx(1.0)
        assert wall.GetClosestPointOn(*(v / 1000.0 for v in reading.pick_local_mm))[3] == pytest.approx(0.5)
    settled[-1]()


def test_capture_c4_mouth_top_corner_pick_selects_the_coincident_clevis_line(
    native_property_package, monkeypatch,
) -> None:
    """Picking at the criterion itself lands on the retainer's top bore corner,
    where the clevis shank's lower section line is coincident and runs through.
    Native resolved that pick to the CLEVIS (jig-retention 1772 worker 9); the
    unchanged strict owner proof refuses it before any C4 note or BOM, so the
    mid-height acquisition point is necessary.
    """
    package = native_property_package
    readings = tuple(
        dataclasses.replace(reading, pick_local_mm=None)
        if reading.text.startswith("C4 MOUTH") else reading
        for reading in drawing.capture_readings()
    )
    monkeypatch.setattr(drawing, "capture_readings", lambda: readings)
    with pytest.raises(RuntimeError, match=r"jig capture C4 MOUTH.*did not select .* own edge"):
        drawing._place_package(package.adapter)
    index = next(i for i, reading in enumerate(readings) if reading.text.startswith("C4 MOUTH"))
    assert readings[index + 1].text.startswith("C4 MOUTH")
    assert len(package.doc.coordinate_picks) == index + 1
    pick_xy, zoom_centre, candidates = package.doc.coordinate_picks[index]
    slots, types = package.doc.pick_slots[index]
    picked = slots[types.index(1)]
    view = slots[types.index(12)]
    corner = view.ModelToViewTransform.apply(drawing._capture_world_point(readings[index]))[:2]
    assert pick_xy == pytest.approx(corner, abs=1e-12)
    assert zoom_centre == pytest.approx(corner, abs=1e-12)
    root = package.source_root.Name2
    retainer = f"{root}/{spec.instance_name(spec.PIVOT_RETAINER, 0)}"
    clevis = f"{root}/{spec.instance_name(spec.PIVOT_CLEVIS_PIN, 0)}"
    touching = sorted(
        (edge.owner.Name2, interior)
        for distance, interior, edge in candidates if distance <= 1e-8
    )
    assert touching == sorted(((retainer, False), (clevis, True)))
    assert picked.owner.Name2 == clevis
    # The coincidence is physical: both mouth corners lie on the clevis line.
    a, b = picked.world_endpoints
    axis = tuple(b[i] - a[i] for i in range(3))
    for reading in readings[index:index + 2]:
        point = drawing._capture_world_point(reading)
        along = sum((point[i] - a[i]) * axis[i] for i in range(3)) / sum(v * v for v in axis)
        assert 0.0 < along < 1.0
        assert math.dist(point, tuple(a[i] + along * axis[i] for i in range(3))) < 1e-12
    assert not any(note.text.startswith("C4 MOUTH") for note in package.doc.attached_notes)
    assert not package.doc.bom_inserted


def test_capture_c4_mouth_wall_through_the_pick_but_short_of_its_corner_is_refused(
    native_property_package,
) -> None:
    """The retainer's own wall acquired at mid-height does not identify the
    reading unless it reaches the top corner: the unchanged strict closest
    point refuses it before any C4 note or BOM.
    """
    package = native_property_package
    package.doc.capture_edge_defect = "short-mouth-wall"
    with pytest.raises(RuntimeError, match=r"jig capture C4 MOUTH.*does not pass through its section point"):
        drawing._place_package(package.adapter)
    readings = drawing.capture_readings()
    index = next(i for i, reading in enumerate(readings) if reading.text.startswith("C4 MOUTH"))
    reading = readings[index]
    slots, types = package.doc.pick_slots[index]
    picked = slots[types.index(1)]
    root = package.source_root.Name2
    assert picked.owner.Name2 == f"{root}/{spec.instance_name(spec.PIVOT_RETAINER, 0)}"
    local_pick = tuple(v / 1000.0 for v in reading.pick_local_mm)
    assert picked.GetClosestPointOn(*local_pick)[:3] == pytest.approx(local_pick, abs=1e-15)
    local = tuple(v / 1000.0 for v in reading.local_mm)
    assert math.dist(picked.GetClosestPointOn(*local)[:3], local) == pytest.approx(
        spec.pivot_retainer.THICKNESS / 4000.0, abs=1e-12,
    )
    assert not any(note.text.startswith("C4 MOUTH") for note in package.doc.attached_notes)
    assert not package.doc.bom_inserted


def _c4a_cross_hole_row(readings):
    return next((index, reading) for index, reading in enumerate(readings)
                if reading.text.startswith("C4A UPPER CROSS-HOLE"))


@pytest.mark.parametrize("raw_picks", (False, True))
def test_capture_c4a_cross_hole_acquires_the_pin_wall_above_and_lands_on_the_hole_corner(
    native_property_package, raw_picks,
) -> None:
    """The C4A UPPER CROSS-HOLE row picks the pin's exposed outer journal wall
    midway between the hole top and the lead chamfer, where it is the only
    segment, and still identifies, attaches and lands at the unchanged
    hole-top height: the text-side corner of the upper hole boundary
    (jig-retention 1772 worker 15, 58e34c). By the source geometry the loaded
    clevis shank's top section line is coincident there too; native proved
    only a wrong CLEVIS owner at the row's old midpoint (worker 5, 650a9308).
    """
    package = native_property_package
    package.doc.raw_picks = raw_picks
    _scales, settled = drawing._place_package(package.adapter)
    index, reading = _c4a_cross_hole_row(drawing.capture_readings())
    pin = spec.pivot_pin
    hole_top = pin.CROSS_HOLE_STATION + pin.CROSS_HOLE_DIA / 2.0
    chamfer = pin.OVERALL_LENGTH - pin.LEAD_CHAMFER
    assert reading.stem == spec.PIVOT_PIN
    # The reading's height is the hole top as before; only the leader's end
    # moved along that boundary to its text-side corner.
    assert reading.local_mm == (-pin.FIT_DIA / 2.0, 0.0, hole_top)
    assert reading.pick_local_mm == (-pin.FIT_DIA / 2.0, 0.0, (hole_top + chamfer) / 2.0)
    assert hole_top < reading.pick_local_mm[2] < chamfer
    root = package.source_root.Name2
    pin_owner = f"{root}/{spec.instance_name(spec.PIVOT_PIN, 0)}"
    clevis = f"{root}/{spec.instance_name(spec.PIVOT_CLEVIS_PIN, 0)}"
    note = package.doc.attached_notes[index]
    assert note.text == reading.text
    view = note.view
    criterion = drawing._capture_world_point(reading)
    acquisition = drawing._capture_world_point(reading, local_mm=reading.pick_local_mm)
    paper_criterion = view.ModelToViewTransform.apply(criterion)[:2]
    paper_acquisition = view.ModelToViewTransform.apply(acquisition)[:2]
    ratio = view.ScaleRatio[0] / view.ScaleRatio[1]
    assert math.dist(paper_acquisition, paper_criterion) == pytest.approx(
        ratio * (chamfer - hole_top) / 2000.0, abs=1e-12,
    )
    # The zoom aperture and the coordinate pick see the acquisition only.
    pick_xy, zoom_centre, candidates = package.doc.coordinate_picks[index]
    assert pick_xy == pytest.approx(paper_acquisition, abs=1e-12)
    assert zoom_centre == pytest.approx(paper_acquisition, abs=1e-12)
    # Above the hole, the pin's own outer wall is the one segment at the pick.
    touching = [edge for distance, _interior, edge in candidates if distance <= 1e-8]
    assert [edge.owner.Name2 for edge in touching] == [pin_owner]
    wall, = touching
    assert note.entity is wall
    corner, top = wall.endpoints
    assert corner == pytest.approx(tuple(v / 1000.0 for v in reading.local_mm), abs=1e-15)
    assert top == pytest.approx((-pin.FIT_DIA / 2000.0, 0.0, chamfer / 1000.0), abs=1e-15)
    # The corner is the text-side end of the pin's own full upper hole
    # boundary, a separate candidate lying along the criterion's height.
    boundary, = [
        edge for _distance, _interior, edge in candidates
        if edge.owner.Name2 == pin_owner and edge is not wall
        and all(abs(point[2] - criterion[2]) < 1e-12 for point in edge.world_endpoints)
    ]
    near, far = boundary.endpoints
    assert near == pytest.approx(corner, abs=1e-15)
    assert far == pytest.approx((pin.FIT_DIA / 2000.0, 0.0, hole_top / 1000.0), abs=1e-15)
    # The clevis top line is a real separate candidate: it runs through the
    # corner in model space, half the exposed wall below the pick.
    upper, = [
        edge for _distance, _interior, edge in candidates
        if edge.owner.Name2 == clevis
        and all(abs(point[2] - criterion[2]) < 1e-12 for point in edge.world_endpoints)
    ]
    a, b = upper.world_endpoints
    axis = tuple(b[i] - a[i] for i in range(3))
    along = sum((criterion[i] - a[i]) * axis[i] for i in range(3)) / sum(v * v for v in axis)
    assert 0.0 < along < 1.0
    assert math.dist(criterion, tuple(a[i] + along * axis[i] for i in range(3))) < 1e-12
    clevis_distance, = [d for d, _interior, edge in candidates if edge is upper]
    assert clevis_distance == pytest.approx(ratio * (chamfer - hole_top) / 2000.0, abs=1e-12)
    # Identification, attachment and landing stay at the hole-top corner.
    owner = drawing._bind(note.entity.GetComponent(), "IComponent2")
    assert owner.Name2 == pin_owner
    assert note.world == pytest.approx(criterion, abs=1e-12)
    landing = note.annotation.GetLeaderPointsAtIndex(0)[-3:-1]
    assert landing == pytest.approx(paper_criterion, abs=1e-12)
    assert math.dist(landing, paper_acquisition) > 1e-4
    # The strict closest point proves the acquired wall passes through the
    # corner; that this modelled wall also ends there is not what it proves.
    assert math.dist(wall.GetClosestPointOn(*corner)[:3], corner) < 1e-12
    assert wall.GetClosestPointOn(*(v / 1000.0 for v in reading.pick_local_mm))[3] == pytest.approx(0.5)
    settled[-1]()


def test_capture_c4a_cross_hole_corner_pick_selects_the_coincident_clevis_top_line(
    native_property_package, monkeypatch,
) -> None:
    """Picking at the criterion itself lands on the upper hole boundary's
    text-side corner, where the source geometry puts the loaded clevis shank's
    top section line, coincident and running through. Native resolved the
    row's old midpoint pick to the CLEVIS owner (jig-retention 1772 worker 5,
    650a9308, after both C4 MOUTH repairs and every preceding row landed; the
    clevis curve itself was not logged); the fixture models that adverse
    choice at the corner, and the unchanged strict owner proof refuses it
    before any C4A note or BOM, so the mid-wall acquisition is necessary.
    """
    package = native_property_package
    readings = tuple(
        dataclasses.replace(reading, pick_local_mm=None)
        if reading.text.startswith("C4A UPPER CROSS-HOLE") else reading
        for reading in drawing.capture_readings()
    )
    monkeypatch.setattr(drawing, "capture_readings", lambda: readings)
    with pytest.raises(RuntimeError, match=r"jig capture C4A UPPER CROSS-HOLE.*did not select .* own edge"):
        drawing._place_package(package.adapter)
    index, reading = _c4a_cross_hole_row(readings)
    assert len(package.doc.coordinate_picks) == index + 1
    pick_xy, zoom_centre, candidates = package.doc.coordinate_picks[index]
    slots, types = package.doc.pick_slots[index]
    picked = slots[types.index(1)]
    view = slots[types.index(12)]
    corner = view.ModelToViewTransform.apply(drawing._capture_world_point(reading))[:2]
    assert pick_xy == pytest.approx(corner, abs=1e-12)
    assert zoom_centre == pytest.approx(corner, abs=1e-12)
    root = package.source_root.Name2
    pin_owner = f"{root}/{spec.instance_name(spec.PIVOT_PIN, 0)}"
    clevis = f"{root}/{spec.instance_name(spec.PIVOT_CLEVIS_PIN, 0)}"
    # The pin's wall and its hole boundary both end at the corner; only the
    # clevis line runs through it.
    touching = sorted(
        (edge.owner.Name2, interior)
        for distance, interior, edge in candidates if distance <= 1e-8
    )
    assert touching == sorted(((pin_owner, False), (pin_owner, False), (clevis, True)))
    assert picked.owner.Name2 == clevis
    # The coincidence is physical: the corner lies inside the clevis top line.
    a, b = picked.world_endpoints
    axis = tuple(b[i] - a[i] for i in range(3))
    point = drawing._capture_world_point(reading)
    along = sum((point[i] - a[i]) * axis[i] for i in range(3)) / sum(v * v for v in axis)
    assert 0.0 < along < 1.0
    assert math.dist(point, tuple(a[i] + along * axis[i] for i in range(3))) < 1e-12
    # Both C4 MOUTH repairs landed first; this row and the BOM are refused.
    assert sum(note.text.startswith("C4 MOUTH") for note in package.doc.attached_notes) == 2
    assert not any(note.text.startswith("C4A UPPER CROSS-HOLE") for note in package.doc.attached_notes)
    assert not package.doc.bom_inserted


def test_capture_c4a_cross_hole_wall_through_the_pick_but_starting_above_its_corner_is_refused(
    native_property_package,
) -> None:
    """The pin's own wall acquired mid-wall does not identify the reading
    unless it passes through the hole-top corner: the unchanged strict
    closest point refuses it before any C4A note or BOM.
    """
    package = native_property_package
    package.doc.capture_edge_defect = "short-cross-hole-wall"
    with pytest.raises(RuntimeError, match=r"jig capture C4A UPPER CROSS-HOLE.*does not pass through its section point"):
        drawing._place_package(package.adapter)
    index, reading = _c4a_cross_hole_row(drawing.capture_readings())
    slots, types = package.doc.pick_slots[index]
    picked = slots[types.index(1)]
    root = package.source_root.Name2
    assert picked.owner.Name2 == f"{root}/{spec.instance_name(spec.PIVOT_PIN, 0)}"
    local_pick = tuple(v / 1000.0 for v in reading.pick_local_mm)
    assert picked.GetClosestPointOn(*local_pick)[:3] == pytest.approx(local_pick, abs=1e-15)
    pin = spec.pivot_pin
    exposed = pin.OVERALL_LENGTH - pin.LEAD_CHAMFER - reading.local_mm[2]
    local = tuple(v / 1000.0 for v in reading.local_mm)
    assert math.dist(picked.GetClosestPointOn(*local)[:3], local) == pytest.approx(
        0.25 * exposed / 1000.0, abs=1e-12,
    )
    assert not any(note.text.startswith("C4A UPPER CROSS-HOLE") for note in package.doc.attached_notes)
    assert not package.doc.bom_inserted


@pytest.mark.parametrize("defect", ("owner", "attachment", "landing"))
@pytest.mark.parametrize("prefix", ("C2 LOWER", "C2 UPPER"))
def test_capture_occurrence_edges_still_refuse_settled_c2_attachment_and_landing_drift(
    native_property_package, defect, prefix,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    note = next(note for note in package.doc.attached_notes if note.text.startswith(prefix))
    if defect == "owner":
        note.entity.owner.Name2 = f"foreign-parent/{spec.instance_name(spec.PIVOT_PIN, 0)}"
    elif defect == "attachment":
        note.entity = object()
    else:
        note.landing_shift = (0.001, 0.0)
    with pytest.raises(RuntimeError, match=f"jig capture {prefix}"):
        settled[-1]()


def test_capture_plan_cotter_identification_preserves_measured_depth_difference(
    native_property_package,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    reading = next(reading for reading in drawing.capture_readings()
                   if reading.view_index == 1)
    note = next(note for note in package.doc.attached_notes if note.text == reading.text)
    local = tuple(value / 1000.0 for value in reading.local_mm)
    closest = note.entity.GetClosestPointOn(*local)[:3]
    assert math.dist(local, closest) == pytest.approx(0.00767055, abs=1e-12)
    expected = note.view.ModelToViewTransform.apply(drawing._capture_world_point(reading))
    landing = note.annotation.GetLeaderPointsAtIndex(0)[-3:-1]
    assert landing == pytest.approx(expected[:2], abs=1e-12)
    settled[-1]()


def test_capture_plan_same_owner_wrong_paper_landing_is_not_identification(
    native_property_package,
) -> None:
    package = native_property_package
    package.doc.capture_edge_defect = "plan-wrong-paper"
    with pytest.raises(RuntimeError, match="jig capture C5B COTTER"):
        drawing._place_package(package.adapter)
    assert not package.doc.bom_inserted


@pytest.mark.parametrize("edge_first", (False, True))
@pytest.mark.parametrize("defect", ("plan-parent", "plan-qualified", "plan-wrong-part-file"))
def test_capture_plan_reading_requires_a_top_level_source_occurrence(
    native_property_package, defect, edge_first,
) -> None:
    """The plan view's cotter is owned bare and top-level, in its own part file.

    A one-level parent chain, a root-qualified name, or another part file is
    refused even though each is a valid section-view owner shape.
    """
    package = native_property_package
    package.doc.capture_edge_defect = defect
    package.doc.edge_first = edge_first
    with pytest.raises(RuntimeError, match="jig capture C5B COTTER"):
        drawing._place_package(package.adapter)
    assert not any(note.text.startswith("C5B COTTER") for note in package.doc.attached_notes)
    assert not package.doc.bom_inserted


def _source_owner(name, *, part_file, parent=None):
    """A native-shaped ``IComponent2`` owner: name, part file, parent chain."""
    return SimpleNamespace(
        Name2=name, GetPathName=lambda: part_file, GetParent=lambda: parent,
    )


def _capture_leaf(reading, *, part_file, drawing_root="Draw54-SectionAssembly-1-1"):
    wanted = spec.instance_name(reading.stem, reading.index)
    return _drawing_balloons._ComponentLeaf(
        name=f"{drawing_root}/{wanted}" if reading.view_index != 1 else wanted,
        component=_source_owner(wanted, part_file=part_file),
        identities=frozenset({wanted}), visible=True, path=wanted,
    )


def test_capture_owner_proof_isolated_from_live_source_publication(
    monkeypatch, tmp_path, request,
) -> None:
    live_source = tmp_path / "live-build" / drawing.SOURCE.name
    live_source.parent.mkdir()
    live_source.touch()
    monkeypatch.setattr(drawing, "SOURCE", live_source)
    package = request.getfixturevalue("native_property_package")
    reading = next(r for r in drawing.capture_readings() if r.view_index == 2)
    wanted = spec.instance_name(reading.stem, reading.index)
    part_file = str(tmp_path / "stable-part.SLDPRT")
    Path(part_file).touch()
    leaf = _capture_leaf(reading, part_file=part_file)
    owner = _source_owner(
        f"{package.source_root.Name2}/{wanted}",
        part_file=part_file, parent=package.source_root,
    )
    resolve = Path.resolve
    live_reads = []

    def publication_gap(path, *args, **kwargs):
        resolved = resolve(path, *args, **kwargs)
        if path == live_source:
            live_reads.append(path)
            if len(live_reads) == 1:
                # Windows realpath retains this prefix if the source disappears
                # between GetFinalPathName and its prefix-removal probe. The
                # next resolve of the same (now missing) path has no prefix.
                live_source.unlink()
                return Path("//?/" + str(resolved).replace("\\", "/"))
        return resolved

    monkeypatch.setattr(Path, "resolve", publication_gap)
    assert drawing._assert_capture_component_identity(
        package.adapter, owner, leaf, view_index=2,
        label="jig capture: hidden occurrence",
    ) is owner
    assert not live_reads
    assert drawing.SOURCE != live_source
    assert drawing.SOURCE.is_file()


@pytest.mark.parametrize("view_index", (1, 2, 3))
def test_capture_reading_owner_is_proved_through_the_source_hierarchy(
    native_bom_bindings, view_index,
) -> None:
    """Plan owners are bare and top-level; section owners hang one level under
    the source assembly's own occurrence, whose name only native supplies."""
    reading = next(r for r in drawing.capture_readings() if r.view_index == view_index)
    wanted = spec.instance_name(reading.stem, reading.index)
    part_file = f"C:/native/{spec.COMPONENT_IDENTITIES[reading.stem][0]}.SLDPRT"
    leaf = _capture_leaf(reading, part_file=part_file)
    root = _source_owner("jig-source-occurrence-7", part_file=str(drawing.SOURCE))
    if view_index == 1:
        owner = _source_owner(wanted, part_file=part_file.replace("/", "\\"))
    else:
        owner = _source_owner(
            f"{root.Name2}\\{wanted}", part_file=part_file.replace("/", "\\"), parent=root,
        )
    entity = SimpleNamespace(GetComponent=lambda: owner)
    adapter = SimpleNamespace(_attempt=lambda callback, **_kwargs: callback())
    assert drawing._capture_reading_component(
        adapter, reading, entity, (leaf,), label="jig capture probe",
    ) is owner


# Which reading roles each native-owner counterexample is wrong for: plan (1)
# owners carry no parent chain, so parent-shaped defects only apply to sections.
_SOURCE_OWNER_COUNTEREXAMPLES = (
    ("drawing-root", (1, 2)),
    ("bare-section", (2,)),
    ("qualified-plan", (1,)),
    ("plan-parent", (1,)),
    ("foreign-source-file", (2,)),
    ("parent-name-prefix", (2,)),
    ("wrong-part-file", (1, 2)),
    ("null-section-parent", (2,)),
    ("two-level-chain", (1, 2)),
    ("self-cycle", (1, 2)),
    ("empty-owner-file", (1, 2)),
    ("empty-leaf-file", (1, 2)),
    ("empty-parent-name", (2,)),
    ("empty-parent-file", (2,)),
    ("null-owner", (1, 2)),
    ("parent-read-error", (1, 2)),
)


@pytest.mark.parametrize("defect, view_index", [
    (defect, view_index)
    for defect, view_indices in _SOURCE_OWNER_COUNTEREXAMPLES
    for view_index in view_indices
])
def test_capture_reading_owner_refuses_each_source_hierarchy_counterexample(
    native_bom_bindings, view_index, defect,
) -> None:
    reading = next(r for r in drawing.capture_readings() if r.view_index == view_index)
    wanted = spec.instance_name(reading.stem, reading.index)
    part_file = f"C:/native/{spec.COMPONENT_IDENTITIES[reading.stem][0]}.SLDPRT"
    foreign_part = f"C:/native/{spec.COMPONENT_IDENTITIES[spec.PIVOT_BLOCK][0]}.SLDPRT"
    foreign_source = str(drawing.SOURCE.with_name(f"foreign-{drawing.SOURCE.name}"))
    leaf = _capture_leaf(reading, part_file=part_file)
    root = _source_owner("jig-source-occurrence-7", part_file=str(drawing.SOURCE))
    section = view_index != 1
    name = f"{root.Name2}/{wanted}" if section else wanted
    parent = root if section else None
    owner_file = part_file
    evidence = []
    if defect == "drawing-root":
        name = leaf.name if section else f"Draw54-SectionAssembly-1-1/{wanted}"
        evidence.append(name)
    elif defect == "bare-section":
        name = wanted
    elif defect == "qualified-plan":
        name = f"{root.Name2}/{wanted}"
    elif defect == "plan-parent":
        parent = root
        evidence.append(root.Name2)
    elif defect == "foreign-source-file":
        parent = _source_owner(root.Name2, part_file=foreign_source)
        evidence.append(foreign_source)
    elif defect == "parent-name-prefix":
        name = f"foreign-parent/{wanted}"
        evidence += [name, root.Name2]
    elif defect == "wrong-part-file":
        owner_file = foreign_part
        evidence += [foreign_part, part_file]
    elif defect == "null-section-parent":
        parent = None
    elif defect == "two-level-chain":
        grandparent = _source_owner("jig-source-grandparent-1", part_file=foreign_source)
        parent = _source_owner(root.Name2, part_file=str(drawing.SOURCE), parent=grandparent)
        name = f"{root.Name2}/{wanted}"
        evidence += [root.Name2, grandparent.Name2]
    elif defect == "self-cycle":
        cycle = _source_owner(root.Name2, part_file=str(drawing.SOURCE))
        cycle.GetParent = lambda: cycle
        parent = cycle
        evidence.append(root.Name2)
    elif defect == "empty-owner-file":
        owner_file = ""
        evidence.append(part_file)
    elif defect == "empty-leaf-file":
        leaf = _capture_leaf(reading, part_file="")
        evidence.append(part_file)
    elif defect == "empty-parent-name":
        parent = _source_owner("", part_file=str(drawing.SOURCE))
        name = f"/{wanted}"
    elif defect == "empty-parent-file":
        parent = _source_owner(root.Name2, part_file="")
        evidence.append(str(drawing.SOURCE))
    owner = _source_owner(name, part_file=owner_file, parent=parent)
    if defect == "null-owner":
        owner = None
    elif defect == "parent-read-error":
        def failing_parent():
            raise OSError("native parent dispatch failed")
        owner.GetParent = failing_parent
        evidence.append(name)
    entity = SimpleNamespace(GetComponent=lambda: owner)
    adapter = SimpleNamespace(_attempt=lambda callback, **_kwargs: callback())
    with pytest.raises(RuntimeError, match="jig capture probe") as refusal:
        drawing._capture_reading_component(
            adapter, reading, entity, (leaf,), label="jig capture probe",
        )
    # The refusal carries the native evidence as repr'd values (Windows paths
    # print with doubled separators), not a reworded summary of them.
    message = str(refusal.value)
    assert repr(wanted) in message
    for item in evidence:
        assert repr(item) in message


@pytest.mark.parametrize("defect", ("owner", "attachment", "landing"))
def test_capture_plan_identification_still_refuses_settled_drift(
    native_property_package, defect,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    note = next(note for note in package.doc.attached_notes
                if note.text.startswith("C5B COTTER"))
    if defect == "owner":
        note.entity.owner.Name2 = f"foreign-root/{note.entity.owner.Name2}"
    elif defect == "attachment":
        note.entity = object()
    else:
        note.landing_shift = (0.001, 0.0)
    with pytest.raises(RuntimeError, match="jig capture C5B COTTER"):
        settled[-1]()


@pytest.mark.parametrize("letter, view_index", (("A", 2), ("B", 3)))
def test_capture_section_native_xyz_comes_from_authored_line_not_paper_annotations(
    native_property_package, letter, view_index,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    views = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views
    parent, view = views[1], views[view_index]
    section = view.section
    line = package.doc.section_segments[view_index - 2]
    authored = line.points
    assert section.line is line and line.GetSketch() is parent.sketch
    assert section.GetLineInfo() == tuple(value for point in authored for value in point)
    inverse = parent.sketch.ModelToSketchTransform.Inverse()
    paper = tuple(inverse.apply(point) for point in authored)
    assert math.dist(authored[0], paper[0]) > 0.001
    arrows = section.GetArrowInfo()
    assert arrows[:3] == pytest.approx(paper[0])
    assert arrows[6:9] == pytest.approx(paper[1])
    assert section.GetTextInfo() == pytest.approx((
        paper[0][0] + 0.002, paper[0][1], 0.0,
        paper[1][0] + 0.002, paper[1][1], 0.0,
    ))
    drawing._assert_capture_section(package.adapter, parent, view, letter)
    line.points = authored[::-1]
    assert section.GetLineInfo() == tuple(value for point in authored[::-1] for value in point)
    drawing._assert_capture_section(package.adapter, parent, view, letter)
    assert section.GetArrowInfo() == arrows


@pytest.mark.parametrize("letter, view_index", (("A", 2), ("B", 3)))
@pytest.mark.parametrize("defect", (
    "start-z", "both-z", "underlength", "overlength", "length-only",
    "translated-on-axis", "translated-off-axis", "oblique", "paper-as-sketch",
    "current-sketch-transform",
))
def test_capture_section_proof_refuses_actual_sketch_endpoint_counterexamples(
    native_property_package, letter, view_index, defect,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    views = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views
    parent, view = views[1], views[view_index]
    line = package.doc.section_segments[view_index - 2]
    authored = line.points
    a, b = authored
    length = math.dist(a, b)
    along = tuple((b[i] - a[i]) / length for i in range(3))
    across = (-along[1], along[0], 0.0)
    if defect in {"start-z", "both-z"}:
        line.points = (
            (a[0], a[1], a[2] + 0.001),
            (b[0], b[1], b[2] + (0.001 if defect == "both-z" else 0.0)),
        )
        assert line.points[0][:2] == a[:2] and line.points[1][:2] == b[:2]
    elif defect in {"underlength", "overlength", "length-only"}:
        shift = 7.5e-8 if defect == "length-only" else 0.0005
        if defect == "overlength":
            shift = -shift
        line.points = (
            tuple(a[i] + shift * along[i] for i in range(3)),
            tuple(b[i] - shift * along[i] for i in range(3)),
        )
        if defect == "length-only":
            assert max(math.dist(p, q) for p, q in zip(line.points, authored)) < 1e-7
            assert abs(math.dist(*line.points) - length) > 1e-7
    elif defect in {"translated-on-axis", "translated-off-axis"}:
        direction = along if defect == "translated-on-axis" else across
        line.points = tuple(
            tuple(point[i] + 0.001 * direction[i] for i in range(3))
            for point in authored
        )
    elif defect == "oblique":
        line.points = (a, tuple(b[i] + 0.001 * across[i] for i in range(3)))
    elif defect == "paper-as-sketch":
        inverse = parent.sketch.ModelToSketchTransform.Inverse()
        line.points = tuple(inverse.apply(point) for point in authored)
    else:
        origin = parent.sketch.sketch_origin
        parent.sketch.sketch_origin = (origin[0] + 0.001, *origin[1:])
    # The native getter reads mutated authored geometry, never a production
    # expectation; annotations and the child view's model axes stay untouched.
    if defect != "current-sketch-transform":
        assert view.section.GetLineInfo() == tuple(
            value for point in line.points for value in point
        )
    with pytest.raises(RuntimeError, match="native cut plane misses its model reading axes"):
        drawing._assert_capture_section(package.adapter, parent, view, letter)
    refusal = "native cut plane misses its model reading axes"
    with pytest.raises(RuntimeError, match=refusal):
        settled[-1]()


@pytest.mark.parametrize("defect", ("snapped-x", "snapped-z", "wrong-radius"))
def test_capture_crop_refuses_created_native_geometry_before_crop2(
    native_property_package, defect,
) -> None:
    package = native_property_package
    manager = package.doc.SketchManager
    create = manager.CreateCircle

    def displaced(*coordinates):
        circle = create(*coordinates)
        if defect == "wrong-radius":
            circle.radius += 0.001
        else:
            axis = 0 if defect == "snapped-x" else 2
            circle.centre = tuple(
                value + (0.001 if i == axis else 0.0)
                for i, value in enumerate(circle.centre)
            )
        return circle

    manager.CreateCircle = displaced
    with pytest.raises(RuntimeError, match="created native crop circle moved or changed radius"):
        drawing._place_package(package.adapter)
    assert package.doc.crop_calls == []
    assert manager.AddToDB is False
    assert not package.doc.bom_inserted


@pytest.mark.parametrize("defect, refusal", (
    ("refused", "failed to select native crop circle"),
    ("empty", "crop circle selection is not one profile"),
    ("extra", "crop circle selection is not one profile"),
))
def test_capture_crop_refuses_selection_failure_or_wrong_count_before_crop2(
    native_property_package, defect, refusal,
) -> None:
    package = native_property_package
    manager = package.doc.SketchManager
    create = manager.CreateCircle
    selections = []

    def with_bad_selection(*coordinates):
        circle = create(*coordinates)
        select = circle.Select4

        def bad_select(append, data):
            assert append is False and data.View is circle.GetSketch().view
            selections.append(circle)
            if defect == "refused":
                return False
            assert select(append, data)
            if defect == "empty":
                package.doc.selected.clear()
            else:
                package.doc.selected.append(object())
            return True

        circle.Select4 = bad_select
        return circle

    manager.CreateCircle = with_bad_selection
    with pytest.raises(RuntimeError, match=refusal):
        drawing._place_package(package.adapter)
    assert selections == package.doc.crop_circles
    assert package.doc.crop_calls == []
    assert manager.AddToDB is False
    assert not package.doc.bom_inserted


@pytest.mark.parametrize("previous_add_to_db", (False, True))
@pytest.mark.parametrize("failure", ("none", "exception"))
def test_capture_crop_creation_refusal_restores_database_mode(
    native_property_package, previous_add_to_db, failure,
) -> None:
    package = native_property_package
    manager = package.doc.SketchManager
    manager.AddToDB = previous_add_to_db

    def refuse(*_coordinates):
        assert manager.AddToDB is True
        if failure == "exception":
            raise RuntimeError("native crop creation error")
        return None

    manager.CreateCircle = refuse
    refusal = "native crop creation error" if failure == "exception" else "failed to create crop circle"
    with pytest.raises(RuntimeError, match=refusal):
        drawing._place_package(package.adapter)
    assert manager.AddToDB is previous_add_to_db
    assert package.doc.crop_calls == []
    assert not package.doc.bom_inserted


def test_capture_native_crop_boundary_uses_explicit_view_owned_selection_not_last_created(
    native_property_package,
) -> None:
    package = native_property_package
    doc = package.doc
    assert doc.ActivateSheet(drawing.PIVOT_CAPTURE_SHEET)
    view = doc.CreateDrawViewFromModelView3(
        "capture-fixture.SLDASM", spec.PLAN_VIEW, 0.250, 0.240, 0.0,
    )
    other_view = doc.CreateDrawViewFromModelView3(
        "capture-fixture.SLDASM", spec.PLAN_VIEW, 0.350, 0.240, 0.0,
    )
    view.ScaleRatio = (1, 4)
    assert doc.ActivateView(view.GetName2())
    transform = view.sketch.ModelToSketchTransform
    centre = transform.apply((*view.Position, 0.0))
    edge = transform.apply((view.Position[0] + 0.055 / 4.0, view.Position[1], 0.0))
    manager = doc.SketchManager
    previous = manager.AddToDB
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*centre, *edge)
        other = manager.CreateCircle(*centre, centre[0] + circle.radius * 0.8,
                                     centre[1], centre[2])
    finally:
        manager.AddToDB = previous
    assert other is not circle and doc.selected == []
    with pytest.raises(ValueError):
        view.Crop2(False, False, 1)
    data = doc.SelectionManager.CreateSelectData()
    data.View = other_view
    assert circle.Select4(False, data) is False
    assert doc.selected == []
    data.View = view
    assert circle.Select4(False, data) is True
    assert other.Select4(True, data) is True
    with pytest.raises(ValueError):
        view.Crop2(False, False, 1)
    assert circle.Select4(False, data) is True
    assert view.Crop2(False, False, 1) == 1
    assert doc.crop_calls[-1] == (view, circle)
    assert view.crop[1] == pytest.approx(0.055)
    assert circle.GetSketch() is not view.sketch
    assert view.sketch.GetSketchSegments() == (other,)
    doc.ClearSelection2(True)
    assert circle.Select4(False, data) is False
    assert doc.selected == []
    assert other.Select4(False, data) is True
    assert view.Crop2(False, False, 1) == 1
    assert doc.crop_calls[-1] == (view, other)
    assert view.crop[1] == pytest.approx(0.055 * 0.8)
    assert other.GetSketch() is not view.sketch
    assert view.sketch.GetSketchSegments() == ()


def test_capture_crop_returns_the_selected_profile_after_native_absorption(
    native_property_package,
) -> None:
    package = native_property_package
    doc = package.doc
    assert doc.ActivateSheet(drawing.PIVOT_CAPTURE_SHEET)
    view = doc.CreateDrawViewFromModelView3(
        "capture-fixture.SLDASM", spec.PLAN_VIEW, 0.250, 0.240, 0.0,
    )
    view.ScaleRatio = (1, 4)
    creation_transform = view.GetSketch().ModelToSketchTransform.ArrayData
    manager = doc.SketchManager
    create = manager.CreateCircle

    def create_with_unselected_successor(*coordinates):
        selected = create(*coordinates)
        create(*selected.centre, selected.centre[0] + selected.radius * 0.8,
               selected.centre[1], selected.centre[2])
        return selected

    manager.CreateCircle = create_with_unselected_successor
    profile = drawing._crop_capture_view(
        package.adapter, view, tuple(view.Position), 0.055 / 4.0,
        label="retained native crop boundary",
    )
    selected, unselected = doc.crop_circles
    assert profile is selected and profile is not unselected
    assert doc.crop_calls == [(view, selected)]
    assert view.crop[1] == pytest.approx(0.055)
    assert profile.GetSketch() is not view.GetSketch()
    assert profile.GetSketch().ModelToSketchTransform.ArrayData == creation_transform
    assert view.GetSketch().GetSketchSegments() == (unselected,)
    assert manager.AddToDB is False
    drawing._assert_capture_crop(package.adapter, view, 1, profile)


def test_capture_measured_locator_outline_keeps_bounded_field_and_caption_clearance(
    native_property_package,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    locator = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[1]
    outline = locator.GetOutline()
    field = drawing.CAPTURE_VIEW_REGIONS[1]
    # Native d1c padded extent, not the selected circle's ideal paper diameter.
    assert (outline[2] - outline[0], outline[3] - outline[1]) == pytest.approx(
        (0.0438842, 0.0415158),
    )
    assert _inside(outline, field) and _inside_sheet(outline)
    horizontal = (outline[0] - field[0], field[2] - outline[2])
    vertical = (outline[1] - field[1], field[3] - outline[3])
    assert all(0.00505 < gap < 0.00507 for gap in horizontal)
    assert all(0.00073 < gap < 0.00075 for gap in vertical)
    caption = next(note for note in locator.notes if note.GetText().startswith("ASSEMBLED PLAN "))
    assert tuple(caption.position) == (0.224, 0.220, 0.0)
    extent = caption.GetExtent()
    assert 0.00073 < outline[1] - extent[4] < 0.00075
    assert not _overlap(outline, (extent[0], extent[1], extent[3], extent[4]))
    settled[-1]()


@pytest.mark.parametrize("balloon_state", ("valid", "missing", "extra", "foreign-identity"))
def test_capture_native_balloon_inventory_binds_raw_boolean_and_keeps_exact_identity(
    native_property_package, monkeypatch, balloon_state,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    exploded = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[0]
    native_notes = list(exploded.notes)
    nonballoon = next((note for note in native_notes if not note.IsBomBalloon()), None)
    if nonballoon is None:
        nonballoon = SimpleNamespace(IsBomBalloon=lambda: False)
        native_notes.append(nonballoon)
    target_index = next(
        index for index, note in enumerate(native_notes) if note.IsBomBalloon()
    )
    target = native_notes[target_index]
    foreign = SimpleNamespace(**vars(target))

    class RawNote:
        def __init__(self, native_note):
            self.native_note = native_note
            self.IsBomBalloon = native_note.IsBomBalloon()

    original_early_bound = drawing._early_bound
    original_is_same = package.adapter.swApp.IsSame

    def native(value):
        return value.native_note if isinstance(value, RawNote) else value

    def early_bound(value, interface):
        if isinstance(value, RawNote):
            assert interface == "INote"
            return value.native_note
        return original_early_bound(value, interface)

    def is_same(a, b):
        # Model IUnknown identity for both operands, delegating the underlying
        # objects to the existing identity-aware fixture (never value equality).
        return original_is_same(native(a), native(b))

    monkeypatch.setattr(drawing, "_early_bound", early_bound)
    monkeypatch.setattr(package.adapter.swApp, "IsSame", is_same)
    raw_target, raw_foreign = RawNote(target), RawNote(foreign)
    assert raw_target.IsBomBalloon is True
    assert callable(drawing._early_bound(raw_target, "INote").IsBomBalloon)
    assert drawing._early_bound(raw_target, "INote").IsBomBalloon() is True
    raw_nonballoon = RawNote(nonballoon)
    assert raw_nonballoon.IsBomBalloon is False
    assert callable(drawing._early_bound(raw_nonballoon, "INote").IsBomBalloon)
    assert drawing._early_bound(raw_nonballoon, "INote").IsBomBalloon() is False
    assert is_same(raw_target, target) == is_same(target, raw_target) == 1
    assert is_same(raw_foreign, target) == is_same(target, raw_foreign) == 0
    if balloon_state == "missing":
        del native_notes[target_index]
    elif balloon_state == "extra":
        native_notes.append(foreign)
    elif balloon_state == "foreign-identity":
        native_notes[target_index] = foreign
    owned = tuple(RawNote(note) for note in native_notes)
    assert {note.IsBomBalloon for note in owned} == {True, False}
    monkeypatch.setattr(exploded, "GetNotes", lambda: owned)
    if balloon_state == "valid":
        settled[-1]()
    else:
        with pytest.raises(
            RuntimeError, match="native exploded balloons differ from proved landings",
        ):
            settled[-1]()


@pytest.mark.parametrize("caption_state", ("valid", "wrong-text", "duplicate", "missing"))
def test_capture_locator_caption_binds_materialized_raw_text_before_exact_proof(
    native_property_package, monkeypatch, caption_state,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    locator = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[1]
    caption = next(
        note for note in locator.notes if note.GetText().startswith("ASSEMBLED PLAN ")
    )
    if caption_state == "wrong-text":
        caption.text = "ASSEMBLED PLAN 1:8"
    # GetNotes can return an untyped dispatch whose zero-argument GetText was
    # materialized as a string; binding INote exposes the actual method.
    raw_caption = SimpleNamespace(GetText=caption.GetText(), native_note=caption)
    original_early_bound = drawing._early_bound

    def early_bound(value, interface):
        if value is raw_caption:
            assert interface == "INote"
            return value.native_note
        return original_early_bound(value, interface)

    monkeypatch.setattr(drawing, "_early_bound", early_bound)
    owned = tuple(raw_caption if note is caption else note for note in locator.notes)
    if caption_state == "duplicate":
        owned += (raw_caption,)
    elif caption_state == "missing":
        owned = tuple(note for note in owned if note is not raw_caption)
    monkeypatch.setattr(locator, "GetNotes", lambda: owned)
    assert isinstance(raw_caption.GetText, str)
    assert callable(drawing._early_bound(raw_caption, "INote").GetText)
    if caption_state == "valid":
        settled[-1]()
    else:
        with pytest.raises(
            RuntimeError, match="locator lost its independently fitted scale caption",
        ):
            settled[-1]()


@pytest.mark.parametrize("oversized", ("width", "height"))
def test_capture_fixed_locator_fit_keeps_strict_measured_field_bounds(
    native_property_package, oversized,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    locator = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[1]
    profile = package.doc.crop_circles[0]
    width, height = locator.crop_outline_size
    locator.crop_outline_size = (
        0.0540158 if oversized == "width" else width,
        0.0430158 if oversized == "height" else height,
    )
    with pytest.raises(RuntimeError, match="no measured scale fits its reserved field"):
        drawing._fit_capture_view(
            package.adapter, locator, drawing.CAPTURE_VIEW_REGIONS[1], ((1, 4),),
            crop_profile=profile, label="jig capture locator boundary",
        )
    assert tuple(locator.ScaleRatio) == (1, 4)
    assert locator.post_crop_scale_writes == []


@pytest.mark.parametrize("view_index", (1, 2, 3))
def test_capture_crop_proof_refuses_a_missing_retained_profile(
    native_property_package, view_index,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    view = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[view_index]
    profile = package.doc.crop_circles[view_index - 1]
    assert view.IsCropped() is True
    with pytest.raises(RuntimeError, match="native fence is not a sketch arc"):
        drawing._assert_capture_crop(package.adapter, view, view_index, None)
    drawing._assert_capture_crop(package.adapter, view, view_index, profile)


@pytest.mark.parametrize("view_index", (1, 2, 3))
def test_capture_retained_crop_owner_tracks_recenter_independently_of_view_sketch(
    native_property_package, view_index,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    view = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[view_index]
    circle = package.doc.crop_circles[view_index - 1]
    owner = circle.GetSketch()
    authored = (circle.centre, circle.radius)
    before = owner.ModelToSketchTransform.ArrayData
    view.Position = (view.Position[0] + 0.001, view.Position[1] - 0.002)
    assert owner.ModelToSketchTransform.ArrayData != before
    drawing._assert_capture_crop(package.adapter, view, view_index, circle)
    # The original view-owned sketch is no longer the crop's geometry frame.
    origin = view.sketch.sketch_origin
    view.sketch.sketch_origin = (origin[0] + 0.001, origin[1], origin[2] + 0.001)
    drawing._assert_capture_crop(package.adapter, view, view_index, circle)
    assert (circle.centre, circle.radius) == authored
    assert view.post_crop_scale_writes == []


@pytest.mark.parametrize("view_index", (1, 2, 3))
@pytest.mark.parametrize("defect, refusal", (
    ("centre-x", "persisted native crop centre or model radius changed"),
    ("centre-z", "persisted native crop centre or model radius changed"),
    ("radius", "persisted native crop centre or model radius changed"),
    ("paper-as-sketch", "persisted native crop centre or model radius changed"),
    ("owner-transform-x", "persisted native crop centre or model radius changed"),
    ("owner-transform-z", "persisted native crop centre or model radius changed"),
    ("disconnected-handle", "retained native crop handle is disconnected"),
    ("missing-owner", "retained native crop circle has no sketch owner"),
    ("missing-centre", "native circle has no centre point"),
    ("nonfinite-centre", "invalid native circle centre"),
    ("nonfinite-radius", "invalid native circle centre"),
    ("zero-radius", "invalid native circle centre"),
    ("line-not-arc", "native fence is not a sketch arc"),
    ("noncircle", "native fence is not a complete circle"),
))
def test_capture_settled_crop_proof_reads_fresh_retained_native_geometry(
    native_property_package, view_index, defect, refusal,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    view = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[view_index]
    circle = package.doc.crop_circles[view_index - 1]
    rendered_crop, outline = view.crop, view.GetOutline()
    targets = tuple(note.world for note in package.doc.attached_notes)
    if defect in {"centre-x", "centre-z"}:
        axis = 0 if defect == "centre-x" else 2
        circle.centre = tuple(
            value + (0.001 if i == axis else 0.0)
            for i, value in enumerate(circle.centre)
        )
    elif defect == "radius":
        circle.radius += 0.001
    elif defect == "paper-as-sketch":
        inverse = circle.GetSketch().ModelToSketchTransform.Inverse()
        edge = inverse.apply((circle.centre[0] + circle.radius,
                              circle.centre[1], circle.centre[2]))
        circle.centre = inverse.apply(circle.centre)
        circle.radius = math.dist(circle.centre, edge)
    elif defect in {"owner-transform-x", "owner-transform-z"}:
        owner = circle.GetSketch()
        axis = 0 if defect == "owner-transform-x" else 2
        owner.sketch_origin = tuple(
            value + (0.001 if i == axis else 0.0)
            for i, value in enumerate(owner.sketch_origin)
        )
    elif defect == "disconnected-handle":
        def disconnected():
            raise RuntimeError("retained native crop handle is disconnected")
        circle.GetType = disconnected
    elif defect == "missing-owner":
        circle.owner = None
    elif defect == "missing-centre":
        circle.GetCenterPoint2 = lambda: None
    elif defect == "nonfinite-centre":
        circle.centre = (circle.centre[0], circle.centre[1], math.nan)
    elif defect == "nonfinite-radius":
        circle.radius = math.inf
    elif defect == "zero-radius":
        circle.radius = 0.0
    elif defect == "line-not-arc":
        circle.GetType = lambda: 0
    else:
        circle.IsCircle = lambda: 0
    assert view.IsCropped() is True
    assert view.crop == rendered_crop and view.GetOutline() == outline
    assert tuple(note.world for note in package.doc.attached_notes) == targets
    with pytest.raises(RuntimeError, match=refusal):
        drawing._assert_capture_crop(package.adapter, view, view_index, circle)
    with pytest.raises(RuntimeError, match=refusal):
        settled[-1]()


@pytest.mark.parametrize("reference", range(6))
@pytest.mark.parametrize("angle_index", (0, 1))
def test_capture_native_glyph_bounds_normalize_all_anchors_and_rotation(
    native_bom_bindings, reference, angle_index,
) -> None:
    note = _native_glyph_note([{
        "t": "INK", "w": 0.012, "h": 0.004, "pos": (0.100, 0.200, 0.0),
        "ref": reference, "ang": angle_index * math.pi / 2.0,
    }])
    # Fixed measured rectangles, independently worked from the six native
    # anchors; neither the whole-note extent nor production boxer supplies them.
    expected = (
        (
            (0.100, 0.196, 0.112, 0.200),
            (0.100, 0.200, 0.112, 0.204),
            (0.094, 0.198, 0.106, 0.202),
            (0.088, 0.196, 0.100, 0.200),
            (0.088, 0.200, 0.100, 0.204),
            (0.094, 0.196, 0.106, 0.200),
        ),
        (
            (0.100, 0.200, 0.104, 0.212),
            (0.096, 0.200, 0.100, 0.212),
            (0.098, 0.194, 0.102, 0.206),
            (0.100, 0.188, 0.104, 0.200),
            (0.096, 0.188, 0.100, 0.200),
            (0.100, 0.194, 0.104, 0.206),
        ),
    )[angle_index][reference]
    assert drawing._capture_note_bounds(note) == pytest.approx(expected, abs=1e-12)
    assert drawing._capture_note_extent(note) == (0.08, 0.17, 0.14, 0.23)


@pytest.mark.parametrize("key, value", (
    ("w", 0.0), ("w", math.inf), ("h", 0.0), ("h", math.nan),
    ("pos", (0.1,)), ("pos", (0.1, math.nan)), ("ang", math.inf),
    ("ref", -1), ("ref", 6), ("ref", 1.5), ("ref", True), ("t", None),
))
def test_capture_native_glyph_bounds_refuse_invalid_measurements_without_estimation(
    native_bom_bindings, key, value,
) -> None:
    run = {
        "t": "INK", "w": 0.012, "h": 0.004, "pos": (0.1, 0.2, 0.0),
        "ref": 0, "ang": 0.0,
    }
    run[key] = value
    note = _native_glyph_note([run])
    with pytest.raises(RuntimeError, match="unreadable native note text geometry") as refusal:
        drawing._capture_note_bounds(note)
    message = str(refusal.value)
    assert "count=1; runs=" in message
    for field, native_value in run.items():
        assert f"{field!r}: {native_value!r}" in message
    assert "'validation_error':" in message
    # A readable whole extent must never rescue invalid native glyph geometry.
    assert drawing._capture_note_extent(note) == (0.08, 0.17, 0.14, 0.23)


def test_capture_native_glyph_bounds_collect_every_run_and_getter_error(
    native_bom_bindings,
) -> None:
    import ast

    base = {
        "t": "INK", "w": 0.012, "h": 0.004, "pos": (0.1, 0.2, 0.0),
        "ref": 0, "ang": 0.0,
    }
    runs = [
        {**base, "w": RuntimeError("width unavailable")},
        {**base, "ref": 1.5},
        {**base, "t": OSError("text unavailable"), "ang": ValueError("angle unavailable")},
        {**base, "t": "LAST", "pos": (0.2, 0.3, 0.0)},
    ]
    with pytest.raises(RuntimeError, match="unreadable native note text geometry") as refusal:
        drawing._capture_note_bounds(_native_glyph_note(runs))
    assert "count=4;" in str(refusal.value)
    evidence = ast.literal_eval(str(refusal.value).split("; runs=", 1)[1])
    assert [row["index"] for row in evidence] == [0, 1, 2, 3]
    assert evidence[0]["read_errors"] == [("w", "RuntimeError: width unavailable")]
    assert evidence[2]["read_errors"] == [
        ("t", "OSError: text unavailable"), ("ang", "ValueError: angle unavailable"),
    ]
    assert evidence[1]["validation_error"].startswith("ValueError:")
    for index, run in enumerate(runs):
        for key, value in run.items():
            if not isinstance(value, Exception):
                assert evidence[index][key] == value
    assert evidence[3] == {"index": 3, **runs[3]}


@pytest.mark.parametrize("channel", ("display", "count"))
def test_capture_native_glyph_bounds_refuse_interface_and_count_errors(
    native_bom_bindings, monkeypatch, channel,
) -> None:
    note = _native_glyph_note([])

    def unavailable():
        raise OSError("native text channel unavailable")

    if channel == "display":
        monkeypatch.setattr(note.GetAnnotation(), "GetDisplayData", unavailable)
    else:
        monkeypatch.setattr(note.display_data, "GetTextCount", unavailable)
    with pytest.raises(RuntimeError, match="unreadable native note text interface/count") as refusal:
        drawing._capture_note_bounds(note)
    assert "OSError: native text channel unavailable" in str(refusal.value)


@pytest.mark.parametrize("runs", (
    [],
    [{"t": " ", "w": 0.0, "h": 0.0, "pos": (0.1, 0.2), "ref": 0, "ang": 0.0}],
))
def test_capture_native_glyph_bounds_refuse_missing_ink(native_bom_bindings, runs):
    with pytest.raises(RuntimeError, match="unreadable native note text geometry"):
        drawing._capture_note_bounds(_native_glyph_note(runs))


def test_capture_native_glyph_bounds_union_all_measured_runs(native_bom_bindings):
    note = _native_glyph_note([
        {"t": "FIRST", "w": 0.012, "h": 0.004, "pos": (0.1, 0.2), "ref": 1, "ang": 0.0},
        {"t": "SECOND", "w": 0.008, "h": 0.003, "pos": (0.12, 0.19), "ref": 1, "ang": 0.0},
        {"t": " ", "w": 0.0, "h": 0.0, "pos": (0.9, 0.9), "ref": 0, "ang": 0.0},
    ])
    assert drawing._capture_note_bounds(note) == pytest.approx((0.1, 0.19, 0.128, 0.204))


@pytest.mark.parametrize("whole_outside", (False, True))
def test_capture_settled_glyph_and_whole_extents_keep_distinct_authority(
    native_property_package, monkeypatch, whole_outside,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    views = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views
    note = package.doc.attached_notes[0]
    glyph = drawing._capture_note_bounds(note)
    leader = note.GetAnnotation().GetLeaderPointsAtIndex(0)
    whole = (
        min(glyph[0], *leader[0::3]), min(glyph[1], *leader[1::3]),
        max(glyph[2], *leader[0::3]), max(glyph[3], *leader[1::3]),
    )
    if whole_outside:
        whole = (whole[0], drawing.CAPTURE_READING_REGION[1] - 0.001, *whole[2:])
    monkeypatch.setattr(note, "GetExtent", lambda: (*whole[:2], 0.0, *whole[2:], 0.0))
    outline = views[2].GetOutline()
    assert _overlap(whole, outline)
    assert not _overlap(glyph, outline)
    assert drawing._capture_note_bounds(note) == glyph
    assert drawing._capture_note_extent(note) == whole
    if whole_outside:
        import ast

        with pytest.raises(RuntimeError, match="overlap or leave field") as refusal:
            settled[-1]()
        layout = ast.literal_eval(str(refusal.value).split("; layout=", 1)[1])
        assert layout["outside"] == []
        assert layout["whole_outside"] == [1]
        assert layout["rectangles"][1]["bbox_m"] == glyph
        assert layout["rectangles"][1]["whole_bbox_m"] == whole
    else:
        settled[-1]()


def test_capture_section_hidden_channel_overrides_all_true_generated_flags(
    native_property_package,
) -> None:
    package = native_property_package
    package.doc.generated_section_flags_all_true = True
    _scales, settled = drawing._place_package(package.adapter)
    views = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views
    cluster = next(c for c in drawing.CLUSTERS if c.sheet == drawing.PIVOT_CAPTURE_SHEET)
    support = drawing.capture_support_instances(cluster, 0)
    installed = support | {spec.instance_name(spec.CARRIER, 0)}
    for view_index, view in enumerate(views):
        raw = drawing._view_component_leaves(package.adapter, view, label="native tree")
        leaves = drawing._capture_view_leaves(
            package.adapter, view, view_index=view_index, label="jig capture native hidden",
        )
        expected = support if view_index == 0 else installed
        assert {leaf.path for leaf in leaves if leaf.visible} == expected
        if view_index in (2, 3):
            assert len(raw) == 110 and all(leaf.visible for leaf in raw)
            hidden = view.GetHiddenComponents()
            assert len(hidden) == 95
            assert {owner.Name2 for owner in hidden} == {
                f"{package.source_root.Name2}/{leaf.path}"
                for leaf in leaves if not leaf.visible
            }
            assert all(owner.GetParent() is package.source_root for owner in hidden)
        else:
            assert leaves == raw
    # The same native channel must serve placement's reading-leaf cache and
    # the fresh settled proof; no generated-tree visibility is repaired.
    settled[-1]()
    assert all(leaf.Visible for view in views[2:] for leaf in view.components)


@pytest.mark.parametrize("view_index", (2, 3))
@pytest.mark.parametrize("defect", ("hidden-installed", "missing-hide", "none"))
def test_capture_section_hidden_channel_keeps_exact_isolation_guard(
    native_property_package, view_index, defect,
) -> None:
    package = native_property_package
    package.doc.generated_section_flags_all_true = True
    _scales, settled = drawing._place_package(package.adapter)
    view = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[view_index]
    hidden = list(view.GetHiddenComponents())
    carrier_path = spec.instance_name(spec.CARRIER, 0)
    if defect == "hidden-installed":
        carrier = next(leaf for leaf in view.components if leaf.Component.Name2 == carrier_path)
        hidden.append(carrier.native_owner)
        offending_path = carrier_path
    elif defect == "missing-hide":
        removed = hidden.pop()
        offending_path = next(
            leaf.Component.Name2 for leaf in view.components if leaf.native_owner is removed
        )
    else:
        offending_path = carrier_path
    view.GetHiddenComponents = lambda: None if defect == "none" else tuple(hidden)
    if defect == "none":
        leaves = drawing._capture_view_leaves(
            package.adapter, view, view_index=view_index, label="jig capture native hidden",
        )
        assert len(leaves) == 110 and all(leaf.visible for leaf in leaves)
    with pytest.raises(RuntimeError, match=f"jig capture view {view_index}: wrong visible occurrence isolation") as refusal:
        settled[-1]()
    message = str(refusal.value)
    assert repr(offending_path) in message
    if defect == "hidden-installed":
        assert f"missing={[carrier_path]!r}; extra=[]" in message
    else:
        assert "missing=[]; extra=[" in message
    assert all(leaf.Visible for leaf in view.components)


@pytest.mark.parametrize("view_index", (2, 3))
@pytest.mark.parametrize("defect", (
    "unknown", "bare-name", "drawing-root-prefix", "foreign-parent-prefix",
    "foreign-source-file", "wrong-part-file", "empty-owner-file",
    "empty-leaf-file", "null-parent", "parent-depth", "empty-parent-name",
    "empty-parent-file", "parent-read-error", "owner-name-read-error",
    "owner-file-read-error",
    "empty-occurrence-path",
    "hidden-query-error", "hidden-query-unsupported", "hidden-bind-error",
    "duplicate-hidden", "duplicate-leaf-candidate",
))
def test_capture_section_hidden_channel_refuses_unproved_native_identity(
    native_property_package, monkeypatch, view_index, defect,
) -> None:
    package = native_property_package
    package.doc.generated_section_flags_all_true = True
    drawing._place_package(package.adapter)
    view = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[view_index]
    hidden = list(view.GetHiddenComponents())
    if defect == "empty-occurrence-path":
        nonsemantic = next(
            item.native_owner for item in view.components
            if item._hidden and item.Component.ComponentReference == ""
        )
        hidden = [nonsemantic, *(item for item in hidden if item is not nonsemantic)]
    original = hidden[0]
    owner = SimpleNamespace(**vars(original))
    hidden[0] = owner
    leaf = next(item for item in view.components if item.native_owner is original)
    root = package.source_root
    path = leaf.Component.Name2

    def unreadable():
        raise OSError("native hidden metadata unavailable")

    if defect == "unknown":
        owner.Name2 = f"{root.Name2}/unknown-occurrence-1"
    elif defect == "bare-name":
        owner.Name2 = path
    elif defect == "drawing-root-prefix":
        owner.Name2 = leaf.Name
    elif defect == "foreign-parent-prefix":
        owner.Name2 = f"foreign-parent/{path}"
    elif defect == "foreign-source-file":
        owner.GetParent = lambda: _source_owner(
            root.Name2, part_file=str(drawing.SOURCE.with_name(f"foreign-{drawing.SOURCE.name}")),
        )
    elif defect == "wrong-part-file":
        owner.GetPathName = lambda: "C:/native/unrelated.SLDPRT"
    elif defect == "empty-owner-file":
        owner.GetPathName = lambda: ""
    elif defect == "owner-file-read-error":
        owner.GetPathName = unreadable
    elif defect == "empty-leaf-file":
        leaf.Component.GetPathName = lambda: ""
    elif defect == "empty-occurrence-path":
        leaf.Component.Name2 = ""
        owner.Name2 = f"{root.Name2}/"
    elif defect == "null-parent":
        owner.GetParent = lambda: None
    elif defect == "parent-depth":
        owner.GetParent = lambda: _source_owner(
            root.Name2, part_file=str(drawing.SOURCE), parent=root,
        )
    elif defect == "empty-parent-name":
        owner.GetParent = lambda: _source_owner("", part_file=str(drawing.SOURCE))
        owner.Name2 = f"/{path}"
    elif defect == "empty-parent-file":
        owner.GetParent = lambda: _source_owner(root.Name2, part_file="")
    elif defect == "parent-read-error":
        owner.GetParent = unreadable
    elif defect == "owner-name-read-error":
        class UnreadableName(SimpleNamespace):
            @property
            def Name2(self):
                return unreadable()
        owner = UnreadableName(GetPathName=original.GetPathName, GetParent=original.GetParent)
        hidden[0] = owner
    elif defect == "hidden-query-error":
        view.GetHiddenComponents = unreadable
    elif defect == "hidden-query-unsupported":
        del view.GetHiddenComponents
    elif defect == "hidden-bind-error":
        original_bind = drawing._bind

        def bind(value, interface):
            if value is owner and interface == "IComponent2":
                return unreadable()
            return original_bind(value, interface)

        monkeypatch.setattr(drawing, "_bind", bind)
    elif defect == "duplicate-hidden":
        hidden.append(owner)
    elif defect == "duplicate-leaf-candidate":
        view.components.append(_CaptureNativeDrawingComponent(**vars(leaf)))
    if defect not in ("hidden-query-error", "hidden-query-unsupported"):
        view.GetHiddenComponents = lambda: tuple(hidden)
    with pytest.raises(RuntimeError, match="jig capture native hidden"):
        drawing._capture_view_leaves(
            package.adapter, view, view_index=view_index, label="jig capture native hidden",
        )


@pytest.mark.parametrize("defect", (
    "source-qualified-name", "carrier-hidden", "empty-path",
))
@pytest.mark.parametrize("unread_view", ("source-qualified-name", "read-error"))
def test_capture_settled_isolation_refusal_reports_all_native_view_censuses(
    native_property_package, defect, unread_view,
) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    views = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views
    cluster = next(c for c in drawing.CLUSTERS if c.sheet == drawing.PIVOT_CAPTURE_SHEET)
    support = drawing.capture_support_instances(cluster, 0)
    carrier_path = spec.instance_name(spec.CARRIER, 0)
    installed = support | {carrier_path}
    carrier = next(leaf for leaf in views[2].components if leaf.Component.Name2 == carrier_path)
    qualified_path = f"{package.source_root.Name2}/{carrier_path}"
    if defect == "source-qualified-name":
        carrier.Component.Name2 = qualified_path
        actual = (installed - {carrier_path}) | {qualified_path}
        offending = [(carrier.Name, qualified_path, True)]
        extra = [qualified_path]
    elif defect == "carrier-hidden":
        carrier.Visible = False
        actual = installed - {carrier_path}
        offending = [(carrier.Name, carrier_path, False)]
        extra = []
    else:
        # This authored component has no semantic reference requiring a path.
        assert carrier.Component.ComponentReference == ""
        carrier.Component.Name2 = ""
        actual = (installed - {carrier_path}) | {""}
        offending = [(carrier.Name, "", True)]
        extra = [""]

    # View 3 has not been walked when the strict view-2 isolation check fails.
    # Its own fresh inventory (or read error) must be in that same refusal.
    if unread_view == "source-qualified-name":
        last_carrier = next(
            leaf for leaf in views[3].components if leaf.Component.Name2 == carrier_path
        )
        last_carrier.Component.Name2 = qualified_path
        last_actual = (installed - {carrier_path}) | {qualified_path}
        last_offending = [(last_carrier.Name, qualified_path, True)]
        last_record = (
            f"view 3: expected={sorted(installed)!r}; actual={sorted(last_actual)!r}; "
            f"missing={[carrier_path]!r}; extra={[qualified_path]!r}; leaves={last_offending!r}"
        )
    else:
        views[3].RootDrawingComponent2 = lambda _resolve: None
        error = RuntimeError("jig capture isolation census: drawing view has no root component")
        last_record = f"view 3: read_error={error!r}"

    # Keep the actual native leaf reader and the section's independent native
    # hidden collection: neither may normalize or repair occurrence identity.
    assert drawing._view_component_leaves is _drawing_balloons._view_component_leaves
    with pytest.raises(RuntimeError) as refusal:
        settled[-1]()
    census = [
        f"view 0: expected={sorted(support)!r}; actual={sorted(support)!r}; "
        "missing=[]; extra=[]; leaves=[]",
        f"view 1: expected={sorted(installed)!r}; actual={sorted(installed)!r}; "
        "missing=[]; extra=[]; leaves=[]",
        f"view 2: expected={sorted(installed)!r}; actual={sorted(actual)!r}; "
        f"missing={[carrier_path]!r}; extra={extra!r}; leaves={offending!r}",
        last_record,
    ]
    assert str(refusal.value) == (
        "jig capture view 2: wrong visible occurrence isolation; "
        f"isolation_census={census!r}"
    )


@pytest.mark.parametrize("defect", ("caption-overlaps", "captions-outside"))
def test_capture_layout_refusal_reports_all_native_caption_conflicts(
    native_property_package, monkeypatch, defect,
) -> None:
    import ast

    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    _exploded, locator, main, bolt = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views
    captions = (
        next(note for note in locator.notes if note.GetText().startswith("ASSEMBLED PLAN ")),
        next(note for note in main.notes if "<VLLABEL>" in note.PropertyLinkedText),
        next(note for note in bolt.notes if "<VLLABEL>" in note.PropertyLinkedText),
    )
    def glyph_bounds(note):
        # These fixture runs are independently measured upper-left,
        # unrotated rectangles; direct anchor tests cover normalization.
        boxes = []
        for run in note.GetAnnotation().GetDisplayData().runs:
            if run["t"].strip():
                assert run["ref"] == 0 and run["ang"] == 0.0
                x, y = run["pos"][:2]
                boxes.append((x, y - run["h"], x + run["w"], y))
        return (
            min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes),
        )

    field = drawing.CAPTURE_READING_REGION
    if defect == "caption-overlaps":
        first_box, second_box = (
            glyph_bounds(note) for note in package.doc.attached_notes[:2]
        )
        caption_boxes = (first_box, second_box, first_box)
    else:
        left, bottom, right, top = field
        caption_boxes = (
            (left - 0.003, bottom + 0.005, left - 0.001, bottom + 0.007),
            (right + 0.001, bottom + 0.005, right + 0.004, bottom + 0.007),
            (left + 0.005, top + 0.001, left + 0.009, top + 0.004),
        )
    for note, box in zip(captions, caption_boxes, strict=True):
        raw = note.GetExtent()
        # Whole-note bounds independently enclose both the glyphs and the
        # leader/other supplied extent; only glyphs govern overlap guards.
        whole = (
            min(raw[0], box[0]), min(raw[1], box[1]),
            max(raw[3], box[2]), max(raw[4], box[3]),
        )
        monkeypatch.setattr(
            note, "GetExtent", lambda whole=whole: (*whole[:2], 0.0, *whole[2:], 0.0),
        )
        if defect == "caption-overlaps":
            data = _CaptureNativeTextData([{
                "t": note.GetText(), "w": box[2] - box[0], "h": box[3] - box[1],
                "pos": (box[0], box[3], 0.0), "ref": 0, "ang": 0.0,
            }])
            monkeypatch.setattr(
                note.GetAnnotation(), "GetDisplayData", lambda data=data: data,
            )
    native_notes = [
        ("locator caption", captions[0]),
        *(
            (f"jig capture {reading.text.splitlines()[0]} {reading.local_mm}", note)
            for reading, note in zip(
                drawing.capture_readings(), package.doc.attached_notes, strict=True,
            )
        ),
        ("section caption", captions[1]),
        ("section caption", captions[2]),
    ]
    observed = []
    for index, (label, note) in enumerate(native_notes):
        raw = note.GetExtent()
        whole = (raw[0], raw[1], raw[3], raw[4])
        box = glyph_bounds(note)
        observed.append({
            "index": index, "label": label, "bbox_m": box,
            "whole_bbox_m": whole,
            "field_gaps_m": (
                box[0] - field[0], box[1] - field[1],
                field[2] - box[2], field[3] - box[3],
            ),
            "whole_field_gaps_m": (
                whole[0] - field[0], whole[1] - field[1],
                field[2] - whole[2], field[3] - whole[3],
            ),
        })
    assert len(observed) == 17
    overlaps = []
    for a, first in enumerate(observed):
        for b, second in enumerate(observed[a + 1:], a + 1):
            x, y = first["bbox_m"], second["bbox_m"]
            if _overlap(x, y):
                overlaps.append({
                    "a": a, "b": b,
                    "gaps_m": (
                        max(x[0], y[0]) - min(x[2], y[2]),
                        max(x[1], y[1]) - min(x[3], y[3]),
                    ),
                })
    segments = []
    for label, note in native_notes[1:-2]:
        raw = note.GetAnnotation().GetLeaderPointsAtIndex(0)
        segments.extend(
            LeaderSegment(
                label=label, kind="note", x0=raw[i], y0=raw[i + 1],
                x1=raw[i + 3], y1=raw[i + 4],
            )
            for i in range(0, len(raw) - 3, 3)
        )
    with pytest.raises(
        RuntimeError, match="jig capture: native captions/reading labels overlap or leave field",
    ) as refusal:
        settled[-1]()
    layout = ast.literal_eval(str(refusal.value).split("; layout=", 1)[1])
    assert layout["field_m"] == field
    assert layout["rectangles"] == observed
    assert layout["outside"] == [
        rectangle["index"] for rectangle in observed
        if any(gap < 0.0 for gap in rectangle["field_gaps_m"])
    ]
    assert layout["whole_outside"] == [
        rectangle["index"] for rectangle in observed
        if any(gap < 0.0 for gap in rectangle["whole_field_gaps_m"])
    ]
    assert layout["overlaps"] == overlaps
    if defect == "caption-overlaps":
        assert {(0, 1), (0, 16), (1, 16), (2, 15)} <= {
            (pair["a"], pair["b"]) for pair in layout["overlaps"]
        }
        assert all(gap < 0.0 for pair in overlaps for gap in pair["gaps_m"])
        assert layout["outside"] == []
        assert layout["whole_outside"] == []
    else:
        assert layout["outside"] == []
        assert layout["whole_outside"] == [0, 15, 16]
    assert layout["view_outlines"] == [
        {"view_index": index, "bbox_m": tuple(view.GetOutline())}
        for index, view in enumerate((locator, main, bolt), 1)
    ]
    assert layout["model_overlaps"] == [
        (rectangle["index"], outline["view_index"])
        for rectangle in observed for outline in layout["view_outlines"]
        if _overlap(rectangle["bbox_m"], outline["bbox_m"])
    ]
    assert layout["leaders"] == [
        (segment.label, segment.kind, segment.x0, segment.y0, segment.x1, segment.y1)
        for segment in segments
    ]
    assert layout["leader_label_crossings"] == [
        (index, rectangle["index"])
        for index, segment in enumerate(segments) for rectangle in observed
        if segment.label != rectangle["label"]
        and drawing._segment_crosses_box(segment, rectangle["bbox_m"], inset=0.0)
    ]
    assert layout["leader_crossings"] == [
        (crossing.a.label, crossing.b.label, crossing.x, crossing.y)
        for crossing in find_leader_leader_crossings(segments)
    ]


@pytest.mark.parametrize("defect", (
    "extra-view", "scale", "configuration", "exploded", "carrier-hidden",
    "crop", "missing-section", "hatch", "partial", "label", "cut-plane",
    "cut-axis", "fasteners", "cut-only", "hidden-lines", "cut-arrows", "legacy-xy-cut",
    "attachment", "edge-owner", "edge-owner-root", "edge-owner-parent-file",
    "edge-owner-part-file", "edge-owner-depth", "view-owner", "wrong-note-view", "right-balloon",
    "missing-native-balloon", "extra-native-balloon", "substituted-native-balloon",
    "landing", "font", "caption",
    "caption-overlap", "note-overlap", "balloon-border", "bearing-duplicate",
    "bearing-number", "third-bearing", "other-duplicate",
))
def test_capture_settled_proof_refuses_native_drift(native_property_package, defect) -> None:
    package = native_property_package
    _scales, settled = drawing._place_package(package.adapter)
    sheet = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET]
    exploded, locator, main, bolt = sheet.views
    first_note = package.doc.attached_notes[0]
    bearings = [item for item in package.doc.balloon_landings if item.stem == spec.BEARING]
    if defect == "extra-view":
        sheet.views.append(locator)
    elif defect == "scale":
        numerator, denominator = main.ScaleRatio
        main.ScaleRatio = (numerator, denominator * 2)
    elif defect == "configuration":
        main.ReferencedConfiguration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    elif defect == "exploded":
        locator.exploded = True
    elif defect == "carrier-hidden":
        next(leaf for leaf in main.components if leaf.Component.Name2 == spec.instance_name(spec.CARRIER, 0)).Visible = False
    elif defect == "crop":
        bolt.cropped = False
    elif defect == "missing-section":
        main.section = None
    elif defect == "hatch":
        main.section.hatch = False
    elif defect == "partial":
        main.section.partial = False
    elif defect == "label":
        bolt.section.label = "A"
    elif defect == "cut-plane":
        main.section.line_shift = (0.0, 0.001, 0.0)
    elif defect == "legacy-xy-cut":
        main.section.GetLineInfo = lambda: (0.1, 0.2, 0.3, 0.4)
    elif defect == "cut-axis":
        main.Angle += 0.1
    elif defect == "fasteners":
        main.section.ExcludeFasteners = True
    elif defect == "cut-only":
        main.section.cut_only = True
    elif defect == "hidden-lines":
        main.mode = 3
    elif defect == "cut-arrows":
        main.section.GetArrowInfo = lambda: (0.0,) * 12
    elif defect == "attachment":
        first_note.entity = object()
    elif defect.startswith("edge-owner"):
        # A fully shaped native owner that drifted in exactly one identity.
        owner = SimpleNamespace(**vars(first_note.entity.owner))
        root = package.source_root
        if defect == "edge-owner":
            owner.Name2 = f"{root.Name2}/{spec.instance_name(spec.PIVOT_PIN, 1)}"
        elif defect == "edge-owner-root":
            owner.Name2 = f"Draw54-SectionAssembly-1-1/{spec.instance_name(spec.PIVOT_PIN, 0)}"
        elif defect == "edge-owner-parent-file":
            owner.GetParent = lambda: SimpleNamespace(**{
                **vars(root),
                "GetPathName": lambda: str(drawing.SOURCE.with_name(f"foreign-{drawing.SOURCE.name}")),
            })
        elif defect == "edge-owner-part-file":
            owner.GetPathName = lambda: f"C:/native/{spec.COMPONENT_IDENTITIES[spec.PIVOT_BLOCK][0]}.SLDPRT"
        else:
            owner.GetParent = lambda: SimpleNamespace(**{**vars(root), "GetParent": lambda: root})
        first_note.entity.GetComponent = lambda: owner
    elif defect == "view-owner":
        first_note.annotation.OwnerType = 1
    elif defect == "landing":
        first_note.landing_shift = (0.001, 0.0)
    elif defect == "font":
        first_note.annotation.GetTextFormat(0).CharHeight = 0.003
    elif defect == "wrong-note-view":
        main.notes.remove(first_note)
        bolt.notes.append(first_note)
    elif defect == "right-balloon":
        first_note.IsBomBalloon = lambda: True
    elif defect == "missing-native-balloon":
        exploded.notes.remove(bearings[0].note)
    elif defect == "extra-native-balloon":
        exploded.notes.append(SimpleNamespace(**vars(bearings[0].note)))
    elif defect == "substituted-native-balloon":
        exploded.notes[exploded.notes.index(bearings[0].note)] = SimpleNamespace(**vars(bearings[0].note))
    elif defect == "caption":
        main.notes[0].PropertyLinkedText = ""
    elif defect == "caption-overlap":
        main.notes[0].position[:] = first_note.position
    elif defect == "note-overlap":
        package.doc.attached_notes[1].position[:] = first_note.position
    elif defect == "balloon-border":
        left, bottom, _right, top = drawing.CAPTURE_EXPLODED_REGION
        bearings[0].note.circle = (left, (bottom+top)/2.0, drawing.BALLOON_RADIUS)
    elif defect == "bearing-duplicate":
        bearings[1].instance = bearings[0].instance
    elif defect == "bearing-number":
        bearings[1].note.GetBomBalloonText = lambda _upper: "4"
    elif defect in {"third-bearing", "other-duplicate"}:
        # The retained callback must also refuse a changed capture landing set.
        cluster = next(c for c in drawing.CLUSTERS if c.sheet == sheet.name)
        landings = [item for item in package.doc.balloon_landings if item.stem in cluster.stems]
        landings.append(bearings[0] if defect == "third-bearing" else next(item for item in landings if item.stem != spec.BEARING))
        with pytest.raises(RuntimeError, match="exactly two bearings"):
            drawing._assert_capture_coverage(landings, cluster.stems)
        return
    with pytest.raises(RuntimeError, match="jig capture|reading label"):
        settled[-1]()


def test_capture_both_bearings_join_one_existing_ring_and_keep_exact_item14(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *_args: None)
    links, calls, rings = [], [], []
    monkeypatch.setattr(drawing, "_link_view_to_bom", lambda view, bom, **_kw: links.append((view, bom)))
    monkeypatch.setattr(drawing, "_source_configuration_active", lambda *_a, **_kw: nullcontext())
    monkeypatch.setattr(drawing, "_ring_balloons", lambda _a, _v, landings, **_kw: rings.append(tuple(landings)))
    cluster = next(c for c in drawing.CLUSTERS if c.sheet == drawing.PIVOT_CAPTURE_SHEET)
    view = object()

    def create(_adapter, requested_view, *, items, anchors, **_kwargs):
        assert requested_view is view
        calls.append((tuple(items), anchors))
        return [
            drawing.BalloonLanding(
                stem=stem, instance=anchors[stem].instance or spec.instance_name(stem, 0),
                note=SimpleNamespace(GetBomBalloonText=lambda _upper, item=item: str(item)),
                sheet_xy=(0.1, 0.1), label="native balloon boundary",
            )
            for stem, item in items
        ]

    monkeypatch.setattr(drawing, "add_component_bom_balloons", create)
    landings = drawing._balloon_cluster(object(), view, cluster, tuple(spec.ITEM_NUMBERS.items()), "JigBOM")
    assert links == [(view, "JigBOM")]
    assert len(calls) == 2 and len(calls[0][0]) == 8 and len(calls[1][0]) == 1
    assert calls[0][1][spec.BEARING].instance is None
    assert calls[1][1][spec.BEARING].instance == spec.instance_name(spec.BEARING, 1)
    assert len(landings) == 9 and rings == [tuple(landings)]
    drawing._assert_capture_coverage(landings, cluster.stems)


def test_capture_fit_exhaustion_refuses_before_any_bom(native_property_package) -> None:
    package = native_property_package
    package.doc.oversized = drawing.PIVOT_CAPTURE_SHEET
    with pytest.raises(RuntimeError, match="no measured scale fits"):
        drawing._place_package(package.adapter)
    assert not package.doc.bom_inserted


def test_capture_uncropped_fit_refreshes_native_geometry_at_each_candidate_scale(
    native_property_package,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    exploded = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[0]
    assert exploded.IsCropped() is False
    native_outline = exploded.GetOutline
    refreshed = []

    def refresh():
        refreshed.append(tuple(exploded.ScaleRatio))
        return None  # Native UpdateViewDisplayGeometry is VT_VOID.

    def outline():
        box = native_outline()
        # Until refreshed, the native cache retains an oversized pre-change
        # view. The refreshed 1:4 also misses; uncropped 1:5 first fits.
        if not refreshed or refreshed[-1] != tuple(exploded.ScaleRatio) or exploded.ScaleRatio[1] == 4:
            return (*box[:3], box[3] + 0.3)
        return box

    exploded.UpdateViewDisplayGeometry = refresh
    exploded.GetOutline = outline
    scale = drawing._fit_capture_view(
        package.adapter, exploded, drawing.CAPTURE_VIEW_REGIONS[0],
        ((1, 4), (1, 5), (1, 6)), label="jig capture exploded",
    )
    assert scale == (1, 5)
    assert refreshed == [(1.0, 4.0), (1.0, 5.0)]
    assert _inside(native_outline(), drawing.CAPTURE_VIEW_REGIONS[0])


@pytest.mark.parametrize("view_index, ladder, has_profile, refusal", (
    (1, ((1, 4), (1, 5), (1, 6)), True, "cropped view requires one pre-authored scale"),
    (2, ((1, 1), (1, 2)), True, "cropped view requires one pre-authored scale"),
    (1, ((1, 5),), True, "cropped view scale differs from its pre-authored scale"),
    (2, ((1, 2),), True, "cropped view scale differs from its pre-authored scale"),
    (3, ((1, 2),), True, "cropped view scale differs from its pre-authored scale"),
    (1, ((1, 4),), False, "cropped view lost its selected native profile"),
))
def test_capture_cropped_fit_refuses_rescaling_or_a_lost_selected_profile(
    native_property_package, view_index, ladder, has_profile, refusal,
) -> None:
    package = native_property_package
    drawing._place_package(package.adapter)
    view = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[view_index]
    circle = package.doc.crop_circles[view_index - 1]
    before = (tuple(view.ScaleRatio), tuple(view.Position), view.GetOutline())
    with pytest.raises(RuntimeError, match=refusal):
        drawing._fit_capture_view(
            package.adapter, view, drawing.CAPTURE_VIEW_REGIONS[view_index], ladder,
            crop_profile=circle if has_profile else None, label="jig capture fixed crop",
        )
    assert (tuple(view.ScaleRatio), tuple(view.Position), view.GetOutline()) == before
    assert view.post_crop_scale_writes == []




def test_capture_cropped_fit_refusal_reports_actual_owner_geometry_at_authored_scale(
    native_property_package,
) -> None:
    import ast

    package = native_property_package
    drawing._place_package(package.adapter)
    locator = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[1]
    circle = package.doc.crop_circles[0]
    owner = circle.GetSketch()
    origin = locator.sketch.sketch_origin
    locator.sketch.sketch_origin = (origin[0] + 0.001, origin[1], origin[2] + 0.001)
    locator.GetOutline = lambda: (0.1, 0.1, 0.3, 0.3)
    field = drawing.CAPTURE_VIEW_REGIONS[1]
    assert field == (0.224, 0.220, 0.278, 0.263)
    assert (field[2] - field[0], field[3] - field[1]) == pytest.approx((0.054, 0.043))
    with pytest.raises(RuntimeError, match="no measured scale fits its reserved field") as failure:
        drawing._fit_capture_view(
            package.adapter, locator, field, ((1, 4),),
            crop_profile=circle, label="jig capture locator",
        )
    message = str(failure.value)
    assert f"field={field!r}; margin=0.0;" in message
    candidates = ast.literal_eval(message.split("; candidates=", 1)[1])
    candidate, = candidates
    assert candidate["scale"] == (1.0, 4.0)
    assert candidate["position"] == tuple(locator.Position)
    assert candidate["outline"] == (0.1, 0.1, 0.3, 0.3)
    assert candidate["overflows"] == ["width 200.0 mm > 54.0 mm", "height 200.0 mm > 43.0 mm"]
    assert candidate["cropped"] is True
    assert candidate["sketch_transform"] == owner.ModelToSketchTransform.ArrayData
    assert candidate["sketch_transform"] != locator.sketch.ModelToSketchTransform.ArrayData
    crop, = candidate["crop_circles"]
    assert crop["sketch_centre"] == circle.centre
    assert crop["sketch_radius"] == circle.radius
    inverse = owner.ModelToSketchTransform.Inverse()
    sheet_centre = inverse.apply(circle.centre)
    sheet_rim = inverse.apply((circle.centre[0] + circle.radius, *circle.centre[1:]))
    assert crop["sheet_centre"] == pytest.approx(sheet_centre)
    assert crop["sheet_radius"] == pytest.approx(math.dist(sheet_centre, sheet_rim))
    assert crop["sheet_radius"] == pytest.approx(0.055 / 4.0)
    assert tuple(locator.ScaleRatio) == (1, 4)
    assert locator.post_crop_scale_writes == []


@pytest.mark.parametrize("defect", ("section-xyz", "persisted-crop"))
def test_capture_native_proof_is_called_by_real_finalizer_after_rebuild(
    native_property_package, defect,
) -> None:
    package = native_property_package
    scales, settled = drawing._place_package(package.adapter)
    main = package.doc.sheets[drawing.PIVOT_CAPTURE_SHEET].views[2]
    if defect == "section-xyz":
        # An XYZ-only drift cannot be caught by paper-plane XY collinearity.
        main.section.line_shift = (0.0, 0.0, 0.001)
        refusal = "native cut plane"
    else:
        circle = package.doc.crop_circles[1]
        circle.radius += 0.001
        assert main.IsCropped() is True
        refusal = "persisted native crop centre or model radius changed"
    with pytest.raises(RuntimeError, match=refusal):
        asyncio.run(drawing.finalize_drawing(
            package.adapter, drawing.OUTPUTS, layout=drawing.SPEC.layout,
            pdf_title="native capture lifecycle", scale=drawing.SHEET_SCALE,
            expected_sheet_names=drawing.SHEET_NAMES,
            sheet_layouts=drawing.SHEET_LAYOUTS, sheet_scales=scales,
            settled_checks=(settled[-1],),
        ))
