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
    coincident_mate,
    component_transform,
    distance_driver,
    named_ref,
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
# Parked in the FAR-WEST margin lane running along Z (machine x -220..-212,
# z -100..100, y 50.8..53.8), the ~12.5 mm clear lane between the west columns
# (west face x -209.7) and the west top-plate edge (x -222.25); well clear of the
# rocker-arm-support foot (x 41..105). Authored as the EXACT machine transform
# (mirror=False): flat, long axis along Z, GRADUATIONS UP. build_measuring_stick
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


def _plane_normals_and_origin(adapter, name: str):
    """World normals of a component's (Right, Top, Front) planes + its origin
    (mm). Transform2 is row-major (`world = local.R`), so the world normal of
    the plane whose local normal is local axis i is row i."""
    a = component_transform(adapter, name)
    rows = [(a[0], a[1], a[2]), (a[3], a[4], a[5]), (a[6], a[7], a[8])]
    org = [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]
    return rows, org


async def _locate_to_datum(adapter, name: str) -> None:
    """Locate a component by three orthogonal plane-distance mates to the
    machine datum planes -- the semantic replacement for a fix (#110 idiom).
    Orientation-agnostic: each principal plane is paired to the datum plane
    whose world normal is most parallel, and the perpendicular distance is the
    origin offset projected onto that normal. Valid for parts whose planes are
    (near-)parallel to the datum -- here every subassembly is authored in
    machine coordinates at the identity transform (origin coincident), so each
    pairs to its own datum plane at distance 0 (a coincident mate)."""
    planes = ("Right Plane", "Top Plane", "Front Plane")
    datum_n = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    part_n, o = _plane_normals_and_origin(adapter, name)
    used: set[int] = set()
    for li, part_plane in enumerate(planes):
        n = part_n[li]
        bi = max((j for j in range(3) if j not in used),
                 key=lambda j: abs(sum(n[k] * datum_n[j][k] for k in range(3))))
        used.add(bi)
        coord = o[bi]  # datum normals are the axes, so the projection is the axis coord
        part_ref = named_ref(f"{part_plane}@{name}", "PLANE")
        base_ref = named_ref(planes[bi], "PLANE")
        tag = f"{part_plane.split()[0]}->{planes[bi].split()[0]}"
        if abs(coord) < 1e-6:
            await coincident_mate(adapter, part_ref, base_ref,
                                  label=f"{name} datum {tag}=0", verify=(name, o))
            continue
        await distance_driver(adapter, part_ref, base_ref, abs(coord),
                              label=f"{name} datum {tag} d={abs(coord):.2f}",
                              verify=(name, o))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        InsertComponentParameters,
    )

    check("create_assembly", await adapter.create_assembly())

    # Each subassembly is authored in machine coordinates, so it is inserted at
    # the identity transform. frame is FIRST -> the auto-fixed assembly seed;
    # every other subassembly is datum-located (three plane mates to the
    # coincident machine datum planes), not fixed -- the #110 cleanup lifted one
    # level. Each sub rides through the seat as one rigid body either way.
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
        assert_component_placed(adapter, comp, [0.0, 0.0, 0.0], IDENTITY)
        if data.get("fixed"):
            continue  # frame = auto-fixed seed
        await _locate_to_datum(adapter, comp)

    # Loose hardware on the base top (not part of any mechanism). Exact machine
    # transform (mirror=False): flat, graduated face up, long axis along Z. Its
    # rows are an axis-aligned permutation, so it datum-locates instead of being
    # fixed (the #110 cleanup) -- not the seed (frame is).
    stick = await place_component(adapter, "measuring-stick", list(STICK_POS),
                                  STICK_EULER, STICK_ROWS, mirror=False, ground=False)
    await _locate_to_datum(adapter, stick)

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
