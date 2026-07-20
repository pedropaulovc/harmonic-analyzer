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
tapered-pin cross-hole along Z at the crank-seat height.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crankshaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    POLISHED_STEEL,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from crank_arm_spec import HUB_DIA
from crank_pin_spec import PIN_SEAT_PROUD, hole_dia_at

PART_NAME = "crankshaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_DIA = 0.375 * IN  # ch11: legacy ShaftDiameter, uncontradicted
# Domed south end cap (ch11 page002_img04: the polished dome proud of the arm
# face at the sprocket centre -- the hero shot's "oval boss").
DOME_DIA = 12.0
DOME_H = 2.5
DOME_R = 2.4  # rim fillet -> the dome read
SHAFT_LENGTH = 145.0  # ch11: derived (crank seat + pedestal bearing + seats);
# lengthened again with the ch30 GT re-read (2026-07-02): the crank plane moved
# south (arm hub at machine z -175..-167, T12 at -157.5, pedestal slab at
# -145..-125) while the inboard 16T station stayed, so the shaft spans
# -175..-30. The arm/handle sweep entirely in front of the chain plane and
# cannot foul the chain when turning (book ch30 p005/p002).
# pin cross-hole: was a straight #9 pilot; now the AS-REAMED 1:48 cone
# matching crank_pin_spec (a taper pin cannot seat in a straight pilot
# without solid interference), radial at the crank-seat height.
PIN_HOLE_HEIGHT = 12.0  # crank hub centre above the outboard end
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


def _dome_fillet_volume(body_r: float, r: float) -> float:
    """Removed volume of a radius-r fillet on a body_r cylinder's end rim
    (Pappus over the corner cross-section; the cone-lock-knob idiom)."""
    area = r * r * (1.0 - math.pi / 4.0)
    sq = r * r * (r / 2.0)
    disc = (math.pi * r * r / 4.0) * (r - 4.0 * r / (3.0 * math.pi))
    x_bar = (sq - disc) / area
    return 2.0 * math.pi * (body_r - x_bar) * area


def _x_strip_area(r: float, b: float) -> float:
    """Area of a radius-r disc (centred x=0) restricted to ``|x| <= b``."""
    b = min(b, r)
    if b <= 0.0:
        return 0.0
    return 2.0 * (b * math.sqrt(r * r - b * b) + r * r * math.asin(b / r))


