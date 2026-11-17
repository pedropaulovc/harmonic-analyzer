r"""Reproduction script: ms-measuring-stick.SLDASM (MHA-MS-00).

The ch16 measuring stick with its stop clamped at the 2.0 mark (user-approved
re-derivation, 2026-10-09; sketch stop_rederive_v2): the graduated bar
ms-stick, the brass block ms-stop-block, its cover ms-stop-plate, two brass
#2-56 ms-vn-stop-plate-screw fillisters and one #4-40 sh-vn-thumb-screw.

Authored thumbscrew-up (+Y), with the block below the stick: the stop's part
frame is turned halfway about the stick's X axis. Every pose is
``ms_measuring_stick_assembly_spec``'s, derived from the part contracts. The
graduated face still bears on the window wall opposite the screw, the plain
face meets the tip, and the 2.0 division lies on the screw axis. The cover
and its screws turn with the block; no part geometry or contact changes.
The clamped stop has no operational freedom, so every component is fixed
(the fix-all strategy of the other sub-assemblies): 0 DOF, fully defined.

The named explode MS_EXPLODED (Default and Default Simplified) is the fitter
drawing's exploded view: the disassembly order along global axes, each step
read back in world space and the saved pose proven unchanged.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ms_measuring_stick_assembly.py
"""

from __future__ import annotations

import sys
from typing import Any

import _telemetry
import ms_measuring_stick_assembly_spec as spec
import ms_measuring_stick_explode_spec as explode
from _assembly import (
    activate_assembly_contract,
    assembly_title_properties,
    assert_components_fully_defined,
    author_in_drawing_configurations,
    check_no_interference,
    component_transform,
    place_component,
    save_assembly_and_images,
)
from _assembly_contract import assembly_contract
from _explode_steps import Step as ExplodeStep, author_explode_steps, stem_groups
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _session import run_build
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision, _named_dimension
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _assembly_named_views import name_standard_views
from _named_views import name_octant_views
from _sketch import (
    SketchDims, anchor_point_to_origin, blank_sketch, dimension_between,
    ensure_fully_defined, set_sketch_direct_db,
)
from _ms_measuring_stick_interference import ALLOWED_PAIRS
from _transforms import euler_from_rows

ASM_NAME = "ms-measuring-stick"
assert ASM_NAME == spec.ASM_NAME, (ASM_NAME, spec.ASM_NAME)


def _rows(rows: spec.Rows) -> list[list[float]]:
    return [list(row) for row in rows]


async def _place_fixed(
    adapter: Any, part: str, origin: tuple[float, float, float], rows: spec.Rows
) -> str:
    """One fixed component at its exact assembly-frame transform."""
    matrix = _rows(rows)
    return await place_component(
        adapter, part, list(origin), euler_from_rows(matrix), matrix
    )


def _ms_explode_plan(_model: Any, components: Any, _baseline: Any) -> list[ExplodeStep]:
    groups = stem_groups(components, spec.QUANTITIES)
    return [
        ExplodeStep(label, tuple(name for stem in stems for name in groups[stem]), key, distance_mm)
        for label, stems, key, distance_mm in explode.EXPLODE_STEPS
    ]


def _create_ms_explode(adapter: Any, configuration_name: str) -> None:
    """Author ``explode.EXPLODE_STEPS`` in the active ``configuration_name``
    (Default or Default Simplified) and leave the operational model collapsed."""
    author_explode_steps(
        adapter,
        configuration_name,
        view=explode.EXPLODED_VIEW_NAME,
        source=explode.SOURCE_CONFIGURATION,
        step_prefix="MS",
        plan=_ms_explode_plan,
    )


