r"""Configured Precision Matthews clamping-kit hardware (MHA-SH-VN-57).

One purchased SKU owns the exact ``HoldDownStud``, ``TNut`` and ``FlangeNut``
native members. TNut and FlangeNut retain their datasheet-built envelopes and
Hole Wizard sequences. HoldDownStud preserves the existing upper-end-only
shortening, genuine native length driver and independent end chamfers.

All members retain their +Y thread axis at the origin as one shared
``ScrewAxis`` (Front Plane x Right Plane). Member-owned geometry is suppressed
in every other configuration. Each member carries its own installed quantity,
notes and native BOM grouping key while sharing the canonical purchase Number.
The threads are not modeled, so there are no separate Simplified members or
Default aliases. Saving/reopening and per-member export ownership are delegated
to ``save_member_part``; its readback callback never repairs native state.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sh_vn_clamping_kit_hardware.py
"""

from __future__ import annotations

import math
import sys

import _config
import sh_vn_clamping_kit_flange_nut_spec as flange_nut
import sh_vn_clamping_kit_hold_down_stud_spec as hold_down_stud
import sh_vn_clamping_kit_t_nut_spec as t_nut
from _appearance import PANEL_BLACK, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _dimensions import name_dimensions
from _document_units import apply_package_model_units
from _drawing_marks import apply_drawing_properties, mark_dimensions_for_drawing
from _drawing_precision import _named_dimension, apply_drawing_precision
from _feature_tree import name_last_feature
from _holes import wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _purchased_part_variants import (
    activate_member,
    apply_member_properties,
    assert_member_properties,
    assert_member_suppression,
    create_member_configurations,
    require_member_bodies,
    require_member_colour,
    require_member_configurations,
    save_member_part,
    select_member_features,
    set_member_suppression,
)
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_polygon_chain, define_rectilinear_chain
from _sketch_circle import define_circle
from _visibility import assert_reference_geometry_hidden, blank_reference_geometry

PART_NAME = "sh-vn-clamping-kit-hardware"
HOLD_DOWN_STUD_CONFIGURATION = "HoldDownStud"
T_NUT_CONFIGURATION = "TNut"
FLANGE_NUT_CONFIGURATION = "FlangeNut"
CONFIGURATIONS = (
    HOLD_DOWN_STUD_CONFIGURATION,
    T_NUT_CONFIGURATION,
    FLANGE_NUT_CONFIGURATION,
)
MATERIAL = hold_down_stud.MATERIAL
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}
MEMBER_SPECS = {
    HOLD_DOWN_STUD_CONFIGURATION: hold_down_stud,
    T_NUT_CONFIGURATION: t_nut,
    FLANGE_NUT_CONFIGURATION: flange_nut,
}
# Parent sketches precede their dependent solid features. ScrewAxis is shared,
# not owned by any one member, and is never part of the suppression matrix.
MEMBER_FEATURES = {
    HOLD_DOWN_STUD_CONFIGURATION: (
        "StudProfile", "Stud", "LowerFactoryChamfer", "CutEndChamfer",
    ),
    T_NUT_CONFIGURATION: ("SectionProfile", "Body", "TNutThreadBore"),
    FLANGE_NUT_CONFIGURATION: (
        "FlangeProfile",
        "Flange",
        "HexProfile",
        "Hex",
        "FlangeNutThreadBore",
    ),
}
MEMBER_DESCRIPTIONS = {
    HOLD_DOWN_STUD_CONFIGURATION: hold_down_stud.BOM_DESCRIPTION,
    T_NUT_CONFIGURATION: t_nut.BOM_DESCRIPTION,
    FLANGE_NUT_CONFIGURATION: flange_nut.BOM_DESCRIPTION,
}
MEMBER_PROPERTIES = {
    configuration: {
        **STOCK_PROPERTIES,
        "Material Specification": str(_PART["material_specification"]),
        "Finish": str(_PART["finish"]),
        "Manufacturing Notes": spec.DRAWING_NOTES,
    }
    for configuration, spec in MEMBER_SPECS.items()
}
# The purchased family stays untouched at document scope; these machining
# instructions and finished-end treatment belong only to the stud member.
STUD_REWORK_PROPERTIES = {
    "Stock Length": f"{hold_down_stud.STOCK_LENGTH} IN STOCK",
    "Stock Note": hold_down_stud.STOCK_NOTE,
    "Lower End Note": hold_down_stud.LOWER_END_NOTE,
}
MEMBER_PROPERTIES[HOLD_DOWN_STUD_CONFIGURATION].update({
    **STUD_REWORK_PROPERTIES,
    "Process": hold_down_stud.PROCESS,
    "Finish": hold_down_stud.FINISH,
    "Tolerance Class": hold_down_stud.TOLERANCE_CLASS,
})
MEMBER_NOTE_PROPERTIES = {
    f"{configuration} Manufacturing Notes": spec.DRAWING_NOTES
    for configuration, spec in MEMBER_SPECS.items()
}
MEMBER_NOTE_PROPERTIES.update({
    f"{HOLD_DOWN_STUD_CONFIGURATION} Rework {name}": value
    for name, value in STUD_REWORK_PROPERTIES.items()
})
SAVED_DRAWING_PROPERTIES = (
    "Number", "Material Specification", "Finish", "Quantity",
    *STOCK_PROPERTIES, *MEMBER_NOTE_PROPERTIES,
)


