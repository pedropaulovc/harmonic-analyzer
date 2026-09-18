r"""McMaster 1330K524 -- music-wire DOUBLE-LOOP extension spring, 12.7 mm OD.

Native recipe, decoded feature by feature off the vendor part's own tree
(harvest ``cad/out/reports/mcmaster-1330K524-dump.json``).  This script
re-authors that tree; it never loads the dump as geometry (``truth`` is
accepted for the fleet's builder signature and deliberately unused), and it
never imports vendor CAD.

Vendor tree (solid-producing features only -- their Sketch1/2/4/5/6/12/27 are
configurator layout/equation scaffolding and carry no geometry this build
needs; the decoded constants live in :mod:`counter_spring_stock_geom`)::

    Plane5   z = -1.640205      (|| Front)        loop helix base
    Plane1   x = -116.7003      (|| Right)        coil helix base
    Plane3   x = +116.7003      (|| Right)        +X half-turn base
    Helix/Spiral1  coil segment  R 5.5499, 32 rev, rise 58.150125,
                                 ccw, start 180 deg
    Helix/Spiral3  -X loop       R 5.5499 @ x -122.2502, 1.75 rev,
                                 rise 3.28041, cw, start 0 deg
    3DSketch1/Spline5            loop -> coil transition, arc 9.665831
    CompCurve1 = Helix3 + Spline5
    Helix/Spiral2  +X half-turn  0.5 rev, rise 0.8001, cw, REVERSED
    3DSketch2/Spline6            arc 9.574238
    Helix/Spiral4  +X loop       1.75 rev, rise 3.28041, cw, start 90 deg
    CompCurve2 = Helix2 + Spline6 + Helix4
    Sweep1  profile r 0.8001 @ (-116.7003, 0, 5.5499) along CompCurve1
    Sweep2  same profile along Helix1            (the coil seed body)
    LPattern1  4 instances @ 58.150125 along +X  (128 turns total)
    Sweep3  profile r 0.8001 @ (116.7003, 0, 1.640205) along CompCurve2
    Combine1  ADD, 5 bodies -- everything EXCEPT Sweep3

Sweeps are authored with the vendor's read-back option set verbatim through
the obsolete ``InsertProtrusionSwept4`` (profile mark 1, path mark 4): twist
control ``swTwistControlFollowPath``, path align ``swMinimumTwist`` (10),
merge-smooth-faces on, merge OFF (each sweep is its own body), and the
per-sweep ``AlignWithEndFaces`` / ``EndTangencyType`` pair that decides
whether each free wire end is capped in the profile plane or perpendicular to
the path.  Those two flags are why the vendor's 13 faces are
``4 coil laterals + 2 + 2 caps`` on Combine1 and ``3 laterals + 2 caps`` on the
uncombined Sweep3, and why the two bodies only TOUCH (coincident wire-section
disc centred (115.9002, 0, 5.5499) in the plane y = 0) instead of merging.

Frame: authored **in the vendor's own frame** -- spring axis +X, eye axes +Z,
origin at mid-length -- so no ``_mcm_com_map`` is declared and the vendor COM
gate compares directly.  Plane and sketch frames are read back and asserted
(``IRefPlane::Transform`` / ``ISketch::ModelToSketchTransform``) because the
helix start angles below are expressed in those exact frames, and because
``create_sketch`` silently falls back to the standard planes when a named
plane fails to select.

Interface ownership: every COM member below is invoked on the interface that
DECLARES it, checked one by one against the generated wrapper, and read as a
plain attribute or call so a mis-binding RAISES.  Two that bite here:
``IFeatureManager::InsertRefPlane`` returns the reference PLANE
(``IRefPlane``), not its feature, so the transform is read off the return
while the feature is claimed from the tree; and ``FeatureByName`` is declared
on ``IPartDoc``, not ``IModelDoc2``, so named lookups go through the tree
walk.  An accessor that swallows the resulting error into ``None`` only moves
the crash three dereferences downstream, which is exactly how the first live
run failed (``IFeature::GetSpecificFeature2`` invoked on an ``IRefPlane``).

Transition splines: the vendor's two 3D splines are undimensioned and
solver-shaped, but a native detail read (``ISketchSpline`` ->
``ICurve::GetBCurveParams5``) shows each is a SINGLE CUBIC BEZIER -- order 4,
non-periodic, 4 control points, knots ``[0,0,0,0,1,1,1,1]`` -- so both are
re-authored control point for control point through
``ISketchManager::CreateSplineParamData`` +
``CreateSplinesByEqnParams2``.  The two interior control points are
axis-aligned (loop end straight inboard along X, coil end along +Y), which
leaves a ~3 deg kink against each adjoining helix; that is the vendor's own
wire and it is replicated, not smoothed.  Their handle lengths are
asymmetric (2.5536/3.3844 mm at ``-X``, 3.3804/2.1235 mm at ``+X``) and
reproduce the vendor's separately measured arc lengths (9.665831 /
9.574238 mm) to 1.5e-7 mm -- asserted at free length -- and every created
spline's ``ISketchSegment::GetLength`` is checked against its own control
points to 1e-3 mm.

``length_mm`` (catalogue INSIDE-loop length, mm; ``None`` = vendor free
geometry) stretches only the coil: its axial span, pitch and pattern spacing
follow the length while wire diameter, turn count and both rigid end loops do
not, and each end assembly translates by ``(L - 254)/2``.  The domain is the
catalogue extension range 254 .. 421.6146 mm -- an extension spring has no
compressed state -- enforced by
:func:`counter_spring_stock_geom.validate_length_mm`.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_1330K524.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
import counter_spring_stock_geom as geom  # noqa: E402
from _common import (  # noqa: E402
    _early_bound,
    _feature_by_name,
    _last_feature,
    check,
    name_last_feature,
    volume_check,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    SW_BODY_ADD,
    bodies,
    no_sketch_inference,
    replica_main,
)

PART_NO = "1330K524"

#: What this replica still takes on trust, all of it a READ of the vendor part
#: (``references/mcmaster/1330K524.SLDPRT``, which is not yet staged -- copy it
#: in before ``render_vendor``/the gate can run).  The transition B-curves are
#: NO LONGER on this list: they were read natively and are authored exactly.
#:
#: 1. ``LPattern1`` -> ``ILinearPatternFeatureData::DirectionReference``: the
#:    entity the vendor patterned along (their Sketch1 carries an X
#:    construction line).  This build inserts its own Front/Top axis and
#:    verifies the marching sense from the body box instead.
#: 2. ``Plane1``/``Plane3``/``Plane5`` -> ``IRefPlaneFeatureData::Reference``
#:    plus ``ReverseDirection``: confirms which base plane each offset came
#:    from and the flip convention.  This build asserts the resolved plane
#:    normal and origin instead, and retries the flip flag when the plane
#:    lands on the wrong side.
#: 3. ``Sweep1``/``Sweep2``/``Sweep3`` -> ``ISweepFeatureData`` start/end
#:    tangency read back on the rebuilt part, to confirm SolidWorks put the
#:    caps where the vendor's are (plain wire disc in the profile plane at the
#:    coil end, normal-to-path at the loop tip).
LIVE_READS_NEEDED = (
    "LPattern1 direction reference entity",
    "Plane1/Plane3/Plane5 reference + ReverseDirection",
    "Sweep1/2/3 start+end tangency read-back on the replica",
)

# swHelixDefinedBy_e.swHelixDefinedByHeightAndRevolution -- the vendor's own
# definition mode (defined_by 1), so the segment rise stays exact and the
# pitch is never round-tripped through 6 decimals.
SW_HELIX_HEIGHT_AND_REVOLUTION = 1

# Vendor helix start angles, in each base plane's own frame (asserted below).
COIL_START_ANGLE_DEG = 180.0  # -> (coil_start_x, 0, +R)
LOOP_NEG_START_ANGLE_DEG = 0.0  # -> (coil_start_x, 0, -1.640205) = wire tip
LOOP_POS_START_ANGLE_DEG = 90.0  # -> (+122.2502, +R, -1.640205)
HALF_TURN_START_ANGLE_DEG = 0.0  # -> (+116.7003, 0, -R)
HALF_TURN_TURNS = 0.5

# The vendor's two transitions, read natively off their 3D sketches
# (ISketchSpline -> ICurve::GetBCurveParams5): both are SINGLE CUBIC BEZIER
# segments -- Dimension 3, Order 4, non-periodic, 4 control points, knot
# vector [0,0,0,0,1,1,1,1] -- so they are re-authored exactly, control point
# for control point, through ISketchManager::CreateSplinesByEqnParams2.
#
# Both interior control points are AXIS-ALIGNED off their endpoints: the loop
# end's handle runs straight inboard along X, the coil end's handle straight
# along +Y.  That is NOT tangent to the adjoining helices (which leave tilted
# by their pitch: 3.08 deg at the loop, 2.98 deg at the coil), so the vendor's
# own wire has a small kink at each junction.  It is replicated, not
# "corrected": those kinks are exactly why their Sweep3 caps come out
# 2.1341 / 1.9683 mm2 instead of the plain wire disc 2.0111 mm2.
#
# Handle lengths are the read-back derivative magnitudes / 3 (SolidWorks
# reports 3 * |P1 - P0| for a cubic).  They are asymmetric between the two
# ends -- vendor solver output, not physics -- and reproduce the vendor's
# measured arc lengths to 1.5e-7 mm, which is the cross-check below.
TRANSITION_ORDER = 4
TRANSITION_KNOTS = (0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0)
TRANSITION_NEG_HANDLE_LOOP_MM = 2.553571092655277
TRANSITION_NEG_HANDLE_COIL_MM = 3.384357528593550
TRANSITION_POS_HANDLE_LOOP_MM = 3.380410828816682
TRANSITION_POS_HANDLE_COIL_MM = 2.123539631142306

# ISketchSegment::GetLength off the vendor's own splines, for the free-length
# consistency assert against the control points above.
TRANSITION_ARC_NEG_MM = 9.665831
TRANSITION_ARC_POS_MM = 9.574238
TRANSITION_ARC_TOL_MM = 0.001

# Expected plane normals (3rd column of IRefPlane::Transform.ArrayData[0:9]).
_NORMAL_RIGHT = (1.0, 0.0, 0.0)
_NORMAL_FRONT = (0.0, 0.0, 1.0)

# Sketch frames (columns of ISketch::ModelToSketchTransform.ArrayData[0:9] --
# the images of model X/Y/Z in sketch space; these are the vendor's own values
# for Sketch28 (Top), Sketch3 (|| Right) and Sketch24 (|| Front)).
_SKETCH_TOP = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
_SKETCH_RIGHT = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))
_SKETCH_FRONT = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

_FRAME_TOL = 1e-6
_BOX_SLACK_MM = 1.5  # SolidWorks body boxes run up to one wire radius proud

# Native per-body mass properties of the vendor part at free length, used to
# size the stage guards below and for one end-to-end sanity assert (the real
# gate is the fleet's SolidWorks-against-SolidWorks comparison).
VENDOR_COMBINE1_VOLUME_MM3 = 9117.468163768517
VENDOR_SWEEP3_VOLUME_MM3 = 174.52879455712852
VENDOR_FREE_VOLUME_MM3 = VENDOR_COMBINE1_VOLUME_MM3 + VENDOR_SWEEP3_VOLUME_MM3
VOLUME_STAGE_TOL = 0.025
VENDOR_FREE_VOLUME_TOL = 0.01


# --------------------------------------------------------------- geometry
def _bezier_speed(ctrl: tuple[tuple[float, float, float], ...], t: float) -> float:
    """Speed |dP/dt| of a cubic Bezier, for the arc-length cross-check."""
    p0, p1, p2, p3 = ctrl
    u = 1.0 - t
    a, b, c = 3.0 * u * u, 6.0 * u * t, 3.0 * t * t
    d = [
        a * (p1[i] - p0[i]) + b * (p2[i] - p1[i]) + c * (p3[i] - p2[i])
        for i in range(3)
    ]
    return math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])


def _bezier_length(
    ctrl: tuple[tuple[float, float, float], ...], panels: int = 2000
) -> float:
    """Composite-Simpson arc length (exact to ~1e-12 mm for a cubic)."""
    h = 1.0 / (2 * panels)
    total = _bezier_speed(ctrl, 0.0) + _bezier_speed(ctrl, 1.0)
    for i in range(1, 2 * panels):
        total += (4.0 if i % 2 else 2.0) * _bezier_speed(ctrl, i * h)
    return total * h / 3.0


def _transition_ctrl(
    length_mm: float, positive_x: bool
) -> tuple[tuple[float, float, float], ...]:
    """The vendor's four B-curve control points for one transition, in mm.

    The curve is rigid: its endpoints are the loop helix's inboard end and the
    coil-side helix's outboard end, and both interior points are axis-aligned
    offsets from those, so a length change only translates the whole end
    assembly along X.  Ordered loop end -> coil end, matching the vendor's own
    ``3DSketch1``/``3DSketch2`` point order.
    """
    r = geom.COIL_MEAN_RADIUS_MM
    eye_x = geom.end_centers_mm(length_mm)[1 if positive_x else 0][0]
    coil_x = geom.coil_start_x_mm(length_mm)
    z_loop = geom.LOOP_HALF_RISE_MM
    if positive_x:
        # A' -> loop4 tangent side, B' -> the reversed half-turn.
        loop_end = (eye_x, r, -z_loop)  # +122.2502, +5.5499, -1.640205
        coil_end = (-coil_x, 0.0, -r)  # +116.7003, 0, -5.5499
        handle_loop = -TRANSITION_POS_HANDLE_LOOP_MM
        handle_coil = TRANSITION_POS_HANDLE_COIL_MM
    else:
        loop_end = (eye_x, r, z_loop)  # -122.2502, +5.5499, +1.640205
        coil_end = (coil_x, 0.0, r)  # -116.7003, 0, +5.5499
        handle_loop = TRANSITION_NEG_HANDLE_LOOP_MM
        handle_coil = TRANSITION_NEG_HANDLE_COIL_MM
    return (
        loop_end,
        (loop_end[0] + handle_loop, loop_end[1], loop_end[2]),
        (coil_end[0], coil_end[1] + handle_coil, coil_end[2]),
        coil_end,
    )


def _helix_arc_mm(radius: float, turns: float, rise_mm: float) -> float:
    circ = 2.0 * math.pi * radius * turns
    return math.sqrt(circ * circ + rise_mm * rise_mm)


def _tube_volume_mm3(path_mm: float) -> float:
    """Ideal swept-wire volume for ``path_mm`` of centreline."""
    return math.pi * geom.WIRE_RADIUS_MM**2 * path_mm


async def _check_volume(adapter, label: str, path_mm: float) -> float:
    """Stage guard: part volume against the ideal tube volume of the wire laid
    down so far.

    The tolerance is deliberately 2.5%: SolidWorks integrates a tightly
    curved swept tube LIGHT, and the vendor's own bodies show how much --
    Combine1 9117.4682 mm3 against 9131.1559 ideal (-0.15%, coil-dominated)
    and Sweep3 174.5288 against 177.2614 (-1.57%, all end geometry, and its
    surface area is short by half that, exactly the signature of a slightly
    under-integrated tube radius).  This guard is for gross errors (a missing
    or doubled feature, a wrong profile radius); the precise instrument is the
    SolidWorks-against-SolidWorks gate in ``diag_mcmaster_lib``.
    """
    expected = _tube_volume_mm3(path_mm)
    return await volume_check(adapter, label, expected, VOLUME_STAGE_TOL * expected)


# ------------------------------------------------------------ COM helpers
def _frame_dev(got: tuple, want: tuple) -> float:
    return max(abs(g - w) for gc, wc in zip(got, want) for g, w in zip(gc, wc))


def _plane_frame(ref_plane) -> tuple[tuple, tuple[float, float, float]]:
    """(columns, origin_mm) of a reference plane, from ``IRefPlane::Transform``.

    ``IFeatureManager::InsertRefPlane`` returns the REFERENCE PLANE
    (``IRefPlane``), NOT its feature -- the API docs' own example casts the
    return to ``RefPlane`` and fetches the ``Feature`` separately -- so the
    transform is read straight off it and the feature is taken from the tree.
    Every member here is called on the interface that DECLARES it (checked
    against the generated wrapper) and read as a plain attribute: a wrong
    binding then raises, instead of being swallowed into a ``None`` that only
    surfaces three dereferences later.
    """
    plane = _early_bound(ref_plane, "IRefPlane")
    xform = _early_bound(plane.Transform, "IMathTransform")
    arr = [float(v) for v in (xform.ArrayData or ())]
    if len(arr) != 16:
        raise RuntimeError(f"IRefPlane::Transform gave {len(arr)} doubles, expected 16")
    if abs(arr[12] - 1.0) > 1e-12:
        raise RuntimeError(f"plane transform is scaled by {arr[12]}, expected 1.0")
    cols = (tuple(arr[0:3]), tuple(arr[3:6]), tuple(arr[6:9]))
    origin = (arr[9] * 1000.0, arr[10] * 1000.0, arr[11] * 1000.0)
    return cols, origin


def _delete_feature(adapter, feat) -> None:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    model.ClearSelection2(True)
    if not _early_bound(feat, "IFeature").Select2(False, 0):
        raise RuntimeError("cannot select feature for delete")
    if not adapter._attempt(lambda: extension.DeleteSelection2(0), default=False):
        adapter._attempt(lambda: model.EditDelete(), default=None)
    model.ClearSelection2(True)


def _delete_named_feature(adapter, name: str) -> None:
    # Tree walk rather than ``FeatureByName``: that member is declared on
    # IPartDoc/IAssemblyDoc/IDrawingDoc, not IModelDoc2, and the walk
    # early-binds IFeature per node so no document rebind is needed.
    _delete_feature(adapter, _feature_by_name(adapter, name))


def _parallel_plane(
    adapter,
    name: str,
    base: str,
    offset_mm: float,
    expect_normal: tuple[float, float, float],
    expect_origin_mm: tuple[float, float, float],
) -> str:
    """Reference plane parallel to ``base``, VERIFIED against its transform.

    ``InsertRefPlane``'s ``OptionFlip`` decides which side of the base plane
    the offset lands on; the flag that means "the negative side" is not
    contractual, so the resolved origin is read back and the other flag tried
    before giving up.  Only the plane NORMAL is asserted here -- SolidWorks
    picks a derived plane's in-plane axes itself, and those axes are what the
    helix start angles are written against, so they are checked where they
    actually bite: on the sketch transform in :func:`_sketch_on`.
    """
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    manager = _early_bound(model.FeatureManager, "IFeatureManager")
    attempts = []
    for flip in (offset_mm < 0.0, offset_mm >= 0.0):
        model.ClearSelection2(True)
        if not extension.SelectByID2(
            base, "PLANE", 0, 0, 0, False, 0, null_callout(), 0
        ):
            raise RuntimeError(f"{name}: cannot select base plane {base!r}")
        ref_plane = manager.InsertRefPlane(
            8 | (256 if flip else 0), abs(offset_mm) / 1000.0, 0, 0, 0, 0
        )
        model.ClearSelection2(True)
        if ref_plane is None:
            raise RuntimeError(f"{name}: InsertRefPlane off {base!r} returned None")
        cols, origin = _plane_frame(ref_plane)
        if max(abs(a - b) for a, b in zip(cols[2], expect_normal)) > _FRAME_TOL:
            raise RuntimeError(
                f"{name}: plane off {base!r} resolved with normal {cols[2]}, "
                f"expected {expect_normal}"
            )
        if max(abs(a - b) for a, b in zip(origin, expect_origin_mm)) <= 1e-6:
            return name_last_feature(adapter, name)
        attempts.append((flip, origin))
        _delete_feature(adapter, _last_feature(adapter))
    raise RuntimeError(
        f"{name}: no InsertRefPlane flip put the plane at {expect_origin_mm} mm "
        f"(tried {attempts})"
    )


async def _sketch_on(
    adapter,
    plane: str,
    label: str,
    expect_frame: tuple,
    expect_origin_mm: tuple[float, float, float],
) -> None:
    """Open a sketch and assert the plane it actually landed on.

    ``create_sketch`` falls back to Top/Front/Right when a named plane fails
    to select, which would silently rebuild the spring around the wrong axis;
    the sketch transform is the cheapest decisive check.

    ``ModelToSketchTransform`` maps model points to sketch space, so its
    translation is ``-frame * plane_origin`` -- for the vendor's own sketches
    on planes parallel to Right at ``x0`` that is ``(0, 0, -x0)``, in the
    sketch's own (u, v, normal) slots, not ``(-x0, 0, 0)``.
    """
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    sketch = adapter.currentSketch or model.GetActiveSketch2()
    if sketch is None:
        raise RuntimeError(f"{label}: no active sketch after create_sketch")
    xform = _early_bound(
        _early_bound(sketch, "ISketch").ModelToSketchTransform, "IMathTransform"
    )
    arr = [float(v) for v in (xform.ArrayData or ())]
    if len(arr) != 16:
        raise RuntimeError(
            f"{label}: ModelToSketchTransform gave {len(arr)} doubles, expected 16"
        )
    cols = (tuple(arr[0:3]), tuple(arr[3:6]), tuple(arr[6:9]))
    translation = (arr[9] * 1000.0, arr[10] * 1000.0, arr[11] * 1000.0)
    want_t = tuple(
        -sum(expect_origin_mm[i] * expect_frame[i][k] for i in range(3))
        for k in range(3)
    )
    if _frame_dev(cols, expect_frame) > _FRAME_TOL:
        raise RuntimeError(
            f"{label}: sketch opened on a plane oriented {cols}, "
            f"expected {expect_frame}"
        )
    if max(abs(a - b) for a, b in zip(translation, want_t)) > 1e-6:
        raise RuntimeError(
            f"{label}: sketch opened at offset {translation} mm, expected {want_t}"
        )


def _circle(adapter, u_mm: float, v_mm: float, radius_mm: float, label: str) -> None:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.SketchManager, "ISketchManager")
    with no_sketch_inference(adapter):
        circle = manager.CreateCircleByRadius(
            u_mm / 1000.0, v_mm / 1000.0, 0.0, radius_mm / 1000.0
        )
        if circle is None:
            raise RuntimeError(f"{label}: CreateCircleByRadius failed")


def _helix(
    adapter,
    *,
    rise_mm: float,
    turns: float,
    clockwise: bool,
    reverse: bool,
    start_angle_deg: float,
    feature_name: str,
) -> str:
    """``InsertHelix`` on the ACTIVE sketch (it consumes it), height+revolution
    mode exactly as the vendor defined theirs."""
    # Declared on IModelDoc2 and typed VOID: the helix is claimed from the
    # tree, never from a return value.
    _early_bound(adapter.currentModel, "IModelDoc2").InsertHelix(
        reverse,
        clockwise,
        False,
        False,  # Tapered / Outward
        SW_HELIX_HEIGHT_AND_REVOLUTION,
        rise_mm / 1000.0,
        (rise_mm / turns) / 1000.0,
        turns,
        0.0,  # TaperAngle
        math.radians(start_angle_deg),
    )
    return name_last_feature(adapter, feature_name)


def _sketch_arc_mm(adapter, feature_name: str) -> float:
    """Arc length of the one segment of a named sketch, read from the model.

    ``IFeature::GetSpecificFeature2`` on a sketch feature hands back the
    ``ISketch``; ``ISketch::GetSketchSegments`` then gives the segments and
    ``ISketchSegment::GetLength`` their length in metres.  Read through the
    tree, not through the creation return, so it reflects what the rebuilt
    model actually holds.
    """
    feat = _early_bound(_feature_by_name(adapter, feature_name), "IFeature")
    sketch = feat.GetSpecificFeature2()
    if sketch is None:
        raise RuntimeError(f"{feature_name}: no ISketch behind the sketch feature")
    segments = list(_early_bound(sketch, "ISketch").GetSketchSegments() or ())
    if len(segments) != 1:
        raise RuntimeError(
            f"{feature_name}: the rebuilt sketch holds {len(segments)} "
            f"segments, expected 1"
        )
    return float(_early_bound(segments[0], "ISketchSegment").GetLength()) * 1000.0


def _transition_sketch(
    adapter,
    ctrl_mm: tuple[tuple[float, float, float], ...],
    feature_name: str,
) -> str:
    """3D sketch holding one transition, authored from the vendor B-curve.

    ``ISketchManager::CreateSplineParamData`` + ``CreateSplinesByEqnParams2``
    take the control points and knot vector directly, so the curve is the
    vendor's curve rather than a fit through sampled points
    (``CreateSpline2``/``CreateSpline3`` would only interpolate, and
    ``CreateSplineByEqnParams`` is documented 2D-only).

    The call shape is the one proven live on the sibling 9432K31 replica: a
    3D sketch is closed by calling ``Insert3DSketch`` a SECOND time (not
    ``InsertSketch``), and this family writes straight to the database
    (documented: it ignores ``AddToDB``/``DisplayWhenAdded``), so the model
    is force-rebuilt before the curve is read back.  The realised segment is
    then found through the named sketch rather than through the creation
    return, and its arc length asserted against the analytic length of the
    same control points.
    """
    from solidworks_mcp.adapters.com_variant import double_array

    expect_mm = _bezier_length(ctrl_mm)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.SketchManager, "ISketchManager")
    manager.Insert3DSketch(True)
    data = _early_bound(manager.CreateSplineParamData(), "ISplineParamData")
    data.Dimension = 3
    data.Order = TRANSITION_ORDER
    data.Periodic = 0
    data.ControlPointsCount = len(ctrl_mm)
    flat = [c / 1000.0 for point in ctrl_mm for c in point]
    if not data.SetControlPoints(double_array(flat)):
        raise RuntimeError(f"{feature_name}: SetControlPoints rejected {ctrl_mm}")
    if not data.SetKnotPoints(double_array(list(TRANSITION_KNOTS))):
        raise RuntimeError(f"{feature_name}: SetKnotPoints rejected {TRANSITION_KNOTS}")
    created = manager.CreateSplinesByEqnParams2(data)
    segments = list(created) if isinstance(created, (list, tuple)) else [created]
    if not created or segments[0] is None:
        raise RuntimeError(
            f"{feature_name}: CreateSplinesByEqnParams2 created no segment "
            f"from the vendor cubic"
        )
    if len(segments) != 1:
        raise RuntimeError(
            f"{feature_name}: CreateSplinesByEqnParams2 made {len(segments)} "
            f"segments, expected 1 cubic Bezier"
        )
    model.ClearSelection2(True)
    manager.Insert3DSketch(True)
    model.ForceRebuild3(True)
    adapter.currentSketch = None
    adapter.currentSketchManager = None
    name_last_feature(adapter, feature_name)
    got = _sketch_arc_mm(adapter, feature_name)
    if abs(got - expect_mm) > TRANSITION_ARC_TOL_MM:
        raise RuntimeError(
            f"{feature_name}: spline arc {got:.6f} mm, control points give "
            f"{expect_mm:.6f} mm (tol {TRANSITION_ARC_TOL_MM})"
        )
    _telemetry.info(f"{feature_name}: spline arc {got:.6f} mm matches the vendor")
    return feature_name


def _composite_curve(adapter, members: tuple[str, ...], feature_name: str) -> str:
    """Vendor CompCurve: every member selected under mark 1, then
    ``IModelDoc2::InsertCompositeCurve``.  One member = one swept face, which
    is what pins the vendor's 2-face / 3-face lateral split."""
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    for index, member in enumerate(members):
        if not _select_named_feature(adapter, member, 1, index > 0):
            raise RuntimeError(f"{feature_name}: cannot select member {member!r}")
    if not model.InsertCompositeCurve():
        raise RuntimeError(f"{feature_name}: InsertCompositeCurve failed")
    model.ClearSelection2(True)
    return name_last_feature(adapter, feature_name)


