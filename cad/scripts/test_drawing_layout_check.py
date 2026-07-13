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

from _drawing_layout_check import (
    DEFAULT_BOUNDARY_ALLOWANCE_M,
    DEFAULT_OVERLAP_TOL_M,
    CollisionScope,
    LayoutElement,
    audit_layout,
    find_overflows,
    find_overlaps,
)

# ASME B sheet used by every project drawing (meters).
SHEET_W = 0.4318
SHEET_H = 0.2794


def _el(label, x0, y0, x1, y1, kind="view", scope=CollisionScope.ALL, owner=""):
    return LayoutElement(label, kind, x0, y0, x1, y1, scope=scope, owner=owner)


def test_disjoint_layout_is_clean():
    elements = [
        _el("V1", 0.05, 0.18, 0.11, 0.23),
        _el("V2", 0.18, 0.18, 0.20, 0.23),
        _el("N1", 0.014, 0.089, 0.153, 0.112, kind="note"),
    ]
    overlaps, overflows = audit_layout(elements, SHEET_W, SHEET_H)
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
    overflows = find_overflows([iso_off, note_off], SHEET_W, SHEET_H)
    flagged = {o.element.label: {side for side, _ in o.sides} for o in overflows}
    assert flagged == {"ISO": {"top"}, "N": {"left"}}


def test_overflow_off_each_sheet_edge():
    allow = DEFAULT_BOUNDARY_ALLOWANCE_M
    left = _el("L", -allow - 0.002, 0.10, 0.05, 0.15)
    right = _el("R", 0.40, 0.10, SHEET_W + allow + 0.002, 0.15)
    top = _el("T", 0.10, 0.20, 0.15, SHEET_H + allow + 0.002)
    bottom = _el("Bt", 0.10, -allow - 0.002, 0.15, 0.10)
    inside = _el("I", 0.10, 0.10, 0.15, 0.15)
    overflows = find_overflows([left, right, top, bottom, inside], SHEET_W, SHEET_H)
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
    assert find_overflows([view], SHEET_W, SHEET_H) == []


def test_exact_note_barely_off_sheet_is_flagged():
    # Codex #269 thread 7: the GetOutline padding allowance applies only to view
    # boxes; an exact note/table poking even 1 mm past the edge is a real clip in
    # the exported PDF/PNG and must be flagged.
    note = _el("N", 0.05, SHEET_H - 0.02, 0.15, SHEET_H + 0.001, kind="note")
    (overflow,) = find_overflows([note], SHEET_W, SHEET_H)
    assert {side for side, _ in overflow.sides} == {"top"}
    # ... the same 1 mm overhang on a padded VIEW box is absorbed by the allowance.
    view = _el("V", 0.05, SHEET_H - 0.02, 0.15, SHEET_H + 0.001, kind="view")
    assert find_overflows([view], SHEET_W, SHEET_H) == []


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
    # The title block and its projection symbol overlap slightly by design; two
    # keep-out boxes must not report a self-collision.
    title = _el("title-block", 0.278, 0.0, SHEET_W, 0.080, kind="titleblock")
    proj = _el("projection-symbol", 0.242, 0.019, 0.281, 0.035, kind="titleblock")
    assert find_overlaps([title, proj]) == []


def test_dimension_is_overflow_only():
    # Codex #269 thread 1: display dimensions / hole callouts sit on the geometry
    # they measure, so they are NONE-scope -- not overlap-checked against a view,
    # but an off-sheet callout is caught by the overflow audit.
    view = _el("V", 0.05, 0.15, 0.20, 0.23)
    dim_on_view = _el("D", 0.10, 0.18, 0.108, 0.188, kind="dim", scope=CollisionScope.NONE)
    assert find_overlaps([view, dim_on_view]) == []
    dim_off = _el("D2", SHEET_W - 0.002, 0.15, SHEET_W + 0.006, 0.16, kind="dim", scope=CollisionScope.NONE)
    overflows = find_overflows([dim_off], SHEET_W, SHEET_H)
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
    overflows = find_overflows([gdt_off], SHEET_W, SHEET_H)
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
    overlaps, overflows = audit_layout(elements, SHEET_W, SHEET_H)
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
    overlaps, overflows = audit_layout(elements, SHEET_W, SHEET_H)
    assert overlaps == []
    assert overflows == []
