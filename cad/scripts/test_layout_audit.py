"""SolidWorks-free contract for the unified drawing layout audit (``_layout_audit``).

The audit's input is a per-sheet JSON dump the live collector
(``_drawing_layout_audit.collect_sheet_dumps``) records on every drawing leaf,
so every test here builds or replays a dump. The replayed values are REAL
SolidWorks display data from harmonic-base farm leaves (dt-logs/hb-render-2 and
hb-render-4 drawing-task.log, supports' "callout ... display data" lines and
``INote::GetExtent`` obstacle boxes), not hand-drawn boxes.
"""

from __future__ import annotations


import pytest

from _layout_audit import (
    LAYOUT_AUDIT_MODE,
    FindingSeverity,
    LayoutAuditMode,
    TextItem,
    apply_transform,
    audit_dump,
    balloon_circle,
    find_merged_blocks,
    glyph_count,
    row_boxes,
    severity,
    sheet_model,
    view_ink,
    view_polyline_segments,
)
from _layout_geometry import Segment

SHEET_W = 0.4318
SHEET_H = 0.2794
ZONE = {"left": 0.0127, "right": 0.0127, "bottom": 0.0127, "top": 0.0127}
TITLE_BLOCK = [0.216, 0.0, SHEET_W, 0.066]


def _line(x0, y0, x1, y1):
    """A GetLineAtIndex3-shaped record: [color, type, style, weight, s3, e3]."""
    return [0, 0, 0, 0, x0, y0, 0.0, x1, y1, 0.0]


def _hole_callout(name, lines, texts, *, height=0.0035):
    return {
        "type": 4,
        "name": name,
        "visible": 1,
        "display": {
            "lines": [_line(*line) for line in lines],
            "texts": [{"t": t, "pos": [x, y, 0.0], "h": height} for t, x, y in texts],
        },
        "dim": {"hole_callout": True},
    }


def _dim(name, text, x, y, *, lines=(), height=0.0035):
    return {
        "type": 4,
        "name": name,
        "display": {
            "lines": [_line(*line) for line in lines],
            "texts": [{"t": text, "pos": [x, y, 0.0], "h": height}],
        },
    }


def _note(name, text, extent, *, owner_type=1):
    x0, y0, x1, y1 = extent
    return {
        "type": 6,
        "name": name,
        "owner_type": owner_type,
        "display": {},
        "note": {"text": text, "extent": [x0, y0, 0.0, x1, y1, 0.0], "balloon": False},
    }


def _dump(*, views=(), sheet_annotations=(), tables=()):
    return {
        "schema": 1,
        "stem": "fixture",
        "sheet": "Sheet2",
        "width": SHEET_W,
        "height": SHEET_H,
        "zone": ZONE,
        "title_block": TITLE_BLOCK,
        "views": list(views),
        "sheet_annotations": list(sheet_annotations),
        "tables": list(tables),
    }


def _view(name, outline, annotations=(), **extra):
    return {"name": name, "outline": list(outline), "annotations": list(annotations), **extra}


def _kinds(findings):
    return sorted({f.kind for f in findings})


# --------------------------------------------------------------------------
# Real display data: MHA-035 harmonic base, sheet 2
# --------------------------------------------------------------------------

# hb-render-2 (e533ef6fd's layout): the MHA-004 transfer callout, as the leaf
# logged its IDisplayDimension display data.
HB2_PEDESTAL = (
    "MHA-004",
    [
        (0.264542, 0.218153, 0.23054, 0.240834),
        (0.265261, 0.217673, 0.264542, 0.218153),
        (0.23054, 0.240834, 0.171047, 0.240834),
    ],
    [
        ("2X ", 0.179215, 0.25761),
        ("<MOD-DIAM>", 0.185938, 0.257556),
        (" 3.45 ", 0.191216, 0.25761),
        ("<HOLE-DEPTH>", 0.202854, 0.257556),
        (" 19.50", 0.207854, 0.25761),
        ("TRANSFER FROM MHA-004", 0.171047, 0.252),
        ("AT ASSEMBLY;", 0.184746, 0.246444),
        (" 8-32 UNC - 2B ", 0.174589, 0.240888),
        ("<HOLE-DEPTH>", 0.20748, 0.240834),
        (" 16.00", 0.21248, 0.240888),
    ],
)
HB2_BLOCK = (
    "MHA-061",
    [
        (0.278736, 0.216933, 0.29254, 0.240834),
        (0.278304, 0.216185, 0.278736, 0.216933),
        (0.29254, 0.240834, 0.233047, 0.240834),
    ],
    [
        ("4X ", 0.241215, 0.25761),
        ("<MOD-DIAM>", 0.247938, 0.257556),
        (" 3.45 ", 0.253216, 0.25761),
        ("<HOLE-DEPTH>", 0.264854, 0.257556),
        (" 15.00", 0.269854, 0.25761),
        ("TRANSFER FROM MHA-061", 0.233047, 0.252),
        ("AT ASSEMBLY;", 0.246746, 0.246444),
        (" 8-32 UNC - 2B ", 0.236589, 0.240888),
        ("<HOLE-DEPTH>", 0.26948, 0.240834),
        (" 12.75", 0.27448, 0.240888),
    ],
)
# INote::GetExtent of "TOP VIEW SCALE 1:4": centred over the plan in
# hb-render-2, moved beside the plan's top-left corner in hb-render-4.
HB2_TOP_LABEL = (0.23475, 0.23265, 0.27947, 0.23703)
HB4_TOP_LABEL = (0.169863, 0.23265, 0.214585, 0.237034)
# The plan's casting box as supports' check logged it (hb-render-5 obstacles,
# 'view holes top'); the label and every callout sit outside it.
HOLES_TOP_OUTLINE = (0.22285, 0.1591, 0.33715, 0.2309)

