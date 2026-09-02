r"""Reproduction script: rocker pivot bracket (book ch. 14 pp. 26-27; 2 used).

The black steel bracket that carries each end of the rocker pivot shaft on
the green rocker-arm support (ch14 page002_img01, page002_img07 "pivot"): a
flat rectangular foot screwed to the support's top, and a round-topped ear
plate rising from it, cross-bored for the O6.35 shaft whose bright domed end
shows through the ear. It replaces the photo-refuted chrome ball pillar
(pivot-ball-mount), which the plates never show.

Layout (part frame): seat face at y = 0; foot FOOT_LENGTH along X (the arm
direction) by FOOT_DEPTH along Z (the shaft direction), symmetric about the
origin; ear EAR_WIDTH wide (X) by EAR_T thick (Z), also centred, rising to a
full-round top around the bore at (0, BORE_H); two hold-down holes through
the foot at x = +-HOLE_DX. Symmetric about both the XY and YZ planes, so the
same IDENTITY placement serves both shaft ends.

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
    anchor_point_to_origin,
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
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "pivot-bracket"
MATERIAL = "Plain Carbon Steel"  # black-finished steel (ch14 p.27)

FOOT_LENGTH = 24.0  # X, along the rocker arms (ch14 page002_img01, photo-scaled low)
FOOT_DEPTH = 12.0  # Z, along the shaft
FOOT_H = 6.0
EAR_WIDTH = 14.0  # X; full-round top radius = EAR_WIDTH / 2
EAR_T = 6.0  # Z
BORE_H = 25.2  # shaft axis above the seat (unchanged from the ball mount:
# the rocker pivot stays at machine y 253.8 on the 228.6 support apex)
BORE_DIA = 6.5  # O6.35 shaft, 0.15 diametral clearance
HOLE_DIA = 4.2  # #19-drill hold-down clearance
HOLE_DX = 9.0  # hole centres, outboard of the ear each side

EAR_R = EAR_WIDTH / 2.0
EAR_TOP_Y = BORE_H + EAR_R

V_FOOT = FOOT_LENGTH * FOOT_H * FOOT_DEPTH
V_EAR = (EAR_WIDTH * (BORE_H - FOOT_H) + math.pi * EAR_R**2 / 2.0) * EAR_T
V_BORE = math.pi * (BORE_DIA / 2.0) ** 2 * EAR_T
V_HOLES = 2.0 * math.pi * (HOLE_DIA / 2.0) ** 2 * FOOT_H
V_TOTAL = V_FOOT + V_EAR - V_BORE - V_HOLES


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    await set_global(adapter, "FootLength", f"{FOOT_LENGTH}mm")
    await set_global(adapter, "FootDepth", f"{FOOT_DEPTH}mm")
    await set_global(adapter, "FootH", f"{FOOT_H}mm")
    await set_global(adapter, "EarWidth", f"{EAR_WIDTH}mm")
    await set_global(adapter, "EarT", f"{EAR_T}mm")
    await set_global(adapter, "BoreH", f"{BORE_H}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")
    await set_global(adapter, "HoleDx", f"{HOLE_DX}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Foot: Front-plane rectangle x -L/2..L/2, y 0..FOOT_H, extruded both ways
    # (FOOT_DEPTH total). Anchor vertex 0 at (-L/2, 0): width, height, anchor x.
    half_l = FOOT_LENGTH / 2.0
    foot = SketchDims()
    check("create_sketch foot", await adapter.create_sketch("Front"))
    rect = [(-half_l, 0.0), (half_l, 0.0), (half_l, FOOT_H), (-half_l, FOOT_H)]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="foot", dims=foot,
        names=["FootLength", "FootH", "FootAnchorX"],
        drives=['"FootLength"', '"FootH"', '"FootLength" / 2'],
    )
    await ensure_fully_defined(adapter, "foot sketch")
    check("exit_sketch foot", await adapter.exit_sketch())
    name_last_feature(adapter, "FootProfile")
    drive_jobs += foot.apply(adapter, "FootProfile")
    check(
        "extrude foot",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=FOOT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Foot")
    expected = V_FOOT
    await volume_check(adapter, "foot", expected, 0.005 * V_FOOT)

    # Ear: bottom edge on the foot top (y = FOOT_H), two vertical flanks, a
    # full-round top about the bore centre. Direct-to-DB so the flank/arc join
    # picks up no inferred relations; constrained explicitly below.
    ear = SketchDims()
    check("create_sketch ear", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    bottom = check("ear bottom", await adapter.add_line(-EAR_R, FOOT_H, EAR_R, FOOT_H))
    right = check("ear right flank", await adapter.add_line(EAR_R, FOOT_H, EAR_R, BORE_H))
    arc = check(
        "ear top arc",
        await adapter.add_arc(0.0, BORE_H, EAR_R, BORE_H, -EAR_R, BORE_H),
    )
    left = check("ear left flank", await adapter.add_line(-EAR_R, BORE_H, -EAR_R, FOOT_H))
    set_sketch_direct_db(adapter, False)
    for label, ent, relation in (
        ("ear bottom", bottom, "horizontal"),
        ("ear right flank", right, "vertical"),
        ("ear left flank", left, "vertical"),
    ):
        check(f"{label} {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    for label, a, b in (
        ("bottom-right join", f"{bottom}.end", f"{right}.start"),
        ("right-arc join", f"{right}.end", f"{arc}.start"),
        ("arc-left join", f"{arc}.end", f"{left}.start"),
        ("left-bottom join", f"{left}.end", f"{bottom}.start"),
    ):
        check(label, await adapter.add_sketch_constraint(a, b, "coincident"))
    check(
        "ear width dim",
        await adapter.add_sketch_dimension(bottom, None, "linear", EAR_WIDTH),
    )
    ear.record("EarWidth", '"EarWidth"')
    await anchor_point_to_origin(adapter, f"{bottom}.start", -EAR_R, FOOT_H, "ear corner")
    ear.record("EarAnchorX", '"EarWidth" / 2')
    ear.record("EarAnchorZ", '"FootH"')
    await anchor_point_to_origin(adapter, f"{arc}.center", 0.0, BORE_H, "ear arc centre")
    ear.record("EarArcRise", '"BoreH"')
    check("ear arc radius", await adapter.add_sketch_dimension(arc, None, "radial", EAR_R))
    ear.record("EarR", '"EarWidth" / 2')
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
    expected += V_EAR
    await volume_check(adapter, "ear", expected, 0.01 * V_EAR)

    # Shaft cross-bore through the ear along Z at (0, BORE_H): on-axis in X,
    # so define_circle records the rise + diameter.
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

    # Hold-down holes through the foot (Top-plane circles at x = +-HOLE_DX, on
    # the z = 0 line), cut both ways past the foot height.
    holes = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, HOLE_DX, 0.0, HOLE_DIA / 2.0, "hole +x",
        dims=holes, names=("HoleAx", "HoleAz", "HoleADia"),
        drives=('"HoleDx"', None, '"HoleDia"'),
    )
    await define_circle(
        adapter, -HOLE_DX, 0.0, HOLE_DIA / 2.0, "hole -x",
        dims=holes, names=("HoleBx", "HoleBz", "HoleBDia"),
        drives=('"HoleDx"', None, '"HoleDia"'),
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
    await volume_check(adapter, "driven bracket (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
