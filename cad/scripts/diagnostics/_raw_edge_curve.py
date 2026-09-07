"""Diagnostic-only native curve data; no rounding, conversions or acceptance waiver.

GetBCurveParams5 returns a parameter object, not a proof that its representation
is an exact serialization of every underlying curve kind. Keep the native kind,
trim, closure and periodicity alongside all returned parameters for inspection.
"""

import math

from _common import _early_bound
from diagnostics import probe_drawing_attachments as attachments


def sequence(value, *, label, maximum, minimum=1):
    if not isinstance(value, (tuple, list)) or not minimum <= len(value) <= maximum:
        raise RuntimeError(f"{label}: unsupported native array shape")
    return value


def numbers(value, count, label):
    sequence(value, label=label, minimum=count, maximum=count)
    if any(type(item) not in (int, float) or not math.isfinite(item) for item in value):
        raise RuntimeError(f"{label}: non-finite or nonnumeric value")
    return value


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise RuntimeError(f"{label}: unsupported integer {value!r}")
    return value


def boolean(value, label):
    if type(value) is not bool:
        raise RuntimeError(f"{label}: unsupported boolean {value!r}")
    return value


def read_edge(edge, row):
    """Append raw evidence before each validation; caller retains partial failures."""
    edge = _early_bound(edge, "IEdge")
    raw_curve = edge.GetCurve()  # Required before GetCurveParams3.
    if raw_curve is None:
        raise RuntimeError("edge has no native curve")
    curve = _early_bound(raw_curve, "ICurve")
    row["identity"] = curve.Identity()
    integer(row["identity"], 3001, 3009, "curve identity")
    row["is_circle"] = curve.IsCircle()
    row["is_line"] = curve.IsLine()
    row["is_bcurve"] = curve.IsBcurve()
    for name in ("is_circle", "is_line", "is_bcurve"):
        boolean(row[name], name)
    if row["is_circle"] and row["is_line"]:
        raise RuntimeError("curve reports both line and circle")

    row["end_params_return"] = curve.GetEndParams()
    result = sequence(
        row["end_params_return"], label="GetEndParams", minimum=5, maximum=5
    )
    if result[0] is not True:
        raise RuntimeError("GetEndParams rejected")
    numbers(result[1:3], 2, "curve parameter interval")
    closed, periodic = (boolean(result[3], "closed"), boolean(result[4], "periodic"))

    raw_trim = edge.GetCurveParams3()
    if raw_trim is None:
        raise RuntimeError("edge has no native trim data")
    trim = _early_bound(raw_trim, "ICurveParamData")
    data = row["trim"] = {}
    for name in (
        "CurveType",
        "CurveTag",
        "Sense",
        "UMinValue",
        "UMaxValue",
        "StartPoint",
        "EndPoint",
    ):
        data[name] = getattr(trim, name)
    integer(data["CurveType"], 3001, 3009, "trim curve type")
    integer(data["CurveTag"], -2147483648, 2147483647, "curve tag")
    boolean(data["Sense"], "edge sense")
    numbers((data["UMinValue"], data["UMaxValue"]), 2, "edge trim interval")
    numbers(data["StartPoint"], 3, "trim start")
    numbers(data["EndPoint"], 3, "trim end")
    if data["UMinValue"] >= data["UMaxValue"]:
        raise RuntimeError("native edge trim interval is not increasing")

    if row["is_line"] or row["is_circle"]:
        row["analytic_parameters"] = (
            curve.CircleParams if row["is_circle"] else curve.LineParams
        )
        numbers(
            row["analytic_parameters"], 7 if row["is_circle"] else 6, "analytic curve"
        )
        row["existing_geometry"] = attachments.geometry(edge, 1)
        return
    if not row["is_bcurve"]:
        raise RuntimeError(f"unsupported nonanalytic native curve {row['identity']}")

    # False/False does not request cubic/non-rational conversion. Request
    # nonperiodicity only when the native curve already reports nonperiodic.
    arguments = (False, False, not periodic, closed)
    row["bcurve_arguments"] = arguments
    raw_spline = curve.GetBCurveParams5(*arguments)
    row["bcurve_return"] = "null" if raw_spline is None else "ISplineParamData"
    if raw_spline is None:
        raise RuntimeError("GetBCurveParams5 returned null for the recorded call shape")
    spline = _early_bound(raw_spline, "ISplineParamData")
    metadata = row["spline"] = {}
    for name in (
        "Dimension",
        "Order",
        "Periodic",
        "ControlPointsCount",
        "KnotPointsCount",
    ):
        metadata[name] = getattr(spline, name)
    dimension = integer(metadata["Dimension"], 3, 4, "3D spline dimension")
    order = integer(metadata["Order"], 2, 64, "spline order")
    count = integer(metadata["ControlPointsCount"], order, 10000, "control count")
    spline_periodic = integer(metadata["Periodic"], 0, 1, "spline periodicity")
    knots = integer(metadata["KnotPointsCount"], 1, 10064, "knot count")
    if spline_periodic != int(periodic):
        raise RuntimeError("returned spline changed native periodicity")
    if knots != count + (1 if spline_periodic else order):
        raise RuntimeError("spline knot count contradicts native metadata")
    for method, size in (
        ("GetControlPoints", count * dimension),
        ("GetKnotPoints", knots),
    ):
        row[method] = getattr(spline, method)()
        returned = sequence(row[method], label=method, minimum=2, maximum=2)
        if returned[0] is not True:
            raise RuntimeError(f"{method} rejected")
        numbers(returned[1], size, method)
    knot_values = row["GetKnotPoints"][1]
    if any(first > second for first, second in zip(knot_values, knot_values[1:])):
        raise RuntimeError("native knots are not nondecreasing")