# hb-render-4: the MHA-114 spring callout and the MHA-132 cross-tap callout
# whose top row sits 1.7 mm under the spring callout's underline.
HB4_SPRING = (
    "MHA-114",
    [
        (0.271414, 0.175759, 0.274041, 0.136412),
        (0.271376, 0.176323, 0.271414, 0.175759),
        (0.274041, 0.136412, 0.354372, 0.136412),
    ],
    [
        ("<MOD-DIAM>", 0.297576, 0.147578),
        (" 2.26 ", 0.302855, 0.147632),
        ("<HOLE-DEPTH>", 0.314492, 0.147578),
        (" 11.30", 0.319493, 0.147632),
        ("TRANSFER FROM MHA-114", 0.286047, 0.142022),
        ("AT ASSEMBLY; 4-40 UNC - 2B ", 0.275628, 0.136466),
        ("<HOLE-DEPTH>", 0.339027, 0.136412),
        (" 9.28", 0.344027, 0.136466),
    ],
)
HB4_CROSS_TAP = (
    "MHA-132",
    [
        (0.329717, 0.098055, 0.342356, 0.103278),
        (0.328783, 0.09767, 0.329717, 0.098055),
        (0.342356, 0.103278, 0.229232, 0.103278),
    ],
    [
        ("4X ", 0.262404, 0.131166),
        ("<MOD-DIAM>", 0.269127, 0.131113),
        (" 4.04 ", 0.274406, 0.131166),
        ("<HOLE-DEPTH>", 0.286043, 0.131113),
        (" 48 MIN", 0.291044, 0.131166),
        ("MHA-132 TUBE CROSS-SCREWS", 0.250907, 0.125556),
        ("THRU BOTH WALLS, SINGLE CONTINUOUS THREAD", 0.230711, 0.12),
        ("DEPTHS FROM SPOTFACE FLOOR", 0.248979, 0.114444),
        ("ON A1-A4 X CENTRES", 0.261375, 0.108888),
        ("2 EACH FRONT/REAR FACE 10-32 UNF - 2B ", 0.229232, 0.103331),
        ("<HOLE-DEPTH>", 0.322837, 0.103278),
        (" 46.00", 0.327838, 0.103331),
    ],
)


def _holes_sheet(top_label, *callouts):
    return _dump(
        views=[_view("holes top", HOLES_TOP_OUTLINE, [_hole_callout(*c) for c in callouts])],
        sheet_annotations=[_note("DetailItem467", "TOP VIEW SCALE 1:4", top_label)],
    )


def test_e533ef6fd_leader_through_the_top_view_label_is_found():
    """Positive control: hb-render-2's MHA-004 leader struck "TOP VIEW SCALE 1:4"."""
    findings = audit_dump(_holes_sheet(HB2_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK))
    hits = [
        f
        for f in findings
        if f.kind == "leader-through-text" and "MHA-004" in f.a and "TOP VIEW" in f.b
    ]
    assert len(hits) == 1
    assert severity(hits[0]) is FindingSeverity.GATING


def test_the_moved_top_view_label_clears_every_leader():
    """hb-render-4 moved the label beside the plan; the same leaders miss it."""
    findings = audit_dump(_holes_sheet(HB4_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK))
    assert not [f for f in findings if f.kind.startswith("leader") and "TOP VIEW" in f.b]


def test_the_two_transfer_callouts_side_by_side_keep_their_air():
    findings = audit_dump(_holes_sheet(HB4_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK))
    assert not [f for f in findings if f.kind == "text-clearance"]


