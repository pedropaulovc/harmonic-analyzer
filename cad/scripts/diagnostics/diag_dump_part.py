r"""Diagnostic: dump a ``.SLDPRT``'s complete recipe to JSON -- the harvest half
of "edit in the GUI, re-author in the script".

:func:`_common.dump_dimensions` answers "which named dims drive THIS feature".
This answers the whole question for a part nobody scripted: what would a build
script have to call, in what order, with which numbers, to produce this file?
Three passes, all READ-ONLY (the document is never saved):

``tree``
    Every top-level feature in order -- name, ``GetTypeName2``, suppression,
    its display dimensions (value in mm *or* degrees, chosen from the
    dimension's own param type -- an angular dim read as mm silently becomes a
    plausible-looking length), and for a sketch every segment with its
    endpoints/centre/radius plus the sketch's ``ModelToSketchTransform`` (the
    only way to map sketch coordinates back to model space). Extrude / revolve
    / plane / fillet / chamfer feature data is decoded per type.

``refs``
    The reference topology the tree pass cannot see: each feature's direct
    parents, and -- via ``AccessSelections`` -- the entities behind a plane's
    constraints and an extrude's from/up-to end conditions, each identified by
    its owning feature and surface parameters. ``AccessSelections`` rolls the
    model back, so every access is released in a ``finally``; pass
    ``--no-refs`` to skip the pass entirely.

    A plane's own constraint references DO read back (named: ``Front Plane`` +
    ``YAxis`` for an angled plane, the tangent cylinder face for a tangent
    plane). An extrude's ``GetEndConditionReference`` /  ``GetFromEntity`` do
    NOT -- both returned an empty entity with ``ReferenceType`` -1/0 on 2026
    SP2.0 even for a feature whose end condition is demonstrably
    up-to-surface. Identify those from ``parents`` (an up-to plane appears
    there and nowhere else) cross-checked against the ``faces`` pass, which
    shows where the boss actually ends.

``faces``
    The as-built B-rep: every face with its surface parameters, area and box,
    plus the body box. This is the ground truth that turns a face-referenced
    end condition ("up to surface") into the number a script can assert.

Run (SolidWorks already open; the part may be open or closed)::

    uv run python cad\scripts\diagnostics\diag_dump_part.py ^
        cad\out\sldprt\cone-pivot-post-v2.SLDPRT dump.json [--no-refs] [--no-faces]

Cross-check the result against what the FeatureManager actually shows with
``diag_ui_feature_tree.py`` -- the tree is custom-drawn, so a screenshot is the
independent witness that no feature was missed.
"""

from __future__ import annotations

import inspect
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import _early_bound, _read_member, check, run_build  # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
FLAGS = {a for a in sys.argv[1:] if a.startswith("--")}
PART = Path(ARGS[0]) if ARGS else None
OUT = Path(ARGS[1]) if len(ARGS) > 1 else Path("part-dump.json")
WANT_REFS = "--no-refs" not in FLAGS
WANT_FACES = "--no-faces" not in FLAGS

# swSketchSegments_e
SEG_TYPES = {0: "line", 1: "arc", 2: "ellipse", 3: "spline", 4: "text", 5: "parabola"}
# swDimensionParamType_e -- 1 is angular, so its SystemValue is RADIANS
DIM_ANGULAR = 1
# swSelectType_e values seen as feature references
SELECT_TYPES = {1: "edge", 2: "face", 3: "vertex", 4: "datum-plane", 5: "datum-axis"}
# folder/administrative features that carry no recipe
SKIP_TYPES = {
    "CommentsFolder", "FavoriteFolder", "HistoryFolder", "SelectionSetFolder",
    "SensorFolder", "DocsFolder", "DetailCabinet", "SurfaceBodyFolder",
    "SolidBodyFolder", "EnvFolder", "InkMarkupFolder", "EqnFolder",
}