def _boss_sweep(
    adapter,
    profile: str,
    path: str,
    feature_name: str,
    *,
    align_end_faces: bool,
    end_tangency: int,
) -> str:
    """The vendor's Sweep option set, verbatim, via ``InsertProtrusionSwept4``."""
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.FeatureManager, "IFeatureManager")
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, profile, 1, False):
        raise RuntimeError(
            f"{feature_name}: cannot select profile {profile!r} (mark 1)"
        )
    if not _select_named_feature(adapter, path, 4, True):
        raise RuntimeError(f"{feature_name}: cannot select path {path!r} (mark 4)")
    with _telemetry.span("feature.boss_sweep", label=feature_name):
        swept = manager.InsertProtrusionSwept4(
            False,  # Propagate (vendor TangentPropagation)
            align_end_faces,  # Alignment (vendor AlignWithEndFaces)
            0,  # TwistCtrlOption: swTwistControlFollowPath
            False,  # KeepTangency (vendor MaintainTangency)
            False,  # BAdvancedSmoothing
            0,  # StartMatchingType (vendor StartTangencyType)
            end_tangency,  # EndMatchingType (vendor EndTangencyType)
            False,  # IsThinBody
            0.0,
            0.0,
            0,  # thin wall type
            10,  # PathAlign: swMinimumTwist (vendor PathAlignmentType)
            False,  # Merge -- every vendor sweep is its own body
            False,  # UseFeatScope
            True,  # UseAutoSelect
            0.0,  # TwistAngle
            True,  # BMergeSmoothFaces (vendor MergeSmoothFaces)
            False,  # CircularProfile (vendor: sketched profile)
            0.0,
            -1,  # Direction (vendor read-back)
        )
    model.ClearSelection2(True)
    if swept is None:
        raise RuntimeError(f"{feature_name}: InsertProtrusionSwept4 returned None")
    return name_last_feature(adapter, feature_name)


