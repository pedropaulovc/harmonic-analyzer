r"""Shared machinery for the McMaster reverse-engineering replicas.

Extracted from ``diag_build_91829A560.py`` (the validated shoulder-screw
replica) so every subsequent part replica -- see ``diag_build_mcmaster.py`` --
reuses the same session helpers, vendor gates and report/render flow instead
of re-proving them per part.

Ground truth comes straight from each part's harvest JSON
(``cad/out/reports/mcmaster-<part>-dump.json``, written by
``diag_dump_part.py``): mass properties, COM and the per-face area multiset.
Nothing vendor-derived is hardcoded here.

Gate policy (relative, with absolute floors -- the fleet spans 65 mm^3 to
9628 mm^3, so the 91829A560 script's absolute tolerances don't transfer):

- volume:   |delta| <= max(0.02 mm^3, 0.02 %)
- surface:  |delta| <= max(0.10 mm^2, 0.05 %)
- COM:      each axis within 0.02 mm of the vendor's
- faces:    vendor count <= FACE_MULTISET_LIMIT -> exact sorted-area multiset
            (per-face |delta| <= max(0.06 mm^2, 0.1 %)); above the limit
            (the knurled parts: 1382/3974 faces) -> exact face COUNT plus the
            sorted TOP-K largest areas (the structural, non-knurl faces).

The McMaster ``.SLDPRT`` files are (c) McMaster-Carr, reference-only: they are
never saved or modified, and replica artefacts go only under the gitignored
``cad/out/reference/``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    CAD_ROOT,
    REFERENCES_DIR,
    _early_bound,
    _read_member,
    check,
)

OUT_DIR = CAD_ROOT / "out" / "reference"
REPORTS_DIR = CAD_ROOT / "out" / "reports"
MCMASTER_DIR = REFERENCES_DIR / "mcmaster"

SW_BODY_ADD = 15903  # swBodyOperationType_e.SWBODYADD

FACE_MULTISET_LIMIT = 60  # above this, gate count + top-K instead of multiset
FACE_TOP_K = 30


def vendor_truth(part_no: str) -> dict:
    """Load the harvest JSON for one part -- the gate's ground truth."""
    path = REPORTS_DIR / f"mcmaster-{part_no}-dump.json"
    if not path.exists():
        raise FileNotFoundError(
            f"no harvest for {part_no}: run diag_dump_part.py first ({path})")
    return json.loads(path.read_text(encoding="utf-8"))


def vendor_face_areas(truth: dict) -> list[float]:
    areas = []
    for body in truth.get("bodies") or []:
        for face in body.get("faces") or []:
            areas.append(round(float(face["area_mm2"]), 4))
    return sorted(areas)


def mass_properties(adapter) -> dict:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    ext = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    mp = ext.CreateMassProperty()
    return {
        "volume_mm3": round(float(_read_member(mp, "Volume")) * 1e9, 4),
        "surface_mm2": round(float(_read_member(mp, "SurfaceArea")) * 1e6, 4),
        "com_mm": [round(float(v) * 1000.0, 6)
                   for v in (_read_member(mp, "CenterOfMass") or [])],
    }


def bodies(adapter) -> list:
    part = _early_bound(adapter.currentModel, "IPartDoc")
    return list(part.GetBodies2(0, False) or [])


def face_areas(adapter) -> list[float]:
    bl = bodies(adapter)
    if len(bl) != 1:
        raise RuntimeError(f"replica has {len(bl)} bodies, expected 1")
    body = _early_bound(bl[0], "IBody2")
    areas = []
    for f in body.GetFaces() or []:
        f = _early_bound(f, "IFace2")
        areas.append(round(float(_read_member(f, "GetArea")) * 1e6, 4))
    return sorted(areas)


async def export_views(adapter, stem: str) -> dict[str, str]:
    out = {}
    for view in ("front", "isometric"):
        img = (OUT_DIR / f"{stem}_{view}.png").resolve()
        check(f"export_image {stem} {view}", await adapter.export_image({
            "file_path": str(img), "format_type": "png",
            "width": 1600, "height": 1000, "view_orientation": view,
        }))
        out[view] = str(img)
    return out


from contextlib import contextmanager

# swUserPreferenceToggle_e (values read from swconst.tlb on this install)
_SW_SKETCH_AUTOMATIC_RELATIONS = 9
_SW_SKETCH_INFERENCE = 249


