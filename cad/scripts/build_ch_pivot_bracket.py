r"""Reproduction script: rocker pivot bracket (MHA-CH-08; book ch. 14 pp. 26-27; 2 used).

The black steel bracket that carries each end of the rocker pivot shaft on
the green rocker-arm support (ch14 page002_img01/img02, page002_img07
"pivot"). 2026-09-02 photo re-derive: it is an L, not a T -- the ear stands
at one END of the foot, and the foot is only as wide as the support's apex.
#743 PR2 (Reading 1, user Q4): the bright dome on the ear is the pivot
shaft's own domed end, not a brazed-on ball, so the ear is a plain plate
arched EAR_W/2 over the O.256 cross-bore, its apex EAR_TOP_Y over the seat
(#1371: the arch's centre stands ARCH_LIFT over the bore so the apex tap
keeps 1.5D of full thread). The north ear's inner face is the
rocker bank's axial datum (the north thrust washer behind hub 19 bears on
it); the south one is set off the MHA-CH-VN-54 preload spring
(``rocker_bank_layout``). One MHA-CH-VN-53 #4-40 set screw
drops through each ear's arch apex onto the pivot shaft's flat (user,
2026-10-10).

The channel assembly inserts the NORTH bracket as IDENTITY and the SOUTH one
turned Ry(180) about its bore axis, so both feet run OUTBOARD, away from the
rocker stack (user-approved sketch, 2026-10-09). One part serves both sides
(#1341, option A): its foot ends flush with the south support end face and
short of the north one (``ch_pivot_bracket_sides`` derives the foot end
``FootZ1`` and hole station ``HoleZ`` from both sides).

Layout (part frame; the section lives in ``ch_pivot_bracket_spec``): seat face
at y = 0; origin under the bore, on the seat plane. Foot FOOT_W along X by
FOOT_H tall by FOOT_Z0..FootZ1 along Z; ear EAR_W (= FOOT_W, so its sides run
flush with the foot's) wide by EAR_T thick (Z), centred on the origin: a block
from the foot top to the arch centre (BORE_H + ARCH_LIFT) plus a full
O EAR_W boss on that centre, whose upper half is the arch (the arbor-pedestal
crown idiom: no arcs, only proven primitives); O BORE_DIA cross-bore along Z;
one #4-40 tap down through the arch apex (EAR_TOP_Y) on x = 0, z = 0 into
the bore (``SetScrewTap``); one hold-down hole through the foot on x = 0 in
the foot's free run (``ch_pivot_bracket_sides`` places it), its station
(``HoleStation``) dimensioned from the ear's inboard face at FOOT_Z0; the
foot-to-ear inside corner filleted at its MAX radius (``CornerFillet``).

Drawing contract (``ch_pivot_bracket_drawing_spec``): four blanked
reference-line sketches carry the bore's and the hold-down hole's lateral
locations off the west side face, the apex tap's station off the inboard
face and the overall height off the seat; the build marks the drawing
dimensions, owns their decimal places and bands, and authors the foot seat's
finish.

Volume (``V_TOTAL``): foot FOOT_W * FOOT_H * FOOT_LEN, plus the ear block
EAR_W * (BORE_H + ARCH_LIFT - FOOT_H) * EAR_T and the arch half-disc
pi R^2 / 2 * EAR_T, less the bore, the apex tap's drill from the arch down to
the bore (``V_TAP``) and the hold-down hole, plus the corner fillet's
spandrel (``V_CORNER``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_pivot_bracket.py
"""

from __future__ import annotations

import math
import sys

