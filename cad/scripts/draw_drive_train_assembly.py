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
import re
import sys
import time
from pathlib import Path
from typing import Any

import _config
import _telemetry
from _assembly_drawing_bom import (
    configured_part_numbers,
    insert_identified_bom_table,
)
from _common import check, run_build
from _drawing_common import (
    DrawingOutputs,
    _edge_endpoint_key,
    _balloon_item_number,
    _spread_balloons,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    iter_views,
    place_view,
    view_name,
)
from pinion_spring_geometry import BLADE_TILT_DEG as PINION_PARK_ANGLE_DEG


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

# Seven sheets let the ~300 mm-wide mechanism use a readable 1:3 scale without
# forcing its 32-row BOM, exterior balloons, concealed-item identification, and
# functional setup data into one field.  All views use the sheet scale so the
# title block remains truthful without per-view scale exceptions.
SHEET_SCALE = (1.0, 3.0)
VIEW_SCALE = (1, 3)
SHEET_NAMES = (
    "GENERAL ASSEMBLY",
    "PARTS LIST",
    "GEAR-TRAIN ITEM IDENTIFICATION",
    "CONCEALED ITEM IDENTIFICATION",
    "GEAR-TRAIN SETUP",
    "PINION ITEM IDENTIFICATION",
    "PINION SETUP AND ACCEPTANCE",
)

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
    "cone-pivot-post": "T120 JOURNAL POST",
    "cone-tip-block": "T006 JOURNAL BLOCK",
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

BOTTOM_VISIBILITY_STEMS = frozenset(
    {"cone-tip-bushing", "cone-gear-shaft", "crank-drive-gear"}
)
CONCEALED_BALLOON_ITEMS = {
    stem: str(index)
    for index, stem in enumerate(BOM_COMPONENTS, start=1)
    if stem in BOTTOM_VISIBILITY_STEMS
}
GENERAL_POINTER_NOTE = (
    "GEAR-TRAIN SETUP: SEE SHEET 5. PINION ITEMS: SEE SHEET 6. "
    "PINION SETUP AND FINAL ACCEPTANCE: SEE SHEET 7."
)

# Sheet 5 holds the source-backed assembly contract in three short columns.
# Interfaces whose fit, retention, torque, or joining process is not defined by
# the part sources are deliberately not completed here with invented values.
_SETUP_NOTE_LINES = (
    (
        "ASSEMBLY NOTES",
        "1. ORIENTATION APPLIES TO ALL SHEETS:",
        "   MACHINE FRONT = PAPER/OUTPUT SIDE (-Z);",
        "   MACHINE BACK = +Z.",
        "   IN THE MACHINE-FRONT VIEW:",
        "   EAST = VIEWER RIGHT (-X);",
        "   WEST = VIEWER LEFT (+X); UP = +Y.",
        '   "T120 END" = ITEM 4 / ITEM 27 T120 END.',
        '   "T006 END" = ITEM 5 / ITEM 27 T006 END.',
        "2. INSTALL ITEM 27 CONE GEARS T120 THROUGH T006",
        "   IN 6-TOOTH STEPS ON ITEM 25 CONE GEAR SHAFT;",
        "   T120 AT ITEM 4 END AND T006 AT ITEM 5 END.",
        "3. SET ITEM 27 CENTER PLANES 40.55 + j(6.889) MM",
        "   FROM ITEM 25 MACHINE-FRONT END FACE, j = 0...19",
        "   FOR T120, T114...T006. SET FACES SQUARE TO",
        "   ITEM 25 AXIS; SOLDER EACH GEAR TO SHAFT; NO KEY.",
        "4. INSTALL ITEM 28 CYLINDER DRUM GEARS FREE TO",
        "   ROTATE ON ITEM 1 CYLINDER DRUM ARBOR. SET ITEM 28",
        "   TOOTHED-DISC MIDPLANES 22.90 + j(7.0565) MM",
        "   FROM ITEM 1 MACHINE-FRONT END, j = 0...19.",
        "   TOOTHED DISC FACES MACHINE FRONT; CAM FACES",
        "   MACHINE BACK. PHASE ALL ITEM 28 INDEX NOTCHES ALIKE.",
        "5. SHOWN: ITEM 3 ENGAGED AND CLAMPED BY ITEM 9;",
        "   ITEM 12 DISENGAGED. LOOSEN ITEM 9 ONLY TO SWING",
        "   ITEM 3. ITEM 11 LIMITS DISENGAGED TRAVEL.",
    ),
    (
        "6. TURN ITEM 7 UNTIL ITEM 25 AXIAL PLAY IS REMOVED",
        "   AND ITEM 25 ROTATES FREELY BY HAND. HOLD ITEM 7;",
        "   TIGHTEN ITEM 8 TO LOCK. RECHECK FREE ROTATION.",
        "7. DISENGAGED: SET 2.00 MM CLEARANCE BETWEEN ITEM 12",
        "   AND ITEM 28 TOOTH-TIP CIRCLE ENVELOPES, MEASURED",
        "   ON THE LINE JOINING THEIR AXES; AXES SHALL BE LEVEL.",
        "8. ENGAGED: SET 41.30 MM C-C BETWEEN ITEM 22 PINION",
        "   DRUM ARBOR AXIS AND ITEM 1 CYLINDER DRUM ARBOR AXIS.",
        "9. AT DISENGAGED PARK, SET THE LINE JOINING ITEM 15",
        "   TORQUE-SHAFT AXIS AND ITEM 22 DRUM-ARBOR AXIS",
        f"   {PINION_PARK_ANGLE_DEG:.2f} DEG TOWARD MACHINE WEST FROM +Y VERTICAL.",
        "   SET BOTH ITEM 13 STRAPS PARALLEL.",
        "10. SET 0.25 MM AXIAL CLEARANCE BETWEEN EACH ITEM 12",
        "   DRUM END FACE AND ADJACENT ITEM 13 INNER FACE.",
        "11. INSTALL BOTH ITEM 19 CAMS ON ITEM 16 WITH",
        "   ECCENTRIC CENTER AND SET-PIN BOSS BELOW ITEM 16",
        "   AXIS AT PARK; PHASE BOTH CAMS ALIKE.",
        "12. SET EACH ITEM 18 FOLLOWER-PIN AXIAL CENTER PLANE",
        "   7.00 MM FROM THE CORRESPONDING ITEM 19",
        "   MACHINE-FRONT END FACE, PARALLEL TO ITEM 16 AXIS.",
        "13. AT PARK, SET 0.10-0.25 MM MINIMUM SURFACE",
        "   CLEARANCE BETWEEN EACH ITEM 18 AND ITEM 19 CAM OD,",
        "   MEASURED AS THE SHORTEST NORMAL DISTANCE.",
        "14. AT PARK, SET ITEM 20 LEVER ROD CENTERLINE 40 DEG",
        "   TOWARD MACHINE EAST FROM +Y VERTICAL; ITEM 19",
        "   ECCENTRICS SHALL BE DOWN.",
        "15. INSTALL ONE ITEM 17 AT THE MACHINE-BACK ITEM 13",
        "   STRAP ONLY; NONE AT THE MACHINE-FRONT STRAP.",
        "   ITEM 17 SHALL RETURN BOTH ITEM 13 STRAPS TO THE",
        "   2.00 MM DISENGAGED GAP.",
        "16. SET 0.05-0.20 MM TANGENTIAL BACKLASH AT EACH",
        "   ITEM 27/28 PITCH-CIRCLE MESH.",
    ),
    (
        "17. FINAL FUNCTIONAL ACCEPTANCE:",
        "   A. WITH ITEM 3 ENGAGED AND ITEM 9 TIGHT, HAND-ROTATE",
        "   ITEM 29 ONE REVOLUTION. ITEM 30/26 AND ALL",
        "   ITEM 27/28 MESHES SHALL ROLL WITHOUT BINDING.",
        "   EACH ITEM 28 SHALL REMAIN FREE ON ITEM 1.",
        "   B. WITH ITEM 12 DISENGAGED, HAND-ROTATE ITEM 21 ONE",
        "   REVOLUTION. ITEM 12/22 SHALL TURN FREELY WITHOUT",
        "   CONTACTING ITEM 28.",
        "   C. OPERATE ITEM 20 FROM PARK UNTIL ITEM 12/28 C-C IS",
        "   41.30 MM. BOTH ITEM 18 FOLLOWERS SHALL MOVE THEIR",
        "   ITEM 13 STRAPS TOGETHER WITHOUT BINDING. RELEASE",
        "   ITEM 20; ITEM 17 SHALL RETURN ITEM 12 TO 2.00 MM GAP.",
        "   D. LOOSEN ITEM 9. ITEM 3 SHALL SWING FREELY TO CONTACT",
        "   ITEM 11 AND RETURN. RETIGHTEN ITEM 9.",
        "   E. AFTER ITEM 8 IS TIGHT, RECHECK ITEM 25 FOR FREE",
        "   ROTATION AND NO AXIAL PLAY.",
    ),
)
SETUP_NOTE_COLUMNS = tuple("\n".join(lines) for lines in _SETUP_NOTE_LINES)
ASSEMBLY_NOTES = "\n".join(
    line for column in _SETUP_NOTE_LINES for line in column
)