def hold_down_stud_profile_points() -> list[tuple[float, float]]:
    """Length-driven blank; separate native chamfers produce the finished PROFILE."""
    return [
        (0.0, 0.0), (hold_down_stud.RADIUS, 0.0),
        (hold_down_stud.RADIUS, hold_down_stud.LENGTH), (0.0, hold_down_stud.LENGTH),
    ]


def t_nut_profile_points() -> list[tuple[float, float]]:
    """T-nut PROFILE as Right Plane points: u = across the slot, v = +Y."""
    return list(t_nut.PROFILE)


def flange_nut_hex_points() -> list[tuple[float, float]]:
    """Flange-nut HEX_OUTLINE as Top Plane points (u, v) = (X, -Z)."""
    return [(x, -z) for x, z in flange_nut.HEX_OUTLINE]


def _author_cut_end_maximum(adapter) -> None:
    """Apply native MAX to the actual cut-end feature, never reference ink."""
    _display, dimension = _named_dimension(adapter, "CutEndChamfer", "CutEndChamfer")
    maximum = hold_down_stud.CUT_END_CHAMFER_MAX / 1000.0
    if int(dimension.DrivenState) != 2 or not math.isclose(
        float(dimension.SystemValue), maximum, abs_tol=1e-9
    ):
        raise RuntimeError("cut-end chamfer is not the real driving maximum")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 6  # swTolMAX
    if not tolerance.SetValues(-maximum, 0.0):
        raise RuntimeError("cut-end chamfer MAX band was rejected")
    if (
        int(tolerance.Type) != 6
        or not math.isclose(float(tolerance.GetMinValue()), -maximum, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), 0.0, abs_tol=1e-12)
    ):
        raise RuntimeError("cut-end chamfer MAX band did not persist")


