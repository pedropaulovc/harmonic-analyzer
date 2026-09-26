"""Offline contracts for the leader geometry the crank drawings gate on."""

from __future__ import annotations

import pytest

import _drawing_leaders as leaders


def test_segments_cross_only_on_a_proper_intersection() -> None:
    assert leaders.segments_cross(((0, 0), (1, 1)), ((0, 1), (1, 0)))
    assert not leaders.segments_cross(((0, 0), (1, 0)), ((0, 1), (1, 1)))
    # A shared endpoint, or a T that stops short, is not a crossing.
    assert not leaders.segments_cross(((0, 0), (1, 0)), ((1, 0), (1, 1)))
    assert not leaders.segments_cross(((0, 0), (1, 0)), ((0.5, 0.1), (0.5, 1)))


def test_a_stroke_ending_on_another_line_is_a_crossing_unless_declared() -> None:
    # Codex P2 on 81651bb85: a T-junction has one orientation product of 0,
    # which the proper-crossing test rejected.
    tol = leaders.COLLINEAR_TOLERANCE
    base = ((0.0, 0.0), (0.010, 0.0))
    t_leader = ((0.005, 0.0), (0.005, 0.010))
    assert leaders.segments_cross(base, t_leader)
    assert leaders.segments_cross(t_leader, base)
    assert leaders.segments_cross(base, ((0.005, tol / 2), (0.005, 0.010)))
    # Only a true shared endpoint is exempt, within the tolerance too.
    assert not leaders.segments_cross(base, ((0.010 + tol / 2, 0.0), (0.010, 0.010)))
    # A declared touch lets the T stand, never a proper crossing.
    assert not leaders.segments_cross(base, t_leader, touching="allowed")
    assert leaders.segments_cross(
        base, ((0.005, -0.001), (0.005, 0.010)), touching="allowed"
    )
    with pytest.raises(ValueError, match="touching"):
        leaders.segments_cross(base, t_leader, touching="maybe")
    groups = {"Dim": [base], "Leader": [t_leader]}
    assert leaders.leader_crossings(groups) == [("Dim", "Leader")]
    assert leaders.leader_crossings(groups, {frozenset(("Dim", "Leader"))}) == []


def test_a_leader_laid_along_another_line_crosses_it() -> None:
    # Main's rider on _drawing_leaders: collinear overlap prints as one stroke.
    tol = leaders.COLLINEAR_TOLERANCE
    base = ((0.0, 0.0), (0.010, 0.0))
    assert leaders.segments_cross(base, ((0.004, 0.0), (0.020, 0.0)))
    assert leaders.segments_cross(base, ((0.002, tol / 2), (0.006, -tol / 2)))
    assert leaders.segments_cross(((0.004, 0.0), (0.006, 0.0)), base)  # contained
    # Collinear but apart, touching end to end, or parallel beyond the tolerance.
    assert not leaders.segments_cross(base, ((0.012, 0.0), (0.020, 0.0)))
    assert not leaders.segments_cross(base, ((0.010, 0.0), (0.020, 0.0)))
    assert not leaders.segments_cross(base, ((0.002, 2 * tol), (0.008, 2 * tol)))


def test_distance_to_point_clamps_to_the_segment() -> None:
    assert leaders.distance_to_point(((0, 0), (2, 0)), (1, 1)) == pytest.approx(1.0)
    assert leaders.distance_to_point(((0, 0), (2, 0)), (3, 0)) == pytest.approx(1.0)
    assert leaders.distance_to_point(((1, 1), (1, 1)), (1, 2)) == pytest.approx(1.0)


def test_assert_leaders_clear_names_crossings_intrusions_and_missing_ink() -> None:
    through = [((-1.0, 1.0), (1.0, -1.0))]
    radius = [((-2.0, 0.5), (0.4, -0.1))]
    near = [((-0.3, 1.0), (-0.1, 0.4))]
    anywhere = {"A": (0.0, 9.0), "B": (0.0, 9.0)}
    with pytest.raises(RuntimeError, match=r"crossings \[\('A', 'B'\)\]"):
        leaders.assert_leaders_clear(
            {"A": through, "B": radius}, centre=(0.0, 0.0), keep_out={},
            lands_within=anywhere, label="t",
        )
    with pytest.raises(RuntimeError, match="inside the keep-out"):
        leaders.assert_leaders_clear(
            {"A": through}, centre=(0.0, 0.0), keep_out={"A": 0.2},
            lands_within=anywhere, label="t",
        )
    with pytest.raises(RuntimeError, match=r"no ink read for \['B'\]"):
        leaders.assert_leaders_clear(
            {"A": near, "B": []}, centre=(0.0, 0.0), keep_out={},
            lands_within=anywhere, label="t",
        )
    # Segments read in the wrong space (here: shifted far off the feature)
    # land nowhere near it, so the check cannot pass vacuously.
    shifted = [((x + 5.0, y + 5.0), (u + 5.0, v + 5.0)) for (x, y), (u, v) in near]
    with pytest.raises(RuntimeError, match="landing off its feature"):
        leaders.assert_leaders_clear(
            {"A": shifted}, centre=(0.0, 0.0), keep_out={"A": 0.2},
            lands_within={"A": (0.3, 0.5)}, label="t",
        )
    with pytest.raises(ValueError, match="no landing band"):
        leaders.assert_leaders_clear(
            {"A": near}, centre=(0.0, 0.0), keep_out={}, lands_within={}, label="t"
        )
    # A leader that ENDS on another's line (R12.7 ends at the centre) is a
    # T: a crossing unless the pair is declared touching.
    tee = [((-2.0, 0.5), (0.0, 0.0))]
    assert leaders.segments_cross(through[0], tee[0])
    with pytest.raises(RuntimeError, match=r"crossings \[\('A', 'B'\)\]"):
        leaders.assert_leaders_clear(
            {"A": through, "B": tee}, centre=(0.0, 0.0), keep_out={},
            lands_within=anywhere, label="t",
        )
    leaders.assert_leaders_clear(
        {"A": through, "B": tee}, centre=(0.0, 0.0), keep_out={},
        lands_within=anywhere, label="t", touching={frozenset(("A", "B"))},
    )
    leaders.assert_leaders_clear(
        {"A": near, "B": radius}, centre=(0.0, 0.0), keep_out={"A": 0.2},
        lands_within={"A": (0.3, 0.5), "B": (0.3, 0.5)}, label="t",
    )


