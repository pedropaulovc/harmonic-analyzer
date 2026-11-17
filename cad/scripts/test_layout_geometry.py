"""SolidWorks-free contract for the annotation-level layout geometry.

``_layout_geometry`` decides whether a dimension's TEXT collides with another
annotation's ink or the border, and whether leaders cross.  Those decisions
are pure arithmetic on sheet-space
boxes and segments, so they are pinned here without a COM seat; the live
collection that feeds them lives in
``diagnostics/drawing_layout_audit.collect_document``.

Coordinates are sheet METRES (what every SolidWorks annotation API returns) and
findings report millimetres (what an author types into ``SetPosition2``).
"""

from __future__ import annotations

import math

import pytest

from _layout_geometry import (
    DEFAULT_ADVANCE_RATIO,
    AnnotationGeometry,
    Box,
    DrawableRegion,
    Segment,
    SheetGeometry,
    ViewGeometry,
    calibrate_advance_ratio,
    clip_segment_to_box,
    estimate_text_box,
    find_border_breaches,
    find_leader_crossings,
    find_text_on_line,
    segment_box_overlap_length,
)

SHEET_W = 0.4318
SHEET_H = 0.2794
REGION = DrawableRegion.from_margins(
    SHEET_W, SHEET_H, left=0.0127, right=0.0127, bottom=0.0127, top=0.0127
)


def _text(label, box, *, owner="ViewA", segments=()):
    return AnnotationGeometry(
        label=label,
        kind="dim",
        owner=owner,
        text_boxes=(box,),
        segments=tuple(segments),
        position=(box.xmin, box.ymin),
    )


def _sheet(annotations, *, views=()):
    return SheetGeometry(
        name="Sheet1",
        width=SHEET_W,
        height=SHEET_H,
        region=REGION,
        views=tuple(views),
        annotations=tuple(annotations),
    )


# --------------------------------------------------------------------------
# segment / box arithmetic
# --------------------------------------------------------------------------


def test_segment_crossing_a_text_box_reports_the_chord_it_spends_inside():
    box = Box(0.100, 0.100, 0.110, 0.104)
    # A horizontal line straight through the middle spends the full 10 mm width.
    through = Segment(0.090, 0.102, 0.120, 0.102)
    assert segment_box_overlap_length(through, box) == pytest.approx(0.010)


def test_segment_stopping_short_of_a_text_box_overlaps_nothing():
    box = Box(0.100, 0.100, 0.110, 0.104)
    assert segment_box_overlap_length(Segment(0.080, 0.102, 0.099, 0.102), box) == 0.0
    assert clip_segment_to_box(Segment(0.080, 0.102, 0.099, 0.102), box) is None


def test_segment_grazing_a_text_box_face_is_not_ink_through_the_text():
    """A line running exactly along the box edge must not read as a collision.

    Witness lines routinely terminate on the dimension text's edge; the audit
    gates on the LENGTH inside, and an edge-grazing run has zero depth, so the
    tolerance never has to guess whether the contact was intentional.
    """
    box = Box(0.100, 0.100, 0.110, 0.104)
    along_top = Segment(0.090, 0.104, 0.120, 0.104)
    assert segment_box_overlap_length(along_top, box) == pytest.approx(0.0)
    # A run one text-height INSIDE the edge is real ink through the text.
    inside = Segment(0.090, 0.102, 0.120, 0.102)
    assert segment_box_overlap_length(inside, box) == pytest.approx(0.010)
    # ... but a perpendicular line that only touches the face has no chord.
    touching = Segment(0.105, 0.090, 0.105, 0.100)
    assert segment_box_overlap_length(touching, box) == pytest.approx(0.0)


def test_vertical_segment_inside_the_box_column_is_clipped_to_the_box_height():
    box = Box(0.100, 0.100, 0.110, 0.104)
    assert segment_box_overlap_length(
        Segment(0.105, 0.080, 0.105, 0.120), box
    ) == pytest.approx(0.004)


# --------------------------------------------------------------------------
# text boxes
# --------------------------------------------------------------------------


