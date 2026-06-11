r"""Reproduction script: harmonic-analyzer.SLDASM (top level, M6.5).

The complete machine: the four subassemblies mated to the frame. Every
subassembly is authored in MACHINE coordinates (assembly origin = base
origin, Y up, base top y 50.8, channels along Z, output side -Z), so each
one is inserted at the identity transform and fixed -- the fix-all
strategy of M6.2-M6.4 lifted one level.

Cross-subassembly fits proven by the top-level interference check:

* channel springs (channel.SLDASM) thread the summing plate's O4.5 holes
  (output.SLDASM) -- gated analytically by
  build_channel_assembly._assert_plate_threading;
* top-crossbar ends face-flush on the top-frame ring rail inner faces
  (frame.SLDASM), knife-stay rod above the ring, gooseneck-clamp around
  the east column;
* column-clamps (output) ride the O34.925 columns (frame) with a 35.2
  bore;
* chain sprockets (drive-train crankshaft + output knob shaft) share the
  z -81 chain plane;
* rocker-arm connecting-rod rings (channel) ride the cam lobes integral
  to the drive-train's cylinder gears;
* A-frame foot and loose hardware sit on the base top (y 50.8).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_harmonic_analyzer_assembly.py
"""

from __future__ import annotations

import sys

from _common import (
    OUT_PNG,
    OUT_SLDASM,
    assert_component_placed,
    assert_components_fully_defined,
    check,
    check_no_interference,
    run_build,
    save_assembly_and_images,
)

ASM_NAME = "harmonic-analyzer"

SUBASSEMBLIES = ("frame", "drive-train", "channel", "output")

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

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


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

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    artefacts = await save_assembly_and_images(adapter, ASM_NAME)

    # Ch. 30 eight-views gallery (after the save: gallery + BOM leave the
    # doc dirty, the SLDASM on disk stays table-free).
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

    # Parts-only BOM (flattened through the subassemblies) -> CSV.
    from solidworks_mcp.adapters.base import CreateBomParameters

    bom_path = (OUT_PNG.parent / "harmonic-analyzer-bom.csv").resolve()
    data = check(
        "export_bom_csv",
        await adapter.export_bom_csv(
            CreateBomParameters(bom_type="parts_only", file_path=str(bom_path))
        ),
    )
    print(f"  BOM: {data['rows']} rows -> {data['file_path']}", flush=True)
    artefacts["bom"] = str(bom_path)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
