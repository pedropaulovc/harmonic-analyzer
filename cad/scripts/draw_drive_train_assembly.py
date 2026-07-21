r"""Create the curated assembly drawing for the drive-train subassembly.

Front / right / bottom / isometric views of ``cad/out/sldasm/drive-train.SLDASM`` plus a
top-level parts BOM and auto-inserted item-number balloons, on the same
hand-made ASME B template every part print uses. The title block resolves from
the custom properties ``build_drive_train_assembly.py`` stamps on the assembly
(Number, Revision, component-drawing material/finish, and the TOL_* cells
``finalize_drawing`` requires).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing_bom import (
    configured_part_numbers,
    insert_identified_bom_table,
)
from _common import check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_auto_balloons_across_views,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["drive_train_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# The drive-train is the machine's WIDEST subassembly but not its tallest: its
# dominant extent is the Z depth -- the crank outboard end (machine z ~-175, plus
# the hanging arm/handle) to the cone-integrator tip end (cone_station(199) ~z
# +106, north arbor pedestal +97.5) -- a ~300 mm span shown horizontally in the
# RIGHT view. In X it runs the crank axis (-122.8) to the alignment-pinion drum
# (~+1), ~125 mm; in Y only ~50.8 (base top) to ~148 (crankshaft axis + gear
# tips), ~100 mm. So the governing on-sheet dimension is the right view's ~300
# mm depth: 1:5 shrinks it to ~60 mm, and the ~125 mm-wide front view to ~25 mm,
# which clears summing's view centers (a larger 1:3 would render the right view
# ~100 mm and collide the front/right views). 1:5 also keeps the whole assembly-
# drawing batch (summing, frame) on one scale.
SHEET_SCALE = (1.0, 5.0)
VIEW_SCALE = (1, 5)

# One BOM row per UNIQUE top-level component of build_drive_train_assembly.py.
# Stems placed more than once collapse to a single QTY row under the standard
# BOM's IgnoreMultiple: arbor-pedestal (south + north), pinion-bracket (front +
# back strap), pinion-pivot-block / pinion-cam-pin / pinion-cam (front + back),
# foot-screw (spring foot + pedestal flange). The cone-gear and cylinder-gear
# ladders are ONE placed seed each -- their siblings are CopyWithMates2 copies
# (cone-gear-N / cylinder-gear-N), never place_component'd, so they carry no
# extra BOM row. Descriptions fill the template's DESCRIPTION column (the parts
# carry no Description custom property, and a blank column reads as unreleased).
BOM_COMPONENTS = {
    "cylinder-gear-shaft": "CYLINDER DRUM ARBOR",
    "arbor-pedestal": "ARBOR PEDESTAL SUPPORT",
    "cone-swing-platform": "CONE SWING PLATFORM",
    "cone-pivot-post": "CONE BIG-END JOURNAL POST",
    "cone-tip-block": "CONE TIP JOURNAL BLOCK",
    "cone-tip-bushing": "CONE TIP SPACER BUSHING",
    "cone-tip-adjuster": "CONE TIP ENDPLAY ADJUSTER",
    "cone-tip-pinch-screw": "CONE TIP PINCH SCREW",
    "cone-lock-knob": "CONE PLATFORM LOCK KNOB",
    "cone-pivot-screw": "CONE SWING PIVOT SCREW",
    "swing-stop-screw": "SWING TRAVEL STOP SCREW",
    "alignment-pinion": "ALIGNMENT PINION DRUM",
    "pinion-bracket": "PINION ENGAGE STRAP",
    "pinion-pivot-block": "PINION PIVOT BLOCK",
    "pinion-pivot-shaft": "PINION TORQUE SHAFT",
    "pinion-lift-rod": "PINION LIFT ROD",
    "pinion-spring": "PINION DISENGAGE SPRING",
    "pinion-cam-pin": "PINION CAM FOLLOWER PIN",
    "pinion-cam": "PINION ECCENTRIC CAM",
    "pinion-lever": "PINION ENGAGE LEVER",
    "pinion-handle": "PINION TEE HANDLE",
    "pinion-arbor": "PINION DRUM ARBOR",
    "slotted-screw": "SLOTTED HOLD-DOWN SCREW",
    "foot-screw": "FOOT MOUNT SCREW",
    "cone-gear-shaft": "CONE GEAR SHAFT",
    "crank-drive-gear": "64T CRANK DRIVE GEAR",
    "cone-gear": "CONE GEAR, T006-T120 BY 6; 1 EACH",
    "cylinder-gear": "CYLINDER DRUM GEAR",
    "crankshaft": "CRANKSHAFT",
    "crank-pinion": "16T CRANK PINION",
    "crank-arm": "CRANK ARM",
    "crank-handle": "CRANK HANDLE",
}
BOM_PART_NUMBERS = configured_part_numbers(tuple(BOM_COMPONENTS))

ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. INSTALL CONE GEARS T006-T120 IN 6-TOOTH STEPS; T120 AT BIG END.",
        "2. SHOWN: CONE PLATFORM ENGAGED; ALIGNMENT PINION DISENGAGED.",
        "3. ADJUST CONE-TIP END PLAY, THEN LOCK THE PINCH SCREW.",
        "4. VERIFY CRANK, CONE SWING, PINION SWING AND CAM SHAFT MOVE FREELY.",
    )
)

# Three-view centers carried over from summing/pen: front and right left-shifted
# to open the right-view/iso gap, iso to the right of them, BOM anchored top-
# right above the title block. The ~30-row BOM grows DOWNWARD from the anchor.
FRONT_CENTER = (0.060, 0.150)
RIGHT_CENTER = (0.130, 0.150)
ISO_CENTER = (0.225, 0.140)
BOTTOM_CENTER = (0.170, 0.078)
# Top-left BOM anchor, top-right of the sheet above the title block, bounded by
# the sheet ZONE band (0.2667); refined against the render.
BOM_ANCHOR = (0.248, 0.265)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open drive-train assembly source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(adapter, scale=SHEET_SCALE)
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Drive-Train Assembly Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank; cone integrator; cylinder drum; pinion engage; parts list",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(
        adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE
    )
    right = place_view(
        adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE
    )
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE
    )
    for view in (front, right, iso, bottom):
        set_hidden_lines_removed(adapter, view)

    insert_identified_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        descriptions=BOM_COMPONENTS,
        part_numbers=BOM_PART_NUMBERS,
        configuration_grouping="same-part",
        label="drive-train assembly",
    )
    # The lower platform and fastener families are occluded in the front/right
    # pair and behind the gear ladders in the pictorial.  The bottom projection
    # exposes those remaining BOM identities rather than accepting an
    # incomplete balloon set.
    add_auto_balloons_across_views(
        adapter, (front, right, iso, bottom), expected=len(BOM_COMPONENTS),
        label="drive-train assembly balloons",
    )
    if add_note(adapter, ASSEMBLY_NOTES, 0.018, 0.052) is None:
        raise RuntimeError("failed to add drive-train assembly notes")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Drive-Train Assembly Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
