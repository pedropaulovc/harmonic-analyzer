r"""McMaster 9490T1 -- #10-24 routing eyebolt (counter-spring lower anchor).
Native rebuild: no imported body, no dump replay.

Vendor tree (harvest ``cad/out/reports/mcmaster-9490T1-dump.json``)::

    Sketch1         master layout (Wire OD / Thread OD 4.826, Eye Dia
                    7.9375, Thread Lg. 58.7375, bend 4.7625)
    Sketch2 ->      shank OD 4.826 over the threaded length
    Boss-Extrude1   (-67.53225 .. -8.79475)
    Sketch3 ->      pitch 1.0583333, 56.5 revs, start 90 deg, height
    Helix/Spiral1   "Pitch + Thread Lg." = 59.795833
    Sketch4         UN cutter: 60 deg V, P/8 root flat, 15P/16 cap, centred
                    7P/16 below the end face
    Cut-Sweep1      the thread groove
    Sketch5 ->      45 deg deburr off the shank's free end: circle
    Cut-Extrude1    r 1.611024, draft 45 deg, through all, side flipped
    Sketch6         wire profile: circle OD 4.826 at the shank top
    Sketch7         wire centreline: bend arc R2.869189 -> eye arc R6.38175
    Sweep1          the wire, as a SECOND body
    Combine1        add (2 bodies -> 1)
    Dome1           wire tip, height "Thread OD / 2" = 2.413
    SketchX         cosmetic thread callout -- no solid geometry

Every dimension comes from :mod:`stock_anchor_geom` (vendor equations and
read-backs, no COM).  Both sketched profiles land on the vendor's own
coordinates: the cutter chain reproduces Sketch4's four corners
(2.470284, -67.499177) (1.725592, -67.929125) (1.725592, -68.061417)
(2.470284, -68.491365) exactly, and the wire path reproduces Sketch7's two
arcs, endpoints and centres included.

Frame: the vendor's own, kept as-is (``_mcm_com_map = None``) -- eye centred
on the origin in the model XY plane (the Front plane, where Sketch7's
coordinates ARE model x/y), shank down the -Y axis, wire tip at +X.

Three deliberate deviations from the vendor's feature tree, all of which leave
the same solid:

1. The deburr is a Chamfer feature, and it is cut BEFORE the groove instead
   of after.  Both removals are pure subtractions of the same two solids from
   the same cylinder, so the order cannot change the result -- but it does
   change what there is to select: before the groove the shank's end edge is
   one full circle, after it three arcs.  The rails allow for it: the two
   removals overlap by 2.601966 mm^3, which
   :func:`stock_anchor_geom.end_chamfer_groove_overlap_mm3` gives in closed
   form.
2. Sweep1 is authored with a circular profile and ``Merge = True`` rather
   than the vendor's sketched circle (Sketch6) + separate body + Combine1
   "add".  A circular profile IS the vendor's Sketch6 -- same diameter, same
   plane normal to the path -- and merging two touching bodies at creation is
   Combine1's own result, so Combine1 has nothing left to do.
3. Boss-Extrude1 is authored between the vendor's own two stations
   (``swStartOffset`` + blind depth) instead of their layout-driven end
   condition.

Analytic closure of the recipe (pure geometry, no COM): shank 1074.4346 - end
chamfer 4.3355 - groove (273.3831 - 2.6020 the chamfer already took) + wire
tube 586.1823 (Weyl, path 32.045586) + dome 29.4260 (hemisphere, r 2.413) =
1414.9262 mm^3 against the vendor's 1414.8951, i.e. +0.0022 %.  The area
closes the same way: the dump's ten faces sum to 1871.2849, which is the
vendor's own surface area.

The production shank is shortened AFTER the complete stock anchor is built.
An axial trim and a revolved 45-degree deburr reproduce the physical operation
without changing the factory thread phase. A shortened sweep is not equivalent:
its end treatment and phase require independent verification. The per-length
thread-volume estimate is not used as a truth value for the trimmed solid.
Both trim sketches require ``no_sketch_inference`` (SketchManager.AddToDB):
inference can snap the deburr profile to nearby thread edges and change the
solid even when the requested coordinates are correct.

``truth`` is accepted for :func:`diag_mcmaster_lib.run_replica` (which gates
the finished part) and is deliberately not read while building.

Run standalone (SolidWorks open)::

    uv run python cad/scripts/diagnostics/diag_build_9490T1.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters
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
    ANCHOR_9490T1,
    PathArc,
    ShankTrim,
    end_chamfer_groove_overlap_mm3,
    eye_path_mm,
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
)

A = ANCHOR_9490T1

# swconst values read off this install's swconst.tlb (SW 3DEXPERIENCE R2026x).
SW_FM_SWEEP = 17  # swFeatureNameID_e.swFmSweep
SW_FM_SWEEP_CUT = 18  # swFeatureNameID_e.swFmSweepCut
SW_TWIST_FOLLOW_PATH = 0  # swTwistControlType_e.swTwistControlFollowPath
SW_TANGENCY_NONE = 0  # swTangencyType_e.swTangencyNone
SW_PATH_ALIGN_NONE = 0  # 9490T1's OWN PathAlignmentType read-back (not 10)

PART_FACES = 10  # thread land, root, 2 flanks, chamfer cone, end disc,
# shank-top seam (the groove's bite at y=-8.79475), eye torus, bend torus,
# and the wire's tip cap -- which the dome replaces in kind, so the count is
# the same before and after Dome1 and matches the vendor's own ten faces.


# --------------------------------------------------------------------------
# COM helpers -- this part's own read-back option sets
# --------------------------------------------------------------------------
def _sweep_wire(adapter, path: str, feature_name: str) -> None:
    """Vendor Sweep1 + Combine1: circular profile of the wire along ``path``.

    Read-back set of THIS part's Sweep1: AlignWithEndFaces False,
    TwistControlType 0, PathAlignmentType 0, Direction -1, MergeSmoothFaces
    True, MaintainTangency False, AdvancedSmoothing False, Start/EndTangency
    0/0, FeatureScope True, AutoSelect False, CircularProfile False.  Two
    values are authored differently on purpose (see the module docstring):
    ``CircularProfile`` stands in for the vendor's Sketch6, and ``Merge`` is
    True, which is Combine1's "add" done at creation.
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
    """Vendor Cut-Sweep1, with 9490T1's read-back option values.

    ``diag_mcmaster_lib.thread_sweep_cut_modern`` is the same authoring route
    but hardcodes 94025A150's set (PathAlignmentType 10, tangency 1/1); this
    part stores PathAlignmentType 0 and tangency 0/0, so its own values are
    written here.  The obsolete ``InsertCutSwept5`` path is not used: it
    under-removes ~0.4 % of the groove (measured on 91829A560 and 94025A150),
    which this part's 0.02 % volume gate would not survive.  The vendor scoped
    theirs to their only body; this adapter's cut is ``AutoSelect`` over the
    same single body.
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


def _select_face_mark1(adapter, point_mm: list[float], tol_mm: float = 0.05) -> None:
    """Select the one face carrying ``point_mm``, with selection mark 1.

    ``InsertDome`` documents mark 1 as a precondition, and the shared
    ``_select_faces_geometric`` selects with mark 0, so the geometric walk is
    repeated here with the mark the dome needs.  Resolution is by
    ``IFace2.GetClosestPointOn``, exactly as the shared helper does it: the
    wire's tip cap contains its own centre, so its distance is 0, while the
    nearest rival (the eye torus the cap is cut from) is a full wire radius
    away -- a 0.05 mm window cannot pick the wrong one.
    """
    from solidworks_mcp.adapters.solidworks.features import (
        _all_body_faces,
        _flag_feature_methods,
    )

    px, py, pz = (c / 1000.0 for c in point_mm)
    tol_m = tol_mm / 1000.0
    best, best_d = None, tol_m
    for face in _all_body_faces(adapter):
        near = adapter._attempt(
            lambda f=face: list(f.GetClosestPointOn(px, py, pz)), default=None
        )
        if not near or len(near) < 3:
            continue
        d = math.dist(near[:3], (px, py, pz))
        if d < best_d:
            best, best_d = face, d
    if best is None:
        raise RuntimeError(
            f"no face within {tol_mm} mm of {point_mm} to put the dome on"
        )
    adapter.currentModel.ClearSelection2(True)
    entity = _flag_feature_methods(best, "IEntity", "Select2")
    if not adapter._attempt(lambda e=entity: e.Select2(False, 1), default=False):
        raise RuntimeError(f"cannot select dome face at {point_mm} (mark 1)")


# --------------------------------------------------------------------------
# features
# --------------------------------------------------------------------------
async def _wire_path(adapter, feature_name: str) -> None:
    """Vendor Sketch7: eye arc R6.38175 -> bend arc R2.869189, on Front.

    Front-plane sketch coordinates ARE model (x, y) here (Sketch7 harvests
    with an identity transform), so the vendor's published endpoints and
    centres go in unchanged.  The vendor drew the pair shank-end first; a
    circular profile sweeps the same tube either way round, and tip-first is
    the order :func:`stock_anchor_geom.eye_path_mm` publishes for both
    anchors.  ``CreateArc`` takes TEN arguments -- centre, start and end
    points in metres, each with its own z, then the direction flag (+1 CCW,
    -1 CW) -- and needs ``AddToDB`` while the arcs are drawn.
    """
    check("create_sketch wire path", await adapter.create_sketch("Front"))
    sk = _sketch_manager(adapter)
    prev_db = bool(sk.AddToDB)
    sk.AddToDB = True
    try:
        for segment in eye_path_mm(A):
            if not isinstance(segment, PathArc):
                raise RuntimeError(f"9490T1 wire path is all arcs, got {segment!r}")
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
    finally:
        sk.AddToDB = prev_db
    check("exit_sketch wire path", await adapter.exit_sketch())
    name_last_feature(adapter, feature_name)


async def _thread(adapter) -> None:
    """Build the factory Sketch3 + Helix/Spiral1 + Sketch4 + Cut-Sweep1.

    The datum, helix and cutter use only the stock anchor's dimensions.
    Production shortening happens later as a physical cut of this solid.
    """
    offset_plane(adapter, "ThreadDatum", A.shank_end_y_mm)
    check("create_sketch helix seed", await adapter.create_sketch("ThreadDatum"))
    seed = _sketch_manager(adapter).CreateCircleByRadius(
        0.0, 0.0, 0.0, A.thread_major_radius_mm / 1000.0
    )
    if seed is None:
        raise RuntimeError("helix seed circle failed")
    # InsertHelix consumes the ACTIVE sketch.  In this Top-offset frame,
    # clockwise=False and reversed_dir=False match the supplier's helix in
    # model space; pi/2 starts on +X, the cutter's meridian.  Native helix
    # samples and cutter corners agree with 9490T1's supplier within 1e-12 mm.
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


@_telemetry.traced("stock.shank.trim")
async def _trim_factory_shank(adapter, cut: ShankTrim) -> None:
    """Physically trim stock; AddToDB prevents snapping to nearby thread edges."""
    radius, chamfer = A.thread_major_radius_mm, A.end_chamfer_mm
    y = cut.shank_end_y_mm
    with no_sketch_inference(adapter):
        check("create trim sketch", await adapter.create_sketch("Front"))
        await add_line_chain(
            adapter,
            [
                [-2 * radius, A.shank_end_y_mm - A.thread_major_dia_mm],
                [2 * radius, A.shank_end_y_mm - A.thread_major_dia_mm],
                [2 * radius, y],
                [-2 * radius, y],
            ],
        )
        check("close trim sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StockTrimProfile")
        check(
            "trim stock shank",
            await adapter.create_cut_extrude(
                ExtrusionParameters(
                    depth=4 * A.thread_major_dia_mm, both_directions=True
                )
            ),
        )
        name_last_feature(adapter, "StockTrim")
        check("create deburr sketch", await adapter.create_sketch("Front"))
        await add_line_chain(
            adapter,
            [
                [radius - chamfer, y],
                [radius + chamfer, y],
                [radius + chamfer, y + chamfer],
                [radius, y + chamfer],
            ],
        )
        axis = _sketch_manager(adapter).CreateCenterLine(
            0, (y - chamfer) / 1000, 0, 0, (y + 2 * chamfer) / 1000, 0
        )
        if axis is None:
            raise RuntimeError("stock deburr axis failed")
        check("close deburr sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StockDeburrProfile")
        check(
            "deburr trimmed stock",
            await adapter.create_revolve(RevolveParameters(angle=360, is_cut=True)),
        )
        name_last_feature(adapter, "StockDeburr")
    solid_bodies = bodies(adapter)
    if len(solid_bodies) != 1:
        raise RuntimeError("stock trim must leave one solid anchor")
    body = _early_bound(solid_bodies[0], "IBody2")
    extent = body.GetExtremePoint(0, -1, 0)
    if not extent[0] or abs(extent[2] * 1000 - y) > 1e-6:
        raise RuntimeError(f"trimmed shank end {extent} does not match Y={y} mm")
    _telemetry.event(
        "stock.trimmed",
        length_mm=cut.shank_length_mm,
        removed_mm=cut.removed_length_mm,
        end_y_mm=y,
    )


# --------------------------------------------------------------------------
# builder
# --------------------------------------------------------------------------
async def build_9490T1(adapter, truth=None, *, shank_length_mm: float | None = None):
    """Build 9490T1 into the current (empty) part.  Never opens or saves.

    ``shank_length_mm=None`` reproduces the vendor part exactly (58.7375 mm).
    A shorter length physically trims that complete solid and restores its
    end deburr; it never re-seeds or rotates the factory thread.
    """
    requested_cut = trim(A, shank_length_mm)
    _telemetry.info(
        f"9490T1: {A.thread_size} shank {A.shank_length_mm} mm "
        f"(OD {A.thread_major_dia_mm} from y={A.shank_end_y_mm}), wire "
        f"{A.wire_dia_mm} on eye R{A.eye_mean_radius_mm}, helix "
        f"{A.thread_helix_height_mm:.5f} mm x {A.thread_helix_revolutions:g} "
        f"revs at pitch {A.thread_pitch_mm}, dome {A.dome_height_mm}"
    )

    with no_sketch_inference(adapter):
        # --- shank (vendor Sketch2 + Boss-Extrude1) ------------------------
        check("create_sketch shank", await adapter.create_sketch("Top"))
        await define_circle(adapter, 0.0, 0.0, A.thread_major_radius_mm, "shank")
        check("exit_sketch shank", await adapter.exit_sketch())
        name_last_feature(adapter, "ShankProfile")
        extrude_at_offset(adapter, A.shank_length_mm, A.shank_end_y_mm)
        name_last_feature(adapter, "Shank")
        shank_v = math.pi * A.thread_major_radius_mm**2 * A.shank_length_mm
        volume = await volume_check(adapter, "shank", shank_v, 0.002 * shank_v)

    # --- deburr (vendor Sketch5 + Cut-Extrude1, brought forward) -----------
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
    # Analytic check of the factory groove, net of the chamfer overlap.
    # The final stock gate below uses supplier truth; this estimate does not
    # supply mass properties for a physically trimmed production anchor.
    groove_v = A.shank_length_mm * thread_groove_volume_per_mm_mm3(
        A
    ) - end_chamfer_groove_overlap_mm3(A)
    volume = await volume_check(
        adapter, "thread groove", volume - groove_v, 0.005 * groove_v
    )

    # --- wire (vendor Sketch7 + Sweep1 + Combine1) -------------------------
    with no_sketch_inference(adapter):
        await _wire_path(adapter, "WirePath")
    _sweep_wire(adapter, "WirePath", "Wire")
    if len(bodies(adapter)) != 1:
        raise RuntimeError(
            f"wire sweep left {len(bodies(adapter))} bodies, expected 1 merged "
            "eyebolt (Merge=True stands in for the vendor's Combine1)"
        )
    # Weyl: a tube of radius r about an embedded curve is exactly pi r^2 L.
    # Both arcs curve well inside the tube's own radius (1/R = 0.157 and 0.348
    # against 1/r = 0.414), so nothing folds over itself, and the tube meets
    # the shank on a flat cap at y=-8.79475 -- the wire ADDS its whole volume,
    # the shank's top face surviving only as the groove's bite (4.6559 mm^2 of
    # the dump's ten faces).
    path_len = sum(
        segment.radius_mm * math.radians(segment.sweep_deg)
        for segment in eye_path_mm(A)
    )
    wire_v = math.pi * A.wire_radius_mm**2 * path_len
    volume = await volume_check(adapter, "wire", volume + wire_v, 0.003 * wire_v)
    if _face_counts(adapter) != [PART_FACES]:
        raise RuntimeError(
            f"pre-dome bodies/faces {_face_counts(adapter)}, expected "
            f"[{PART_FACES}] (thread land, root, 2 flanks, chamfer cone, end "
            "disc, shank-top seam, eye, bend, tip cap)"
        )

    # --- dome (vendor Dome1) -----------------------------------------------
    # Height = wire radius on a circular cap: the vendor's own face list shows
    # the result is a sphere (36.5843 mm^2 = 2 pi r^2), so it adds a clean
    # hemisphere.  The cap's centre is the eye arc's own start point.
    _select_face_mark1(adapter, [A.eye_open_tip_mm[0], A.eye_open_tip_mm[1], 0.0])
    with _telemetry.span("feature.dome", label="Dome1"):
        adapter.currentModel.InsertDome(
            A.dome_height_mm / 1000.0,  # metres
            False,  # ReverseDir -- the cap's normal already points off the wire
            False,  # DoEllipticSurface -- vendor read-back
        )
    adapter.currentModel.ClearSelection2(True)
    name_last_feature(adapter, "Dome1")
    dome_v = (2.0 / 3.0) * math.pi * A.dome_height_mm**3
    await volume_check(adapter, "dome", volume + dome_v, 0.01 * dome_v)

    # Prove the complete stock solid before applying a production modification.
    await volume_check(
        adapter, "9490T1 (vendor part)", A.truth.volume_mm3, 0.0002 * A.truth.volume_mm3
    )
    if _face_counts(adapter) != [PART_FACES]:
        raise RuntimeError(
            f"finished bodies/faces {_face_counts(adapter)}, expected "
            f"[{PART_FACES}] (thread land, root, 2 flanks, chamfer cone, end "
            "disc, shank-top seam, eye, bend, dome)"
        )
    if requested_cut.removed_length_mm:
        await _trim_factory_shank(adapter, requested_cut)

    # The replica is authored in the vendor's own frame: no COM remap.
    adapter._mcm_com_map = None


if __name__ == "__main__":
    sys.exit(replica_main("9490T1", build_9490T1))
