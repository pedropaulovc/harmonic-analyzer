"""Prove a rebuilt replica has the SAME FACES, not merely the same solid.

The 91247A720 / 99607A213 rewrites changed how the profiles are authored
(direct-to-database plus explicit ``merge`` relations instead of inference).
``diag_mcmaster_lib.gate_and_save`` already fails the build if the resulting
SOLID moves -- volume, surface area, centre of mass, face count and, for parts
at or under ``FACE_MULTISET_LIMIT`` faces, the exact sorted face-area multiset,
all against the vendor ground truth.  What that gate cannot see is a solid that
is geometrically identical while its FACES are different faces.  Downstream
work that resolves a face and remembers it -- a stored annotation attachment,
a mate, a face-level appearance -- would then attach to nothing, and would
surface days later as a drawing or assembly defect rather than as a build
failure.

That question has two halves, and they are deliberately not mixed:

* **Geometry** -- are the faces the same size, in the same place, of the same
  surface type?  Offline, from two captured censuses.
* **Identity** -- does a reference STORED against the old part still resolve,
  in the new part, to the face it was taken from?  This one cannot be answered
  by comparing stored bytes.  ``GetPersistReference3`` documents its own
  representation as unstable: "The internal representations of the return
  value array may change, possibly from rebuild to rebuild ... but their usage
  in finding the correct entity will be consistent across rebuilds."  So
  equal bytes are not proof and differing bytes are not a defect; the only
  honest test is to feed the stored reference back through
  ``GetObjectByPersistReference3`` against the new part and see what comes
  out.  That needs a seat and the two parts, so it is its own mode.

Three modes::

    # Needs the COM seat.  Read-only: OPENS a saved replica and reads it; it
    # does not rebuild anything and it does not run doit.
    uv run python cad/scripts/diagnostics/probe_face_identity.py \
        --capture cad/out/reference/91247A720-replica.SLDPRT \
        --output cad/out/reports/91247A720-faces-before.json

    # No seat.  Geometry equivalence of two captures.
    uv run python cad/scripts/diagnostics/probe_face_identity.py \
        --diff before.json after.json

    # Needs the COM seat.  Replays every reference captured from the old part
    # against the new one and writes the verdict rows next to the answer.
    uv run python cad/scripts/diagnostics/probe_face_identity.py \
        --resolve before.json --into cad/out/reference/91247A720-replica.SLDPRT \
        --output cad/out/reports/91247A720-resolve.json

    # No seat.  Re-read verdict rows captured earlier.
    uv run python cad/scripts/diagnostics/probe_face_identity.py \
        --verdicts cad/out/reports/91247A720-resolve.json

The "before" census does not require building the old code: any replica saved
by a pre-change build is a valid subject, including one already published by a
release build.

Exit code 1 and one line per difference.
"""

from __future__ import annotations

import argparse
import base64
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

# swPersistReferencedObjectStates_e, a BITMASK: 0 is the only healthy answer.
PERSIST_STATES = {1: "invalid", 2: "suppressed", 4: "deleted"}


