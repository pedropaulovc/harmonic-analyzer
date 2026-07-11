r"""Reproduction script: recording paper sheet on the platen (book ch. 30).

The white paper the pen traces onto, clipped to the platen's front face.
Every front-quarter ch30 plate (p002/p003/p009) shows the white sheet
covering most of the platen; without it the CAD platen reads as a bare
dark board. Consumable media, but modeled for photo fidelity (M6.8
photo-tuning).

Sized to sit between the two platen clips (clip bands at platen-local
x 8..18 and 280..290 - see build_paper_drive_assembly CLIP_FRONT_DX) with a
6 mm top/bottom margin. The front face sits 0.5 mm proud of the platen front
face; the sheet is 0.25 thick so its BACK face keeps the standard 0.25 clear
of the platen instead of landing coplanar on it — two coincident faces
z-fight in the offline renders (the ch30 gallery views read as torn white
shards where the black board and white sheet alternate per pixel).

Layout: width along +X, height along +Y from the origin corner,
thickness extruded +Z (same scheme as build_platen).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_platen_paper.py
"""

from __future__ import annotations

import sys

from _common import (
    PAPER_WHITE,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
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

PART_NAME = "platen-paper"
MATERIAL = "Oak"  # nearest wood-fibre entry in the SW database; colour overridden

PAPER_WIDTH = 259.5  # spans platen-local x 20.25..279.75: 2.25 clear of
# each clip band (8..18 / 280..290) per the 0.25-margin design rule
PAPER_HEIGHT = 128.0  # platen 140 minus 6 top/bottom margins
PAPER_THICKNESS = 0.25  # front face stays 0.5 proud (assembly plants it at
# PLATE_FRONT_Z - 0.5); the thinner sheet leaves 0.25 air behind so the back
# face never coincides with the platen front face (render z-fight)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the sheet width, height, and the proud
    # thickness (an extrude depth -- a knob, but a feature parameter, so nothing
    # drives it). The mm suffix is load-bearing -- this is an INCH document and
    # the equation manager reads BARE numbers in document units (an unsuffixed
    # 259.5 = 259.5 in).
    await set_global(adapter, "PaperWidth", f"{PAPER_WIDTH}mm")
    await set_global(adapter, "PaperHeight", f"{PAPER_HEIGHT}mm")
    await set_global(adapter, "PaperThickness", f"{PAPER_THICKNESS}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Origin-CORNER rectangle (corner at (0,0)), so define_rectilinear_chain --
    # not define_centered_rectangle. Emission order: the per-segment distance dims
    # in line order skipping one redundant span per direction -- width (segment 0,
    # bottom edge) then height (segment 1, right edge) -- then the anchor dims,
    # of which there are none (the anchor vertex is the origin).
    paper = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    paper_rect = [
        (0.0, 0.0),
        (PAPER_WIDTH, 0.0),
        (PAPER_WIDTH, PAPER_HEIGHT),
        (0.0, PAPER_HEIGHT),
    ]
    lines = await add_line_chain(adapter, paper_rect)
    await define_rectilinear_chain(
        adapter, lines, paper_rect, label="paper", dims=paper,
        names=["Width", "Height"],
        drives=['"PaperWidth"', '"PaperHeight"'],
    )
    await ensure_fully_defined(adapter, "paper outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "PaperProfile")
    drive_jobs += paper.apply(adapter, "PaperProfile")
    check(
        "extrude paper",
        await adapter.create_extrusion(ExtrusionParameters(depth=PAPER_THICKNESS)),
    )
    name_last_feature(adapter, "Paper")

    expected = PAPER_WIDTH * PAPER_HEIGHT * PAPER_THICKNESS
    await volume_check(adapter, "paper", expected, 0.005 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven paper (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PAPER_WHITE)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
