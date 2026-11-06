"""Offline contract for the oblique-trammel jig drawing package (TL-00).

The sheet text comes from the jig spec, the BOM prints every family made and
bought with its registry number, numbered as the steps cite it, every BOM row
carries a balloon, and each sheet's budgeted regions stay inside the border,
out of the title block and clear of one another. Actual view creation and the
shared finalizer must leave every physical sheet linked to the live source.
"""

from __future__ import annotations

import functools
import math
from types import SimpleNamespace

import numpy as np
import pytest

import _com
import _config
import _drawing_balloons
import _component_references
import _drawing_tables
import _drawing_dimensions
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
import draw_ch_rocker_arm_tl_oblique_jig_assembly as drawing
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings


# Default-format note text: about 2.8 mm a character and 4.5 mm a line on the
# farm's templates (draw_pd_paper_drive_assembly fits 68 characters in 0.192).
CHAR_M = 0.0029
LINE_M = drawing.NOTE_LINE_M
ROW_PITCH_M = 0.00615
ISO = math.sqrt(2.0 / 3.0)  # an isometric view's foreshortening


def _ink_height(text: str) -> float:
    """The taller of the layout's flat line pitch and the farm-measured ink
    (a first line's box plus a pitch a further line)."""
    return max(_lines(text) * LINE_M, drawing.note_ink_height(text))


def _note_box(text: str, xy: tuple[float, float]) -> tuple[float, float, float, float]:
    lines = text.split("\n")
    width = max(len(line) for line in lines) * CHAR_M
    return xy[0], xy[1] - _ink_height(text), xy[0] + width, xy[1]


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


def _pivot_cluster_extent():
    """Bounds of the new purchased pieces under their actual explode transforms."""
    screw, spacer, shim = spec.pivot_screw, spec.pivot_spacer, spec.pivot_shim
    head_radius = screw.HEAD_DIA / 2.0
    spacer_radius, shim_radius = spacer.OD / 2.0, shim.OD / 2.0
    boxes = {
        spec.PIVOT_SCREW: (
            (-head_radius, head_radius), (-head_radius, head_radius),
            (-screw.THREAD_LENGTH, screw.SHOULDER_LENGTH + screw.HEAD_HEIGHT),
        ),
        spec.PIVOT_SPACER: (
            (-spacer_radius, spacer_radius), (-spacer_radius, spacer_radius),
            (0.0, spacer.LENGTH),
        ),
        spec.PIVOT_SHIM: (
            (-shim_radius, shim_radius), (-shim_radius, shim_radius),
            (0.0, shim.THICKNESS),
        ),
    }
    points = [
        point for stem, bounds in boxes.items()
        for point in _exploded_part_points(stem, bounds)
    ]
    for stem in (spec.FEED_BLOCK, spec.PIVOT_BLOCK):
        block = spec.feed_block if stem == spec.FEED_BLOCK else spec.pivot_block
        bounds = (
            (block.BLOCK_X0, block.BLOCK_X1),
            (spec.feed_block.LUG_Y0 if stem == spec.FEED_BLOCK else -block.BLOCK_WIDTH / 2.0,
             block.BLOCK_WIDTH / 2.0),
            (0.0, block.BLOCK_HEIGHT),
        )
        points.extend(_exploded_part_points(stem, bounds))
    return [(x, y) for x, y, _z in points], (
        min(z for _x, _y, z in points), max(z for _x, _y, z in points)
    )


def _hub_hardware_points():
    """Actual new R3 hardware envelopes, including their distinct explode lifts."""
    stud, sleeve, washer = spec.hub_stud, spec.hub_sleeve, spec.hub_washer
    boxes = {
        spec.HUB_STUD: (
            (-stud.FLANGE_DIA / 2.0, stud.FLANGE_DIA / 2.0),
            (-stud.FLANGE_DIA / 2.0, stud.FLANGE_DIA / 2.0),
            (0.0, stud.LENGTH),
        ),
        spec.HUB_SLEEVE: (
            (-sleeve.OD / 2.0, sleeve.OD / 2.0),
            (-sleeve.OD / 2.0, sleeve.OD / 2.0),
            (0.0, sleeve.LENGTH),
        ),
        spec.HUB_WASHER: (
            (-washer.OD / 2.0, washer.OD / 2.0),
            (-washer.OD / 2.0, washer.OD / 2.0),
            (0.0, washer.THICK),
        ),
    }
    for family, screw in ((spec.HUB_SCREW, spec.hub_screw), (spec.LEFT_CLAMP_SCREW, spec.left_clamp_screw)):
        radius = max(screw.DIMS.head_dia, screw.DIMS.major_dia) / 2.0
        boxes[family] = ((-radius, radius), (-screw.DIMS.length, screw.DIMS.head_h), (-radius, radius))
    return {
        family: _exploded_part_points(family, bounds)
        for family, bounds in boxes.items()
    }


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
    elif sheet == drawing.PIVOT_SHEET:
        return _pivot_cluster_extent()
    elif sheet == "LEADSCREW FEED EXPLODED":
        points = [p for outline in spec.feed_outlines().values() for p in outline]
        points += [
            (x + spec.explode_shift(spec.HANDWHEEL, "x"), y)
            for x, y in feed.rect(*feed.HANDWHEEL_BOX)
        ]
        block = spec.feed_block
        points += feed.rect(
            spec.CARRIAGE_STATION + block.BLOCK_X0,
            spec.CARRIAGE_STATION + block.BLOCK_X1,
            -block.BLOCK_WIDTH / 2.0,
            -block.LUG_Y0,
        )
        # The feed block's four carriage screws explode above it here.
        screw_tops = (
            origin[2] + spec.carriage_screw.DIMS.head_h + lift(spec.CARRIAGE_SCREW)
            for (origin, _rows), parent in zip(
                spec.CARRIAGE_SCREW_PLACEMENTS,
                spec.LOCKED_TO[spec.CARRIAGE_SCREW],
                strict=True,
            )
            if parent == (spec.FEED_BLOCK, 0)
        )
        z = (
            -feed.BAR_SCREW_LENGTH_MM + lift(spec.BAR_SCREW_INSTANCES[0]),
            max(spec.trammel.PIVOT_BLOCK_TOP_Z + lift(spec.FEED_BLOCK), *screw_tops),
        )
    else:
        assert sheet == "CARRIER EXPLODED"
        points = [
            spec.POSE.to_machine(p)
            for outline in spec.CARRIER_OUTLINES.values()
            for p in outline
        ]
        z = (
            spec.HUB_STUD_BOTTOM_Z + lift(spec.HUB_STUD),
            spec.MODEL_EXTENT[2][1] + lift(spec.LEVER_SCREW),
        )
        hardware = [point for corners in _hub_hardware_points().values() for point in corners]
        points.extend((x, y) for x, y, _z in hardware)
        z = (min(z[0], *(point[2] for point in hardware)),
             max(z[1], *(point[2] for point in hardware)))
    return points, z


def test_carrier_exploded_extent_includes_all_new_hardware() -> None:
    cluster = next(cluster for cluster in drawing.CLUSTERS if cluster.sheet == "CARRIER EXPLODED")
    hardware = _hub_hardware_points()
    assert set(hardware) == {
        spec.HUB_STUD, spec.HUB_SLEEVE, spec.HUB_WASHER, spec.HUB_SCREW, spec.LEFT_CLAMP_SCREW,
    }
    assert set(hardware) <= set(cluster.stems)
    points, (low, high) = _cluster_extent(cluster.sheet)
    for family, corners in hardware.items():
        assert spec.QUANTITIES[family] == 1
        assert spec.explode_lift(family) != 0.0
        assert family in drawing.BALLOON_ANCHORS
        for x, y, z in corners:
            assert (x, y) in points
            assert low <= z <= high


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
    assert drawing.SHEET_NAMES[7:10] == (drawing.FIT_SHEET, drawing.OPERATION_SHEET, drawing.HOLDING_SHEET)
    # The owner's linear-motion sheet is appended: no cited sheet number moves.
    assert drawing.SHEET_NAMES[10:] == (drawing.LINEAR_MOTION_SHEET,)
    assert len(drawing.SHEET_NAMES) == 11
    assert drawing.SHEET_NAMES.index(drawing.OPERATION_SHEET) + 1 == spec.OPERATION_SHEET_NUMBER
    assert set(drawing.SHEET_LAYOUTS.values()) == {drawing.DrawingLayout.LANDSCAPE}
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert drawing.SHEET_SCALES[drawing.ASSEMBLED_SHEET] == drawing.ASSEMBLED_SCALE
    assert drawing.SHEET_SCALES[drawing.BOM_SHEET] == drawing.REFERENCE_SCALE
    assert drawing.SHEET_SCALES[drawing.OPERATION_SHEET] == drawing.ISOMETRIC_SCALE
    assert drawing.SHEET_SCALES[drawing.STEPS_SHEET] == drawing.NOTES_REFERENCE_SCALE
    assert drawing.SHEET_SCALES[drawing.FIT_SHEET] == drawing.NOTES_REFERENCE_SCALE
    assert drawing.SHEET_SCALES[drawing.HOLDING_SHEET] == drawing.NOTES_REFERENCE_SCALE
    assert drawing.SHEET_SCALES[drawing.LINEAR_MOTION_SHEET] == drawing.LINEAR_MOTION_SCALE
    assert drawing.LINEAR_MOTION_SCALE in drawing.CLUSTER_SCALE_LADDER
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
    feed = next(c for c in drawing.CLUSTERS if c.sheet == "LEADSCREW FEED EXPLODED")
    assert spec.FEED_BLOCK in feed.stems
    # Review jig-asm r1: the feed block's carriage screws explode over it on
    # the feed sheet, the pivot block's alone on the rail-bar sheet, which
    # balloons them.
    feed_screws = tuple(spec.instance_name(spec.CARRIAGE_SCREW, i) for i in range(4))
    pivot_screws = tuple(spec.instance_name(spec.CARRIAGE_SCREW, i) for i in range(4, 8))
    assert spec.LOCKED_TO[spec.CARRIAGE_SCREW] == (
        ((spec.FEED_BLOCK, 0),) * 4 + ((spec.PIVOT_BLOCK, 0),) * 4
    )
    # The common #8 rail screw is one BOM row over two joints: eight a rail
    # into its bar, then the end brackets' screws up from Bar1's underside.
    rail_family = tuple(
        spec.instance_name(spec.RAIL_SCREW, index)
        for index in range(spec.QUANTITIES[spec.RAIL_SCREW])
    )
    assert rail_family == (*spec.RAIL_SCREW_INSTANCES, *spec.BAR_SCREW_INSTANCES)
    assert len(spec.RAIL_SCREW_INSTANCES) == len(spec.RAILS) * len(spec.guide_rail.HOLE_X)
    assert len(spec.BAR_SCREW_INSTANCES) == len(spec.leadscrew.BASE_BAR_HOLES)
    # The feed nut's four flat heads are riser-screw instances (option B,
    # 2026-11-04): shown over the nut on the feed sheet, ballooned with the
    # riser's four on the carrier sheet. The bracket screws show under their
    # brackets there too, ballooned with the rail occurrences on the rail sheet.
    assert feed.context == (
        *spec.BAR_SCREW_INSTANCES,
        spec.instance_name(spec.CARRIAGE, 0),
        *feed_screws,
        *spec.NUT_SCREW_INSTANCES,
    )
    assert spec.RAIL_SCREW not in feed.visible
    assert set(spec.BAR_SCREW_INSTANCES) <= feed.visible
    assert not set(spec.RAIL_SCREW_INSTANCES) & feed.visible
    assert spec.CARRIAGE_SCREW not in feed.visible
    assert set(feed_screws) | set(spec.NUT_SCREW_INSTANCES) <= feed.visible
    assert spec.FEED_NUT in feed.stems and spec.RISER_SCREW not in feed.stems
    carrier_sheet = next(c for c in drawing.CLUSTERS if c.sheet == "CARRIER EXPLODED")
    assert carrier_sheet.partial == ((spec.RISER_SCREW, spec.RISER_SCREW_INSTANCES),)
    assert not set(spec.RISER_SCREW_INSTANCES) & set(spec.NUT_SCREW_INSTANCES)
    assert len(spec.RISER_SCREW_INSTANCES) + len(spec.NUT_SCREW_INSTANCES) == (
        spec.QUANTITIES[spec.RISER_SCREW]
    )
    assert set(spec.RISER_SCREW_INSTANCES) <= carrier_sheet.visible
    assert not set(spec.NUT_SCREW_INSTANCES) & carrier_sheet.visible
    rails = next(c for c in drawing.CLUSTERS if c.sheet == "RAIL BARS EXPLODED")
    assert spec.CARRIAGE_SCREW in rails.stems
    assert rails.partial == (
        (spec.CARRIAGE_SCREW, pivot_screws),
        (spec.RAIL_SCREW, spec.RAIL_SCREW_INSTANCES),
    )
    assert rails.visible == frozenset(
        {*rails.stems, *pivot_screws, *spec.RAIL_SCREW_INSTANCES}
        - {spec.CARRIAGE_SCREW, spec.RAIL_SCREW}
    )
    assert not set(spec.BAR_SCREW_INSTANCES) & rails.visible
    assert rails.title == "BASE BARS, RAILS, CARRIAGES AND PIVOT BLOCK"
    pivot = next(c for c in drawing.CLUSTERS if c.sheet == drawing.PIVOT_SHEET)
    assert set(pivot.stems) == {spec.PIVOT_SCREW, spec.PIVOT_SPACER, spec.PIVOT_SHIM}
    assert set(pivot.context) == {
        spec.instance_name(spec.FEED_BLOCK, 0), spec.instance_name(spec.PIVOT_BLOCK, 0)
    }
    assert all(stem in spec.BOM_ORDER for c in drawing.CLUSTERS for stem in c.stems)



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