def test_hb_render_4_cross_tap_under_the_spring_underline_reads_as_one_callout():
    """1.75 mm under the spring callout's underline: clear of it, but tighter
    than the 2.06 mm gap between rows INSIDE one callout, so the pair reads as
    one. It sits on the provisional 0.5 h clearance line (1.746 vs 1.75 mm);
    whichever class the calibrated thresholds put it in, it is reported."""
    findings = audit_dump(_holes_sheet(HB4_TOP_LABEL, HB4_SPRING, HB4_CROSS_TAP))
    pair = [
        f
        for f in findings
        if f.kind in ("text-clearance", "merged-blocks", "text-separation")
        and {f.a.split()[1], f.b.split()[1]} == {"MHA-114", "MHA-132"}
    ]
    assert pair
    assert min(f.extra["gap_mm"] for f in pair) == pytest.approx(1.75, abs=0.05)


def test_stacked_callouts_under_a_row_pitch_apart_read_as_one_block():
    """Port of supports' find_merged_blocks: Main's hb-render-4 eye pass read
    the spring block 1.7 mm over the cross-tap block as its fourth row. The
    side-by-side transfer pair (x spans disjoint, 2.5 mm apart) is not one
    column, and the plan's view label is not a callout."""
    sheet = sheet_model(
        _holes_sheet(HB4_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK, HB4_SPRING, HB4_CROSS_TAP)
    ).geometry
    merged = find_merged_blocks(sheet)
    assert [(f.a.split()[1], f.b.split()[1]) for f in merged] == [("MHA-114", "MHA-132")]
    assert merged[0].extra["gap_mm"] == pytest.approx(1.75, abs=0.05)
    assert merged[0].extra["limit_mm"] == pytest.approx(5.556, abs=0.01)
    assert severity(merged[0]) is FindingSeverity.GATING


def test_a_callout_over_four_rows_is_a_tall_block():
    """Port of supports' find_tall_callouts: hb-render-4's cross-tap ran six
    rows (Main's 4-row ruling). The 3-row spring and 4-row transfer pass."""
    findings = audit_dump(_holes_sheet(HB4_TOP_LABEL, HB2_PEDESTAL, HB4_SPRING, HB4_CROSS_TAP))
    tall = [f for f in findings if f.kind == "tall-block"]
    assert [(f.a, f.extra["rows"]) for f in tall] == [("hole-callout MHA-132", 6)]
    assert severity(tall[0]) is FindingSeverity.GATING


def test_callout_rows_centre_on_the_shoulder_and_tokens_are_one_glyph():
    items = [TextItem(t, x, y, 0.0035) for t, x, y in HB2_PEDESTAL[2]]
    shoulder = Segment(*HB2_PEDESTAL[1][2])
    rows = dict(row_boxes(items, advance=0.6, shoulders=[shoulder]))
    # The shoulder spans the widest row; the centred rows mirror about it.
    centre = (0.23054 + 0.171047) / 2.0
    top = rows["2X <MOD-DIAM> 3.45 <HOLE-DEPTH> 19.50"]
    assert top.xmin == pytest.approx(0.179215)
    assert top.xmax == pytest.approx(2 * centre - 0.179215)
    assert top.ymin == pytest.approx(0.257556)
    assert top.ymax == pytest.approx(0.25761 + 0.0035)
    assert glyph_count("<MOD-DIAM> 3.45 ") == 7


# --------------------------------------------------------------------------
# the classes the older audits could not see
# --------------------------------------------------------------------------


def test_touching_dimension_texts_fail_the_clearance():
    """MHA-092's "20.8" and "8.42" printed as "20.88.42": zero gap, no overlap.
    A penetration test passes that; a clearance test does not."""
    advance = 0.6
    h = 0.0035
    left = _dim("D1", "20.8", 0.040, 0.200)
    # "8.42" starts exactly where "20.8" ends.
    right = _dim("D2", "8.42", 0.040 + 4 * advance * h, 0.200)
    # An exact-width item on the sheet pins the advance at 0.6.
    ruler = _dim("D3", "", 0, 0)
    ruler["display"]["texts"] = [
        {"t": "12", "pos": [0.300, 0.100, 0.0], "h": h},
        {"t": "34", "pos": [0.300 + 2 * advance * h, 0.100, 0.0], "h": h},
    ]
    dump = _dump(views=[_view("plan", (0.02, 0.15, 0.1, 0.25), [left, right, ruler])])
    findings = [f for f in audit_dump(dump) if f.kind == "text-clearance"]
    assert len(findings) == 1
    assert findings[0].extra["gap_mm"] == pytest.approx(0.0, abs=1e-6)


def test_text_crossed_by_a_foreign_view_edge_is_found():
    """MHA-092's ADJUSTER ENTRY: a callout's text crossed by ANOTHER view's
    outline edge. Model edges come from GetPolylines7 (sheet space here)."""
    # A single vertical model edge of the right view at x = 0.130.
    polyline = [0, 0, 0, 0, 0, 1, 0, 0, 2, 0.130, 0.080, 0.0, 0.130, 0.160, 0.0]
    right_view = _view("right", (0.128, 0.078, 0.170, 0.162), polylines=polyline)
    callout = _hole_callout(
        "ADJ",
        [(0.080, 0.100, 0.100, 0.118), (0.100, 0.118, 0.140, 0.118)],
        [("ADJUSTER ENTRY", 0.100, 0.118)],
    )
    front = _view("front", (0.060, 0.080, 0.100, 0.160), [callout])
    findings = audit_dump(_dump(views=[front, right_view]))
    hits = [f for f in findings if f.kind == "text-on-line" and "view right geometry" in f.b]
    assert len(hits) == 1