def test_section_line_info_parses_chain_segments_arrow_shafts_and_heads() -> None:
    # One section line, two chain segments, two arrows, two labels.
    chain = [4, 0.1, 0.1, 0.0, 0.1, 0.2, 0.0, 4, 0.1, 0.2, 0.0, 0.1, 0.3, 0.0]
    arrow1 = [0.1, 0.1, 0.0, 0.12, 0.1, 0.0, 0.002, 0.004, 1]
    arrow2 = [0.1, 0.3, 0.0, 0.12, 0.3, 0.0, 0.002, 0.004, 1]
    text = [0.13, 0.1, 0.0, 0.13, 0.3, 0.0, 0.005]
    values = [1, 0, 2, *chain, *arrow1, *arrow2, *text]
    segments = leaders.parse_section_line_info(values)
    shaft1, shaft2 = ((0.1, 0.1), (0.12, 0.1)), ((0.1, 0.3), (0.12, 0.3))
    assert segments == [
        ((0.1, 0.1), (0.1, 0.2)),
        ((0.1, 0.2), (0.1, 0.3)),
        shaft1,
        *leaders.arrowhead_outline(shaft1, 0.002, 0.004),
        shaft2,
        *leaders.arrowhead_outline(shaft2, 0.002, 0.004),
    ]
    assert leaders.parse_section_line_info([]) == []
    with pytest.raises(RuntimeError, match="parsed"):
        leaders.parse_section_line_info([*values, 0.0])


def test_section_arrow_tip_is_the_shaft_end_off_the_chain_line() -> None:
    # Main's rider on the P2 fix: the tip is resolved from which shaft end
    # meets a chain endpoint, never assumed to be ``end``.
    chain = [4, 0.1, 0.1, 0.0, 0.1, 0.3, 0.0]
    text = [0.13, 0.1, 0.0, 0.13, 0.3, 0.0, 0.005]
    forward = [0.1, 0.3, 0.0, 0.12, 0.3, 0.0, 0.002, 0.004, 1]
    reversed_ = [0.12, 0.1, 0.0, 0.1, 0.1, 0.0, 0.002, 0.004, 1]
    segments = leaders.parse_section_line_info(
        [1, 0, 1, *chain, *reversed_, *forward, *text]
    )
    # The reversed shaft comes back as read, its head at its START.
    assert segments[1] == ((0.12, 0.1), (0.1, 0.1))
    assert segments[2:8] == leaders.arrowhead_outline(
        ((0.1, 0.1), (0.12, 0.1)), 0.002, 0.004
    )
    assert segments[9:] == leaders.arrowhead_outline(
        ((0.1, 0.3), (0.12, 0.3)), 0.002, 0.004
    )
    floating = [0.2, 0.1, 0.0, 0.22, 0.1, 0.0, 0.002, 0.004, 1]
    with pytest.raises(RuntimeError, match="section arrow 1: cannot tell its tip"):
        leaders.parse_section_line_info([1, 0, 1, *chain, *floating, *forward, *text])
    # A shaft lying along the chain touches it at both ends: ambiguous too.
    along = [0.1, 0.1, 0.0, 0.1, 0.3, 0.0, 0.002, 0.004, 1]
    with pytest.raises(RuntimeError, match="section arrow 2: cannot tell its tip"):
        leaders.parse_section_line_info([1, 0, 1, *chain, *forward, *along, *text])


