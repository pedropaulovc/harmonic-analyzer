"""Bounded VIEW-origin silhouette evidence; never a source-topology surrogate.

ISilhouetteEdge.GetView/GetFace/GetCurve and ordered MathPoint endpoints are
read directly. GetFace's reference frame is not documented: no source reverse
mapping is inferred. Drawing persistent IDs prove silhouette identity; native
IsSame continues to prove same-session view/face ownership;
captured parameters describe geometry but never substitute for identity.
Unsupported native shapes fail. No rounding or coordinate-frame transform is
applied, so any cold serialization differences remain visible in raw receipts.
"""

import math

from _common import _early_bound
import _drawing_silhouette_identity as persistent
from diagnostics import _bsurface_attachment_witness as bsurface
from diagnostics import _silhouette_bcurve_witness as bcurve


def finite_array(raw, size, *, label):
    if not isinstance(raw, (tuple, list)) or len(raw) != size:
        raise RuntimeError(f"{label}: expected {size} native doubles, got {raw!r}")
    if any(
        type(value) not in (int, float) or not math.isfinite(value) for value in raw
    ):
        raise RuntimeError(f"{label}: non-finite/non-numeric native array {raw!r}")
    return tuple(raw)


def same(app, first, second, *, label):
    if first is None or second is None:
        raise RuntimeError(f"{label}: null native identity")
    result = int(app.IsSame(first, second))
    if result != 1:
        raise RuntimeError(f"{label}: native IsSame returned {result}")


def _nonzero(values, label):
    if not any(value != 0 for value in values):
        raise RuntimeError(f"{label}: zero native direction")


def surface_witness(face, *, evidence=None):
    """Raw supported surface, never an approximate IFace2.GetBox identity proxy."""
    if face is None:
        raise RuntimeError("silhouette face is null")
    face = _early_bound(face, "IFace2")
    surface = face.GetSurface()
    if surface is None:
        raise RuntimeError("silhouette face surface is null")
    surface = _early_bound(surface, "ISurface")
    raw_identity = surface.Identity()
    identity = int(raw_identity)
    if identity == 4006:
        if type(raw_identity) is not int:
            raise RuntimeError(
                f"BSURF Identity: expected native integer, got {raw_identity!r}"
            )
        return bsurface.snapshot(face, surface, evidence=evidence)
    # swSurfaceTypes_e: explicit bounded initial repertoire. Cones and other
    # surfaces require their own native positive control, not guessed arrays.
    fields = {4001: ("PlaneParams", 6), 4002: ("CylinderParams", 7)}
    if identity not in fields:
        raise RuntimeError(f"unsupported silhouette surface identity {identity}")
    field, size = fields[identity]
    params = finite_array(getattr(surface, field), size, label=field)
    _nonzero(params[:3] if identity == 4001 else params[3:6], field)
    if identity == 4002 and params[6] <= 0:
        raise RuntimeError(f"{field}: non-positive native radius {params[6]}")
    return {"identity": identity, "parameters": params}


def _curve_read(curve, method, evidence):
    """Journal the actual zero-argument getter without retrying or coercing it."""
    record = None
    if evidence is not None:
        record = {"method": method, "arguments": ()}
        evidence.setdefault("curve_reads", []).append(record)
    return bsurface._read(lambda: getattr(curve, method)(), record, "returned")


