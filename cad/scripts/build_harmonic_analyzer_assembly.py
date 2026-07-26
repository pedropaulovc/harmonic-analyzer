r"""Reproduction script: harmonic-analyzer.SLDASM (top level, M6.5).

The complete machine: the seven subassemblies plus the loose hardware, mated
to the frame. Every subassembly is authored in MACHINE coordinates (assembly
origin = base origin, Y up, base top y 50.8, channels along Z, output side -Z),
so each one is inserted at the identity transform and fixed -- the fix-all
strategy of M6.2-M6.4 lifted one level. The output is split by function into
the signal-flow chain summing -> magnifier -> pen (the value) plus paper-drive
(the orthogonal time-base).

Cross-subassembly fits proven by the top-level interference check:

* channel spring-hook fasteners (channel.SLDASM) seat shank-up in the
  summing-lever plate's O4.5 holes (summing.SLDASM), each presenting its arm
  just above the plate where the spring's bottom eye links on -- gated
  analytically by build_channel_assembly._assert_hook_fastener;
* top-crossbar ends face-flush on the top-frame ring rail inner faces
  (frame.SLDASM), gooseneck-clamp around the east column (all summing.SLDASM);
* column-clamps (magnifier + paper-drive) ride the Ø25.4 columns (frame) with
  a 25.6 bore;
* the pen-hanger (pen.SLDASM) clamps the wheel-bar (magnifier.SLDASM), and the
  wheel rim -> pen-rod wire couples the two;
* chain sprockets (drive-train crankshaft + paper-drive knob shaft) share the
  z -155 chain plane;
* rocker-arm connecting-rod rings (channel) ride the cam lobes integral
  to the drive-train's cylinder gears;
* the loose measuring-stick sits on the base top (y 50.8). The spare T18
  transgear-removable, a swap part for the platen drive, rides inside
  paper-drive (a flat sibling of its mounted T24) rather than floating here --
  at the top level its leaf name would collide with the T12/T24 instances
  nested in drive-train / paper-drive.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_harmonic_analyzer_assembly.py
"""

from __future__ import annotations

import sys

from _common import (
    OUT_PNG,
    OUT_SLDASM,
    apply_custom_properties,
    apply_summary_info,
    check,
    run_build,
)
from _drawing_marks import DRAWN_BY
from _assembly import (
    _discard_copy_source,
    assembly_title_properties,
    assert_component_placed,
    assert_components_fully_defined,
    check_no_interference,
    place_component,
    remap_front_to_machine_front,
    save_assembly_and_images,
)
from _transforms import IDENTITY
from _interference_contracts import allowed_interference_pairs

import _telemetry

ASM_NAME = "harmonic-analyzer"

SUBASSEMBLIES = ("frame", "drive-train", "channel", "summing", "magnifier", "pen",
                 "paper-drive")

# Loose hardware on the base top -- a generic tool, not part of any mechanism.
# Parked in the FAR-WEST margin lane running along Z (machine x -220..-212,
# z -100..100, y 50.8..53.8), the ~12.5 mm clear lane between the west columns
# (west face x -209.7) and the west top-plate edge (x -222.25); well clear of the
# rocker-arm-support foot (x 41..105). Authored as the EXACT machine transform:
# flat, long axis along Z, GRADUATIONS UP. build_measuring_stick
# cuts the ticks into the local z=0 face (outward normal -Z), so graduations-up
# requires local -Z -> machine +Y, i.e. local +Z -> -Y. The rows therefore map
# part X(length 200)->machine +Z, part Y(width 8)->machine -X, part Z(3 thick)->
# machine -Y; the body hangs in -Y from the graduated face, so the placed corner
# (part origin, on the z=0 face) sits at y 53.8 = base-top 50.8 + 3 thickness,
# dropping the body onto the base with the graduated face up. POS.x = -212 so the
# width runs -X into x -212..-220 (same lane as before, on the base). euler
# [90,-90,0] is rows_from_euler of those rows.
STICK_POS = (-212.0, 53.8, -100.0)
STICK_EULER = [90.0, -90.0, 0.0]
STICK_ROWS = [[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]]

