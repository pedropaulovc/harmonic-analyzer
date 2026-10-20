"""Native circular sweeps for purchased cartridge holes and formed lock wire.

Uses the existing stock-spring CreateSplinesByEqnParams2/CreateFeature idiom.
Input is explicit piecewise cubic Bezier geometry in model millimetres, not an
interpolating spline that may wander outside the receiving channel.
"""

from __future__ import annotations

from _com import _early_bound
from _feature_tree import name_last_feature


def line_bezier(a, b):
    return (a, tuple((2 * x + y) / 3 for x, y in zip(a, b)),
            tuple((x + 2 * y) / 3 for x, y in zip(a, b)), b)


def circular_sweep(adapter, segments, diameter, name, *, cut=False):
    import pythoncom
    from win32com.client import VARIANT
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    if not segments or diameter <= 0:
        raise ValueError("a circular sweep needs a path and positive diameter")
    controls = list(segments[0])
    for segment in segments[1:]:
        if any(abs(a - b) > 1e-9 for a, b in zip(controls[-1], segment[0])):
            raise ValueError(f"{name}: disconnected Bezier segments")
        controls.extend(segment[1:])
    knots = [0.0] * 4
    for i in range(1, len(segments)):
        knots.extend([float(i)] * 3)
    knots.extend([float(len(segments))] * 4)
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
    sweep.PathAlignmentType = 10
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
