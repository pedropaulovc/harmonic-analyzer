r"""Reproduction script: rocker pivot bracket (MHA-123; book ch. 14 pp. 26-27; 2 used).

The black steel bracket that carries each end of the rocker pivot shaft on
the green rocker-arm support (ch14 page002_img01/img02, page002_img07
"pivot"). 2026-09-02 photo re-derive: it is an L, not a T -- the ear stands
at one END of the foot, and the foot is only as wide as the support's apex.
#743 PR2 (Reading 1, user Q4): the bright dome on the ear is the pivot
shaft's own domed end, not a brazed-on ball, so the ear is a plain plate
arched EAR_W/2 about the O6.5 cross-bore. The north ear's inner face is the
rocker bank's axial datum (the shaft's shoulder bears on it); the south one
is feeler-set (``rocker_bank_layout``).

The channel assembly inserts the SOUTH bracket (inboard = +Z) as IDENTITY
and the NORTH one turned Ry(180) about its bore axis, so both feet run
INBOARD under the outer arms (the support leaves too little apex outboard
of an ear for a 24 foot); inboard, the foot top (y 234.6) clears the arm
bottoms (245.8) and the O10 hubs (248.8).

Layout (part frame; the numbers live in ``pivot_bracket_spec``): seat face
at y = 0; origin under the bore, on the seat plane. Foot FOOT_W along X by
FOOT_H tall by FOOT_Z0..FOOT_Z1 along Z; ear EAR_W wide (X) by EAR_T thick
(Z), centred on the origin: a block from the foot top to the bore height
plus a full O EAR_W boss on the bore axis, whose upper half is the arch (the
arbor-pedestal crown idiom: no arcs, only proven primitives); O BORE_DIA
cross-bore along Z; two hold-down holes through the foot on x = 0 at
z = HOLE_Z.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pivot_bracket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from pivot_bracket_spec import (
    BORE_DIA,
    BORE_H,
    EAR_ARCH_R,
    EAR_T,
    EAR_W,
    FOOT_H,
    FOOT_LEN,
    FOOT_W,
    FOOT_Z0,
    FOOT_Z1,
    HOLE_DIA,
    HOLE_Z,
)


PART_NAME = "pivot-bracket"
MATERIAL = "Plain Carbon Steel"  # black-finished steel (ch14 p.27)

V_FOOT = FOOT_W * FOOT_H * FOOT_LEN
V_BLOCK = EAR_W * (BORE_H - FOOT_H) * EAR_T
V_ARCH = 0.5 * math.pi * EAR_ARCH_R**2 * EAR_T  # the boss's upper half
V_BORE = math.pi * (BORE_DIA / 2.0) ** 2 * EAR_T
V_HOLES = len(HOLE_Z) * math.pi * (HOLE_DIA / 2.0) ** 2 * FOOT_H
V_TOTAL = V_FOOT + V_BLOCK + V_ARCH - V_BORE - V_HOLES
if EAR_ARCH_R != EAR_W / 2.0 or BORE_H - EAR_ARCH_R <= FOOT_H:
    raise AssertionError("the ear boss must be the block's width and clear the foot")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    await set_global(adapter, "FootW", f"{FOOT_W}mm")
    await set_global(adapter, "FootH", f"{FOOT_H}mm")
    await set_global(adapter, "FootLen", f"{FOOT_LEN}mm")
    await set_global(adapter, "FootZ1", f"{FOOT_Z1}mm")
    await set_global(adapter, "EarW", f"{EAR_W}mm")
    await set_global(adapter, "EarT", f"{EAR_T}mm")
    await set_global(adapter, "BoreH", f"{BORE_H}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Foot: Top-plane rectangle (sketch y = model -Z) x +-W/2, z FOOT_Z0..
    # FOOT_Z1, extruded +Y by FOOT_H. Emission: seg0 width, seg1 length, then
    # the (-W/2, -FOOT_Z1) corner anchor (x then z; the anchor z lands at the
    # magnitude FOOT_Z1 -- the magnifying-bracket Top-sketch idiom).
    half_w = FOOT_W / 2.0
    foot = SketchDims()
    check("create_sketch foot", await adapter.create_sketch("Top"))
    rect = [
        (-half_w, -FOOT_Z1),
        (half_w, -FOOT_Z1),
        (half_w, -FOOT_Z0),
        (-half_w, -FOOT_Z0),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="foot", dims=foot,
        names=["FootW", "FootLen", "FootAnchorX", "FootAnchorZ"],
        drives=['"FootW"', '"FootLen"', '"FootW" / 2', '"FootZ1"'],
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
    expected = V_FOOT
    await volume_check(adapter, "foot", expected, 0.005 * V_FOOT)

    # Ear block: Front-plane rectangle x +-EAR_W/2, y FOOT_H..BORE_H,
    # extruded both ways (EAR_T total) -- its Z band is the bore's. Emission:
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

    # Hold-down holes through the foot: Top-plane circles on x = 0 (sketch y
    # = -z), cut both ways past the foot height. On-axis in X, so each
    # records only its z rise + diameter.
    holes = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Top"))
    for tag, z in zip("AB", HOLE_Z, strict=True):
        await define_circle(
            adapter, 0.0, -z, HOLE_DIA / 2.0, f"hole z{z:g}",
            dims=holes, names=(f"Hole{tag}x", f"Hole{tag}z", f"Hole{tag}Dia"),
            drives=(None, None, '"HoleDia"'),
        )
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += holes.apply(adapter, "HoleProfile")
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * FOOT_H + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "HoldDownHoles")
    expected -= V_HOLES
    await volume_check(adapter, "hold-down holes", expected, 0.02 * V_HOLES)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bracket (equations neutral)", V_TOTAL, 0.005 * V_TOTAL)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