def _spring_axis(adapter, name: str) -> str:
    """Reference axis on Front x Top = the global X axis (the pattern
    direction; the vendor used an X construction line in their layout
    sketch)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    model.ClearSelection2(True)
    for index, plane in enumerate(("Front Plane", "Top Plane")):
        if not extension.SelectByID2(
            plane, "PLANE", 0, 0, 0, index > 0, 0, null_callout(), 0
        ):
            raise RuntimeError(f"{name}: cannot select {plane!r}")
    if not model.InsertAxis2(True):
        raise RuntimeError(f"{name}: InsertAxis2 rejected Front x Top")
    model.ClearSelection2(True)
    # The tree, not the selection: a "PLANE" pick leaves a plane OBJECT in the
    # selection (it does not answer IFeature), so the axis is claimed as the
    # feature the insert appended.
    created = _early_bound(_last_feature(adapter), "IFeature")
    kind = str(created.GetTypeName2())
    if kind != "RefAxis":
        raise RuntimeError(f"{name}: InsertAxis2 made a {kind!r}")
    return name_last_feature(adapter, name)


def _overall_box_mm(adapter) -> list[float]:
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for body in bodies(adapter):
        box = [
            float(v) * 1000.0 for v in (_early_bound(body, "IBody2").GetBodyBox() or [])
        ]
        if len(box) != 6:
            raise RuntimeError("GetBodyBox did not return 6 values")
        for axis in range(3):
            lo[axis] = min(lo[axis], box[axis])
            hi[axis] = max(hi[axis], box[axis + 3])
    return [*lo, *hi]


def _check_box(adapter, label: str, expect: list[float], count: int) -> None:
    found = bodies(adapter)
    if len(found) != count:
        raise RuntimeError(f"{label}: {len(found)} bodies, expected {count}")
    got = _overall_box_mm(adapter)
    worst = max(abs(a - b) for a, b in zip(got, expect))
    if worst > _BOX_SLACK_MM:
        raise RuntimeError(
            f"{label}: body box {[round(v, 4) for v in got]} vs expected "
            f"{[round(v, 4) for v in expect]} (worst {worst:.4f} mm)"
        )


def _coil_pattern(
    adapter, seed: str, axis: str, spacing_mm: float, feature_name: str
) -> str:
    """Vendor LPattern1: 4 instances (seed included) at the segment rise.

    The pattern's marching sense along a reference axis is not contractual, so
    it is verified from the body box (a +X pattern must put material past the
    origin) and re-run flipped if it went the wrong way."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    manager = _early_bound(model.FeatureManager, "IFeatureManager")
    for flip in (False, True):
        model.ClearSelection2(True)
        if not extension.SelectByID2(
            axis, "AXIS", 0, 0, 0, False, 1, null_callout(), 0
        ) and not _select_named_feature(adapter, axis, 1, False):
            raise RuntimeError(f"{feature_name}: cannot select axis {axis!r} (mark 1)")
        if not _select_named_feature(adapter, seed, 4, True):
            raise RuntimeError(f"{feature_name}: cannot select seed {seed!r} (mark 4)")
        pattern = manager.FeatureLinearPattern5(
            geom.COIL_SEGMENTS,  # Num1 (includes the seed)
            spacing_mm / 1000.0,  # Spacing1
            1,
            0.0,
            flip,  # FlipDir1
            False,
            "",
            "",
            False,  # GeometryPattern
            False,
            False,
            False,
            True,  # CtrlByNum1
            True,
            False,
            False,
            False,
            False,
            0.0,
            0.0,
            False,
            False,
        )
        model.ClearSelection2(True)
        # A rejected pattern can come back as None with the tree untouched;
        # renaming blind would rename Sweep2 and the retry would delete it.
        last = _early_bound(_last_feature(adapter), "IFeature")
        kind = str(last.GetTypeName2())
        if pattern is None and kind != "LPattern":
            raise RuntimeError(
                f"{feature_name}: FeatureLinearPattern5 made no pattern "
                f"(tree still ends in {kind!r})"
            )
        name_last_feature(adapter, feature_name)
        if _overall_box_mm(adapter)[3] > 0.0:
            return feature_name
        _telemetry.warn(f"{feature_name}: pattern marched -X, retrying flipped")
        _delete_named_feature(adapter, feature_name)
    raise RuntimeError(f"{feature_name}: neither pattern sense marched +X")


