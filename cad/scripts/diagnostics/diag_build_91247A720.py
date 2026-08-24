r"""McMaster 91247A720 -- Grade 5 zinc steel hex head screw, 1/2"-13 x 2".

FIVE bodies: the screw, three RAISED Grade 5 dashes (stadium bosses 0.2
tall, Merge=false, fillet 0.15 on the top rim, vendor CirPattern 3x --
authored directly at 0/120/240), and a raised rounded-triangle logo
ring (thin extrude, wall 0.4 centred on the sketched centreline, 0.2
tall, fillet 0.15 on BOTH top rims).  Screw: shank revolve with tip
chamfer P*0.75 to tip flat r = P*2.5, hex 19.05 A/F from the underside,
washer disc r=9.525 extruded 0.2 BELOW the hex, corner trim = FlipSide
ThroughAll cut of r = HW*.925/2 with 45-deg draft, split at the THREAD
TOP (tip + Minimum Thread Length 31.75 = +2.38125), tip-seeded helix
MTL+P (17.25 revs), symmetric cutter law, 30-deg runout at the thread
top (single-direction ThroughAll drafted boss, re-merges).
Frame: vendor origin (mid overall), underside +21.43125, top +29.36875,
tip -29.36875.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91247A720.py

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
from diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)

GB_MAJOR_R = 12.7 / 2.0
GB_LEN = 50.8
GB_HW = 19.05
GB_HH = 7.9375
GB_PITCH = 25.4 / 13.0     # stored 1.953846
GB_MTL = 31.75
GB_UNDERSIDE = 21.43125    # (L + HH)/2 - HH


async def build_91247A720(adapter, truth):
    from _common import (add_line_chain, _early_bound, _feature_by_name,
                         _read_member)
    from diag_mcmaster_lib import (mass_properties, no_sketch_inference,
                                   split_at_plane)
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    major_r = GB_MAJOR_R
    pitch = GB_PITCH
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    flat_r = GB_HW / 2.0
    hex_R = flat_r * 2.0 / math.sqrt(3.0)
    tip_y = GB_UNDERSIDE - GB_LEN            # -29.36875
    top_y = GB_UNDERSIDE + GB_HH             # +29.36875
    thread_top = tip_y + GB_MTL              # +2.38125
    tip_ch = pitch * 0.75                    # 1.465385
    tip_flat_r = pitch * 2.5                 # 4.884615 (D1@Sketch2)
    trim_r = GB_HW * 0.925 / 2.0             # 8.81062
    washer_r = flat_r                        # Sketch5 circle 9.525
    washer_t = 0.2

    # --- shank with tip chamfer (Revolve1 + Chamfer1) -----------------------
    check("create_sketch shank", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    if sk.CreateCenterLine(0.0, GB_UNDERSIDE / 1000.0, 0.0,
                           0.0, tip_y / 1000.0, 0.0) is None:
        raise RuntimeError("91247 shank: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, GB_UNDERSIDE),
            (major_r, GB_UNDERSIDE),
            (major_r, tip_y + tip_ch),
            (tip_flat_r, tip_y),
            (0.0, tip_y),
        ])
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Shank")
    v_shank = (math.pi * major_r ** 2 * (GB_LEN - tip_ch)
               + _rev_frustum(tip_ch, major_r, tip_flat_r))
    await volume_check(adapter, "shank revolve", v_shank, 0.005 * v_shank)

    # --- hex head + washer disc ---------------------------------------------
    offset_plane(adapter, "UndersidePlane", GB_UNDERSIDE)
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
        depth=GB_HH)))
    name_last_feature(adapter, "HexHead")
    v_hex = GB_HW ** 2 * math.sqrt(3.0) / 2.0 * GB_HH
    await volume_check(adapter, "hex head", v_shank + v_hex, 0.005 * v_hex)

    check("create_sketch washer", await adapter.create_sketch("UndersidePlane"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, washer_r / 1000.0) is None:
            raise RuntimeError("washer circle failed")
    check("exit_sketch washer", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    check("washer disc", await adapter.create_extrusion(ExtrusionParameters(
        depth=washer_t, reverse_direction=True)))
    name_last_feature(adapter, "WasherFace")
    v_washer = (math.pi * washer_r ** 2 - math.pi * major_r ** 2) * washer_t
    await volume_check(adapter, "washer disc",
                       v_shank + v_hex + v_washer, 0.05 * v_washer)

    # --- corner trim (45-deg boundary cone) ----------------------------------
    offset_plane(adapter, "HeadTopPlane", top_y)
    check("create_sketch trim", await adapter.create_sketch("HeadTopPlane"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, trim_r / 1000.0) is None:
            raise RuntimeError("trim circle failed")
    check("exit_sketch trim", await adapter.exit_sketch())
    name_last_feature(adapter, "TrimProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "TrimProfile").Select2(False, 0)
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    feat = fm.FeatureCut4(
        True, True, False, 1, 0, 0.0, 0.0,
        True, False, False, False, math.radians(45.0), 0.0,
        False, False, False, False,
        False, False, True, False, False, False,
        0, 0.0, False, False)
    if feat is None:
        raise RuntimeError("corner trim cut failed")
    name_last_feature(adapter, "CornerTrim")

    # --- split at the THREAD TOP, thread, runout -----------------------------
    offset_plane(adapter, "ThreadTopPlane", thread_top)
    body_boxes = split_at_plane(adapter, "ThreadTopPlane", "ThreadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < thread_top - 1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no threaded body")
    _telemetry.info(f"threaded body: {shank_name}")

    offset_plane(adapter, "TipPlane", tip_y)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, GB_MTL / pitch + 1.0, clockwise=False,
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
                     "ThreadGroove")

    check("create_sketch runout", await adapter.create_sketch("ThreadTopPlane"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, major_r / 1000.0) is None:
            raise RuntimeError("runout circle failed")
    check("exit_sketch runout", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutProfile")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "RunoutProfile").Select2(False, 0)
    feat = fm.FeatureExtrusion3(
        True, False, True,               # single ended, down
        1, 0, 0.0, 0.0,                  # ThroughAll
        True, False, False, False,       # draft, shrinking (empirical)
        math.radians(30.0), 0.0,
        False, False, False, False,
        True, False, True,
        0, 0.0, False)
    if feat is None:
        raise RuntimeError("runout extrude failed")
    name_last_feature(adapter, "ThreadRunout")
    v_before_marks = mass_properties(adapter)["volume_mm3"]

    # --- three raised Grade 5 dashes (separate bodies) -----------------------
    def _rot(x, y, deg):
        a = math.radians(deg)
        return (x * math.cos(a) - y * math.sin(a),
                x * math.sin(a) + y * math.cos(a))

    mark_w = 0.4
    mark_c1, mark_c2 = 5.03875, 7.42     # arc centres along the radial
    z_sgn = 0.0  # sketch-y -> model-z sign, read off the first dash body
    for i, deg in enumerate((0.0, 120.0, 240.0)):
        check(f"create_sketch dash{i}",
              await adapter.create_sketch("HeadTopPlane"))
        c1 = _rot(0.0, mark_c1, deg)
        c2 = _rot(0.0, mark_c2, deg)
        with no_sketch_inference(adapter):
            if adapter.currentSketchManager.CreateSketchSlot(
                    0, 0, mark_w / 1000.0,
                    c1[0] / 1000.0, c1[1] / 1000.0, 0.0,
                    c2[0] / 1000.0, c2[1] / 1000.0, 0.0,
                    0.0, 0.0, 0.0, 1, False) is None:
                raise RuntimeError(f"dash slot failed at {deg}")
        check(f"exit_sketch dash{i}", await adapter.exit_sketch())
        name_last_feature(adapter, f"DashProfile{i}")
        model.ClearSelection2(True)
        _feature_by_name(adapter, f"DashProfile{i}").Select2(False, 0)
        feat = fm.FeatureExtrusion3(
            True, False, False,          # single ended, up (sketch normal)
            0, 0, 0.2 / 1000.0, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False,
            False, False, True,          # Merge=FALSE -> separate body
            0, 0.0, False)
        if feat is None:
            raise RuntimeError(f"dash extrude {i} failed")
        name_last_feature(adapter, f"Dash{i}")
        if i == 0:
            # Dash0 sits entirely at sketch y in [4.84, 7.62]; the sign of
            # its model-z extent reveals the plane's sketch-y -> model-z
            # mapping (offset planes here place sketch +y at model -z, but
            # read it off the geometry rather than trusting convention).
            part = _early_bound(adapter.currentModel, "IPartDoc")
            for b in part.GetBodies2(0, False) or []:
                b2 = _early_bound(b, "IBody2")
                box = [float(x) * 1000 for x in (b2.GetBodyBox() or [])]
                if box and min(box[1], box[4]) > top_y - 0.1:
                    z_sgn = 1.0 if (box[2] + box[5]) > 0 else -1.0
            if z_sgn == 0.0:
                raise RuntimeError("dash0 body not found for z-sign probe")
            _telemetry.info(f"sketch-y -> model-z sign: {z_sgn:+.0f}")
        rim = _rot(0.0, mark_c2 + mark_w / 2.0, deg)
        check(f"dash fillet {i}", await adapter.add_fillet(
            0.15, [[rim[0], top_y + 0.2, z_sgn * rim[1]]]))
        name_last_feature(adapter, f"DashFillet{i}")

    # --- raised triangle logo ring (separate body) --------------------------
    # The vendor authored this as a mid-plane Extrude-Thin over a 6-segment
    # centreline, but FeatureExtrusionThin2 rejects ANY closed chain that
    # contains tangent arcs on this build (probed: closed lines-only loops
    # thin-extrude fine; line+tangent-arc loops fail at every wall/type/
    # depth).  The FACES prove the equivalent explicit region: outer
    # boundary = the centreline's 3 lines offset out 0.2 joined by r=0.4
    # corner arcs; inner boundary = the SHARP triangle through the 3 corner
    # arc centres (the inner offset degenerates: the centreline lines are
    # tangent to the r=0.2 corner circles, so centreline - 0.2 IS the
    # centre-to-centre edge).  Ring area check: P_core*R + pi*R^2 =
    # 7.208412*0.4 + pi*0.16 = 3.38602 = the vendor's 3.386 bottom face.
    ct = (0.0, -5.33911)        # apex corner-arc centre (core vertex)
    cbr = (1.201402, -7.42)     # bottom-right centre
    cbl = (-1.201402, -7.42)    # bottom-left centre
    r_out = 0.4
    nx, ny = 0.8660254037844387, 0.5   # outward normal of the right line
    logo_segs = [
        # outer: right line, BR arc, bottom line, BL arc, left line, apex arc
        ("line", (ct[0] + r_out * nx, ct[1] + r_out * ny),
                 (cbr[0] + r_out * nx, cbr[1] + r_out * ny)),
        ("arc", (cbr[0] + r_out * nx, cbr[1] + r_out * ny),
                (cbr[0], cbr[1] - r_out),
                (cbr[0] + r_out * nx, cbr[1] - r_out * ny)),
        ("line", (cbr[0], cbr[1] - r_out), (cbl[0], cbl[1] - r_out)),
        ("arc", (cbl[0], cbl[1] - r_out),
                (cbl[0] - r_out * nx, cbl[1] + r_out * ny),
                (cbl[0] - r_out * nx, cbl[1] - r_out * ny)),
        ("line", (cbl[0] - r_out * nx, cbl[1] + r_out * ny),
                 (ct[0] - r_out * nx, ct[1] + r_out * ny)),
        ("arc", (ct[0] - r_out * nx, ct[1] + r_out * ny),
                (ct[0] + r_out * nx, ct[1] + r_out * ny),
                (ct[0], ct[1] + r_out)),
        # inner: the sharp core triangle
        ("line", ct, cbr),
        ("line", cbr, cbl),
        ("line", cbl, ct),
    ]
    check("create_sketch logo", await adapter.create_sketch("HeadTopPlane"))
    sk4 = adapter.currentSketchManager
    # Inference stays ON: exactly-coincident endpoints must merge into
    # closed loops.  No endpoint radius (5.15-7.91) sits near a model
    # silhouette (6.35/8.81/9.525), so the circle-snap hazard is absent.
    for seg in logo_segs:
        if seg[0] == "line":
            (x1, y1), (x2, y2) = seg[1], seg[2]
            if sk4.CreateLine(x1 / 1000.0, y1 / 1000.0, 0.0,
                              x2 / 1000.0, y2 / 1000.0, 0.0) is None:
                raise RuntimeError("logo line failed")
        else:
            (x1, y1), (x2, y2), (xm, ym) = seg[1], seg[2], seg[3]
            if sk4.Create3PointArc(x1 / 1000.0, y1 / 1000.0, 0.0,
                                   x2 / 1000.0, y2 / 1000.0, 0.0,
                                   xm / 1000.0, ym / 1000.0, 0.0) is None:
                raise RuntimeError("logo arc failed")
    check("exit_sketch logo", await adapter.exit_sketch())
    name_last_feature(adapter, "LogoProfile")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "LogoProfile").Select2(False, 0)
    feat = fm.FeatureExtrusion3(
        True, False, False,              # single ended, up (sketch normal)
        0, 0, 0.2 / 1000.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, False, True,              # Merge=FALSE -> separate body
        0, 0.0, False)
    if feat is None:
        raise RuntimeError("logo ring extrude failed")
    name_last_feature(adapter, "LogoRing")
    # Outer top rim is tangent-continuous (offset corner arcs r=0.4) so one
    # propagated point covers it; the INNER rim's corner arcs degenerate to
    # sharp vertices (r = 0.2 - wall/2 = 0), so each of its 3 line segments
    # needs its own seed point (tangent propagation stops at sharp corners).
    # One fillet over all 9 top-rim edges, like the vendor's single Fillet2.
    # Tangent PROPAGATION must be off: FeatureFillet3 with Propagate=True
    # fails on this closed tangent-continuous outer loop at every seed and
    # radius probed, while the same edges fillet fine selected explicitly --
    # hence propagate=False with every rim edge listed (the adapter resolves
    # each point GEOMETRICALLY; raw SelectByID2 is view-dependent and
    # silently misses back-facing edges).
    ft = 0.15
    rim_y = top_y + 0.2
    mid_out = ((ct[0] + cbr[0]) / 2.0 + r_out * nx,
               (ct[1] + cbr[1]) / 2.0 + r_out * ny)
    mid_in = ((ct[0] + cbr[0]) / 2.0, (ct[1] + cbr[1]) / 2.0)
    rim_pts = [  # (sketch x, sketch y), one per rim edge
        (0.0, cbr[1] - r_out),                 # outer bottom line
        (cbr[0] + r_out, cbr[1]),              # outer BR corner arc
        (cbl[0] - r_out, cbl[1]),              # outer BL corner arc
        (0.0, ct[1] + r_out),                  # outer apex arc
        (mid_out[0], mid_out[1]),              # outer right slant line
        (-mid_out[0], mid_out[1]),             # outer left slant line
        (0.0, cbr[1]),                         # inner bottom line
        (mid_in[0], mid_in[1]),                # inner right line
        (-mid_in[0], mid_in[1]),               # inner left line
    ]
    check("logo fillet", await adapter.add_fillet(
        ft, [[sx, rim_y, z_sgn * sy] for sx, sy in rim_pts],
        propagate=False))
    name_last_feature(adapter, "LogoFillet")

    v_dash = (mark_w * (mark_c2 - mark_c1) + math.pi * (mark_w / 2.0) ** 2) * 0.2
    p_core = 3.0 * math.hypot(cbr[0] - ct[0], cbr[1] - ct[1])
    v_logo = (p_core * r_out + math.pi * r_out ** 2) * 0.2
    await volume_check(adapter, "marks + logo (pre-fillet approx)",
                       v_before_marks + 3.0 * v_dash + v_logo,
                       0.5 * (3.0 * v_dash + v_logo))

    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("91247A720", build_91247A720))