# Sheet 1: uncluttered assembly views and a pointer to the setup sheet.
GENERAL_FRONT_CENTER = (0.060, 0.165)
GENERAL_RIGHT_CENTER = (0.190, 0.165)
GENERAL_ISO_CENTER = (0.335, 0.165)
GENERAL_POINTER_ORIGIN = (0.018, 0.070)

# Sheet 2: one continuous 32-row parts list plus a small orientation view.
BOM_ANCHOR = (0.018, 0.266)
BOM_ROW_HEIGHT = 0.0075
BOM_MAX_ROW_HEIGHT = 0.0103
BOM_ISO_CENTER = (0.310, 0.165)

# Sheets 3 and 6: four isolated subsystem views replace the black, overlapping gear
# bands in the former full-assembly identification views.  Every exterior BOM
# family appears in exactly one group and gets one deliberately attached balloon.
EXTERIOR_VIEW_NAMES = ("*Front", "*Isometric", "*Isometric", "*Isometric")
EXTERIOR_VIEW_LABELS = (
    "VIEW A — CONE PLATFORM / GEAR TRAIN",
    "VIEW B — PINION SUPPORT / STRAPS",
    "VIEW C — PINION CAM / CONTROLS",
    "VIEW D — CYLINDER / CRANK",
)
EXTERIOR_VIEW_STEMS = (
    frozenset(
        {
            "cone-swing-platform",
            "cone-pivot-post",
            "cone-tip-block",
            "cone-tip-adjuster",
            "cone-tip-pinch-screw",
            "cone-lock-knob",
            "cone-pivot-screw",
            "swing-stop-screw",
            "cone-gear",
        }
    ),
    frozenset(
        {
            "alignment-pinion",
            "pinion-bracket",
            "pinion-pivot-block",
            "pinion-pivot-shaft",
            "pinion-lift-rod",
            "pinion-spring",
        }
    ),
    frozenset(
        {
            "pinion-cam-pin",
            "pinion-cam",
            "pinion-lever",
            "pinion-handle",
            "pinion-arbor",
            "slotted-screw",
            "foot-screw",
        }
    ),
    frozenset(
        {
            "cylinder-gear-shaft",
            "arbor-pedestal",
            "cylinder-gear",
            "crankshaft",
            "crank-pinion",
            "crank-arm",
            "crank-handle",
        }
    ),
)
GEAR_IDENTIFICATION_VIEW_INDICES = (0, 3)
GEAR_IDENTIFICATION_VIEW_CENTERS = ((0.120, 0.150), (0.320, 0.150))
GEAR_IDENTIFICATION_LABEL_ORIGINS = ((0.070, 0.235), (0.270, 0.235))
PINION_IDENTIFICATION_VIEW_INDICES = (1, 2)
PINION_IDENTIFICATION_VIEW_CENTERS = ((0.120, 0.150), (0.310, 0.150))
PINION_IDENTIFICATION_LABEL_ORIGINS = ((0.070, 0.235), (0.260, 0.235))

# Sheet 4: selected context makes the three concealed families comprehensible
# without duplicating their exterior balloons.
CONCEALED_BOTTOM_CENTER = (0.115, 0.135)
CONCEALED_FRONT_CENTER = (0.285, 0.155)
CONCEALED_BOTTOM_VISIBLE_STEMS = frozenset(
    {
        "cone-pivot-post",
        "cone-tip-block",
        "cone-tip-bushing",
        "cone-tip-adjuster",
        "cone-tip-pinch-screw",
        "cone-gear-shaft",
    }
)
CONCEALED_FRONT_VISIBLE_STEMS = frozenset(
    {"cone-gear-shaft", "crank-drive-gear", "crankshaft", "crank-pinion"}
)
CONCEALED_BOTTOM_STEMS = frozenset({"cone-tip-bushing", "cone-gear-shaft"})
CONCEALED_FRONT_STEMS = frozenset({"crank-drive-gear"})
CONCEALED_BOTTOM_BALLOON_RING_MARGIN = 0.015
CONCEALED_FRONT_BALLOON_RING_MARGIN = 0.025
CONCEALED_BALLOON_CLEARANCE = 0.006
CONCEALED_HEADING_ORIGIN = (0.060, 0.255)
CONCEALED_VIEW_LABEL_ORIGINS = ((0.045, 0.225), (0.245, 0.225))

# Sheet 5: one row is one physical item-27/item-28 mesh pair.  The station
# values are the evaluated source laws from the numbered assembly notes.
CONE_SCHEDULE_ANCHOR = (0.018, 0.232)
CONE_SCHEDULE_COLUMN_WIDTHS = (0.016, 0.025, 0.025, 0.028, 0.075, 0.075)
CONE_SCHEDULE_TEXT_HEIGHT = 0.0025
CONE_SCHEDULE_ROW_HEIGHT = 0.006
GEAR_REQUIREMENTS_ANCHOR = (0.275, 0.232)
GEAR_REQUIREMENTS_COLUMN_WIDTHS = (0.028, 0.072, 0.040)
GEAR_REQUIREMENTS_ROW_HEIGHT = 0.012
GEAR_SETUP_VIEW_CENTERS = ((0.310, 0.095), (0.375, 0.095))
GEAR_SETUP_VIEW_SCALE = (1, 5)
GEAR_SETUP_VIEW_STEMS = (
    frozenset({"cone-gear-shaft", "cone-gear"}),
    frozenset({"cylinder-gear-shaft", "cylinder-gear"}),
)
GEAR_SETUP_VIEW_LABELS = (
    "ITEMS 25/27\nCONE STACK — SCALE 1:5",
    "ITEMS 1/28\nDRUM STACK — SCALE 1:5",
)
GEAR_SETUP_VIEW_LABEL_ORIGINS = ((0.285, 0.125), (0.350, 0.125))

