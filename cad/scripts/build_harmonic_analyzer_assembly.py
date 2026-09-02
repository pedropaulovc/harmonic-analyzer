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
* knife-hanger studs (summing.SLDASM) rise through the top-frame casting's
  integral crossbar (frame.SLDASM), whose set screw grips the gooseneck post
  at the east-rail hub;
* column-clamps (magnifier + paper-drive) ride the Ø25.4 columns (frame) with
  a 25.6 bore;
* the pen-hanger (pen.SLDASM) clamps the wheel-bar (magnifier.SLDASM), and the
  wheel rim -> pen-rod wire couples the two;
* chain sprockets (drive-train crankshaft + paper-drive knob shaft) share the
  z -155 chain plane;
* rocker-arm connecting-rod rings (channel) ride the cam lobes integral
  to the drive-train's cylinder gears;
* the loose measuring-stick stands on its stop block on the base top (y 50.8),
  the stop's thumbscrew head resting on the deck. The spare T18
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

SUBASSEMBLIES = (
    "frame",
    "drive-train",
    "channel",
    "summing",
    "magnifier",
    "pen",
    "paper-drive",
)

# Loose hardware on the base top -- a generic tool, not part of any mechanism.
# Parked on the deck just INBOARD of the west columns, running along Z
# (machine x -183..-175, z -100..100, propped on its stop block ~8 above the
# deck -- see the height derivation below): the old far-west margin
# lane (x -220..-212) is under the base's raised rim since the 2026-09 photo
# re-derive (lip inner edge x -215.25, interference-gate proven 2375 mm^3),
# and the corridor left between rim and columns (5.5) is narrower than the
# 8 mm stick, while the column pair leaves only 198.6 along Z for its 200 --
# so it sits east of the column band (column east face x -184.3, 1.3 clear),
# well clear of the crank column (x >= -150.7) and the rocker-arm-support foot
# (x 41..105). Authored as the EXACT machine transform:
# flat, long axis along Z, GRADUATIONS UP. build_measuring_stick
# cuts the ticks into the local z=0 face (outward normal -Z), so graduations-up
# requires local -Z -> machine +Y, i.e. local +Z -> -Y. The rows therefore map
# part X(length 200)->machine +Z, part Y(width 8)->machine -X, part Z(3 thick)->
# machine -Y; the body hangs in -Y from the graduated face, so the placed corner
# (part origin, on the z=0 face) sits STICK_THICK above the bar's underside.
# POS.x = -175 so the width runs -X into x -175..-183. euler [90,-90,0] is
# rows_from_euler of those rows.
#
# Height (2026-09-02 stop rework): the parked stick is PROPPED ON THE STOP
# BLOCK, as the ch30 plates show it standing on the block rather than flat on
# the deck -- the stop's closed window wraps the bar and its knurled thumbscrew
# head hangs under the block, so the head bottom is what rests on the deck
# (STOP_DECK_GAP above it) and the bar rides SLOT_FLOOR + half the window
# clearance above the block bottom. STICK_POS.y (the graduated top face) is
# therefore derived from the stop's constants, never a literal.
import _telemetry  # noqa: E402
from build_measuring_stick import (  # noqa: E402
    BODY_THICKNESS as STICK_THICK,
    BODY_WIDTH as STICK_WIDTH,
    DIVISION_SPACING as STICK_DIVISION,
    SCALE_START_X as STICK_SCALE_START,
)
from build_measuring_stick_stop import (  # noqa: E402
    HEAD_H as STOP_HEAD_H,
    SLOT_FLOOR as STOP_SLOT_FLOOR,
    SLOT_H as STOP_SLOT_H,
    SLOT_W as STOP_SLOT_W,
)

DECK_TOP_Y = 50.8  # harmonic-base top face
STOP_DECK_GAP = 0.25  # thumbscrew head bottom above the deck (sliver margin)
# The bar (3 thick x 8 wide) must pass the stop's closed window with clearance
# on every side (the window is 8.4 x 3.4, floor 4.0 above the block bottom).
STOP_BAR_CLEAR_Y = (STOP_SLOT_H - STICK_THICK) / 2.0  # 0.2 above and below
assert STOP_BAR_CLEAR_Y > 0.0, (STOP_SLOT_H, STICK_THICK)
assert STOP_SLOT_W - STICK_WIDTH >= 0.2, (STOP_SLOT_W, STICK_WIDTH)

# Stack up from the deck: gap + head + floor + centring clearance = bar
# underside; + bar thickness = the graduated face the part origin sits on.
STICK_BOTTOM_Y = (
    DECK_TOP_Y + STOP_DECK_GAP + STOP_HEAD_H + STOP_SLOT_FLOOR + STOP_BAR_CLEAR_Y
)
STICK_POS = (-170.0, STICK_BOTTOM_Y + STICK_THICK, -100.0)  # 2026-09: 5 further
# inboard so the stop block straddling it clears the base rim's inner edge (x -183)
STICK_EULER = [90.0, -90.0, 0.0]
STICK_ROWS = [[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]]

STOP_MARK = 2.0  # the ch16 p.36 setting
STOP_POS = (
    STICK_POS[0] - STICK_WIDTH / 2.0,  # centred across the bar (part +Y -> machine -X)
    # Bar centred in the window: the block bottom sits SLOT_FLOOR + 0.2 below
    # the bar's underside (the bar rides the window floor + half the clearance).
    STICK_BOTTOM_Y - STOP_SLOT_FLOOR - STOP_BAR_CLEAR_Y,
    STICK_POS[2] + STICK_SCALE_START + STOP_MARK * STICK_DIVISION,
)
STOP_EULER = [0.0, -90.0, 0.0]
STOP_ROWS = [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]
STOP_HEAD_BOTTOM_Y = STOP_POS[1] - STOP_HEAD_H
STICK_DECK_FLOAT = STICK_BOTTOM_Y - DECK_TOP_Y
assert abs(STOP_HEAD_BOTTOM_Y - DECK_TOP_Y - STOP_DECK_GAP) < 1e-6, STOP_HEAD_BOTTOM_Y
assert STICK_DECK_FLOAT > 0.0, STICK_DECK_FLOAT
_telemetry.info(
    f"measuring stick propped on its stop: underside floats {STICK_DECK_FLOAT:.2f} "
    f"above the deck (head bottom {STOP_HEAD_BOTTOM_Y:.2f}, deck {DECK_TOP_Y})"
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
    # transform: flat, graduated face up, long axis along Z.
    await place_component(
        adapter, "measuring-stick", list(STICK_POS), STICK_EULER, STICK_ROWS
    )
    # Its sliding stop (ch16 page001_img01), parked at the 2.0 mark: the
    # block's seat is on the deck, its open-bottom slot straddling the bar
    # (part +X along the stick = machine +Z, +Y up, +Z across = machine -X).
    await place_component(
        adapter, "measuring-stick-stop", list(STOP_POS), STOP_EULER, STOP_ROWS
    )

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
