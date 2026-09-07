"""Opt-in raw BCURVE_TYPE readback; native attachment identity stays separate.

The returned ICurve domain and ordered silhouette endpoints are recorded by the
caller. A silhouette is not an IEdge, so no CurveTag/Sense/edge trim is invented.
GetBCurveParams5 accuracy is API/modeler-dependent; raw equality is not a claim
that the parameter object is an exact serialization of the underlying BREP.
"""

from copy import deepcopy
from enum import StrEnum
import os

from _common import _early_bound
from _telemetry import traced
from diagnostics import _bsurface_attachment_witness as native


class CurveControl(StrEnum):
    OFF = "off"
    BCURVE_3005 = "bcurve-3005"


def curve_control_from_environment():
    field = "HARMONIC_SILHOUETTE_CURVE_CONTROL"
    value = os.environ.get(field, CurveControl.OFF.value)
    try:
        return CurveControl(value)
    except ValueError as error:
        raise ValueError(
            f"{field}: expected off or bcurve-3005, got {value!r}"
        ) from error


@traced("diagnostic.silhouette.bcurve_3005")
def snapshot(curve, evidence):
    """Read once, journal before validating, and keep all unnormalized values."""
    # Reuse the existing curve-control bounds without requiring an IEdge or
    # importing its attachment reader while this module is being initialized.
    from diagnostics._raw_edge_curve import integer, sequence

    def read(name, operation):
        row = {"method": name, "arguments": ()}
        evidence.setdefault("reads", []).append(row)
        return native._read(operation, row, "returned")

    identity = read("Identity", curve.Identity)
    integer(identity, 3005, 3005, "BCURVE Identity")
    evidence["identity"] = identity
    is_bcurve = read("IsBcurve", curve.IsBcurve)
    if is_bcurve is not True:
        raise RuntimeError("BCURVE IsBcurve must return native True")
    raw_domain = read("GetEndParams", curve.GetEndParams)
    sequence(raw_domain, label="BCURVE GetEndParams", minimum=5, maximum=5)
    if raw_domain[0] is not True or any(
        type(value) is not bool for value in raw_domain[3:]
    ):
        raise RuntimeError(
            "BCURVE GetEndParams requires native success/closure/periodicity"
        )
    domain = native._doubles(raw_domain[1:3], 2, label="BCURVE parameter domain")
    if domain[0] >= domain[1]:
        raise RuntimeError("BCURVE parameter domain is empty or reversed")
    closed, periodic = raw_domain[3:]
    evidence.update(domain=domain, closure="closed" if closed else "open")
    # Same flags as the proven 3004 source reader: no cubic/non-rational request,
    # and no periodic-to-nonperiodic change for a native periodic curve. The
    # official example's True/True tail describes its particular selected curve.
    arguments = (False, False, not periodic, closed)
    request = evidence["GetBCurveParams5"] = {"arguments": arguments}
    try:
        raw = curve.GetBCurveParams5(*arguments)
    except Exception as error:
        request["error"] = repr(error)
        raise
    request["returned"] = "null" if raw is None else "ISplineParamData"
    if raw is None:
        raise RuntimeError("BCURVE GetBCurveParams5 returned null")
    data = _early_bound(raw, "ISplineParamData")
    metadata = evidence["spline"] = {}
    for name in (
        "Dimension",
        "Order",
        "Periodic",
        "ControlPointsCount",
        "KnotPointsCount",
    ):
        metadata[name] = read(name, lambda name=name: getattr(data, name))
    dimension = integer(metadata["Dimension"], 3, 4, "BCURVE dimension")
    order = integer(metadata["Order"], 2, 64, "BCURVE order")
    count = integer(
        metadata["ControlPointsCount"], order, 10000, "BCURVE control count"
    )
    knot_count = integer(metadata["KnotPointsCount"], 1, 10064, "BCURVE knot count")
    periodicity = integer(metadata["Periodic"], 0, 1, "BCURVE periodicity")
    if periodicity != int(periodic):
        raise RuntimeError(
            "BCURVE returned parameterization changed native periodicity"
        )
    if knot_count != count + (1 if periodicity else order):
        raise RuntimeError("BCURVE knot count contradicts native metadata")
    for method, field, size in (
        ("GetControlPoints", "control_points", count * dimension),
        ("GetKnotPoints", "knots", knot_count),
    ):
        returned = read(method, getattr(data, method))
        sequence(returned, label=f"BCURVE {method}", minimum=2, maximum=2)
        if returned[0] is not True:
            raise RuntimeError(f"BCURVE {method} rejected")
        evidence[field] = native._doubles(returned[1], size, label=f"BCURVE {method}")
    knots = evidence["knots"]
    if any(first > second for first, second in zip(knots, knots[1:])):
        raise RuntimeError("BCURVE knots are not nondecreasing")
    # Retain raw rational coefficients, including weights, without dividing or
    # projecting them. Detached banks cannot change when native arrays are reused.
    return deepcopy(evidence)
