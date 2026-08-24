r"""Diagnostic: rebuild McMaster-Carr 91829A560 from scratch -- the re-author
half of "edit in the GUI, re-author in the script" for a part nobody scripted.

A PURE reverse-engineering of ``cad/references/mcmaster/91829A560.SLDPRT``
(slotted 18-8 SS precision shoulder screw): every number below was harvested
from the vendor model itself -- the dims/faces via ``diag_dump_part.py``
(``cad/out/reports/mcmaster-91829A560-dump2.json``) and the sketch geometry /
sweep options read live off the open vendor document -- nothing is imported
from the repo's part specs, and the vendor thread is cut FOR REAL (helical
sweep cut at the UN form), not simplified to a tap-drill envelope like the
shipped ``cone-pivot-screw``.

Vendor recipe, reproduced feature-for-feature (tree order):

1.  Base solid: head 9.525 x 4.7625 up from the under-head datum; shoulder
    6.35 x 6.35 and thread shank 4.826 x 9.525 down (the vendor models these
    as one revolve; stacked extrudes are the same solid).
2.  Thread-relief undercut (their Cut-Revolve1, Sketch5 read live): land
    DIA 3.3528 x 0.8636; the UPPER boundary is a R0.7366 QUARTER-FILLET
    (tangent to the land, radial at the shoulder end) -- not a 45-deg cone --
    and the lower boundary is the 45-deg flank rising to the thread major.
3.  Driver slot 1.524 wide x 1.905 deep across the full head.
4.  Helix (their Helix/Spiral2): seeded on the TIP plane, ascending, pitch
    1.058333 x 9 revs.
5.  Chamfers: head rim 0.309563 x 45 (the slot already split the rim -- two
    edges), thread start 0.43434 x 45.
6.  Split (their Split2 at Plane1): a transverse plane at the undercut land
    BOTTOM (junction - 1.6002) splits the body so the thread cut is scoped to
    the tail -- this is what keeps the sweep off the shoulder annulus and the
    undercut fillet, and it is load-bearing, not bookkeeping.
7.  Thread groove (their Cut-Sweep1, options read live: AlignWithEndFaces,
    FollowPath, PathAlignmentType=swMinimumTwist, Direction=-1): their
    Sketch10 cutter is the UN 60-deg V truncated to a P/8 root flat at
    r 1.7256 and capped at 15P/16 top width (their D1 = P dims only the
    construction sharp-V), positioned 7P/16 BELOW the tip in air at the
    path-start azimuth, scoped to the tail body.
8.  Combine (their Combine1) unions the bodies back.

Gates: per-step analytic volumes, then the vendor's own numbers -- volume
633.4188 mm^3, surface 630.1218 mm^2, COM, and the sorted 20-face area
multiset.  Output goes to ``cad/out/reference/`` (gitignored): the McMaster
file itself is (c) McMaster-Carr, reference-only; this replica exists to prove
the recipe was decoded, not to ship.

Run (SolidWorks already open)::

    uv run python cad\scripts\diagnostics\diag_build_91829A560.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    CAD_ROOT,
    REFERENCES_DIR,
    _early_bound,
    _read_member,
    add_line_chain,
    check,
    define_centered_rectangle,
    define_circle,
    run_build,
    volume_check,
)

OUT_DIR = CAD_ROOT / "out" / "reference"
REPLICA = OUT_DIR / "91829A560-replica.SLDPRT"
REPORT = OUT_DIR / "91829A560-replica-report.json"
VENDOR = REFERENCES_DIR / "mcmaster" / "91829A560.SLDPRT"

# --- vendor dims (all mm/deg, straight from the harvest) -------------------
HEAD_DIA = 9.525  # Head Diameter@Sketch1
HEAD_T = 4.7625  # Head Height@Sketch1
SHOULDER_DIA = 6.35  # Shoulder Diameter@Sketch1
SHOULDER_LEN = 6.35  # Shoulder Length@Sketch1
THREAD_MAJOR = 4.826  # Screw Size Decimal Equivalent@Sketch1
THREAD_LEN = 9.525  # Thread Length@Sketch1
UNDERHEAD_LEN = SHOULDER_LEN + THREAD_LEN  # 15.875
SLOT_W = 1.524  # D1@Sketch8
SLOT_D = 1.905  # D1@Cut-Extrude2
HEAD_CHAMFER = 0.309563  # D1@Chamfer1 (45 deg)
TIP_CHAMFER = 0.43434  # D1@Chamfer2 (45 deg)
UC_LAND_DIA = 3.3528  # CADA@Sketch5 (diametric)
UC_W = 1.6002  # CADB@Sketch5 (fillet + land; also the split-plane offset)
PITCH = 1.058333  # Pitch@Helix/Spiral2 (#10-24: 25.4/24)
REVS = 9.0  # 9000@Helix/Spiral2

# Undercut (vendor Sketch5): R-UC_FILLET quarter-round upper boundary tangent
# to the land, then the land, then the 45-deg lower flank up to the major.
UC_LAND_R = UC_LAND_DIA / 2.0  # 1.6764
UC_FILLET = THREAD_MAJOR / 2.0 - UC_LAND_R  # 0.7366 (fillet R == flank rise)
UC_LAND = UC_W - UC_FILLET  # 0.8636
UC_SPAN = UC_LAND + 2.0 * UC_FILLET  # 2.3368 (junction -> flank@major)

# Thread cutter (vendor Sketch10): UN form.  H is the sharp-V height; the
# groove is the V truncated to a P/8 flat at the root and capped at a 15P/16
# top width (the vendor's D1 = P dims the CONSTRUCTION sharp-V only).
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = THREAD_MAJOR / 2.0 - 0.75 * H_SHARP  # 1.725585 (vendor: 1.7256)
ROOT_FLAT = PITCH / 8.0  # 0.132292 == vendor D2@Sketch10
CUT_TOP_W = 15.0 * PITCH / 16.0  # 0.992187 (vendor: 0.9922)
CUT_TOP_R = ROOT_R + (CUT_TOP_W - ROOT_FLAT) / 2.0 * math.sqrt(3.0)  # 2.470292
CUT_CENTRE_Y = -UNDERHEAD_LEN - 7.0 * PITCH / 16.0  # -16.338 (vendor, in air)

# --- vendor ground truth (mass + 20-face B-rep) ----------------------------
VENDOR_VOLUME = 633.4188
VENDOR_SURFACE = 630.1218
VENDOR_COM_Y = 3.470949 - 5.55625  # vendor frame -> own (y = vendor z - 5.55625)
VENDOR_FACE_AREAS = sorted([
    11.5156, 3.0016, 12.7728, 6.8007, 10.6716, 71.9601, 71.9610, 24.3938,
    128.3643, 39.5865, 126.6769, 13.3771, 24.3938, 14.1333, 9.0964, 17.8142,
    17.8142, 14.4539, 5.6670, 5.6670,
])

SW_BODY_ADD = 15903  # swBodyOperationType_e.SWBODYADD
SW_FM_SWEEP_CUT = 18  # swFeatureNameID_e.swFmSweepCut


def _slot_strip_area(r: float, w: float) -> float:
    """Plan area of a width-w strip across a radius-r circle (exact)."""
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


def _slotted_rim_chamfer_volume(r: float, chamfer: float, slot_w: float) -> float:
    """45-degree rim-chamfer volume remaining after a centered through-slot."""
    centroid_radius = r - chamfer / 3.0
    slot_half = slot_w / 2.0
    if not 0.0 < slot_half < centroid_radius:
        raise ValueError("slot must remove less than the full chamfer rim")
    full_volume = math.pi * chamfer**2 * centroid_radius
    missing_fraction = 2.0 * math.asin(slot_half / centroid_radius) / math.pi
    return full_volume * (1.0 - missing_fraction)


def _undercut_volume(major_r: float, land_r: float, land_w: float) -> float:
    """Vendor undercut: quarter-fillet + land + one 45-deg flank, revolved.

    Fillet band (height R = major_r - land_r, boundary radius
    ``major_r - sqrt(R^2 - t^2)``):  pi * ( (pi/2)*major_r*R^2 - (2/3)*R^3 ).
    """
    rise = major_r - land_r
    v_fillet = math.pi * (
        (math.pi / 2.0) * major_r * rise**2 - (2.0 / 3.0) * rise**3
    )
    v_land = math.pi * (major_r**2 - land_r**2) * land_w
    v_flank = math.pi * (major_r**2 * rise - (major_r**3 - land_r**3) / 3.0)
    return v_fillet + v_land + v_flank


def _mass_properties(adapter) -> dict:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    ext = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    mp = ext.CreateMassProperty()
    return {
        "volume_mm3": round(float(_read_member(mp, "Volume")) * 1e9, 4),
        "surface_mm2": round(float(_read_member(mp, "SurfaceArea")) * 1e6, 4),
        "com_mm": [round(float(v) * 1000.0, 6)
                   for v in (_read_member(mp, "CenterOfMass") or [])],
    }


def _bodies(adapter) -> list:
    part = _early_bound(adapter.currentModel, "IPartDoc")
    return list(part.GetBodies2(0, False) or [])


def _face_areas(adapter) -> list[float]:
    bl = _bodies(adapter)
    if len(bl) != 1:
        raise RuntimeError(f"replica has {len(bl)} bodies, expected 1")
    body = _early_bound(bl[0], "IBody2")
    areas = []
    for f in body.GetFaces() or []:
        f = _early_bound(f, "IFace2")
        areas.append(round(float(_read_member(f, "GetArea")) * 1e6, 4))
    return sorted(areas)


async def _export_views(adapter, stem: str) -> dict[str, str]:
    out = {}
    for view in ("front", "isometric"):
        img = (OUT_DIR / f"{stem}_{view}.png").resolve()
        check(f"export_image {stem} {view}", await adapter.export_image({
            "file_path": str(img), "format_type": "png",
            "width": 1600, "height": 1000, "view_orientation": view,
        }))
        out[view] = str(img)
    return out


def _offset_plane(adapter, name: str, offset_mm: float):
    """Reference plane parallel to Top at (signed) offset_mm; returns name."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "Top Plane", "PLANE", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("cannot select Top Plane")
    flags = 8 | (256 if offset_mm < 0 else 0)  # Distance | OptionFlip
    plane = model.FeatureManager.InsertRefPlane(
        flags, abs(offset_mm) / 1000.0, 0, 0, 0, 0
    )
    if plane is None:
        raise RuntimeError(f"InsertRefPlane failed for {name}")
    plane.Name = name
    model.ClearSelection2(True)
    return name