def _combine_coil(adapter, length_mm: float, feature_name: str) -> None:
    """Vendor Combine1: ADD every body EXCEPT the +X loop sweep (5 of 6).

    The +X loop is the only body that lies entirely outboard of the coil's
    last turn, so it is identified geometrically rather than by feature name.
    """
    import pythoncom
    from win32com.client import VARIANT

    threshold = geom.coil_end_x_mm(length_mm) - 2.0
    combine, separate = [], []
    for body in bodies(adapter):
        box = [
            float(v) * 1000.0 for v in (_early_bound(body, "IBody2").GetBodyBox() or [])
        ]
        (separate if box[0] > threshold else combine).append(body)
    if len(combine) != 5 or len(separate) != 1:
        raise RuntimeError(
            f"{feature_name}: expected 5 bodies to combine and 1 (+X loop) to "
            f"stay separate, got {len(combine)}/{len(separate)}"
        )
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.FeatureManager, "IFeatureManager")
    model.ClearSelection2(True)
    combined = manager.InsertCombineFeature(
        SW_BODY_ADD,
        None,
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, combine),
    )
    if combined is None:
        raise RuntimeError(f"{feature_name}: InsertCombineFeature (ADD) failed")
    name_last_feature(adapter, feature_name)


# ------------------------------------------------------------------ build
async def build_1330K524(adapter, truth=None, *, length_mm: float | None = None):
    """Re-author the vendor's 1330K524 tree in the EMPTY active part.

    Args:
        adapter: Connected adapter whose ``currentModel`` is an empty part.
            The document is neither created, saved nor closed here.
        truth: Harvest dict, accepted for the fleet builder signature and
            unused -- the recipe is native, not a dump replay.
        length_mm: Catalogue INSIDE-loop length in mm; ``None`` (default)
            rebuilds the vendor's free geometry exactly, in its own frame.

    Raises:
        ValueError: If ``length_mm`` is outside the buildable range.
        RuntimeError: If any feature, frame read-back or geometry check fails.
    """
    del truth  # native recipe: the harvest is gate ground truth, not input
    length = geom.validate_length_mm(length_mm)
    radius = geom.COIL_MEAN_RADIUS_MM
    wire_r = geom.WIRE_RADIUS_MM
    coil_x = geom.coil_start_x_mm(length)  # -116.7003 free
    coil_end_x = geom.coil_end_x_mm(length)  # +115.9002 free
    segment_rise = geom.coil_segment_rise_mm(length)
    eye_neg, eye_pos = geom.end_centers_mm(length)
    loop_z = geom.LOOP_HALF_RISE_MM
    envelope = radius + wire_r  # 6.35 -- tube outer radius

    loop_arc = _helix_arc_mm(radius, geom.LOOP_TURNS, geom.LOOP_RISE_MM)
    coil_arc = _helix_arc_mm(radius, geom.COIL_SEGMENT_TURNS, segment_rise)
    half_arc = _helix_arc_mm(radius, HALF_TURN_TURNS, wire_r)
    neg_ctrl = _transition_ctrl(length, positive_x=False)
    pos_ctrl = _transition_ctrl(length, positive_x=True)
    neg_arc = _bezier_length(neg_ctrl)
    pos_arc = _bezier_length(pos_ctrl)
    if length_mm is None:
        # The B-curve control points and the vendor's measured spline lengths
        # are two independent native reads; they must agree at free length.
        for label, got, want in (
            ("TransitionNeg", neg_arc, TRANSITION_ARC_NEG_MM),
            ("TransitionPos", pos_arc, TRANSITION_ARC_POS_MM),
        ):
            if abs(got - want) > TRANSITION_ARC_TOL_MM:
                raise RuntimeError(
                    f"{label}: control points give arc {got:.9f} mm but the "
                    f"vendor spline measures {want:.6f} mm"
                )
    _telemetry.info(
        f"{PART_NO}: L {length} mm, coil {coil_x:.4f}..{coil_end_x:.4f}, "
        f"pitch {geom.coil_pitch_mm(length):.9f}, transitions "
        f"{neg_arc:.6f}/{pos_arc:.6f} mm"
    )

    with no_sketch_inference(adapter):
        # --- base planes (vendor Plane5 / Plane1 / Plane3) ----------------
        loop_plane = _parallel_plane(
            adapter,
            "LoopBasePlane",
            "Front Plane",
            -loop_z,
            _NORMAL_FRONT,
            (0.0, 0.0, -loop_z),
        )
        coil_plane = _parallel_plane(
            adapter,
            "CoilStartPlane",
            "Right Plane",
            coil_x,
            _NORMAL_RIGHT,
            (coil_x, 0.0, 0.0),
        )
        half_plane = _parallel_plane(
            adapter,
            "HalfTurnPlane",
            "Right Plane",
            -coil_x,
            _NORMAL_RIGHT,
            (-coil_x, 0.0, 0.0),
        )

        # --- coil helix: one patterned segment (vendor Helix/Spiral1) -----
        # On a || Right plane the sketch axes are (u, v) = (-z, y), so the
        # 180 deg start angle lands the wire at (coil_x, 0, +R).
        await _sketch_on(
            adapter, coil_plane, "coil helix base", _SKETCH_RIGHT, (coil_x, 0.0, 0.0)
        )
        _circle(adapter, 0.0, 0.0, radius, "coil helix base")
        coil_helix = _helix(
            adapter,
            rise_mm=segment_rise,
            turns=geom.COIL_SEGMENT_TURNS,
            clockwise=False,
            reverse=False,
            start_angle_deg=COIL_START_ANGLE_DEG,
            feature_name="CoilHelix",
        )

        # --- -X double loop (vendor Helix/Spiral3) ------------------------
        # || Front plane: sketch axes are model (x, y); start angle 0 puts the
        # wire tip at (coil_x, 0, -loop_z), and 1.75 cw turns end at +90 deg.
        await _sketch_on(
            adapter, loop_plane, "-X loop base", _SKETCH_FRONT, (0.0, 0.0, -loop_z)
        )
        _circle(adapter, eye_neg[0], 0.0, radius, "-X loop base")
        loop_neg = _helix(
            adapter,
            rise_mm=geom.LOOP_RISE_MM,
            turns=geom.LOOP_TURNS,
            clockwise=True,
            reverse=False,
            start_angle_deg=LOOP_NEG_START_ANGLE_DEG,
            feature_name="LoopHelixNeg",
        )
        transition_neg = _transition_sketch(adapter, neg_ctrl, "TransitionNeg")
        path_neg = _composite_curve(adapter, (loop_neg, transition_neg), "PathLoopNeg")

        # --- +X end: half-turn, transition, loop (vendor Helix2/4) --------
        await _sketch_on(
            adapter, half_plane, "+X half-turn base", _SKETCH_RIGHT, (-coil_x, 0.0, 0.0)
        )
        _circle(adapter, 0.0, 0.0, radius, "+X half-turn base")
        half_turn = _helix(
            adapter,
            rise_mm=wire_r,
            turns=HALF_TURN_TURNS,
            clockwise=True,
            reverse=True,  # advances -X, back onto the coil's last turn
            start_angle_deg=HALF_TURN_START_ANGLE_DEG,
            feature_name="HalfTurnPos",
        )
        transition_pos = _transition_sketch(adapter, pos_ctrl, "TransitionPos")
        await _sketch_on(
            adapter, loop_plane, "+X loop base", _SKETCH_FRONT, (0.0, 0.0, -loop_z)
        )
        _circle(adapter, eye_pos[0], 0.0, radius, "+X loop base")
        loop_pos = _helix(
            adapter,
            rise_mm=geom.LOOP_RISE_MM,
            turns=geom.LOOP_TURNS,
            clockwise=True,
            reverse=False,
            start_angle_deg=LOOP_POS_START_ANGLE_DEG,
            feature_name="LoopHelixPos",
        )
        path_pos = _composite_curve(
            adapter, (half_turn, transition_pos, loop_pos), "PathLoopPos"
        )

        # --- wire sweeps --------------------------------------------------
        # Every profile is the wire section on the Top plane (y = 0), where
        # (u, v) = (x, -z): vendor Sketch28/32 at the coil start, Sketch38 at
        # the +X loop's wire tip.
        await _sketch_on(
            adapter, "Top", "-X loop profile", _SKETCH_TOP, (0.0, 0.0, 0.0)
        )
        _circle(adapter, coil_x, -radius, wire_r, "-X loop profile")
        check("exit_sketch -X loop profile", await adapter.exit_sketch())
        name_last_feature(adapter, "ProfileLoopNeg")
        _boss_sweep(
            adapter,
            "ProfileLoopNeg",
            path_neg,
            "LoopNeg",
            align_end_faces=False,
            end_tangency=1,
        )
        await _check_volume(adapter, "-X loop sweep", loop_arc + neg_arc)
        _check_box(
            adapter,
            "-X loop sweep",
            [
                eye_neg[0] - envelope,
                -envelope,
                -(loop_z + wire_r),
                coil_x + wire_r,
                envelope,
                envelope,
            ],
            1,
        )

        # The coil seed shares that same wire section (vendor Sketch32): the
        # two sweeps meet on a coincident disc, which is why the vendor's
        # bodies touch without merging.
        await _sketch_on(adapter, "Top", "coil profile", _SKETCH_TOP, (0.0, 0.0, 0.0))
        _circle(adapter, coil_x, -radius, wire_r, "coil profile")
        check("exit_sketch coil profile", await adapter.exit_sketch())
        name_last_feature(adapter, "ProfileCoil")
        _boss_sweep(
            adapter,
            "ProfileCoil",
            coil_helix,
            "CoilSegment",
            align_end_faces=False,
            end_tangency=0,
        )
        wire_so_far = loop_arc + neg_arc + coil_arc
        await _check_volume(adapter, "coil seed sweep", wire_so_far)
        _check_box(
            adapter,
            "coil seed sweep",
            [
                eye_neg[0] - envelope,
                -envelope,
                -envelope,
                coil_x + segment_rise + wire_r,
                envelope,
                envelope,
            ],
            2,
        )

        # --- 4 coil segments = 128 turns (vendor LPattern1) ---------------
        axis = _spring_axis(adapter, "SpringAxis")
        _coil_pattern(adapter, "CoilSegment", axis, segment_rise, "CoilPattern")
        wire_so_far = loop_arc + neg_arc + geom.COIL_SEGMENTS * coil_arc
        await _check_volume(adapter, "coil pattern", wire_so_far)
        _check_box(
            adapter,
            "coil pattern",
            [
                eye_neg[0] - envelope,
                -envelope,
                -envelope,
                coil_end_x + wire_r,
                envelope,
                envelope,
            ],
            1 + geom.COIL_SEGMENTS,
        )

        # --- +X end sweep (vendor Sweep3, left UNCOMBINED) ----------------
        # Profile sits at the +X loop's wire tip, the far end of PathLoopPos.
        await _sketch_on(
            adapter, "Top", "+X loop profile", _SKETCH_TOP, (0.0, 0.0, 0.0)
        )
        _circle(adapter, -coil_x, -loop_z, wire_r, "+X loop profile")
        check("exit_sketch +X loop profile", await adapter.exit_sketch())
        name_last_feature(adapter, "ProfileLoopPos")
        _boss_sweep(
            adapter,
            "ProfileLoopPos",
            path_pos,
            "LoopPos",
            align_end_faces=True,
            end_tangency=0,
        )
        wire_total = wire_so_far + half_arc + pos_arc + loop_arc
        await _check_volume(adapter, "+X loop sweep", wire_total)
        _check_box(
            adapter,
            "+X loop sweep",
            [
                eye_neg[0] - envelope,
                -envelope,
                -envelope,
                eye_pos[0] + envelope,
                envelope,
                envelope,
            ],
            2 + geom.COIL_SEGMENTS,
        )

        # --- vendor Combine1: everything but the +X loop ------------------
        _combine_coil(adapter, length, "Combine1")
        volume = await _check_volume(adapter, "combined spring", wire_total)
        _check_box(
            adapter,
            "combined spring",
            [
                eye_neg[0] - envelope,
                -envelope,
                -envelope,
                eye_pos[0] + envelope,
                envelope,
                envelope,
            ],
            2,
        )
        if length_mm is None:
            # End to end against the vendor's own mass properties.  Loose on
            # purpose (1%): the fleet gate compares face areas, volume and COM
            # to 0.02% and owns the verdict -- this only makes a structurally
            # wrong rebuild fail here, with a readable message.
            deviation = abs(volume - VENDOR_FREE_VOLUME_MM3)
            if deviation > VENDOR_FREE_VOLUME_TOL * VENDOR_FREE_VOLUME_MM3:
                raise RuntimeError(
                    f"free-length volume {volume:.4f} mm3 vs vendor "
                    f"{VENDOR_FREE_VOLUME_MM3:.4f} mm3 (off by {deviation:.4f})"
                )

    _telemetry.success(
        f"{PART_NO}: 2 bodies, wire path {wire_total:.4f} mm, eyes at "
        f"{eye_neg[0]:.4f} / {eye_pos[0]:.4f} mm"
    )
    return {
        "part_no": PART_NO,
        "length_mm": length,
        "wire_path_mm": wire_total,
        "volume_mm3": volume,
        "end_centers_mm": (eye_neg, eye_pos),
        "end_tip_points_mm": geom.end_tip_points_mm(length),
        "coil_pitch_mm": geom.coil_pitch_mm(length),
    }


if __name__ == "__main__":
    raise SystemExit(replica_main(PART_NO, build_1330K524))