from _appearance import PANEL_BLACK, apply_color, apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
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
from _sketch_circle import define_circle
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _hole_spec import blind_cut_dia_mm
from _holes import cross_hole_volume_mm3, wizard_hole_on_cylinder
from _part_pmi import author_part_pmi
import _telemetry
from ch_pivot_bracket_drawing_spec import (
    BORE_DIA_BAND,
    CORNER_R_BAND,
    CORNER_R_MAX,
    CORNER_R_TOL_TYPE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    REFERENCE_SKETCHES,
    SURFACE_FINISHES,
)
from ch_pivot_bracket_sides import FOOT_LEN, FOOT_Z1, HOLE_STATION, HOLE_Z
from ch_pivot_bracket_spec import (
    ARCH_LIFT,
    BORE_DIA,
    BORE_H,
    EAR_ARCH_R,
    EAR_T,
    EAR_T_BAND,
    EAR_TOP_Y,
    EAR_W,
    FOOT_H,
    FOOT_W,
    FOOT_Z0,
    HOLE_DIA,
    SET_SCREW_HOLE_SPEC,
    SET_SCREW_STATION_BAND,
    UNIT,
)


PART_NAME = "ch-pivot-bracket"
MATERIAL = "Plain Carbon Steel"  # black-finished steel (ch14 p.27)

V_FOOT = FOOT_W * FOOT_H * FOOT_LEN
# The ear block sits on the foot top, as wide as the foot: its sides merge
# into the foot's, so the part stays one body and the volumes simply add. It
# rises to the arch's centre, ARCH_LIFT over the bore.
ARCH_CENTER_Y = BORE_H + ARCH_LIFT
V_BLOCK = EAR_W * (ARCH_CENTER_Y - FOOT_H) * EAR_T
V_ARCH = 0.5 * math.pi * EAR_ARCH_R**2 * EAR_T  # the boss's upper half
V_BORE = math.pi * (BORE_DIA / 2.0) ** 2 * EAR_T
V_HOLE = math.pi * (HOLE_DIA / 2.0) ** 2 * FOOT_H
# The apex tap's drill runs on x = 0 from the arch down to the bore: half of
# the arch's perpendicular cross-hole volume, the straight drill over the
# ARCH_LIFT between the arch's centre and the bore's, less half of the bore's
# (the arbor pedestal's crown-minus-bore idiom, its two axes ARCH_LIFT apart).
TAP_DRILL_DIA = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC)
V_TAP = (
    cross_hole_volume_mm3(TAP_DRILL_DIA, 2.0 * EAR_ARCH_R)
    - cross_hole_volume_mm3(TAP_DRILL_DIA, BORE_DIA)
) / 2.0 + math.pi * (TAP_DRILL_DIA / 2.0) ** 2 * ARCH_LIFT
# The foot-to-ear inside corner's fillet adds its spandrel, (1 - pi/4) R^2,
# along the ear's width.
V_CORNER = (1.0 - math.pi / 4.0) * CORNER_R_MAX**2 * EAR_W
V_TOTAL = V_FOOT + V_BLOCK + V_ARCH - V_BORE - V_TAP - V_HOLE + V_CORNER
if EAR_ARCH_R != EAR_W / 2.0 or ARCH_CENTER_Y - EAR_ARCH_R <= FOOT_H:
    raise AssertionError("the ear boss must be the block's width and clear the foot")
if EAR_W > FOOT_W:
    raise AssertionError("the ear must not overhang the foot's sides")
if abs(ARCH_CENTER_Y + EAR_ARCH_R - EAR_TOP_Y) > 1e-9:
    raise AssertionError("the arch apex must be the ear top the tap starts on")
if not 0.0 < ARCH_LIFT < BORE_DIA / 2.0:
    raise AssertionError("the arch centre must stand over the bore, inside it")