async def _author_clamped_setting(adapter: Any) -> None:
    """No solid/pose edits: a source-owned chord between physical face stations."""
    (left_x, contact_y), (face_x, _) = spec.SETTING_CHORD
    for name, value in (
        ("SettingStickLeft", left_x),
        ("SettingBlockFace", face_x),
        ("SettingContact", contact_y),
    ):
        await set_global(adapter, name, f"{value}mm")
    dims = SketchDims()
    check("create clamped setting sketch", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    line = check("setting chord", await adapter.add_line(left_x, contact_y, face_x, contact_y))
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("clamped setting chord is not construction")
    check("setting horizontal", await adapter.add_sketch_constraint(line, None, "horizontal"))
    await anchor_point_to_origin(adapter, f"{line}.start", left_x, contact_y, "setting left end")
    dims.record("SettingLeftX", '-"SettingStickLeft"')
    dims.record("SettingContactY", '-"SettingContact"')
    await dimension_between(
        adapter, f"{line}.start", f"{line}.end", "horizontal_distance",
        spec.SETTING_NEAR_FACE_MM, "near face from left stick end",
    )
    dims.record(spec.SETTING_DIMENSION, '"SettingBlockFace" - "SettingStickLeft"')
    await ensure_fully_defined(adapter, "clamped setting")
    check("exit clamped setting sketch", await adapter.exit_sketch())
    name_last_feature(adapter, spec.SETTING_FEATURE)
    for name, expression in dims.apply(adapter, spec.SETTING_FEATURE):
        await drive_dimension(adapter, name, expression)
    # A parenthesized reference to the saved pose, not a band: the native
    # prefix/suffix channel around the live value, as the magnifier's.
    display, dimension = _named_dimension(adapter, spec.SETTING_FEATURE, spec.SETTING_DIMENSION)
    _early_bound(dimension.Tolerance, "IDimensionTolerance").Type = 0  # swTolNONE
    display.ShowParenthesis = False
    display.SetText(1, "(")
    display.SetText(2, ")")
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    mark_dimensions_for_drawing(adapter, spec.SETTING_FEATURE, {spec.SETTING_DIMENSION})
    blank_sketch(adapter, spec.SETTING_FEATURE)


def _assert_working_pose(adapter: Any, thumbscrew: str) -> None:
    # Read the final solved native pose, not the camera or the expected spec.
    spec.assert_thumbscrew_up(
        tuple(component_transform(adapter, thumbscrew)[:3]), label=ASM_NAME
    )


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    check("create_assembly", await adapter.create_assembly())
    apply_package_model_units(adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME)

    # The block and cover share the stop's turned, thumbscrew-up frame.
    await _place_fixed(adapter, "ms-stop-block", spec.BLOCK_ORIGIN, spec.BLOCK_ROWS)
    await _place_fixed(adapter, "ms-stop-plate", spec.PLATE_ORIGIN, spec.PLATE_ROWS)
    # The graduated face still bears on the fixed wall opposite the screw.
    await _place_fixed(adapter, "ms-stick", spec.STICK_ORIGIN, spec.STICK_ROWS)
    # The stop thumbscrew points down onto the stick's plain face.
    thumbscrew = await _place_fixed(
        adapter, "sh-vn-thumb-screw", spec.THUMB_ORIGIN, spec.THUMB_ROWS
    )
    # The cover plate screws into the block: heads on the cover's outer face,
    # threads in the #2-56 blind taps (MHA-MS-00 step 4).
    for origin in spec.PLATE_SCREW_ORIGINS:
        await _place_fixed(adapter, "ms-vn-stop-plate-screw", origin, spec.PLATE_SCREW_ROWS)
    _telemetry.info(
        f"stop clamped at mark {spec.stop.STOP_MARK:.1f}: bar x {spec.STICK_X_MIN:.2f}.."
        f"{spec.STICK_X_MAX:.2f}, graduated face y {spec.STICK_BOTTOM_Y:.2f}, "
        f"{spec.STICK_SIDE_CLEARANCE:.2f} clear each side; thumbscrew face y "
        f"{spec.THUMB_HEAD_FACE_Y:.3f}, {spec.THUMB_EXPOSED_THREAD:.3f} thread exposed; "
        f"plate screws {spec.PLATE_SCREW_TAP_RESERVE:.2f} short of the tapped depth"
    )

    await _author_clamped_setting(adapter)
    assert_components_fully_defined(adapter)
    # Only the two thread engagements may overlap; the bar's fixed-wall contact,
    # the tip contact and the cover's seat are faces, not volume.
    check_no_interference(
        adapter,
        allowed_pairs=ALLOWED_PAIRS,
    )

    # Title-block identity for the fitter drawing
    # (draw_ms_measuring_stick_assembly.py): assembly_title_properties supplies
    # Title/Generator and the TOL_* cells finalize_drawing requires; material
    # and finish are per component (the BOM's MATERIAL column, the finish note
    # and each component drawing), so the assembly's own cells defer to them.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The fitter drawing's exploded view references Default Simplified, so
    # the explode is authored in both drawing configurations.
    author_in_drawing_configurations(
        adapter, ASM_NAME, lambda configuration: _create_ms_explode(adapter, configuration)
    )
    name_standard_views(
        adapter,
        views=spec.DRAWING_STANDARD_VIEWS,
        label=ASM_NAME,
        model_rotation=spec.WORKING_ROWS,
    )
    name_octant_views(
        adapter, octants=spec.DRAWING_EXPLODED_OCTANTS, label=ASM_NAME
    )
    return await save_assembly_and_images(
        adapter,
        ASM_NAME,
        solved_gates=lambda current: _assert_working_pose(current, thumbscrew),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