def _subassembly(name: str) -> str:
    path = (OUT_SLDASM / f"{name}.SLDASM").resolve()
    if not path.exists():
        raise RuntimeError(
            f"missing subassembly {path}; run build_{name.replace('-', '_')}_assembly.py first"
        )
    return str(path)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    check("create_assembly", await adapter.create_assembly())

    for name in SUBASSEMBLIES:
        data = check(
            f"insert {name}.SLDASM",
            await adapter.insert_component(
                InsertComponentParameters(
                    file_path=_subassembly(name),
                    position=[0.0, 0.0, 0.0],
                    rotation=[0.0, 0.0, 0.0],
                )
            ),
        )
        comp = data["name"]
        if not data.get("fixed"):
            check(
                f"fix {name}",
                await adapter.fix_component(ComponentRefParameters(name=comp)),
            )
        assert_component_placed(adapter, comp, [0.0, 0.0, 0.0], IDENTITY)

    # Loose hardware on the base top (not part of any mechanism). Exact machine
    # transform: flat, graduated face up, long axis along Z.
    await place_component(adapter, "measuring-stick", list(STICK_POS),
                          STICK_EULER, STICK_ROWS)

    assert_components_fully_defined(adapter)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )

    # Title-block identity for the top assembly drawing
    # (draw_harmonic_analyzer_assembly.py): assembly_title_properties supplies
    # Title/Generator and the TOL_* general-tolerance cells finalize_drawing
    # hard-requires; material/finish defer to each released component drawing
    # because the top-level BOM has no material/finish columns.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            # MHA-A## = assembly-drawing ids (A08 = the top machine assembly).
            "Number": "MHA-A08",
            "Revision": "A",
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")

    # The machine is authored output-side -Z, so SolidWorks' native Front view
    # shows the BACK. Redefine the document's standard views so Front (and the
    # eight-views gallery below, which goes through ShowNamedView2) shows the
    # machine front, and the file opens on it. Geometry is untouched.
    remap_front_to_machine_front(adapter)
    artefacts = await save_assembly_and_images(adapter, ASM_NAME)
    # save_assembly_and_images deliberately discards the dirty anonymous source
    # after its SaveAsCopy.  Reopen the clean copy for the top-only gallery/BOM;
    # those exports dirty the reopened document, so discard it again without
    # saving to keep the shipped assembly table-free.
    asm_path = (OUT_SLDASM / f"{ASM_NAME}.SLDASM").resolve()
    check(f"reopen {ASM_NAME} for gallery/BOM", await adapter.open_model(str(asm_path)))
    try:
        artefacts.update(await export_gallery_and_bom(adapter))
    finally:
        _discard_copy_source(adapter)
    return artefacts


async def export_gallery_and_bom(adapter) -> dict[str, str]:
    """Export the top-level parts-only BOM CSV.

    Factored out of :func:`build` so the cheap REFRESH path (refresh_assembly.py)
    regenerates them after a subassembly change -- otherwise the generic refresh
    saves only the .SLDASM + three default views and these top-level deliverables
    go stale (codex review #6). The standard-view remap is already baked into the
    saved .SLDASM, so the gallery's ShowNamedView2 views are correct on reopen; the
    BOM export leaves the doc dirty but the .SLDASM on disk stays table-free."""
    artefacts: dict[str, str] = {}
    for stale in OUT_PNG.glob("eight-views-*.png"):
        stale.unlink()

    from solidworks_mcp.adapters.base import CreateBomParameters

    bom_path = (OUT_PNG.parent / "harmonic-analyzer-bom.csv").resolve()
    data = check(
        "export_bom_csv",
        await adapter.export_bom_csv(
            CreateBomParameters(bom_type="parts_only", file_path=str(bom_path))
        ),
    )
    _telemetry.info(f"BOM: {data['rows']} rows -> {data['file_path']}")
    artefacts["bom"] = str(bom_path)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