def test_text_box_grows_the_documented_direction_from_each_anchor_corner():
    """``swTextPosition_e`` decides which corner the anchor is.

    ``IAnnotation::GetPosition`` anchors a NOTE at its text box's upper-left and
    a surface-finish symbol at its lower-left, so getting the corner wrong
    mis-places every box by a full text height -- the audit would then chase
    phantom collisions one line below the real ink.
    """
    upper_left = estimate_text_box(
        "ABCD", anchor=(0.100, 0.200), height=0.003, reference=0
    )
    assert upper_left.ymax == pytest.approx(0.200)
    assert upper_left.xmin == pytest.approx(0.100)

    lower_left = estimate_text_box(
        "ABCD", anchor=(0.100, 0.200), height=0.003, reference=1
    )
    assert lower_left.ymin == pytest.approx(0.200)

    centered = estimate_text_box(
        "ABCD", anchor=(0.100, 0.200), height=0.003, reference=2
    )
    assert centered.center()[0] == pytest.approx(0.100)
    assert centered.center()[1] == pytest.approx(0.200)


def test_multiline_text_box_stacks_lines_and_takes_the_widest():
    box = estimate_text_box(
        "4X \u00d89.525\nREAM THRU", anchor=(0.10, 0.20), height=0.003, reference=0
    )
    assert box.height == pytest.approx(0.006)
    assert box.width == pytest.approx(len("REAM THRU") * 0.003 * DEFAULT_ADVANCE_RATIO)


def test_rotated_text_is_boxed_by_its_rotated_hull():
    """A vertical dimension must not be audited as if it read left to right."""
    flat = estimate_text_box("12.50", anchor=(0.10, 0.20), height=0.003, reference=0)
    turned = estimate_text_box(
        "12.50", anchor=(0.10, 0.20), height=0.003, reference=0, angle=math.pi / 2
    )
    assert turned.height == pytest.approx(flat.width)
    assert turned.width == pytest.approx(flat.height)


def test_empty_text_has_no_box():
    assert estimate_text_box("", anchor=(0.1, 0.2), height=0.003) is None
    assert estimate_text_box("x", anchor=(0.1, 0.2), height=0.0) is None


def test_advance_ratio_is_measured_from_exact_note_extents():
    """The one quantity no API exposes is calibrated from text that does.

    A note reports both its string and its true extent, so the sheet carries
    its own measurement of the font's glyph advance.  Without this the estimate
    is a constant, and a template font change silently mis-sizes every
    dimension box on the sheet.
    """
    samples = [
        ("ABCDE", 0.003, Box(0.0, 0.0, 5 * 0.003 * 0.7, 0.003)),
        ("ABCDEFGH", 0.003, Box(0.0, 0.0, 8 * 0.003 * 0.7, 0.003)),
    ]
    assert calibrate_advance_ratio(samples) == pytest.approx(0.7)


def test_advance_ratio_ignores_a_leader_polluted_extent():
    """A balloon's extent includes its leader, which would blow the ratio up."""
    samples = [("A", 0.003, Box(0.0, 0.0, 0.050, 0.003))]
    assert calibrate_advance_ratio(samples) == DEFAULT_ADVANCE_RATIO
    assert calibrate_advance_ratio([]) == DEFAULT_ADVANCE_RATIO


# --------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------


def test_dimension_line_through_a_neighbours_text_is_reported_with_coordinates():
    """drawing-guidelines.md rule 14 (keep text off the part): "no text sits on a line" -- the defect the PDF used to reveal."""
    victim = _text("D1", Box(0.100, 0.100, 0.120, 0.104))
    offender = AnnotationGeometry(
        label="D2",
        kind="dim",
        owner="ViewA",
        text_boxes=(Box(0.140, 0.100, 0.160, 0.104),),
        segments=(Segment(0.090, 0.102, 0.160, 0.102, "line"),),
    )
    findings = find_text_on_line(_sheet([victim, offender]))
    assert [finding.kind for finding in findings] == ["text-on-line"]
    finding = findings[0]
    assert (finding.a, finding.b) == ("D1", "D2")
    assert finding.extra["overlap_mm"] == pytest.approx(20.0)
    # The fix needs a coordinate, not an adjective.
    assert finding.move_target_mm is not None