def _mha_092_pre_287c_sheet():
    """MHA-092's three collisions as Main's I31 eye pass measured them, rebuilt
    as display data (the calibration run's own dump replaces this once logged):

    * plan "20.8" 0.68 mm left of "8.42" -- same view, no overlap;
    * the pinch-clearance callout (front view) over the right view's "6.0",
      overlapping it 1.3 x 4.8 mm;
    * the ADJUSTER callout (front view) printed INSIDE the right view's face,
      between its edges, touching none of them.
    """
    h = 0.0035
    advance = 0.6
    ruler = _dim("ruler", "", 0, 0)
    ruler["display"]["texts"] = [
        {"t": "12", "pos": [0.300, 0.230, 0.0], "h": h},
        {"t": "34", "pos": [0.300 + 2 * advance * h, 0.230, 0.0], "h": h},
    ]
    plan_left = _dim("PlanWidth", "20.8", 0.040, 0.200)
    plan_right = _dim("PlanPitch", "8.42", 0.040 + 4 * advance * h + 0.00068, 0.200)
    plan = _view("plan", (0.020, 0.170, 0.110, 0.240), [plan_left, plan_right, ruler])
    # The right view: a 30 x 60 mm face whose only model edges are its border.
    x0, y0, x1, y1 = 0.160, 0.080, 0.190, 0.140
    border = [x0, y0, 0.0, x1, y0, 0.0, x1, y1, 0.0, x0, y1, 0.0, x0, y0, 0.0]
    polyline = [0, 0, 0, 0, 0, 1, 0, 0, 5, *border]
    six = _dim("RightDepth", "6.0", 0.165, 0.120)
    right = _view("right", (x0 - 0.001, y0 - 0.001, x1 + 0.001, y1 + 0.001), [six], polylines=polyline)
    # "6.0" spans x 165.0-171.3, y 120.0-123.5 mm. "<MOD-DIAM> 3.26" ends
    # 4.8 mm into it and sits 1.3 mm down over its top.
    pinch = _hole_callout(
        "PinchClearance",
        [(0.120, 0.100, 0.1572, 0.1222), (0.1572, 0.1222, 0.1698, 0.1222)],
        [("<MOD-DIAM>", 0.1572, 0.1222), (" 3.26", 0.1572 + advance * h, 0.1222)],
    )
    adjuster = _hole_callout(
        "Adjuster",
        [(0.140, 0.090, 0.1650, 0.0950), (0.1650, 0.0950, 0.1850, 0.0950)],
        [("THRU ALL", 0.1660, 0.0952)],
    )
    front = _view("front", (0.100, 0.080, 0.150, 0.140), [pinch, adjuster])
    return _dump(views=[plan, right, front])


def test_mha_092_collisions_fail_the_shared_audit_and_passed_the_old_one():
    """Fail-first: the annotation audit of the time (``_layout_geometry``)
    passes the 0.68 mm "20.88.42" pair and the ADJUSTER text inside the right
    view; the element audit boxed every dimension as a NONE-scope placeholder
    and compared none of the three. The shared audit gates all three."""
    from _layout_geometry import audit_sheet

    dump = _mha_092_pre_287c_sheet()
    old = audit_sheet(sheet_model(dump).geometry)
    assert not [f for f in old if {"PlanWidth", "PlanPitch"} <= set((f.a + " " + f.b).split())]
    assert not [f for f in old if "Adjuster" in f.a and f.kind.startswith("text")]

    findings = audit_dump(dump)
    gating = [f for f in findings if severity(f) is FindingSeverity.GATING]

    def pair(kind, a, b):
        return [f for f in gating if f.kind == kind and a in f.a + f.b and b in f.a + f.b]

    near = pair("text-clearance", "PlanWidth", "PlanPitch")
    assert len(near) == 1 and near[0].extra["gap_mm"] == pytest.approx(0.68, abs=0.01)
    assert pair("text-clearance", "PinchClearance", "RightDepth")
    assert pair("text-on-view", "Adjuster", "view right")
    assert not pair("text-on-line", "Adjuster", "view right geometry")