@contextmanager
def no_sketch_inference(adapter):
    """Disable sketch inference + automatic relations for the duration.

    SolidWorks inference snapping is PIXEL-based (view-dependent): it
    silently re-solved a scripted arc by snapping its centre to a
    centreline midpoint and an endpoint to a horizontal alignment, at
    distances that depend on the current zoom.  Scripted geometry must
    never depend on the view, so profile sketching runs with both
    toggles off.  (AddToDB also suppresses snapping but leaves contours
    the boss revolve rejects.)"""
    app = adapter.swApp
    prev = [bool(app.GetUserPreferenceToggle(t))
            for t in (_SW_SKETCH_AUTOMATIC_RELATIONS, _SW_SKETCH_INFERENCE)]
    app.SetUserPreferenceToggle(_SW_SKETCH_AUTOMATIC_RELATIONS, False)
    app.SetUserPreferenceToggle(_SW_SKETCH_INFERENCE, False)
    try:
        yield
    finally:
        app.SetUserPreferenceToggle(_SW_SKETCH_AUTOMATIC_RELATIONS, prev[0])
        app.SetUserPreferenceToggle(_SW_SKETCH_INFERENCE, prev[1])


def offset_plane(adapter, name: str, offset_mm: float, base: str = "Top Plane"):
    """Reference plane parallel to ``base`` at (signed) offset_mm."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        base, "PLANE", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {base}")
    flags = 8 | (256 if offset_mm < 0 else 0)  # Distance | OptionFlip
    plane = model.FeatureManager.InsertRefPlane(
        flags, abs(offset_mm) / 1000.0, 0, 0, 0, 0
    )
    if plane is None:
        raise RuntimeError(f"InsertRefPlane failed for {name}")
    plane.Name = name
    model.ClearSelection2(True)
    return name


def split_at_plane(adapter, plane_name: str, feature_name: str) -> list[dict]:
    """Vendor-style Split2: split the body at ``plane_name``, keep every
    piece, and return [{name, box_mm}] per resulting body."""
    import pythoncom
    from win32com.client import VARIANT
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from _common import name_last_feature

    model = adapter.currentModel
    fm = model.FeatureManager
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        plane_name, "PLANE", 0, 0, 0, True, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {plane_name} for the split")
    pre = fm.PreSplitBody2
    if callable(pre):
        pre = pre()
    if not pre or len(pre) < 2:
        raise RuntimeError(f"PreSplitBody2 returned {pre!r}, expected >=2")
    split = fm.PostSplitBody2(
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(pre)),
        False,  # keep every body in the part
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [None] * len(pre)),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [""] * len(pre)),
        "",
    )
    if split is None:
        raise RuntimeError("PostSplitBody2 failed")
    model.ClearSelection2(True)
    name_last_feature(adapter, feature_name)
    out = []
    for b in bodies(adapter):
        b2 = _early_bound(b, "IBody2")
        box = [float(x) * 1000.0 for x in (b2.GetBodyBox() or [])]
        out.append({"name": str(_read_member(b2, "Name")), "box_mm": box})
    return out


def thread_sweep_cut(adapter, profile: str, path: str, body_name: str | None,
                     feature_name: str):
    """The decoded vendor Cut-Sweep: obsolete ``InsertCutSwept5`` with the
    profile at mark 1, the helix at mark 4 and (optionally) an explicit
    SOLIDBODY scope -- the modern CreateDefinition path fails body-scoped
    cuts (see the 91829A560 postmortem)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from solidworks_mcp.adapters.solidworks.features import (
        _flag_feature_methods,
        _select_named_feature,
    )
    from _common import name_last_feature

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, profile, 1, False):
        raise RuntimeError(f"cannot select sweep profile {profile!r} (mark 1)")
    if not _select_named_feature(adapter, path, 4, True):
        raise RuntimeError(f"cannot select sweep path {path!r} (mark 4)")
    scoped = body_name is not None
    if scoped and not model.Extension.SelectByID2(
        body_name, "SOLIDBODY", 0, 0, 0, True, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select body {body_name!r} for scope")
    feature_manager = _flag_feature_methods(
        model.FeatureManager, "IFeatureManager", "InsertCutSwept5")
    with _telemetry.span("feature.thread_sweep_cut", label=feature_name):
        swept = feature_manager.InsertCutSwept5(
            False,  # Propagate
            True,   # Alignment (vendor AlignWithEndFaces=True)
            0,      # TwistCtrlOption: swTwistControlFollowPath
            False,  # KeepTangency
            False,  # BAdvancedSmoothing
            1, 1,   # Start/EndMatchingType (vendor Start/EndTangencyType=1)
            False, 0.0, 0.0, 0,  # thin body
            10,     # PathAlign: swMinimumTwist (vendor PathAlignmentType)
            scoped,          # UseFeatScope
            not scoped,      # UseAutoSelect
            0.0,    # TwistAngle
            True,   # BMergeSmoothFaces
            False, False, False,  # assembly scope
            False, 0.0,  # CircularProfile
            -1,     # Direction (vendor)
        )
    model.ClearSelection2(True)
    if swept is None:
        raise RuntimeError(f"InsertCutSwept5 returned None for {feature_name}")
    name_last_feature(adapter, feature_name)
    return swept


def thread_sweep_cut_modern(adapter, profile: str, path: str,
                            feature_name: str):
    """Modern sweep-cut authoring: CreateDefinition(swFmSweepCut) with the
    vendor's exact read-back option values, then CreateFeature.  The
    obsolete InsertCutSwept5 under-removes ~0.4% of the groove volume vs
    the vendor's feature (measured on 91829A560 AND 94025A150); this path
    reproduces the vendor's authoring route.  (It failed on 91829A560 only
    for the BODY-SCOPED case -- single-body parts can use it.)"""
    from solidworks_mcp.adapters.solidworks.features import (
        _select_named_feature,
    )
    from _common import name_last_feature

    SW_FM_SWEEP_CUT = 18  # swFeatureNameID_e.swFmSweepCut
    model = adapter.currentModel
    fm = model.FeatureManager
    data = _early_bound(fm.CreateDefinition(SW_FM_SWEEP_CUT),
                        "ISweepFeatureData")
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, profile, 1, False):
        raise RuntimeError(f"cannot select sweep profile {profile!r} (mark 1)")
    if not _select_named_feature(adapter, path, 4, True):
        raise RuntimeError(f"cannot select sweep path {path!r} (mark 4)")
    # Vendor Cut-Sweep option set (read off their feature data).
    data.AlignWithEndFaces = True
    data.TwistControlType = 0       # swTwistControlFollowPath
    data.PathAlignmentType = 10     # swMinimumTwist
    data.Direction = -1
    data.MergeSmoothFaces = True
    data.MaintainTangency = False
    data.AdvancedSmoothing = False
    data.StartTangencyType = 1
    data.EndTangencyType = 1
    data.AutoSelect = True
    with _telemetry.span("feature.thread_sweep_cut_modern",
                         label=feature_name):
        swept = fm.CreateFeature(data)
    model.ClearSelection2(True)
    if swept is None:
        raise RuntimeError(f"CreateFeature (sweep cut) returned None for "
                           f"{feature_name}")
    name_last_feature(adapter, feature_name)
    return swept


