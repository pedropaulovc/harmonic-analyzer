"""Bounded raw BSURF readback, not a replacement for native attachment identity.

The official Get B-Spline Surface Parameterization Data example supplies the
False/False/0.01 call shape. Its approximation request is recorded, never used
as an equality allowance. All returned coefficients stay unrounded. See
cad/docs/pipeline/tooth-tip-bsurface-witness.md for the native acceptance scope.
"""

from enum import StrEnum
import math

from _common import _early_bound
from _telemetry import traced
from diagnostics._silhouette_identity_control import _raw_return


class Periodicity(StrEnum):
    PERIODIC = "periodic"
    NON_PERIODIC = "non_periodic"


class Sense(StrEnum):
    SAME = "same"
    OPPOSITE = "opposite"


# Diagnostic read-budget bounds, not asserted SolidWorks API limits.
MAX_CONTROL_POINTS = 4096
MAX_ORDER = 32
MAX_PROPERTIES = 64
BOUND_TYPES = frozenset((13741, 13734, 13733, 13735, 13701, 13736))
PROPERTY_TYPES = frozenset((13737, 13738, 13746, 13740, 13739, 13701))


def _integer(raw, *, label, minimum, maximum):
    if type(raw) is not int or not minimum <= raw <= maximum:
        raise RuntimeError(
            f"BSURF {label}: expected integer {minimum}..{maximum}, got {raw!r}"
        )
    return raw


def _double(raw, *, label):
    if type(raw) is not float or not math.isfinite(raw):
        raise RuntimeError(f"BSURF {label}: expected finite native double, got {raw!r}")
    return raw


def _doubles(raw, size, *, label):
    if not isinstance(raw, (tuple, list)) or len(raw) != size:
        raise RuntimeError(
            f"BSURF {label}: expected {size} native doubles, got {raw!r}"
        )
    return tuple(
        _double(value, label=f"{label}[{index}]") for index, value in enumerate(raw)
    )


def _enum(raw, choices, *, label):
    if type(raw) is not int or raw not in choices:
        raise RuntimeError(f"BSURF {label}: unsupported native enum {raw!r}")
    return raw


def _read(operation, records, field):
    """Journal one actual getter result before validation; never retry it."""
    try:
        raw = operation()
    except Exception as error:
        if records is not None:
            records[field] = {"error": repr(error)}
        raise
    if records is not None:
        records[field] = {"type": f"{type(raw).__module__}.{type(raw).__qualname__}"}
        try:
            records[field].update(_raw_return(raw))
        except Exception as error:
            # An encoder failure must not hide the native validation verdict.
            records[field]["observation_error"] = repr(error)
    return raw


def _parameterization(data, *, evidence=None):
    result = {}
    raw_reads = None
    if evidence is not None:
        evidence["parameterization"] = result
        raw_reads = evidence["raw_parameterization"] = {}
    for axis in ("U", "V"):
        for end in ("Min", "Max"):
            field = f"{axis}{end}"
            result[field] = _double(
                _read(lambda: getattr(data, field), raw_reads, field), label=field
            )
            field = f"{axis}{end}BoundType"
            result[field] = _enum(
                _read(lambda: getattr(data, field), raw_reads, field),
                BOUND_TYPES, label=field,
            )
        if result[f"{axis}Min"] >= result[f"{axis}Max"]:
            raise RuntimeError(
                f"BSURF {axis} parameter range is empty/reversed: {result!r}"
            )
        count_field, field = f"{axis}PropertyNumber", f"{axis}Properties"
        count = _integer(
            _read(lambda: getattr(data, count_field), raw_reads, count_field),
            label=count_field,
            minimum=0,
            maximum=MAX_PROPERTIES,
        )
        result[count_field] = count
        raw = _read(lambda: getattr(data, field), raw_reads, field)
        if not isinstance(raw, (tuple, list)) or len(raw) != count:
            raise RuntimeError(
                f"BSURF {field}: expected {count} native enums, got {raw!r}"
            )
        result[field] = tuple(
            _enum(value, PROPERTY_TYPES, label=field) for value in raw
        )
    return result


