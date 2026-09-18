r"""McMaster 9489T111 -- #6-32 routing eyebolt with hex nut (channel-spring
lower anchor).  Native rebuild: no imported body, no dump replay.

Vendor tree (harvest ``cad/out/reports/mcmaster-9489T111-dump.json``)::

    Sketch1         master layout (Wire OD 3.175, Eye Dia 6.35, OD 12.7,
                    Shank Lg. 19.05, Thread OD 3.5052, Thread Lg. 15.875)
    Boss-Extrude1   shank OD 3.5052, the threaded length (-25.4 .. -9.525)
    Sketch8         wire centreline: eye arc R4.7625 -> bend arc R3.81
                    ("D1@Sketch8" = Shank Lg. * 0.2) -> straight neck
    Sweep1          circular profile 3.175 along Sketch8, merged
    Fillet1         wire tip round, "Thread OD / 4" = 0.8763
    Chamfer1        shank end 45 deg x "Thread OD * 0.13" = 0.455676
    Sketch9 ->      hex nut: across flats "Thread OD * 1.5" = 5.2578,
    Boss-Extrude2   height "Thread OD * 0.875" = 3.06705, seated
                    "Thread Lg. * 0.44" = 6.985 above the shank end
    Sketch10 ->     nut corner chamfers (60 deg from the axis) and bore
    Cut-Revolve1    chamfers ("Pitch / 8" = 0.099219 x 45 deg)
    Helix/Spiral1   pitch 0.79375, 21 revs, start 90 deg (height
                    "Pitch + Thread Lg." = 16.66875)
    Sketch4         UN cutter: 60 deg V, P/8 root flat, 15P/16 cap
    Cut-Sweep1      the thread groove, scoped to the bolt body
    SketchX         cosmetic thread callout -- no solid geometry

Every dimension comes from :mod:`stock_anchor_geom` (vendor equations and
read-backs, no COM), and both sketched profiles land on the vendor's own
coordinates: this script's cutter chain reproduces Sketch4's four corners
(1.795563, -25.375195) (1.237044, -25.697656) (1.237044, -25.796875)
(1.795563, -26.119336) exactly, and the nut chamfer contour reproduces
Sketch10's six corners including its 0.234804 mm cone depth.

Frame: the vendor's own, kept as-is (``_mcm_com_map = None``) -- eye centred
on the origin in the model XY plane, shank down the -Y axis, wire tip at +X.

Two deliberate deviations from the vendor's feature ORDER, both of which leave
the same solid (proven analytically below), and both forced by one fact: this
adapter's sweep cut and revolve cut are authored with ``UseFeatScope = False``
/ ``AutoSelect = True``, i.e. they cannot be scoped to one body of a
multi-body part the way the vendor scoped theirs.

1. The nut is built LAST, after the thread groove.  The vendor's Cut-Sweep1
   carries ``FeatureScope = True, AutoSelect = False`` because their cutter
   (top radius 1.795563) oversails the nut's 1.7526 bore by 0.043 mm: cut
   unscoped with the nut already present, it would shave ~1.3 mm^3 of helical
   slivers out of the nut's bore.  With the nut built afterwards, the bolt is
   the only body while the groove is cut, and the nut's bore then meets the
   already-threaded shank exactly as the vendor's does -- along the crest
   land, not a full cylinder.
2. The nut's two bore chamfers are a Chamfer feature instead of the second
   contour of Cut-Revolve1.  That contour's inner edge runs 0.0992 mm INSIDE
   the bore (air, for a cut scoped to the nut); unscoped it would cut two
   rings into the shank.  A 45 deg x 0.099219 chamfer on the bore's end edges
   is the identical cone, and it cannot reach another body.  The corner
   chamfers keep the vendor contour verbatim -- that loop lives at radius
   >= 2.6289, where no part of the bolt exists.

Analytic closure of the recipe (pure geometry, no COM): shank 153.1896 + wire
tube 255.0248 (Weyl, path 32.211063) - tip fillet 1.4411 (Pappus) - end
chamfer 1.0442 - groove (41.0861 - 0.6939 the chamfer already took, see
:func:`stock_anchor_geom.end_chamfer_groove_overlap_mm3`) = 365.3369 mm^3
against the vendor bolt's 365.7780, i.e. -0.12 %.  The residue is the groove's
runout into the Dia 3.175 neck, where the cutter leaves the shank gradually
and the per-mm law over-removes, plus ~0.12 mm^3 where the tip and bend tubes
overlap (a 24M-sample Monte-Carlo union of the swept wire reads 254.90
against Weyl's 255.02).  The nut closes exactly: hex ring 43.83141 - corner
cones 0.315560 - bore chamfers 0.110450 = 43.405397 against the vendor's
43.405400 (5e-8 relative).

``nut='omitted'`` plus a shorter ``shank_length_mm`` is the production
configuration: the anchor threads straight into the summing lever, so the
shipped nut is never installed and the free end is cut back to a stop INSIDE
the plate it threads into (``spring_hook_spec``).  Both gates above still run
on the COMPLETE stock solid -- the bolt BODY (365.7780 mm^3, 13 faces) -- and
the trim is applied afterwards, by
:func:`diag_mcmaster_lib.trim_factory_shank`, so the vendor's ``Shank Lg.``
(and the bend radius it drives) keeps its stock value.
The cut plane lies past the captive nut's seat, so a trim with the nut built
is rejected.  ``truth`` is accepted for
:func:`diag_mcmaster_lib.run_replica` (which gates the finished part) and is
deliberately not read while building.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_9489T111.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    _early_bound,
    add_line_chain,
    check,
    define_circle,
    extrude_at_offset,
    name_last_feature,
    volume_check,
)
from stock_anchor_geom import (  # noqa: E402
    ANCHOR_9489T111,
    PathArc,
    end_chamfer_groove_overlap_mm3,
    eye_path_mm,
    nut_corner_chamfer_contour_mm,
    nut_hex_profile_mm,
    thread_cutter_profile_mm,
    thread_groove_volume_per_mm_mm3,
    trim,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    bodies,
    insert_helix,
    no_sketch_inference,
    offset_plane,
    replica_main,
    trim_factory_shank,
)

A = ANCHOR_9489T111

# swconst values read off this install's swconst.tlb (SW 3DEXPERIENCE R2026x).
SW_FM_SWEEP = 17  # swFeatureNameID_e.swFmSweep
SW_FM_SWEEP_CUT = 18  # swFeatureNameID_e.swFmSweepCut
SW_TWIST_FOLLOW_PATH = 0  # swTwistControlType_e.swTwistControlFollowPath
SW_TANGENCY_NONE = 0  # swTangencyType_e.swTangencyNone
SW_PATH_ALIGN_NONE = 0  # 9489T111's OWN PathAlignmentType read-back (not 10)

NUT_CHOICES = ("included", "omitted")

BOLT_FACES = 13  # land, root, 2 flanks, groove wash, chamfer cone, end disc,
# neck annulus, wire cylinder, bend torus, eye torus, tip fillet, tip cap
NUT_FACES = 23  # 6 flats, 2 end rings, 12 corner cones, bore, 2 bore cones


# --------------------------------------------------------------------------
# COM helpers -- this part's own read-back option sets
# --------------------------------------------------------------------------
def _sweep_wire(adapter, path: str, feature_name: str) -> None:
    """Vendor Sweep1: circular profile of the wire diameter along ``path``.

    Read-back set of THIS part's Sweep1: AlignWithEndFaces False,
    TwistControlType 0, PathAlignmentType 0, Direction -1, MergeSmoothFaces
    True, MaintainTangency False, AdvancedSmoothing False, Start/EndTangency
    0/0, FeatureScope True, AutoSelect False, CircularProfile False.  Two
    values are pinned by the RESULT rather than the harvest: the profile is
    authored as a circular profile (identical tube, and it spares a reference
    plane normal to the path), and ``Merge`` is True because the vendor ships
    the wire and shank as one body.
    """
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    model = adapter.currentModel
    fm = _early_bound(model.FeatureManager, "IFeatureManager")
    data = _early_bound(fm.CreateDefinition(SW_FM_SWEEP), "ISweepFeatureData")
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, path, 4, False):
        raise RuntimeError(f"cannot select sweep path {path!r} (mark 4)")
    data.TangentPropagation = False
    data.AlignWithEndFaces = False
    data.TwistControlType = SW_TWIST_FOLLOW_PATH
    data.MaintainTangency = False
    data.AdvancedSmoothing = False
    data.StartTangencyType = SW_TANGENCY_NONE
    data.EndTangencyType = SW_TANGENCY_NONE
    data.PathAlignmentType = SW_PATH_ALIGN_NONE
    data.Direction = -1
    data.ThinFeature = False
    data.Merge = True
    data.FeatureScope = True
    data.AutoSelect = True
    data.MergeSmoothFaces = True
    data.CircularProfile = True
    data.CircularProfileDiameter = A.wire_dia_mm / 1000.0
    with _telemetry.span("feature.sweep_wire", label=feature_name):
        swept = fm.CreateFeature(data)
    model.ClearSelection2(True)
    if swept is None:
        raise RuntimeError(f"CreateFeature (sweep) returned None for {feature_name}")
    name_last_feature(adapter, feature_name)


def _thread_sweep_cut(adapter, profile: str, path: str, feature_name: str) -> None:
    """Vendor Cut-Sweep1, with 9489T111's read-back option values.

    ``diag_mcmaster_lib.thread_sweep_cut_modern`` is the same authoring route
    but hardcodes 94025A150's set (PathAlignmentType 10, tangency 1/1); this
    part stores PathAlignmentType 0 and tangency 0/0, so its own values are
    written here.  The obsolete ``InsertCutSwept5`` path is not used: it
    under-removes ~0.4 % of the groove (measured on 91829A560 and 94025A150),
    which this part's 0.02 % volume gate would not survive.  Feature scope is
    ``AutoSelect`` over a single body -- see the module docstring.
    """
    from solidworks_mcp.adapters.solidworks.features import _select_named_feature

    model = adapter.currentModel
    fm = _early_bound(model.FeatureManager, "IFeatureManager")
    data = _early_bound(fm.CreateDefinition(SW_FM_SWEEP_CUT), "ISweepFeatureData")
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, profile, 1, False):
        raise RuntimeError(f"cannot select sweep profile {profile!r} (mark 1)")
    if not _select_named_feature(adapter, path, 4, True):
        raise RuntimeError(f"cannot select sweep path {path!r} (mark 4)")
    data.AlignWithEndFaces = True
    data.TwistControlType = SW_TWIST_FOLLOW_PATH
    data.PathAlignmentType = SW_PATH_ALIGN_NONE
    data.Direction = -1
    data.MergeSmoothFaces = True
    data.MaintainTangency = False
    data.AdvancedSmoothing = False
    data.StartTangencyType = SW_TANGENCY_NONE
    data.EndTangencyType = SW_TANGENCY_NONE
    data.AutoSelect = True
    with _telemetry.span("feature.thread_sweep_cut", label=feature_name):
        swept = fm.CreateFeature(data)
    model.ClearSelection2(True)
    if swept is None:
        raise RuntimeError(
            f"CreateFeature (sweep cut) returned None for {feature_name}"
        )
    name_last_feature(adapter, feature_name)


def _sketch_manager(adapter):
    """The generated ``ISketchManager`` wrapper for raw sketch calls.

    ``CreateArc``'s ten arguments end in a COM ``short`` (Direction); the
    generated wrapper invokes the DISPID with the type library's own signature
    instead of guessing a variant for it, which is the route
    ``diag_build_9432K31`` proved.  ``_early_bound`` raises rather than handing
    back a raw dispatch, so a wrapper that needs regenerating fails here and
    not inside SolidWorks.
    """
    return _early_bound(adapter.currentModel.SketchManager, "ISketchManager")


# --------------------------------------------------------------------------
# features
# --------------------------------------------------------------------------
async def _wire_path(adapter, feature_name: str) -> None:
    """Vendor Sketch8: eye arc -> bend arc -> straight neck, on Front.

    Front-plane sketch coordinates ARE model (x, y) here, so the vendor's
    published endpoints go in unchanged.  ``CreateArc`` takes TEN arguments --
    centre, start and end points in metres, each with its own z, then the
    direction flag (+1 CCW, -1 CW) -- and needs ``AddToDB`` while the arcs are
    drawn, exactly like the other McMaster profile sketches.
    """
    check("create_sketch wire path", await adapter.create_sketch("Front"))
    sk = _sketch_manager(adapter)
    prev_db = bool(sk.AddToDB)
    sk.AddToDB = True
    try:
        for segment in eye_path_mm(A):
            if isinstance(segment, PathArc):
                arc = sk.CreateArc(
                    segment.centre_mm[0] / 1000.0,
                    segment.centre_mm[1] / 1000.0,
                    0.0,
                    segment.start_mm[0] / 1000.0,
                    segment.start_mm[1] / 1000.0,
                    0.0,
                    segment.end_mm[0] / 1000.0,
                    segment.end_mm[1] / 1000.0,
                    0.0,
                    1 if segment.ccw else -1,
                )
                if arc is None:
                    raise RuntimeError(
                        f"wire path: CreateArc failed for {segment.start_mm} -> "
                        f"{segment.end_mm}"
                    )
            else:
                await add_line_chain(
                    adapter, [segment.start_mm, segment.end_mm], close=False
                )
    finally:
        sk.AddToDB = prev_db
    check("exit_sketch wire path", await adapter.exit_sketch())
    name_last_feature(adapter, feature_name)


async def _thread(adapter) -> None:
    """Vendor Helix/Spiral1 + Sketch4 + Cut-Sweep1."""
    offset_plane(adapter, "ThreadDatum", A.shank_end_y_mm)
    check("create_sketch helix seed", await adapter.create_sketch("ThreadDatum"))
    with no_sketch_inference(adapter):
        seed = _sketch_manager(adapter).CreateCircleByRadius(
            0.0, 0.0, 0.0, A.thread_major_radius_mm / 1000.0
        )
        if seed is None:
            raise RuntimeError("helix seed circle failed")
    # InsertHelix consumes the ACTIVE sketch.  The datum plane is a negative
    # Top offset, so it carries the flipped normal: clockwise=False is the
    # vendor's right-hand thread in that frame and start angle pi/2 puts the
    # helix start on +X, the meridian the cutter is drawn on (proven on
    # 91829A560 / 93075A194, where the other flag left a mirrored thread).
    insert_helix(
        adapter,
        A.thread_pitch_mm,
        A.thread_helix_revolutions,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    check("create_sketch cutter", await adapter.create_sketch("Front"))
    await add_line_chain(adapter, [list(p) for p in thread_cutter_profile_mm(A)])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    _thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", "ThreadGroove")


def _face_counts(adapter) -> list[int]:
    """Face count of every solid body, in body order."""
    return [
        len(list(_early_bound(body, "IBody2").GetFaces() or []))
        for body in bodies(adapter)
    ]


async def _hex_nut(adapter, bolt_volume: float) -> float:
    """Vendor Sketch9 + Boss-Extrude2 + Sketch10 + Cut-Revolve1.

    Built last and unmerged (see the module docstring): the ring's bore is
    coincident with the shank's thread major, so ``merge_result=False`` keeps
    the captive nut the separate body the vendor ships.  ``bolt_volume`` is
    the measured part volume before the nut, so the finished nut is gated on
    its OWN delta and the bolt's tolerance does not leak in.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    nut = A.nut
    check("create_sketch nut", await adapter.create_sketch("Top"))
    await add_line_chain(adapter, [list(p) for p in nut_hex_profile_mm(nut)])
    await define_circle(adapter, 0.0, 0.0, nut.bore_radius_mm, "nut bore")
    check("exit_sketch nut", await adapter.exit_sketch())
    name_last_feature(adapter, "NutProfile")
    extrude_at_offset(adapter, nut.height_mm, nut.seat_y_mm, merge_result=False)
    name_last_feature(adapter, "NutRing")
    if len(bodies(adapter)) != 2:
        raise RuntimeError(
            f"nut ring left {len(bodies(adapter))} bodies, expected 2 (bolt + nut)"
        )
    ring = (
        1.5 * math.sqrt(3.0) * nut.corner_radius_mm**2 - math.pi * nut.bore_radius_mm**2
    ) * nut.height_mm
    await volume_check(adapter, "nut ring", bolt_volume + ring, 0.002 * ring)

    # Corner chamfers: Sketch10's outer contour verbatim (radius >= 2.6289,
    # where the bolt does not exist), revolved 360 deg about the shank axis.
    check("create_sketch nut corners", await adapter.create_sketch("Front"))
    sk = _sketch_manager(adapter)
    with no_sketch_inference(adapter):
        axis = sk.CreateCenterLine(
            0.0, nut.seat_y_mm / 1000.0, 0.0, 0.0, nut.top_y_mm / 1000.0, 0.0
        )
        if axis is None:
            raise RuntimeError("nut corners: CreateCenterLine failed")
    await add_line_chain(adapter, [list(p) for p in nut_corner_chamfer_contour_mm(nut)])
    check("exit_sketch nut corners", await adapter.exit_sketch())
    name_last_feature(adapter, "NutCornerProfile")
    check(
        "revolve-cut nut corners",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "NutCornerChamfers")

    check(
        "chamfer nut bore",
        await adapter.add_chamfer(
            nut.bore_chamfer_mm,
            [
                [nut.bore_radius_mm, nut.seat_y_mm, 0.0],
                [nut.bore_radius_mm, nut.top_y_mm, 0.0],
            ],
        ),
    )
    name_last_feature(adapter, "NutBoreChamfers")

    # The nut's own delta at the fleet gate's tolerance (0.02 %): hex ring
    # 43.83141 less the two 60 deg corner cones (0.315560) less the two 45 deg
    # bore chamfers (0.110450) = 43.405397 against the vendor's 43.405400.
    return await volume_check(
        adapter,
        "nut (vendor body)",
        bolt_volume + nut.truth.volume_mm3,
        0.0002 * nut.truth.volume_mm3,
    )


