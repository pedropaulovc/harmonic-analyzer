"""Resolve face selectors in one native document traversal.

Separate from annotation authoring so drawing face picks do not fold the part PMI hub.
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _common import _bind, _com_invoke, _early_bound
from _gtol_face import FaceSpec
from _gtol_face_read import face_geometry


@_telemetry.traced("pmi.resolve_faces")
def resolve_faces(model: Any, requests: dict[str, FaceSpec]) -> dict[str, Any]:
    """Resolve every face spec in one document traversal.

    The previous implementation retraversed every body and reread every
    surface once per annotation (36 traversals across the ten migrated parts).
    One traversal per part cuts that to ten and reads each face's COM geometry
    once, while keeping the exact-one-match contract per annotation.  The walk
    is raw and binds only the faces it returns; a face whose surface type no
    request names costs two reads.
    """
    identities = frozenset(spec.surface_identity for spec in requests.values())
    matches: dict[str, list[Any]] = {label: [] for label in requests}
    walked = 0
    part = _early_bound(model, "IPartDoc")
    for body in part.GetBodies2(0, False) or ():
        face = _com_invoke(body, "IBody2", "GetFirstFace")
        while face is not None:
            walked += 1
            geometry = face_geometry(face, identities=identities)
            if geometry is not None:
                for label, spec in requests.items():
                    if spec.matches(geometry):
                        matches[label].append(face)
            face = _com_invoke(face, "IFace2", "GetNextFace")
    _telemetry.annotate(requests=len(requests), faces=walked)

    resolved: dict[str, Any] = {}
    for label, candidates in matches.items():
        if len(candidates) != 1:
            raise RuntimeError(
                f"{label}: face spec {requests[label]!r} matched "
                f"{len(candidates)} faces; the spec must identify exactly one"
            )
        resolved[label] = _bind(candidates[0], "IFace2")
    return resolved