# Ink measured on the I31 farm render (7ab69742b, cone-tip-block_drawing.png,
# 5100 x 3300 px, 11.81 px/mm) by swing: dark-pixel component boxes in sheet
# mm (test_cone_tip_block_drawing @ 287c5cf6a, _I31_TEXT_MM and friends).
I31_TEXT_MM = {
    "FlangeLen": ("plan", "20.8", (37.68, 229.19, 46.31, 232.66)),
    "FlangeSlotCtoC": ("plan", "8.42", (46.99, 229.70, 55.63, 233.09)),
    "PinchClearance": ("front", "<MOD-DIAM>3.26 <HOLE-DEPTH>6.9", (118.11, 170.60, 149.52, 175.68)),
    "PinchDepthCenter": ("right", "6.0", (143.00, 169.42, 148.84, 172.72)),
    "Adjuster": ("front", "ADJUSTER\nENTRY\nTHRU ALL", (85.60, 106.51, 142.66, 122.68)),
}
I31_RIGHT_BODY_MM = (141.31, 93.81, 159.43, 164.17)
I31_HEEL_HEIGHT_LINE_MM = ((119.25, 87.55), (119.25, 108.46))


def test_mha_092_i31_ink_fails_on_every_collision_the_eye_pass_found():
    """Positive control on the I31 render's own ink: all four of Main's
    collisions gate -- "20.8"/"8.42" 0.68 mm apart, the pinch callout on the
    6.0, the adjuster callout over the right view's body, and the 5.56
    heel-height line through the adjuster callout."""
    by_view = {"plan": [], "front": [], "right": []}
    for name, (view, text, box) in I31_TEXT_MM.items():
        by_view[view].append(_note(name, text, tuple(v / 1000.0 for v in box)))
    (hx0, hy0), (hx1, hy1) = I31_HEEL_HEIGHT_LINE_MM
    by_view["front"].append(
        _dim("HeelReliefHt", "5.56", 0.1100, 0.0950, lines=[(hx0 / 1000, hy0 / 1000, hx1 / 1000, hy1 / 1000)])
    )
    x0, y0, x1, y1 = (v / 1000.0 for v in I31_RIGHT_BODY_MM)
    border = [x0, y0, 0.0, x1, y0, 0.0, x1, y1, 0.0, x0, y1, 0.0, x0, y0, 0.0]
    pad = 0.003  # GetOutline pads the body with whitespace
    dump = _dump(
        views=[
            _view("plan", (0.020, 0.190, 0.120, 0.250), by_view["plan"]),
            _view("front", (0.060, 0.090, 0.118, 0.170), by_view["front"]),
            _view(
                "right",
                (x0 - pad, y0 - pad, x1 + pad, y1 + pad),
                by_view["right"],
                polylines=[0, 0, 0, 0, 0, 1, 0, 0, 5, *border],
            ),
        ]
    )
    gating = [f for f in audit_dump(dump) if severity(f) is FindingSeverity.GATING]

    def hits(kind, a, b):
        return [f for f in gating if f.kind == kind and a in f.a + f.b and b in f.a + f.b]

    near = hits("text-clearance", "FlangeLen", "FlangeSlotCtoC")
    assert len(near) == 1 and near[0].extra["gap_mm"] == pytest.approx(0.68, abs=0.01)
    assert hits("text-clearance", "PinchClearance", "PinchDepthCenter")
    assert hits("text-on-view", "Adjuster", "view right")
    assert hits("text-on-line", "HeelReliefHt", "Adjuster")


def test_a_shoulder_crossed_by_a_foreign_dimension_line_is_found():
    """Swing's class d: a dimension line crossing a callout's shoulder, the
    run under its text, below the text box itself."""
    h = 0.0035
    callout = _hole_callout(
        "Adjuster",
        [(0.080, 0.090, 0.100, 0.1000), (0.100, 0.1000, 0.140, 0.1000)],
        [("THRU ALL", 0.100, 0.1001)],
        height=h,
    )
    heel = _dim("HeelReliefHt", "5.56", 0.150, 0.080, lines=[(0.1190, 0.0875, 0.1190, 0.0990)])
    heel["display"]["lines"].append(_line(0.1190, 0.0990, 0.1190, 0.1010))
    findings = audit_dump(_dump(views=[_view("front", (0.05, 0.05, 0.2, 0.2), [callout, heel])]))
    crossed = [f for f in findings if f.kind == "shoulder-crosses-line"]
    assert [(f.a.split()[1], f.b.split()[1]) for f in crossed] == [("Adjuster", "HeelReliefHt")]
    assert severity(crossed[0]) is FindingSeverity.GATING