def test_exploded_captions_fit_their_text_region() -> None:
    for cluster in drawing.CLUSTERS:
        scale = drawing.cluster_ring_scale(
            _cluster_outline(cluster), cluster.scale, label=cluster.sheet
        )
        caption = drawing.exploded_caption(cluster, scale)
        assert max(map(len, caption.split("\n"))) <= drawing.EXPLODED_CAPTION_WIDTH
        assert _inside_sheet(_note_box(caption, drawing.EXPLODED_CAPTION_XY))


def test_sheet_text_wraps_within_its_layout_width() -> None:
    # Split only between complete labelled steps or sub-steps.
    if drawing.ASSEMBLY_STEPS_CONTINUED:
        label = drawing.ASSEMBLY_STEPS_CONTINUED.split(". ", 1)[0]
        assert drawing._STEP_LABEL.fullmatch(label)
    fit = drawing.FIT_LAYOUT
    operation = drawing.OPERATION_LAYOUT
    holding = drawing.HOLDING_LAYOUT
    for text, width in (
        (drawing.ASSEMBLED_CAPTION, drawing.CAPTION_WIDTH),
        (drawing.ALIGNMENT_NOTE, drawing.ALIGNMENT_WIDTH),
        (drawing.ASSEMBLY_STEPS, drawing.STEPS_LINE_WIDTH),
        (drawing.ASSEMBLY_STEPS_CONTINUED, drawing.STEPS_LINE_WIDTH),
        (drawing.ASSEMBLY_CHECKS, drawing.STEPS_LINE_WIDTH),
        (fit.steps, drawing.STEPS_LINE_WIDTH),
        (fit.continued, drawing.STEPS_LINE_WIDTH),
        (operation.steps, drawing.STEPS_LINE_WIDTH),
        (operation.continued, drawing.STEPS_LINE_WIDTH),
        (operation.checks, drawing.STEPS_LINE_WIDTH),
        (holding.steps, drawing.STEPS_LINE_WIDTH),
        (holding.continued, drawing.STEPS_LINE_WIDTH),
        (holding.checks, drawing.STEPS_LINE_WIDTH),
    ):
        assert max(len(line) for line in text.split("\n")) <= width
    # Each alignment station and sweep-limit row prints whole on one line.
    for line in (*spec.ALIGNMENT_NOTE_LINES[1:], *spec.SWEEP_NOTE_LINES[1:]):
        assert line in drawing.ALIGNMENT_NOTE.split("\n")
    # The general torque note opens sheet 7's sequence, its items unbroken.
    assert drawing.ASSEMBLY_STEPS.split("\n")[1].startswith("UNSPECIFIED TORQUES")
    assert " ".join(spec.GENERAL_TORQUE_NOTE.split()) in " ".join(drawing.ASSEMBLY_STEPS.split())


def test_a_blank_line_parts_each_top_level_step() -> None:
    text = drawing._wrapped(
        ("1. FIRST.", "13A. SUB A.", "13B. SUB B.", "HOLD-DOWN FIT:", "HD1. THIRD.",
         "HD2. FOURTH.", "CHECK: LOOSE."),
        width=drawing.STEPS_LINE_WIDTH, heading="HEAD", spaced=True,
    )
    assert text.split("\n") == [
        "HEAD", "1. FIRST.", "", "13A. SUB A.", "13B. SUB B.", "", "HOLD-DOWN FIT:",
        "HD1. THIRD.", "", "HD2. FOURTH.", "CHECK: LOOSE.",
    ]


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
    # Review jig-asm r1: the plan's title reads as the plan's, with clearly
    # more air below it to the elevation than above it to the plan.
    assert plan_title[1] - elevation[3] >= 3.0 * (plan[1] - plan_title[3])


