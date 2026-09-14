r"""McMaster 9432K31 -- music-wire steel extension spring, machine hook ends.

Native rebuild of the vendor part (1/4" OD x 0.026" wire, 55.5 coils,
49.4792 mm / 1.948" free length, hook ends), authored feature-for-feature the
way McMaster authored it -- no imported body, no dump replay, no rate formula.

Vendor tree (harvest ``cad/out/reports/mcmaster-9432K31-dump.json``)::

    Sketch3 (seed circle r 2.8448 on Plane1 @ x = -19.7104)
    Helix/Spiral1   height 39.4208, 55.5 revs, start 180 deg, RH
    Sketch2         hook arc R 2.8448, 180 deg, centre (-22.225, 0, 0)
                    + the construction centreline the pattern turns about
    3DSketch1       coil->hook transition spline, handle magnitude
                    D1 = D2 = OD*3/4 = 4.7625 at both ends
    CompCurve4      Sketch2 (arc) + 3DSketch1 (spline)
    Sweep2          circular profile 0.6604 along CompCurve4  -> hook body
    CirPattern1     the Sweep2 BODY, 2 x 360 deg about the sketch centreline
    Sweep3          circular profile 0.6604 along the helix, merges all three

Result: one body, seven faces (coil tube, 2 x hook torus, 2 x transition
tube, 2 x flat wire-end caps).

Frame (vendor's own, kept as-is -- the replica needs no COM remap): coil axis
+X, origin at the spring centre, both hook eyes lie in the model XY plane
with their bores parallel to Z and their openings facing -Y.

Geometry taken from the vendor model, not re-derived:

* the transition spline is read back natively as ONE clamped cubic Bezier
  (order 4, four control points, knots [0,0,0,0,1,1,1,1]) and those four
  points are used verbatim -- the ``OD*3/4`` handle magnitude is exactly 3x
  the control-point offset, so nothing is fitted;
* the hook is rigid: its arc, its loop-end handle and both handle magnitudes
  are the vendor's, and the whole hook translates by (L - free)/2 when the
  catalog length changes.  Only the coil stretches, and only the transition's
  coil-end handle turns with it, so the swept wire stays tangent continuous
  where the transition meets the helix.

``length_mm`` is the catalog INSIDE-hook length; ``None`` (the default) is the
free length and reproduces the vendor body exactly.  ``truth`` is accepted for
:func:`diag_mcmaster_lib.run_replica` (it gates the finished body) and is
deliberately NOT read while building.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_9432K31.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    _early_bound,
    check,
    name_last_feature,
    volume_check,
)
from channel_spring_stock_geom import (  # noqa: E402
    COIL_MEAN_RADIUS_MM,
    COIL_TURNS,
    FREE_LENGTH_MM,
    TRANSITION_TANGENT_MM,
    WIRE_DIA_MM,
    check_length_mm,
    coil_ends_mm,
    end_centers_mm,
    helix_height_mm,
    helix_pitch_mm,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    bodies,
    insert_helix,
    no_sketch_inference,
    offset_plane,
    replica_main,
)

# swconst values read off this install's swconst.tlb (SW 3DEXPERIENCE R2026x).
SW_FM_SWEEP = 17  # swFeatureNameID_e.swFmSweep
SW_FM_CIRPATTERN = 5  # swFeatureNameID_e.swFmCirPattern
SW_MINIMUM_TWIST = 10  # swTangencyType_e.swMinimumTwist (vendor PathAlignmentType)
SW_TWIST_FOLLOW_PATH = 0  # swTwistControlType_e.swTwistControlFollowPath
SW_TANGENCY_NONE = 0  # swTangencyType_e.swTangencyNone (vendor Start/EndTangencyType)
SW_SKETCH_LINE = 0  # swSketchSegments_e.swSketchLINE
SW_SEL_EXT_SKETCH_SEGS = 24  # swSelectType_e.swSelEXTSKETCHSEGS ("EXTSKETCHSEGMENT")
SW_SEL_SOLID_BODIES = 76  # swSelectType_e.swSelSOLIDBODIES ("SOLIDBODY")
# ICircularPatternFeatureData's own mark table: 1 = direction axis,
# 4 = features to pattern, 256 = BODIES to pattern (this vendor feature).
SW_MARK_BODIES_TO_PATTERN = 256

# Vendor Line12@Sketch2: the construction centreline CirPattern1 turns about
# (axis_type 3 == sketch line).  Its length is cosmetic; its direction is not.
PATTERN_AXIS_LEN_MM = 2.629784

_POS_TOL_MM = 1e-6  # positional agreement demanded of every rebuilt curve
_SAMPLES = 25  # spline verification samples
_POLY_SEGMENTS = 4000  # analytic-Bezier polyline used to measure deviation


# --------------------------------------------------------------------------
# pure geometry (mm) -- the vendor's transition curve
# --------------------------------------------------------------------------
# Native read-back of the vendor's 3DSketch1/Spline1 (ISplineParamData off
# ISketchSegment::GetCurve): Dimension 3, Order 4, 4 control points, knots
# [0,0,0,0,1,1,1,1] -- one clamped cubic Bezier, exactly as its two tangent-
# driving handles of magnitude OD*3/4 imply.  These are the vendor's own
# doubles, not a reconstruction.
VENDOR_TRANSITION_CP_MM = (
    (-22.225, 2.844799999999999, 0.0),
    (-20.637500000000003, 2.8447999999999984, 1.313149238967755e-24),
    (-19.773433588404487, 1.5862480767989158, 2.8450357638548507),
    (-19.710400000000003, 0.0, 2.844799999999999),
)
# Handle 2 (coil end) read back as radial -1.5310796881807311 rad, polar
# -0.00014851266501942706 rad, magnitude 4.7625 mm, with the direction
# (cos r cos p, sin r cos p, sin p) reproducing the control points to 1e-15.
# Its radial is the free-pitch helix tangent to 7.3e-9 rad; the polar tilt is
# the vendor solver's own residue and rides along with the hook.
VENDOR_HANDLE_POLAR_RAD = -0.00014851266501942706
# The basis those four points live in, straight off the same read-back.
_SPLINE_ORDER = 4
_CLAMPED_KNOTS = (0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0)
_KNOT_TOL = 1e-12
_FREE_EPS_MM = 1e-9


def transition_bezier_mm(length_mm: float | None = None) -> list[tuple[float, ...]]:
    """Control points of the -X coil->hook transition (mm), free or stretched.

    At the free length these are the vendor's own control points, untouched.
    Stretching translates the rigid hook -- arc, loop-end handle and both
    handle magnitudes are the vendor's -- by ``-(L - free)/2``, and turns the
    coil-end handle to the stretched pitch's helix tangent.  That last turn is
    what the vendor's own tangency relation would do: the hook end of the
    spline is rigid, the coil end has to stay tangent to the helix or the two
    sweeps meet in a notch instead of a continuous wire.
    """
    length = check_length_mm(length_mm)
    if abs(length - FREE_LENGTH_MM) <= _FREE_EPS_MM:
        return [tuple(p) for p in VENDOR_TRANSITION_CP_MM]
    dx = -(length - FREE_LENGTH_MM) / 2.0
    b0, b1, _b2, b3 = ((p[0] + dx, p[1], p[2]) for p in VENDOR_TRANSITION_CP_MM)
    radial = math.atan2(-COIL_MEAN_RADIUS_MM, helix_pitch_mm(length) / (2.0 * math.pi))
    polar = VENDOR_HANDLE_POLAR_RAD
    t3 = (
        math.cos(radial) * math.cos(polar),
        math.sin(radial) * math.cos(polar),
        math.sin(polar),
    )
    m = TRANSITION_TANGENT_MM / 3.0
    return [b0, b1, tuple(b3[i] - m * t3[i] for i in range(3)), b3]


def _bezier_point(bez: list[tuple[float, ...]], t: float) -> tuple[float, ...]:
    u = 1.0 - t
    w = (u * u * u, 3.0 * u * u * t, 3.0 * u * t * t, t * t * t)
    return tuple(sum(w[k] * bez[k][i] for k in range(4)) for i in range(3))


def _bezier_monomials(bez: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """Bezier -> power basis: P(s) = c0 + c1 s + c2 s^2 + c3 s^3."""
    b0, b1, b2, b3 = bez
    return [
        b0,
        tuple(3.0 * (b1[i] - b0[i]) for i in range(3)),
        tuple(3.0 * (b0[i] - 2.0 * b1[i] + b2[i]) for i in range(3)),
        tuple(-b0[i] + 3.0 * b1[i] - 3.0 * b2[i] + b3[i] for i in range(3)),
    ]


def _bezier_length_mm(bez: list[tuple[float, ...]], steps: int = 20000) -> float:
    """Arc length by Simpson on |P'(s)| (cubic -> converges to ~1e-12 mm)."""
    c = _bezier_monomials(bez)

    def speed(s: float) -> float:
        d = [c[1][i] + 2.0 * c[2][i] * s + 3.0 * c[3][i] * s * s for i in range(3)]
        return math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])

    h = 1.0 / steps
    total = speed(0.0) + speed(1.0)
    for i in range(1, steps):
        total += (4.0 if i % 2 else 2.0) * speed(i * h)
    return total * h / 3.0