# --------------------------------------------------------------------------
# builder
# --------------------------------------------------------------------------
async def build_9489T111(
    adapter,
    truth=None,
    *,
    nut: str = "included",
    shank_length_mm: float | None = None,
):
    """Build 9489T111 into the current (empty) part.  Never opens or saves.

    ``nut='included'`` reproduces the vendor part (bolt + captive hex nut);
    ``nut='omitted'`` builds the bolt alone, which is how the anchor installs
    (threaded straight into the summing lever).

    ``shank_length_mm=None`` keeps the full factory shank (19.05 mm).  A
    shorter length physically trims the complete stock solid and restores its
    end deburr; it never re-seeds or rotates the factory thread, and the
    vendor's own ``Shank Lg.`` -- which drives the bend radius -- keeps its
    stock value.  The cut lands past the captive nut's seat, so trimming
    requires ``nut='omitted'``.
    """
    if nut not in NUT_CHOICES:
        raise ValueError(f"nut must be one of {NUT_CHOICES}, got {nut!r}")
    requested_cut = trim(A, shank_length_mm)
    if requested_cut.removed_length_mm and nut != "omitted":
        raise ValueError(
            "9489T111 cannot be trimmed with the captive nut built: its seat "
            f"at y={A.nut.seat_y_mm} is past the cut at "
            f"y={requested_cut.shank_end_y_mm}"
        )
    _telemetry.info(
        f"9489T111: {A.thread_size} shank {A.shank_length_mm} mm "
        f"(OD {A.thread_major_dia_mm} x thread {A.thread_length_mm} from "
        f"y={A.shank_end_y_mm}), wire {A.wire_dia_mm} on eye R"
        f"{A.eye_mean_radius_mm}, helix {A.thread_helix_height_mm:.5f} mm x "
        f"{A.thread_helix_revolutions:g} revs at pitch {A.thread_pitch_mm}, "
        f"nut {nut}, finished shank {requested_cut.shank_length_mm} mm"
    )

    with no_sketch_inference(adapter):
        # --- shank (vendor Boss-Extrude1) ----------------------------------
        check("create_sketch shank", await adapter.create_sketch("Top"))
        await define_circle(adapter, 0.0, 0.0, A.thread_major_radius_mm, "shank")
        check("exit_sketch shank", await adapter.exit_sketch())
        name_last_feature(adapter, "ShankProfile")
        extrude_at_offset(adapter, A.thread_length_mm, A.shank_end_y_mm)
        name_last_feature(adapter, "Shank")
        shank_v = math.pi * A.thread_major_radius_mm**2 * A.thread_length_mm
        volume = await volume_check(adapter, "shank", shank_v, 0.002 * shank_v)

        # --- wire (vendor Sketch8 + Sweep1) --------------------------------
        await _wire_path(adapter, "WirePath")

    _sweep_wire(adapter, "WirePath", "Wire")
    if len(bodies(adapter)) != 1:
        raise RuntimeError(
            f"wire sweep left {len(bodies(adapter))} bodies, expected 1 merged bolt"
        )
    # Weyl: a tube of radius r about an embedded curve is exactly pi r^2 L,
    # and the wire only ABUTS the shank's top face (no overlap to subtract).
    path_len = sum(
        segment.radius_mm * math.radians(segment.sweep_deg)
        if isinstance(segment, PathArc)
        else segment.length_mm
        for segment in eye_path_mm(A)
    )
    wire_v = math.pi * A.wire_radius_mm**2 * path_len
    volume = await volume_check(adapter, "wire", volume + wire_v, 0.003 * wire_v)

    # --- tip round + end chamfer (vendor Fillet1, Chamfer1) ----------------
    # The tip cap is normal to the path, so its rim runs through the cap
    # centre offset by the wire radius along the eye axis (+Z).
    check(
        "fillet wire tip",
        await adapter.add_fillet(
            A.tip_fillet_mm,
            [[A.eye_open_tip_mm[0], A.eye_open_tip_mm[1], A.wire_radius_mm]],
        ),
    )
    name_last_feature(adapter, "TipFillet")
    # Pappus about the wire axis: area R^2 (1 - pi/4) at the corner's centroid.
    r_w, r_f = A.wire_radius_mm, A.tip_fillet_mm
    fillet_v = (
        2.0
        * math.pi
        * (
            r_f * (2.0 * r_w * r_f - r_f * r_f) / 2.0
            - (math.pi * r_f * r_f / 4.0) * ((r_w - r_f) + 4.0 * r_f / (3.0 * math.pi))
        )
    )
    volume = await volume_check(
        adapter, "tip fillet", volume - fillet_v, 0.05 * fillet_v
    )

    check(
        "chamfer shank end",
        await adapter.add_chamfer(
            A.end_chamfer_mm,
            [[A.thread_major_radius_mm, A.shank_end_y_mm, 0.0]],
        ),
    )
    name_last_feature(adapter, "EndChamfer")
    chamfer_v = (
        math.pi
        * A.end_chamfer_mm**2
        * (A.thread_major_radius_mm - A.end_chamfer_mm / 3.0)
    )
    volume = await volume_check(
        adapter, "end chamfer", volume - chamfer_v, 0.02 * chamfer_v
    )

    # --- thread (vendor Helix/Spiral1 + Sketch4 + Cut-Sweep1) --------------
    with no_sketch_inference(adapter):
        await _thread(adapter)
    # The groove crosses the neck: below y=-9.525 it is bounded by the thread
    # major, above it by the thinner wire.  The end chamfer, already cut, took
    # 0.6939 of it.  What is left over is the runout, where the cutter climbs
    # out of the neck gradually and the per-mm law over-removes by ~1 % of the
    # groove -- the vendor's own numbers below are the gate, this is the shape
    # rail.
    groove_v = (
        A.thread_length_mm * thread_groove_volume_per_mm_mm3(A)
        + (A.thread_runout_y_mm - A.thread_start_y_mm)
        * thread_groove_volume_per_mm_mm3(A, clip_radius_mm=A.wire_radius_mm)
        - end_chamfer_groove_overlap_mm3(A)
    )
    volume = await volume_check(
        adapter, "thread groove", volume - groove_v, 0.03 * groove_v
    )

    # The vendor's own bolt body, at the fleet gate's tolerance (0.02 %).
    bolt_truth = A.body_truth[0][1]
    volume = await volume_check(
        adapter,
        "bolt (vendor body)",
        bolt_truth.volume_mm3,
        0.0002 * bolt_truth.volume_mm3,
    )
    if _face_counts(adapter) != [BOLT_FACES]:
        raise RuntimeError(
            f"bolt bodies/faces {_face_counts(adapter)}, expected [{BOLT_FACES}] "
            "(thread land, root, 2 flanks, groove wash, chamfer cone, end "
            "disc, neck annulus, wire, bend, eye, tip fillet, tip cap)"
        )

    # --- captive hex nut (vendor Sketch9..Cut-Revolve1, built last) --------
    if nut == "included":
        with no_sketch_inference(adapter):
            await _hex_nut(adapter, volume)
        counts = sorted(_face_counts(adapter))
        if counts != sorted((BOLT_FACES, NUT_FACES)):
            raise RuntimeError(
                f"finished part has bodies/faces {counts}, expected "
                f"{sorted((BOLT_FACES, NUT_FACES))} (bolt + 6 flats, 2 end "
                "rings, 12 corner cones, bore, 2 bore cones)"
            )
        await volume_check(
            adapter,
            "9489T111 (vendor part)",
            A.truth.volume_mm3,
            0.0002 * A.truth.volume_mm3,
        )
    else:
        _telemetry.info(
            "9489T111: nut omitted -- the anchor threads into the summing "
            f"lever, so only the bolt body ships ({bolt_truth.volume_mm3:.4f} "
            "mm^3, 13 faces)"
        )

    # Production modification, applied only once the stock solid is proven.
    # trim_factory_shank gates it: one solid body whose extreme -Y point IS the
    # cut plane. The face count is deliberately NOT re-asserted -- the cut
    # replaces the end disc and chamfer cone but also removes whatever the
    # vendor helix leaves at its free end, so the stock 13-face topology is not
    # a contract of the trimmed part (9490T1's trim asserts nothing either).
    if requested_cut.removed_length_mm:
        await trim_factory_shank(adapter, A, requested_cut)

    # The replica is authored in the vendor's own frame: no COM remap.
    adapter._mcm_com_map = None


if __name__ == "__main__":
    sys.exit(replica_main("9489T111", build_9489T111))
