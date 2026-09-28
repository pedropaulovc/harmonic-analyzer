r"""Reproduction script: crankshaft (book ch. 11, pp. 12-15; ch. 12 p. 19).

Stepped steel shaft in the green v2 post bearing at the base corner:
an integral Ø11.388 journal runs over local stations 32.755105572..104.789505572,
while the crank arm on the outboard end (affixed by a removable tapered
pin so the crankshaft gear can be changed), chain sprocket and the 4:1
drive pinion retain their existing 3/8-in seats. Modeled with the
tapered-pin cross-hole and, near the far end, the 1/8 in straight-pin
cross-hole that keys the 16T pinion's hub boss to the shaft (ch12 p.19
page002_img02: the pin head on the boss; crank_pinion_spec owns the pin);
the crank arm/pin/handle and the gears are separate parts
(`build_crank_arm.py` etc., gears in M4).

Dimensions: cad/DIMENSIONS.md "Chapter 11" - dia legacy (med), length
derived from eight-views 8/8 pedestal proportions (low).

Layout: shaft axis along +Y, outboard (crank) end at the origin;
tapered-pin cross-hole along Z at the crank-seat height; pinion-pin
cross-hole at SEAT_PINION + the pinion's PIN_STATION, its entry point
turned PIN_CLOCKING_DEG from -X toward -Z about the shaft axis so it meets
the pinion's own -X hole once the assembly seats the pinion rot_z(-seed).
Run (SolidWorks already open)::

    uv run python cad\scripts\build_crankshaft.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    SketchDims,
    _early_bound,
    _feature_by_name,
    _read_member,
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
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _hole_spec import blind_cut_dia_mm
from _holes import cross_hole_volume_mm3, wizard_hole_on_cylinder
from _part_pmi import author_part_pmi
from crank_pinion_spec import (
    CRANKSHAFT_PIN_HOLE_PROCESS,
    PIN_CLOCKING_DEG as PINION_PIN_CLOCKING_DEG,
    PIN_DIA as PINION_PIN_DIA,
    PIN_HOLE_SPEC as PINION_PIN_HOLE_SPEC,
    PIN_STATION as PINION_PIN_STATION,
)
from crankshaft_spec import (
    CRANK_END_NOTE,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    JOURNAL_DIA_BAND,
    END_VIEW_NOTE,
    JOURNAL_DIA,
    JOURNAL_LENGTH,
    JOURNAL_START,
    PIN_HOLE_SPEC,
    PIN_HOLE_HEIGHT,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)

PART_NAME = "crankshaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# SHAFT_DIA / SHAFT_LENGTH / PIN_HOLE_HEIGHT live in crankshaft_spec (the
# COM-free contract the drawing shares). Provenance: dia is the ch11 legacy
# ShaftDiameter (uncontradicted); length was rederived with the ch30 GT re-read
# (2026-07-02): the crank plane moved south (arm hub at machine z -175..-167,
# T12 at -157.5, pedestal slab at -145..-125) while the inboard 16T station
# stayed, so the shaft spans -175..-53 (2026-09: shortened to end 6.2 past
# the 16T's north face, ch12 page002_img02). The arm/handle sweep entirely in front
# of the chain plane and cannot foul the chain when turning (book ch30
# p005/p002). The number-drilled pin cross-hole passes through local X at station
# 4.0, coaxial with the crank arm's local-Y pilot after the arm's assembly
# transform. Both are taper-reamed together for MHA-024.
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
# The pinion's retention-pin cross-hole station: the pinion's own PIN_STATION
# (from its toothed south face) measured from the SeatPinion datum that face
# sits on. Machine z = CRANKSHAFT_Z0 + this. The recess of the shaft end inside
# the pinion's boss (build_drive_train_assembly asserts it) is
# SEAT_PINION + OVERALL_LENGTH - SHAFT_LENGTH.
PINION_PIN_STATION_Y = SEAT_PINION + PINION_PIN_STATION  # 119.0795
if PINION_PIN_STATION_Y + PINION_PIN_DIA / 2.0 > SHAFT_LENGTH - 1.0:
    raise AssertionError("pinion pin hole runs out the crankshaft's north end")


def _plane_normal(adapter, name: str) -> tuple[float, float, float]:
    """A reference plane's unit normal in model coordinates, read back from
    ``IRefPlane::Transform`` (the transform that takes the canonical Front-
    aligned plane to the actual one; its third rotation row is the normal)."""
    feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
    plane = _early_bound(feature.GetSpecificFeature2(), "IRefPlane")
    data = [
        float(v) for v in _read_member(_read_member(plane, "Transform"), "ArrayData")
    ]
    return (data[6], data[7], data[8])


def _delete_feature(adapter, name: str, kind: str) -> None:
    """Select a feature by name and delete it (blank_sketch's Select2 recipe
    plus ``DeleteSelection2``, the channel assembly's delete path)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name, kind, 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {name!r} for deletion")
    if not model.Extension.DeleteSelection2(0):
        raise RuntimeError(f"DeleteSelection2 refused {name!r}")
    model.ClearSelection2(True)


async def _angled_plane_containing(
    adapter,
    name: str,
    *,
    base_plane: str,
    pivot_axis: str,
    angle_deg: float,
    direction: tuple[float, float, float],
) -> None:
    """Build the angled plane through ``pivot_axis`` that CONTAINS ``direction``.

    ``InsertRefPlane`` has two angled solutions per magnitude and the adapter
    exposes the choice as the angle's sign, whose meaning nothing documents.
    The first attempt uses ``+angle_deg``; the plane normal is read back and if
    ``direction`` does not lie in the plane the attempt is deleted and the
    mirror (``-angle_deg``) built, then proven the same way.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    for attempt, signed in enumerate((angle_deg, -angle_deg)):
        check(
            f"create_plane {name} ({signed:+.4f} deg about {pivot_axis})",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="angle",
                    base_plane=base_plane,
                    angle=signed,
                    pivot_axis=pivot_axis,
                )
            ),
        )
        name_last_feature(adapter, name)
        normal = _plane_normal(adapter, name)
        off_plane = abs(sum(n * d for n, d in zip(normal, direction, strict=True)))
        _telemetry.info(
            f"{name}: attempt {attempt + 1} normal {normal}, |n.d| = {off_plane:.3e}"
        )
        if off_plane < 1e-6:
            return
        _delete_feature(adapter, name, "PLANE")
    raise RuntimeError(f"{name}: neither angled-plane solution contains {direction}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): shaft and journal dimensions. The
    # mm suffix is load-bearing -- this is an
    # INCH document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 120 = 120 in, blowing the part up 25.4x). SHAFT_DIA is
    # already mm (0.375 * IN), so it serialises as its mm value.
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")
    await set_global(adapter, "JournalDia", f"{JOURNAL_DIA}mm")
    await set_global(adapter, "JournalStart", f"{JOURNAL_START}mm")
    await set_global(adapter, "JournalLength", f"{JOURNAL_LENGTH}mm")
    # The cross-hole station plane remains an editable equation below.
    await set_global(adapter, "PinHoleHeight", f"{PIN_HOLE_HEIGHT}mm")
    await set_global(adapter, "PinionPinStation", f"{PINION_PIN_STATION_Y}mm")

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

    check(
        "create_plane PinHoleStationPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=PIN_HOLE_HEIGHT
            )
        ),
    )
    name_last_feature(adapter, "PinHoleStationPlane")
    pin_station_dim = name_dimensions(
        adapter, "PinHoleStationPlane", ["PinHoleHeight"]
    )
    drive_jobs += [(pin_station_dim[0], '"PinHoleHeight"')]

    # Tapered-pin cross-hole through the crank seat, drilled radially on the
    # shaft's -X side, away from the +X seam.
    # Exact host-face selection keeps the hole on the intended Ø9.525 crank
    # seat. Coincidence to the driven station plane and Front Plane constrains
    # only axial station and clocking; the radial coordinate follows ShaftDia.
    pin_hole_dia = blind_cut_dia_mm(PIN_HOLE_SPEC)
    wizard_hole_on_cylinder(
        adapter,
        PIN_HOLE_SPEC,
        [-SHAFT_DIA / 2.0, PIN_HOLE_HEIGHT, 0.0],
        "tapered-pin cross-hole",
        name="PinHole",
        point_planes=("PinHoleStationPlane", "Front Plane"),
    )
    # Cross-drill removal = the perpendicular cylinder-cylinder intersection,
    # integrated numerically (probe-exact; replaces the old ~178 as-built
    # constant for the retired Ø5.0).
    v_pin = cross_hole_volume_mm3(pin_hole_dia, SHAFT_DIA)
    v_final = v_with_journal - v_pin
    await volume_check(adapter, "shaft + pin hole", v_final, 0.02 * v_pin)

    # Named central axis (shaft axis = local +Y through the origin) so the
    # crankshaft mates concentric in the pedestal and the crank parts /
    # pinion / chain wheel lock to it (M6 mated-DOF drive train). Created
    # BEFORE the pinion-pin hole because that hole's clocking plane pivots on
    # it; the hole adds no axis of its own, so it stays Axis1.
    shaft_axis = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shaft axis"
    )

    # Pinion retention-pin cross-hole (ch12 p.19; crank_pinion_spec owns the
    # pin): the 1/8 in drill through the pinion seat at the pinion's boss
    # mid-length, match-drilled at assembly with the pinion on its seat -- so
    # this print's callout says MATCH DRILL WITH THE PINION and the hole is
    # modelled here only so the assembly is the truth and the shaft's drawing
    # can show it. Its entry point is turned PIN_CLOCKING_DEG from -X toward
    # -Z about the shaft axis: the assembly seats the pinion rot_z(-seed) with
    # its own hole on its local -X, and this shaft is placed ROT_X_POS90
    # (local z = machine -y), so the pinion's machine (-cos s, +sin s, 0)
    # hole axis is local (-cos s, 0, -sin s). The clocking plane is the Front
    # plane turned about the shaft axis; SolidWorks has two angled planes for
    # one angle, so the normal is READ BACK and the hole goes in only once the
    # plane provably contains the entry direction (the other solution is
    # deleted and the mirror built instead).
    check(
        "create_plane PinionPinStationPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=PINION_PIN_STATION_Y
            )
        ),
    )
    name_last_feature(adapter, "PinionPinStationPlane")
    pinion_station_dim = name_dimensions(
        adapter, "PinionPinStationPlane", ["PinionPinStation"]
    )
    drive_jobs += [(pinion_station_dim[0], '"PinionPinStation"')]
    clocking = math.radians(PINION_PIN_CLOCKING_DEG)
    entry_dir = (-math.cos(clocking), 0.0, -math.sin(clocking))
    await _angled_plane_containing(
        adapter,
        "PinionPinClockingPlane",
        base_plane="Front Plane",
        pivot_axis=shaft_axis,
        angle_deg=PINION_PIN_CLOCKING_DEG,
        direction=entry_dir,
    )
    wizard_hole_on_cylinder(
        adapter,
        PINION_PIN_HOLE_SPEC,
        [
            SHAFT_DIA / 2.0 * entry_dir[0],
            PINION_PIN_STATION_Y,
            SHAFT_DIA / 2.0 * entry_dir[2],
        ],
        "pinion retention-pin cross-hole",
        name="PinionPinHole",
        point_planes=("PinionPinStationPlane", "PinionPinClockingPlane"),
    )
    v_pinion_pin = cross_hole_volume_mm3(PINION_PIN_DIA, SHAFT_DIA)
    v_final -= v_pinion_pin
    await volume_check(adapter, "shaft + pinion pin hole", v_final, 0.02 * v_pinion_pin)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "ShaftProfile", "ShaftDiaDim", *deviations(SHAFT_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "JournalProfile",
        "JournalDiaDim",
        *deviations(JOURNAL_DIA_BAND),
    )
    await volume_check(adapter, "driven crankshaft (equations neutral)", v_final, 50.0)

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
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    # "Pinion Pin Hole Process" is the PinionPinHole callout prefix the
    # crankshaft's sheet must print (crank_pinion_spec owns the wording so the
    # two prints of one matched fit can never disagree); the drawing reads it
    # off the part like the other note rows.
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Crank End Note": CRANK_END_NOTE,
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Pinion Pin Hole Process": CRANKSHAFT_PIN_HOLE_PROCESS,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
