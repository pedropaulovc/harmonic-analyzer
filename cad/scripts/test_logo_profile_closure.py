r"""Offline invariants for the profiles that are closed by AUTHORED relations.

These tests pin the two profiles that were rewritten after the 2026-09-17
``logo ring extrude failed`` leaf on ``swmaker000005@5``: the 91247A720 logo
ring and the 99607A213 flare lens.  They run without SolidWorks, against the
real production geometry functions -- not a reimplementation of them -- so a
coordinate edit that opens a profile fails here, in seconds, instead of on a
farm worker twenty minutes into a release build.

What they do NOT claim: they do not prove the profile extrudes.  The coincident
endpoints were ALREADY bit-exact before the rewrite (measured: gap 0.000e+00
across all 15 pairs), and per the SolidWorks learning
``sketch-inference-endpoint-merging.md`` identical coordinates are NOT a merge
-- "coincidence is an inference-time behavior, not a geometry-time one".  So
exactness was necessary, already true, and never sufficient.  What these tests
pin is the property that makes the authored ``merge`` relations resolvable at
all: **each shared vertex must be written as the same expression in both
segments**, so the two doubles are identical and the pairing is unambiguous.
Closure itself is guaranteed by the relations; the seat's outcome is recorded
once after ``exit_sketch`` (``_common.record_sketch_closure``) as evidence, not
as the guarantee.
"""

from __future__ import annotations

import math

import pytest

from diagnostics.diag_build_91247A720 import (
    LOGO_APEX_CENTRE,
    LOGO_BOTTOM_LEFT_CENTRE,
    LOGO_BOTTOM_RIGHT_CENTRE,
    LOGO_OUTER_R,
    logo_ring_profile,
)
from diagnostics.diag_build_99607A213 import (
    TS_FLARE_CENTRE,
    TS_FLARE_Z0,
    TS_FLARE_Z1,
    TS_SH_R,
    flare_profile,
)
from diagnostics.sketch_profile import (
    Arc,
    Line,
    OpenProfileError,
    arc_radii_mm,
    arc_sweep_deg,
    closed_loops,
    endpoint_merges,
    minor_arc,
)


def test_logo_ring_vertices_are_bit_identical_across_segments() -> None:
    """Every shared vertex is the SAME double in both segments that meet there.

    This is the property the authored merges rely on: ``endpoint_merges``
    groups endpoints on ``==``, so a vertex written as ``ct[0] + r * nx`` in one
    segment and ``ct[0] + r * 0.866...`` in its neighbour would be two
    different vertices even though both "are" the same point.
    """
    segments = logo_ring_profile()
    merges = endpoint_merges(segments)

    assert len(segments) == 9
    assert len(merges) == 9  # nine vertices, each shared by exactly two ends
    for (first, first_end), (second, second_end) in merges:
        a = getattr(segments[first], first_end)
        b = getattr(segments[second], second_end)
        assert a == b, f"segment {first}.{first_end} vs {second}.{second_end}"
        # Not merely close: identical, in both coordinates.
        assert a[0] == b[0] and a[1] == b[1]


def test_logo_ring_forms_a_ring_of_exactly_two_loops() -> None:
    """Outer boundary plus inner core, which is what ``loops=2`` asserts live."""
    segments = logo_ring_profile()
    loops = closed_loops(segments)

    assert len(loops) == 2
    assert sorted(len(loop) for loop in loops) == [3, 6]
    # The 3-segment loop is the sharp inner triangle; the 6-segment loop is the
    # offset outer boundary (3 lines + 3 corner arcs).
    inner = next(loop for loop in loops if len(loop) == 3)
    assert all(isinstance(segments[i], Line) for i in inner)
    outer = next(loop for loop in loops if len(loop) == 6)
    assert sum(isinstance(segments[i], Arc) for i in outer) == 3


def test_logo_inner_vertices_are_the_outer_corner_arc_centres() -> None:
    """The 0.400 mm snap competitor, pinned as intentional.

    Each inner-triangle vertex IS an outer corner arc's centre point, so it
    sits exactly ``LOGO_OUTER_R`` from four distinct outer-loop points.  That
    is the cluster that made inference authoring a coin flip at low px/mm, and
    it is why this profile must never be drawn through inference again.  The
    geometry is correct and stays; the authoring path is what changed.
    """
    segments = logo_ring_profile()
    arcs = [s for s in segments if isinstance(s, Arc)]
    centres = {s.center for s in arcs}

    assert centres == {
        LOGO_APEX_CENTRE,
        LOGO_BOTTOM_RIGHT_CENTRE,
        LOGO_BOTTOM_LEFT_CENTRE,
    }
    for arc in arcs:
        start_r, end_r = arc_radii_mm(arc)
        assert start_r == pytest.approx(LOGO_OUTER_R, abs=1e-12)
        assert end_r == pytest.approx(LOGO_OUTER_R, abs=1e-12)


def test_logo_corner_arcs_sweep_120_degrees_counter_clockwise() -> None:
    """``add_arc`` passes CCW; ``minor_arc`` must have reordered every corner.

    The profile is authored clockwise, so each corner arc's authored endpoint
    order is the reverse of the one ``SketchManager.CreateArc`` needs.  If
    ``minor_arc`` stopped reordering, every corner would be drawn as its 240
    degree complement and the ring would self-intersect.
    """
    segments = logo_ring_profile()
    for arc in (s for s in segments if isinstance(s, Arc)):
        assert arc_sweep_deg(arc) == pytest.approx(120.0, abs=1e-9)


def test_flare_lens_is_one_closed_loop_with_a_minor_arc() -> None:
    segments = flare_profile()
    merges = endpoint_merges(segments)

    assert len(segments) == 2
    assert len(merges) == 2
    assert len(closed_loops(segments)) == 1
    arc = next(s for s in segments if isinstance(s, Arc))
    assert arc_sweep_deg(arc) < 180.0


