r"""Build MHA-152, the brass ferrule at the crank end of the handle.

User ruling 2026-09-29 (ch11 p.14/p.15 photographs): the bright ring between
the crank arm and the ebonized grip is a separate brass ferrule, epoxied on
the MHA-022 tenon and seated on its shoulder; its outer end face runs against
the arm.  Dimensions live in ``crank_handle_ferrule_spec``.

Layout: one revolve about local +X, in the handle's own frame -- the
arm-bearing face at x=0, the seat face at x=LENGTH -- so the drive train
places it with the handle's transform.  ``Axis1`` is the ferrule axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_handle_ferrule.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    SketchDims,
    _early_bound,
    active_configuration_name,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    assert_saved_configurations_regenerate,
    check,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
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
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from _configuration_material import require_material_in_every_configuration
from _grouped_bom_properties import apply_grouped_bom_properties
from solidworks_mcp.adapters.com_variant import bstr_array
from crank_handle_ferrule_spec import (
    BORE_DIA,
    BORE_DIA_TOL,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    INSTALLED_CONFIG,
    INSTALLED_OUTER_DIA,
    ISOMETRIC_VIEW_NOTE,
    LENGTH,
    OUTER_DIA,
)

PART_NAME = "crank-handle-ferrule"
MATERIAL = "Brass"  # the gears' gold; see _common.apply_material docstring

OUTER_R = OUTER_DIA / 2.0
BORE_R = BORE_DIA / 2.0
V_FERRULE = math.pi * (OUTER_R**2 - BORE_R**2) * LENGTH
INSTALLED_R = INSTALLED_OUTER_DIA / 2.0
V_INSTALLED = math.pi * (INSTALLED_R**2 - BORE_R**2) * LENGTH
_SKIM_MARGIN = 0.5


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_crankshaft).
    for name, value in (
        ("OuterDia", OUTER_DIA),
        ("BoreDia", BORE_DIA),
        ("Length", LENGTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Rectangular section on the Front plane, revolved about the X axis:
    # arm face -> OD -> seat face -> bore.
    profile = SketchDims()
    check("create_sketch ferrule profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "ferrule axis centerline",
        await adapter.add_centerline(0.0, 0.0, LENGTH, 0.0),
    )
    arm_face, outer, seat_face, bore = await add_line_chain(
        adapter,
        [(0.0, BORE_R), (0.0, OUTER_R), (LENGTH, OUTER_R), (LENGTH, BORE_R)],
    )
    set_sketch_direct_db(adapter, False)
    check("axis horizontal", await adapter.add_sketch_constraint(axis, None, "horizontal"))
    for label, entity, relation in (
        ("arm face", arm_face, "vertical"),
        ("OD", outer, "horizontal"),
        ("seat face", seat_face, "vertical"),
        ("bore", bore, "horizontal"),
    ):
        check(
            f"ferrule {label} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    check(
        "axis starts at the origin",
        await adapter.add_sketch_constraint(f"{axis}.start", "origin", "coincident"),
    )
    check(
        "arm face on the origin plane",
        await adapter.add_sketch_constraint(f"{arm_face}.start", "origin", "vertical_points"),
    )
    # Dimensions in creation order.
    check(
        "axis length",
        await adapter.add_sketch_dimension(axis, None, "linear", LENGTH),
    )
    profile.record("AxisLength", '"Length"')
    check(
        "ferrule length",
        await adapter.add_sketch_dimension(outer, None, "linear", LENGTH),
    )
    profile.record("Length", '"Length"')
    await add_diametric_linear_dimension(
        adapter, axis, outer, (LENGTH / 2.0, OUTER_R + 4.0), "OuterDia"
    )
    profile.record("OuterDia", '"OuterDia"')
    await add_diametric_linear_dimension(
        adapter, axis, bore, (LENGTH / 2.0, BORE_R - 2.0), "BoreDia"
    )
    profile.record("BoreDia", '"BoreDia"')
    await ensure_fully_defined(adapter, "ferrule profile sketch")
    check("exit_sketch ferrule profile", await adapter.exit_sketch())
    name_last_feature(adapter, "FerruleProfile")
    drive_jobs += profile.apply(adapter, "FerruleProfile")
    check("revolve ferrule", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Ferrule")
    await volume_check(adapter, "brass ferrule", V_FERRULE, 0.005 * V_FERRULE)

    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "ferrule axis")

    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven brass ferrule (equations neutral)", V_FERRULE, 0.005 * V_FERRULE
    )

    # The one model-owned band (policy rule 2): the bore, which the oak tenon
    # is turned to suit, holds both the MHA-022 seat and the oak round the
    # pivot bore.  The OD is the rod as supplied, skimmed at assembly; the
    # handle's end play is fitted on the MHA-139 shoulder.
    set_dimension_symmetric_tolerance(adapter, "FerruleProfile", "BoreDia", BORE_DIA_TOL)
    # Every model edit precedes the INSTALLED split, so the split copies a
    # finished default (the MHA-135 lesson).
    await apply_material(adapter, MATERIAL)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)

    default_config = active_configuration_name(adapter)
    check(
        f"create_configuration {INSTALLED_CONFIG}",
        await adapter.create_configuration(
            CreateConfigurationParameters(
                name=INSTALLED_CONFIG,
                comment="bonded; skimmed to the grip contour with the oak shoulder",
            )
        ),
    )
    check(
        f"activate {INSTALLED_CONFIG}",
        await adapter.set_active_configuration(INSTALLED_CONFIG),
    )
    await _cut_skim(adapter)
    await force_rebuild(adapter)
    if bool(_skim_feature(adapter).IsSuppressed()):
        raise RuntimeError(f"Skim is suppressed in {INSTALLED_CONFIG}")
    await volume_check(adapter, "installed ferrule (skimmed)", V_INSTALLED, 0.005 * V_INSTALLED)
    check(
        f"re-activate {default_config}",
        await adapter.set_active_configuration(default_config),
    )
    # Suppress with the target configuration active (crank-v4-10: specified
    # from INSTALLED, SetSuppression2 returned True but left the cut live).
    # swSuppressFeature, swSpecifyConfiguration.
    if not bool(_skim_feature(adapter).SetSuppression2(0, 3, bstr_array([default_config]))):
        raise RuntimeError(f"Skim would not suppress in {default_config}")
    await force_rebuild(adapter)
    if not bool(_skim_feature(adapter).IsSuppressed()):
        raise RuntimeError(f"Skim is not suppressed in {default_config}")
    await volume_check(adapter, "as-made ferrule (default)", V_FERRULE, 0.005 * V_FERRULE)
    grouped_spec = _config.parts(PART_NAME)
    apply_grouped_bom_properties(
        adapter,
        [default_config, INSTALLED_CONFIG],
        part_number=str(grouped_spec["number"]),
        description=str(grouped_spec["description"]),
    )
    await report_mass_properties(adapter)
    require_material_in_every_configuration(
        adapter, PART_NAME, MATERIAL, (default_config, INSTALLED_CONFIG)
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    # The drive train places INSTALLED while the part saves on its default;
    # reopen and prove its saved cache regenerates (cg-fx1).
    part_title = str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
    adapter.swApp.CloseDoc(part_title)
    adapter.currentModel = None
    check(f"reopen saved {PART_NAME}", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, PART_NAME)
    return artefacts


def _skim_feature(adapter):
    """The Skim cut, looked up afresh: a configuration switch can leave an
    earlier IFeature pointer reading the old configuration's state."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    return _early_bound(part.FeatureByName("Skim"), "IFeature")