# Sheet 7: a large parked/disengaged reference view plus scan-friendly setup
# and functional-acceptance tables.  The saved assembly does not claim to show
# the engaged pose.
PINION_SETUP_VIEW_CENTER = (0.095, 0.165)
PINION_SETUP_VIEW_STEMS = EXTERIOR_VIEW_STEMS[1] | EXTERIOR_VIEW_STEMS[2]
PINION_SETUP_VIEW_LABEL_ORIGIN = (0.030, 0.245)
PINION_PARAMETER_TABLE_ANCHOR = (0.175, 0.232)
PINION_PARAMETER_COLUMN_WIDTHS = (0.048, 0.058, 0.050, 0.075)
PINION_PARAMETER_ROW_HEIGHT = 0.010
ACCEPTANCE_TABLE_ANCHOR = (0.175, 0.120)
ACCEPTANCE_COLUMN_WIDTHS = (0.075, 0.156)
ACCEPTANCE_ROW_HEIGHT = 0.009
SETUP_HEADING_ORIGIN = (0.018, 0.262)
SETUP_NOTE_TEXT_HEIGHT = 0.0025
BOM_COLUMN_WIDTHS = {
    "ITEM NO.": 0.014,
    "PART NUMBER": 0.025,
    "DESCRIPTION": 0.074,
    "QTY.": 0.012,
}
EXTERIOR_BALLOON_RING_MARGINS = (0.020, 0.014)
EXTERIOR_BALLOON_CLEARANCES = (0.002, 0.002)

CONE_GEAR_SCHEDULE = tuple(
    (position, f"T{int(channel['cone_teeth']):03d}", int(channel["cone_teeth"]))
    for position, channel in enumerate(_config.channels(), start=1)
)
GEAR_PAIR_ROWS = tuple(
    (
        f"{position:02d}",
        config,
        "T120",
        f"{teeth}:120",
        f"{40.550 + (position - 1) * 6.888787817:.3f}",
        f"{22.900 + (position - 1) * 7.056542133:.3f}",
    )
    for position, config, teeth in CONE_GEAR_SCHEDULE
)
GEAR_REQUIREMENT_ROWS = (
    (
        "ORIENTATION",
        "MACHINE FRONT = PAPER/OUTPUT SIDE (-Z); BACK = +Z. FRONT-VIEW EAST = RIGHT (-X); WEST = LEFT (+X).",
        "APPLIES TO ALL SETUP FEATURES",
    ),
    (
        "ITEM 27",
        "T120 AT ITEM 4 END; T006 AT ITEM 5 END. FACES SQUARE. SOLDER TO ITEM 25; NO KEY.",
        "VERIFY SEQUENCE AND TABLE STATIONS",
    ),
    (
        "ITEM 28",
        "FREE ON ITEM 1. TOOTHED FACES FRONT; CAM FACES BACK. ALIGN ALL INDEX NOTCHES.",
        "WITH ITEM 3 DISENGAGED, HAND-SPIN EACH ITEM 28",
    ),
    (
        "PAIR 01–20",
        "ITEM 27 AND ITEM 28 IN THE SAME ROW FORM ONE MESH PAIR.",
        "0.05–0.20 MM TANGENTIAL BACKLASH",
    ),
)
PINION_PARAMETER_ROWS = (
    (
        "ORIENTATION",
        "FRONT = PAPER SIDE (-Z); BACK = +Z",
        "EAST = -X; WEST = +X",
        "FRONT-VIEW DIRECTIONS",
    ),
    (
        "ITEM 12/28 RELATION",
        "2.00 MM GAP; AXES LEVEL",
        "41.30 MM C-C",
        "PARK: TOOTH-TIP ENVELOPES ON AXIS LINE; ENGAGED: ITEM 22-ITEM 1 AXES",
    ),
    (
        "ITEM 13 PARK ANGLE",
        f"{PINION_PARK_ANGLE_DEG:.2f}° WEST OF +Y; STRAPS PARALLEL",
        "—",
        "ITEM 15-22 AXIS-CENTER LINE TO +Y",
    ),
    (
        "ITEM 12 END CLEARANCE",
        "0.25 MM EACH END",
        "SAME",
        "ITEM 12 END FACE TO ITEM 13 INNER FACE",
    ),
    (
        "ITEM 18 STATION",
        "7.00 MM FROM ITEM 19 MACHINE-FRONT FACE",
        "SAME",
        "ITEM 18 C/L FROM ITEM 19 MACHINE-FRONT FACE",
    ),
    (
        "ITEM 18/19 PARK",
        "0.10–0.25 MM MIN; CAMS PHASED ALIKE; ECCENTRIC AND BOSS DOWN",
        "FUNCTIONAL LIFT",
        "SHORTEST NORMAL GAP",
    ),
    (
        "ITEM 20 ANGLE",
        "40° EAST OF +Y; ECCENTRICS DOWN",
        "OPERATE TO 41.30 MM C-C",
        "ITEM 20 ROD C/L TO +Y",
    ),
    (
        "ITEM 17",
        "MACHINE-BACK STRAP ONLY",
        "ON RELEASE: RETURNS BOTH STRAPS",
        "VISUAL / FUNCTION",
    ),
)
ACCEPTANCE_ROWS = (
    (
        "A. ENGAGE ITEM 3; TIGHTEN ITEM 9; ROTATE ITEM 29 ONE REV.",
        "ITEMS 30/26 AND ALL 27/28 PAIRS ROLL WITHOUT BINDING; EACH 28 FREE ON 1.",
    ),
    (
        "B. DISENGAGE ITEM 12; ROTATE ITEM 21 ONE REV.",
        "ITEMS 12/22 TURN FREELY WITHOUT CONTACTING ITEM 28.",
    ),
    (
        "C. OPERATE ITEM 20 TO 41.30 MM C-C; RELEASE.",
        "BOTH STRAPS MOVE TOGETHER; ITEM 17 RETURNS ITEM 12 TO 2.00 MM GAP.",
    ),
    (
        "D. LOOSEN ITEM 9; SWING ITEM 3 TO ITEM 11; RETURN; RETIGHTEN.",
        "ITEM 3 SWINGS FREELY TO THE STOP AND CAN BE MANUALLY RETURNED.",
    ),
)
_CONE_GEAR_INSTANCE = re.compile(r"cone-gear-(\d+)\Z", re.IGNORECASE)