def test_flare_arc_dips_to_the_vendor_minimum_radius() -> None:
    """The centre-based arc reproduces the lens the 3-point form approximated.

    The replaced code passed ``(2.096452, 1.905)`` as the arc's mid-point: a
    6-decimal ROUNDING of the true minimum-radius point, so SolidWorks fitted a
    circle 9.5e-08 mm off the intended one and re-solved the endpoints.  Centre
    plus endpoints puts the radius exactly where the vendor equation
    (D2 = D1 * 0.75) puts it.
    """
    segments = flare_profile()
    arc = next(s for s in segments if isinstance(s, Arc))
    radius = arc_radii_mm(arc)[0]
    min_radius = arc.center[0] - radius

    assert arc.center == TS_FLARE_CENTRE
    assert arc.center[1] == (TS_FLARE_Z0 + TS_FLARE_Z1) / 2.0
    assert min_radius == pytest.approx(2.0964519054308415, abs=1e-15)
    # The old literal, and the error it carried.
    assert min_radius != 2.096452
    assert abs(min_radius - 2.096452) == pytest.approx(9.46e-08, rel=0.05)
    # Both endpoints sit on the shoulder OD, which is what makes this profile
    # the silhouette-snap case the learning describes.
    for end in ("start", "end"):
        assert getattr(arc, end)[0] == TS_SH_R


def test_a_one_ulp_gap_is_rejected_rather_than_left_to_the_seat() -> None:
    """The failure mode this suite exists to catch, injected deliberately."""
    segments = list(logo_ring_profile())
    line = segments[0]
    assert isinstance(line, Line)
    nudged = (math.nextafter(line.start[0], math.inf), line.start[1])
    assert nudged != line.start
    segments[0] = Line(nudged, line.end)

    with pytest.raises(OpenProfileError) as raised:
        endpoint_merges(tuple(segments))
    assert "expected exactly 2" in str(raised.value)
    assert "the profile is open" in str(raised.value)


def test_three_segments_meeting_at_a_point_is_rejected() -> None:
    """``swSketchCheckFeatureStatus_ThreeEnts`` (4), caught offline.

    SolidWorks reports "an endpoint is wrongly shared by multiple entities" as
    a distinct sketch-check status.  The offline pairing refuses the same shape,
    so the two agree by construction instead of by coincidence.
    """
    shared = (0.0, 0.0)
    segments = (
        Line(shared, (1.0, 0.0)),
        Line(shared, (0.0, 1.0)),
        Line(shared, (-1.0, 0.0)),
        Line((1.0, 0.0), (0.0, 1.0)),
    )

    with pytest.raises(OpenProfileError) as raised:
        endpoint_merges(segments)
    assert "shared by 3 segment ends" in str(raised.value)


def test_a_semicircular_span_has_no_unique_minor_arc() -> None:
    """Refused rather than silently picking one of two equal arcs."""
    with pytest.raises(OpenProfileError):
        minor_arc((0.0, 0.0), (1.0, 0.0), (-1.0, 0.0))


def test_an_endpoint_that_reached_the_arc_centre_is_refused() -> None:
    """The exact shape an inference snap to an arc centre produces.

    This is one of the two OFFLINE gates, and it is where a collapsed corner is
    actually caught -- NOT at the closure read-back, which raises only on a
    measured zero-contour sketch.  In the logo ring the
    nearest wrong snap target for an outer arc's endpoint is that arc's own
    centre, 0.400 mm away, so "endpoint == centre" is the realised failure and
    it must be named, not inferred from a zero sweep.
    """
    centre = LOGO_BOTTOM_RIGHT_CENTRE
    with pytest.raises(OpenProfileError, match="IS the centre"):
        minor_arc(centre, centre, (centre[0] + LOGO_OUTER_R, centre[1]))
    with pytest.raises(OpenProfileError, match="IS the centre"):
        minor_arc(centre, (centre[0] + LOGO_OUTER_R, centre[1]), centre)


def test_a_collapsed_segment_is_refused_instead_of_pairing_with_itself() -> None:
    """The one degenerate shape that SATISFIES the degree-two pairing.

    A zero-length segment puts both of its own ends on a single vertex, so that
    vertex has degree two and the dangling-end check passes it; ``closed_loops``
    then reports it as a loop in its own right.  A collapsed segment would
    therefore be counted toward the asserted loop total and authored straight
    into ``add_line``/``add_arc`` as a line (or arc) with identical endpoints --
    which is exactly the residue of the snap these gates exist to catch.  Both
    segment kinds are covered because ``Arc`` is constructible without going
    through ``minor_arc``, whose own zero-radius/zero-sweep refusals do not
    apply to a directly built arc.
    """
    collapsed = (3.0, 4.0)
    square = (
        Line((0.0, 0.0), (1.0, 0.0)),
        Line((1.0, 0.0), (1.0, 1.0)),
        Line((1.0, 1.0), (0.0, 1.0)),
        Line((0.0, 1.0), (0.0, 0.0)),
    )
    assert endpoint_merges(square), "the control profile must be accepted"

    for degenerate in (
        Line(collapsed, collapsed),
        Arc((0.0, 0.0), collapsed, collapsed),
    ):
        segments = (*square, degenerate)
        # Degree two, by self-reference: the check it must NOT slip past.
        assert len(closed_loops(segments)) == 2
        with pytest.raises(OpenProfileError, match="starts and ends at") as raised:
            endpoint_merges(segments)
        assert "pairs with itself" in str(raised.value)
        assert str(collapsed) in str(raised.value)
