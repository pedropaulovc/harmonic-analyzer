r"""Reproduction script: ha-harmonic-analyzer.SLDASM (top level, M6.5).

The complete machine: the seven subassemblies plus the loose hardware, mated
to the frame. Every subassembly is authored in MACHINE coordinates (assembly
origin = base origin, Y up, base top y 50.8, channels along Z, output side -Z),
so each one is inserted at the identity transform and fixed -- the fix-all
strategy of M6.2-M6.4 lifted one level. The output is split by function into
the signal-flow chain summing -> magnifier -> pen (the value) plus paper-drive
(the orthogonal time-base).

Cross-subassembly fits proven by the top-level interference check:

* channel spring anchors (ch-channel.SLDASM) thread DOWN into the 20 #6-32 taps
  through the summing-lever plate (sm-summing.SLDASM), each eye standing above
  the plate where the spring's lower eye links on and each trimmed shank
  stopping 1/16 in above the plate's underside -- gated analytically by
  build_ch_channel_assembly._assert_spring_mount;
* knife-hanger screws (sm-summing.SLDASM) drop through the #6 counterbores in
  the top-frame casting's integral crossbar (fr-frame.SLDASM) with O4.318
  clearance, each head seated on its counterbore floor, and each pressed
  knife-mount dowel stands in the crossbar underside's O3.24 slip hole short
  of its floor; the knife-mount top seats touch the underside face to face
  (gap 0), coincident contact the gate does not count as interference.  The
  casting's set screw grips the gooseneck post at the east-rail hub;
* column-clamps (magnifier + paper-drive) ride the Ø25.4 columns (frame) with
  a 25.6 bore;
* the pen-hanger (pn-pen.SLDASM) clamps the wheel-bar (mg-magnifier.SLDASM), and the
  wheel rim -> pen-rod wire couples the two;
* chain sprockets (drive-train crankshaft + paper-drive knob shaft) share the
  z -155.7 chain plane (pd_transgear_removable_spec.CHAIN_MID_Z);
* rocker-arm connecting-rod rings (channel) ride the cam lobes integral
  to the drive-train's cylinder gears;
* the loose measuring-stick stands on its stop block on the base top (y 50.8),
  the stop's thumbscrew head resting on the deck. The spare T18
  transgear-removable, a swap part for the platen drive, rides inside
  paper-drive (a flat sibling of its mounted T24) rather than floating here --
  at the top level its leaf name would collide with the T12/T24 instances
  nested in drive-train / paper-drive.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ha_harmonic_analyzer_assembly.py
"""

from __future__ import annotations

import sys