def _g(obj, name, default=None):
    """Read a COM accessor that pywin32 may expose as a method or a property.

    NEVER re-invoke the result: a pywin32 ``CDispatch`` is itself callable (its
    default DISPID), so calling a returned COM object as if it were an
    unresolved method raises and the value vanishes into the default -- the
    reason an earlier version of this probe reported every sketch as absent.

    Rejecting via bare ``callable(v)`` over-corrected: a *valid* ``CDispatch``
    result (``GetSpecificFeature2`` -> the sketch, ``GetSurface`` -> the
    surface) is itself callable and was discarded along with the failed
    accessors, which nulled every sketch/surface in the dump. Only a plain
    Python method/function -- what ``_read_member`` hands back when the
    zero-argument invocation was rejected -- is a failed accessor; a COM
    dispatch is harvested data.
    """
    try:
        v = _read_member(obj, name)
    except Exception:  # noqa: BLE001
        return default
    if v is None or inspect.ismethod(v) or inspect.isfunction(v):
        return default
    return v


def _mm(v):
    try:
        return round(float(v) * 1000.0, 6)
    except Exception:  # noqa: BLE001
        return None


def _deg(v):
    try:
        return round(math.degrees(float(v)), 6)
    except Exception:  # noqa: BLE001
        return None


def _pt(p):
    """An ``ISketchPoint`` as mm in SKETCH coordinates."""
    if p is None:
        return None
    p = _early_bound(p, "ISketchPoint")
    return {"x": _mm(_g(p, "X")), "y": _mm(_g(p, "Y")), "z": _mm(_g(p, "Z"))}


# --------------------------------------------------------------------------
# pass 1 -- the feature tree
# --------------------------------------------------------------------------
def _dimensions(feat):
    """Every display dimension of ``feat``, valued in its OWN unit.

    A sketch on a reference plane also enumerates that plane's angle/offset dim
    first (the owner-filter caveat in ``_common._display_dimensions``), so the
    owning feature is reported per row rather than assumed.
    """
    rows = []
    feat = _early_bound(
        feat, "IFeature"
    )
    disp = _read_member(feat, "GetFirstDisplayDimension")
    for _ in range(1000):
        if not disp:
            break
        disp = _early_bound(disp, "IDisplayDimension")
        try:
            idim = _early_bound(disp.GetDimension2(0), "IDimension")
        except Exception:  # noqa: BLE001
            break
        full = str(_g(idim, "FullName"))
        param_type = _g(idim, "GetType")
        raw = _g(idim, "SystemValue")
        row = {
            "full_name": full,
            "owner": full.split("@")[1] if "@" in full else "",
            "param_type": param_type,
        }
        if param_type == DIM_ANGULAR:
            row["value_deg"] = _deg(raw)
        else:
            row["value_mm"] = _mm(raw)
        for key, prop in (("display_type", "Type2"), ("diametric", "Diametric")):
            v = _g(disp, prop)
            if v is not None:
                row[key] = v
        rows.append(row)
        try:
            disp = feat.GetNextDisplayDimension(disp)
        except Exception:  # noqa: BLE001
            break
    return rows


