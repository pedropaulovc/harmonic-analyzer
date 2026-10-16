r"""Reproduction script: ha-harmonic-analyzer.SLDASM (top level, M6.5).

The complete machine: the seven machine subassemblies plus the parked
measuring stick, mated to the frame. Every machine subassembly is authored in
MACHINE coordinates (assembly origin = base origin, Y up, base top y 50.8,
channels along Z, output side -Z), so each one is inserted at the identity
transform and fixed -- the fix-all strategy of M6.2-M6.4 lifted one level.
The measuring stick (ms-measuring-stick.SLDASM) is authored in its stop's own
frame, so it is inserted at the explicit park transform derived below and
fixed. The output is split by function into the signal-flow chain summing ->
magnifier -> pen (the value) plus paper-drive (the orthogonal time-base).

Cross-subassembly fits proven by the top-level interference check:

* channel spring anchors (ch-channel.SLDASM) thread DOWN into the 20 #6-32 taps
  through the summing-lever plate (sm-summing.SLDASM), each eye standing above
  the plate where the spring's lower eye links on and each trimmed shank
  stopping 1/16 in above the plate's underside -- gated analytically by
  build_ch_channel_assembly._assert_spring_mount;
* cut #10-24 plain hex bolts (sm-summing.SLDASM) pass the top-frame crossbar's
  O6.045 loose clearance holes (fr-frame.SLDASM); each under-head face seats
  on its new SAE washer, whose lower bearing face seats on the crossbar's
  faced top 36.50 above the finished underside. Each pressed knife-mount
  dowel stands in the underside's O3.24 slip hole or slot short of its floor.
  Knife-mount top seats touch the underside face to face (gap 0); bearing
  contacts allow zero solid overlap. The casting's set screw grips the
  gooseneck post at the east-rail hub;
* column-clamps (magnifier + paper-drive) ride the Ø25.4 columns (frame) with
  a 25.6 bore;
* the pen-hanger (pn-pen.SLDASM) clamps the wheel-bar (mg-magnifier.SLDASM), and the
  wheel rim -> pen-rod wire couples the two;
* chain sprockets (drive-train crankshaft + paper-drive knob shaft) share the
  z -155.7 chain plane (pd_transgear_removable_spec.CHAIN_MID_Z);
* rocker-arm connecting-rod rings (channel) ride the cam lobes integral
  to the drive-train's cylinder gears;
* the measuring stick (ms-measuring-stick.SLDASM, stop clamped at the 2.0
  mark) is parked on the base's green land (y 47.8) east of the deck, the
  stop's thumbscrew head just above the land. The spare T18
  transgear-removable, a swap part for the platen drive, rides inside
  paper-drive (a flat sibling of its mounted T24) rather than floating here --
  at the top level its leaf name would collide with the T12/T24 instances
  nested in drive-train / paper-drive.

The fitter package (draw_ha_harmonic_analyzer_assembly.py, MHA-HA-000) reads
two things this build authors from ha_harmonic_analyzer_assembly_spec: the
hidden ``IntegrationSettings`` sketch, whose two driving dimensions are the
settings only the complete machine makes (wheel-bar top above the deck, pen
stud head below the bar top), and the named ``HA_EXPLODED`` presentation,
authored in Default and in Default Simplified and collapsed again before save.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ha_harmonic_analyzer_assembly.py
"""

from __future__ import annotations

import sys
from typing import Any

import fr_harmonic_base_spec
import ha_harmonic_analyzer_assembly_spec as spec
import ms_measuring_stick_assembly_spec as ms
from _check import check
from _custom_properties import apply_custom_properties
from _paths import OUT_PNG, OUT_SLDASM
from _session import run_build
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _ha_harmonic_analyzer_explode import create_harmonic_analyzer_explode
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _com import _early_bound
from _assembly import (
    activate_assembly_contract,
    _discard_copy_source,
    assembly_title_properties,
    assert_component_placed,
    assert_components_fully_defined,
    author_in_drawing_configurations,
    check_no_interference,
    remap_front_to_machine_front,
    save_assembly_and_images,
)
from _transforms import IDENTITY, euler_from_rows, rows_from_euler
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
if (*SUBASSEMBLIES, spec.MEASURING_STICK) != spec.BOM_ORDER:
    raise AssertionError("the drawing's BOM order is the insertion order")

