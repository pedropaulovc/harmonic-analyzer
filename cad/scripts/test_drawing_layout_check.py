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
    LayoutElement,
    audit_layout,
    find_overflows,
    find_overlaps,
)

# ASME B sheet used by every project drawing (meters).
SHEET_W = 0.4318
SHEET_H = 0.2794


def _el(label, x0, y0, x1, y1, kind="view", overlap_exempt=False):
    return LayoutElement(label, kind, x0, y0, x1, y1, overlap_exempt=overlap_exempt)


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


def test_overlap_exempt_view_never_collides():
    # An isometric view's box swallows a nearby label, but an overlap-exempt
    # element is excluded from overlap detection so it does not false-positive.
    iso = _el("ISO", 0.17, 0.14, 0.40, 0.28, overlap_exempt=True)
    label = _el("LBL", 0.14, 0.14, 0.22, 0.145, kind="note")
    assert find_overlaps([iso, label]) == []
    # ... but the same box NOT exempt WOULD be flagged, proving the exclusion is
    # what suppresses it (not a tolerance fluke).
    solid = _el("ISO", 0.17, 0.14, 0.40, 0.28, overlap_exempt=False)
    assert len(find_overlaps([solid, label])) == 1


def test_overlap_exempt_element_still_checked_for_overflow():
    # Codex #269: exemption suppresses collisions only -- a pictorial view or
    # leadered note mis-placed OFF the sheet must still be flagged.
    iso_off = _el("ISO", 0.17, 0.14, 0.40, SHEET_H + 0.02, overlap_exempt=True)
    note_off = _el("N", -0.03, 0.10, 0.05, 0.12, kind="note", overlap_exempt=True)
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
    # absorbs GetOutline padding, even for an overlap-exempt pictorial view.
    view = _el("V", 0.05, 0.10, 0.15, SHEET_H + 0.0015, overlap_exempt=True)
    assert find_overflows([view], SHEET_W, SHEET_H) == []


def test_large_note_on_its_own_view_is_still_flagged():
    # Codex #269: the tag exemption is size-gated, so a general-notes block
    # (large) centered inside its owning view is NOT exempt and the collision is
    # reported -- only a small tag centered inside its view is suppressed.
    view = _el("V1", 0.05, 0.05, 0.20, 0.20)
    big_note = _el("N", 0.08, 0.08, 0.18, 0.15, kind="note")  # 100 x 70 mm
    assert len(find_overlaps([view, big_note])) == 1


def test_lever_bushing_real_boxes_are_clean():
    # Measured element boxes from the shipped lever-bushing drawing (meters):
    # 3 views (V3 is the isometric -> overlap-exempt) + the 2 general-notes blocks.
    elements = [
        _el("V1", 0.05041, 0.17541, 0.10959, 0.23459),
        _el("V2", 0.17553, 0.17541, 0.20293, 0.23459),
        _el("V3", 0.28670, 0.16671, 0.34330, 0.24329, overlap_exempt=True),
        _el("N18", 0.01390, 0.08939, 0.15347, 0.11211, kind="note"),
        _el("N19", 0.16970, 0.06440, 0.32193, 0.10529, kind="note"),
    ]
    overlaps, overflows = audit_layout(elements, SHEET_W, SHEET_H)
    assert overlaps == []
    assert overflows == []


def test_platen_guide_real_boxes_are_clean():
    # Measured off the shipped platen-guide drawing: 2 ortho views, the iso view
    # (overlap-exempt), the general-notes block, the "PLATEN-MATING FACE" label
    # (which bbox-overlaps the iso view), and the 10x4 hole table on the sheet.
    # The iso view's outline reaches ymax=280.9 mm on a 279.4 mm sheet -- within
    # the 3 mm overflow allowance, so it does not false-positive despite now
    # being overflow-checked.
    elements = [
        _el("V1", 0.03441, 0.10191, 0.34559, 0.11809),
        _el("V2", 0.35941, 0.10191, 0.38059, 0.11809),
        _el("V3", 0.16981, 0.13910, 0.40019, 0.28090, overlap_exempt=True),
        _el("N46", 0.01390, 0.02999, 0.17262, 0.07511, kind="note"),
        _el("N47", 0.14373, 0.14067, 0.22163, 0.14522, kind="note"),
        _el("T45", 0.01400, 0.16874, 0.15876, 0.25800, kind="table"),
    ]
    overlaps, overflows = audit_layout(elements, SHEET_W, SHEET_H)
    assert overlaps == []
    assert overflows == []