async def _author_hold_down_stud(adapter) -> None:
    """Author the existing finished stud rework only in its own configuration."""
    from solidworks_mcp.adapters.base import RevolveParameters

    dims = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, hold_down_stud.LENGTH),
    )
    points = hold_down_stud_profile_points()
    profile = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    # Genuine drivers on the rectangular blank; closure defines opposite sides.
    for line, direction in zip(
        profile, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
    ):
        check(f"stud {direction}", await adapter.add_sketch_constraint(line, None, direction))
    await dimension_between(
        adapter, f"{profile[1]}.start", f"{profile[1]}.end",
        "vertical_distance", hold_down_stud.LENGTH, "stud FinishedLength",
    )
    dims.record("FinishedLength")
    await dimension_between(
        adapter, f"{profile[0]}.start", f"{profile[0]}.end",
        "horizontal_distance", hold_down_stud.RADIUS, "stud MajorRadius",
    )
    dims.record("MajorRadius")
    await anchor_point_to_origin(adapter, f"{profile[0]}.start", 0.0, 0.0, "stud anchor")
    await ensure_fully_defined(adapter, "stud profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "StudProfile")
    dims.apply(adapter, "StudProfile")
    check("revolve stud", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Stud")
    # Preserve the estimated lower factory rim and the branch's new cut-end
    # chamfer as separate features; neither touches the loaded lower interval.
    check("lower factory envelope", await adapter.add_chamfer(
        hold_down_stud.LOWER_FACTORY_CHAMFER,
        [[hold_down_stud.RADIUS, 0.0, 0.0]], tangent_propagation=False,
    ))
    name_last_feature(adapter, "LowerFactoryChamfer")
    check("upper cut-end chamfer", await adapter.add_chamfer(
        hold_down_stud.CUT_END_CHAMFER_MAX,
        [[hold_down_stud.RADIUS, hold_down_stud.LENGTH, 0.0]], tangent_propagation=False,
    ))
    name_last_feature(adapter, "CutEndChamfer")
    name_dimensions(adapter, "CutEndChamfer", ["CutEndChamfer"])
    _author_cut_end_maximum(adapter)
    apply_drawing_precision(adapter, hold_down_stud.DRAWING_PRECISION)
    for feature, dimensions in hold_down_stud.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, dimensions)
    await volume_check(
        adapter, "stud", hold_down_stud.VOLUME_MM3, 0.005 * hold_down_stud.VOLUME_MM3
    )
    await bbox_extent_check(adapter, "stud length", "y", hold_down_stud.LENGTH)
    await bbox_extent_check(
        adapter, "stud major diameter", "x", hold_down_stud.MAJOR_DIA
    )


async def _author_t_nut(adapter) -> None:
    """Author the original mid-plane stepped block and through-all tapped hole."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    # --- 1. Foot and neck --------------------------------------------------------
    check("create_sketch section", await adapter.create_sketch("Right"))
    points = t_nut_profile_points()
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(adapter, lines, points, label="T-nut section")
    await ensure_fully_defined(adapter, "T-nut section")
    check("exit_sketch section", await adapter.exit_sketch())
    name_last_feature(adapter, "SectionProfile")
    check(
        "extrude T-nut",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=t_nut.LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Body")
    await volume_check(
        adapter, "T-nut block", t_nut.BLOCK_VOLUME, 0.005 * t_nut.BLOCK_VOLUME
    )
    await bbox_extent_check(adapter, "length along the slot", "x", t_nut.LENGTH)
    await bbox_extent_check(adapter, "height", "y", t_nut.HEIGHT)
    await bbox_extent_check(adapter, "foot width", "z", t_nut.FOOT_WIDTH)

    # --- 2. Thread: tapped through from the foot's bottom face ----------------------
    wizard_holes(
        adapter,
        t_nut.TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        f"T-nut thread ({t_nut.TAP_SPEC.size} through)",
        name="TNutThreadBore",
        expect_dia_mm=t_nut.TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    await volume_check(
        adapter, "tapped T-nut", t_nut.VOLUME_MM3, 0.005 * t_nut.VOLUME_MM3
    )


async def _author_flange_nut(adapter) -> None:
    """Author the original flange, overlapping full-height hex and tapped hole."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    # --- 1. Flange -----------------------------------------------------------------
    check("create_sketch flange", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, flange_nut.FLANGE_DIA / 2.0, "flange")
    await ensure_fully_defined(adapter, "flange")
    check("exit_sketch flange", await adapter.exit_sketch())
    name_last_feature(adapter, "FlangeProfile")
    check(
        "extrude flange",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=flange_nut.FLANGE_THICK)
        ),
    )
    name_last_feature(adapter, "Flange")
    await volume_check(
        adapter, "flange", flange_nut.FLANGE_VOLUME, 0.005 * flange_nut.FLANGE_VOLUME
    )

    # --- 2. Hex ----------------------------------------------------------------------
    check("create_sketch hex", await adapter.create_sketch("Top"))
    points = flange_nut_hex_points()
    lines = await add_line_chain(adapter, points)
    await define_polygon_chain(adapter, lines, points, label="hex")
    await ensure_fully_defined(adapter, "hex")
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    check(
        "extrude hex",
        await adapter.create_extrusion(ExtrusionParameters(depth=flange_nut.HEIGHT)),
    )
    name_last_feature(adapter, "Hex")
    await volume_check(
        adapter,
        "flange and hex",
        flange_nut.SOLID_VOLUME,
        0.005 * flange_nut.SOLID_VOLUME,
    )
    await bbox_extent_check(adapter, "nut height", "y", flange_nut.HEIGHT)
    await bbox_extent_check(adapter, "flange diameter", "x", flange_nut.FLANGE_DIA)

    # --- 3. Thread: tapped through from the bearing face ------------------------------
    wizard_holes(
        adapter,
        flange_nut.TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        f"flange nut thread ({flange_nut.TAP_SPEC.size} through)",
        name="FlangeNutThreadBore",
        expect_dia_mm=flange_nut.TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    await volume_check(
        adapter,
        "tapped flange nut",
        flange_nut.VOLUME_MM3,
        0.005 * flange_nut.VOLUME_MM3,
    )


async def _readback(adapter, configuration: str) -> None:
    """Assert the selected member without authoring, repairing or saving it."""
    assert_member_suppression(adapter, configuration, MEMBER_FEATURES)
    require_member_bodies(adapter, configuration, 1, ("ScrewAxis",))
    spec = MEMBER_SPECS[configuration]
    await volume_check(
        adapter,
        f"{configuration} saved volume",
        spec.VOLUME_MM3,
        0.005 * spec.VOLUME_MM3,
    )
    if configuration == HOLD_DOWN_STUD_CONFIGURATION:
        await bbox_extent_check(adapter, "stud length", "y", hold_down_stud.LENGTH)
        await bbox_extent_check(
            adapter, "stud major diameter", "x", hold_down_stud.MAJOR_DIA
        )
    elif configuration == T_NUT_CONFIGURATION:
        await bbox_extent_check(adapter, "length along the slot", "x", t_nut.LENGTH)
        await bbox_extent_check(adapter, "height", "y", t_nut.HEIGHT)
        await bbox_extent_check(adapter, "foot width", "z", t_nut.FOOT_WIDTH)
    elif configuration == FLANGE_NUT_CONFIGURATION:
        await bbox_extent_check(adapter, "nut height", "y", flange_nut.HEIGHT)
        await bbox_extent_check(adapter, "flange diameter", "x", flange_nut.FLANGE_DIA)
    assert_member_properties(
        adapter,
        PART_NAME,
        configuration,
        MEMBER_DESCRIPTIONS[configuration],
        MEMBER_PROPERTIES[configuration],
    )
    require_member_colour(adapter, configuration, PANEL_BLACK)
    assert_reference_geometry_hidden(adapter, f"{PART_NAME} [{configuration}]")


async def build(adapter) -> dict[str, str]:
    require_member_configurations(PART_NAME, CONFIGURATIONS)
    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    await create_member_configurations(adapter, PART_NAME, CONFIGURATIONS)

    # A single principal-plane intersection preserves all three legacy frames.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "thread axis")
    name_last_feature(adapter, "ScrewAxis")

    authored = []
    for configuration, author in (
        (HOLD_DOWN_STUD_CONFIGURATION, _author_hold_down_stud),
        (T_NUT_CONFIGURATION, _author_t_nut),
        (FLANGE_NUT_CONFIGURATION, _author_flange_nut),
    ):
        await activate_member(adapter, configuration)
        # Foreign solids must be absent during authoring: otherwise an extrusion
        # or a face-selected Hole Wizard feature can merge with another member.
        for previous in reversed(authored):
            set_member_suppression(adapter, MEMBER_FEATURES[previous], suppressed=True)
        await author(adapter)
        authored.append(configuration)

    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, MEMBER_NOTE_PROPERTIES)
    for configuration in CONFIGURATIONS:
        await select_member_features(adapter, configuration, MEMBER_FEATURES)
        set_member_suppression(adapter, ("ScrewAxis",), suppressed=False)
        blank_reference_geometry(adapter, (("ScrewAxis", "AXIS"),))
        await apply_material(adapter, MATERIAL)
        # Preserve the kit's black-oxide finish at document and body scope.
        await apply_color(adapter, PANEL_BLACK)
        apply_member_properties(
            adapter,
            PART_NAME,
            configuration,
            MEMBER_DESCRIPTIONS[configuration],
            MEMBER_PROPERTIES[configuration],
        )
        await report_mass_properties(adapter)

    artefacts = await save_member_part(
        adapter, PART_NAME, CONFIGURATIONS, material=MATERIAL, readback=_readback
    )
    require_saved_drawing_properties(adapter, SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
