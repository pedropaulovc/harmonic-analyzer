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
    capture_com_failure,
    check,
    name_last_feature,
    volume_check,
)
from diagnostics.diag_mcmaster_lib import (
    assert_profile_closed,  # noqa: E402
    _rev_frustum,
    draw_closed_profile,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)
from diagnostics.sketch_profile import (  # noqa: E402
    Line,
    Segment,
    endpoint_merges,
    minor_arc,
)

GB_MAJOR_R = 12.7 / 2.0
GB_LEN = 50.8
GB_HW = 19.05
GB_HH = 7.9375
GB_PITCH = 25.4 / 13.0     # stored 1.953846
GB_MTL = 31.75
GB_UNDERSIDE = 21.43125    # (L + HH)/2 - HH
GB_WASHER_T = 0.2

# --- raised triangle logo ring -----------------------------------------------
# The vendor authored this as a mid-plane Extrude-Thin over a 6-segment
# centreline, but FeatureExtrusionThin2 rejects ANY closed chain that contains
# tangent arcs on this build (probed: closed lines-only loops thin-extrude
# fine; line+tangent-arc loops fail at every wall/type/depth).  The FACES
# prove the equivalent explicit region, which is what these constants
# describe: the three corner-arc centres of the vendor's centreline triangle,
# and the 0.4 offset that turns it into a ring.
LOGO_APEX_CENTRE = (0.0, -5.33911)        # apex corner-arc centre (core vertex)
LOGO_BOTTOM_RIGHT_CENTRE = (1.201402, -7.42)
LOGO_BOTTOM_LEFT_CENTRE = (-1.201402, -7.42)
LOGO_OUTER_R = 0.4
# Outward normal of the right-hand slant line.  Kept as the literal pair the
# geometry was authored and gated with -- NOT recomputed as
# ``math.sqrt(3.0) / 2.0``, which is one ULP lower and would move every offset
# vertex.  Closure does not depend on this value being exactly cos(30 deg); it
# depends on the same expression being used on both sides of every joint.
LOGO_NX, LOGO_NY = 0.8660254037844387, 0.5


def logo_ring_profile() -> tuple[Segment, ...]:
    """The logo ring's nine segments: outer boundary CW, then the inner core.

    Outer boundary = the vendor centreline's three lines offset out 0.2, joined
    by r=0.4 corner arcs.  Inner boundary = the SHARP triangle through the
    three corner-arc centres: the inner offset degenerates, because the
    centreline lines are tangent to the r=0.2 corner circles, so
    ``centreline - 0.2`` IS the centre-to-centre edge.  Ring area check:
    ``P_core * R + pi * R**2 = 7.208412 * 0.4 + pi * 0.16 = 3.38602``, the
    vendor's 3.386 bottom face.

    Every vertex shared by two segments is written as the SAME expression in
    both places, so the two doubles are bit-identical and
    :func:`sketch_profile.endpoint_merges` pairs them on ``==``.  Do not
    "simplify" one side of a pair: a one-ULP difference opens the profile, and
    nothing -- no user setting, no tolerance -- can be relied on to bridge it.

    Pure: no COM, no adapter.  ``test_logo_profile_closure.py`` asserts the
    exact-equality and loop-count invariants against this function directly.
    """
    ct = LOGO_APEX_CENTRE
    cbr = LOGO_BOTTOM_RIGHT_CENTRE
    cbl = LOGO_BOTTOM_LEFT_CENTRE
    r_out, nx, ny = LOGO_OUTER_R, LOGO_NX, LOGO_NY
    apex_right = (ct[0] + r_out * nx, ct[1] + r_out * ny)
    apex_left = (ct[0] - r_out * nx, ct[1] + r_out * ny)
    right_slant = (cbr[0] + r_out * nx, cbr[1] + r_out * ny)
    right_flat = (cbr[0], cbr[1] - r_out)
    left_flat = (cbl[0], cbl[1] - r_out)
    left_slant = (cbl[0] - r_out * nx, cbl[1] + r_out * ny)
    return (
        Line(apex_right, right_slant),               # outer right slant
        minor_arc(cbr, right_slant, right_flat),     # outer BR corner, 120 deg
        Line(right_flat, left_flat),                 # outer bottom
        minor_arc(cbl, left_flat, left_slant),       # outer BL corner, 120 deg
        Line(left_slant, apex_left),                 # outer left slant
        minor_arc(ct, apex_left, apex_right),        # outer apex corner, 120 deg
        Line(ct, cbr),                               # inner core triangle
        Line(cbr, cbl),
        Line(cbl, ct),
    )