def test_a_leader_through_its_own_rows_is_found_but_its_shoulder_joint_is_not():
    h = 0.0035
    rows = [("TOP ROW TEXT", 0.100, 0.110), ("BOTTOM ROW", 0.100, 0.1044)]
    # Leader rises from the shoulder's right end, straight up through the rows.
    through = _hole_callout(
        "UP", [(0.125, 0.1044, 0.125, 0.140), (0.100, 0.1044, 0.1245, 0.1044)], rows, height=h
    )
    findings = audit_dump(_dump(views=[_view("v", (0.05, 0.05, 0.2, 0.2), [through])]))
    assert [f.kind for f in findings if f.kind.startswith("leader-through")] == [
        "leader-through-own-text"
    ]
    # Same leader leaving DOWNWARD from the shoulder end: only the joint touches.
    down = _hole_callout(
        "DOWN", [(0.1245, 0.1044, 0.140, 0.080), (0.100, 0.1044, 0.1245, 0.1044)], rows, height=h
    )
    findings = audit_dump(_dump(views=[_view("v", (0.05, 0.05, 0.2, 0.2), [down])]))
    assert not [f for f in findings if f.kind.startswith("leader-through")]


def test_a_leader_crossing_another_dimension_line_is_found():
    callout = _hole_callout(
        "C", [(0.100, 0.100, 0.140, 0.140), (0.140, 0.140, 0.170, 0.140)], [("Ø4.0", 0.140, 0.1402)]
    )
    dim = _dim("D", "25.0", 0.200, 0.200, lines=[(0.100, 0.130, 0.140, 0.110)])
    findings = audit_dump(_dump(views=[_view("v", (0.05, 0.05, 0.25, 0.25), [callout, dim])]))
    assert "leader-crosses-line" in _kinds(findings)


def test_dimension_text_over_the_title_block_or_off_the_sheet_is_found():
    """Main's rider: the deleted ``_dim_element`` gave every dimension and hole
    callout the border check and the title-block keep-out (Codex #269 thread
    1). The shared audit boxes their measured text against both."""
    over_block = _dim("OverBlock", "12.0", 0.300, 0.030)  # title block: x > 216, y < 66 mm
    off_sheet = _dim("OffSheet", "12.0", SHEET_W + 0.010, 0.150)
    in_border_band = _dim("InBand", "12.0", 0.005, 0.150)  # inside the 12.7 mm zone band
    callout = _hole_callout(
        "CalloutOverBlock", [(0.200, 0.100, 0.260, 0.050), (0.260, 0.050, 0.300, 0.050)], [("<MOD-DIAM>4.0 THRU", 0.262, 0.0502)]
    )
    clear = _dim("Clear", "12.0", 0.100, 0.150)
    findings = audit_dump(
        _dump(views=[_view("v", (0.05, 0.05, 0.25, 0.25), [over_block, off_sheet, in_border_band, callout, clear])])
    )

    def named(kind, name):
        return [f for f in findings if f.kind == kind and f" {name} " in f" {f.a} "]

    assert named("keep-out", "OverBlock")
    assert named("keep-out", "CalloutOverBlock")
    assert named("outside-border", "OffSheet")
    assert named("outside-border", "InBand")
    assert not [f for f in findings if " Clear " in f" {f.a} "]
    assert all(
        severity(f) is FindingSeverity.GATING
        for f in findings
        if f.kind in ("keep-out", "outside-border")
    )


def test_hidden_annotations_and_template_notes_are_not_audited():
    hidden = _dim("H", "99", 0.005, 0.005)
    hidden["visible"] = 3
    template = _note("Z", "A", (0.003, 0.03, 0.009, 0.038), owner_type=2)
    findings = audit_dump(
        _dump(views=[_view("v", (0.05, 0.05, 0.25, 0.25), [hidden])], sheet_annotations=[template])
    )
    assert findings == []


# --------------------------------------------------------------------------
# coordinate spaces, primitives, transport
# --------------------------------------------------------------------------


def test_polylines7_records_parse_with_and_without_geometry_data():
    # One polyline record (type 0, no geom data) and one arc record (type 1,
    # 12 geom values) followed by its tessellation.
    arc_geom = [0.0] * 12
    records = [
        0, 0, 0, 0, 0, 1, 0, 0, 3, 0.0, 0.0, 0.0, 0.01, 0.0, 0.0, 0.01, 0.01, 0.0,
        1, 12, *arc_geom, 0, 0, 0, 1, 0, 0, 2, 0.02, 0.0, 0.0, 0.03, 0.0, 0.0,
    ]
    segments = view_polyline_segments(records)
    assert [(s.x0, s.y0, s.x1, s.y1) for s in segments] == [
        (0.0, 0.0, 0.01, 0.0),
        (0.01, 0.0, 0.01, 0.01),
        (0.02, 0.0, 0.03, 0.0),
    ]