def snapshot(app, view, entity, *, evidence=None):
    """Return raw supported geometry plus the native face handle for live checks."""
    curve_control = bcurve.curve_control_from_environment()
    if entity is None:
        raise RuntimeError("silhouette attachment is null")
    silhouette = _early_bound(entity, "ISilhouetteEdge")
    same(app, silhouette.GetView(), view, label="silhouette owning view")
    face = silhouette.GetFace()
    face_data = surface_witness(
        face, evidence=evidence.setdefault("face_surface", {}) if evidence is not None else None
    )
    if evidence is not None:
        # Replace a completed surface journal with its unchanged geometry bank.
        # Failed surface reads retain their partial journal instead. Neither a
        # partial journal nor a later curve rejection is a successful snapshot.
        evidence["face_surface"] = face_data
    raw_curve = silhouette.GetCurve()
    if raw_curve is None:
        raise RuntimeError("silhouette curve is null")
    curve = _early_bound(raw_curve, "ICurve")
    raw_line = _curve_read(curve, "IsLine", evidence)
    raw_circle = _curve_read(curve, "IsCircle", evidence)
    is_line, is_circle = bool(raw_line), bool(raw_circle)
    if (
        curve_control is bcurve.CurveControl.BCURVE_3005
        and raw_line is False and raw_circle is False
    ):
        params = bcurve.snapshot(
            curve, evidence.setdefault("bcurve", {}) if evidence is not None else {}
        )
        curve_kind = curve_control.value
    elif is_line == is_circle:
        primary = RuntimeError("unsupported or contradictory silhouette curve kind")
        if evidence is not None:
            try:
                # ICurve.Identity reports swCurveTypes_e. The literal result is
                # failure-only evidence, never a new supported geometry reader.
                _curve_read(curve, "Identity", evidence)
            except Exception:
                # The journal retains this getter error; classification already
                # failed independently and must remain the primary rejection.
                pass
        raise primary
    else:
        field, size = ("LineParams", 6) if is_line else ("CircleParams", 7)
        params = finite_array(getattr(curve, field), size, label=field)
        _nonzero(params[3:6], field)
        if is_circle and params[6] <= 0:
            raise RuntimeError(f"{field}: non-positive native radius {params[6]}")
        curve_kind = "line" if is_line else "circle"
    points = []
    for field in ("GetStartPoint", "GetEndPoint"):
        point = getattr(silhouette, field)()
        if point is None:
            raise RuntimeError(f"silhouette {field} returned null")
        points.append(
            finite_array(_early_bound(point, "IMathPoint").ArrayData, 3, label=field)
        )
    if is_line and points[0] == points[1]:
        raise RuntimeError("silhouette line has coincident endpoints")
    return {
        "curve_kind": curve_kind,
        "curve_parameters": params,
        "start": points[0],
        "end": points[1],
        "face_surface": face_data,
    }, face


def _record_identity_controls(app, expected, actual, before_face, after_face, evidence):
    """Characterize a rejected native identity without changing its verdict."""
    controls = evidence.setdefault("identity_controls", {})
    pairs = {
        "expected_self": (expected, expected),
        "actual_self": (actual, actual),
        "reverse_pair": (actual, expected),
        "expected_face_self": (before_face, before_face),
        "actual_face_self": (after_face, after_face),
        "face_pair": (before_face, after_face),
    }
    for name, pair in pairs.items():
        try:
            controls[name] = {"result": int(app.IsSame(*pair))}
        except Exception as error:
            # Evidence must not replace the already established identity failure.
            controls[name] = {"error": repr(error)}


def require_same(app, view, expected, actual, *, drawing, label, evidence):
    """Record both raw snapshots before exact entity/face/geometry acceptance."""
    before, before_face = snapshot(
        app, view, expected, evidence=evidence.setdefault("expected", {})
    )
    evidence["expected"] = before
    after, after_face = snapshot(
        app, view, actual, evidence=evidence.setdefault("actual", {})
    )
    evidence["actual"] = after
    try:
        persistent.require_same(
            drawing,
            expected,
            actual,
            label=f"{label} silhouette entity",
            evidence=evidence.setdefault("persistent_identity", {}),
        )
    except RuntimeError:
        _record_identity_controls(
            app, expected, actual, before_face, after_face, evidence
        )
        raise
    same(app, before_face, after_face, label=f"{label} silhouette face")
    if before != after:
        raise RuntimeError(f"{label}: silhouette raw geometry changed: {evidence!r}")
    return after
