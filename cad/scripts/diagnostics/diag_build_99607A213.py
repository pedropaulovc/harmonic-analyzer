r"""McMaster 99607A213 -- #4-40 x 5/8" knurled-head thumb screw, flared shoulder.

Vendor tree: shank extrude + tip chamfer P*.75 -> shoulder boss (dia
5.953125 x 3.175) -> head boss (dia 7.540625 x 3.175) -> Cut-Revolve1
flare (a chord+arc lens revolved: arc centred over the chord midpoint,
raised D2 = 0.47625 above the shoulder OD, spanning z 0.635..3.175 --
vendor equations D1 = ShoulderLen*.2, D2 = D1*.75) -> Chamfer2 =
HeadDia/16 on BOTH head rims -> split at the shoulder underside ->
tip-seeded helix (L+P, 26 revs) with the vendor's 6-gon cutter (60-deg
flanks crossing the major radius exactly at the tip and tip+7P/8, root
flat P/8 at tip+7P/16, top flat at major+0.254) -> runout boss from the
split plane, UpToNext with 20-deg draft, Merge re-unites the bodies ->
knurl: NOT helical -- a diagonal parallelogram stripe (width 0.127)
sketched on a side plane outside the head, extruded-cut to the head OD
face OFFSET-FROM-SURFACE 0.127 with TranslateSurface (the groove floor
is the OD cylinder translated 0.127 along the cut direction), mirrored
across the x=0 plane, both feature-patterned x36 (10 deg, re-solved,
not a geometry pattern -- matching the vendor flags).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_99607A213.py

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
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    assert_profile_closed,
    draw_closed_profile,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)
from diagnostics.sketch_profile import (  # noqa: E402
    Line,
    Segment,
    minor_arc,
)

TS_MAJOR_R = 2.8448 / 2.0
TS_PITCH = 0.635
TS_LEN = 15.875
TS_SH_R = 5.953125 / 2.0
TS_SH_H = 3.175
TS_HEAD_R = 7.540625 / 2.0
TS_HEAD_H = 3.175

# --- flare lens (Cut-Revolve1) -----------------------------------------------
# The vendor's equations: D1 = ShoulderLen * 0.2 = 0.635 sets the axial span,
# D2 = D1 * 0.75 = 0.47625 raises the arc centre above the shoulder OD.  The
# lens is a chord along the shoulder OD closed by an arc that dips toward the
# axis, revolved as a cut.
TS_FLARE_D2 = 0.47625
TS_FLARE_Z0 = 0.635
TS_FLARE_Z1 = 3.175
TS_FLARE_CENTRE = (TS_SH_R + TS_FLARE_D2, (TS_FLARE_Z0 + TS_FLARE_Z1) / 2.0)


def flare_profile() -> tuple[Segment, ...]:
    """The flare lens: the shoulder-OD chord, closed by the dipping arc.

    The two segments share both endpoints, which are written as the SAME
    expressions in both, so they are bit-identical doubles and pair exactly.

    The arc is authored by CENTRE, not through a rounded mid-point.  The old
    three-point form passed ``(2.096452, 1.905)`` as its mid-point -- the
    true minimum-radius point is ``2.0964519054308415``, so the arc SolidWorks
    fitted was 9.5e-8 mm off the intended circle and its realised endpoints
    were re-solved rather than taken verbatim.  Centre + endpoints puts the
    radius exactly where the vendor equation puts it.

    Pure: no COM, no adapter.
    """
    lower = (TS_SH_R, TS_FLARE_Z0)
    upper = (TS_SH_R, TS_FLARE_Z1)
    return (
        Line(lower, upper),
        minor_arc(TS_FLARE_CENTRE, lower, upper),
    )


async def build_99607A213(adapter, truth=None):
    from _common import (add_line_chain, _early_bound, _feature_by_name,
                         _read_member)
    from diagnostics.diag_mcmaster_lib import (mass_properties, no_sketch_inference,
                                   split_at_plane)
    from solidworks_mcp.adapters.base import (CircularPatternParameters,
                                              CreateAxisParameters,
                                              ExtrusionParameters,
                                              MirrorFeatureParameters,
                                              RevolveParameters)

    major_r, pitch = TS_MAJOR_R, TS_PITCH
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp    # 1.009955
    tip_ch = pitch * 0.75
    tip_y = -TS_LEN
    head_base = TS_SH_H                   # 3.175
    head_top = TS_SH_H + TS_HEAD_H        # 6.35
    ch2 = 7.540625 / 16.0                 # 0.471289

    # --- shank with tip chamfer ---------------------------------------------
    check("create_sketch shank", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if sk.CreateCenterLine(0.0, 0.0, 0.0, 0.0, tip_y / 1000.0, 0.0) is None:
            raise RuntimeError("99607 shank: CreateCenterLine failed")
        await add_line_chain(adapter, [
            (0.0, 0.0),
            (major_r, 0.0),
            (major_r, tip_y + tip_ch),
            (major_r - tip_ch, tip_y),
            (0.0, tip_y),
        ])
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Shank")
    v_shank = (math.pi * major_r ** 2 * (TS_LEN - tip_ch)
               + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    await volume_check(adapter, "shank revolve", v_shank, 0.005 * v_shank)

    # --- shoulder + head bosses ---------------------------------------------
    check("create_sketch shoulder", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, TS_SH_R / 1000.0) is None:
            raise RuntimeError("shoulder circle failed")
    check("exit_sketch shoulder", await adapter.exit_sketch())
    name_last_feature(adapter, "ShoulderProfile")
    check("shoulder boss", await adapter.create_extrusion(ExtrusionParameters(
        depth=TS_SH_H)))
    name_last_feature(adapter, "Shoulder")
    v_sh = math.pi * TS_SH_R ** 2 * TS_SH_H
    await volume_check(adapter, "shoulder boss", v_shank + v_sh, 0.005 * v_sh)

    offset_plane(adapter, "HeadBasePlane", head_base)
    check("create_sketch head", await adapter.create_sketch("HeadBasePlane"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, TS_HEAD_R / 1000.0) is None:
            raise RuntimeError("head circle failed")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    check("head boss", await adapter.create_extrusion(ExtrusionParameters(
        depth=TS_HEAD_H)))
    name_last_feature(adapter, "Head")
    v_head = math.pi * TS_HEAD_R ** 2 * TS_HEAD_H
    await volume_check(adapter, "head boss",
                       v_shank + v_sh + v_head, 0.005 * v_head)

    # --- flare: revolve-cut the chord+arc lens off the shoulder -------------
    # Geometry and its derivation: :func:`flare_profile` (module level, so the
    # offline closure test asserts against the real thing).
    #
    # Inference must stay OFF here for a reason this file recorded the hard
    # way: the lens endpoints lie exactly ON the shoulder-OD silhouette, and
    # pixel-snapping MOVED the lower one (0.635 became 0.5, observed as a
    # 1.5 mm^2 torus-area drift).  What this block used to do about the
    # resulting open profile was merge the endpoints through
    # ``IModelDoc2.SketchAddConstraints("sgMERGEPOINTS")`` -- which SILENTLY
    # NO-OPS on SW 2026/3DEXPERIENCE (see the note on
    # ``_add_sketch_constraint_impl`` in the MCP sketch adapter).  So the
    # nearest-endpoint search, the selection dance and the constraint call
    # were all dead code, and this profile has been closing on nothing but
    # coincident coordinates and a tolerant revolve.  ``draw_closed_profile``
    # relates the endpoints through ``ISketchRelationManager.AddRelation``,
    # which does not no-op, and CHECKS each relation.
    check("create_sketch flare", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        # Revolve axis: raw construction geometry, drawn under the same
        # suppression as the profile so it cannot snap to the silhouette
        # either.
        if adapter.currentSketchManager.CreateCenterLine(
                0.0, 0.0, 0.0, 0.0, 1.0 / 1000.0, 0.0) is None:
            raise RuntimeError("flare centerline failed")
    await draw_closed_profile(adapter, flare_profile(), label="flare lens", loops=1)
    check("exit_sketch flare", await adapter.exit_sketch())
    name_last_feature(adapter, "FlareProfile")
    # The revolve axis is construction geometry in this same sketch, which is
    # exactly why the contour COUNT is not allowed to fail a build here -- see
    # assert_profile_closed.  Zero contours still does.
    assert_profile_closed(
        adapter, "flare lens", loops=1, feature="FlareProfile"
    )
    check("flare cut", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=True)))
    name_last_feature(adapter, "FlareCut")

    # --- head rim chamfers ---------------------------------------------------
    check("chamfer2", await adapter.add_chamfer(ch2, [
        [TS_HEAD_R, head_top, 0.0],
        [TS_HEAD_R, head_base, 0.0],
    ]))
    name_last_feature(adapter, "HeadChamfers")
    v_before_split = mass_properties(adapter)["volume_mm3"]
    _telemetry.info(f"pre-thread volume: {v_before_split}")

    # --- split, thread, runout ----------------------------------------------
    body_boxes = split_at_plane(adapter, "Top Plane", "ThreadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    offset_plane(adapter, "TipPlane", tip_y)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, major_r / 1000.0) is None:
            raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, (TS_LEN + pitch) / pitch, clockwise=False,
                 reversed_dir=False, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    # Vendor 6-gon cutter: 60-deg flanks crossing the major radius at the
    # tip and tip+7P/8, root flat P/8 wide at tip+7P/16, and the flanks
    # extended past the major radius to a top flat at major+0.254.
    ext = 0.254
    ext_dx = ext / math.sqrt(3.0)
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (major_r + ext, tip_y + ext_dx),                       # top corner (tip side)
            (major_r, tip_y),                                      # flank crosses major at tip
            (root_r, tip_y - 3.0 * pitch / 8.0),                   # root flat (tip side)
            (root_r, tip_y - 4.0 * pitch / 8.0),                   # root flat (far side)
            (major_r, tip_y - 7.0 * pitch / 8.0),                  # flank crosses major
            (major_r + ext, tip_y - 7.0 * pitch / 8.0 - ext_dx),   # top corner (far side)
        ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name,
                     "ThreadGroove", tangency=(0, 0))

    check("create_sketch runout", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, major_r / 1000.0) is None:
            raise RuntimeError("runout circle failed")
    check("exit_sketch runout", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "RunoutProfile").Select2(False, 0)
    feat = fm.FeatureExtrusion3(
        True, False, True,               # single ended, down
        2, 0, 0.0, 0.0,                  # UpToNext (vendor end_cond1=2)
        True, False, False, False,       # 20-deg draft, shrinking
        math.radians(20.0), 0.0,
        False, False, False, False,
        True, False, True,               # Merge -> re-unites the bodies
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
    v_after_thread = mass_properties(adapter)["volume_mm3"]
    _telemetry.info(f"post-thread volume: {v_after_thread}")

    # --- knurl: diagonal stripe cut, mirrored, patterned x36 ----------------
    offset_plane(adapter, "KnurlSidePlane", TS_HEAD_R + 0.5,
                 base="Front Plane")
    check("create_sketch knurl stripe",
          await adapter.create_sketch("KnurlSidePlane"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (-1.029926, 6.316747),
            (-0.921732, 6.383253),
            (1.029926, 3.208253),
            (0.921732, 3.141747),
        ])
    check("exit_sketch knurl stripe", await adapter.exit_sketch())
    name_last_feature(adapter, "KnurlStripe")

    selmgr = _early_bound(_read_member(model, "SelectionManager"),
                          "ISelectionMgr")

    def _select_head_od(mark: int) -> bool:
        from solidworks_mcp.adapters.solidworks.features import _all_body_faces
        for f in _all_body_faces(adapter):
            f2 = _early_bound(f, "IFace2")
            surf = _early_bound(f2.GetSurface(), "ISurface")
            try:
                cp = list(_read_member(surf, "CylinderParams") or [])
            except Exception:
                continue
            if len(cp) < 7 or abs(cp[6] * 1000.0 - TS_HEAD_R) > 1e-3:
                continue
            box = [float(v) * 1000.0 for v in (f2.GetBox() or [])]
            if not box or min(box[1], box[4]) < head_base - 0.5:
                continue
            sd = selmgr.CreateSelectData
            if callable(sd):
                sd = sd()
            sd = _early_bound(sd, "ISelectData")
            sd.Mark = mark
            ent = _early_bound(f2, "IEntity")
            return bool(ent.Select4(True, sd))
        return False

    feat = None
    for dir_flag in (False, True):
        for off_rev in (False, True):
            model.ClearSelection2(True)
            _feature_by_name(adapter, "KnurlStripe").Select2(False, 0)
            if not _select_head_od(1):
                raise RuntimeError("head OD face selection failed")
            feat = fm.FeatureCut4(
                True, False, dir_flag, 5, 0,     # OffsetFromSurface
                0.127 / 1000.0, 0.0,
                False, False, False, False, 0.0, 0.0,
                off_rev, False, True, False,     # TranslateSurface1: vendor
                False, False, True, False, False, False,  # floors = shifted OD
                0, 0.0, False, False)
            if feat is not None:
                _telemetry.info(f"knurl cut ok: dir={dir_flag} "
                                f"offset_rev={off_rev}")
                break
        if feat is not None:
            break
    if feat is None:
        capture_com_failure(
            adapter,
            "knurl-stripe-cut",
            "knurl stripe cut failed (all flag combos)",
            api="IFeatureManager.FeatureCut4",
            sketch="KnurlStripe",
        )
    name_last_feature(adapter, "KnurlGroove")
    v_knurl1 = mass_properties(adapter)["volume_mm3"]
    _telemetry.info(f"one-groove volume: {v_knurl1} "
                    f"(removed {v_after_thread - v_knurl1:.4f})")

    # Mirror across FRONT -- the plane PERPENDICULAR to the cut direction --
    # not Right.  Both land the mirrored stripe on the 10-deg pattern grid,
    # but Right keeps the floor's translation direction (-z), so at the
    # on-grid crossing the two grooves' translated-OD floors COINCIDE and
    # their fragments fuse (observed: 3 floor faces per groove instead of
    # the vendor's 4, exactly 72 faces short).  Front flips the translation,
    # the floors differ everywhere, and the crossings split cleanly.
    check("knurl mirror", await adapter.mirror_feature(MirrorFeatureParameters(
        plane="Front Plane", features=["KnurlGroove"])))
    name_last_feature(adapter, "KnurlMirror")

    check("pattern axis", await adapter.create_axis(CreateAxisParameters(
        mode="two_planes", planes=["Front Plane", "Right Plane"])))
    name_last_feature(adapter, "PatternAxis")
    # geometry_pattern=True (vendor used a re-solved pattern, but re-solve
    # fails through the adapter with the Front-mirrored seed; a geometry
    # pattern of the same seeds is rotationally identical here).
    check("knurl pattern", await adapter.circular_pattern_feature(
        CircularPatternParameters(
            axis_name="PatternAxis",
            features=["KnurlGroove", "KnurlMirror"],
            count=36, angle=360.0, equal_spacing=True,
            geometry_pattern=True)))
    name_last_feature(adapter, "KnurlPattern")

    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("99607A213", build_99607A213))
