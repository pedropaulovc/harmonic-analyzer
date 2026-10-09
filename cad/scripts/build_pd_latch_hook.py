r"""Reproduction script: latch hook (MHA-PD-014; book ch. 23 pp. 58-63; video 4/4).

The "small latch that allows the operator to disengage the gearing from the
platen" (ch23 text; p.58 "latch" callout): ONE formed 0.8 (0.032 in) 1095
spring-steel part.  A base lies on the MHA-PD-007 support bar's back face
under two #4-40 screws (MHA-VN-043); a 90 deg ear rises at its +X end; an arm
hangs from the ear's lower edge, rolled R80 flatwise until it lies square to
the MHA-VN-042 latch pin, with the pin hole and a finger tab below it.
Geometry and frame: ``pd_latch_hook_geometry``; printed bands, walls, notes
and the marked dimensions: ``pd_latch_hook_spec``.

Layout (part frame = machine axes, origin at the ear's outer face x = 0, the
base's underside z = 0 and the base's low-Y edge y = 0; the assembly places
the part by translation to ``PART_ORIGIN_MACHINE``):

* ``BaseEarProfile``: the L section on the Top Plane (sketch y = model -Z),
  extruded +Y by the width (``BaseEar``); ``InsideBend`` / ``OutsideBend``
  the concentric bend radii;
* ``ArmProfile``: the arm's Front-plane outline -- the ear-high top, the
  vertical, the R80 roll, the straight (split at the far face where the pin
  crosses it), the R10 tab and its radial end -- extruded over the arm's z
  band from a start offset (``Arm``);
* ``TaperProfile`` / ``Taper``: the front edge's 10 -> 11.5 taper, cut
  through on the Right Plane (sketch x = model -Z);
* ``RootRelief``: the inside corner where the arm's front edge meets the
  ear's lower edge;
* ``RoundProfile`` / ``Round``: the full round at the tip, seen along X;
* ``ScrewHoleProfile`` / ``ScrewHoles``: the two screw holes, drilled after
  bending, located from the ear's outer face;
* ``PinHolePlane`` / ``PinHoleProfile`` / ``PinHole``: the pin hole, a
  revolve cut about its axis along U at the pin's height;
* ``FlatBlank``: the flat pattern, a hidden construction-only reference
  sketch on the Right Plane beside the part (the drawing's phantom).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_latch_hook.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    bbox_extent_check,
    blank_reference_sketches,
    check,
    define_circle,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
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
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _visibility import blank_reference_geometry
from pd_latch_hook_geometry import (
    ARM_N,
    ARM_U,
    ARM_Z0,
    ARM_Z1,
    BASE_LENGTH,
    BBOX_X,
    BBOX_Y,
    BBOX_Z,
    DEV_TAPER,
    DEV_TIP,
    EAR_HEIGHT,
    FAR_FACE_STATION,
    FLAT_LENGTH,
    INNER_ROLL_END,
    INNER_ROLL_R,
    INNER_ROLL_START,
    INNER_TAB_END,
    INNER_TAB_START,
    INNER_TOP,
    INSIDE_BEND_R,
    LIP_W,
    LOW_W,
    OUTER_ROLL_END,
    OUTER_ROLL_START,
    OUTER_TAB_END,
    OUTER_TAB_R,
    OUTER_TAB_START,
    OUTER_TOP,
    OUTSIDE_BEND_R,
    PIN_HOLE_DIA,
    PIN_HOLE_L,
    PIN_HOLE_ZL,
    ROLL_C_L,
    ROOT_R,
    ROUND_C_L,
    ROUND_R,
    SCREW_HOLE_DIA,
    SCREW_HOLE_X,
    SCREW_HOLE_Y,
    SHEET_T,
    TAB_C_L,
    TAPER_L,
    V_ARM_ON_EAR,
    V_ARM_PRISM,
    V_L,
    V_PIN_HOLE,
    V_ROOT_FILL,
    V_ROUND_CUT,
    V_SCREW_HOLES,
    V_TAPER_CUT,
    VOLUME,
    WIDTH,
    Z_FRONT,
    on_arm,
    to_local,
    z_local,
)
from pd_latch_hook_spec import (
    BASE_LENGTH_TOL,
    BEND_R_BAND,
    BOTTOM_VIEW_NOTE,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FACE_BAND,
    FACE_DIMENSIONS,
    FLAT_SKETCH,
    FORMED_BAND,
    FORMED_DIMENSIONS,
    HOLE_BAND,
    ISOMETRIC_VIEW_NOTE,
    POSITION_DIMENSIONS,
    POSITION_TOL,
    REFERENCE_SKETCHES,
    WIDTH_TOL,
)

PART_NAME = "pd-latch-hook"
MATERIAL = "Plain Carbon Steel"  # 1095 spring steel (the registry row names it)
DRAWING_PROPERTIES = {
    "Manufacturing Notes": DRAWING_NOTES,
    "Isometric View Note": ISOMETRIC_VIEW_NOTE,
    "Bottom View Note": BOTTOM_VIEW_NOTE,
}

# The L section in Top-Plane sketch coordinates (x, -z), from the base's -X
# underside corner round to the base's top: segment 0 prints the base length,
# 1 the ear height, 2 the ear's thickness, 3 the ear's inside height; the
# last horizontal and vertical close the chain.  Vertex 1 is the origin.
_L_POINTS = [
    (-BASE_LENGTH, 0.0),
    (0.0, 0.0),
    (0.0, -EAR_HEIGHT),
    (-SHEET_T, -EAR_HEIGHT),
    (-SHEET_T, -SHEET_T),
    (-BASE_LENGTH, -SHEET_T),
]
V_SHARP_L = (BASE_LENGTH + EAR_HEIGHT - SHEET_T) * SHEET_T * WIDTH

# The arm's far (+U) face where the pin crosses it: the outer straight is
# split there so the sheet locates the latching face from the origin.
FAR_FACE_POINT = to_local(*on_arm(FAR_FACE_STATION))
ARM_FRONT_Z = z_local(Z_FRONT)  # the front edge above the taper: 6.0

# Right-Plane sketches: sketch (x, y) = (-Z, Y).
_TAPER_POINTS = [
    (-ARM_FRONT_Z, 0.0),  # A: the front edge at the ear's lower edge
    (-ARM_FRONT_Z, TAPER_L[0]),  # B: the taper's start
    (-ARM_Z0, TAPER_L[1]),  # C: the taper's end, on the low front edge
    (-ARM_Z0 + 1.0, TAPER_L[1]),  # D: 1.0 behind the arm's front face
    (-ARM_Z0 + 1.0, 0.0),  # E
]
_ROUND_C = (-ROUND_C_L[1], ROUND_C_L[0])
_ROUND_OVERRUN = 1.0  # the cut's margin past the band edges and the tab end
_ROUND_BOTTOM = min(OUTER_TAB_END[1], INNER_TAB_END[1]) - _ROUND_OVERRUN

# The pin hole's revolve profile, on the plane at the pin's height (sketch
# (x, y) = (X, Y)): the axis along U through the hole centre, the profile a
# rectangle from the axis to the hole radius along +N, 2 each way along U --
# well past the 0.8 strip it crosses square.
_PIN_HALF_RUN = 2.0
_PIN_AXIS = (
    (
        PIN_HOLE_L[0] - _PIN_HALF_RUN * ARM_U[0],
        PIN_HOLE_L[1] - _PIN_HALF_RUN * ARM_U[1],
    ),
    (
        PIN_HOLE_L[0] + _PIN_HALF_RUN * ARM_U[0],
        PIN_HOLE_L[1] + _PIN_HALF_RUN * ARM_U[1],
    ),
)
_PIN_R = PIN_HOLE_DIA / 2.0
_PIN_PROFILE = [
    _PIN_AXIS[0],
    _PIN_AXIS[1],
    (_PIN_AXIS[1][0] + _PIN_R * ARM_N[0], _PIN_AXIS[1][1] + _PIN_R * ARM_N[1]),
    (_PIN_AXIS[0][0] + _PIN_R * ARM_N[0], _PIN_AXIS[0][1] + _PIN_R * ARM_N[1]),
]

# The flat pattern, Right-Plane sketch (x, y): x across the blank from the
# ear's top edge (FLAT_GAP right of the part) to the base's -X end, y along
# the arm from the ear's lower edge (y = 0, the blank's low-Y edge).
FLAT_GAP = 20.0
_FLAT_FRONT = FLAT_GAP + EAR_HEIGHT - ARM_FRONT_Z  # the arm's front edge
_FLAT_LOW = FLAT_GAP + LOW_W  # the front edge below the taper
_FLAT_ROUND_C = (FLAT_GAP + ROUND_R, -(DEV_TIP - ROUND_R))
_FLAT = {
    "top_rear": (FLAT_GAP, WIDTH),
    "top_end": (FLAT_GAP + FLAT_LENGTH, WIDTH),
    "low_end": (FLAT_GAP + FLAT_LENGTH, 0.0),
    "root_start": (_FLAT_FRONT + ROOT_R, 0.0),
    "root_c": (_FLAT_FRONT + ROOT_R, -ROOT_R),
    "root_end": (_FLAT_FRONT, -ROOT_R),
    "taper_start": (_FLAT_FRONT, -DEV_TAPER[0]),
    "taper_end": (_FLAT_LOW, -DEV_TAPER[1]),
    "round_front": (_FLAT_LOW, _FLAT_ROUND_C[1]),
    "round_rear": (FLAT_GAP, _FLAT_ROUND_C[1]),
}
if abs(_FLAT_LOW - _FLAT_FRONT - LIP_W) > 1e-9:
    raise AssertionError("the flat's taper does not step the front edge by LIP_W")


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch segment as construction geometry."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _relate(adapter, rows) -> None:
    """Apply ``(label, first, second, relation)`` sketch relations."""
    for label, first, second, relation in rows:
        check(label, await adapter.add_sketch_constraint(first, second, relation))


async def _arm_profile(adapter) -> SketchDims:
    """The arm's Front-plane outline in the open sketch, fully defined.

    Direct to the DB at the geometry's exact points, then constrained (48
    DOF): 11 joins (22); the top horizontal, both verticals (3); six
    tangencies (6); the outer straight's two halves collinear (1); both arc
    pairs concentric (4); the inner straight parallel to the outer (1); the
    end radial through the tab's centre (1); and ten dimensions -- the
    thickness, the top's height, the roll start, the inside roll radius, the
    far face's X and Y, the straight's length, the inside tab radius and the
    tab end's X.  ``add_arc`` runs counter-clockwise from start to end.
    """
    dims = SketchDims()
    set_sketch_direct_db(adapter, True)
    top = check("arm top", await adapter.add_line(*INNER_TOP, *OUTER_TOP))
    outer_v = check(
        "arm outer vertical", await adapter.add_line(*OUTER_TOP, *OUTER_ROLL_START)
    )
    outer_roll = check(
        "outer roll",
        await adapter.add_arc(*ROLL_C_L, *OUTER_ROLL_END, *OUTER_ROLL_START),
    )
    outer_upper = check(
        "outer straight above the pin",
        await adapter.add_line(*OUTER_ROLL_END, *FAR_FACE_POINT),
    )
    outer_lower = check(
        "outer straight below the pin",
        await adapter.add_line(*FAR_FACE_POINT, *OUTER_TAB_START),
    )
    outer_tab = check(
        "inside tab", await adapter.add_arc(*TAB_C_L, *OUTER_TAB_START, *OUTER_TAB_END)
    )
    end = check("tab end", await adapter.add_line(*OUTER_TAB_END, *INNER_TAB_END))
    inner_tab = check(
        "outside tab", await adapter.add_arc(*TAB_C_L, *INNER_TAB_START, *INNER_TAB_END)
    )
    inner_straight = check(
        "inner straight", await adapter.add_line(*INNER_TAB_START, *INNER_ROLL_END)
    )
    inner_roll = check(
        "inner roll",
        await adapter.add_arc(*ROLL_C_L, *INNER_ROLL_END, *INNER_ROLL_START),
    )
    inner_v = check(
        "arm inner vertical", await adapter.add_line(*INNER_ROLL_START, *INNER_TOP)
    )
    set_sketch_direct_db(adapter, False)
    await _relate(
        adapter,
        (
            ("top-outer join", f"{top}.end", f"{outer_v}.start", "coincident"),
            ("vertical-roll join", f"{outer_v}.end", f"{outer_roll}.end", "coincident"),
            (
                "roll-straight join",
                f"{outer_roll}.start",
                f"{outer_upper}.start",
                "coincident",
            ),
            (
                "far-face split",
                f"{outer_upper}.end",
                f"{outer_lower}.start",
                "coincident",
            ),
            (
                "straight-tab join",
                f"{outer_lower}.end",
                f"{outer_tab}.start",
                "coincident",
            ),
            ("tab-end join", f"{outer_tab}.end", f"{end}.start", "coincident"),
            ("end-outside tab join", f"{end}.end", f"{inner_tab}.end", "coincident"),
            (
                "outside tab-straight join",
                f"{inner_tab}.start",
                f"{inner_straight}.start",
                "coincident",
            ),
            (
                "straight-inner roll join",
                f"{inner_straight}.end",
                f"{inner_roll}.start",
                "coincident",
            ),
            (
                "inner roll-vertical join",
                f"{inner_roll}.end",
                f"{inner_v}.start",
                "coincident",
            ),
            ("vertical-top join", f"{inner_v}.end", f"{top}.start", "coincident"),
            ("arm top horizontal", top, None, "horizontal"),
            ("outer vertical", outer_v, None, "vertical"),
            ("inner vertical", inner_v, None, "vertical"),
            ("outer roll tangent to the vertical", outer_roll, outer_v, "tangent"),
            ("outer roll tangent to the straight", outer_roll, outer_upper, "tangent"),
            ("inside tab tangent to the straight", outer_tab, outer_lower, "tangent"),
            ("inner roll tangent to the vertical", inner_roll, inner_v, "tangent"),
            (
                "inner roll tangent to the straight",
                inner_roll,
                inner_straight,
                "tangent",
            ),
            (
                "outside tab tangent to the straight",
                inner_tab,
                inner_straight,
                "tangent",
            ),
            ("outer straight one line", outer_upper, outer_lower, "collinear"),
            (
                "roll arcs concentric",
                f"{outer_roll}.center",
                f"{inner_roll}.center",
                "coincident",
            ),
            (
                "tab arcs concentric",
                f"{outer_tab}.center",
                f"{inner_tab}.center",
                "coincident",
            ),
            ("straights parallel", inner_straight, outer_upper, "parallel"),
            ("tab end radial", f"{outer_tab}.center", end, "coincident"),
        ),
    )
    check(
        "arm thickness",
        await adapter.add_sketch_dimension(top, None, "linear", SHEET_T),
    )
    dims.record("ArmT", '"SheetT"')
    await anchor_point_to_origin(
        adapter, f"{outer_v}.start", *OUTER_TOP, "arm top at the ear's top"
    )
    dims.record("ArmTop", '"Width"')
    await dimension_between(
        adapter,
        "origin",
        f"{outer_v}.end",
        "vertical_distance",
        -OUTER_ROLL_START[1],
        "roll start below the ear",
    )
    dims.record("RollStart")
    check(
        "inside roll radius",
        await adapter.add_sketch_dimension(inner_roll, None, "radial", INNER_ROLL_R),
    )
    dims.record("RollR")
    await dimension_between(
        adapter,
        "origin",
        f"{outer_upper}.end",
        "horizontal_distance",
        -FAR_FACE_POINT[0],
        "far face at the pin, X",
    )
    dims.record("FaceX")
    await dimension_between(
        adapter,
        "origin",
        f"{outer_upper}.end",
        "vertical_distance",
        -FAR_FACE_POINT[1],
        "far face at the pin, Y",
    )
    dims.record("FaceY")
    await dimension_between(
        adapter,
        f"{outer_upper}.start",
        f"{outer_lower}.end",
        "distance",
        math.dist(OUTER_ROLL_END, OUTER_TAB_START),
        "straight from roll to tab",
    )
    dims.record("StraightLen")
    check(
        "inside tab radius",
        await adapter.add_sketch_dimension(outer_tab, None, "radial", OUTER_TAB_R),
    )
    dims.record("TabR")
    await dimension_between(
        adapter,
        "origin",
        f"{outer_tab}.end",
        "horizontal_distance",
        -OUTER_TAB_END[0],
        "tab end X",
    )
    dims.record("TabEndX")
    return dims


async def _flat_blank(adapter) -> SketchDims:
    """The flat pattern in the open Right-plane sketch, construction only.

    38 DOF: 9 joins (18); six horizontals/verticals (6); four tangencies (4);
    the blank's top corner anchored (2); its length and width, the root
    relief radius, the arm's two widths, the taper's two developed stations
    and the full round's centre (8).
    """
    dims = SketchDims()
    p = _FLAT
    set_sketch_direct_db(adapter, True)
    top = check("flat top edge", await adapter.add_line(*p["top_rear"], *p["top_end"]))
    base_end = check(
        "flat base end", await adapter.add_line(*p["top_end"], *p["low_end"])
    )
    low = check(
        "flat low edge", await adapter.add_line(*p["low_end"], *p["root_start"])
    )
    root = check(
        "flat root relief",
        await adapter.add_arc(*p["root_c"], *p["root_start"], *p["root_end"]),
    )
    front = check(
        "flat front edge", await adapter.add_line(*p["root_end"], *p["taper_start"])
    )
    taper = check(
        "flat taper", await adapter.add_line(*p["taper_start"], *p["taper_end"])
    )
    low_front = check(
        "flat low front edge",
        await adapter.add_line(*p["taper_end"], *p["round_front"]),
    )
    tip = check(
        "flat full round",
        await adapter.add_arc(*_FLAT_ROUND_C, *p["round_rear"], *p["round_front"]),
    )
    rear = check(
        "flat rear edge", await adapter.add_line(*p["round_rear"], *p["top_rear"])
    )
    set_sketch_direct_db(adapter, False)
    for entity in (top, base_end, low, root, front, taper, low_front, tip, rear):
        _as_construction(adapter, entity)
    await _relate(
        adapter,
        (
            ("flat top-end join", f"{top}.end", f"{base_end}.start", "coincident"),
            ("flat end-low join", f"{base_end}.end", f"{low}.start", "coincident"),
            ("flat low-root join", f"{low}.end", f"{root}.start", "coincident"),
            ("flat root-front join", f"{root}.end", f"{front}.start", "coincident"),
            ("flat front-taper join", f"{front}.end", f"{taper}.start", "coincident"),
            ("flat taper-low join", f"{taper}.end", f"{low_front}.start", "coincident"),
            ("flat low-round join", f"{low_front}.end", f"{tip}.end", "coincident"),
            ("flat round-rear join", f"{tip}.start", f"{rear}.start", "coincident"),
            ("flat rear-top join", f"{rear}.end", f"{top}.start", "coincident"),
            ("flat top horizontal", top, None, "horizontal"),
            ("flat base end vertical", base_end, None, "vertical"),
            ("flat low edge horizontal", low, None, "horizontal"),
            ("flat front edge vertical", front, None, "vertical"),
            ("flat low front edge vertical", low_front, None, "vertical"),
            ("flat rear edge vertical", rear, None, "vertical"),
            ("flat root tangent to the low edge", root, low, "tangent"),
            ("flat root tangent to the front edge", root, front, "tangent"),
            ("flat round tangent to the front edge", tip, low_front, "tangent"),
            ("flat round tangent to the rear edge", tip, rear, "tangent"),
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{top}.start", *p["top_rear"], "flat blank beside the part"
    )
    dims.record(None)
    dims.record(None)
    check(
        "flat length",
        await adapter.add_sketch_dimension(top, None, "linear", FLAT_LENGTH),
    )
    dims.record("FlatLength")
    check(
        "flat width",
        await adapter.add_sketch_dimension(base_end, None, "linear", WIDTH),
    )
    dims.record("FlatWidth", '"Width"')
    check(
        "flat root relief radius",
        await adapter.add_sketch_dimension(root, None, "radial", ROOT_R),
    )
    dims.record("FlatRootR", '"RootR"')
    await dimension_between(
        adapter,
        f"{top}.start",
        f"{front}.start",
        "horizontal_distance",
        _FLAT_FRONT - FLAT_GAP,
        "flat arm width",
    )
    dims.record("FlatArmW", '"EarHeight" - "ArmFrontZ"')
    await dimension_between(
        adapter,
        f"{top}.start",
        f"{low_front}.start",
        "horizontal_distance",
        LOW_W,
        "flat low width",
    )
    dims.record("FlatLowW", '"EarHeight" - "ArmLowZ"')
    for name, ref, value in (
        ("DevTaper1", f"{front}.end", DEV_TAPER[0]),
        ("DevTaper2", f"{taper}.end", DEV_TAPER[1]),
        ("DevRoundC", f"{tip}.center", -_FLAT_ROUND_C[1]),
    ):
        await dimension_between(
            adapter, f"{base_end}.end", ref, "vertical_distance", value, name
        )
        dims.record(name)
    return dims


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("SheetT", SHEET_T),
        ("Width", WIDTH),
        ("BaseLength", BASE_LENGTH),
        ("EarHeight", EAR_HEIGHT),
        ("InsideBendR", INSIDE_BEND_R),
        ("ArmLowZ", ARM_Z0),
        ("ArmFrontZ", ARM_FRONT_Z),
        ("RootR", ROOT_R),
        ("ScrewHoleX1", -SCREW_HOLE_X[0]),
        ("ScrewHoleX2", -SCREW_HOLE_X[1]),
        ("ScrewHoleY", SCREW_HOLE_Y),
        ("ScrewHoleDia", SCREW_HOLE_DIA),
        ("PinHoleDia", PIN_HOLE_DIA),
        ("PinHoleZ", PIN_HOLE_ZL),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Base and ear: one Top-plane section extruded +Y by the width.
    profile = SketchDims()
    check("create_sketch base and ear", await adapter.create_sketch("Top"))
    lines = await add_line_chain(adapter, _L_POINTS)
    await define_rectilinear_chain(
        adapter,
        lines,
        _L_POINTS,
        anchor=1,
        label="base and ear L",
        dims=profile,
        names=["BaseLength", "EarHeight", "EarT", "EarInside"],
        drives=[
            '"BaseLength"',
            '"EarHeight"',
            '"SheetT"',
            '"EarHeight" - "SheetT"',
        ],
    )
    await ensure_fully_defined(adapter, "base and ear profile")
    check("exit_sketch base and ear", await adapter.exit_sketch())
    name_last_feature(adapter, "BaseEarProfile")
    drive_jobs += profile.apply(adapter, "BaseEarProfile")
    check(
        "extrude base and ear",
        await adapter.create_extrusion(ExtrusionParameters(depth=WIDTH)),
    )
    name_last_feature(adapter, "BaseEar")
    width_dim = name_dimensions(adapter, "BaseEar", ["Width"])
    drive_jobs.append((width_dim[0], '"Width"'))
    await volume_check(adapter, "sharp L", V_SHARP_L, 0.005 * V_SHARP_L)

    # The bend: inside R1.2 in the re-entrant corner, outside R2.0 on the
    # outer corner, about one centre.
    check(
        "fillet inside bend",
        await adapter.add_fillet(INSIDE_BEND_R, [[-SHEET_T, WIDTH / 2.0, SHEET_T]]),
    )
    name_last_feature(adapter, "InsideBend")
    inside = name_dimensions(adapter, "InsideBend", ["InsideBendR"])
    drive_jobs.append((inside[0], '"InsideBendR"'))
    check(
        "fillet outside bend",
        await adapter.add_fillet(OUTSIDE_BEND_R, [[0.0, WIDTH / 2.0, 0.0]]),
    )
    name_last_feature(adapter, "OutsideBend")
    outside = name_dimensions(adapter, "OutsideBend", ["OutsideBendR"])
    drive_jobs.append((outside[0], '"InsideBendR" + "SheetT"'))
    expected = V_L
    await volume_check(adapter, "bent L", expected, 0.005 * V_L)

    # --- The arm: its Front-plane outline over the z band, from a start
    # offset.  Its top (y 0..8) lies inside the ear, already solid.
    check("create_sketch arm", await adapter.create_sketch("Front"))
    arm = await _arm_profile(adapter)
    await ensure_fully_defined(adapter, "arm profile")
    check("exit_sketch arm", await adapter.exit_sketch())
    name_last_feature(adapter, "ArmProfile")
    drive_jobs += arm.apply(adapter, "ArmProfile")
    extrude_at_offset(adapter, ARM_Z1 - ARM_Z0, ARM_Z0)
    name_last_feature(adapter, "Arm")
    # Offset bosses expose depth first and start offset second.
    band_dim, low_dim = name_dimensions(adapter, "Arm", ["ArmBand", "ArmLowZ"])
    drive_jobs += [
        (band_dim, '"EarHeight" - "ArmLowZ"'),
        (low_dim, '"ArmLowZ"'),
    ]
    expected += V_ARM_PRISM - V_ARM_ON_EAR
    await volume_check(adapter, "arm", expected, 0.005 * expected)

    # --- The taper: the front edge 1.5 forward of the guide-lock screw heads
    # down to TAPER_L[0], then out to the low band at TAPER_L[1].  Cut
    # through along X; the region stops at the ear's lower edge (y = 0).
    taper = SketchDims()
    check("create_sketch taper", await adapter.create_sketch("Right"))
    taper_lines = await add_line_chain(adapter, _TAPER_POINTS)
    a, _slope, c, d, e = taper_lines
    await _relate(
        adapter,
        (
            ("taper front edge vertical", a, None, "vertical"),
            ("taper end horizontal", c, None, "horizontal"),
            ("taper back vertical", d, None, "vertical"),
            ("taper top horizontal", e, None, "horizontal"),
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{a}.start", *_TAPER_POINTS[0], "front edge at the ear"
    )
    taper.record("ArmFrontZ", '"ArmFrontZ"')
    await dimension_between(
        adapter,
        f"{a}.start",
        f"{a}.end",
        "vertical_distance",
        -TAPER_L[0],
        "taper start below the ear",
    )
    taper.record("TaperY1")
    await dimension_between(
        adapter,
        "origin",
        f"{c}.start",
        "horizontal_distance",
        ARM_Z0,
        "taper end on the low front edge",
    )
    taper.record("TaperLowZ", '"ArmLowZ"')
    await dimension_between(
        adapter,
        f"{a}.start",
        f"{c}.start",
        "vertical_distance",
        -TAPER_L[1],
        "taper end below the ear",
    )
    taper.record("TaperY2")
    check(
        "taper cut margin",
        await adapter.add_sketch_dimension(
            c, None, "linear", _TAPER_POINTS[3][0] - _TAPER_POINTS[2][0]
        ),
    )
    taper.record("TaperMargin")
    await ensure_fully_defined(adapter, "taper profile")
    check("exit_sketch taper", await adapter.exit_sketch())
    name_last_feature(adapter, "TaperProfile")
    drive_jobs += taper.apply(adapter, "TaperProfile")
    check(
        "cut taper",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=4.0 * (BBOX_X[1] - BBOX_X[0]), both_directions=True
            )
        ),
    )
    name_last_feature(adapter, "Taper")
    expected -= V_TAPER_CUT
    await volume_check(adapter, "taper", expected, 0.03 * V_TAPER_CUT)

    # --- The root relief: the inside corner where the front edge meets the
    # ear's lower edge, across the strip.
    check(
        "fillet root relief",
        await adapter.add_fillet(ROOT_R, [[-SHEET_T / 2.0, 0.0, ARM_FRONT_Z]]),
    )
    name_last_feature(adapter, "RootRelief")
    root = name_dimensions(adapter, "RootRelief", ["RootR"])
    drive_jobs.append((root[0], '"RootR"'))
    expected += V_ROOT_FILL
    await volume_check(adapter, "root relief", expected, 0.1 * V_ROOT_FILL + 0.05)

    # --- The full round at the tip, seen along X: everything below the
    # round's centre outside its lower half-circle, cut through along X.
    rnd = SketchDims()
    check("create_sketch round", await adapter.create_sketch("Right"))
    rear_x = _ROUND_C[0] - ROUND_R
    front_x = _ROUND_C[0] + ROUND_R
    set_sketch_direct_db(adapter, True)
    arc = check(
        "full round",
        await adapter.add_arc(*_ROUND_C, rear_x, _ROUND_C[1], front_x, _ROUND_C[1]),
    )
    set_sketch_direct_db(adapter, False)
    round_lines = await add_line_chain(
        adapter,
        [
            (rear_x, _ROUND_C[1]),
            (rear_x - _ROUND_OVERRUN, _ROUND_C[1]),
            (rear_x - _ROUND_OVERRUN, _ROUND_BOTTOM),
            (front_x + _ROUND_OVERRUN, _ROUND_BOTTOM),
            (front_x + _ROUND_OVERRUN, _ROUND_C[1]),
            (front_x, _ROUND_C[1]),
        ],
        close=False,
    )
    rear_lip, rear_side, bottom, front_side, front_lip = round_lines
    await _relate(
        adapter,
        (
            ("round-rear lip join", f"{arc}.start", f"{rear_lip}.start", "coincident"),
            ("round-front lip join", f"{arc}.end", f"{front_lip}.end", "coincident"),
            ("rear lip horizontal", rear_lip, None, "horizontal"),
            ("rear side vertical", rear_side, None, "vertical"),
            ("round cut bottom horizontal", bottom, None, "horizontal"),
            ("front side vertical", front_side, None, "vertical"),
            ("front lip horizontal", front_lip, None, "horizontal"),
            (
                "round's centre level with its rear end",
                f"{arc}.center",
                f"{arc}.start",
                "horizontal_points",
            ),
            (
                "round's centre level with its front end",
                f"{arc}.center",
                f"{arc}.end",
                "horizontal_points",
            ),
        ),
    )
    check(
        "full round radius",
        await adapter.add_sketch_dimension(arc, None, "radial", ROUND_R),
    )
    rnd.record("RoundR", '("EarHeight" - "ArmLowZ") / 2')
    await anchor_point_to_origin(
        adapter, f"{arc}.center", *_ROUND_C, "full round centre"
    )
    rnd.record("RoundZ", '("EarHeight" + "ArmLowZ") / 2')
    rnd.record("RoundY")
    for name, line, value in (
        ("RoundRearLip", rear_lip, _ROUND_OVERRUN),
        ("RoundFrontLip", front_lip, _ROUND_OVERRUN),
        ("RoundDepth", rear_side, _ROUND_C[1] - _ROUND_BOTTOM),
    ):
        check(name, await adapter.add_sketch_dimension(line, None, "linear", value))
        rnd.record(name)
    await ensure_fully_defined(adapter, "round profile")
    check("exit_sketch round", await adapter.exit_sketch())
    name_last_feature(adapter, "RoundProfile")
    drive_jobs += rnd.apply(adapter, "RoundProfile")
    check(
        "cut full round",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=4.0 * (BBOX_X[1] - BBOX_X[0]), both_directions=True
            )
        ),
    )
    name_last_feature(adapter, "Round")
    expected -= V_ROUND_CUT
    await volume_check(adapter, "full round", expected, 0.05 * V_ROUND_CUT + 0.1)

    # --- Screw holes, drilled through the base after bending: a Front-plane
    # sketch cut +Z through the sheet.  Both holes' X run from the ear's
    # outer face (the origin); the second hole's Y and size ride the same
    # globals and print once under "2X".
    screws = SketchDims()
    check("create_sketch screw holes", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        SCREW_HOLE_X[0],
        SCREW_HOLE_Y,
        SCREW_HOLE_DIA / 2.0,
        "far screw hole",
        dims=screws,
        names=("ScrewX1", "ScrewY", "ScrewDia"),
        drives=('"ScrewHoleX1"', '"ScrewHoleY"', '"ScrewHoleDia"'),
    )
    await define_circle(
        adapter,
        SCREW_HOLE_X[1],
        SCREW_HOLE_Y,
        SCREW_HOLE_DIA / 2.0,
        "near screw hole",
        dims=screws,
        names=("ScrewX2", "ScrewY2", "ScrewDia2"),
        drives=('"ScrewHoleX2"', '"ScrewHoleY"', '"ScrewHoleDia"'),
    )
    await ensure_fully_defined(adapter, "screw hole sketch")
    check("exit_sketch screw holes", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewHoleProfile")
    drive_jobs += screws.apply(adapter, "ScrewHoleProfile")
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SHEET_T, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    expected -= V_SCREW_HOLES
    await volume_check(adapter, "screw holes", expected, 0.02 * V_SCREW_HOLES)

    # --- The pin hole: a revolve cut about its axis along U, sketched on the
    # plane at the pin's height.  Match-drilled from the pin at assembly; the
    # model holds the geometry's nominal and the sheet prints its size only.
    check(
        "create_plane PinHolePlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=PIN_HOLE_ZL
            )
        ),
    )
    name_last_feature(adapter, "PinHolePlane")
    plane_dim = name_dimensions(adapter, "PinHolePlane", ["PinHoleZ"])
    drive_jobs.append((plane_dim[0], '"PinHoleZ"'))
    blank_reference_geometry(adapter, (("PinHolePlane", "PLANE"),))
    pin = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch("PinHolePlane"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "pin hole axis", await adapter.add_centerline(*_PIN_AXIS[0], *_PIN_AXIS[1])
    )
    set_sketch_direct_db(adapter, False)
    pin_lines = await add_line_chain(adapter, _PIN_PROFILE)
    on_axis, near_end, rim, far_end = pin_lines
    await _relate(
        adapter,
        (
            (
                "profile on the axis, start",
                f"{axis}.start",
                f"{on_axis}.start",
                "coincident",
            ),
            ("profile on the axis, end", f"{axis}.end", f"{on_axis}.end", "coincident"),
            ("profile end square to the axis", near_end, on_axis, "perpendicular"),
            ("profile start square to the axis", far_end, on_axis, "perpendicular"),
            ("hole rim parallel to the axis", rim, on_axis, "parallel"),
        ),
    )
    for index, point in enumerate(_PIN_AXIS):
        end_ref = f"{axis}.start" if index == 0 else f"{axis}.end"
        await anchor_point_to_origin(adapter, end_ref, *point, f"pin axis end {index}")
        pin.record(None)
        pin.record(None)
    text = (
        _PIN_PROFILE[2][0] + 2.0 * _PIN_R * ARM_N[0],
        _PIN_PROFILE[2][1] + 2.0 * _PIN_R * ARM_N[1],
    )
    await add_diametric_linear_dimension(adapter, axis, rim, text, "PinHoleDia")
    pin.record("PinHoleDia", '"PinHoleDia"')
    await ensure_fully_defined(adapter, "pin hole profile")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin.apply(adapter, "PinHoleProfile")
    check(
        "revolve-cut pin hole",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "PinHole")
    expected -= V_PIN_HOLE
    await volume_check(adapter, "pin hole", expected, 0.02 * V_PIN_HOLE)
    if abs(expected - VOLUME) > 1e-6:
        raise AssertionError(f"feature gates sum to {expected}, geometry says {VOLUME}")

    # --- The flat pattern: hidden reference sketch, printed by the drawing.
    check("create_sketch flat blank", await adapter.create_sketch("Right"))
    flat = await _flat_blank(adapter)
    await ensure_fully_defined(adapter, "flat blank")
    check("exit_sketch flat blank", await adapter.exit_sketch())
    name_last_feature(adapter, FLAT_SKETCH)
    drive_jobs += flat.apply(adapter, FLAT_SKETCH)

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven hook (equations neutral)", VOLUME, 0.005 * VOLUME
    )
    await bbox_extent_check(adapter, "hook X", "x", BBOX_X[1] - BBOX_X[0], 0.1)
    await bbox_extent_check(adapter, "hook Y", "y", BBOX_Y[1] - BBOX_Y[0])
    await bbox_extent_check(adapter, "hook Z", "z", BBOX_Z[1] - BBOX_Z[0])

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    # Drilled after bending (screw holes) or on the pin (pin hole), never
    # under size.
    set_dimension_bilateral_tolerance(
        adapter, "ScrewHoleProfile", "ScrewDia", *deviations(HOLE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinHoleProfile", "PinHoleDia", *deviations(HOLE_BAND)
    )
    # The inside bend: R1.5 the largest the screw head clears.
    set_dimension_bilateral_tolerance(
        adapter, "InsideBend", "InsideBendR", *deviations(BEND_R_BAND)
    )
    # Screw-hole positions from the formed ear and the low-Y edge.
    for feature_name, dimension_names in POSITION_DIMENSIONS.items():
        for dimension_name in dimension_names:
            set_dimension_symmetric_tolerance(
                adapter, feature_name, dimension_name, POSITION_TOL
            )
    # The ear's +Y edge in the guide-lock sweep and the screw holes' y-edge
    # walls; the far screw hole's -X edge wall.
    set_dimension_symmetric_tolerance(adapter, "BaseEar", "Width", WIDTH_TOL)
    set_dimension_symmetric_tolerance(
        adapter, "BaseEarProfile", "BaseLength", BASE_LENGTH_TOL
    )
    # Every hand-formed arm feature carries the one formed band; the far face
    # at the pin its per-axis share of it.
    for bands, band in ((FORMED_DIMENSIONS, FORMED_BAND), (FACE_DIMENSIONS, FACE_BAND)):
        for feature_name, dimension_names in bands.items():
            for dimension_name in sorted(dimension_names):
                set_dimension_symmetric_tolerance(
                    adapter, feature_name, dimension_name, band
                )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Hidden so no assembly instance renders it; the drawing shows it per view.
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    apply_drawing_properties(adapter, PART_NAME, DRAWING_PROPERTIES)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
