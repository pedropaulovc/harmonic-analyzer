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
    """
    problems: list[str] = []
    left, right = canonical(before), canonical(after)
    if len(left) != len(right):
        problems.append(f"geometry: body count {len(left)} -> {len(right)}")
    for index, (a, b) in enumerate(zip(left, right)):
        label = f"body {index}"
        box_delta = max(
            (
                abs(float(x) - float(y))
                for x, y in zip(a.get("box_mm") or (), b.get("box_mm") or ())
            ),
            default=0.0,
        )
        if box_delta > box_tol_mm:
            problems.append(
                f"geometry: {label} bounding box moved by {box_delta:.9f} mm"
            )
        faces_a, faces_b = a["faces"], b["faces"]
        if len(faces_a) != len(faces_b):
            problems.append(
                f"geometry: {label} face count {len(faces_a)} -> {len(faces_b)}"
            )
        for position, (face_a, face_b) in enumerate(zip(faces_a, faces_b)):
            where = f"{label} face {position}"
            area_delta = abs(float(face_a["area_mm2"]) - float(face_b["area_mm2"]))
            if area_delta > area_tol_mm2:
                problems.append(
                    f"geometry: {where} area {face_a['area_mm2']} -> "
                    f"{face_b['area_mm2']} (delta {area_delta:.6f} mm^2)"
                )
                continue
            box_delta = max(
                (
                    abs(float(x) - float(y))
                    for x, y in zip(face_a["box_mm"], face_b["box_mm"])
                ),
                default=0.0,
            )
            if box_delta > box_tol_mm:
                problems.append(f"geometry: {where} box moved by {box_delta:.9f} mm")
                continue
            if face_a.get("surface") != face_b.get("surface"):
                problems.append(
                    f"geometry: {where} surface type "
                    f"{face_a.get('surface')} -> {face_b.get('surface')}"
                )
                continue
            if face_a.get("persist") != face_b.get("persist"):
                problems.append(
                    f"identity: {where} is the same face geometrically but its "
                    f"persistent reference changed "
                    f"({face_a.get('persist')} -> {face_b.get('persist')})"
                )
    return problems


async def capture_census(adapter, part_path: Path) -> dict:
    """Read one saved part's face census.  Opens the document; changes nothing."""
    from _common import _early_bound, _read_member, check

    check(f"open {part_path.name}", await adapter.open_model(str(part_path)))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    part = _early_bound(model, "IPartDoc")
    bodies = []
    for raw_body in part.GetBodies2(0, False) or ():
        body = _early_bound(raw_body, "IBody2")
        faces = []
        for raw_face in body.GetFaces() or ():
            face = _early_bound(raw_face, "IFace2")
            surface = _read_member(face, "GetSurface")
            # GetPersistReference3 is the handle a saved downstream reference
            # actually stores.  Opaque bytes, and its LENGTH is informative
            # too, so it is hashed whole rather than truncated.
            reference = extension.GetPersistReference3(raw_face)
            faces.append(
                {
                    "area_mm2": round(float(_read_member(face, "GetArea")) * 1e6, 6),
                    "box_mm": [
                        round(float(v) * 1000.0, 9)
                        for v in (_read_member(face, "GetBox") or ())
                    ],
                    "surface": (
                        int(_read_member(surface, "Identity") or -1) if surface else -1
                    ),
                    "persist": hashlib.sha256(
                        bytes(bytearray(reference or ()))
                    ).hexdigest()[:16],
                }
            )
        bodies.append(
            {
                "name": str(_read_member(body, "Name")),
                # The BOX, not the volume: IBody2 volume needs a density
                # argument, and the vendor gate in gate_and_save already owns
                # volume.  The box is only used to pair bodies up.
                "box_mm": [
                    round(float(v) * 1000.0, 9)
                    for v in (_read_member(body, "GetBodyBox") or ())
                ],
                "faces": faces,
            }
        )
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
