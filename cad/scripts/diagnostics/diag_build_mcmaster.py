r"""Diagnostic: rebuild the McMaster-Carr reference fasteners from scratch --
the fleet-wide successor of ``diag_build_91829A560.py`` (which stays as the
validated single-part original).

Every replica is a PURE reverse-engineering of its vendor model in
``cad/references/mcmaster/``: all numbers come from that part's harvest JSON
(``diag_dump_part.py`` -> ``cad/out/reports/mcmaster-<part>-dump.json``) or
were read live off the open vendor document -- nothing is imported from the
repo's part specs.  Gates run against the vendor's own mass properties and
face-area multiset, loaded from the same harvest (see
``diag_mcmaster_lib.gate_and_save``).

Run (SolidWorks already open)::

    uv run python cad\scripts\diagnostics\diag_build_mcmaster.py 90126A211
    uv run python cad\scripts\diagnostics\diag_build_mcmaster.py --all

Output (replica .SLDPRT + report JSON + render pairs) goes to the gitignored
``cad/out/reference/``.  The McMaster files are (c) McMaster-Carr,
reference-only: opened read-only for the render pair, never saved.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    check,
    define_circle,
    extrude_at_offset,
    name_last_feature,
    run_build,
    volume_check,
)
from diag_mcmaster_lib import (  # noqa: E402
    bodies,
    close_all,
    gate_and_save,
    insert_helix,
    offset_plane,
    render_vendor,
    thread_sweep_cut,
    thread_sweep_cut_modern,
    vendor_truth,
)


def _rev_frustum(h: float, r1: float, r2: float) -> float:
    """Volume of a revolved cone frustum (full cone when one radius is 0)."""
    return math.pi / 3.0 * h * (r1 * r1 + r1 * r2 + r2 * r2)


def _strip_area(r: float, w: float) -> float:
    """Plan area of a width-w strip across a radius-r circle (exact)."""
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))

async def _asymmetric_fillet(adapter, edge_points_mm, r1_mm: float,
                             r2_mm: float, conic_rho: float,
                             feature_name: str, reverse: bool = False):
    """Constant asymmetric conic fillet: author a plain symmetric fillet
    through the adapter's proven path, then EDIT its definition via
    ISimpleFilletFeatureData2 (the same API the dump reads).

    Direct FeatureFillet3 authoring proved non-deterministic on this
    build -- runs with identical arguments produced different leg
    orientations (the positional call partially inherits SolidWorks
    session defaults), so the replica goes create-then-modify instead."""
    from _common import _early_bound, _feature_by_name

    check(f"fillet base {feature_name}", await adapter.add_fillet(
        r1_mm, [list(p) for p in edge_points_mm]))
    name_last_feature(adapter, feature_name)
    model = adapter.currentModel
    feat = _feature_by_name(adapter, feature_name)
    data = _early_bound(feat.GetDefinition(), "ISimpleFilletFeatureData2")
    if not data.AccessSelections(model, None):
        raise RuntimeError(f"AccessSelections failed for {feature_name}")
    data.AsymmetricFillet = True
    data.DefaultRadius = r1_mm / 1000.0
    data.DefaultDistance = r2_mm / 1000.0
    data.ConicTypeForCrossSectionProfile = 1  # swFeatureFilletConicRho
    data.DefaultConicRhoOrRadius = conic_rho
    if reverse:
        # Indexed property (WhichFaceList) -- flips Direction 1/2 for the
        # feature's face list; single-edge features use list 0.
        data.SetReverseFaceNormal(0, True)
    if not feat.ModifyDefinition(data, model, None):
        raise RuntimeError(f"ModifyDefinition failed for {feature_name}")
    return feat


# --------------------------------------------------------------------------
# 90126A211 -- zinc-plated steel SAE washer for 1/2" screws
# Vendor tree: annulus sketch -> midplane Boss-Extrude1 -> asymmetric rim
# fillet (Fillet1: D1 0.34671 radial x D2 0.173355 axial, equations
# D2 = thickness*0.07, D1 = D2*2).
# --------------------------------------------------------------------------
W_OD = 26.9748  # OD@Sketch1 (diametric)
W_ID = 13.4874  # ID@Sketch1 (diametric)
W_T = 2.4765    # Thickness Range@Sketch2
W_F1 = 0.34671  # D1@Fillet1 (radial leg)
W_F2 = 0.173355  # D2@Fillet1 (axial leg)
W_RHO = 0.65    # Fillet1 conic rho (conic_type=1 in the harvest)


async def build_90126A211(adapter, truth):
    check("create_sketch annulus", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, W_OD / 2.0, "washer OD")
    await define_circle(adapter, 0.0, 0.0, W_ID / 2.0, "washer ID")
    check("exit_sketch annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "AnnulusProfile")
    # MIDPLANE extrude like the vendor (end_cond 6) -- not blind from an
    # offset plane: a blind extrude's start-face edges orient opposite the
    # end-face ones, which flipped the asymmetric fillet's Direction 1 on
    # the bottom rim (the vendor needs no per-edge reverse, and with the
    # midplane body neither do we).
    from solidworks_mcp.adapters.base import ExtrusionParameters
    check("extrude washer", await adapter.create_extrusion(
        ExtrusionParameters(depth=W_T, both_directions=True)))
    name_last_feature(adapter, "WasherBody")
    v = math.pi * ((W_OD / 2.0) ** 2 - (W_ID / 2.0) ** 2) * W_T
    await volume_check(adapter, "washer annulus", v, 0.005 * v)

    # The four rim edges in one feature, like the vendor's Fillet1 (read
    # off the model: asymmetric=true, D1 0.34671 / D2 0.173355, conic-rho
    # profile rho=0.65; leg layout from the vendor faces: LONG leg radial
    # across the flats, SHORT leg axial down the cylinders).
    # The vendor's single Fillet1 reads no per-edge reverse, but on OUR
    # body the bottom edges' Direction 1 lands on the cylinder instead of
    # the flat (midplane vs blind extrude made no difference), and every
    # reverse knob probed inert (swFeatureFilletReverseFace1Dir,
    # SetReverseFaceNormal).  So: one feature per edge, with the D1/D2
    # values swapped on the bottom pair -- geometrically identical to the
    # vendor's one feature.
    h = W_T / 2.0
    for label, pt, r1, r2 in (
        ("RimFilletODTop", (W_OD / 2.0, h, 0.0), W_F2, W_F1),
        ("RimFilletODBot", (W_OD / 2.0, -h, 0.0), W_F1, W_F2),
        ("RimFilletIDTop", (W_ID / 2.0, h, 0.0), W_F1, W_F2),
        ("RimFilletIDBot", (W_ID / 2.0, -h, 0.0), W_F2, W_F1),
    ):
        await _asymmetric_fillet(adapter, [pt], r1, r2, W_RHO, label)

    # Replica frame: extrude axis = model Y, vendor frame: axis = Z.
    adapter._mcm_com_map = lambda v: [v[0], v[2], v[1]]


# --------------------------------------------------------------------------
# 94025A150 -- 18-8 SS slotted cup-tip set screw, 5/16"-18 x 1/2"
# Vendor tree: through-axis revolve profile (integral tip cone + cup cone +
# slot-end chamfer) -> slot Cut-Extrude (ThroughAllBoth) -> helix (seeded at
# the cup tip, height L+..., start angle 90 deg) -> thread Cut-Sweep (UN
# cutter capped at 15P/16, centred 7P/16 past the slot-end face in air,
# scoped to the body; no Split -- the cutter never crosses other geometry).
# Frame: replica axial = +y with the SLOT end up (vendor axial = z, cup at
# +z; map my (x,y,z) = (vendor y, -vendor z, vendor x)).
# --------------------------------------------------------------------------
SS_MAJOR_R = 3.9751       # Screw Size Decimal Equivalent@Sketch1 / 2
SS_LEN = 12.7             # Length@Sketch1 (full, slot face to cup rim)
SS_HALF = SS_LEN / 2.0    # vendor origin sits mid-length; mine too
SS_PITCH = 1.411111       # Pitch@Sketch1 (5/16-18: 25.4/18)
SS_REVS = 11.0            # vendor 10 from the face; +1 lead-in rev in air
SS_CHAM_R = 3.516828      # slot-end rim chamfer inner radius (Sketch2)
SS_CHAM_H = 6.35 - 6.029115  # its axial extent (0.320885)
SS_TIP_R = 1.98755        # tip cone end radius = cup rim radius (Sketch2)
SS_CONE_Y = 4.36245       # tip cone start / cup apex |y| (Sketch2)
SS_SLOT_W = 1.325033      # D3@Sketch1 (slot width)
SS_SLOT_D = 1.411111      # Drive Depth@Sketch1 (slot depth)
# Thread cutter (vendor Sketch7, exact): UN V capped at 15P/16, root flat
# P/8, centred 7P/16 past the slot-end face in air.
SS_CUT_TOP_R = 4.051479
SS_CUT_TOP_W = 1.322917   # 15P/16
SS_CUT_ROOT_R = 3.058556  # major_r - 0.75 * (P*sqrt(3)/2)
SS_CUT_ROOT_W = 0.176389  # P/8
SS_CUT_CY = SS_HALF + SS_PITCH + 7.0 * SS_PITCH / 16.0  # 7P/16 past the raised start


async def build_94025A150(adapter, truth):
    from _common import add_line_chain
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    # --- revolve profile (vendor Sketch2 mapped (r, y) = (y_v, -x_v)) -----
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    axis = sk_mgr.CreateCenterLine(0.0, SS_HALF / 1000.0, 0.0,
                                   0.0, -SS_HALF / 1000.0, 0.0)
    if axis is None:
        raise RuntimeError("set-screw profile: CreateCenterLine failed")
    await add_line_chain(adapter, [
        (SS_CHAM_R, SS_HALF),                    # slot-end rim
        (SS_MAJOR_R, SS_HALF - SS_CHAM_H),       # chamfer -> OD
        (SS_MAJOR_R, -SS_CONE_Y),                # OD -> tip cone
        (SS_TIP_R, -SS_HALF),                    # tip cone end (cup rim)
        (0.0, -SS_CONE_Y),                       # cup cone to the axis
        (0.0, SS_HALF),                          # axis
    ])
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Body")
    v = (_rev_frustum(SS_CHAM_H, SS_MAJOR_R, SS_CHAM_R)
         + math.pi * SS_MAJOR_R ** 2 * (SS_LEN - SS_CHAM_H - (SS_HALF - SS_CONE_Y))
         + _rev_frustum(SS_HALF - SS_CONE_Y, SS_MAJOR_R, SS_TIP_R)
         - _rev_frustum(SS_HALF - SS_CONE_Y, SS_TIP_R, 0.0))
    volume = await volume_check(adapter, "revolved body", v, 0.005 * v)

    # --- driver slot (vendor Cut-Extrude1: ThroughAllBoth) ----------------
    check("create_sketch slot", await adapter.create_sketch("Front"))
    await add_line_chain(adapter, [
        (-SS_SLOT_W / 2.0, SS_HALF),
        (SS_SLOT_W / 2.0, SS_HALF),
        (SS_SLOT_W / 2.0, SS_HALF - SS_SLOT_D),
        (-SS_SLOT_W / 2.0, SS_HALF - SS_SLOT_D),
    ])
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    # Vendor end condition is ThroughAllBoth, but the adapter's cut path
    # passes Sd=True for ThroughAll (single-direction), so a midplane
    # blind cut deeper than the diameter stands in -- same geometry.
    check("cut slot", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=12.0, both_directions=True)))
    name_last_feature(adapter, "DriverSlot")
    # Slot volume: strip across the section, integrated over the chamfer
    # taper (the slot depth 1.411 reaches into the chamfer band 0.321).
    steps = 200
    v_slot = 0.0
    for i in range(steps):
        y = SS_HALF - SS_SLOT_D * (i + 0.5) / steps
        r = (SS_MAJOR_R if y <= SS_HALF - SS_CHAM_H else
             SS_MAJOR_R + (SS_CHAM_R - SS_MAJOR_R)
             * (y - (SS_HALF - SS_CHAM_H)) / SS_CHAM_H)
        v_slot += _strip_area(r, SS_SLOT_W) * SS_SLOT_D / steps
    volume = await volume_check(adapter, "driver slot", volume - v_slot,
                                0.02 * v_slot)

    # --- helix ------------------------------------------------------------
    # Seeded AT the slot face, descending 10 revs to one pitch PAST the
    # cup rim (height 14.111 = L + P; the overrun fades the groove out
    # over the cup cone).  The cutter sits 7P/16 ABOVE the path start in
    # air -- the proven 91829A560 configuration; with the cutter at the
    # path's FAR end instead, InsertCutSwept5 returns None.
    offset_plane(adapter, "ThreadTopPlane", SS_HALF + SS_PITCH)
    check("create_sketch helix seed",
          await adapter.create_sketch("ThreadTopPlane"))
    seed = adapter.currentSketchManager.CreateCircleByRadius(
        0.0, 0.0, 0.0, SS_MAJOR_R / 1000.0)
    if seed is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, SS_PITCH, SS_REVS, clockwise=True,
                 reversed_dir=True, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    # --- thread groove (vendor Cut-Sweep1, cutter coords exact) -----------
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    await add_line_chain(adapter, [
        (SS_CUT_TOP_R, SS_CUT_CY + SS_CUT_TOP_W / 2.0),
        (SS_CUT_ROOT_R, SS_CUT_CY + SS_CUT_ROOT_W / 2.0),
        (SS_CUT_ROOT_R, SS_CUT_CY - SS_CUT_ROOT_W / 2.0),
        (SS_CUT_TOP_R, SS_CUT_CY - SS_CUT_TOP_W / 2.0),
    ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    bl = bodies(adapter)
    if len(bl) != 1:
        raise RuntimeError(f"expected 1 body before thread cut, got {len(bl)}")
    from _common import _early_bound, _read_member
    body_name = str(_read_member(_early_bound(bl[0], "IBody2"), "Name"))
    thread_sweep_cut_modern(adapter, "ThreadCutter", "ThreadHelix",
                            "ThreadGroove")

    # Vendor slot end is +z in their frame (COM-verified: the cup end
    # loses ~49 mm^3 to the cone+cup, so mass biases toward the slot).
    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


# --------------------------------------------------------------------------
# 90280A* -- steel narrow fillister head slotted screws (5 sizes, one
# parametric recipe: the vendor drives every derived number off 5 named
# dims via equations, reproduced here):
#   slot width = HeadDia*0.135, slot depth = width*1.5 (from the dome apex)
#   head cylinder band = HeadHeight*0.8; dome = spherical cap (centre on
#     the axis) through the apex and the head rim -- fully derived
#   tip chamfer = 45 deg x 0.7P (tip face radius = major_r - 0.7P)
#   helix = under-head junction to P past the tip (revs = L/P + 1)
#   cutter (fractions of P, from their solved Sketch6): root flat at
#     r = major - 0.75H spanning y 3P/8..P/2; left flank tops out at
#     y 15P/16, right flank at y -P/32; 30-deg flanks.  The cutter
#     overlaps the HEAD region in air -- hence the vendor's Split before
#     the sweep, scoping the cut to the shank body.
#   runout boss: r = major circle at the junction, 30-deg draft, P/2 deep
#     (re-merges the split bodies); junction fillet r = P/10.
# Frame: head UP, under-head junction at y = 0 (the stock Top Plane plays
# the vendor Plane1's three roles: split plane, helix seed, runout).
# --------------------------------------------------------------------------
FILLISTER_SIZES = {
    # part:        (major dia, length, head height, head dia, pitch)
    "90280A108": (2.8448, 9.525, 2.7178, 4.6482, 0.635),
    "90280A194": (4.1656, 12.7, 3.9624, 6.858, 0.79375),
    "90280A196": (4.1656, 15.875, 3.9624, 6.858, 0.79375),
    "90280A199": (4.1656, 25.4, 3.9624, 6.858, 0.79375),
    "90280A201": (4.1656, 31.75, 3.9624, 6.858, 0.79375),
}


def _spherical_cap_volume(r_rim: float, h: float) -> float:
    """Volume of a spherical cap of rim radius r_rim and height h."""
    return math.pi * h * (3.0 * r_rim * r_rim + h * h) / 6.0


async def _build_fillister(adapter, part_no: str):
    from _common import add_line_chain
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters
    from diag_mcmaster_lib import no_sketch_inference, split_at_plane

    major_d, length, hh, hd, pitch = FILLISTER_SIZES[part_no]
    major_r = major_d / 2.0
    head_r = hd / 2.0
    band = hh * 0.8            # head cylinder height
    dome_h = hh - band         # spherical-cap height
    slot_w = hd * 0.135
    slot_d = slot_w * 1.5
    tip_ch = 0.7 * pitch
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    revs = length / pitch + 1.0
    apex_y = band + dome_h
    # Spherical-cap centre on the axis through apex (0, apex_y) and rim
    # (head_r, band):  R - dome_h = sqrt(R^2 - head_r^2).
    cap_R = (head_r ** 2 + dome_h ** 2) / (2.0 * dome_h)

    # --- revolve profile ----------------------------------------------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    if sk_mgr.CreateCenterLine(0.0, hh / 1000.0, 0.0,
                               0.0, -length / 1000.0, 0.0) is None:
        raise RuntimeError("fillister profile: CreateCenterLine failed")
    # Dome arc as a THREE-POINT arc under no_sketch_inference.  Two traps,
    # both hit here: inference snapping is PIXEL-based (view-dependent)
    # and silently re-solved scripted arcs (centre snapped to the
    # centreline midpoint; an endpoint snapped horizontal with the apex);
    # and CreateArc's direction flag resolved INCONSISTENTLY across the
    # family sizes (A108's dome built fine, A194's identical-topology arc
    # made the revolve fail).  The mid-point form pins the bulge side with
    # no direction flag.
    yc = apex_y - cap_R
    ang_mid = (math.pi / 2.0 + math.atan2(band - yc, head_r)) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            0.0, apex_y / 1000.0, 0.0,             # start: dome apex
            head_r / 1000.0, band / 1000.0, 0.0,   # end: head rim
            cap_R * math.cos(ang_mid) / 1000.0,    # mid, on the sphere
            (yc + cap_R * math.sin(ang_mid)) / 1000.0, 0.0,
        )
        if arc is None:
            raise RuntimeError("fillister profile: dome arc failed")
        await add_line_chain(adapter, [
            (head_r, band),
            (head_r, 0.0),
            (major_r, 0.0),
            (major_r, -(length - tip_ch)),
            (major_r - tip_ch, -length),
            (0.0, -length),
            (0.0, apex_y),
        ], close=False)
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Body")
    v = (_spherical_cap_volume(head_r, dome_h)
         + math.pi * head_r ** 2 * band
         + math.pi * major_r ** 2 * (length - tip_ch)
         + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    volume = await volume_check(adapter, "revolved body", v, 0.005 * v)

    # --- driver slot (from the dome apex) -----------------------------------
    check("create_sketch slot", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (-slot_w / 2.0, apex_y + 0.5),
            (slot_w / 2.0, apex_y + 0.5),
            (slot_w / 2.0, apex_y - slot_d),
            (-slot_w / 2.0, apex_y - slot_d),
        ])
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check("cut slot", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=2.0 * hd, both_directions=True)))
    name_last_feature(adapter, "DriverSlot")

    # --- split at the under-head junction (scopes the sweep) ---------------
    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:  # extends below the junction
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- helix (junction -> P past the tip) ---------------------------------
    check("create_sketch helix seed", await adapter.create_sketch("Top"))
    seed = adapter.currentSketchManager.CreateCircleByRadius(
        0.0, 0.0, 0.0, major_r / 1000.0)
    if seed is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, revs, clockwise=True,
                 reversed_dir=True, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    # --- thread groove -------------------------------------------------------
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (root_r + (7.0 * pitch / 16.0) * math.sqrt(3.0),
             15.0 * pitch / 16.0),
            (root_r + (13.0 * pitch / 32.0) * math.sqrt(3.0),
             -pitch / 32.0),
            (root_r, 3.0 * pitch / 8.0),
            (root_r, pitch / 2.0),
        ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name,
                     "ThreadGroove")

    # --- runout boss + junction fillet (re-merges the bodies) ---------------
    # The vendor's one Boss-Extrude1 (FromType=swStartOffset P/2, both
    # directions, 30-deg draft) decomposes into: a straight cylinder fill
    # from the junction down to -P/2, then a 30-deg taper cone below it
    # until the cone falls under the thread root (adds nothing deeper).
    check("create_sketch runout fill", await adapter.create_sketch("Top"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("runout fill circle failed")
    check("exit_sketch runout fill", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutFillProfile")
    check("runout fill", await adapter.create_extrusion(ExtrusionParameters(
        depth=pitch / 2.0, reverse_direction=True)))
    name_last_feature(adapter, "RunoutFill")

    # Taper as a revolved frustum: the adapter's extrusion path hardcodes
    # Dchk1=False, so its draft_angle never applies.  The frustum's bottom
    # disc sits at the thread root radius, fully submerged -- no face.
    taper_h = (major_r - root_r) * math.sqrt(3.0)  # 30 deg from the axis
    check("create_sketch runout taper", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    if sk2.CreateCenterLine(0.0, -pitch / 2.0 / 1000.0, 0.0,
                            0.0, (-pitch / 2.0 - taper_h) / 1000.0,
                            0.0) is None:
        raise RuntimeError("runout taper: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, -pitch / 2.0),
            (major_r, -pitch / 2.0),
            (root_r, -pitch / 2.0 - taper_h),
            (0.0, -pitch / 2.0 - taper_h),
        ])
    check("exit_sketch runout taper", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutTaperProfile")
    check("runout taper", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "RunoutTaper")

    check("junction fillet", await adapter.add_fillet(
        pitch / 10.0, [[major_r, 0.0, 0.0]]))
    name_last_feature(adapter, "JunctionFillet")

    # Vendor frame: axis z with the head at +z (COM sits toward the heavy
    # head), origin mid-span, so their under-head junction is at
    # z = (L - HH)/2 -- exactly where their helix seed plane resolved
    # (z = +3.4036 on A108).  My junction is y = 0.
    adapter._mcm_com_map = lambda v: [v[1], v[2] - (length - hh) / 2.0, v[0]]


def _fillister_builder(part_no: str):
    async def build_one(adapter, truth):
        await _build_fillister(adapter, part_no)
    return build_one


# --------------------------------------------------------------------------
# 90114A511 -- brass fillister head slotted screw, #4-40 x 1/4"
# Same idiom family as 90280A* with its own laws (all from the vendor
# equations + solved sketches): FULL spherical dome (apex ON the axis,
# cap through apex + head rim), head band = HH*0.75, slot 0.9906 x 1.2192
# from the apex, junction fillet HH*0.05 BEFORE the slot, tip chamfer
# 45 deg x 0.75P, helix seeded at the TIP ascending L+P (11 revs,
# overrunning the JUNCTION by P -- harmless: the sweep is scoped to the
# shank body), SYMMETRIC cutter at tip+7P/16 in air (root flat P/8 at
# root_r, top 15P/16 at major+H/16), 45-deg runout cone at the junction.
# Frame: head UP, junction y=0 (vendor origin is the junction too).
# --------------------------------------------------------------------------
BF_MAJOR_R = 2.8448 / 2.0
BF_LEN = 6.35
BF_HH = 2.7178
BF_HEAD_R = 4.6482 / 2.0
BF_PITCH = 0.635
BF_SLOT_W = 0.9906   # Slot Width@Sketch1
BF_SLOT_D = 1.2192   # Slot Depth@Sketch1


async def build_90114A511(adapter, truth):
    from _common import add_line_chain
    from diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    major_r, head_r = BF_MAJOR_R, BF_HEAD_R
    pitch = BF_PITCH
    band = BF_HH * 0.75
    dome_h = BF_HH - band
    apex_y = BF_HH
    tip_ch = 0.75 * pitch
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    cap_R = (head_r ** 2 + dome_h ** 2) / (2.0 * dome_h)
    fillet_r = BF_HH * 0.05

    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    if sk_mgr.CreateCenterLine(0.0, apex_y / 1000.0, 0.0,
                               0.0, -BF_LEN / 1000.0, 0.0) is None:
        raise RuntimeError("90114 profile: CreateCenterLine failed")
    yc = apex_y - cap_R
    ang_mid = (math.pi / 2.0 + math.atan2(band - yc, head_r)) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            0.0, apex_y / 1000.0, 0.0,
            head_r / 1000.0, band / 1000.0, 0.0,
            cap_R * math.cos(ang_mid) / 1000.0,
            (yc + cap_R * math.sin(ang_mid)) / 1000.0, 0.0,
        )
        if arc is None:
            raise RuntimeError("90114 profile: dome arc failed")
        await add_line_chain(adapter, [
            (head_r, band),
            (head_r, 0.0),
            (major_r, 0.0),
            (major_r, -(BF_LEN - tip_ch)),
            (major_r - tip_ch, -BF_LEN),
            (0.0, -BF_LEN),
            (0.0, apex_y),
        ], close=False)
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Body")
    v = (_spherical_cap_volume(head_r, dome_h)
         + math.pi * head_r ** 2 * band
         + math.pi * major_r ** 2 * (BF_LEN - tip_ch)
         + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    await volume_check(adapter, "revolved body", v, 0.005 * v)

    # Vendor Fillet1 (before the slot) rounds TWO edges: the head-OD
    # bottom rim (underside plane <-> band cylinder -- their 3.0508 torus
    # spans z 0..0.14 at r~2.32, and their underside annulus reads
    # pi*(2.188^2 - 1.4224^2), outer radius trimmed by the fillet while
    # the shank corner stays SHARP) AND the dome-to-band rim (the
    # spherical cap is not tangent to the head cylinder).
    check("junction fillet", await adapter.add_fillet(
        fillet_r, [[head_r, 0.0, 0.0], [head_r, band, 0.0]]))
    name_last_feature(adapter, "JunctionFillet")

    check("create_sketch slot", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (-BF_SLOT_W / 2.0, apex_y + 0.5),
            (BF_SLOT_W / 2.0, apex_y + 0.5),
            (BF_SLOT_W / 2.0, apex_y - BF_SLOT_D),
            (-BF_SLOT_W / 2.0, apex_y - BF_SLOT_D),
        ])
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check("cut slot", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=2.0 * BF_HEAD_R * 2.0, both_directions=True)))
    name_last_feature(adapter, "DriverSlot")

    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # Tip-seeded ascending helix: flipped offset plane at the tip, 11 revs
    # to P past the junction.  clockwise=False here IS the vendor's
    # right-hand thread: their tip plane has normal -z with reverse=True,
    # ours +y with reverse=False, so the clockwise flag must invert
    # (proven on 93075A194, where clockwise=True left a mirror thread
    # whose sweep end slivers read +0.0575 mm^3 across every phase).
    offset_plane(adapter, "TipPlane", -BF_LEN)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, BF_LEN / pitch + 1.0, clockwise=False,
                 reversed_dir=False, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    cy = -BF_LEN - 7.0 * pitch / 16.0
    top_r = major_r + h_sharp / 16.0
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (top_r, cy + 15.0 * pitch / 32.0),
            (root_r, cy + pitch / 16.0),
            (root_r, cy - pitch / 16.0),
            (top_r, cy - 15.0 * pitch / 32.0),
        ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name,
                     "ThreadGroove")

    # 45-deg runout cone at the junction (their Boss-Extrude1, draft 45,
    # single direction, no offset -- a plain revolved frustum, merging
    # the split bodies back).
    taper_h = major_r - root_r  # 45 deg
    check("create_sketch runout", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    if sk2.CreateCenterLine(0.0, 0.0, 0.0,
                            0.0, -taper_h / 1000.0, 0.0) is None:
        raise RuntimeError("runout: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, 0.0),
            (major_r, 0.0),
            (root_r, -taper_h),
            (0.0, -taper_h),
        ])
    check("exit_sketch runout", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutProfile")
    check("runout cone", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "ThreadRunout")

    # Vendor frame: origin at the junction, head at +z per the COM sign
    # measured on the first gate run.  My junction y=0, head +y.
    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


# --------------------------------------------------------------------------
# 91783A722 -- 18-8 SS slotted round head screw, 1/2" x 2-1/2", 56 TPI,
# partially threaded (Minimum Thread Length 38.1).  All laws from the
# vendor equations + solved sketches: slot = HD*.135 wide x 1.5x deep from
# the apex, band = HH*.1, Fillet3 = HH*.02 on BOTH band rims (after the
# slot), tip chamfer 45 deg x 0.7P, cutter identical to the fillister law
# (root flat P/8 at root_r spanning 3P/8..P/2, corners root_r+7P/16*sqrt3
# @ 15P/16 and root_r+13P/32*sqrt3 @ -P/32 -- vendor Sketch6 matches to
# 4 decimals), head-seeded descending helix L+P tall.  The partial thread
# is their Boss-Extrude1: a refill cylinder r=major from the junction down
# to -(L - thread_len) plus a 30-deg-from-axis taper frustum below it
# (draft1=30 through-all down; the frustum bottom disc sits at root_r,
# submerged).  Fillet4 = P*.2 at the shank-underside junction, last.
# Frame: junction y=0, head +y (vendor origin mid-span, junction at
# z = +27.2415 = (L+HH)/2 - HH).
# --------------------------------------------------------------------------
RH_MAJOR_R = 12.7 / 2.0
RH_LEN = 63.5
RH_HH = 9.017
RH_HEAD_R = 20.6502 / 2.0
RH_PITCH = 25.4 / 56.0     # stored 0.453571
RH_THREAD_LEN = 38.1       # Minimum Thread Length@Sketch1


async def build_91783A722(adapter, truth):
    from _common import add_line_chain
    from diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    major_r, head_r = RH_MAJOR_R, RH_HEAD_R
    pitch = RH_PITCH
    band = RH_HH * 0.1         # D1@Sketch1 = Head Height * .1
    dome_h = RH_HH - band
    apex_y = RH_HH
    slot_w = 2.0 * head_r * 0.135   # D1@Sketch4 = Head Diameter * .135
    slot_d = slot_w * 1.5           # D2@Sketch4
    tip_ch = 0.7 * pitch            # D2@Sketch3 = Thread Pitch * .7
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    cap_R = (head_r ** 2 + dome_h ** 2) / (2.0 * dome_h)
    fillet3_r = RH_HH * 0.02        # 0.18034
    fillet4_r = pitch * 0.2         # 0.090714
    fill_len = RH_LEN - RH_THREAD_LEN   # 25.4: unthreaded shank below head

    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    if sk_mgr.CreateCenterLine(0.0, apex_y / 1000.0, 0.0,
                               0.0, -RH_LEN / 1000.0, 0.0) is None:
        raise RuntimeError("91783 profile: CreateCenterLine failed")
    yc = apex_y - cap_R
    ang_mid = (math.pi / 2.0 + math.atan2(band - yc, head_r)) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            0.0, apex_y / 1000.0, 0.0,
            head_r / 1000.0, band / 1000.0, 0.0,
            cap_R * math.cos(ang_mid) / 1000.0,
            (yc + cap_R * math.sin(ang_mid)) / 1000.0, 0.0,
        )
        if arc is None:
            raise RuntimeError("91783 profile: dome arc failed")
        await add_line_chain(adapter, [
            (head_r, band),
            (head_r, 0.0),
            (major_r, 0.0),
            (major_r, -(RH_LEN - tip_ch)),
            (major_r - tip_ch, -RH_LEN),
            (0.0, -RH_LEN),
            (0.0, apex_y),
        ], close=False)
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Body")
    v = (_spherical_cap_volume(head_r, dome_h)
         + math.pi * head_r ** 2 * band
         + math.pi * major_r ** 2 * (RH_LEN - tip_ch)
         + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    await volume_check(adapter, "revolved body", v, 0.005 * v)

    check("create_sketch slot", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (-slot_w / 2.0, apex_y + 0.5),
            (slot_w / 2.0, apex_y + 0.5),
            (slot_w / 2.0, apex_y - slot_d),
            (-slot_w / 2.0, apex_y - slot_d),
        ])
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check("cut slot", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=4.0 * head_r, both_directions=True)))
    name_last_feature(adapter, "DriverSlot")

    check("band fillets", await adapter.add_fillet(
        fillet3_r, [[head_r, 0.0, 0.0], [head_r, band, 0.0]]))
    name_last_feature(adapter, "BandFillets")

    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    check("create_sketch helix seed", await adapter.create_sketch("Top"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, RH_LEN / pitch + 1.0, clockwise=True,
                 reversed_dir=True, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (root_r + (7.0 * pitch / 16.0) * math.sqrt(3.0),
             15.0 * pitch / 16.0),
            (root_r + (13.0 * pitch / 32.0) * math.sqrt(3.0),
             -pitch / 32.0),
            (root_r, 3.0 * pitch / 8.0),
            (root_r, pitch / 2.0),
        ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name,
                     "ThreadGroove")

    # Partial-thread refill + 30-deg runout in ONE double-ended extrude,
    # exactly like the vendor's Boss-Extrude1: dir2 blind fill_len up to
    # the junction (refills the grooves, re-merges the split bodies),
    # dir1 ThroughAll down with a 30-deg shrinking draft (the taper cone
    # dives under the thread root after (major_r-root_r)*sqrt(3) and adds
    # nothing deeper).  This MUST stay one feature: authoring the refill
    # cylinder and the taper as two separate features produces the same
    # nominal geometry but a pathological merged body whose
    # IMassProperty under-integrates by 22.44 mm^3 / 10.45 mm^2 (the
    # flush-over-84-helical-crest-remnants merge), failing the volume
    # gate against a healthy vendor body.  Empirical flag inversion:
    # Ddir1=False shrinks the drafted cone here (docs say True=inward).
    from _common import _early_bound, _feature_by_name, _read_member

    offset_plane(adapter, "RefillPlane", -fill_len)
    check("create_sketch refill", await adapter.create_sketch("RefillPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("refill circle failed")
    check("exit_sketch refill", await adapter.exit_sketch())
    name_last_feature(adapter, "RefillProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "RefillProfile").Select2(False, 0)
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    feat = fm.FeatureExtrusion3(
        False, False, True,          # double ended, dir1 down
        1, 0,                        # T1 ThroughAll, T2 blind
        0.0, fill_len / 1000.0,      # D1, D2
        True, False, False, False,   # draft on dir1, shrinking
        math.radians(30.0), 0.0,
        False, False, False, False,
        True, False, True,           # Merge, UseFeatScope, UseAutoSelect
        0, 0.0, False)
    if feat is None:
        raise RuntimeError("refill/runout extrude failed")
    name_last_feature(adapter, "ThreadRunout")

    check("underhead fillet", await adapter.add_fillet(
        fillet4_r, [[major_r, 0.0, 0.0]]))
    name_last_feature(adapter, "UnderheadFillet")

    # Vendor origin is mid-span of L+HH (apex +36.2585); their under-head
    # junction sits at z = +27.2415.  My junction y=0, head +y.
    adapter._mcm_com_map = lambda v: [
        v[1], v[2] - ((RH_LEN + RH_HH) / 2.0 - RH_HH), v[0]]


# --------------------------------------------------------------------------
# 91410A538 -- square-head cup-point set screw, 1/4"-20 x 5/8".
# Two boss revolves (shank+cup point, then the head), the square cut as a
# ThroughAll FeatureCut4 with Flip=True (remove OUTSIDE the 6.35-square --
# the head revolve's OD is major_d*sqrt(2) so the square's corners land
# exactly on it), 75-deg chamfer cones top+bottom of the head, split at
# the junction, tip-seeded ascending helix L+P (13.5 revs, vendor stores
# start angle 90 explicitly), the SYMMETRIC 90114A511 cutter law at
# tip - 7P/16 in air, sweep scoped to the shank, 60-deg runout frustum at
# the junction (re-merges).  Cup point: 45-deg outer chamfer to the rim,
# 59-deg interior cone (rim radius 1.739789 as solved in Sketch2).
# Frame: junction y=0, head +y (vendor origin is the junction too).
# --------------------------------------------------------------------------
SQ_MAJOR_R = 6.35 / 2.0
SQ_LEN = 15.875
SQ_HH = 4.7625
SQ_PITCH = 1.27
SQ_CUP_RIM_R = 1.739789   # Sketch2 solved rim; 45/59 deg from its dims
SQ_CHAMFER_DEG = 75.0     # head chamfer cones (Sketch3 D1/D2)


async def build_91410A538(adapter, truth):
    from _common import (add_line_chain, _early_bound, _feature_by_name,
                         _read_member)
    from diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import RevolveParameters

    major_r = SQ_MAJOR_R
    pitch = SQ_PITCH
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    od_r = major_r * math.sqrt(2.0)          # head revolve OD 4.490128
    cham = (od_r - major_r) * math.tan(math.radians(90.0 - SQ_CHAMFER_DEG))
    rim_r = SQ_CUP_RIM_R
    cup_apex_y = -SQ_LEN + rim_r / math.tan(math.radians(59.0))
    cham_start_y = -SQ_LEN + (major_r - rim_r)   # 45-deg outer chamfer

    # --- shank + cup point ---------------------------------------------------
    check("create_sketch shank", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    if sk.CreateCenterLine(0.0, 0.0, 0.0,
                           0.0, -SQ_LEN / 1000.0, 0.0) is None:
        raise RuntimeError("91410 shank: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, 0.0),
            (major_r, 0.0),
            (major_r, cham_start_y),
            (rim_r, -SQ_LEN),
            (0.0, cup_apex_y),
        ])
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Shank")
    v_shank = (math.pi * major_r ** 2 * -cham_start_y
               + _rev_frustum(cham_start_y + SQ_LEN, major_r, rim_r)
               - _rev_frustum(cup_apex_y + SQ_LEN, rim_r, 0.0))
    await volume_check(adapter, "shank revolve", v_shank, 0.005 * v_shank)

    # --- head revolve (OD cylinder + 75-deg chamfer cones) -------------------
    check("create_sketch head", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    if sk.CreateCenterLine(0.0, 0.0, 0.0,
                           0.0, SQ_HH / 1000.0, 0.0) is None:
        raise RuntimeError("91410 head: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, SQ_HH),
            (major_r, SQ_HH),
            (od_r, SQ_HH - cham),
            (od_r, cham),
            (major_r, 0.0),
            (0.0, 0.0),
        ])
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    check("revolve head", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Head")
    v_head = (math.pi * od_r ** 2 * (SQ_HH - 2.0 * cham)
              + 2.0 * _rev_frustum(cham, od_r, major_r))
    await volume_check(adapter, "head revolve", v_shank + v_head,
                       0.005 * v_head)

    # --- square (ThroughAll cut, remove OUTSIDE the profile) -----------------
    offset_plane(adapter, "HeadTopPlane", SQ_HH)
    check("create_sketch square", await adapter.create_sketch("HeadTopPlane"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (-major_r, -major_r),
            (major_r, -major_r),
            (major_r, major_r),
            (-major_r, major_r),
        ])
    check("exit_sketch square", await adapter.exit_sketch())
    name_last_feature(adapter, "SquareProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "SquareProfile").Select2(False, 0)
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    feat = fm.FeatureCut4(
        True, True, False,           # single ended, Flip=outside, default dir
        1, 0, 0.0, 0.0,              # T1 ThroughAll
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False,                       # NormalCut
        False, True,                 # UseFeatScope, UseAutoSelect
        False, False, False,         # assembly scope args
        0, 0.0, False,               # T0 sketch plane
        False)                       # OptimizeGeometry
    if feat is None:
        raise RuntimeError("square cut failed")
    name_last_feature(adapter, "SquareCut")
    # corner segments beyond the 6.35 square inside the OD circle: exact on
    # the OD band, Simpson over each chamfer cone
    def _seg(R):
        if R <= major_r:
            return 0.0
        th = 2.0 * math.acos(major_r / R)
        return 4.0 * R * R / 2.0 * (th - math.sin(th))
    n, acc = 50, 0.0
    for i in range(n + 1):
        w = (1 if i in (0, n) else (4 if i % 2 else 2))
        acc += w * _seg(major_r + (od_r - major_r) * i / n)
    v_cham_cut = acc * (cham / n) / 3.0
    v_sq_cut = _seg(od_r) * (SQ_HH - 2.0 * cham) + 2.0 * v_cham_cut
    await volume_check(adapter, "square cut",
                       v_shank + v_head - v_sq_cut, 0.01 * v_sq_cut)

    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- tip-seeded ascending helix, L+P (vendor stores start angle 90) -----
    offset_plane(adapter, "TipPlane", -SQ_LEN)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, SQ_LEN / pitch + 1.0, clockwise=False,
                 reversed_dir=False, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    cy = -SQ_LEN - 7.0 * pitch / 16.0
    top_r = major_r + h_sharp / 16.0
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (top_r, cy + 15.0 * pitch / 32.0),
            (root_r, cy + pitch / 16.0),
            (root_r, cy - pitch / 16.0),
            (top_r, cy - 15.0 * pitch / 32.0),
        ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name,
                     "ThreadGroove")

    # --- 60-deg runout at the junction (their Boss-Extrude1, draft 60) ------
    taper_h = (major_r - root_r) / math.sqrt(3.0)
    check("create_sketch runout", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    if sk2.CreateCenterLine(0.0, 0.0, 0.0,
                            0.0, -taper_h / 1000.0, 0.0) is None:
        raise RuntimeError("runout: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, 0.0),
            (major_r, 0.0),
            (root_r, -taper_h),
            (0.0, -taper_h),
        ])
    check("exit_sketch runout", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutProfile")
    check("runout cone", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "ThreadRunout")

    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


# --------------------------------------------------------------------------
# 93075A194 -- low-strength steel hex head screw, #8-32 x 1/2".
# Laws from the vendor equations + solved sketches: hex 6.35 across flats
# extruded HH=2.794 up from the underside; corner trim = ThroughAll
# FeatureCut4 of the r=3.175 inscribed circle with Flip=True and a 60-deg
# draft (the trim boundary cone runs 60 deg FROM THE AXIS -- each corner
# face is plan 0.542 / cos30 = 0.6257); crown dish = revolved cut, r =
# HW*0.9/2 at the top sinking HH*0.1 at 45 deg; tip chamfer 45 x P*0.851
# (their Chamfer1); tip-seeded L+P helix (17 revs, start 90) with the
# symmetric cutter law; under-head runout = ONE both-directions
# FeatureExtrusion3 from a circle r = major+0.0508 on the underside
# (dir1 down blind 10 with 20-deg shrinking draft, dir2 up 0.254
# submerged), re-merging the split bodies.  Frame: vendor origin kept
# (mid-shank), underside +4.953, top +7.747, tip -7.747.
# --------------------------------------------------------------------------
HX_MAJOR_R = 4.1656 / 2.0
HX_LEN = 12.7
HX_HW = 6.35            # across flats
HX_HH = 2.794
HX_PITCH = 0.79375
HX_UNDERSIDE = 4.953    # vendor origin sits mid-shank


async def build_93075A194(adapter, truth):
    from _common import (add_line_chain, _early_bound, _feature_by_name,
                         _read_member)
    from diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    major_r = HX_MAJOR_R
    pitch = HX_PITCH
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    flat_r = HX_HW / 2.0
    hex_R = flat_r * 2.0 / math.sqrt(3.0)
    tip_y = HX_UNDERSIDE - HX_LEN            # -7.747
    top_y = HX_UNDERSIDE + HX_HH             # +7.747
    tip_ch = pitch * 0.851                   # Chamfer1 = Thread Pitch * .851
    crown_r = HX_HW * 0.9 / 2.0              # 2.8575
    crown_d = HX_HH * 0.1                    # 0.2794, 45 deg dish

    # --- shank with tip chamfer (their Boss-Extrude1 + Chamfer1) ------------
    check("create_sketch shank", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    if sk.CreateCenterLine(0.0, HX_UNDERSIDE / 1000.0, 0.0,
                           0.0, tip_y / 1000.0, 0.0) is None:
        raise RuntimeError("93075 shank: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, HX_UNDERSIDE),
            (major_r, HX_UNDERSIDE),
            (major_r, tip_y + tip_ch),
            (major_r - tip_ch, tip_y),
            (0.0, tip_y),
        ])
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Shank")
    v_shank = (math.pi * major_r ** 2 * (HX_LEN - tip_ch)
               + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    await volume_check(adapter, "shank revolve", v_shank, 0.005 * v_shank)

    # --- hex head from the underside ----------------------------------------
    offset_plane(adapter, "UndersidePlane", HX_UNDERSIDE)
    check("create_sketch hex", await adapter.create_sketch("UndersidePlane"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, hex_R),
            (-flat_r, hex_R / 2.0),
            (-flat_r, -hex_R / 2.0),
            (0.0, -hex_R),
            (flat_r, -hex_R / 2.0),
            (flat_r, hex_R / 2.0),
        ])
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    check("extrude hex", await adapter.create_extrusion(ExtrusionParameters(
        depth=HX_HH)))
    name_last_feature(adapter, "HexHead")
    v_hex = HX_HW ** 2 * math.sqrt(3.0) / 2.0 * HX_HH
    await volume_check(adapter, "hex head", v_shank + v_hex, 0.005 * v_hex)

    # --- corner trim: outside the inscribed circle, 60-deg cone --------------
    offset_plane(adapter, "HeadTopPlane", top_y)
    check("create_sketch trim", await adapter.create_sketch("HeadTopPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, flat_r / 1000.0) is None:
        raise RuntimeError("trim circle failed")
    check("exit_sketch trim", await adapter.exit_sketch())
    name_last_feature(adapter, "TrimProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "TrimProfile").Select2(False, 0)
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    feat = fm.FeatureCut4(
        True, True, False,               # single ended, Flip=outside
        1, 0, 0.0, 0.0,                  # T1 ThroughAll
        True, False, False, False,       # draft dir1; Ddir1=False (empirical)
        math.radians(60.0), 0.0,
        False, False, False, False,
        False, False, True,              # NormalCut, UseFeatScope, AutoSelect
        False, False, False,
        0, 0.0, False, False)
    if feat is None:
        raise RuntimeError("corner trim cut failed")
    name_last_feature(adapter, "CornerTrim")

    # --- crown dish (45-deg revolved cut) ------------------------------------
    check("create_sketch crown", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    if sk2.CreateCenterLine(0.0, top_y / 1000.0, 0.0,
                            0.0, (top_y - crown_d) / 1000.0, 0.0) is None:
        raise RuntimeError("crown: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, top_y + 0.2),
            (crown_r + 0.2, top_y + 0.2),
            (crown_r, top_y),
            (crown_r - crown_d, top_y - crown_d),
            (0.0, top_y - crown_d),
        ])
    check("exit_sketch crown", await adapter.exit_sketch())
    name_last_feature(adapter, "CrownProfile")
    check("crown cut", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=True)))
    name_last_feature(adapter, "CrownDish")

    body_boxes = split_at_plane(adapter, "UndersidePlane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < HX_UNDERSIDE - 1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- tip-seeded ascending helix, L+P (17 revs) ---------------------------
    offset_plane(adapter, "TipPlane", tip_y)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, HX_LEN / pitch + 1.0, clockwise=False,
                 reversed_dir=False, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    cy = tip_y - 7.0 * pitch / 16.0
    top_r = major_r + h_sharp / 16.0
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (top_r, cy + 15.0 * pitch / 32.0),
            (root_r, cy + pitch / 16.0),
            (root_r, cy - pitch / 16.0),
            (top_r, cy - 15.0 * pitch / 32.0),
        ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name,
                     "ThreadGroove", tangency=(0, 0))

    # --- under-head runout: ONE both-directions drafted extrude -------------
    check("create_sketch runout", await adapter.create_sketch("UndersidePlane"))
    # 0.0508 from the shank silhouette is inside pixel-snapping range:
    # without inference off the circle snaps to r=2.0828 (seen live).
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, (major_r + 0.0508) / 1000.0) is None:
            raise RuntimeError("runout circle failed")
    check("exit_sketch runout", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutProfile")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "RunoutProfile").Select2(False, 0)
    feat = fm.FeatureExtrusion3(
        False, False, True,              # double ended, dir1 down
        0, 0,                            # T1 blind, T2 blind
        10.0 / 1000.0, 0.254 / 1000.0,   # D1, D2
        True, False, False, False,       # draft dir1, shrinking (empirical)
        math.radians(20.0), 0.0,
        False, False, False, False,
        True, False, True,               # Merge, UseFeatScope, AutoSelect
        0, 0.0, False)
    if feat is None:
        raise RuntimeError("runout extrude failed")
    name_last_feature(adapter, "ThreadRunout")

    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


REGISTRY = {
    "90126A211": build_90126A211,
    "94025A150": build_94025A150,
    "90114A511": build_90114A511,
    "91783A722": build_91783A722,
    "91410A538": build_91410A538,
    "93075A194": build_93075A194,
    **{p: _fillister_builder(p) for p in FILLISTER_SIZES},
}


def _selected_parts() -> list[str]:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv[1:]:
        return list(REGISTRY)
    if not args:
        raise SystemExit(
            f"usage: diag_build_mcmaster.py <part_no>...|--all "
            f"(known: {', '.join(REGISTRY)})")
    unknown = [a for a in args if a not in REGISTRY]
    if unknown:
        raise SystemExit(f"no builder for: {', '.join(unknown)} "
                         f"(known: {', '.join(REGISTRY)})")
    return args


async def build(adapter) -> dict[str, str]:
    artefacts: dict[str, str] = {}
    for part_no in _selected_parts():
        truth = vendor_truth(part_no)
        with _telemetry.span("replica.build", label=part_no):
            check(f"create_part {part_no}", await adapter.create_part())
            await REGISTRY[part_no](adapter, truth)
            artefacts.update(await gate_and_save(adapter, part_no, truth))
            await close_all(adapter)
            artefacts.update(await render_vendor(adapter, part_no))
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
