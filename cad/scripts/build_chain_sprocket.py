r"""Reproduction script: drive-chain sprocket (book ch. 23; 2 used).

The two roller-chain sprockets of the translational gearing (one at the
platen front, one on the crankshaft) -- modeled identical: 17 teeth
(counted on `v4_transgear_012` crops), ~3/8" chain pitch (scaled from the
sprocket OD), 4.5 mm tooth width, plain 3/8" bore.

The tooth form is SIMPLIFIED: a flaring trapezoid notch per roller (seat
width = roller diameter at the seat radius, opening to a pointed-ish tooth
at the OD) instead of the standard seat-arc + topping-curve profile. Good
enough for the visual/BOM purposes of this model; the chain itself is not
modeled (flexible element, out of scope).

Sprocket math (3/8" pitch, roller 0.200"): PD = p / sin(pi/N) = 51.84 mm,
OD = p (0.6 + cot(pi/N)) = 56.67 mm, seat radius = PD/2 - roller/2.

Layout: axis = Z through the origin, body z = 0..4.5 mm, seed gap on +X.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_chain_sprocket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
)
from _gear import volume_check

PART_NAME = "chain-sprocket"
MATERIAL = "Plain Carbon Steel"  # ch. 23 photos: steel sprockets

TEETH = 17  # DIMENSIONS.md ch23: counted on v4_transgear_012 (low)
CHAIN_PITCH = 0.375 * IN  # 9.525 -- scaled from sprocket OD (low)
ROLLER_DIAMETER = 0.200 * IN  # 5.08 -- standard 3/8" roller chain (low)
FACE_WIDTH = 4.5  # mm -- 3/8" chain inner width budget (low)
BORE_DIAMETER = 0.375 * IN  # 9.525 -- crankshaft stock (low)

PITCH_RADIUS = CHAIN_PITCH / (2.0 * math.sin(math.pi / TEETH))  # 25.92
OUTER_RADIUS = CHAIN_PITCH * (0.6 + 1.0 / math.tan(math.pi / TEETH)) / 2.0  # 28.34
SEAT_RADIUS = PITCH_RADIUS - ROLLER_DIAMETER / 2.0  # 23.38, notch floor
NOTCH_OUTER_MARGIN = 1.2  # NOTCH_OUTER opens this far past the OD
NOTCH_OUTER = OUTER_RADIUS + NOTCH_OUTER_MARGIN  # opens past the OD
SEAT_HALF_WIDTH = ROLLER_DIAMETER / 2.0  # 2.54 at the floor
TIP_HALF_WIDTH = 4.0  # flare at NOTCH_OUTER -> ~2.4 mm pointed tooth tip

# The pitch/outer radii are trig functions of the tooth count, which has no tidy
# SolidWorks-equation form (degrees-vs-radians trap, no sqr()). As in hex-bolt we
# fold the tooth-count trig into DIMENSIONLESS coefficients of the chain pitch, so
# the derived radius globals stay unit-safe pure-arithmetic equations of "ChainPitch".
_PITCH_RADIUS_PER_PITCH = 1.0 / (2.0 * math.sin(math.pi / TEETH))  # PITCH_RADIUS / pitch
_OUTER_RADIUS_PER_PITCH = (0.6 + 1.0 / math.tan(math.pi / TEETH)) / 2.0  # OUTER_RADIUS / pitch


def notch_area_in_disc(step: float = 0.004) -> float:
    """Area (mm^2) of the trapezoid notch inside the blank disc."""
    nx = max(2, round((NOTCH_OUTER - SEAT_RADIUS) / step))
    ny = max(2, round(2.0 * TIP_HALF_WIDTH / step))
    dx = (NOTCH_OUTER - SEAT_RADIUS) / nx
    dy = 2.0 * TIP_HALF_WIDTH / ny
    hits = 0
    for i in range(nx):
        x = SEAT_RADIUS + (i + 0.5) * dx
        half = SEAT_HALF_WIDTH + (TIP_HALF_WIDTH - SEAT_HALF_WIDTH) * (
            (x - SEAT_RADIUS) / (NOTCH_OUTER - SEAT_RADIUS)
        )
        for j in range(ny):
            y = -TIP_HALF_WIDTH + (j + 0.5) * dy
            if abs(y) <= half and math.hypot(x, y) <= OUTER_RADIUS:
                hits += 1
    return hits * dx * dy


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the chain pitch, roller diameter, face
    # width and bore drive everything below. The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in document
    # units (an unsuffixed 9.525 = 9.525 in). The radii are trig of the tooth
    # count, so they are derived globals built from a dimensionless coefficient
    # times "ChainPitch" (unit-safe, no SolidWorks trig). FaceWidth is a feature
    # depth (not a sketch dim), so nothing drives it; it stays an editable knob.
    await set_global(adapter, "ChainPitch", f"{CHAIN_PITCH}mm")
    await set_global(adapter, "RollerDiameter", f"{ROLLER_DIAMETER}mm")
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDiameter", f"{BORE_DIAMETER}mm")
    await set_global(adapter, "PitchRadius", f'"ChainPitch" * {_PITCH_RADIUS_PER_PITCH!r}')
    await set_global(adapter, "OuterRadius", f'"ChainPitch" * {_OUTER_RADIUS_PER_PITCH!r}')
    await set_global(adapter, "SeatRadius", '"PitchRadius" - "RollerDiameter" / 2')
    await set_global(adapter, "NotchOuter", f'"OuterRadius" + {NOTCH_OUTER_MARGIN}mm')
    await set_global(adapter, "SeatHalfWidth", '"RollerDiameter" / 2')
    await set_global(adapter, "TipHalfWidth", f"{TIP_HALF_WIDTH}mm")

    # Each sketch records its dim names + drive equations inline; the deferred
    # drive batch at the end runs once the whole model + a rebuild exists. The
    # tooth pattern between the notch cut and the bore does not perturb the
    # notch's own display dims, so its drive job still resolves afterwards.
    drive_jobs: list[tuple[str, str]] = []

    # Blank disc at the OD. Origin circle: only the diameter is a dim.
    blank = SketchDims()
    check("create_sketch blank", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, OUTER_RADIUS, "sprocket blank", dims=blank,
        names=("BlankCx", "BlankCz", "OuterDia"),
        drives=(None, None, '2 * "OuterRadius"'),
    )
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch blank", await adapter.exit_sketch())
    name_last_feature(adapter, "BlankProfile")
    drive_jobs += blank.apply(adapter, "BlankProfile")
    check(
        "extrude blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=FACE_WIDTH)),
    )
    name_last_feature(adapter, "Blank")
    v_blank = math.pi * OUTER_RADIUS**2 * FACE_WIDTH
    volume = await volume_check(adapter, "blank", v_blank, 0.005 * v_blank)

    # One roller notch on +X (inference off near the OD). The flanks are
    # sloped, so the trapezoid is anchored at the seat corner and spanned
    # with point-pair dims: flank run/flare locate the tip corner, the two
    # vertical edges carry the seat/tip widths.
    notch_dims = SketchDims()
    check("create_sketch notch", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    notch = await add_line_chain(
        adapter,
        [
            (SEAT_RADIUS, -SEAT_HALF_WIDTH),
            (NOTCH_OUTER, -TIP_HALF_WIDTH),
            (NOTCH_OUTER, TIP_HALF_WIDTH),
            (SEAT_RADIUS, SEAT_HALF_WIDTH),
        ],
    )
    set_sketch_direct_db(adapter, False)
    lower_flank, outer_edge, upper_flank, inner_edge = notch
    for edge in (outer_edge, inner_edge):
        check(f"notch vertical {edge}", await adapter.add_sketch_constraint(edge, None, "vertical"))
    # Record each manual dim into SketchDims as it is added (creation = emission
    # order): the seat-corner anchor emits TWO dims (x then z; both nonzero ->
    # general case), then flank run, flank flare, tip width, seat width -- six
    # display dims total. apply() count-asserts this against the feature.
    await anchor_point_to_origin(
        adapter, f"{lower_flank}.start", SEAT_RADIUS, -SEAT_HALF_WIDTH, "seat corner"
    )
    notch_dims.record("SeatCornerX", '"SeatRadius"')
    notch_dims.record("SeatCornerZ", '"SeatHalfWidth"')
    await dimension_between(
        adapter, f"{lower_flank}.start", f"{lower_flank}.end",
        "horizontal_distance", NOTCH_OUTER - SEAT_RADIUS, "flank run",
    )
    notch_dims.record("FlankRun", '"NotchOuter" - "SeatRadius"')
    await dimension_between(
        adapter, f"{lower_flank}.start", f"{lower_flank}.end",
        "vertical_distance", TIP_HALF_WIDTH - SEAT_HALF_WIDTH, "flank flare",
    )
    notch_dims.record("FlankFlare", '"TipHalfWidth" - "SeatHalfWidth"')
    await dimension_between(
        adapter, f"{outer_edge}.start", f"{outer_edge}.end",
        "vertical_distance", 2.0 * TIP_HALF_WIDTH, "tip width",
    )
    notch_dims.record("TipWidth", '2 * "TipHalfWidth"')
    await dimension_between(
        adapter, f"{inner_edge}.start", f"{inner_edge}.end",
        "vertical_distance", 2.0 * SEAT_HALF_WIDTH, "seat width",
    )
    notch_dims.record("SeatWidth", '2 * "SeatHalfWidth"')
    await ensure_fully_defined(adapter, "notch sketch")
    check("exit_sketch notch", await adapter.exit_sketch())
    name_last_feature(adapter, "NotchProfile")
    drive_jobs += notch_dims.apply(adapter, "NotchProfile")
    notch_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=FACE_WIDTH + 1.0)
    )
    check("cut roller notch", notch_cut)
    # Rename the seed cut and pattern THAT name -- the circular pattern selects
    # the seed feature by name, so the rename and the pattern reference must use
    # the same string (notch_cut.data.name still holds the pre-rename name).
    roller_notch = name_last_feature(adapter, "RollerNotch")

    from _gear import pattern_about_z

    await pattern_about_z(
        adapter, roller_notch, TEETH, OUTER_RADIUS, FACE_WIDTH / 2.0
    )
    v_teeth = v_blank - TEETH * notch_area_in_disc() * FACE_WIDTH
    volume = await volume_check(adapter, "toothed sprocket", v_teeth, 0.01 * v_teeth)

    # Bore. Origin circle: only the diameter is a dim.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIAMETER / 2.0, "bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDiameter"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * (BORE_DIAMETER / 2.0) ** 2 * FACE_WIDTH
    v_final = volume - v_bore
    await volume_check(adapter, "bore", v_final, 0.01 * v_bore)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven sprocket (equations neutral)", v_final, 0.01 * v_bore)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