async def build_91247A720(adapter, truth=None):
    from _common import (add_line_chain, _early_bound, _feature_by_name,
                         _read_member)
    from diagnostics.diag_mcmaster_lib import (mass_properties, no_sketch_inference,
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
    washer_t = GB_WASHER_T

    # --- shank with tip chamfer (Revolve1 + Chamfer1) -----------------------
    check("create_sketch shank", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        # The revolve axis is raw construction geometry drawn before the
        # profile, so it was the one entity in this sketch still authored at
        # the seat's inference setting.  An axis that snaps is a revolve about
        # the wrong line.
        if sk.CreateCenterLine(0.0, GB_UNDERSIDE / 1000.0, 0.0,
                               0.0, tip_y / 1000.0, 0.0) is None:
            raise RuntimeError("91247 shank: CreateCenterLine failed")
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
    if not _feature_by_name(adapter, "TrimProfile").Select2(False, 0):
        raise RuntimeError("corner trim: TrimProfile selection failed")
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    feat = fm.FeatureCut4(
        True, True, False, 1, 0, 0.0, 0.0,
        True, False, False, False, math.radians(45.0), 0.0,
        False, False, False, False,
        False, False, True, False, False, False,
        0, 0.0, False, False)
    if feat is None:
        capture_com_failure(
            adapter,
            "corner-trim-cut",
            "corner trim cut failed",
            api="IFeatureManager.FeatureCut4",
            sketch="TrimProfile",
        )
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
    with no_sketch_inference(adapter):
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
    if not _feature_by_name(adapter, "RunoutProfile").Select2(False, 0):
        raise RuntimeError("thread runout: RunoutProfile selection failed")
    feat = fm.FeatureExtrusion3(
        True, False, True,               # single ended, down
        1, 0, 0.0, 0.0,                  # ThroughAll
        True, False, False, False,       # draft, shrinking (empirical)
        math.radians(30.0), 0.0,
        False, False, False, False,
        True, False, True,
        0, 0.0, False)
    if feat is None:
        capture_com_failure(
            adapter,
            "runout-extrude",
            "runout extrude failed",
            api="IFeatureManager.FeatureExtrusion3",
            sketch="RunoutProfile",
        )
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
        if not _feature_by_name(adapter, f"DashProfile{i}").Select2(False, 0):
            raise RuntimeError(f"dash {i}: DashProfile{i} selection failed")
        feat = fm.FeatureExtrusion3(
            True, False, False,          # single ended, up (sketch normal)
            0, 0, 0.2 / 1000.0, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False,
            False, False, True,          # Merge=FALSE -> separate body
            0, 0.0, False)
        if feat is None:
            capture_com_failure(
                adapter,
                f"dash-extrude-{i}",
                f"dash extrude {i} failed",
                api="IFeatureManager.FeatureExtrusion3",
                sketch=f"DashProfile{i}",
                angle_deg=deg,
            )
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
    # Geometry and its derivation: :func:`logo_ring_profile` (module level, so
    # the offline closure test asserts against the real thing).
    #
    # THIS is the site that failed 2026-09-17 on swmaker000005 as "logo ring
    # extrude failed" and passed on retry.  It used to draw nine bare
    # CreateLine/Create3PointArc segments through the inference engine, on the
    # theory that exactly-coincident endpoints would merge into closed loops,
    # having audited the endpoints against MODEL silhouettes and found the
    # nearest 0.898 mm away.  Two things were wrong with that audit.
    #
    # First, snapping is measured in PIXELS, not millimetres, and nothing on
    # this path fits or orients the view -- px/mm is inherited from the part
    # template and the SolidWorks main-window size.  That is no longer a
    # hypothesis: the seat variable was MEASURED across the three workers.  The
    # window that failed was 1024x640; the two that passed were 1296x816, which
    # is 1/0.620 of the area, so the failing seat resolved every millimetre into
    # 0.62x the pixels.  Preference drift is REFUTED as the explanation -- zero
    # divergence across 45 preference names, and the failing seat had every snap
    # toggle ON exactly like the two that passed.  Nothing about the seat's
    # settings differed; its WINDOW did.  (diagnostics/exp_inference_zoom.py had
    # already measured the view dependence itself.)
    #
    # Second, the sketch's OWN points are snap candidates too, not just model
    # silhouettes: each
    # inner-triangle vertex IS an outer corner arc's centre -- arc centres are
    # a first-class snap target (swSketchSnapsCenterPoints) -- so every outer
    # arc endpoint has a competitor at exactly 0.400 mm, and at each corner the
    # competitor is THREE coincident targets (the centre plus the two inner
    # endpoints meeting there) against one correct partner at 0 mm.  Of the 24
    # snap targets in this profile, 15 pairs are exactly coincident and 69 more
    # sit within 0.75 mm.
    #
    # 0.400 mm is not merely tighter than the 0.898 mm that was audited -- it is
    # 0.53x a snap distance this codebase has WATCHED fire: a rectangle corner
    # authored 0.75 mm off the origin snapped back to 0 with inference on and
    # rebuilt the untrimmed shape with no error at all, caught only by a volume
    # gate (memory/solidworks-modeling-pitfalls.md:145-150).  That is what makes
    # the old comment's conclusion unsound rather than just unproven.
    #
    # Closure is now AUTHORED and has no pixel term at all: segments go
    # straight to the sketch database (AddToDB), arcs are centre-based rather
    # than re-fitted from three points, and every shared vertex gets an
    # explicit merge relation.  Direct-to-DB is the fix precisely BECAUSE it
    # removes the pixel term -- the measured seat variable was window size, so
    # no preference baseline could have prevented this.  The ring extrudes
    # identically at any window size, at any view scale, on any seat.
    #
    # The two gates that catch a degenerate corner are OFFLINE, in
    # sketch_profile: endpoint_merges refuses any vertex not shared by exactly
    # two ends, and minor_arc refuses an endpoint that has arrived at the
    # centre.  The CheckFeatureUse read-back in draw_closed_profile is
    # forensics, not a gate.
    logo_segs = logo_ring_profile()
    check("create_sketch logo", await adapter.create_sketch("HeadTopPlane"))
    await draw_closed_profile(adapter, logo_segs, label="logo ring", loops=2)
    check("exit_sketch logo", await adapter.exit_sketch())
    name_last_feature(adapter, "LogoProfile")
    # ONE closure read, shared with the forensics record: no second COM call,
    # and the extrude's failure context below comes from these same numbers.
    closure = assert_profile_closed(adapter, "logo ring", loops=2)
    model.ClearSelection2(True)
    # FeatureExtrusion3 also returns None when NOTHING is selected, so an
    # unchecked Select2 leaves a failed selection and a bad profile
    # indistinguishable in the log.  That is a real defect and it is fixed
    # here, but it is NOT what happened on 2026-09-17: the extrude spent
    # 1.925 s before returning None, which is contour analysis running on a
    # selected profile, not an immediate refusal on an empty selection.
    if not _feature_by_name(adapter, "LogoProfile").Select2(False, 0):
        raise RuntimeError("logo ring: LogoProfile selection failed")
    feat = fm.FeatureExtrusion3(
        True, False, False,              # single ended, up (sketch normal)
        0, 0, 0.2 / 1000.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, False, True,              # Merge=FALSE -> separate body
        0, 0.0, False)
    if feat is None:
        capture_com_failure(
            adapter,
            "logo-ring-extrude",
            "logo ring extrude failed",
            api="IFeatureManager.FeatureExtrusion3",
            sketch="LogoProfile",
            # Each merge WELDS two endpoints into one point, so a closed
            # nine-segment ring has nine sketch points and a wholly
            # unmerged one has eighteen.  FailureForensics reports the
            # difference as unmerged_points.
            expected_points=len(logo_segs),
            segments=len(logo_segs),
            merges=len(endpoint_merges(logo_segs)),
            contour_count=closure.get("contour_count"),
            unmerged_points=closure.get("unmerged_points"),
        )
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
    ct = LOGO_APEX_CENTRE
    cbr = LOGO_BOTTOM_RIGHT_CENTRE
    cbl = LOGO_BOTTOM_LEFT_CENTRE
    r_out, nx, ny = LOGO_OUTER_R, LOGO_NX, LOGO_NY
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
