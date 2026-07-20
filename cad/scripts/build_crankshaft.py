r"""Reproduction script: crankshaft (book ch. 11, pp. 12-15).

Short Ø3/8 in steel shaft in the green pedestal bearing at the base
corner: crank arm on the outboard end (affixed by a removable tapered
pin so the crankshaft gear can be changed), chain sprocket and the 4:1
drive pinion inboard. Modeled as the plain shaft with the tapered-pin
cross-hole; the crank arm/pin/handle and the gears are separate parts
(`build_crank_arm.py` etc., gears in M4).

Dimensions: cad/DIMENSIONS.md "Chapter 11" - dia legacy (med), length
derived from eight-views 8/8 pedestal proportions (low).

Layout: shaft axis along +Y, outboard (crank) end at the origin;
tapered-pin cross-hole along X at the rear-hub station.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crankshaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    POLISHED_STEEL,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _holes import HoleSpec, cross_hole_volume_mm3, wizard_hole_on_cylinder
from crank_arm_spec import PIN_BORE_DIA, PIN_STATION_FROM_OUTBOARD_FACE

PART_NAME = "crankshaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_DIA = 0.375 * IN  # ch11: legacy ShaftDiameter, uncontradicted
SHAFT_LENGTH = 145.0  # ch11: derived (crank seat + pedestal bearing + seats);
# lengthened again with the ch30 GT re-read (2026-07-02): the crank plane moved
# south (arm hub at machine z -175..-167, T12 at -157.5, pedestal slab at
# -145..-125) while the inboard 16T station stayed, so the shaft spans
# -175..-30. The arm/handle sweep entirely in front of the chain plane and
# cannot foul the chain when turning (book ch30 p005/p002).
# The radial pin crosses the arm plate at its midplane, machine z=-171 in the
# assembly, safely outboard of the chain plates that begin at z=-158.35.
PIN_HOLE_HEIGHT = PIN_STATION_FROM_OUTBOARD_FACE
# Keyed-chain seat stations (local +Y from the outboard origin): named datum
# planes the T12 chain wheel and the 16T pinion mate COINCIDENT to in the
# assembly (the frame CboreSeat idiom). Coincident replaces the old unsigned
# plane-plane DISTANCE seats, whose two solution branches let the free-
# spinning crank family reflect about the shaft origin on a re-solve (the
# 16T rendered floating 200 mm south -- render-gate catch, 2026-07-04). The
# arm seats at SEAT_ARM. build_drive_train asserts these match its
# REMOVABLE_Z0 / PINION_TOOTH_Z / arm-placement derivations.
SEAT_T12 = 17.5
SEAT_PINION = 100.7  # |PINION_TOOTH_Z - FACE/2 - CRANKSHAFT_Z0|
# (2026-07-14 crank-mesh rederive: the pinion stands proud of the pivot
# post's casting face, centred in the TRUE casting-to-T120 span -- ch12
# page002_img06, no relief pocket -- at the engaged-c2c Y_CRANK 142.985;
# = |-68.90 - 10.8/2 - (-175)|)
SEAT_ARM = 8.0  # the arm's ORIGIN plane. The arm's placed pose composes a
# Ry(180), which keeps its 8-thick plate at station 0..8 but puts the
# AS-BUILT origin at the plate's NORTH face (station 8, machine -167): the
# plate extrudes machine -z from the origin. Seating the
# origin at station 0 instead hung the plate at -183..-175 and buried the
# handle collar in the arm's square end (502 mm^3 -- interference-gate catch
# 2026-07-05).


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the shaft diameter/length and the
    # cross-hole diameter/height. The mm suffix is load-bearing -- this is an
    # INCH document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 120 = 120 in, blowing the part up 25.4x). SHAFT_DIA is
    # already mm (0.375 * IN), so it serialises as its mm value.
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")
    await set_global(adapter, "PinBoreDia", f"{PIN_BORE_DIA}mm")
    await set_global(adapter, "PinHoleHeight", f"{PIN_HOLE_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Shaft: on-axis circle (centre at the origin), so define_circle emits only
    # the diameter dim -- the two centre slots are ignored.
    shaft = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, SHAFT_DIA / 2.0, "shaft circle", dims=shaft,
        names=("ShaftCx", "ShaftCz", "ShaftDiaDim"),
        drives=(None, None, '"ShaftDia"'),
    )
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += shaft.apply(adapter, "ShaftProfile")
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LENGTH)),
    )
    name_last_feature(adapter, "Shaft")
    v_shaft = math.pi * (SHAFT_DIA / 2.0) ** 2 * SHAFT_LENGTH
    await volume_check(adapter, "shaft", v_shaft, 0.005 * v_shaft)

    # Assembly-ream envelope, authored on the Right plane so the hole axis is
    # local X.  ROT_X_POS90 maps local X to machine X, collinear with the arm's
    # rear-hub hole; the former local-Z wizard hole mapped to machine -Y and
    # could never accept the pin.
    drive_jobs += wizard_hole_on_cylinder(
        adapter,
        HoleSpec("drilled_number", "#9"),
        [SHAFT_DIA / 2.0, PIN_HOLE_HEIGHT, 0.0],
        "shaft taper-pin pilot (#9)",
        name="PinPilot",
        y_dim=("PinPilotHeight", '"PinHoleHeight"'),
    )
    pin_hole = SketchDims()
    check("create_sketch shaft pin hole", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        0.0,
        PIN_HOLE_HEIGHT,
        PIN_BORE_DIA / 2.0,
        "shaft pin hole",
        dims=pin_hole,
        names=("PinHoleZ", "PinHoleHeight", "PinHoleDia"),
        drives=(None, '"PinHoleHeight"', '"PinBoreDia"'),
    )
    await ensure_fully_defined(adapter, "shaft pin-hole sketch")
    check("exit_sketch shaft pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_hole.apply(adapter, "PinHoleProfile")
    check(
        "cut shaft pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SHAFT_DIA + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    # Cross-drill removal = the perpendicular cylinder-cylinder intersection,
    # integrated numerically (probe-exact; replaces the old ~178 as-built
    # constant for the retired Ø5.0).
    v_pin = cross_hole_volume_mm3(PIN_BORE_DIA, SHAFT_DIA)
    measured = await adapter.get_mass_properties()
    if not measured.is_success:
        raise RuntimeError(f"crankshaft mass properties failed: {measured.error}")
    v_final = float(measured.data.volume)
    actual_removal = v_shaft - v_final
    if abs(actual_removal - v_pin) > 0.10 * v_pin:
        raise RuntimeError(
            "shaft pin-hole removal differs from its analytic envelope: "
            f"{actual_removal:.1f} mm^3 vs {v_pin:.1f} mm^3"
        )
    await volume_check(adapter, "shaft + pilot/ream envelope", v_final, 0.5)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven crankshaft (equations neutral)", v_final, 50.0)

    # Named central axis (shaft axis = local +Y through the origin) so the
    # crankshaft mates concentric in the pedestal and the crank parts /
    # pinion / chain wheel lock to it (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    # Keyed-chain SEAT DATUMS (see the constants block): the T12 wheel, the
    # 16T pinion and the crank arm mate their origin planes COINCIDENT to
    # these in the assembly -- flip-free, unlike an unsigned plane-plane
    # distance.
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    for seat_name, station in (
        ("SeatT12", SEAT_T12),
        ("SeatPinion", SEAT_PINION),
        ("SeatArm", SEAT_ARM),
    ):
        check(
            f"create_plane {seat_name} (Top Plane, +{station:.3f})",
            await adapter.create_plane(CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=station,
            )),
        )
        name_last_feature(adapter, seat_name)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