def _plan_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet metres of a machine plan point, the plan centred on the extent."""
    (x0, x1), (y0, y1), _z = spec.MODEL_EXTENT
    ratio = drawing.ASSEMBLED_SCALE[0] / drawing.ASSEMBLED_SCALE[1] / 1000.0
    return (
        drawing.PLAN_CENTER[0] + (x_mm - (x0 + x1) / 2.0) * ratio,
        drawing.PLAN_CENTER[1] + (y_mm - (y0 + y1) / 2.0) * ratio,
    )


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
    # The left column's ink ends over its floor at the layout pitch and at
    # the farm-measured ink height.
    assert drawing.STEPS_XY[1] - _ink_height(layout.steps) >= drawing.STEPS_FLOOR


def _lines(text: str) -> int:
    return text.count("\n") + 1 if text else 0


def test_steps_sheet_regions_fit_apart() -> None:
    _assert_steps_sheet_fits(drawing.STEPS_LAYOUT)
    _assert_steps_sheet_fits(drawing.FIT_LAYOUT)
    _assert_steps_sheet_fits(drawing.HOLDING_LAYOUT)


@pytest.mark.parametrize(
    "sheet,layout",
    (
        (drawing.STEPS_SHEET, drawing.STEPS_LAYOUT),
        (drawing.FIT_SHEET, drawing.FIT_LAYOUT),
        (drawing.HOLDING_SHEET, drawing.HOLDING_LAYOUT),
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


def test_operation_notes_and_finished_view_fit_their_sheet() -> None:
    layout = drawing.OPERATION_LAYOUT
    _assert_steps_sheet_fits(layout)
    assert drawing.OPERATION_SHEET != drawing.STEPS_SHEET
    assert drawing.OPERATION_SHEET in drawing.SHEET_NAMES
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


@pytest.mark.parametrize("outside_room", (False, True))
def test_finished_native_view_belongs_to_operation_sheet_and_must_fit(
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
        assert sheet == drawing.OPERATION_SHEET
        assert caption.endswith("1:17")  # measured native scale, not a typed 1:15
        assert _inside_sheet(_note_box(caption, xy))
        assert not _overlap(_note_box(caption, xy), outline)
    assert sheets == [drawing.OPERATION_SHEET]
    assert placements == [(spec.ISOMETRIC_VIEW, center, drawing.ISOMETRIC_SCALE)]
    assert configurations == [(False, drawing.ASSEMBLY_VIEW_CONFIGURATION)]


def test_every_bom_row_carries_one_balloon() -> None:
    assert set(drawing.BALLOON_ANCHORS) == set(spec.BOM_ORDER)
    walked = {
        stem: anchor
        for stem, anchor in drawing.BALLOON_ANCHORS.items()
        if stem not in {spec.RAIL_SCREW, *drawing.BALLOON_APPROACH_DEG}
        and stem not in spec.MEMBER_IDENTITIES
    }
    assert all(
        anchor.instance is None and anchor.point_mm is None
        for anchor in walked.values()
    )
    # Review r5: balloon 1 lands on bar 1's operator-side long top edge, part
    # frame, mid-span between the spindle end and the far hold-down slot.
    # PR2: balloon 2 lands on the same machine edge of the turned-over Bar2,
    # its part +Y edge at z 0.
    bar = drawing.BALLOON_ANCHORS[spec.BASE_BAR_1]
    assert bar.instance == spec.instance_name(spec.BASE_BAR_1, 0) == "@Bar1:1"
    assert bar.point_mm == (200.0, base_bar.HIGH_SIDE_Y, base_bar.BAR_THICK)
    assert base_bar.NEAR_SLOT_X < bar.point_mm[0] < base_bar.FAR_SLOT_X
    assert 0.0 < bar.point_mm[0] < base_bar.BAR_LENGTH
    two = drawing.BALLOON_ANCHORS[spec.BASE_BAR_2]
    assert two.instance == spec.instance_name(spec.BASE_BAR_2, 0) == "@Bar2:1"
    assert two.point_mm == (200.0, base_bar.HIGH_SIDE_Y, 0.0)
    p1, p2 = spec.bar_point(1, bar.point_mm), spec.bar_point(2, two.point_mm)
    assert p2 == pytest.approx((-p1[0], p1[1], p1[2]), abs=1e-9)
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
    # TL-00 review (farm 20261104T210601055Z): balloon 22 lands on rail 1's
    # outboard-end screw, the last hole's, on its head's top rim (the
    # screw's part frame: head up +Y, bearing face at 0), not across the
    # T-nut, bar and rail on the spindle-end screw.
    screw = drawing.BALLOON_ANCHORS[spec.RAIL_SCREW]
    last_hole = len(spec.guide_rail.HOLE_X) - 1
    assert screw.instance == spec.instance_name(spec.RAIL_SCREW, last_hole)
    origin, _rows = spec.RAIL_SCREW_PLACEMENTS[last_hole]
    assert origin == pytest.approx(spec.compose(
        spec.RAIL_PLACEMENTS[0],
        (spec.guide_rail.HOLE_X[-1], 0.0, spec.trammel.RAIL_SCREW_SEAT_ABOVE_BASE),
        spec.UPRIGHT_ROWS,
    )[0])
    dims = spec.rail_screw.DIMS
    x, y, z = screw.point_mm
    assert (x, y, z) == (dims.head_dia / 2.0, dims.head_h, 0.0)
    assert drawing.BALLOON_RING_REACH == (
        drawing.BALLOON_MARGIN + drawing.BALLOON_RADIUS
    )


FEED_SHEET = "LEADSCREW FEED EXPLODED"


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def test_feed_sheet_balloons_land_on_clear_edges_of_their_own_parts() -> None:
    """TL-00 review (farm 20261105T054045952Z, sheet 5): the walks put
    balloon 4 on the feed block's corner over the carriage and leadscrew, 15
    in the near KP08's bore and 17 on the KP08 foot at its bracket. Each is
    frozen on an edge of its own part away from every other one."""
    away = spec.rail_direction(spec.leadscrew.RAIL)  # from the spindle
    block = spec.feed_block
    anchor = drawing.BALLOON_ANCHORS[spec.FEED_BLOCK]
    assert anchor.instance is None and len(spec.PLACEMENTS[spec.FEED_BLOCK]) == 1
    x, y, z = anchor.point_mm
    # The spindle-end face's edge with the lug-side face, bare because the
    # lug starts inboard of it, between the block's bottom and top.
    assert (x, y) == (block.BLOCK_X0, -block.BLOCK_WIDTH / 2.0)
    assert block.BLOCK_X0 < block.LUG_X0 and block.LUG_Y1 == y
    assert 0.0 < z < block.BLOCK_HEIGHT
    assert _dot(spec.PLACEMENTS[spec.FEED_BLOCK][0][1][0], away) > 0.0

    screw = spec.leadscrew_stock
    anchor = drawing.BALLOON_ANCHORS[spec.LEADSCREW]
    assert anchor.instance == spec.instance_name(spec.LEADSCREW, 0)
    x, y, z = anchor.point_mm
    # The far end chamfer's outer circle, off the handwheel flat (part +X,
    # ending short of the circle) and on the end that stands past the far
    # KP08's outer face.
    assert math.hypot(x, z) == pytest.approx(screw.MAJOR_DIA / 2.0)
    assert y == screw.LENGTH - screw.END_CHAMFER
    assert x <= 0.0
    assert screw.FLAT_STATIONS["Handwheel"] + screw.FLAT_LENGTH / 2.0 < y
    assert (
        spec.leadscrew.SCREW_NEAR_END_S + screw.LENGTH
        > max(spec.leadscrew.KP08_S) + spec.pillow_block.WIDTH / 2.0
    )

    kp08 = spec.pillow_block
    anchor = drawing.BALLOON_ANCHORS[spec.PILLOW_BLOCK]
    near = min(
        range(len(spec.PILLOW_BLOCK_PLACEMENTS)),
        key=lambda index: _dot(spec.PILLOW_BLOCK_PLACEMENTS[index][0], away),
    )
    assert anchor.instance == spec.instance_name(spec.PILLOW_BLOCK, near)
    x, y, z = anchor.point_mm
    # The boss rim on the spindle-side face (part +Y runs away from the
    # spindle), on its upper half, well off the bore.
    assert math.hypot(x, z - kp08.AXIS_HEIGHT) == pytest.approx(kp08.BOSS_RADIUS)
    assert z > kp08.AXIS_HEIGHT and x > 0.0
    assert y == -kp08.WIDTH / 2.0
    assert _dot(spec.PILLOW_BLOCK_PLACEMENTS[near][1][1], away) > 0.0


def test_re_routed_balloons_on_sheets_3_to_6_land_on_their_own_edges() -> None:
    """The same run's replay of every walked leader on sheets 3-6: 25 ran
    over the near KP08 to the screw end in its foot, 11 crossed a bracket
    screw, 3 landed on the pivot block's corner over bar 2, 19 crossed bar 2,
    7 crossed the feed block's top, 8 landed on the riser's corner on the
    carrier and 10 crossed the riser. Each is frozen on an edge of its own
    part."""
    away = spec.rail_direction(spec.leadscrew.RAIL)  # from the spindle
    near = drawing.BALLOON_ANCHORS[spec.PILLOW_BLOCK].instance
    kp08_origin, kp08_rows = spec.PLACEMENTS[spec.PILLOW_BLOCK][
        int(near.rsplit("-", 1)[1]) - 1
    ]

    def nearest(stem, point):
        return min(
            range(len(spec.PLACEMENTS[stem])),
            key=lambda index: math.dist(spec.PLACEMENTS[stem][index][0][:2], point[:2]),
        )

    # 25: the near KP08's outboard screw (KP08 part +X), on its socket head's
    # top rim.
    dims = spec.bracket_screw.DIMS
    anchor = drawing.BALLOON_ANCHORS[spec.PILLOW_BLOCK_SCREW]
    assert anchor.instance == spec.instance_name(spec.PILLOW_BLOCK_SCREW, 1)
    origin = spec.PLACEMENTS[spec.PILLOW_BLOCK_SCREW][1][0]
    assert spec.instance_name(spec.PILLOW_BLOCK, nearest(spec.PILLOW_BLOCK, origin)) == near
    assert _dot([o - k for o, k in zip(origin, kp08_origin)], kp08_rows[0]) > 0.0
    x, y, z = anchor.point_mm
    assert math.hypot(x, z) == pytest.approx(dims.head_dia / 2.0)
    assert y == dims.head_h
    # 11: the bracket under the near KP08, on its outboard end's edge with
    # its spindle-side face, mid-height.
    lead = spec.leadscrew
    anchor = drawing.BALLOON_ANCHORS[spec.END_BRACKET]
    assert anchor.instance == spec.instance_name(
        spec.END_BRACKET, nearest(spec.END_BRACKET, kp08_origin)
    )
    assert anchor.point_mm == (
        lead.BRACKET_LENGTH, -lead.BRACKET_WIDTH / 2.0, lead.BRACKET_THICK / 2.0
    )
    rows = spec.PLACEMENTS[spec.END_BRACKET][0][1]
    assert _dot(rows[1], away) > 0.0  # part -Y faces the spindle
    # 3: the pivot block's outboard vertical edge, mid-height.
    block = spec.pivot_block
    assert drawing.BALLOON_ANCHORS[spec.PIVOT_BLOCK] == drawing.BalloonAnchor(
        point_mm=(block.BLOCK_X1, block.BLOCK_WIDTH / 2.0, block.BLOCK_HEIGHT / 2.0)
    )
    # 19: bar 2's near stud (STUD_XY: bar 1 near and far, then bar 2), on
    # its upper cut-end chamfer's boundary with the barrel.
    stud = spec.hold_down_stud
    anchor = drawing.BALLOON_ANCHORS[spec.HOLD_DOWN_STUD]
    assert anchor.instance == spec.instance_name(spec.HOLD_DOWN_STUD, 2)
    assert spec.STUD_XY[2] == spec.trammel.rail_point(2, *spec.trammel.HOLD_DOWN_STUDS[0])
    x, y, z = anchor.point_mm
    assert math.hypot(x, z) == pytest.approx(stud.RADIUS)
    assert y == stud.LENGTH - stud.CUT_END_CHAMFER_MAX
    # On the barrel's near side: farm 20261105T070642635Z froze it at 210
    # degrees, where the stud's own barrel covers it in the isometric.
    placement = spec.PLACEMENTS[spec.HOLD_DOWN_STUD][2]
    rim = spec.frame_point(placement, (x, y, z))
    axis = spec.frame_point(placement, (0.0, y, 0.0))
    toward = spec.VIEW_AXES[spec.ISOMETRIC_VIEW][2]
    assert _dot([r - a for r, a in zip(rim, axis)], toward) > 0.5 * stud.RADIUS
    # 7: the top shim of the pivot block's stack, on its outer top rim.
    shim = spec.pivot_shim
    anchor = drawing.BALLOON_ANCHORS[spec.PIVOT_SHIM]
    stack = [
        index
        for index, parent in enumerate(spec.LOCKED_TO[spec.PIVOT_SHIM])
        if parent == (spec.PIVOT_BLOCK, 0)
    ]
    top = max(stack, key=lambda index: spec.PLACEMENTS[spec.PIVOT_SHIM][index][0][2])
    assert anchor.instance == spec.instance_name(spec.PIVOT_SHIM, top)
    x, y, z = anchor.point_mm
    assert math.hypot(x, y) == pytest.approx(shim.OD / 2.0)
    assert z == shim.THICKNESS
    # 8: the riser's back top long edge, along it.
    riser = spec.riser
    x, y, z = drawing.BALLOON_ANCHORS[spec.RISER].point_mm
    assert (y, z) == (riser.BLANK_WIDTH, riser.THICKNESS)
    assert 0.0 < x < riser.BLANK_LENGTH
    # 10: the lever's top front long edge, short of the grip end's corners.
    lever = spec.feed_lever
    x, y, z = drawing.BALLOON_ANCHORS[spec.FEED_LEVER].point_mm
    assert (y, z) == (lever.LEVER_THICK, -lever.LEVER_WIDTH)
    assert 0.0 < x < lever.LEVER_LENGTH - lever.CORNER_R


def _box(x0, x1, y0, y1, z0, z1):
    return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def _cylinder(axis, start, length, radius, centre=(0.0, 0.0, 0.0), sides=24):
    """Part points round a cylinder along part axis ``axis`` (0, 1 or 2)."""
    across = [k for k in range(3) if k != axis]
    points = []
    for t in (start, start + length):
        for k in range(sides):
            angle = 2.0 * math.pi * k / sides
            point = list(centre)
            point[axis] += t
            point[across[0]] += radius * math.cos(angle)
            point[across[1]] += radius * math.sin(angle)
            points.append(tuple(point))
    return points


def _frustum(y0, r0, y1, r1, sides=24):
    """Part points round a frustum along part +Y."""
    return [
        (r * math.cos(2.0 * math.pi * k / sides), y, r * math.sin(2.0 * math.pi * k / sides))
        for y, r in ((y0, r0), (y1, r1))
        for k in range(sides)
    ]


def _screw(dims):
    """A screw's head and shank (part +Y up, bearing face at 0): a flat
    head as its countersunk cone below 0."""
    shank = _cylinder(1, -dims.length, dims.length, dims.major_dia / 2.0)
    if hasattr(dims, "head_h"):
        return [_cylinder(1, 0.0, dims.head_h, dims.head_dia / 2.0), shank]
    sink = (dims.head_dia - dims.major_dia) / 2.0 / math.tan(math.radians(dims.head_angle_deg / 2.0))
    return [_frustum(-sink, dims.major_dia / 2.0, 0.0, dims.head_dia / 2.0), shank]


def _part_solids():
    """Each family's part-frame solids: the spec's conservative boxes, finer
    where a box would cover what the sheets show: the feed block and its lug,
    the KP08's foot, pedestal and boss, the turned leadscrew, nut and
    handwheel (at its wheel's diameter over its whole length), the carriage
    body and every screw's head and shank."""
    block, kp08, lead = spec.feed_block, spec.pillow_block, spec.leadscrew
    screw, nut, carriage = spec.leadscrew_stock, spec.feed_nut, spec.carriage
    solids = {
        stem: [_box(*box[0], *box[1], *box[2])]
        for stem, box in spec._component_local_boxes().items()
    }
    solids.update({
        spec.FEED_BLOCK: [
            _box(block.BLOCK_X0, block.BLOCK_X1, -block.BLOCK_WIDTH / 2.0,
                 block.BLOCK_WIDTH / 2.0, 0.0, block.BLOCK_HEIGHT),
            _box(block.LUG_X0, block.LUG_X1, block.LUG_Y0, block.LUG_Y1, 0.0,
                 block.BLOCK_HEIGHT),
        ],
        spec.LEADSCREW: [_cylinder(1, 0.0, screw.LENGTH, screw.MAJOR_DIA / 2.0)],
        spec.FEED_NUT: [
            _cylinder(1, 0.0, nut.FLANGE_THICK, nut.FLANGE_DIA / 2.0),
            _cylinder(1, 0.0, nut.BODY_LENGTH, nut.BODY_DIA / 2.0),
        ],
        spec.PILLOW_BLOCK: [
            _box(-kp08.LENGTH / 2.0, kp08.LENGTH / 2.0, -kp08.WIDTH / 2.0,
                 kp08.WIDTH / 2.0, 0.0, kp08.FOOT_THICK),
            _box(-kp08.BOSS_RADIUS, kp08.BOSS_RADIUS, -kp08.WIDTH / 2.0,
                 kp08.WIDTH / 2.0, 0.0, kp08.AXIS_HEIGHT),
            _cylinder(1, -kp08.WIDTH / 2.0, kp08.WIDTH, kp08.BOSS_RADIUS,
                      (0.0, 0.0, kp08.AXIS_HEIGHT)),
        ],
        spec.HANDWHEEL: [
            _cylinder(1, 0.0, lead.HANDWHEEL_LENGTH, lead.HANDWHEEL_WHEEL_DIA / 2.0)
        ],
        spec.CARRIAGE: [
            _box(-carriage.LENGTH / 2.0, carriage.LENGTH / 2.0, -carriage.WIDTH / 2.0,
                 carriage.WIDTH / 2.0, carriage.UNDERSIDE_Z, carriage.MOUNTING_FACE_Z),
        ],
    })
    for stem, fastener in (
        (spec.RAIL_SCREW, spec.rail_screw), (spec.CARRIAGE_SCREW, spec.carriage_screw),
        (spec.PILLOW_BLOCK_SCREW, spec.bracket_screw), (spec.RISER_SCREW, spec.riser_screw),
        (spec.CLAMP_SCREW, spec.clamp_screw), (spec.LEVER_SCREW, spec.lever_screw),
    ):
        solids[stem] = _screw(fastener.DIMS)
    return solids


def _sheet_occurrences(cluster):
    """A cluster sheet's occurrences, instance -> (family, index): its
    families' shown instances, and its context."""
    shown = dict(cluster.partial)
    return {
        name: (stem, index)
        for stem in spec.BOM_ORDER
        for index in range(len(spec.PLACEMENTS[stem]))
        for name in (spec.instance_name(stem, index),)
        if (stem in cluster.stems and name in shown.get(stem, (name,)))
        or name in cluster.context
    }


def _exploded(name, stem, index, point):
    """Part-frame ``point`` (mm) of occurrence ``name``, exploded, machine mm."""
    machine = spec.frame_point(spec.PLACEMENTS[stem][index], point)
    return [machine[k] + spec.explode_shift(name, axis) for k, axis in enumerate("xyz")]


@functools.cache
def _sheet_bodies(sheet):
    """Every convex solid the sheet shows, exploded: (instance, face
    normals, offsets, vertices), inside where ``normals @ p + offsets <= 0``."""
    from scipy.spatial import ConvexHull

    cluster = next(c for c in drawing.CLUSTERS if c.sheet == sheet)
    solids = _part_solids()
    bodies = []
    for name, (stem, index) in _sheet_occurrences(cluster).items():
        for solid in solids[stem]:
            hull = ConvexHull([_exploded(name, stem, index, p) for p in solid])
            bodies.append(
                (name, hull.equations[:, :3], hull.equations[:, 3], hull.points[hull.vertices])
            )
    return tuple(bodies)


def _iso_axes():
    return tuple(np.array(axis, dtype=float) for axis in spec.VIEW_AXES[spec.ISOMETRIC_VIEW])


def _frontmost(sheet, ratio, points):
    """The instance drawn frontmost at each sheet point (mm about the model
    origin at ``ratio``), or None: each point's view ray against every body,
    the hit nearest the viewer winning, as ViewRayCaster ranks covered_by."""
    right, up, toward = _iso_axes()
    points = np.asarray(points, dtype=float).reshape(-1, 2)
    base = np.outer(points[:, 0] / ratio, right) + np.outer(points[:, 1] / ratio, up)
    front = np.full(len(points), -np.inf)
    drawn = [None] * len(points)
    for name, normals, offsets, _vertices in _sheet_bodies(sheet):
        rate = normals @ toward
        room = -(offsets[None, :] + base @ normals.T)
        with np.errstate(divide="ignore", invalid="ignore"):
            bound = room / rate[None, :]
        upper = np.where(rate[None, :] > 1e-12, bound, np.inf).min(axis=1)
        lower = np.where(rate[None, :] < -1e-12, bound, -np.inf).max(axis=1)
        level = np.abs(rate) <= 1e-12
        hit = (lower <= upper) & (room[:, level] >= 0.0).all(axis=1)
        for k in np.flatnonzero(hit & (upper > front)):
            front[k], drawn[k] = upper[k], name
    return drawn


def _replay_ratio(cluster):
    """The smaller of the placed scale and the offline ring fit's, so the
    replayed clearances are the smaller."""
    fitted = drawing.cluster_ring_scale(_cluster_outline(cluster), cluster.scale, label=cluster.sheet)
    return min(cluster.scale[0] / cluster.scale[1], fitted[0] / fitted[1])


def _approach_replay(stem):
    """Replay the declared balloon on its sheet: (the instance drawn at its
    landing, the other instances drawn frontmost along its approach ray until
    the ray is past every body, those drawn within LANDING_CLEARANCE_M of the
    landing)."""
    cluster = next(c for c in drawing.CLUSTERS if stem in c.stems)
    anchor = drawing.BALLOON_ANCHORS[stem]
    own = anchor.instance or spec.instance_name(stem, 0)
    ratio = _replay_ratio(cluster)
    right, up, _toward = _iso_axes()
    occurrence = _sheet_occurrences(cluster)[own]
    moved = np.array(_exploded(own, *occurrence, anchor.point_mm))
    landing = np.array([moved @ right, moved @ up]) * ratio
    vertices = np.vstack([body[3] for body in _sheet_bodies(cluster.sheet)])
    reach = np.hypot(vertices @ right * ratio - landing[0], vertices @ up * ratio - landing[1]).max()
    angle = math.radians(drawing.BALLOON_APPROACH_DEG[stem])
    steps = np.arange(0.05, reach, 0.1)
    ray = landing + np.outer(steps, (math.cos(angle), math.sin(angle)))
    turns = np.linspace(0.0, 2.0 * math.pi, 48, endpoint=False)
    radii = np.arange(0.1, drawing.LANDING_CLEARANCE_M * 1000.0 + 1e-9, 0.1)
    disk = landing + np.vstack(
        [np.column_stack((r * np.cos(turns), r * np.sin(turns))) for r in radii]
    )

    def others(points):
        return set(_frontmost(cluster.sheet, ratio, points)) - {own, None}

    return _frontmost(cluster.sheet, ratio, [landing])[0], others(ray), others(disk)


def test_declared_approaches_are_the_re_routed_balloons() -> None:
    assert set(drawing.BALLOON_APPROACH_DEG) == {
        spec.PIVOT_BLOCK, spec.HOLD_DOWN_STUD, spec.PIVOT_SHIM,
        spec.FEED_BLOCK, spec.LEADSCREW, spec.PILLOW_BLOCK,
        spec.PILLOW_BLOCK_SCREW, spec.END_BRACKET,
        spec.RISER, spec.FEED_LEVER,
    }
    for stem in drawing.BALLOON_APPROACH_DEG:
        assert sum(stem in cluster.stems for cluster in drawing.CLUSTERS) == 1
        assert drawing.BALLOON_ANCHORS[stem].point_mm is not None


@pytest.mark.parametrize("stem", sorted(drawing.BALLOON_APPROACH_DEG))
def test_declared_approaches_clear_every_other_occurrence(stem) -> None:
    """Ray-cast on the spec's exploded poses and part envelopes through the
    isometric: the landing is its own part's ink (or its silhouette), the
    declared leader crosses no other instance on its sheet, and none is drawn
    within LANDING_CLEARANCE_M of the landing (the nearest at the farm's
    scales: 4 riser screw 5.2 mm, 15 KP08 screw 4.2, 17 bracket 2.5, 11 KP08
    2.7, 25 none within 6; 3 none, 19 bar 2 2.2; 7 the next shim 2.9; 8 riser
    screw 5.3, 10 none)."""
    anchor = drawing.BALLOON_ANCHORS[stem]
    drawn, crossed, beside = _approach_replay(stem)
    assert drawn in {anchor.instance or spec.instance_name(stem, 0), None}
    assert not crossed
    assert not beside


@pytest.mark.parametrize(
    ("stem", "degrees", "crossed"),
    (
        # Farm 20261105T054045952Z: balloon 4 hung under the block, its leader
        # up through the carriage and across the leadscrew.
        (spec.FEED_BLOCK, -115.0, {spec.instance_name(spec.CARRIAGE, 0), spec.instance_name(spec.LEADSCREW, 0)}),
        # The ring's own slot for the far end, beside balloon 18's.
        (spec.LEADSCREW, 165.0, {spec.instance_name(spec.HANDWHEEL, 0)}),
    ),
)
def test_the_replay_refuses_a_route_across_another_part(
    monkeypatch, stem, degrees, crossed,
) -> None:
    monkeypatch.setitem(drawing.BALLOON_APPROACH_DEG, stem, degrees)
    assert _approach_replay(stem)[1] == crossed


def test_the_replay_refuses_a_landing_beside_another_part(monkeypatch) -> None:
    # Farm 20261105T054045952Z, sheet 3: balloon 3 on the pivot block's
    # bottom corner, drawn against bar 2 behind it and the carriage under it.
    block = spec.pivot_block
    monkeypatch.setitem(
        drawing.BALLOON_ANCHORS,
        spec.PIVOT_BLOCK,
        drawing.BalloonAnchor(point_mm=(block.BLOCK_X1, -block.BLOCK_WIDTH / 2.0, 0.0)),
    )
    assert _approach_replay(spec.PIVOT_BLOCK)[2] == {
        spec.instance_name(spec.BASE_BAR_2, 0), spec.instance_name(spec.CARRIAGE, 1),
    }


def _ring_outline():
    return (0.10, 0.10, 0.30, 0.20)


def test_an_approach_meets_the_ring_on_its_ray() -> None:
    outline, margin = _ring_outline(), drawing.BALLOON_MARGIN
    attach = (0.25, 0.12)
    for degrees in (0.0, 10.0, 225.0, 270.0):
        x, y = drawing.approach_ring_centre(outline, attach, degrees)
        rx, ry = 0.1 + margin, 0.05 + margin
        assert ((x - 0.2) / rx) ** 2 + ((y - 0.15) / ry) ** 2 == pytest.approx(1.0)
        assert math.degrees(math.atan2(y - attach[1], x - attach[0])) % 360.0 == pytest.approx(degrees)
    with pytest.raises(ValueError, match="not inside"):
        drawing.approach_ring_centre(outline, (0.40, 0.15), 0.0)


def test_declared_balloons_take_their_approach_and_keep_it() -> None:
    outline = _ring_outline()
    names = ["a", "b", "c"]
    attachments = [(0.25, 0.15), (0.15, 0.12), (0.20, 0.12)]
    centres = [(0.33, 0.15), (0.07, 0.17), (0.20, 0.05)]
    placed, slots = drawing.approached_ring_slots(
        centres, attachments, {0: 45.0}, outline=outline, radius=0.005, names=names,
    )
    assert slots == [0, 1, 2]
    assert placed[0] == drawing.approach_ring_centre(outline, attachments[0], 45.0)
    assert placed[1:] == centres[1:]
    # Up and right from a's landing runs onto c's circle...
    centres[2] = drawing.approach_ring_centre(outline, attachments[0], 50.0)
    with pytest.raises(RuntimeError, match="a's approach puts it"):
        drawing.approached_ring_slots(
            centres, attachments, {0: 45.0}, outline=outline, radius=0.005, names=names,
        )
    # ...and leftward from a's landing crosses b's leader.
    centres[2] = (0.20, 0.05)
    with pytest.raises(RuntimeError, match=r"approaches of \['a'\] cross"):
        drawing.approached_ring_slots(
            centres, attachments, {0: 180.0}, outline=outline, radius=0.005, names=names,
        )


def test_leader_probes_cover_the_route_and_ring_its_landing() -> None:
    leader = [(0.0, 0.0), (0.01, 0.0), (0.01, 0.003)]
    points = drawing.leader_probe_points(leader)
    assert points[0] == leader[0] and points[-1] == pytest.approx(leader[-1])
    assert max(math.dist(a, b) for a, b in zip(points, points[1:])) <= drawing.LEADER_PROBE_STEP_M + 1e-12
    ring = drawing.landing_probe_points(leader[-1])
    assert len(ring) == drawing.LANDING_PROBES
    assert all(math.dist(p, leader[-1]) == pytest.approx(drawing.LANDING_CLEARANCE_M) for p in ring)
    assert max(math.dist(a, b) for a, b in zip(ring, ring[1:])) < 0.95e-3


def test_leader_clearance_names_crossings_and_junctions() -> None:
    route, ring = [(0.0, 0.0), (0.001, 0.0)], [(0.002, 0.0), (0.003, 0.0)]
    assert not drawing.leader_clearance_failures(
        "4 balloon", "Block-1", route, [None, "block-1"], ring, ["BLOCK-1", None]
    )
    failures = drawing.leader_clearance_failures(
        "4 balloon", "block-1", route, ["carriage-1", "block-1"], ring, [None, "screw-2"]
    )
    assert failures == [
        "4 balloon crosses carriage-1 at (0.0, 0.0) mm",
        "4 balloon lands within 1.0 mm of screw-2 at (3.0, 0.0) mm",
    ]
    with pytest.raises(ValueError):
        drawing.leader_clearance_failures("4", "block-1", route, [None], ring, [None, None])


def test_a_landing_beside_its_own_items_stacked_occurrences_clears() -> None:
    # Farm 20261105T163942818Z, balloon 7: the top pivot shim of a stack of
    # five lands within 1 mm of the shims under it. Those are the balloon's
    # own item; another part there, or any crossing, still fails.
    shims = drawing._same_item_occurrences(spec.PIVOT_SHIM)
    assert len(shims) == spec.QUANTITIES[spec.PIVOT_SHIM]
    own, below = shims[-1], shims[5]
    route, ring = [(0.0, 0.0), (0.001, 0.0)], [(0.002, 0.0), (0.003, 0.0)]
    assert not drawing.leader_clearance_failures(
        "7 balloon", own, route, [own, None], ring, [below, shims[7]], same_item=shims
    )
    assert drawing.leader_clearance_failures(
        "7 balloon", own, route, [below, None], ring, [None, None], same_item=shims
    ) == [f"7 balloon crosses {below} at (0.0, 0.0) mm"]
    block = spec.instance_name(spec.PIVOT_BLOCK, 0)
    assert drawing.leader_clearance_failures(
        "7 balloon", own, route, [None, None], ring, [below, block], same_item=shims
    ) == [f"7 balloon lands within 1.0 mm of {block} at (3.0, 0.0) mm"]


@pytest.mark.parametrize("scale_in_rows", (False, True))
def test_sheet_points_invert_the_view_transform(scale_in_rows) -> None:
    from _drawing_ray_pick import _to_model

    right, up, toward = spec.VIEW_AXES[spec.ISOMETRIC_VIEW]
    rows = [c for axis in range(3) for c in (right[axis], up[axis], toward[axis])]
    scale = 1.0 / 3.0
    if scale_in_rows:
        rows, scale = [c * 1.0 / 3.0 for c in rows], 1.0
    values = (*rows, 0.2, 0.15, 0.01, scale)
    model = (0.1, -0.2, 0.05)
    sheet = _to_model(values, model)
    point = drawing.sheet_point_in_model(values, toward, sheet[:2], depth=2.0)
    drawn = _to_model(values, point)
    assert drawn[:2] == pytest.approx(sheet[:2])
    assert drawn[2] == pytest.approx(0.01 - 2.0 / 3.0)
    assert _dot([p - m for p, m in zip(point, model)], toward) < -1.5


class _ClearanceCaster:
    """Draws the probes' sheet points through ``outlines`` (instance -> (box,
    depth toward the viewer)), the frontmost first, as ViewRayCaster lists
    what covers a point behind every body."""

    outlines: dict = {}

    def __init__(self, adapter, view, leaves, pose, *, label):
        self.normal = (0.0, 0.0, 1.0)

    def probe(self, candidates, *, label):
        picks = []
        for _own, (x, y, _z) in candidates:
            hits = sorted(
                (-depth, name)
                for name, ((x0, y0, x1, y1), depth) in self.outlines.items()
                if x0 <= x <= x1 and y0 <= y <= y1
            )
            picks.append(SimpleNamespace(covered_by=tuple(name for _d, name in hits)))
        return picks


@pytest.mark.parametrize(
    ("outlines", "message"),
    (
        # The block, the carriage behind it under the leader: drawn over.
        ({"block-1": ((0.0, 0.0, 0.010, 0.010), 2.0), "carriage-1": ((0.002, 0.003, 0.009, 0.007), 1.0)}, None),
        # The carriage in front across the route.
        ({"block-1": ((0.0, 0.0, 0.010, 0.010), 1.0), "carriage-1": ((0.020, 0.003, 0.025, 0.007), 1.0)}, "crosses carriage-1"),
        # A screw in front of the block 0.5 mm under the landing.
        ({"block-1": ((0.0, 0.0, 0.010, 0.010), 1.0), "screw-2": ((0.003, 0.0035, 0.005, 0.0045), 3.0)}, "lands within 1.0 mm of screw-2"),
    ),
)
def test_declared_leaders_are_probed_from_balloon_to_landing(
    monkeypatch, outlines, message,
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_view_component_leaves", lambda *a, **kw: ())
    monkeypatch.setattr(drawing, "_view_explode_offsets", lambda *a, **kw: {})
    monkeypatch.setattr(_ClearanceCaster, "outlines", outlines)
    monkeypatch.setattr(drawing, "ViewRayCaster", _ClearanceCaster)
    identity = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    monkeypatch.setattr(
        drawing, "_com_invoke",
        lambda target, _interface, member: identity if member == "ArrayData" else "transform",
    )
    # Leader from its balloon at (40, 5) mm over the block to (4, 5).
    annotation = SimpleNamespace(GetLeaderPointsAtIndex=lambda _i: (0.040, 0.005, 0.0, 0.004, 0.005, 0.0))
    note = SimpleNamespace(GetAnnotation=lambda: annotation)
    landing = drawing.BalloonLanding(spec.FEED_BLOCK, "block-1", note, (0.004, 0.005), "4")
    if message is None:
        drawing._assert_declared_leaders_clear(object(), object(), [landing], label="feed")
    else:
        with pytest.raises(RuntimeError, match=message):
            drawing._assert_declared_leaders_clear(object(), object(), [landing], label="feed")


def test_feed_balloons_prove_their_declared_leaders_with_the_explode_active(
    monkeypatch,
) -> None:
    from contextlib import contextmanager

    cluster = next(c for c in drawing.CLUSTERS if c.sheet == FEED_SHEET)
    events = []

    @contextmanager
    def active(view, *, label):
        events.append("activate")
        yield
        events.append("restore")

    monkeypatch.setattr(drawing, "_activate_sheet", lambda *a: None)
    monkeypatch.setattr(drawing, "_link_view_to_bom", lambda *a, **kw: None)
    monkeypatch.setattr(drawing, "_source_configuration_active", active)
    monkeypatch.setattr(drawing, "_ring_balloons", lambda *a, **kw: events.append("ring"))
    monkeypatch.setattr(
        drawing, "_relax_cluster_slide",
        lambda a, v, landings, **kw: events.append("relax") or landings,
    )
    monkeypatch.setattr(
        drawing, "add_component_bom_balloons",
        lambda a, v, *, items, **kw: [SimpleNamespace(stem=stem) for stem, _item in items],
    )
    monkeypatch.setattr(
        drawing, "_assert_declared_leaders_clear",
        lambda a, v, declared, **kw: events.append(("clear", {d.stem for d in declared})),
    )
    drawing._balloon_cluster(object(), object(), cluster, tuple(spec.ITEM_NUMBERS.items()), "BOM")
    assert events == [
        "activate", "restore", "ring", "relax",
        "activate",
        ("clear", {stem for stem in drawing.BALLOON_APPROACH_DEG if stem in cluster.stems}),
        "restore",
    ]


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
    # TL-20's two members (PR2) print its one Number, no second part number.
    assert drawing.BOM_PART_NUMBERS[spec.BASE_BAR_1] == "MHA-CH-06-TL-20"
    assert drawing.BOM_PART_NUMBERS[spec.BASE_BAR_2] == "MHA-CH-06-TL-20"
    # Every member of a kit prints its kit's one Number.
    assert {
        family: drawing.BOM_PART_NUMBERS[family] for family in spec.KIT_IDENTITIES
    } == {
        spec.RAIL: "MHA-CH-06-TL-VN-83",
        spec.CARRIAGE: "MHA-CH-06-TL-VN-83",
        spec.LEADSCREW: "MHA-CH-06-TL-VN-84",
        spec.FEED_NUT: "MHA-CH-06-TL-VN-84",
        spec.HOLD_DOWN_STUD: "MHA-SH-VN-57",
        spec.T_NUT: "MHA-SH-VN-57",
        spec.FLANGE_NUT: "MHA-SH-VN-57",
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
            drawing.STEPS_LAYOUT, drawing.FIT_LAYOUT, drawing.OPERATION_LAYOUT,
            drawing.HOLDING_LAYOUT,
        )
        for text in (layout.steps, layout.continued)
    )
    for stem in screws:
        assert f"(ITEM {drawing.BOM_ITEM_NUMBERS[stem]})" in steps
    # A citation never breaks across a line.
    for line in steps.split("\n"):
        assert not line.rstrip().endswith(("ITEM", "(ITEM"))


def test_instruction_split_drops_or_duplicates_no_source_step() -> None:
    layouts = (
        drawing.STEPS_LAYOUT, drawing.FIT_LAYOUT,
        drawing.OPERATION_LAYOUT, drawing.HOLDING_LAYOUT,
    )
    def content(layout):
        return " ".join(" ".join((layout.steps, layout.continued, layout.checks)).split())

    all_text = " ".join(content(layout) for layout in layouts)
    source_steps = (
        spec.GENERAL_TORQUE_NOTE, *spec.ASSEMBLY_STEPS, *spec.ASSEMBLY_CHECKS,
        *spec.PIVOT_FIT_STEPS, *spec.FEED_FIT_STEPS,
        *spec.OPERATION_STEPS, *spec.HOLD_DOWN_STEPS, *spec.CAPTURE_CHECKS,
    )
    for step in source_steps:
        assert all_text.count(" ".join(step.split())) == 1, step
    operation, holding = content(drawing.OPERATION_LAYOUT), content(drawing.HOLDING_LAYOUT)
    for step in (*spec.OPERATION_STEPS[:2], *spec.HOLD_DOWN_STEPS, *spec.CAPTURE_CHECKS[:3], *spec.CAPTURE_CHECKS[4:]):
        assert " ".join(step.split()) in operation
    for step in (*spec.OPERATION_STEPS[2:], *spec.CAPTURE_CHECKS[3:4]):
        assert " ".join(step.split()) in holding


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
    for family in spec.MEMBER_IDENTITIES:
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
    seat._place_bom_note.return_value = lambda: None
    seat._place_notes_reference_views.return_value = {
        name: drawing.NOTES_REFERENCE_SCALE for name in drawing.NOTES_REFERENCE_REGIONS
    }
    seat._place_cluster_view.side_effect = lambda _adapter, cluster: (
        object(),
        drawing.SHEET_SCALES[cluster.sheet],
    )
    seat._balloon_cluster.side_effect = (
        lambda _adapter, _view, cluster, _items, _bom_name: [
            SimpleNamespace(stem=stem)
            for stem in cluster.stems
        ]
    )
    linear_view, linear_landing = object(), SimpleNamespace(stem=spec.RAIL)
    seat._place_linear_motion_view.return_value = (linear_view, (1.0, 3.0))
    seat._balloon_linear_motion.return_value = [linear_landing]
    monkeypatch.setattr(drawing, "_bom_feature_name", lambda _table: "offline BOM")
    scales, checks = drawing._place_package(object())
    assert tuple(scales) == drawing.SHEET_NAMES
    assert scales[drawing.LINEAR_MOTION_SHEET] == (1.0, 3.0)
    seat._place_linear_motion_view.assert_called_once()
    assert seat._balloon_linear_motion.call_args.args[1] is linear_view
    expected_configurations = [reference.ReferencedConfiguration] * len(spec.BOM_ORDER)
    assert table.association_configurations == expected_configurations
    table.association_configurations.clear()
    for check in checks:
        check()
    assert table.association_configurations == expected_configurations
    assert linear_landing in seat.assert_balloon_landings.call_args.args[1]
    seat._assert_linear_motion_visibility.assert_called_once()
    assert seat._assert_linear_motion_visibility.call_args.args[1] is linear_view

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
    kit_rows = {
        family: table.cells[int(spec.ITEM_NUMBERS[family])][1::2]
        for family in spec.KIT_IDENTITIES
    }
    assert kit_rows == {
        spec.RAIL: ["MHA-CH-06-TL-VN-83", "2"],
        spec.CARRIAGE: ["MHA-CH-06-TL-VN-83", "2"],
        spec.LEADSCREW: ["MHA-CH-06-TL-VN-84", "1"],
        spec.FEED_NUT: ["MHA-CH-06-TL-VN-84", "1"],
        spec.HOLD_DOWN_STUD: ["MHA-SH-VN-57", "4"],
        spec.T_NUT: ["MHA-SH-VN-57", "4"],
        spec.FLANGE_NUT: ["MHA-SH-VN-57", "4"],
    }
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
    # Each base-bar configuration is its own row, one off (Bar1, Bar2); the
    # regression is both bars counted on Bar1's row.
    row = int(spec.ITEM_NUMBERS[spec.BASE_BAR_1])
    assert table.cells[row][3] == str(spec.QUANTITIES[spec.BASE_BAR_1]) == "1"
    table.cells[row][3] = str(
        spec.QUANTITIES[spec.BASE_BAR_1] + spec.QUANTITIES[spec.BASE_BAR_2]
    )
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
    # Reversed native rows prove the citations are not copied from spec items.
    order = tuple(reversed(spec.BOM_ORDER))
    table = _Table(order)
    text = drawing._kit_bom_note_text(
        table, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
    )
    lines = text.splitlines()
    assert lines[0] == "PURCHASED KITS, MEMBER CONFIGURATIONS (INSTALLED QTY.):"
    assert lines[-1] == "BOM QTY. COUNTS MEMBERS, NOT KITS."
    assert max(map(len, lines)) <= drawing.KIT_KEY_LINE_WIDTH
    kits: dict[str, list[tuple[str, str]]] = {}
    for family, (physical, member) in spec.KIT_IDENTITIES.items():
        kits.setdefault(physical, []).append((family, member))
    assert list(kits) == [spec.RAIL_KIT, spec.LEADSCREW_KIT, spec.CLAMPING_KIT]
    # One block per kit: its Number, supplier and SKU, then its members.
    starts = []
    for physical in kits:
        registry = _config.parts(physical)
        [sku] = registry["supplier_skus"]
        starts.append(lines.index(
            f"{registry['number']}, {str(registry['supplier']).upper()} SKU {sku}:"
        ))
    assert starts[0] == 1 and starts == sorted(starts)
    for (physical, members), start, end in zip(kits.items(), starts, [*starts[1:], len(lines) - 1]):
        quantities = _config.parts(physical)["configuration_quantities"]
        cited = "; ".join(lines[start + 1:end]).split("; ")
        assert sorted(cited) == sorted(
            f"ITEM {order.index(family) + 1}: {member} ({quantities[member]})"
            for family, member in members
        )
    # The two Amazon kits and the clamping kit each print their own SKU.
    assert "B0C4DJNL33" in text and "B085DDHJTW" in text and "52PCCK-9/16-14mm" in text


class _KitBomNote:
    """Native-style note geometry with a nonzero insertion-to-extent offset and
    the farm-measured ink height of its line count; ``drift`` moves its ink
    once it has been seated."""

    def __init__(self, text, xy, *, width, move, drift=(0.0, 0.0)):
        self.text = text
        self.position = (*xy, 0.0)
        self.width = width
        self.move = move
        self.drift = (0.0, 0.0)
        self.seat_drift = drift
        self.OwnerType = 1
        self.Visible = 1
        self.leaders = 0

    def GetAnnotation(self):
        return self

    def GetPosition(self):
        return self.position

    def GetExtent(self):
        x, y, _z = self.position
        x, y = x + self.drift[0], y + self.drift[1]
        bottom = y + 0.002 - drawing.note_ink_height(self.text)
        return x + 0.005, bottom, 0.0, x + 0.005 + self.width, y + 0.002, 0.0

    def GetText(self):
        return self.text.replace("\n", "\r\n")

    def GetLeaderCount(self):
        return self.leaders

    def SetPosition2(self, *position):
        if self.move == "refused":
            return False
        if self.move != "ignored":
            self.position = position
            self.drift = self.seat_drift
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
        drift=(0.0, 0.0),
        active=None,
    )
    state.reference = SimpleNamespace(
        ReferencedConfiguration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        GetOutline=lambda: state.outline,
    )

    def add_native_note(_adapter, text, x, y):
        assert state.active == drawing.BOM_SHEET
        note = _KitBomNote(
            text, (x, y), width=state.width, move=state.move, drift=state.drift
        )
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
    # Three kits: a heading, three blocks of two lines and the closing line.
    assert len(note.text.splitlines()) == 9
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
        assert row[1] == drawing.BOM_PART_NUMBERS[family]
        assert row[3] == str(spec.QUANTITIES[family])