# The drawing-reference lines (ch_pivot_bracket_drawing_spec.REFERENCE_SKETCHES):
# (sketch, plane, dimension, start, end, orientation, value, drives). Points
# are sketch coordinates -- the Top plane's sketch y is model -Z, the Front
# plane's is model +Y. The lateral and station lines lie on the part outline,
# so the view that shows their sketch prints no extra line, and each starts
# on a FEATURE (drawing-guidelines.md rule 10): the west side face for the
# lateral locations, the ear's inboard face for the tap station, the seat
# for the overall height (its line runs up the tap's axis to the apex).
# ``drives`` binds, in creation order, the value dimension and then the start
# point's origin anchors (x then y for a general point, one for a point on a
# sketch axis) to the part's globals, so a global edit moves the line with the
# geometry.
REFERENCE_LINES = (
    (
        "BoreLateralReference",
        "Front",
        "BoreLateral",
        (-FOOT_W / 2.0, 0.0),
        (0.0, 0.0),
        "horizontal",
        FOOT_W / 2.0,
        ('"FootW" / 2', '"FootW" / 2'),
    ),
    (
        # Along the foot's free end edge, west side to the hole's x = 0.
        "HoleLateralReference",
        "Top",
        "HoleLateral",
        (-FOOT_W / 2.0, -FOOT_Z1),
        (0.0, -FOOT_Z1),
        "horizontal",
        FOOT_W / 2.0,
        ('"FootW" / 2', '"FootW" / 2', '"FootZ1"'),
    ),
    (
        # Along the east side face, inboard face to the tap's z = 0.
        "SetScrewReference",
        "Top",
        "SetScrewLocation",
        (FOOT_W / 2.0, -FOOT_Z0),
        (FOOT_W / 2.0, 0.0),
        "vertical",
        -FOOT_Z0,
        ('"EarT" / 2', '"FootW" / 2', '"EarT" / 2'),
    ),
    (
        # Up the tap's axis, the seat to the arch apex.
        "HeightReference",
        "Front",
        "OverallHeight",
        (0.0, 0.0),
        (0.0, EAR_TOP_Y),
        "vertical",
        EAR_TOP_Y,
        ('"TopH"',),
    ),
)
if tuple(row[0] for row in REFERENCE_LINES) != REFERENCE_SKETCHES:
    raise AssertionError("REFERENCE_LINES and REFERENCE_SKETCHES disagree")


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry.

    ``ConstructionGeometry`` is declared on the base ISketchSegment, not the
    derived ISketchLine the entity registry binds -- rebind before the set.
    """
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _reference_line(
    adapter, sketch, plane, dimension, start, end, orientation, value, drives
) -> list[tuple[str, str]]:
    """One hidden-reference sketch: a construction line whose driving
    dimension IS ``value``; returns its deferred drive jobs
    (build_dt_arbor_pedestal's idiom)."""
    check(f"create_sketch {sketch}", await adapter.create_sketch(plane))
    # Direct-to-DB: the line lies on an outline edge and runs along a sketch
    # axis direction, so creation-time inference would snap in the relations
    # added below and over-define the sketch.
    set_sketch_direct_db(adapter, True)
    line = check(f"{sketch} line", await adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    check(
        f"{sketch} {orientation}",
        await adapter.add_sketch_constraint(line, None, orientation),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        f"{orientation}_distance",
        value,
        sketch,
    )
    await anchor_point_to_origin(adapter, f"{line}.start", *start, sketch)
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    names = [dimension, *(f"{dimension}Anchor{i}" for i in range(1, len(drives)))]
    full = name_dimensions(adapter, sketch, names)
    dimension_value = _early_bound(
        adapter.currentModel.Parameter(full[0]), "IDimension"
    ).SystemValue
    measured = float(dimension_value) * 1000.0
    if abs(measured - value) > 1e-6:
        raise RuntimeError(f"{full[0]} measures {measured:g} mm, expected {value:g} mm")
    return list(zip(full, drives, strict=True))


@_telemetry.traced("appearance.hide_reference_sketches")
def _hide_reference_sketches(adapter) -> None:
    """Blank the drawing-reference sketches and prove each one reads hidden."""
    for name in REFERENCE_SKETCHES:
        blank_sketch(adapter, name)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    shown = {
        name: visible
        for name in REFERENCE_SKETCHES
        # swVisibilityState_e: 1 hidden
        if (visible := int(_read_member(part.FeatureByName(name), "Visible"))) != 1
    }
    if shown:
        raise RuntimeError(f"reference sketches still visible after blanking: {shown}")


def _corner_radius_max_limit(adapter) -> None:
    """CornerRadius as the single limit "R.02 MAX" carrying the band's
    deviations (build_pn_pen_rod._shoulder_fillet_max_limit's recipe)."""
    lower, upper = deviations(CORNER_R_BAND)
    _, dimension = _named_dimension(adapter, "CornerFillet", "CornerRadius")
    label = "CornerRadius@CornerFillet"
    value = float(dimension.SystemValue)
    if not math.isclose(value, CORNER_R_MAX / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max {CORNER_R_MAX}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = CORNER_R_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != CORNER_R_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {CORNER_R_MAX:g} MAX")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    await set_global(adapter, "FootW", f"{FOOT_W}mm")
    await set_global(adapter, "FootH", f"{FOOT_H}mm")
    await set_global(adapter, "FootZ1", f"{FOOT_Z1}mm")
    await set_global(adapter, "HoleZ", f"{HOLE_Z}mm")
    await set_global(adapter, "EarW", f"{EAR_W}mm")
    await set_global(adapter, "EarT", f"{EAR_T}mm")
    await set_global(adapter, "BoreH", f"{BORE_H}mm")
    await set_global(adapter, "TopH", f"{EAR_TOP_Y}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")
    await set_global(adapter, "CornerR", f"{CORNER_R_MAX}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Foot: Top-plane rectangle (sketch y = model -Z) x +-W/2, z FOOT_Z0..
    # FootZ1, extruded +Y by FOOT_H. Emission: seg0 width, seg1 length, then
    # the (-W/2, -FootZ1) corner anchor (x then z; the anchor z lands at the
    # magnitude FootZ1 -- the magnifying-bracket Top-sketch idiom).
    half_w = FOOT_W / 2.0
    foot_z1 = FOOT_Z1
    foot = SketchDims()
    check("create_sketch foot", await adapter.create_sketch("Top"))
    rect = [
        (-half_w, -foot_z1),
        (half_w, -foot_z1),
        (half_w, -FOOT_Z0),
        (-half_w, -FOOT_Z0),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="foot", dims=foot,
        names=["FootW", "FootLen", "FootAnchorX", "FootAnchorZ"],
        drives=['"FootW"', '"FootZ1" + "EarT" / 2', '"FootW" / 2', '"FootZ1"'],
    )
    await ensure_fully_defined(adapter, "foot sketch")
    check("exit_sketch foot", await adapter.exit_sketch())
    name_last_feature(adapter, "FootProfile")
    drive_jobs += foot.apply(adapter, "FootProfile")
    check(
        "extrude foot",
        await adapter.create_extrusion(ExtrusionParameters(depth=FOOT_H)),
    )
    name_last_feature(adapter, "Foot")
    foot_ht_dim = name_dimensions(adapter, "Foot", ["FootHt"])
    drive_jobs.append((foot_ht_dim[0], '"FootH"'))
    expected = V_FOOT
    await volume_check(adapter, "foot", expected, 0.005 * expected)

    # Ear block: Front-plane rectangle x +-EAR_W/2, y FOOT_H..the arch centre
    # (ARCH_LIFT over the bore), extruded both ways (EAR_T total) -- its Z
    # band is the bore's; its sides lie in the foot's, so the merge leaves one
    # body. Emission: seg0 width, seg1 rise, then the (-EAR_W/2, FOOT_H)
    # corner anchor (x, z).
    half_e = EAR_W / 2.0
    ear = SketchDims()
    check("create_sketch ear", await adapter.create_sketch("Front"))
    ear_rect = [
        (-half_e, FOOT_H),
        (half_e, FOOT_H),
        (half_e, ARCH_CENTER_Y),
        (-half_e, ARCH_CENTER_Y),
    ]
    ear_lines = await add_line_chain(adapter, ear_rect)
    await define_rectilinear_chain(
        adapter, ear_lines, ear_rect, label="ear", dims=ear,
        names=["EarW", "EarRise", "EarAnchorX", "EarAnchorZ"],
        drives=[
            '"EarW"',
            '"TopH" - "EarW" / 2 - "FootH"',
            '"EarW" / 2',
            '"FootH"',
        ],
    )
    await ensure_fully_defined(adapter, "ear sketch")
    check("exit_sketch ear", await adapter.exit_sketch())
    name_last_feature(adapter, "EarProfile")
    drive_jobs += ear.apply(adapter, "EarProfile")
    check(
        "extrude ear",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=EAR_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Ear")
    # The ear thickness carries its +/-.004 band natively: named so the band
    # selects it by name (the MHA-CH-03 ForkThick idiom).
    ear_thick_dim = name_dimensions(adapter, "Ear", ["EarThick"])
    drive_jobs.append((ear_thick_dim[0], '"EarT"'))
    expected += V_BLOCK
    await volume_check(adapter, "ear block", expected, 0.005 * V_BLOCK)

    # Ear arch: a full O EAR_W boss on the block's top edge (ARCH_LIFT over
    # the bore), the block's own width, merged over it -- its lower half lies
    # inside the block, its upper half is the arch (the arbor-pedestal crown
    # idiom). On-axis in X, so define_circle records the rise + size. The size
    # is the RADIUS the print gives the arch (a sheet must never flip a model
    # diameter radial).
    arch = SketchDims()
    check("create_sketch arch", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, ARCH_CENTER_Y, EAR_ARCH_R, "ear arch",
        dims=arch, names=("ArchCx", "ArchCz", "ArchRadius"),
        drives=(None, '"TopH" - "EarW" / 2', '"EarW" / 2'),
        size_dimension="radius",
    )
    await ensure_fully_defined(adapter, "arch sketch")
    check("exit_sketch arch", await adapter.exit_sketch())
    name_last_feature(adapter, "ArchProfile")
    drive_jobs += arch.apply(adapter, "ArchProfile")
    check(
        "extrude arch",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=EAR_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Arch")
    expected += V_ARCH
    await volume_check(adapter, "ear arch", expected, 0.01 * V_ARCH)

    # Shaft cross-bore along Z at (0, BORE_H), through the ear.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_H, BORE_DIA / 2.0, "shaft bore",
        dims=bore, names=("BoreCx", "BoreCz", "ShaftBoreDia"),
        drives=(None, '"BoreH"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftBoreProfile")
    drive_jobs += bore.apply(adapter, "ShaftBoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=EAR_T + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")
    expected -= V_BORE
    await volume_check(adapter, "shaft bore", expected, 0.02 * V_BORE)

    # Apex set-screw tap (user, 2026-10-10): ONE native #4-40 tapped hole
    # drilled radially down through the arch apex on the ear's mid-plane and
    # stopped at the next surface -- the shaft bore -- so it never runs on
    # into the ear below (build_dt_arbor_pedestal's apex-tap idiom). The arch is the
    # cylinder the wizard drills: its normal at the apex is -Y, through the
    # arch's axis and on down through the bore's, ARCH_LIFT below it. Front
    # Plane holds the point on z = 0, Right Plane clocks it to the apex.
    wizard_hole_on_cylinder(
        adapter,
        SET_SCREW_HOLE_SPEC,
        [0.0, EAR_TOP_Y, 0.0],
        "apex set-screw tap (#4-40)",
        name="SetScrewTap",
        point_planes=("Front Plane", "Right Plane"),
    )
    expected -= V_TAP
    await volume_check(adapter, "apex set-screw tap", expected, 0.03 * V_TAP)

    # Hold-down hole through the foot: a Top-plane circle on x = 0 (sketch
    # (u, v) = model (X, -Z)), cut both ways past the foot height. A
    # construction line on x = 0 from the ear's inboard face (FOOT_Z0, the
    # face fit-up sets and the S4 hold's Z0) to the hole centre carries the
    # station, HoleStation = HoleZ + EarT / 2 (build_pd_transgear_disc_hub's
    # oil-hole station idiom); the circle's centre sits on its end.
    hole_z = HOLE_Z
    hole = SketchDims()
    check("create_sketch hole", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    station = check(
        "hold-down hole station line",
        await adapter.add_line(0.0, -FOOT_Z0, 0.0, -hole_z),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, station)
    check(
        "hold-down hole station vertical",
        await adapter.add_sketch_constraint(station, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{station}.start", 0.0, -FOOT_Z0, "hole datum at the inboard face"
    )
    hole.record("HoleDatum", '"EarT" / 2')
    await dimension_between(
        adapter,
        f"{station}.start",
        f"{station}.end",
        "vertical_distance",
        HOLE_STATION,
        "hold-down hole station from the ear's inboard face",
    )
    hole.record("HoleStation", '"HoleZ" + "EarT" / 2')
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        circle = check(
            "hold-down hole circle",
            await adapter.add_circle(0.0, -hole_z, HOLE_DIA / 2.0),
        )
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    check(
        "hold-down hole centre on the station",
        await adapter.add_sketch_constraint(
            f"{circle}.center", f"{station}.end", "coincident"
        ),
    )
    check(
        "hold-down hole diameter",
        await adapter.add_sketch_dimension(circle, None, "diameter", HOLE_DIA),
    )
    hole.record("HoleDia", '"HoleDia"')
    await ensure_fully_defined(adapter, "hole sketch")
    check("exit_sketch hole", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += hole.apply(adapter, "HoleProfile")
    check(
        "cut hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * FOOT_H + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "HoldDownHole")
    expected -= V_HOLE
    await volume_check(adapter, "hold-down hole", expected, 0.02 * V_HOLE)

    # Foot-to-ear inside corner (drawing-guidelines.md rule 16): the edge where
    # the foot top meets the ear's outboard face, filleted AT the largest
    # radius the hold-down screw's head clears (CORNER_R_MAX), the radius the
    # print gives as a single MAX limit.
    check(
        "fillet foot-to-ear corner",
        await adapter.add_fillet(
            CORNER_R_MAX, [[0.0, FOOT_H, EAR_T / 2.0]], propagate=False
        ),
    )
    name_last_feature(adapter, "CornerFillet")
    corner_dim = name_dimensions(adapter, "CornerFillet", ["CornerRadius"])
    drive_jobs.append((corner_dim[0], '"CornerR"'))
    expected += V_CORNER
    await volume_check(adapter, "foot-to-ear corner fillet", expected, 0.1 * V_CORNER)

    for row in REFERENCE_LINES:
        drive_jobs += await _reference_line(adapter, *row)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven bracket (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    _hide_reference_sketches(adapter)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)

    # Decimal places are the tolerance statement, so the PART carries them
    # (drawing-simplicity-policy.md `How the repository implements the
    # guidelines`); the drawing reads them back instead of rewriting them.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _corner_radius_max_limit(adapter)
    # Two lengths carry +/-.004 natively (ch_pivot_bracket_spec): the apex
    # tap's station from the ear's inboard face -- the face fit-up sets and
    # the S4 hold touches Z0 on -- and the ear thickness. The foot length and
    # the hold-down station ride the title block. The cross-bore holds the
    # drilled-hole row's +.004/0 its set-screw thread is counted at.
    set_dimension_symmetric_tolerance(
        adapter, "Ear", "EarThick", EAR_T_BAND, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "SetScrewReference",
        "SetScrewLocation",
        SET_SCREW_STATION_BAND,
        display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "ShaftBoreProfile",
        "ShaftBoreDia",
        *deviations(BORE_DIA_BAND),
        places=3,
        display_unit=UNIT,
    )

    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)

if __name__ == "__main__":
    sys.exit(run_build(build))