def _sketch(feat):
    sk = _g(feat, "GetSpecificFeature2")
    if sk is None:
        return None
    sk = _early_bound(sk, "ISketch")
    info = {
        "constrained_status": _g(sk, "GetConstrainedStatus"),
        "is_3d": bool(_g(sk, "Is3D")),
        "segments": [],
        "points": [],
    }
    xform = _g(sk, "ModelToSketchTransform")
    if xform is not None:
        arr = _g(_early_bound(xform, "IMathTransform"), "ArrayData")
        if arr is not None:
            # 9 rotation + 3 translation (m) + scale; sketch = R^T . model + t
            info["model_to_sketch"] = [round(float(v), 9) for v in arr]

    for s in _g(sk, "GetSketchSegments") or []:
        s = _early_bound(s, "ISketchSegment")
        st = _g(s, "GetType")
        row = {
            "kind": SEG_TYPES.get(int(st) if st is not None else -1, f"type{st}"),
            "name": str(_g(s, "GetName")),
            "construction": bool(_g(s, "ConstructionGeometry")),
            "length_mm": _mm(_g(s, "GetLength")),
            "relations": _g(s, "GetRelationsCount"),
        }
        if row["kind"] == "line":
            ln = _early_bound(s, "ISketchLine")
            row["start"] = _pt(_g(ln, "GetStartPoint2"))
            row["end"] = _pt(_g(ln, "GetEndPoint2"))
        elif row["kind"] == "arc":
            ar = _early_bound(s, "ISketchArc")
            row["center"] = _pt(_g(ar, "GetCenterPoint2"))
            row["start"] = _pt(_g(ar, "GetStartPoint2"))
            row["end"] = _pt(_g(ar, "GetEndPoint2"))
            row["radius_mm"] = _mm(_g(ar, "GetRadius"))
            row["is_circle"] = bool(_g(ar, "IsCircle"))
        elif row["kind"] == "ellipse":
            el = _early_bound(s, "ISketchEllipse")
            for key, meth in (("center", "GetCenterPoint2"), ("start", "GetStartPoint2"),
                              ("end", "GetEndPoint2"), ("major", "GetMajorPoint2"),
                              ("minor", "GetMinorPoint2")):
                row[key] = _pt(_g(el, meth))
        info["segments"].append(row)

    for p in _g(sk, "GetSketchPoints2") or []:
        info["points"].append(_pt(p))
    return info


