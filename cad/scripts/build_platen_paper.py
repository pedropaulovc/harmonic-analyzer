r"""Reproduction script: recording paper sheet on the platen (book ch. 30).

The white paper the pen traces onto, clipped to the platen's front face.
Every front-quarter ch30 plate (p002/p003/p009) shows the white sheet
covering most of the platen; without it the CAD platen reads as a bare
dark board. Consumable media, but modeled for photo fidelity (M6.8
photo-tuning).

Sized to sit between the two platen clips (clip bands at platen-local
x 8..18 and 280..290 - see build_output_assembly CLIP_FRONT_DX) with a
6 mm top/bottom margin, 0.5 mm proud of the platen front face.

Layout: width along +X, height along +Y from the origin corner,
thickness extruded +Z (same scheme as build_platen).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_platen_paper.py
"""

from __future__ import annotations

import sys

from _common import (
    PAPER_WHITE,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
)

PART_NAME = "platen-paper"
MATERIAL = "Oak"  # nearest wood-fibre entry in the SW database; colour overridden

PAPER_WIDTH = 259.5  # spans platen-local x 20.25..279.75: 2.25 clear of
# each clip band (8..18 / 280..290) per the 0.25-margin design rule
PAPER_HEIGHT = 128.0  # platen 140 minus 6 top/bottom margins
PAPER_THICKNESS = 0.5


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    check("create_sketch outline", await adapter.create_sketch("Front"))
    paper_rect = [
        (0.0, 0.0),
        (PAPER_WIDTH, 0.0),
        (PAPER_WIDTH, PAPER_HEIGHT),
        (0.0, PAPER_HEIGHT),
    ]
    lines = await add_line_chain(adapter, paper_rect)
    await define_rectilinear_chain(adapter, lines, paper_rect, label="paper")
    await ensure_fully_defined(adapter, "paper outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude paper",
        await adapter.create_extrusion(ExtrusionParameters(depth=PAPER_THICKNESS)),
    )

    res = await adapter.get_mass_properties()
    vol = res.data.volume
    expected = PAPER_WIDTH * PAPER_HEIGHT * PAPER_THICKNESS
    print(f"  volume: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"paper volume {vol:.1f} != {expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PAPER_WHITE)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