# The measuring stick and its clamped stop -- a generic tool, not part of any
# mechanism -- parked on the base's green land just INBOARD of the east
# columns, the stick along Z, GRADUATIONS UP (ms_measuring_stick_assembly_spec:
# the bar's graduated face bears on the stop's roof, +Y of the stop frame). The
# user ruling of 2026-10-09 (#1310) took away the raised rim and set a black
# deck at x -167..167, 3.0 above the land, so the whole stop sits in the land
# corridor between the deck's east edge and the east columns' inboard faces
# (x -184.3).
# The column pair leaves only 198.6 along Z for the 200 bar, so the bar stays
# inboard of the column band, clear of the crank column (x >= -150.7) and the front
# rocker-support band (z <= -118).
#
# The stop frame maps X (along the stick) -> machine +Z, Y (thumbscrew axis,
# up to the roof) -> machine +Y, Z (cover into the block) -> machine -X; the
# bar's own rows compose to part X -> +Z, part Y -> -X, part Z -> -Y.
MS_ROWS = [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]
MS_EULER = euler_from_rows(MS_ROWS)
assert all(
    abs(a - b) < 1e-12
    for got, want in zip(rows_from_euler(MS_EULER), MS_ROWS, strict=True)
    for a, b in zip(got, want, strict=True)
), MS_EULER

LAND_TOP_Y = fr_harmonic_base_spec.GREEN_TOP  # the green land the stop rests on
STOP_LAND_GAP = 0.25  # thumbscrew head bottom above the land (sliver margin)
PARK_WEST_LIMIT_X = -184.3  # east columns' inboard faces
PARK_EAST_LIMIT_X = -fr_harmonic_base_spec.DECK_HALF_X  # the deck's east edge
PARK_FRONT_LIMIT_Z = -118.0  # front rocker-support band (z <= -118)

# Machine image of a stop-frame point p: (P.x - p.z, P.y + p.y, P.z + p.x).
# The stop's machine-X envelope (stop Z, cover-screw heads to the block's back
# wall) is centred in the land corridor; the thumbscrew's head face (the stop's
# lowest Y) sits STOP_LAND_GAP above the land; the 200 bar is centred on z = 0.
MS_POS = (
    (PARK_WEST_LIMIT_X + PARK_EAST_LIMIT_X) / 2.0
    + (ms.EXTENT_MIN[2] + ms.EXTENT_MAX[2]) / 2.0,
    LAND_TOP_Y + STOP_LAND_GAP - ms.THUMB_HEAD_FACE_Y,
    -(ms.STICK_X_MIN + ms.STICK_X_MAX) / 2.0,
)
MS_WEST_X = MS_POS[0] - ms.EXTENT_MAX[2]
MS_EAST_X = MS_POS[0] - ms.EXTENT_MIN[2]
MS_FRONT_Z = MS_POS[2] + ms.EXTENT_MIN[0]
MS_HEAD_BOTTOM_Y = MS_POS[1] + ms.THUMB_HEAD_FACE_Y
MS_STICK_BOTTOM_Y = MS_POS[1] + ms.STICK_BOTTOM_Y
assert MS_WEST_X > PARK_WEST_LIMIT_X, MS_WEST_X
assert MS_EAST_X < PARK_EAST_LIMIT_X, MS_EAST_X
assert MS_FRONT_Z > PARK_FRONT_LIMIT_Z, MS_FRONT_Z
assert abs(MS_HEAD_BOTTOM_Y - LAND_TOP_Y - STOP_LAND_GAP) < 1e-9, MS_HEAD_BOTTOM_Y
assert MS_POS[1] + ms.EXTENT_MIN[1] > LAND_TOP_Y, MS_POS
_telemetry.info(
    f"measuring stick parked: stop x {MS_WEST_X:.2f}..{MS_EAST_X:.2f}, bar underside "
    f"y {MS_STICK_BOTTOM_Y:.2f}, front z {MS_FRONT_Z:.2f} (head bottom "
    f"{MS_HEAD_BOTTOM_Y:.2f}, land {LAND_TOP_Y})"
)