def _feature_data(feat, type_name):
    """Per-type parameter harvest for the feature kinds this repo authors."""
    try:
        raw = feat.GetDefinition()
    except Exception:  # noqa: BLE001
        return None
    if raw is None:
        return None
    out: dict = {}
    if type_name in ("Extrusion", "ICE", "BossThin", "CutThin"):  # boss AND cut extrudes
        d = _early_bound(raw, "IExtrudeFeatureData2")
        for key, meth, args in (
            ("depth1_mm", "GetDepth", (True,)),
            ("depth2_mm", "GetDepth", (False,)),
            ("end_cond1", "GetEndCondition", (True,)),   # swEndConditions_e
            ("end_cond2", "GetEndCondition", (False,)),
            ("draft1_deg", "GetDraftAngle", (True,)),
            ("draft2_deg", "GetDraftAngle", (False,)),
        ):
            try:
                v = getattr(d, meth)(*args)
            except Exception:  # noqa: BLE001
                continue
            out[key] = _mm(v) if key.endswith("_mm") else (
                _deg(v) if key.endswith("_deg") else v)
        for prop in ("ReverseDirection", "BothDirections", "Merge", "FlipSideToCut",
                     "NormalCut", "IsBaseExtrude", "IsBossFeature", "IsThinFeature",
                     "ThinWallType", "CapEnds", "FromType", "FromOffsetDistance"):
            v = _g(d, prop)
            if v is None:
                continue
            out[prop] = _mm(v) if prop == "FromOffsetDistance" else v
        for key, meth, args in (
                ("wall_forward_mm", "GetWallThickness", (True,)),
                ("wall_reverse_mm", "GetWallThickness", (False,)),
                ("cap_mm", "CapThickness", ())):
            try:
                v = getattr(d, meth)(*args) if args else _g(d, meth)
            except Exception as exc:  # noqa: BLE001
                _telemetry.debug(
                    f"feature dump: {type_name}.{meth} unavailable: {exc}")
                continue
            if v is not None:
                out[key] = _mm(v)
    elif type_name in ("RevolveBoss", "RevolveCut", "Revolve", "Revolution",
                       "RevCut"):
        d = _early_bound(raw, "IRevolveFeatureData2")
        for key, prop in (("angle_deg", "GetRevolutionAngle"),
                          ("reverse", "ReverseDirection"), ("type", "Type"),
                          ("is_boss", "IsBossFeature"), ("is_thin", "IsThinFeature"),
                          ("axis_type", "GetAxisType")):
            v = _g(d, prop)
            if v is None:
                continue
            out[key] = _deg(v) if key == "angle_deg" else v
    elif type_name == "RefPlane":
        d = _early_bound(raw, "IRefPlaneFeatureData")
        for key, prop in (("distance_mm", "Distance"), ("angle_deg", "Angle"),
                          ("reverse", "ReverseDirection"), ("type", "Type"),
                          ("type2", "Type2")):
            v = _g(d, prop)
            if v is None:
                continue
            out[key] = _mm(v) if key.endswith("_mm") else (
                _deg(v) if key.endswith("_deg") else v)
        # The constraint data says HOW the plane is defined; the resolved
        # transform says WHERE it landed -- the number a replica script needs
        # (this is how the vendor Split plane was located at the undercut
        # land bottom).
        rp = _g(feat, "GetSpecificFeature2")
        if rp is not None:
            xf = _g(_early_bound(rp, "IRefPlane"), "Transform")
            if xf is not None:
                arr = _g(_early_bound(xf, "IMathTransform"), "ArrayData")
                if arr is not None:
                    out["origin_mm"] = [_mm(v) for v in list(arr)[9:12]]
                    out["rotation"] = [round(float(v), 9)
                                       for v in list(arr)[0:9]]
    elif type_name == "Helix":
        d = _early_bound(raw, "IHelixFeatureData")
        for key, prop in (("pitch_mm", "Pitch"), ("height_mm", "Height"),
                          ("revolutions", "Revolution"),
                          ("clockwise", "Clockwise"),
                          ("reverse", "ReverseDirection"),
                          ("start_angle_deg", "StartingAngle"),
                          ("defined_by", "DefinedBy"),
                          ("variable_pitch", "VariablePitch")):
            v = _g(d, prop)
            if v is None:
                continue
            out[key] = _mm(v) if key.endswith("_mm") else (
                _deg(v) if key.endswith("_deg") else v)
    elif type_name in ("SweepCut", "Sweep", "SweepSurface"):
        d = _early_bound(raw, "ISweepFeatureData")
        # The options a re-authored InsertCutSwept5/CreateFeature call must
        # pass -- reading these live off the vendor's Cut-Sweep1 is what
        # cracked the 91829A560 thread (AlignWithEndFaces + swMinimumTwist).
        for prop in ("AlignWithEndFaces", "TwistControlType",
                     "PathAlignmentType", "Direction", "MergeSmoothFaces",
                     "MaintainTangency", "AdvancedSmoothing",
                     "StartTangencyType", "EndTangencyType", "FeatureScope",
                     "AutoSelect", "ThinFeature", "CircularProfile",
                     "TangentPropagation"):
            v = _g(d, prop)
            if v is not None:
                out[prop] = v
    elif type_name == "Fillet":
        d = _early_bound(raw, "ISimpleFilletFeatureData2")
        for key, prop in (("type", "Type"), ("radius_mm", "DefaultRadius"),
                          ("propagate", "PropagateToTangentFaces"),
                          ("asymmetric", "AsymmetricFillet"),
                          ("distance_mm", "DefaultDistance"),
                          ("multi_radius", "IsMultipleRadius"),
                          ("conic_type", "ConicTypeForCrossSectionProfile"),
                          ("conic_rho_or_radius", "DefaultConicRhoOrRadius")):
            v = _g(d, prop)
            if v is None:
                continue
            out[key] = _mm(v) if key.endswith("_mm") else v
    elif type_name == "Chamfer":
        d = _early_bound(raw, "IChamferFeatureData2")
        for key, prop in (("type", "Type"), ("distance_mm", "Distance"),
                          ("angle_deg", "Angle")):
            v = _g(d, prop)
            if v is None:
                continue
            out[key] = _mm(v) if key.endswith("_mm") else (
                _deg(v) if key.endswith("_deg") else v)
    elif type_name == "CirPattern":
        d = _early_bound(raw, "ICircularPatternFeatureData")
        for key, prop in (("spacing_deg", "Spacing"),
                          ("instances", "TotalInstances"),
                          ("equal_spacing", "EqualSpacing"),
                          ("reverse", "ReverseDirection"),
                          ("symmetric", "Symmetric"),
                          ("geometry_pattern", "GeometryPattern"),
                          ("axis_type", "GetAxisType")):
            v = _g(d, prop)
            if v is None:
                continue
            out[key] = _deg(v) if key.endswith("_deg") else v
    elif type_name == "MirrorPattern":
        d = _early_bound(raw, "IMirrorPatternFeatureData")
        for key, prop in (("plane_type", "GetMirrorPlaneType"),
                          ("geometry_pattern", "GeometryPattern"),
                          ("feature_count", "GetPatternFeatureCount")):
            v = _g(d, prop)
            if v is not None:
                out[key] = v
    elif type_name == "CombineBodies":
        d = _early_bound(raw, "ICombineBodiesFeatureData")
        for key, prop in (("operation", "OperationType"),  # swBodyOperationType_e
                          ("body_count", "GetBodiesToCombineCount")):
            v = _g(d, prop)
            if v is not None:
                out[key] = v
    elif type_name == "Split":
        d = _early_bound(raw, "ISplitBodyFeatureData")
        for key, prop in (("consume", "Consume"),
                          ("split_body_count", "GetSplitBodiesCount"),
                          ("trim_tool_count", "GetTrimToolsCount")):
            v = _g(d, prop)
            if v is not None:
                out[key] = v
    elif type_name == "RefAxis":
        # Definition data says HOW; the resolved endpoints say WHERE.
        ax = _g(feat, "GetSpecificFeature2")
        if ax is not None:
            params = _g(_early_bound(ax, "IRefAxis"), "GetRefAxisParams")
            if params is not None:
                vals = [_mm(v) for v in list(params)]
                out["start_mm"] = vals[0:3]
                out["end_mm"] = vals[3:6]
    elif type_name == "HoleWzd":
        d = _early_bound(raw, "IWizardHoleFeatureData2")
        # Readable WITHOUT AccessSelections (the _holes.py read-back path).
        for prop in ("Type", "Standard", "FastenerType", "FastenerSize", "HoleFit",
                     "ThreadClass", "EndCondition", "ReverseDirection"):
            v = _g(d, prop)
            if v is not None:
                out[prop] = v
        for prop in ("ThruHoleDiameter", "ThruHoleDepth", "HoleDiameter", "HoleDepth",
                     "CounterBoreDiameter", "CounterBoreDepth", "CounterSinkDiameter",
                     "ThreadDiameter", "ThreadDepth", "BlindHoleDepth"):
            v = _g(d, prop)
            if v:
                out[f"{prop}_mm"] = _mm(v)
        for prop in ("CounterSinkAngle", "DrillAngle"):
            v = _g(d, prop)
            if v:
                out[f"{prop}_deg"] = _deg(v)
    return out or None


