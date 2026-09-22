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

The post passes through the east rail's clearance bore and is clamped at
the height needed to balance the channel springs. The historical reference
position put its lower tip near machine Y880; the stock counter spring's
installed geometry now owns that adjustment in ``build_summing_assembly``.
The horizontal arm retains the photographed 90-degree bend and axial screw.
The 1330K524 double-loop eye needs its full axial wire band on the exposed
shank; the assembly checks both end-face/head clearance and coil clearance.

The released MHA-032 package remains one assembly BOM row, but its physical
construction is explicit: a bent Ø16 x 2 tube body, a separate AISI 1018 annular
plug match-turned to the actual tube bore for the BAg-7 capillary clearance, and
a separate #6-32 slotted adjustment screw. The plug is 6 mm deep and carries the
standard Ø2.705 tap-minor envelope. The screw is fully threaded over its 14 mm
under-head length so the 6 mm plug remains engaged throughout adjustment. The
saved Default places the head at the stock MHA-019 end-band width; loosening can
open the head gap to 8 mm for installation. These are three native bodies;
plug and screw are each one revolve of a Front-plane half profile, so their
diameters are side-view dimensions in the plane of the bend.

Layout: part origin at the vertical leg's mid-height; leg y -330..+112.3,
bend arc centre (-51, +112.3), arm centreline y +163.3 from x -51 to -101.8
(a 50.8 run: the arm end sets the spring station). The plug occupies
x -101.8..-95.8; the saved screw station is derived from the clamped MHA-019
end-band width. The tube remains hollow Ø16 x 2 wall.
Dimensions: cad/DIMENSIONS.md ch. 19 (low/med).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_gooseneck.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    _early_bound,
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    dump_dimensions,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

import _telemetry
from _visibility import blank_reference_geometry
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from gooseneck_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ELEVATION_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
)

# The form nominals live in gooseneck_geom -- the prose-free module the summing
# assembly imports for its hang proof -- so this build, that proof and the
# drawing's form note (gooseneck_spec note 2) can never drift apart.
from gooseneck_geom import (  # noqa: E402
    ARM_END_X,
    ARM_RUN,
    ARM_Y,
    BEND_R,
    PLUG_BRAZE_RADIAL_CLEARANCE,
    PLUG_DIA,
    PLUG_T,
    SCREW_HEAD_DIA,
    SCREW_HEAD_T,
    SCREW_THREAD_MAJOR_DIA,
    SCREW_SLOT_DEPTH,
    SCREW_SLOT_W,
    SCREW_TAP_MINOR_DIA,
    SPRING_SCREW_CLAMPED_GAP_MM,
    SPRING_SCREW_UNDERHEAD_LENGTH_MM,
    TUBE_DIA,
    WALL_T,
)

PART_NAME = "gooseneck"
MATERIAL = "Plain Carbon Steel"

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

TUBE_R = TUBE_DIA / 2.0
TUBE_IR = TUBE_R - WALL_T  # hollow bore radius (6.0)
_RING_AREA = math.pi * (TUBE_R**2 - TUBE_IR**2)  # annular wall cross-section
PLUG_R = PLUG_DIA / 2.0
TAP_MINOR_R = SCREW_TAP_MINOR_DIA / 2.0
SHANK_R = SCREW_THREAD_MAJOR_DIA / 2.0
HEAD_R = SCREW_HEAD_DIA / 2.0
HEAD_X = ARM_END_X - SPRING_SCREW_CLAMPED_GAP_MM
SCREW_TIP_X = HEAD_X - SCREW_HEAD_T
SHANK_END_X = HEAD_X + SPRING_SCREW_UNDERHEAD_LENGTH_MM
PLUG_END_X = ARM_END_X + PLUG_T


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")

def _solid_body_count(adapter) -> int:
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = adapter._attempt(lambda: part.GetBodies2(0, False), default=None)
    if bodies is None:
        raise RuntimeError("gooseneck solid-body census failed")
    return len(tuple(bodies))


def _assert_start_stations(adapter) -> None:
    """Read back the native (undriven) axial stations as magnitudes."""
    expected = {
        ("Leg", "LegStart"): LEG_BOTTOM,
        ("EndPlugProfile", "PlugStation"): abs(ARM_END_X),
        ("ScrewProfile", "ScrewStation"): abs(HEAD_X),
    }
    for (feature, dimension), expected_mm in expected.items():
        rows = dump_dimensions(adapter, feature)
        actual = next(
            (
                row["value_mm"]
                for row in rows
                if row["full_name"].split("@")[:2] == [dimension, feature]
            ),
            None,
        )
        if actual is None or not math.isclose(
            actual, expected_mm, rel_tol=0.0, abs_tol=1e-6
        ):
            raise RuntimeError(
                f"{dimension}@{feature}: start station {actual!r} mm; "
                f"expected {expected_mm:g} mm"
            )