def test_view_edges_are_accepted_in_sheet_space_or_through_the_view_transform():
    outline = [0.10, 0.10, 0.20, 0.20]
    in_sheet = [0, 0, 0, 0, 0, 1, 0, 0, 2, 0.12, 0.12, 0.0, 0.18, 0.18, 0.0]
    assert view_ink({"name": "a", "outline": outline, "polylines": in_sheet}).space == "sheet"
    # Model-space points (metres about the part origin) with a 1:2 view at (0.15, 0.15).
    in_model = [0, 0, 0, 0, 0, 1, 0, 0, 2, -0.04, -0.04, 0.0, 0.04, 0.04, 0.0]
    transform = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0.15, 0.15, 0.0, 0.5, 0, 0, 0]
    ink = view_ink({"name": "b", "outline": outline, "polylines": in_model, "transform": transform})
    assert ink.space == "transformed"
    assert (ink.segments[0].x0, ink.segments[0].y1) == pytest.approx((0.13, 0.17))
    lost = view_ink({"name": "c", "outline": outline, "polylines": in_model})
    assert lost.space == "unresolved"


def test_an_unresolved_view_is_a_gating_finding_not_a_silent_skip():
    in_model = [0, 0, 0, 0, 0, 1, 0, 0, 2, -0.04, -0.04, 0.0, 0.04, 0.04, 0.0]
    findings = audit_dump(_dump(views=[_view("lost", (0.1, 0.1, 0.2, 0.2), polylines=in_model)]))
    unresolved = [f for f in findings if f.kind == "view-geometry-unresolved"]
    assert len(unresolved) == 1 and severity(unresolved[0]) is FindingSeverity.GATING


def test_apply_transform_uses_row_vectors_scale_and_translation():
    quarter_turn = [0, 1, 0, -1, 0, 0, 0, 0, 1, 0.1, 0.2, 0.0, 2.0, 0, 0, 0]
    assert apply_transform(quarter_turn, 0.01, 0.0, 0.0) == pytest.approx((0.1, 0.22))


def test_a_balloon_is_its_single_rendered_circle():
    arc = [0, 0, 0, 0, 0.105, 0.2, 0.0, 0.105, 0.2, 0.0, 0.1, 0.2, 0.0, 0.0, 0.0, 1.0, 1.0]
    assert balloon_circle({"arcs": [arc]}) == pytest.approx((0.1, 0.2, 0.005))
    assert balloon_circle({"arcs": [arc, arc]}) is None


def test_the_audit_ships_in_report_mode_until_the_fleet_report_is_triaged():
    """Main's gating decision (a), 2026-09-25: REPORT first, then GATE."""
    assert LAYOUT_AUDIT_MODE is LayoutAuditMode.REPORT


def test_sheet_model_measures_the_glyph_advance_from_exact_item_widths():
    model = sheet_model(_holes_sheet(HB2_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK))
    # '2X ' / '4X ' span 6.72 mm, ' 3.45 ' 11.64 mm, ' 8-32 UNC - 2B ' 32.9 mm,
    # all at 3.5 mm height; token items are excluded.
    assert model.advance == pytest.approx(median_ratio(), rel=1e-3)


def median_ratio():
    from statistics import median

    widths = [
        (0.185938 - 0.179215) / 3,
        (0.202854 - 0.191216) / 6,
        (0.247938 - 0.241215) / 3,
        (0.264854 - 0.253216) / 6,
        (0.20748 - 0.174589) / 15,
        (0.26948 - 0.236589) / 15,
    ]
    return median(w / 0.0035 for w in widths)


# --------------------------------------------------------------------------
# run_layout_audit: the cached report, fail-loud faults, GATE on gating findings
# --------------------------------------------------------------------------


def _patch_collect(monkeypatch, result):
    import _drawing_layout_audit as live

    def collect(*_args, **_kwargs):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(live, "collect_sheet_dumps", collect)
    return live


def _run(live, mode, report):
    live.run_layout_audit(
        object(),
        stem="fixture",
        report=report,
        sheet_layouts={},
        is_pictorial=lambda _o: False,
        mode=mode,
    )


def test_a_collector_fault_fails_loud_in_every_mode(monkeypatch, tmp_path):
    """Main's rider: a fault that skipped a sheet would silently under-count
    the fleet report, so REPORT fails the drawing too, and writes no report."""
    live = _patch_collect(monkeypatch, RuntimeError("COM went away"))
    for mode in LayoutAuditMode:
        with pytest.raises(RuntimeError, match="COM went away"):
            _run(live, mode, tmp_path / f"{mode.value}.json")
    assert not list(tmp_path.iterdir())


def test_report_mode_writes_every_finding_and_dump_and_gate_mode_raises(monkeypatch, tmp_path):
    import json

    sheet = _holes_sheet(HB2_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK)
    live = _patch_collect(monkeypatch, [sheet])
    report = tmp_path / "reports" / "fixture.json"
    _run(live, LayoutAuditMode.REPORT, report)
    content = json.loads(report.read_text(encoding="utf-8"))
    assert content["mode"] == "report"
    assert content["sheets"] == [sheet]
    assert content["summary"]["findings"]["leader-through-text"] == 1
    assert content["summary"]["gating"] >= 1
    assert {f["kind"] for f in content["findings"]} >= {"leader-through-text"}
    # The cached report replays to the same findings the seat saw.
    assert [f.kind for f in audit_dump(content["sheets"][0])] == [
        f["kind"] for f in content["findings"]
    ]
    with pytest.raises(RuntimeError, match="leader-through-text"):
        _run(live, LayoutAuditMode.GATE, tmp_path / "gate.json")
    assert (tmp_path / "gate.json").is_file()  # written before the gate fails