def _tree(model):
    rows = []
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        feat = _early_bound(feat, "IFeature")
        name = str(_g(feat, "Name"))
        tn = str(_g(feat, "GetTypeName2"))
        if tn in SKIP_TYPES:
            feat = _read_member(feat, "GetNextFeature")
            continue
        row = {
            "name": name,
            "type": tn,
            "suppressed": _g(feat, "IsSuppressed"),
            "dimensions": _dimensions(feat),
        }
        data = _feature_data(feat, tn)
        if data:
            row["data"] = data
        if tn in ("ProfileFeature", "3DProfileFeature"):
            row["sketch"] = _sketch(feat)
        subs = []
        sub = _g(feat, "GetFirstSubFeature")
        for _ in range(100):
            if not sub:
                break
            sub = _early_bound(sub, "IFeature")
            stn = str(_g(sub, "GetTypeName2"))
            srow = {"name": str(_g(sub, "Name")), "type": stn,
                    "dimensions": _dimensions(sub)}
            if stn in ("ProfileFeature", "3DProfileFeature"):
                srow["sketch"] = _sketch(sub)
            subs.append(srow)
            sub = _read_member(sub, "GetNextSubFeature")
        if subs:
            row["sub_features"] = subs
        rows.append(row)
        _telemetry.info(f"{name} [{tn}] dims={len(row['dimensions'])}")
        feat = _read_member(feat, "GetNextFeature")
    return rows