def _subassembly(name: str) -> str:
    path = (OUT_SLDASM / f"{name}.SLDASM").resolve()
    if not path.exists():
        raise RuntimeError(
            f"missing subassembly {path}; run build_{name.replace('-', '_')}_assembly.py first"
        )
    return str(path)


async def _author_integration_settings(adapter: Any) -> None:
    """No solid/pose edits: one vertical construction line per setting, its
    low end anchored to the origin and its length the driving dimension the
    drawing imports (ha_harmonic_analyzer_assembly_spec.SETTING_LINES)."""
    dims = SketchDims()
    check("create integration settings sketch", await adapter.create_sketch("Front"))
    for line_spec in spec.SETTING_LINES:
        label = line_spec.dimension
        # Direct to the database: inference would snap the line ends to the
        # component edges around them, or tie the two lines' common top.
        set_sketch_direct_db(adapter, True)
        line = check(
            f"{label} line",
            await adapter.add_line(
                line_spec.x, line_spec.y_low, line_spec.x, line_spec.y_high
            ),
        )
        set_sketch_direct_db(adapter, False)
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not bool(segment.ConstructionGeometry):
            raise RuntimeError(f"{label} line is not construction")
        check(
            f"{label} vertical",
            await adapter.add_sketch_constraint(line, None, "vertical"),
        )
        await anchor_point_to_origin(
            adapter, f"{line}.start", line_spec.x, line_spec.y_low, f"{label} low end"
        )
        dims.record(f"{label}X")
        dims.record(f"{label}Y")
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "vertical_distance",
            line_spec.length,
            label,
        )
        dims.record(label)
    await ensure_fully_defined(adapter, "integration settings")
    check("exit integration settings sketch", await adapter.exit_sketch())
    name_last_feature(adapter, spec.SETTING_FEATURE)
    dims.apply(adapter, spec.SETTING_FEATURE)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    mark_dimensions_for_drawing(
        adapter,
        spec.SETTING_FEATURE,
        set(spec.DRAWING_DIMENSIONS[spec.SETTING_FEATURE]),
    )
    blank_sketch(adapter, spec.SETTING_FEATURE)


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
    # The measuring stick and its clamped stop, fixed at the exact park
    # transform (not the identity: it is authored in the stop frame).
    data = check(
        "insert ms-measuring-stick.SLDASM",
        await adapter.insert_component(
            InsertComponentParameters(
                file_path=_subassembly("ms-measuring-stick"),
                position=list(MS_POS),
                rotation=MS_EULER,
            )
        ),
    )
    comp = data["name"]
    if not data.get("fixed"):
        check(
            "fix ms-measuring-stick",
            await adapter.fix_component(ComponentRefParameters(name=comp)),
        )
    assert_component_placed(adapter, comp, list(MS_POS), MS_ROWS)

    assert_components_fully_defined(adapter)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
        chain_mounts=mounted_wheels(),
    )
    await _author_integration_settings(adapter)

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
    # Both drawing configurations own the explode: the exploded sheet's 1:10
    # view references Default Simplified.
    author_in_drawing_configurations(
        adapter,
        ASM_NAME,
        lambda configuration: create_harmonic_analyzer_explode(adapter, configuration),
    )
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
