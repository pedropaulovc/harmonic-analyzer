r"""Reproduction script: pinion return spring (book ch. 25; 1 used).

The leaf spring that holds the alignment-pinion drum disengaged by default
(p. 68-69 close-ups img01/img03/img04; video frames v4_pinion_013/018/019):
a 17-7 PH stainless strip screwed to the base EAST of the BACK swing strap,
outboard, rising in a blade that leans IN toward the strap and bears on its
east flank 23.0 up from the pivot, 5.0 below the arbor.  Gravity swings the
cluster east into mesh; the blade pushes the strap top back west onto the
parked cam, and the lever engages against it.

Re-derived 2026-09-24 (handoff dt-pinion-spring-rederive-20260924): the old
foot ran 35 WEST under the strap and the lift rod, read off img01's far-left
screw as west -- that side of img01 is the drum side, east.

Layout (sketch on the Front plane; the assembly seats the part at its machine
anchor, base top 50.8, with a composed Ry(180), so part-local +x reads machine
EAST -- direction words below are MACHINE directions; the part is an exact
mid-plane z-extrude, so the Ry(180)'s z-flip is immaterial): the strip's
INSIDE-surface path, drawn from the free tip down = a 2.0 flat, an R_KINK x 25
deg crest turning back west, the straight blade leaning BLADE_LEAN_DEG west of
vertical, an R_BEND bend, and the FOOT_LEN foot heading EAST to its free end.
Traced that way the one-sided thin wall lands right of travel -- west of the
blade, under the foot -- so the blade's west face is the contact face.  The
pad-merge volume gate proves the foot side and a west-extreme probe the
blade side.  Thin mid-plane extrude, WIDTH symmetric about z 0, plus a square
screw pad (PAD_WIDTH x PAD_LEN) at the foot's free end, its wing set back
behind a PAD_RELIEF_R MAX bend relief, cut with the flat blank.

The model is the INSTALLED, parked shape (O2); the maker forms the free shape,
PRESET_DEG more bend (dt_pinion_spring_geometry).

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_pinion_spring.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _holes import blind_cut_dia_mm, wizard_holes
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _saved_part_guard import require_saved_drawing_properties
from dt_pinion_spring_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FLAT_LEN,
    FOOT_LEN,
    FORMED_BANDED_DIMENSIONS,
    FORMED_TOLERANCE_MM,
    FREE_FORM_SKETCH,
    ISOMETRIC_VIEW_NOTE,
    PAD_RELIEF_DIMENSION,
    PAD_RELIEF_FEATURE,
    PAD_RELIEF_R,
    PAD_RELIEF_TOL_TYPE,
    PAD_WIDTH,
    PAD_Z,
    R_BEND,
    R_KINK,
    THICK,
    WIDTH,
)
from dt_pinion_spring_geometry import (
    BEND_CX,
    BEND_CY,
    BEND_EXIT,
    FLAT_TIP,
    FOOT_END,
    FOOT_TAN,
    FOOT_Y,
    FREE_BEND_EXIT,
    FREE_FLAT_TIP,
    FREE_KINK_ANGLE_BISECTOR,
    FREE_KINK_C,
    FREE_KINK_EXIT,
    FREE_KINK_START,
    FREE_KINK_VERTEX,
    HOLE_DIA as HOLE_DIA,
    HOLE_FROM_END,
    HOLE_SPEC,
    KINK_ANGLE_BISECTOR,
    KINK_C,
    KINK_DEG,
    KINK_EXIT,
    KINK_START,
    KINK_VERTEX,
    PAD_RELIEF_VOLUME,
    PAD_VOLUME,
    PAD_WING_LEN,
    VOLUME,
)

PART_NAME = "dt-pinion-spring"
# #859 ruling 4: 17-7 PH stainless, Condition C (the registry row carries the
# stock).  p.68 reads the leaf brass-coloured; Main traded that look for a
# corrosion-resistant spring that holds the corner gates (ruling 3).  The
# SolidWorks library material the repo already uses for stainless, "AISI 304",
# stands in for 17-7 PH (7.81 vs 8.0 g/cc; the part weighs about a gram).
MATERIAL = "AISI 304"

# Primitive nominals come from the drawing spec (single source of truth shared
# with the manufacturing print). Design rationale:
#   FOOT_LEN -- the pad plus a short straight to the bend: the foot heads EAST,
#               outboard, away from the strap and the lift rod.
#   FLAT_LEN -- short on purpose: the flick turns back east, clear of the strap.

_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)


def _pad_relief_max_limit(adapter) -> None:
    """PadReliefR as a single MAX limit, sharp up to the nominal
    (build_pn_pen_rod._shoulder_fillet_max_limit's recipe): the native type
    prints the nominal, so the nominal is the limit."""
    _, dimension = _named_dimension(adapter, PAD_RELIEF_FEATURE, PAD_RELIEF_DIMENSION)
    label = f"{PAD_RELIEF_DIMENSION}@{PAD_RELIEF_FEATURE}"
    value = float(dimension.SystemValue)
    if not math.isclose(value, PAD_RELIEF_R / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the limit {PAD_RELIEF_R}"
        )
    lower, upper = -PAD_RELIEF_R / 1000.0, 0.0
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = PAD_RELIEF_TOL_TYPE
    if not tolerance.SetValues(lower, upper):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} m")
    if (
        int(tolerance.Type) != PAD_RELIEF_TOL_TYPE
        or not math.isclose(float(tolerance.GetMinValue()), lower, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), upper, abs_tol=1e-12)
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {PAD_RELIEF_R:g} MAX")


def _extreme_mm(adapter, direction: tuple[float, float, float], axis: int) -> float:
    """The solid's extreme coordinate (mm) along ``direction`` on ``axis``.

    ``IBody2::GetExtremePoint`` is exact (``GetBodyBox`` is approximate); the
    early-bound wrapper returns (ok, x, y, z) in metres.
    """
    doc = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, False)) or []
    if len(bodies) != 1:
        raise RuntimeError(f"spring: expected one solid body, found {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    res = adapter._attempt(lambda: body.GetExtremePoint(*direction), default=None)
    if not res or len(res) < 4:
        raise RuntimeError("spring: GetExtremePoint failed")
    return float(res[1 + axis]) * 1000.0


INSTALLED_PATH = {
    "flat_tip": FLAT_TIP,
    "kink_exit": KINK_EXIT,
    "kink_c": KINK_C,
    "kink_start": KINK_START,
    "bend_exit": BEND_EXIT,
    "bend_c": (BEND_CX, BEND_CY),
    "foot_tan": FOOT_TAN,
    "foot_end": FOOT_END,
    "kink_vertex": KINK_VERTEX,
    "kink_bisector": KINK_ANGLE_BISECTOR,
}
FREE_PATH = {
    **INSTALLED_PATH,
    "flat_tip": FREE_FLAT_TIP,
    "kink_exit": FREE_KINK_EXIT,
    "kink_c": FREE_KINK_C,
    "kink_start": FREE_KINK_START,
    "bend_exit": FREE_BEND_EXIT,
    "kink_vertex": FREE_KINK_VERTEX,
    "kink_bisector": FREE_KINK_ANGLE_BISECTOR,
}
# The kink angle's text point in the sketch, this far from the vertex (mm)
# along the lower acute wedge's bisector turned clockwise by each of these in
# turn (deg): the lower acute wedge, its vertically opposite, then the two
# obtuse wedges.  The first placement that reads 25 deg is kept.
KINK_ANGLE_TEXT_MM = 4.0
KINK_ANGLE_WEDGE_TURNS_DEG = (0.0, 180.0, 90.0, -90.0)


def _as_construction(adapter, entity_id: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _driving_kink_angle(adapter, blade: str, flat: str, pts, label: str) -> None:
    """The kink's sweep as the DRIVING angle between the blade and flat lines.

    Both lines are selected as segments
    (build_dt_cone_pivot_post._add_driving_plan_incline's recipe) and the
    text point decides which of the four angles at the lines' crossing
    (dt_pinion_spring_geometry.KINK_VERTEX) is measured
    (build_dt_cylinder_gear's notch phase); on the Front plane the sketch and
    model frames coincide, so it goes in model metres.  With the text on the
    bisector of the acute wedge below the crossing SOLIDWORKS read 155 deg
    (spring r3 leaf), and its SupplementaryAngle left the reading at 155
    whether turned driving (r6) or driven (r7).  So the dimension is placed,
    made DRIVEN and read, in each wedge in turn (the lower acute one first)
    and deleted unless it reads 25 deg; the first 25 deg reading is made
    driving and read back.  Every reading is logged and named if none
    reads 25.  Which of the two acute wedges the arc takes the print checks
    and, if need be, turns to its vertically opposite
    (draw_dt_pinion_spring._assert_kink_angle_wedge).
    """
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    vertex, bisector = pts["kink_vertex"], pts["kink_bisector"]
    model = adapter.currentModel
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    expected = math.radians(KINK_DEG)
    readings: list[str] = []
    for turn in KINK_ANGLE_WEDGE_TURNS_DEG:
        c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
        text = (
            vertex[0] + KINK_ANGLE_TEXT_MM * (bisector[0] * c + bisector[1] * s),
            vertex[1] + KINK_ANGLE_TEXT_MM * (bisector[1] * c - bisector[0] * s),
        )
        model.ClearSelection2(True)
        _select_sketch_entities(adapter, [blade, flat], 0)
        display, status = extension.AddSpecificDimension(
            text[0] / 1000.0,
            text[1] / 1000.0,
            0.0,
            3,  # swDimensionType_e.swAngularDimension
            0,
        )
        model.ClearSelection2(True)
        if display is None:
            raise RuntimeError(
                f"{label}: AddSpecificDimension(angular) failed ({status})"
            )
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
        if int(_read_member(dimension, "DrivenState")) != 1:
            raise RuntimeError(f"{label}: angular dimension did not become driven")
        measured = abs(float(_read_member(dimension, "SystemValue")))
        degrees = math.degrees(measured)
        readings.append(f"{turn:g} deg off the lower bisector: {degrees:.6f}")
        _telemetry.info(f"{label}: text {readings[-1]} deg")
        if abs(measured - expected) <= 1e-8:
            break
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if not annotation.Select3(False, None):
            raise RuntimeError(f"{label}: cannot select the {degrees:.6f} deg reading")
        model.EditDelete()
        model.ClearSelection2(True)
    else:
        raise RuntimeError(
            f"{label}: no wedge reads {KINK_DEG:g} deg ({'; '.join(readings)} deg)"
        )
    dimension.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    state = int(_read_member(dimension, "DrivenState"))
    value = abs(float(_read_member(dimension, "SystemValue")))
    if state != 2 or abs(value - expected) > 1e-8:
        raise RuntimeError(
            f"{label}: angular dimension is not a driving {KINK_DEG:g} deg "
            f"(DrivenState {state}, {math.degrees(value):.6f} deg)"
        )
    _telemetry.success(f"driving {label}: {KINK_DEG:g} deg")


async def _formed_path(
    adapter, pts: dict[str, tuple[float, float]], *, prefix: str, construction: bool
) -> SketchDims:
    """The strip's inside-surface path in the open Front sketch, fully defined.

    Drawn from the free tip DOWN: flat -> crest (kink) -> blade -> bend ->
    foot, endpoints merged at creation.  The traversal order sets the
    one-sided thin wall's side (right of travel: west of the blade, under the
    foot).  Inference OFF: the foot endpoints sit near the origin.  add_arc
    runs counter-clockwise start -> end.  ``prefix`` names the dimensions
    (the free form's are "Free*"); ``construction`` makes every segment
    construction geometry (the hidden FreeForm reference sketch).
    """
    dims = SketchDims()
    set_sketch_direct_db(adapter, True)
    flat = check(
        f"{prefix}flat line",
        await adapter.add_line(*pts["flat_tip"], *pts["kink_exit"]),
    )
    kink = check(
        f"{prefix}kink arc",
        await adapter.add_arc(*pts["kink_c"], *pts["kink_exit"], *pts["kink_start"]),
    )
    blade = check(
        f"{prefix}blade line",
        await adapter.add_line(*pts["kink_start"], *pts["bend_exit"]),
    )
    bend = check(
        f"{prefix}bend arc",
        await adapter.add_arc(*pts["bend_c"], *pts["bend_exit"], *pts["foot_tan"]),
    )
    foot = check(
        f"{prefix}foot line",
        await adapter.add_line(*pts["foot_tan"], *pts["foot_end"]),
    )
    set_sketch_direct_db(adapter, False)
    if construction:
        for entity in (flat, kink, blade, bend, foot):
            _as_construction(adapter, entity)

    # Shape: the foot is horizontal, each arc is tangent to its neighbouring
    # line at the merged endpoint. Position: foot free end anchored to the
    # origin, foot length, both radii, then the kink start (the two literal
    # lean-dependent dims) and the kink's angle, blade to flat, which fixes
    # its sweep.
    # The print baselines the formed profile from the foot's free end (policy
    # drawing-guidelines.md rule 10 (dimension from a real feature)), so those locations dimension from foot.end, not the origin.
    check(
        f"{prefix}foot horizontal",
        await adapter.add_sketch_constraint(foot, None, "horizontal"),
    )
    for label, first, second in (
        ("bend tangent foot", bend, foot),
        ("bend tangent blade", bend, blade),
        ("kink tangent blade", kink, blade),
        ("kink tangent flat", kink, flat),
    ):
        check(
            f"{prefix}{label}",
            await adapter.add_sketch_constraint(first, second, "tangent"),
        )

    foot_end, kink_start = pts["foot_end"], pts["kink_start"]
    await anchor_point_to_origin(adapter, f"{foot}.end", *foot_end, "foot end")
    dims.record(f"{prefix}FootEndX")
    dims.record(f"{prefix}FootEndY")
    await dimension_between(
        adapter, f"{foot}.end", f"{foot}.start", "horizontal_distance", FOOT_LEN, "foot"
    )
    dims.record(f"{prefix}FootLen", '"FootLength"')
    check(
        f"{prefix}bend radius",
        await adapter.add_sketch_dimension(bend, None, "radial", R_BEND),
    )
    dims.record(f"{prefix}BendR", '"BendRadius"')
    await dimension_between(
        adapter,
        f"{foot}.end",
        f"{blade}.start",
        "horizontal_distance",
        foot_end[0] - kink_start[0],
        "kink start from the free end",
    )
    dims.record(f"{prefix}KinkH")
    await dimension_between(
        adapter,
        f"{foot}.end",
        f"{blade}.start",
        "vertical_distance",
        kink_start[1] - foot_end[1],
        "kink start above the foot",
    )
    dims.record(f"{prefix}KinkV")
    check(
        f"{prefix}kink radius",
        await adapter.add_sketch_dimension(kink, None, "radial", R_KINK),
    )
    dims.record(f"{prefix}KinkR", '"KinkRadius"')
    check(
        f"{prefix}flat length",
        await adapter.add_sketch_dimension(flat, None, "linear", FLAT_LEN),
    )
    dims.record(f"{prefix}FlatLen", '"FlatLength"')
    _driving_kink_angle(adapter, blade, flat, pts, f"{prefix}kink angle")
    dims.record(f"{prefix}KinkAngle", '"KinkAngle"')
    return dims


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing --
    # INCH document, the equation manager reads bare numbers in doc units.
    # StripThickness/StripWidth are the thin-extrude feature parameters
    # (built with the literals); declared so a GUI edit sees the knobs.
    # Blade-tilt-dependent endpoint dims stay literal (no trig equations --
    # the equation manager rejects several dim bindings, probed 2026-07-02).
    await set_global(adapter, "FootLength", f"{FOOT_LEN}mm")
    await set_global(adapter, "BendRadius", f"{R_BEND}mm")
    await set_global(adapter, "KinkRadius", f"{R_KINK}mm")
    await set_global(adapter, "FlatLength", f"{FLAT_LEN}mm")
    await set_global(adapter, "StripThickness", f"{THICK}mm")
    await set_global(adapter, "StripWidth", f"{WIDTH}mm")
    await set_global(adapter, "PadWidth", f"{PAD_WIDTH}mm")
    await set_global(adapter, "PadLength", f"{PAD_WING_LEN}mm")
    await set_global(adapter, "PadReliefRadius", f"{PAD_RELIEF_R}mm")
    await set_global(adapter, "KinkAngle", f"{KINK_DEG}deg")

    # Open inside-surface path, drawn from the free tip DOWN (_formed_path).
    check("create_sketch spring", await adapter.create_sketch("Front"))
    spring = await _formed_path(adapter, INSTALLED_PATH, prefix="", construction=False)

    await ensure_fully_defined(adapter, "spring sketch")
    check("exit_sketch spring", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringProfile")
    drive_jobs = spring.apply(adapter, "SpringProfile")

    # Open profile -> thin mid-plane extrude: depth is the TOTAL width
    # (SolidWorks splits it); the THICK wall lands one-sided, right of travel.
    check(
        "extrude spring",
        await adapter.create_extrusion(
            ExtrusionParameters(
                depth=WIDTH,
                both_directions=True,
                thin_feature=True,
                thin_thickness=THICK,
            )
        ),
    )
    name_last_feature(adapter, "Spring")
    drive_jobs += [
        (name_dimensions(adapter, "Spring", ["StripWidth"])[0], '"StripWidth"')
    ]
    volume = await volume_check(adapter, "spring", VOLUME, 0.01 * VOLUME)
    # Blade side: with the wall west of the path the crest's outer face is the
    # part's westmost point; on the wrong side it would read THICK further east
    # and every contact number would be off by the strip.
    west = _extreme_mm(adapter, (-1.0, 0.0, 0.0), axis=0)
    want = KINK_C[0] - (R_KINK + THICK)
    if abs(west - want) > 0.05:
        raise RuntimeError(
            f"spring wall on the wrong side: westmost x {west:.3f}, want {want:.3f}"
        )
    _telemetry.success(f"spring wall west of the blade: westmost x {west:.3f}")

    # Screw pad: a PAD_WIDTH-wide wing PAD_WING_LEN in from the foot's free end,
    # flush with the strip's aft edge, local -z (machine +z once placed
    # Ry(180)); the Top-plane sketch reads v = -z, so that edge is v = +W/2 and
    # the pad widens toward -v.  Extruded the strip thickness up from the foot's underside
    # (y 0, the gated side of the one-sided thin wall) so it merges with the
    # foot. The volume gate proves the merge: a pad on the wrong side would add
    # its whole footprint, not just the wing beside the strip.  The chain
    # starts on the wing's forward edge, so PadLen measures the edge the
    # print can witness (the aft edge runs on into the strip).
    pad = SketchDims()
    check("create_sketch pad", await adapter.create_sketch("Top"))
    x0 = FOOT_END[0]
    pad_pts = [
        (x0, WIDTH / 2.0 - PAD_WIDTH),
        (x0 - PAD_WING_LEN, WIDTH / 2.0 - PAD_WIDTH),
        (x0 - PAD_WING_LEN, WIDTH / 2.0),
        (x0, WIDTH / 2.0),
    ]
    pad_lines = await add_line_chain(adapter, pad_pts)
    await define_rectilinear_chain(
        adapter,
        pad_lines,
        pad_pts,
        anchor=3,
        label="pad",
        dims=pad,
        names=["PadLen", "PadWidth", "PadEndX", "PadEdgeZ"],
        drives=['"PadLength"', '"PadWidth"', None, '"StripWidth" / 2'],
    )
    await ensure_fully_defined(adapter, "pad sketch")
    check("exit_sketch pad", await adapter.exit_sketch())
    name_last_feature(adapter, "PadProfile")
    drive_jobs += pad.apply(adapter, "PadProfile")
    check(
        "extrude pad",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICK)),
    )
    name_last_feature(adapter, "Pad")
    drive_jobs += [(name_dimensions(adapter, "Pad", ["PadThk"])[0], '"StripThickness"')]
    volume += PAD_VOLUME
    padded = await volume_check(adapter, "pad", volume, 0.02 * PAD_VOLUME)

    # Bend relief: the wing's inside corner, where its west edge meets the
    # strip's forward edge PAD_RELIEF_R east of the bend tangent, rounds at
    # PAD_RELIEF_R, so the round ends tangent to the strip AT the bend tangent.
    # The volume gate is on the measured step: the concave round ADDS its
    # spandrel (a round on a convex edge would remove one).
    check(
        "fillet pad relief",
        await adapter.add_fillet(
            PAD_RELIEF_R,
            [[x0 - PAD_WING_LEN, THICK / 2.0, WIDTH / 2.0]],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "PadRelief")
    drive_jobs += [
        (name_dimensions(adapter, "PadRelief", ["PadReliefR"])[0], '"PadReliefRadius"')
    ]
    volume += PAD_RELIEF_VOLUME
    await volume_check(
        adapter, "pad relief", padded + PAD_RELIEF_VOLUME, 0.5 * PAD_RELIEF_VOLUME
    )

    # Foot screw hole (PR7 item 11): ONE native Hole Wizard #4 clearance feature
    # (through-all along Y) through the foot strip near its free end, drilled
    # from the foot's underside (normal -Y). The path is the foot's top face at
    # y=FOOT_Y and the wall lies under it (the pad gate proved it), so the -Y
    # face is within the 1.0 mm find_planar_face tolerance of the FOOT_Y point
    # and the -Y normal filter disambiguates it from the top face.
    screw_dia = blind_cut_dia_mm(HOLE_SPEC)
    wizard_holes(
        adapter,
        HOLE_SPEC,
        [[FOOT_END[0] - HOLE_FROM_END, FOOT_Y, PAD_Z]],
        (0.0, -1.0, 0.0),
        "foot screw hole (#4 clearance)",
        name="FootHole",
    )
    v_hole = math.pi * (screw_dia / 2.0) ** 2 * THICK
    volume -= v_hole
    await volume_check(adapter, "foot hole", volume, 0.05 * v_hole)

    # O2 (Main, 2026-09-24): the part is the INSTALLED shape; the maker forms
    # the FREE shape.  A hidden construction-only reference sketch carries the
    # whole free profile -- the blade turned PRESET_DEG further toward the
    # strap about the bend centre -- and owns the printed free locations; the
    # drawing shows it as the phantom (_drawing_hidden_sketches).
    check("create_sketch free form", await adapter.create_sketch("Front"))
    free = await _formed_path(adapter, FREE_PATH, prefix="Free", construction=True)
    await ensure_fully_defined(adapter, "free-form sketch")
    check("exit_sketch free form", await adapter.exit_sketch())
    name_last_feature(adapter, FREE_FORM_SKETCH)
    drive_jobs += free.apply(adapter, FREE_FORM_SKETCH)

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven spring (equations neutral)", volume, 0.01 * VOLUME
    )

    # Manufacturing drawing support: the formed features that set the crest's
    # preload carry the one formed band, the rest of the profile rides the
    # title-block .X row, the blank's cut features its .XX row, and the pad's
    # bend relief a single MAX limit. The part authors the decimal places and
    # the drawing reads them back.
    for feature_name, dimension_names in FORMED_BANDED_DIMENSIONS.items():
        for name in sorted(dimension_names):
            set_dimension_symmetric_tolerance(
                adapter, feature_name, name, FORMED_TOLERANCE_MM
            )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _pad_relief_max_limit(adapter)

    # Hidden so no assembly instance renders it; the drawing shows it per view.
    blank_sketch(adapter, FREE_FORM_SKETCH)
    part_doc = _early_bound(adapter.currentModel, "IPartDoc")
    feature = _early_bound(part_doc.FeatureByName(FREE_FORM_SKETCH), "IFeature")
    if int(feature.Visible) != 1:  # swVisibilityStateHide
        raise RuntimeError(f"{FREE_FORM_SKETCH} still visible after BlankSketch")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