# --------------------------------------------------------------------------
# pass 2 -- reference topology (rolls the model back; always released)
# --------------------------------------------------------------------------
def _entity(ent):
    """Identify a face/plane/axis used as a feature reference.

    ``GetEndConditionReference(Forward, out ReferenceType)`` and
    ``GetFromEntity(out FromEntity, out Type)`` both carry OUT parameters, so a
    generated early-bound wrapper returns a TUPLE, not the entity -- unpack it
    or every reference silently reads as absent.
    """
    if isinstance(ent, (tuple, list)):
        if not ent:
            return None
        ent, tail = ent[0], list(ent[1:])
        desc = _entity(ent) or {}
        if tail:
            desc["reference_type"] = tail[0]
        return desc or None
    if ent is None:
        return None
    out: dict = {}
    sel = _g(_early_bound(ent, "IEntity"), "GetType")
    if sel is not None:
        out["select_type"] = SELECT_TYPES.get(int(sel), sel)
    if out.get("select_type") != "face":
        # A datum plane/axis reference often IS its feature dispatch, so a bare
        # Name read identifies it; a face has no Name and goes the GetFeature
        # route below.
        name = _g(ent, "Name")
        if isinstance(name, str) and name:
            out["name"] = name
        return out or None
    face = _early_bound(ent, "IFace2")
    feat = _g(face, "GetFeature")
    if feat is not None:
        out["owner_feature"] = str(_g(_early_bound(feat, "IFeature"), "Name"))
    area = _g(face, "GetArea")
    if area is not None:
        try:
            out["area_mm2"] = round(float(area) * 1e6, 4)
        except Exception:  # noqa: BLE001
            pass
    box = _g(face, "GetBox")
    if box:
        out["box_mm"] = [_mm(v) for v in box]
    out.update(_surface(_g(face, "GetSurface")) or {})
    return out or None


def _surface(surf):
    if surf is None:
        return None
    s = _early_bound(surf, "ISurface")
    for flag, kind, params in (("IsPlane", "plane", "PlaneParams"),
                               ("IsCylinder", "cylinder", "CylinderParams"),
                               ("IsCone", "cone", "ConeParams2"),
                               ("IsSphere", "sphere", "SphereParams"),
                               ("IsTorus", "torus", "TorusParams")):
        if not _g(s, flag):
            continue
        out = {"surface": kind, "identity": int(_g(s, "Identity"))}
        p = _g(s, params)
        if p is None:
            return out
        p = [float(v) for v in p]
        if kind == "plane":
            out["normal"] = [round(v, 9) for v in p[0:3]]
            out["root_mm"] = [_mm(v) for v in p[3:6]]
        elif kind == "cylinder":
            out["origin_mm"] = [_mm(v) for v in p[0:3]]
            out["axis"] = [round(v, 9) for v in p[3:6]]
            out["radius_mm"] = _mm(p[6])
        else:
            out["raw"] = [round(v, 9) for v in p]
        return out
    return None


