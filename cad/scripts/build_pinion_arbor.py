r"""Build the integral MHA-102 pinion arbor and turned grip head.

The head, neck, and long shaft are one turned steel part.  Their absolute
released envelope and assembly origin are unchanged; only the unsupported
socket/retention-pin construction is removed.  MHA-058 is the separate grip
crossrod bonded into the head's reamed hole.
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    _feature_by_name,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    feature_name_by_type,
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
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_prefix,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _gtol_spec import CylinderFace
from _part_pmi import _face_geometry, _face_matches, _resolve_faces, author_part_pmi
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from _saved_part_guard import require_saved_drawing_properties
from pinion_arbor_pin_spec import PIN_HOLE_DIA, PIN_HOLE_DIA_BAND
from pinion_arbor_spec import (
    BACK_RIM_FROM_HEAD_REAR,
    BACK_CAP_R,
    BACK_CAP_SAG,
    BACK_JOURNAL_FROM_HEAD_REAR,
    BACK_JOURNAL_Z,
    BOND_ZONE_DIA_FROM_HEAD_REAR,
    BOND_ZONE_DIA_Z,
    CROSS_HOLE_DIA,
    CROSS_HOLE_DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRUM_STATION,
    DRUM_STATION_BAND,
    EXPOSED_SHAFT_LEN,
    FRONT_JOURNAL_FROM_HEAD_REAR,
    FRONT_JOURNAL_Z,
    HEAD_CAP_R,
    HEAD_CAP_SAG,
    HEAD_CENTER_Z,
    HEAD_DIA,
    HEAD_FRONT_Z,
    HEAD_LEN,
    HEAD_REAR_Z,
    ISOMETRIC_VIEW_NOTE,
    JOURNAL_DIA_BAND,
    JOURNAL_LEN,
    NECK_DIA,
    NECK_END_Z,
    NECK_LEN,
    OVERALL_LEN,
    PIN_STATION_FROM_HEAD_REAR,
    PIN_Z,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHAFT_LEN,
    SURFACE_FINISHES,
)

PART_NAME = "pinion-arbor"
MATERIAL = "Plain Carbon Steel"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

SHAFT_R = SHAFT_DIA / 2.0
NECK_R = NECK_DIA / 2.0
HEAD_R = HEAD_DIA / 2.0
CROSS_HOLE_R = CROSS_HOLE_DIA / 2.0
PIN_HOLE_R = PIN_HOLE_DIA / 2.0
V_SHAFT = math.pi * SHAFT_R**2 * EXPOSED_SHAFT_LEN
V_NECK = math.pi * NECK_R**2 * NECK_LEN
V_HEAD = math.pi * HEAD_R**2 * HEAD_LEN
V_FRONT_CAP = math.pi * HEAD_CAP_SAG**2 * (3.0 * HEAD_CAP_R - HEAD_CAP_SAG) / 3.0
V_BACK_CAP = math.pi * BACK_CAP_SAG**2 * (3.0 * BACK_CAP_R - BACK_CAP_SAG) / 3.0
# Split lines reach this far past the shaft flank so the projection crosses
# the whole Ø8 face on both sides of the Top plane.
SPLIT_OVERHANG = 2.0
JOURNAL_AREA = math.pi * SHAFT_DIA * JOURNAL_LEN
# Each land's diameter is measured at a short construction witness this far
# in from the land's crown-side end, so the sheet's diameter line stands 1 mm
# from it and its extensions are ~1 mm, not a run along the flank from the
# land's head-side end (Main, 2026-09-24).  Just inside the end rather than on
# it: the drum-station witness sits 4.4 mm head side of the front land's
# crown end, and the text hangs away from the side its extensions come from.
JOURNAL_DIA_POINT_FROM_CROWN_END = 2.0
JOURNAL_DIA_POINT_LEN = 1.0
# The drum station has no feature on the shaft, so its far end is a short
# construction witness ON THE Ø8 FLANK (sketch +x, the sheet's lower flank
# under the -90 deg *Top profile), not a point on the axis: from the axis its
# sheet witness drew a 4 mm stub inside the silhouette that read as a step a
# machinist might cut (Main, c3419623).
DRUM_STATION_POINT_X = SHAFT_R
DRUM_STATION_POINT_LEN = 1.0
# The bond-zone diameter's construction witness: a short run of the flank.
BOND_ZONE_WITNESS_LEN = 4.0


def _perpendicular_cylinder_intersection(hole_radius: float, body_radius: float) -> float:
    """Volume removed where the Y-axis cross-hole passes through the round head."""
    intervals = 2000
    y0, y1 = -body_radius, body_radius
    step = (y1 - y0) / intervals

    def area(y: float) -> float:
        chord_half = math.sqrt(max(body_radius**2 - y * y, 0.0))
        if chord_half >= hole_radius:
            return math.pi * hole_radius**2
        return 2.0 * (
            chord_half * math.sqrt(hole_radius**2 - chord_half**2)
            + hole_radius**2 * math.asin(chord_half / hole_radius)
        )

    total = area(y0) + area(y1)
    for index in range(1, intervals):
        total += (4.0 if index % 2 else 2.0) * area(y0 + index * step)
    return total * step / 3.0


V_CROSS_HOLE = _perpendicular_cylinder_intersection(CROSS_HOLE_R, HEAD_R)
V_PIN_HOLE = _perpendicular_cylinder_intersection(PIN_HOLE_R, SHAFT_R)
V_TOTAL = (
    V_NECK + V_SHAFT + V_HEAD + V_FRONT_CAP + V_BACK_CAP - V_CROSS_HOLE - V_PIN_HOLE
)


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected exactly one solid body, found {len(bodies)}")


async def _add_axial_reference(
    adapter,
    *,
    feature_name: str,
    dimension_name: str,
    start_v: float,
    end_v: float,
    drive_expression: str,
    end_on_flank: float | None = None,
) -> list[tuple[str, str]]:
    """Author one native axial dimension without adding model geometry.

    With ``end_on_flank`` the far end is the start of a short construction
    witness that far off the axis (on the flank), not the axis point itself.
    """
    dims = SketchDims()
    check(f"create sketch {feature_name}", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    line = check(
        f"add {feature_name} witness",
        await adapter.add_centerline(0.0, start_v, 0.0, end_v),
    )
    flank = None
    if end_on_flank is not None:
        flank = check(
            f"add {feature_name} flank witness",
            await adapter.add_line(
                end_on_flank, end_v, end_on_flank, end_v + DRUM_STATION_POINT_LEN
            ),
        )
    set_sketch_direct_db(adapter, False)
    if flank is not None:
        segment = _early_bound(adapter._sketch_entities[flank], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"{flank}: failed to become construction geometry")
    check(
        f"{feature_name} vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{line}.start", 0.0, start_v, f"{feature_name} start"
    )
    dims.record(None, None)
    far_end = f"{line}.end" if flank is None else f"{flank}.start"
    check(
        f"dimension {dimension_name}",
        await adapter.add_sketch_dimension(
            f"{line}.start", far_end, "vertical_distance", abs(end_v - start_v)
        ),
    )
    dims.record(dimension_name, drive_expression)
    if flank is not None:
        for first, second, relation in (
            (flank, None, "vertical"),
            (f"{flank}.start", f"{line}.end", "horizontal_points"),
        ):
            check(
                f"{feature_name} {first} {relation}",
                await adapter.add_sketch_constraint(first, second, relation),
            )
        check(
            f"{feature_name} flank offset",
            await adapter.add_sketch_dimension(
                f"{line}.end", f"{flank}.start", "horizontal_distance", end_on_flank
            ),
        )
        dims.record(None, None)
        check(
            f"{feature_name} flank witness length",
            await adapter.add_sketch_dimension(
                f"{flank}.start", f"{flank}.end", "vertical_distance", DRUM_STATION_POINT_LEN
            ),
        )
        dims.record(None, None)
    await ensure_fully_defined(adapter, feature_name)
    check(f"exit sketch {feature_name}", await adapter.exit_sketch())
    name_last_feature(adapter, feature_name)
    return dims.apply(adapter, feature_name)


def _shaft_faces(adapter) -> list[object]:
    spec = CylinderFace(SHAFT_DIA)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    faces = []
    for body in part.GetBodies2(0, False) or ():
        face = _early_bound(body, "IBody2").GetFirstFace()
        while face is not None:
            geometry = _face_geometry(face)
            if geometry is not None and _face_matches(geometry, spec):
                faces.append(geometry.face)
            face = _early_bound(face, "IFace2").GetNextFace()
    return faces


def _journal_face(adapter, prefix: str, journal_z: float) -> object:
    label = f"{prefix} land"
    spec = CylinderFace(SHAFT_DIA, contains_z_mm=journal_z + JOURNAL_LEN / 2.0)
    return _resolve_faces(adapter.currentModel, {label: spec})[label]


async def _add_journal_land(
    adapter,
    *,
    prefix: str,
    journal_z: float,
    station_expression: str,
) -> list[tuple[str, str]]:
    """Split one MHA-056 journal land off the Ø8 shaft and dimension it.

    One Top-plane sketch owns the land: two real cross lines at its ends
    (projected both ways they cut the cylinder into its own face), a
    construction witness on the flank between them, and the three native
    dimensions the sheet prints -- station from the head shoulder, land
    length, and the diameter that carries the journal band (policy rule 2).
    """
    feature_name = f"{prefix}Reference"
    start_v = -journal_z
    end_v = -(journal_z + JOURNAL_LEN)
    reach = SHAFT_R + SPLIT_OVERHANG
    dims = SketchDims()
    check(f"create sketch {feature_name}", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        f"{feature_name} axis",
        await adapter.add_centerline(0.0, -HEAD_REAR_Z, 0.0, end_v),
    )
    near = check(
        f"{feature_name} head-side split",
        await adapter.add_line(-reach, start_v, reach, start_v),
    )
    far = check(
        f"{feature_name} crown-side split",
        await adapter.add_line(-reach, end_v, reach, end_v),
    )
    witness = check(
        f"{feature_name} flank witness",
        await adapter.add_line(SHAFT_R, start_v, SHAFT_R, end_v),
    )
    dia_v = end_v + JOURNAL_DIA_POINT_FROM_CROWN_END
    dia_witness = check(
        f"{feature_name} diameter witness",
        await adapter.add_line(SHAFT_R, dia_v, SHAFT_R, dia_v + JOURNAL_DIA_POINT_LEN),
    )
    set_sketch_direct_db(adapter, False)
    for construction in (witness, dia_witness):
        segment = _early_bound(adapter._sketch_entities[construction], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"{construction}: failed to become construction geometry")
    for line, relation in (
        (axis, "vertical"),
        (witness, "vertical"),
        (near, "horizontal"),
        (far, "horizontal"),
    ):
        check(
            f"{feature_name} {line} {relation}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    for first, second, relation in (
        (f"{axis}.end", far, "midpoint"),
        (f"{near}.start", f"{far}.start", "vertical_points"),
        (f"{near}.end", f"{far}.end", "vertical_points"),
        (f"{witness}.start", f"{near}.start", "horizontal_points"),
        (f"{witness}.end", f"{axis}.end", "horizontal_points"),
    ):
        check(
            f"{feature_name} {first} {relation} {second}",
            await adapter.add_sketch_constraint(first, second, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{axis}.start", 0.0, -HEAD_REAR_Z, f"{feature_name} shoulder"
    )
    dims.record(None, None)
    check(
        f"{feature_name} split reach",
        await adapter.add_sketch_dimension(
            f"{far}.start", f"{far}.end", "horizontal_distance", 2.0 * reach
        ),
    )
    dims.record(None, None)
    check(
        f"{feature_name} station",
        await adapter.add_sketch_dimension(
            f"{axis}.start",
            f"{witness}.start",
            "vertical_distance",
            journal_z - HEAD_REAR_Z,
        ),
    )
    dims.record(f"{prefix}FromHeadRear", station_expression)
    check(
        f"{feature_name} length",
        await adapter.add_sketch_dimension(
            f"{witness}.start", f"{witness}.end", "vertical_distance", JOURNAL_LEN
        ),
    )
    dims.record(f"{prefix}Len", '"JournalLen"')
    check(
        f"{feature_name} diameter witness on the flank",
        await adapter.add_sketch_constraint(dia_witness, witness, "collinear"),
    )
    check(
        f"{feature_name} diameter witness station",
        await adapter.add_sketch_dimension(
            f"{witness}.end",
            f"{dia_witness}.start",
            "vertical_distance",
            JOURNAL_DIA_POINT_FROM_CROWN_END,
        ),
    )
    dims.record(None, None)
    check(
        f"{feature_name} diameter witness length",
        await adapter.add_sketch_dimension(
            f"{dia_witness}.start",
            f"{dia_witness}.end",
            "vertical_distance",
            JOURNAL_DIA_POINT_LEN,
        ),
    )
    dims.record(None, None)
    await add_diametric_linear_dimension(
        adapter,
        axis,
        f"{dia_witness}.start",
        (SHAFT_R + 5.0, dia_v),
        f"{prefix}Dia",
    )
    dims.record(f"{prefix}Dia", '"ShaftDia"')
    await ensure_fully_defined(adapter, feature_name)
    check(f"exit sketch {feature_name}", await adapter.exit_sketch())
    name_last_feature(adapter, feature_name)
    drive_jobs = dims.apply(adapter, feature_name)

    # Projected split line: the sketch at mark 4, the Ø8 face it cuts at mark 1.
    before = len(_shaft_faces(adapter))
    target = _journal_face(adapter, prefix, journal_z)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        feature_name, "SKETCH", 0.0, 0.0, 0.0, False, 4, null_callout(), 0
    ):
        raise RuntimeError(f"{feature_name}: failed to select the split sketch")
    selection_manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    selection_data = _early_bound(selection_manager.CreateSelectData(), "ISelectData")
    selection_data.Mark = 1
    if not _early_bound(target, "IEntity").Select4(True, selection_data):
        raise RuntimeError(f"{feature_name}: failed to select the Ø8 shaft face")
    previous = feature_name_by_type(adapter, "PLine")
    model.InsertSplitLineProject(False, False)  # both directions: a full ring
    model.ClearSelection2(True)
    split = feature_name_by_type(adapter, "PLine")
    if not split or split == previous:
        raise RuntimeError(f"{feature_name}: projected split line was not created")
    _feature_by_name(adapter, split).Name = f"{prefix}Split"
    after = len(_shaft_faces(adapter))
    if after != before + 2:
        raise RuntimeError(
            f"{prefix}Split: Ø8 shaft faces went {before} -> {after}; "
            "expected the land split off as its own face"
        )
    area = float(_early_bound(_journal_face(adapter, prefix, journal_z), "IFace2").GetArea())
    area_mm2 = area * 1e6
    if abs(area_mm2 - JOURNAL_AREA) > 0.01 * JOURNAL_AREA:
        raise RuntimeError(
            f"{prefix}Split: land face area {area_mm2:.1f} mm^2 != "
            f"{JOURNAL_AREA:.1f} mm^2"
        )
    _telemetry.success(
        f"{prefix}Split: Ø8 shaft faces {before} -> {after}, land {area_mm2:.1f} mm^2",
        faces=after,
        land_area_mm2=area_mm2,
    )
    return drive_jobs


async def _add_bond_zone_reference(adapter) -> list[tuple[str, str]]:
    """Dimension the Ø8 bond zone on its own flank, like a journal land.

    A Top-plane sketch with no model geometry: the turning axis from the head
    shoulder to the bond-zone station, a construction witness on the flank
    there, and the diameter between them.  The profile view prints it as a
    local diameter whose witnesses stay on the bond zone, where the end-on
    shaft circle's ran along the neck face and out through the detail fence.
    """
    feature_name = "BondZoneReference"
    start_v = -HEAD_REAR_Z
    end_v = -BOND_ZONE_DIA_Z
    dims = SketchDims()
    check(f"create sketch {feature_name}", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        f"{feature_name} axis",
        await adapter.add_centerline(0.0, start_v, 0.0, end_v),
    )
    witness = check(
        f"{feature_name} flank witness",
        await adapter.add_line(SHAFT_R, end_v, SHAFT_R, end_v - BOND_ZONE_WITNESS_LEN),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[witness], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{witness}: failed to become construction geometry")
    for line in (axis, witness):
        check(
            f"{feature_name} {line} vertical",
            await adapter.add_sketch_constraint(line, None, "vertical"),
        )
    check(
        f"{feature_name} witness level with the axis end",
        await adapter.add_sketch_constraint(
            f"{witness}.start", f"{axis}.end", "horizontal_points"
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{axis}.start", 0.0, start_v, f"{feature_name} shoulder"
    )
    dims.record(None, None)
    check(
        f"{feature_name} station",
        await adapter.add_sketch_dimension(
            f"{axis}.start", f"{axis}.end", "vertical_distance", BOND_ZONE_DIA_FROM_HEAD_REAR
        ),
    )
    dims.record(None, None)
    check(
        f"{feature_name} witness length",
        await adapter.add_sketch_dimension(
            f"{witness}.start", f"{witness}.end", "vertical_distance", BOND_ZONE_WITNESS_LEN
        ),
    )
    dims.record(None, None)
    await add_diametric_linear_dimension(
        adapter,
        axis,
        f"{witness}.start",
        (SHAFT_R + 5.0, end_v),
        "BondZoneDia",
    )
    dims.record("BondZoneDia", '"ShaftDia"')
    await ensure_fully_defined(adapter, feature_name)
    check(f"exit sketch {feature_name}", await adapter.exit_sketch())
    name_last_feature(adapter, feature_name)
    return dims.apply(adapter, feature_name)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    globals_mm = {
        "HeadDia": HEAD_DIA,
        "HeadLen": HEAD_LEN,
        "HeadCapSag": HEAD_CAP_SAG,
        "HeadFrontZ": HEAD_FRONT_Z,
        "HeadCenterZ": HEAD_CENTER_Z,
        "NeckDia": NECK_DIA,
        "NeckLen": NECK_LEN,
        "NeckEndZ": NECK_END_Z,
        "ShaftDia": SHAFT_DIA,
        "ExposedShaftLen": EXPOSED_SHAFT_LEN,
        "ShaftLen": SHAFT_LEN,
        "BackCapSag": BACK_CAP_SAG,
        "CrossHoleDia": CROSS_HOLE_DIA,
        "BackRimFromHeadRear": BACK_RIM_FROM_HEAD_REAR,
        "OverallLen": OVERALL_LEN,
        "JournalLen": JOURNAL_LEN,
        "FrontJournalFromHeadRear": FRONT_JOURNAL_FROM_HEAD_REAR,
        "BackJournalFromHeadRear": BACK_JOURNAL_FROM_HEAD_REAR,
        "DrumStationFromHeadRear": DRUM_STATION,
        "PinStationFromHeadRear": PIN_STATION_FROM_HEAD_REAR,
        "PinHoleDia": PIN_HOLE_DIA,
    }
    for name, value in globals_mm.items():
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    neck = SketchDims()
    check("create_sketch neck", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        NECK_R,
        "integral neck",
        dims=neck,
        names=("NeckCx", "NeckCz", "NeckDia"),
        drives=(None, None, '"NeckDia"'),
    )
    await ensure_fully_defined(adapter, "integral-neck sketch")
    check("exit_sketch neck", await adapter.exit_sketch())
    name_last_feature(adapter, "NeckProfile")
    drive_jobs += neck.apply(adapter, "NeckProfile")
    extrude_at_offset(adapter, NECK_LEN, HEAD_REAR_Z)
    name_last_feature(adapter, "Neck")
    drive_jobs.append((name_dimensions(adapter, "Neck", ["NeckLen"])[0], '"NeckLen"'))
    expected = V_NECK
    await volume_check(adapter, "integral neck", expected, 0.005 * V_NECK)

    shaft = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SHAFT_R,
        "exposed shaft",
        dims=shaft,
        names=("ShaftCx", "ShaftCz", "ShaftDia"),
        drives=(None, None, '"ShaftDia"'),
    )
    await ensure_fully_defined(adapter, "exposed-shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += shaft.apply(adapter, "ShaftProfile")
    extrude_at_offset(adapter, EXPOSED_SHAFT_LEN, NECK_END_Z)
    name_last_feature(adapter, "Shaft")
    drive_jobs.append(
        (name_dimensions(adapter, "Shaft", ["ExposedShaftLen"])[0], '"ExposedShaftLen"')
    )
    expected += V_SHAFT
    await volume_check(adapter, "neck and exposed shaft", expected, 0.005 * V_SHAFT)

    head = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        HEAD_R,
        "integral head",
        dims=head,
        names=("HeadCx", "HeadCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "integral-head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    extrude_at_offset(adapter, HEAD_LEN, HEAD_FRONT_Z)
    name_last_feature(adapter, "Head")
    drive_jobs.append((name_dimensions(adapter, "Head", ["HeadLen"])[0], '"HeadLen"'))
    expected += V_HEAD
    await volume_check(adapter, "integral head", expected, 0.005 * V_HEAD)

    # Front crown: Top-plane sketch coordinates map v=-Z, so the negative-Z
    # head end appears at positive v.  Rim-to-apex is the minor CCW arc.
    front_v_base = -HEAD_FRONT_Z
    front_v_apex = front_v_base + HEAD_CAP_SAG
    front_v_center = front_v_apex - HEAD_CAP_R
    front_cap = SketchDims()
    check("create_sketch front cap", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    check(
        "front cap centerline",
        await adapter.add_centerline(0.0, front_v_base, 0.0, front_v_apex),
    )
    front_base = check(
        "front cap base", await adapter.add_line(0.0, front_v_base, HEAD_R, front_v_base)
    )
    front_arc = check(
        "front cap arc",
        await adapter.add_arc(
            0.0, front_v_center, HEAD_R, front_v_base, 0.0, front_v_apex
        ),
    )
    front_close = check(
        "front cap close", await adapter.add_line(0.0, front_v_apex, 0.0, front_v_base)
    )
    set_sketch_direct_db(adapter, False)
    check("front cap base horizontal", await adapter.add_sketch_constraint(front_base, None, "horizontal"))
    check("front cap close vertical", await adapter.add_sketch_constraint(front_close, None, "vertical"))
    check(
        "front cap rim reach",
        await adapter.add_sketch_dimension(
            f"{front_base}.end", "origin", "horizontal_distance", HEAD_R
        ),
    )
    front_cap.record("HeadCapRim", '"HeadDia" / 2')
    check(
        "front cap sagitta",
        await adapter.add_sketch_dimension(
            f"{front_close}.start",
            f"{front_close}.end",
            "vertical_distance",
            HEAD_CAP_SAG,
        ),
    )
    front_cap.record("HeadCapSagDim", '"HeadCapSag"')
    check(
        "front cap on axis",
        await adapter.add_sketch_constraint(f"{front_base}.start", "origin", "vertical_points"),
    )
    check(
        "front cap station",
        await adapter.add_sketch_dimension(
            f"{front_base}.start", "origin", "vertical_distance", front_v_base
        ),
    )
    front_cap.record("HeadFrontZDim", '-"HeadFrontZ"')
    check(
        "front cap radius",
        await adapter.add_sketch_dimension(front_arc, None, "radial", HEAD_CAP_R),
    )
    front_cap.record(
        "HeadCapR",
        '("HeadDia" / 2 * "HeadDia" / 2 + "HeadCapSag" * "HeadCapSag") / (2 * "HeadCapSag")',
    )
    await ensure_fully_defined(adapter, "front-cap sketch")
    check("exit_sketch front cap", await adapter.exit_sketch())
    name_last_feature(adapter, "FrontCapProfile")
    drive_jobs += front_cap.apply(adapter, "FrontCapProfile")
    check(
        "revolve front cap", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "FrontCap")
    expected += V_FRONT_CAP
    await volume_check(adapter, "front crown", expected, 0.03 * V_FRONT_CAP)

    cross_hole = SketchDims()
    check("create_sketch cross hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        -HEAD_CENTER_Z,
        CROSS_HOLE_R,
        "grip cross-hole",
        dims=cross_hole,
        names=("CrossHoleCx", "HeadCenterZ", "CrossHoleDia"),
        drives=(None, '-("HeadFrontZ" + "HeadLen" / 2)', '"CrossHoleDia"'),
    )
    await ensure_fully_defined(adapter, "grip-cross-hole sketch")
    check("exit_sketch cross hole", await adapter.exit_sketch())
    name_last_feature(adapter, "CrossHoleProfile")
    drive_jobs += cross_hole.apply(adapter, "CrossHoleProfile")
    check(
        "cut grip cross-hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HEAD_DIA + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CrossHole")
    expected -= V_CROSS_HOLE
    await volume_check(adapter, "grip cross-hole", expected, 0.02 * V_CROSS_HOLE)

    back_v_base = -SHAFT_LEN
    back_v_apex = -(SHAFT_LEN + BACK_CAP_SAG)
    back_v_center = -(SHAFT_LEN + BACK_CAP_SAG - BACK_CAP_R)
    back_cap = SketchDims()
    check("create_sketch back cap", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    check(
        "back cap centerline",
        await adapter.add_centerline(0.0, back_v_base, 0.0, back_v_apex),
    )
    back_base = check(
        "back cap base", await adapter.add_line(0.0, back_v_base, SHAFT_R, back_v_base)
    )
    back_arc = check(
        "back cap arc",
        await adapter.add_arc(
            0.0, back_v_center, 0.0, back_v_apex, SHAFT_R, back_v_base
        ),
    )
    back_close = check(
        "back cap close", await adapter.add_line(0.0, back_v_apex, 0.0, back_v_base)
    )
    set_sketch_direct_db(adapter, False)
    check("back cap base horizontal", await adapter.add_sketch_constraint(back_base, None, "horizontal"))
    check("back cap close vertical", await adapter.add_sketch_constraint(back_close, None, "vertical"))
    check(
        "back cap rim reach",
        await adapter.add_sketch_dimension(
            f"{back_base}.end", "origin", "horizontal_distance", SHAFT_R
        ),
    )
    back_cap.record("BackCapRim", '"ShaftDia" / 2')
    check(
        "back cap sagitta",
        await adapter.add_sketch_dimension(
            f"{back_close}.start",
            f"{back_close}.end",
            "vertical_distance",
            BACK_CAP_SAG,
        ),
    )
    back_cap.record("BackCapSagDim", '"BackCapSag"')
    check(
        "back cap on axis",
        await adapter.add_sketch_constraint(f"{back_base}.start", "origin", "vertical_points"),
    )
    check(
        "back cap station",
        await adapter.add_sketch_dimension(
            f"{back_base}.start", "origin", "vertical_distance", SHAFT_LEN
        ),
    )
    back_cap.record("BackCapZ", '"ShaftLen"')
    check(
        "back cap radius",
        await adapter.add_sketch_dimension(back_arc, None, "radial", BACK_CAP_R),
    )
    back_cap.record(
        "BackCapR",
        '("ShaftDia" / 2 * "ShaftDia" / 2 + "BackCapSag" * "BackCapSag") / (2 * "BackCapSag")',
    )
    await ensure_fully_defined(adapter, "back-cap sketch")
    check("exit_sketch back cap", await adapter.exit_sketch())
    name_last_feature(adapter, "BackCapProfile")
    drive_jobs += back_cap.apply(adapter, "BackCapProfile")
    check(
        "revolve back cap", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "BackCap")
    expected += V_BACK_CAP
    await volume_check(adapter, "back crown", expected, 0.03 * V_BACK_CAP)

    # R1a: the MHA-144 collar's 1/16 in spring-pin hole, through the Ø8 on
    # the crossrod's local Y (one V-block setup drills both cross holes).
    pin_hole = SketchDims()
    check("create_sketch collar pin hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        -PIN_Z,
        PIN_HOLE_R,
        "collar pin hole",
        dims=pin_hole,
        names=("PinHoleCx", "PinHoleZ", "PinHoleDia"),
        drives=(
            None,
            '"HeadCenterZ" + "HeadLen" / 2 + "PinStationFromHeadRear"',
            '"PinHoleDia"',
        ),
    )
    await ensure_fully_defined(adapter, "collar-pin-hole sketch")
    check("exit_sketch collar pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_hole.apply(adapter, "PinHoleProfile")
    check(
        "cut collar pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SHAFT_DIA + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    expected -= V_PIN_HOLE
    await volume_check(adapter, "collar pin hole", expected, 0.05 * V_PIN_HOLE)
    _require_one_solid_body(adapter, label="integral pinion arbor")

    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "arbor axis")
    drive_jobs += await _add_axial_reference(
        adapter,
        feature_name="BackRimReference",
        dimension_name="BackRimFromHeadRear",
        start_v=-HEAD_REAR_Z,
        end_v=-SHAFT_LEN,
        drive_expression='"BackRimFromHeadRear"',
    )
    drive_jobs += await _add_axial_reference(
        adapter,
        feature_name="DrumStationReference",
        dimension_name="DrumStationFromHeadRear",
        start_v=-HEAD_REAR_Z,
        end_v=-(HEAD_REAR_Z + DRUM_STATION),
        drive_expression='"DrumStationFromHeadRear"',
        end_on_flank=DRUM_STATION_POINT_X,
    )
    # The pin station ends on the axis at the hole's centre: the sheet's
    # witness rises from the hole's own centre mark.
    drive_jobs += await _add_axial_reference(
        adapter,
        feature_name="PinStationReference",
        dimension_name="PinStationFromHeadRear",
        start_v=-HEAD_REAR_Z,
        end_v=-PIN_Z,
        drive_expression='"PinStationFromHeadRear"',
    )
    drive_jobs += await _add_axial_reference(
        adapter,
        feature_name="OverallReference",
        dimension_name="OverallLen",
        start_v=-(HEAD_FRONT_Z - HEAD_CAP_SAG),
        end_v=-(SHAFT_LEN + BACK_CAP_SAG),
        drive_expression='"OverallLen"',
    )
    drive_jobs += await _add_journal_land(
        adapter,
        prefix="FrontJournal",
        journal_z=FRONT_JOURNAL_Z,
        station_expression='"FrontJournalFromHeadRear"',
    )
    drive_jobs += await _add_journal_land(
        adapter,
        prefix="BackJournal",
        journal_z=BACK_JOURNAL_Z,
        station_expression='"BackJournalFromHeadRear"',
    )
    if len(_shaft_faces(adapter)) != 5:
        raise RuntimeError("the Ø8 shaft must read as two journal lands and three plain zones")
    drive_jobs += await _add_bond_zone_reference(adapter)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven integral arbor (equations neutral)", V_TOTAL, 0.005 * V_SHAFT
    )
    _require_one_solid_body(adapter, label="driven integral pinion arbor")

    set_dimension_bilateral_tolerance(
        adapter, "BondZoneReference", "BondZoneDia", *deviations(SHAFT_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "CrossHoleProfile", "CrossHoleDia", *deviations(CROSS_HOLE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PinHoleProfile", "PinHoleDia", *deviations(PIN_HOLE_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "DrumStationReference", "DrumStationFromHeadRear", DRUM_STATION_BAND
    )
    set_dimension_bilateral_tolerance(
        adapter, "FrontJournalReference", "FrontJournalDia", *deviations(JOURNAL_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BackJournalReference", "BackJournalDia", *deviations(JOURNAL_DIA_BAND)
    )
    # A diametric linear dimension on a side-view sketch prints no Ø by itself.
    for prefix in ("FrontJournal", "BackJournal", "BondZone"):
        set_dimension_prefix(adapter, f"{prefix}Reference", f"{prefix}Dia", "<MOD-DIAM>")
    set_dimension_prefix(adapter, "FrontCapProfile", "HeadCapR", "SR")
    set_dimension_prefix(adapter, "BackCapProfile", "BackCapR", "SR")
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
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