def combine_union(adapter, feature_name: str = "BodyUnion"):
    """Vendor Combine: union every body back into one."""
    import pythoncom
    from win32com.client import VARIANT
    from _common import name_last_feature

    model = adapter.currentModel
    bl = bodies(adapter)
    if len(bl) < 2:
        raise RuntimeError(f"combine needs >=2 bodies, got {len(bl)}")
    model.ClearSelection2(True)
    comb = model.FeatureManager.InsertCombineFeature(
        SW_BODY_ADD, None,
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, bl),
    )
    if comb is None:
        raise RuntimeError("InsertCombineFeature (union) failed")
    name_last_feature(adapter, feature_name)
    return comb


def insert_helix(adapter, pitch_mm: float, revolutions: float, *,
                 clockwise: bool = True, reversed_dir: bool = False,
                 start_angle_rad: float, feature_name: str):
    """InsertHelix on the ACTIVE sketch (it consumes it)."""
    from _common import name_last_feature

    adapter.currentModel.InsertHelix(
        reversed_dir,
        clockwise,
        False, False,  # Tapered / Outward
        0,  # swHelixDefinedByPitchAndRevolution
        0.0,  # Height (derived)
        pitch_mm / 1000.0,
        revolutions,
        0.0,  # TaperAngle
        start_angle_rad,
    )
    name_last_feature(adapter, feature_name)