async def build(adapter) -> dict[str, str]:
    import pythoncom
    from win32com.client import VARIANT
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from _common import extrude_at_offset, name_last_feature

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    check("create_part", await adapter.create_part())
    model = adapter.currentModel

    # --- base solid ----------------------------------------------------------
    check("create_sketch head", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    check("extrude head",
          await adapter.create_extrusion(ExtrusionParameters(depth=HEAD_T)))
    v = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_T
    volume = await volume_check(adapter, "head", v, 0.005 * v)

    check("create_sketch shoulder", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, SHOULDER_DIA / 2.0, "shoulder")
    check("exit_sketch shoulder", await adapter.exit_sketch())
    name_last_feature(adapter, "ShoulderProfile")
    extrude_at_offset(adapter, SHOULDER_LEN, -SHOULDER_LEN)
    v = math.pi * (SHOULDER_DIA / 2.0) ** 2 * SHOULDER_LEN
    volume = await volume_check(adapter, "shoulder", volume + v, 0.005 * v)

    check("create_sketch shank", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, THREAD_MAJOR / 2.0, "thread shank")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    extrude_at_offset(adapter, THREAD_LEN, -UNDERHEAD_LEN)
    v = math.pi * (THREAD_MAJOR / 2.0) ** 2 * THREAD_LEN
    volume = await volume_check(adapter, "thread shank", volume + v, 0.005 * v)

    # --- thread-relief undercut (vendor Cut-Revolve1: fillet + land + flank) -
    major_r = THREAD_MAJOR / 2.0
    y_jct = -SHOULDER_LEN
    y_land_top = y_jct - UC_FILLET
    y_land_bot = y_jct - UC_W
    check("create_sketch undercut", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    axis = sk_mgr.CreateCenterLine(
        0.0, y_jct / 1000.0, 0.0, 0.0, -UNDERHEAD_LEN / 1000.0, 0.0)
    if axis is None:
        raise RuntimeError("undercut: CreateCenterLine failed")
    prev_db = bool(sk_mgr.AddToDB)
    sk_mgr.AddToDB = True
    try:
        # quarter-fillet from the junction@major down to the land (tangent)
        arc = sk_mgr.CreateArc(
            major_r / 1000.0, y_land_top / 1000.0, 0.0,   # centre
            major_r / 1000.0, y_jct / 1000.0, 0.0,        # start (junction)
            UC_LAND_R / 1000.0, y_land_top / 1000.0, 0.0, # end (land top)
            1,
        )
        if arc is None:
            raise RuntimeError("undercut: fillet arc failed")
        await add_line_chain(adapter, [
            (UC_LAND_R, y_land_top),
            (UC_LAND_R, y_land_bot),
            (SHOULDER_DIA / 2.0, y_land_bot - (SHOULDER_DIA / 2.0 - UC_LAND_R)),
            (SHOULDER_DIA / 2.0, y_jct),
            (major_r, y_jct),
        ], close=False)
    finally:
        sk_mgr.AddToDB = prev_db
    check("exit_sketch undercut", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadReliefProfile")
    check("revolve-cut undercut", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=True)))
    name_last_feature(adapter, "ThreadRelief")
    v = _undercut_volume(major_r, UC_LAND_R, UC_LAND)
    volume = await volume_check(adapter, "thread relief", volume - v, 0.01 * v)

    # --- driver slot (vendor Cut-Extrude2) ------------------------------------
    _offset_plane(adapter, "HeadTop", HEAD_T)
    check("create_sketch slot", await adapter.create_sketch("HeadTop"))
    await define_centered_rectangle(
        adapter, HEAD_DIA / 2.0 + 1.0, SLOT_W / 2.0, "slot")
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check("cut slot", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=SLOT_D)))
    name_last_feature(adapter, "DriverSlot")
    v = _slot_strip_area(HEAD_DIA / 2.0, SLOT_W) * SLOT_D
    volume = await volume_check(adapter, "driver slot", volume - v, 0.02 * v)

    # --- helix (vendor Helix/Spiral2: tip-seeded, ascending, 9 revs) ---------
    _offset_plane(adapter, "TipPlane", -UNDERHEAD_LEN)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    seed = adapter.currentSketchManager.CreateCircleByRadius(
        0.0, 0.0, 0.0, major_r / 1000.0)
    if seed is None:
        raise RuntimeError("helix seed circle failed")
    # InsertHelix consumes the ACTIVE sketch.  Ascending from the tip toward
    # the head; start azimuth +X so the start lies on the Front plane where
    # the cutter is drawn (the flipped offset plane maps ang pi/2 -> +X).
    # Clockwised=False IS the vendor's right-hand thread in this frame:
    # their tip plane carries normal -z with reverse=True, ours +y with
    # reverse=False, so the clockwise flag inverts (proven on 93075A194,
    # where True left a mirror thread reading +0.0575 mm^3 at every phase).
    model.InsertHelix(
        False,  # Reversed
        False,  # Clockwised (inverted frame -- see note above)
        False, False,  # Tapered / Outward
        0,  # swHelixDefinedByPitchAndRevolution
        0.0,  # Height (derived)
        PITCH / 1000.0,
        REVS,
        0.0,  # TaperAngle
        math.pi / 2.0,  # Startangle
    )
    name_last_feature(adapter, "ThreadHelix")

    # --- chamfers (vendor order: after the helix, before the thread cut) -----
    head_r = HEAD_DIA / 2.0
    check("chamfer head rim", await adapter.add_chamfer(
        HEAD_CHAMFER,
        [[0.0, HEAD_T, head_r], [0.0, HEAD_T, -head_r]]))
    name_last_feature(adapter, "HeadChamfer")
    v = _slotted_rim_chamfer_volume(head_r, HEAD_CHAMFER, SLOT_W)
    volume = await volume_check(adapter, "head chamfer", volume - v, 0.03 * v)

    check("chamfer thread start", await adapter.add_chamfer(
        TIP_CHAMFER, [[major_r, -UNDERHEAD_LEN, 0.0]]))
    name_last_feature(adapter, "TipChamfer")
    v = math.pi * TIP_CHAMFER**2 * (major_r - TIP_CHAMFER / 3.0)
    volume = await volume_check(adapter, "tip chamfer", volume - v, 0.02 * v)

    # --- split at the land bottom (vendor Split2 @ Plane1) --------------------
    # Scopes the thread cut to the tail body: the sweep physically cannot
    # touch the shoulder annulus or the undercut fillet above this plane.
    _offset_plane(adapter, "SplitPlane", y_land_bot)
    fm = model.FeatureManager
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "SplitPlane", "PLANE", 0, 0, 0, True, 0, null_callout(), 0
    ):
        raise RuntimeError("cannot select SplitPlane for the split")
    pre = fm.PreSplitBody2
    if callable(pre):
        pre = pre()
    if not pre or len(pre) != 2:
        raise RuntimeError(f"PreSplitBody2 returned {pre!r}, expected 2 bodies")
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
    name_last_feature(adapter, "TailSplit")
    tail_name = None
    for b in _bodies(adapter):
        b2 = _early_bound(b, "IBody2")
        box = [float(x) * 1000.0 for x in (b2.GetBodyBox() or [])]
        if box and box[1] < -10.0:
            tail_name = str(_read_member(b2, "Name"))
    if not tail_name:
        raise RuntimeError("split produced no tail body")
    _telemetry.info(f"tail body: {tail_name}")

    # --- thread groove (vendor Cut-Sweep1) ------------------------------------
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    await add_line_chain(adapter, [
        (CUT_TOP_R, CUT_CENTRE_Y + CUT_TOP_W / 2.0),
        (ROOT_R, CUT_CENTRE_Y + ROOT_FLAT / 2.0),
        (ROOT_R, CUT_CENTRE_Y - ROOT_FLAT / 2.0),
        (CUT_TOP_R, CUT_CENTRE_Y - CUT_TOP_W / 2.0),
    ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")

    from solidworks_mcp.adapters.solidworks.features import (
        _flag_feature_methods,
        _select_named_feature,
    )
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, "ThreadCutter", 1, False):
        raise RuntimeError("cannot select thread cutter profile (mark 1)")
    if not _select_named_feature(adapter, "ThreadHelix", 4, True):
        raise RuntimeError("cannot select thread helix path (mark 4)")
    if not model.Extension.SelectByID2(
        tail_name, "SOLIDBODY", 0, 0, 0, True, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select tail body {tail_name!r} for scope")
    feature_manager = _flag_feature_methods(
        model.FeatureManager, "IFeatureManager", "InsertCutSwept5")
    with _telemetry.span("feature.thread_sweep_cut"):
        swept = feature_manager.InsertCutSwept5(
            False,  # Propagate
            True,   # Alignment (vendor AlignWithEndFaces=True)
            0,      # TwistCtrlOption: swTwistControlFollowPath
            False,  # KeepTangency
            False,  # BAdvancedSmoothing
            0, 0,   # Start/EndMatchingType: swTangencyNone
            False, 0.0, 0.0, 0,  # thin body
            10,     # PathAlign: swMinimumTwist (vendor PathAlignmentType)
            True,   # UseFeatScope
            False,  # UseAutoSelect: the tail body is selected above
            0.0,    # TwistAngle
            True,   # BMergeSmoothFaces
            False, False, False,  # assembly scope
            False, 0.0,  # CircularProfile
            -1,     # Direction (vendor)
        )
    model.ClearSelection2(True)
    if swept is None:
        raise RuntimeError("InsertCutSwept5 returned None -- thread cut failed")
    name_last_feature(adapter, "ThreadGroove")

    # --- combine (vendor Combine1) --------------------------------------------
    bl = _bodies(adapter)
    if len(bl) != 2:
        raise RuntimeError(f"expected 2 bodies before combine, got {len(bl)}")
    model.ClearSelection2(True)
    comb = fm.InsertCombineFeature(
        SW_BODY_ADD,
        None,
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, bl),
    )
    if comb is None:
        raise RuntimeError("InsertCombineFeature (union) failed")
    name_last_feature(adapter, "ThreadedUnion")

    # --- vendor ground-truth gates --------------------------------------------
    props = _mass_properties(adapter)
    areas = _face_areas(adapter)
    deltas = ([round(a - b, 4) for a, b in zip(areas, VENDOR_FACE_AREAS)]
              if len(areas) == len(VENDOR_FACE_AREAS) else None)
    report = {
        "replica": str(REPLICA),
        "vendor": str(VENDOR),
        "volume_mm3": props["volume_mm3"],
        "vendor_volume_mm3": VENDOR_VOLUME,
        "volume_delta": round(props["volume_mm3"] - VENDOR_VOLUME, 4),
        "surface_mm2": props["surface_mm2"],
        "vendor_surface_mm2": VENDOR_SURFACE,
        "surface_delta": round(props["surface_mm2"] - VENDOR_SURFACE, 4),
        "com_mm": props["com_mm"],
        "vendor_com_y_own_frame": round(VENDOR_COM_Y, 6),
        "face_count": len(areas),
        "face_areas": areas,
        "vendor_face_areas": VENDOR_FACE_AREAS,
        "face_area_deltas": deltas,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _telemetry.info(f"report -> {REPORT}")

    problems = []
    if abs(report["volume_delta"]) > 0.05:
        problems.append(f"volume delta {report['volume_delta']:+.4f} mm^3")
    if abs(report["surface_delta"]) > 0.10:
        problems.append(f"surface delta {report['surface_delta']:+.4f} mm^2")
    if len(areas) != len(VENDOR_FACE_AREAS):
        problems.append(
            f"face count {len(areas)} != vendor {len(VENDOR_FACE_AREAS)}")
    elif deltas and max(abs(d) for d in deltas) > 0.06:
        problems.append(f"face area max delta {max(abs(d) for d in deltas):.4f}")
    com = props["com_mm"]
    if com and (abs(com[0]) > 0.01 or abs(com[2]) > 0.01
                or abs(com[1] - VENDOR_COM_Y) > 0.02):
        problems.append(f"COM {com} != (0, {VENDOR_COM_Y:.6f}, 0)")

    # Save FIRST so a gate failure still leaves the model on disk to inspect.
    check(f"save -> {REPLICA}", await adapter.save_file(str(REPLICA.resolve())))
    artefacts = {"part": str(REPLICA), "report": str(REPORT)}
    artefacts.update(await _export_views(adapter, "91829A560-replica"))

    if problems:
        raise RuntimeError("replica differs from vendor: " + "; ".join(problems))
    _telemetry.success(
        f"replica matches vendor: volume {props['volume_mm3']:.4f} mm^3 "
        f"(vendor {VENDOR_VOLUME}), 20-face multiset max delta "
        f"{max(abs(d) for d in deltas):.4f} mm^2")

    # Vendor renders beside the replica's -- the handedness witness pair.
    closed = adapter._attempt(
        lambda: adapter.swApp.CloseAllDocuments(True), default=False)
    if not closed:
        raise RuntimeError("failed to close replica before vendor render")
    adapter.currentModel = None
    check("open vendor part", await adapter.open_model(str(VENDOR)))
    artefacts.update({f"vendor_{k}": p
                      for k, p in (await _export_views(adapter, "91829A560-vendor")).items()})
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
