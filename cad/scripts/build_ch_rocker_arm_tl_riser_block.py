r"""Build the rocker arm's riser block (MHA-CH-006-TL-10; shop fixture).

Six 1018 blocks the rocker blank or its strap shim stacks stand on in the S1-S4
mill setups, faced together to one height (``ch_rocker_arm_tl_riser_block_spec``).
One part with two configurations, L036 (four off) and L045 (two off), which
differ only in the ``BlockLength`` global.

Layout: the block profile is a Front-plane rectangle from the origin (length
along +X, height along +Y), extruded +Z by the stock width.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_riser_block.py
"""

from __future__ import annotations

import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _configuration_material import require_material_in_every_configuration
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import assert_saved_configurations_regenerate, force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_riser_block_spec import (
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BLOCK_WIDTH,
    CONFIGS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "ch-rocker-arm-tl-riser-block"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 1018 CR bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)


def _block_volume(length: float) -> float:
    return length * BLOCK_HEIGHT * BLOCK_WIDTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        ExtrusionParameters,
        SetGlobalVariableParameters,
    )

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "BlockLength", f"{BLOCK_LENGTH}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BlockWidth", f"{BLOCK_WIDTH}mm")

    profile = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    points = [
        (0.0, 0.0),
        (BLOCK_LENGTH, 0.0),
        (BLOCK_LENGTH, BLOCK_HEIGHT),
        (0.0, BLOCK_HEIGHT),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="block profile",
        dims=profile,
        names=["BlockLength", "BlockHeight"],
        drives=['"BlockLength"', '"BlockHeight"'],
    )
    await ensure_fully_defined(adapter, "block profile")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs = profile.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_WIDTH)),
    )
    name_last_feature(adapter, "Block")
    drive_jobs.append(
        (name_dimensions(adapter, "Block", ["BlockWidth"])[0], '"BlockWidth"')
    )
    v_block = _block_volume(BLOCK_LENGTH)
    volume = await volume_check(adapter, "block", v_block, 0.002 * v_block)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven block (equations neutral)", volume, 0.002 * v_block
    )

    # Every model edit -- material, marked set, model-owned places -- precedes
    # the configuration split (build_dt_pinion_lever_pin: an edit made after
    # it touches only the active configuration and leaves the other stale).
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )

    # The two lengths (build_pd_transgear_removable's recipe): one named
    # configuration each, BlockLength set in each so neither inherits the
    # other's length, the saved one rebuilt last.
    names = [name for name, _length, _qty in CONFIGS]
    for name, length, qty in CONFIGS:
        check(
            f"create_configuration {name}",
            await adapter.create_configuration(
                CreateConfigurationParameters(
                    name=name, comment=f"riser block {length:g} long, {qty} off"
                )
            ),
        )
    for name, length, _qty in CONFIGS:
        check(
            f"BlockLength = {length} in {name}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="BlockLength", expression=f"{length}mm", configuration=name
                )
            ),
        )
    # Last activated: CONFIGS[0], the configuration the part saves on.
    for name, length, _qty in reversed(CONFIGS):
        check(f"activate {name}", await adapter.set_active_configuration(name))
        await force_rebuild(adapter)
        expected = _block_volume(length)
        await volume_check(adapter, f"{name} block", expected, 0.002 * expected)
    require_material_in_every_configuration(adapter, PART_NAME, MATERIAL, names)

    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    # The drawing places L045 while the part saves on L036, so L045's saved
    # cache is what it rebuilds: reopen and prove it the way it loads (cg-fx1).
    part_title = str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
    adapter.swApp.CloseDoc(part_title)
    adapter.currentModel = None
    check("reopen saved riser block", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, PART_NAME)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
