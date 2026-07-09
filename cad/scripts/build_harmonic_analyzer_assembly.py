r"""Reproduction script: harmonic-analyzer.SLDASM (top level, M6.5).

The complete OPERATING machine: the seven subassemblies plus the loose
hardware, coupled into one working mechanism. Every subassembly is authored in
MACHINE coordinates (assembly origin = base origin, Y up, base top y 50.8,
channels along Z, output side -Z), so each one is inserted at the identity
transform; frame stays FIXED, and the six moving subs are floated, 3-plane
grounded at identity and set FLEXIBLE (one batched toggle), so their
default-`free` internals stay live in the saved doc.

On top of the flexible subs the build authors (see _assembly_top.py):

* the 23 engaged SETUP clamps (``SETUP_<key>``) -- drive-train's cone_swing /
  pinion_swing / pinion_cam setup poses + the 20 channel bar_amplitude
  stations, replayed from the sub park sidecars into top context (the bars
  are Fourier coefficient SETTINGS, clamped while the crank turns; the
  ``machine/amplitude.yaml preset`` config picks config vs square stations);
* the physical cross-sub couplings: 20 cam ring<->lobe point-on-axis mates
  (``CAM_chNN``), the crank->paper chain tie (``CHAIN_crank_paper``), the
  summing->magnifying lever hand-off (``HANDOFF_levers``), and the WIRE-2
  rim->pen scotch yoke (``WIRE2_pen``) -- dragging the crank in the saved
  model articulates the whole machine down to the pen;
* TWO saved Basic Motion studies: ``kinematic`` (crank motor only) and
  ``full`` (motor + the 21 spring force elements) -- the shipped .SLDASM
  opens ready to solve, no runtime study assembly required
  (build_motion_study.py just resolves, solves and samples them).

Cross-subassembly FITS remain proven by the top-level interference check
(channel spring-hook fasteners in the summing plate holes, crossbar/clamp
seats on the frame, chain sprockets on the z -81 plane, rod rings on the cam
lobes, the pen-hanger on the wheel-bar); the DOF gate is the OPERATIONAL one
-- the machine's kinematic chains must read genuinely live
(``assert_top_operational_dof``), not frozen into a display model.

The loose measuring-stick sits on the base top (y 50.8) in the far-west
margin lane. The spare T18 transgear-removable rides inside paper-drive (a
flat sibling of its mounted T24) rather than floating here -- at the top
level its leaf name would collide with the T12/T24 instances nested in
drive-train / paper-drive.

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
    check_no_interference,
    place_component,
    remap_front_to_machine_front,
    save_assembly_and_images,
)
from _assembly_top import (
    _components,
    add_cam_couplings,
    add_output_couplings,
    assert_top_operational_dof,
    author_operation_studies,
    flex_moving_subs,
    replay_setup_clamps,
    require_free_movers,
    tie_paper_chain,
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

    # Fail fast: the coupling web presupposes default-`free` movers.
    require_free_movers()

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
        # Only frame stays FIXED (usually auto-fixed as the first insert). The
        # six movers must stay floatable: a fixed component silently refuses
        # the flexible toggle, so they are 3-plane grounded instead
        # (flex_moving_subs).
        if name == "frame" and not data.get("fixed"):
            check(
                f"fix {name}",
                await adapter.fix_component(ComponentRefParameters(name=comp)),
            )
        assert_component_placed(adapter, comp, [0.0, 0.0, 0.0], IDENTITY)

    # Loose hardware on the base top (not part of any mechanism). Exact machine
    # transform: flat, graduated face up, long axis along Z.
    await place_component(adapter, "measuring-stick", list(STICK_POS),
                          STICK_EULER, STICK_ROWS)

    # Float + 3-plane ground the movers at identity, then ONE batched flexible
    # toggle -- the subs' default-`free` internals are now live in this doc.
    await flex_moving_subs(adapter)

    # The 23 engaged setup clamps (SETUP_*), from the sub park sidecars.
    await replay_setup_clamps(adapter)

    # One full-tree component walk, reused by every coupling + the studies.
    comps = _components(adapter)

    # Physical cross-sub couplings: cams, chain, lever hand-off, WIRE2 yoke.
    await add_cam_couplings(adapter, comps)
    await tie_paper_chain(adapter, comps)
    await add_output_couplings(adapter, comps)

    # Gates: the machine must be kinematically LIVE (not frozen) and fit-clean.
    assert_top_operational_dof(adapter)
    check_no_interference(adapter)

    # The machine is authored output-side -Z, so SolidWorks' native Front view
    # shows the BACK. Redefine the document's standard views so Front (and the
    # eight-views gallery below, which goes through ShowNamedView2) shows the
    # machine front, and the file opens on it. Geometry is untouched.
    remap_front_to_machine_front(adapter)

    # The saved operation studies (kinematic + full), AFTER every mate exists
    # (a mate authored under an existing study risks initial-animation-state
    # corruption) and BEFORE the save that ships them.
    await author_operation_studies(adapter, comps)

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
