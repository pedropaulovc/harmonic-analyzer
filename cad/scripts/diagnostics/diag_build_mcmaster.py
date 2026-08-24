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


REGISTRY = {
    "90126A211": build_90126A211,
    "94025A150": build_94025A150,
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