@pytest.mark.parametrize("fault", ("oversized", "ignored", "refused"))
def test_kit_bom_key_refuses_a_native_note_that_does_not_fit(kit_bom_note_state, fault):
    state = kit_bom_note_state
    if fault == "oversized":
        state.width = 0.250
    else:
        state.move = fault
    with pytest.raises(RuntimeError):
        drawing._place_kit_bom_note(_ADAPTER, state.table, state.reference)


def test_bom_note_sits_under_the_bom_left_of_the_title(kit_bom_note_state):
    state = kit_bom_note_state
    settled = drawing._place_bom_note(_ADAPTER, state.table)
    [note] = state.notes
    assert note.text == spec.BOM_NOTE
    extent = drawing._kit_bom_note_extent(note)
    bom = drawing._bom_bounds(state.table)
    # Seated by its ink, the allowance inside the table's left edge and
    # inside REGION_GAP under its last row.
    assert extent[0] - bom[0] == pytest.approx(drawing.NOTE_SEAT_ALLOWANCE)
    assert bom[1] - extent[3] == pytest.approx(
        drawing.REGION_GAP + drawing.NOTE_SEAT_ALLOWANCE
    )
    assert extent[2] < drawing.TITLE_BLOCK_KEEP_OUT[0] and _inside_sheet(extent)
    settled()
    state.notes[0].text = "ITEM 7: SOMETHING ELSE"
    with pytest.raises(RuntimeError, match="text changed"):
        settled()