@_telemetry.traced("drawing.format_drive_train_bom")
def _format_drive_train_bom(adapter: Any, table: Any) -> None:
    """Fit the 32-item BOM as one readable table on its dedicated sheet."""
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    header = [
        str(table.DisplayedText2(0, column, False) or "").strip().upper()
        for column in range(columns)
    ]
    if set(header) != set(BOM_COLUMN_WIDTHS):
        raise RuntimeError(f"unexpected drive-train BOM columns: {header!r}")

    for column, title in enumerate(header):
        requested = BOM_COLUMN_WIDTHS[title]
        actual = float(table.SetColumnWidth(column, requested, 0))
        if abs(actual - requested) > 0.0005:
            raise RuntimeError(
                f"drive-train BOM column {title!r} width {actual:.4f} m "
                f"does not match requested {requested:.4f} m"
            )

    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    if rows != len(BOM_COMPONENTS) + 1:
        raise RuntimeError(
            f"drive-train BOM has {rows} rows, expected {len(BOM_COMPONENTS) + 1}"
        )
    # SolidWorks enforces a 10.2 mm minimum on the header and any wrapped row.
    # Request 7.5 mm throughout, then verify the native readback stays within
    # that measured range; the layout audit below remains the fit authority.
    actual_heights: list[float] = []
    for row in range(rows):
        actual = float(table.SetRowHeight(row, BOM_ROW_HEIGHT, 0))
        actual_heights.append(actual)
        if actual < BOM_ROW_HEIGHT - 0.0005 or actual > BOM_MAX_ROW_HEIGHT:
            raise RuntimeError(
                f"drive-train BOM row {row} height {actual:.4f} m "
                f"outside {BOM_ROW_HEIGHT:.4f}-{BOM_MAX_ROW_HEIGHT:.4f} m"
            )

    adapter.currentModel.EditRebuild3()
    _telemetry.success(
        f"drive-train BOM formatted as one {len(BOM_COMPONENTS)}-item table "
        f"({sum(actual_heights) * 1000.0:.1f} mm high)"
    )


@_telemetry.traced("drawing.verify_cone_gear_schedule")
def _verify_cone_gear_schedule_components(
    adapter: Any,
    bom_table: Any,
    bom_view: Any,
) -> None:
    """Prove BOM item 27 contains the 20 scheduled gear configurations."""
    table = _sw_type_info.early_bound_or_flag(
        bom_table, "ITableAnnotation", "DisplayedText2"
    )
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    header = [
        str(table.DisplayedText2(0, column, False) or "").strip().upper()
        for column in range(columns)
    ]
    if "ITEM NO." not in header:
        raise RuntimeError(f"drive-train BOM has no ITEM NO. column: {header!r}")
    item_column = header.index("ITEM NO.")
    matching_rows = [
        row
        for row in range(1, rows)
        if str(table.DisplayedText2(row, item_column, False) or "").strip() == "27"
    ]
    if len(matching_rows) != 1:
        raise RuntimeError(
            f"drive-train BOM carries {len(matching_rows)} item-27 rows, expected 1"
        )

    bom = _sw_type_info.early_bound_or_flag(
        bom_table, "IBomTableAnnotation", "GetComponents2"
    )
    configuration = str(
        adapter._get_attr_or_call(bom_view, "ReferencedConfiguration") or "Default"
    )
    components = tuple(bom.GetComponents2(matching_rows[0], configuration) or ())
    observed: list[tuple[int, str]] = []
    for component in components:
        component = _sw_type_info.early_bound_or_flag(component, "IComponent2")
        raw_name = str(adapter._get_attr_or_call(component, "Name2") or "")
        leaf = raw_name.replace("\\", "/").rsplit("/", 1)[-1]
        match = _CONE_GEAR_INSTANCE.fullmatch(leaf)
        if match is None:
            raise RuntimeError(
                f"drive-train BOM item 27 includes unexpected component {raw_name!r}"
            )
        referenced = str(
            adapter._get_attr_or_call(component, "ReferencedConfiguration") or ""
        )
        observed.append((int(match.group(1)), referenced))

    observed.sort()
    expected = [(position, config) for position, config, _teeth in CONE_GEAR_SCHEDULE]
    if observed != expected:
        raise RuntimeError(
            "drive-train cone-gear schedule differs from BOM item 27: "
            f"observed={observed!r}, expected={expected!r}"
        )
    _telemetry.success("drive-train BOM item 27 matches all 20 scheduled configs")


def _insert_plain_table(
    adapter: Any,
    contents: tuple[tuple[str, ...], ...],
    *,
    anchor: tuple[float, float],
    column_widths: tuple[float, ...],
    row_height: float,
    label: str,
) -> Any:
    """Insert one title-merged table and read-verify its persisted formatting."""
    if not contents or len(contents[0]) != len(column_widths):
        raise ValueError(f"{label}: table shape and column widths differ")
    columns = len(column_widths)
    if any(len(row) != columns for row in contents):
        raise ValueError(f"{label}: inconsistent table row widths")
    draw = adapter.currentModel
    ddoc = _sw_type_info.early_bound_or_flag(
        draw, "IDrawingDoc", "InsertTableAnnotation2"
    )
    table = ddoc.InsertTableAnnotation2(
        False,
        anchor[0],
        anchor[1],
        1,
        "",
        len(contents),
        columns,
    )
    if table is None:
        raise RuntimeError(f"failed to insert {label}")
    table = _sw_type_info.early_bound_or_flag(
        table,
        "ITableAnnotation",
        "DisplayedText2",
        "MergeCells",
        "GetTextFormat",
        "SetColumnWidth",
        "SetRowHeight",
        "SetText2",
        "SetTextFormat",
    )
    text_format = table.GetTextFormat()
    if text_format is None:
        raise RuntimeError(f"{label}: table has no text format")
    text_format = _sw_type_info.early_bound_or_flag(text_format, "ITextFormat")
    text_format.CharHeight = CONE_SCHEDULE_TEXT_HEIGHT
    if not table.SetTextFormat(False, text_format):
        raise RuntimeError(f"{label}: failed to set text format")
    applied_height = float(table.GetTextFormat().CharHeight)
    if abs(applied_height - CONE_SCHEDULE_TEXT_HEIGHT) > 0.0001:
        raise RuntimeError(
            f"{label}: text height did not persist: "
            f"{applied_height:.4f} m != {CONE_SCHEDULE_TEXT_HEIGHT:.4f} m"
        )
    if not table.MergeCells(0, 0, 0, columns - 1):
        raise RuntimeError(f"{label}: failed to merge title row")
    for row, values in enumerate(contents):
        populated_columns = (0,) if row == 0 else range(columns)
        for column in populated_columns:
            text = values[column]
            table.SetText2(row, column, False, text)
            applied = str(table.DisplayedText2(row, column, False) or "")
            if applied != text:
                raise RuntimeError(
                    f"{label}: text did not persist: "
                    f"row={row}, column={column}, {applied!r} != {text!r}"
                )
    for column, requested in enumerate(column_widths):
        actual = float(table.SetColumnWidth(column, requested, 0))
        if abs(actual - requested) > 0.0005:
            raise RuntimeError(
                f"{label}: column {column} width "
                f"{actual:.4f} m != {requested:.4f} m"
            )
    for row in range(len(contents)):
        actual = float(table.SetRowHeight(row, row_height, 0))
        if abs(actual - row_height) > 0.0005:
            raise RuntimeError(
                f"{label}: row {row} height "
                f"{actual:.4f} m != {row_height:.4f} m"
            )
    draw.EditRebuild3()
    _telemetry.success(f"{label}: {len(contents) - 2} data rows inserted")
    return table


@_telemetry.traced("drawing.insert_cone_gear_schedule")
def _insert_cone_gear_schedule(adapter: Any, bom_table: Any, bom_view: Any) -> Any:
    """Insert and read-verify the explicit item-27/item-28 mesh schedule."""
    _verify_cone_gear_schedule_components(adapter, bom_table, bom_view)
    contents = (
        (
            "MESH PAIRS — ITEM 27 AND ITEM 28 IN EACH ROW MATE AT THE SAME POSITION",
            "",
            "",
            "",
            "",
            "",
        ),
        (
            "PAIR",
            "ITEM 27",
            "ITEM 28",
            "TOOTH RATIO 27:28",
            "ITEM 27 C/L FROM ITEM 25 MACHINE-FRONT END, MM",
            "ITEM 28 DISC C/L FROM ITEM 1 MACHINE-FRONT END, MM",
        ),
        *GEAR_PAIR_ROWS,
    )
    return _insert_plain_table(
        adapter,
        contents,
        anchor=CONE_SCHEDULE_ANCHOR,
        column_widths=CONE_SCHEDULE_COLUMN_WIDTHS,
        row_height=CONE_SCHEDULE_ROW_HEIGHT,
        label="drive-train mesh-pair schedule",
    )


