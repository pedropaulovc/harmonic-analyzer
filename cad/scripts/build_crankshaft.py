r"""Reproduction script: crankshaft (book ch. 11, pp. 12-15).

Stepped steel shaft in the green v2 post bearing at the base corner:
an integral Ø11.388 journal runs over local stations 26.623905572..99.035905572,
while the crank arm on the outboard end (affixed by a removable tapered
pin so the crankshaft gear can be changed), chain sprocket and the 4:1
drive pinion retain their existing 3/8-in seats. Modeled with the
tapered-pin cross-hole; the crank arm/pin/handle and the gears are separate parts
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
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import (
    NUMBER_DRILL_MM,
    HoleSpec,
    cross_hole_volume_mm3,
    wizard_hole_on_cylinder,
)
from crankshaft_spec import (
    CRANK_END_NOTE,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    JOURNAL_DIA,
    JOURNAL_LENGTH,
    JOURNAL_START,
    PIN_HOLE_HEIGHT,
    SHAFT_DIA,
    SHAFT_LENGTH,
)

PART_NAME = "crankshaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# SHAFT_DIA / SHAFT_LENGTH / PIN_HOLE_HEIGHT live in crankshaft_spec (the
# COM-free contract the drawing shares). Provenance: dia is the ch11 legacy
# ShaftDiameter (uncontradicted); length was rederived with the ch30 GT re-read
# (2026-07-02): the crank plane moved south (arm hub at machine z -175..-167,
# T12 at -157.5, pedestal slab at -145..-125) while the inboard 16T station
# stayed, so the shaft spans -175..-30. The arm/handle sweep entirely in front
# of the chain plane and cannot foul the chain when turning (book ch30
# p005/p002). Pin cross-hole: #9 drill (Ø4.978, wizard) through local X at
# station 4.0, coaxial with the crank arm's local-Y pilot after the arm's
# assembly transform.  Both land at the arm mid-plane and are taper-reamed
# together for MHA-024.
# Keyed-chain seat stations (local +Y from the outboard origin): named datum
# planes the T12 chain wheel and the 16T pinion mate COINCIDENT to in the
# assembly (the frame CboreSeat idiom). Coincident replaces the old unsigned
# plane-plane DISTANCE seats, whose two solution branches let the free-
# spinning crank family reflect about the shaft origin on a re-solve (the
# 16T rendered floating 200 mm south -- render-gate catch, 2026-07-04). The
# arm seats at SEAT_ARM. build_drive_train asserts these match its
# REMOVABLE_Z0 / PINION_TOOTH_Z / arm-placement derivations.
SEAT_T12 = 17.5
SEAT_PINION = 105.039505572
# = -31.0252033243 - 10.8/2 - (-175): rear-shifted 16T centred on the 64T row.
SEAT_ARM = 8.0  # the arm's ORIGIN plane. The arm's placed pose composes a
# Ry(180), which keeps its 8-thick plate at station 0..8 but puts the
# AS-BUILT origin at the plate's NORTH face (station 8, machine -167): the
# plate extrudes machine -z from the origin. Seating the
# origin at station 0 instead hung the plate at -183..-175 and buried the
# handle collar in the arm's square end (502 mm^3 -- interference-gate catch
# 2026-07-05).


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the shaft diameter/length and the
    # cross-hole diameter/height. The mm suffix is load-bearing -- this is an
    # INCH document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 120 = 120 in, blowing the part up 25.4x). SHAFT_DIA is
    # already mm (0.375 * IN), so it serialises as its mm value.
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")
    await set_global(adapter, "JournalDia", f"{JOURNAL_DIA}mm")
    await set_global(adapter, "JournalStart", f"{JOURNAL_START}mm")
    await set_global(adapter, "JournalLength", f"{JOURNAL_LENGTH}mm")
    # PinHoleHeight is deliberately the COM-free spec constant used below.
    # On the local-X radial point, assigning the same 4 mm value through a
    # 3D-sketch equation built the hole but made ForceRebuild3 fail on both
    # +X and -X probes (2026-07-22).  The released drawing owns the native
    # associative end-face-to-axis dimension; no unstable equation is saved.

    drive_jobs: list[tuple[str, str]] = []

    # Shaft: on-axis circle (centre at the origin), so define_circle emits only
    # the diameter dim -- the two centre slots are ignored.
    shaft = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SHAFT_DIA / 2.0,
        "shaft circle",
        dims=shaft,
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
    depth_dim = name_dimensions(adapter, "Shaft", ["Depth"])
    drive_jobs += [(depth_dim[0], '"ShaftLength"')]
    v_shaft = math.pi * (SHAFT_DIA / 2.0) ** 2 * SHAFT_LENGTH
    await volume_check(adapter, "shaft", v_shaft, 0.005 * v_shaft)

    # Integral v2-post bearing journal.  An offset reference plane exposes the
    # start station as a markable manufacturing dimension; the journal then
    # extrudes exactly across the boss span and merges into the 3/8-in core.
    check(
        "create_plane JournalStartPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=JOURNAL_START
            )
        ),
    )
    name_last_feature(adapter, "JournalStartPlane")
    start_dim = name_dimensions(adapter, "JournalStartPlane", ["JournalStart"])
    drive_jobs += [(start_dim[0], '"JournalStart"')]

    journal = SketchDims()
    check(
        "create_sketch bearing journal",
        await adapter.create_sketch("JournalStartPlane"),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        JOURNAL_DIA / 2.0,
        "bearing journal circle",
        dims=journal,
        names=("JournalCx", "JournalCz", "JournalDiaDim"),
        drives=(None, None, '"JournalDia"'),
    )
    await ensure_fully_defined(adapter, "bearing journal sketch")
    check("exit_sketch bearing journal", await adapter.exit_sketch())
    name_last_feature(adapter, "JournalProfile")
    drive_jobs += journal.apply(adapter, "JournalProfile")
    check(
        "extrude bearing journal",
        await adapter.create_extrusion(ExtrusionParameters(depth=JOURNAL_LENGTH)),
    )
    name_last_feature(adapter, "Journal")
    journal_depth_dim = name_dimensions(adapter, "Journal", ["JournalLength"])
    drive_jobs += [(journal_depth_dim[0], '"JournalLength"')]
    v_with_journal = (
        v_shaft
        + math.pi * ((JOURNAL_DIA / 2.0) ** 2 - (SHAFT_DIA / 2.0) ** 2) * JOURNAL_LENGTH
    )
    await volume_check(
        adapter,
        "shaft + bearing journal",
        v_with_journal,
        0.005 * v_with_journal,
    )

    # Tapered-pin cross-hole through the crank seat: a native Hole Wizard #9
    # drill placed RADIALLY on the shaft's cylindrical face (3D-sketch
    # placement; no planar face carries the drill axis). The placement point
    # sits on the surface at the crank-seat height, -X side; through-all
    # drills diametrally out the +X wall.  The circle's parameter seam lies
    # on +X and rejects the otherwise-neutral station equation on rebuild;
    # -X defines the identical finished bore axis away from that seam.
    # ROT_X_POS90 preserves local X as machine X, matching the arm pilot.
    drive_jobs += wizard_hole_on_cylinder(
        adapter,
        HoleSpec("drilled_number", "#9"),
        [-SHAFT_DIA / 2.0, PIN_HOLE_HEIGHT, 0.0],
        "tapered-pin cross-hole (#9)",
        name="PinHole",
    )
    # Cross-drill removal = the perpendicular cylinder-cylinder intersection,
    # integrated numerically (probe-exact; replaces the old ~178 as-built
    # constant for the retired Ø5.0).
    v_pin = cross_hole_volume_mm3(NUMBER_DRILL_MM["#9"], SHAFT_DIA)
    v_final = v_with_journal - v_pin
    await volume_check(adapter, "shaft + pin hole", v_final, 0.02 * v_pin)

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
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset",
                    base_plane="Top Plane",
                    offset=station,
                )
            ),
        )
        name_last_feature(adapter, seat_name)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Crank End Note": CRANK_END_NOTE,
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
