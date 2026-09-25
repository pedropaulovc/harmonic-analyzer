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
    annotation_geometry,
    arrowhead_segments,
    audit_dump,
    balloon_circle,
    find_merged_blocks,
    glyph_count,
    ink_edges,
    match_ink,
    row_boxes,
    severity,
    sheet_model,
    view_edges,
)
from _layout_geometry import DEFAULT_TEXT_TOUCH_TOL_M, Box, Segment

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


def _edges(*segments, width=0.00025, dashed=0):
    """PDF strokes as the collector dumps them: [x0, y0, x1, y1, width, dashed]."""
    return [[*segment, width, dashed] for segment in segments]


def _box_edges(x0, y0, x1, y1):
    return _edges((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0))


def _printed(annotations, advance=0.6):
    """An ideal PDF of fixture COM text: one text object per item, its glyphs
    from the item's lower-left, symbols printing as paths (no object)."""
    from _layout_audit import ink_key, text_items

    spans = []
    for annotation in annotations:
        for item in text_items(annotation.get("display") or {}):
            if not ink_key(item.text) or "<" in item.text:
                continue
            width = advance * item.height * len(item.text.strip())
            spans.append([item.text.strip(), item.x, item.y, item.x + width, item.y + item.height])
    return spans


def _dump(*, views=(), sheet_annotations=(), tables=(), spans=(), strokes=(), print_rest=True):
    """A sheet dump; with ``strokes`` or ``spans`` it is a printed page. Text
    ``spans`` does not give prints where the fixture's COM items say, unless
    ``print_rest`` is off."""
    ink = {}
    if strokes or spans:
        from _layout_audit import ink_key

        annotations = [a for view in views for a in view.get("annotations", ())] + list(sheet_annotations)
        given = {ink_key(str(span[0])) for span in spans}
        rest = [span for span in _printed(annotations) if ink_key(span[0]) not in given] if print_rest else []
        printed = [*spans, *rest]
        ink = {"ink": {"spans": [list(span) for span in printed], "strokes": [list(stroke) for stroke in strokes]}}
    return {**ink, **{
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
        "read_errors": {},
    }}


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
    outline edge. Model edges are the PDF's 0.25 mm solid strokes."""
    # A single vertical model edge of the right view at x = 0.130.
    right_view = _view("right", (0.128, 0.078, 0.170, 0.162))
    callout = _hole_callout(
        "ADJ",
        [(0.080, 0.100, 0.100, 0.118), (0.100, 0.118, 0.140, 0.118)],
        [("ADJUSTER ENTRY", 0.100, 0.118)],
    )
    front = _view("front", (0.060, 0.080, 0.100, 0.160), [callout])
    printed = [["ADJUSTER ENTRY", 0.1002, 0.1189, 0.1400, 0.1222]]  # runs the width of its shoulder
    findings = audit_dump(
        _dump(views=[front, right_view], strokes=_edges((0.130, 0.080, 0.130, 0.160)), spans=printed)
    )
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
    six = _dim("RightDepth", "6.0", 0.165, 0.120)
    right = _view("right", (x0 - 0.001, y0 - 0.001, x1 + 0.001, y1 + 0.001), [six])
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
    return _dump(views=[plan, right, front], strokes=_box_edges(x0, y0, x1, y1))


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
    pad = 0.003  # GetOutline pads the body with whitespace
    dump = _dump(
        views=[
            _view("plan", (0.020, 0.190, 0.120, 0.250), by_view["plan"]),
            _view("front", (0.060, 0.090, 0.118, 0.170), by_view["front"]),
            _view("right", (x0 - pad, y0 - pad, x1 + pad, y1 + pad), by_view["right"]),
        ],
        strokes=_box_edges(x0, y0, x1, y1),
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
# primitives
# --------------------------------------------------------------------------


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
    from pathlib import Path

    live.run_layout_audit(
        object(),
        stem="fixture",
        pdf=Path("fixture.pdf"),
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
    recorded = dict(spans)
    assert list(recorded) == ["layout.audit fixture", "layout.findings"]
    assert recorded["layout.audit fixture"].attributes["findings.leader-through-text"] == 1
    assert recorded["layout.audit fixture"].attributes["sheets"] == 1
    assert recorded["layout.findings"].attributes["findings.leader-through-text"] == 1
    assert recorded["layout.findings"].attributes["findings_s"] >= 0.0


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


# --------------------------------------------------------------------------
# PDF ink: where text and model edges printed
# --------------------------------------------------------------------------
#
# Real records from the d09c2b9eb calibration leaves (integ 06b840e49): each
# drawing's layout dump replayed against its own exported PDF page.


def test_an_arrowhead_base_lies_along_its_direction_from_the_tip():
    """``GetArrowHeadAtIndex2``'s direction points from the tip back along the
    shaft. pinion-bracket's 28.00 (ArborBoreCz) prints its lower arrowhead's
    base at y 125.55 mm, above the tip at 122.00: drawn the other way, the
    triangle landed inside the section label "B" beneath it."""
    lower = [0.24, 0.122, -0.0088, 0.0, 1.0, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0]
    upper = [0.24, 0.178, -0.0088, -0.0, -1.0, -0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0]
    tip, *base = ((s.x0, s.y0) for s in arrowhead_segments(lower))
    assert tip == pytest.approx((0.24, 0.122))
    assert [v for point in sorted(base) for v in point] == pytest.approx([0.239619, 0.125556, 0.240381, 0.125556])
    assert {round(s.y0, 6) for s in arrowhead_segments(upper)} == {0.178, 0.174444}


def test_ink_matching_is_one_to_one_nearest_first_and_same_string_only():
    """Six "13.12"s on one sheet must not all claim one printed run."""
    h = 0.0035
    near_left = TextItem("13.12", 0.1000, 0.1000, h)
    near_right = TextItem("13.12", 0.1015, 0.1000, h)
    stranded = TextItem("13.12", 0.3000, 0.1000, h)
    other_string = TextItem("8.42", 0.1000, 0.1000, h)
    spans = [
        _ink_span("13.12", 0.1012, 0.0991),
        _ink_span("13.12", 0.1003, 0.0991),
        _ink_span("13.12", 0.3100, 0.0991),  # 10 mm off: outside the window
    ]
    matched = match_ink(
        [("L", near_left), ("R", near_right), ("S", stranded), ("O", other_string)], spans
    )
    assert matched["L"].xmin == pytest.approx(0.1003)
    assert matched["R"].xmin == pytest.approx(0.1012)
    assert "S" not in matched and "O" not in matched


def _ink_span(text, x, y, width=0.008, height=0.0033):
    from _layout_audit import InkSpan, ink_key

    return InkSpan(ink_key(text), Box(x, y, x + width, y + height))


def test_printed_glyph_boxes_replace_com_boxes_and_a_symbol_follows_its_row():
    """The row box is the printed glyphs', not COM's row estimate (which ran
    up to 21 mm wide on a dimension). ``<MOD-DIAM>`` prints as a path, so it
    is boxed from COM and shifted by the offset its printed neighbour shows."""
    h = 0.0035
    dim = _dim("Bore", "", 0, 0)
    dim["display"]["texts"] = [
        {"t": "<MOD-DIAM>", "pos": [0.1000, 0.1500, 0.0], "h": h},
        {"t": " 3.26", "pos": [0.1027, 0.1500, 0.0], "h": h},
    ]
    printed = Box(0.1035, 0.1491, 0.1120, 0.1524)
    geometry = annotation_geometry(dim, owner="v", advance=0.6, ink={1: printed})
    [row] = geometry.text_boxes
    assert (row.xmin, row.ymin, row.xmax, row.ymax) == pytest.approx((0.1000, 0.1491, 0.1120, 0.1524))
    assert geometry.exact


def test_com_text_the_pdf_never_printed_gates_but_symbols_do_not():
    """The audit is blind wherever COM and the PDF disagree, so an unmatched
    string is a gating finding. A symbol-only item (``<MOD-DIAM>``) prints as
    a path and is exempt."""
    printed = _dim("Printed", "12.0", 0.100, 0.150)
    lost = _dim("Lost", "7.5", 0.150, 0.150)
    symbol = _dim("Symbol", "<MOD-DIAM>", 0.180, 0.150)
    dump = _dump(
        views=[_view("v", (0.05, 0.05, 0.25, 0.25), [printed, lost, symbol])],
        spans=[["12.0", 0.1002, 0.1491, 0.1060, 0.1524]],
        print_rest=False,
    )
    unmatched = [f for f in audit_dump(dump) if f.kind == "text-unmatched"]
    assert [(f.a, f.b) for f in unmatched] == [("Lost", "7.5")]
    assert severity(unmatched[0]) is FindingSeverity.GATING


def test_model_edges_are_solid_quarter_millimetre_strokes_owned_by_the_smallest_view():
    """Model edges print 0.25 mm solid black; annotation ink is 0.18 mm and
    hidden lines are dashed. An edge belongs to the innermost outline holding
    it (a detail drawn inside its parent's box), and none outside every view."""
    dump = {
        "ink": {
            "strokes": [
                [0.12, 0.12, 0.13, 0.12, 0.00025, 0],  # parent edge
                [0.15, 0.15, 0.16, 0.15, 0.00025, 0],  # inside the detail
                [0.12, 0.13, 0.13, 0.13, 0.00018, 0],  # annotation line
                [0.12, 0.14, 0.13, 0.14, 0.00025, 1],  # hidden line
                [0.30, 0.30, 0.31, 0.30, 0.00025, 0],  # in no view
            ]
        }
    }
    edges = ink_edges(dump)
    assert len(edges) == 3
    owned = view_edges(edges, [("parent", Box(0.10, 0.10, 0.20, 0.20)), ("detail", Box(0.14, 0.14, 0.17, 0.17))])
    assert [(e.x0, e.y0) for e in owned["parent"]] == [(0.12, 0.12)]
    assert [(e.x0, e.y0) for e in owned["detail"]] == [(0.15, 0.15)]


# cone-tip-block section A-A: GetLineInfo answers (0, -8)..(0, 8) mm -- the
# view's model space -- for a cutting line printed at x 72 mm.
CTB_SECTION_A = {
    "label": "A",
    "line": [0.0, -0.008, 0.0, 0.0, 0.008, 0.0],
    "arrows": [0.072, 0.209, 0.0, 0.084, 0.209, 0.0, 0.072, 0.241, 0.0, 0.084, 0.241, 0.0],
    "texts": [0.0855346, 0.2138229, 0.0, 0.0855346, 0.2458229, 0.0],
    "text_height": 0.00635,
}
CTB_SECTION_A_SPANS = [
    ["A", 0.0862235, 0.2077981, 0.0920824, 0.2139703],
    ["A", 0.0862235, 0.2397982, 0.0920824, 0.2459704],
]


def test_a_section_line_runs_between_its_arrow_tails_with_its_printed_labels():
    view = _view("Drawing View2", (0.051412, 0.207412, 0.092588, 0.242588), sections=[CTB_SECTION_A])
    model = sheet_model(_dump(views=[view], spans=CTB_SECTION_A_SPANS))
    [section] = [a for a in model.geometry.annotations if a.kind == "section-line"]
    [line] = [s for s in section.segments if s.role == "line"]
    assert (line.x0, line.y0, line.x1, line.y1) == pytest.approx((0.072, 0.209, 0.072, 0.241))
    assert [(b.xmin, b.ymin, b.xmax, b.ymax) for b in section.text_boxes] == [
        tuple(span[1:]) for span in CTB_SECTION_A_SPANS
    ]
    assert model.unmatched == ()
    lost = sheet_model(_dump(views=[view], spans=CTB_SECTION_A_SPANS[:1]))
    assert lost.unmatched == (("section-line A", "A"),)


# cone-swing-platform, Drawing View2: the 6.76 hole callout's leader runs
# past its arrow tip on the hole's edge to the hole's centre, where 195.09's
# extension line and section line A both pass.
CSP_VIEW2 = (0.1594442, 0.1285735, 0.2005558, 0.2514265)
CSP_DRILL = {
    "type": 4,
    "name": "RD1",
    "visible": 1,
    "display": {
        "lines": [
            _line(0.1773666, 0.1360656, 0.1884146, 0.1041951),
            _line(0.1762602, 0.1392573, 0.1773666, 0.1360656),
            _line(0.1884146, 0.1041951, 0.2399979, 0.1041951),
        ],
        "arrows": [[0.1773666, 0.1360656, -0.0015875, 0.3275313, -0.9448403, 0.0, 0.003556, 0.000762, 0.0, 0.0, -0.0, -1.0]],
        "texts": [
            {"t": "DRILL ", "pos": [0.1900021, 0.1042486, 0.0], "h": 0.0035},
            {"t": "<MOD-DIAM>", "pos": [0.2029618, 0.1041951, 0.0], "h": 0.0035},
            {"t": " 6.76 THRU ALL", "pos": [0.2082403, 0.1042486, 0.0], "h": 0.0035},
        ],
    },
    "dim": {"hole_callout": True},
}
CSP_POST_MOUNT = _dim(
    "PostMountEastZ",
    " 195.09 ",
    0.1215951,
    0.1722219,
    lines=[
        (0.1737778, 0.2352052, 0.129, 0.2352052),
        (0.1807524, 0.1376615, 0.129, 0.1376615),
        (0.13, 0.2352052, 0.13, 0.1777781),
        (0.13, 0.1376615, 0.13, 0.1722219),
    ],
)
CSP_SECTION_A = {
    "label": "A",
    "arrows": [0.1574442, 0.1376615, 0.0, 0.1574442, 0.1256615, 0.0, 0.2025558, 0.1376615, 0.0, 0.2025558, 0.1256615, 0.0],
    "texts": [0.1547156, 0.1235998, 0.0, 0.1998272, 0.1235998, 0.0],
    "text_height": 0.00635,
}
CSP_DETAIL_B = [1.0, -1.0, 0.1768134, 0.1406615, 0.0, 0.1828134, 0.1406615, 0.0, 0.1828134, 0.1406615, 0.0,
                3.0, 0.1849758, 0.1445509, -0.0, 0.00635, 0.0]
CSP_DETAIL_B_SPAN = ["B", 0.1860114, 0.1383209, 0.1896602, 0.1444931]
# Detail View B: the C'BORE SLOT note's leader crosses 11.00's dimension line
# mid-span -- the one true leader crossing on the sheet.
CSP_SLOT_NOTE = {
    "type": 6,
    "name": "DetailItem375",
    "visible": 1,
    "leaders": [[0.1204851, 0.0455793, -0.0, 0.0940041, 0.0504458, 0.0]],
    "display": {
        "lines": [_line(0.1202019, 0.04615, 0.0940041, 0.0504458)],
        "arrows": [[0.0940041, 0.0504458, 0.0, 0.9868211, -0.1618151, -0.0, 0.003556, 0.000762, 1.0, 0.0, 0.0, 1.0]],
        "texts": [
            {"t": "<MOD-DIAM>", "pos": [0.121, 0.0435, 0.0], "h": 0.0025},
            {"t": "7.94 END MILL C'BORE SLOT", "pos": [0.1247703, 0.0435, 0.0], "h": 0.0025},
            {"t": "FROM UNDERSIDE", "pos": [0.121, 0.04, 0.0], "h": 0.0025},
        ],
    },
    "note": {"text": "<MOD-DIAM>7.94 END MILL C'BORE SLOT\r\nFROM UNDERSIDE", "balloon": False},
}
CSP_TIP_SLOT = _dim(
    "TipSlotZ",
    " 11.00 ",
    0.1135,
    0.0567219,
    lines=[
        (0.0805, 0.055, 0.1145, 0.055),
        (0.096256, 0.033, 0.1145, 0.033),
        (0.1277236, 0.0567219, 0.1135, 0.0567219),
        (0.1135, 0.0567219, 0.1135, 0.055),
        (0.1135, 0.055, 0.1135, 0.033),
    ],
)


def _cone_swing_platform():
    view2 = _view(
        "Drawing View2",
        CSP_VIEW2,
        [CSP_DRILL, CSP_POST_MOUNT],
        sections=[CSP_SECTION_A],
        detail_circles_info=CSP_DETAIL_B,
    )
    detail = _view("Detail View B (2 : 1)", (0.049112, 0.0106121, 0.117888, 0.079388), [CSP_SLOT_NOTE, CSP_TIP_SLOT])
    return _dump(views=[view2, detail], spans=[CSP_DETAIL_B_SPAN])


def test_a_leader_running_past_its_arrow_into_the_hole_crosses_nothing():
    """The crossings on the stretch past the arrow tip are the hole's own
    centre and extension lines; the slot note's leader across 11.00's
    dimension line, 20 mm from its tip, still gates."""
    crossings = [f for f in audit_dump(_cone_swing_platform()) if "crosses" in f.kind]
    assert [(f.kind, f.a.split()[1], f.b.split()[1]) for f in crossings] == [
        ("leader-crosses-line", "DetailItem375", "TipSlotZ")
    ]
    assert severity(crossings[0]) is FindingSeverity.GATING


def test_a_detail_circle_is_no_leader_target_and_its_label_is_the_printed_one():
    """A leader to a feature inside a detail circle must cross the circle.
    The circle's label is boxed from its printed "B" (x 186.0 mm), which
    10.50's dimension line (ending x 185.8) stops short of; the COM estimate
    started at 185.0 and read the line as crossing it."""
    detail = {"type": 4, "name": "Reach", "visible": 1, "display": {
        "lines": [_line(0.1700, 0.1300, 0.1840, 0.1420)], "texts": []}, "dim": {"hole_callout": True}}
    relief = _dim("PivotBearingReliefDia", "10.50", 0.1650, 0.1500, lines=[(0.1794, 0.1411, 0.1858, 0.1411)])
    view = _view("Drawing View2", CSP_VIEW2, [detail, relief], detail_circles_info=CSP_DETAIL_B)
    findings = audit_dump(_dump(views=[view], spans=[CSP_DETAIL_B_SPAN]))
    assert not [f for f in findings if "detail-circle" in f.a + f.b]
    estimated = audit_dump(_dump(views=[view]))
    assert [f.kind for f in estimated if "detail-circle" in f.a + f.b] == ["text-on-line"]


def test_a_leader_across_a_section_cutting_line_gates():
    """Main's ruling: gating -- the MHA-025 finish leader was moved off its
    A-A line for exactly this."""
    callout = _hole_callout(
        "C", [(0.160, 0.120, 0.190, 0.150), (0.190, 0.150, 0.230, 0.150)], [("THRU", 0.190, 0.1502)]
    )
    view = _view("v", CSP_VIEW2, [callout], sections=[CSP_SECTION_A])
    [finding] = [f for f in audit_dump(_dump(views=[view])) if "crosses" in f.kind]
    assert finding.kind == "leader-crosses-section-line"
    assert severity(finding) is FindingSeverity.GATING


def test_text_beside_a_view_is_measured_against_its_printed_edges_not_its_padded_outline():
    """knife-mount's Ra 0.8 (owned by View1) ends 2 mm inside View2's
    GetOutline but 1.5 mm clear of its first printed edge."""
    outline = (0.200412, 0.105046, 0.239588, 0.174954)
    beside = _note("Ra", "Ra 0.8", (0.1805, 0.1194, 0.2044, 0.1259))
    over = _note("Over", "Ra 0.8", (0.1845, 0.1394, 0.2084, 0.1459))
    views = [_view("View1", (0.085, 0.105, 0.145, 0.175), [beside, over]), _view("View2", outline)]
    findings = audit_dump(_dump(views=views, strokes=_box_edges(0.2059, 0.1070, 0.2380, 0.1730)))
    assert [f.a for f in findings if f.kind == "text-on-view"] == ["note Over 'Ra 0.8'"]
    padded = audit_dump(_dump(views=views))
    assert sorted(f.a for f in padded if f.kind == "text-on-view") == ["note Over 'Ra 0.8'", "note Ra 'Ra 0.8'"]


def test_a_general_note_is_no_tall_callout_but_a_leadered_one_is():
    """knife-mount's 11-row process note is a text block by design; the
    same rows at the end of a leader stop reading as one label."""
    h = 0.0035
    rows = [{"t": f"ROW {i}", "pos": [0.020, 0.070 - i * 0.0045, 0.0], "h": h} for i in range(11)]
    general = {"type": 6, "name": "Process", "visible": 1, "display": {"texts": rows}, "note": {"balloon": False}}
    leadered = {**general, "name": "Callout", "leaders": [[0.020, 0.075, 0.0, 0.050, 0.090, 0.0]]}
    findings = audit_dump(_dump(views=[_view("v", (0.1, 0.1, 0.2, 0.2), [general, leadered])]))
    assert [f.a for f in findings if f.kind == "tall-block"] == ["note Callout"]


def test_one_line_through_a_two_row_dimension_is_one_finding():
    """knife-mount's Ø12.00 / THRU, both rows crossed by 29.37's dimension line."""
    bore = _dim("BoreDia", "", 0, 0)
    bore["display"]["texts"] = [
        {"t": "<MOD-DIAM>12.00", "pos": [0.0585, 0.1555, 0.0], "h": 0.0035},
        {"t": "THRU", "pos": [0.0615, 0.1500, 0.0], "h": 0.0035},
    ]
    height = _dim("BlockHeight", "29.37", 0.0590, 0.1380, lines=[(0.063, 0.1694, 0.063, 0.1428)])
    findings = audit_dump(_dump(views=[_view("v", (0.04, 0.13, 0.09, 0.18), [bore, height])]))
    assert [(f.a.split()[1], f.b.split()[1]) for f in findings if f.kind == "text-on-line"] == [
        ("BoreDia", "BlockHeight")
    ]


def test_a_pdf_page_dumps_its_text_and_only_its_black_stroked_lines():
    """The frame and title block print grey and arrowheads/section arrows are
    filled: neither is a line the audit measures."""
    from _pdf_ink import page_ink
    from _pdf_ink import PageInk, Span, Stroke

    def stroke(y, *, rgb=(0, 0, 0), filled=False, stroked=True, dashed=False):
        return Stroke(0.1, y, 0.2, y, 0.00025, rgb, dashed, filled, stroked)

    page = PageInk(
        width=SHEET_W,
        height=SHEET_H,
        glyphs=(),
        spans=(Span("6.0", 0.1, 0.1, 0.106, 0.1033, ()),),
        strokes=(
            stroke(0.10),
            stroke(0.11, dashed=True),
            stroke(0.12, rgb=(128, 128, 128)),
            stroke(0.13, filled=True),
            stroke(0.14, stroked=False, filled=True),
        ),
    )
    ink = page_ink(page)
    assert ink["spans"] == [["6.0", 0.1, 0.1, 0.106, 0.1033]]
    assert ink["strokes"] == [[0.1, 0.1, 0.2, 0.1, 0.00025, 0], [0.1, 0.11, 0.2, 0.11, 0.00025, 1]]


# --------------------------------------------------------------------------
# codex review of 6bab30da9
# --------------------------------------------------------------------------


def test_a_run_mixing_a_symbol_and_text_keeps_the_symbol_in_its_box():
    """``<MOD-DIAM>12.00`` prints "12.00" as text and "Ø" as a path: the box
    reaches back to the run's COM start, where the symbol is."""
    dim = _dim("Bore", "<MOD-DIAM>12.00", 0.0585, 0.1545)
    printed = Box(0.0645, 0.1556, 0.0753, 0.1592)
    geometry = annotation_geometry(dim, owner="v", advance=0.6, ink={0: printed})
    [row] = geometry.text_boxes
    assert (row.xmin, row.xmax) == pytest.approx((0.0585, 0.0753))
    trailing = _dim("Depth", "6.9<HOLE-DEPTH>", 0.100, 0.100)
    [row] = annotation_geometry(
        trailing, owner="v", advance=0.6, ink={0: Box(0.1005, 0.1009, 0.1060, 0.1042)}
    ).text_boxes
    assert row.xmax == pytest.approx(0.1060 + 0.6 * 0.0035)


def test_hidden_and_template_text_neither_claims_printed_text_nor_goes_unmatched():
    visible = _dim("Visible", "12.0", 0.1000, 0.1500)
    hidden = _dim("Hidden", "12.0", 0.1001, 0.1500)
    hidden["visible"] = 3
    template = _note("Template", "", (0.003, 0.03, 0.009, 0.038), owner_type=2)
    template["display"] = {"texts": [{"t": "REV", "pos": [0.005, 0.030, 0.0], "h": 0.0035}]}
    dump = _dump(
        views=[_view("v", (0.05, 0.05, 0.25, 0.25), [hidden, visible])],
        sheet_annotations=[template],
        spans=[["12.0", 0.10012, 0.15093, 0.1060, 0.1542]],
    )
    model = sheet_model(dump)
    assert model.unmatched == ()
    [box] = [a.text_boxes[0] for a in model.geometry.annotations if "Visible" in a.label]
    assert box.xmin == pytest.approx(0.10012)


def test_two_printed_leadered_notes_stacked_tight_merge():
    """A note matched to its PDF text is exact, and still a callout."""
    h = 0.0035

    def leadered(name, y):
        note = {
            "type": 6,
            "name": name,
            "visible": 1,
            "leaders": [[0.100, y, 0.0, 0.080, y - 0.010, 0.0]],
            "display": {"texts": [{"t": name, "pos": [0.100, y, 0.0], "h": h}]},
            "note": {"balloon": False},
        }
        return note, [name, 0.1002, y + 0.0009, 0.1300, y + 0.0042]

    upper, upper_ink = leadered("UPPER", 0.1500)
    lower, lower_ink = leadered("LOWER", 0.1450)
    dump = _dump(views=[_view("v", (0.02, 0.02, 0.07, 0.07), [upper, lower])], spans=[upper_ink, lower_ink])
    assert [f.kind for f in audit_dump(dump) if f.kind == "merged-blocks"] == ["merged-blocks"]


def test_pdf_arcs_are_the_curve_not_its_control_polygon():
    from _pdf_ink import bezier_points

    k = 0.5522847498  # quarter-circle cubic, 30 mm radius
    r = 0.030
    points = bezier_points((r, 0.0), (r, k * r), (k * r, r), (0.0, r))
    assert points[0] == (r, 0.0) and points[-1] == pytest.approx((0.0, r))
    assert all(abs((x * x + y * y) ** 0.5 - r) < 1e-5 for x, y in points)


def _fake_drawing(monkeypatch, *, sheet_names, views, pages):
    import _drawing_layout_audit as live

    class Doc:
        def GetSheetNames(self):  # noqa: N802 - COM name
            if isinstance(sheet_names, Exception):
                raise sheet_names
            return sheet_names

        def GetViews(self):  # noqa: N802 - COM name
            return views

    monkeypatch.setattr(live, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(live, "read_pdf_ink", lambda _pdf: pages)
    adapter = type("Adapter", (), {"currentModel": Doc()})()
    return live, adapter


def test_the_collector_fails_loud_rather_than_audit_no_sheet(monkeypatch, tmp_path):
    """A refused GetSheetNames/GetViews used to read as an empty drawing and
    cache a clean zero-sheet report."""
    from pathlib import Path

    kwargs = {"stem": "x", "pdf": Path("x.pdf"), "sheet_layouts": {}, "is_pictorial": lambda _o: False}
    live, adapter = _fake_drawing(monkeypatch, sheet_names=RuntimeError("RPC"), views=(), pages=[object()])
    with pytest.raises(RuntimeError, match="RPC"):
        live.collect_sheet_dumps(adapter, **kwargs)
    live, adapter = _fake_drawing(monkeypatch, sheet_names=("Sheet1",), views=(), pages=[object()])
    with pytest.raises(RuntimeError, match=r"dumped sheets \[\], drawing has \['Sheet1'\]"):
        live.collect_sheet_dumps(adapter, **kwargs)
    live, adapter = _fake_drawing(monkeypatch, sheet_names=("Sheet1", "Sheet2"), views=(), pages=[object()])
    with pytest.raises(RuntimeError, match="2 sheet"):
        live.collect_sheet_dumps(adapter, **kwargs)


def test_stacked_leadered_balloons_are_not_merged_callouts():
    """Codex on 9aaa829d6: admitting exact (PDF-matched) leadered notes as
    callouts must not admit BOM balloons, which are leadered note circles."""

    def balloon(name, cy):
        arc = [0, 0, 0, 0, 0.105, cy, 0.0, 0.105, cy, 0.0, 0.1, cy, 0.0, 0.0, 0.0, 1.0, 1.0]
        return {
            "type": 6,
            "name": name,
            "visible": 1,
            "leaders": [[0.095, cy, 0.0, 0.080, cy - 0.010, 0.0]],
            "display": {"arcs": [arc], "texts": [{"t": name, "pos": [0.099, cy - 0.001, 0.0], "h": 0.0035}]},
            "note": {"balloon": True, "text": name},
        }

    dump = _dump(
        views=[_view("v", (0.02, 0.02, 0.07, 0.07), [balloon("1", 0.150), balloon("2", 0.1385)])],
        spans=[["1", 0.0992, 0.1491, 0.1010, 0.1524], ["2", 0.0992, 0.1376, 0.1010, 0.1409]],
    )
    findings = audit_dump(dump)
    assert not [f for f in findings if f.kind == "merged-blocks"]
    assert {a.kind for a in sheet_model(dump).geometry.annotations} == {"balloon"}


# --------------------------------------------------------------------------
# Main's C2 review (CHANGES) and rulings, 2026-09-25
# --------------------------------------------------------------------------


def _dim_record(name, lines, arrows, texts):
    """A dimension as the collector dumps it (real d09c2b9eb records below)."""
    return {
        "type": 4,
        "name": name,
        "visible": 1,
        "display": {
            "lines": [[0.0, 0.0, 0.0, 0.0, x0, y0, 0.0, x1, y1, 0.0] for x0, y0, x1, y1 in lines],
            "arrows": [[x, y, 0.0, dx, dy, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0] for x, y, dx, dy in arrows],
            "texts": [{"t": t, "pos": [x, y, 0.0], "h": 0.0035, "ref": 1} for t, x, y in texts],
        },
        "dim": {"hole_callout": False},
    }


# pinion-bracket (d09c2b9eb): in Drawing View2, 4.50 +/-0.10 and 9.0 share
# the x = 71 extension line; in View1, 28.00 runs its dimension line down
# x = 240, the line section arrow B is drawn along.
PB_PIN_SEAT_CZ = _dim_record(
    "PinSeatCz",
    [
        (0.08, 0.126, 0.08, 0.2007219),
        (0.071, 0.123, 0.071, 0.2007219),
        (0.08, 0.1997219, 0.071, 0.1997219),
        (0.071, 0.1997219, 0.0457281, 0.1997219),
    ],
    [(0.08, 0.1997219, -1.0, 0.0), (0.071, 0.1997219, 1.0, 0.0)],
    [(" 4.50 ±0.10 ", 0.0457281, 0.1997219)],
)
PB_DEPTH = _dim_record(
    "Depth",
    [
        (0.071, 0.123, 0.071, 0.2102219),
        (0.089, 0.123, 0.089, 0.2102219),
        (0.071, 0.2092219, 0.06465, 0.2092219),
        (0.071, 0.2092219, 0.089, 0.2092219),
        (0.089, 0.2092219, 0.09535, 0.2092219),
    ],
    [(0.071, 0.2092219, -1.0, 0.0), (0.089, 0.2092219, 1.0, 0.0)],
    [(" 9.0 ", 0.0754743, 0.2092219)],
)
PB_ARBOR_BORE_CZ = _dim_record(
    "ArborBoreCz",
    [
        (0.224, 0.178, 0.241, 0.178),
        (0.22235, 0.122, 0.241, 0.122),
        (0.24, 0.178, 0.24, 0.1537781),
        (0.24, 0.122, 0.24, 0.1482219),
    ],
    [(0.24, 0.178, 0.0, -1.0), (0.24, 0.122, 0.0, 1.0)],
    [(" 28.00 ", 0.2328882, 0.1482219)],
)
PB_SECTION_B = {
    "label": "B",
    "line": [-0.015, -0.007, 0.0, 0.015, -0.007, 0.0],
    "arrows": [0.18, 0.136, 0.0, 0.18, 0.124, 0.0, 0.24, 0.136, 0.0, 0.24, 0.124, 0.0],
    "texts": [0.1778777, 0.1219384, 0.0, 0.2378777, 0.1219384, 0.0],
    "text_height": 0.00635,
}
PB_SPANS = [
    ["28.00", 0.2343213, 0.1491558, 0.2456694, 0.1527211],
    ["B", 0.1783162, 0.11566, 0.1819653, 0.1218322],
    ["B", 0.2383162, 0.11566, 0.2419653, 0.1218322],
    ["9.0", 0.0769961, 0.2101558, 0.0830833, 0.2137211],
    ["4.50±0.10", 0.0471378, 0.2006558, 0.0688295, 0.2042211],
]


def test_a_dimension_splits_into_its_dimension_line_and_extension_lines():
    geometry = annotation_geometry(PB_PIN_SEAT_CZ, owner="v", advance=0.6)
    roles = [
        (s.role, round(s.x0 * 1000, 1), round(s.x1 * 1000, 1)) for s in geometry.segments if s.role != "arrow"
    ]
    assert roles == [
        ("ext-line", 80.0, 80.0),
        ("ext-line", 71.0, 71.0),
        ("dim-line", 80.0, 71.0),
        ("dim-line", 71.0, 45.7),  # the run out to the text parked left
    ]


def test_a_section_arrow_along_a_dimension_line_gates_but_a_shared_extension_line_does_not():
    """Main's collinear ruling: pinion-bracket's section arrow B runs 12 mm
    down 28.00's dimension line. 4.50 +/-0.10 and 9.0 share x = 71 as
    extension line, which is normal drafting."""
    view1 = _view(
        "Drawing View1", (0.189412, 0.101412, 0.230588, 0.198588), [PB_ARBOR_BORE_CZ], sections=[PB_SECTION_B]
    )
    view2 = _view("Drawing View2", (0.04, 0.12, 0.1, 0.215), [PB_PIN_SEAT_CZ, PB_DEPTH])
    findings = audit_dump(_dump(views=[view1, view2], spans=PB_SPANS, print_rest=False))
    along = [f for f in findings if f.kind == "line-on-dimension-line"]
    assert [(f.a, f.b.split()[1]) for f in along] == [("section-line B", "ArborBoreCz")]
    assert along[0].extra["overlap_mm"] == pytest.approx(12.0, abs=0.01)
    assert severity(along[0]) is FindingSeverity.GATING


def test_a_dimension_line_across_a_foreign_extension_line_gates_only_at_text():
    """Main's ruling b: advisory, unless within 0.5 h of either dimension's text."""
    far = _dim_record("Far", [(0.100, 0.150, 0.140, 0.150)], [(0.100, 0.150, 1.0, 0.0)], [("12.0", 0.150, 0.150)])
    near = _dim_record("Near", [(0.100, 0.130, 0.140, 0.130)], [(0.100, 0.130, 1.0, 0.0)], [("8.0", 0.121, 0.1305)])
    crossed = _dim_record(
        "Crossed",
        [(0.120, 0.100, 0.120, 0.170), (0.120, 0.160, 0.180, 0.160)],
        [(0.180, 0.160, -1.0, 0.0)],
        [("30.0", 0.185, 0.160)],
    )
    findings = audit_dump(_dump(views=[_view("v", (0.05, 0.05, 0.25, 0.25), [far, near, crossed])]))
    crossings = {(f.a.split()[1], f.kind, severity(f).value) for f in findings if f.kind.startswith("dim-line")}
    assert crossings == {
        ("Far", "dim-line-crosses-extension", "advisory"),
        ("Near", "dim-line-crosses-extension-at-text", "gating"),
    }


# --------------------------------------------------------------------------
# Arrow and extension line near foreign text (Main's ruling on swing's MHA-092
# round-2 rule). Ink measured off the 287c5cf6a cone-tip-block render, sheet
# mm (C:/src/dt-logs/handoffs/mha092-r2-fixtures.md).
# --------------------------------------------------------------------------


def _mm(*values):
    return tuple(value / 1000.0 for value in values)


def _vertical_dim(name, text, x, low, high, text_box, *, outside=True):
    """A vertical dimension between tips (x, low) and (x, high), its text
    printed in ``text_box`` (mm). Outside arrows point in and carry 6.35 mm
    tails; inside arrows point out."""
    sign = 1.0 if outside else -1.0
    lines = [_mm(x, low, x, high)]
    if outside:
        lines += [_mm(x, low, x, low - 6.35), _mm(x, high, x, high + 6.35)]
    arrows = [(*_mm(x, low), 0.0, -sign), (*_mm(x, high), 0.0, sign)]
    record = _dim_record(name, lines, arrows, [(f" {text} ", *_mm(text_box[0], text_box[1]))])
    return record, [text, *_mm(*text_box)]


def _text_note(name, text, box):
    x0, y0 = _mm(box[0], box[1])
    note = {
        "type": 6,
        "name": name,
        "visible": 1,
        "display": {"texts": [{"t": text, "pos": [x0, y0, 0.0], "h": 0.0035, "ref": 1}]},
        "note": {"text": text, "balloon": False},
    }
    return note, [text, *_mm(*box)]


def _near_text(annotations_and_spans):
    annotations = [a for a, _span in annotations_and_spans]
    spans = [span for _a, span in annotations_and_spans]
    view = _view("v", _mm(20.0, 20.0, 300.0, 270.0), annotations)
    findings = audit_dump(_dump(views=[view], spans=spans, print_rest=False))
    return {
        (f.kind, f.a.split()[1], f.b.split()[1], severity(f).value)
        for f in findings
        if f.kind in ("arrow-near-text", "extension-near-text", "text-on-line")
    }


def test_an_arrow_tail_near_foreign_text_gates():
    """287c: the 15.2's lower outside arrow's tail stood 0.2 mm over the
    ADJUSTER ENTRY note; its head, 3.5 mm off, does not reach. Arrows set
    inside (the fix) carry no tail and clear the note."""
    note = _text_note("adjuster", "ADJUSTER ENTRY", (95.17, 130.98, 131.49, 134.37))
    slit = _vertical_dim("SlitDepth", "15.2", 114.93, 141.39, 164.19, (116.5, 150.0, 122.5, 153.5))
    assert _near_text([note, slit]) == {("arrow-near-text", "SlitDepth", "adjuster", "gating")}
    inside = _vertical_dim("SlitDepth", "15.2", 114.93, 141.39, 164.19, (116.5, 150.0, 122.5, 153.5), outside=False)
    assert _near_text([note, inside]) == set()


def test_an_arrowhead_near_foreign_text_gates():
    """287c: the 5.56's lower arrow ran 0.4 mm from the foot finish's Ra 3.2
    (fixture 2), and the 7.50's left arrow sat on VIEW C's letter. Moving the
    note clears it."""
    heel = _vertical_dim("HeelReliefHt", "5.56", 124.25, 93.90, 102.11, (125.5, 96.2, 131.5, 99.7))
    finish = _text_note("foot", "Ra 3.2", (112.35, 85.94, 123.70, 89.49))
    assert _near_text([heel, finish]) == {("arrow-near-text", "HeelReliefHt", "foot", "gating")}
    moved = _text_note("foot", "Ra 3.2", (62.35, 85.94, 73.70, 89.49))  # 50 mm left, clear of every arrow
    assert _near_text([heel, moved]) == set()

    letter = _text_note("viewC", "C", (64.60, 254.51, 69.17, 259.50))
    slot_x = _dim_record(
        "FlangeSlotX",
        [_mm(72.0, 259.88, 79.5, 259.88), _mm(72.0, 259.88, 65.65, 259.88), _mm(79.5, 259.88, 85.85, 259.88)],
        [(*_mm(72.0, 259.88), -1.0, 0.0), (*_mm(79.5, 259.88), 1.0, 0.0)],
        [(" 7.50 ", *_mm(73.0, 262.0))],
    )
    assert _near_text([letter, (slot_x, ["7.50", *_mm(73.0, 262.0, 79.0, 265.5)])]) == {
        ("arrow-near-text", "FlangeSlotX", "viewC", "gating")
    }


def test_an_arrow_inside_foreign_text_is_one_gating_finding():
    """287c fixture 3: the 10.7's upper arrow landed inside the 3.97's
    tolerance stack. It is ink through text (text-on-line), reported once."""
    stack = _text_note("FlangeSlotW", "3.97", (83.48, 232.58, 102.36, 240.96))
    slot_z = _vertical_dim("FlangeSlotZ", "10.7", 93.90, 215.48, 231.39, (90.17, 221.66, 98.30, 225.04))
    found = _near_text([stack, slot_z])
    assert {(kind, a, b) for kind, a, b, _severity in found} == {("text-on-line", "FlangeSlotW", "FlangeSlotZ")}


def test_an_extension_line_near_foreign_text_is_advisory():
    """Main's ruling: an extension line within 2 mm of another annotation's
    text, not touching it, is advisory; through it is text-on-line."""
    witness = _dim_record(
        "Witness",
        [_mm(150.0, 100.0, 150.0, 140.0), _mm(170.0, 100.0, 170.0, 140.0), _mm(150.0, 138.0, 170.0, 138.0)],
        [(*_mm(150.0, 138.0), 1.0, 0.0), (*_mm(170.0, 138.0), -1.0, 0.0)],
        [(" 20.0 ", *_mm(155.0, 139.0))],
    )
    beside = _text_note("beside", "SIDE", (130.0, 120.0, 148.8, 123.5))
    through = _text_note("through", "CROSS", (165.0, 125.0, 175.0, 128.5))
    found = _near_text(
        [(witness, ["20.0", *_mm(155.0, 139.0, 163.0, 142.5)]), beside, through]
    )
    assert found == {
        ("extension-near-text", "Witness", "beside", "advisory"),
        ("text-on-line", "through", "Witness", "gating"),
    }


def test_only_an_outside_arrow_has_a_tail():
    """Real pinion-bracket records: 9.0's outside arrows carry 6.35 mm tails;
    4.50's inside arrows, whose line runs on to text parked left, carry none."""
    depth = annotation_geometry(PB_DEPTH, owner="v", advance=0.6)
    assert sorted((round(t.x0 * 1000, 2), round(t.x1 * 1000, 2)) for t in depth.arrow_tails) == [
        (71.0, 64.65),
        (89.0, 95.35),
    ]
    assert annotation_geometry(PB_PIN_SEAT_CZ, owner="v", advance=0.6).arrow_tails == ()


def test_the_audit_and_the_placement_checks_share_one_arrow_text_clearance():
    from _layout_audit import find_arrows_near_text, find_extensions_near_text
    from _layout_geometry import ARROW_TEXT_CLEARANCE_M

    assert ARROW_TEXT_CLEARANCE_M == 0.002
    for finder in (find_arrows_near_text, find_extensions_near_text):
        assert finder.__kwdefaults__["clearance"] is ARROW_TEXT_CLEARANCE_M


def test_two_leaders_converging_on_one_landing_are_advisory():
    """cone-gear-shaft (d09c2b9eb): Ra 1.6's leader meets Sec4Dia's dimension
    line 3.7 mm before both arrows land on the shaft's corner. Main's ruling:
    advisory within the last 5 mm."""
    finish = {
        "type": 7,
        "name": "DetailItem352",
        "visible": 1,
        "leaders": [[0.02275, 0.196, 0.0, 0.03035, 0.196, 0.0, 0.0537143, 0.1507938, 0.0]],
        "display": {
            "lines": [_line(0.02275, 0.196, 0.03035, 0.196), _line(0.03035, 0.196, 0.0537143, 0.1507938)],
            "arrows": [
                [0.0537143, 0.1507938, 0.0, -0.4591403, 0.8883638, -0.0, 0.003556, 0.000762, 1.0, 0.0, 0.0, 1.0]
            ],
            "texts": [{"t": "Ra 1.6", "pos": [0.029, 0.1995713, 0.0], "h": 0.0025, "ref": 1}],
        },
    }
    sec4 = _dim_record(
        "Sec4Dia",
        [(0.0833972, 0.1954743, 0.052, 0.1954743), (0.052, 0.1954743, 0.052, 0.1507938)],
        [(0.052, 0.1507938, 0.0, 1.0)],
        [("1.588 ", 0.0585715, 0.1955278)],
    )
    findings = audit_dump(_dump(views=[_view("v", (0.02, 0.14, 0.09, 0.21), [finish, sec4])]))
    crossing = [f for f in findings if "leader" in f.kind and "Sec4Dia" in f.b]
    assert [(f.kind, severity(f).value) for f in crossing] == [("leader-converges-at-landing", "advisory")]


def test_a_clockwise_arc_is_its_own_sweep_not_the_complement():
    """``rotationDir`` CW = 0. Read as CCW, a 30 degree CW arc became its
    330 degree complement: phantom ink across the sheet."""
    import math

    from _layout_audit import arc_segments

    r = 0.010
    start = (r, 0.0)
    end = (r * math.cos(math.radians(-30)), r * math.sin(math.radians(-30)))
    raw = [0, 0, 0, 0, *start, 0.0, *end, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    angles = [math.degrees(math.atan2(s.y0, s.x0)) for s in arc_segments(raw)]
    assert all(-30.0 - 1e-6 <= a <= 1e-6 for a in angles)
    ccw = arc_segments([*raw[:16], 1.0])
    assert max(math.degrees(math.atan2(s.y0, s.x0)) for s in ccw) > 90.0
    variant_true = arc_segments([*raw[:16], -1.0])  # a COM VARIANT_BOOL true
    assert [(s.x0, s.y0) for s in variant_true] == [(s.x0, s.y0) for s in ccw]


def test_a_wide_centred_string_matches_on_its_centre():
    """``GetTextRefPositionAtIndex`` swCENTER (2): the item's point is the
    box centre. Compared as a lower-left corner, a 60 mm string's centre sits
    30 mm off its printed left edge and matched nothing."""
    item = TextItem("GENERAL TOLERANCES UNLESS NOTED", 0.200, 0.100, 0.0035, reference=2)
    span = _ink_span("GENERAL TOLERANCES UNLESS NOTED", 0.170, 0.0983, width=0.060, height=0.0033)
    assert match_ink([("C", item)], [span])["C"].xmin == pytest.approx(0.170)
    as_lower_left = TextItem(item.text, item.x, item.y, item.height, reference=1)
    assert match_ink([("C", as_lower_left)], [span]) == {}


def test_a_run_with_a_symbol_inside_matches_the_text_either_side():
    """A symbol inside a run prints as a path, splitting the text around it."""
    item = TextItem("2X <MOD-DIAM> 3.45", 0.100, 0.100, 0.0035)
    spans = [_ink_span("2X", 0.1002, 0.1009, width=0.004), _ink_span("3.45", 0.1090, 0.1009, width=0.009)]
    box = match_ink([("S", item)], spans)["S"]
    assert (box.xmin, box.xmax) == pytest.approx((0.1002, 0.1180))


def test_printed_text_no_annotation_claims_gates_outside_the_title_block_border_and_tables():
    """The reverse of text-unmatched: an annotation whose COM read failed
    still prints, and would be invisible to every other check."""
    owned = _dim("Owned", "12.0", 0.100, 0.150)
    dump = _dump(
        views=[_view("v", (0.05, 0.05, 0.25, 0.25), [owned])],
        tables=[{"name": "BOM", "box": [0.300, 0.200, 0.400, 0.250]}],
        spans=[
            ["12.0", 0.1002, 0.1509, 0.1060, 0.1542],
            ["7.5", 0.1500, 0.1509, 0.1550, 0.1542],  # printed, no COM owner
            ["REV", 0.3000, 0.0300, 0.3100, 0.0335],  # title block
            ["A", 0.0035, 0.1000, 0.0090, 0.1060],  # zone label in the border band
            ["QTY", 0.3100, 0.2300, 0.3200, 0.2335],  # inside the BOM table
        ],
        print_rest=False,
    )
    unclaimed = [f for f in audit_dump(dump) if f.kind == "pdf-text-unclaimed"]
    assert [f.a for f in unclaimed] == ["pdf '7.5'"]
    assert severity(unclaimed[0]) is FindingSeverity.GATING


def test_a_printed_page_that_cannot_hold_the_sheet_fails_loud():
    """No silent fall-back to COM boxes: COM text on a page with no PDF text,
    or a page where most strings find no printed match (origin, scale or page
    mapping wrong), stops the audit."""
    dims = [_dim(f"D{i}", f"{i}.5", 0.100, 0.100 + 0.01 * i) for i in range(6)]
    view = _view("v", (0.05, 0.05, 0.25, 0.25), dims)
    blank = _dump(views=[view], strokes=_edges((0.06, 0.06, 0.07, 0.06)))
    blank["ink"]["spans"] = []
    with pytest.raises(ValueError, match="no text"):
        audit_dump(blank)
    shifted = _dump(
        views=[view], spans=[[f"{i}.5", 0.200, 0.100 + 0.01 * i, 0.206, 0.1033 + 0.01 * i] for i in range(6)]
    )
    with pytest.raises(ValueError, match="does not line up"):
        audit_dump(shifted)


def test_a_view_that_printed_no_model_edge_is_found():
    """A shaded or draft view, or a template with another edge weight, prints
    no 0.25 mm stroke: text over it is unchecked. Pictorial: advisory."""
    views = [
        _view("front", (0.05, 0.05, 0.10, 0.10)),
        _view("shaded", (0.15, 0.05, 0.20, 0.10)),
        _view("iso", (0.25, 0.05, 0.30, 0.10), pictorial=True),
    ]
    findings = audit_dump(_dump(views=views, strokes=_edges((0.06, 0.06, 0.09, 0.06))))
    missing = {(f.a, f.kind, severity(f).value) for f in findings if f.kind.startswith("view-edges")}
    assert missing == {
        ("view shaded", "view-edges-missing", "gating"),
        ("view iso", "view-edges-missing-pictorial", "advisory"),
    }


def test_a_refused_com_read_is_a_gating_finding():
    dump = _dump(views=[_view("v", (0.05, 0.05, 0.25, 0.25))])
    dump["read_errors"] = {"GetDisplayData": 2}
    [finding] = [f for f in audit_dump(dump) if f.kind == "com-read-errors"]
    assert finding.extra["read_errors"] == {"GetDisplayData": 2}
    assert severity(finding) is FindingSeverity.GATING


def test_an_overload_fallback_is_not_a_read_error():
    """GetLineAtIndex3 refusing before GetLineAtIndex2 answers is the
    expected path; only a primitive every overload refuses counts."""
    from _drawing_layout_audit import _Reader

    reader = _Reader(adapter=None)

    def refuse():
        raise RuntimeError("E_NOTIMPL")

    assert reader.first([refuse, lambda: (1.0, 2.0)], name="GetLineAtIndex3/GetLineAtIndex2") == (1.0, 2.0)
    assert reader.take_errors() == {}
    assert reader.first([refuse, refuse], name="GetLineAtIndex3/GetLineAtIndex2") is None
    assert reader.take_errors() == {"GetLineAtIndex3/GetLineAtIndex2": 1}


def test_a_required_read_answering_none_is_a_read_error(monkeypatch):
    """SolidWorks often fails a getter by answering None rather than raising:
    an annotation whose display data is None loses all its ink, so it counts."""
    import _drawing_layout_audit as collector

    monkeypatch.setattr(collector, "_early_bound", lambda obj, _interface: obj)

    class Annotation:
        Visible = 1
        OwnerType = 1
        Layer = ""

        def GetType(self):
            return 6  # swNote

        def GetName(self):
            return "Note1"

        def GetPosition(self):
            return (0.1, 0.1, 0.0)

        def GetLeaderCount(self):
            return 1

        def GetLeaderPointsAtIndex(self, _index):
            return None

        def GetDisplayData(self):
            return None

        def GetSpecificAnnotation(self):
            return None

    reader = collector._Reader(adapter=None)
    record = collector._dump_annotation(reader, Annotation())
    assert record is not None and record["display"] == {}
    assert reader.take_errors() == {
        "GetDisplayData": 1,
        "GetLeaderPointsAtIndex": 1,
        "GetSpecificAnnotation": 1,
    }
    # An optional read answering None is not a refusal.
    assert reader.call(lambda: None, "") == "" and reader.take_errors() == {}


def test_a_run_meeting_a_leader_end_to_end_is_not_its_copy():
    """A shoulder running on from a leader's landing shares an end and a
    direction with it but is real ink; only a run overlapping it is a copy."""
    from _layout_audit import _same_run

    leader = Segment(0.10, 0.10, 0.12, 0.10)
    assert _same_run(Segment(0.10, 0.10, 0.12, 0.10), leader)
    assert _same_run(Segment(0.1005, 0.10, 0.12, 0.10), leader)  # starts 0.5 mm off the attach point
    assert not _same_run(Segment(0.12, 0.10, 0.13, 0.10), leader)
    assert not _same_run(Segment(0.10, 0.10, 0.09, 0.10), leader)


def test_the_report_keeps_a_stroke_count_not_every_stroke():
    from _layout_audit import audit_report

    dump = _dump(
        views=[_view("v", (0.05, 0.05, 0.25, 0.25))], strokes=_edges((0.06, 0.06, 0.07, 0.06), (0.1, 0.1, 0.2, 0.1))
    )
    report, _gating = audit_report("x", LayoutAuditMode.REPORT, [dump])
    [sheet] = report["sheets"]
    assert sheet["ink"]["stroke_count"] == 2 and "strokes" not in sheet["ink"]
    assert "strokes" in dump["ink"]  # the audited dump is untouched


def test_a_page_the_size_of_another_sheet_fails_loud(monkeypatch):
    from pathlib import Path

    from _pdf_ink import PageInk

    letter = PageInk(0.2794, 0.2159, (), (), ())
    live, adapter = _fake_drawing(monkeypatch, sheet_names=("Sheet1",), views=(), pages=[letter])

    class View:
        def GetName2(self):  # noqa: N802 - COM name
            return "Sheet1"

        def GetAnnotations(self):  # noqa: N802 - COM name
            return ()

        def GetTableAnnotations(self):  # noqa: N802 - COM name
            return ()

    class Sheet:
        def GetProperties2(self):  # noqa: N802 - COM name
            return (0, 0, 0, 0, 0, SHEET_W, SHEET_H)

        def GetZoneMargin(self, _code):  # noqa: N802 - COM name
            return 0.0

    adapter.currentModel.GetViews = lambda: ((View(),),)
    adapter.currentModel.Sheet = lambda _name: Sheet()
    with pytest.raises(RuntimeError, match=r"431\.8 x 279\.4 mm but page 0 of x\.pdf is 279\.4 x 215\.9 mm"):
        live.collect_sheet_dumps(
            adapter, stem="x", pdf=Path("x.pdf"), sheet_layouts={}, is_pictorial=lambda _o: False
        )


def test_a_collector_fault_carries_what_was_collected(monkeypatch):
    """Main's ruling: fail loud, no report on a fault, but the error and a
    warn say how far the collector got -- the sheets dumped with their
    refused reads, and the refusals on the sheet it died in."""
    from pathlib import Path

    import _telemetry
    from _pdf_ink import PageInk

    pages = [PageInk(SHEET_W, SHEET_H, (), (), ()), PageInk(0.2794, 0.2159, (), (), ())]
    live, adapter = _fake_drawing(monkeypatch, sheet_names=("A", "B"), views=(), pages=pages)

    class View:
        def __init__(self, name):
            self.name = name

        def GetName2(self):  # noqa: N802 - COM name
            return self.name

        def GetAnnotations(self):  # noqa: N802 - COM name
            if self.name == "B":
                raise RuntimeError("E_FAIL")
            return ()

        def GetTableAnnotations(self):  # noqa: N802 - COM name
            return ()

    class Sheet:
        def GetProperties2(self):  # noqa: N802 - COM name
            return (0, 0, 0, 0, 0, SHEET_W, SHEET_H)

        def GetZoneMargin(self, _code):  # noqa: N802 - COM name
            return 0.0

    warnings = []
    monkeypatch.setattr(_telemetry, "warn", lambda message, **_kw: warnings.append(message))
    adapter.currentModel.GetViews = lambda: ((View("A"),), (View("B"),))
    adapter.currentModel.Sheet = lambda _name: Sheet()
    with pytest.raises(RuntimeError) as raised:
        live.collect_sheet_dumps(
            adapter, stem="x", pdf=Path("x.pdf"), sheet_layouts={}, is_pictorial=lambda _o: False
        )
    message = str(raised.value)
    assert "1 sheet(s) dumped {'A': {}}" in message
    assert "refused reads on the failing sheet {'GetAnnotations': 1}" in message
    assert "page 1 of x.pdf is 279.4 x 215.9 mm" in message
    assert message in warnings


def test_an_empty_answer_is_not_a_refused_read():
    """Main's rider: an overload answering an empty value (no points, ())
    answered; only raising or None from every overload is a refusal."""
    from _drawing_layout_audit import _Reader

    reader = _Reader(adapter=None)

    def refuse():
        raise RuntimeError("E_NOTIMPL")

    assert reader.first([refuse, lambda: ()], name="GetPolylineAtIndex2") == ()
    assert reader.take_errors() == {}
    assert reader.first([refuse, lambda: None], name="GetPolylineAtIndex2") is None
    assert reader.take_errors() == {"GetPolylineAtIndex2": 1}


def test_an_empty_answer_falls_through_to_the_next_overload():
    """GetLineAtIndex3 answering () must not hide the primitive
    GetLineAtIndex2 holds: that ink is what the overload chain is for."""
    from _drawing_layout_audit import _Reader

    reader = _Reader(adapter=None)
    line = (0.0, 0.0, 0.0, 0.0, 0.1, 0.1, 0.0, 0.2, 0.1, 0.0)
    assert reader.first([lambda: (), lambda: line], name="GetLineAtIndex3/GetLineAtIndex2") == line
    assert reader.take_errors() == {}


def test_a_path_inside_a_form_xobject_fails_rather_than_misplace_ink():
    import pypdfium2.raw as pdfium_raw
    from _pdf_ink import _strokes

    class FormPath:
        type = pdfium_raw.FPDF_PAGEOBJ_PATH
        level = 1

    class Page:
        def get_objects(self, max_depth):
            return [FormPath()]

    with pytest.raises(ValueError, match="form XObject"):
        _strokes(Page())


def test_the_segment_grid_finds_exactly_what_a_full_scan_finds():
    """find_text_on_line buckets ink in a grid (thousands of PDF edge pieces
    per sheet, checked while the build holds the COM seat); its findings must
    equal the every-box-against-every-segment scan it replaced."""
    import random

    from _layout_geometry import AnnotationGeometry, SheetGeometry, find_text_on_line, segment_box_overlap_length

    random.seed(7)
    annotations = []
    for i in range(40):
        x, y = random.uniform(0.02, 0.4), random.uniform(0.02, 0.26)
        starts = [(random.uniform(0.0, 0.43), random.uniform(0.0, 0.28)) for _ in range(30)]
        segments = tuple(
            Segment(a, b, a + random.uniform(-0.05, 0.05), b + random.uniform(-0.05, 0.05)) for a, b in starts
        )
        annotations.append(AnnotationGeometry(f"a{i}", "dim", "v", (Box(x, y, x + 0.01, y + 0.0035),), segments))
    sheet = SheetGeometry("s", SHEET_W, SHEET_H, None, (), (), tuple(annotations), 0.6)
    found = [(f.a, f.b) for f in find_text_on_line(sheet)]
    expected = [
        (target.label, source.label)
        for target in annotations
        for box in target.text_boxes
        for source in annotations
        if source.label != target.label
        for segment in source.segments
        if segment_box_overlap_length(segment, box) > DEFAULT_TEXT_TOUCH_TOL_M
    ]
    assert found == expected
    assert len(found) > 20


def test_a_note_leader_is_one_leader_not_also_a_line():
    """cone-swing-platform's C'BORE note (d09c2b9eb): its display data draws
    the leader from 0.5 mm off the attach point GetLeaderPointsAtIndex (and
    the printed stroke) starts at. Kept both, the leader read as line AND
    leader, and a crossing was reported twice under two kinds."""
    note = {
        "type": 6,
        "name": "DetailItem375",
        "visible": 1,
        "leaders": [[0.1204851, 0.0455793, -0.0, 0.0940041, 0.0504458, 0.0]],
        "display": {
            "lines": [_line(0.1202019, 0.04615, 0.1202019, 0.04615), _line(0.1202019, 0.04615, 0.0940041, 0.0504458)],
            "texts": [{"t": "7.94 END MILL C'BORE SLOT", "pos": [0.1247703, 0.0435, 0.0], "h": 0.0025}],
        },
        "note": {"balloon": False},
    }
    geometry = annotation_geometry(note, owner="v", advance=0.6)
    long_runs = [(s.role, round(s.x0 * 1000, 2)) for s in geometry.segments if s.length > 0.001]
    assert long_runs == [("leader", 120.49)]