def _pin_cone_removal_mm3(big_end_reach_mm: float) -> float:
    """Removed volume of the 1:48 as-reamed pin cone through the shaft.

    Simpson integration along the hole axis (shaft-local X): each slice of
    the Y-axis shaft cylinder is the strip ``|z| <= sqrt(R^2 - x^2)``; the
    hole slice is the ``hole_dia_at`` cone disc centred on z=0.
    ``big_end_reach_mm`` is the pin big-end face's distance outboard of the
    shaft axis (arm hub radius + PIN_SEAT_PROUD).
    """
    shaft_r = SHAFT_DIA / 2.0
    n = 200
    h = 2.0 * shaft_r / n
    total = 0.0
    for i in range(n + 1):
        x = -shaft_r + i * h
        rh = hole_dia_at(big_end_reach_mm + x) / 2.0
        w_band = max(0.0, shaft_r * shaft_r - x * x) ** 0.5
        area = _x_strip_area(rh, w_band)
        w = 1.0 if i in (0, n) else (4.0 if i % 2 else 2.0)
        total += w * area
    return total * h / 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the shaft diameter/length and the
    # cross-hole diameter/height. The mm suffix is load-bearing -- this is an
    # INCH document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 120 = 120 in, blowing the part up 25.4x). SHAFT_DIA is
    # already mm (0.375 * IN), so it serialises as its mm value.
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")
    await set_global(adapter, "PinHoleHeight", f"{PIN_HOLE_HEIGHT}mm")
    await set_global(adapter, "DomeDia", f"{DOME_DIA}mm")
    # (The old PinHoleDia/PinHoleHeight knobs are gone: the cross-hole is a
    # native Hole Wizard #9 feature; its size comes from the drill table and
    # its station is baked into the placement point.)

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

    # Domed south end cap (ch11 page002_img04): a Ø12 disc proud of the
    # outboard end (local -Y), rim-filleted near-full-radius so it reads as
    # the polished dome at the arm face. Merged with the shaft; its north
    # annulus lands ON the arm's south face plane (face contact, no overlap).
    dome = SketchDims()
    check("create_sketch dome", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, DOME_DIA / 2.0, "dome disc", dims=dome,
        names=("DomeCx", "DomeCz", "DomeDia"),
        drives=(None, None, '"DomeDia"'),
    )
    await ensure_fully_defined(adapter, "dome sketch")
    check("exit_sketch dome", await adapter.exit_sketch())
    name_last_feature(adapter, "DomeProfile")
    drive_jobs += dome.apply(adapter, "DomeProfile")
    extrude_at_offset(adapter, DOME_H, 0.0, flip=True)
    name_last_feature(adapter, "DomeDisc")
    v_expect = v_shaft + math.pi * (DOME_DIA / 2.0) ** 2 * DOME_H
    v_expect = await volume_check(adapter, "dome disc", v_expect, 1.0)
    check(
        "fillet dome rim",
        await adapter.add_fillet(DOME_R, [[DOME_DIA / 2.0, -DOME_H, 0.0]]),
    )
    name_last_feature(adapter, "DomeCrown")
    v_expect -= _dome_fillet_volume(DOME_DIA / 2.0, DOME_R)
    v_expect = await volume_check(adapter, "dome crown", v_expect, 1.5)

    # Tapered-pin cross-hole, AS-REAMED (matches build_crank_arm's hub cone:
    # same 1:48 cone, same machine station -- PIN_HOLE_HEIGHT 12 = the arm's
    # PIN_HOLE_Z). Revolve-cut about the hole axis (local X at the crank-seat
    # height; FeatureCut4's draft flag is hardcoded off in the adapter, so a
    # draft-extrude cannot make this cone). The big end faces local -X, which
    # the assembly maps outboard together with the arm's +Y entry side.
    big_end_reach = HUB_DIA / 2.0 + PIN_SEAT_PROUD  # 12.5 off the shaft axis
    shaft_r = SHAFT_DIA / 2.0
    r_entry = hole_dia_at(big_end_reach - shaft_r) / 2.0
    r_exit = hole_dia_at(big_end_reach + shaft_r) / 2.0
    check("create_sketch pin hole", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    pin_axis_line = check(
        "add_centerline pin-hole axis",
        await adapter.add_centerline(
            -shaft_r, PIN_HOLE_HEIGHT, shaft_r, PIN_HOLE_HEIGHT
        ),
    )
    pin_lines = await add_line_chain(
        adapter,
        [
            (-shaft_r, PIN_HOLE_HEIGHT),
            (-shaft_r, PIN_HOLE_HEIGHT + r_entry),
            (shaft_r, PIN_HOLE_HEIGHT + r_exit),
            (shaft_r, PIN_HOLE_HEIGHT),
        ],
    )
    set_sketch_direct_db(adapter, False)
    entry_line, _taper, exit_line, _closure = pin_lines
    check(
        "axis horizontal",
        await adapter.add_sketch_constraint(pin_axis_line, None, "horizontal"),
    )
    for label, ent in (("entry", entry_line), ("exit", exit_line)):
        check(
            f"{label} vertical",
            await adapter.add_sketch_constraint(ent, None, "vertical"),
        )
    check(
        "axis length",
        await adapter.add_sketch_dimension(pin_axis_line, None, "linear", SHAFT_DIA),
    )
    check(
        "entry radius",
        await adapter.add_sketch_dimension(entry_line, None, "linear", r_entry),
    )
    check(
        "exit radius",
        await adapter.add_sketch_dimension(exit_line, None, "linear", r_exit),
    )
    check(
        "axis station",
        await adapter.add_sketch_dimension(
            f"{pin_axis_line}.start", "origin", "vertical_distance", PIN_HOLE_HEIGHT
        ),
    )
    check(
        "axis reach",
        await adapter.add_sketch_dimension(
            f"{pin_axis_line}.start", "origin", "horizontal_distance", shaft_r
        ),
    )
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    check(
        "revolve-cut pin cone",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "PinHole")
    v_final = v_expect - _pin_cone_removal_mm3(big_end_reach)
    await volume_check(adapter, "shaft + pin cone", v_final, 3.0)

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
    # The ch11 close-ups show the shaft and its domed end cap bright-polished;
    # the bare carbon-steel appearance renders the dome face near-black.
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