def test_bom_note_seat_absorbs_the_farm_measured_ink_drift(kit_bom_note_state):
    # Farm 20261104T203420333Z: seated flush, the note's ink then read
    # 0.19 mm over its field's top and 0.05 mm right of where it was seated,
    # and the settle check refused it.
    state = kit_bom_note_state
    farm = (0.01804789062499998 - 0.018, 0.079484140625 - 0.07929453150272764)
    state.drift = farm
    settled = drawing._place_bom_note(_ADAPTER, state.table)
    settled()
    # Drift past the allowance, either way, is still refused.
    for drift in (
        (0.0, drawing.NOTE_SEAT_ALLOWANCE + 1e-5),
        (-(drawing.NOTE_SEAT_ALLOWANCE + 1e-5), 0.0),
    ):
        state.drift = drift
        with pytest.raises(RuntimeError, match="leaves its clear field"):
            drawing._place_bom_note(_ADAPTER, state.table)


def test_bom_note_ink_model_reproduces_the_farm_and_fits_its_native_field(
    kit_bom_note_state, monkeypatch,
):
    def block(lines: int) -> str:
        return "\n".join("X" * lines for _ in range(lines))

    # The two farm measurements the model is fitted to, at their 0.01 mm.
    assert drawing.note_ink_height(block(8)) == pytest.approx(0.0365596, abs=1e-5)
    assert drawing.note_ink_height(block(47)) == pytest.approx(0.21233, abs=1e-5)
    # Farm 20261104T203420333Z's field under the native BOM, whose rows grew
    # to 5.82 mm on average: the note, seated the allowance under its top,
    # inks above its floor.
    field = (0.018, 0.0187, 0.207, 0.07929453150272764)
    native_bom = (field[0], field[3] + drawing.REGION_GAP, 0.208, drawing.BOM_ANCHOR[1])
    assert drawing.bom_note_region(native_bom) == pytest.approx(field)
    top = field[3] - drawing.NOTE_SEAT_ALLOWANCE
    assert top - drawing.note_ink_height(spec.BOM_NOTE) >= field[1]
    # A note too tall for its field is refused before it is placed.
    state = kit_bom_note_state
    region = drawing.bom_note_region(drawing._bom_bounds(state.table))
    lines = 1
    while drawing.note_ink_height(block(lines)) + drawing.NOTE_SEAT_ALLOWANCE <= (
        region[3] - region[1]
    ):
        lines += 1
    monkeypatch.setattr(drawing.spec, "BOM_NOTE", "\n".join(["ITEM 7"] * lines))
    with pytest.raises(RuntimeError, match="inks about"):
        drawing._place_bom_note(_ADAPTER, state.table)
    assert state.notes == []
    monkeypatch.setattr(drawing.spec, "BOM_NOTE", "\n".join(["ITEM 7"] * (lines - 1)))
    drawing._place_bom_note(_ADAPTER, state.table)
    assert len(state.notes) == 1


