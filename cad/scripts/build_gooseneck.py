r"""Reproduction script: gooseneck post (book ch. 19, pp. 44-45).

The tall chrome tube that "towers above the machine" and anchors the top
of the counter spring: a vertical O16 tube rising from the east column
line, a 90-DEGREE bend (R 51) at the top, and a horizontal arm reaching
west over the summing-lever boss, carrying the spring's top eye on a
SLOTTED SCREW driven axially into the arm's flat end face (ch. 19 p. 45
close-up, page001_img02: tube horizontal, round slotted head at its end,
the eye encircling the shank between head and end face, the spring
hanging straight down). (M6.8 ch30 8-view pass: 90 degrees, not the
earlier 180 candy-cane -- user-confirmed against the ch. 19 photos; the
ch30 plates crop below the bend.) Tension is set by sliding the tube
through the top-frame casting's rail-hub bore, gripped by its 1/4-20
square-head set screw (build_top_frame).

Geometry: vertical leg at machine x 197 (east column line), y 880 -- the
post passes through a clearance bore in the east rail (build_top_frame
gooseneck bore) and drops ~120 below the rail underside (999.7), so the
support extends well below the top plate. The free lower tip is visible,
clear of the columns, in the ch. 7 back-left three-quarter view
(page001_img17): tip at machine 880 by the frame-height vertical scale,
cross-checked by the post's Ø16 silhouette. Up to the bend start 1322.3;
quarter bend to the horizontal arm at centreline y 1373.3, running west
to its end face at machine x 101.75. The end screw runs ON the tube axis,
so the arm height IS the spring hang: the eye centre stays at machine
(95, 1370.7) -- plumb above the summing-lever boss hook -- and the
O3.6 shank (radius 1.8) hangs the eye's inner top (radius 4.45) with a
0.05 air gap, which puts the axis at 1373.3 (the 2026-09-02 photo
re-derive: the old 1386 only ever cleared a lug under the arm). Along the
arm the eye sits 6.75 in from the end face on the 8.0 exposed shank --
1.25 from the head shoulder, the wire band (0.9 half-width) 0.35 clear of
the head and 5.85 clear of the end face -- because the coil's O12.5 body
hangs under the eye and its top (1367.1) rises above the tube underside
(1365.3): the coil clears the end face by 0.5 in x instead (the photo
shows exactly this: the eye pressed up against the head, the coil
partly under the tube end). ``build_summing_assembly`` proves both
hangs analytically.

The screw is modelled INTEGRAL to the post: this repo models small
captive fasteners as part of their carrier when they never come apart in
use, and this one is set once and carries the spring for life. Its
modelled shank is the EXPOSED length (end face to head underside); the
engaged thread sits inside a 6.0-deep end plug that caps the tube's O12
bore (the end face is otherwise a 2 mm annulus with nothing on the axis
for the shank to merge into), so plug + shank + head are ONE stepped
revolve about the tube axis. The head slot is omitted (a 0.8 x 0.8 slot
across the head face adds nothing the notes don't carry).

Layout: part origin at the vertical leg's MID-height of the OLD 180 lay
(machine (197, 1210, 0), placement preserved): leg y -330..+112.3, bend
arc centre (-51, +112.3), arm centreline y +163.3 from x -51 to -95.25,
end plug x -95.25..-89.25 (mid-wall O14, so it overlaps the wall rather
than sharing the bore face), shank x -95.25..-103.25 (O3.6), head
x -103.25..-105.25 (O10 -- wider than the eye's 8.9 inner diameter, so it
retains a slack eye; its underside at y 158.3 clears the coil's top wire
at 158.0). The tube is HOLLOW -- O16 x 2.0 wall, matching
the drawing's tube stock -- so every tube profile is an annulus.
Dimensions: cad/DIMENSIONS.md ch. 19 (low/med).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_gooseneck.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

import _telemetry
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from gooseneck_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ELEVATION_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
)

# Geometry nominals the summing assembly reads live in gooseneck_geom (the
# prose-free module assemblies import); re-imported here so the build and the
# assembly's hang proof can never drift.
from gooseneck_geom import (  # noqa: E402
    ARM_END_X,
    ARM_Y,
    PLUG_T,
    SCREW_HEAD_DIA,
    SCREW_HEAD_T,
    SCREW_SHANK_DIA,
    SCREW_SHANK_LEN,
    TUBE_DIA,
    WALL_T,
)

PART_NAME = "gooseneck"
MATERIAL = "Plain Carbon Steel"

BEND_R = 51.0  # 90-degree bend (med)
LEG_TOP = round(ARM_Y - BEND_R, 3)  # 112.3: bend start = machine 1322.3
# (derived: the arm centreline is the spring hang, see gooseneck_geom.ARM_Y;
# rounded so the equation-manager literal reads 112.3mm, not float noise)
LEG_BOTTOM = -330.0  # leg bottom = machine 880: the post passes through a
# clearance bore in the east rail (build_top_frame gooseneck bore) and drops
# ~120 below the rail underside (999.7). Measured from the ch. 7 back-left
# three-quarter view (page001_img17): the post candy-canes, descends through
# the top frame and ends in a free rounded tip (image y 491), clear of the
# columns -- machine 880 by the frame-height vertical scale (41 mm / 26 px =
# 1.58 mm/px), cross-checked by the post's own Ø16 silhouette (10 px). Was
# -169 (machine 1041, at the rail top), then -250 (a front-view guess while
# the lower end was occluded by the coincident east column)
ARM_RUN = -ARM_END_X - BEND_R  # 44.25: straight run after the bend exit

TUBE_R = TUBE_DIA / 2.0
TUBE_IR = TUBE_R - WALL_T  # hollow bore radius (6.0)
_RING_AREA = math.pi * (TUBE_R**2 - TUBE_IR**2)  # annular wall cross-section
PLUG_DIA = TUBE_DIA - WALL_T  # 14: mid-wall, so the plug OVERLAPS the wall by
# 1.0 instead of sharing the bore's cylindrical face (a curved face needs real
# overlap to merge; the volume it adds is only the bore fill)
PLUG_R = PLUG_DIA / 2.0
SHANK_R = SCREW_SHANK_DIA / 2.0
HEAD_R = SCREW_HEAD_DIA / 2.0
HEAD_X = ARM_END_X - SCREW_SHANK_LEN  # -103.25: head underside (shoulder)
SCREW_TIP_X = HEAD_X - SCREW_HEAD_T  # -105.25: head outer face


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

    # Editable knobs (Tools > Equations): every module constant above as a named
    # global that drives the sketch dims below. The ``mm`` suffix is load-bearing
    # -- this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 16 would be 16 inches and blow the part up
    # 25.4x). Signed coordinates keep their sign in the global; the UNSIGNED
    # distance dims they drive negate them so the equation evaluates positive
    # (a centre/anchor dim at a negative coordinate displays as the magnitude).
    # Derived spans (ArmY/ArmRun/PlugDia) reference other globals as equation
    # strings. LegBottom is a feature parameter (start-offset extrude), NOT a
    # sketch dim, so it is an editable knob that nothing drives.
    await set_global(adapter, "TubeDia", f"{TUBE_DIA}mm")
    await set_global(adapter, "WallT", f"{WALL_T}mm")
    await set_global(adapter, "LegTop", f"{LEG_TOP}mm")
    await set_global(adapter, "LegBottom", f"{LEG_BOTTOM}mm")
    await set_global(adapter, "BendR", f"{BEND_R}mm")
    await set_global(adapter, "ArmEndX", f"{ARM_END_X}mm")
    await set_global(adapter, "ArmY", '"LegTop" + "BendR"')
    await set_global(adapter, "ArmRun", '-"ArmEndX" - "BendR"')
    await set_global(adapter, "PlugT", f"{PLUG_T}mm")
    await set_global(adapter, "PlugDia", '"TubeDia" - "WallT"')
    await set_global(adapter, "ScrewShankDia", f"{SCREW_SHANK_DIA}mm")
    await set_global(adapter, "ScrewShankLen", f"{SCREW_SHANK_LEN}mm")
    await set_global(adapter, "ScrewHeadDia", f"{SCREW_HEAD_DIA}mm")
    await set_global(adapter, "ScrewHeadT", f"{SCREW_HEAD_T}mm")

    # Per-sketch dim names + drive equations are declared inline at each define_*
    # / record call; their drive jobs collect here and apply in one deferred batch
    # after the whole model + a rebuild exist (every equation target must resolve).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Vertical leg (start-offset extrude from the Top plane: the leg is
    # asymmetric -- bottom at LEG_BOTTOM, top at +LEG_TOP into the bend).
    # TWO concentric on-axis (origin) circles -- the OD and the tube bore --
    # extrude as the annular wall. Only the diameters are dims; the centre
    # slots are ignored.
    leg = SketchDims()
    check("create_sketch leg", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, TUBE_R, "leg", dims=leg,
        names=("LegCx", "LegCz", "TubeDia"),
        drives=(None, None, '"TubeDia"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, TUBE_IR, "leg bore", dims=leg,
        names=("LegBoreCx", "LegBoreCz", "TubeBoreDia"),
        drives=(None, None, '"TubeDia" - 2 * "WallT"'),
    )
    await ensure_fully_defined(adapter, "leg sketch")
    check("exit_sketch leg", await adapter.exit_sketch())
    name_last_feature(adapter, "LegProfile")
    drive_jobs += leg.apply(adapter, "LegProfile")
    extrude_at_offset(adapter, LEG_TOP - LEG_BOTTOM, LEG_BOTTOM)
    name_last_feature(adapter, "Leg")
    expected = _RING_AREA * (LEG_TOP - LEG_BOTTOM)
    vol = await _volume(adapter)
    _telemetry.info(f"volume after leg: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"leg volume {vol:.1f} != {expected:.1f}")

    # 2. Quarter bend + horizontal arm: ONE sweep along an arc + line
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
            -BEND_R, LEG_TOP,  # centre
            0.0, LEG_TOP,  # start (bend entry, top of the leg)
            -BEND_R, ARM_Y,  # end (bend exit into the arm)
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
    await anchor_point_to_origin(adapter, f"{arc}.center", -BEND_R, LEG_TOP, "bend centre")
    bend_path.record("BendCentreX", '"BendR"')
    bend_path.record("BendCentreY", '"LegTop"')
    check(
        "bend radius",
        await adapter.add_sketch_dimension(arc, None, "radial", BEND_R),
    )
    bend_path.record("BendRadius", '"BendR"')
    check(
        "bend entry level with centre",
        await adapter.add_sketch_constraint(f"{arc}.start", f"{arc}.center", "horizontal_points"),
    )
    check(
        "bend exit above centre",
        await adapter.add_sketch_constraint(f"{arc}.end", f"{arc}.center", "vertical_points"),
    )
    check("arm horizontal", await adapter.add_sketch_constraint(arm, None, "horizontal"))
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
    check(
        "create_sketch bend profile",
        await adapter.create_sketch(getattr(profile_plane, "name", profile_plane)),
    )
    # Annular (OD + bore) like the leg, so the swept bend + arm stay hollow
    # tube -- and driven by the SAME TubeDia/WallT knobs as the leg (each
    # sketch owns its dims; without its own drives, a WallT edit would update
    # the leg bore but leave the bend/arm inner diameter behind). The drive
    # jobs are collected but only applied for whichever profile the sweep
    # actually consumed.
    bend_prof = SketchDims()
    await define_circle(
        adapter, 0.0, 0.0, TUBE_R, "bend profile", dims=bend_prof,
        names=("BendCx", "BendCz", "BendOD"),
        drives=(None, None, '"TubeDia"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, TUBE_IR, "bend profile bore", dims=bend_prof,
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
        check(
            "create_sketch bend profile (flipped)",
            await adapter.create_sketch(getattr(profile_plane, "name", profile_plane)),
        )
        bend_prof_flipped = SketchDims()
        await define_circle(
            adapter, 0.0, 0.0, TUBE_R, "bend profile (flipped)",
            dims=bend_prof_flipped,
            names=("BendCx", "BendCz", "BendOD"),
            drives=(None, None, '"TubeDia"'),
        )
        await define_circle(
            adapter, 0.0, 0.0, TUBE_IR, "bend profile bore (flipped)",
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
    # Quarter torus with an annular cross-section: V = (arc/2pi) * 2pi*Rc*A
    # = (pi/2) * BendR * ring area; the straight arm is the same ring extruded.
    v_bend = math.pi / 2.0 * BEND_R * _RING_AREA
    v_arm = _RING_AREA * ARM_RUN
    expected = expected + v_bend + v_arm
    vol = await _volume(adapter)
    _telemetry.info(f"volume after bend + arm: {vol:.1f} mm^3 (analytic {expected:.1f})")
    # 0.02 (was 0.01 solid): the annular wall is ~44% of the solid section, so
    # the same absolute B-rep slack is ~2.3x larger relative to the expectation.
    if abs(vol - expected) > 0.02 * expected:
        raise RuntimeError(f"bend volume {vol:.1f} != {expected:.1f}")
    expected = vol  # rebase: keep the sweep's B-rep slack out of the screw delta

    # 3. End plug + spring screw: ONE stepped half-profile revolved 360 about
    # the tube axis (a centreline along X at y = ARM_Y in the Front plane -- no
    # Right-plane axis-mapping ambiguity). Read from the tube inward-out: the
    # plug (mid-wall radius, PLUG_T deep INTO the arm from the end face), the
    # exposed shank (SCREW_SHANK_LEN beyond the end face, toward more negative
    # x), then the head. The centreline shares the profile's on-axis corners
    # (exact-coordinate merge, the pin pattern proven live) and carries no dim
    # of its own. Emission order = per-segment distance dims in line order,
    # skipping the LAST segment of each direction (closure supplies it): the
    # plug radius (line0, V), plug depth (line1, H), plug-to-shank step
    # (line2, V), shank length (line3, H), shank-to-head step (line4, V), head
    # thickness (line5, H); line6 (V, head radius) and line7 (H, on the axis)
    # are the skipped closers. THEN the anchor at vertex 0 (the plug's inner
    # on-axis corner at (ARM_END_X + PLUG_T, ARM_Y)) -- both non-zero, X then
    # Y, the X driven by its magnitude (the vertex is at negative x).
    y_axis = ARM_Y
    y_plug = ARM_Y + PLUG_R
    y_shank = ARM_Y + SHANK_R
    y_head = ARM_Y + HEAD_R
    x_plug_in = ARM_END_X + PLUG_T
    screw_dims = SketchDims()
    check("create_sketch end screw", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "end screw centerline",
        await adapter.add_centerline(SCREW_TIP_X, y_axis, x_plug_in, y_axis),
    )
    screw_profile = [
        (x_plug_in, y_axis),
        (x_plug_in, y_plug),
        (ARM_END_X, y_plug),
        (ARM_END_X, y_shank),
        (HEAD_X, y_shank),
        (HEAD_X, y_head),
        (SCREW_TIP_X, y_head),
        (SCREW_TIP_X, y_axis),
    ]
    profile = await add_line_chain(adapter, screw_profile)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter, profile, screw_profile, label="end screw", dims=screw_dims,
        names=[
            "PlugRadius", "PlugDepth", "PlugShankStep", "ShankLen",
            "ShankHeadStep", "HeadThick", "ScrewAnchorX", "ScrewAnchorY",
        ],
        drives=[
            '"PlugDia" / 2',
            '"PlugT"',
            '"PlugDia" / 2 - "ScrewShankDia" / 2',
            '"ScrewShankLen"',
            '"ScrewHeadDia" / 2 - "ScrewShankDia" / 2',
            '"ScrewHeadT"',
            '-"ArmEndX" - "PlugT"',
            '"ArmY"',
        ],
    )
    await ensure_fully_defined(adapter, "end screw sketch")
    check("exit_sketch end screw", await adapter.exit_sketch())
    name_last_feature(adapter, "EndScrewProfile")
    drive_jobs += screw_dims.apply(adapter, "EndScrewProfile")
    check("revolve end screw", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "EndScrew")
    # Added material: the plug fills only the BORE (its mid-wall overlap band
    # r 6..7 is already tube wall), then the solid shank and head outside the
    # end face. The plug/end-face boundary is coplanar with the tube's annular
    # end face over r 6..7 -- a planar coincidence the union merges cleanly.
    v_plug = math.pi * TUBE_IR**2 * PLUG_T
    v_shank = math.pi * SHANK_R**2 * SCREW_SHANK_LEN
    v_head = math.pi * HEAD_R**2 * SCREW_HEAD_T
    v_screw = v_plug + v_shank + v_head
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    _telemetry.info(
        f"volume after end screw: {vol:.1f} mm^3 (+{added:.1f}, analytic {v_screw:.1f}:"
        f" plug {v_plug:.1f} + shank {v_shank:.1f} + head {v_head:.1f})"
    )
    if abs(added - v_screw) > 0.02 * v_screw:
        raise RuntimeError(f"end screw: added {added:.1f}, expected ~{v_screw:.1f}")
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