async def _cut_skim(adapter) -> None:
    """Revolve-cut the brass from the rod OD down to the installed Ø12.5
    over the ring's whole length (INSTALLED)."""
    from solidworks_mcp.adapters.base import RevolveParameters

    x0, x1 = -_SKIM_MARGIN, LENGTH + _SKIM_MARGIN
    top = OUTER_R + _SKIM_MARGIN
    check("create_sketch skim", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("skim axis", await adapter.add_centerline(x0, 0.0, x1, 0.0))
    left, outer, right, inner = await add_line_chain(
        adapter,
        [(x0, INSTALLED_R), (x0, top), (x1, top), (x1, INSTALLED_R)],
    )
    set_sketch_direct_db(adapter, False)
    for entity, relation in (
        (axis, "horizontal"),
        (left, "vertical"),
        (outer, "horizontal"),
        (right, "vertical"),
        (inner, "horizontal"),
    ):
        check(
            f"skim {relation} {entity}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    await anchor_point_to_origin(adapter, f"{axis}.start", x0, 0.0, "skim axis start")
    check("skim axis length", await adapter.add_sketch_dimension(axis, None, "linear", x1 - x0))
    await anchor_point_to_origin(adapter, f"{left}.start", x0, INSTALLED_R, "skim corner")
    check("skim length", await adapter.add_sketch_dimension(inner, None, "linear", x1 - x0))
    await dimension_between(
        adapter, f"{left}.start", f"{left}.end", "vertical_distance", top - INSTALLED_R,
        "skim depth",
    )
    await ensure_fully_defined(adapter, "skim sketch")
    check("exit_sketch skim", await adapter.exit_sketch())
    name_last_feature(adapter, "SkimProfile")
    check(
        "revolve-cut skim",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Skim")


if __name__ == "__main__":
    sys.exit(run_build(build))