@pytest.mark.parametrize("fault", ("oversized", "ignored", "refused"))
def test_bom_note_refuses_a_note_that_does_not_fit(kit_bom_note_state, fault):
    state = kit_bom_note_state
    if fault == "oversized":
        state.width = 0.250
    else:
        state.move = fault
    with pytest.raises(RuntimeError):
        drawing._place_bom_note(_ADAPTER, state.table)


def test_bom_note_buys_the_worst_case_at_both_supports() -> None:
    # Owner ruling 2026-10-27: the nominal pack plus the worst-case pack a
    # support, at both supports, from the fitting stock alone.
    assert set(spec.PIVOT_SHIM_BUY) == set(spec.pivot_shim.FIT_SKUS.values())
    assert all(count % 2 == 0 for _thickness, count in spec.PIVOT_SHIM_BUY.values())
    assert spec.PIVOT_SHIM_BUY[spec.pivot_shim.SKU][1] >= spec.pivot_shim.QUANTITY
    note = spec.BOM_NOTE
    assert note.startswith(f"ITEM {spec.ITEM_NUMBERS[spec.PIVOT_SHIM]}:")
    for sku, (_thickness, count) in spec.PIVOT_SHIM_BUY.items():
        assert f"{sku} " in note and f"X{count}" in note
    assert "SELECTED PER P1" in note
    item = f"(ITEM {spec.ITEM_NUMBERS[spec.PIVOT_SHIM]})"
    assert item in spec.PIVOT_FIT_STEPS[0] and "BUY LIST UNDER THE BOM" in spec.PIVOT_FIT_STEPS[0]
    # One purchase list, not a duplicate expanded inside the two-page fit-up.
    assert all(sku not in spec.PIVOT_FIT_STEPS[0] for sku in spec.PIVOT_SHIM_BUY)
    description = spec.BOM_DESCRIPTIONS[spec.PIVOT_SHIM]
    assert "FITTING STOCK" in description
    assert len(description) <= drawing.BOM_DESCRIPTION_MAX_CHARS


def test_ring_down_slack_follows_what_lies_under_each_balloon() -> None:
    keep_out = (0.200, 0.0, 0.400, 0.070)
    floor = 0.033
    outline = (0.050, 0.120, 0.150, 0.200)
    # The room ends at the title block's top, above the floor, for every
    # balloon: one beside the block could lead across its corner.
    over = [(0.300, 0.110, 0.005)]
    assert drawing.ring_floor_clearance(
        over, outline, keep_out=keep_out, floor=floor
    ) == pytest.approx(0.035)
    beside = [(0.100, 0.060, 0.005)]
    assert drawing.ring_floor_clearance(
        beside, outline, keep_out=keep_out, floor=floor
    ) == pytest.approx(-0.015)
    assert drawing.ring_floor_clearance(
        over, outline, keep_out=keep_out, floor=0.100
    ) == pytest.approx(0.005)
    # The outline binds too, and the cap (the centred position) limits it.
    wide = (0.050, 0.090, 0.250, 0.200)
    assert drawing.ring_down_slack(
        over, wide, keep_out=keep_out, floor=floor, cap=0.040
    ) == pytest.approx(0.020)
    assert drawing.ring_down_slack(
        over, outline, keep_out=keep_out, floor=floor, cap=0.010
    ) == pytest.approx(0.010)
    # A balloon already in the keep-out allows nothing.
    inside = [(0.300, 0.070, 0.005)]
    assert drawing.ring_down_slack(
        inside, outline, keep_out=keep_out, floor=floor, cap=0.040
    ) == 0.0