def _insert_gear_requirements_table(adapter: Any) -> Any:
    contents = (
        ("GEAR-TRAIN COMMON REQUIREMENTS", "", ""),
        ("ITEMS", "REQUIREMENT", "ACCEPTANCE"),
        *GEAR_REQUIREMENT_ROWS,
    )
    return _insert_plain_table(
        adapter,
        contents,
        anchor=GEAR_REQUIREMENTS_ANCHOR,
        column_widths=GEAR_REQUIREMENTS_COLUMN_WIDTHS,
        row_height=GEAR_REQUIREMENTS_ROW_HEIGHT,
        label="drive-train gear requirements",
    )


def _insert_pinion_parameter_table(adapter: Any) -> Any:
    contents = (
        ("PINION SETUP PARAMETERS", "", "", ""),
        ("PARAMETER", "PARK / DISENGAGED", "ENGAGED", "INSPECTION"),
        *PINION_PARAMETER_ROWS,
    )
    return _insert_plain_table(
        adapter,
        contents,
        anchor=PINION_PARAMETER_TABLE_ANCHOR,
        column_widths=PINION_PARAMETER_COLUMN_WIDTHS,
        row_height=PINION_PARAMETER_ROW_HEIGHT,
        label="drive-train pinion parameters",
    )


def _insert_acceptance_table(adapter: Any) -> Any:
    contents = (
        ("FINAL FUNCTIONAL ACCEPTANCE", ""),
        ("TEST / ACTION", "PASS CONDITION"),
        *ACCEPTANCE_ROWS,
    )
    return _insert_plain_table(
        adapter,
        contents,
        anchor=ACCEPTANCE_TABLE_ANCHOR,
        column_widths=ACCEPTANCE_COLUMN_WIDTHS,
        row_height=ACCEPTANCE_ROW_HEIGHT,
        label="drive-train functional acceptance",
    )


def _drawing_component_children(drawing_component: Any) -> tuple[Any, ...]:
    """Return children across callable and materialized pywin32 dispatch shapes."""
    member = drawing_component.GetChildren
    children = member() if callable(member) else member
    return tuple(children or ())


def _set_note_text_height(adapter: Any, note: Any, *, label: str) -> None:
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label}: note has no annotation")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetTextFormat", "SetTextFormat"
    )
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label}: note has no text format")
    text_format = _sw_type_info.early_bound_or_flag(text_format, "ITextFormat")
    text_format.CharHeight = SETUP_NOTE_TEXT_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"{label}: failed to set note text height")
    applied = annotation.GetTextFormat(0)
    if (
        applied is None
        or abs(float(applied.CharHeight) - SETUP_NOTE_TEXT_HEIGHT) > 1e-5
    ):
        raise RuntimeError(f"{label}: note text height did not persist")


def _stems_for_identity(identity: str, stems: frozenset[str]) -> set[str]:
    """Which of ``stems`` one identity string represents (exact, or ``stem-<n>``)."""
    return {
        stem
        for stem in stems
        if identity == stem
        or (
            identity.startswith(f"{stem}-")
            and identity.removeprefix(f"{stem}-").isdigit()
        )
    }


def _drawing_component_matches(
    adapter: Any,
    drawing_component: Any,
    stems: frozenset[str],
    *,
    name: str,
) -> set[str]:
    """Return configured stems represented by one leaf drawing component.

    ``name`` is passed in because the caller has already paid for it -- reading
    ``IDrawingComponent::Name`` twice per node is a wasted late-bound round trip.

    The component's PATH is resolved **lazily**: it costs two more round trips
    (``.Component`` then ``GetPathName``) and is only ever consulted when the
    name-derived identity matched nothing. Since a match is the union of both
    identities, skipping the path once the name has already matched cannot change
    the result. On the drive-train tree most nodes match on name alone or are
    structure we do not care about, so this removes the majority of the calls.

    It does not remove enough, and there is no cross-view memo to add. This
    drawing isolates NINE views, each walking the same ~80-leaf tree, and the
    leaves needing the path are exactly the ones no view matches by name -- so
    every view re-resolves the same misses (~20 s of the ~35 s per isolation,
    ~315 s of a 585 s drawing). Caching the identity on ``Name`` was tried and
    does NOT work: ``IDrawingComponent::Name`` carries the VIEW, so the same
    physical component is a different key in each of the nine views and the
    cache never saturates (measured: entries climbing 52 -> 105 -> 569 instead
    of settling at ~80, for 585 s -> 580 s). Any future memo needs a key that
    is view-independent; the span attributes below are what would prove it.
    """
    drawing_name = name.split("@", 1)[0].replace("\\", "/")
    matched = _stems_for_identity(drawing_name.rsplit("/", 1)[-1].casefold(), stems)
    if matched:
        return matched

    component = adapter._attempt(
        lambda dc=drawing_component: dc.Component, default=None
    )
    if component is None:
        return matched
    path = adapter._attempt(lambda c=component: c.GetPathName(), default="") or ""
    return _stems_for_identity(Path(str(path)).stem.casefold(), stems)


