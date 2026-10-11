"""Read native face geometry for part authoring, drawing validation and export.

This selector-independent COM bridge avoids folding the part authoring hub into drawings.
"""

from __future__ import annotations

from typing import Any

from _common import _com_invoke
from _gtol_face import (
    SURFACE_CONE,
    SURFACE_CYLINDER,
    SURFACE_PLANE,
    SURFACE_SPHERE,
    SURFACE_TORUS,
    FaceGeometry,
    unit_vector,
)

# The ISurface accessor that holds each supported identity's parameters.
_PARAMETERS = {
    SURFACE_CYLINDER: "CylinderParams",
    SURFACE_CONE: "ConeParams2",
    SURFACE_PLANE: "PlaneParams",
    SURFACE_SPHERE: "SphereParams",
    SURFACE_TORUS: "TorusParams",
}


def face_geometry(
    face: Any, *, identities: frozenset[int] | None = None
) -> FaceGeometry | None:
    """Read one face's surface identity, parameters, sense and box.

    Every read is one raw round trip (``_common._com_invoke``): through the
    generated wrapper each returned surface cost three more (type info and a
    ``QueryInterface``) on every face a walk only steps over.  ``face`` comes
    back as given.  With ``identities``, a face whose surface is not one of
    them stops after its identity: no spec of another type can match it.
    """
    surface = _com_invoke(face, "IFace2", "GetSurface")
    if surface is None:
        return None
    identity = int(_com_invoke(surface, "ISurface", "Identity"))
    accessor = _PARAMETERS.get(identity)
    if accessor is None or (identities is not None and identity not in identities):
        return FaceGeometry(face, identity, (), None, ())
    parameters = tuple(_com_invoke(surface, "ISurface", accessor))
    normal = None
    if identity == SURFACE_PLANE:
        normal = unit_vector(parameters[0:3])
        if bool(_com_invoke(face, "IFace2", "FaceInSurfaceSense")):
            normal = (-normal[0], -normal[1], -normal[2])
    return FaceGeometry(
        face=face,
        identity=identity,
        parameters=parameters,
        outward_normal=normal,
        box=tuple(_com_invoke(face, "IFace2", "GetBox") or ()),
    )
