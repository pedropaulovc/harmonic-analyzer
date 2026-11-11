r"""Reproduction script: bar pivot pin (MHA-CH-11; 20 used, one per channel).

The plain 5/64 drill-rod pin that hangs each amplitude bar on its channel
lever (``ch_bar_pivot_pin_spec`` owns the joint and its budget). It RUNS in
the lever's #47 bar-pin hole and is PRESSED into the reamed top pin hole
through both cheeks of the bar's top notch, its ends dressed flush with the
bar's faces (user ruling 2026-10: press fit, removable with a punch).

Two configurations (the ``build_dt_pinion_lever_pin`` pattern): the default
is the pin the shop makes, a Ø PIN_DIA cylinder cut PIN_BLANK_LENGTH long,
which the drawing prints; ``INSTALLED_CONFIG`` is the same pin dressed flush,
PIN_INSTALLED_LENGTH (the bar's width) long, which the channel assembly
places. ``PinLen`` is set per configuration. Layout: pin axis along local X,
centred on the origin, so the channel assembly seats it with its axis on the
bar's top pin bore and its Right Plane on the bar's mid-width plane. The pin
is a Front-plane half-profile revolved about that axis, so its diameter and
length both import into the *Front side view (drawing-guidelines.md rule 11
(turned parts read like the lathe)).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_bar_pivot_pin.py
"""

from __future__ import annotations

import math
import sys

import _config
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _configuration_material import require_material_in_every_configuration
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _grouped_bom_properties import apply_grouped_bom_properties
from _part_properties import part_drawing_unit
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import (
    active_configuration_name,
    assert_saved_configurations_regenerate,
    force_rebuild,
)
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from ch_bar_pivot_pin_notes import DRAWING_DIMENSIONS, DRAWING_PRECISION
from ch_bar_pivot_pin_spec import (
    INSTALLED_CONFIG,
    PIN_BLANK_LENGTH,
    PIN_DIA,
    PIN_DIA_TOLERANCE,
    PIN_INSTALLED_LENGTH,
)

PART_NAME = "ch-bar-pivot-pin"
MATERIAL = "Plain Carbon Steel"  # drill rod, as the fleet's other drill-rod pins
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
)

