"""The face-identity comparisons, offline.

``diag_mcmaster_lib.gate_and_save`` already fails a build whose SOLID moved:
volume, surface area, centre of mass, face count and (at or under
``FACE_MULTISET_LIMIT`` faces) the exact sorted face-area multiset, all against
the vendor ground truth.  What it cannot see is a solid that is geometrically
identical while its FACES are different faces.  A build never notices; a
stored downstream reference would, days later, as a drawing or assembly
defect.

``probe_face_identity`` splits that into two questions, and so does this file:

* ``diff_census`` -- geometry, face for face, from two captures.  It must NOT
  compare stored references: ``GetPersistReference3`` documents its own
  representation as changing "possibly from rebuild to rebuild ... but their
  usage in finding the correct entity will be consistent", so a byte
  difference is not a defect and byte equality is not a proof.
* ``diff_resolution`` -- whether a reference captured from the old part still
  resolves, in the new part, to the face it was taken from.  Replaying it
  needs a seat; turning the outcome into a verdict does not, and that is the
  half tested here.
"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagnostics.probe_face_identity import (  # noqa: E402
    canonical,
    diff_census,
    diff_resolution,
)


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


def test_a_changed_reference_alone_is_not_a_difference() -> None:
    """Reference BYTES are not the contract, and this is the trap.

    ``GetPersistReference3`` documents its own representation as changing
    "possibly from rebuild to rebuild ... but their usage in finding the
    correct entity will be consistent across rebuilds".  So a byte comparison
    reports failures that are not failures -- and a probe that cries wolf on
    an ordinary rebuild gets switched off, which costs the check as well.
    Whether a stored reference still finds its face is ``diff_resolution``'s
    question, and it has to be asked on a seat.
    """
    before = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "aaaa"))
    after = _census(_face(12.5, (0, 0, 0, 5, 5, 0), "cccc"))

    assert diff_census(before, after) == []


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


def test_a_changed_reference_among_identical_faces_still_pairs_cleanly() -> None:
    """References only DISAMBIGUATE ties; they never produce a verdict.

    Three congruent faces and one changed reference is exactly the shape an
    ordinary rebuild is allowed to take, so the geometry comparison has to
    stay quiet: the worst a mispaired tie can do here is compare one
    identical face against another identical one.
    """
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

    assert diff_census(before, after) == []


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


_OWN_BODY = [0.0, 0.0, 0.0, 5.0, 5.0, 5.0]
_OTHER_BODY = [9.0, 0.0, 0.0, 14.0, 5.0, 5.0]


def _row(
    state,
    *,
    area: float = 12.5,
    resolved_area: float | None = None,
    owner: list[float] | None = _OWN_BODY,
):
    """One replayed reference: what was stored, what came back."""
    stored = _face(area, (0, 0, 0, 5, 5, 0), "cGVyc2lzdA==")
    row: dict = {"stored": stored, "body": "Body1", "body_box_mm": _OWN_BODY}
    if state is not None:
        row["state"] = state
    if resolved_area is not None:
        row["resolved"] = _face(resolved_area, (0, 0, 0, 5, 5, 0), "")
        if owner is not None:
            row["resolved_body_box_mm"] = owner
    return row


def test_references_that_all_find_their_own_face_report_nothing() -> None:
    """The verdict this whole exercise is trying to earn."""
    rows = [
        _row(0, area=12.5, resolved_area=12.5),
        _row(0, area=3.25, resolved_area=3.25),
    ]

    assert diff_resolution(rows) == []


def test_a_deleted_reference_is_reported_by_name() -> None:
    """swPersistReferencedObjectStates_e is a bitmask; 0 is the only pass.

    This is the real failure: the face the rewrite produced is a different
    face, so a stored annotation attachment or mate now points at nothing.
    """
    problems = diff_resolution([_row(4)])

    assert problems == ["identity: face 0 (area 12.5 mm^2) no longer resolves: deleted"]


def test_several_state_bits_are_all_named() -> None:
    problems = diff_resolution([_row(6)])

    assert problems == [
        "identity: face 0 (area 12.5 mm^2) no longer resolves: suppressed, deleted"
    ]


def test_a_reference_that_finds_the_wrong_face_is_reported() -> None:
    """A healthy state is not enough; WHAT it found has to be the same face.

    This is the shape a renumbering takes when the handle happens to stay
    valid -- it resolves, so a naive check passes, and the annotation quietly
    lands on the neighbouring face.
    """
    problems = diff_resolution([_row(0, area=12.5, resolved_area=3.25)])

    assert len(problems) == 1
    assert problems[0].startswith("identity:")
    assert "DIFFERENT face (area 3.25 mm^2)" in problems[0]


def test_a_healthy_state_with_no_object_is_reported() -> None:
    """State 0 and nothing returned is not a pass, it is a contradiction."""
    problems = diff_resolution([_row(0)])

    assert len(problems) == 1
    assert "resolved to no object at all" in problems[0]


def test_a_row_with_no_recorded_state_proves_nothing() -> None:
    """A resolve pass that lost its outcome must not read as a pass.

    The probe writes a row per face whatever happens, including when the COM
    call came back in a shape it could not read; treating that as success is
    how a probe becomes decoration.
    """
    problems = diff_resolution([_row(None, resolved_area=12.5)])

    assert len(problems) == 1
    assert "no recorded resolution state" in problems[0]


def test_rebuild_noise_in_the_resolved_face_is_tolerated() -> None:
    """The resolved face is measured, so it gets the same tolerance."""
    rows = [_row(0, area=12.5, resolved_area=12.5 + 5e-5)]

    assert diff_resolution(rows) == []


def test_a_reference_that_lands_in_another_body_is_reported() -> None:
    """Congruent bodies make a drifted reference look perfect.

    91247A720's three raised grade marks are congruent separate bodies, so a
    reference that now finds another mark's corresponding face matches on
    area, box and surface type. Only the OWNING body tells them apart, and
    without that check the probe would certify a broken reference.
    """
    problems = diff_resolution(
        [_row(0, area=12.5, resolved_area=12.5, owner=_OTHER_BODY)]
    )

    assert len(problems) == 1
    assert problems[0].startswith("identity:")
    assert "DIFFERENT body" in problems[0]


def test_a_resolved_face_with_no_owning_body_recorded_proves_nothing() -> None:
    """``IFace2.GetBody`` returning nothing is a gap, not a pass."""
    problems = diff_resolution([_row(0, area=12.5, resolved_area=12.5, owner=None)])

    assert len(problems) == 1
    assert "owning body of one side was not recorded" in problems[0]


def test_congruent_bodies_whose_faces_differ_are_paired_by_their_faces() -> None:
    """Equal extents are not enough to pair two bodies.

    A box tie is common -- congruent marks, a mirrored pair -- and the
    reference bytes cannot break it, because they are allowed to change on
    rebuild. Pairing such bodies by enumeration order would report both of
    them as having swapped faces, out of nothing.
    """
    ribbed = {
        "name": "Ribbed",
        "box_mm": [0.0, 0.0, 0.0, 5.0, 5.0, 5.0],
        "faces": [_face(4.0, (0, 0, 0, 2, 2, 0), "r1")],
    }
    smooth = {
        "name": "Smooth",
        "box_mm": [0.0, 0.0, 0.0, 5.0, 5.0, 5.0],
        "faces": [_face(9.0, (0, 0, 0, 3, 3, 0), "s1")],
    }
    renumbered = [
        {**smooth, "faces": [_face(9.0, (0, 0, 0, 3, 3, 0), "s2")]},
        {**ribbed, "faces": [_face(4.0, (0, 0, 0, 2, 2, 0), "r2")]},
    ]

    before = {"part": "p", "bodies": [ribbed, smooth]}
    after = {"part": "p", "bodies": renumbered}

    assert diff_census(before, after) == []