def _bezier_polyline(bez: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    return [_bezier_point(bez, i / _POLY_SEGMENTS) for i in range(_POLY_SEGMENTS + 1)]


def _distance_to_polyline(p: tuple[float, ...], poly: list[tuple[float, ...]]) -> float:
    best = float("inf")
    for k in range(len(poly) - 1):
        a, b = poly[k], poly[k + 1]
        vx, vy, vz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        wx, wy, wz = p[0] - a[0], p[1] - a[1], p[2] - a[2]
        vv = vx * vx + vy * vy + vz * vz
        t = 0.0 if vv == 0.0 else max(0.0, min(1.0, (wx * vx + wy * vy + wz * vz) / vv))
        dx, dy, dz = wx - t * vx, wy - t * vy, wz - t * vz
        best = min(best, dx * dx + dy * dy + dz * dz)
    return math.sqrt(best)


def wire_length_mm(length_mm: float | None = None) -> float:
    """Swept wire centreline: 2 hook arcs + 2 transitions + the helix."""
    a = COIL_MEAN_RADIUS_MM
    arcs = 2.0 * math.pi * a
    transitions = 2.0 * _bezier_length_mm(transition_bezier_mm(length_mm))
    helix = COIL_TURNS * math.hypot(2.0 * math.pi * a, helix_pitch_mm(length_mm))
    return arcs + transitions + helix


# --------------------------------------------------------------------------
# COM helpers
# --------------------------------------------------------------------------
def _sketch_frame(sketch) -> tuple[list[tuple[float, ...]], tuple[float, ...]]:
    """Rows + translation (mm) of the model->sketch transform of ``sketch``.

    ``IMathTransform::ArrayData`` stores the rotation as three COLUMNS, so
    sketch_x = a[0]*px + a[3]*py + a[6]*pz + a[9] (verified against the
    vendor's own Plane1 sketch, whose transform maps (-19.7104, 0, 0) to the
    sketch origin).
    """
    xf = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    a = [float(v) for v in (xf.ArrayData or [])]
    if len(a) != 16:
        raise RuntimeError(f"ArrayData returned {len(a)} doubles, expected 16")
    if abs(a[12] - 1.0) > 1e-12:
        raise RuntimeError(f"sketch transform is scaled by {a[12]}, expected 1.0")
    rows = [(a[0], a[3], a[6]), (a[1], a[4], a[7]), (a[2], a[5], a[8])]
    trans = tuple(v * 1000.0 for v in a[9:12])
    return rows, trans


def _to_sketch_mm(frame, p_mm: tuple[float, float, float]) -> tuple[float, ...]:
    rows, trans = frame
    return tuple(
        sum(rows[k][i] * p_mm[i] for i in range(3)) + trans[k] for k in range(3)
    )


def _sketch_manager(adapter):
    """``ISketchManager`` off the model (the adapter only caches it while a
    2D sketch it opened is active)."""
    return _early_bound(adapter.currentModel.SketchManager, "ISketchManager")


def _feature_by_name(adapter, name: str):
    """``FeatureByName`` is declared on IPartDoc, not on IModelDoc2."""
    feature = _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(name)
    if feature is None:
        raise RuntimeError(f"feature {name!r} not found")
    return _early_bound(feature, "IFeature")


def _active_sketch(adapter):
    sketch = _sketch_manager(adapter).ActiveSketch
    if sketch is None:
        raise RuntimeError("no active sketch")
    return _early_bound(sketch, "ISketch")


def _require_identity_frame(frame, label: str) -> None:
    rows, trans = frame
    ident = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    off = max(
        max(abs(rows[k][i] - ident[k][i]) for i in range(3)) for k in range(3)
    ) + max(abs(t) for t in trans)
    if off > 1e-9:
        raise RuntimeError(
            f"{label}: sketch frame is not the model frame (rows {rows}, "
            f"translation {trans}); the vendor authors this sketch on Front "
            "with an identity transform"
        )


def _sketch_segment(adapter, feature_name: str):
    """The single segment of a named sketch feature (read back, as the
    documented Edit Spline example does, from the CLOSED sketch)."""
    sketch = _early_bound(
        _feature_by_name(adapter, feature_name).GetSpecificFeature2(), "ISketch"
    )
    segments = list(sketch.GetSketchSegments() or [])
    if len(segments) != 1:
        raise RuntimeError(f"{feature_name} holds {len(segments)} segments, expected 1")
    return _early_bound(segments[0], "ISketchSegment")


def _spline_params(segment) -> tuple[int, int, list[float]]:
    """(order, control-point count, knot vector) of a sketch spline, read
    unconverted -- the caller has already refused rational splines."""
    curve = _early_bound(segment.GetCurve(), "ICurve")
    data = _early_bound(
        curve.GetBCurveParams5(False, False, False, False), "ISplineParamData"
    )
    dim = int(data.Dimension)
    if dim != 3:
        raise RuntimeError(
            f"spline came back with dimension {dim}; the vendor curve is a "
            "non-rational 3D cubic (dimension 3)"
        )
    order = int(data.Order)
    count = int(data.ControlPointsCount)
    knots = [float(k) for k in _com_out(data.GetKnotPoints(), "GetKnotPoints")]
    return order, count, knots


def _com_out(result, label: str):
    """Unpack the ``(retval, out)`` tuple an early-bound [out] param returns."""
    if not (isinstance(result, tuple) and len(result) == 2):
        raise RuntimeError(f"{label} returned {result!r}, expected (status, data)")
    ok, data = result
    if not ok or data is None:
        raise RuntimeError(f"{label} failed (status {ok!r})")
    return list(data)


# --------------------------------------------------------------------------
# feature steps
# --------------------------------------------------------------------------
async def _coil_helix(adapter, length_mm: float | None, feature_name: str) -> None:
    """Vendor Sketch3 + Helix/Spiral1: seed circle on a plane at the coil start.

    The start angle and the two direction flags are computed from the plane
    SolidWorks actually built rather than hardcoded, so an offset plane whose
    normal or in-plane axes come out flipped still lands the helix start on
    the transition spline's end point.  Right-handed about the advance
    direction means ``Clockwised == Reversed`` (advance is +normal when
    ``Reversed`` is false, and ``Clockwised`` is read about +normal).
    """
    a = COIL_MEAN_RADIUS_MM
    x_start, _ = coil_ends_mm(length_mm)
    plane = "CoilStartPlane"
    offset_plane(adapter, plane, x_start, base="Right Plane")
    check(f"create_sketch {plane}", await adapter.create_sketch(plane))
    seed = _sketch_manager(adapter).CreateCircleByRadius(0.0, 0.0, 0.0, a / 1000.0)
    if seed is None:
        raise RuntimeError("helix seed circle failed")

    frame = _sketch_frame(_active_sketch(adapter))
    origin = _to_sketch_mm(frame, (x_start, 0.0, 0.0))
    if max(abs(c) for c in origin) > _POS_TOL_MM:
        raise RuntimeError(
            f"{plane} does not pass through the coil axis at x={x_start:.4f}: "
            f"that point maps to sketch {origin}"
        )
    start = _to_sketch_mm(frame, (x_start, 0.0, a))
    if abs(start[2]) > _POS_TOL_MM or abs(math.hypot(start[0], start[1]) - a) > 1e-9:
        raise RuntimeError(
            f"helix start point (x={x_start:.4f}, 0, {a}) is not on the seed "
            f"circle of {plane}: sketch coords {start}"
        )
    start_angle = math.atan2(start[1], start[0]) % (2.0 * math.pi)
    reversed_dir = frame[0][2][0] < 0.0  # plane normal's X component
    _telemetry.info(
        f"helix: start angle {math.degrees(start_angle):.4f} deg, "
        f"reversed={reversed_dir}, clockwise={reversed_dir}"
    )

    # The vendor defines the helix by HEIGHT and revolution (its height is the
    # equation ``Length - 2*(OD - 2*Wire Diameter)``); pitch and revolution is
    # the same curve for pitch = height/turns, and it is the call this repo
    # has proven live, so the shared helper carries it.
    insert_helix(
        adapter,
        helix_pitch_mm(length_mm),
        COIL_TURNS,
        clockwise=reversed_dir,  # Clockwised == Reversed keeps it right-handed
        reversed_dir=reversed_dir,
        start_angle_rad=start_angle,
        feature_name=feature_name,
    )
    _verify_helix(adapter, feature_name, length_mm)


def _verify_helix(adapter, feature_name: str, length_mm: float | None) -> None:
    """The helix must end where the two hook transitions do, or the sweep
    joins the coil to the hooks with a kink instead of tangentially."""
    a = COIL_MEAN_RADIUS_MM
    x_start, x_end = coil_ends_mm(length_mm)
    feature = _feature_by_name(adapter, feature_name)
    curve_feature = _early_bound(feature.GetSpecificFeature2(), "IReferenceCurve")
    edge = _early_bound(curve_feature.GetFirstSegment(), "IEdge")
    edge.GetCurve()  # required before GetCurveParams2 (SolidWorks caches it)
    params = [float(v) for v in (edge.GetCurveParams2() or [])]
    if len(params) < 6:
        raise RuntimeError(f"helix edge returned {len(params)} curve params")
    got = [
        tuple(v * 1000.0 for v in params[0:3]),
        tuple(v * 1000.0 for v in params[3:6]),
    ]
    want = [(x_start, 0.0, a), (x_end, 0.0, -a)]
    worst = min(
        max(
            max(abs(g[i] - w[i]) for i in range(3))
            for g, w in zip(order, want, strict=True)
        )
        for order in (got, got[::-1])
    )
    if worst > 1e-4:
        raise RuntimeError(
            f"helix ends at {got} but the hook transitions need {want} "
            f"(worst axis error {worst:.6f} mm) -- start angle or handedness"
        )
    _telemetry.info(f"helix ends verified within {worst:.6f} mm")


def _hook_sketch(adapter, length_mm: float | None, feature_name: str) -> None:
    """Vendor Sketch2: the 180 deg hook arc plus the pattern centreline.

    The centreline is construction geometry, so ``InsertCompositeCurve`` skips
    it and it survives as the pattern axis (found again by name at pattern
    time -- a segment pointer taken here would predate three rebuilds).
    """
    a = COIL_MEAN_RADIUS_MM
    x_eye = end_centers_mm(length_mm)[0][0]
    _require_identity_frame(_sketch_frame(_active_sketch(adapter)), feature_name)
    sk = _sketch_manager(adapter)
    # CCW from the +Y transition end to the -Y free tip -> the eye bulges -X.
    arc = sk.CreateArc(
        x_eye / 1000.0,
        0.0,
        0.0,
        x_eye / 1000.0,
        a / 1000.0,
        0.0,
        x_eye / 1000.0,
        -a / 1000.0,
        0.0,
        1,
    )
    if arc is None:
        raise RuntimeError("hook arc failed")
    axis = sk.CreateCenterLine(0.0, 0.0, 0.0, 0.0, -PATTERN_AXIS_LEN_MM / 1000.0, 0.0)
    if axis is None:
        raise RuntimeError("pattern centreline failed")


def _transition_sketch(
    adapter, bez: list[tuple[float, ...]], feature_name: str
) -> None:
    """Vendor 3DSketch1: the coil->hook transition, as the vendor's own cubic.

    The vendor's spline IS a single clamped cubic Bezier -- order 4, four
    control points, knots [0,0,0,0,1,1,1,1] -- so it is handed to SolidWorks
    as exactly that B-curve (``ISketchManager::CreateSplineParamData`` filled
    in and passed to ``ISketchManager::CreateSplinesByEqnParams2``, the
    documented route for authoring a spline from B-spline parameters).  No
    fitting and no control-point editing: the numbers that go in are the
    vendor's numbers.  The realised curve is then measured against the cubic
    before anything is swept along it.
    """
    import pythoncom
    from win32com.client import VARIANT

    def _doubles(values: tuple[float, ...] | list[float]):
        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in values])

    model = adapter.currentModel
    sk = _sketch_manager(adapter)
    sk.Insert3DSketch(True)
    data = _early_bound(sk.CreateSplineParamData(), "ISplineParamData")
    data.Dimension = 3
    data.Order = _SPLINE_ORDER
    data.Periodic = 0
    data.ControlPointsCount = len(bez)
    control_points: list[float] = []
    for point in bez:
        control_points.extend(c / 1000.0 for c in point)
    if not data.SetControlPoints(_doubles(control_points)):
        raise RuntimeError("SetControlPoints rejected the vendor control points")
    if not data.SetKnotPoints(_doubles(_CLAMPED_KNOTS)):
        raise RuntimeError("SetKnotPoints rejected the clamped cubic knot vector")
    created = sk.CreateSplinesByEqnParams2(data)
    segments = list(created) if isinstance(created, (list, tuple)) else [created]
    if not created or segments[0] is None:
        raise RuntimeError(
            "CreateSplinesByEqnParams2 created no segment from the vendor cubic"
        )
    if len(segments) != 1:
        raise RuntimeError(
            f"the vendor cubic came back as {len(segments)} segments; it is one "
            "G1 span and must stay one"
        )
    model.ClearSelection2(True)
    sk.Insert3DSketch(True)
    # This family of calls writes straight to the database (documented: it
    # ignores AddToDB/DisplayWhenAdded), so the sketch is rebuilt before the
    # curve is read back and swept.
    model.ForceRebuild3(True)
    name_last_feature(adapter, feature_name)

    segment = _sketch_segment(adapter, feature_name)
    if bool(_early_bound(segment, "ISketchSpline").IsRationalCurve):
        raise RuntimeError(
            "SolidWorks made a RATIONAL spline out of a polynomial cubic; its "
            "weights would distort the parameterisation"
        )
    order, count, knots = _spline_params(segment)
    shape = (order, count, len(knots))
    want_shape = (_SPLINE_ORDER, len(bez), len(_CLAMPED_KNOTS))
    knot_err = (
        max(abs(k - w) for k, w in zip(knots, _CLAMPED_KNOTS, strict=True))
        if shape == want_shape
        else float("inf")
    )
    if shape != want_shape or knot_err > _KNOT_TOL:
        raise RuntimeError(
            f"transition spline came back order {order} with {count} control "
            f"points and knots {knots} -- the vendor basis is order "
            f"{_SPLINE_ORDER}, {len(bez)} points, knots {list(_CLAMPED_KNOTS)}"
        )
    _verify_transition(adapter, feature_name, bez)


