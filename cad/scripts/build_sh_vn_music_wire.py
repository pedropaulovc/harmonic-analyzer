r"""McMaster 9666K56 music wire, with the two existing straight rest-run members.

LeverWire retains the drum-origin frame, midpoint balloon edge, hook/hub
reference points and wire axis. PenWire retains the eye-origin frame and its
independent length. Neither member defines wraps, tie-offs or a developed cut
length; the purchased package drawing prints only the supplier wire diameter
from the zero-body SUPPLIER_REFERENCE state. Geometry is not supplier redesign.

The lever endpoint/yoke solver lives in ``sh_vn_music_wire_lever_geom``. Its
wheel mid-plane is the pen-rod line ``_recording_geometry.PEN_Z_MID``; recording
anchors do not bring the paper-feed checks into the wire's geometry closure.
"""

from __future__ import annotations

import math
import sys

import _config
import sh_vn_music_wire_lever_geom as lever
import sh_vn_music_wire_lever_spec as lever_spec
import sh_vn_music_wire_pen_geom as pen
import sh_vn_music_wire_pen_spec as pen_spec
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _com_invoke, _early_bound
from _custom_properties import apply_custom_properties
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing
from _feature_tree import _feature_by_name, feature_name_by_type, name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _purchased_part_variants import (
    activate_member,
    apply_member_properties,
    assert_member_properties,
    assert_member_suppression,
    create_member_configurations,
    require_member_bodies,
    require_member_configurations,
    save_member_part,
    select_member_features,
)
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _mcmaster_9666k56 import SKU
from _sketch_circle import define_circle
from _visibility import assert_reference_geometry_hidden, blank_reference_geometry
from _supplier_wire_stock import author_nominal_stock_cross_section
from solidworks_mcp.adapters.pywin32_adapter import null_callout

PART_NAME = "sh-vn-music-wire"
MATERIAL = "Plain Carbon Steel"
CONFIGURATIONS = (lever.CONFIGURATION, pen.CONFIGURATION)
WIRE_DIA = lever.WIRE_DIA
WIRE_LEN = lever.WIRE_LEN
BALLOON_RING_FRACTION = lever_spec.BALLOON_RING_FRACTION
BALLOON_RING_STATION = BALLOON_RING_FRACTION * WIRE_LEN
_SPLIT_OVERHANG = 0.5
_CYLINDER_IDENTITY = 4002  # swSurfaceTypes_e.CYLINDER_TYPE
MEMBER_FEATURES = {
    lever.CONFIGURATION: (
        "BalloonRingReference",
        "BalloonRingSplit",
        "HookPoint",
        "HubPoint",
    ),
    pen.CONFIGURATION: (),
}
DESCRIPTIONS = {
    lever.CONFIGURATION: lever_spec.BOM_DESCRIPTION,
    pen.CONFIGURATION: pen_spec.BOM_DESCRIPTION,
}
# The one package note: the purchase identity. The diameter is the native
# supplier dimension on the drawing, never note text.
DRAWING_NOTES = f"PURCHASED WIRE: McMASTER-CARR {SKU}"

if not math.isclose(WIRE_DIA, pen.WIRE_DIA, abs_tol=1e-12):
    raise ValueError("the two 9666K56 members must retain their shared stock diameter")


