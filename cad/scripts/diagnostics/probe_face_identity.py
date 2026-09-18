"""Prove a rebuilt replica has the SAME FACES, not merely the same solid.

The 91247A720 / 99607A213 rewrites changed how the profiles are authored
(direct-to-database plus explicit ``merge`` relations instead of inference).
``diag_mcmaster_lib.gate_and_save`` already fails the build if the resulting
SOLID moves -- volume, surface area, centre of mass, face count and, for parts
at or under ``FACE_MULTISET_LIMIT`` faces, the exact sorted face-area multiset,
all against the vendor ground truth.  What that gate cannot see is a solid that
is geometrically identical while its FACES are different faces: same areas,
same boxes, different persistent references.  Downstream work that resolves a
face and remembers it -- a stored annotation attachment, a mate, a face-level
appearance -- would then attach to nothing, and would surface days later as a
drawing or assembly defect rather than as a build failure.

This probe reduces that question to a diff.  Capture a census from each saved
replica and compare them::

    # No seat.  Pure comparison of two captured censuses.
    uv run python cad/scripts/diagnostics/probe_face_identity.py \
        --diff before.json after.json

    # Needs the COM seat.  Read-only: it OPENS a saved replica and reads it,
    # it does not rebuild anything and it does not run doit.
    uv run python cad/scripts/diagnostics/probe_face_identity.py \
        --capture cad/out/reference/91247A720-replica.SLDPRT \
        --output cad/out/reports/91247A720-faces-after.json

The "before" census does not require building the old code: any replica saved
by a pre-change build is a valid subject, including one already published by a
release build.

Exit code 1 and one line per difference if the two censuses disagree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Faces that differ by less than this are the same face to every consumer in
# this repo, all of which pick faces by coordinate (``IFace2.GetBox`` in the
# builders, a view XY pick in the drawings) rather than by a name string.
AREA_TOL_MM2 = 1e-4
BOX_TOL_MM = 1e-6


def face_key(face: dict) -> tuple:
    """Canonical order for faces: geometry only, never the stored reference.

    Ordering by the persistent reference would make a renumbering look like a
    reordering and hide exactly what this probe is for.
    """
    return (
        round(float(face["area_mm2"]), 6),
        tuple(round(float(v), 9) for v in face["box_mm"]),
        int(face.get("surface", -1)),
    )


def body_key(body: dict) -> tuple:
    return (
        tuple(round(float(v), 9) for v in body.get("box_mm") or ()),
        len(body.get("faces") or ()),
    )


def canonical(census: dict) -> list[dict]:
    """``census`` with bodies and faces in geometry order.

    Body and face ORDER is not a contract -- SolidWorks is free to enumerate
    them differently -- so comparing in document order would report noise.
    """
    bodies = []
    for body in sorted(census.get("bodies") or (), key=body_key):
        faces = sorted(body.get("faces") or (), key=face_key)
        bodies.append({**body, "faces": faces})
    return bodies


def _box_delta(left: dict, right: dict) -> float | None:
    """Largest corner disagreement in mm, or ``None`` if either box is unusable."""
    box_a = [float(v) for v in left.get("box_mm") or ()]
    box_b = [float(v) for v in right.get("box_mm") or ()]
    if len(box_a) != 6 or len(box_b) != 6:
        return None
    return max(abs(x - y) for x, y in zip(box_a, box_b))


def _same_face(left: dict, right: dict, *, area_tol_mm2: float, box_tol_mm: float):
    delta = _box_delta(left, right)
    if delta is None or delta > box_tol_mm:
        return False
    if abs(float(left["area_mm2"]) - float(right["area_mm2"])) > area_tol_mm2:
        return False
    return left.get("surface") == right.get("surface")


def _same_body(left: dict, right: dict, *, box_tol_mm: float, **_: float):
    """Bodies pair on EXTENTS alone, not on face count.

    A body that lost a face is still that body, and saying "body 0 lost a
    face (area 3.25 mm^2)" is the diagnosis worth having; refusing the pair
    would degrade it to "a body vanished, another appeared".
    """
    delta = _box_delta(left, right)
    return delta is not None and delta <= box_tol_mm


def _persist_multiset(body: dict) -> list[str]:
    return sorted(str(face.get("persist") or "") for face in body.get("faces") or ())


def _pair(left: list[dict], right: list[dict], same, exact) -> tuple[list, list, list]:
    """Greedy two-pass pairing: exact partners first, equivalent ones after.

    Pairing by sorted POSITION is what this replaces, and it was wrong in
    both directions on the very part this probe was written for.  91247A720
    carries three identical raised grade marks and a great many identical
    fillet faces, so ties are the rule here, not an edge case: sorted
    position among equals is enumeration order, which is not a contract, so
    the comparison would pair one mark's face against another's and report a
    renumbering that never happened.  And a tolerated difference that crosses
    a rounding boundary reverses the sort, which mispairs everything after
    it.

    The exact pass is what makes ties behave: among geometrically
    indistinguishable candidates it takes the one whose reference also
    matches, so an identity difference is reported only when the multiset of
    references really changed.
    """
    unclaimed = list(range(len(right)))
    pairs: list[tuple[dict, dict]] = []
    lost: list[dict] = []
    for item in left:
        chosen = next(
            (
                index
                for index in unclaimed
                if same(item, right[index]) and exact(item, right[index])
            ),
            None,
        )
        if chosen is None:
            chosen = next(
                (index for index in unclaimed if same(item, right[index])), None
            )
        if chosen is None:
            lost.append(item)
            continue
        unclaimed.remove(chosen)
        pairs.append((item, right[chosen]))
    return pairs, lost, [right[index] for index in unclaimed]


def _describe(face: dict) -> str:
    return f"area {face['area_mm2']} mm^2"


def _diff_faces(
    label: str, before: list[dict], after: list[dict], tolerances: dict
) -> list[str]:
    problems: list[str] = []
    pairs, lost, gained = _pair(
        before,
        after,
        lambda a, b: _same_face(a, b, **tolerances),
        lambda a, b: bool(a.get("persist")) and a.get("persist") == b.get("persist"),
    )
    for face_a, face_b in pairs:
        if not face_a.get("persist") or not face_b.get("persist"):
            problems.append(
                f"identity: {label} face ({_describe(face_a)}) has no persistent "
                "reference in one of the censuses -- nothing was compared for it"
            )
        elif face_a["persist"] != face_b["persist"]:
            problems.append(
                f"identity: {label} face ({_describe(face_a)}) is the same face "
                "geometrically but its persistent reference changed "
                f"({face_a['persist']} -> {face_b['persist']})"
            )
    # Leftovers in equal number are the same face reported twice, so they are
    # paired up to say HOW it moved; that is the diagnosis worth having.
    if len(lost) == len(gained):
        for face_a, face_b in zip(lost, gained):
            area_delta = abs(float(face_a["area_mm2"]) - float(face_b["area_mm2"]))
            if area_delta > tolerances["area_tol_mm2"]:
                problems.append(
                    f"geometry: {label} face area {face_a['area_mm2']} -> "
                    f"{face_b['area_mm2']} (delta {area_delta:.6f} mm^2)"
                )
                continue
            delta = _box_delta(face_a, face_b)
            if delta is None:
                problems.append(
                    f"geometry: {label} face ({_describe(face_a)}) box is not six "
                    "corners in one of the censuses -- it is incomplete"
                )
            elif delta > tolerances["box_tol_mm"]:
                problems.append(
                    f"geometry: {label} face ({_describe(face_a)}) box moved by "
                    f"{delta:.9f} mm"
                )
            else:
                problems.append(
                    f"geometry: {label} face ({_describe(face_a)}) surface type "
                    f"{face_a.get('surface')} -> {face_b.get('surface')}"
                )
        return problems
    for face in lost:
        problems.append(f"geometry: {label} lost a face ({_describe(face)})")
    for face in gained:
        problems.append(f"geometry: {label} gained a face ({_describe(face)})")
    return problems


def diff_census(
    before: dict,
    after: dict,
    *,
    area_tol_mm2: float = AREA_TOL_MM2,
    box_tol_mm: float = BOX_TOL_MM,
) -> list[str]:
    """Every difference between two censuses, as one line each.

    Two KINDS of difference, deliberately worded apart:

    * ``geometry`` -- a face moved, changed size, or stopped existing.  The
      solid is not the same solid, which the vendor gate in
      ``gate_and_save`` would also have failed.
    * ``identity`` -- the geometry matches face for face but a persistent
      reference changed.  Nothing in a build notices, and nothing in this repo
      consumes it today; a stored downstream reference would.

    Bodies and faces are matched by GEOMETRY within the tolerances, never by
    position in either census: SolidWorks does not promise an enumeration
    order, and this part has identical bodies and identical faces.
    """
    tolerances = {"area_tol_mm2": area_tol_mm2, "box_tol_mm": box_tol_mm}
    problems: list[str] = []
    left, right = canonical(before), canonical(after)
    if len(left) != len(right):
        problems.append(f"geometry: body count {len(left)} -> {len(right)}")
    pairs, lost, gained = _pair(
        left,
        right,
        lambda a, b: _same_body(a, b, **tolerances),
        lambda a, b: _persist_multiset(a) == _persist_multiset(b),
    )
    for index, (body_a, body_b) in enumerate(pairs):
        problems.extend(
            _diff_faces(f"body {index}", body_a["faces"], body_b["faces"], tolerances)
        )
    if len(lost) == len(gained):
        for index, (body_a, body_b) in enumerate(zip(lost, gained), start=len(pairs)):
            label = f"body {index}"
            delta = _box_delta(body_a, body_b)
            if delta is None:
                problems.append(
                    f"geometry: {label} bounding box is not six corners in one of "
                    "the censuses -- it is incomplete"
                )
            elif delta > box_tol_mm:
                problems.append(
                    f"geometry: {label} bounding box moved by {delta:.9f} mm"
                )
            problems.extend(
                _diff_faces(label, body_a["faces"], body_b["faces"], tolerances)
            )
        return problems
    for body in lost:
        problems.append(f"geometry: body {body.get('name')!r} has no counterpart")
    for body in gained:
        problems.append(f"geometry: body {body.get('name')!r} is new")
    return problems


def _box_mm(owner, member: str, what: str) -> list[float]:
    """A six-corner box in millimetres, or a refusal.

    An empty read must never reach the census: two censuses that both failed
    to read a box would compare equal and the probe would report a match it
    never made.
    """
    from _common import _read_member

    box = [round(float(v) * 1000.0, 9) for v in (_read_member(owner, member) or ())]
    if len(box) != 6:
        raise RuntimeError(f"{member} returned {len(box)} corners for {what}, not 6")
    return box


async def capture_census(adapter, part_path: Path) -> dict:
    """Read one saved part's face census.  Opens the document; changes nothing."""
    from _common import _early_bound, _read_member, check

    check(f"open {part_path.name}", await adapter.open_model(str(part_path)))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    part = _early_bound(model, "IPartDoc")
    bodies = []
    for body_index, raw_body in enumerate(part.GetBodies2(0, False) or ()):
        body = _early_bound(raw_body, "IBody2")
        faces = []
        for face_index, raw_face in enumerate(body.GetFaces() or ()):
            what = f"body {body_index} face {face_index} of {part_path.name}"
            face = _early_bound(raw_face, "IFace2")
            surface = _read_member(face, "GetSurface")
            # GetPersistReference3 is the handle a saved downstream reference
            # actually stores.  Opaque bytes, and its LENGTH is informative
            # too, so it is hashed whole rather than truncated.  A missing one
            # is refused rather than hashed: sha256(b"") on both sides would
            # read as "same reference" and turn this probe into decoration.
            reference = extension.GetPersistReference3(raw_face)
            if not reference:
                raise RuntimeError(f"GetPersistReference3 returned nothing for {what}")
            faces.append(
                {
                    "area_mm2": round(float(_read_member(face, "GetArea")) * 1e6, 6),
                    "box_mm": _box_mm(face, "GetBox", what),
                    "surface": (
                        int(_read_member(surface, "Identity") or -1) if surface else -1
                    ),
                    "persist": hashlib.sha256(bytes(bytearray(reference))).hexdigest()[
                        :16
                    ],
                }
            )
        if not faces:
            raise RuntimeError(
                f"body {body_index} of {part_path.name} reported 0 faces"
            )
        bodies.append(
            {
                "name": str(_read_member(body, "Name")),
                # The BOX, not the volume: IBody2 volume needs a density
                # argument, and the vendor gate in gate_and_save already owns
                # volume.  The box is only used to pair bodies up.
                "box_mm": _box_mm(body, "GetBodyBox", f"body {body_index}"),
                "faces": faces,
            }
        )
    if not bodies:
        raise RuntimeError(f"{part_path.name} reported no solid bodies")
    return {"part": part_path.name, "bodies": bodies}


def _capture(part_path: Path, output: Path) -> int:
    import dodo
    from _common import discard_open_documents, run_build

    async def build(adapter):
        try:
            census = await capture_census(adapter, part_path)
        finally:
            # A replica left resident holds a document lock, and the next leaf
            # to open the same part on this seat would fail on it.
            discard_open_documents(adapter)
            adapter.currentModel = None
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(census, indent=2), encoding="utf-8")
        return {"census": str(output)}

    with dodo._com_seat(f"face-identity-{part_path.stem}"):
        return run_build(build)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, help="saved part to census")
    parser.add_argument("--output", type=Path, help="where to write the census")
    parser.add_argument(
        "--diff", type=Path, nargs=2, metavar=("BEFORE", "AFTER"), help="compare"
    )
    args = parser.parse_args()
    if args.diff:
        before, after = (
            json.loads(path.read_text(encoding="utf-8")) for path in args.diff
        )
        problems = diff_census(before, after)
        for problem in problems:
            print(problem)
        if not problems:
            print(f"{len(canonical(after))} bodies: same faces, same references")
        return 1 if problems else 0
    if args.capture:
        if not args.output:
            parser.error("--capture needs --output")
        return _capture(args.capture, args.output)
    parser.error("pass --capture or --diff")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