def _verify_transition(
    adapter, feature_name: str, bez: list[tuple[float, ...]]
) -> None:
    """Sample the realised curve and measure it against the vendor's cubic."""
    curve = _early_bound(_sketch_segment(adapter, feature_name).GetCurve(), "ICurve")
    ends = curve.GetEndParams()
    if not (isinstance(ends, tuple) and len(ends) == 5 and ends[0]):
        raise RuntimeError(f"GetEndParams returned {ends!r}")
    t0, t1 = float(ends[1]), float(ends[2])
    poly = _bezier_polyline(bez)
    worst = 0.0
    got_ends = []
    for i in range(_SAMPLES + 1):
        t = t0 + (t1 - t0) * i / _SAMPLES
        ev = [float(v) for v in (curve.Evaluate2(t, 0) or [])]
        if len(ev) < 3:
            raise RuntimeError(f"Evaluate2({t}) returned {ev!r}")
        point = tuple(v * 1000.0 for v in ev[0:3])
        if i in (0, _SAMPLES):
            got_ends.append(point)
        worst = max(worst, _distance_to_polyline(point, poly))
    # Lateral deviation alone would not catch a curve that runs the right
    # path but stops short of the arc or the helix.
    end_err = min(
        max(
            max(abs(g[k] - w[k]) for k in range(3))
            for g, w in zip(pair, (bez[0], bez[3]), strict=True)
        )
        for pair in (got_ends, got_ends[::-1])
    )
    if end_err > _POS_TOL_MM:
        raise RuntimeError(
            f"{feature_name} ends at {got_ends}, needs {(bez[0], bez[3])} "
            f"(worst axis error {end_err:.6f} mm)"
        )
    if worst > _POS_TOL_MM:
        raise RuntimeError(
            f"{feature_name} deviates from the vendor cubic by {worst:.6f} mm "
            f"(limit {_POS_TOL_MM} mm): the control-point edit did not stick"
        )
    _telemetry.info(f"transition spline matches the vendor cubic within {worst:.3e} mm")