def _refs(model):
    rows = []
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        feat = _early_bound(feat, "IFeature")
        name = str(_g(feat, "Name"))
        tn = str(_g(feat, "GetTypeName2"))
        if tn in SKIP_TYPES:
            feat = _read_member(feat, "GetNextFeature")
            continue
        row = {"name": name, "type": tn}
        parents = _g(feat, "GetParents")
        if parents:
            row["parents"] = [str(_g(_early_bound(p, "IFeature"), "Name"))
                              for p in parents]

        if tn in ("ProfileFeature", "3DProfileFeature"):
            sk = _g(feat, "GetSpecificFeature2")
            if sk is not None:
                try:
                    row["sketch_plane"] = _entity(
                        _early_bound(sk, "ISketch").GetReferenceEntity(0))
                except Exception as exc:  # noqa: BLE001
                    row["sketch_plane_error"] = repr(exc)

        if tn in ("Extrusion", "ICE"):
            row.update(_extrude_refs(feat, model, name))
        elif tn == "RefPlane":
            row.update(_plane_refs(feat, model, name))

        rows.append(row)
        _telemetry.info(f"{name} [{tn}] parents={row.get('parents')}")
        feat = _read_member(feat, "GetNextFeature")
    return rows


def _extrude_refs(feat, model, name):
    out: dict = {}
    try:
        d = _early_bound(feat.GetDefinition(), "IExtrudeFeatureData2")
    except Exception:  # noqa: BLE001
        return out
    out["contours_count"] = _g(d, "GetContoursCount")
    try:
        if not d.AccessSelections(model, None):
            out["access"] = "denied"
            return out
    except Exception as exc:  # noqa: BLE001
        out["access_error"] = repr(exc)
        return out
    try:
        for key, meth, args in (("end_ref1", "GetEndConditionReference", (True,)),
                                ("end_ref2", "GetEndConditionReference", (False,)),
                                ("from_entity", "GetFromEntity", ())):
            try:
                desc = _entity(getattr(d, meth)(*args))
            except Exception:  # noqa: BLE001
                desc = None
            if desc:
                out[key] = desc
    finally:
        try:
            d.ReleaseSelectionAccess()
        except Exception as exc:  # noqa: BLE001
            _telemetry.warn(f"{name}: ReleaseSelectionAccess failed: {exc!r}")
    return out


def _plane_refs(feat, model, name):
    out: dict = {}
    try:
        d = _early_bound(feat.GetDefinition(), "IRefPlaneFeatureData")
    except Exception:  # noqa: BLE001
        return out
    try:
        if not d.AccessSelections(model, None):
            out["access"] = "denied"
            return out
    except Exception as exc:  # noqa: BLE001
        out["access_error"] = repr(exc)
        return out
    try:
        sels = _g(d, "Selections")
        if sels:
            out["plane_refs"] = [_entity(s) for s in sels]
    finally:
        try:
            d.ReleaseSelectionAccess()
        except Exception as exc:  # noqa: BLE001
            _telemetry.warn(f"{name}: ReleaseSelectionAccess failed: {exc!r}")
    return out


# --------------------------------------------------------------------------
# pass 3 -- the as-built B-rep
# --------------------------------------------------------------------------
def _faces(adapter):
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = part.GetBodies2(0, True) or []
    out = []
    for b in bodies:
        b = _early_bound(b, "IBody2")
        brow = {
            "name": str(_g(b, "Name")),
            "box_mm": [_mm(v) for v in (_g(b, "GetBodyBox") or [])],
            "face_count": _g(b, "GetFaceCount"),
            "faces": [],
        }
        for i, f in enumerate(_g(b, "GetFaces") or []):
            f = _early_bound(f, "IFace2")
            row = {"i": i, "area_mm2": round(float(_g(f, "GetArea") or 0.0) * 1e6, 4)}
            feat = _g(f, "GetFeature")
            if feat is not None:
                row["feature"] = str(_g(_early_bound(feat, "IFeature"), "Name"))
            box = _g(f, "GetBox")
            if box:
                row["box_mm"] = [_mm(v) for v in box]
            row.update(_surface(_g(f, "GetSurface")) or {})
            brow["faces"].append(row)
        out.append(brow)
    return out


