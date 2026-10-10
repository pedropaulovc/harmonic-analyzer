r"""Build the gooseneck post with its brazed, through-tapped end plug.

The polished Ø16 x 2-wall tube anchors the stock counter spring above the
summing lever. Its vertical leg, R51 quarter bend and horizontal arm form
one hollow tube. A physical Ø12 x 8 AISI 1018 plug is silver-brazed flush
with the arm end, then drilled and tapped #6-32 UNC-2B through. Both tap
ends have a 0.25 x 45-degree break, leaving 7.50 mm nominal full thread
(6.99 mm minimum at the printed plug-length band). The made MHA-SM-004
slotted fillister screw is a separate component, not part of this weldment.

The post slides through the east top-frame hub, whose square-head set screw
sets its installed height. The stock counter spring's geometry owns that
adjustment in ``build_sm_summing_assembly``; the shared gooseneck geometry
puts the spring eye on its counter-anchor axis.

Layout: origin at the vertical leg's reference mid-height; leg y -330..112.3,
bend centre (-51, 112.3), arm centreline y 163.3. The straight arm runs
52.359695 mm west from x -51 to -103.359695; the plug extends east from that
end face to x -95.359695. The plug's modelling envelope is Ø14, overlapping
the tube's mid-wall by 1 mm so the union adds only the Ø12 bore fill.
That overlap is not the physical plug diameter on the print.
``ThreadBore`` is the axial native Hole Wizard tap; ``SpringScrewAxis`` is
its hidden, equation-driven assembly reference.

Run on a SolidWorks worker::

    uv run python cad\scripts\build_sm_gooseneck.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, set_global
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _bore_axis import name_bore_axis
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_polygon_chain, define_rectilinear_chain
from _sketch_circle import define_circle

import _telemetry
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import wizard_holes
from _visibility import blank_reference_geometry
from sm_gooseneck_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ELEVATION_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
)

# The form nominals live in sm_gooseneck_geom -- the prose-free module the summing
# assembly imports for its hang proof -- so this build, that proof and the
# drawing's form note (sm_gooseneck_spec note 2) can never drift apart.
from sm_gooseneck_geom import (  # noqa: E402
    ARM_END_X,
    ARM_RUN,
    ARM_Y,
    BEND_R,
    PLUG_LENGTH,
    TUBE_DIA,
    WALL_T,
)
from sm_gooseneck_spring_joint import (
    EDGE_BREAK,
    PLUG_DIA,
    TAP_DRILL_DIA,
    TAP_SPEC,
)

PART_NAME = "sm-gooseneck"
MATERIAL = "Plain Carbon Steel"

LEG_TOP = round(ARM_Y - BEND_R, 3)  # 112.3: bend start = machine 1322.3
# (derived: the arm centreline is the spring hang, see sm_gooseneck_geom.ARM_Y;
# rounded so the equation-manager literal reads 112.3mm, not float noise)
LEG_BOTTOM = -330.0  # leg bottom = machine 880: the post passes through a
# clearance bore in the east rail (build_fr_top_frame gooseneck bore) and drops
# ~120 below the rail underside (999.7). Measured from the ch. 7 back-left
# three-quarter view (page001_img17): the post candy-canes, descends through
# the top frame and ends in a free rounded tip (image y 491), clear of the
# columns -- machine 880 by the frame-height vertical scale (41 mm / 26 px =
# 1.58 mm/px), cross-checked by the post's own Ø16 silhouette (10 px). Was
# -169 (machine 1041, at the rail top), then -250 (a front-view guess while
# the lower end was occluded by the coincident east column)

TUBE_R = TUBE_DIA / 2.0
TUBE_IR = TUBE_R - WALL_T  # hollow bore radius (6.0)
_RING_AREA = math.pi * (TUBE_R**2 - TUBE_IR**2)  # annular wall cross-section
PLUG_OVERLAP_DIA = TUBE_DIA - WALL_T  # Ø14 modelling union, not the physical Ø12
# The 1 mm radial overlap merges into the tube wall; added volume is bore fill.
PLUG_OVERLAP_R = PLUG_OVERLAP_DIA / 2.0
TAP_DRILL_R = TAP_DRILL_DIA / 2.0
_BREAK_OVERRUN = 0.5  # each revolved tap-end cutter closes in air


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        RevolveParameters,
        SweepParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable form and plug globals drive the sketches below; the native tap's
    # thread identity comes from TAP_SPEC. The ``mm`` suffix is load-bearing
    # -- this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 16 would be 16 inches and blow the part up
    # 25.4x). Signed coordinates keep their sign in the global; the UNSIGNED
    # distance dims they drive negate them so the equation evaluates positive
    # (a centre/anchor dim at a negative coordinate displays as the magnitude).
    # Derived spans and diameters reference other globals as equation strings.
    # LegBottom is a feature parameter (start-offset extrude), NOT a sketch dim.
    await set_global(adapter, "TubeDia", f"{TUBE_DIA}mm")
    await set_global(adapter, "WallT", f"{WALL_T}mm")
    await set_global(adapter, "LegTop", f"{LEG_TOP}mm")
    await set_global(adapter, "LegBottom", f"{LEG_BOTTOM}mm")
    await set_global(adapter, "BendR", f"{BEND_R}mm")
    await set_global(adapter, "ArmEndX", f"{ARM_END_X}mm")
    await set_global(adapter, "ArmY", '"LegTop" + "BendR"')
    await set_global(adapter, "ArmRun", '-"ArmEndX" - "BendR"')
    await set_global(adapter, "PlugLength", f"{PLUG_LENGTH}mm")
    await set_global(adapter, "PlugDia", '"TubeDia" - 2 * "WallT"')
    await set_global(adapter, "PlugOverlapDia", '"TubeDia" - "WallT"')
    await set_global(adapter, "TapDrillDia", f"{TAP_DRILL_DIA}mm")
    await set_global(adapter, "TapEdgeBreak", f"{EDGE_BREAK}mm")
    await set_global(adapter, "FullThreadLength", '"PlugLength" - 2 * "TapEdgeBreak"')

    # Per-sketch dim names + drive equations are declared inline at each define_*
    # / record call; their drive jobs collect here and apply in one deferred batch
    # after the whole model + a rebuild exist (every equation target must resolve).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Plug first: the native through-all tap must precede the tube sweep,
    # otherwise its axial ray would also perforate the far curved bend wall.
    # The Ø14 modelling envelope later overlaps the tube's mid-wall; only the
    # physical Ø12 bore fill remains additional material after that union.
    x_plug_in = ARM_END_X + PLUG_LENGTH
    plug_dims = SketchDims()
    check("create_sketch end plug", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "end plug centerline",
        await adapter.add_centerline(ARM_END_X, ARM_Y, x_plug_in, ARM_Y),
    )
    plug_profile = [
        (x_plug_in, ARM_Y),
        (x_plug_in, ARM_Y + PLUG_OVERLAP_R),
        (ARM_END_X, ARM_Y + PLUG_OVERLAP_R),
        (ARM_END_X, ARM_Y),
    ]
    profile = await add_line_chain(adapter, plug_profile)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter,
        profile,
        plug_profile,
        label="end plug",
        dims=plug_dims,
        names=["PlugOverlapRadius", "PlugLength", "PlugAnchorX", "PlugAnchorY"],
        drives=[
            '"PlugOverlapDia" / 2',
            '"PlugLength"',
            '-"ArmEndX" - "PlugLength"',
            '"ArmY"',
        ],
    )
    await ensure_fully_defined(adapter, "end plug sketch")
    check("exit_sketch end plug", await adapter.exit_sketch())
    name_last_feature(adapter, "EndPlugProfile")
    drive_jobs += plug_dims.apply(adapter, "EndPlugProfile")
    check(
        "revolve end plug", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "EndPlug")
    v_plug_envelope = math.pi * PLUG_OVERLAP_R**2 * PLUG_LENGTH
    vol = await volume_check(
        adapter, "end plug envelope", v_plug_envelope, 0.02 * v_plug_envelope
    )

    # The native through tap starts on the west-facing, flush plug mouth.
    # At this feature-history stage only the receiver exists, so through-all
    # is exactly the plug's length, not a cut into the downstream tube bend.
    tap = wizard_holes(
        adapter,
        TAP_SPEC,
        [[ARM_END_X, ARM_Y, 0.0]],
        (-1.0, 0.0, 0.0),
        f"gooseneck spring receiver ({TAP_SPEC.size} through)",
        name="ThreadBore",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), ("TapAxisY", '"ArmY"'))],
    )
    drive_jobs += tap.placement_drive_jobs
    v_tap = math.pi * TAP_DRILL_R**2 * PLUG_LENGTH
    vol = await volume_check(adapter, "plug through tap", vol - v_tap, 0.02 * v_tap)

    # Both tap ends lose 0.25 mm of full thread. These 45-degree cutters run
    # radially only inside the Ø12 bore, so their overruns remove no tube wall.
    reach = TAP_DRILL_R + EDGE_BREAK + _BREAK_OVERRUN
    mouth_apex = ARM_END_X + TAP_DRILL_R + EDGE_BREAK
    inner_apex = x_plug_in - TAP_DRILL_R - EDGE_BREAK
    breaks = SketchDims()
    check("create_sketch tap edge breaks", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "tap edge break centerline",
        await adapter.add_centerline(mouth_apex, ARM_Y, inner_apex, ARM_Y),
    )
    mouth_profile = [
        (mouth_apex, ARM_Y),
        (mouth_apex - reach, ARM_Y + reach),
        (mouth_apex - reach, ARM_Y),
    ]
    inner_profile = [
        (inner_apex, ARM_Y),
        (inner_apex + reach, ARM_Y + reach),
        (inner_apex + reach, ARM_Y),
    ]
    mouth_lines = await add_line_chain(adapter, mouth_profile)
    inner_lines = await add_line_chain(adapter, inner_profile)
    set_sketch_direct_db(adapter, False)
    break_reach_drive = f'"TapDrillDia" / 2 + "TapEdgeBreak" + {_BREAK_OVERRUN}mm'
    for prefix, lines, points, apex_drive in (
        (
            "Mouth",
            mouth_lines,
            mouth_profile,
            '-"ArmEndX" - "TapDrillDia" / 2 - "TapEdgeBreak"',
        ),
        (
            "Inner",
            inner_lines,
            inner_profile,
            '-"ArmEndX" - "PlugLength" + "TapDrillDia" / 2 + "TapEdgeBreak"',
        ),
    ):
        await define_polygon_chain(
            adapter,
            lines,
            points,
            label=f"{prefix.lower()} tap break",
            dims=breaks,
            names=[
                f"{prefix}ApexX",
                f"{prefix}AxisY",
                f"{prefix}ConeRun",
                f"{prefix}ConeRise",
                f"{prefix}Closure",
            ],
            drives=[
                apex_drive,
                '"ArmY"',
                break_reach_drive,
                break_reach_drive,
                break_reach_drive,
            ],
        )
    await ensure_fully_defined(adapter, "tap edge breaks")
    check("exit_sketch tap edge breaks", await adapter.exit_sketch())
    name_last_feature(adapter, "TapEdgeBreakProfile")
    drive_jobs += breaks.apply(adapter, "TapEdgeBreakProfile")
    check(
        "revolve tap edge breaks",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "TapEdgeBreaks")
    v_breaks = 2.0 * math.pi * EDGE_BREAK**2 * (TAP_DRILL_R + EDGE_BREAK / 3.0)
    receiver_vol = await volume_check(
        adapter, "both tap edge breaks", vol - v_breaks, 0.03 * v_breaks + 0.05
    )

    await name_bore_axis(
        adapter,
        "Front Plane",
        0.0,
        "Top Plane",
        ARM_Y,
        "spring screw",
        drive_b='"ArmY"',
        drive_jobs=drive_jobs,
    )
    name_last_feature(adapter, "SpringScrewAxis")

    # 2. Vertical leg (start-offset extrude from the Top plane: the leg is
    # asymmetric -- bottom at LEG_BOTTOM, top at +LEG_TOP into the bend).
    # TWO concentric on-axis (origin) circles -- the OD and the tube bore --
    # extrude as the annular wall. Only the diameters are dims; the centre
    # slots are ignored.
    leg = SketchDims()
    check("create_sketch leg", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        TUBE_R,
        "leg",
        dims=leg,
        names=("LegCx", "LegCz", "TubeDia"),
        drives=(None, None, '"TubeDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        TUBE_IR,
        "leg bore",
        dims=leg,
        names=("LegBoreCx", "LegBoreCz", "TubeBoreDia"),
        drives=(None, None, '"TubeDia" - 2 * "WallT"'),
    )
    await ensure_fully_defined(adapter, "leg sketch")
    check("exit_sketch leg", await adapter.exit_sketch())
    name_last_feature(adapter, "LegProfile")
    drive_jobs += leg.apply(adapter, "LegProfile")
    extrude_at_offset(adapter, LEG_TOP - LEG_BOTTOM, LEG_BOTTOM, merge_result=False)
    name_last_feature(adapter, "Leg")
    expected = receiver_vol + _RING_AREA * (LEG_TOP - LEG_BOTTOM)
    vol = await _volume(adapter)
    _telemetry.info(f"volume after leg: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"leg volume {vol:.1f} != {expected:.1f}")

    # 3. Quarter bend + horizontal arm: ONE sweep along an arc + line
    # chain (the equation-curve workaround for fix endpoint DOFs reverted
    # once sketch points became addressable). Direct DB keeps inference
    # relations off; exact-coordinate joints still merge. add_arc draws
    # CCW: bend-entry (angle 0 from the centre) to bend-exit (angle 90).
    bend_path = SketchDims()
    check("create_sketch bend path", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    arc = check(
        "bend arc",
        await adapter.add_arc(
            -BEND_R,
            LEG_TOP,  # centre
            0.0,
            LEG_TOP,  # start (bend entry, top of the leg)
            -BEND_R,
            ARM_Y,  # end (bend exit into the arm)
        ),
    )
    arm = check(
        "arm run",
        await adapter.add_line(-BEND_R, ARM_Y, ARM_END_X, ARM_Y),
    )
    set_sketch_direct_db(adapter, False)
    # Manual-dim sketch (crank-pin pattern): record each display dim into the
    # SketchDims as it is created, in creation order. The centre anchor is at
    # (-BEND_R, LEG_TOP) -- both coords non-zero, so it emits TWO unsigned
    # distance dims (horizontal then vertical), driven by the magnitudes: the
    # centre X is BEND_R east of the origin, the centre Y is LEG_TOP up. THEN the
    # arc radius, THEN the arm run -- four dims total.
    await anchor_point_to_origin(
        adapter, f"{arc}.center", -BEND_R, LEG_TOP, "bend centre"
    )
    bend_path.record("BendCentreX", '"BendR"')
    bend_path.record("BendCentreY", '"LegTop"')
    check(
        "bend radius",
        await adapter.add_sketch_dimension(arc, None, "radial", BEND_R),
    )
    bend_path.record("BendRadius", '"BendR"')
    check(
        "bend entry level with centre",
        await adapter.add_sketch_constraint(
            f"{arc}.start", f"{arc}.center", "horizontal_points"
        ),
    )
    check(
        "bend exit above centre",
        await adapter.add_sketch_constraint(
            f"{arc}.end", f"{arc}.center", "vertical_points"
        ),
    )
    check(
        "arm horizontal", await adapter.add_sketch_constraint(arm, None, "horizontal")
    )
    await dimension_between(
        adapter, f"{arm}.start", f"{arm}.end", "horizontal_distance", ARM_RUN, "arm run"
    )
    bend_path.record("ArmRun", '"ArmRun"')
    await ensure_fully_defined(adapter, "bend path")
    check("exit_sketch bend path", await adapter.exit_sketch())
    # The sweep selects this sketch by name below; rename it BEFORE the sweep so
    # the path reference resolves to the new name (a captured auto-name goes
    # stale the instant it is renamed). The path sketch is NOT absorbed (it stays
    # in the tree as the sweep path), so naming it here is permanent.
    path_name = name_last_feature(adapter, "BendPath")
    drive_jobs += bend_path.apply(adapter, "BendPath")

    profile_plane = check(
        "create_plane bend profile",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=LEG_TOP)
        ),
    )
    # Both attempts' planes survive a failed first sweep, so hide them all.
    profile_planes = [getattr(profile_plane, "name", profile_plane)]
    check(
        "create_sketch bend profile",
        await adapter.create_sketch(profile_planes[-1]),
    )
    # Annular (OD + bore) like the leg, so the swept bend + arm stay hollow
    # tube -- and driven by the SAME TubeDia/WallT knobs as the leg (each
    # sketch owns its dims; without its own drives, a WallT edit would update
    # the leg bore but leave the bend/arm inner diameter behind). The drive
    # jobs are collected but only applied for whichever profile the sweep
    # actually consumed.
    bend_prof = SketchDims()
    await define_circle(
        adapter,
        0.0,
        0.0,
        TUBE_R,
        "bend profile",
        dims=bend_prof,
        names=("BendCx", "BendCz", "BendOD"),
        drives=(None, None, '"TubeDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        TUBE_IR,
        "bend profile bore",
        dims=bend_prof,
        names=("BendBoreCx", "BendBoreCz", "BendBoreDia"),
        drives=(None, None, '"TubeDia" - 2 * "WallT"'),
    )
    await ensure_fully_defined(adapter, "bend profile sketch")
    check("exit_sketch bend profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BendProfile")
    res = await adapter.create_sweep(SweepParameters(path=path_name))
    if res.is_success:
        drive_jobs += bend_prof.apply(adapter, "BendProfile")
    if not res.is_success:
        _telemetry.debug(f"bend sweep failed ({res.error}); flipping profile plane")
        profile_plane = check(
            "create_plane bend profile (flipped)",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Top Plane", offset=-LEG_TOP
                )
            ),
        )
        profile_planes.append(getattr(profile_plane, "name", profile_plane))
        check(
            "create_sketch bend profile (flipped)",
            await adapter.create_sketch(profile_planes[-1]),
        )
        bend_prof_flipped = SketchDims()
        await define_circle(
            adapter,
            0.0,
            0.0,
            TUBE_R,
            "bend profile (flipped)",
            dims=bend_prof_flipped,
            names=("BendCx", "BendCz", "BendOD"),
            drives=(None, None, '"TubeDia"'),
        )
        await define_circle(
            adapter,
            0.0,
            0.0,
            TUBE_IR,
            "bend profile bore (flipped)",
            dims=bend_prof_flipped,
            names=("BendBoreCx", "BendBoreCz", "BendBoreDia"),
            drives=(None, None, '"TubeDia" - 2 * "WallT"'),
        )
        await ensure_fully_defined(adapter, "bend profile sketch (flipped)")
        check("exit_sketch bend profile (flipped)", await adapter.exit_sketch())
        # Distinct name: if the primary sweep failed, the original "BendProfile"
        # sketch still exists (unconsumed), so reusing the name would collide.
        # (Dim local names may repeat across sketches -- they scope to the
        # owning feature -- so only the sketch name needs to differ.)
        name_last_feature(adapter, "BendProfileFlipped")
        res = await adapter.create_sweep(SweepParameters(path=path_name))
        if res.is_success:
            drive_jobs += bend_prof_flipped.apply(adapter, "BendProfileFlipped")
    check("sweep bend + arm", res)
    name_last_feature(adapter, "BendArmSweep")
    blank_reference_geometry(adapter, tuple((name, "PLANE") for name in profile_planes))
    # Quarter torus with an annular cross-section: V = (arc/2pi) * 2pi*Rc*A
    # = (pi/2) * BendR * ring area; the straight arm is the same ring extruded.
    v_bend = math.pi / 2.0 * BEND_R * _RING_AREA
    v_arm = _RING_AREA * ARM_RUN
    # The sweep merges the plug and leg. Subtract the Ø12..Ø14 overlap band:
    # the finished plug adds bore fill only, less its native tap and breaks.
    v_overlap = math.pi * (PLUG_OVERLAP_R**2 - (PLUG_DIA / 2.0) ** 2) * PLUG_LENGTH
    expected = expected + v_bend + v_arm - v_overlap
    vol = await _volume(adapter)
    _telemetry.info(
        f"volume after bend + arm: {vol:.1f} mm^3 (analytic {expected:.1f})"
    )
    # 0.02 (was 0.01 solid): the annular wall is ~44% of the solid section, so
    # the same absolute B-rep slack is ~2.3x larger relative to the expectation.
    if abs(vol - expected) > 0.02 * expected:
        raise RuntimeError(f"bend volume {vol:.1f} != {expected:.1f}")
    final_vol = vol

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move; the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven gooseneck (equations neutral)", final_vol, 0.001 * final_vol
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Elevation View Note": ELEVATION_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