def _composite_curve(adapter, parts: list[str], feature_name: str) -> None:
    """Vendor CompCurve4: join the hook arc and the transition into one path.

    Construction geometry (the pattern centreline) is not joined, which is
    exactly why the vendor keeps both in one sketch.
    """
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    model = adapter.currentModel
    model.ClearSelection2(True)
    for i, part in enumerate(parts):
        if not _select_named_feature(adapter, part, 1, i > 0):
            raise RuntimeError(f"cannot select {part!r} for the composite curve")
    if not model.InsertCompositeCurve():
        raise RuntimeError("InsertCompositeCurve failed")
    model.ClearSelection2(True)
    name_last_feature(adapter, feature_name)


def _sweep_wire(adapter, path: str, feature_name: str) -> None:
    """Vendor Sweep2/Sweep3: circular profile of the wire diameter along ``path``.

    Option values are the vendor's read-back set, in the order the SolidWorks
    "swept cut using a circular profile" example writes them.  Two are not in
    the harvest and are pinned by the vendor's RESULT instead: ``Merge`` (the
    part ends as one body, so the coil sweep must absorb both hook bodies) and
    the feature scope's body list -- the vendor stored ``AutoSelect = False``,
    i.e. an explicit list the harvest does not carry, and auto-select over a
    part whose every body must merge is the same scope.
    """
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    model = adapter.currentModel
    fm = _early_bound(model.FeatureManager, "IFeatureManager")
    data = _early_bound(fm.CreateDefinition(SW_FM_SWEEP), "ISweepFeatureData")
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, path, 4, False):
        raise RuntimeError(f"cannot select sweep path {path!r} (mark 4)")
    data.TangentPropagation = False
    data.AlignWithEndFaces = False
    data.TwistControlType = SW_TWIST_FOLLOW_PATH
    data.MaintainTangency = False
    data.AdvancedSmoothing = False
    data.StartTangencyType = SW_TANGENCY_NONE
    data.EndTangencyType = SW_TANGENCY_NONE
    data.PathAlignmentType = SW_MINIMUM_TWIST
    data.Direction = -1
    data.ThinFeature = False
    data.Merge = True
    data.FeatureScope = True
    data.AutoSelect = True
    data.MergeSmoothFaces = True
    data.CircularProfile = True
    data.CircularProfileDiameter = WIRE_DIA_MM / 1000.0
    with _telemetry.span("feature.sweep_wire", label=feature_name):
        swept = fm.CreateFeature(data)
    model.ClearSelection2(True)
    if swept is None:
        raise RuntimeError(f"CreateFeature (sweep) returned None for {feature_name}")
    name_last_feature(adapter, feature_name)