@_telemetry.traced("drawing.component_balloon", label_param="stem")
def _create_component_balloon(
    adapter: Any, views: tuple[Any, ...], *, stem: str, expected_item: str
) -> tuple[Any, Any]:
    """Insert one BOM balloon on a real visible edge of the requested component."""
    selected_view: Any | None = None
    selected_edge: Any | None = None
    selected_name = ""
    selected_edge_count = 0
    enumerated: list[str] = []
    for view in views:
        root = adapter._attempt(
            lambda v=view: v.RootDrawingComponent2(False), default=None
        )
        if root is None:
            continue
        pending = list(_drawing_component_children(root))
        while pending:
            drawing_component = pending.pop()
            children = _drawing_component_children(drawing_component)
            pending.extend(children)
            if children:
                continue
            name = str(drawing_component.Name or "")
            if not _drawing_component_matches(
                adapter, drawing_component, frozenset({stem}), name=name
            ):
                continue
            enumerated.append(name)
            component = adapter._attempt(
                lambda dc=drawing_component: dc.Component, default=None
            )
            edges = adapter._attempt(
                lambda v=view, c=component: v.GetVisibleEntities2(c, 1), default=()
            ) or ()
            if not edges:
                continue
            selected_view = view
            selected_edge = edges[0]
            selected_name = name
            selected_edge_count = len(edges)
            break
        if selected_edge is not None:
            break
    if selected_view is None or selected_edge is None:
        raise RuntimeError(
            f"drive-train {stem} balloon has no visible edge across drawing views; "
            f"matching components={enumerated}"
        )
    # Record WHERE the anchor landed. This is the drawing whose sheet built clean
    # on one fleet pass and failed with "1 leader crossing(s)" on the next, and
    # `edges[0]` off an enumeration SolidWorks does not order is the obvious
    # suspect -- but nothing had ever shown it moving, because nothing recorded
    # it. Diffing two passes' drawing.balloon_anchor events answers that: same
    # anchors mean the enumeration is stable and the crossing came from
    # elsewhere; different anchors prove it and earn the cost of ordering them.
    #
    # ONE geometry read, on the winner only. Ordering every visible edge by its
    # curve endpoints was tried and is unusable here -- a GetCurve (24.6 ms,
    # measured) + GetCurveParams2 (2.6 ms) pair per edge, over the 481-577
    # visible edges a gear view carries, is ~13 s for a SINGLE balloon.
    _telemetry.event(
        "drawing.balloon_anchor",
        stem=stem,
        component=selected_name,
        edges=selected_edge_count,
        anchor=",".join(
            f"{value:.6f}"
            for value in (_edge_endpoint_key(adapter, selected_edge) or ())
        ),
    )

    draw = adapter.currentModel
    ddoc = _sw_type_info.early_bound_or_flag(draw, "IDrawingDoc", "ActivateView")
    if not ddoc.ActivateView(view_name(adapter, selected_view)):
        raise RuntimeError(f"failed to activate drive-train {stem} balloon view")
    draw.ClearSelection2(True)
    if not selected_view.SelectEntity(selected_edge, False):
        raise RuntimeError(f"failed to select drive-train {stem} visible edge")
    extension = _sw_type_info.early_bound_or_flag(
        draw.Extension,
        "IModelDocExtension",
        "CreateBalloonOptions",
        "InsertBOMBalloon2",
    )
    options = extension.CreateBalloonOptions()
    if options is None:
        raise RuntimeError(f"failed to create drive-train {stem} balloon options")
    options = _sw_type_info.early_bound_or_flag(options, "IBalloonOptions")
    options.Style = 1
    options.Size = 2
    options.UpperTextContent = 1
    options.ShowQuantity = False
    options.ItemNumberStart = 1
    options.ItemNumberIncrement = 1
    options.ItemOrder = 1
    note = extension.InsertBOMBalloon2(options)
    draw.ClearSelection2(True)
    if note is None:
        raise RuntimeError(f"failed to insert drive-train {stem} BOM balloon")
    item = _balloon_item_number(adapter, note, label=f"drive-train {stem} balloon")
    if item != expected_item:
        raise RuntimeError(
            f"drive-train {stem} balloon resolved item {item}, expected {expected_item}"
        )
    _telemetry.success(f"drive-train {stem} component balloon -> item {item}")
    return note, selected_view


@_telemetry.traced("drawing.isolate_balloon_components", label_param="label")
def _isolate_balloon_components(
    adapter: Any,
    view: Any,
    *,
    visible_stems: frozenset[str],
    label: str,
) -> None:
    """Show only the requested enclosed BOM families in an auxiliary view.

    Nine views call this, so the span carries the view ``label`` -- otherwise
    the nine rows are indistinguishable and a slow ``resolve_s`` cannot be
    pinned to the view that spent it.

    The walk is ONE span with its phases TIMED, not a span per component
    (hundreds of near-instant leaves would drown the trace) and not one opaque
    number either: identity resolution and the ``Visible`` writes are entirely
    different optimisations, and only one of them is cacheable, so a single
    duration could not say which was worth attacking.
    """
    root = adapter._attempt(
        lambda: view.RootDrawingComponent2(False), default=None
    )
    if root is None:
        raise RuntimeError("drive-train bottom view has no root drawing component")

    pending = list(_drawing_component_children(root))
    found: set[str] = set()
    enumerated: list[str] = []
    resolve_s = 0.0
    visible_s = 0.0
    leaves = 0
    while pending:
        drawing_component = pending.pop()
        children = _drawing_component_children(drawing_component)
        pending.extend(children)

        name = str(drawing_component.Name or "")
        enumerated.append(name)
        # Resolve identity only for LEAVES. This used to run before the
        # `continue`, so every internal node paid a `.Component` + `GetPathName`
        # round trip for a `matched` that was then thrown away -- and only leaves
        # ever have their visibility set.
        if children:
            continue
        leaves += 1
        started = time.perf_counter()
        matched = _drawing_component_matches(
            adapter, drawing_component, visible_stems, name=name
        )
        marked = time.perf_counter()
        drawing_component.Visible = bool(matched)
        visible_s += time.perf_counter() - marked
        resolve_s += marked - started
        if not matched:
            continue
        found.update(matched)
        for stem in matched:
            _telemetry.event("drawing.component_visible", component=stem)

    span = _telemetry.trace.get_current_span()
    span.set_attribute("nodes", len(enumerated))
    span.set_attribute("leaves", leaves)
    span.set_attribute("resolve_s", round(resolve_s, 3))
    span.set_attribute("visible_s", round(visible_s, 3))

    missing = sorted(visible_stems - found)
    if missing:
        raise RuntimeError(
            f"drive-train {label} view is missing enclosed components: "
            f"{missing}; enumerated drawing components: {sorted(enumerated)}"
        )
    adapter.currentModel.EditRebuild3()


@_telemetry.traced("drawing.grouped_component_balloons")
def _add_component_balloons(
    adapter: Any,
    views: tuple[Any, ...],
    groups: tuple[frozenset[str], ...],
    *,
    label: str,
) -> list[Any]:
    """Attach one validated BOM balloon per exterior family in isolated views."""
    field_count = len(groups)
    if not (
        len(views)
        == field_count
        == len(EXTERIOR_BALLOON_RING_MARGINS)
        == len(EXTERIOR_BALLOON_CLEARANCES)
    ):
        raise ValueError(f"{label}: grouped view, component, and ring counts differ")

    observed_stems = frozenset().union(*groups)
    unexpected_stems = observed_stems - frozenset(BOM_COMPONENTS)
    if unexpected_stems:
        raise RuntimeError(
            f"{label}: unexpected BOM families: {sorted(unexpected_stems)}"
        )
    duplicates = [
        stem for stem in observed_stems if sum(stem in group for group in groups) != 1
    ]
    if duplicates:
        raise RuntimeError(
            f"drive-train exterior families appear in multiple groups: {duplicates}"
        )

    item_by_stem = {
        stem: str(index) for index, stem in enumerate(BOM_COMPONENTS, start=1)
    }
    all_balloons: list[Any] = []
    for index, (view, stems) in enumerate(zip(views, groups, strict=True), start=1):
        view_balloons: list[Any] = []
        for stem in BOM_COMPONENTS:
            if stem not in stems:
                continue
            note, owner_view = _create_component_balloon(
                adapter,
                (view,),
                stem=stem,
                expected_item=item_by_stem[stem],
            )
            if owner_view is not view:
                raise RuntimeError(
                    f"drive-train exterior group {index}: {stem} balloon changed views"
                )
            view_balloons.append(note)
        _spread_balloons(
            adapter,
            view,
            view_balloons,
            margin=EXTERIOR_BALLOON_RING_MARGINS[index - 1],
            clearance=EXTERIOR_BALLOON_CLEARANCES[index - 1],
        )
        all_balloons.extend(view_balloons)
        _telemetry.success(
            f"{label} group {index}: "
            f"{len(view_balloons)} deliberately attached balloons"
        )
    return all_balloons