def test_cluster_rings_keep_air_under_the_top_border() -> None:
    assert drawing.CLUSTER_RING_REGION[3] == pytest.approx(
        drawing.SHEET_INNER_BORDER[3] - drawing.BOM_SHEET_CLEARANCE
    )


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
    """The parenthesised tip text, centred on its point: on the sheet, left of
    the dowel and the riser's -X end, above the tip, clear of the plan and
    every note."""
    tx, _ty, tz = drawing.CL_TIP_TEXT_MODEL_MM
    cx, cy = _elevation_xy(tx, tz)
    printed = f"({spec._length(spec.cl_dowel.TIP_HEIGHT, spec.CL_TIP_PRECISION)})"
    half_w, half_h = len(printed) * CHAR_M / 2.0, LINE_M / 2.0
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




def test_plain_pivot_geometry_sets_the_carrier_and_positive_head_capture() -> None:
    """Exercise placed solids' stack, not the wording of their fitter notes."""
    screw, spacer, shim = spec.pivot_screw, spec.pivot_spacer, spec.pivot_shim
    block = spec.pivot_block
    for index in range(2):
        screw_origin, screw_rows = spec.PLACEMENTS[spec.PIVOT_SCREW][index]
        spacer_origin, spacer_rows = spec.PLACEMENTS[spec.PIVOT_SPACER][index]
        shims = spec.PLACEMENTS[spec.PIVOT_SHIM][
            index * shim.PER_SUPPORT:(index + 1) * shim.PER_SUPPORT
        ]
        shim_origin, shim_rows = shims[0]
        assert screw_rows[2] == spacer_rows[2] == shim_rows[2] == (0.0, 0.0, 1.0)
        assert screw_origin[:2] == spacer_origin[:2] == shim_origin[:2]
        assert shim_origin[2] == pytest.approx(spec.trammel.PIVOT_BLOCK_TOP_Z)
        assert spacer_origin[2] == pytest.approx(shims[-1][0][2] + shim.THICKNESS)
        assert spacer_origin[2] + spacer.LENGTH == pytest.approx(spec.trammel.CARRIER_UNDERSIDE_Z)
        assert screw_origin[2] == pytest.approx(shim_origin[2] - block.BORE_DEPTH)
        assert screw_origin[2] - screw.THREAD_LENGTH > spec.trammel.CARRIAGE_TOP_Z
        gap = screw_origin[2] + screw.SHOULDER_LENGTH - spec.trammel.CARRIER_TOP_Z
        assert spec.PIVOT_RUNNING_GAP[0] <= gap <= spec.PIVOT_RUNNING_GAP[1]
        assert screw.HEAD_DIA > spec.carrier.PIN_HOLE_DIA


def test_block_occurrences_and_integral_nut_axis_match_the_feed_geometry() -> None:
    assert len(spec.PLACEMENTS[spec.PIVOT_BLOCK]) == 1
    assert len(spec.PLACEMENTS[spec.FEED_BLOCK]) == 1
    assert spec.PLACEMENTS[spec.FEED_BLOCK][0] == spec.BLOCK_PLACEMENTS[0]
    assert spec.PLACEMENTS[spec.PIVOT_BLOCK][0] == spec.BLOCK_PLACEMENTS[1]
    block = spec.feed_block
    origin, rows = spec.PLACEMENTS[spec.FEED_BLOCK][0]
    nut_axis = (block.NUT_FACE_X, block.NUT_AXIS_Y, block.NUT_AXIS_Z)
    world = tuple(origin[i] + sum(nut_axis[k] * rows[k][i] for k in range(3)) for i in range(3))
    assert world[2] == pytest.approx(spec.leadscrew.SCREW_AXIS_Z)
    assert 0.0 <= block.NUT_Z[0] < block.NUT_Z[1] <= block.BLOCK_HEIGHT


@pytest.mark.parametrize(
    "sheet", (drawing.PIVOT_SHEET, "LEADSCREW FEED EXPLODED", "RAIL BARS EXPLODED")
)
def test_cluster_recipe_isolates_real_families_and_their_context_before_fitting(
    monkeypatch, sheet,
) -> None:
    cluster = next(c for c in drawing.CLUSTERS if c.sheet == sheet)
    view, adapter = object(), object()
    events = []
    monkeypatch.setattr(drawing, "_activate_sheet", lambda a, s: events.append(("sheet", s)))
    monkeypatch.setattr(drawing, "_place_named_view", lambda *a, **kw: view)
    monkeypatch.setattr(drawing, "set_high_quality_shaded_with_edges", lambda *a, **kw: None)
    monkeypatch.setattr(drawing, "apply_view_configuration", lambda *a, **kw: "Default Simplified")
    monkeypatch.setattr(
        drawing, "set_view_exploded_state",
        lambda a, v, exploded, **kw: events.append(("explode", exploded, kw["configuration"])),
    )
    monkeypatch.setattr(
        drawing, "isolate_drawing_view_components",
        lambda a, v, **kw: events.append(("isolate", kw["visible_stems"])),
    )

    def fit(a, placed, fitted_cluster, configuration, **kwargs):
        assert a is adapter and placed is view and fitted_cluster is cluster
        assert configuration == "Default Simplified"
        assert events[-1] == ("isolate", cluster.visible)
        return (1.0, 5.0)

    monkeypatch.setattr(drawing, "_fit_cluster_view", fit)
    assert drawing._place_cluster_view(adapter, cluster) == (view, (1.0, 5.0))
    assert events[0] == ("sheet", sheet)
    assert events[1] == ("explode", True, "Default Simplified")


@pytest.mark.parametrize("missing", (False, True))
def test_pivot_balloon_recipe_requests_each_new_family_once_and_refuses_missing(
    monkeypatch, missing,
) -> None:
    from contextlib import nullcontext

    cluster = next(c for c in drawing.CLUSTERS if c.sheet == drawing.PIVOT_SHEET)
    calls = []
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *a: None)
    monkeypatch.setattr(drawing, "_link_view_to_bom", lambda *a, **kw: None)
    monkeypatch.setattr(drawing, "_source_configuration_active", lambda *a, **kw: nullcontext())
    monkeypatch.setattr(drawing, "_ring_balloons", lambda *a, **kw: None)
    monkeypatch.setattr(drawing, "_relax_cluster_slide", lambda a, v, landings, **kw: landings)
    proved = []
    monkeypatch.setattr(
        drawing, "_assert_declared_leaders_clear",
        lambda a, v, declared, **kw: proved.append({d.stem for d in declared}),
    )

    def create(a, v, *, items, **kwargs):
        calls.append(tuple(items))
        return [SimpleNamespace(stem=stem) for stem, item in items if not (missing and stem == spec.PIVOT_SHIM)]

    monkeypatch.setattr(drawing, "add_component_bom_balloons", create)
    if missing:
        with pytest.raises(RuntimeError, match="expected one for each"):
            drawing._balloon_cluster(object(), object(), cluster, tuple(spec.ITEM_NUMBERS.items()), "BOM")
    else:
        landings = drawing._balloon_cluster(object(), object(), cluster, tuple(spec.ITEM_NUMBERS.items()), "BOM")
        assert {landing.stem for landing in landings} == set(cluster.stems)
        assert proved == [{spec.PIVOT_SHIM}]
    assert calls == [tuple((stem, item) for stem, item in spec.ITEM_NUMBERS.items() if stem in cluster.stems)]


def test_assembly_overflow_moves_whole_steps_to_fit_sheet_without_losing_checks():
    # Spaced, each one-line step takes two lines (pitch and blank).
    steps = tuple(f"{index}. STEP-{index}." for index in range(1, 49))
    checks = ("CHECK: COMPLETE.",)
    fit = ("P1. FIT THE PIVOT.", "F1. ALIGN THE FEED.")
    sequence, fitting = drawing.assembly_and_fit_layouts(steps, checks, fit)
    assert "CONTINUED ON SHEET 8" in sequence.steps
    assert fitting.steps.startswith("ASSEMBLY CONTINUED AND FIT-UP\n")
    texts = (
        sequence.steps, sequence.continued, sequence.checks,
        fitting.steps, fitting.continued, fitting.checks,
    )
    combined = "\n".join(texts)
    positions = []
    for step in steps:
        assert combined.count(step + "\n") + int(combined.endswith(step)) == 1
        positions.append(combined.index(step))
    assert positions == sorted(positions)
    assert combined.index(steps[-1]) < combined.index("P1. FIT THE PIVOT.")
    assert combined.count(checks[0]) == 1
    assert sequence.checks == ""
    assert fitting.checks == checks[0]
    for layout in (sequence, fitting):
        _assert_steps_sheet_fits(layout)
        bottom = layout.checks_xy[1] - drawing._note_height(layout.checks)
        reference_floor = (
            drawing.TITLE_BLOCK[3] + drawing.BOM_SHEET_CLEARANCE
            + drawing.NOTE_LINE_M + drawing.VIEW_LABEL_GAP
        )
        assert bottom - drawing.REGION_GAP - reference_floor >= drawing.NOTES_REFERENCE_MIN_HEIGHT


def test_reference_reservation_refuses_text_that_only_fits_without_the_live_view():
    steps = tuple(f"{index}. STEP." for index in range(1, 41))
    drawing.steps_sheet_layout(steps, ())
    with pytest.raises(ValueError, match="instruction checks overrun"):
        drawing.steps_sheet_layout(
            steps, (), reference_height=drawing.NOTES_REFERENCE_MIN_HEIGHT,
        )


def test_two_instruction_sheets_refuse_a_sequence_that_cannot_fit():
    steps = tuple(f"{index}. STEP." for index in range(1, 101))
    with pytest.raises(ValueError, match="exceed sheets"):
        drawing.assembly_and_fit_layouts(steps, (), ("P1. FIT.",))


def test_complete_source_instructions_fit_existing_pages_at_normal_note_size():
    assert drawing.NOTE_LINE_M == 0.004525
    assert drawing.STEPS_LINE_WIDTH == 68
    assert drawing.NOTES_REFERENCE_MIN_HEIGHT == 0.075
    assert [step.split(". ", 1)[0] for step in spec.ASSEMBLY_STEPS] == [
        "1", "2", "3", "4", "5", "6", "7", "8A", "8B", "9", "10", "11",
        "12", "13A", "13B", "13C", "13D",
    ]
    # The integrated two-sheet budget was short by 1.075 mm: F3's fourth
    # line. Preserve all checks while keeping that paragraph to three lines.
    f3 = drawing._wrapped(
        (spec.FEED_FIT_STEPS[-1],), width=drawing.STEPS_LINE_WIDTH, spaced=True,
    )
    assert len(f3.splitlines()) == 3
    layouts = (drawing.STEPS_LAYOUT, drawing.FIT_LAYOUT)
    printed = " ".join(" ".join(
        text
        for layout in layouts
        for text in (layout.steps, layout.continued, layout.checks)
    ).split())
    for step in (
        spec.GENERAL_TORQUE_NOTE, *spec.ASSEMBLY_STEPS,
        *spec.PIVOT_FIT_STEPS, *spec.FEED_FIT_STEPS, *spec.ASSEMBLY_CHECKS,
    ):
        assert printed.count(" ".join(step.split())) == 1
    for layout in layouts:
        _assert_steps_sheet_fits(layout)
        text_bottom = layout.checks_xy[1] - drawing._note_height(layout.checks)
        reference_floor = (
            drawing.TITLE_BLOCK[3] + drawing.BOM_SHEET_CLEARANCE
            + drawing.NOTE_LINE_M + drawing.VIEW_LABEL_GAP
        )
        assert (
            text_bottom - drawing.REGION_GAP - reference_floor
            >= drawing.NOTES_REFERENCE_MIN_HEIGHT
        )


def _family_instances(*stems: str) -> set[str]:
    return {
        spec.instance_name(stem, index)
        for stem in stems
        for index in range(spec.QUANTITIES[stem])
    }