def test_an_annotations_own_dimension_line_never_collides_with_its_own_text():
    """Every dimension's text sits ON its own dimension line by construction."""
    own = AnnotationGeometry(
        label="D1",
        kind="dim",
        owner="ViewA",
        text_boxes=(Box(0.100, 0.100, 0.120, 0.104),),
        segments=(Segment(0.080, 0.102, 0.140, 0.102, "line"),),
    )
    assert find_text_on_line(_sheet([own])) == []


def test_annotation_crossing_the_inner_border_is_reported_with_the_side():
    escaping = _text("NOTE1", Box(0.005, 0.100, 0.030, 0.104))
    findings = [f for f in find_border_breaches(_sheet([escaping])) if f.kind == "outside-border"]
    assert len(findings) == 1
    assert findings[0].b == "left border"
    assert findings[0].extra["breach_mm"] == pytest.approx(7.7)


def test_annotation_inside_the_title_block_keep_out_is_reported():
    sheet = SheetGeometry(
        name="Sheet1",
        width=SHEET_W,
        height=SHEET_H,
        region=REGION,
        keep_outs=(("title-block", Box(0.216, 0.0, SHEET_W, 0.066)),),
        annotations=(_text("D9", Box(0.300, 0.040, 0.320, 0.044)),),
    )
    findings = [f for f in find_border_breaches(sheet) if f.kind == "keep-out"]
    assert len(findings) == 1
    assert findings[0].b == "title-block"


def test_leader_crossing_a_foreign_view_is_reported_through_the_shared_audit():
    """A leader running across a foreign view is reported."""
    views = (
        ViewGeometry("Front", Box(0.050, 0.050, 0.150, 0.150)),
        ViewGeometry("Top", Box(0.200, 0.050, 0.300, 0.150)),
    )
    crossing = AnnotationGeometry(
        label="RA1",
        kind="gdt",
        owner="Top",
        text_boxes=(Box(0.320, 0.100, 0.340, 0.104),),
        # Runs from the Top view's text back across the whole Front view.
        segments=(Segment(0.320, 0.102, 0.060, 0.102, "leader"),),
    )
    findings = find_leader_crossings(_sheet([crossing], views=views))
    assert any(finding.kind == "leader-crosses-view" for finding in findings)


def test_leader_clipping_a_pictorial_view_is_not_a_crossing():
    """A pictorial outline is not an obstacle: an isometric's box is mostly
    empty diagonal space."""
    views = (
        ViewGeometry("Isometric", Box(0.050, 0.050, 0.150, 0.150), pictorial=True),
        ViewGeometry("Top", Box(0.200, 0.050, 0.300, 0.150)),
    )
    crossing = AnnotationGeometry(
        label="RA1",
        kind="gdt",
        owner="Top",
        text_boxes=(Box(0.320, 0.100, 0.340, 0.104),),
        segments=(Segment(0.320, 0.102, 0.060, 0.102, "leader"),),
    )
    findings = find_leader_crossings(_sheet([crossing], views=views))
    assert not any(finding.kind == "leader-crosses-view" for finding in findings)


def test_a_hole_callouts_attach_run_is_leader_even_where_it_misses_its_text():
    """swing, #902 case 2: collect_document promoted only the run touching the
    text, so MHA-DT-20 RD1's rim-to-shelf diagonal (S1 @ ac4fa6dd0 dump) stayed
    "line" and a leader crossing it passed the leader audit. A hole callout's
    display lines are all leader."""
    from diagnostics.drawing_layout_audit import _classify_segments

    lines = [
        Segment(0.1773, 0.1361, 0.1884, 0.1042, "line"),  # rim to shelf
        Segment(0.1762, 0.1393, 0.1773, 0.1361, "line"),
        Segment(0.1884, 0.1042, 0.2400, 0.1042, "line"),  # shelf under the text
    ]
    text = [Box(0.1900, 0.1042, 0.2436, 0.1077)]
    assert [s.role for s in _classify_segments(lines, text)] == ["line", "line", "leader"]
    rd1 = AnnotationGeometry(
        label="RD1",
        kind="dim",
        owner="v",
        text_boxes=tuple(text),
        segments=tuple(_classify_segments(lines, text, hole_callout=True)),
    )
    assert {s.role for s in rd1.segments} == {"leader"}
    rd3 = AnnotationGeometry(  # moved so its diagonal crosses RD1's
        label="RD3",
        kind="dim",
        owner="v",
        text_boxes=(Box(0.1250, 0.1205, 0.1650, 0.1240),),
        segments=(
            Segment(0.1950, 0.1400, 0.1700, 0.1200, "leader"),
            Segment(0.1700, 0.1200, 0.1200, 0.1200, "leader"),
        ),
    )
    views = (ViewGeometry("v", Box(0.050, 0.050, 0.260, 0.260)),)

    def crossings(callout):
        findings = find_leader_crossings(_sheet([callout, rd3], views=views))
        return [(f.a, f.b) for f in findings if f.kind == "leader-crosses-leader"]

    assert crossings(rd1)
    by_topology = AnnotationGeometry(
        label="RD1", kind="dim", owner="v", text_boxes=tuple(text),
        segments=tuple(_classify_segments(lines, text)),
    )
    assert not crossings(by_topology)  # the miss swing reported