def _wire_cylinder_areas(adapter) -> list[tuple[object, float]]:
    """Every Ø WIRE_DIA cylinder face of the body with its area in mm^2."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    faces: list[tuple[object, float]] = []
    for body in part.GetBodies2(0, False) or ():
        face = _early_bound(body, "IBody2").GetFirstFace()
        while face is not None:
            surface = _com_invoke(face, "IFace2", "GetSurface")
            if (
                surface is not None
                and int(_com_invoke(surface, "ISurface", "Identity"))
                == _CYLINDER_IDENTITY
                and math.isclose(
                    float(tuple(_com_invoke(surface, "ISurface", "CylinderParams"))[6])
                    * 1000.0,
                    WIRE_DIA / 2.0,
                    abs_tol=1e-4,
                )
            ):
                faces.append(
                    (face, float(_early_bound(face, "IFace2").GetArea()) * 1e6)
                )
            face = _early_bound(face, "IFace2").GetNextFace()
    return faces


async def _add_balloon_ring(adapter) -> list[tuple[str, str]]:
    """Preserve the shape-neutral projected midpoint split on the lever member."""
    reach = WIRE_DIA / 2.0 + _SPLIT_OVERHANG
    dims = SketchDims()
    check("create_sketch balloon ring", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "balloon ring axis",
        await adapter.add_centerline(0.0, 0.0, 0.0, BALLOON_RING_STATION),
    )
    split = check(
        "balloon ring split line",
        await adapter.add_line(
            -reach, BALLOON_RING_STATION, reach, BALLOON_RING_STATION
        ),
    )
    set_sketch_direct_db(adapter, False)
    for entity, relation in ((axis, "vertical"), (split, "horizontal")):
        check(
            f"balloon ring {entity} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    check(
        "balloon ring split centred on the axis",
        await adapter.add_sketch_constraint(f"{axis}.end", split, "midpoint"),
    )
    await anchor_point_to_origin(
        adapter, f"{axis}.start", 0.0, 0.0, "balloon ring axis on the drum end"
    )
    await dimension_between(
        adapter,
        f"{axis}.start",
        f"{axis}.end",
        "vertical_distance",
        BALLOON_RING_STATION,
        "balloon ring station",
    )
    dims.record("BalloonRingStation", f'"WireLength" * {BALLOON_RING_FRACTION}')
    await dimension_between(
        adapter,
        f"{split}.start",
        f"{split}.end",
        "horizontal_distance",
        2.0 * reach,
        "balloon ring split reach",
    )
    dims.record(None, None)
    await ensure_fully_defined(adapter, "balloon ring sketch")
    check("exit_sketch balloon ring", await adapter.exit_sketch())
    name_last_feature(adapter, "BalloonRingReference")
    drive_jobs = dims.apply(adapter, "BalloonRingReference")

    before = _wire_cylinder_areas(adapter)
    if len(before) != 1:
        raise RuntimeError(
            f"BalloonRingSplit: expected the one wire cylinder, got {len(before)}"
        )
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "BalloonRingReference", "SKETCH", 0.0, 0.0, 0.0, False, 4, null_callout(), 0
    ):
        raise RuntimeError("BalloonRingSplit: failed to select the split sketch")
    selection_manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    selection_data = _early_bound(selection_manager.CreateSelectData(), "ISelectData")
    selection_data.Mark = 1
    if not _early_bound(before[0][0], "IEntity").Select4(True, selection_data):
        raise RuntimeError("BalloonRingSplit: failed to select the wire cylinder")
    previous = feature_name_by_type(adapter, "PLine")
    model.InsertSplitLineProject(False, False)
    model.ClearSelection2(True)
    created = feature_name_by_type(adapter, "PLine")
    if not created or created == previous:
        raise RuntimeError("BalloonRingSplit: projected split line was not created")
    _feature_by_name(adapter, created).Name = "BalloonRingSplit"
    _require_cylinder_areas(adapter, lever.CONFIGURATION)
    blank_sketch(adapter, "BalloonRingReference")
    return drive_jobs


def _require_cylinder_areas(adapter, configuration: str) -> None:
    length = lever.WIRE_LEN if configuration == lever.CONFIGURATION else pen.WIRE_LEN
    runs = (
        (BALLOON_RING_STATION, length - BALLOON_RING_STATION)
        if configuration == lever.CONFIGURATION
        else (length,)
    )
    areas = sorted(area for _face, area in _wire_cylinder_areas(adapter))
    expected = sorted(math.pi * WIRE_DIA * run for run in runs)
    if len(areas) != len(expected) or any(
        abs(got - want) > 0.01 * want for got, want in zip(areas, expected, strict=True)
    ):
        raise RuntimeError(
            f"{configuration}: wire cylinder areas {areas} mm^2, expected {expected}"
        )


async def _author_wire(adapter) -> list[tuple[str, str]]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    body = SketchDims()
    check("create_sketch wire", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        WIRE_DIA / 2.0,
        "wire",
        dims=body,
        names=("WireCx", "WireCz", "WireDiaDim"),
        drives=(None, None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire sketch")
    check("exit_sketch wire", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs = body.apply(adapter, "WireProfile")
    check(
        "extrude wire",
        await adapter.create_extrusion(ExtrusionParameters(depth=WIRE_LEN)),
    )
    name_last_feature(adapter, "Wire")
    length_dim = name_dimensions(adapter, "Wire", ["Depth"])
    drive_jobs.append((length_dim[0], '"WireLength"'))
    v_wire = math.pi * (WIRE_DIA / 2.0) ** 2 * WIRE_LEN
    await volume_check(adapter, "wire", v_wire, 0.005 * v_wire)
    return drive_jobs


async def _add_lever_wire_references(adapter) -> None:
    from solidworks_mcp.adapters.base import CreateReferencePointParameters

    check(
        "ref point HookPoint",
        await adapter.create_reference_point(
            CreateReferencePointParameters(
                mode="arc_center", edge_point=[WIRE_DIA / 2.0, WIRE_LEN, 0.0]
            )
        ),
    )
    name_last_feature(adapter, "HookPoint")
    check(
        "ref point HubPoint",
        await adapter.create_reference_point(
            CreateReferencePointParameters(
                mode="arc_center", edge_point=[WIRE_DIA / 2.0, 0.0, 0.0]
            )
        ),
    )
    name_last_feature(adapter, "HubPoint")
    blank_reference_geometry(
        adapter, (("HookPoint", "DATUMPOINT"), ("HubPoint", "DATUMPOINT"))
    )


async def _readback(adapter, configuration: str) -> None:
    assert_member_suppression(adapter, configuration, MEMBER_FEATURES)
    references = (
        ("Axis1", "HookPoint", "HubPoint")
        if configuration == lever.CONFIGURATION
        else ("Axis1",)
    )
    require_member_bodies(adapter, configuration, 1, references)
    length = lever.WIRE_LEN if configuration == lever.CONFIGURATION else pen.WIRE_LEN
    volume = math.pi * (WIRE_DIA / 2.0) ** 2 * length
    await volume_check(adapter, f"{configuration} wire", volume, 0.005 * volume)
    await bbox_extent_check(adapter, f"{configuration} length", "y", length)
    _require_cylinder_areas(adapter, configuration)
    assert_member_properties(
        adapter, PART_NAME, configuration, DESCRIPTIONS[configuration], {}
    )
    assert_reference_geometry_hidden(adapter, f"{PART_NAME} {configuration}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    require_member_configurations(PART_NAME, CONFIGURATIONS)
    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    await create_member_configurations(adapter, PART_NAME, CONFIGURATIONS)
    await activate_member(adapter, lever.CONFIGURATION)
    # All globals are born after the member configurations exist (IEquationMgr.Add3).
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    await set_global(adapter, "WireLength", f"{WIRE_LEN}mm")
    drive_jobs = await _author_wire(adapter)
    drive_jobs += await _add_balloon_ring(adapter)
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await _add_lever_wire_references(adapter)
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "wire axis")

    for configuration, geometry in (
        (lever.CONFIGURATION, lever),
        (pen.CONFIGURATION, pen),
    ):
        await select_member_features(adapter, configuration, MEMBER_FEATURES)
        check(
            f"WireLength in {configuration}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="WireLength",
                    expression=f"{geometry.WIRE_LEN}mm",
                    configuration=configuration,
                )
            ),
        )
        await force_rebuild(adapter)
        blank_sketch(adapter, "WireProfile")
        if configuration == lever.CONFIGURATION:
            blank_sketch(adapter, "BalloonRingReference")
            blank_reference_geometry(
                adapter, (("HookPoint", "DATUMPOINT"), ("HubPoint", "DATUMPOINT"))
            )
        blank_reference_geometry(adapter, (("Axis1", "AXIS"),))
        await apply_material(adapter, MATERIAL)
        apply_member_properties(
            adapter, PART_NAME, configuration, DESCRIPTIONS[configuration], {}
        )
        await report_mass_properties(adapter)

    clear_dimensions_for_drawing(adapter)
    # The supplier's .7874-mm stock circle lives only in its own zero-body
    # construction reference state; it is the package's one printed dimension.
    await author_nominal_stock_cross_section(adapter)
    row = _config.parts(PART_NAME)
    apply_custom_properties(
        adapter,
        {
            "Stock Name": str(row["stock_name"]),
            "Supplier": str(row["supplier"]),
            "Supplier SKUs": ", ".join(str(sku) for sku in row["supplier_skus"]),
        },
    )
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_member_part(
        adapter,
        PART_NAME,
        CONFIGURATIONS,
        material=MATERIAL,
        readback=_readback,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
