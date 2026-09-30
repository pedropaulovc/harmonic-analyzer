r"""Build crankshaft MHA-026 with the photographed integral domed nose.

The cylindrical shaft starts at local y=0, the common outboard plane where
MHA-020 and through hub MHA-137 finish flush.  Only the shaft's same-diameter
spherical dome projects outboard (negative Y), so the crank can still withdraw
through the hub bore after removable taper pin MHA-024 is removed.  The shared
8-mm face shift preserves the established bearing interfaces.  Behind the
hub, an integral collar's front spigot seats the removable sprocket MHA-081,
driven by two MHA-173 dowels pressed into blind reamed holes in its face
(ch. 23; crankshaft_spec owns the seat).  Near
the far end, the 1/8 in
straight-pin cross-hole keys the 16T pinion's hub boss to the shaft (ch12
p.19 page002_img02; crank_pinion_spec owns the pin), its entry turned
PIN_CLOCKING_DEG from -X toward -Z about the shaft axis so it meets the
pinion's own -X hole once the assembly seats the pinion rot_z(-seed).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crankshaft.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    _early_bound,
    _feature_by_name,
    _read_member,
    SketchDims,
    anchor_point_to_origin,
    apply_material,
    blank_sketch,
    check,
    define_circle,
    dimension_between,
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
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _hole_spec import blind_cut_dia_mm
from _holes import cross_hole_volume_mm3, wizard_hole_on_cylinder
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from crank_pinion_spec import (
    CRANKSHAFT_PIN_HOLE_PROCESS,
    PIN_CLOCKING_DEG as PINION_PIN_CLOCKING_DEG,
    PIN_DIA as PINION_PIN_DIA,
    PIN_HOLE_SPEC as PINION_PIN_HOLE_SPEC,
)
from crankshaft_spec import (
    COLLAR_DIA,
    COLLAR_DIA_TOL,
    COLLAR_LENGTH,
    COLLAR_REAR,
    COLLAR_STATION_TOL,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRIVE_PIN_CIRCLE_RADIUS,
    DRIVE_PIN_DEPTH,
    DRIVE_PIN_DEPTH_TOL,
    DRIVE_PIN_FLOOR,
    DRIVE_PIN_HOLE_BAND,
    DRIVE_PIN_HOLE_DIA,
    DRIVE_PIN_OFFSET_TOL,
    DRIVE_PIN_SPIGOT_RIM,
    DRIVE_PIN_SPIGOT_RIM_WORST,
    FIDUCIAL_MODEL_DEPTH,
    FIDUCIAL_MODEL_DIA,
    HOLE_CALLOUT_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    JOURNAL_DIA,
    JOURNAL_DIA_BAND,
    JOURNAL_START,
    JOURNAL_LENGTH,
    RELIEF_DIA,
    RELIEF_START,
    RELIEF_LENGTH,
    PINION_PIN_STATION_Y,
    PIN_HOLE_SPEC,
    PIN_HOLE_HEIGHT,
    PINION_SEAT_DIA,
    PINION_SEAT_DIA_BAND,
    SEAT_COLLAR,
    SEAT_STEP,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHAFT_DOME_HEIGHT,
    SHAFT_FIDUCIAL_RADIUS,
    SEAT_PINION,
    SHAFT_LENGTH,
    SHAFT_LENGTH_BAND,
    SPIGOT_DIA,
    SPIGOT_DIA_BAND,
    SPIGOT_END,
    SPIGOT_LENGTH,
    SPIGOT_LENGTH_TOL,
    SURFACE_FINISHES,
)
from crank_native_acceptance import assert_signed_circle_center

PART_NAME = "crankshaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# Dimensions live in crankshaft_spec / crank_hub_geometry. The crank face,
# collar seat and restored post bore stay fixed while the shaft's north end
# follows the shortest W15-compliant pinion boss; MHA-024 still crosses the
# separate hub behind the arm.
# The pinion's retention-pin cross-hole station: the pinion's own PIN_STATION
# (from its toothed south face) measured from the SeatPinion datum that face
# sits on. Machine z = CRANKSHAFT_Z0 + this. The recess of the shaft end inside
# the pinion's boss (build_drive_train_assembly asserts it) is
# SEAT_PINION + OVERALL_LENGTH - SHAFT_LENGTH.

DOME_R = SHAFT_DIA / 2.0
DOME_SPHERE_R = (DOME_R**2 + SHAFT_DOME_HEIGHT**2) / (2.0 * SHAFT_DOME_HEIGHT)
V_DOME = (
    math.pi
    * SHAFT_DOME_HEIGHT**2
    * (3.0 * DOME_SPHERE_R - SHAFT_DOME_HEIGHT)
    / 3.0
)
_FIDUCIAL_AXIS = SHAFT_FIDUCIAL_RADIUS / math.sqrt(2.0)
FIDUCIAL_MODEL_X = -_FIDUCIAL_AXIS
FIDUCIAL_MODEL_Z = -_FIDUCIAL_AXIS
FIDUCIAL_SURFACE_Y = DOME_SPHERE_R - SHAFT_DOME_HEIGHT - math.sqrt(
    DOME_SPHERE_R**2 - SHAFT_FIDUCIAL_RADIUS**2
)


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


# Far-end stations the drawing prints (policy rule 7), each drawn on the
# StationReference sketch from its dome-root station and driven by the same
# globals as the feature it locates.
_STATIONS = {
    "PinionSeatStation": SEAT_STEP,
    "JournalInboardStation": JOURNAL_START + JOURNAL_LENGTH,
    "ReliefInboardStation": RELIEF_START + RELIEF_LENGTH,
    "ReliefOutboardStation": RELIEF_START,
    "JournalOutboardStation": JOURNAL_START,
    "CollarRearStation": COLLAR_REAR,
    "CollarSeatStation": SEAT_COLLAR,
    "PinHoleStation": PIN_HOLE_HEIGHT,
}
_STATION_DRIVES = {
    "PinionSeatStation": '"ShaftLength" - "PinionSeatStep"',
    "JournalInboardStation": '"ShaftLength" - "JournalStart" - "JournalLength"',
    "ReliefInboardStation": '"ShaftLength" - "ReliefStart" - "ReliefLength"',
    "ReliefOutboardStation": '"ShaftLength" - "ReliefStart"',
    "JournalOutboardStation": '"ShaftLength" - "JournalStart"',
    "CollarRearStation": '"ShaftLength" - "SeatCollar" - "CollarLength"',
    "CollarSeatStation": '"ShaftLength" - "SeatCollar"',
    "PinHoleStation": '"ShaftLength" - "PinHoleHeight"',
}


async def _cut_annulus_inboard(
    adapter,
    name: str,
    *,
    start: float,
    start_global: str,
    turned_dia: float,
    inner_dia: float,
    inner_global: str,
    length: float,
    length_expr: str,
    drive_jobs: list[tuple[str, str]],
) -> float:
    """Turn a ``turned_dia`` section down to ``inner_dia`` inboard of ``start``.

    The annulus from ``inner_dia`` out past ``turned_dia`` is cut from a
    ``<name>StartPlane`` at ``start``; its profile is ``<name>Profile`` with
    the printed ``<name>DiaDim``.  A mid-body blind cut defaults back toward
    its base plane, so running AWAY from Top it takes ``reverse_direction``
    (memory/solidworks-modeling-pitfalls.md); the caller's volume gate fails
    loud on the wrong side.  Returns the volume removed.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    plane = f"{name}StartPlane"
    check(
        f"create_plane {plane}",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=start)
        ),
    )
    name_last_feature(adapter, plane)
    start_dim = name_dimensions(adapter, plane, [start_global])
    drive_jobs += [(start_dim[0], f'"{start_global}"')]
    dims = SketchDims()
    check(f"create_sketch {name}", await adapter.create_sketch(plane))
    await define_circle(
        adapter, 0.0, 0.0, inner_dia / 2.0, f"{name} turned circle",
        dims=dims,
        names=(f"{name}Cx", f"{name}Cz", f"{name}DiaDim"),
        drives=(None, None, f'"{inner_global}"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, turned_dia / 2.0 + 1.0, f"{name} clearance circle",
        dims=dims,
        names=(f"{name}OuterCx", f"{name}OuterCz", f"{name}OuterDia"),
    )
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{name}Profile")
    drive_jobs += dims.apply(adapter, f"{name}Profile")
    check(
        f"cut {name}",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=length, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, name)
    length_dim = name_dimensions(adapter, name, [f"{name}Length"])
    drive_jobs += [(length_dim[0], length_expr)]
    return math.pi * ((turned_dia / 2.0) ** 2 - (inner_dia / 2.0) ** 2) * length


async def _collar_section(
    adapter,
    name: str,
    *,
    plane: str,
    station: float,
    station_expr: str,
    dia: float,
    dia_global: str,
    length: float,
    length_name: str,
    length_expr: str,
    drive_jobs: list[tuple[str, str]],
) -> float:
    """Extrude a Ø ``dia`` collar section inboard from a new datum at its front face.

    The Top-parallel datum ``plane`` at ``station`` is the section's own
    sketch plane, so the diameter the drawing drags onto the profile has its
    extension lines start on this section's silhouette.  The profile is
    ``<name>Profile`` with ``<name>DiaDim``; the blind extrude ``name``
    carries ``length_name``.  Returns the volume added over the shaft.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check(
        f"create_plane {plane}",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=station)
        ),
    )
    name_last_feature(adapter, plane)
    plane_dim = name_dimensions(adapter, plane, [f"{plane}Offset"])
    drive_jobs += [(plane_dim[0], station_expr)]
    dims = SketchDims()
    check(f"create_sketch {name}", await adapter.create_sketch(plane))
    await define_circle(
        adapter,
        0.0,
        0.0,
        dia / 2.0,
        f"{name} circle",
        dims=dims,
        names=(f"{name}Cx", f"{name}Cz", f"{name}DiaDim"),
        drives=(None, None, f'"{dia_global}"'),
    )
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{name}Profile")
    drive_jobs += dims.apply(adapter, f"{name}Profile")
    check(
        f"extrude {name}",
        await adapter.create_extrusion(ExtrusionParameters(depth=length)),
    )
    name_last_feature(adapter, name)
    length_dim = name_dimensions(adapter, name, [length_name])
    drive_jobs += [(length_dim[0], length_expr)]
    return math.pi * ((dia / 2.0) ** 2 - (SHAFT_DIA / 2.0) ** 2) * length


async def _volume(adapter) -> float:
    result = await adapter.get_mass_properties()
    return result.data.volume if result.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): shaft and seat dimensions. The
    # mm suffix is load-bearing -- this is an
    # INCH document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 120 = 120 in, blowing the part up 25.4x). SHAFT_DIA is
    # already mm (0.375 * IN), so it serialises as its mm value.
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")
    await set_global(adapter, "JournalDia", f"{JOURNAL_DIA}mm")
    await set_global(adapter, "JournalStart", f"{JOURNAL_START}mm")
    await set_global(adapter, "JournalLength", f"{JOURNAL_LENGTH}mm")
    await set_global(adapter, "ReliefDia", f"{RELIEF_DIA}mm")
    await set_global(adapter, "ReliefStart", f"{RELIEF_START}mm")
    await set_global(adapter, "ReliefLength", f"{RELIEF_LENGTH}mm")
    await set_global(adapter, "PinionSeatDia", f"{PINION_SEAT_DIA}mm")
    await set_global(adapter, "PinionSeatStep", f"{SEAT_STEP}mm")
    await set_global(adapter, "PinHoleHeight", f"{PIN_HOLE_HEIGHT}mm")
    await set_global(adapter, "PinionPinStation", f"{PINION_PIN_STATION_Y}mm")
    await set_global(adapter, "DomeHeight", f"{SHAFT_DOME_HEIGHT}mm")
    await set_global(adapter, "FiducialDia", f"{FIDUCIAL_MODEL_DIA}mm")
    await set_global(adapter, "FiducialDepth", f"{FIDUCIAL_MODEL_DEPTH}mm")
    # Sketch distance dimensions are unsigned magnitudes; the seeded point
    # coordinates below retain the witness's quadrant.
    await set_global(adapter, "FiducialX", f"{abs(FIDUCIAL_MODEL_X)}mm")
    await set_global(adapter, "FiducialZ", f"{abs(FIDUCIAL_MODEL_Z)}mm")
    await set_global(adapter, "SeatCollar", f"{SEAT_COLLAR}mm")
    await set_global(adapter, "CollarLength", f"{COLLAR_LENGTH}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "SpigotDia", f"{SPIGOT_DIA}mm")
    await set_global(adapter, "SpigotLength", f"{SPIGOT_LENGTH}mm")
    await set_global(adapter, "DrivePinCircleRadius", f"{DRIVE_PIN_CIRCLE_RADIUS}mm")
    await set_global(adapter, "DrivePinHoleDia", f"{DRIVE_PIN_HOLE_DIA}mm")
    await set_global(adapter, "DrivePinDepth", f"{DRIVE_PIN_DEPTH}mm")

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

    # Integral same-diameter spherical dome on the outboard end.  Its base is
    # exactly the shaft cylinder, so no mushroom head or removable cap can trap
    # the crank behind the through hub.
    dome = SketchDims()
    check("create_sketch shaft dome", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    dome_axis = check(
        "dome axis",
        await adapter.add_centerline(0.0, -SHAFT_DOME_HEIGHT, 0.0, 0.0),
    )
    dome_base = check(
        "dome base", await adapter.add_line(0.0, 0.0, DOME_R, 0.0)
    )
    dome_arc = check(
        "dome arc",
        await adapter.add_arc(
            0.0,
            DOME_SPHERE_R - SHAFT_DOME_HEIGHT,
            0.0,
            -SHAFT_DOME_HEIGHT,
            DOME_R,
            0.0,
        ),
    )
    dome_close = check(
        "dome closure",
        await adapter.add_line(0.0, -SHAFT_DOME_HEIGHT, 0.0, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    for label, first, second in (
        ("base-arc", f"{dome_base}.end", f"{dome_arc}.end"),
        ("arc-close", f"{dome_arc}.start", f"{dome_close}.start"),
        ("close-base", f"{dome_close}.end", f"{dome_base}.start"),
        ("axis start", f"{dome_axis}.start", f"{dome_arc}.start"),
        ("axis end", f"{dome_axis}.end", f"{dome_base}.start"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, "coincident"))
    for label, entity, relation in (
        ("dome base", dome_base, "horizontal"),
        ("dome closure", dome_close, "vertical"),
        ("dome axis", dome_axis, "vertical"),
    ):
        check(label, await adapter.add_sketch_constraint(entity, None, relation))
    await anchor_point_to_origin(
        adapter, f"{dome_base}.start", 0.0, 0.0, "dome base"
    )
    check(
        "dome base radius",
        await adapter.add_sketch_dimension(dome_base, None, "linear", DOME_R),
    )
    dome.record("DomeBaseR", '"ShaftDia" / 2')
    check(
        "dome height",
        await adapter.add_sketch_dimension(
            f"{dome_arc}.start", "origin", "vertical_distance", SHAFT_DOME_HEIGHT
        ),
    )
    dome.record("DomeHeight", '"DomeHeight"')
    check(
        "dome sphere radius",
        await adapter.add_sketch_dimension(dome_arc, None, "radial", DOME_SPHERE_R),
    )
    dome.record(
        "DomeSphereR",
        '("ShaftDia" / 2 * "ShaftDia" / 2 + "DomeHeight" * "DomeHeight") '
        '/ (2 * "DomeHeight")',
    )
    await ensure_fully_defined(adapter, "shaft dome profile")
    check("exit_sketch shaft dome", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftDomeProfile")
    drive_jobs += dome.apply(adapter, "ShaftDomeProfile")
    check(
        "revolve shaft dome",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "ShaftDome")
    await volume_check(
        adapter,
        "shaft with integral dome",
        v_shaft + V_DOME,
        0.005 * (v_shaft + V_DOME),
    )

    # Simple punched alignment witness on the dome, angularly aligned with the
    # arm witness.  The shallow cut is visual-only and never dimensioned.
    check(
        "create_plane ShaftFiducialPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Top Plane",
                offset=FIDUCIAL_SURFACE_Y,
            )
        ),
    )
    name_last_feature(adapter, "ShaftFiducialPlane")
    fiducial = SketchDims()
    check(
        "create_sketch shaft fiducial",
        await adapter.create_sketch("ShaftFiducialPlane"),
    )
    await define_circle(
        adapter,
        FIDUCIAL_MODEL_X,
        -FIDUCIAL_MODEL_Z,
        FIDUCIAL_MODEL_DIA / 2.0,
        "shaft punch witness",
        dims=fiducial,
        names=("FiducialX", "FiducialZ", "FiducialDia"),
        drives=('"FiducialX"', '"FiducialZ"', '"FiducialDia"'),
    )
    await ensure_fully_defined(adapter, "shaft fiducial sketch")
    check("exit_sketch shaft fiducial", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftFiducialProfile")
    drive_jobs += fiducial.apply(adapter, "ShaftFiducialProfile")
    check(
        "cut shaft fiducial",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=2.0 * FIDUCIAL_MODEL_DEPTH,
                both_directions=True,
            )
        ),
    )
    name_last_feature(adapter, "PunchedFiducial")
    v_shaft_nose = await _volume(adapter)

    # Integral journal: the original concentric extrusion and middle relief,
    # retaining the later rebuild-neutrality, signed witness and visibility gates.
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
    check("create_sketch bearing journal", await adapter.create_sketch("JournalStartPlane"))
    await define_circle(
        adapter, 0.0, 0.0, JOURNAL_DIA / 2.0, "bearing journal circle",
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
    v_with_seat = v_shaft_nose + math.pi * (
        (JOURNAL_DIA / 2.0) ** 2 - (SHAFT_DIA / 2.0) ** 2
    ) * JOURNAL_LENGTH
    await volume_check(
        adapter, "shaft + bearing journal", v_with_seat, 0.005 * v_with_seat
    )
    v_with_seat -= await _cut_annulus_inboard(
        adapter,
        "Relief",
        start=RELIEF_START,
        start_global="ReliefStart",
        turned_dia=JOURNAL_DIA,
        inner_dia=RELIEF_DIA,
        inner_global="ReliefDia",
        length=RELIEF_LENGTH,
        length_expr='"ReliefLength"',
        drive_jobs=drive_jobs,
    )
    await volume_check(adapter, "journal relief", v_with_seat, 0.005 * v_with_seat)
    # The Ø9.0 pinion seat (RULING (b)): the same cut from the seat step to
    # the far end face.
    v_with_seat -= await _cut_annulus_inboard(
        adapter,
        "PinionSeat",
        start=SEAT_STEP,
        start_global="PinionSeatStep",
        turned_dia=SHAFT_DIA,
        inner_dia=PINION_SEAT_DIA,
        inner_global="PinionSeatDia",
        length=SHAFT_LENGTH - SEAT_STEP,
        length_expr='"ShaftLength" - "PinionSeatStep"',
        drive_jobs=drive_jobs,
    )
    await volume_check(
        adapter, "pinion seat step", v_with_seat, 0.005 * v_with_seat
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

    # Tapered MHA-024 cross-hole through the shaft and MHA-137 rear barrel.
    # It sits behind the arm at the shared station plane; Front Plane fixes the
    # radial clocking while the host face follows ShaftDia.
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
    v_final = v_with_seat - v_pin
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
            PINION_SEAT_DIA / 2.0 * entry_dir[0],
            PINION_PIN_STATION_Y,
            PINION_SEAT_DIA / 2.0 * entry_dir[2],
        ],
        "pinion retention-pin cross-hole",
        name="PinionPinHole",
        point_planes=("PinionPinStationPlane", "PinionPinClockingPlane"),
    )
    v_pinion_pin = cross_hole_volume_mm3(PINION_PIN_DIA, PINION_SEAT_DIA)
    v_final -= v_pinion_pin
    await volume_check(adapter, "shaft + pinion pin hole", v_final, 0.02 * v_pinion_pin)

    # ch. 23 seat collar, integral with the shaft (CONTRACT-crank), turned in
    # two sections: the seat spigot, whose face on the SeatCollar datum is the
    # removable sprocket's seat and which the #25 plates wrapping the T12 pass
    # over, then the body from the spigot's step (the SpigotEnd datum) to the
    # CollarRear face the MHA-172 washer rides.  The step is sharp: the title
    # block's general edge break covers its corners.
    v_final += await _collar_section(
        adapter,
        "Spigot",
        plane="SeatCollar",
        station=SEAT_COLLAR,
        station_expr='"SeatCollar"',
        dia=SPIGOT_DIA,
        dia_global="SpigotDia",
        length=SPIGOT_LENGTH,
        length_name="SpigotLength",
        length_expr='"SpigotLength"',
        drive_jobs=drive_jobs,
    )
    await volume_check(adapter, "shaft + seat spigot", v_final, 0.005 * v_final)
    v_final += await _collar_section(
        adapter,
        "Collar",
        plane="SpigotEnd",
        station=SPIGOT_END,
        station_expr='"SeatCollar" + "SpigotLength"',
        dia=COLLAR_DIA,
        dia_global="CollarDia",
        length=COLLAR_LENGTH - SPIGOT_LENGTH,
        length_name="CollarBodyLength",
        length_expr='"CollarLength" - "SpigotLength"',
        drive_jobs=drive_jobs,
    )
    await volume_check(adapter, "shaft + seat collar", v_final, 0.005 * v_final)

    # Two blind, flat-bottomed holes reamed into the seat face for the pressed
    # MHA-173 dowels, on the wheel's pin circle at local +Z (#1) and -Z (#2);
    # the Top-parallel sketch reads (u, v) = (x, -z).  A cut from a mid-body
    # plane runs back toward Top by default -- into air in front of the seat --
    # so it takes reverse_direction, and the volume gate fails loud on the
    # wrong side.  The pin holes' rim to the spigot is logged below.
    pins = SketchDims()
    check("create_sketch drive-pin holes", await adapter.create_sketch("SeatCollar"))
    for index, sketch_v in (
        (1, -DRIVE_PIN_CIRCLE_RADIUS),
        (2, DRIVE_PIN_CIRCLE_RADIUS),
    ):
        await define_circle(
            adapter,
            0.0,
            sketch_v,
            DRIVE_PIN_HOLE_DIA / 2.0,
            f"drive-pin hole {index}",
            dims=pins,
            names=(None, f"DrivePinOffset{index}", f"DrivePinHoleDia{index}"),
            drives=(None, '"DrivePinCircleRadius"', '"DrivePinHoleDia"'),
        )
    await ensure_fully_defined(adapter, "drive-pin hole sketch")
    check("exit_sketch drive-pin holes", await adapter.exit_sketch())
    name_last_feature(adapter, "DrivePinProfile")
    drive_jobs += pins.apply(adapter, "DrivePinProfile")
    check(
        "cut drive-pin holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=DRIVE_PIN_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "DrivePinHoles")
    pin_depth_dim = name_dimensions(adapter, "DrivePinHoles", ["DrivePinDepth"])
    drive_jobs += [(pin_depth_dim[0], '"DrivePinDepth"')]
    v_pin_holes = 2.0 * math.pi * (DRIVE_PIN_HOLE_DIA / 2.0) ** 2 * DRIVE_PIN_DEPTH
    v_final -= v_pin_holes
    await volume_check(
        adapter, "seat collar drive-pin holes", v_final, 0.05 * v_pin_holes
    )
    _telemetry.info(
        f"seat spigot rim (floor 1.5): drive-pin hole to the Ø{SPIGOT_DIA:g}"
        f" spigot {DRIVE_PIN_SPIGOT_RIM:.2f} nominal,"
        f" {DRIVE_PIN_SPIGOT_RIM_WORST:.2f} at the printed worst case"
    )
    for plane, station, expr in (
        ("CollarRear", COLLAR_REAR, '"SeatCollar" + "CollarLength"'),
        ("DrivePinFloor", DRIVE_PIN_FLOOR, '"SeatCollar" + "DrivePinDepth"'),
    ):
        check(
            f"create_plane {plane} (Top Plane + {station:g})",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Top Plane", offset=station
                )
            ),
        )
        name_last_feature(adapter, plane)
        plane_dim = name_dimensions(adapter, plane, [f"{plane}Offset"])
        drive_jobs += [(plane_dim[0], expr)]
    # The pins' axes for the drive-train mates: DrivePinAxis1 on local +Z
    # (machine -Y once placed), DrivePinAxis2 opposite; created after the
    # shaft's Axis1 so that name stays put.
    for axis_name, z in (
        ("DrivePinAxis1", DRIVE_PIN_CIRCLE_RADIUS),
        ("DrivePinAxis2", -DRIVE_PIN_CIRCLE_RADIUS),
    ):
        await name_bore_axis(
            adapter,
            "Right Plane",
            0.0,
            "Front Plane",
            z,
            axis_name,
            drive_b='"DrivePinCircleRadius"',
            drive_jobs=drive_jobs,
        )
        name_last_feature(adapter, axis_name)

    # Drawing-only station reference.  The print baselines every axial
    # station from the FAR END, the one faced end a machinist zeroes on
    # (policy rule 7), but the model's features measure from the dome root.
    # Each construction line's one driving dimension IS the printed value
    # (policy rule 2), driven by the same globals as the features, so no
    # geometry moves.  The sketch sits on the Right plane because the *Right
    # side view prints it (every reference sketch that imports natively sits
    # on the plane of its view -- build_crank_hub's
    # ServicePinStationReference), on the shaft axis under the view's
    # centreline so the construction lines add no visible ink.  A
    # construction arc over the dome silhouette carries its spherical radius.
    # Right (u, v) -> (-Z, Y); u < 0 is model +Z, the side the rotated side
    # view prints UP.
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    overall_line = check(
        "overall reference line",
        await adapter.add_line(0.0, -SHAFT_DOME_HEIGHT, 0.0, SHAFT_LENGTH),
    )
    station_lines = {}
    for name, station in _STATIONS.items():
        station_lines[name] = check(
            f"{name} reference line",
            await adapter.add_line(0.0, SHAFT_LENGTH, 0.0, station),
        )
    # Counter-clockwise from the dome root corner down to the tip.
    dome_arc = check(
        "dome radius reference arc",
        await adapter.add_arc(
            0.0,
            DOME_SPHERE_R - SHAFT_DOME_HEIGHT,
            -DOME_R,
            0.0,
            0.0,
            -SHAFT_DOME_HEIGHT,
        ),
    )
    set_sketch_direct_db(adapter, False)
    for entity in (overall_line, *station_lines.values(), dome_arc):
        segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"station reference {entity} did not take construction flag")
    check(
        "overall reference vertical",
        await adapter.add_sketch_constraint(overall_line, None, "vertical"),
    )
    for name, line in station_lines.items():
        check(
            f"{name} reference vertical",
            await adapter.add_sketch_constraint(line, None, "vertical"),
        )
        check(
            f"{name} reference starts at the far end",
            await adapter.add_sketch_constraint(
                f"{line}.start", f"{overall_line}.end", "coincident"
            ),
        )
    check(
        "dome radius reference ends at the tip",
        await adapter.add_sketch_constraint(
            f"{dome_arc}.end", f"{overall_line}.start", "coincident"
        ),
    )
    check(
        "dome radius reference centre on the axis",
        await adapter.add_sketch_constraint(f"{dome_arc}.center", "origin", "vertical_points"),
    )
    check(
        "dome radius reference starts at the dome root",
        await adapter.add_sketch_constraint(f"{dome_arc}.start", "origin", "horizontal_points"),
    )
    # Dimensions in creation order; SketchDims renames them by that order.
    await anchor_point_to_origin(
        adapter, f"{overall_line}.start", 0.0, -SHAFT_DOME_HEIGHT, "dome tip reference"
    )
    stations.record(None, '"DomeHeight"')
    await dimension_between(
        adapter,
        f"{overall_line}.start",
        f"{overall_line}.end",
        "vertical_distance",
        SHAFT_LENGTH + SHAFT_DOME_HEIGHT,
        "overall length reference",
    )
    stations.record("OverallLength", '"ShaftLength" + "DomeHeight"')
    for name, line in station_lines.items():
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "vertical_distance",
            SHAFT_LENGTH - _STATIONS[name],
            f"{name} reference",
        )
        stations.record(name, _STATION_DRIVES[name])
    check(
        "dome radius reference",
        await adapter.add_sketch_dimension(dome_arc, None, "radial", DOME_SPHERE_R),
    )
    stations.record(
        "DomeSphereRadius",
        '("ShaftDia" / 2 * "ShaftDia" / 2 + "DomeHeight" * "DomeHeight") '
        '/ (2 * "DomeHeight")',
    )
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    assert_signed_circle_center(
        adapter,
        "ShaftFiducialProfile",
        label="MHA-026 punched fiducial",
        expected_sketch_xy_mm=(FIDUCIAL_MODEL_X, -FIDUCIAL_MODEL_Z),
        expected_model_xyz_mm=(
            FIDUCIAL_MODEL_X,
            FIDUCIAL_SURFACE_Y,
            FIDUCIAL_MODEL_Z,
        ),
    )
    set_dimension_bilateral_tolerance(
        adapter, "ShaftProfile", "ShaftDiaDim", *deviations(SHAFT_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "JournalProfile", "JournalDiaDim", *deviations(JOURNAL_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "PinionSeatProfile",
        "PinionSeatDiaDim",
        *deviations(PINION_SEAT_DIA_BAND),
    )
    # W15: the length is unilateral (crankshaft_spec.SHAFT_LENGTH_BAND); it
    # prints from the model on the far-end-to-dome-root Depth.
    set_dimension_bilateral_tolerance(
        adapter, "Shaft", "Depth", *deviations(SHAFT_LENGTH_BAND)
    )
    # The seat collar's functional bands (crankshaft_spec, rule 12): the two
    # far-end stations, the body OD, the seat spigot's diameter and its length
    # from the seat face, and the drive-pin holes' location, press size and
    # depth.
    for name in ("CollarSeatStation", "CollarRearStation"):
        set_dimension_symmetric_tolerance(
            adapter, "StationReference", name, COLLAR_STATION_TOL
        )
    set_dimension_symmetric_tolerance(
        adapter, "CollarProfile", "CollarDiaDim", COLLAR_DIA_TOL
    )
    set_dimension_bilateral_tolerance(
        adapter, "SpigotProfile", "SpigotDiaDim", *deviations(SPIGOT_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "Spigot", "SpigotLength", SPIGOT_LENGTH_TOL
    )
    for index in (1, 2):
        set_dimension_symmetric_tolerance(
            adapter, "DrivePinProfile", f"DrivePinOffset{index}", DRIVE_PIN_OFFSET_TOL
        )
        set_dimension_bilateral_tolerance(
            adapter,
            "DrivePinProfile",
            f"DrivePinHoleDia{index}",
            *deviations(DRIVE_PIN_HOLE_BAND),
        )
    set_dimension_symmetric_tolerance(
        adapter, "DrivePinHoles", "DrivePinDepth", DRIVE_PIN_DEPTH_TOL
    )
    await volume_check(adapter, "driven crankshaft (equations neutral)", v_final, 50.0)

    # The 16T's seat datum.  The through hub seats at the shaft's Top/origin
    # plane; the wheel's seat datums were made with the collar.
    check(
        f"create_plane SeatPinion (Top Plane, +{SEAT_PINION:.3f})",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Top Plane",
                offset=SEAT_PINION,
            )
        ),
    )
    name_last_feature(adapter, "SeatPinion")
    # Every surviving plane (the rejected clocking attempt was deleted); the
    # seat datums stay selectable by name for the drive-train mates.
    blank_reference_geometry(
        adapter,
        tuple(
            (name, "PLANE")
            for name in (
                "ShaftFiducialPlane",
                "JournalStartPlane",
                "ReliefStartPlane",
                "PinionSeatStartPlane",
                "PinHoleStationPlane",
                "PinionPinStationPlane",
                "PinionPinClockingPlane",
                "SeatCollar",
                "SpigotEnd",
                "CollarRear",
                "DrivePinFloor",
                "SeatPinion",
            )
        ),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # The drive-pin holes print through their native callout, which reads the
    # cut's own size and depth dimensions at these places.
    apply_drawing_precision(adapter, HOLE_CALLOUT_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            # crank_pinion_spec owns the PinionPinHole callout prefix so the two
            # prints of one matched fit can never disagree.
            "Pinion Pin Hole Process": CRANKSHAFT_PIN_HOLE_PROCESS,
        },
    )
    # The reference sketch owns printed dimensions but no geometry: hide it so
    # no assembly instance renders it (#880).  The drawing shows it per view
    # through _drawing_hidden_sketches to import those dimensions.
    blank_sketch(adapter, "StationReference")
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