def _bspline(data, *, evidence=None):
    result = {}
    raw_reads = None
    if evidence is not None:
        evidence["bspline"] = result
        raw_reads = evidence["raw_bspline"] = {}
    for field in ("UOrder", "VOrder"):
        result[field] = _integer(
            _read(lambda: getattr(data, field), raw_reads, field),
            label=field, minimum=2, maximum=MAX_ORDER,
        )
    for field in ("ControlPointColumnCount", "ControlPointRowCount"):
        result[field] = _integer(
            _read(lambda: getattr(data, field), raw_reads, field),
            label=field, minimum=1, maximum=MAX_CONTROL_POINTS,
        )
    columns, rows = result["ControlPointColumnCount"], result["ControlPointRowCount"]
    if columns * rows > MAX_CONTROL_POINTS:
        raise RuntimeError(
            f"BSURF control grid {rows}x{columns} exceeds read budget {MAX_CONTROL_POINTS}"
        )
    field = "ControlPointDimension"
    dimension = _integer(
        _read(lambda: getattr(data, field), raw_reads, field),
        label=field, minimum=3, maximum=4,
    )
    result[field] = dimension
    for axis, count in (("U", columns), ("V", rows)):
        field = f"{axis}Periodicity"
        periodic = _read(lambda: getattr(data, field), raw_reads, field)
        if type(periodic) is not bool:
            raise RuntimeError(
                f"BSURF {field}: expected native Boolean, got {periodic!r}"
            )
        result[field] = (
            Periodicity.PERIODIC if periodic else Periodicity.NON_PERIODIC
        ).value
        field = f"{axis}Knots"
        # IBSurfParamData documents count+order, including periodic output.
        knots = _doubles(
            _read(lambda: getattr(data, field), raw_reads, field),
            count + result[f"{axis}Order"], label=field,
        )
        if knots[0] >= knots[-1] or any(a > b for a, b in zip(knots, knots[1:])):
            raise RuntimeError(
                f"BSURF {field}: empty/decreasing native knot vector {knots!r}"
            )
        result[field] = knots
    point_reads = []
    if evidence is not None:
        evidence["control_point_reads"] = point_reads

    def control_point(row, column):
        record = None
        if evidence is not None:
            record = {"row": row, "column": column}
            point_reads.append(record)
        raw = _read(lambda: data.GetControlPoints(row, column), record, "returned")
        return _doubles(raw, dimension, label=f"GetControlPoints({row},{column})")

    # Read every 1-based native point. Rational weights remain raw components.
    # Publish a completed grid only after every point passes, but retain each
    # requested index/result (including null) before validating its vector.
    result["control_points"] = tuple(
        tuple(control_point(row, column) for column in range(1, columns + 1))
        for row in range(1, rows + 1)
    )
    return result


@traced("diagnostic.silhouette.bsurface")
def snapshot(face, surface, *, evidence=None):
    """Read an already type-checked BSURF with the documented example request.

    Face UV bounds are a parameter rectangle, NOT its trimming loops or BREP.
    The caller still checks drawing PID, owning view, native face identity and
    exact raw silhouette curve/endpoints; no geometric fallback is introduced.
    An optional journal retains partial metadata and raw scalar/array reads.
    It is non-authoritative and adds no native calls.
    """
    result = {
        "identity": 4006,
        "read_request": {
            "conversion": "no_cubic_or_nonrational_request",
            "tolerance_m": 0.01,
        },
    }
    if evidence is not None:
        evidence.update(result)
    parameterization = surface.Parameterization2()
    if parameterization is None:
        raise RuntimeError("BSURF Parameterization2 returned null")
    parameterization = _early_bound(parameterization, "ISurfaceParameterizationData")
    result["parameterization"] = _parameterization(parameterization, evidence=evidence)
    face_bounds = _doubles(face.GetUVBounds(), 4, label="GetUVBounds")
    if face_bounds[0] >= face_bounds[1] or face_bounds[2] >= face_bounds[3]:
        raise RuntimeError(
            f"BSURF GetUVBounds: empty/reversed native range {face_bounds!r}"
        )
    # A periodic face may straddle a surface boundary, so do not demand simple
    # containment of this rectangle in the surface parameterization rectangle.
    reversed_face = face.FaceInSurfaceSense()
    if type(reversed_face) is not bool:
        raise RuntimeError(
            f"BSURF FaceInSurfaceSense: expected native Boolean, got {reversed_face!r}"
        )
    face_sense = (Sense.OPPOSITE if reversed_face else Sense.SAME).value
    result.update(face_uv_bounds=face_bounds, face_sense=face_sense)
    if evidence is not None:
        evidence.update(result)
    # Keep the example's request as the first positive-control candidate. The
    # docs do NOT say the tolerance is ignored for an already-BSURF surface.
    returned = surface.GetBSurfParams3(False, False, parameterization, 0.01)
    if type(returned) is not tuple or len(returned) != 2:
        raise RuntimeError(
            f"BSURF GetBSurfParams3: expected (data, sense), got {returned!r}"
        )
    data, same_sense = returned
    if data is None or type(same_sense) is not bool:
        raise RuntimeError(
            f"BSURF GetBSurfParams3: null data/invalid native sense {returned!r}"
        )
    result["bspline_sense"] = (Sense.SAME if same_sense else Sense.OPPOSITE).value
    if evidence is not None:
        evidence.update(result)
    result["bspline"] = _bspline(_early_bound(data, "IBSurfParamData"), evidence=evidence)
    return result
