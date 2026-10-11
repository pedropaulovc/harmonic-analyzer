r"""Reproduce the v2 cone pivot post and integrated crank pedestal.

The v2 casting supplies the retained diameters, cone-axis, foot and mounting
datums.  Its original 86 mm height came from the ch30 eight-view; this
normal-24DP crank variant grows the actual body to 90 mm and keeps the 26.6 mm
head so the raised crank boss remains inside the host outline.  The body,
head and boss proportions otherwise retain the harvested feature geometry.

The v2 coordinate frame is also authoritative: the body stands on Top at y=0,
the crank bore runs straight along +Z, and the cone journal itself is yawed
by the configured cone-line incline about the vertical body axis. That is the PART feature frame;
installation turns the casting exactly Ry(180), mapping its long +Z crank boss
to machine -Z as shown by ch30 p004.  Stable semantic references are emitted
for downstream mates: ``ConeShaftNormal``, ``journal axis``, ``swing pivot``,
``mount east`` and ``mount west``.

Run only with SolidWorks already open::

    uv run python cad\scripts\build_dt_cone_pivot_post.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
from _appearance import CASTING_GREEN, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    blank_reference_sketches,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _holes import HoleSpec, wizard_holes
from _named_views import octant_rotation
from _part_pmi import author_part_pmi
from solidworks_mcp.adapters.com_variant import double_array
from dt_cone_pivot_post_spec import (
    ATTACHMENT_CBORE_DEPTH,
    ATTACHMENT_CBORE_DIA,
    ATTACHMENT_SPACING,
    ATTACHMENT_THRU_DIA,
    ATTACHMENT_X,
    BLOCK_DIA,
    BLOCK_HEIGHT,
    BORE_DIA,
    BORE_HEIGHT,
    CONE_AXIS_VIEW,
    CONE_BOSS_DIA,
    CONE_BOSS_LENGTH,
    CRANK_ABOVE_CONE,
    CRANK_ABOVE_CONE_BAND,
    CRANK_BORE_DIA,
    CRANK_BORE_HEIGHT,
    CRANK_BOSS_DIA,
    CRANK_BOSS_END_Z,
    CRANK_BOSS_LENGTH,
    CRANK_BOSS_NEAR_Z,
    CRANK_BOSS_START_Z,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    GEOMETRIC_CONTROLS,
    HARVESTED_VOLUME_MM3,
    HEAD_BASE_Y,
    HEAD_DIA,
    HEAD_HEIGHT,
    INCLINE_DEG,
    JOURNAL_AXIS_HEIGHT_TOLERANCE_MM,
    JOURNAL_REFERENCE_LENGTH,
    JOURNAL_REFERENCE_X,
    JOURNAL_REFERENCE_Z,
    PART_DATUMS,
    RUNNING_BORE_BAND,
    SURFACE_FINISHES,
)

PART_NAME = "dt-cone-pivot-post"
# The dimension-carrying reference sketches, saved hidden (#880): they render
# in no part or assembly view, and the drawing shows each one only in the view
# that dimensions it (_drawing_hidden_sketches).
REFERENCE_SKETCHES = (
    "JournalPlanReference",
    "CrankBossStationReference",
    "BoreSpacingReference",
)
MATERIAL = "Gray Cast Iron"

ATTACHMENT_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    "1/4",
    overrides_mm={
        "HoleDiameter": ATTACHMENT_THRU_DIA,
        "CounterBoreDiameter": ATTACHMENT_CBORE_DIA,
        "CounterBoreDepth": ATTACHMENT_CBORE_DEPTH,
    },
)

# The north boss end, the face the cone shaft's thrust collar bears on (#914),
# in the PART frame: the journal axis runs through (0, BORE_HEIGHT, 0) along
# (sin I, 0, cos I), and the mid-plane pads end CONE_BOSS_LENGTH/2 either side
# of ConeShaftNormal, so the north end faces -(sin I, 0, cos I).  The whole
# face is the annulus between the pad and the journal bore.
_INCLINE_RAD = math.radians(INCLINE_DEG)
BOSS_NORTH_NORMAL = (-math.sin(_INCLINE_RAD), 0.0, -math.cos(_INCLINE_RAD))
BOSS_NORTH_CENTRE = tuple(
    base + CONE_BOSS_LENGTH / 2.0 * n
    for base, n in zip((0.0, BORE_HEIGHT, 0.0), BOSS_NORTH_NORMAL)
)
BOSS_NORTH_AREA = math.pi / 4.0 * (CONE_BOSS_DIA**2 - BORE_DIA**2)
# The found face must be this square to the axis and this close to the end
# station: float noise through the angle plane sits far below both, and the
# nearest other planar face (the crank boss's north face, normal to z) is
# 0.024 off square.  The area band is float noise on a whole annulus; any cut
# into it costs square millimetres.
_FACE_SQUARE_TOL = 1e-9
_FACE_PLANE_TOL_MM = 1e-3
_FACE_AREA_TOL_MM2 = 0.01

BLOCK_RADIUS = BLOCK_DIA / 2.0
HEAD_RADIUS = HEAD_DIA / 2.0
BORE_RADIUS = BORE_DIA / 2.0
CRANK_BORE_RADIUS = CRANK_BORE_DIA / 2.0
CRANK_BOSS_RADIUS = CRANK_BOSS_DIA / 2.0
CONE_BOSS_RADIUS = CONE_BOSS_DIA / 2.0


def _simpson(f: Any, a: float, b: float, n: int = 4000) -> float:
    h = (b - a) / n
    s = f(a) + f(b) + sum((4.0 if k % 2 else 2.0) * f(a + k * h) for k in range(1, n))
    return s * h / 3.0


def _disc_column_integral(radius: float, column: Any) -> float:
    """``∫ 2*sqrt(r²-x²) * column(x) dx`` over ``|x| <= r``.

    The volume of a cylinder feature clipped by a second surface is the disc
    integral of the clipped column length; ``x = r sin t`` removes the
    square-root end-point singularity so Simpson converges (error < 1e-4 mm³
    at n=4000, checked against a 400k-point trapezoid).
    """
    return _simpson(
        lambda t: 2.0 * radius**2 * math.cos(t) ** 2 * column(radius * math.sin(t)),
        -math.pi / 2.0,
        math.pi / 2.0,
    )


def _head_surface_z(x: float) -> float:
    """|z| of the head cylinder; the spec guards nominal boss containment."""
    return math.sqrt(HEAD_RADIUS**2 - x * x)


# Per-feature analytic volumes (mm³) the build checks natively one feature at
# a time, so a cut that ran the wrong way is caught at THAT feature instead of
# as an unexplained final gap.  Their sum is HARVESTED_VOLUME_MM3 (asserted at
# import below).
MAIN_BODY_MM3 = math.pi * BLOCK_RADIUS**2 * BLOCK_HEIGHT
HEAD_SHELL_MM3 = math.pi * (HEAD_RADIUS**2 - BLOCK_RADIUS**2) * HEAD_HEIGHT
#
# Crank boss: a Ø21.93 cylinder from the head's tangent plane
# (z = -CRANK_BOSS_NORTH_FACE) to +50.6591 minus the part of it already inside
# the head -- at each x the head spans |z| <= s(x), and the boss starts at the
# station, so the overlap column is s + min(station, s).
CRANK_BOSS_OUTSIDE_HEAD_MM3 = (
    math.pi * CRANK_BOSS_RADIUS** 2 * CRANK_BOSS_LENGTH
    - _disc_column_integral(
        CRANK_BOSS_RADIUS,
        lambda x: _head_surface_z(x) + min(-CRANK_BOSS_START_Z, _head_surface_z(x)),
    )
)
# Crank bore: the full Ø11.438 cylinder from the station through the boss
# end; nothing stands proud of the tangent plane inside the boss disc, so
# everything on that path is solid.
CRANK_BORE_MM3 = math.pi * CRANK_BORE_RADIUS**2 * CRANK_BOSS_LENGTH
# Cone pads: a Ø17.2 mid-plane cylinder of total length 42.011 whose axis is
# yawed about Y and passes through the post axis, so a point at axial t and
# radial p (in the yaw plane) sits at post radius sqrt(t² + p²) whatever the
# yaw -- the body clips each column to |t| <= sqrt(R² - p²).
CONE_PADS_OUTSIDE_BODY_MM3 = (
    math.pi * CONE_BOSS_RADIUS** 2 * CONE_BOSS_LENGTH
    - _disc_column_integral(
        CONE_BOSS_RADIUS, lambda p: 2.0 * math.sqrt(BLOCK_RADIUS**2 - p * p)
    )
)
CONE_BORE_MM3 = math.pi * BORE_RADIUS**2 * CONE_BOSS_LENGTH
# Mounting holes: two through drills plus two counterbores; they clear the
# crank bore (|x| <= 5.72 against a hole edge at 9.87) and, drilled last, are
# not re-filled by any boss.
ATTACHMENT_HOLES_MM3 = 2.0 * (
    math.pi * (ATTACHMENT_THRU_DIA / 2.0) ** 2 * (BLOCK_HEIGHT - ATTACHMENT_CBORE_DEPTH)
    + math.pi * (ATTACHMENT_CBORE_DIA / 2.0) ** 2 * ATTACHMENT_CBORE_DEPTH
)
_ANALYTIC_FINAL_MM3 = (
    MAIN_BODY_MM3
    + HEAD_SHELL_MM3
    + CRANK_BOSS_OUTSIDE_HEAD_MM3
    - CRANK_BORE_MM3
    + CONE_PADS_OUTSIDE_BODY_MM3
    - CONE_BORE_MM3
    - ATTACHMENT_HOLES_MM3
)
if abs(_ANALYTIC_FINAL_MM3 - HARVESTED_VOLUME_MM3) > 0.01:
    raise AssertionError(
        f"HARVESTED_VOLUME_MM3 {HARVESTED_VOLUME_MM3} differs from the "
        f"independent per-feature analytic sum {_ANALYTIC_FINAL_MM3:.4f}"
    )


def _transpose_rotation(rotation: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        rotation[column + 3 * row]
        for column in range(3)
        for row in range(3)
    )


def _rotations_close(
    left: tuple[float, ...],
    right: tuple[float, ...],
    tolerance: float,
) -> bool:
    return len(left) == len(right) and max(
        abs(a - b) for a, b in zip(left, right, strict=True)
    ) <= tolerance


def _name_cone_axis_view(adapter: Any) -> None:
    """Persist the true-shape journal view used by the manufacturing drawing."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    built_in = tuple(float(value) for value in model.GetStandardViewRotation(7))
    row_isometric = octant_rotation(1, 1, 1)
    if _rotations_close(built_in, row_isometric, 1e-3):
        store = lambda rotation: rotation  # noqa: E731
    elif _rotations_close(built_in, _transpose_rotation(row_isometric), 1e-3):
        store = _transpose_rotation
    else:
        raise RuntimeError(
            f"*Isometric rotation {built_in!r} establishes no known convention"
        )

    incline = math.radians(INCLINE_DEG)
    sine = math.sin(incline)
    cosine = math.cos(incline)
    # View X is the cone-axis-normal direction in the model X-Z plane, view Y
    # is model +Y, and view Z points along the journal axis at the observer.
    row_rotation = (
        cosine,
        0.0,
        -sine,
        0.0,
        1.0,
        0.0,
        sine,
        0.0,
        cosine,
    )
    rotation = store(row_rotation)
    transform = utility.CreateTransform(
        double_array([*rotation, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
    )
    if transform is None:
        raise RuntimeError("failed to create cone-axis view transform")
    view = _early_bound(model.ActiveView, "IModelView")
    view.Orientation3 = transform
    model.NameView(CONE_AXIS_VIEW)
    readback = tuple(
        float(value)
        for value in (extension.GetNamedViewRotation(CONE_AXIS_VIEW) or ())
    )
    if not _rotations_close(readback, rotation, 1e-6):
        raise RuntimeError(
            f"cone-axis named view read back {readback!r}, expected {rotation!r}"
        )
    model.ShowNamedView2("*Isometric", 7)
    _telemetry.info(
        f"cone-axis named view {CONE_AXIS_VIEW!r}: rotation={readback!r}"
    )


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Retain the harvested reference topology, but give the vertical axis the
    # semantic name the assembly consumes instead of relying on Axis<N> order.
    await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot"
    )
    name_last_feature(adapter, "swing pivot")
    check(
        "create ConeShaftNormal",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="angle",
                base_plane="Front Plane",
                # The harvested v2 plane reports ReverseDirection=true.  The
                # signed helper maps the negative angle to that alternate
                # solution while retaining the configured positive magnitude.
                angle=-INCLINE_DEG,
                pivot_axis="swing pivot",
            )
        ),
    )
    name_last_feature(adapter, "ConeShaftNormal")

    # GUI-editable dimensional contract.  Explicit mm is load-bearing because
    # the project part template uses inch document units.
    globals_mm = {
        "MainBodyDia": BLOCK_DIA,
        "MainBodyHeight": BLOCK_HEIGHT,
        "HeadDia": HEAD_DIA,
        "HeadHeight": HEAD_HEIGHT,
        "CrankBossDia": CRANK_BOSS_DIA,
        "CrankBoreDia": CRANK_BORE_DIA,
        "ConeBossDia": CONE_BOSS_DIA,
        "JournalBoreDia": BORE_DIA,
        "JournalAxisY": BORE_HEIGHT,
        "CrankAboveCone": CRANK_ABOVE_CONE,
        "MountSpacing": ATTACHMENT_SPACING,
        "MountThruDia": ATTACHMENT_THRU_DIA,
        "MountCboreDia": ATTACHMENT_CBORE_DIA,
        "MountCboreDepth": ATTACHMENT_CBORE_DEPTH,
        # The crank boss's north-face station: one global drives both the
        # interface plane the boss grows from and the plan ray the print
        # dimensions it on.
        "CrankBossNearZ": CRANK_BOSS_NEAR_Z,
    }
    for name, value in globals_mm.items():
        await set_global(adapter, name, f"{value}mm")
    await set_global(adapter, "ConeIncline", f"{INCLINE_DEG}deg")
    # The crank axis is located FROM THE CONE AXIS (U31): the 16T:64T mesh
    # closes on that spacing, so it is the independent value and the height
    # above the foot only follows it.
    await set_global(adapter, "CrankAxisY", '"JournalAxisY" + "CrankAboveCone"')

    drive_jobs: list[tuple[str, str]] = []

    # 1. Main O42.011 body, from the unchanged foot to BLOCK_HEIGHT.
    main = SketchDims()
    check("create sketch MainBodyProfile", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BLOCK_RADIUS,
        "main body",
        dims=main,
        names=("MainBodyCx", "MainBodyCz", "MainBodyDia"),
        drives=(None, None, '"MainBodyDia"'),
    )
    await ensure_fully_defined(adapter, "MainBodyProfile")
    check("exit sketch MainBodyProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "MainBodyProfile")
    drive_jobs += main.apply(adapter, "MainBodyProfile")
    check(
        "extrude MainBody",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "MainBody")
    main_depth = name_dimensions(adapter, "MainBody", ["MainBodyHt"])
    drive_jobs.append((main_depth[0], '"MainBodyHeight"'))
    body_volume = MAIN_BODY_MM3
    await volume_check(adapter, "v2 main body", body_volume, 0.001 * body_volume)

    # 2. HEAD_DIA head (dt_cone_pivot_post_spec) over HEAD_BASE_Y..BLOCK_HEIGHT.
    check(
        "create HeadBasePlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=HEAD_BASE_Y
            )
        ),
    )
    name_last_feature(adapter, "HeadBasePlane")
    drive_jobs.append(("D1@HeadBasePlane", '"MainBodyHeight" - "HeadHeight"'))
    head = SketchDims()
    check(
        "create sketch HeadProfile", await adapter.create_sketch("HeadBasePlane")
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        HEAD_RADIUS,
        "head",
        dims=head,
        names=("HeadCx", "HeadCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "HeadProfile")
    check("exit sketch HeadProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check(
        "extrude Head",
        await adapter.create_extrusion(ExtrusionParameters(depth=HEAD_HEIGHT)),
    )
    name_last_feature(adapter, "Head")
    head_depth = name_dimensions(adapter, "Head", ["HeadHt"])
    drive_jobs.append((head_depth[0], '"HeadHeight"'))
    head_volume = body_volume + HEAD_SHELL_MM3
    await volume_check(adapter, "v2 head", head_volume, 0.001 * head_volume)

    # 3. Straight crank boss along +Z from the head's tangent plane (the
    # north-face station), then the bore.  The boss sketch sits ON the
    # station plane and the blind extrude runs along the plane normal (+Z).
    check(
        "create CrankInterfacePlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Front Plane",
                offset=CRANK_BOSS_START_Z,
            )
        ),
    )
    name_last_feature(adapter, "CrankInterfacePlane")
    # The offset is authored toward -Z; SOLIDWORKS stores that as a positive
    # distance with the plane reversed, so the positive station drives it.  A
    # sign slip would move the boss 42.75 mm and fail the final volume gate.
    drive_jobs.append(("D1@CrankInterfacePlane", '"CrankBossNearZ"'))
    crank_boss = SketchDims()
    check(
        "create sketch CrankBossProfile",
        await adapter.create_sketch("CrankInterfacePlane"),
    )
    await define_circle(
        adapter,
        0.0,
        CRANK_BORE_HEIGHT,
        CRANK_BOSS_DIA / 2.0,
        "crank boss",
        dims=crank_boss,
        names=("CrankBossX", "CrankAxisY", "CrankBossDia"),
        drives=(None, '"CrankAxisY"', '"CrankBossDia"'),
    )
    await ensure_fully_defined(adapter, "CrankBossProfile")
    check("exit sketch CrankBossProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "CrankBossProfile")
    drive_jobs += crank_boss.apply(adapter, "CrankBossProfile")
    check(
        "extrude CrankSprocketBoss",
        await adapter.create_extrusion(ExtrusionParameters(depth=CRANK_BOSS_LENGTH)),
    )
    name_last_feature(adapter, "CrankSprocketBoss")
    name_dimensions(adapter, "CrankSprocketBoss", ["CrankBossLen"])
    volume = head_volume + CRANK_BOSS_OUTSIDE_HEAD_MM3
    await volume_check(adapter, "v2 crank boss", volume, 0.001 * volume)

    # The bore runs INTO the boss (+Z), i.e. against the cut default, so it is
    # reversed explicitly (build_fr_top_frame's SetScrewPocket precedent).  Do
    # not rely on SolidWorks flipping an empty cut toward material: that is
    # exactly what stopped working once the Ø44 collar (since withdrawn) gave
    # the default direction something to bite.
    crank_bore = SketchDims()
    check(
        "create sketch CrankBoreProfile",
        await adapter.create_sketch("CrankInterfacePlane"),
    )
    await define_circle(
        adapter,
        0.0,
        CRANK_BORE_HEIGHT,
        CRANK_BORE_RADIUS,
        "crank bore",
        dims=crank_bore,
        names=("CrankBoreX", "CrankBoreY", "CrankBoreDia"),
        drives=(None, '"CrankAxisY"', '"CrankBoreDia"'),
    )
    await ensure_fully_defined(adapter, "CrankBoreProfile")
    check("exit sketch CrankBoreProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "CrankBoreProfile")
    drive_jobs += crank_bore.apply(adapter, "CrankBoreProfile")
    check(
        "cut CrankBore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CRANK_BOSS_LENGTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "CrankBore")
    volume -= CRANK_BORE_MM3
    await volume_check(adapter, "v2 crank bore", volume, 0.001 * volume)

    # 4. O17.2 flush pads and O12.2808 journal on the inclined v2 axis.  Both
    # are mid-plane extrusions from the harvested ConeShaftNormal reference
    # (material on both sides of the plane, so no cut-direction question).
    # Do not substitute an on-axis revolve here: that SolidWorks topology is
    # known to make later Boolean features fail on this class of casting.
    cone_boss = SketchDims()
    check(
        "create sketch ConeBossProfile",
        await adapter.create_sketch("ConeShaftNormal"),
    )
    await define_circle(
        adapter,
        -BORE_HEIGHT,
        0.0,
        CONE_BOSS_DIA / 2.0,
        "inclined cone boss",
        dims=cone_boss,
        names=("JournalAxisY", "ConeBossY", "ConeBossDia"),
        # ConeShaftNormal's local X axis points down the model's -Y axis.
        # The horizontal distance is unsigned; the authored point retains the
        # negative side that places the bore at world Y=+JournalAxisY.
        drives=('"JournalAxisY"', None, '"ConeBossDia"'),
    )
    await ensure_fully_defined(adapter, "ConeBossProfile")
    check("exit sketch ConeBossProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "ConeBossProfile")
    drive_jobs += cone_boss.apply(adapter, "ConeBossProfile")
    check(
        "extrude ConeShaftBoss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=CONE_BOSS_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ConeShaftBoss")
    name_dimensions(adapter, "ConeShaftBoss", ["ConeBossLen"])
    volume += CONE_PADS_OUTSIDE_BODY_MM3
    await volume_check(adapter, "v2 cone pads", volume, 0.001 * volume)

    journal_bore = SketchDims()
    check(
        "create sketch JournalBoreProfile",
        await adapter.create_sketch("ConeShaftNormal"),
    )
    await define_circle(
        adapter,
        -BORE_HEIGHT,
        0.0,
        BORE_RADIUS,
        "inclined journal bore",
        dims=journal_bore,
        names=("JournalAxisY", "JournalBoreY", "JournalBoreDia"),
        drives=('"JournalAxisY"', None, '"JournalBoreDia"'),
    )
    await ensure_fully_defined(adapter, "JournalBoreProfile")
    check("exit sketch JournalBoreProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "JournalBoreProfile")
    drive_jobs += journal_bore.apply(adapter, "JournalBoreProfile")
    check(
        "cut ConeShaftBore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CONE_BOSS_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ConeShaftBore")
    volume -= CONE_BORE_MM3
    await volume_check(adapter, "v2 cone bore", volume, 0.001 * volume)

    # 5. Two vertical ANSI-inch 1/4 Fillister Head Screw counterbores in the
    # top face, ONE native Hole Wizard feature with two driven placement
    # points.  Drilled LAST, as the real casting is: the crank boss is cast
    # integral and its Ø21.93 cylinder overlaps both Ø7.14 thru holes; a boss
    # extruded after the holes would re-fill a crescent of each and no 1/4
    # screw would pass.  All transverse booleans stop below the top face (the
    # spec guards boss containment), so it remains one +Y planar face for the
    # normal-based placement-face walk.
    attachment_cut = wizard_holes(
        adapter,
        ATTACHMENT_HOLE_SPEC,
        [
            [ATTACHMENT_X, BLOCK_HEIGHT, 0.0],
            [-ATTACHMENT_X, BLOCK_HEIGHT, 0.0],
        ],
        (0.0, 1.0, 0.0),
        "mounting counterbores (1/4 fillister)",
        name="AttachmentScrewHoles",
        expect_dia_mm=ATTACHMENT_THRU_DIA,
        placement_dims=[
            (("MountWestX", '"MountSpacing" / 2'), (None, None)),
            # Horizontal-distance dimensions are unsigned; the authored point
            # retains the east/west side.
            (("MountEastX", '"MountSpacing" / 2'), (None, None)),
        ],
    )
    drive_jobs += attachment_cut.placement_drive_jobs
    volume -= ATTACHMENT_HOLES_MM3
    await volume_check(adapter, "v2 mounting holes", volume, 0.001 * volume)

    # 6. Journal-plan reference sketch.  The configured plan angle between
    # the crank axis and the cone-journal axis is the casting's defining
    # relationship, but it lives in ConeShaftNormal's plane angle and no FACE
    # projects it into a view.  Two Top-plane construction centrelines carry
    # the two axis directions and a driving angular dimension reports the
    # angle, so the plan value the shop needs is model-owned, not sheet text
    # (drawing-simplicity-policy.md rule 2); the crank boss's station has its
    # own sketch (6b).  All geometry is construction, and the part saves the
    # sketch hidden (REFERENCE_SKETCHES): the drawing's plan shows it, and
    # imports its angle, through the hidden-owner import.
    plan = SketchDims()
    check(
        "create sketch JournalPlanReference",
        await adapter.create_sketch("Top"),
    )
    set_sketch_direct_db(adapter, True)
    # Top-plane sketch X is model +X; sketch Y is model -Z, so the crank boss
    # (model -21.3753..+50.6591 along +Z) runs from sketch +Y down to -Y.
    #
    # Every line here is a RAY ROOTED AT THE ORIGIN, which is the post axis:
    # that is how the shop stations these faces, and it is also the only
    # construction an angular dimension reads unambiguously.  Two rays that
    # share a vertex enclose one wedge; two lines that merely cross enclose
    # two, and SOLIDWORKS then reports whichever it likes -- for this pair it
    # reported the 167.48 deg supplement regardless of where the text sat
    # (``AddSpecificDimension`` places text in MODEL space, so a Top-plane
    # sketch cannot steer the quadrant through it at all).
    crank_axis_line = check(
        "crank axis reference ray",
        await adapter.add_centerline(0.0, 0.0, 0.0, -CRANK_BOSS_END_Z),
    )
    journal_axis_line = check(
        "journal axis reference ray",
        await adapter.add_centerline(
            0.0, 0.0, JOURNAL_REFERENCE_X, -JOURNAL_REFERENCE_Z
        ),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "crank axis ray vertical",
        await adapter.add_sketch_constraint(crank_axis_line, None, "vertical"),
    )
    for line, label in (
        (crank_axis_line, "crank axis ray"),
        (journal_axis_line, "journal axis ray"),
    ):
        check(
            f"{label} rooted on the post axis",
            await adapter.add_sketch_constraint(
                f"{line}.start", "origin", "coincident"
            ),
        )
    check(
        "crank boss far face station",
        await adapter.add_sketch_dimension(
            f"{crank_axis_line}.end", "origin", "vertical_distance", CRANK_BOSS_END_Z
        ),
    )
    plan.record("CrankBossFarZ")
    check(
        "journal reference ray length",
        await adapter.add_sketch_dimension(
            journal_axis_line, None, "linear", JOURNAL_REFERENCE_LENGTH
        ),
    )
    plan.record("JournalRefLen")
    # The plan incline is a DRIVING sketch dimension, driven in turn by the
    # same ``ConeIncline`` global that builds ConeShaftNormal, so the value the
    # print carries and the value the geometry is built from cannot drift.
    #
    # It is authored between the journal ray and the DOWNWARD crank ray.  Two
    # lines admit four angle regions and ``AddSpecificDimension`` picks the one
    # containing its text point, so the text goes on the bisector INSIDE the
    # acute wedge, expressed as a full model-space point (Top-plane sketch y
    # is model -Z): a point with z=0 lands on the sketch x-axis, outside the
    # wedge, which is why the driven-reference route only ever read the
    # 167.48 deg supplement.  A driving dimension then fixes that quadrant at
    # authoring time, so nothing downstream can flip it.
    _add_driving_plan_incline(
        adapter,
        journal_axis_line,
        crank_axis_line,
        "journal plan incline",
        expected_degrees=INCLINE_DEG,
    )
    plan.record("InclineAngle", '"ConeIncline"')
    await ensure_fully_defined(adapter, "JournalPlanReference")
    check("exit sketch JournalPlanReference", await adapter.exit_sketch())
    name_last_feature(adapter, "JournalPlanReference")
    drive_jobs += plan.apply(adapter, "JournalPlanReference")

    # 6b. Crank-boss station reference sketch: one Top-plane ray from the post
    # axis to the crank boss's north face, carrying the station the print
    # locates that face by.  It is its own sketch because a drawing view that
    # dimensions only the station must not print the plan-angle rays beside it
    # undimensioned (MHA-DT-005 sheet 2), and hiding a sketch in a view hides the
    # dimensions imported from it (_drawing_hidden_sketches, r21).  The part
    # saves it hidden; the drawing shows it per view.
    station = SketchDims()
    check(
        "create sketch CrankBossStationReference",
        await adapter.create_sketch("Top"),
    )
    # Authored without inference, as the plan rays are, so the explicit
    # relations below are the only ones.
    set_sketch_direct_db(adapter, True)
    station_line = check(
        "crank boss north face reference ray",
        await adapter.add_centerline(0.0, 0.0, 0.0, CRANK_BOSS_NEAR_Z),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "station ray vertical",
        await adapter.add_sketch_constraint(station_line, None, "vertical"),
    )
    check(
        "station ray rooted on the post axis",
        await adapter.add_sketch_constraint(
            f"{station_line}.start", "origin", "coincident"
        ),
    )
    check(
        "crank boss near face station",
        await adapter.add_sketch_dimension(
            f"{station_line}.end",
            "origin",
            "vertical_distance",
            CRANK_BOSS_NEAR_Z,
        ),
    )
    station.record("CrankBossStartZ", '"CrankBossNearZ"')
    await ensure_fully_defined(adapter, "CrankBossStationReference")
    check("exit sketch CrankBossStationReference", await adapter.exit_sketch())
    name_last_feature(adapter, "CrankBossStationReference")
    drive_jobs += station.apply(adapter, "CrankBossStationReference")

    # 7. Bore-spacing reference sketch.  Both bore axes cross the post axis,
    # which is ConeShaftNormal's local X axis (pointing down model -Y), so one
    # construction centreline on it runs from the cone-bore centre to the
    # crank-bore centre.  Its length is the driving crank-above-cone spacing
    # the print locates the crank bore by, and the one dimension that carries
    # the mesh band; in the cone-axis view it reads as the centreline joining
    # the two bores.
    spacing = SketchDims()
    check(
        "create sketch BoreSpacingReference",
        await adapter.create_sketch("ConeShaftNormal"),
    )
    set_sketch_direct_db(adapter, True)
    spacing_line = check(
        "cone-to-crank bore spacing centreline",
        await adapter.add_centerline(-BORE_HEIGHT, 0.0, -CRANK_BORE_HEIGHT, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "bore spacing line along the post axis",
        await adapter.add_sketch_constraint(spacing_line, None, "horizontal"),
    )
    # A point pair takes HORIZPOINTS: swConstraintType_HORIZONTAL applies only
    # to lines, and on a point and the origin it was accepted without holding
    # the point (r6 farm: the sketch stayed under-defined).
    check(
        "bore spacing line rooted on the post axis",
        await adapter.add_sketch_constraint(
            f"{spacing_line}.start", "origin", "horizontal_points"
        ),
    )
    check(
        "cone bore centre height",
        await adapter.add_sketch_dimension(
            f"{spacing_line}.start", "origin", "horizontal_distance", BORE_HEIGHT
        ),
    )
    spacing.record("SpacingConeY", '"JournalAxisY"')
    check(
        "crank above cone spacing",
        await adapter.add_sketch_dimension(
            spacing_line, None, "linear", CRANK_ABOVE_CONE
        ),
    )
    spacing.record("CrankAboveCone", '"CrankAboveCone"')
    await ensure_fully_defined(adapter, "BoreSpacingReference")
    check("exit sketch BoreSpacingReference", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreSpacingReference")
    drive_jobs += spacing.apply(adapter, "BoreSpacingReference")

    # Apply all neutral equations only after every referenced dimension exists.
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "v2 harvested final",
        HARVESTED_VOLUME_MM3,
        0.001 * HARVESTED_VOLUME_MM3,
    )
    # Four accuracy features on this casting: both running bores carry the
    # band that closes the `shaft_in_bushing` fit class against their turned
    # shafts (cad/docs/tolerance-policy.md), the spacing between them the
    # 16T:64T mesh band, and the cone axis above the foot the band that keeps
    # the tip's stub inside the adjuster's cup.  Everything else -- cast body
    # and head diameters, boss diameters, boss extents, mounting-hole
    # stations -- runs at the title block's general grade.
    set_dimension_bilateral_tolerance(
        adapter, "CrankBoreProfile", "CrankBoreDia", *deviations(RUNNING_BORE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "JournalBoreProfile",
        "JournalBoreDia",
        *deviations(RUNNING_BORE_BAND),
    )
    # The mesh band on the bore-to-bore spacing (derivation in
    # dt_cone_pivot_post_spec.CRANK_ABOVE_CONE_BAND).
    set_dimension_bilateral_tolerance(
        adapter,
        "BoreSpacingReference",
        "CrankAboveCone",
        *deviations(CRANK_ABOVE_CONE_BAND),
    )
    # The cup-capture band on the cone-axis height (derivation in
    # dt_cone_pivot_post_spec.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM).
    set_dimension_symmetric_tolerance(
        adapter,
        "ConeBossProfile",
        "JournalAxisY",
        JOURNAL_AXIS_HEIGHT_TOLERANCE_MM,
    )

    # Semantic, name-selected assembly references.  The journal axis is taken
    # from its actual cylindrical wall; the three vertical axes are plane
    # intersections and therefore independent of screen projection.
    _create_feature_cylinder_axis(
        adapter,
        "ConeShaftBoss",
        CONE_BOSS_DIA / 2.0,
        "journal axis",
    )
    for label, x in (("mount west", ATTACHMENT_X), ("mount east", -ATTACHMENT_X)):
        await name_bore_axis(
            adapter, "Front Plane", 0.0, "Right Plane", x, label
        )
        name_last_feature(adapter, label)
    _create_face_plane(
        adapter,
        BOSS_NORTH_NORMAL,
        BOSS_NORTH_CENTRE,
        BOSS_NORTH_AREA,
        "BossNorth",
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    _name_cone_axis_view(adapter)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Decimal places select the title-block general band, so they are product
    # definition the PART owns; the sheet only reads them back.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(
        adapter,
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        surface_finishes=SURFACE_FINISHES,
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    _blank_reference_geometry(
        adapter,
        (
            ("ConeShaftNormal", "PLANE"),
            ("HeadBasePlane", "PLANE"),
            ("CrankInterfacePlane", "PLANE"),
            ("Plane4", "PLANE"),
            ("Plane5", "PLANE"),
            ("BossNorth", "PLANE"),
            ("swing pivot", "AXIS"),
            ("journal axis", "AXIS"),
            ("mount west", "AXIS"),
            ("mount east", "AXIS"),
        ),
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    return await save_part_and_images(adapter, PART_NAME)


@_telemetry.traced("dim.driving_plan_incline", label_param="label")
def _add_driving_plan_incline(
    adapter: Any,
    journal_line: str,
    crank_line: str,
    label: str,
    *,
    expected_degrees: float,
) -> None:
    """Author the acute plan angle between two origin-rooted rays as DRIVING.

    Both rays are selected as segments (Smart Dimension on one segment plus
    its vertex, the adapter's angular route, never yields an angular control:
    see ``diag_mcmaster_lib``).  The rays are the journal direction
    ``(sin i, -cos i)`` and the downward crank axis ``(0, -1)`` in Top-plane
    sketch axes, so the text point sits on their bisector, ``TEXT_RADIUS``
    from the origin, inside the acute wedge.  It is passed with sketch y in
    BOTH the y and the -z slots so it lands in that wedge whether SOLIDWORKS
    reads the point in sketch or in model space (the off-plane component
    projects away).  The value is verified acute BEFORE the dimension is
    made driving: a supplement here would swing the journal ray, not print
    it wrong.
    """
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    text_radius_m = 0.020
    half = math.radians(expected_degrees / 2.0)
    text_x = text_radius_m * math.sin(half)
    text_y = -text_radius_m * math.cos(half)
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [journal_line, crank_line], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_x,
        text_y,
        -text_y,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    expected_rad = math.radians(expected_degrees)
    actual_rad = abs(float(dimension.SystemValue))
    if abs(actual_rad - expected_rad) > 1e-8:
        raise RuntimeError(
            f"{label}: angular dimension measured {math.degrees(actual_rad):.6f} "
            f"deg, expected {expected_degrees:.6f} deg"
        )
    dimension.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    if int(dimension.DrivenState) != 2:
        raise RuntimeError(f"{label}: angular dimension did not become driving")
    _telemetry.success(f"driving plan incline {label}: {expected_degrees:.4f} deg")


@_telemetry.traced("reference.axis_from_feature_cylinder", label_param="label")
def _create_feature_cylinder_axis(
    adapter: Any,
    feature_name: str,
    radius_mm: float,
    label: str,
) -> None:
    """Create an axis from an exact feature-owned cylindrical face.

    Coordinate picks are view-dependent and selected ``MainBody`` in the
    generated post even when the point lay on the small inclined pad. Walking
    only ``ConeShaftBoss``'s created faces makes the ownership explicit and
    costs four surface reads instead of scanning the part's complete B-rep.
    """
    from solidworks_mcp.adapters import sw_type_info

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = sw_type_info.early_bound_doc(adapter.currentModel)
    feature = part.FeatureByName(feature_name)
    if feature is None:
        raise RuntimeError(f"axis {label}: feature {feature_name!r} not found")
    feature = _early_bound(feature, "IFeature")
    candidates: list[tuple[float, Any]] = []
    for face in feature.GetFaces() or []:
        face = _early_bound(face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if not surface.IsCylinder():
            continue
        parameters = tuple(float(value) for value in surface.CylinderParams)
        if abs(parameters[6] * 1000.0 - radius_mm) > 0.001:
            continue
        candidates.append((float(face.GetArea()), face))
    if not candidates:
        raise RuntimeError(
            f"axis {label}: {feature_name!r} has no cylinder at r={radius_mm:g} mm"
        )

    face = max(candidates, key=lambda row: row[0])[1]
    model.ClearSelection2(True)
    selectable = _early_bound(face, "IEntity")
    if not selectable.Select2(False, 0):
        raise RuntimeError(f"axis {label}: exact cylindrical face selection failed")
    if not model.InsertAxis2(True):
        raise RuntimeError(f"axis {label}: InsertAxis2 failed")
    model.ClearSelection2(True)
    name_last_feature(adapter, label)
    _telemetry.success(
        f"axis {label} from {feature_name} r={radius_mm:g} mm "
        f"({len(candidates)} candidate face(s))"
    )


def _planar_faces_on(
    faces: Any, normal: tuple[float, ...], point_mm: tuple[float, ...]
) -> list[Any]:
    """The planar faces whose outward normal is ``normal`` and whose plane
    passes through ``point_mm`` (part frame).  A non-planar face reads a zero
    ``Normal``, so it never matches."""
    matches = []
    for face in faces:
        face = _early_bound(face, "IFace2")
        face_normal = [float(v) for v in face.Normal]
        if sum(a * b for a, b in zip(face_normal, normal)) < 1.0 - _FACE_SQUARE_TOL:
            continue
        surface = _early_bound(face.GetSurface(), "ISurface")
        root = [float(v) * 1000.0 for v in surface.PlaneParams[3:6]]
        offset = sum((r - p) * n for r, p, n in zip(root, point_mm, normal))
        if abs(offset) > _FACE_PLANE_TOL_MM:
            continue
        matches.append(face)
    return matches


@_telemetry.traced("ref.face_plane", label_param="label")
def _create_face_plane(
    adapter: Any,
    normal: tuple[float, ...],
    point_mm: tuple[float, ...],
    area_mm2: float,
    label: str,
) -> None:
    """Name a reference plane coincident with the one planar face that has
    this outward normal through this point, after checking the face whole by
    its area.

    The assembly mates the plane by name.  A coordinate pick on the face is
    view-dependent: in the drive train it selected the shaft collar's OD,
    0.33 mm off the pick point, on one seat and the face on another (#916).
    """
    from solidworks_mcp.adapters import sw_type_info

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = sw_type_info.early_bound_doc(adapter.currentModel)
    faces = [
        face
        for body in part.GetBodies2(0, False) or []  # swSolidBody
        for face in _early_bound(body, "IBody2").GetFaces() or []
    ]
    matches = _planar_faces_on(faces, normal, point_mm)
    if len(matches) != 1:
        raise RuntimeError(
            f"plane {label}: {len(matches)} planar faces face {normal} through "
            f"{point_mm} mm among {len(faces)}, expected exactly one"
        )
    face = matches[0]
    area = float(face.GetArea()) * 1e6
    if abs(area - area_mm2) > _FACE_AREA_TOL_MM2:
        raise RuntimeError(
            f"plane {label}: the face reads {area:.3f} mm^2, not the whole "
            f"{area_mm2:.3f} mm^2"
        )
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select2(False, 0):
        raise RuntimeError(f"plane {label}: face selection failed")
    feature_manager = _early_bound(model.FeatureManager, "IFeatureManager")
    # swRefPlaneReferenceConstraint_Coincident = 4
    if feature_manager.InsertRefPlane(4, 0.0, 0, 0.0, 0, 0.0) is None:
        raise RuntimeError(f"plane {label}: InsertRefPlane failed")
    model.ClearSelection2(True)
    name_last_feature(adapter, label)
    _telemetry.success(
        f"plane {label} on the {area:.3f} mm^2 face through {point_mm} "
        f"facing {normal} ({len(faces)} faces walked)"
    )


@_telemetry.traced("appearance.hide_reference_geometry")
def _blank_reference_geometry(
    adapter: Any, references: tuple[tuple[str, str], ...]
) -> None:
    """Keep mating references selectable but out of the saved part render."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    for index, (name, kind) in enumerate(references):
        selected = model.Extension.SelectByID2(
            name,
            kind,
            0,
            0,
            0,
            index > 0,
            0,
            null_callout(),
            0,
        )
        if not selected:
            raise RuntimeError(f"cannot select {name!r} to hide reference geometry")
    model.BlankRefGeom()
    model.ClearSelection2(True)
    _telemetry.success(f"blanked {len(references)} reference entities")


if __name__ == "__main__":
    sys.exit(run_build(build))