IDENTITY_MM = 1e-6
IDENTITY_MM3 = 1e-6


def _slot_strip_area() -> float:
    half = SCREW_SLOT_W / 2.0
    return 2.0 * (half * math.sqrt(HEAD_R**2 - half**2) + HEAD_R**2 * math.asin(half / HEAD_R))


def _body_census(body) -> dict[str, object]:
    """Exact axial planes, X-axis cylinders and volume of one native body."""
    planes: list[tuple[float, float]] = []
    radii: list[tuple[float, float]] = []
    for raw in body.GetFaces() or ():
        face = _early_bound(raw, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface.IsPlane():
            n = tuple(float(v) for v in surface.PlaneParams)
            if abs(abs(n[0]) - 1.0) < 1e-10:
                planes.append((n[3] * 1000.0, float(face.GetArea()) * 1e6))
        elif surface.IsCylinder():
            c = tuple(float(v) for v in surface.CylinderParams)
            if abs(abs(c[3]) - 1.0) < 1e-10:
                if abs(c[1] * 1000.0 - ARM_Y) > IDENTITY_MM or abs(c[2]) * 1000.0 > IDENTITY_MM:
                    raise RuntimeError(f"arm-end cylinder off the arm axis: {c}")
                radii.append((c[6] * 1000.0, 0.0))
    volume = float(body.GetMassProperties(1.0)[3]) * 1e9
    return {"planes": sorted(planes), "radii": sorted(radii), "volume": volume}


def _grouped(values: list[tuple[float, float]]) -> list[tuple[float, int, float]]:
    """(station, face count, summed area) per distinct station/radius."""
    groups: list[list[float]] = []
    for key, area in sorted(values):
        if groups and abs(groups[-1][0] - key) <= IDENTITY_MM:
            groups[-1][1] += 1
            groups[-1][2] += area
            continue
        groups.append([key, 1, area])
    return [(key, int(count), total) for key, count, total in groups]


def _assert_arm_end_identity(adapter) -> None:
    """Fail unless plug and screw are the released geometry to 1e-6 mm / mm^3.

    The spring-seat calibration selects exactly one plug face at the arm end,
    one head-underside face at HEAD_X and one shank cylinder, each by station
    and analytic area, so those must survive the construction change as single
    faces. The anchor dimensions are unsigned; the signed face stations are
    also the side-of-origin proof.
    """
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = [_early_bound(raw, "IBody2") for raw in part.GetBodies2(0, False) or ()]
    census = [_body_census(body) for body in bodies]
    strip = _slot_strip_area()
    plug_ring = math.pi * (PLUG_R**2 - TAP_MINOR_R**2)
    expected = {
        "plug": {
            "radii": [(TAP_MINOR_R, 1), (PLUG_R, 1)],
            "planes": [(ARM_END_X, 1, plug_ring), (PLUG_END_X, 1, plug_ring)],
            "volume": plug_ring * PLUG_T,
        },
        "screw": {
            "radii": [(SHANK_R, 1), (HEAD_R, None)],
            "planes": [
                (SCREW_TIP_X, None, math.pi * HEAD_R**2 - strip),
                (SCREW_TIP_X + SCREW_SLOT_DEPTH, None, None),
                (HEAD_X, 1, math.pi * (HEAD_R**2 - SHANK_R**2)),
                (SHANK_END_X, 1, math.pi * SHANK_R**2),
            ],
            "volume": math.pi * SHANK_R**2 * SPRING_SCREW_UNDERHEAD_LENGTH_MM
            + math.pi * HEAD_R**2 * SCREW_HEAD_T
            - strip * SCREW_SLOT_DEPTH,
        },
    }
    for name, want in expected.items():
        radii_wanted = [radius for radius, _ in want["radii"]]
        matches = [
            row for row in census
            if len(_grouped(row["radii"])) == len(radii_wanted)
            and all(
                abs(got[0] - radius) <= IDENTITY_MM
                for got, radius in zip(_grouped(row["radii"]), sorted(radii_wanted))
            )
        ]
        if len(matches) != 1:
            raise RuntimeError(f"{name}: expected one body with radii {radii_wanted}; census {census}")
        row = matches[0]
        radii = _grouped(row["radii"])
        for (radius, count), got in zip(sorted(want["radii"]), radii):
            if count is not None and got[1] != count:
                raise RuntimeError(f"{name}: {got[1]} cylinder faces at r {radius:g}, expected {count}")
        planes = _grouped(row["planes"])
        wanted = sorted(want["planes"])
        if len(planes) != len(wanted):
            raise RuntimeError(f"{name}: axial faces {planes} != stations {wanted}")
        for (x, count, area), (got_x, got_count, got_area) in zip(wanted, planes):
            if abs(got_x - x) > IDENTITY_MM:
                raise RuntimeError(f"{name}: axial face at {got_x!r}, expected {x!r} mm")
            if count is not None and got_count != count:
                raise RuntimeError(f"{name}: {got_count} faces at x {x:g}, expected {count}")
            if area is not None and abs(got_area - area) > IDENTITY_MM3:
                raise RuntimeError(f"{name}: face area at x {x:g} is {got_area!r}, expected {area!r} mm^2")
        if abs(row["volume"] - want["volume"]) > IDENTITY_MM3:
            raise RuntimeError(
                f"{name}: volume {row['volume']!r} != analytic {want['volume']!r} mm^3"
            )
        _telemetry.success(
            f"{name} identity: axial faces {[(round(x, 9), n) for x, n, _ in planes]}, "
            f"radii {[(round(r, 9), n) for r, n, _ in radii]}, "
            f"volume {row['volume']:.9f} mm^3 (analytic {want['volume']:.9f})"
        )
    _telemetry.info(
        "gooseneck body volumes mm^3: "
        + ", ".join(f"{row['volume']:.9f}" for row in census)
    )


async def _constrain_rectilinear(
    adapter, lines: list[str], points: list[tuple[float, float]], label: str
) -> None:
    """Horizontal/vertical relations only; dims come from the caller.

    A revolve half profile is sized by doubled diameter dims, so the chain
    dimensions define_rectilinear_chain would add would over-define it.
    """
    count = len(lines)
    for index, line in enumerate(lines):
        (_, y1), (_, y2) = points[index], points[(index + 1) % count]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"{label} {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
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
    # Derived spans (ArmY/ArmRun) reference other globals as equation strings;
    # extrude depths are equation-driven below, while negative starts stay native.
    await set_global(adapter, "TubeDia", f"{TUBE_DIA}mm")
    await set_global(adapter, "WallT", f"{WALL_T}mm")
    await set_global(adapter, "LegTop", f"{LEG_TOP}mm")
    await set_global(adapter, "LegBottom", f"{LEG_BOTTOM}mm")
    await set_global(adapter, "BendR", f"{BEND_R}mm")
    await set_global(adapter, "ArmEndX", f"{ARM_END_X}mm")
    await set_global(adapter, "ArmY", '"LegTop" + "BendR"')
    await set_global(adapter, "ArmRun", '-"ArmEndX" - "BendR"')
    await set_global(adapter, "PlugDia", f"{PLUG_DIA}mm")
    await set_global(adapter, "PlugT", f"{PLUG_T}mm")
    await set_global(adapter, "TapMinorDia", f"{SCREW_TAP_MINOR_DIA}mm")
    await set_global(adapter, "ScrewShankDia", f"{SCREW_THREAD_MAJOR_DIA}mm")
    await set_global(
        adapter, "ScrewUnderHeadLen", f"{SPRING_SCREW_UNDERHEAD_LENGTH_MM}mm"
    )
    await set_global(adapter, "ScrewHeadDia", f"{SCREW_HEAD_DIA}mm")
    await set_global(adapter, "ScrewHeadT", f"{SCREW_HEAD_T}mm")
    await set_global(adapter, "ScrewSlotW", f"{SCREW_SLOT_W}mm")
    await set_global(adapter, "ScrewSlotDepth", f"{SCREW_SLOT_DEPTH}mm")

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
    extrude_at_offset(adapter, LEG_TOP - LEG_BOTTOM, LEG_BOTTOM)
    name_last_feature(adapter, "Leg")
    leg_dims = name_dimensions(adapter, "Leg", ["LegLength", "LegStart"])
    drive_jobs.append((leg_dims[0], '"LegTop" - "LegBottom"'))
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

    check(
        "create_plane bend profile",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=LEG_TOP)
        ),
    )
    # Construction only: named so the saved part can blank it (it printed as a
    # stray "Plane1" in the isometric render).
    profile_planes = [name_last_feature(adapter, "BendProfilePlane")]
    check(
        "create_sketch bend profile",
        await adapter.create_sketch(profile_planes[0]),
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
        check(
            "create_plane bend profile (flipped)",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Top Plane", offset=-LEG_TOP
                )
            ),
        )
        profile_planes.append(name_last_feature(adapter, "BendProfilePlaneFlipped"))
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
    # Quarter torus with an annular cross-section: V = (arc/2pi) * 2pi*Rc*A
    # = (pi/2) * BendR * ring area; the straight arm is the same ring extruded.
    v_bend = math.pi / 2.0 * BEND_R * _RING_AREA
    v_arm = _RING_AREA * ARM_RUN
    expected = expected + v_bend + v_arm
    vol = await _volume(adapter)
    _telemetry.info(
        f"volume after bend + arm: {vol:.1f} mm^3 (analytic {expected:.1f})"
    )
    # 0.02 (was 0.01 solid): the annular wall is ~44% of the solid section, so
    # the same absolute B-rep slack is ~2.3x larger relative to the expectation.
    if abs(vol - expected) > 0.02 * expected:
        raise RuntimeError(f"bend volume {vol:.1f} != {expected:.1f}")
    nominal_braze_gap = TUBE_IR - PLUG_R
    if abs(nominal_braze_gap - PLUG_BRAZE_RADIAL_CLEARANCE) > 1e-9:
        raise RuntimeError(
            "nominal plug/tube radial gap drifted from the fabrication contract"
        )
    if not 0.051 <= nominal_braze_gap <= 0.127:
        raise RuntimeError(
            f"nominal BAg-7 surface gap {nominal_braze_gap:g} mm is out of range"
        )
    if PLUG_DIA >= 2.0 * TUBE_IR:
        raise RuntimeError("end plug cannot enter the nominal tube bore")
    expected = vol  # rebase: keep the sweep's B-rep slack out of the screw delta

    # 3. The arm-end package is three physical bodies in one assembly BOM row:
    # bent tube, capillary-clearance plug, and adjustment screw. The old Ø14
    # plug was only Boolean overlap and could not enter the Ø12 tube bore. This
    # Ø11.85 annular plug leaves 0.075 mm nominal gap per facing surface and keeps
    # a modeled #6-32 tap-minor passage. The fully threaded screw retains the
    # maximum external envelope and can advance through the plug into the bore.
    if _solid_body_count(adapter) != 1:
        raise RuntimeError("formed gooseneck tube is not one solid body")

    # Plug and screw are turned parts, so each is ONE revolve of a Front-plane
    # half profile about the arm axis. Their diameters are doubled
    # centerline-to-outline dims in the plane of the bend: a longitudinal
    # section on z=0 imports them as the side-view diameters a lathe hand works
    # to (a Right-plane circle is edge-on there and cannot be imported -- farm
    # r1, 2026-09-22). The axial stations stay native magnitudes, as the old
    # negative extrude starts did; _assert_arm_end_identity reads the bodies.
    plug = SketchDims()
    check("create_sketch end plug", await adapter.create_sketch("Front"))
    # Direct DB: the axis must not infer onto the tube's projected edges.
    set_sketch_direct_db(adapter, True)
    try:
        plug_axis = check(
            "plug axis",
            await adapter.add_centerline(ARM_END_X, ARM_Y, PLUG_END_X, ARM_Y),
        )
    finally:
        set_sketch_direct_db(adapter, False)
    plug_profile = [
        (ARM_END_X, ARM_Y + TAP_MINOR_R),
        (PLUG_END_X, ARM_Y + TAP_MINOR_R),
        (PLUG_END_X, ARM_Y + PLUG_R),
        (ARM_END_X, ARM_Y + PLUG_R),
    ]
    plug_lines = await add_line_chain(adapter, plug_profile)
    await _constrain_rectilinear(adapter, plug_lines, plug_profile, "end plug")
    check(
        "plug axis horizontal",
        await adapter.add_sketch_constraint(plug_axis, None, "horizontal"),
    )
    for axis_end, profile_point in (
        (f"{plug_axis}.start", f"{plug_lines[0]}.start"),
        (f"{plug_axis}.end", f"{plug_lines[0]}.end"),
    ):
        check(
            f"plug axis {axis_end} square to the profile",
            await adapter.add_sketch_constraint(
                axis_end, profile_point, "vertical_points"
            ),
        )
    await anchor_point_to_origin(
        adapter, f"{plug_axis}.start", ARM_END_X, ARM_Y, "plug axis"
    )
    plug.record("PlugStation")
    plug.record("PlugCy", '"ArmY"')
    # Measured on the OUTER edge: the drawing's extension lines then rise
    # through the tube wall only, not through the whole plug section.
    await dimension_between(
        adapter,
        f"{plug_lines[2]}.start",
        f"{plug_lines[2]}.end",
        "horizontal_distance",
        PLUG_T,
        "plug depth",
    )
    plug.record("PlugDepth", '"PlugT"')
    # Diameter text sits across the axis from the half profile, as in
    # build_transgear_stub; the drawing repositions every imported dimension.
    await add_diametric_linear_dimension(
        adapter,
        plug_axis,
        plug_lines[0],
        (ARM_END_X + PLUG_T / 2.0, ARM_Y - TAP_MINOR_R - 4.0),
        "tap minor",
    )
    plug.record("TapMinorDia", '"TapMinorDia"')
    await add_diametric_linear_dimension(
        adapter,
        plug_axis,
        plug_lines[2],
        (ARM_END_X + PLUG_T / 2.0, ARM_Y - PLUG_R - 4.0),
        "plug",
    )
    plug.record("PlugDia", '"PlugDia"')
    await ensure_fully_defined(adapter, "end plug sketch")
    check("exit_sketch end plug", await adapter.exit_sketch())
    name_last_feature(adapter, "EndPlugProfile")
    drive_jobs += plug.apply(adapter, "EndPlugProfile")
    check(
        "revolve end plug",
        await adapter.create_revolve(
            RevolveParameters(angle=360.0, merge_result=False)
        ),
    )
    name_last_feature(adapter, "EndPlug")
    if _solid_body_count(adapter) != 2:
        raise RuntimeError("brazed end plug did not persist as a separate body")

    screw = SketchDims()
    check("create_sketch spring screw", await adapter.create_sketch("Front"))
    # Drawn first, in direct DB, so its ends merge into the on-axis profile
    # corners exactly as build_transgear_stub's axis does.
    set_sketch_direct_db(adapter, True)
    try:
        screw_axis = check(
            "screw axis",
            await adapter.add_centerline(SCREW_TIP_X, ARM_Y, SHANK_END_X, ARM_Y),
        )
    finally:
        set_sketch_direct_db(adapter, False)
    screw_profile = [
        (SCREW_TIP_X, ARM_Y),
        (SCREW_TIP_X, ARM_Y + HEAD_R),
        (HEAD_X, ARM_Y + HEAD_R),
        (HEAD_X, ARM_Y + SHANK_R),
        (SHANK_END_X, ARM_Y + SHANK_R),
        (SHANK_END_X, ARM_Y),
    ]
    screw_lines = await add_line_chain(adapter, screw_profile)
    await _constrain_rectilinear(adapter, screw_lines, screw_profile, "spring screw")
    # The station is the head UNDERSIDE, HEAD_X itself -- the clamp face the
    # spring-seat calibration measures -- exactly as the old shank extrude
    # started there; the head face follows through HeadThickness.
    await dimension_between(
        adapter,
        "origin",
        f"{screw_lines[2]}.start",
        "horizontal_distance",
        abs(HEAD_X),
        "screw head underside station",
    )
    screw.record("ScrewStation")
    await dimension_between(
        adapter,
        "origin",
        f"{screw_lines[0]}.start",
        "vertical_distance",
        ARM_Y,
        "screw axis height",
    )
    screw.record("ScrewCy", '"ArmY"')
    for line, span, name, drive in (
        (screw_lines[1], SCREW_HEAD_T, "HeadThickness", '"ScrewHeadT"'),
        (
            screw_lines[3],
            SPRING_SCREW_UNDERHEAD_LENGTH_MM,
            "UnderHeadLength",
            '"ScrewUnderHeadLen"',
        ),
    ):
        await dimension_between(
            adapter, f"{line}.start", f"{line}.end", "horizontal_distance", span, name
        )
        screw.record(name, drive)
    for line, name, drive, text_xy in (
        (
            screw_lines[1],
            "ScrewHeadDia",
            '"ScrewHeadDia"',
            (SCREW_TIP_X + SCREW_HEAD_T / 2.0, ARM_Y - HEAD_R - 4.0),
        ),
        (
            screw_lines[3],
            "ScrewShankDia",
            '"ScrewShankDia"',
            (SHANK_END_X - 2.0, ARM_Y - SHANK_R - 4.0),
        ),
    ):
        await add_diametric_linear_dimension(
            adapter, screw_axis, line, text_xy, name
        )
        screw.record(name, drive)
    await ensure_fully_defined(adapter, "spring screw sketch")
    check("exit_sketch spring screw", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewProfile")
    drive_jobs += screw.apply(adapter, "ScrewProfile")
    check(
        "revolve spring screw",
        await adapter.create_revolve(
            RevolveParameters(angle=360.0, merge_result=False)
        ),
    )
    name_last_feature(adapter, "Screw")
    if _solid_body_count(adapter) != 3:
        raise RuntimeError("spring screw did not persist as a separate body")

    slot = SketchDims()
    slot_profile = [
        (SCREW_TIP_X, ARM_Y - SCREW_SLOT_W / 2.0),
        (SCREW_TIP_X + SCREW_SLOT_DEPTH, ARM_Y - SCREW_SLOT_W / 2.0),
        (SCREW_TIP_X + SCREW_SLOT_DEPTH, ARM_Y + SCREW_SLOT_W / 2.0),
        (SCREW_TIP_X, ARM_Y + SCREW_SLOT_W / 2.0),
    ]
    check("create_sketch spring screw slot", await adapter.create_sketch("Front"))
    slot_lines = await add_line_chain(adapter, slot_profile)
    await define_rectilinear_chain(
        adapter,
        slot_lines,
        slot_profile,
        label="spring screw slot",
        dims=slot,
        names=("SlotDepth", "SlotWidth", None, None),
        drives=('"ScrewSlotDepth"', '"ScrewSlotW"', None, None),
    )
    await ensure_fully_defined(adapter, "spring screw slot sketch")
    check("exit_sketch spring screw slot", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewSlotProfile")
    drive_jobs += slot.apply(adapter, "ScrewSlotProfile")
    check(
        "cut spring screw slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * HEAD_R + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewSlot")
    if _solid_body_count(adapter) != 3:
        raise RuntimeError("spring screw slot changed the three-body fabrication")

    v_plug = math.pi * (PLUG_R**2 - TAP_MINOR_R**2) * PLUG_T
    v_shank = math.pi * SHANK_R**2 * SPRING_SCREW_UNDERHEAD_LENGTH_MM
    v_head = math.pi * HEAD_R**2 * SCREW_HEAD_T
    half_slot = SCREW_SLOT_W / 2.0
    slot_strip_area = 2.0 * (
        half_slot * math.sqrt(HEAD_R**2 - half_slot**2)
        + HEAD_R**2 * math.asin(half_slot / HEAD_R)
    )
    v_slot = slot_strip_area * SCREW_SLOT_DEPTH
    v_fabrication = v_plug + v_shank + v_head - v_slot
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    _telemetry.info(
        f"volume after plug + adjustment screw: {vol:.1f} mm^3 "
        f"(+{added:.1f}, analytic {v_fabrication:.1f})"
    )
    if abs(added - v_fabrication) > 0.02 * v_fabrication:
        raise RuntimeError(
            f"plug + adjustment screw: added {added:.1f}, expected ~{v_fabrication:.1f}"
        )
    final_vol = vol

    # Measured on SW 2026: a positive-magnitude equation reversed the old
    # negative extrude starts on rebuild, while a signed-global RHS is refused
    # when the equation is added.  The leg start and the plug/screw axial
    # stations therefore stay native construction coordinates, not printed
    # controls; their final readback below guards the released envelope.
    # Apply each deferred equation only after the whole model exists.  Rebuild
    # at each boundary so a rejected neutral constraint is attributed to its
    # exact native target instead of surfacing as an unactionable batch failure.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
        try:
            await force_rebuild(adapter)
        except RuntimeError as exc:
            raise RuntimeError(
                f"equation {dim_name!r} = {expr!r} made the model fail rebuild"
            ) from exc
    await volume_check(
        adapter, "driven gooseneck (equations neutral)", final_vol, 0.001 * final_vol
    )
    if _solid_body_count(adapter) != 3:
        raise RuntimeError("driven gooseneck did not retain tube/plug/screw bodies")

    await apply_material(adapter, MATERIAL)
    _assert_start_stations(adapter)
    _assert_arm_end_identity(adapter)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Elevation View Note": ELEVATION_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    blank_reference_geometry(
        adapter, tuple((plane, "PLANE") for plane in profile_planes)
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
