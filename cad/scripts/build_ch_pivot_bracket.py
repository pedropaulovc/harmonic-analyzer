r"""Reproduction script: rocker pivot bracket (MHA-CH-008; book ch. 14 pp. 26-27; 2 used).

The black steel bracket that carries each end of the rocker pivot shaft on
the green rocker-arm support (ch14 page002_img01/img02, page002_img07
"pivot"). 2026-09-02 photo re-derive: it is an L, not a T -- the ear stands
at one END of the foot, and the foot is only as wide as the support's apex.
#743 PR2 (Reading 1, user Q4): the bright dome on the ear is the pivot
shaft's own domed end, not a brazed-on ball, so the ear is a plain plate
arched EAR_W/2 about the O6.5 cross-bore. The north ear's inner face is the
rocker bank's axial datum (the shaft's shoulder bears on it); the south one
is set off the MHA-VN-053 preload spring (#948 ruling R; ``rocker_bank_layout``).

The channel assembly inserts the NORTH bracket as IDENTITY and the SOUTH one
turned Ry(180) about its bore axis, so both feet run OUTBOARD, away from the
rocker stack, and end flush with the support's end faces (user-approved
sketch, 2026-10-09). The two feet therefore differ in length: one part number,
two configurations, ``S`` and ``N``, each carrying its own ``FootZ1`` and
``HoleZ`` globals (``ch_pivot_bracket_sides`` derives them). Default is a
bystander that is never placed: the S configuration exists before the first
global so every equation row is born through ``IEquationMgr.Add3`` and stays
configuration-scopable (the MHA-DT-003 lesson).

Layout (part frame; the section lives in ``ch_pivot_bracket_spec``): seat face
at y = 0; origin under the bore, on the seat plane. Foot FOOT_W along X by
FOOT_H tall by FOOT_Z0..FootZ1 along Z; ear EAR_W (= FOOT_W, so its sides run
flush with the foot's) wide by EAR_T thick (Z), centred on the origin: a block
from the foot top to the bore height plus a full O EAR_W boss on the bore
axis, whose upper half is the arch (the arbor-pedestal crown idiom: no arcs,
only proven primitives); O BORE_DIA cross-bore along Z; one hold-down hole
through the foot on x = 0 at z = HoleZ, centred in the foot's free run.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_pivot_bracket.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    PANEL_BLACK,
    SketchDims,
    _early_bound,
    _read_member,
    active_configuration_name,
    add_line_chain,
    apply_color,
    apply_material,
    assert_saved_configurations_regenerate,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _configuration_material import require_material_in_every_configuration
from _drawing_marks import set_dimension_symmetric_tolerance
from _grouped_bom_properties import apply_grouped_bom_properties
from ch_pivot_bracket_sides import (
    CONFIGURATION_NUMBER,
    CONFIGURATIONS,
    FOOT_LEN,
    FOOT_Z1,
    HOLE_Z,
)
from ch_pivot_bracket_spec import (
    BORE_DIA,
    BORE_H,
    EAR_ARCH_R,
    EAR_T,
    EAR_T_BAND,
    EAR_W,
    FOOT_H,
    FOOT_LEN_BAND,
    FOOT_W,
    FOOT_Z0,
    HOLE_DIA,
    STATION_BAND,
)


PART_NAME = "ch-pivot-bracket"
MATERIAL = "Plain Carbon Steel"  # black-finished steel (ch14 p.27)

# The features are authored in AUTHORING_CONFIG; the other configuration is
# copied from it once the part is finished.
AUTHORING_CONFIG = CONFIGURATIONS[0]
V_FOOT = {name: FOOT_W * FOOT_H * FOOT_LEN[name] for name in CONFIGURATIONS}
# The ear block sits on the foot top, as wide as the foot: its sides merge
# into the foot's, so the part stays one body and the volumes simply add.
V_BLOCK = EAR_W * (BORE_H - FOOT_H) * EAR_T
V_ARCH = 0.5 * math.pi * EAR_ARCH_R**2 * EAR_T  # the boss's upper half
V_BORE = math.pi * (BORE_DIA / 2.0) ** 2 * EAR_T
V_HOLE = math.pi * (HOLE_DIA / 2.0) ** 2 * FOOT_H
V_TOTAL = {
    name: V_FOOT[name] + V_BLOCK + V_ARCH - V_BORE - V_HOLE for name in CONFIGURATIONS
}
if EAR_ARCH_R != EAR_W / 2.0 or BORE_H - EAR_ARCH_R <= FOOT_H:
    raise AssertionError("the ear boss must be the block's width and clear the foot")
if EAR_W > FOOT_W:
    raise AssertionError("the ear must not overhang the foot's sides")


def _apply_configuration_number(adapter, configuration: str, number: str) -> None:
    """Write and read back one configuration's ``Number`` property."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _read_member(model, "Extension")
    manager = adapter._attempt(
        lambda: extension.CustomPropertyManager(configuration), default=None
    )
    if manager is None:
        raise RuntimeError(f"CustomPropertyManager unavailable for {configuration}")
    manager = _early_bound(manager, "ICustomPropertyManager")
    # swCustomInfoText (30), swCustomPropertyReplaceValue (2).
    adapter._attempt(lambda: manager.Add3("Number", 30, number, 2), default=None)
    observed = str(
        adapter._attempt(
            lambda: model.GetCustomInfoValue(configuration, "Number"), default=""
        )
    )
    if observed != number:
        raise RuntimeError(
            f"{configuration} Number readback {observed!r} != {number!r}"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        ExtrusionParameters,
        SetGlobalVariableParameters,
    )

    check("create_part", await adapter.create_part())
    # Seed the authoring configuration before the first global: on a
    # one-configuration model the equation manager falls back to Add2, whose
    # rows do not take per-configuration values (build_dt_cone_gear).
    check(
        f"create_configuration {AUTHORING_CONFIG}",
        await adapter.create_configuration(
            CreateConfigurationParameters(
                name=AUTHORING_CONFIG, comment="south pivot bracket"
            )
        ),
    )

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    await set_global(adapter, "FootW", f"{FOOT_W}mm")
    await set_global(adapter, "FootH", f"{FOOT_H}mm")
    await set_global(adapter, "FootZ1", f"{FOOT_Z1[AUTHORING_CONFIG]}mm")
    await set_global(adapter, "HoleZ", f"{HOLE_Z[AUTHORING_CONFIG]}mm")
    await set_global(adapter, "EarW", f"{EAR_W}mm")
    await set_global(adapter, "EarT", f"{EAR_T}mm")
    await set_global(adapter, "BoreH", f"{BORE_H}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Foot: Top-plane rectangle (sketch y = model -Z) x +-W/2, z FOOT_Z0..
    # FootZ1, extruded +Y by FOOT_H. Emission: seg0 width, seg1 length, then
    # the (-W/2, -FootZ1) corner anchor (x then z; the anchor z lands at the
    # magnitude FootZ1 -- the magnifying-bracket Top-sketch idiom).
    half_w = FOOT_W / 2.0
    foot_z1 = FOOT_Z1[AUTHORING_CONFIG]
    foot = SketchDims()
    check("create_sketch foot", await adapter.create_sketch("Top"))
    rect = [
        (-half_w, -foot_z1),
        (half_w, -foot_z1),
        (half_w, -FOOT_Z0),
        (-half_w, -FOOT_Z0),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="foot", dims=foot,
        names=["FootW", "FootLen", "FootAnchorX", "FootAnchorZ"],
        drives=['"FootW"', '"FootZ1" + "EarT" / 2', '"FootW" / 2', '"FootZ1"'],
    )
    await ensure_fully_defined(adapter, "foot sketch")
    check("exit_sketch foot", await adapter.exit_sketch())
    name_last_feature(adapter, "FootProfile")
    drive_jobs += foot.apply(adapter, "FootProfile")
    check(
        "extrude foot",
        await adapter.create_extrusion(ExtrusionParameters(depth=FOOT_H)),
    )
    name_last_feature(adapter, "Foot")
    drive_jobs.append(("D1@Foot", '"FootH"'))
    expected = V_FOOT[AUTHORING_CONFIG]
    await volume_check(adapter, "foot", expected, 0.005 * expected)

    # Ear block: Front-plane rectangle x +-EAR_W/2, y FOOT_H..BORE_H,
    # extruded both ways (EAR_T total) -- its Z band is the bore's; its sides
    # lie in the foot's, so the merge leaves one body. Emission:
    # seg0 width, seg1 rise, then the (-EAR_W/2, FOOT_H) corner anchor (x, z).
    half_e = EAR_W / 2.0
    ear = SketchDims()
    check("create_sketch ear", await adapter.create_sketch("Front"))
    ear_rect = [
        (-half_e, FOOT_H),
        (half_e, FOOT_H),
        (half_e, BORE_H),
        (-half_e, BORE_H),
    ]
    ear_lines = await add_line_chain(adapter, ear_rect)
    await define_rectilinear_chain(
        adapter, ear_lines, ear_rect, label="ear", dims=ear,
        names=["EarW", "EarRise", "EarAnchorX", "EarAnchorZ"],
        drives=['"EarW"', '"BoreH" - "FootH"', '"EarW" / 2', '"FootH"'],
    )
    await ensure_fully_defined(adapter, "ear sketch")
    check("exit_sketch ear", await adapter.exit_sketch())
    name_last_feature(adapter, "EarProfile")
    drive_jobs += ear.apply(adapter, "EarProfile")
    check(
        "extrude ear",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=EAR_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Ear")
    # The ear thickness carries its +/-0.10 band natively: named so the band
    # selects it by name (the MHA-CH-003 ForkThick idiom).
    ear_thick_dim = name_dimensions(adapter, "Ear", ["EarThick"])
    drive_jobs.append((ear_thick_dim[0], '"EarT"'))
    expected += V_BLOCK
    await volume_check(adapter, "ear block", expected, 0.005 * V_BLOCK)

    # Ear arch: a full O EAR_W boss on the bore axis, the block's own width,
    # merged over the block's top -- its lower half lies inside the block, its
    # upper half is the arch (the arbor-pedestal crown idiom). On-axis in X,
    # so define_circle records the rise + diameter.
    arch = SketchDims()
    check("create_sketch arch", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_H, EAR_ARCH_R, "ear arch",
        dims=arch, names=("ArchCx", "ArchCz", "ArchDia"),
        drives=(None, '"BoreH"', '"EarW"'),
    )
    await ensure_fully_defined(adapter, "arch sketch")
    check("exit_sketch arch", await adapter.exit_sketch())
    name_last_feature(adapter, "ArchProfile")
    drive_jobs += arch.apply(adapter, "ArchProfile")
    check(
        "extrude arch",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=EAR_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Arch")
    expected += V_ARCH
    await volume_check(adapter, "ear arch", expected, 0.01 * V_ARCH)

    # Shaft cross-bore along Z at (0, BORE_H), through the ear.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_H, BORE_DIA / 2.0, "shaft bore",
        dims=bore, names=("BoreCx", "BoreCz", "ShaftBoreDia"),
        drives=(None, '"BoreH"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftBoreProfile")
    drive_jobs += bore.apply(adapter, "ShaftBoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=EAR_T + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")
    expected -= V_BORE
    await volume_check(adapter, "shaft bore", expected, 0.02 * V_BORE)

    # Hold-down hole through the foot: a Top-plane circle on x = 0 (sketch y
    # = -z), cut both ways past the foot height. On-axis in X, so it records
    # only its z station (HoleZ, per configuration) + diameter.
    hole_z = HOLE_Z[AUTHORING_CONFIG]
    hole = SketchDims()
    check("create_sketch hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, -hole_z, HOLE_DIA / 2.0, "hold-down hole",
        dims=hole, names=("HoleX", "HoleStation", "HoleDia"),
        drives=(None, '"HoleZ"', '"HoleDia"'),
    )
    await ensure_fully_defined(adapter, "hole sketch")
    check("exit_sketch hole", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += hole.apply(adapter, "HoleProfile")
    check(
        "cut hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * FOOT_H + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "HoldDownHole")
    expected -= V_HOLE
    await volume_check(adapter, "hold-down hole", expected, 0.02 * V_HOLE)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    authored = V_TOTAL[AUTHORING_CONFIG]
    await volume_check(
        adapter, "driven bracket (equations neutral)", authored, 0.005 * authored
    )

    # Every model edit precedes the split, so the copied configuration starts
    # from a finished part (the MHA-DT-030 lesson: apply_material sets only the
    # ACTIVE configuration's material).
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)

    for name in CONFIGURATIONS[1:]:
        check(
            f"create_configuration {name}",
            await adapter.create_configuration(
                CreateConfigurationParameters(name=name, comment="north pivot bracket")
            ),
        )
    # Each side's foot end and hole station, set in its own configuration so
    # neither inherits the other's.
    for name in CONFIGURATIONS:
        for variable, value in (("FootZ1", FOOT_Z1[name]), ("HoleZ", HOLE_Z[name])):
            check(
                f"{variable} = {value} in {name}",
                await adapter.set_global_variable(
                    SetGlobalVariableParameters(
                        name=variable, expression=f"{value}mm", configuration=name
                    )
                ),
            )
    for name in (*CONFIGURATIONS[1:], AUTHORING_CONFIG):
        check(f"activate {name}", await adapter.set_active_configuration(name))
        if active_configuration_name(adapter) != name:
            raise RuntimeError(f"configuration {name} did not activate")
        await force_rebuild(adapter)
        await volume_check(
            adapter, f"{name} bracket", V_TOTAL[name], 0.005 * V_TOTAL[name]
        )

    # The three lengths along the foot carry +/-0.10 natively, shared by both
    # configurations (ch_pivot_bracket_spec: the south foot's short run cannot
    # take title-block .XX). The foot length runs from the ear's inboard face
    # to the free end. HoleStation is HoleZ, from the ear's mid-plane, while
    # the spec's stack books the station from the free end, where the S4 hold
    # gauges it off the ledge; on the mid-plane datum the foot-end ligament
    # loses EAR_T_BAND / 2 more (S 2.23, still over the 2.0 target) and every
    # other margin gains. No in-repo sheet prints this part, so a fixture plan
    # or later drawing inherits the bands from the saved model.
    set_dimension_symmetric_tolerance(adapter, "FootProfile", "FootLen", FOOT_LEN_BAND)
    set_dimension_symmetric_tolerance(adapter, "Ear", "EarThick", EAR_T_BAND)
    set_dimension_symmetric_tolerance(adapter, "HoleProfile", "HoleStation", STATION_BAND)

    # One BOM identity for both sides; each configuration's own Number carries
    # its side (the MHA-DT-003-T006 qualifier convention).
    grouped_spec = _config.parts(PART_NAME)
    apply_grouped_bom_properties(
        adapter,
        list(CONFIGURATIONS),
        part_number=str(grouped_spec["number"]),
        description=str(grouped_spec["description"]),
    )
    for name in CONFIGURATIONS:
        _apply_configuration_number(adapter, name, CONFIGURATION_NUMBER[name])
    await report_mass_properties(adapter)
    require_material_in_every_configuration(
        adapter, PART_NAME, MATERIAL, CONFIGURATIONS
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    # The channel assembly places both configurations while the part saves on
    # one; reopen and prove each saved cache regenerates (cg-fx1).
    part_title = str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
    adapter.swApp.CloseDoc(part_title)
    adapter.currentModel = None
    check(f"reopen saved {PART_NAME}", await adapter.open_model(artefacts["part"]))
    assert_saved_configurations_regenerate(adapter, PART_NAME)
    return artefacts

if __name__ == "__main__":
    sys.exit(run_build(build))