# --------------------------------------------------------------------------
def _doc_level(adapter, model):
    out: dict = {}
    part = _early_bound(adapter.currentModel, "IPartDoc")
    for meth, args in (("GetMaterialPropertyName2", ("Default", "")),
                       ("GetMaterialPropertyName2", ("", ""))):
        try:
            v = getattr(part, meth)(*args)
        except Exception:  # noqa: BLE001
            continue
        if v:
            out["material"] = str(v)
            break
    try:
        out["appearance_rgb"] = [round(float(v), 6)
                                 for v in (model.MaterialPropertyValues or [])[:3]]
    except Exception:  # noqa: BLE001
        pass
    try:
        out["configurations"] = [str(c) for c in (model.GetConfigurationNames() or [])]
    except Exception:  # noqa: BLE001
        pass

    mgr = _g(model, "GetEquationMgr")
    eqns = []
    if mgr is not None:
        mgr = _early_bound(mgr, "IEquationMgr")
        for i in range(int(_g(mgr, "GetCount") or 0)):
            try:
                equation = str(mgr.Equation(i))
                is_global = bool(mgr.GlobalVariable(i))
                # Status is the scalar status of the last indexed operation,
                # not another indexed property.  Calling it as Status(i)
                # turns the returned int into a callable and loses the entire
                # otherwise-successful equation row.
                eqns.append({"index": i, "equation": equation,
                             "global": is_global,
                             "status": _g(mgr, "Status")})
            except Exception as exc:  # noqa: BLE001
                eqns.append({"index": i, "error": repr(exc)})
    out["equations"] = eqns

    props = {}
    ext = _g(model, "Extension")
    try:
        cpm = ext.CustomPropertyManager("")
        for nm in (_g(_early_bound(cpm, "ICustomPropertyManager"),
                      "GetNames") or []):
            try:
                res = cpm.Get5(str(nm), False)
                props[str(nm)] = {"value": str(res[0]), "resolved": str(res[1])}
            except Exception:  # noqa: BLE001
                props[str(nm)] = {"value": "<unreadable>"}
    except Exception:  # noqa: BLE001
        pass
    out["custom_properties"] = props

    mass = {}
    try:
        mp = ext.CreateMassProperty()
        mass = {
            "mass_kg": round(float(_g(mp, "Mass")), 9),
            "volume_mm3": round(float(_g(mp, "Volume")) * 1e9, 4),
            "surface_area_mm2": round(float(_g(mp, "SurfaceArea")) * 1e6, 4),
            "density": _g(mp, "Density"),
            "com_mm": [_mm(v) for v in (_g(mp, "CenterOfMass") or [])],
        }
    except Exception as exc:  # noqa: BLE001
        mass = {"error": repr(exc)}
    out["mass"] = mass
    return out


async def build(adapter) -> dict[str, str]:
    if PART is None:
        raise SystemExit(
            "usage: diag_dump_part.py <part.SLDPRT> [out.json] [--no-refs] "
            "[--no-faces]")
    check("open", await adapter.open_model(str(PART)))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    doc: dict = {"path": str(PART), "title": str(_g(model, "GetTitle"))}
    doc.update(_doc_level(adapter, model))

    with _telemetry.span("dump.tree"):
        doc["features"] = _tree(model)
    if WANT_REFS:
        with _telemetry.span("dump.refs"):
            doc["references"] = _refs(model)
    if WANT_FACES:
        with _telemetry.span("dump.faces"):
            doc["bodies"] = _faces(adapter)

    OUT.write_text(json.dumps(doc, indent=2, default=repr), encoding="utf-8")
    _telemetry.success(f"wrote {OUT} ({len(doc['features'])} recipe features)")
    return {"dump": str(OUT)}


if __name__ == "__main__":
    sys.exit(run_build(build))
