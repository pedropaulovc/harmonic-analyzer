"""Native circular sweeps for purchased cartridge holes and formed lock wire.

Uses the existing stock-spring CreateSplinesByEqnParams2/CreateFeature idiom.
Input is explicit piecewise cubic Bezier geometry in model millimetres, not an
interpolating spline that may wander outside the receiving channel.
"""

from __future__ import annotations

import math

from _com import _early_bound
from _feature_tree import name_last_feature


def line_bezier(a, b):
    return (a, tuple((2 * x + y) / 3 for x, y in zip(a, b)),
            tuple((x + 2 * y) / 3 for x, y in zip(a, b)), b)


def bezier_spline_parameters(segments):
    """Preserve the cubic route in the SDK's required [0, 1] knot domain.

    Each interior knot has multiplicity three, so no fitting or smoothing can
    move a head passage or a bend outside its certified Bezier control hull.
    Positive collinear endpoint handles set adjacent parameter-span ratios.
    This makes the first derivative continuous without moving any control.
    Shared endpoints must have a common forward tangent: a circular sweep
    cannot supply an unspecified physical bend at a sharp cubic join.
    """
    if not segments:
        raise ValueError("a spline needs nonempty Bezier segments")
    controls = list(segments[0])
    spans = [1.0]
    for segment in segments[1:]:
        if any(abs(a - b) > 1e-9 for a, b in zip(controls[-1], segment[0])):
            raise ValueError("disconnected Bezier segments")
        incoming = tuple(b - a for a, b in zip(controls[-2], controls[-1]))
        outgoing = tuple(b - a for a, b in zip(segment[0], segment[1]))
        incoming_length, outgoing_length = math.hypot(*incoming), math.hypot(*outgoing)
        if not all(math.isfinite(length) and length > 0
                   for length in (incoming_length, outgoing_length)):
            raise ValueError("circular sweep needs finite nonzero join tangents")
        incoming = tuple(value / incoming_length for value in incoming)
        outgoing = tuple(value / outgoing_length for value in outgoing)
        cross = (
            incoming[1] * outgoing[2] - incoming[2] * outgoing[1],
            incoming[2] * outgoing[0] - incoming[0] * outgoing[2],
            incoming[0] * outgoing[1] - incoming[1] * outgoing[0],
        )
        if (sum(a * b for a, b in zip(incoming, outgoing)) <= 0
                or math.hypot(*cross) > 1e-9):
            raise ValueError("circular sweep needs tangent-continuous Bezier segments")
        # A cubic's endpoint derivative is 3 * handle / parameter_span.
        # Match that derivative across this join, then normalize all spans.
        span = spans[-1] * (outgoing_length / incoming_length)
        if not math.isfinite(span) or span <= 0:
            raise ValueError("circular sweep needs finite positive knot spans")
        spans.append(span)
        controls.extend(segment[1:])
    total = sum(spans)
    if not math.isfinite(total):
        raise ValueError("circular sweep knot spans overflow their parameter domain")
    knots = [0.0] * 4
    cumulative = 0.0
    for span in spans[:-1]:
        cumulative += span
        knot = cumulative / total
        if not knots[-1] < knot < 1.0:
            raise ValueError("circular sweep knot span collapses in the SDK parameter domain")
        knots.extend([knot] * 3)
    knots.extend([1.0] * 4)
    return controls, knots


def circular_sweep(adapter, segments, diameter, name, *, cut=False):
    import pythoncom
    from win32com.client import VARIANT
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    if not segments or diameter <= 0:
        raise ValueError("a circular sweep needs a path and positive diameter")
    controls, knots = bezier_spline_parameters(segments)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.SketchManager, "ISketchManager")
    model.ClearSelection2(True)
    manager.Insert3DSketch(True)
    data = _early_bound(manager.CreateSplineParamData(), "ISplineParamData")
    data.Dimension = 3
    data.Order = 4
    data.Periodic = 0
    data.ControlPointsCount = len(controls)
    points = [coordinate / 1000 for point in controls for coordinate in point]
    if not data.SetControlPoints(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, points)):
        raise RuntimeError(f"{name}: spline control points rejected")
    if not data.SetKnotPoints(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, knots)):
        raise RuntimeError(f"{name}: spline knots rejected")
    created = manager.CreateSplinesByEqnParams2(data)
    if created is None or (isinstance(created, (list, tuple)) and not created):
        raise RuntimeError(f"{name}: spline creation failed")
    manager.Insert3DSketch(True)
    name_last_feature(adapter, f"{name}Path")
    model.ForceRebuild3(True)
    fm = _early_bound(model.FeatureManager, "IFeatureManager")
    # swFeatureNameID_e.swFmSweep / swFmSweepCut; existing stock-spring constants.
    sweep = _early_bound(fm.CreateDefinition(18 if cut else 17), "ISweepFeatureData")
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, f"{name}Path", 4, False):
        raise RuntimeError(f"{name}: cannot select sweep path")
    sweep.TangentPropagation = False
    sweep.AlignWithEndFaces = False
    sweep.TwistControlType = 0
    sweep.MaintainTangency = False
    sweep.AdvancedSmoothing = False
    sweep.StartTangencyType = 0
    sweep.EndTangencyType = 0
    sweep.PathAlignmentType = 10  # swTangencyType_e.swMinimumTwist; 3D paths
    sweep.Direction = -1
    sweep.ThinFeature = False
    sweep.Merge = False
    sweep.FeatureScope = True
    sweep.AutoSelect = True
    sweep.MergeSmoothFaces = True
    sweep.CircularProfile = True
    sweep.CircularProfileDiameter = diameter / 1000
    feature = fm.CreateFeature(sweep)
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError(f"{name}: circular sweep failed")
    name_last_feature(adapter, name)
