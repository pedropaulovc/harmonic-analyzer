r"""McMaster 93585A190 -- 18-8 stainless high-profile knurled-head thumb screw,
1/4"-20 x 3/4".

The official 93585A190.SLDPRT recipe was read-only harvested on 2026-09-29
(vendor SLDPRT SHA-256
``f168d0847e364090ace8e7401b3563a388a8a01307ef9590decd5ac2218e5555``;
dump ``cad/out/reports/mcmaster-93585A190-dump.json``).  Sketch1 drives it:
Thread Size 6.35, Length 19.05, Head Diameter 15.875, Head Height 12.7,
Pitch 1.27.  Vendor tree, in order:

* Extrude1: dia 6.35 stud, 19.05 down (reversed) -> Chamfer2 on the tip,
  P*.75 = 0.9525.
* Sketch21 core circle dia HD*.98 = 15.5575 -> Boss-Extrude1/2/3 split the
  core into three NON-merged bands at z 0..0.635, 0.635..12.065 and
  12.065..12.7 (Plane2 / Plane1; band = HH*.05) -> Chamfer3 / Chamfer4
  (HH*.05 = 0.635) on the two outer band rims -> Combine1 adds the 4 bodies.
* Thread: Helix/Spiral1 seeded on the tip (Sketch15 dia 6.35 at z -19.05),
  pitch 1.27, height L+P = 20.32, start 90 deg; Sketch14 cutter = closed
  4-gon with its top edge ON the major radius (7P/8 wide), 60-deg flanks
  and a P/8 root flat at major - 0.75*H -> Cut-Sweep1.
* Knurl: Sketch26 on Plane1 = one straight ridge (base arc on the core
  radius, crest arc on HD/2, crest width 0.127, flanks 20 deg off the
  ridge's radial centreline) -> Boss-Extrude4 up to Plane2 (merged) ->
  CirPattern1, 131 instances equal over 360 deg, geometry pattern
  (vendor equation HD*3.14/0.015 with HD in inches, rounded).
* Sketch37: 0.79375 x 0.79375 triangle revolve-cut off the head-top rim
  (Cut-Revolve4; its cone coincides with Chamfer4's and trims the ridge
  tops) -> Mirror1 across Plane3 (z = HH/2) for the bottom rim.
* Boss-Extrude7: Sketch38 dia 6.35 circle at z 0, both directions -- dir1
  blind 2.54 with a 45-deg inward draft (the thread's run-out cone into the
  head), dir2 up to the head-top face (re-fills the thread groove the sweep
  cut into the head underside).

Frame: the replica is authored in the ``diag_mcmaster_thumb`` convention --
axis = model Y, head underside (bearing face) at y = 0, head up to +12.7,
stud down to -19.05.  The vendor axis is Z, so the COM map is
``(x, y, z)_vendor -> (y, z, x)_replica``.

Deviations from the vendor authoring (geometry identical): the band
bosses and the ridge boss use blind depths equal to the vendor's up-to
vertex/plane distances, and Boss-Extrude7 dir2 is blind HH (ends on the
head-top face) instead of up-to-surface.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_93585A190.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

import _seat_forensics  # noqa: E402
import _telemetry  # noqa: E402
if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import check  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    assert_profile_closed,
    combine_union,
    draw_closed_profile,
    insert_helix,
    mass_properties,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)
from diagnostics.sketch_profile import (  # noqa: E402
    Line,
    Segment,
    minor_arc,
)

from _mcmaster_93585a190 import (  # noqa: E402
    MAJOR_R,
    PITCH,
    LENGTH,
    HEAD_R,
    HEAD_H,
    RIM_CHAMFER,
    TIP_CHAMFER,
    CORE_R,
    BAND_H,
    KNURL_COUNT,
    KNURL_CREST_W,
    KNURL_FLANK_DEG,
    RUNOUT_DEPTH,
    RUNOUT_DRAFT_DEG,
    ROOT_R,
)


def knurl_ridge_profile() -> tuple[Segment, ...]:
    """One Sketch26 ridge in the Plane1 sketch, centred on sketch +x.

    Crest arc on HEAD_R, ``KNURL_CREST_W`` wide; flanks leave the crest ends
    ``KNURL_FLANK_DEG`` off the ridge's radial centreline and land on the
    core radius, closed by the base arc on CORE_R (vendor: half-widths
    0.0635 / 0.121533).  Pure: no COM.
    """
    half = KNURL_CREST_W / 2.0
    crest_r = math.sqrt(HEAD_R**2 - half**2)
    s = math.sin(math.radians(KNURL_FLANK_DEG))
    c = math.cos(math.radians(KNURL_FLANK_DEG))
    # (half + t*s, crest_r - t*c) on the circle of radius CORE_R.
    b = half * s - crest_r * c
    t = -b - math.sqrt(b * b - (HEAD_R**2 - CORE_R**2))
    base_half = half + t * s
    base_r = crest_r - t * c
    crest_p, crest_m = (crest_r, half), (crest_r, -half)
    base_p, base_m = (base_r, base_half), (base_r, -base_half)
    origin = (0.0, 0.0)
    return (
        Line(base_p, crest_p),
        minor_arc(origin, crest_p, crest_m),
        Line(crest_m, base_m),
        minor_arc(origin, base_m, base_p),
    )


def thread_cutter_profile() -> tuple[Segment, ...]:
    """Sketch14 on Front: top edge on the major radius from the tip to
    tip - 7P/8, 60-deg flanks down to the P/8 root flat at tip - P/2 ..
    tip - 3P/8.  Pure: no COM."""
    tip = -LENGTH
    a = (MAJOR_R, tip)
    b = (MAJOR_R, tip - 7.0 * PITCH / 8.0)
    c = (ROOT_R, tip - PITCH / 2.0)
    d = (ROOT_R, tip - 3.0 * PITCH / 8.0)
    return (Line(a, b), Line(b, c), Line(c, d), Line(d, a))


def rim_cut_profile() -> tuple[Segment, ...]:
    """Sketch37 on Front: the head-top rim triangle (legs RIM_CHAMFER)."""
    a = (HEAD_R, HEAD_H)
    b = (HEAD_R, HEAD_H - RIM_CHAMFER)
    c = (HEAD_R - RIM_CHAMFER, HEAD_H)
    return (Line(a, b), Line(b, c), Line(c, a))


@stock_recipe("93585A190", threaded=True)
async def build_93585A190(adapter, truth=None):
    from _com import _early_bound, _read_member
    from _feature_tree import _feature_by_name
    from diagnostics.diag_mcmaster_lib import no_sketch_inference
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateAxisParameters,
        ExtrusionParameters,
        MirrorFeatureParameters,
        RevolveParameters,
    )

    tip_y = -LENGTH

    async def circle_sketch(plane: str, r: float, name: str) -> None:
        check(f"create_sketch {name}", await adapter.create_sketch(plane))
        with no_sketch_inference(adapter):
            if (
                adapter.currentSketchManager.CreateCircleByRadius(
                    0.0, 0.0, 0.0, r / 1000.0
                )
                is None
            ):
                raise RuntimeError(f"{name}: circle failed")
        check(f"exit_sketch {name}", await adapter.exit_sketch())
        name_last_feature(adapter, name)

    # --- Extrude1 stud + Chamfer2 tip ----------------------------------------
    await circle_sketch("Top", MAJOR_R, "StudProfile")
    check(
        "stud extrude",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LENGTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Stud")
    check(
        "tip chamfer", await adapter.add_chamfer(TIP_CHAMFER, [[MAJOR_R, tip_y, 0.0]])
    )
    name_last_feature(adapter, "TipChamfer")
    v_stud = math.pi * MAJOR_R**2 * (LENGTH - TIP_CHAMFER) + _rev_frustum(
        TIP_CHAMFER, MAJOR_R, MAJOR_R - TIP_CHAMFER
    )
    await volume_check(adapter, "stud", v_stud, 0.005 * v_stud)

    # --- Boss-Extrude1/2/3: three non-merged core bands ----------------------
    offset_plane(adapter, "Plane2", BAND_H)
    offset_plane(adapter, "Plane1", HEAD_H - BAND_H)
    bands = (
        ("Top", "Band0", BAND_H),
        ("Plane2", "Band1", HEAD_H - 2.0 * BAND_H),
        ("Plane1", "Band2", BAND_H),
    )
    for plane, name, depth in bands:
        await circle_sketch(plane, CORE_R, f"{name}Profile")
        check(
            f"{name} boss",
            await adapter.create_extrusion(
                ExtrusionParameters(depth=depth, merge_result=False)
            ),
        )
        name_last_feature(adapter, name)
    v_core = math.pi * CORE_R**2 * HEAD_H
    await volume_check(adapter, "core bands", v_stud + v_core, 0.005 * v_core)

    # --- Chamfer3 / Chamfer4 on the outer band rims, Combine1 ----------------
    check("chamfer3", await adapter.add_chamfer(BAND_H, [[CORE_R, 0.0, 0.0]]))
    name_last_feature(adapter, "BottomBandChamfer")
    check("chamfer4", await adapter.add_chamfer(BAND_H, [[CORE_R, HEAD_H, 0.0]]))
    name_last_feature(adapter, "TopBandChamfer")
    combine_union(adapter, "Combine")
    _telemetry.info(f"pre-thread volume: {mass_properties(adapter)['volume_mm3']}")

    # --- thread: tip-seeded helix + Sketch14 cutter, Cut-Sweep1 --------------
    offset_plane(adapter, "TipPlane", tip_y)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, MAJOR_R / 1000.0
            )
            is None
        ):
            raise RuntimeError("helix seed circle failed")
    insert_helix(
        adapter,
        PITCH,
        (LENGTH + PITCH) / PITCH,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    check("create_sketch cutter", await adapter.create_sketch("Front"))
    await draw_closed_profile(
        adapter, thread_cutter_profile(), label="thread cutter", loops=1
    )
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    assert_profile_closed(adapter, "thread cutter", loops=1, feature="ThreadCutter")
    thread_sweep_cut(
        adapter, "ThreadCutter", "ThreadHelix", None, "ThreadGroove", tangency=(0, 0)
    )
    _telemetry.info(f"post-thread volume: {mass_properties(adapter)['volume_mm3']}")

    # --- knurl: Sketch26 ridge on Plane1, down to Plane2, x131 ---------------
    check("create_sketch knurl ridge", await adapter.create_sketch("Plane1"))
    await draw_closed_profile(
        adapter, knurl_ridge_profile(), label="knurl ridge", loops=1
    )
    check("exit_sketch knurl ridge", await adapter.exit_sketch())
    name_last_feature(adapter, "KnurlRidgeProfile")
    assert_profile_closed(adapter, "knurl ridge", loops=1, feature="KnurlRidgeProfile")
    check(
        "knurl ridge boss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HEAD_H - 2.0 * BAND_H, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "KnurlRidge")
    _telemetry.info(f"one-ridge volume: {mass_properties(adapter)['volume_mm3']}")

    check(
        "pattern axis",
        await adapter.create_axis(
            CreateAxisParameters(
                mode="two_planes", planes=["Front Plane", "Right Plane"]
            )
        ),
    )
    name_last_feature(adapter, "PatternAxis")
    check(
        "knurl pattern",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_name="PatternAxis",
                features=["KnurlRidge"],
                count=KNURL_COUNT,
                angle=360.0,
                equal_spacing=True,
                geometry_pattern=True,
            )
        ),
    )
    name_last_feature(adapter, "KnurlPattern")

    # --- Cut-Revolve4 head-top rim, Mirror1 across Plane3 --------------------
    check("create_sketch rim cut", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCenterLine(
                0.0, 0.0, 0.0, 0.0, 1.0 / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError("rim cut centerline failed")
    await draw_closed_profile(adapter, rim_cut_profile(), label="rim cut", loops=1)
    check("exit_sketch rim cut", await adapter.exit_sketch())
    name_last_feature(adapter, "RimCutProfile")
    assert_profile_closed(adapter, "rim cut", loops=1, feature="RimCutProfile")
    check(
        "rim revolve cut",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "TopRimCut")
    offset_plane(adapter, "Plane3", HEAD_H / 2.0)
    check(
        "rim mirror",
        await adapter.mirror_feature(
            MirrorFeatureParameters(plane="Plane3", features=["TopRimCut"])
        ),
    )
    name_last_feature(adapter, "BottomRimCut")
    _telemetry.info(f"pre-runout volume: {mass_properties(adapter)['volume_mm3']}")

    # --- Boss-Extrude7: run-out cone (dir1) + head refill (dir2) -------------
    await circle_sketch("Top", MAJOR_R, "RunoutProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "RunoutProfile").Select2(False, 0)
    feat = fm.FeatureExtrusion3(
        False,  # Sd: both directions
        False,  # Flip
        True,  # Dir: dir1 down the stud
        0,  # T1 blind
        0,  # T2 blind
        RUNOUT_DEPTH / 1000.0,
        HEAD_H / 1000.0,  # dir2 ends on the head-top face
        True,  # Dchk1: draft dir1
        False,  # Dchk2
        False,  # Ddir1: False shrinks the cone (True drafted outward, seen live)
        False,  # Ddir2
        math.radians(RUNOUT_DRAFT_DEG),
        0.0,
        False,
        False,
        False,
        False,
        True,  # Merge
        False,  # UseFeatScope
        True,  # UseAutoSelect
        0,  # T0: sketch plane
        0.0,
        False,
    )
    if feat is None:
        _seat_forensics.capture_com_failure(
            adapter,
            "runout-extrude",
            "runout extrude failed",
            api="IFeatureManager.FeatureExtrusion3",
            sketch="RunoutProfile",
        )
    name_last_feature(adapter, "ThreadRunout")
    _telemetry.info(f"final volume: {mass_properties(adapter)['volume_mm3']}")

    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("93585A190", build_93585A190))