def _construction_line_name(adapter, sketch_name: str) -> str:
    """Name of the one construction line in a named sketch (live, post-rebuild)."""
    sketch = _early_bound(
        _feature_by_name(adapter, sketch_name).GetSpecificFeature2(), "ISketch"
    )
    segments = [
        _early_bound(seg, "ISketchSegment")
        for seg in (sketch.GetSketchSegments() or [])
    ]
    lines = [
        seg
        for seg in segments
        if seg.GetType() == SW_SKETCH_LINE and bool(seg.ConstructionGeometry)
    ]
    if len(lines) != 1:
        raise RuntimeError(
            f"{sketch_name} holds {len(lines)} construction lines, expected the "
            "single pattern centreline"
        )
    name = str(lines[0].GetName())
    if not name:
        raise RuntimeError(f"the {sketch_name} centreline has no name to select by")
    return name


def _hook_pattern(adapter, sketch_name: str, feature_name: str) -> None:
    """Vendor CirPattern1: the hook BODY, twice, 360 deg about the centreline.

    Read natively off the vendor feature (``IFeature::GetDefinition`` +
    ``AccessSelections``): ``BodyPattern`` true, seed bodies ``[Sweep2]``,
    seed features empty, ``TotalInstances`` 2, ``Spacing`` 2 pi,
    ``EqualSpacing`` true, ``ReverseDirection`` true, ``GeometryPattern``
    false.  So this is a bodies-to-pattern feature, not a features-to-pattern
    one, and the two modes take different inputs: bodies come in under mark
    256 and are read through ``PatternBodyArray``, which ``BodyPattern``
    gates.  ``IFeatureManager::FeatureCircularPattern5`` cannot express it --
    its documented marks cover features (4) and components only -- so the
    feature goes in the way the pattern feature-data page prescribes:
    pre-select, ``CreateDefinition(swFmCirPattern)``, set the vendor's
    fields, ``CreateFeature``.

    The axis is a SKETCH LINE (the vendor's GetAxisType reads 3), looked up
    live rather than kept from sketch time -- the sketch has been closed,
    absorbed by the composite curve and rebuilt since -- and selected by name
    as an EXTSKETCHSEGMENT under mark 1, first.  Both selections are read
    back and asserted, because a selection that does not stick produces no
    error, only a feature that never appears.

    Two instances over 360 deg is a 180 deg turn about model Y, which maps
    (x, y, z) to (-x, y, -z) -- the far hook, coplanar with the near one and
    opening the same way.
    """
    from solidworks_mcp.adapters.com_variant import null_callout

    model = adapter.currentModel
    fm = _early_bound(model.FeatureManager, "IFeatureManager")
    axis = f"{_construction_line_name(adapter, sketch_name)}@{sketch_name}"
    model.ClearSelection2(True)
    extension = _early_bound(model.Extension, "IModelDocExtension")
    if not extension.SelectByID2(
        axis, "EXTSKETCHSEGMENT", 0.0, 0.0, 0.0, False, 1, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {axis} as the pattern axis (mark 1)")
    seed_bodies = bodies(adapter)
    if len(seed_bodies) != 1:
        raise RuntimeError(
            f"the hook sweep left {len(seed_bodies)} bodies; the vendor patterns "
            "the single Sweep2 body"
        )
    sel_mgr = _early_bound(model.SelectionManager, "ISelectionMgr")
    select_data = _early_bound(sel_mgr.CreateSelectData(), "ISelectData")
    select_data.Mark = SW_MARK_BODIES_TO_PATTERN
    if not _early_bound(seed_bodies[0], "IBody2").Select2(True, select_data):
        raise RuntimeError("cannot select the hook body to pattern (mark 256)")
    # The definition is built from what is selected right now, so prove it:
    # one entity per mark, and the pair is a sketch segment plus a solid body.
    # (Counts are read per mark; the types are read over the whole list, whose
    # indexing needs no assumption about how marks index into it.)
    counts = tuple(
        int(sel_mgr.GetSelectedObjectCount2(mark))
        for mark in (1, SW_MARK_BODIES_TO_PATTERN)
    )
    types = sorted(
        int(sel_mgr.GetSelectedObjectType3(i + 1, -1))
        for i in range(int(sel_mgr.GetSelectedObjectCount2(-1)))
    )
    want_types = sorted((SW_SEL_EXT_SKETCH_SEGS, SW_SEL_SOLID_BODIES))
    if counts != (1, 1) or types != want_types:
        raise RuntimeError(
            f"pattern inputs are {counts} entities under marks "
            f"(1, {SW_MARK_BODIES_TO_PATTERN}) of swSelectType_e {types}; need "
            f"the axis {axis} ({SW_SEL_EXT_SKETCH_SEGS}) under mark 1 and the "
            f"hook body ({SW_SEL_SOLID_BODIES}) under mark "
            f"{SW_MARK_BODIES_TO_PATTERN}"
        )
    data = _early_bound(
        fm.CreateDefinition(SW_FM_CIRPATTERN), "ICircularPatternFeatureData"
    )
    # Bodies, not features: this is what makes the definition read the
    # mark-256 selection as PatternBodyArray.
    data.BodyPattern = True
    data.TotalInstances = 2
    data.EqualSpacing = True
    data.Spacing = 2.0 * math.pi
    data.ReverseDirection = True
    data.GeometryPattern = False
    with _telemetry.span("feature.hook_pattern", label=feature_name):
        pattern = fm.CreateFeature(data)
    model.ClearSelection2(True)
    if pattern is None:
        raise RuntimeError(
            "CreateFeature (circular body pattern) returned None with axis "
            f"{axis} (mark 1) and the hook body (mark "
            f"{SW_MARK_BODIES_TO_PATTERN})"
        )
    name_last_feature(adapter, feature_name)


# --------------------------------------------------------------------------
# builder
# --------------------------------------------------------------------------
async def build_9432K31(adapter, truth=None, *, length_mm: float | None = None):
    """Build 9432K31 into the current (empty) part.  Never opens or saves."""
    length = check_length_mm(length_mm)
    bez = transition_bezier_mm(length)
    _telemetry.info(
        f"9432K31: length {length:.4f} mm, helix {helix_height_mm(length):.4f} mm "
        f"x {COIL_TURNS} at pitch {helix_pitch_mm(length):.6f} mm, "
        f"eye centres +-{end_centers_mm(length)[1][0]:.4f} mm"
    )

    with no_sketch_inference(adapter):
        # --- coil (vendor Sketch3 + Helix/Spiral1) -------------------------
        await _coil_helix(adapter, length, "CoilHelix")

        # --- hook path (vendor Sketch2 + 3DSketch1 + CompCurve4) -----------
        check("create_sketch hook", await adapter.create_sketch("Front"))
        _hook_sketch(adapter, length, "HookProfile")
        check("exit_sketch hook", await adapter.exit_sketch())
        name_last_feature(adapter, "HookProfile")
        _transition_sketch(adapter, bez, "HookTransition")
        _composite_curve(adapter, ["HookProfile", "HookTransition"], "HookPath")

    # --- wire (vendor Sweep2 -> CirPattern1 -> Sweep3) ---------------------
    _sweep_wire(adapter, "HookPath", "HookWire")
    # (the hook sweep's single body is the pattern seed; _hook_pattern checks it)
    _hook_pattern(adapter, "HookProfile", "HookMirror")
    if len(bodies(adapter)) != 2:
        raise RuntimeError(
            f"hook pattern left {len(bodies(adapter))} bodies, expected 2"
        )
    _sweep_wire(adapter, "CoilHelix", "CoilWire")

    # --- shape checks (the vendor gate runs separately, on the free part) --
    body_list = bodies(adapter)
    if len(body_list) != 1:
        raise RuntimeError(
            f"coil sweep left {len(body_list)} bodies, expected 1 merged spring"
        )
    faces = list(_early_bound(body_list[0], "IBody2").GetFaces() or [])
    if len(faces) != 7:
        raise RuntimeError(
            f"spring has {len(faces)} faces, expected 7 (coil + 2 hooks + "
            "2 transitions + 2 wire-end caps)"
        )
    # Weyl: a tube of radius r about an embedded space curve has volume
    # pi*r^2*L exactly.  SolidWorks' integrator reads ~0.055 % under that on
    # this helical body (vendor part: 349.6031 mm^3 against 349.7950 analytic),
    # so this is a shape sanity check, not the vendor gate.
    expected = math.pi * (WIRE_DIA_MM / 2.0) ** 2 * wire_length_mm(length)
    await volume_check(adapter, "spring wire", expected, 0.003 * expected)

    # The replica is authored in the vendor's own frame: no COM remap.
    adapter._mcm_com_map = None


if __name__ == "__main__":
    sys.exit(replica_main("9432K31", build_9432K31))