def test_arrowhead_outline_has_both_size_readings_tipped_at_the_shaft_end() -> None:
    wings = leaders.arrowhead_outline(((0.0, 0.0), (0.010, 0.0)), 0.002, 0.004)
    # width along / height across, then height along / width across.
    assert wings == pytest.approx([
        ((0.010, 0.0), (0.008, 0.002)),
        ((0.010, 0.0), (0.008, -0.002)),
        ((0.008, 0.002), (0.008, -0.002)),
        ((0.010, 0.0), (0.006, 0.001)),
        ((0.010, 0.0), (0.006, -0.001)),
        ((0.006, 0.001), (0.006, -0.001)),
    ])
    assert leaders.arrowhead_outline(((0.0, 0.0), (0.0, 0.0)), 0.002, 0.004) == []


def test_a_leader_through_a_section_arrow_wing_crosses_the_section_line() -> None:
    # Codex P2 on 81651bb85: only the arrow shafts came back, so a leader
    # through a wing -- clear of the shaft -- read clear.
    chain = [4, 0.1, 0.1, 0.0, 0.1, 0.3, 0.0]
    arrow1 = [0.1, 0.1, 0.0, 0.12, 0.1, 0.0, 0.003, 0.003, 1]
    arrow2 = [0.1, 0.3, 0.0, 0.12, 0.3, 0.0, 0.003, 0.003, 1]
    text = [0.13, 0.1, 0.0, 0.13, 0.3, 0.0, 0.005]
    section = leaders.parse_section_line_info([1, 0, 1, *chain, *arrow1, *arrow2, *text])
    wing_only = [((0.1185, 0.1005), (0.1185, 0.110))]  # above the shaft, inside the head
    assert leaders.leader_crossings({"SectionLine": section, "Leader": wing_only}) == [
        ("SectionLine", "Leader")
    ]
    clear = [((0.1185, 0.1025), (0.1185, 0.110))]  # above the head's 1.5 half-breadth
    assert leaders.leader_crossings({"SectionLine": section, "Leader": clear}) == []


def test_points_inside_is_strict() -> None:
    box = (0.0, 0.0, 1.0, 1.0)
    assert leaders.points_inside([(0.5, 0.5), (1.5, 0.5), (1.0, 0.5)], box) == [(0.5, 0.5)]


def test_distance_to_box_is_zero_on_contact_and_the_gap_otherwise() -> None:
    box = (0.0, 0.0, 2.0, 1.0)
    # An end inside, straight through, and along an edge all touch.
    assert leaders.distance_to_box(((1.0, 0.5), (5.0, 5.0)), box) == 0.0
    assert leaders.distance_to_box(((-1.0, 0.5), (3.0, 0.5)), box) == 0.0
    assert leaders.distance_to_box(((2.0, -1.0), (2.0, 3.0)), box) == 0.0
    assert leaders.distance_to_box(((3.0, 0.0), (3.0, 1.0)), box) == pytest.approx(1.0)
    assert leaders.distance_to_box(((1.0, 1.5), (1.0, 4.0)), box) == pytest.approx(0.5)
    # Beside a corner the nearest point is the corner.
    assert leaders.distance_to_box(((3.0, 2.0), (3.0, 4.0)), box) == pytest.approx(2.0**0.5)
    # A diagonal passing a corner measures to the corner, not to an end.
    assert leaders.distance_to_box(((1.5, 2.0), (3.0, 0.5)), box) == pytest.approx(
        0.5 / 2.0**0.5
    )


def test_arrows_near_text_flags_foreign_text_within_the_clearance() -> None:
    assert leaders.ARROW_TEXT_CLEARANCE == 0.002
    texts = {"value": (0.010, 0.010, 0.016, 0.013), "note": (0.000, 0.000, 0.005, 0.004)}
    # A vertical arrow 0.55 mm right of the note, 4.45 mm from the value.
    arrows = {"A": [((0.00555, 0.0030), (0.00555, -0.0035))]}
    assert leaders.arrows_near_text(arrows, texts) == [("A", "note", pytest.approx(0.00055))]
    # The arrowhead's half breadth comes off the gap.
    ((owner, name, gap),) = leaders.arrows_near_text(arrows, texts, half_width=0.0003)
    assert (owner, name, gap) == ("A", "note", pytest.approx(0.00025))
    # An arrow inside the text is at 0, not negative.
    inside = {"B": [((0.012, 0.011), (0.012, 0.020))]}
    assert leaders.arrows_near_text(inside, texts, half_width=0.0003) == [("B", "value", 0.0)]


def test_arrows_near_text_skips_own_text_empty_ink_and_clear_arrows() -> None:
    texts = {"value": (0.010, 0.010, 0.016, 0.013)}
    # Its own value is not foreign text.
    assert leaders.arrows_near_text({"value": [((0.009, 0.011), (0.009, 0.005))]}, texts) == []
    assert leaders.arrows_near_text({"A": []}, texts) == []
    # 2.5 mm off is clear of the 2 mm default, and near under a 3 mm one.
    clear = {"A": [((0.0185, 0.011), (0.0185, 0.005))]}
    assert leaders.arrows_near_text(clear, texts) == []
    assert leaders.arrows_near_text(clear, texts, clearance=0.003) == [
        ("A", "value", pytest.approx(0.0025))
    ]