from _check import check
from _custom_properties import apply_custom_properties
from _paths import OUT_PNG, OUT_SLDASM
from _session import run_build
from _drawing_marks import DRAWN_BY
from _assembly import (
    activate_assembly_contract,
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
from _chain_mounts import mounted_wheels

import _telemetry

ASM_NAME = "ha-harmonic-analyzer"

SUBASSEMBLIES = (
    "fr-frame",
    "dt-drive-train",
    "ch-channel",
    "sm-summing",
    "mg-magnifier",
    "pn-pen",
    "pd-paper-drive",
)

# Loose hardware on the base top -- a generic tool, not part of any mechanism.
# Parked on the base's green land just INBOARD of the west columns, running
# along Z (machine x -178..-170, z -100..100, propped on its stop block ~8
# above the land -- see the height derivation below). The user ruling of
# 2026-10-09 took away the raised rim and set a black deck at x -167..167, 3.0
# above the land: the stick and its stop (block x -180..-168, head Ø7 at
# x -174) sit wholly in the land corridor between the deck's east edge and the
# column east face (x -184.3), which the old rim narrowed to 5.5 -- too narrow
# for the 8 mm stick. The column pair leaves only 198.6 along Z for its 200,
# so the stick stays east of the column band, well clear of the crank column
# (x >= -150.7) and the rocker-arm-support foot (x 41..105). Authored as the
# EXACT machine transform:
# flat, long axis along Z, GRADUATIONS UP. build_ha_measuring_stick
# cuts the ticks into the local z=0 face (outward normal -Z), so graduations-up
# requires local -Z -> machine +Y, i.e. local +Z -> -Y. The rows therefore map
# part X(length 200)->machine +Z, part Y(width 8)->machine -X, part Z(3 thick)->
# machine -Y; the body hangs in -Y from the graduated face, so the placed corner
# (part origin, on the z=0 face) sits STICK_THICK above the bar's underside.
# POS.x = -170 so the width runs -X into x -170..-178. euler [90,-90,0] is
# rows_from_euler of those rows.
#
# Height (2026-09-02 stop rework): the parked stick is PROPPED ON THE STOP
# BLOCK, as the ch30 plates show it standing on the block rather than flat on
# the base -- the stop's closed window wraps the bar and its knurled thumbscrew
# head hangs under the block, so the head bottom is what rests on the green
# land (STOP_LAND_GAP above it) and the bar rides SLOT_FLOOR + half the window
# clearance above the block bottom. STICK_POS.y (the graduated top face) is
# therefore derived from the stop's constants, never a literal.
from build_ha_measuring_stick import (  # noqa: E402
    BODY_THICKNESS as STICK_THICK,
    BODY_WIDTH as STICK_WIDTH,
    DIVISION_SPACING as STICK_DIVISION,
    SCALE_START_X as STICK_SCALE_START,
)
from build_ha_measuring_stick_stop import (  # noqa: E402
    BLOCK_DEPTH as STOP_BLOCK_DEPTH,
    HEAD_H as STOP_HEAD_H,
    SLOT_FLOOR as STOP_SLOT_FLOOR,
    SLOT_H as STOP_SLOT_H,
    SLOT_W as STOP_SLOT_W,
)
from fr_harmonic_base_spec import DECK_HALF_X, GREEN_TOP  # noqa: E402

LAND_TOP_Y = GREEN_TOP  # the harmonic base's green land the stop rests on
STOP_LAND_GAP = 0.25  # thumbscrew head bottom above the land (sliver margin)
# The bar (3 thick x 8 wide) must pass the stop's closed window with clearance
# on every side (the window is 8.4 x 3.4, floor 4.0 above the block bottom).
STOP_BAR_CLEAR_Y = (STOP_SLOT_H - STICK_THICK) / 2.0  # 0.2 above and below
assert STOP_BAR_CLEAR_Y > 0.0, (STOP_SLOT_H, STICK_THICK)
assert STOP_SLOT_W - STICK_WIDTH >= 0.2, (STOP_SLOT_W, STICK_WIDTH)

# Stack up from the land: gap + head + floor + centring clearance = bar
# underside; + bar thickness = the graduated face the part origin sits on.
STICK_BOTTOM_Y = (
    LAND_TOP_Y + STOP_LAND_GAP + STOP_HEAD_H + STOP_SLOT_FLOOR + STOP_BAR_CLEAR_Y
)
STICK_POS = (-170.0, STICK_BOTTOM_Y + STICK_THICK, -100.0)
# The stop block (12 wide in x, centred on the bar) must stay off the deck's
# east edge, and the bar inside the land corridor short of the west columns.
assert STICK_POS[0] - STICK_WIDTH / 2.0 + STOP_BLOCK_DEPTH / 2.0 < -DECK_HALF_X
assert STICK_POS[0] - STICK_WIDTH > -184.3
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
STICK_LAND_FLOAT = STICK_BOTTOM_Y - LAND_TOP_Y
assert abs(STOP_HEAD_BOTTOM_Y - LAND_TOP_Y - STOP_LAND_GAP) < 1e-6, STOP_HEAD_BOTTOM_Y
assert STICK_LAND_FLOAT > 0.0, STICK_LAND_FLOAT
_telemetry.info(
    f"measuring stick propped on its stop: underside floats {STICK_LAND_FLOAT:.2f} "
    f"above the green land (head bottom {STOP_HEAD_BOTTOM_Y:.2f}, land {LAND_TOP_Y})"
)


def _subassembly(name: str) -> str:
    path = (OUT_SLDASM / f"{name}.SLDASM").resolve()
    if not path.exists():
        raise RuntimeError(
            f"missing subassembly {path}; run build_{name.replace('-', '_')}_assembly.py first"
        )
    return str(path)


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
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
        adapter, "ha-measuring-stick", list(STICK_POS), STICK_EULER, STICK_ROWS
    )
    # Its sliding stop (ch16 page001_img01), parked at the 2.0 mark: the
    # block's seat is on the deck, its open-bottom slot straddling the bar
    # (part +X along the stick = machine +Z, +Y up, +Z across = machine -X).
    await place_component(
        adapter, "ha-measuring-stick-stop", list(STOP_POS), STOP_EULER, STOP_ROWS
    )

    assert_components_fully_defined(adapter)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
        chain_mounts=mounted_wheels(),
    )

    # Title-block identity for the top assembly drawing
    # (draw_ha_harmonic_analyzer_assembly.py): assembly_title_properties supplies
    # Title/Generator and the TOL_* general-tolerance cells finalize_drawing
    # hard-requires; material/finish defer to each released component drawing
    # because the top-level BOM has no material/finish columns.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
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

    bom_path = (OUT_PNG.parent / "ha-harmonic-analyzer-bom.csv").resolve()
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
