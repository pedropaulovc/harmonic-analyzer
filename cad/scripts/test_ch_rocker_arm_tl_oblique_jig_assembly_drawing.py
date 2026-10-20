"""Offline contract for the oblique-trammel jig drawing package (TL-00).

The sheet text comes from the jig spec, the BOM prints every family made and
bought with its registry number, numbered as the steps cite it, every BOM row
carries a balloon, and each sheet's budgeted regions stay inside the border,
out of the title block and clear of one another.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import _com
import _config
import _drawing_balloons
import _component_references
import _drawing_tables
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
import draw_ch_rocker_arm_tl_oblique_jig_assembly as drawing
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings


# Default-format note text: about 2.8 mm a character and 4.5 mm a line on the
# farm's templates (draw_pd_paper_drive_assembly fits 68 characters in 0.192).
CHAR_M = 0.0029
LINE_M = 0.0045
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
            spec.PIN_TOP_Z + lift(spec.PIVOT_PIN),
        )
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
            -feed.BLOCK_SIDE_LATERAL,
            feed.BLOCK_SIDE_LATERAL,
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


def _cluster_outline(cluster, center=(0.2, 0.15)):
    """The cluster view's estimated outline (sheet metres) at its placed scale."""
    points, (z0, z1) = _cluster_extent(cluster.sheet)
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    plan = (max(xs) - min(xs)) + (max(ys) - min(ys))
    width = plan * math.cos(math.pi / 4.0) * OUTLINE_GROWTH[0]
    height = (plan * ISO / 2.0 + (z1 - z0) * ISO) * OUTLINE_GROWTH[1]
    return _view_box(center, width, height, cluster.scale)


def test_sheets_are_landscape_with_their_scales() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED AT INNER PASS",
        "BILL OF MATERIALS",
        "RAIL BARS EXPLODED",
        "LEADSCREW FEED EXPLODED",
        "CARRIER EXPLODED",
        "ASSEMBLY STEPS",
    )
    assert set(drawing.SHEET_LAYOUTS.values()) == {drawing.DrawingLayout.LANDSCAPE}
    assert drawing.SHEET_SCALES == {
        "ASSEMBLED AT INNER PASS": (1.0, 4.0),
        "BILL OF MATERIALS": (1.0, 6.0),
        "RAIL BARS EXPLODED": (1.0, 5.0),
        "LEADSCREW FEED EXPLODED": (1.0, 3.0),
        "CARRIER EXPLODED": (1.0, 5.0),
        "ASSEMBLY STEPS": (1.0, 15.0),
    }
    assert drawing.SHEET_SCALE == (1.0, 4.0)
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
    for item in ("22", "25", "26"):
        assert spec.BOM_ORDER[int(item) - 1] in feed.stems
    # Review full-bought: the feed sheet shows the nut bracket on its pivot
    # block (rail 1's), ballooned only on the rail bars' sheet.
    assert feed.context == (spec.instance_name(spec.PIVOT_BLOCK, 0),)
    assert spec.lock_parent(spec.NUT_BRACKET, 0) in feed.context
    assert all(
        not cluster.context for cluster in drawing.CLUSTERS if cluster is not feed
    )


def test_exploded_captions_fit_their_text_region() -> None:
    for cluster in drawing.CLUSTERS:
        caption = drawing.exploded_caption(cluster, (1.0, 5.0))
        lines = caption.split("\n")
        assert max(map(len, lines)) <= drawing.EXPLODED_CAPTION_WIDTH
        assert len(lines) <= 3


def test_sheet_text_is_the_spec_text_wrapped() -> None:
    def words(text: str) -> list[str]:
        return text.split()

    assert words(drawing.ASSEMBLED_CAPTION) == words(spec.ASSEMBLED_CAPTION)
    assert words(drawing.ALIGNMENT_NOTE) == words(
        " ".join((*spec.ALIGNMENT_NOTE_LINES, spec.SWEEP_NOTE_LINE))
    )
    # Both columns read as the spec's steps, in order, split between steps
    # (or sub-steps).
    if drawing.ASSEMBLY_STEPS_CONTINUED:
        label = drawing.ASSEMBLY_STEPS_CONTINUED.split(". ", 1)[0]
        assert drawing._STEP_LABEL.fullmatch(label)
    assert words(drawing.ASSEMBLY_STEPS + " " + drawing.ASSEMBLY_STEPS_CONTINUED) == (
        words("ASSEMBLY SEQUENCE " + " ".join(spec.ASSEMBLY_STEPS))
    )
    assert words(drawing.ASSEMBLY_CHECKS) == words(" ".join(spec.ASSEMBLY_CHECKS))
    for text, width in (
        (drawing.ASSEMBLED_CAPTION, drawing.CAPTION_WIDTH),
        (drawing.ALIGNMENT_NOTE, drawing.ALIGNMENT_WIDTH),
        (drawing.ASSEMBLY_STEPS, drawing.STEPS_LINE_WIDTH),
        (drawing.ASSEMBLY_STEPS_CONTINUED, drawing.STEPS_LINE_WIDTH),
        (drawing.ASSEMBLY_CHECKS, drawing.STEPS_LINE_WIDTH),
    ):
        assert max(len(line) for line in text.split("\n")) <= width
    # Each alignment station prints whole on one line.
    for line in spec.ALIGNMENT_NOTE_LINES[1:]:
        assert line in drawing.ALIGNMENT_NOTE.split("\n")


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
    assert bom[2] == pytest.approx(drawing.SHEET_INNER_BORDER[2])
    # One unsplit table, clear of the title block by the clearance the
    # recipe measures it against at run time.
    assert not drawing.bom_extent_violations(drawing.BOM_ANCHOR, BOM_WIDTH, BOM_HEIGHT)
    assert bom[1] - drawing.TITLE_BLOCK[3] >= drawing.BOM_SHEET_CLEARANCE
    # The reference view stays in the room the drawing asserts at run time,
    # which keeps out of the title block.
    region = drawing.REFERENCE_REGION
    assert _inside(reference, region) and _inside_sheet(region)
    assert region[2] <= bom[0] - drawing.REGION_GAP