@_telemetry.traced("drawing.create_drive_train_sheets")
def _create_drive_train_sheets(adapter: Any) -> None:
    """Duplicate the still-blank project sheet into the six-sheet package."""
    draw = adapter.currentModel
    ddoc = _sw_type_info.early_bound_or_flag(
        draw,
        "IDrawingDoc",
        "ActivateSheet",
        "GetCurrentSheet",
        "GetSheetNames",
        "PasteSheet",
    )
    sheet = ddoc.GetCurrentSheet()
    if sheet is None:
        raise RuntimeError("drive-train drawing template has no initial sheet")
    initial_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if len(initial_names) != 1:
        raise RuntimeError(
            f"drive-train drawing template has {len(initial_names)} sheets, expected 1"
        )
    if next(iter_views(adapter), None) is not None:
        raise RuntimeError("drive-train drawing template initial sheet is not blank")
    sheet.SetName(SHEET_NAMES[0])
    renamed = str(adapter._get_attr_or_call(sheet, "GetName") or "")
    if renamed != SHEET_NAMES[0]:
        raise RuntimeError(
            f"failed to rename initial drive-train sheet: {renamed!r}"
        )

    for previous_name, new_name in zip(SHEET_NAMES[:-1], SHEET_NAMES[1:], strict=True):
        pasted_name = ""
        for attempt in range(1, 4):
            if not ddoc.ActivateSheet(previous_name):
                raise RuntimeError(
                    f"failed to activate blank drive-train sheet {previous_name!r}"
                )
            before_names = tuple(
                adapter._get_attr_or_call(ddoc, "GetSheetNames") or ()
            )
            draw.ClearSelection2(True)
            selected = draw.Extension.SelectByID2(
                previous_name,
                "SHEET",
                0.0,
                0.0,
                0.0,
                False,
                0,
                null_callout(),
                0,
            )
            if not selected:
                raise RuntimeError(
                    f"failed to select blank drive-train sheet {previous_name!r}"
                )
            draw.EditCopy()
            # swInsertOption_MoveToEnd=2, swRenameOption_No=2. Copying the
            # blank sheet preserves the project sheet format and title block.
            returned = bool(ddoc.PasteSheet(2, 2))
            after_names = tuple(
                adapter._get_attr_or_call(ddoc, "GetSheetNames") or ()
            )
            added = tuple(name for name in after_names if name not in before_names)
            if len(after_names) == len(before_names) + 1 and len(added) == 1:
                pasted_name = added[0]
                if not returned:
                    _telemetry.warn(
                        "PasteSheet returned false but created "
                        f"{pasted_name!r}; accepting verified side effect"
                    )
                break
            _telemetry.warn(
                f"PasteSheet attempt {attempt}/3 created no sheet "
                f"(returned={returned!r}, before={before_names!r}, "
                f"after={after_names!r})"
            )
        if not pasted_name:
            raise RuntimeError(
                f"failed to duplicate blank drive-train sheet {previous_name!r} "
                "after 3 verified attempts"
            )
        if not ddoc.ActivateSheet(pasted_name):
            raise RuntimeError(f"failed to activate pasted sheet {pasted_name!r}")
        sheet = ddoc.GetCurrentSheet()
        if sheet is None:
            raise RuntimeError("pasted drive-train sheet has no ISheet")
        sheet.SetName(new_name)
        renamed = str(adapter._get_attr_or_call(sheet, "GetName") or "")
        if renamed != new_name:
            raise RuntimeError(
                f"failed to rename pasted drive-train sheet: {renamed!r}"
            )

    actual = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if actual != SHEET_NAMES:
        raise RuntimeError(f"drive-train sheet order mismatch: {actual!r}")
    for name in SHEET_NAMES:
        if not ddoc.ActivateSheet(name):
            raise RuntimeError(f"failed to activate drive-train sheet {name!r}")
        current = ddoc.GetCurrentSheet()
        current_name = str(adapter._get_attr_or_call(current, "GetName") or "")
        if current_name != name:
            raise RuntimeError(
                f"drive-train activated sheet {current_name!r}, expected {name!r}"
            )


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
    _create_drive_train_sheets(adapter)
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

    ddoc = _sw_type_info.early_bound_or_flag(
        drawing_model, "IDrawingDoc", "ActivateSheet"
    )

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate general-assembly sheet")
    general_front = place_view(
        adapter, str(SOURCE), "*Front", *GENERAL_FRONT_CENTER, scale=VIEW_SCALE
    )
    general_right = place_view(
        adapter, str(SOURCE), "*Right", *GENERAL_RIGHT_CENTER, scale=VIEW_SCALE
    )
    general_iso = place_view(
        adapter, str(SOURCE), "*Isometric", *GENERAL_ISO_CENTER, scale=VIEW_SCALE
    )
    for view in (general_front, general_right, general_iso):
        set_hidden_lines_removed(adapter, view)
    if add_note(
        adapter, "SHEET 1 OF 7 — GENERAL ASSEMBLY", 0.018, 0.255
    ) is None:
        raise RuntimeError("failed to add general-assembly heading")
    if add_note(adapter, GENERAL_POINTER_NOTE, *GENERAL_POINTER_ORIGIN) is None:
        raise RuntimeError("failed to add drive-train setup-sheet pointer")

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate drive-train parts-list sheet")
    bom_iso = place_view(
        adapter, str(SOURCE), "*Isometric", *BOM_ISO_CENTER, scale=VIEW_SCALE
    )
    set_hidden_lines_removed(adapter, bom_iso)
    bom_table = insert_identified_bom_table(
        adapter,
        bom_iso,
        anchor_xy=BOM_ANCHOR,
        descriptions=BOM_COMPONENTS,
        part_numbers=BOM_PART_NUMBERS,
        configuration_grouping="same-part",
        label="drive-train assembly",
    )
    _format_drive_train_bom(adapter, bom_table)
    if add_note(
        adapter,
        "SHEET 2 OF 7 — PARTS LIST; ITEM NUMBERS APPLY TO SHEETS 3-7",
        0.170,
        0.255,
    ) is None:
        raise RuntimeError("failed to add drive-train parts-list heading")

    if not ddoc.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("failed to activate exterior-identification sheet")
    gear_identification_groups = tuple(
        EXTERIOR_VIEW_STEMS[index] for index in GEAR_IDENTIFICATION_VIEW_INDICES
    )
    gear_identification_views = tuple(
        place_view(
            adapter,
            str(SOURCE),
            EXTERIOR_VIEW_NAMES[index],
            *center,
            scale=VIEW_SCALE,
        )
        for index, center in zip(
            GEAR_IDENTIFICATION_VIEW_INDICES,
            GEAR_IDENTIFICATION_VIEW_CENTERS,
            strict=True,
        )
    )
    for field, (view, stems) in enumerate(
        zip(gear_identification_views, gear_identification_groups, strict=True),
        start=1,
    ):
        set_hidden_lines_removed(adapter, view)
        _isolate_balloon_components(
            adapter, view, visible_stems=stems,
            label=f"gear identification {field}",
        )
    _add_component_balloons(
        adapter,
        gear_identification_views,
        gear_identification_groups,
        label="drive-train gear identification",
    )
    for index, origin in zip(
        GEAR_IDENTIFICATION_VIEW_INDICES,
        GEAR_IDENTIFICATION_LABEL_ORIGINS,
        strict=True,
    ):
        if add_note(adapter, EXTERIOR_VIEW_LABELS[index], *origin) is None:
            raise RuntimeError("failed to add gear identification-view label")
    if add_note(
        adapter,
        "SHEET 3 OF 7 — GEAR-TRAIN ITEM IDENTIFICATION; "
        "SELECTED SUBSYSTEMS SHOWN; HIDDEN LINES REMOVED",
        0.018,
        0.255,
    ) is None:
        raise RuntimeError("failed to add exterior-identification heading")

    if not ddoc.ActivateSheet(SHEET_NAMES[3]):
        raise RuntimeError("failed to activate concealed-identification sheet")
    concealed_bottom = place_view(
        adapter,
        str(SOURCE),
        "*Bottom",
        *CONCEALED_BOTTOM_CENTER,
        scale=VIEW_SCALE,
    )
    set_hidden_lines_visible(adapter, concealed_bottom)
    _isolate_balloon_components(
        adapter,
        concealed_bottom,
        visible_stems=CONCEALED_BOTTOM_VISIBLE_STEMS,
        label="bottom"
    )
    bottom_balloons: list[Any] = []
    for stem in sorted(CONCEALED_BOTTOM_STEMS):
        item = CONCEALED_BALLOON_ITEMS[stem]
        note, _owner_view = _create_component_balloon(
            adapter, (concealed_bottom,), stem=stem, expected_item=item
        )
        bottom_balloons.append(note)
    _spread_balloons(
        adapter,
        concealed_bottom,
        bottom_balloons,
        margin=CONCEALED_BOTTOM_BALLOON_RING_MARGIN,
        clearance=CONCEALED_BALLOON_CLEARANCE,
    )

    concealed_front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *CONCEALED_FRONT_CENTER,
        scale=VIEW_SCALE,
    )
    set_hidden_lines_visible(adapter, concealed_front)
    _isolate_balloon_components(
        adapter,
        concealed_front,
        visible_stems=CONCEALED_FRONT_VISIBLE_STEMS,
        label="front"
    )
    front_balloons: list[Any] = []
    for stem in sorted(CONCEALED_FRONT_STEMS):
        item = CONCEALED_BALLOON_ITEMS[stem]
        note, _owner_view = _create_component_balloon(
            adapter, (concealed_front,), stem=stem, expected_item=item
        )
        front_balloons.append(note)
    _spread_balloons(
        adapter,
        concealed_front,
        front_balloons,
        margin=CONCEALED_FRONT_BALLOON_RING_MARGIN,
        clearance=CONCEALED_BALLOON_CLEARANCE,
    )
    concealed_labels = (
        "VIEW A — CONE JOURNAL / ENDPLAY STACK, BOTTOM VIEW",
        "VIEW B — CRANK MESH / SHAFT RELATIONSHIP, FRONT VIEW",
    )
    for label, origin in zip(
        concealed_labels, CONCEALED_VIEW_LABEL_ORIGINS, strict=True
    ):
        if add_note(adapter, label, *origin) is None:
            raise RuntimeError("failed to add concealed relationship-view label")
    if add_note(
        adapter,
        "SHEET 4 OF 7 — CONCEALED ITEM IDENTIFICATION; "
        "SELECTED COMPONENTS SHOWN; HIDDEN LINES VISIBLE",
        *CONCEALED_HEADING_ORIGIN,
    ) is None:
        raise RuntimeError("failed to add concealed-identification heading")

    if not ddoc.ActivateSheet(SHEET_NAMES[4]):
        raise RuntimeError("failed to activate gear-train setup sheet")
    _insert_cone_gear_schedule(adapter, bom_table, bom_iso)
    _insert_gear_requirements_table(adapter)
    for index, (center, stems, label, origin) in enumerate(
        zip(
            GEAR_SETUP_VIEW_CENTERS,
            GEAR_SETUP_VIEW_STEMS,
            GEAR_SETUP_VIEW_LABELS,
            GEAR_SETUP_VIEW_LABEL_ORIGINS,
            strict=True,
        ),
        start=1,
    ):
        view = place_view(
            adapter, str(SOURCE), "*Right", *center, scale=GEAR_SETUP_VIEW_SCALE
        )
        set_hidden_lines_removed(adapter, view)
        _isolate_balloon_components(
            adapter, view, visible_stems=stems,
            label=f"gear setup {index}",
        )
        if add_note(adapter, label, *origin) is None:
            raise RuntimeError("failed to add gear setup view label")
    if add_note(
        adapter,
        "SHEET 5 OF 7 — GEAR-TRAIN SETUP",
        *SETUP_HEADING_ORIGIN,
    ) is None:
        raise RuntimeError("failed to add gear-train setup heading")

    if not ddoc.ActivateSheet(SHEET_NAMES[5]):
        raise RuntimeError("failed to activate pinion-identification sheet")
    pinion_identification_groups = tuple(
        EXTERIOR_VIEW_STEMS[index] for index in PINION_IDENTIFICATION_VIEW_INDICES
    )
    pinion_identification_views = tuple(
        place_view(
            adapter,
            str(SOURCE),
            EXTERIOR_VIEW_NAMES[index],
            *center,
            scale=VIEW_SCALE,
        )
        for index, center in zip(
            PINION_IDENTIFICATION_VIEW_INDICES,
            PINION_IDENTIFICATION_VIEW_CENTERS,
            strict=True,
        )
    )
    for field, (view, stems) in enumerate(
        zip(
            pinion_identification_views,
            pinion_identification_groups,
            strict=True,
        ),
        start=1,
    ):
        set_hidden_lines_removed(adapter, view)
        _isolate_balloon_components(
            adapter,
            view,
            visible_stems=stems,
            label=f"pinion identification {field}"
        )
    _add_component_balloons(
        adapter,
        pinion_identification_views,
        pinion_identification_groups,
        label="drive-train pinion identification",
    )
    for index, origin in zip(
        PINION_IDENTIFICATION_VIEW_INDICES,
        PINION_IDENTIFICATION_LABEL_ORIGINS,
        strict=True,
    ):
        if add_note(adapter, EXTERIOR_VIEW_LABELS[index], *origin) is None:
            raise RuntimeError("failed to add pinion identification-view label")
    if add_note(
        adapter,
        "SHEET 6 OF 7 — PINION ITEM IDENTIFICATION; "
        "SELECTED SUBSYSTEMS SHOWN; HIDDEN LINES REMOVED",
        0.018,
        0.255,
    ) is None:
        raise RuntimeError("failed to add pinion-identification heading")

    if not ddoc.ActivateSheet(SHEET_NAMES[6]):
        raise RuntimeError("failed to activate pinion setup-and-acceptance sheet")
    pinion_setup = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *PINION_SETUP_VIEW_CENTER,
        scale=VIEW_SCALE,
    )
    set_hidden_lines_removed(adapter, pinion_setup)
    _isolate_balloon_components(
        adapter,
        pinion_setup,
        visible_stems=PINION_SETUP_VIEW_STEMS,
        label="pinion parked reference"
    )
    if add_note(
        adapter,
        "PARK / DISENGAGED — SHOWN POSITION; ITEMS 12–24; NOT AN ENGAGED VIEW",
        *PINION_SETUP_VIEW_LABEL_ORIGIN,
    ) is None:
        raise RuntimeError("failed to add pinion reference-view label")
    _insert_pinion_parameter_table(adapter)
    _insert_acceptance_table(adapter)
    if add_note(
        adapter,
        "SHEET 7 OF 7 — PINION SETUP AND ACCEPTANCE",
        *SETUP_HEADING_ORIGIN,
    ) is None:
        raise RuntimeError("failed to add pinion setup-and-acceptance heading")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Drive-Train Assembly Drawing",
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
