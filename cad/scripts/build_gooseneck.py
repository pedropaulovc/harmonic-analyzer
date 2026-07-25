r"""Reproduction script: gooseneck post (book ch. 19, pp. 44-45).

The tall chrome tube that "towers above the machine" and anchors the top
of the counter spring: a vertical O16 tube rising from the east column
line, a 90-DEGREE bend (R 51) at the top, and a horizontal arm reaching
west over the summing-lever boss, carrying the spring pin under its end.
(M6.8 ch30 8-view pass: 90 degrees, not the earlier 180 candy-cane --
user-confirmed against the ch. 19 photos; the ch30 plates crop below the
bend.) Tension is set by sliding the tube in its socket -- cast into the top
frame itself and pinched by the square-head set screw (build_gooseneck_screw);
there is no separate clamp block on the machine.

Geometry: vertical leg at machine x 203.8 (east column line), y 903.35 -- the
post passes through a clearance bore in the east rail (build_top_frame
gooseneck socket) and drops ~130 below the rail underside (1033.6), so the
support extends well below the top plate. The free lower tip is visible,
clear of the columns, in the ch. 7 back-left three-quarter view
(page001_img17): tip read at the frame-height vertical scale, then carried
with the post by the counter-spring hang (below). Up to the bend start
1358.35; quarter bend to the horizontal arm at centreline
y 1409.35, running west to its end face at machine x 85; the spring lug
hangs under the arm end so the pin stays at machine (95, 1396.35) --
directly above the summing-lever boss hook, counter spring hanging
plumb, loop top 1400.25 clearing the arm underside 1401.35. The book's tip
"slotted screw" is modeled as a lug + O4 X-pin for the spring's top
loop to encircle (simplification).

Layout: part origin at the vertical leg's MID-height of the OLD 180 lay
(machine (203.8, 1233.35, 0), placement preserved): leg y -330..+125, bend
arc centre (-51, +125), arm centreline y +176 from x -51 to -118.8, lug
x -115.8..-110.3 rising y 159..169.5 into the arm's 2 mm wall (underside
min 168), pin along X at (y 163, z 0). The tube is HOLLOW -- O16 x 2.0
wall, matching the drawing's tube stock -- so every profile is an
annulus. Dimensions: cad/DIMENSIONS.md ch. 19 (low/med).

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

PART_NAME = "gooseneck"
MATERIAL = "Plain Carbon Steel"

TUBE_DIA = 16.0  # DIMENSIONS.md ch19: scaled vs frame anchors (med)
WALL_T = 2.0  # tube wall: the drawing ships O16 x 2.0 WALL tube stock, so the
# native CAD is the same hollow tube, not solid bar (codex review #361)
LEG_TOP = 125.0  # bend start = machine 1358.35 (derived: arm y - bend R)
LEG_BOTTOM = -330.0  # leg bottom = machine 903.35: the post passes through a
# clearance bore in the east rail (build_top_frame gooseneck socket) and drops
# ~130 below the rail underside (1033.6). Measured from the ch. 7 back-left
# three-quarter view (page001_img17): the post candy-canes, descends through
# the top frame and ends in a free rounded tip (image y 491), clear of the
# columns -- read at the frame-height vertical scale (41 mm / 26 px =
# 1.58 mm/px), cross-checked by the post's own Ø16 silhouette (10 px); the
# 2026-07-24 re-anchor then carried the whole post +23.35 with the
# counter-spring chain it hangs (NOT +33.9 with the frame -- the post slides
# in its socket, so the spring hang sets its height). Was
# -169 (at the rail top), then -250 (a front-view guess while
# the lower end was occluded by the coincident east column)
BEND_R = 51.0  # 90-degree bend (med)
ARM_Y = LEG_TOP + BEND_R  # 176: arm centreline = machine 1409.35; underside
# 168 = machine 1401.35, 1.1 above the spring loop top 1400.25
ARM_END_X = -118.8  # arm end face = machine 85: covers the lug with margin.
# The 2026-07-24 re-anchor moved the socket 6.8 further out (column |x| 197 ->
# 203.8) while the lug/pin/spring targets on the summing lever stayed put, so
# every local X station below reaches 6.8 further
ARM_RUN = -ARM_END_X - BEND_R  # 61: straight run after the bend exit
LUG_X = (-115.8, -110.3)  # lug plate, machine x 88..93.5 (derived: clear
# of the spring loop's wire band x 94.1..95.9)
LUG_Y = (159.0, 169.5)  # rises 1.5 past the arm underside (168) so the prism
# merges into the round tube (a curved face needs real overlap) while staying
# inside the 2 mm wall band (outer 168.0..168.14 over the lug's z, inner
# 170.0..170.19) -- a taller lug would poke through into the hollow bore
LUG_HALF_Z = 1.5
PIN_DIA = 4.0  # spring-loop pin (low)
PIN_Y = 163.0  # machine 1396.35: loop centre 1393.95 + (loop mean r 5.35
# - wire r 0.9 - pin r 2.0) hanging contact (derived)
PIN_X = (-115.8, -104.8)  # cantilevers past the loop band to machine x 99

TUBE_R = TUBE_DIA / 2.0
TUBE_IR = TUBE_R - WALL_T  # hollow bore radius (6.0)
_RING_AREA = math.pi * (TUBE_R**2 - TUBE_IR**2)  # annular wall cross-section


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
    # Derived spans (ArmY/ArmRun) reference other globals as equation strings.
    # LegBottom and the LugY/extrude depths are feature parameters (start-offset
    # extrudes), NOT sketch dims, so they are editable knobs that nothing drives.
    await set_global(adapter, "TubeDia", f"{TUBE_DIA}mm")
    await set_global(adapter, "WallT", f"{WALL_T}mm")
    await set_global(adapter, "LegTop", f"{LEG_TOP}mm")
    await set_global(adapter, "LegBottom", f"{LEG_BOTTOM}mm")
    await set_global(adapter, "BendR", f"{BEND_R}mm")
    await set_global(adapter, "ArmEndX", f"{ARM_END_X}mm")
    await set_global(adapter, "ArmY", '"LegTop" + "BendR"')
    await set_global(adapter, "ArmRun", '-"ArmEndX" - "BendR"')
    await set_global(adapter, "LugX0", f"{LUG_X[0]}mm")
    await set_global(adapter, "LugX1", f"{LUG_X[1]}mm")
    await set_global(adapter, "LugY0", f"{LUG_Y[0]}mm")
    await set_global(adapter, "LugY1", f"{LUG_Y[1]}mm")
    await set_global(adapter, "LugHalfZ", f"{LUG_HALF_Z}mm")
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinY", f"{PIN_Y}mm")
    await set_global(adapter, "PinX0", f"{PIN_X[0]}mm")
    await set_global(adapter, "PinX1", f"{PIN_X[1]}mm")

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
    expected = vol  # rebase: keep the sweep's B-rep slack out of the lug delta

    # 3. Pin lug rising into the arm underside. NOT origin-centred (offset in X),
    # so it stays a rectilinear chain. Emission order = per-segment distance dims
    # in line order skipping the last of each direction (closure supplies it):
    # the width (line0, |X1-X0|=5.5) then the depth (line1, 2*half-Z=3.0), THEN
    # the anchor dims at vertex 0 (LUG_X[0], -LUG_HALF_Z) -- both non-zero, so X
    # then Z, driven by their magnitudes (vertex is at negative X and -Z).
    lug_dims = SketchDims()
    check("create_sketch lug", await adapter.create_sketch("Top"))
    lug_rect = [
        (LUG_X[0], -LUG_HALF_Z),
        (LUG_X[1], -LUG_HALF_Z),
        (LUG_X[1], LUG_HALF_Z),
        (LUG_X[0], LUG_HALF_Z),
    ]
    lug = await add_line_chain(adapter, lug_rect)
    await define_rectilinear_chain(
        adapter, lug, lug_rect, label="lug", dims=lug_dims,
        names=["LugWidth", "LugDepth", "LugAnchorX", "LugAnchorZ"],
        drives=['"LugX1" - "LugX0"', '2 * "LugHalfZ"', '-"LugX0"', '"LugHalfZ"'],
    )
    await ensure_fully_defined(adapter, "lug sketch")
    check("exit_sketch lug", await adapter.exit_sketch())
    name_last_feature(adapter, "LugProfile")
    drive_jobs += lug_dims.apply(adapter, "LugProfile")
    extrude_at_offset(adapter, LUG_Y[1] - LUG_Y[0], LUG_Y[0])
    name_last_feature(adapter, "Lug")
    # Added material = the prism OUTSIDE the tube: height to the tube
    # underside (~168 + z^2/16 over z +-1.5) ~ 9.05 mean, vs the 9-high
    # solid reference -> ratio 1.005, inside the (0.95, 1.01) window. The
    # prism's top (169.5) is buried in the 2 mm wall band, so nothing lands
    # inside the hollow bore and the overlap adds no volume.
    v_lug = (LUG_X[1] - LUG_X[0]) * 2.0 * LUG_HALF_Z * 9.0
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    _telemetry.info(f"volume after lug: {vol:.1f} mm^3 (+{added:.1f}, solid {v_lug:.1f})")
    if not (0.95 * v_lug <= added <= 1.01 * v_lug):
        raise RuntimeError(f"lug: added {added:.1f}, expected ~{v_lug:.1f}")
    expected = vol

    # 4. Spring pin along X (revolved in the Front plane -- no Right-plane
    # axis-mapping ambiguity). The centerline shares the profile's bottom corners
    # (exact-coordinate merge), carries no dim of its own, so the four profile
    # dims are the whole record. Emission order = width (line0, |X1-X0|=11), then
    # depth (line1, PIN_DIA/2=2), THEN anchor at vertex 0 (PIN_X[0], PIN_Y): X is
    # at negative X (driven by its magnitude) and Y is positive.
    pin_dims = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "pin centerline",
        await adapter.add_centerline(PIN_X[0], PIN_Y, PIN_X[1], PIN_Y),
    )
    pin_rect = [
        (PIN_X[0], PIN_Y),
        (PIN_X[1], PIN_Y),
        (PIN_X[1], PIN_Y + PIN_DIA / 2.0),
        (PIN_X[0], PIN_Y + PIN_DIA / 2.0),
    ]
    profile = await add_line_chain(adapter, pin_rect)
    set_sketch_direct_db(adapter, False)
    # The centerline shares the profile's bottom corners (exact-coordinate
    # merge, proven live), so the dimensioned profile defines it too.
    await define_rectilinear_chain(
        adapter, profile, pin_rect, label="pin", dims=pin_dims,
        names=["PinLen", "PinRadius", "PinAnchorX", "PinAnchorY"],
        drives=['"PinX1" - "PinX0"', '"PinDia" / 2', '-"PinX0"', '"PinY"'],
    )
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += pin_dims.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    pin_len = PIN_X[1] - PIN_X[0]
    v_pin = math.pi * (PIN_DIA / 2.0) ** 2 * pin_len
    # The pin passes through the lug: subtract the lens-clipped overlap.
    r, h = PIN_DIA / 2.0, LUG_HALF_Z
    a_clip = 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))
    v_overlap = a_clip * (LUG_X[1] - LUG_X[0])
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    v_net = v_pin - v_overlap
    _telemetry.info(f"volume after pin: {vol:.1f} mm^3 (+{added:.1f}, net {v_net:.1f})")
    if not (0.9 * v_net <= added <= 1.1 * v_net):
        raise RuntimeError(f"pin: added {added:.1f}, expected ~{v_net:.1f}")
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