def test_bom_extent_violations_name_each_breach() -> None:
    anchor = drawing.BOM_ANCHOR
    assert drawing.bom_extent_violations(anchor, BOM_WIDTH, 0.200) == [
        "enters the title block"
    ]
    assert drawing.bom_extent_violations(anchor, BOM_WIDTH + 0.001, BOM_HEIGHT) == [
        "crosses the inner border"
    ]
    assert drawing.bom_extent_violations(
        (anchor[0] - 0.001, anchor[1]), BOM_WIDTH, BOM_HEIGHT
    ) == ["enters the reference view's room"]


def test_each_cluster_rings_inside_its_sheet() -> None:
    for cluster in drawing.CLUSTERS:
        outline = _cluster_outline(cluster)
        # Its estimated ring fits at the scale it is placed at, and at no
        # larger one: the sheet scales are the fit's, larger than the one
        # 1:10 view they replace.
        assert drawing.cluster_ring_scale(outline, cluster.scale, label="t") == (
            cluster.scale
        )
        assert cluster.scale[0] / cluster.scale[1] > 1.0 / 10.0
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
            drawing.exploded_caption(cluster, cluster.scale),
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
    assert drawing.cluster_ring_scale(small, (1.0, 10.0), label="t") == (1.0, 3.0)
    huge = (0.0, 0.0, 0.400, 0.300)
    with pytest.raises(ValueError, match="1:3: .* \\| .*1:10: "):
        drawing.cluster_ring_scale(huge, (1.0, 10.0), label="t")
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
    finished = _view_box(
        _center(layout.finished_region), *_iso_size(0.0), drawing.ISOMETRIC_SCALE
    )
    boxes = [
        finished,
        _note_box(layout.steps, drawing.STEPS_XY),
        _note_box(layout.checks, layout.checks_xy),
    ]
    if layout.continued:
        boxes.append(_note_box(layout.continued, drawing.STEPS_CONTINUED_XY))
    return finished, boxes


def _assert_steps_sheet_fits(layout) -> None:
    finished, boxes = _steps_sheet_boxes(layout)
    assert all(_inside_sheet(box) for box in boxes)
    for index, a in enumerate(boxes):
        for b in boxes[index + 1 :]:
            assert not _overlap(a, b)
    # The finished view stays in the room the drawing asserts at run time.
    assert _inside(finished, layout.finished_region)
    assert _inside_sheet(layout.finished_region)
    # The left column ends over its floor at the farm's measured line pitch.
    steps_lines = _lines(layout.steps)
    assert drawing.STEPS_XY[1] - steps_lines * drawing.NOTE_LINE_M >= (
        drawing.STEPS_FLOOR
    )


def _lines(text: str) -> int:
    return text.count("\n") + 1 if text else 0


def test_steps_sheet_regions_fit_apart() -> None:
    _assert_steps_sheet_fits(drawing.STEPS_LAYOUT)


def test_steps_sheet_holds_an_added_step() -> None:
    # Headroom: a line more in the last step (the right column) still lays
    # out with the finished view at its scale. The left column is full: steps
    # 1 to 10 fill it to its floor.
    steps = list(spec.ASSEMBLY_STEPS)
    steps[-1] += " " + "WORD " * 13
    layout = drawing.steps_sheet_layout(steps, spec.ASSEMBLY_CHECKS)
    _assert_steps_sheet_fits(layout)
    added = sum(map(_lines, (layout.steps, layout.continued))) - sum(
        map(_lines, (drawing.ASSEMBLY_STEPS, drawing.ASSEMBLY_STEPS_CONTINUED))
    )
    assert added >= 1