async def gate_and_save(adapter, part_no: str, truth: dict) -> dict:
    """Run the vendor ground-truth gates, save the replica + report + renders,
    then render the vendor part beside it.  Raises on any gate failure
    (after saving, so the failed model is on disk to inspect)."""
    v_mass = truth["mass"]
    v_vol = float(v_mass["volume_mm3"])
    v_surf = float(v_mass["surface_area_mm2"])
    v_com = [float(x) for x in v_mass["com_mm"]]
    v_faces = vendor_face_areas(truth)

    props = mass_properties(adapter)
    areas = face_areas(adapter)
    replica = OUT_DIR / f"{part_no}-replica.SLDPRT"
    report_path = OUT_DIR / f"{part_no}-replica-report.json"

    vol_tol = max(0.02, v_vol * 2e-4)
    surf_tol = max(0.10, v_surf * 5e-4)
    exact_multiset = len(v_faces) <= FACE_MULTISET_LIMIT

    # The dump reads COM in the VENDOR frame (its own axes); the replica is
    # authored head-up on Top, so map: replica (x, y, z) ~ vendor frame via
    # the builder-declared axis map in truth-space.  Builders author so the
    # replica COM y equals the vendor COM z minus the builder's declared
    # origin shift; each builder records that shift in adapter._mcm_com_map.
    com_map = getattr(adapter, "_mcm_com_map", None)
    exp_com = com_map(v_com) if com_map else v_com

    deltas = ([round(a - b, 4) for a, b in zip(areas, v_faces)]
              if len(areas) == len(v_faces) else None)
    top_k = sorted(areas)[-FACE_TOP_K:]
    v_top_k = sorted(v_faces)[-FACE_TOP_K:]
    report = {
        "part_no": part_no,
        "replica": str(replica),
        "vendor": str(MCMASTER_DIR / f"{part_no}.SLDPRT"),
        "volume_mm3": props["volume_mm3"],
        "vendor_volume_mm3": v_vol,
        "volume_delta": round(props["volume_mm3"] - v_vol, 4),
        "surface_mm2": props["surface_mm2"],
        "vendor_surface_mm2": v_surf,
        "surface_delta": round(props["surface_mm2"] - v_surf, 4),
        "com_mm": props["com_mm"],
        "vendor_com_mm": v_com,
        "expected_com_mm": exp_com,
        "face_count": len(areas),
        "vendor_face_count": len(v_faces),
        "face_gate": "multiset" if exact_multiset else f"count+top{FACE_TOP_K}",
        "face_areas": areas if exact_multiset else top_k,
        "vendor_face_areas": v_faces if exact_multiset else v_top_k,
        "face_area_deltas": deltas if exact_multiset else None,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _telemetry.info(f"report -> {report_path}")

    problems = []
    if abs(report["volume_delta"]) > vol_tol:
        problems.append(
            f"volume delta {report['volume_delta']:+.4f} mm^3 (tol {vol_tol:.4f})")
    if abs(report["surface_delta"]) > surf_tol:
        problems.append(
            f"surface delta {report['surface_delta']:+.4f} mm^2 (tol {surf_tol:.4f})")
    if len(areas) != len(v_faces):
        problems.append(f"face count {len(areas)} != vendor {len(v_faces)}")
    elif exact_multiset:
        face_tol = max(0.06, max(v_faces) * 1e-3)
        worst = max(abs(d) for d in deltas)
        if worst > face_tol:
            problems.append(
                f"face area max delta {worst:.4f} (tol {face_tol:.4f})")
    else:
        face_tol = max(0.06, max(v_faces) * 1e-3)
        worst = max(abs(a - b) for a, b in zip(top_k, v_top_k))
        if worst > face_tol:
            problems.append(
                f"top-{FACE_TOP_K} face area max delta {worst:.4f} "
                f"(tol {face_tol:.4f})")
    com = props["com_mm"]
    if com and exp_com and any(
            abs(a - b) > 0.02 for a, b in zip(com, exp_com)):
        problems.append(f"COM {com} != expected {exp_com}")

    # Save FIRST so a gate failure still leaves the model on disk to inspect.
    check(f"save -> {replica}", await adapter.save_file(str(replica.resolve())))
    artefacts = {"part": str(replica), "report": str(report_path)}
    artefacts.update(await export_views(adapter, f"{part_no}-replica"))

    if problems:
        raise RuntimeError(
            f"{part_no} replica differs from vendor: " + "; ".join(problems))
    _telemetry.success(
        f"{part_no} replica matches vendor: volume {props['volume_mm3']:.4f} "
        f"mm^3 (vendor {v_vol}), {len(areas)} faces "
        f"[{report['face_gate']} gate]")
    return artefacts


async def close_all(adapter):
    """Discard every open document (the vendor part is NEVER saved)."""
    closed = adapter._attempt(
        lambda: adapter.swApp.CloseAllDocuments(True), default=False)
    if not closed:
        raise RuntimeError("CloseAllDocuments failed")
    adapter.currentModel = None


async def render_vendor(adapter, part_no: str) -> dict[str, str]:
    """Open the vendor part read-only for the eyeball pair, render, close."""
    vendor = MCMASTER_DIR / f"{part_no}.SLDPRT"
    check(f"open vendor {part_no}", await adapter.open_model(str(vendor)))
    out = {f"vendor_{k}": p
           for k, p in (await export_views(adapter, f"{part_no}-vendor")).items()}
    await close_all(adapter)
    return out