PIN_R = PIN_DIA / 2.0
HALF_LEN = PIN_BLANK_LENGTH / 2.0
V_PIN = math.pi * PIN_R**2 * PIN_BLANK_LENGTH
V_INSTALLED = math.pi * PIN_R**2 * PIN_INSTALLED_LENGTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        RevolveParameters,
        SetGlobalVariableParameters,
    )

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_BLANK_LENGTH}mm")

    # Half-profile on the Front Plane (sketch x -> model X, y -> model Y): the
    # axis centerline along X through the origin and the rectangle above it,
    # centred on the origin -- the bar's top pin bore in the assembly. Its two
    # dimensions are the print's two: the length along the outline and the
    # diameter as a doubled centerline-to-outline dim.
    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "axis centerline", await adapter.add_centerline(-HALF_LEN, 0.0, HALF_LEN, 0.0)
    )
    profile_pts = [
        (-HALF_LEN, 0.0),
        (-HALF_LEN, PIN_R),
        (HALF_LEN, PIN_R),
        (HALF_LEN, 0.0),
    ]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    n = len(profile_lines)
    for i, line in enumerate(profile_lines):
        (_, y1), (_, y2) = profile_pts[i], profile_pts[(i + 1) % n]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"pin {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    outline = profile_lines[1]
    await dimension_between(
        adapter,
        f"{outline}.start",
        f"{outline}.end",
        "horizontal_distance",
        PIN_BLANK_LENGTH,
        "pin PinLen",
    )
    pin.record("PinLen", '"PinLen"')
    await add_diametric_linear_dimension(
        adapter, axis, outline, (-HALF_LEN / 2.0, PIN_R + 4.0), "PinDia"
    )
    pin.record("PinDia", '"PinDia"')
    start = f"{profile_lines[0]}.start"
    check(
        "pin end on the axis",
        await adapter.add_sketch_constraint(start, "origin", "horizontal_points"),
    )
    await dimension_between(
        adapter,
        start,
        "origin",
        "horizontal_distance",
        HALF_LEN,
        "pin centred on origin",
    )
    pin.record("PinHalfLen", '"PinLen" / 2')
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs = pin.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    volume = await volume_check(adapter, "cut pin", V_PIN, 0.005 * V_PIN)
    res = await adapter.get_mass_properties()
    com = res.data.center_of_mass
    if com is None or any(abs(c) > 1e-6 for c in com):
        raise RuntimeError(f"bar pivot pin is not centred on its origin (COM {com})")

    # Named pin axis (Axis1, along X): coaxial with the bar's top pin bore and
    # the lever's bar-pin hole in the assembly.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Front Plane", 0.0, "pin axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", volume, 0.005 * V_PIN)

    # Every model edit -- the diameter's band, the marked set, the
    # model-owned decimal places, the material and the appearance -- precedes
    # the INSTALLED split, so INSTALLED is copied from a finished default
    # (build_dt_pinion_lever_pin: an edit made after the split touches only
    # the active configuration and left the other stale in the saved part).
    # The diameter is the press size, .0782 +/-.0001 selected from 5/64 drill
    # rod (ch_bar_pivot_pin_spec, #2339); the cut length takes the title
    # block's .XX band (the dressing stock, ch_bar_pivot_pin_spec.joint_budget
    # blank_excess_min/max).
    set_dimension_symmetric_tolerance(
        adapter,
        "PinProfile",
        "PinDia",
        PIN_DIA_TOLERANCE,
        display_unit=part_drawing_unit(PART_NAME),
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)

    # Installed configuration: the channel assembly places the pin pressed in
    # and dressed flush with both bar faces. The default stays the cut pin the
    # drawing prints, and both carry one MHA-CH-11 BOM identity. PinLen is set
    # per configuration in each, so neither inherits the other's length.
    default_config = active_configuration_name(adapter)
    check(
        f"create_configuration {INSTALLED_CONFIG}",
        await adapter.create_configuration(
            CreateConfigurationParameters(
                name=INSTALLED_CONFIG,
                comment="pressed into the bar, both ends dressed flush",
            )
        ),
    )
    for name, length in (
        (default_config, PIN_BLANK_LENGTH),
        (INSTALLED_CONFIG, PIN_INSTALLED_LENGTH),
    ):
        check(
            f"PinLen = {length} in {name}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="PinLen", expression=f"{length}mm", configuration=name
                )
            ),
        )
    check(
        f"activate {INSTALLED_CONFIG}",
        await adapter.set_active_configuration(INSTALLED_CONFIG),
    )
    await force_rebuild(adapter)
    await volume_check(adapter, "installed pin", V_INSTALLED, 0.005 * V_INSTALLED)
    check(
        f"re-activate {default_config}",
        await adapter.set_active_configuration(default_config),
    )
    await force_rebuild(adapter)
    await volume_check(adapter, "cut pin (default)", volume, 0.005 * V_PIN)
    # The configuration description wins over the channel BOM's written cell,
    # so it is the text that BOM prints (ch_channel_assembly_sheet
    # BOM_DESCRIPTIONS).
    row = _config.parts(PART_NAME)
    apply_grouped_bom_properties(
        adapter,
        [default_config, INSTALLED_CONFIG],
        part_number=str(row["number"]),
        description=str(row["description"]),
    )
    await report_mass_properties(adapter)
    require_material_in_every_configuration(
        adapter, PART_NAME, MATERIAL, (default_config, INSTALLED_CONFIG)
    )
    apply_drawing_properties(adapter, PART_NAME)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    # The channel assembly places INSTALLED while the part saves on its
    # default, so INSTALLED's saved cache is what it rebuilds. Reopen and prove
    # it the way the assembly loads it (cg-fx1).
    part_title = str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
    adapter.swApp.CloseDoc(part_title)
    adapter.currentModel = None
    check("reopen saved bar-pivot-pin", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, PART_NAME)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
