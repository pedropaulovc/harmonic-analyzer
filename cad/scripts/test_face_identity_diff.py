"""The face-identity comparison, offline.

``diag_mcmaster_lib.gate_and_save`` already fails a build whose SOLID moved:
volume, surface area, centre of mass, face count and (at or under
``FACE_MULTISET_LIMIT`` faces) the exact sorted face-area multiset, all against
the vendor ground truth.  What it cannot see is a solid that is geometrically
identical while its FACES are different faces -- same areas, same boxes, new
persistent references.  A build never notices; a stored downstream reference
would, days later, as a drawing or assembly defect.

``probe_face_identity`` exists to reduce that to a diff, and the comparison
itself is pure, so it is tested here rather than on a seat.  What needs the
seat is only the capture.
"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnostics.probe_face_identity import canonical, diff_census  # noqa: E402


def _face(area: float, box: tuple[float, ...], persist: str, surface: int = 4001):
    return {
        "area_mm2": area,
        "box_mm": list(box),
        "surface": surface,
        "persist": persist,
    }


def _census(*faces: dict, box: tuple[float, ...] = (0.0, 0.0, 0.0, 5.0, 5.0, 5.0)):
    return {
        "part": "91247A720-replica.SLDPRT",
        "bodies": [{"name": "Body1", "box_mm": list(box), "faces": list(faces)}],
    }


def test_the_same_part_twice_reports_nothing() -> None:
    census = _census(
        _face(12.5, (0, 0, 0, 5, 5, 0), "aaaa"),
        _face(3.25, (0, 0, 0, 5, 0, 5), "bbbb"),
    )

    assert diff_census(census, census) == []


def test_face_enumeration_order_is_not_a_contract() -> None:
    """SolidWorks may enumerate faces differently; that is not a difference.

    Comparing in document order would report noise on every run and the probe
    would stop being usable, which is the same as not having it.
    """
    first = _face(12.5, (0, 0, 0, 5, 5, 0), "aaaa")
    second = _face(3.25, (0, 0, 0, 5, 0, 5), "bbbb")

    assert diff_census(_census(first, second), _census(second, first)) == []


def test_a_renumbered_face_is_reported_as_identity_not_geometry() -> None:
    """The failure this probe exists for: same solid, different faces.

    Wording them apart matters. A geometry line means the rewrite changed the
    part and the vendor gate would have caught it too; an identity line means
    the part is right and only a stored reference moved, which nothing in a
    build can see.
    """
    before = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "aaaa"))
    after = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "cccc"))

    problems = diff_census(before, after)

    assert len(problems) == 1
    assert problems[0].startswith("identity:")
    assert "aaaa -> cccc" in problems[0]


def test_a_lost_face_is_reported_as_geometry() -> None:
    """A dropped face has no counterpart, so it is named rather than counted.

    The body bounding box is deliberately left alone: a face can vanish
    without changing the extents (a merged tangent pair, a fillet that
    swallowed its neighbour), which is precisely the case a count-only check
    on the bodies would let through.
    """
    before = _census(
        _face(12.5, (0, 0, 0, 5, 5, 0), "aaaa"),
        _face(3.25, (0, 0, 0, 5, 0, 5), "bbbb"),
    )
    after = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "aaaa"))

    problems = diff_census(before, after)

    assert problems == ["geometry: body 0 lost a face (area 3.25 mm^2)"]


def test_a_moved_face_is_reported_as_geometry_not_identity() -> None:
    """A collapsed corner shows up here as a face that moved, not as a rename."""
    before = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "aaaa"))
    after = _census(_face(12.5, (0, 0, 0, 5, 4.6, 0), "aaaa"))

    problems = diff_census(before, after)

    assert len(problems) == 1
    assert problems[0].startswith("geometry:")
    assert "box moved" in problems[0]


def test_a_surface_type_change_is_geometry() -> None:
    """Same area and box, different surface: a fit, not the authored curve.

    This is the shape a re-fitted spline or a 3-point arc rebuilt as something
    else would take, and it must not be excused as a renumbering.
    """
    before = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "aaaa", surface=4001))
    after = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "aaaa", surface=4003))

    problems = diff_census(before, after)

    assert len(problems) == 1
    assert problems[0].startswith("geometry:")
    assert "surface type" in problems[0]


def test_a_census_with_no_persistent_reference_is_not_a_match() -> None:
    """Two failed reads must not compare equal.

    A probe that reports "same references" because neither side read one is
    worse than no probe: it produces the evidence without the check. The
    capture refuses an empty ``GetPersistReference3`` for the same reason, so
    this can only arrive from a hand-written or truncated census file.
    """
    before = _census(_face(12.5, (0, 0, 0, 5, 5, 0), ""))
    after = _census(_face(12.5, (0, 0, 0, 5, 5, 0), ""))

    problems = diff_census(before, after)

    assert len(problems) == 1
    assert problems[0].startswith("identity:")
    assert "nothing was compared" in problems[0]


def test_a_truncated_box_is_reported_rather_than_zipped_away() -> None:
    """A short box would otherwise pair up silently and read as unmoved."""
    before = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "aaaa"))
    after = _census(_face(12.5, (0, 0), "aaaa"))

    problems = diff_census(before, after)

    assert len(problems) == 1
    assert problems[0].startswith("geometry:")
    assert "not six corners" in problems[0]


def test_noise_below_the_tolerance_is_not_a_difference() -> None:
    """Rebuilt geometry is not bit-identical, and must not have to be.

    Every consumer in this repo picks faces by coordinate, so a tolerance is
    the honest comparison; a probe that cried wolf on the last decimal place
    would be switched off.
    """
    before = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "aaaa"))
    after = _census(_face(12.5 + 5e-5, (0, 0, 0, 5, 5, 5e-7), "aaaa"))

    assert diff_census(before, after) == []


def test_multi_body_parts_are_paired_by_geometry() -> None:
    """91247A720 ships its raised grade marks as separate bodies.

    Body order is no more a contract than face order, so the pairing is by
    box -- otherwise the grade marks would look swapped.
    """
    small = {
        "name": "Mark",
        "box_mm": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        "faces": [_face(1.0, (0, 0, 0, 1, 1, 0), "mmmm")],
    }
    large = {
        "name": "Bolt",
        "box_mm": [0.0, 0.0, 0.0, 9.0, 9.0, 9.0],
        "faces": [_face(81.0, (0, 0, 0, 9, 9, 0), "bbbb")],
    }
    before = {"part": "p", "bodies": [small, large]}
    after = {"part": "p", "bodies": [large, small]}

    assert diff_census(before, after) == []
    assert [body["name"] for body in canonical(before)] == ["Mark", "Bolt"]


def test_identical_faces_are_paired_by_reference_not_by_order() -> None:
    """Ties are the RULE on this part, not an edge case.

    91247A720 has three identical raised grade marks and many identical
    fillet faces, so any number of faces share a sort key.  Position among
    equals is enumeration order, which SolidWorks does not promise, so
    comparing by position would report renumberings that never happened --
    and a probe that cries wolf on the part it was written for is a probe
    that gets switched off.
    """
    faces = [
        _face(1.0, (0, 0, 0, 1, 1, 0), "p1"),
        _face(1.0, (0, 0, 0, 1, 1, 0), "p2"),
        _face(1.0, (0, 0, 0, 1, 1, 0), "p3"),
    ]

    assert diff_census(_census(*faces), _census(faces[2], faces[0], faces[1])) == []


def test_one_changed_reference_among_identical_faces_is_reported_once() -> None:
    """The tie tolerance must not swallow a real renumbering."""
    before = _census(
        _face(1.0, (0, 0, 0, 1, 1, 0), "p1"),
        _face(1.0, (0, 0, 0, 1, 1, 0), "p2"),
        _face(1.0, (0, 0, 0, 1, 1, 0), "p3"),
    )
    after = _census(
        _face(1.0, (0, 0, 0, 1, 1, 0), "p1"),
        _face(1.0, (0, 0, 0, 1, 1, 0), "p2"),
        _face(1.0, (0, 0, 0, 1, 1, 0), "zzz"),
    )

    problems = diff_census(before, after)

    assert problems == [
        "identity: body 0 face (area 1.0 mm^2) is the same face geometrically "
        "but its persistent reference changed (p3 -> zzz)"
    ]


def test_tolerated_noise_that_reverses_the_sort_order_is_not_a_difference() -> None:
    """Two faces closer together than the tolerance can swap places.

    Sorting rounds; the comparison tolerates. So rebuild noise smaller than
    the tolerance can still reverse the sort key, and pairing by position
    would then compare face A against face B and report two identity
    changes out of nothing.
    """
    before = _census(
        _face(1.0, (0, 0, 0, 1, 1, 0), "p1"),
        _face(1.00005, (0, 0, 0, 1, 1, 0), "p2"),
    )
    after = _census(
        _face(1.00004, (0, 0, 0, 1, 1, 0), "p1"),
        _face(0.99999, (0, 0, 0, 1, 1, 0), "p2"),
    )

    assert diff_census(before, after) == []


def test_identical_bodies_are_paired_by_their_face_references() -> None:
    """The three grade marks are congruent, so their boxes tie as well."""
    marks = [
        {
            "name": f"Mark{index}",
            "box_mm": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
            "faces": [_face(1.0, (0, 0, 0, 1, 1, 0), reference)],
        }
        for index, reference in enumerate(("m1", "m2", "m3"))
    ]
    before = {"part": "p", "bodies": marks}
    after = {"part": "p", "bodies": [marks[1], marks[2], marks[0]]}

    assert diff_census(before, after) == []