# MHA-DT-20 RD1-RD3 as the S1 @ ac4fa6dd0 dump read them (swing, #902 case 2):
# display lines, then the lower-left of each estimated text row, in mm.
_S1_CALLOUTS = {
    "RD1": (
        [(177.3, 136.1, 188.4, 104.2), (176.2, 139.3, 177.3, 136.1), (188.4, 104.2, 240.0, 104.2)],
        [(190.0, 104.2)],
    ),
    "RD2": (
        [(169.1, 235.8, 154.3, 244.0), (171.3, 234.6, 169.1, 235.8), (154.3, 244.0, 244.1, 244.0)],
        [(178.1, 266.4), (171.0, 260.8), (155.9, 255.2), (162.3, 249.6), (164.1, 244.0)],
    ),
    "RD3": (
        [(174.9, 226.5, 166.6, 211.9), (175.7, 227.9, 174.9, 226.5), (166.6, 211.9, 69.0, 211.9)],
        [(88.5, 226.5), (91.0, 221.0), (69.0, 212.0)],
    ),
}


@pytest.mark.parametrize("label", sorted(_S1_CALLOUTS))
def test_both_audits_classify_a_hole_callouts_lines_alike(label):
    """Main, #902: two classifiers drifted (collect_document tagged RD1's and
    RD2's diagonals "line", RD3's "leader"). collect_document now delegates a
    hole callout to the shared ``classify_segments``; this fails loud if the
    two paths ever disagree on the S1 fixture. The legacy audit has no
    shoulder role, so the shared audit's shoulder reads as leader there."""
    from diagnostics.drawing_layout_audit import _classify_segments
    from _layout_audit import annotation_geometry

    mm = 0.001
    lines, rows = _S1_CALLOUTS[label]
    dump = {
        "type": 4,
        "name": label,
        "visible": 1,
        "display": {
            "lines": [[0, 0, 0, 0, x0 * mm, y0 * mm, 0.0, x1 * mm, y1 * mm, 0.0] for x0, y0, x1, y1 in lines],
            "texts": [{"t": "<MOD-DIAM>6.6 THRU", "pos": [x * mm, y * mm, 0.0], "h": 0.0035} for x, y in rows],
        },
        "dim": {"hole_callout": True},
    }
    shared = annotation_geometry(dump, owner="v", advance=0.6)
    legacy = _classify_segments(
        [Segment(x0 * mm, y0 * mm, x1 * mm, y1 * mm, "line") for x0, y0, x1, y1 in lines],
        [Box(x * mm, y * mm, x * mm + 0.030, y * mm + 0.0035) for x, y in rows],
        hole_callout=True,
    )

    def roles(segments, *, shoulder_as):
        return {
            (round(s.x0, 6), round(s.y0, 6), round(s.x1, 6), round(s.y1, 6)): shoulder_as.get(s.role, s.role)
            for s in segments
        }

    assert roles(legacy, shoulder_as={}) == roles(shared.segments, shoulder_as={"shoulder": "leader"})
    assert set(roles(legacy, shoulder_as={}).values()) == {"leader"}
