r"""Reproduction script: harmonic-analyzer.SLDASM (top level, M6.5).

The complete machine: the seven subassemblies plus the loose hardware, mated
to the frame. Every subassembly is authored in MACHINE coordinates (assembly
origin = base origin, Y up, base top y 50.8, channels along Z, output side -Z),
so each one is inserted at the identity transform and fixed -- the fix-all
strategy of M6.2-M6.4 lifted one level. The output is split by function into
the signal-flow chain summing -> magnifier -> pen (the value) plus paper-drive
(the orthogonal time-base).

Cross-subassembly fits proven by the top-level interference check:

* channel springs (channel.SLDASM) thread the summing-lever plate's O4.5 holes
  (summing.SLDASM) -- gated analytically by
  build_channel_assembly._assert_plate_threading;
* top-crossbar ends face-flush on the top-frame ring rail inner faces
  (frame.SLDASM), knife-stay rod above the ring, gooseneck-clamp around
  the east column (all summing.SLDASM);
* column-clamps (magnifier + paper-drive) ride the Ø25.4 columns (frame) with
  a 25.6 bore;
* the pen-hanger (pen.SLDASM) clamps the wheel-bar (magnifier.SLDASM), and the
  wheel rim -> pen-rod wire couples the two;
* chain sprockets (drive-train crankshaft + paper-drive knob shaft) share the
  z -81 chain plane;
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
    check,
    run_build,
)
from _assembly import (
    assert_component_placed,
    assert_components_fully_defined,
    check_no_interference,
    place_component,
    remap_front_to_machine_front,
    save_assembly_and_images,
)
from _transforms import IDENTITY

import _telemetry

ASM_NAME = "harmonic-analyzer"

SUBASSEMBLIES = ("frame", "drive-train", "channel", "summing", "magnifier", "pen",
                 "paper-drive")

# Loose hardware on the base top -- a generic tool, not part of any mechanism.
# Re-parked to the FAR-WEST margin lane running along Z (machine x -220..-212,
# z -100..100, y 50.8..53.8). The old BACK-band slot (z 121.6..133.35) is now
# filled by the rocker-arm-support foot (z-max 133.35), so the stick moved
# to the ~12.5 mm clear lane between the west columns (west face x -209.7) and the
# west top-plate edge (x -222.25). Authored as the EXACT machine transform
# (mirror=False): flat with graduations up, long axis along Z.
#   rows map part X(length)->machine Z, part Y(width)->machine X, part Z(3 thick)
#   ->machine Y; euler [-90,-90,0] is rows_from_euler of those rows.
STICK_POS = (-220.0, 50.8, -100.0)
STICK_EULER = [-90.0, -90.0, 0.0]
STICK_ROWS = [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

# Render gallery mirroring the book's ch. 30 "Eight Views" chapter: the six
# orthographic faces plus two 3/4 views (the photos walk 45-degree steps
# around the machine; axonometric views are the CAD equivalent).
EIGHT_VIEWS = (
    "front",
    "back",
    "left",
    "right",
    "top",
    "bottom",
    "isometric",
    "trimetric",
)


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
    # transform (mirror=False): flat, graduated face up, long axis along Z.
    await place_component(adapter, "measuring-stick", list(STICK_POS),
                          STICK_EULER, STICK_ROWS, mirror=False)

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)

    # The machine is authored output-side -Z, so SolidWorks' native Front view
    # shows the BACK. Redefine the document's standard views so Front (and the
    # eight-views gallery below, which goes through ShowNamedView2) shows the
    # machine front, and the file opens on it. Geometry is untouched.
    remap_front_to_machine_front(adapter)
    artefacts = await save_assembly_and_images(adapter, ASM_NAME)
    artefacts.update(await export_gallery_and_bom(adapter))
    return artefacts


async def export_gallery_and_bom(adapter) -> dict[str, str]:
    """The top-only artefacts beyond the standard save + DEFAULT_VIEWS: the Ch.30
    eight-views gallery and the parts-only BOM CSV.

    Factored out of :func:`build` so the cheap REFRESH path (refresh_assembly.py)
    regenerates them after a subassembly change -- otherwise the generic refresh
    saves only the .SLDASM + three default views and these top-level deliverables
    go stale (codex review #6). The standard-view remap is already baked into the
    saved .SLDASM, so the gallery's ShowNamedView2 views are correct on reopen; the
    gallery + BOM leave the doc dirty but the .SLDASM on disk stays table-free."""
    artefacts: dict[str, str] = {}
    for view in EIGHT_VIEWS:
        img_path = (OUT_PNG / f"eight-views-{view}.png").resolve()
        check(
            f"export_image eight-views {view}",
            await adapter.export_image(
                {
                    "file_path": str(img_path),
                    "format_type": "png",
                    "width": 1920,
                    "height": 1200,
                    "view_orientation": view,
                }
            ),
        )
        artefacts[f"eight-views-{view}"] = str(img_path)

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
