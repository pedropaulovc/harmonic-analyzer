r"""Build MHA-DT-03-TL-04, the keyed arbor's backing collars (shop tooling, #2465).

One native part, three named members (``dt_cone_gear_tl_arbor_collar_spec``):
each member owns one disc, an annulus on the Front Plane extruded +Z by the
collar's length, and the other members' discs are suppressed in it
(``_purchased_part_variants``: ``create_member_configurations``,
``select_member_features``, ``apply_member_properties``, ``save_member_part``).
Each disc is authored with its own member active and the discs authored
before it suppressed there (the rail kit's recipe): a disc extruded into
another member's solid merges with it and makes that disc its parent, so
unsuppressing it in its own member brings the foreign disc back.

Frame: axis +Z; the face on the blank at z = 0, the face under the nut at
z = LENGTH.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_tl_arbor_collar.py
"""

from __future__ import annotations

import sys

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _purchased_part_variants import (
    activate_member,
    apply_member_properties,
    assert_member_properties,
    assert_member_suppression,
    create_member_configurations,
    require_member_configurations,
    save_member_part,
    select_member_features,
    set_member_suppression,
)
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from diagnostics.diag_mcmaster_lib import no_sketch_inference
import dt_cone_gear_tl_arbor_collar_spec as spec

PART_NAME = "dt-cone-gear-tl-arbor-collar"
if PART_NAME != spec.PART_NAME:
    raise AssertionError("the builder's PART_NAME and its spec disagree")
CONFIGURATIONS = spec.CONFIGURATIONS
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring
_V_TOL = 0.005


async def _readback(adapter, configuration: str) -> None:
    """Assert the selected member without authoring it: its own disc, its BOM
    identity and its volume."""
    assert_member_suppression(adapter, configuration, spec.CONFIGURATION_FEATURES)
    assert_member_properties(
        adapter,
        PART_NAME,
        configuration,
        spec.CONFIGURATION_DESCRIPTIONS[configuration],
        {},
    )
    expected = spec.V_BY_CONFIGURATION[configuration]
    await volume_check(
        adapter, f"collar member {configuration}", expected, _V_TOL * expected
    )


async def _add_disc(
    adapter, drive_jobs: list[tuple[str, str]], configuration: str
) -> None:
    """One member's annulus on the Front Plane, extruded +Z by the length."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    od = spec.OD_BY_CONFIGURATION[configuration]
    label = f"collar {configuration}"
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await define_circle(
            adapter,
            0.0,
            0.0,
            od / 2.0,
            f"{label} outside",
            dims=dims,
            names=(None, None, spec.od_name(configuration)),
            drives=(None, None, f'"{spec.od_name(configuration)}"'),
        )
        await define_circle(
            adapter,
            0.0,
            0.0,
            spec.BORE / 2.0,
            f"{label} bore",
            dims=dims,
            names=(None, None, spec.bore_name(configuration)),
            drives=(None, None, '"CollarBore"'),
        )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, spec.disc_sketch(configuration))
    drive_jobs += dims.apply(adapter, spec.disc_sketch(configuration))
    check(
        f"extrude {label}",
        await adapter.create_extrusion(ExtrusionParameters(depth=spec.LENGTH)),
    )
    name_last_feature(adapter, spec.disc_feature(configuration))
    (length,) = name_dimensions(
        adapter, spec.disc_feature(configuration), [spec.length_name(configuration)]
    )
    drive_jobs.append((length, '"CollarLength"'))


async def build(adapter) -> dict[str, str]:
    require_member_configurations(PART_NAME, CONFIGURATIONS)
    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    await create_member_configurations(adapter, PART_NAME, CONFIGURATIONS)
    for name, value in spec.GLOBALS.items():
        await set_global(adapter, name, f"{value}mm")

    # Each disc with its own member active and every disc authored before it
    # suppressed there, so no disc merges into another member's solid; its
    # equations are driven while its member is active.
    authored: list[str] = []
    for configuration in CONFIGURATIONS:
        await activate_member(adapter, configuration)
        for previous in reversed(authored):
            set_member_suppression(
                adapter, spec.CONFIGURATION_FEATURES[previous], suppressed=True
            )
        drive_jobs: list[tuple[str, str]] = []
        await _add_disc(adapter, drive_jobs, configuration)
        expected = spec.V_BY_CONFIGURATION[configuration]
        await volume_check(
            adapter, f"collar disc {configuration}", expected, _V_TOL * expected
        )
        await force_rebuild(adapter)
        for dimension_name, expression in drive_jobs:
            await drive_dimension(adapter, dimension_name, expression)
        await force_rebuild(adapter)
        await volume_check(
            adapter,
            f"driven collar {configuration} (equations neutral)",
            expected,
            _V_TOL * expected,
        )
        authored.append(configuration)

    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": spec.ISOMETRIC_VIEW_NOTE}
    )
    for configuration in CONFIGURATIONS:
        await select_member_features(
            adapter, configuration, spec.CONFIGURATION_FEATURES
        )
        await apply_material(adapter, MATERIAL)
        apply_member_properties(
            adapter,
            PART_NAME,
            configuration,
            spec.CONFIGURATION_DESCRIPTIONS[configuration],
            {},
        )
        await report_mass_properties(adapter)
    return await save_member_part(
        adapter,
        PART_NAME,
        CONFIGURATIONS,
        material=MATERIAL,
        readback=_readback,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