def test_every_bom_row_carries_one_balloon() -> None:
    assert set(drawing.BALLOON_ANCHORS) == set(spec.BOM_ORDER)
    walked = {
        stem: anchor
        for stem, anchor in drawing.BALLOON_ANCHORS.items()
        if stem != spec.BASE_BAR and stem not in spec.KIT_IDENTITIES
    }
    assert all(
        anchor.instance is None and anchor.point_mm is None
        for anchor in walked.values()
    )
    for family in spec.KIT_IDENTITIES:
        anchor = drawing.BALLOON_ANCHORS[family]
        assert anchor.instance == spec.instance_name(family, 0)
        assert anchor.point_mm is None
    # Review r5: balloon 1 lands on the bar's operator-side long edge, part
    # frame, mid-span between the spindle end and the far hold-down slot.
    bar = drawing.BALLOON_ANCHORS[spec.BASE_BAR]
    assert bar.instance is None
    assert bar.point_mm == (200.0, base_bar.HIGH_SIDE_Y, base_bar.BAR_THICK)
    assert base_bar.NEAR_SLOT_X < bar.point_mm[0] < base_bar.FAR_SLOT_X
    assert 0.0 < bar.point_mm[0] < base_bar.BAR_LENGTH
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
    assert len(screws) == 9
    steps = drawing.ASSEMBLY_STEPS + "\n" + drawing.ASSEMBLY_STEPS_CONTINUED
    for stem in screws:
        assert f"(ITEM {drawing.BOM_ITEM_NUMBERS[stem]})" in steps
    # A citation never breaks across a line.
    for line in steps.split("\n"):
        assert not line.rstrip().endswith(("ITEM", "(ITEM"))


@pytest.fixture
def native_bom_bindings(monkeypatch):
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
        return len(self.column_types)

    def _physical_column(self, column, include_hidden=True):
        columns = [
            index
            for index, hidden in enumerate(self.hidden)
            if include_hidden or not hidden
        ]
        # Native 2310 projected the retained hidden key at the legacy Qty index.
        if not include_hidden and columns and self.column_types[columns[-1]][0] == 203:
            retained = [
                index
                for index, hidden in enumerate(self.hidden)
                if hidden and self.column_types[index][0] == 201
            ]
            if retained:
                columns[-1] = retained[-1]
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
        return self.hidden[column] if 0 <= column < len(self.hidden) else False

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
        if not 0 <= column < len(self.column_types):
            raise IndexError(column)
        self.widths[column] = width
        return width

    def SetRowHeight(self, row, height, options):
        assert options == 0
        self.heights[row] = height
        return height

    def GetColumnWidth(self, column):
        if not 0 <= column < len(self.column_types):
            return 0.0
        return self.widths.get(column, 0.0 if self.hidden[column] else 0.02)

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
    reference = SimpleNamespace(ReferencedConfiguration="Default Simplified")
    seat._place_reference_view.return_value = reference
    seat.insert_bom_table.return_value = table
    seat._validate_bom.return_value = tuple(
        (stem, str(item)) for item, stem in enumerate(spec.BOM_ORDER, 1)
    )
    seat._place_assembled_sheet.return_value = lambda: None
    seat._place_kit_bom_note.return_value = lambda: None
    seat._place_cluster_view.side_effect = lambda _adapter, cluster: (
        object(),
        drawing.SHEET_SCALES[cluster.sheet],
    )
    seat._balloon_cluster.side_effect = (
        lambda _adapter, _view, cluster, _items, _bom_name: [
            SimpleNamespace(stem=stem) for stem in cluster.stems
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
    assert table.DisplayedText(0, 3) == "PART NUMBER"
    assert table.GetColumnType3(3, True)[0] == 203
    assert table.GetColumnType3(3, False)[0] == 201
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


def test_bom_refuses_a_row_that_wraps_into_the_title_block(native_bom_bindings) -> None:

    class Wrapping(_Table):
        def GetRowHeight(self, row):
            return 2.0 * super().GetRowHeight(row)  # every description wrapped

    with pytest.raises(RuntimeError, match="enters the title block"):
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
    state = SimpleNamespace(
        table=table,
        outline=(0.060, 0.125, 0.190, 0.230),
        notes=[],
        width=0.145,
        move="applied",
    )
    state.reference = SimpleNamespace(
        ReferencedConfiguration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        GetOutline=lambda: state.outline,
    )

    def add_block(_adapter, sheet, text, xy, *, label):
        assert sheet == drawing.BOM_SHEET
        note = _KitBomNote(text, xy, width=state.width, move=state.move)
        state.notes.append(note)
        return note

    monkeypatch.setattr(drawing, "_add_note_block", add_block)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *_args: None)
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
    assert bom[0] - extent[2] >= 0.004
    assert drawing.TITLE_BLOCK[0] - extent[2] >= 0.004
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
        state.table.position = (extent[2] + 0.003, state.table.position[1], 0.0)
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
