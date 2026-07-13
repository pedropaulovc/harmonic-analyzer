"""Native Hole Wizard (``HoleWzd``) features for part scripts.

Generalized from ``build_rocker_arm_support._drill_tapped_holes`` -- the proven
live idiom (one 4-point 9/16-12 foot-tap feature) -- so every fastener hole in
the model can be a REAL wizard hole carrying its thread designation instead of
a plain circle cut:

1. ``CreateDefinition(swFmHoleWzd)`` -> ``InitializeHole(type, standard,
   fastener, size, end)`` -> property overrides -> select the placement face
   as an OBJECT (coordinate SelectByID2 mis-resolves on bodies whose end faces
   touch the same plane) -> ``CreateFeature``.
2. Multi-point: the wizard lands with ONE auto placement point; its placement
   sketch is edited, the auto point is moved onto station 0 (``SetCoords``)
   and the remaining stations are added (model->sketch via the sketch's
   ``ModelToSketchTransform``; MathUtility takes an explicit VARIANT array).
   Net: ONE ``HoleWzd`` feature, N hole instances.

Thread policy: everything is **ANSI inch (UNC)** -- see
``memory/fastener-policy-us-customary.md``. The wizard table supplies the cut
diameters (tap drill for taps, fit diameter for clearances), so scripts get
the ACTUAL dimensions back (:class:`WizardHoleResult`) for analytic volume
math, and pin expectations via ``expect_dia_mm`` (a wrong size token that
still resolves in the table fails loud instead of cutting the wrong drill).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import _telemetry
from _common import _early_bound

PlacementDimension = tuple[str | None, str | None]
PlacementDimensions = tuple[PlacementDimension, PlacementDimension]

# swFeatureNameID_e / swWzdGeneralHoleTypes_e / swWzdHoleStandards_e /
# swWzdHoleStandardFastenerTypes_e / swEndConditions_e -- values verified
# against the offline API reference (developing-solidworks bundle) and the
# live rocker-arm-support feature.
SW_FM_HOLE_WZD = 25
_STD_ANSI_INCH = 0

# kind -> (swWzdGeneralHoleTypes_e, swWzdHoleStandardFastenerTypes_e)
_KINDS = {
    "tapped": (4, 27),               # straight tap, AnsiInchTappedHole
    "tapped_bottoming": (4, 26),     # AnsiInchBottomingTappedHole
    "clearance": (2, 22),            # plain hole, AnsiInchScrewClearances
    "drilled_number": (2, 24),       # AnsiInchNumberDrillSizes
    "drilled_fractional": (2, 19),   # AnsiInchFractionalDrillSizes
    "drilled_letter": (2, 20),       # AnsiInchLetterDrillSizes
    "counterbore_hex": (0, 3),       # AnsiInchHexBolt
    "counterbore_fillister": (0, 2), # AnsiInchFillister
    "counterbore_socket": (0, 9),    # AnsiInchSocketCapScrew
    "counterbore_binding": (0, 0),   # AnsiInchBinding
    "counterbore_pan": (0, 8),       # AnsiInchPan
    "dowel": (2, 703),               # AnsiInchDowelHole
}
_ENDS = {"blind": 0, "through_all": 1, "through_next": 2}
_FITS = {"close": 0, "normal": 1, "loose": 2}  # swWzdHoleScrewClearanceTypes_e

# Cut diameters (mm) from this seat's wizard database and live feature probes.
# HoleDiameter commonly reads 0.0; a plain through hole's usable value is in
# ThruHoleDiameter (live #4 normal = 0.0032639 m). Scripts take analytic volume
# expectations from these pinned values; diag_hole_wizard.py re-proves the
# representative cases by measured volume.
TAP_DRILL_MM = {          # taps cut the tap-drill diameter (TAP_DRILL column)
    "#2-56": 1.778, "#3-48": 1.994, "#4-40": 2.261, "#6-32": 2.705,
    "#8-32": 3.454, "#10-24": 3.797, "1/4-20": 5.105, "5/16-18": 6.528,
    "9/16-12": 12.304,
}
CLEARANCE_MM = {          # (size, fit) -> hole diameter (CLOSE/NORMAL/LOOSE_FIT)
    ("#2", "close"): 2.388, ("#2", "normal"): 2.591, ("#2", "loose"): 2.946,
    ("#3", "close"): 2.692, ("#3", "normal"): 2.946, ("#3", "loose"): 3.251,
    ("#4", "close"): 3.048, ("#4", "normal"): 3.264, ("#4", "loose"): 3.658,
    ("#6", "close"): 3.912, ("#6", "normal"): 4.318, ("#6", "loose"): 4.699,
    ("#8", "close"): 4.572, ("#8", "normal"): 4.978, ("#8", "loose"): 5.410,
    ("1/4", "close"): 6.756, ("1/4", "normal"): 7.137, ("1/4", "loose"): 7.544,
    ("5/16", "close"): 8.331, ("5/16", "normal"): 8.738, ("5/16", "loose"): 9.119,
    ("9/16", "close"): 14.684, ("9/16", "normal"): 15.080, ("9/16", "loose"): 15.479,
}
NUMBER_DRILL_MM = {       # number drills cut DIAMETER exactly
    "#9": 4.978, "#19": 4.216, "#20": 4.089, "#21": 4.039, "#29": 3.454,
    "#14": 4.623, "#37": 2.642, "#43": 2.261, "#47": 1.994, "#54": 1.397,
}
FRACTIONAL_DRILL_MM = {"1/8": 3.175, "3/16": 4.763, "15/64": 5.953}
LETTER_DRILL_MM = {"F": 6.528, "V": 9.576}  # V = 0.377in (transgear stud seat)

# 118-degree drill point: tip height = r * cot(59 deg). A BLIND wizard hole's
# depth runs to the flat shoulder; the point extends beyond it (probe: #4-40
# blind 6mm removed 25.0 vs 24.1 cylinder -- exactly the cone term).
DRILL_POINT_H = 0.60086


def blind_hole_volume_mm3(dia_mm: float, depth_mm: float) -> float:
    """Analytic volume of one blind wizard hole (cylinder + drill point)."""
    import math
    r = dia_mm / 2.0
    return math.pi * r * r * depth_mm + math.pi / 3.0 * r * r * (r * DRILL_POINT_H)


@dataclass
class HoleSpec:
    """One Hole Wizard hole definition (all instances of a feature share it).

    Attributes:
        kind: A ``_KINDS`` key -- picks the wizard hole type + fastener table.
        size: Wizard-table size token for the kind (``"#8-32"``, ``"9/16-12"``
            for taps; ``"#8"``, ``"5/16"`` for clearances; ``"#47"`` for number
            drills; the bolt size for counterbores).
        end: ``"through_all"`` | ``"blind"`` | ``"through_next"``.
        depth_mm: Hole depth for a blind end (mm; the wizard's HoleDepth).
        thread_class: Tap class (``"2B"`` default policy; the support's foot
            taps keep their as-built ``"1B"``). Ignored for non-taps.
        fit: Clearance fit (``"normal"`` default) -- clearance kind only.
        overrides_mm: Post-initialize property overrides in mm, keyed by the
            ``IWizardHoleFeatureData2`` property name (``"HoleDiameter"``,
            ``"CounterBoreDiameter"``, ``"CounterBoreDepth"``, ...). Use ONLY
            to preserve a photo-measured artefact dimension the standard table
            would move (e.g. the base's Ø23 lag-head recess); leave empty to
            take the true table dimension.
    """

    kind: str
    size: str
    end: str = "through_all"
    depth_mm: float = 0.0
    thread_class: str = "2B"
    fit: str = "normal"
    overrides_mm: dict[str, float] = field(default_factory=dict)


@dataclass
class WizardHoleResult:
    """The created feature + the ACTUAL wizard dimensions (mm) for volume math."""

    name: str
    hole_dia_mm: float
    depth_mm: float
    cbore_dia_mm: float = 0.0
    cbore_depth_mm: float = 0.0
    placement_drive_jobs: list[tuple[str, str]] = field(default_factory=list)


def blind_cut_dia_mm(spec: HoleSpec) -> float:
    """The pinned cut diameter a blind ``spec`` must pass to HoleWizard5."""
    if spec.kind in ("tapped", "tapped_bottoming"):
        table, key = TAP_DRILL_MM, spec.size
    elif spec.kind == "clearance":
        table, key = CLEARANCE_MM, (spec.size, spec.fit)
    elif spec.kind == "drilled_number":
        table, key = NUMBER_DRILL_MM, spec.size
    elif spec.kind == "drilled_fractional":
        table, key = FRACTIONAL_DRILL_MM, spec.size
    elif spec.kind == "drilled_letter":
        table, key = LETTER_DRILL_MM, spec.size
    else:
        raise ValueError(f"blind is not supported for kind {spec.kind!r}")
    if key not in table:
        raise ValueError(
            f"size {key!r} not pinned for {spec.kind!r} -- add it to the "
            "table in _holes.py (values from the wizard-database dump)")
    return table[key]


def find_planar_face(model, normal, points_mm, tol_mm: float = 1.0):
    """Return the planar face with outward normal ``normal`` (a principal
    +/-X/Y/Z unit tuple) whose plane contains and bounding box spans every
    point of ``points_mm`` -- the face the holes are drilled from.

    Coordinate ``SelectByID2`` is unreliable for this (a point on the target
    plane can resolve to a side face that merely touches the plane, sending
    the drill axis sideways -- the rocker-arm-support live failure), so the
    face OBJECT found by enumeration is the reliable path.
    """
    axis = max(range(3), key=lambda k: abs(normal[k]))
    sign = 1.0 if normal[axis] > 0 else -1.0
    plane_mm = points_mm[0][axis]
    others = [k for k in range(3) if k != axis]
    body = (model.GetBodies2(0, False) or [None])[0]
    body = _early_bound(body, "IBody2")
    faces = body.GetFaces() or []
    # O(faces) with 2-3 COM roundtrips each -- fine on a prismatic body
    # (tens of faces), pathological after a face-exploding cut (the engraved
    # nameplate: thousands of groove faces, >20 min). Callers must place
    # wizard holes BEFORE such features; this log names the offender.
    _telemetry.debug(f"find_planar_face: scanning {len(faces)} faces")
    if len(faces) > 500:
        _telemetry.warn(
            f"find_planar_face: {len(faces)} faces -- the face walk is "
            "O(faces) in COM roundtrips; create wizard holes before "
            "face-exploding features"
        )
    best = None
    for f in faces:
        f = _early_bound(f, "IFace2")
        try:
            n = tuple(f.Normal)
        except Exception:  # noqa: BLE001
            continue
        if n[axis] * sign < 0.99 or any(abs(n[k]) > 0.01 for k in others):
            continue
        box = [v * 1000.0 for v in f.GetBox()]
        if abs(box[axis] - plane_mm) > tol_mm:
            continue
        spans = all(
            box[k] - tol_mm <= p[k] <= box[k + 3] + tol_mm
            for p in points_mm for k in others
        )
        if spans and (best is None or f.GetArea() > best.GetArea()):
            best = f
    return best


@_telemetry.traced("feature.hole_wizard", label_param="label")
def wizard_holes(
    adapter,
    spec: HoleSpec,
    points_mm,
    normal,
    label: str,
    *,
    name: str = "",
    expect_dia_mm: float = 0.0,
    placement_dims: list[PlacementDimensions] | None = None,
) -> WizardHoleResult:
    """Create ONE ``HoleWzd`` feature with an instance at each of ``points_mm``
    (model X,Y,Z in mm, all on the planar face whose outward normal is
    ``normal``), per ``spec``. Optionally rename the feature to ``name`` and
    assert the wizard-table hole diameter is ``expect_dia_mm`` (+/- 0.05 mm).

    ``placement_dims`` optionally restores the parametric contract of the
    pre-Wizard placement sketches. It has one entry per point; each entry is
    ``((x_name, x_drive), (y_name, y_drive))`` in placement-sketch coordinates.
    Every non-zero coordinate receives a driving dimension; a zero coordinate
    receives the matching origin-axis relation because zero-valued dimensions
    are invalid. Named dimensions with equations are returned as deferred
    ``placement_drive_jobs`` so callers can apply them with the same end-of-build
    ``drive_dimension`` pass used by the rest of the part.

    Returns the actual wizard dimensions for the caller's analytic volume
    check -- the check then verifies the CUT, independent of this readback.
    """
    import pythoncom
    from win32com.client import VARIANT

    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    if spec.kind not in _KINDS:
        raise ValueError(f"unknown hole kind {spec.kind!r} (of {sorted(_KINDS)})")
    if spec.end not in _ENDS:
        raise ValueError(f"unknown end {spec.end!r} (of {sorted(_ENDS)})")
    if placement_dims is not None and len(placement_dims) != len(points_mm):
        raise ValueError(
            f"hole wizard {label}: placement_dims has {len(placement_dims)} "
            f"entries for {len(points_mm)} points"
        )
    hole_type, fastener = _KINDS[spec.kind]
    end = _ENDS[spec.end]

    model = adapter.currentModel
    model = _early_bound(model, "IModelDoc2")
    fm = model.FeatureManager
    fm = _early_bound(fm, "IFeatureManager")

    face = find_planar_face(model, normal, points_mm)
    if face is None:
        raise RuntimeError(f"hole wizard {label}: placement face not found")
    model.ClearSelection2(True)
    if not face.Select2(False, 0):
        raise RuntimeError(f"hole wizard {label}: face Select failed")
    # Phase logs: the wizard's create/rebuild calls can spin unbounded on a
    # pathological face (the engraved nameplate front measured >20 min at
    # 100% CPU with no dialog) -- keep the last-started phase visible.
    _telemetry.debug(f"hole wizard {label}: face selected, creating feature")

    if spec.end == "blind":
        # BLIND holes go through the legacy positional HoleWizard5:
        # InitializeHole(..., blind) is broken on this build -- it cuts a
        # garbage default AND poisons the wizard session so SUBSEQUENT holes
        # inherit corrupted diameters (probe 2026-07-11, reproducible), and
        # the depth/end properties silently no-op through ModifyDefinition.
        # Value-slot meanings per the official HoleWizard5 remarks: taps take
        # V1=thread depth, V6=bottom drill angle (radians), V7=cosmetic thread
        # type, V8=thread end condition; plain holes take V1=screw fit,
        # V2=bottom drill angle.
        d = spec.depth_mm / 1000.0
        dia = blind_cut_dia_mm(spec) / 1000.0
        ang = 2.0594885  # 118-degree drill point
        if hole_type == 4:
            vals = [d, -1, -1, -1, -1, ang, 1, _ENDS["blind"], -1, -1, -1, -1]
            tclass = spec.thread_class
        else:
            fit = _FITS[spec.fit] if spec.kind == "clearance" else -1
            vals = [fit, ang, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1]
            tclass = ""
        feat = fm.HoleWizard5(
            hole_type, _STD_ANSI_INCH, fastener, spec.size, _ENDS["blind"],
            dia, d, -1.0, *vals, tclass,
            False, True, True, True, True, False)
        if feat is None:
            raise RuntimeError(
                f"hole wizard {label}: HoleWizard5 (blind) failed -- size "
                f"{spec.size!r} may be invalid for kind {spec.kind!r}")
    else:
        data = fm.CreateDefinition(SW_FM_HOLE_WZD)
        data = _early_bound(data, "IWizardHoleFeatureData2")
        data.InitializeHole(hole_type, _STD_ANSI_INCH, fastener, spec.size, end)
        if hole_type == 4:  # taps carry a class + their own thread end condition
            # Pre-create sets are the support-foot precedent for these two;
            # every other customization (fit, dim overrides) must go through
            # the post-create ModifyDefinition flow.
            for prop, val in (("ThreadClass", spec.thread_class),
                              ("ThreadEndCondition", end)):
                try:
                    setattr(data, prop, val)
                except Exception:  # noqa: BLE001
                    pass
        feat = fm.CreateFeature(data)
        if feat is None:
            raise RuntimeError(
                f"hole wizard {label}: CreateFeature failed -- size {spec.size!r} "
                f"may be invalid for kind {spec.kind!r}"
            )
    feat = _early_bound(feat, "IFeature")
    _telemetry.debug(f"hole wizard {label}: feature created, placing points")

    # Locate the wizard's 1-point placement sketch.
    place_sk = place_name = None
    sub = feat.GetFirstSubFeature()
    while sub is not None:
        sub = _early_bound(sub, "IFeature")
        if str(sub.GetTypeName2()) == "ProfileFeature":
            sk = sub.GetSpecificFeature2()
            sk = _early_bound(sk, "ISketch")
            if len(sk.GetSketchPoints2() or []) == 1:
                place_sk, place_name = sk, str(sub.Name)
                break
        sub = sub.GetNextSubFeature()
    if place_sk is None:
        raise RuntimeError(f"hole wizard {label}: placement sketch not found")

    math_util = adapter.swApp.GetMathUtility()
    math_util = _early_bound(math_util, "IMathUtility")
    xform = place_sk.ModelToSketchTransform
    xform = _early_bound(xform, "IMathTransform")

    def _sketch_xy(pt_mm):
        arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                      [v / 1000.0 for v in pt_mm])
        mpt = math_util.CreatePoint(arr)
        mpt = _early_bound(mpt, "IMathPoint")
        spt = mpt.MultiplyTransform(xform)
        spt = _early_bound(spt, "IMathPoint")
        return list(spt.ArrayData)[:3]

    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
            place_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0):
        raise RuntimeError(f"hole wizard {label}: cannot edit {place_name}")
    model.EditSketch()
    sm = model.SketchManager
    sm = _early_bound(sm, "ISketchManager")
    # Add the placement points straight to the sketch DB (AddToDB): otherwise a
    # point authored within snap distance of a reference SNAPS to it and picks
    # up a coincident relation that rebuild re-applies. Bit us on support-bar's
    # x=-2 bracket hole -- it snapped to the origin (x=0), the drilled hole
    # landed 2 mm off, and the bracket screw plowed 43 mm^3 into solid bar
    # (probe 2026-07-11). Holes far from any reference (the +-179.5 clamp holes)
    # never snapped, which is why only the near-origin hole moved.
    prev_add_to_db = bool(sm.AddToDB)
    sm.AddToDB = True
    placed_points = []
    try:
        auto = (place_sk.GetSketchPoints2() or [None])[0]
        auto = _early_bound(auto, "ISketchPoint")
        sx, sy, sz = _sketch_xy(points_mm[0])
        auto.SetCoords(sx, sy, sz)
        placed_points.append((auto, sx, sy))
        for pt in points_mm[1:]:
            sx, sy, sz = _sketch_xy(pt)
            created = sm.CreatePoint(sx, sy, sz)
            if created is None:
                raise RuntimeError(f"hole wizard {label}: CreatePoint failed")
            created = _early_bound(created, "ISketchPoint")
            placed_points.append((created, sx, sy))
    finally:
        sm.AddToDB = prev_add_to_db

    placement_drive_jobs: list[tuple[str, str]] = []
    if placement_dims is not None:
        from _common import SketchDims, check
        from solidworks_mcp.adapters.solidworks.sketch import (
            _add_sketch_constraint_impl,
            _add_sketch_dimension_impl,
        )

        dims = SketchDims()
        # Direct EditSketch bypasses the adapter's create_sketch registry reset;
        # force the reserved "origin" reference to resolve in THIS placement
        # sketch rather than reusing a prior sketch's cached dispatch.
        adapter._sketch_origin_point = None
        previous_sketch_manager = adapter.currentSketchManager
        adapter.currentSketchManager = sm
        try:
            for index, ((point, sx, sy), point_dims) in enumerate(
                    zip(placed_points, placement_dims, strict=True)):
                point_id = adapter._register_sketch_entity("Point", point)
                zero_x = abs(sx) < 1e-12
                zero_y = abs(sy) < 1e-12
                if zero_x and zero_y:
                    relation = "coincident"
                elif zero_x:
                    relation = "vertical_points"
                elif zero_y:
                    relation = "horizontal_points"
                else:
                    relation = None
                if relation is not None:
                    check(
                        f"constrain hole placement {label} point {index} {relation}",
                        _add_sketch_constraint_impl(
                            adapter, point_id, "origin", relation
                        ),
                    )
                for axis, coord, dim_type, (dim_name, drive) in (
                    ("x", sx, "horizontal_distance", point_dims[0]),
                    ("y", sy, "vertical_distance", point_dims[1]),
                ):
                    if abs(coord) < 1e-12:
                        if dim_name is not None or drive is not None:
                            raise ValueError(
                                f"hole wizard {label}: point {index} {axis} is zero "
                                "and cannot carry a distance dimension"
                            )
                        continue
                    check(
                        f"dimension hole placement {label} point {index} {axis}",
                        _add_sketch_dimension_impl(
                            adapter, point_id, "origin", dim_type, abs(coord) * 1000.0
                        ),
                    )
                    dims.record(dim_name, drive)
        finally:
            adapter.currentSketchManager = previous_sketch_manager
    model.EditSketch()
    _telemetry.debug(f"hole wizard {label}: points placed, rebuilding")
    model.EditRebuild3()

    if placement_dims is not None:
        placement_drive_jobs = dims.apply_feature(adapter, sub, place_name)

    npts = len(place_sk.GetSketchPoints2() or [])
    if npts != len(points_mm):
        raise RuntimeError(
            f"hole wizard {label}: expected {len(points_mm)} placement points, got {npts}")

    if name:
        try:
            feat.Name = name
        except Exception:  # noqa: BLE001
            _telemetry.warn(f"hole wizard {label}: rename to {name!r} failed")

    # Customize + read back through the EDIT flow: the created feature's
    # definition carries the populated table values (the pre-create object
    # reads 0.0 for everything it did not set).
    defn = _early_bound(feat.GetDefinition(), "IWizardHoleFeatureData2")
    edits: list[tuple[str, object]] = []
    if spec.kind == "clearance" and spec.end != "blind":
        # HoleFit is a NO-OP on a plain (type-2) clearance hole: the API
        # applies it to counterbore/countersink features only (per the
        # IWizardHoleFeatureData2.HoleFit remarks), so a plain hole ships the
        # NORMAL-fit diameter regardless of spec.fit -- probe 2026-07-11: a
        # 1/4 "close" hole still cut 7.137 mm (the normal dia, not 6.756).
        # Compare the initialized geometry to the pinned fit before editing.
        # SolidWorks sometimes initializes the requested normal diameter (#4
        # -> 3.2639 mm) and sometimes another fit (#8 probe -> too small).
        # Redundantly writing the SAME diameter corrupts swHoleThru (25) into
        # swHoleThruCounterSinkBottom (26), which adds a bogus far-side
        # countersink line to native hole tables. Modify only on real drift.
        pinned_dia_mm = blind_cut_dia_mm(spec)
        initialized_dia_mm = float(defn.ThruHoleDiameter) * 1000.0
        diameter_drift = abs(initialized_dia_mm - pinned_dia_mm) > 0.05
        if diameter_drift and "HoleDiameter" not in spec.overrides_mm:
            # On a plain hole the DRIVING knob is ThruHoleDiameter -- a
            # HoleDiameter-only write is silently dropped (probe 2026-07-11:
            # HoleDiameter-only still cut 7.137; setting BOTH cut 6.756). Set
            # both, mirroring the counterbore override path below.
            cut_m = pinned_dia_mm / 1000.0
            edits.append(("HoleDiameter", cut_m))
            edits.append(("ThruHoleDiameter", cut_m))
            _telemetry.event(
                "hole_wizard.diameter_override",
                label=label,
                initialized_mm=round(initialized_dia_mm, 4),
                pinned_mm=round(pinned_dia_mm, 4),
            )
    for k, v in spec.overrides_mm.items():
        edits.append((k, v / 1000.0))
        if k == "HoleDiameter":
            # the through-hole knob of a counterbore is ThruHoleDiameter;
            # HoleDiameter writes are ignored there (probe) -- set both
            edits.append(("ThruHoleDiameter", v / 1000.0))

    if edits:
        # Early-bound call: the params are DECLARED dispatches, so a plain
        # None marshals as a typed null -- a VARIANT wrapper here throws
        # "The Python instance can not be converted to a COM object" (the
        # null-VARIANT idiom applies only to LATE-bound calls).
        if not defn.AccessSelections(model, None):
            raise RuntimeError(f"hole wizard {label}: AccessSelections failed")
        for prop, val in edits:
            try:
                setattr(defn, prop, val)
            except Exception:  # noqa: BLE001
                # Properties alias per hole Type; the inapplicable ones reject
                # or no-op. The caller's analytic volume check is the hard
                # gate that the surviving writes produced the right geometry.
                _telemetry.debug(f"hole wizard {label}: property {prop} rejected")
        # ModifyDefinition wants the definition as its underlying dispatch --
        # hand it defn._oleobj_ (the raw IDispatch) rather than the wrapper.
        if not feat.ModifyDefinition(defn._oleobj_, model, null_callout()):
            raise RuntimeError(f"hole wizard {label}: ModifyDefinition failed")
        model.EditRebuild3()
        defn = _early_bound(feat.GetDefinition(), "IWizardHoleFeatureData2")

    def _dim(prop: str) -> float:
        try:
            return float(getattr(defn, prop)) * 1000.0
        except Exception:  # noqa: BLE001
            return 0.0

    stored_size = str(getattr(defn, "FastenerSize", "") or "")
    if stored_size.strip() != spec.size:
        _telemetry.warn(
            f"hole wizard {label}: stored size {stored_size!r} "
            f"!= requested {spec.size!r}"
        )
    result = WizardHoleResult(
        name=str(feat.Name),
        hole_dia_mm=_dim("HoleDiameter"),
        depth_mm=_dim("HoleDepth"),
        cbore_dia_mm=_dim("CounterBoreDiameter"),
        cbore_depth_mm=_dim("CounterBoreDepth"),
        placement_drive_jobs=placement_drive_jobs,
    )
    if expect_dia_mm and abs(result.hole_dia_mm - expect_dia_mm) > 0.05:
        raise RuntimeError(
            f"hole wizard {label}: hole diameter {result.hole_dia_mm:.3f} != "
            f"expected {expect_dia_mm:.3f} -- wrong size token {spec.size!r}?"
        )
    _telemetry.event(
        "hole_wizard.created", label=label, kind=spec.kind, size=spec.size,
        points=len(points_mm), dia_mm=round(result.hole_dia_mm, 3),
    )
    _telemetry.success(
        f"hole wizard {label}: {len(points_mm)}x {spec.size} {spec.kind} "
        f"(Ø{result.hole_dia_mm:.3f})"
    )
    return result


def cross_hole_volume_mm3(hole_dia_mm: float, shaft_dia_mm: float,
                          n: int = 20001) -> float:
    """Removed volume of a radial THROUGH hole drilled diametrally through a
    full cylinder (perpendicular cylinder-cylinder intersection, axes
    crossing): V = integral 2*sqrt(R^2-x^2) * 2*sqrt(r^2-x^2) dx, numeric --
    no clean closed form. Probe-verified 228.39 measured vs 228.41 analytic
    (#9 through Ø12, diag_hole_wizard_cyl 2026-07-11)."""
    import math
    r, big_r = hole_dia_mm / 2.0, shaft_dia_mm / 2.0
    total = 0.0
    dx = 2.0 * r / (n - 1)
    for i in range(n):
        x = -r + i * dx
        w = 0.5 if i in (0, n - 1) else 1.0
        total += w * 2.0 * math.sqrt(max(big_r**2 - x * x, 0.0)) * \
            2.0 * math.sqrt(max(r**2 - x * x, 0.0))
    return total * dx


def wizard_hole_on_cylinder(adapter, spec: HoleSpec, point_mm, label: str,
                            *, name: str = "",
                            y_dim: PlacementDimension | None = None
                            ) -> list[tuple[str, str]]:
    """ONE through wizard hole drilled RADIALLY into a cylindrical face at
    ``point_mm`` (a model point ON the face; the drill axis is the surface
    normal there, through the shaft axis).

    The planar-face path cannot serve a radial cross-hole (no planar face
    carries the drill axis); on a cylinder the wizard hangs its placement on
    a 3D sketch whose point coords ARE model coords, so no
    ModelToSketchTransform is involved (probe: diag_hole_wizard_cyl, volume
    exact to 0.01%). Through-all only -- a blind radial hole would need the
    HoleWizard5 positional path re-probed on a cylinder. Single-point: the
    wizard's auto point is moved onto the station; multi-point radial holes
    would each need their own feature anyway (one 3D-sketch point per face
    parameterization is untested).

    The face picked is the LARGEST cylindrical face of the body -- callers
    with several cylinder faces (stepped shafts) must cut the hole while the
    target section is the dominant cylinder, or extend this to face-pick by
    the point.
    """
    if spec.end != "through_all":
        raise ValueError("wizard_hole_on_cylinder supports through_all only")
    hole_type, fastener = _KINDS[spec.kind]

    model = adapter.currentModel
    model = _early_bound(model, "IModelDoc2")
    fm = model.FeatureManager
    fm = _early_bound(fm, "IFeatureManager")

    body = (model.GetBodies2(0, False) or [None])[0]
    body = _early_bound(body, "IBody2")
    face = None
    for f in body.GetFaces() or []:
        f = _early_bound(f, "IFace2")
        surf = f.GetSurface()
        surf = _early_bound(surf, "ISurface")
        if not surf.IsCylinder():
            continue
        if face is None or f.GetArea() > face.GetArea():
            face = f
    if face is None:
        raise RuntimeError(f"hole wizard {label}: no cylindrical face")
    model.ClearSelection2(True)
    if not face.Select2(False, 0):
        raise RuntimeError(f"hole wizard {label}: cylinder Select2 failed")
    _telemetry.debug(f"hole wizard {label}: cylinder selected, creating feature")

    data = fm.CreateDefinition(SW_FM_HOLE_WZD)
    data = _early_bound(data, "IWizardHoleFeatureData2")
    data.InitializeHole(hole_type, _STD_ANSI_INCH, fastener, spec.size,
                        _ENDS["through_all"])
    feat = fm.CreateFeature(data)
    if feat is None:
        raise RuntimeError(
            f"hole wizard {label}: CreateFeature (cylinder) failed -- size "
            f"{spec.size!r} may be invalid for kind {spec.kind!r}")
    feat = _early_bound(feat, "IFeature")
    _telemetry.debug(f"hole wizard {label}: feature created, placing point")

    # The placement is a 3D sketch with one auto point; its coords are model
    # coords -- pin it straight onto the station.
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    place = None
    sub = feat.GetFirstSubFeature()
    while sub is not None:
        sub = _early_bound(sub, "IFeature")
        if "Profile" in str(sub.GetTypeName2()):
            sk = sub.GetSpecificFeature2()
            sk = _early_bound(sk, "ISketch")
            if bool(sk.Is3D()) and len(sk.GetSketchPoints2() or []) == 1:
                place = (sub, sk)
                break
        sub = sub.GetNextSubFeature()
    if place is None:
        raise RuntimeError(f"hole wizard {label}: 3D placement sketch not found")
    sub, sk = place
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
            str(sub.Name), "SKETCH", 0, 0, 0, False, 0, null_callout(), 0):
        raise RuntimeError(f"hole wizard {label}: cannot edit {sub.Name}")
    model.EditSketch()
    pt = (sk.GetSketchPoints2() or [None])[0]
    pt = _early_bound(pt, "ISketchPoint")
    pt.SetCoords(point_mm[0] / 1000.0, point_mm[1] / 1000.0,
                 point_mm[2] / 1000.0)

    placement_drive_jobs: list[tuple[str, str]] = []
    if y_dim is not None:
        from _common import SketchDims, check
        from solidworks_mcp.adapters.solidworks.sketch import (
            _add_sketch_dimension_impl,
        )

        dims = SketchDims()
        previous_sketch_manager = adapter.currentSketchManager
        adapter.currentSketchManager = model.SketchManager
        adapter._sketch_origin_point = None
        try:
            point_id = adapter._register_sketch_entity("Point", pt)
            check(
                f"dimension radial hole placement {label} y",
                _add_sketch_dimension_impl(
                    adapter,
                    point_id,
                    "origin",
                    "vertical_distance",
                    abs(point_mm[1]),
                ),
            )
            dims.record(*y_dim)
        finally:
            adapter.currentSketchManager = previous_sketch_manager
    model.EditSketch()
    _telemetry.debug(f"hole wizard {label}: point placed, rebuilding")
    model.EditRebuild3()
    if y_dim is not None:
        placement_drive_jobs = dims.apply_feature(adapter, sub, str(sub.Name))

    if name:
        try:
            feat.Name = name
        except Exception:  # noqa: BLE001
            _telemetry.warn(f"hole wizard {label}: rename to {name!r} failed")
    _telemetry.event(
        "hole_wizard.created", label=label, kind=spec.kind, size=spec.size,
        points=1, placement="cylindrical",
    )
    _telemetry.success(
        f"hole wizard {label}: radial {spec.size} {spec.kind} through cylinder")
    return placement_drive_jobs
