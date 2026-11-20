r"""Reproduction script: recording paper sheet on the platen (book ch. 30).

The white paper the pen traces onto, clipped to the platen's front face.
Every front-quarter ch30 plate (p002/p003/p009) shows the white sheet
covering most of the platen; without it the CAD platen reads as a bare
dark board. Consumable media, but modeled for photo fidelity (M6.8
photo-tuning).

Sized by the ch30-p002 Pose Studio fit to sit between the resized platen
clips with an 18.2007 mm side margin and 3.0 mm top margin. The front
face sits 0.5 mm proud of the platen front
face; the sheet is 0.25 thick so its BACK face keeps the standard 0.25 clear
of the platen instead of landing coplanar on it — two coincident faces
z-fight in the offline renders (the ch30 gallery views read as torn white
shards where the black board and white sheet alternate per pixel).

Layout: width along +X, height along +Y from the origin corner,
thickness extruded +Z (same scheme as build_pd_platen).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_platen_paper.py
"""

from __future__ import annotations

import sys

from _appearance import PAPER_WHITE, apply_color, apply_material
from _check import check
from _dimensions import drive_dimension, set_global
from _document_units import keep_equation_angles_exact
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from _recording_geometry import RECORDING_PAPER_HEIGHT_MM, RECORDING_PAPER_WIDTH_MM

PART_NAME = "pd-platen-paper"
MATERIAL = "Oak"  # nearest wood-fibre entry in the SW database; colour overridden

PAPER_THICKNESS = 0.25  # front face stays 0.5 proud (assembly plants it at
# PLATE_FRONT_Z - 0.5); the thinner sheet leaves 0.25 air behind so the back
# face never coincides with the platen front face (render z-fight)


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", adapter.create_part())
    keep_equation_angles_exact(adapter, label=PART_NAME)

    # Editable knobs (Tools > Equations): the sheet width, height, and the proud
    # thickness (an extrude depth -- a knob, but a feature parameter, so nothing
    # drives it). The mm suffix is load-bearing -- this is an INCH document and
    # the equation manager reads BARE numbers in document units (an unsuffixed
    # 233.2386 = 233.2386 in).
    set_global(adapter, "PaperWidth", f"{RECORDING_PAPER_WIDTH_MM}mm")
    set_global(adapter, "PaperHeight", f"{RECORDING_PAPER_HEIGHT_MM}mm")
    set_global(adapter, "PaperThickness", f"{PAPER_THICKNESS}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Origin-CORNER rectangle (corner at (0,0)), so define_rectilinear_chain --
    # not define_centered_rectangle. Emission order: the per-segment distance dims
    # in line order skipping one redundant span per direction -- width (segment 0,
    # bottom edge) then height (segment 1, right edge) -- then the anchor dims,
    # of which there are none (the anchor vertex is the origin).
    paper = SketchDims()
    check("create_sketch outline", adapter.create_sketch("Front"))
    paper_rect = [
        (0.0, 0.0),
        (RECORDING_PAPER_WIDTH_MM, 0.0),
        (RECORDING_PAPER_WIDTH_MM, RECORDING_PAPER_HEIGHT_MM),
        (0.0, RECORDING_PAPER_HEIGHT_MM),
    ]
    lines = add_line_chain(adapter, paper_rect)
    define_rectilinear_chain(
        adapter, lines, paper_rect, label="paper", dims=paper,
        names=["Width", "Height"],
        drives=['"PaperWidth"', '"PaperHeight"'],
    )
    ensure_fully_defined(adapter, "paper outline")
    check("exit_sketch outline", adapter.exit_sketch())
    name_last_feature(adapter, "PaperProfile")
    drive_jobs += paper.apply(adapter, "PaperProfile")
    check(
        "extrude paper",
        adapter.create_extrusion(ExtrusionParameters(depth=PAPER_THICKNESS)),
    )
    name_last_feature(adapter, "Paper")

    expected = RECORDING_PAPER_WIDTH_MM * RECORDING_PAPER_HEIGHT_MM * PAPER_THICKNESS
    volume_check(adapter, "paper", expected, 0.005 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(adapter, "driven paper (equations neutral)", expected, 0.005 * expected)

    apply_material(adapter, MATERIAL)
    apply_color(adapter, PAPER_WHITE)
    report_mass_properties(adapter)
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