def test_gate_mode_passes_a_sheet_with_only_advisories(monkeypatch, tmp_path):
    live = _patch_collect(monkeypatch, [_holes_sheet(HB4_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK)])
    findings = audit_dump(_holes_sheet(HB4_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK))
    assert all(severity(f) is FindingSeverity.ADVISORY for f in findings)
    _run(live, LayoutAuditMode.GATE, tmp_path / "fixture.json")


def test_the_audit_span_carries_per_class_counts(monkeypatch, tmp_path):
    import _telemetry

    spans = []
    real_span = _telemetry.span

    def recording_span(name, **attrs):
        context = real_span(name, **attrs)

        class Recorder:
            def __enter__(self):
                self.span = context.__enter__()
                spans.append((name, self))
                self.attributes = {}
                original = self.span.set_attribute

                def set_attribute(key, value):
                    self.attributes[key] = value
                    return original(key, value)

                self.span.set_attribute = set_attribute
                return self.span

            def __exit__(self, *exc):
                return context.__exit__(*exc)

        return Recorder()

    live = _patch_collect(monkeypatch, [_holes_sheet(HB2_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK)])
    monkeypatch.setattr(live._telemetry, "span", recording_span)
    _run(live, LayoutAuditMode.REPORT, tmp_path / "fixture.json")
    [(name, recorder)] = spans
    assert name == "layout.audit fixture"
    assert recorder.attributes["findings.leader-through-text"] == 1
    assert recorder.attributes["sheets"] == 1


# hb-render-5 (375bf2aad, supports' fix): the cross-tap cut to three rows and
# lowered 10 mm clear of the spring block (dt-logs/hb-render-5 line 54).
HB5_CROSS_TAP = (
    "MHA-132",
    [
        (0.3295759581969177, 0.09824798610154864, 0.3408763902127743, 0.11161215219646692),
        (0.3289240418030824, 0.09747701389845134, 0.3295759581969177, 0.09824798610154864),
        (0.3408763902127743, 0.11161215219646692, 0.23071110978722575, 0.11161215219646692),
    ],
    [
        ("4X ", 0.2624042181670666, 0.12283159763785084),
        ("<MOD-DIAM>", 0.26912713501602414, 0.12277812546119099),
        (" 4.04 ", 0.2744055724143982, 0.12283159763785084),
        ("<HOLE-DEPTH>", 0.2860430719703436, 0.12277812546119099),
        (" 48 MIN", 0.2910436967760325, 0.12283159763785084),
        ("THRU BOTH WALLS, SINGLE CONTINUOUS THREAD", 0.23071110978722575, 0.1172218752955087),
        (" 10-32 UNF - 2B ", 0.2590618392825127, 0.1116656253044494),
        ("<HOLE-DEPTH>", 0.29300697878003124, 0.11161215312778955),
        (" 46.00", 0.2980076035857201, 0.1116656253044494),
    ],
)


def test_hb_render_5_fixed_cross_tap_passes_the_block_rules():
    """Negative control: supports' fix keeps three rows, 10 mm under the
    spring block, so neither block rule nor the clearance rule fires."""
    findings = audit_dump(
        _holes_sheet(HB4_TOP_LABEL, HB2_PEDESTAL, HB2_BLOCK, HB4_SPRING, HB5_CROSS_TAP)
    )
    assert not [
        f
        for f in findings
        if f.kind in ("merged-blocks", "tall-block", "text-clearance", "text-separation")
        and "MHA-132" in f.a + f.b
    ]


def test_every_drawing_task_targets_and_caches_its_layout_report():
    """Main's rider: the report rides the remote cache, so a leaf restored
    from cache still carries its findings -- it is a declared target of every
    drawing task and one of the outputs the cache stores and restores. It is
    not a release output (cut_release stages ``spec.outputs`` only)."""
    import importlib.util
    from pathlib import Path

    from _drawing_registry import DRAWINGS, LAYOUT_REPORT_DIR

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("dodo", root / "dodo.py")
    dodo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dodo)
    tasks = {task["name"]: task for task in dodo.task_drawing()}
    assert LAYOUT_REPORT_DIR == root / "cad" / "out" / "reports" / "layout-audit"
    for drawing in DRAWINGS:
        report = drawing.layout_report.resolve()
        assert report.parent == LAYOUT_REPORT_DIR.resolve()
        assert str(report) in tasks[drawing.name]["targets"]
        assert report in dodo._drawing_cache_outputs(drawing.name)
        assert report not in drawing.outputs.values()
