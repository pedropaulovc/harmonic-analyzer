"""Build the custom MHA-VN-016 collar and reworked 94355A213 set screw.

Default contains both bodies in the installed pose; Collar and SetScrew are
manufacturing configurations. Threads are native cosmetic/Hole Wizard
features, not a vendor-model claim. Only the ground dog is reworked; retained
stock socket geometry is pictorial and excluded from manufacturing marks.
"""

from __future__ import annotations

import math
import sys

import _config
import vn_cone_tip_collar_spec as spec
from _common import (
    SketchDims, _early_bound, _feature_by_name, active_configuration_name,
    assert_saved_configurations_regenerate,
    add_line_chain, apply_material, check, define_circle, define_rectilinear_chain, dimension_between,
    drive_dimension, ensure_fully_defined, force_rebuild, name_bore_axis,
    name_dimensions, name_last_feature, report_mass_properties, run_build,
    save_part_and_images, set_global, set_sketch_direct_db, volume_check,
)
from _drawing_marks import (
    _named_dimension, add_diametric_linear_dimension, apply_drawing_precision,
    apply_drawing_properties, clear_dimensions_for_drawing,
    mark_dimensions_for_drawing, set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _grouped_bom_properties import apply_grouped_bom_properties
from _holes import wizard_holes
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry, blank_sketch_feature
from diagnostics.diag_mcmaster_lib import offset_plane
from solidworks_mcp.adapters.com_variant import null_variant

PART_NAME = "vn-cone-tip-collar"
MATERIAL = "Plain Carbon Steel"
CONFIGURATIONS = ("Default", "Collar", "SetScrew")
COLLAR_FEATURES = (
    "Ring", "BodyPlane", "Body", "RingEdgeBreak", "ShoulderRoot",
    "MountFlat", "FlatEdgeBreak", "SetScrewTap", "TapMouthBreak",
    "TapRootPlane", "TapRootGauge",
)
SCREW_FEATURES = ("SetScrew", "DogEdgeBreak", "StockEndBreak", "HexSocket")


def _plane(adapter, name, offset, *, base="Top Plane"):
    offset_plane(adapter, name, offset, base=base)
    feature = _feature_by_name(adapter, name)
    if str(feature.Name) != name or str(feature.GetTypeName2()) != "RefPlane":
        raise RuntimeError(f"collar native reference plane {name} was not created/named")


async def _ring(adapter, jobs):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
    check("ring sketch", await adapter.create_sketch("Top"))
    for name, dia in (("NoseDia", spec.NOSE_DIA), ("BoreDia", spec.BORE_MODEL_DIA_MM)):
        await define_circle(
            adapter, 0.0, 0.0, dia / 2.0, name, dims=dims,
            names=(None, None, name), drives=(None, None, f'"{name}"'),
        )
    await ensure_fully_defined(adapter, "collar ring")
    check("exit ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    jobs.extend(dims.apply(adapter, "RingProfile"))
    check("extrude ring", await adapter.create_extrusion(ExtrusionParameters(depth=spec.WIDTH)))
    name_last_feature(adapter, "Ring")
    jobs.append((name_dimensions(adapter, "Ring", ["CollarWidth"])[0], '"CollarWidth"'))
    nose_area = math.pi / 4.0 * (spec.NOSE_DIA**2 - spec.BORE_MODEL_DIA_MM**2)
    await volume_check(adapter, "nose annulus", nose_area * spec.WIDTH, 0.005 * nose_area * spec.WIDTH)
    _plane(adapter, "BodyPlane", spec.NOSE_LENGTH)
    jobs.append((name_dimensions(adapter, "BodyPlane", ["NoseLength"])[0], '"NoseLength"'))
    check("large body sketch", await adapter.create_sketch("BodyPlane"))
    dims = SketchDims()
    for name, dia, expression in (
        ("CollarDia", spec.OUTER_DIA, '"CollarDia"'),
        ("BodyBoreDia", spec.BORE_MODEL_DIA_MM, '"BoreDia"'),
    ):
        await define_circle(
            adapter, 0.0, 0.0, dia / 2.0, name, dims=dims,
            names=(None, None, name), drives=(None, None, expression),
        )
    await ensure_fully_defined(adapter, "large collar body")
    check("exit body", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    jobs.extend(dims.apply(adapter, "BodyProfile"))
    check("merge large body", await adapter.create_extrusion(ExtrusionParameters(
        depth=spec.WIDTH - spec.NOSE_LENGTH,
    )))
    name_last_feature(adapter, "Body")
    jobs.append((name_dimensions(adapter, "Body", ["BodyWidth"])[0], '"CollarWidth" - "NoseLength"'))
    expected = nose_area * spec.WIDTH + math.pi / 4.0 * (
        spec.OUTER_DIA**2 - spec.NOSE_DIA**2
    ) * (spec.WIDTH - spec.NOSE_LENGTH)
    await volume_check(adapter, "stepped collar annulus", expected, 0.005 * expected)
    check("ring edge breaks", await adapter.add_chamfer(
        spec.EDGE_BREAK,
        [[spec.BORE_MODEL_DIA_MM / 2.0, y, 0.0] for y in (0.0, spec.WIDTH)]
        + [[spec.NOSE_DIA / 2.0, 0.0, 0.0]]
        + [[spec.OUTER_DIA / 2.0, y, 0.0] for y in (spec.NOSE_LENGTH, spec.WIDTH)],
    ))
    name_last_feature(adapter, "RingEdgeBreak")
    name_dimensions(adapter, "RingEdgeBreak", ["CollarEdge"])
    jobs.append(("CollarEdge@RingEdgeBreak", '"CollarEdge"'))
    check("turned shoulder tool root", await adapter.add_fillet(
        spec.SHOULDER_ROOT_RADIUS, [[spec.NOSE_DIA / 2.0, spec.NOSE_LENGTH, 0.0]],
    ))
    name_last_feature(adapter, "ShoulderRoot")
    name_dimensions(adapter, "ShoulderRoot", ["ShoulderRadius"])
    jobs.append(("ShoulderRadius@ShoulderRoot", '"ShoulderRadius"'))

    # A real full-length flat is the planar Hole Wizard placement face.
    # Its axis offset is routine .XX, not a hidden spotface depth assumption.
    check("mount flat sketch", await adapter.create_sketch("Front"))
    points = [(spec.FLAT_DISTANCE, -1.0), (spec.OUTER_DIA, -1.0),
              (spec.OUTER_DIA, spec.WIDTH + 1.0), (spec.FLAT_DISTANCE, spec.WIDTH + 1.0)]
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    dims = SketchDims()
    await define_rectilinear_chain(
        adapter, lines, points, label="mount flat", dims=dims,
        names=[None, None, "FlatDistance", None],
        drives=[None, None, '"FlatDistance"', None],
    )
    await ensure_fully_defined(adapter, "mount flat")
    check("exit flat", await adapter.exit_sketch())
    name_last_feature(adapter, "MountFlatProfile")
    jobs.extend(dims.apply(adapter, "MountFlatProfile"))
    check("cut flat", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=spec.OUTER_DIA, both_directions=True,
    )))
    name_last_feature(adapter, "MountFlat")
    flat_corner = math.sqrt((spec.OUTER_DIA / 2.0)**2 - spec.FLAT_DISTANCE**2)
    check("mount flat edge breaks", await adapter.add_chamfer(
        spec.EDGE_BREAK,
        [[spec.FLAT_DISTANCE, y, 0.0] for y in (spec.NOSE_LENGTH, spec.WIDTH)]
        + [[spec.FLAT_DISTANCE, spec.TAP_STATION, z] for z in (-flat_corner, flat_corner)],
    ))
    name_last_feature(adapter, "FlatEdgeBreak")
    name_dimensions(adapter, "FlatEdgeBreak", ["FlatEdge"])
    jobs.append(("FlatEdge@FlatEdgeBreak", '"CollarEdge"'))
    hole = wizard_holes(
        adapter, spec.SET_SCREW_HOLE, [(spec.FLAT_DISTANCE, spec.TAP_STATION, 0.0)],
        (1.0, 0.0, 0.0), "collar set screw", name="SetScrewTap",
        expect_dia_mm=spec.TAP_DRILL_DIA,
        placement_dims=[((None, None), ("TapStation", '"TapStation"'))],
    )
    jobs.extend(hole.placement_drive_jobs)
    check("radial tap mouth break", await adapter.add_chamfer(
        spec.EDGE_BREAK,
        [[spec.FLAT_DISTANCE, spec.TAP_STATION + hole.hole_dia_mm / 2.0, 0.0]],
    ))
    name_last_feature(adapter, "TapMouthBreak")
    name_dimensions(adapter, "TapMouthBreak", ["TapEdge"])
    jobs.append(("TapEdge@TapMouthBreak", '"CollarEdge"'))
    # A manufacturing limit, not a fictional physical root cut: 2B alone has
    # no root MAX. This source-native gauge dimension controls the tap tool's
    # permitted envelope and is projected as MAX TAP ROOT on the drawing.
    _plane(adapter, "TapRootPlane", spec.FLAT_DISTANCE, base="Right Plane")
    check("tap root gauge sketch", await adapter.create_sketch("TapRootPlane"))
    dims = SketchDims()
    await define_circle(
        adapter, 0.0, spec.TAP_STATION, spec.THREAD_ENVELOPE_DIA / 2.0,
        "tap root maximum gauge", dims=dims,
        names=(None, "GaugeTapStation", "TapRootLimit"),
        drives=(None, '"TapStation"', '"TapRootLimit"'),
    )
    await ensure_fully_defined(adapter, "tap root maximum gauge")
    check("exit root gauge", await adapter.exit_sketch())
    name_last_feature(adapter, "TapRootGauge")
    jobs.extend(dims.apply(adapter, "TapRootGauge"))


async def _screw(adapter, jobs):
    from solidworks_mcp.adapters.base import AddThreadParameters, ExtrusionParameters, RevolveParameters

    y = spec.TAP_STATION
    x = spec.SET_SCREW_SEAT_RADIUS
    dog_r = spec.DOG_DIA / 2.0
    screw_r = spec.SET_SCREW_MAJOR_DIA / 2.0
    end = spec.SET_SCREW_END_RADIUS
    points = [(x, y), (x, y + dog_r), (x + spec.DOG_LENGTH, y + dog_r),
              (x + spec.DOG_LENGTH, y + screw_r), (end, y + screw_r), (end, y)]
    check("ground screw profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("screw axis", await adapter.add_centerline(0.0, y, end + 1.0, y))
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    dims = SketchDims()
    # The stock envelope is fixed; only the ground dog's actual dimensions
    # are driving manufacturing dimensions. Fix the stock/profile endpoints,
    # not the dog itself, then dimension its length and doubled radius.
    for line in (lines[4], lines[5], axis):
        check("fix retained stock profile", await adapter.add_sketch_constraint(line, None, "fix"))
    for index, direction in ((0, "vertical"), (1, "horizontal"), (2, "vertical"), (3, "horizontal")):
        check("ground profile direction", await adapter.add_sketch_constraint(lines[index], None, direction))
    await dimension_between(adapter, f"{lines[1]}.start", f"{lines[1]}.end",
                            "horizontal_distance", spec.DOG_LENGTH, "ground dog length")
    dims.record("DogLength", '"DogLength"')
    display = await add_diametric_linear_dimension(adapter, axis, lines[1], (x + 0.5, y + 2.0), "ground dog diameter")
    dim = _early_bound(display.GetDimension2(0), "IDimension")
    if abs(float(dim.SystemValue) * 1000.0 - spec.DOG_DIA) > 1e-6:
        raise RuntimeError("ground dog native diameter differs from the contract")
    dims.record("DogDia", '"DogDia"')
    await ensure_fully_defined(adapter, "ground screw profile")
    check("exit screw profile", await adapter.exit_sketch())
    name_last_feature(adapter, "SetScrewProfile")
    jobs.extend(dims.apply(adapter, "SetScrewProfile"))
    check("revolve separate screw body", await adapter.create_revolve(RevolveParameters(
        angle=360.0, merge_result=False,
    )))
    name_last_feature(adapter, "SetScrew")
    check("ground dog edge break", await adapter.add_chamfer(
        spec.DOG_EDGE_BREAK, [[x, y + dog_r, 0.0]],
    ))
    name_last_feature(adapter, "DogEdgeBreak")
    name_dimensions(adapter, "DogEdgeBreak", ["DogEdge"])
    check("supplied socket-end break", await adapter.add_chamfer(
        spec.SET_SCREW_END_BREAK, [[end, y + screw_r, 0.0]],
    ))
    name_last_feature(adapter, "StockEndBreak")
    # A native external thread keeps the stock thread identity on the model.
    check("stock screw thread", await adapter.add_thread(AddThreadParameters(
        edge_point=[end - spec.SET_SCREW_END_BREAK, y + screw_r, 0.0], standard="ansi_inch",
        size=spec.SET_SCREW_THREAD, end_type="blind",
        depth=spec.SET_SCREW_LENGTH - spec.DOG_LENGTH - spec.SET_SCREW_END_BREAK,
    )))
    _plane(adapter, "SocketFace", end, base="Right Plane")
    check("stock socket sketch", await adapter.create_sketch("SocketFace"))
    a = spec.SET_SCREW_SOCKET_AF / 2.0
    r = spec.SET_SCREW_SOCKET_AF / math.sqrt(3.0)
    set_sketch_direct_db(adapter, True)
    socket = await add_line_chain(adapter, [(0.0, y+r), (-a, y+r/2.0), (-a, y-r/2.0),
                                           (0.0, y-r), (a, y-r/2.0), (a, y+r/2.0)])
    set_sketch_direct_db(adapter, False)
    for line in socket:
        check("fix retained stock hex", await adapter.add_sketch_constraint(line, None, "fix"))
    check("exit stock socket", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketProfile")
    check("cut retained stock socket", await adapter.create_cut_extrude(ExtrusionParameters(depth=spec.SET_SCREW_SOCKET_DEPTH)))
    name_last_feature(adapter, "HexSocket")


def _activate_configuration(adapter, name):
    """Read native state before switching: already-active SW2026 can return False."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if active_configuration_name(adapter, model) != name and model.ShowConfiguration2(name) is not True:
        raise RuntimeError(f"cannot activate collar configuration {name}")
    if active_configuration_name(adapter, model) != name:
        raise RuntimeError(f"collar configuration {name} did not remain active")


def _manufacturing_configurations(adapter):
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    for name, suppressed in (("Collar", SCREW_FEATURES), ("SetScrew", COLLAR_FEATURES)):
        _activate_configuration(adapter, "Default")
        if manager.AddConfiguration2(name, "Manufacturing component", "", 0, "Default", "", False) is None:
            raise RuntimeError(f"cannot create {name} manufacturing configuration")
        _activate_configuration(adapter, name)
        # Suppress dependents before their parents, in this configuration only.
        for feature in reversed(suppressed):
            native = _feature_by_name(adapter, feature)
            if native.SetSuppression2(0, 1, null_variant()) is not True:
                raise RuntimeError(f"cannot suppress {feature} in {name}")
            states = native.IsSuppressed2(1, null_variant())
            if not isinstance(states, (tuple, list)) or len(states) != 1 or states[0] is not True:
                raise RuntimeError(f"{feature}: actual suppression did not persist in {name}")
    _activate_configuration(adapter, "Default")


def _functional_dimension_types(adapter):
    """Author part-owned BASIC location and MAX root process limit."""
    for feature, name, kind in (
        ("SetScrewTap", "TapStation", 1),  # swTolBASIC
        ("TapRootGauge", "TapRootLimit", 6),  # swTolMAX
    ):
        _display, dimension = _named_dimension(adapter, feature, name)
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = kind
        if int(tolerance.Type) != kind:
            raise RuntimeError(f"{name}@{feature}: native tolerance type did not persist")

def _configuration_bom_identity(adapter):
    apply_grouped_bom_properties(
        adapter, ("Default",), part_number=str(_config.parts(PART_NAME)["number"]),
        description=str(_config.parts(PART_NAME)["description"]),
    )
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    for name, description in spec.MANUFACTURING_DESCRIPTIONS.items():
        raw = model.GetConfigurationByName(name)
        if raw is None:
            raise RuntimeError(f"missing manufacturing identity configuration {name}")
        configuration = _early_bound(raw, "IConfiguration")
        configuration.Description = description
        configuration.UseDescriptionInBOM = True
        if str(configuration.Description) != description or configuration.UseDescriptionInBOM is not True:
            raise RuntimeError(f"{name}: manufacturing description did not persist")



async def build(adapter) -> dict[str, str]:
    check("create custom collar", await adapter.create_part())
    for name, value in (("CollarDia", spec.OUTER_DIA), ("BoreDia", spec.BORE_MODEL_DIA_MM),
                        ("NoseDia", spec.NOSE_DIA), ("NoseLength", spec.NOSE_LENGTH),
                        ("ShoulderRadius", spec.SHOULDER_ROOT_RADIUS),
                        ("TapStation", spec.TAP_STATION),
                        ("CollarWidth", spec.WIDTH), ("FlatDistance", spec.FLAT_DISTANCE),
                        ("DogDia", spec.DOG_DIA), ("DogLength", spec.DOG_LENGTH),
                        ("CollarEdge", spec.EDGE_BREAK), ("TapRootLimit", spec.THREAD_ENVELOPE_DIA)):
        await set_global(adapter, name, f"{value}mm")
    jobs = []
    await _ring(adapter, jobs)
    await _screw(adapter, jobs)
    await force_rebuild(adapter)
    for name, expression in jobs:
        await drive_dimension(adapter, name, expression)
    await force_rebuild(adapter)
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "collar axis")
    # Free round-bore construction reference; NOT the installed shaft axis.
    name_last_feature(adapter, "ScrewAxis")
    # Distinct from the free ROUND bore: this reference is the retained SHAFT
    # axis in the nonconcentric loaded representative. Assembly mates this
    # axis, not ScrewAxis, so two finite -X BACK arc contacts remain real.
    await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane",
        -spec.INSTALLED_BORE_AXIS_OFFSET_MM, "loaded shaft axis",
    )
    name_last_feature(adapter, "InstalledShaftAxis")
    set_dimension_bilateral_tolerance(adapter, "RingProfile", "BoreDia", *deviations(spec.BORE_MODEL_DIA_BAND))
    set_dimension_bilateral_tolerance(adapter, "SetScrewProfile", "DogDia", *deviations(spec.DOG_DIA_BAND))
    set_dimension_bilateral_tolerance(adapter, "RingEdgeBreak", "CollarEdge", *deviations(spec.EDGE_BREAK_BAND))
    set_dimension_bilateral_tolerance(adapter, "ShoulderRoot", "ShoulderRadius", *deviations(spec.SHOULDER_ROOT_BAND))
    set_dimension_bilateral_tolerance(adapter, "DogEdgeBreak", "DogEdge", *deviations(spec.DOG_EDGE_BAND))
    _functional_dimension_types(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    apply_drawing_properties(adapter, PART_NAME, {
        "Description": spec.BOM_DESCRIPTION,
        "Manufacturing Notes": spec.DRAWING_NOTES,
        "Installation Notes": spec.INSTALLATION_NOTES,
        "Isometric View Note": spec.ISOMETRIC_VIEW_NOTE,
        "Radial Tap View Note": spec.RADIAL_TAP_VIEW_NOTE,
        "Bore View Note": spec.BORE_VIEW_NOTE,
    })
    _manufacturing_configurations(adapter)
    _configuration_bom_identity(adapter)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    for configuration in CONFIGURATIONS:
        _activate_configuration(adapter, configuration)
        await apply_material(adapter, "AISI 304" if configuration == "SetScrew" else MATERIAL)
        await force_rebuild(adapter)
        bodies = _early_bound(model, "IPartDoc").GetBodies2(0, False) or ()
        expected = 2 if configuration == "Default" else 1
        if len(bodies) != expected:
            raise RuntimeError(f"{configuration} has {len(bodies)} solids, expected {expected}")
        for body in bodies:
            native = _early_bound(body, "IBody2")
            bounds = tuple(float(value) for value in native.GetBodyBox())
            if len(bounds) != 6 or not all(math.isfinite(value) for value in bounds):
                raise RuntimeError(f"{configuration}: actual body bounds are unavailable/non-finite")
            is_screw = bounds[1] > 0.001
            material = "AISI 304" if is_screw else MATERIAL
            if native.SetMaterialProperty(configuration, "", material) != 1:
                raise RuntimeError(f"{configuration}: cannot assign {material} to its body")
            observed, _database = native.GetMaterialPropertyName(configuration)
            if str(observed) != material:
                raise RuntimeError(f"{configuration}: body material {observed!r} != {material}")
    _activate_configuration(adapter, "Default")
    author_part_pmi(adapter, datums=spec.PART_DATUMS, controls=spec.GEOMETRIC_CONTROLS)
    blank_sketch_feature(model, _feature_by_name(adapter, "TapRootGauge"), "tap root limit gauge")
    blank_reference_geometry(adapter, (
        ("ScrewAxis", "AXIS"), ("InstalledShaftAxis", "AXIS"), ("SocketFace", "PLANE"),
        ("TapRootPlane", "PLANE"), ("BodyPlane", "PLANE"),
    ))
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    # The part saves on Default while its Collar/SetScrew manufacturing
    # configurations keep their own saved caches; reopen and prove every one
    # regenerates as loaded, like every multi-configuration builder (cg-fx1).
    part_title = str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
    adapter.swApp.CloseDoc(part_title)
    adapter.currentModel = None
    check("reopen saved cone-tip collar", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, PART_NAME)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
