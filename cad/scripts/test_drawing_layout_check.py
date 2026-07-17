"""SolidWorks-free contract for the drawing layout audit geometry.

Exercises the collision / sheet-overflow logic on plain boxes so a regression in
the audit is caught without a COM seat. The live element collection lives in
``_drawing_common`` and is exercised end-to-end by the drawing builds.

The ``*_real_boxes_*`` cases are positive controls: the element boxes measured
off the shipped, visually-inspected lever-bushing and platen-guide drawings must
audit clean, so the tolerances can never be tightened into flagging a known-good
print.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _drawing_common as drawing_common
from _drawing_layout_check import (
    DEFAULT_BOUNDARY_ALLOWANCE_M,
    DEFAULT_OVERLAP_TOL_M,
    CollisionScope,
    Crossing,
    DrawableRegion,
    LayoutElement,
    LeaderCrossing,
    LeaderSegment,
    audit_layout,
    format_findings,
    find_leader_crossings,
    find_leader_leader_crossings,
    find_overflows,
    find_overlaps,
)

# ASME B sheet used by every project drawing (meters).
SHEET_W = 0.4318
SHEET_H = 0.2794

# The bound used by the pre-zone-border cases: the raw sheet rectangle, so each
# keeps asserting exactly what it did before the audit gained a zone frame.
WHOLE_SHEET = DrawableRegion.whole_sheet(SHEET_W, SHEET_H)

# The zone margins the project DRWDOT actually reports through
# ISheet::GetZoneMargin: a uniform 12.7 mm (0.5 in) on all four sides, read off
# a live sheet.
#
# The drawn frame USED to disagree with this metadata (left 15.9 / right 9.5 /
# bottom 13.3 / top 12.0 mm), which made the gate blind on the left by 3.2 mm --
# ink could clear the declared margin and still print on the drawn rule. The
# template was re-centred 2026-07-16 and the artwork now AGREES: measured on the
# rebuilt renders, the rules span left 0.0124..0.0128, right 0.4188..0.4192,
# bottom 0.0124..0.0128, top 0.2665..0.2669 -- centrelines within a 0.4 mm line
# width of 12.7 on all four sides.
#
# The gate still keys on the METADATA, and that is the point: it is queried from
# the live sheet, so it tracked the template edit without a code change. Do not
# replace these with measured drawn-frame constants -- that would freeze today's
# artwork into the test and go stale the next time the frame moves.
ZONE_MARGINS = {"left": 0.0127, "right": 0.0127, "bottom": 0.0127, "top": 0.0127}
ZONE_REGION = DrawableRegion.from_margins(SHEET_W, SHEET_H, **ZONE_MARGINS)


class _FakeAdapter:
    def __init__(self, model):
        self.currentModel = model

    @staticmethod
    def _attempt(callback, default=None):
        try:
            return callback()
        except Exception:
            return default

    @staticmethod
    def _get_attr_or_call(obj, name):
        member = getattr(obj, name, None)
        return member() if callable(member) else member


def _el(label, x0, y0, x1, y1, kind="view", scope=CollisionScope.ALL, owner=""):
    return LayoutElement(label, kind, x0, y0, x1, y1, scope=scope, owner=owner)


def test_live_collector_never_flags_transient_dispatches(monkeypatch):
    """The audit must not pay whole-interface flagging for fresh COM wrappers."""

    def _unexpected_flag(*_args, **_kwargs):
        raise AssertionError("layout collection must not call flagged()")

    monkeypatch.setattr(drawing_common._sw_type_info, "flagged", _unexpected_flag)

    note = SimpleNamespace(GetExtent=[0.01, 0.09, 0.0, 0.04, 0.10, 0.0])
    note_annotation = SimpleNamespace(
        GetLeaderCount=0,
        GetSpecificAnnotation=note,
        GetType=6,
        GetName="general-note",
    )
    dim_annotation = SimpleNamespace(
        GetPosition=[0.12, 0.22, 0.0],
        GetType=lambda: 4,
        GetName=lambda: "dimension",
    )
    table_annotation = SimpleNamespace(GetPosition=lambda: [0.18, 0.12, 0.0])
    table = SimpleNamespace(
        GetAnnotation=lambda: table_annotation,
        RowCount=2,
        ColumnCount=2,
        GetColumnWidth=lambda _index: 0.02,
        GetRowHeight=lambda _index: 0.01,
    )
    table_annotation.GetName = "hole-table"

    view = SimpleNamespace(
        GetName2="Front",
        GetOrientationName=lambda: "*Front",
        GetOutline=[0.05, 0.15, 0.15, 0.25],
        GetAnnotations=lambda: [note_annotation, dim_annotation],
        GetTableAnnotations=[table],
        GetNextView=None,
    )
    sheet_view = SimpleNamespace(GetNextView=lambda: view, GetTableAnnotations=[])
    zone = {0: ZONE_MARGINS["top"], 1: ZONE_MARGINS["bottom"],
            2: ZONE_MARGINS["right"], 3: ZONE_MARGINS["left"]}
    sheet = SimpleNamespace(
        GetProperties=lambda: [0.0, 0.0, 1.0, 1.0, 0.0, SHEET_W, SHEET_H],
        GetZoneMargin=lambda code: zone[code],
    )
    model = SimpleNamespace(GetCurrentSheet=sheet, GetFirstView=lambda: sheet_view)

    elements, leaders, region = drawing_common.collect_layout_elements(
        _FakeAdapter(model)
    )

    # The drawable region is QUERIED from the sheet's zone margins, never a
    # constant: a template whose zone band moves moves the keep-out with it.
    assert region == ZONE_REGION
    assert leaders == []
    assert [(element.label, element.kind) for element in elements] == [
        ("Front", "view"),
        ("general-note", "note"),
        ("dimension", "dim"),
        ("hole-table", "table"),
        ("title-block", "titleblock"),
    ]


def test_disjoint_layout_is_clean():
    elements = [
        _el("V1", 0.05, 0.18, 0.11, 0.23),
        _el("V2", 0.18, 0.18, 0.20, 0.23),
        _el("N1", 0.014, 0.089, 0.153, 0.112, kind="note"),
    ]
    overlaps, overflows, crossings = audit_layout(elements, WHOLE_SHEET)
    assert overlaps == []
    assert overflows == []


def test_two_views_that_overlap_are_flagged():
    a = _el("V1", 0.05, 0.05, 0.15, 0.15)
    b = _el("V2", 0.10, 0.10, 0.20, 0.20)  # 50 mm x 50 mm mutual penetration
    overlaps = find_overlaps([a, b])
    assert len(overlaps) == 1
    assert {overlaps[0].a.label, overlaps[0].b.label} == {"V1", "V2"}
    assert overlaps[0].depth_x > 0 and overlaps[0].depth_y > 0


def test_note_dropped_on_a_view_is_flagged():
    view = _el("V1", 0.05, 0.05, 0.15, 0.15)
    note = _el("N1", 0.09, 0.09, 0.13, 0.11, kind="note")
    overlaps = find_overlaps([view, note])
    assert len(overlaps) == 1


def test_adjacent_views_within_tolerance_are_not_flagged():
    # Two boxes sharing an edge but only overlapping by less than the tolerance
    # on one axis -- the GetOutline padding case -- must NOT be reported.
    tol = DEFAULT_OVERLAP_TOL_M
    a = _el("V1", 0.05, 0.05, 0.15, 0.15)
    b = _el("V2", 0.15 - tol / 2, 0.05, 0.25, 0.15)  # x-penetration = tol/2 < tol
    assert find_overlaps([a, b]) == []


def test_penetration_must_clear_tolerance_on_both_axes():
    # Deep on Y, shallow on X -> the min penetration is below tolerance -> clean.
    tol = DEFAULT_OVERLAP_TOL_M
    a = _el("A", 0.05, 0.05, 0.15, 0.20)
    b = _el("B", 0.15 - tol / 2, 0.05, 0.25, 0.20)
    assert find_overlaps([a, b]) == []


def test_pictorial_view_scope_none_never_collides():
    # An isometric view's box swallows a nearby label, but a NONE-scope element
    # is excluded from overlap detection so it does not false-positive.
    iso = _el("ISO", 0.17, 0.14, 0.40, 0.28, scope=CollisionScope.NONE)
    label = _el("LBL", 0.14, 0.14, 0.22, 0.145, kind="note")
    assert find_overlaps([iso, label]) == []
    # ... but the same box at ALL scope WOULD be flagged, proving the scope is
    # what suppresses it (not a tolerance fluke).
    solid = _el("ISO", 0.17, 0.14, 0.40, 0.28, scope=CollisionScope.ALL)
    assert len(find_overlaps([solid, label])) == 1


def test_scope_exempt_element_still_checked_for_overflow():
    # Codex #269: collision scope suppresses collisions only -- a pictorial view
    # or leadered note mis-placed OFF the sheet must still be flagged.
    iso_off = _el("ISO", 0.17, 0.14, 0.40, SHEET_H + 0.02, scope=CollisionScope.NONE)
    note_off = _el(
        "N", -0.03, 0.10, 0.05, 0.12, kind="note", scope=CollisionScope.NON_VIEW
    )
    overflows = find_overflows([iso_off, note_off], WHOLE_SHEET)
    flagged = {o.element.label: {side for side, _ in o.sides} for o in overflows}
    assert flagged == {"ISO": {"top"}, "N": {"left"}}


def test_overflow_off_each_sheet_edge():
    allow = DEFAULT_BOUNDARY_ALLOWANCE_M
    left = _el("L", -allow - 0.002, 0.10, 0.05, 0.15)
    right = _el("R", 0.40, 0.10, SHEET_W + allow + 0.002, 0.15)
    top = _el("T", 0.10, 0.20, 0.15, SHEET_H + allow + 0.002)
    bottom = _el("Bt", 0.10, -allow - 0.002, 0.15, 0.10)
    inside = _el("I", 0.10, 0.10, 0.15, 0.15)
    overflows = find_overflows([left, right, top, bottom, inside], WHOLE_SHEET)
    flagged = {o.element.label: {side for side, _ in o.sides} for o in overflows}
    assert flagged == {
        "L": {"left"},
        "R": {"right"},
        "T": {"top"},
        "Bt": {"bottom"},
    }


def test_view_padding_within_allowance_is_not_overflow():
    # A view whose padded outline pokes ~1.5 mm past the top edge (measured on
    # the platen-guide iso view) must NOT be flagged -- the outward allowance
    # absorbs GetOutline padding on a (kind == "view") pictorial box.
    view = _el("V", 0.05, 0.10, 0.15, SHEET_H + 0.0015, scope=CollisionScope.NONE)
    assert find_overflows([view], WHOLE_SHEET) == []


def test_exact_note_barely_off_sheet_is_flagged():
    # Codex #269 thread 7: the GetOutline padding allowance applies only to view
    # boxes; an exact note/table poking even 1 mm past the edge is a real clip in
    # the exported PDF/PNG and must be flagged.
    note = _el("N", 0.05, SHEET_H - 0.02, 0.15, SHEET_H + 0.001, kind="note")
    (overflow,) = find_overflows([note], WHOLE_SHEET)
    assert {side for side, _ in overflow.sides} == {"top"}
    # ... the same 1 mm overhang on a padded VIEW box is absorbed by the allowance.
    view = _el("V", 0.05, SHEET_H - 0.02, 0.15, SHEET_H + 0.001, kind="view")
    assert find_overflows([view], WHOLE_SHEET) == []


def test_leadered_callout_collides_with_notes_not_owner_view():
    # Codex #269 thread 6: a NON_VIEW leadered callout's overlap with the view
    # geometry it OWNS is intended and suppressed, but a collision with a free
    # note / table must still be reported.
    callout = _el("C", 0.10, 0.18, 0.13, 0.20, kind="note", scope=CollisionScope.NON_VIEW, owner="V")
    view = _el("V", 0.05, 0.15, 0.20, 0.23)
    assert find_overlaps([view, callout]) == []  # over its OWNER view: allowed
    notes_block = _el("N", 0.09, 0.17, 0.14, 0.21, kind="note")  # ALL scope
    assert len(find_overlaps([callout, notes_block])) == 1  # over a free note: flagged


def test_nonview_tag_collides_with_a_different_view():
    # Codex #269 thread 3: the view exemption is owner-scoped -- a tag owned by
    # V1 that strays onto a DIFFERENT view V2 is real drawing content overlapping
    # and must be flagged; only the overlap with its own V1 is suppressed.
    tag = _el("tag", 0.16, 0.18, 0.175, 0.19, kind="note", scope=CollisionScope.NON_VIEW, owner="V1")
    v1 = _el("V1", 0.05, 0.15, 0.18, 0.23)  # owner -- exempt
    v2 = _el("V2", 0.15, 0.15, 0.30, 0.23)  # different view -- audited
    assert find_overlaps([v1, tag]) == []
    assert len(find_overlaps([v2, tag])) == 1


def test_titleblock_is_a_hard_keepout_for_exempt_elements():
    # Codex #269 threads 1/2: NONE-scope elements (a pictorial view, a GD&T
    # symbol, a dimension) bypass every ordinary collision -- but the title block
    # is a hard keep-out that catches even them if they cover it.
    title = _el("title-block", 0.278, 0.0, SHEET_W, 0.080, kind="titleblock")
    iso = _el("iso", 0.30, 0.02, 0.40, 0.14, scope=CollisionScope.NONE)  # pictorial
    gdt = _el("G", 0.30, 0.02, 0.316, 0.036, kind="gdt", scope=CollisionScope.NONE)
    dim = _el("D", 0.30, 0.03, 0.308, 0.038, kind="dim", scope=CollisionScope.NONE)
    for cover in (iso, gdt, dim):
        assert len(find_overlaps([title, cover])) == 1


def test_two_keepout_boxes_never_collide():
    # Two keep-out boxes must never report a self-collision (today's template
    # reserves ONE box, but the invariant guards any future second keep-out).
    title = _el("title-block", 0.264, 0.0, SHEET_W, 0.064, kind="titleblock")
    other = _el("keepout-2", 0.242, 0.019, 0.281, 0.035, kind="titleblock")
    assert find_overlaps([title, other]) == []


def test_dimension_is_overflow_only():
    # Codex #269 thread 1: display dimensions / hole callouts sit on the geometry
    # they measure, so they are NONE-scope -- not overlap-checked against a view,
    # but an off-sheet callout is caught by the overflow audit.
    view = _el("V", 0.05, 0.15, 0.20, 0.23)
    dim_on_view = _el("D", 0.10, 0.18, 0.108, 0.188, kind="dim", scope=CollisionScope.NONE)
    assert find_overlaps([view, dim_on_view]) == []
    dim_off = _el("D2", SHEET_W - 0.002, 0.15, SHEET_W + 0.006, 0.16, kind="dim", scope=CollisionScope.NONE)
    overflows = find_overflows([dim_off], WHOLE_SHEET)
    assert len(overflows) == 1 and "right" in {s for s, _ in overflows[0].sides}


def test_exact_boxes_get_near_zero_overlap_slack():
    # Codex #269: the 1.5 mm padding tolerance is for fuzzy GetOutline view
    # boxes; two EXACT boxes overlapping by ~1 mm is a real collision. A note
    # nudged 1 mm into a table (both exact) is flagged...
    note = _el("N", 0.05, 0.10, 0.15, 0.15, kind="note")
    table = _el("T", 0.149, 0.10, 0.25, 0.15, kind="table")  # 1 mm x-penetration
    assert len(find_overlaps([note, table])) == 1
    # ... and 1 mm into the title block too ...
    title = _el("title-block", 0.278, 0.0, SHEET_W, 0.080, kind="titleblock")
    stray = _el("N2", 0.20, 0.03, 0.279, 0.06, kind="note")  # 1 mm into the block
    assert len(find_overlaps([title, stray])) == 1
    # ... but two padded VIEW outlines overlapping by <1.5 mm stay clean (the
    # GetOutline whitespace case the tolerance exists for).
    v1 = _el("V1", 0.05, 0.05, 0.15, 0.15)
    v2 = _el("V2", 0.1490, 0.05, 0.25, 0.15)  # 1 mm x-penetration, both views
    assert find_overlaps([v1, v2]) == []


def test_content_overlapping_title_block_is_flagged():
    # A reserved title-block box (bottom-right) plus a note that strays into it:
    # the collision must be reported so content never lands on the title block.
    title = _el("title-block", 0.2785, 0.0, SHEET_W, 0.078, kind="titleblock")
    stray = _el("N", 0.30, 0.03, 0.36, 0.06, kind="note")
    clear = _el("N2", 0.05, 0.03, 0.20, 0.06, kind="note")
    assert len(find_overlaps([title, stray])) == 1
    assert find_overlaps([title, clear]) == []


def test_gdt_symbol_is_overflow_only():
    # GD&T symbols carry only a coarse NOMINAL box (no real bbox API), so they
    # are scoped NONE: never an overlap source (not vs a view, and not vs a note
    # -- two nominal boxes would false-collide), but an off-sheet symbol is still
    # caught by the overflow audit (Codex #269 thread 5).
    gdt = _el("G", 0.10, 0.18, 0.116, 0.196, kind="gdt", scope=CollisionScope.NONE)
    view = _el("V", 0.05, 0.15, 0.20, 0.23)  # gdt sits over its geometry
    assert find_overlaps([view, gdt]) == []
    note = _el("N", 0.10, 0.185, 0.14, 0.205, kind="note")  # gdt also overlaps a note
    assert find_overlaps([gdt, note]) == []  # nominal box is not overlap-checked
    gdt_off = _el("G2", 0.42, 0.15, 0.44, 0.17, kind="gdt", scope=CollisionScope.NONE)
    overflows = find_overflows([gdt_off], WHOLE_SHEET)
    assert len(overflows) == 1 and "right" in {s for s, _ in overflows[0].sides}


def test_large_note_on_its_own_view_is_still_flagged():
    # Codex #269: the tag exemption is size-gated, so a general-notes block
    # (large) centered inside its owning view is NOT exempt and the collision is
    # reported -- only a small tag centered inside its view is suppressed.
    view = _el("V1", 0.05, 0.05, 0.20, 0.20)
    big_note = _el("N", 0.08, 0.08, 0.18, 0.15, kind="note")  # 100 x 70 mm
    assert len(find_overlaps([view, big_note])) == 1


def test_lever_bushing_real_boxes_are_clean():
    # Measured element boxes from the shipped lever-bushing drawing (meters):
    # 3 views (V3 is the isometric -> NONE scope) + the 2 general-notes blocks.
    elements = [
        _el("V1", 0.05041, 0.17541, 0.10959, 0.23459),
        _el("V2", 0.17553, 0.17541, 0.20293, 0.23459),
        _el("V3", 0.28670, 0.16671, 0.34330, 0.24329, scope=CollisionScope.NONE),
        _el("N18", 0.01390, 0.08939, 0.15347, 0.11211, kind="note"),
        _el("N19", 0.16970, 0.06440, 0.32193, 0.10529, kind="note"),
    ]
    overlaps, overflows, crossings = audit_layout(elements, WHOLE_SHEET)
    assert overlaps == []
    assert overflows == []


def test_platen_guide_real_boxes_are_clean():
    # Measured off the shipped platen-guide drawing: 2 ortho views, the iso view
    # (NONE scope), the general-notes block, the "PLATEN-MATING FACE" label
    # (which bbox-overlaps the iso view), and the 10x4 hole table on the sheet.
    # The iso view's outline reaches ymax=280.9 mm on a 279.4 mm sheet -- within
    # the 3 mm overflow allowance for a padded view box, so it does not
    # false-positive despite now being overflow-checked.
    elements = [
        _el("V1", 0.03441, 0.10191, 0.34559, 0.11809),
        _el("V2", 0.35941, 0.10191, 0.38059, 0.11809),
        _el("V3", 0.16981, 0.13910, 0.40019, 0.28090, scope=CollisionScope.NONE),
        _el("N46", 0.01390, 0.02999, 0.17262, 0.07511, kind="note"),
        _el("N47", 0.14373, 0.14067, 0.22163, 0.14522, kind="note"),
        _el("T45", 0.01400, 0.16874, 0.15876, 0.25800, kind="table"),
    ]
    overlaps, overflows, crossings = audit_layout(elements, WHOLE_SHEET)
    assert overlaps == []
    assert overflows == []


# --- sheet zone border -------------------------------------------------------
#
# The border/zone band carries the frame and the A/B + 1..4 zone labels. Content
# may sit anywhere on the paper INSIDE that band and nowhere on it.


def test_zone_region_is_derived_from_the_sheet_margins():
    region = DrawableRegion.from_margins(
        SHEET_W, SHEET_H, left=0.02, right=0.01, bottom=0.015, top=0.005
    )
    assert region.xmin == 0.02
    assert region.ymin == 0.015
    assert region.xmax == SHEET_W - 0.01
    assert region.ymax == SHEET_H - 0.005


def test_zone_margins_that_swallow_the_sheet_raise():
    # A nonsense template must fail loud rather than silently audit nothing.
    try:
        DrawableRegion.from_margins(
            SHEET_W, SHEET_H, left=0.3, right=0.3, bottom=0.0, top=0.0
        )
    except ValueError as exc:
        assert "no drawable region" in str(exc)
    else:
        raise AssertionError("expected a ValueError for inverted zone margins")


def test_note_inside_the_paper_but_on_the_zone_band_is_flagged():
    # The shipped crank-arm notes block started LEFT of the frame line: on the
    # paper, on the zone band. The whole-sheet bound cannot see it; the zone
    # region must.
    note = _el("notes", 0.008, 0.05, 0.20, 0.09, kind="note")
    assert find_overflows([note], WHOLE_SHEET) == []
    (overflow,) = find_overflows([note], ZONE_REGION)
    assert overflow.sides[0][0] == "left"
    assert overflow.describe().startswith("note 'notes' crosses the sheet zone border")


def test_content_inside_the_zone_frame_is_clean():
    note = _el("notes", 0.02, 0.05, 0.20, 0.09, kind="note")
    assert find_overflows([note], ZONE_REGION) == []


def test_view_outline_padding_still_gets_slack_at_the_zone_border():
    # GetOutline pads whitespace, so a legitimately-placed view may poke a
    # millimetre past the frame; an exact-extent note at the same place may not.
    over = ZONE_REGION.xmin - 0.001
    view = _el("V", over, 0.05, 0.20, 0.09, kind="view")
    assert find_overflows([view], ZONE_REGION) == []
    note = _el("N", over, 0.05, 0.20, 0.09, kind="note")
    assert len(find_overflows([note], ZONE_REGION)) == 1


# --- leader crossings --------------------------------------------------------


def _views():
    return [
        _el("Front", 0.10, 0.10, 0.25, 0.18, kind="view"),
        _el("Top", 0.10, 0.20, 0.25, 0.26, kind="view"),
    ]


def test_leader_across_a_foreign_view_is_flagged():
    # The real crank-arm defect: the Ra symbol sat above the top view and its
    # straight leader ran down to the front view's bore, straight through Top.
    leader = LeaderSegment("Ra 1.6", "gdt", 0.14, 0.28, 0.16, 0.14, owner="Front")
    (crossing,) = find_leader_crossings([leader], _views())
    assert crossing.view.label == "Top"
    assert "runs its leader across view 'Top'" in crossing.describe()


def test_leader_landing_on_its_own_view_is_clean():
    leader = LeaderSegment("dia", "dim", 0.30, 0.14, 0.20, 0.14, owner="Front")
    assert find_leader_crossings([leader], _views()) == []


def test_leader_routed_clear_of_other_views_is_clean():
    # Same annotation, anchored so the leader approaches Front from the side it
    # sits on instead of driving through Top: the fix the gate should accept.
    leader = LeaderSegment("Ra 1.6", "gdt", 0.30, 0.08, 0.24, 0.13, owner="Front")
    assert find_leader_crossings([leader], _views()) == []


def _datum_tag(x, y, lines, label="A"):
    spec = SimpleNamespace(
        GetLineCount=lambda: len(lines),
        GetLineAtIndex=lambda i: [1.0, *lines[i][0], 0.0, *lines[i][1], 0.0],
    )
    return SimpleNamespace(
        GetPosition=[x, y, 0.0],
        GetType=lambda: drawing_common._ANNOT_DATUM,
        GetName=lambda: label,
        GetLeaderCount=lambda: 0,          # the whole point: it registers none
        GetSpecificAnnotation=lambda: spec,
    )


def test_datum_tag_leader_is_collected_even_though_it_registers_none():
    """rocker-arm-support datum A as probed: 4 box lines + a 12.6mm leader.

    GetLeaderCount() is 0 for every swDatumTag (SetLeader3 never made a leader,
    and cannot for a datum FEATURE symbol), so _leader_segments_of returns
    nothing however badly the tag is routed. The leader is real and drawn --
    readable only as IDatumTag geometry.
    """
    ax, ay = 0.2100, 0.1436
    box = [((0.2065, 0.1366), (0.2065, ay)), ((0.2065, ay), (0.2135, ay)),
           ((0.2135, ay), (0.2135, 0.1366)), ((0.2135, 0.1366), (0.2065, 0.1366))]
    leader = [((ax, 0.1562), (ax, ay))]
    ann = _datum_tag(ax, ay, box + leader)

    segs = drawing_common._datum_leader_segments(
        _FakeAdapter(None), ann, label="A", owner="Front")

    # The BOX must be excluded -- it is not a leader, and a tag's box legitimately
    # abuts its own view. Only the leader run survives.
    assert len(segs) == 1
    assert (segs[0].x0, segs[0].y0) == pytest.approx((ax, 0.1562))
    assert (segs[0].x1, segs[0].y1) == pytest.approx((ax, ay))


def _hole_callout(text_xy, model_attach, sheet_attach, *, is_callout=True):
    """A fake native hole callout as probed on pen-rod (RD3).

    GetLeaderCount()==0 (no SetLeader3 leader); the attachment is an IDimension
    reference point in MODEL space that projects to ``sheet_attach`` through the
    view's ModelToViewTransform (fake: MultiplyTransform returns the projection).
    """
    projected = SimpleNamespace(ArrayData=[*sheet_attach, 0.0])
    ref0 = SimpleNamespace(
        ArrayData=[*model_attach, 0.0],
        MultiplyTransform=lambda _x: projected,
    )
    origin = SimpleNamespace(
        ArrayData=[0.0, 0.0, 0.0],
        MultiplyTransform=lambda _x: SimpleNamespace(ArrayData=[0.0, 0.0, 0.0]),
    )
    dim = SimpleNamespace(ReferencePoints=[ref0, ref0, origin])
    display = SimpleNamespace(
        IsHoleCallout=lambda: is_callout,
        GetDimension=lambda: dim,
    )
    return SimpleNamespace(
        GetPosition=[*text_xy, 0.0],
        GetType=lambda: drawing_common._ANNOT_DIM,
        GetName=lambda: "RD3",
        GetLeaderCount=lambda: 0,             # the whole point: registers none
        GetSpecificAnnotation=lambda: display,
    )


def test_hole_callout_leader_is_collected_even_though_it_registers_none():
    """pen-rod's RD3 as probed: IsHoleCallout, GetLeaderCount()==0.

    _leader_segments_of returns nothing (no registered leader), so the callout's
    offset-text leader was invisible to the crossing audit. Reconstruct it from
    the text position and the model->sheet-projected attachment (codex
    #3605215320): model (0, 0.115) -> sheet (0.070, 0.205), text at (0.104,
    0.222).
    """
    view = SimpleNamespace(ModelToViewTransform=object())
    ann = _hole_callout((0.104, 0.222), (0.0, 0.115), (0.070, 0.205))

    segs = drawing_common._display_dimension_leader_segments(
        _FakeAdapter(None), ann, view, label="RD3", owner="Front")

    assert len(segs) == 1
    assert (segs[0].x0, segs[0].y0) == pytest.approx((0.070, 0.205))  # attachment
    assert (segs[0].x1, segs[0].y1) == pytest.approx((0.104, 0.222))  # text
    assert segs[0].kind == "dim"


def test_plain_dimension_contributes_no_leader():
    """A non-callout display dimension keeps its text on the dimension line, not
    at the end of a free leader -- so it must yield NO leader segment (else every
    linear/radius dimension would spray phantom leaders across the audit)."""
    view = SimpleNamespace(ModelToViewTransform=object())
    ann = _hole_callout((0.104, 0.222), (0.0, 0.115), (0.070, 0.205),
                        is_callout=False)
    segs = drawing_common._display_dimension_leader_segments(
        _FakeAdapter(None), ann, view, label="Length", owner="Front")
    assert segs == []


def test_datum_leader_across_a_foreign_view_now_flags():
    """The defect the eye pass found on cone-tip-bushing and crank-arm.

    A datum leader driven through a neighbouring view used to pass EVERY gate:
    the box is CollisionScope.NONE so it is never overlap-checked, and the tag
    contributes no leader segments so it was never crossing-checked either.
    """
    # Tag below the view, leader driven straight UP through it to a pick above.
    box = [((0.14, 0.05), (0.14, 0.057)), ((0.14, 0.057), (0.147, 0.057)),
           ((0.147, 0.057), (0.147, 0.05)), ((0.147, 0.05), (0.14, 0.05))]
    leader = [((0.1435, 0.25), (0.1435, 0.057))]
    ann = _datum_tag(0.1435, 0.057, box + leader)
    segs = drawing_common._datum_leader_segments(
        _FakeAdapter(None), ann, label="A", owner="Front")

    (crossing,) = find_leader_crossings(segs, _views())
    assert crossing.view.label == "Top"


def test_closed_rectangle_ignores_a_tag_with_no_box():
    """No rectangle found -> treat every line as leader, never crash.

    Conservative on purpose: an unrecognised tag shape yields MORE crossing
    checks, not fewer. Silently returning [] would restore the blind spot.
    """
    lines = [((0.10, 0.10), (0.15, 0.18))]  # a lone diagonal, no box
    assert drawing_common._closed_rectangle(lines) == set()
    ann = _datum_tag(0.10, 0.10, lines)
    segs = drawing_common._datum_leader_segments(
        _FakeAdapter(None), ann, label="A", owner="Front")
    assert len(segs) == 1


def test_leader_clipping_a_pictorial_view_is_not_a_crossing():
    """An isometric view's outline is mostly EMPTY diagonal space.

    _view_scope already exempts it from the overlap audit for this reason
    (CollisionScope.NONE); the leader audit must agree, or a leader clipping an
    empty corner fails a drawing that is correct (codex #334). Keying on
    kind == "view" alone was what let this in.
    """
    iso = _el("Isometric", 0.10, 0.10, 0.30, 0.30, kind="view",
              scope=CollisionScope.NONE)
    leader = LeaderSegment("Ra 1.6", "gdt", 0.05, 0.12, 0.35, 0.12, owner="Front")
    assert find_leader_crossings([leader], [iso]) == []

    # Positive control: the SAME leader across an ORTHO view still flags, so the
    # skip is scoped to pictorials and has not disabled the gate.
    ortho = _el("Top", 0.10, 0.10, 0.30, 0.30, kind="view", scope=CollisionScope.ALL)
    (crossing,) = find_leader_crossings([leader], [ortho])
    assert crossing.view.label == "Top"


def test_leader_grazing_outline_padding_is_not_a_crossing():
    # Runs along Top's bottom edge, inside the GetOutline whitespace only.
    leader = LeaderSegment("n", "note", 0.05, 0.2005, 0.30, 0.2005, owner="Front")
    assert find_leader_crossings([leader], _views()) == []


def test_bent_leader_reports_each_segment_that_crosses():
    # A bent leader is two segments; only the one through Top is a crossing.
    elbow = LeaderSegment("Ra", "gdt", 0.05, 0.28, 0.14, 0.28, owner="Front")
    tail = LeaderSegment("Ra", "gdt", 0.14, 0.28, 0.16, 0.14, owner="Front")
    crossings = find_leader_crossings([elbow, tail], _views())
    assert [c.view.label for c in crossings] == ["Top"]


def test_audit_layout_reports_crossings_alongside_boxes():
    leader = LeaderSegment("Ra 1.6", "gdt", 0.14, 0.28, 0.16, 0.14, owner="Front")
    overlaps, overflows, crossings = audit_layout(
        _views(), ZONE_REGION, leaders=[leader]
    )
    assert overlaps == []
    assert overflows == []
    assert len(crossings) == 1
    assert "move the anchor or the text placement" in format_findings(
        overlaps, overflows, crossings
    )


def test_titleblock_keepout_is_not_border_checked():
    # The keep-out is a reserved region defined to reach the sheet corner, not
    # content -- border-checking it would report its own definition forever.
    title = _el("title-block", 0.264, 0.0, SHEET_W, 0.064, kind="titleblock")
    assert find_overflows([title], ZONE_REGION) == []


def _gdt(x, y, kind, label):
    annotation = SimpleNamespace(
        GetPosition=[x, y, 0.0], GetType=lambda k=kind: k, GetName=lambda n=label: n
    )
    return drawing_common._gdt_element(
        _FakeAdapter(None), annotation, label, kind
    )


def test_surface_finish_box_matches_the_measured_symbol_anatomy():
    """An Ra symbol's anchor is its BOTTOM VERTEX and its body draws UP-RIGHT.

    Measured on the shipped sheets by three agents independently. A symmetric box
    is the wrong SHAPE here, not merely the wrong size.
    """
    ax, ay = 0.100, 0.200
    element = _gdt(ax, ay, drawing_common._ANNOT_SFSYM, "Ra")

    assert element.xmin == ax - drawing_common._SF_BOX_LEFT_M
    assert element.xmax == ax + drawing_common._SF_BOX_RIGHT_M
    assert element.ymin == ay              # the vertex IS the bottom edge
    assert element.ymax == ay + drawing_common._SF_BOX_UP_M
    # The body is far wider than tall and sits entirely above its anchor.
    assert element.xmax - element.xmin > 2 * (element.ymax - element.ymin)


def _gdt_with_geometry(x, y, kind, label, lines=(), triangles=()):
    """A GD&T annotation whose GetSpecificAnnotation exposes real primitives.

    Mirrors the COM shapes exactly: GetLineAtIndex -> [lineType, startPt[3],
    endPt[3]], GetTriangleAtIndex -> [vtx1[3], vtx2[3], vtx3[3], isFilled,
    lineType].
    """
    spec = SimpleNamespace(
        GetLineCount=lambda: len(lines),
        GetLineAtIndex=lambda i: [1.0, *lines[i][0], 0.0, *lines[i][1], 0.0],
        GetArcCount=lambda: 0,
        GetArcAtIndex=lambda i: None,
        GetTriangleCount=lambda: len(triangles),
        GetTriangleAtIndex=lambda i: [
            c for v in triangles[i] for c in (*v, 0.0)
        ] + [1.0, 1.0],
    )
    annotation = SimpleNamespace(
        GetPosition=[x, y, 0.0],
        GetType=lambda k=kind: k,
        GetName=lambda n=label: n,
        GetSpecificAnnotation=lambda: spec,
    )
    return drawing_common._gdt_element(_FakeAdapter(None), annotation, label, kind)


def test_control_frame_is_measured_from_its_rendered_lines():
    """An FCF's box is its real geometry, NOT a square around its anchor.

    The numbers are top-crossbar's position frame as the COM probe read it
    (2026-07-16): five 7.0mm-tall compartment rectangles spanning x
    0.1200..0.1616 off anchor (0.1200, 0.0900), plus a leader shoulder and a
    diagonal leader. Independently confirmed against the render, which measured
    the same frame at +41.6mm right / -7.1mm down of the anchor.
    """
    ax, ay = 0.1200, 0.0900
    frame = [((ax, ay - 0.0070), (ax, ay)),          # first compartment
             ((ax, ay), (0.1616, ay)),               # frame top run
             ((0.1616, ay), (0.1616, ay - 0.0070)),
             ((0.1616, ay - 0.0070), (ax, ay - 0.0070))]
    leader = [((0.1137, 0.0865), (ax, 0.0865)),      # shoulder
              ((0.1137, 0.0865), (0.1049, 0.1268))]  # diagonal
    el = _gdt_with_geometry(ax, ay, drawing_common._ANNOT_GTOL, "pos",
                            lines=frame + leader)

    # The FRAME hangs down-right of the anchor (its top-left corner), so the
    # box's bottom is the frame's bottom...
    assert el.ymin == pytest.approx(ay - 0.0070)
    # ...and it reaches the frame's full 41.6mm width. The old +-8mm square
    # stopped at 0.128 and left ~34mm of frame body unchecked.
    assert el.xmax == pytest.approx(0.1616)
    assert el.xmax - ax > 0.030
    # The box also spans the LEADER (left to 0.1049, up to 0.1268): that is ink
    # too, and it can cross a border on its own. So the element's ymax is the
    # leader's apex, NOT the frame's top edge at the anchor.
    assert el.xmin == pytest.approx(0.1049)
    assert el.ymax == pytest.approx(0.1268)
    assert el.ymax > ay


def test_datum_tag_box_spans_its_leader_and_triangle():
    """rocker-arm-support datum A as probed: 7x7mm box + a 12.6mm leader up."""
    ax, ay = 0.2100, 0.1436
    box = [((0.2065, 0.1366), (0.2065, ay)), ((0.2065, ay), (0.2135, ay)),
           ((0.2135, ay), (0.2135, 0.1366)), ((0.2135, 0.1366), (0.2065, 0.1366))]
    leader = [((ax, 0.1562), (ax, ay))]
    tri = [((0.2086, 0.1537), (0.2114, 0.1537), (0.2100, 0.1562))]
    el = _gdt_with_geometry(ax, ay, drawing_common._ANNOT_DATUM, "A",
                            lines=box + leader, triangles=tri)

    assert el.ymin == pytest.approx(0.1366)   # box bottom
    assert el.ymax == pytest.approx(0.1562)   # triangle tip at the attachment
    assert (el.xmin, el.xmax) == pytest.approx((0.2065, 0.2135))


def test_unmeasurable_gdt_falls_back_to_the_nominal_square():
    """No GetSpecificAnnotation (PMI-only) -> keep a coarse box, don't drop it.

    A dropped symbol is worse than a coarse one: it leaves the audit silent on a
    symbol placed clear off the sheet.
    """
    half = drawing_common._NOMINAL_GDT_HALF_M
    for kind in (drawing_common._ANNOT_DATUM, drawing_common._ANNOT_GTOL):
        element = _gdt(0.100, 0.200, kind, "tag")
        assert (element.xmin, element.ymin) == (0.100 - half, 0.200 - half)
        assert (element.xmax, element.ymax) == (0.100 + half, 0.200 + half)


def test_surface_finish_over_the_top_border_is_now_caught():
    """Regression: wheel_axle's Ra printed over the zone label, audit silent.

    Its anchor sat at y=0.255 -- inside the 0.2667 top bound -- so the old
    +/-8 mm box topped out at 0.263 and reported clean, while the real body
    reached ay+0.018 = 0.273 and printed over the border.
    """
    ra = _gdt(0.030, 0.255, drawing_common._ANNOT_SFSYM, "Ra")
    overflows = find_overflows([ra], ZONE_REGION)
    assert overflows, "the Ra body crosses the top zone bound and must be flagged"
    assert "top" in format_findings([], overflows).lower()

    # The old symmetric box is the negative control: it does NOT reach the bound.
    half = drawing_common._NOMINAL_GDT_HALF_M
    old = _el("Ra", 0.030 - half, 0.255 - half, 0.030 + half, 0.255 + half,
              kind="gdt", scope=CollisionScope.NONE)
    assert not find_overflows([old], ZONE_REGION), (
        "negative control: the old box was blind here -- that is the bug"
    )


def test_surface_finish_clear_of_the_border_still_passes():
    """Positive control: draw-D's verified-safe bounds must audit clean."""
    for ax, ay in ((0.045, 0.1045), (0.133, 0.1992)):
        ra = _gdt(ax, ay, drawing_common._ANNOT_SFSYM, "Ra")
        assert not find_overflows([ra], ZONE_REGION)


# --- leader-vs-leader crossings ----------------------------------------------


def test_two_leaders_crossing_each_other_are_flagged():
    # The pen-rod defect at its MEASURED sheet coordinates (2026-07-16 render).
    # The Ra rises from its symbol right of the rod to the slide face; the
    # squareness frame's leader descends from its box to the rod's bottom. X.
    #
    # The frame's leader is BENT, and the bend matters here: its box sits at
    # x=0.102 but the shoulder runs left to an elbow at (0.0956, 0.1044) before
    # the diagonal drops to the rod. Modelling it as one straight run from the
    # box moves the reported crossing 1.5 mm (0.0805 -> 0.0820), so the DIAGONAL
    # is what gets asserted -- the segment the sheet actually draws.
    ra = LeaderSegment("Ra 1.6", "gdt", 0.170, 0.068, 0.0675, 0.100, owner="Front")
    fcf = LeaderSegment("perp", "gdt", 0.0956, 0.1044, 0.070, 0.090, owner="Front")
    (crossing,) = find_leader_leader_crossings([ra, fcf])
    assert {crossing.a.label, crossing.b.label} == {"Ra 1.6", "perp"}
    # The real intersection, independently read off the render at (0.080, 0.096)
    # -- not merely "something was reported".
    assert crossing.x == pytest.approx(0.0805, abs=5e-4)
    assert crossing.y == pytest.approx(0.0959, abs=5e-4)
    assert "cross their leaders" in crossing.describe()


def test_the_fix_direction_clears_the_crossing():
    # Positive control for the test above: same two annotations, the frame moved
    # below the rod so its leader approaches from underneath. Without this, the
    # test above would pass just as happily against a function that flags every
    # pair it is handed.
    ra = LeaderSegment("Ra 1.6", "gdt", 0.170, 0.068, 0.0675, 0.100, owner="Front")
    fcf = LeaderSegment("perp", "gdt", 0.102, 0.0765, 0.070, 0.090, owner="Front")
    assert find_leader_leader_crossings([ra, fcf]) == []


def test_a_bent_leaders_own_elbow_and_tail_never_cross():
    # A bent leader is two segments sharing an elbow BY CONSTRUCTION. If the
    # touch tolerance were wrong, every bent leader on every sheet would report.
    elbow = LeaderSegment("Ra", "gdt", 0.10, 0.10, 0.14, 0.10, owner="Front")
    tail = LeaderSegment("Ra", "gdt", 0.14, 0.10, 0.18, 0.16, owner="Front")
    assert find_leader_leader_crossings([elbow, tail]) == []


def test_two_leaders_landing_on_one_point_touch_but_do_not_cross():
    # Two arrows converging on a shared edge point is a STACKING question the
    # overlap audit owns. Reporting it here would be a false positive.
    a = LeaderSegment("datum A", "gdt", 0.20, 0.05, 0.10, 0.10, owner="Front")
    b = LeaderSegment("Ra", "gdt", 0.20, 0.15, 0.10, 0.10, owner="Front")
    assert find_leader_leader_crossings([a, b]) == []


def test_parallel_leaders_never_cross():
    a = LeaderSegment("one", "gdt", 0.10, 0.10, 0.20, 0.14, owner="Front")
    b = LeaderSegment("two", "gdt", 0.10, 0.12, 0.20, 0.16, owner="Front")
    assert find_leader_leader_crossings([a, b]) == []


def test_leaders_whose_extensions_would_meet_off_segment_do_not_cross():
    # Crossing must be judged on the SEGMENTS, not their infinite lines: these
    # two only meet far outside both runs.
    a = LeaderSegment("one", "gdt", 0.10, 0.10, 0.12, 0.11, owner="Front")
    b = LeaderSegment("two", "gdt", 0.10, 0.20, 0.12, 0.19, owner="Front")
    assert find_leader_leader_crossings([a, b]) == []


def test_leader_leader_crossings_reach_the_audit():
    # The gate is only real if audit_layout actually runs it.
    ra = LeaderSegment("Ra 1.6", "gdt", 0.170, 0.068, 0.0675, 0.100, owner="Front")
    fcf = LeaderSegment("perp", "gdt", 0.102, 0.1045, 0.070, 0.090, owner="Front")
    _, _, crossings = audit_layout(
        [_el("Front", 0.06, 0.09, 0.08, 0.21, kind="view")],
        DrawableRegion.whole_sheet(0.4318, 0.2794),
        leaders=[ra, fcf],
    )
    assert any("cross their leaders" in c.describe() for c in crossings)


def test_leaders_converging_on_one_point_are_stacked_not_crossed():
    # platen-guide's REAL segments (2026-07-16). Datum A arrives horizontally and
    # a second frame's leader arrives diagonally; both terminate at x=0.3650,
    # 0.2 mm apart in y. Their last 0.2 mm technically crosses -- underneath
    # ~2.4 mm arrowheads, so no reader can see it. The gate's first sweep DID
    # report this; it was the only false positive in 23 sheets.
    datum = LeaderSegment("datum A", "gdt", 0.3650, 0.1100, 0.3520, 0.1100, owner="Iso")
    other = LeaderSegment("frame", "gdt", 0.3389, 0.0885, 0.3650, 0.1102, owner="Iso")
    assert find_leader_leader_crossings([datum, other]) == []


def test_a_shared_terminus_does_not_mask_a_real_crossing_elsewhere():
    # Positive control for the exemption: pen-assembly's B4xB6 balloons end
    # 4.7 mm apart -- the tightest TRUE positive on the fleet, and it must still
    # report. Without this, widening _SHARED_TERMINUS_M would silently swallow
    # real findings and every test above would still pass.
    b4 = LeaderSegment("B4", "note", 0.2380, 0.1882, 0.2280, 0.1121, owner="Iso")
    b6 = LeaderSegment("B6", "note", 0.2546, 0.1508, 0.2238, 0.1099, owner="Iso")
    (crossing,) = find_leader_leader_crossings([b4, b6])
    assert crossing.x == pytest.approx(0.2285, abs=5e-4)
    assert crossing.y == pytest.approx(0.1161, abs=5e-4)


# --- every sheet is held to zero; there is no grandfathered case -------------


def _stub_layout(monkeypatch, leader_crossings):
    """Drive check_drawing_layout with a chosen number of leader crossings."""
    seg = LeaderSegment("a", "gdt", 0.0, 0.0, 0.1, 0.1, owner="Front")
    found = [LeaderCrossing(seg, seg, 0.05, 0.05) for _ in range(leader_crossings)]
    monkeypatch.setattr(
        drawing_common, "collect_layout_elements",
        lambda _adapter: ([], [], WHOLE_SHEET),
    )
    monkeypatch.setattr(
        drawing_common, "audit_layout",
        lambda *_a, **_k: ([], [], found),
    )


def test_a_clean_sheet_passes(monkeypatch):
    _stub_layout(monkeypatch, 0)
    drawing_common.check_drawing_layout(None, stem="pen-assembly")


@pytest.mark.parametrize("stem", ["pen-assembly", "crank-arm", ""])
def test_no_sheet_is_exempt_from_a_leader_crossing(monkeypatch, stem):
    """pen-assembly USED to be grandfathered for 2 crossings while the fix was
    thought to need a design decision. It needed the balloon radius, which
    GetBalloonInfo always exposed. The exemption died with the defect, and no
    sheet -- named, unnamed, or formerly-grandfathered -- may reintroduce one."""
    _stub_layout(monkeypatch, 1)
    with pytest.raises(RuntimeError):
        drawing_common.check_drawing_layout(None, stem=stem)


def test_the_grandfather_machinery_is_gone():
    """A tripwire on the retirement: re-adding an allowlist must be a deliberate
    act that trips a test, not a quiet way to make a red build green."""
    assert not hasattr(drawing_common, "_KNOWN_LEADER_CROSSINGS")


# --- the shared-terminus exemption must not swallow real crossings -----------


def test_a_shared_terminus_does_not_excuse_a_crossing_ELSEWHERE():
    """Codex #3601319580's counterexample, pinned.

    Two segments whose starts are 0.9 mm apart -- INSIDE _SHARED_TERMINUS_M --
    still cross once, and here that crossing is at (5, 0): 5 mm from the shared
    end, mid-span, plainly visible in ink. The old endpoint-only test skipped the
    pair outright and threw it away. The exemption is for crossings buried under
    a shared arrowhead, so it must key on where the CROSSING is, not merely on
    whether two ends are near each other.
    """
    a = LeaderSegment("A", "gdt", 0.0, 0.0, 0.010, 0.0, owner="Front")
    b = LeaderSegment("B", "gdt", 0.0, 0.0009, 0.010, -0.0009, owner="Front")
    found = find_leader_leader_crossings([a, b])
    assert len(found) == 1, "a mid-span crossing must survive a nearby shared end"
    assert found[0].x == pytest.approx(0.005, abs=1e-4)
    assert found[0].y == pytest.approx(0.0, abs=1e-4)


def test_the_converging_arrowhead_artefact_is_still_exempt():
    """The positive control for the fix: the real platen-guide shape stays clean.

    Two leaders converging on ONE attachment meet AT that attachment, so the
    crossing sits under the ~2.4 mm arrowhead and prints as one arrow. Tightening
    the exemption must not start flagging this.
    """
    a = LeaderSegment("A", "dim", 0.3650, 0.1000, 0.3400, 0.1200, owner="Front")
    b = LeaderSegment("B", "dim", 0.3652, 0.1000, 0.3900, 0.1200, owner="Front")
    assert find_leader_leader_crossings([a, b]) == []


def test_the_ratchet_never_excuses_a_leader_across_a_VIEW():
    """Codex #3601319575, kept after the ratchet's retirement.

    The bug was an exemption swallowing a leader-through-VIEW crossing. The
    exemption is gone, but the class it endangered must stay fatal -- so this
    keeps proving a view crossing fails, whatever the surrounding policy.
    """
    seg = LeaderSegment("a", "gdt", 0.0, 0.0, 0.1, 0.1, owner="Front")
    view = _el("OtherView", 0.05, 0.05, 0.15, 0.15)
    mixed = [Crossing(seg, view)]  # a leader across a foreign view: always fatal

    class _Stub:
        pass

    import _drawing_common as dc

    real_collect, real_audit = dc.collect_layout_elements, dc.audit_layout
    dc.collect_layout_elements = lambda _a: ([], [], WHOLE_SHEET)
    dc.audit_layout = lambda *_a, **_k: ([], [], mixed)
    try:
        with pytest.raises(RuntimeError):
            dc.check_drawing_layout(None, stem="pen-assembly")
    finally:
        dc.collect_layout_elements, dc.audit_layout = real_collect, real_audit


# --- balloon ring separation (SolidWorks-free) -------------------------------

import math as _math


def test_push_apart_never_reorders_the_balloons():
    """The property the whole no-crossing argument rests on.

    Balloons placed about a shared centre IN their attachments' angular order
    cannot have crossing leaders. So a separation pass that reorders silently
    destroys the guarantee. The predecessor -- an iterative pairwise relaxation
    -- did exactly that: it measured gaps modulo 2*pi, so an inverted pair read
    as a ~6 rad gap and was never repaired. These are the REAL pen-assembly
    attachment angles it was probed with, and it returned them reordered.
    """
    angles = [-1.865, -1.661, -1.629, -1.407, -1.152, 1.684, 1.805, 1.838]
    out = drawing_common._push_apart_on_ring(angles, min_gap=0.4211)
    assert out == sorted(out), f"push-apart reordered the balloons: {out}"


def test_push_apart_actually_separates_to_the_gap():
    angles = [-1.865, -1.661, -1.629, -1.407, -1.152, 1.684, 1.805, 1.838]
    gap = 0.4211
    out = drawing_common._push_apart_on_ring(angles, min_gap=gap)
    for a, b in zip(out, out[1:]):
        assert b - a >= gap - 1e-9, f"gap {b - a} < {gap}"
    # and the wrap-around pair, which the linear chain cannot see
    assert (out[0] + 2.0 * _math.pi) - out[-1] >= gap - 1e-9


def _cyclic_order_preserved(inp, out):
    """``out`` traces the same cyclic order round the ring as ``inp``.

    Balloons cannot cross iff their ring order is a rotation of their
    attachments' angular order, so this -- not strict linear monotonicity -- is
    the property to check across the +-pi seam.
    """
    n = len(inp)
    in_order = sorted(range(n), key=lambda i: inp[i])
    out_order = sorted(range(n), key=lambda i: out[i])
    doubled = in_order + in_order
    return any(doubled[k : k + n] == out_order for k in range(n))


def test_push_apart_keeps_a_seam_straddling_cluster_at_the_seam():
    """Codex #3605056589: attachments straddling +-pi must stay near the seam.

    ``[-3.10, 3.10]`` are 0.083 rad apart THROUGH the seam (both left of the
    view), not 6.20 apart. The buggy predecessor solved them in raw-sorted
    linear space -- under-separated, then re-centred on the ORDINARY average of
    the endpoints (~0), flipping both to ``[-0.4, 0.0]`` on the RIGHT of the
    view and hauling their leaders across the model. The unwrap-around-the-
    largest-gap frame must instead separate them to the gap AT the seam.
    """
    angles = [-3.10, 3.10]
    gap = 0.4
    out = drawing_common._push_apart_on_ring(angles, min_gap=gap)
    # Separated to the gap, measured cyclically (the pair spans the seam).
    cyclic = [(b - a) % (2.0 * _math.pi) for a, b in zip(out, out[1:])]
    cyclic.append((out[0] - out[-1]) % (2.0 * _math.pi))
    assert min(cyclic) >= gap - 1e-9, f"seam pair not separated: {out}"
    # Still near +-pi (left of the view), NOT flipped to angle ~0 (right).
    for angle in out:
        assert abs(abs(angle) - _math.pi) < 0.3, f"balloon flipped off the seam: {out}"
    assert _cyclic_order_preserved(angles, out)


def test_push_apart_never_reorders_across_the_seam():
    """The no-crossing property, checked cyclically for a left-clustered view.

    A run whose attachments sit on the left (values near +-pi with the empty gap
    on the RIGHT) must come back in the same cyclic order -- the unwrap frame
    must not shuffle indices when it rotates the run off the seam.
    """
    angles = sorted([-3.0, -2.8, -2.6, 2.7, 2.9, 3.05])
    out = drawing_common._push_apart_on_ring(angles, min_gap=0.35)
    assert _cyclic_order_preserved(angles, out), f"seam run reordered: {out}"
    cyclic = [(b - a) % (2.0 * _math.pi) for a, b in zip(sorted(out), sorted(out)[1:])]
    cyclic.append((min(out) + 2.0 * _math.pi) - max(out))
    assert min(cyclic) >= 0.35 - 1e-9, f"seam run not separated: {out}"


def test_push_apart_leaves_already_separated_angles_alone():
    """Minimum movement: balloons that already clear must not be herded."""
    angles = [0.0, 1.0, 2.0, 3.0]
    out = drawing_common._push_apart_on_ring(angles, min_gap=0.5)
    assert out == pytest.approx(angles)


def test_push_apart_falls_back_to_even_spacing_when_it_cannot_fit():
    # 20 balloons x 0.5 rad = 10 rad > 2*pi: packing tighter than their own
    # circles would trade crossings for overlaps, the trade radial already lost.
    angles = [i * 0.01 for i in range(20)]
    out = drawing_common._push_apart_on_ring(angles, min_gap=0.5)
    spacing = [round(b - a, 6) for a, b in zip(out, out[1:])]
    assert len(set(spacing)) == 1, "fallback must space evenly"


def test_min_angular_gap_clears_the_audits_SQUARE_not_just_the_circle():
    """_note_element boxes the balloon's circumscribed square, so two balloons
    on a ring diagonal still collide after their circles part. The gap must be
    set against the model that grades it, or placement and audit disagree --
    measured as 9 overlaps when this used 2*r."""
    ring, balloon = 0.05, 0.00472
    gap = drawing_common._min_angular_gap(ring, balloon, clearance=0.0)
    assert gap * ring == pytest.approx(2.0 * _math.sqrt(2.0) * balloon, rel=1e-9)