def test_linear_motion_view_hides_only_the_carrier_and_its_load() -> None:
    hidden, shown = set(drawing.LINEAR_MOTION_HIDDEN), set(drawing.LINEAR_MOTION_SHOWN)
    # Every modelled occurrence, each in exactly one list, none twice.
    assert len(hidden) == len(drawing.LINEAR_MOTION_HIDDEN)
    assert len(shown) == len(drawing.LINEAR_MOTION_SHOWN)
    assert not hidden & shown
    assert hidden | shown == spec.INSTANCE_NAMES
    # The owner's hide list, reproduced by the builder's locks to the carrier.
    assert hidden == {
        spec.instance_name(spec.CARRIER, 0),
        *spec.RISER_SCREW_INSTANCES,
        *_family_instances(
            spec.RISER, spec.HUB_STUD, spec.HUB_SLEEVE, spec.HUB_WASHER,
            spec.HUB_SCREW, spec.LEFT_CLAMP_SCREW, spec.FEED_LEVER, spec.CL_DOWEL,
            spec.CLAMP_SCREW, spec.LEVER_SCREW, spec.LEVER_LOCK_WASHER,
        ),
    }
    assert all(
        name == spec.instance_name(spec.CARRIER, 0)
        or any(
            spec.lock_parent(stem, index) == spec.instance_name(spec.CARRIER, 0)
            for stem in spec.LOCKED_TO
            for index in range(len(spec.LOCKED_TO[stem]))
            if spec.instance_name(stem, index) == name
        )
        for name in hidden
    )
    # The riser-screw family splits: the feed nut's four stay on the lug.
    assert set(spec.NUT_SCREW_INSTANCES) <= shown
    assert _family_instances(
        *spec.BASE_BARS, spec.RAIL, spec.CARRIAGE, spec.PIVOT_BLOCK,
        spec.FEED_BLOCK, spec.PIVOT_SCREW, spec.PIVOT_SPACER, spec.PIVOT_SHIM,
        spec.LEADSCREW, spec.FEED_NUT, spec.PILLOW_BLOCK, spec.END_BRACKET,
        spec.HANDWHEEL, spec.HOLD_DOWN_STUD, spec.T_NUT, spec.FLANGE_NUT,
        spec.RAIL_SCREW, spec.CARRIAGE_SCREW, spec.PILLOW_BLOCK_SCREW,
    ) <= shown
    # Drawing-only: no cluster, BOM or model inventory changes for it.
    assert sorted(stem for c in drawing.CLUSTERS for stem in c.stems) == sorted(spec.BOM_ORDER)
    assert drawing.LINEAR_MOTION_SHEET not in {c.sheet for c in drawing.CLUSTERS}


def test_linear_motion_balloons_are_a_sparse_set_on_shown_parts() -> None:
    ballooned = drawing.LINEAR_MOTION_BALLOONED
    assert ballooned == tuple(stem for stem in spec.BOM_ORDER if stem in set(ballooned))
    assert set(ballooned) == {
        spec.PIVOT_BLOCK, spec.FEED_BLOCK, spec.PIVOT_SCREW, spec.END_BRACKET,
        spec.RAIL, spec.CARRIAGE, spec.LEADSCREW, spec.FEED_NUT,
        spec.PILLOW_BLOCK, spec.HANDWHEEL,
    }
    assert all(_family_instances(stem) <= set(drawing.LINEAR_MOTION_SHOWN) for stem in ballooned)
    assert set(drawing.LINEAR_MOTION_ANCHORS) == set(ballooned)
    # Walked, never the exploded sheets' frozen points.
    assert all(anchor.point_mm is None for anchor in drawing.LINEAR_MOTION_ANCHORS.values())
    assert {stem: anchor.instance for stem, anchor in drawing.LINEAR_MOTION_ANCHORS.items()} == {
        spec.PIVOT_BLOCK: None,
        spec.FEED_BLOCK: None,
        spec.PIVOT_SCREW: spec.instance_name(spec.PIVOT_SCREW, 1),
        spec.END_BRACKET: None,
        spec.RAIL: "@Rail:2",
        spec.CARRIAGE: "@Carriage:2",
        spec.LEADSCREW: "@LeadScrew:1",
        spec.FEED_NUT: "@FeedNut:1",
        spec.PILLOW_BLOCK: None,
        spec.HANDWHEEL: None,
    }
    # The pivot side's three are rail 2's and the pivot block's.
    assert spec.lock_parent(spec.PIVOT_SCREW, 1) == spec.instance_name(spec.PIVOT_BLOCK, 0)
    assert spec.lock_parent(spec.PIVOT_BLOCK, 0) == spec.instance_name(spec.CARRIAGE, 1)


def _linear_leaf(name: str, *, visible: bool, path: str | None = None):
    """A drawing-view leaf as _drawing_balloons._component_leaf reads it."""
    identities = {name.casefold()}
    if name.startswith("@"):
        role = name[1:].split(":", 1)[0]
        physical, member = _component_references.REFERENCE_IDENTITIES[role]
        identities |= {physical, f"{physical}--{member}".casefold()}
    else:
        identities.add(name.rsplit("-", 1)[0])
    return SimpleNamespace(
        name=f"{name}@Drawing View11",
        path=path or name,
        identities=frozenset(identities),
        visible=visible,
    )


def _linear_leaves() -> list[SimpleNamespace]:
    return [
        *(_linear_leaf(name, visible=True) for name in drawing.LINEAR_MOTION_SHOWN),
        *(_linear_leaf(name, visible=False) for name in drawing.LINEAR_MOTION_HIDDEN),
    ]


@pytest.mark.parametrize(
    ("fault", "message"),
    (
        (None, None),
        ("carrier drawn", "drawn but must be hidden"),
        ("nut screw hidden", "hidden but must be drawn"),
        ("missing handwheel", "occurs 0 times"),
        ("duplicate rail screw", "occurs 2 times"),
        ("unknown component", "not one occurrence"),
    ),
)
def test_linear_motion_readback_refuses_any_departure(fault, message) -> None:
    leaves = _linear_leaves()
    carrier = spec.instance_name(spec.CARRIER, 0)
    handwheel = spec.instance_name(spec.HANDWHEEL, 0)
    if fault == "carrier drawn":
        leaves = [_linear_leaf(carrier, visible=True) if leaf.path == carrier else leaf for leaf in leaves]
    elif fault == "nut screw hidden":
        nut_screw = spec.NUT_SCREW_INSTANCES[0]
        leaves = [_linear_leaf(nut_screw, visible=False) if leaf.path == nut_screw else leaf for leaf in leaves]
    elif fault == "missing handwheel":
        leaves = [leaf for leaf in leaves if leaf.path != handwheel]
    elif fault == "duplicate rail screw":
        leaves.append(_linear_leaf(spec.RAIL_SCREW_INSTANCES[0], visible=True))
    elif fault == "unknown component":
        leaves.append(_linear_leaf("ch-rocker-arm-tl-oblique-strap-1", visible=False))
    failures = drawing.linear_motion_visibility_failures(leaves)
    if fault is None:
        assert failures == []
        return
    assert any(message in failure for failure in failures), failures


def test_linear_motion_recipe_hides_reads_back_then_fits_collapsed(monkeypatch) -> None:
    view, adapter = object(), object()
    events = []
    monkeypatch.setattr(drawing, "_activate_sheet", lambda a, s: events.append(("sheet", s)))

    def place(a, name, center, scale, *, label):
        events.append(("place", name, center, scale))
        return view

    monkeypatch.setattr(drawing, "_place_named_view", place)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda a, v: events.append(("hlr",)))
    monkeypatch.setattr(
        drawing, "apply_view_configuration",
        lambda a, v, **kw: events.append(("configuration",)) or "Default Simplified",
    )
    monkeypatch.setattr(
        drawing, "set_view_exploded_state",
        lambda a, v, exploded, **kw: events.append(("explode", exploded, kw["configuration"])),
    )
    monkeypatch.setattr(
        drawing, "isolate_drawing_view_components",
        lambda a, v, **kw: events.append(("isolate", kw["visible_stems"])),
    )
    monkeypatch.setattr(
        drawing, "_assert_linear_motion_visibility",
        lambda a, v, **kw: events.append(("readback", v)),
    )

    def fit(a, placed, scale, configuration, *, exploded, label):
        events.append(("fit", scale, configuration, exploded))
        return (1.0, 3.0)

    monkeypatch.setattr(drawing, "_fit_ring_view", fit)
    assert drawing._place_linear_motion_view(adapter, label="linear") == (view, (1.0, 3.0))
    assert events == [
        ("sheet", drawing.LINEAR_MOTION_SHEET),
        ("place", spec.PLAN_VIEW, drawing.CLUSTER_CENTER, drawing.LINEAR_MOTION_SCALE),
        ("hlr",),
        ("configuration",),
        ("explode", False, "Default Simplified"),
        ("isolate", frozenset(drawing.LINEAR_MOTION_SHOWN)),
        ("readback", view),
        ("fit", drawing.LINEAR_MOTION_SCALE, "Default Simplified", False),
    ]


@pytest.mark.parametrize("missing", (False, True))
def test_linear_motion_balloons_request_the_sparse_set_without_approaches(
    monkeypatch, missing,
) -> None:
    calls, rings = [], []
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *a: None)
    monkeypatch.setattr(drawing, "_link_view_to_bom", lambda *a, **kw: None)
    monkeypatch.setattr(
        drawing, "_ring_balloons", lambda a, v, landings, **kw: rings.append(kw["approach_deg"])
    )
    monkeypatch.setattr(drawing, "_relax_cluster_slide", lambda a, v, landings, **kw: landings)

    def create(a, v, *, items, anchors, **kwargs):
        calls.append((tuple(items), anchors))
        return [
            SimpleNamespace(stem=stem)
            for stem, _item in items
            if not (missing and stem == spec.FEED_NUT)
        ]

    monkeypatch.setattr(drawing, "add_component_bom_balloons", create)
    items = tuple(spec.ITEM_NUMBERS.items())
    if missing:
        with pytest.raises(RuntimeError, match="expected one for each"):
            drawing._balloon_linear_motion(object(), object(), items, "BOM", label="linear")
    else:
        landings = drawing._balloon_linear_motion(object(), object(), items, "BOM", label="linear")
        assert [landing.stem for landing in landings] == list(drawing.LINEAR_MOTION_BALLOONED)
    assert calls == [(
        tuple((stem, spec.ITEM_NUMBERS[stem]) for stem in drawing.LINEAR_MOTION_BALLOONED),
        drawing.LINEAR_MOTION_ANCHORS,
    )]
    assert rings == [{}]


def test_linear_motion_plan_ring_and_caption_fit_their_sheet() -> None:
    (x0, x1), (y0, y1), _z = spec.MODEL_EXTENT
    width = (x1 - x0) * OUTLINE_GROWTH[0]
    height = (y1 - y0) * OUTLINE_GROWTH[1]
    outline = _view_box((0.2, 0.15), width, height, drawing.LINEAR_MOTION_SCALE)
    scale = drawing.cluster_ring_scale(
        outline, drawing.LINEAR_MOTION_SCALE, label=drawing.LINEAR_MOTION_SHEET
    )
    assert scale in drawing.CLUSTER_SCALE_LADDER
    for fitted in drawing.CLUSTER_SCALE_LADDER:
        caption = drawing.linear_motion_caption(fitted)
        assert caption.startswith(f"{drawing.LINEAR_MOTION_SHEET} {fitted[0]:g}:{fitted[1]:g}")
        assert max(map(len, caption.split("\n"))) <= drawing.EXPLODED_CAPTION_WIDTH
        assert _inside_sheet(_note_box(caption, drawing.EXPLODED_CAPTION_XY))
        flat = " ".join(caption.split())
        assert f"CARRIER (ITEM {spec.ITEM_NUMBERS[spec.CARRIER]})" in flat
        assert f"BOM ON SHEET {drawing.BOM_SHEET_NUMBER}" in flat
        assert f"ASSEMBLY SEQUENCE ON SHEET {drawing.STEPS_SHEET_NUMBER}" in flat
