r"""McMaster 93075A194 -- low-strength steel hex head screw, #8-32 x 1/2".

Laws from the vendor equations + solved sketches: hex 6.35 across flats
extruded HH=2.794 up from the underside; corner trim = ThroughAll
FeatureCut4 of the r=3.175 inscribed circle with Flip=True and a 60-deg
draft (the trim boundary cone runs 60 deg FROM THE AXIS -- each corner
face is plan 0.542 / cos30 = 0.6257); crown dish = revolved cut, r =
HW*0.9/2 at the top sinking HH*0.1 at 45 deg; tip chamfer 45 x P*0.851
(their Chamfer1); tip-seeded L+P helix (17 revs, start 90) with the
symmetric cutter law; under-head runout = ONE both-directions
FeatureExtrusion3 from a circle r = major+0.0508 on the underside
(dir1 down blind 10 with 20-deg shrinking draft, dir2 up 0.254
submerged), re-merging the split bodies.  Frame: vendor origin kept
(mid-shank), underside +4.953, top +7.747, tip -7.747.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_93075A194.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    check,
    name_last_feature,
    volume_check,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)

HX_MAJOR_R = 4.1656 / 2.0
HX_LEN = 12.7
HX_HW = 6.35            # across flats
HX_HH = 2.794
HX_PITCH = 0.79375
HX_UNDERSIDE = 4.953    # vendor origin sits mid-shank


async def build_93075A194(adapter, truth=None):
    from _common import (add_line_chain, _early_bound, _feature_by_name,
                         _read_member)
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane
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


if __name__ == "__main__":
    sys.exit(replica_main("93075A194", build_93075A194))