def face_key(face: dict) -> tuple:
    """Canonical order for faces: geometry only, never the stored reference.

    Ordering by the reference would be ordering by bytes SOLIDWORKS is free to
    renumber, which is noise, and it would hide the geometry it is meant to
    line up.
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


def _face_geometry_multiset(body: dict) -> list[tuple]:
    """A body's faces as a sorted list of geometry keys.

    This, not the reference bytes, is what disambiguates bodies whose extents
    tie.  References are allowed to change from rebuild to rebuild, so using
    them here would routinely find no exact partner and drop back to pairing
    congruent-but-not-identical bodies by enumeration order -- which then
    reports face differences that are really just a mispairing.
    """
    return sorted(face_key(face) for face in body.get("faces") or ())


def _pair(left: list[dict], right: list[dict], same, exact) -> tuple[list, list, list]:
    """Greedy two-pass pairing: exact partners first, equivalent ones after.

    Pairing by sorted POSITION is what this replaces, and it was wrong in
    both directions on the very part this probe was written for.  91247A720
    carries three identical raised grade marks and a great many identical
    fillet faces, so ties are the rule here, not an edge case: sorted
    position among equals is enumeration order, which is not a contract, so
    the comparison would pair one mark's face against another's.  And a
    tolerated difference that crosses a rounding boundary reverses the sort,
    which mispairs everything after it.

    ``exact`` only DISAMBIGUATES ties -- among candidates that are already
    geometrically indistinguishable it prefers the one whose stored reference
    also matches.  It never produces a verdict on its own, because reference
    bytes are allowed to change from rebuild to rebuild; the worst a wrong
    guess here can do is pair one identical face with another identical one.
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
    _pairs, lost, gained = _pair(
        before,
        after,
        lambda a, b: _same_face(a, b, **tolerances),
        lambda a, b: bool(a.get("persist")) and a.get("persist") == b.get("persist"),
    )
    problems: list[str] = []
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
    """Every GEOMETRY difference between two censuses, as one line each.

    This answers "is it the same solid, face for face" and nothing more.  It
    deliberately does NOT compare stored references: ``GetPersistReference3``
    may renumber them from one rebuild to the next, so a byte difference here
    would be a false alarm and byte equality would be a false reassurance.
    Identity is ``diff_resolution``'s question, and answering it needs a seat.

    Bodies and faces are matched by geometry within the tolerances, never by
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
        lambda a, b: _face_geometry_multiset(a) == _face_geometry_multiset(b),
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


def _state_names(state: int) -> str:
    named = [name for bit, name in PERSIST_STATES.items() if state & bit]
    return ", ".join(named) or f"state {state}"


def diff_resolution(
    rows: list[dict],
    *,
    area_tol_mm2: float = AREA_TOL_MM2,
    box_tol_mm: float = BOX_TOL_MM,
) -> list[str]:
    """Verdicts for references captured from the old part, replayed on the new.

    Each row is one face of the OLD part: the geometry it had, the state
    ``GetObjectByPersistReference3`` returned for its stored reference against
    the NEW part, and the geometry of whatever came back.  This is the check
    that matters, because it is what a stored downstream reference does: not
    "are the bytes the same" but "does my saved handle still find my face".

    An empty result means every stored reference still resolves to the face it
    was taken from -- and to the face IN ITS OWN BODY.  That last part is not
    pedantry on 91247A720: its three raised grade marks are congruent
    separate bodies, so a reference that drifted to another mark's
    corresponding face would match on area, box and surface type alone.  The
    bodies are compared by EXTENTS rather than by name, because a body name
    is derived from the feature that made it and is not something this
    rewrite promises to preserve.

    A row with no state at all is refused rather than ignored: a resolve pass
    that failed to record its outcome has proven nothing, and reading it as a
    pass is how a probe becomes decoration.
    """
    tolerances = {"area_tol_mm2": area_tol_mm2, "box_tol_mm": box_tol_mm}
    problems: list[str] = []
    for index, row in enumerate(rows):
        stored = row.get("stored") or {}
        label = f"face {index} ({_describe(stored)})" if stored else f"face {index}"
        state = row.get("state")
        if not isinstance(state, int):
            problems.append(
                f"identity: {label} has no recorded resolution state -- this row "
                "proves nothing either way"
            )
            continue
        if state != 0:
            problems.append(
                f"identity: {label} no longer resolves: {_state_names(state)}"
            )
            continue
        resolved = row.get("resolved")
        if not resolved:
            problems.append(
                f"identity: {label} reported a healthy state but resolved to no "
                "object at all"
            )
            continue
        if not _same_face(stored, resolved, **tolerances):
            problems.append(
                f"identity: {label} still resolves, but to a DIFFERENT face "
                f"({_describe(resolved)}) -- a stored reference would now point "
                "at the wrong geometry"
            )
            continue
        owner_delta = _box_delta(
            {"box_mm": row.get("body_box_mm") or ()},
            {"box_mm": row.get("resolved_body_box_mm") or ()},
        )
        if owner_delta is None:
            problems.append(
                f"identity: {label} resolved, but the owning body of one side was "
                "not recorded -- the face could belong to another body"
            )
        elif owner_delta > box_tol_mm:
            problems.append(
                f"identity: {label} resolves to a matching face in a DIFFERENT "
                f"body (extents differ by {owner_delta:.9f} mm) -- on this part "
                "the congruent grade marks make that look identical"
            )
    return problems


def _persist_encode(reference) -> str:
    """The FULL reference, base64.  Never a digest.

    A digest cannot be fed back to ``GetObjectByPersistReference3``, which is
    the only thing that can actually answer the identity question.  The bytes
    arrive as an array of small ints that may be signed, hence the mask.
    """
    return base64.b64encode(bytes((int(v) & 0xFF) for v in reference)).decode("ascii")


def _persist_decode(encoded: str) -> list[int]:
    return list(base64.b64decode(encoded.encode("ascii")))


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


def _face_geometry(face, what: str) -> dict:
    from _common import _read_member

    surface = _read_member(face, "GetSurface")
    return {
        "area_mm2": round(float(_read_member(face, "GetArea")) * 1e6, 6),
        "box_mm": _box_mm(face, "GetBox", what),
        "surface": int(_read_member(surface, "Identity") or -1) if surface else -1,
    }


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
            # A missing reference is refused rather than stored empty: an
            # empty one cannot be replayed, and two empty ones would compare
            # equal, which is how a probe turns into decoration.
            reference = extension.GetPersistReference3(raw_face)
            if not reference:
                raise RuntimeError(f"GetPersistReference3 returned nothing for {what}")
            faces.append(
                {**_face_geometry(face, what), "persist": _persist_encode(reference)}
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


async def resolve_census(adapter, census: dict, part_path: Path) -> list[dict]:
    """Replay every reference captured from the old part against ``part_path``.

    One row per stored face, in canonical order, recording the state
    ``GetObjectByPersistReference3`` returned and the geometry of whatever
    came back.  ``diff_resolution`` turns the rows into verdicts; keeping the
    rows means the evidence survives the run.
    """
    from _common import _early_bound, _read_member, check

    check(f"open {part_path.name}", await adapter.open_model(str(part_path)))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    rows: list[dict] = []
    for body in canonical(census):
        for face in body["faces"]:
            row: dict = {
                "stored": face,
                "body": body.get("name"),
                "body_box_mm": list(body.get("box_mm") or ()),
            }
            # The out parameter comes back as the second element of a tuple
            # under pywin32; anything else is recorded as-is rather than
            # guessed at, so an unexpected shape reads as "proves nothing".
            answer = extension.GetObjectByPersistReference3(
                _persist_decode(face["persist"])
            )
            if isinstance(answer, (tuple, list)) and len(answer) == 2:
                obj, state = answer
                row["state"] = int(state)
                if obj is not None:
                    what = f"resolved {_describe(face)}"
                    resolved_face = _early_bound(obj, "IFace2")
                    row["resolved"] = _face_geometry(resolved_face, what)
                    # WHICH body it landed in is half the verdict: the three
                    # grade marks are congruent, so a reference that drifted
                    # to another mark matches on geometry alone.
                    owner = _read_member(resolved_face, "GetBody")
                    if owner is not None:
                        row["resolved_body_box_mm"] = _box_mm(
                            _early_bound(owner, "IBody2"),
                            "GetBodyBox",
                            f"owner of {what}",
                        )
            else:
                row["answer_shape"] = repr(type(answer))
            rows.append(row)
    return rows


def _seat(label: str, work) -> int:
    """Run ``work(adapter)`` under the single-seat lock and the build watchdog."""
    import dodo
    from _common import discard_open_documents, run_build

    async def build(adapter):
        try:
            return await work(adapter)
        finally:
            # A replica left resident holds a document lock, and the next leaf
            # to open the same part on this seat would fail on it.
            discard_open_documents(adapter)
            adapter.currentModel = None

    with dodo._com_seat(label):
        return run_build(build)


def _write(output: Path, payload) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _report(problems: list[str], clean: str) -> int:
    for problem in problems:
        print(problem)
    if not problems:
        print(clean)
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, help="saved part to census")
    parser.add_argument("--resolve", type=Path, help="census whose refs to replay")
    parser.add_argument("--into", type=Path, help="part to replay them against")
    parser.add_argument("--verdicts", type=Path, help="resolve rows to re-read")
    parser.add_argument("--output", type=Path, help="where to write the JSON")
    parser.add_argument(
        "--diff", type=Path, nargs=2, metavar=("BEFORE", "AFTER"), help="compare"
    )
    args = parser.parse_args()
    if args.diff:
        before, after = (
            json.loads(path.read_text(encoding="utf-8")) for path in args.diff
        )
        return _report(
            diff_census(before, after),
            f"{len(canonical(after))} bodies: same geometry, face for face",
        )
    if args.verdicts:
        rows = json.loads(args.verdicts.read_text(encoding="utf-8"))
        return _report(
            diff_resolution(rows),
            f"{len(rows)} stored references all resolve to their own face",
        )
    if args.capture:
        if not args.output:
            parser.error("--capture needs --output")
        part, output = args.capture, args.output

        async def capture(adapter):
            _write(output, await capture_census(adapter, part))
            return {"census": str(output)}

        return _seat(f"face-identity-{part.stem}", capture)
    if args.resolve:
        if not args.into or not args.output:
            parser.error("--resolve needs --into and --output")
        census = json.loads(args.resolve.read_text(encoding="utf-8"))
        part, output = args.into, args.output

        async def replay(adapter):
            rows = await resolve_census(adapter, census, part)
            _write(output, rows)
            problems = diff_resolution(rows)
            for problem in problems:
                print(problem)
            if problems:
                raise RuntimeError(f"{len(problems)} stored references did not survive")
            return {"resolved": str(output)}

        return _seat(f"face-resolve-{part.stem}", replay)
    parser.error("pass --capture, --diff, --resolve or --verdicts")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
