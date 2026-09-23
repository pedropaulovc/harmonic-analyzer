r"""Create the native eight-sheet drive-train assembly drawing package (MHA-A03).

The released ``drive-train.SLDASM`` stays authoritative and byte-for-byte
unchanged. This recipe consumes the builder-owned ``DRIVE_TRAIN_EXPLODED``
presentation (``_drive_train_explode``) and reads every count, identity and
position it prints from the opened model; nothing pending on a sibling branch
(crank hub, lever pin, pinion tooth count, bracket placement) is typed here.

Sheet numbers are fixed: cross-references on the sheets cite them, so a sheet
whose content is still pending keeps its slot with a placeholder.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

import _telemetry
from _common import OUT_FAILURES, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_component_bom_balloons,
    check_drawing_layout,
    create_blank_drawing_sheets,
    finalize_drawing,
    insert_bom_table,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_high_quality_shaded_with_edges,
)
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from drive_train_assembly_spec import (
    CLUSTERS,
    EXPLODED_VIEW_NAME,
    PENDING_STEMS,
    SOURCE_CONFIGURATION,
    Cluster,
    Instance,
    cluster_members,
    unclassified_stems,
)
from solidworks_mcp.adapters.com_variant import double_array
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
DRAWING_NUMBER = "MHA-A03"

SHEET_NAMES = (
    "ASSEMBLED VIEWS",
    "BILL OF MATERIALS",
    "CYLINDER BANK EXPLODED",
    "CONE SET + CRANK EXPLODED",
    "ALIGNMENT PINION RIG EXPLODED",
    "ASSEMBLY SEQUENCE",
    "MESH + FIT DETAILS",
    "CHECKS + SETUP",
)
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the drive-train package primary sheet must remain landscape")
# Which sheet shows which cluster; the BOM sheet and captions cite these.
CLUSTER_SHEETS: dict[Cluster, int] = {
    "cylinder-bank": 3,
    "cone-crank": 4,
    "pinion-rig": 5,
}
CLUSTER_TITLES: dict[Cluster, str] = {
    "cylinder-bank": "CYLINDER BANK",
    "cone-crank": "CONE SET, SWING PLATFORM AND CRANK",
    "pinion-rig": "ALIGNMENT PINION RIG",
}
SEQUENCE_SHEET = 6
FIT_SHEET = 7
CHECKS_SHEET = 8

ASSEMBLED_SCALE = (1.0, 3.0)
ASSEMBLED_ISO_SCALE = (1.0, 4.0)
REFERENCE_ISO_SCALE = (1.0, 8.0)
CLUSTER_SCALE = (1.0, 3.0)
SHEET_SCALES = {
    SHEET_NAMES[0]: ASSEMBLED_SCALE,
    SHEET_NAMES[1]: REFERENCE_ISO_SCALE,
    SHEET_NAMES[2]: CLUSTER_SCALE,
    SHEET_NAMES[3]: CLUSTER_SCALE,
    SHEET_NAMES[4]: CLUSTER_SCALE,
    SHEET_NAMES[5]: REFERENCE_ISO_SCALE,
    SHEET_NAMES[6]: REFERENCE_ISO_SCALE,
    SHEET_NAMES[7]: REFERENCE_ISO_SCALE,
}

# --- sheet 1: projected front/top/right group + isometric ---------------------
# The projected group's lower-left lands here; the views are aligned on the
# model origin (ASME third angle: top above front, right to the right of it).
PROJECTED_GROUP_ORIGIN = (0.024, 0.080)
PROJECTED_GAP = 0.014
PROJECTED_REGION = (0.018, 0.072, 0.300, 0.255)
ASSEMBLED_ISO_CENTER = (0.360, 0.175)
VIEW_CAPTION_GAP = 0.004

# --- sheet 2: BOM in two columns + reference isometric -----------------------
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.022,
    "description": 0.118,
    "quantity": 0.012,
}
BOM_COLUMN_WIDTH = sum(BOM_COLUMN_WIDTHS.values())
# Measured, not derived: in the 118 mm column, four 41-character descriptions
# kept one line and the 47-character MHA-030 row wrapped to 10.195 mm
# (farm leaf 20260923T044055Z-1-20b23f24, swmaker000005).
BOM_DESCRIPTION_MAX_CHARS = 41
BOM_ANCHOR = (0.018, 0.258)
BOM_SECOND_COLUMN_X = BOM_ANCHOR[0] + BOM_COLUMN_WIDTH + 0.008
BOM_ROW_HEIGHT = 0.006
BOM_HEIGHT_TOLERANCE = 1e-6
BOM_SHEET_CLEARANCE = 0.003
BOM_REFERENCE_ISO_CENTER = (0.385, 0.200)
# The MHA-013 station pointer lives here, not in its BOM cell: on the grouped
# 20-configuration row SolidWorks kept a written description only up to its
# second comma (farm leaf 20260923T040258Z-1-0726d474, swmaker000005).
BOM_REFERENCE_CAPTION = (
    "REFERENCE 1:8 - BALLOONS ON SHEETS 3-5\n"
    "MHA-013 CONE GEAR STATIONS: SHEET 6"
)

# --- sheets 3-5: exploded cluster views --------------------------------------
CLUSTER_VIEW_CENTER = (0.200, 0.165)
CLUSTER_RING_REGION = (0.020, 0.072, 0.415, 0.252)
CLUSTER_BALLOON_MARGIN = 0.012
BALLOON_DIAMETER = 0.010

# --- note fields (x0, top, x1, bottom), metres --------------------------------
# Tops sit under the one-line sheet heading at HEADING_XY.
NOTE_FIELD_LEFT = (0.018, 0.255, 0.212, 0.035)
NOTE_FIELD_RIGHT = (0.222, 0.255, 0.415, 0.072)
NOTE_FIELD_INSET = 0.0005
NOTE_ANCHOR_PASSES = 3
NOTE_ANCHOR_SETTLE = 0.00005
NOTE_BLOCK_GAP = 0.006
HEADING_XY = (0.018, 0.268)
# Sheet 1's four-line heading sits over the isometric, clear of the top view.
ASSEMBLED_HEADING_XY = (0.222, 0.268)
SHEET_NUMBER_XY = (0.018, 0.025)
REFERENCE_ISO_CENTER = (0.380, 0.110)
# Sheet 6 needs the whole right column for steps 8-17, so its reference view
# sits under the left column's cone steps and station table. Notes pitch
# 4.525 mm a line (summing-assembly.pdf): 29 left lines end near y=0.118.
SEQUENCE_REFERENCE_ISO_CENTER = (0.110, 0.068)
SEQUENCE_LEFT_FIELD = (NOTE_FIELD_LEFT[0], NOTE_FIELD_LEFT[1], NOTE_FIELD_LEFT[2], 0.100)
REFERENCE_ISO_CAPTION_XY = (0.330, 0.082)

# --- BOM identities: released part numbers and descriptions ------------------
# The model owns the part number (each component's "Number" property, read and
# cross-checked at build time); the description column is drawing wording.
# test_drive_train_assembly_drawing.py pins every number against the parts
# registry and every builder-inserted family against this table.
BOM_PART_NUMBERS = {
    "cylinder-gear-shaft": "MHA-028",
    "arbor-pedestal": "MHA-004",
    "cylinder-end-disc": "MHA-121",
    "dome-cap-screw": "MHA-125",
    "cylinder-gear": "MHA-027",
    "foot-screw": "MHA-103",
    "cone-gear-shaft": "MHA-014",
    "cone-gear": "MHA-013",
    "crank-drive-gear": "MHA-021",
    "cone-swing-platform": "MHA-091",
    "cone-pivot-post": "MHA-016",
    "cone-tip-block": "MHA-092",
    "cone-tip-bushing": "MHA-096",
    "cone-tip-adjuster": "MHA-097",
    "cone-tip-pinch-screw": "MHA-098",
    "cone-lock-knob": "MHA-093",
    "cone-pivot-screw": "MHA-094",
    "swing-stop-screw": "MHA-095",
    "crankshaft": "MHA-026",
    "crank-pinion": "MHA-025",
    "crank-pinion-pin": "MHA-134",
    "crank-arm": "MHA-020",
    "crank-pin": "MHA-024",
    "crank-pin-ring": "MHA-128",
    "crank-pin-eye": "MHA-130",
    "fillister-screw": "MHA-030",
    "crank-handle": "MHA-022",
    "crank-hub": "MHA-137",
    "crank-hub-pin": "MHA-138",
    "alignment-pinion": "MHA-002",
    "pinion-bracket": "MHA-056",
    "pinion-pivot-block": "MHA-061",
    "pinion-pivot-shaft": "MHA-062",
    "pinion-lift-rod": "MHA-060",
    "pinion-spring": "MHA-114",
    "pinion-cam-pin": "MHA-116",
    "pinion-cam": "MHA-104",
    "pinion-lever": "MHA-059",
    "pinion-lever-pin": "MHA-135",
    "pinion-handle": "MHA-058",
    "pinion-arbor": "MHA-102",
    "slotted-screw": "MHA-101",
}
BOM_DESCRIPTIONS = {
    "cylinder-gear-shaft": "CYLINDER GEAR ARBOR",
    "arbor-pedestal": "ARBOR PEDESTAL",
    "cylinder-end-disc": "CYLINDER BANK END DISC",
    "dome-cap-screw": "ARBOR DOME CAP",
    "cylinder-gear": "CYLINDER GEAR WITH CAM, 120T",
    "foot-screw": "#4-40 FILLISTER SCREW, MCMASTER 90280A108",
    "cone-gear-shaft": "CONE GEAR SHAFT",
    "cone-gear": "CONE GEAR, T006-T120 BY 6; 1 EACH",
    "crank-drive-gear": "CRANK DRIVE GEAR, 64T",
    "cone-swing-platform": "CONE SWING PLATFORM",
    "cone-pivot-post": "CONE PIVOT POST AND CRANK COLUMN",
    "cone-tip-block": "CONE TIP BLOCK",
    "cone-tip-bushing": "CONE TIP BUSHING",
    "cone-tip-adjuster": "CUP-TIP SET SCREW, MCMASTER 94025A150",
    "cone-tip-pinch-screw": "#4-40 FILLISTER SCREW, MCMASTER 90280A108",
    "cone-lock-knob": "KNURLED THUMB SCREW, MCMASTER 91882A425",
    "cone-pivot-screw": "SHOULDER SCREW, MCMASTER 91829A560",
    "swing-stop-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A199",
    "crankshaft": "CRANKSHAFT",
    "crank-pinion": "CRANK PINION, 16T",
    "crank-pinion-pin": "CRANK PINION RETENTION PIN",
    "crank-arm": "CRANK ARM",
    "crank-pin": "CRANK TAPER PIN, 1:48",
    "crank-pin-ring": "TAPER PIN KEEPER RING",
    "crank-pin-eye": "KEEPER RING ANCHOR EYE",
    "fillister-screw": "#4-40 BRASS FILLISTER, MCMASTER 90114A511",
    "crank-handle": "CRANK HANDLE",
    "crank-hub": "CRANK HUB",
    "crank-hub-pin": "CRANK HUB AXIAL PIN",
    "alignment-pinion": "ALIGNMENT PINION",
    "pinion-bracket": "PINION BRACKET STRAP",
    "pinion-pivot-block": "PINION PIVOT BLOCK",
    "pinion-pivot-shaft": "PINION PIVOT SHAFT",
    "pinion-lift-rod": "PINION LIFT ROD",
    "pinion-spring": "PINION SPRING",
    "pinion-cam-pin": "PINION CAM FOLLOWER PIN",
    "pinion-cam": "PINION ECCENTRIC CAM",
    "pinion-lever": "PINION LEVER",
    "pinion-lever-pin": "PINION LEVER CROSS PIN",
    "pinion-handle": "PINION GRIP CROSSROD",
    "pinion-arbor": "INTEGRAL PINION ARBOR AND GRIP HEAD",
    "slotted-screw": "#8-32 FILLISTER SCREW, MCMASTER 90280A199",
}
if set(BOM_DESCRIPTIONS) != set(BOM_PART_NUMBERS):
    raise AssertionError("drive-train BOM description coverage is incomplete")
if set(BOM_PART_NUMBERS) != {stem for stems in CLUSTERS.values() for stem in stems}:
    raise AssertionError("drive-train BOM identities must cover exactly the clusters")
BOM_NORMALIZED_ALIASES = {
    number.casefold(): stem for stem, number in BOM_PART_NUMBERS.items()
}

# --- sheet wording ---------------------------------------------------------------
# Only assembly-level requirements live here; part drawings own manufacture and
# every quoted fit/process is the wording already printed on that part's sheet.
# "[PENDING ...]" marks a joint whose hardware or ruling has not landed; the
# package is not released while any remains.
ASSEMBLED_HEADING = (
    "SAVED WORKING POSE: CONE SET ENGAGED, ALIGNMENT PINION PARKED CLEAR,\n"
    "CAMS ECCENTRIC DOWN, CRANK ARM DOWN. FREE: CRANK, CONE SWING, PINION\n"
    "SWING, LIFT ROD. SEE SHEET 8 FOR SETUP."
)

CONE_CRANK_STEPS = "\n".join(
    (
        "ASSEMBLY SEQUENCE - CONE SET AND CRANK",
        "1. BOND {cone_gears}X MHA-013 TO THEIR MHA-014 SEATS PER THE MHA-013",
        "   PRINT, TIP FIRST: T006 AT THE BACK THROUGH T120 AT THE FRONT",
        "   (STATION TABLE). BOND MHA-021 FRONT OF T120 PER ITS PRINT.",
        "2. JOURNAL MHA-014 IN MHA-016. SLIP MHA-096 ON THE TIP STUB AGAINST",
        "   T006 AND SEAT MHA-092 OVER IT. [PENDING: MHA-016 AND MHA-092",
        "   FASTENING TO MHA-091]",
        "3. THREAD MHA-097 INTO MHA-092 TO TAKE UP THE CONE-STACK END PLAY;",
        "   LOCK WITH MHA-098 ACROSS THE SLIT. [PENDING: END-PLAY LIMIT]",
        "4. FIT MHA-026 IN THE MHA-016 CRANK BORE. MESH MHA-025 WITH MHA-021",
        "   TOOTH IN GAP; MATCH-DRILL AND REAM FOR MHA-134 AT BOSS MID-LENGTH",
        "   WITH MHA-026; SEAT FLUSH BOTH SIDES PER THE MHA-025 PRINT.",
        "5. THE PAPER-DRIVE T12 WHEEL GOES ON MHA-026 BEFORE THE ARM.",
        "6. FIT MHA-020 ON MHA-026; TAPER-REAM 1:48 THROUGH ARM AND SHAFT",
        "   TOGETHER; FIT MHA-024, LIGHT DRIVE, REMOVABLE BY TAP ON SMALL END.",
        "   HANG MHA-128 FROM THE PIN HEAD; CLAMP MHA-130 UNDER MHA-030.",
        "   [PENDING: MHA-137/MHA-138 CRANK HUB CONSTRUCTION]",
        "7. FIT MHA-022 ON THE ARM PIVOT. [PENDING: HANDLE RETENTION]",
    )
)

BANK_RIG_STEPS = "\n".join(
    (
        "ASSEMBLY SEQUENCE - CYLINDER BANK AND PINION RIG",
        "8. SLIDE {cylinder_gears}X MHA-027 ONTO MHA-028, ALL ALIKE, CAM SIDE",
        "   FRONT; ADD EACH CHANNEL CONNECTING ROD ON ITS CAM AS ITS GEAR",
        "   GOES ON. FIT MHA-121 AT EACH END. [PENDING: BANK AXIAL STACK-UP]",
        "9. FIT BOTH MHA-004 OVER THE ARBOR ENDS AND MHA-125 IN EACH.",
        "10. FIT MHA-002 ON MHA-102 PER THE MHA-102 PRINT. MATCH-REAM THE",
        "    MHA-102 HEAD TO MHA-058; PRESS MHA-058 (NO TURN OR SLIDE BY HAND).",
        "11. PRESS {cam_pins}X MHA-116 INTO THE MHA-056 SEATS PER ITS PRINT.",
        "12. JOURNAL MHA-102 IN THE MHA-056 TOP BORES; HANG BOTH MHA-056 ON",
        "    MHA-062 THROUGH {pivot_blocks}X MHA-061.",
        "13. FIT {cams}X MHA-104 AND MHA-059 ON MHA-060 IN THE MHA-061 LIFT",
        "    BORES. PARK EACH CAM ECCENTRIC DOWN; LOCK WITH ITS SET SCREW.",
        "    [PENDING: MHA-059 TO MHA-060 PIN MHA-135]",
        # Main ruling 2026-09-23 (U28 corollary): the rig is located by its
        # parked tip gap, and MHA-035 carries its hold-down and spring seats as
        # TRANSFER FROM MHA-061. The level line of centres makes block travel
        # equal gap change; 2.5 is the physical rest gap, not the CAD gap
        # (pinioncluster, PR #837).
        "14. LOCATE THE RIG ON MHA-035; ITS SEATS ARE TRANSFERRED, NOT",
        "    PRE-DRILLED. SET BOTH MHA-061 LOOSE ON THE BASE, MHA-114 FITTED.",
        "    PARK MHA-059: THE MHA-116 PINS REST ON THE CAMS UNDER THE SPRING.",
        "15. FACE A MHA-002 TOOTH TIP TO A MHA-027 TOOTH TIP ON THE LEVEL",
        "    LINE OF CENTRES. SLIDE THE RIG IN UNTIL A 2.5 FEELER (E.G. 2.00",
        "    + 0.50 LEAVES) IS SNUG; ACCEPT 2.3-2.7. SET IT AT THE FRONT AND",
        "    BACK STATIONS TO SQUARE BOTH MHA-061 TO THE DRUM; CLAMP.",
        "16. SPOT MHA-035 THROUGH THE MHA-061 HOLES; DRILL AND TAP #8-32",
        "    UNC-2B, {slotted} PLACES. SET MHA-114 WITH ITS TERMINAL FLAT ON THE",
        "    PARKED BACK MHA-056; SPOT THROUGH ITS FOOT HOLE; DRILL AND TAP",
        "    #4-40 UNC-2B, 1 PLACE. FIT {slotted}X MHA-101 AND 1X MHA-103.",
        "17. OTHER BASE MOUNTING: SEE SHEET 8, EXTERNAL INTERFACES.",
    )
)

CHECKS = "\n".join(
    (
        "ASSEMBLY-ONLY FUNCTIONAL CHECKS",
        "1. CRANK TURNS FREELY THROUGH FULL TURNS; ONE CRANK TURN TURNS THE",
        "   CONE SET 1/4 TURN (16T:64T).",
        "2. MHA-025/MHA-021 BACKLASH PER THE MHA-021 PRINT; EACH CONE GEAR",
        "   MESHES ITS MHA-027 PER THE MHA-013 PRINT.",
        # C:/src/dt-logs/handoffs/dt-crank-mesh-under-spec-20260923.md: the
        # 16T:64T centre distance is the difference of two .XX heights on
        # MHA-016 and nothing sets it at assembly (open user decision).
        "   [PENDING: 16T:64T CENTRE-DISTANCE SETTING - OPEN RULING]",
        "3. EACH MHA-027 TURNS FREELY ON MHA-028 WITHOUT AXIAL BINDING.",
        "4. CONE SWING (P1): LOOSEN MHA-093; THE CONE SET SWINGS ON MHA-094",
        "   CLEAR OF EVERY MHA-027. RETURN IT TO THE MHA-095 STOP AND",
        "   TIGHTEN MHA-093; ALL {cone_gears} MESHES RE-ENGAGE.",
        "5. ZEROING (P2), CONE SET SWUNG CLEAR: TURN EACH MHA-027 BY HAND",
        "   UNTIL ITS NOTCH LINES UP. TURN MHA-059 TO ENGAGE MHA-002; TURN",
        "   MHA-002 BY MHA-058 UNTIL ALL NOTCHES POINT UP (COSINES) OR 90 DEG",
        "   (SINES). RETURN MHA-059 TO PARK; RE-ENGAGE THE CONE SET.",
        "6. PARKED, MHA-114 HOLDS MHA-002 CLEAR OF EVERY MHA-027.",
        "   [PENDING: PINION BRACKET PLACEMENT AND TOOTH-COUNT RULINGS]",
        "7. PARKED, PINS ON THE CAMS: A 2.5 FEELER IS SNUG TIP TO TIP AT THE",
        "   FRONT AND BACK STATIONS; ACCEPT 2.3-2.7 (SHEET 6, STEP 15).",
    )
)

SETUP_NOTES = "\n".join(
    (
        "SAVED POSE AND FREE MOTIONS",
        "SAVED DEFAULT: CONE SET ENGAGED, MHA-002 PARKED CLEAR, CAMS",
        "ECCENTRIC DOWN, CRANK ARM DOWN.",
        "FREE, NEVER LOCKED: CRANK SPIN, CONE-PLATFORM SWING, PINION",
        "SWING, LIFT-ROD/CAM SPIN.",
    )
)

INTERFACE_NOTES = "\n".join(
    (
        "EXTERNAL INTERFACES - NOT BOM ITEMS",
        "HARMONIC BASE MHA-035 RECEIVES MHA-094, MHA-093, MHA-095,",
        "{slotted}X MHA-101 AND {foot}X MHA-103.",
        "PAPER DRIVE: T12 CHAIN WHEEL ON MHA-026.",
        "CHANNEL ASSEMBLY: CONNECTING RODS RUN ON THE MHA-027 CAMS.",
    )
)

FIT_PLACEHOLDER = "\n".join(
    (
        "MESH + FIT DETAILS - PENDING",
        "CONE/CYLINDER STATION MESH, 16T:64T MESH, ALIGNMENT PINION",
        "ENGAGEMENT AND TAPER-PIN STATION DETAILS FOLLOW THE PINION",
        "BRACKET, TOOTH-COUNT, CRANK-HUB AND MHA-135 RULINGS.",
    )
)


# ============================ pure helpers ======================================


def _source_fingerprint(path: Path) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, digest.hexdigest()


def note_field_violations(
    extent: tuple[float, float, float, float],
    field: tuple[float, float, float, float],
) -> list[str]:
    """Name every edge of a note box (x0, y0, x1, y1) that leaves its field."""
    x0, y0, x1, y1 = extent
    left, top, right, bottom = field
    violations = []
    if x0 < left - 1e-6:
        violations.append(f"left {x0 * 1000:.2f} mm < field {left * 1000:.2f}")
    if x1 > right + 1e-6:
        violations.append(f"right {x1 * 1000:.2f} mm > field {right * 1000:.2f}")
    if y1 > top + 1e-6:
        violations.append(f"top {y1 * 1000:.2f} mm > field {top * 1000:.2f}")
    if y0 < bottom - 1e-6:
        violations.append(f"bottom {y0 * 1000:.2f} mm < field {bottom * 1000:.2f}")
    return violations


def ring_fit_shift(
    outline: tuple[float, float, float, float],
    region: tuple[float, float, float, float],
    *,
    grow: float,
) -> tuple[tuple[float, float], list[str]]:
    """Shift that centres an outline's balloon ring in a region, plus overflows."""
    ring = (outline[0] - grow, outline[1] - grow, outline[2] + grow, outline[3] + grow)
    x0, y0, x1, y1 = region
    ring_w, ring_h = ring[2] - ring[0], ring[3] - ring[1]
    overflows = [
        f"{axis} {size * 1000:.1f} mm > {room * 1000:.1f} mm"
        for axis, size, room in (("width", ring_w, x1 - x0), ("height", ring_h, y1 - y0))
        if size > room
    ]
    shift = (
        (x0 + x1) / 2.0 - (ring[0] + ring[2]) / 2.0,
        (y0 + y1) / 2.0 - (ring[1] + ring[3]) / 2.0,
    )
    return shift, overflows


def balloon_attachment_violations(
    records: Sequence[tuple[str, str, tuple[str, ...]]],
    expected: dict[str, str],
) -> list[str]:
    """Findings for balloons whose attached component is not their BOM item."""
    findings = []
    seen: dict[str, int] = {}
    for name, item, stems in records:
        if len(stems) != 1:
            findings.append(f"{name} (item {item}) attaches to {list(stems)!r}")
            continue
        stem = stems[0]
        seen[stem] = seen.get(stem, 0) + 1
        want = expected.get(stem)
        if want is None:
            findings.append(f"{name} (item {item}) attaches to unballooned {stem}")
        elif want != item:
            findings.append(f"{name} shows item {item} but attaches to {stem} (item {want})")
    for stem, item in sorted(expected.items()):
        if seen.get(stem, 0) != 1:
            findings.append(
                f"{stem} (item {item}) carries {seen.get(stem, 0)} balloons, expected 1"
            )
    return findings


def bom_row_fit(requested: float, actual: float) -> Literal["short", "exact", "grown"]:
    """Classify a persisted BOM row height against the requested height."""
    if actual < requested - BOM_HEIGHT_TOLERANCE:
        return "short"
    if actual <= requested + BOM_HEIGHT_TOLERANCE:
        return "exact"
    return "grown"


def bom_split_row(data_rows: int) -> int:
    """Data rows in the FIRST column: the larger half, so column two is never taller."""
    if data_rows < 2:
        raise ValueError("a split BOM needs at least two data rows")
    return (data_rows + 1) // 2


def bom_extent_violations(
    anchor: tuple[float, float],
    width: float,
    height: float,
) -> list[str]:
    """Name every way a top-left-anchored BOM piece leaves its paper budget."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    left, top = anchor
    right = left + width
    bottom = top - height
    clearance = BOM_SHEET_CLEARANCE
    violations = []
    if left < clearance:
        violations.append(f"left edge {left * 1000:.3f} mm is off the sheet")
    if right > template.width_m - clearance:
        violations.append(
            f"right edge {right * 1000:.3f} mm passes "
            f"{(template.width_m - clearance) * 1000:.3f} mm"
        )
    if top > template.height_m - clearance:
        violations.append(
            f"top edge {top * 1000:.3f} mm passes "
            f"{(template.height_m - clearance) * 1000:.3f} mm"
        )
    title_block_floor = template.title_block_top_m + clearance
    if right > template.title_block_left_m and bottom < title_block_floor:
        violations.append(
            f"bottom edge {bottom * 1000:.3f} mm enters the title block "
            f"(floor {title_block_floor * 1000:.3f} mm)"
        )
    if bottom < clearance:
        violations.append(f"bottom edge {bottom * 1000:.3f} mm is off the sheet")
    return violations


def instance_counts(instances: Sequence[Instance]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for instance in instances:
        counts[instance.stem] = counts.get(instance.stem, 0) + 1
    return counts


def bom_components(counts: dict[str, int]) -> tuple[str, ...]:
    """The BOM families the model carries, in cluster order."""
    ordered = [stem for stems in CLUSTERS.values() for stem in stems]
    seen: list[str] = []
    for stem in ordered:
        if stem in counts and stem not in seen:
            seen.append(stem)
    return tuple(seen)


def source_violations(counts: dict[str, int]) -> list[str]:
    """Refusals for a source whose families the package cannot represent."""
    findings = []
    unknown = unclassified_stems(sorted(counts))
    if unknown:
        findings.append(f"unclassified or retired families {unknown!r}")
    required = set(BOM_PART_NUMBERS) - PENDING_STEMS
    missing = sorted(required - set(counts))
    if missing:
        findings.append(f"released families missing from the model {missing!r}")
    return findings


def cone_station_rows(
    gears: Sequence[tuple[float, str]],
) -> list[tuple[int, str]]:
    """(station, configuration) front (-z) to back from (world z mm, config)."""
    ordered = sorted(gears)
    return [(index, config) for index, (_z, config) in enumerate(ordered, start=1)]


def station_table_text(rows: Sequence[tuple[int, str]]) -> str:
    """Two-column station table: STN n  MHA-013 Tnnn."""
    half = (len(rows) + 1) // 2
    lines = ["CONE STATION TABLE - MHA-013 BY STATION, FRONT TO BACK"]
    for left, right in zip(rows[:half], [*rows[half:], None]):
        text = f"STN {left[0]:>2}  {left[1]}"
        if right is not None:
            text += f"      STN {right[0]:>2}  {right[1]}"
        lines.append(text)
    return "\n".join(lines)


# ============================ COM helpers =======================================


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if current is None:
        raise RuntimeError("drawing has no current sheet after activation")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")


def _add_note_block(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> Any:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add {label}")
    note = _early_bound(note, "INote")
    actual = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    expected = text.replace("\r\n", "\n").replace("\r", "\n")
    if actual != expected:
        raise RuntimeError(
            f"{label} text did not persist "
            f"(actual_length={len(actual)}, expected_length={len(expected)})"
        )
    return note


def _note_extent(adapter: Any, note: Any, *, label: str) -> tuple[float, ...]:
    """The rendered sheet-space box (x0, y0, x1, y1) of a free note."""
    adapter.currentModel.GraphicsRedraw2()
    extent = tuple(float(value) for value in (_early_bound(note, "INote").GetExtent() or ()))
    if len(extent) != 6 or extent[3] <= extent[0] or extent[4] <= extent[1]:
        raise RuntimeError(f"{label}: note has no rendered extent: {extent!r}")
    return (extent[0], extent[1], extent[3], extent[4])


def _anchor_note(
    adapter: Any, note: Any, corner: tuple[float, float], *, label: str
) -> tuple[float, ...]:
    """Steer a note's RENDERED top-left corner toward ``corner`` (summing r10/r11:
    the text box neither sits on nor tracks the insertion point 1:1)."""
    target_x, target_y = corner
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{label}: note has no annotation to move")
    extent = _note_extent(adapter, note, label=label)
    moves = 0
    for _pass in range(NOTE_ANCHOR_PASSES):
        shift = (target_x - extent[0], target_y - extent[3])
        if max(abs(shift[0]), abs(shift[1])) <= NOTE_ANCHOR_SETTLE:
            break
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3:
            raise RuntimeError(f"{label}: note position is unreadable: {position!r}")
        if not annotation.SetPosition(position[0] + shift[0], position[1] + shift[1], position[2]):
            raise RuntimeError(f"{label}: note SetPosition failed")
        extent = _note_extent(adapter, note, label=label)
        moves += 1
    _telemetry.event(
        "drawing.note_anchor",
        block=label,
        moves=moves,
        target_mm=(target_x * 1000.0, target_y * 1000.0),
        extent_mm=tuple(value * 1000.0 for value in extent),
    )
    return extent


def _stack_note_field(
    adapter: Any,
    blocks: tuple[tuple[str, str], ...],
    field: tuple[float, float, float, float],
    *,
    label: str,
) -> list[str]:
    """Stack note blocks top-down in one field; return every field violation."""
    left, top, _right, _bottom = field
    y = top
    findings = []
    for block_label, text in blocks:
        note = _add_note_block(adapter, text, (left, y), label=block_label)
        extent = _anchor_note(
            adapter, note, (left + NOTE_FIELD_INSET, y - NOTE_FIELD_INSET), label=block_label
        )
        violations = note_field_violations(extent, field)
        _telemetry.event(
            "drawing.note_field",
            field=label,
            block=block_label,
            extent_mm=tuple(value * 1000.0 for value in extent),
            violations=tuple(violations),
        )
        if violations:
            findings.append(f"{label}: {block_label} leaves its note field: " + "; ".join(violations))
        y = extent[1] - NOTE_BLOCK_GAP
    return findings


def _view_outline(view: Any) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"view has an invalid outline {outline!r}")
    return outline


def _shift_view(adapter: Any, view: Any, delta: tuple[float, float], *, label: str) -> None:
    """Move a drawing view by a sheet-space delta and read the move back."""
    view = _early_bound(view, "IView")
    before = tuple(float(value) for value in view.Position)
    target = (before[0] + delta[0], before[1] + delta[1])
    if not view.SetViewPosition(double_array(list(target)), False):
        raise RuntimeError(f"{label}: SetViewPosition refused {target!r}")
    adapter.currentModel.EditRebuild3()
    after = tuple(float(value) for value in view.Position)
    if math.dist(after, target) > 1e-6:
        raise RuntimeError(f"{label}: view moved to {after!r}, expected {target!r}")


def _caption_under(adapter: Any, view: Any, text: str, *, label: str) -> None:
    """A caption centred under a view's outline."""
    outline = _view_outline(view)
    note = _add_note_block(adapter, text, (outline[0], outline[1]), label=label)
    extent = _note_extent(adapter, note, label=label)
    width = extent[2] - extent[0]
    _anchor_note(
        adapter,
        note,
        ((outline[0] + outline[2]) / 2.0 - width / 2.0, outline[1] - VIEW_CAPTION_GAP),
        label=label,
    )


def _balloon_leader(annotation: Any, name: str) -> LeaderSegment:
    """A balloon's straight leader: balloon end -> attachment, sheet meters."""
    points = tuple(float(value) for value in (annotation.GetLeaderPointsAtIndex(0) or ()))
    if len(points) < 6:
        raise RuntimeError(f"{name}: balloon leader is unreadable: {points!r}")
    return LeaderSegment(name, "note", points[0], points[1], points[-3], points[-2])


def _uncross_balloon_leaders(adapter: Any, balloons: list[Any], *, label: str) -> None:
    """Swap the ring slots of any two balloons whose leaders cross."""
    annotations = {}
    for balloon in balloons:
        note = _early_bound(balloon, "INote")
        annotations[str(note.GetName() or "")] = _early_bound(
            note.GetAnnotation(), "IAnnotation"
        )
    swaps = []
    for _attempt in range(len(annotations)):
        segments = [_balloon_leader(annotation, name) for name, annotation in annotations.items()]
        crossings = find_leader_leader_crossings(segments)
        if not crossings:
            break
        first, second = crossings[0].a.label, crossings[0].b.label
        a, b = annotations[first], annotations[second]
        pa = tuple(float(value) for value in a.GetPosition())
        pb = tuple(float(value) for value in b.GetPosition())
        if not (a.SetPosition(*pb) and b.SetPosition(*pa)):
            raise RuntimeError(f"{label}: cannot swap balloons {first} and {second}")
        adapter.currentModel.EditRebuild3()
        swaps.append((first, second))
    _telemetry.event("drawing.balloon_uncross", label=label, swaps=tuple(swaps))


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _component_name(component: Any) -> str:
    return str(_early_bound(component, "IComponent2").Name2 or "").rsplit("/", 1)[-1]


def _verify_balloon_attachments(
    balloons: Sequence[Any], items: Sequence[tuple[str, str]], *, label: str
) -> None:
    """Prove each balloon's leader lands on the component its item names."""
    records = []
    evidence = []
    for balloon in balloons:
        note = _early_bound(balloon, "INote")
        name = str(note.GetName() or "")
        item = str(note.GetBomBalloonText(True) or "").strip()
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        entities = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(int(value) for value in (annotation.GetAttachedEntityTypes() or ()))
        stems = []
        components = []
        for entity, kind in zip(entities, types):
            if kind == 0 or entity is None:  # swSelNOTHING
                continue
            component = _early_bound(entity, "IEntity").GetComponent()
            if component is None:
                continue
            components.append(_component_name(component))
            stems.append(_component_stem(component))
        leader = _balloon_leader(annotation, name)
        records.append((name, item, tuple(sorted(set(stems)))))
        evidence.append(
            {
                "balloon": name,
                "item": item,
                "components": tuple(components),
                "attach_mm": (leader.x1 * 1000.0, leader.y1 * 1000.0),
            }
        )
    violations = balloon_attachment_violations(records, dict(items))
    _telemetry.event(
        "drawing.balloon_attachment",
        label=label,
        balloons=repr(evidence),
        violations=tuple(violations),
    )
    if violations:
        raise RuntimeError(f"{label}: balloon attachment mismatch: " + "; ".join(violations))


def _set_exploded_state(adapter: Any, view: Any, show: bool, *, label: str) -> None:
    bound = _early_bound(view, "IView")
    if str(bound.ReferencedConfiguration) != SOURCE_CONFIGURATION:
        raise RuntimeError(f"{label}: view must reference {SOURCE_CONFIGURATION!r}")
    returned = bool(bound.ShowExploded(show))
    actual = bool(bound.IsExploded())
    if actual != show:
        raise RuntimeError(f"{label}: exploded-state readback is {actual}, expected {show}")
    if show and not returned:
        raise RuntimeError(f"{label}: ShowExploded returned false")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: exploded-state rebuild failed")


def _isolate_instances(adapter: Any, view: Any, names: frozenset[str], *, label: str) -> None:
    """Show exactly the named top-level instances in one drawing view.

    The shared ``isolate_drawing_view_components`` works per FAMILY; foot-screw
    belongs to two clusters (pedestal flange vs spring foot), so this isolates
    per instance and reads the visibility back.
    """
    view = _early_bound(view, "IView")
    root = view.RootDrawingComponent2(False)
    if root is None:
        raise RuntimeError(f"{label}: drawing view has no root component")
    root = _early_bound(root, "IDrawingComponent")
    shown: set[str] = set()
    seen: list[str] = []
    hidden = 0
    for raw in tuple(root.GetChildren() or ()):
        drawing_component = _early_bound(raw, "IDrawingComponent")
        raw_name = str(drawing_component.Name or "")
        seen.append(raw_name)
        name = raw_name.split("@", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]
        visible = name in names
        drawing_component.Visible = visible
        if visible:
            shown.add(name)
        else:
            hidden += 1
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: rebuild after isolation failed")
    missing = sorted(names - shown)
    _telemetry.event(
        "drawing.isolate_instances",
        label=label,
        shown=len(shown),
        hidden=hidden,
        missing=tuple(missing),
        outline_mm=tuple(value * 1000.0 for value in _view_outline(view)),
    )
    if missing:
        raise RuntimeError(
            f"{label}: instances not in the view: {missing!r}; "
            f"drawing components seen (first 12): {seen[:12]!r}"
        )


def _check_package_layout(adapter: Any, field_findings: list[str]) -> None:
    """Audit every sheet; fail on any finding, including note-field findings."""
    failures = list(field_findings)
    for number, sheet_name in enumerate(SHEET_NAMES, start=1):
        _activate_sheet(adapter, sheet_name)
        try:
            check_drawing_layout(
                adapter, layout=SHEET_LAYOUTS[sheet_name], stem=f"{ARTIFACT_STEM} sheet {number}"
            )
        except RuntimeError as exc:
            failures.append(f"sheet {number} {sheet_name}: {exc}")
    if failures:
        raise RuntimeError("drive-train package layout audit failed:\n" + "\n".join(failures))


def _export_failure_pdf(adapter: Any, stage: str) -> None:
    """Export the failing package under the forensic tree the farm uploads."""
    model = adapter.currentModel
    if model is None or int(_early_bound(model, "IModelDoc2").GetType()) != 3:
        _telemetry.warn(f"{stage}-failure PDF skipped: no active drawing")
        return
    path = (
        OUT_FAILURES
        / f"drive-train-package-{stage}"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        / f"{ARTIFACT_STEM}.pdf"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _early_bound(adapter.currentModel, "IModelDoc2").SaveAs3(str(path), 0, 0)
    except Exception as exc:  # noqa: BLE001 - evidence must not mask the failure
        _telemetry.warn(f"{stage}-failure PDF export failed: {exc!r}")
        return
    if not path.is_file():
        _telemetry.warn(f"{stage}-failure PDF export produced no file: {path}")
        return
    _telemetry.event("drawing.failure_pdf", stage=stage, path=str(path))
    _telemetry.info(f"{stage}-failure evidence PDF: {path}")


# ============================ source validation ==================================


class SourceFacts:
    """What the package reads from the opened drive-train model."""

    def __init__(self, instances: list[Instance], configurations: dict[str, str]):
        self.instances = instances
        self.configurations = configurations
        self.counts = instance_counts(instances)
        self.components = bom_components(self.counts)
        self.clusters = cluster_members(instances)

    def cone_rows(self) -> list[tuple[int, str]]:
        return cone_station_rows(
            [
                (instance.origin_mm[2], self.configurations[instance.name])
                for instance in self.instances
                if instance.stem == "cone-gear"
            ]
        )

    def count(self, stem: str) -> int:
        return self.counts.get(stem, 0)


def _validate_source(source_model: Any) -> SourceFacts:
    """Consume the builder-owned presentation without changing the assembly."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != SOURCE_CONFIGURATION:
        raise RuntimeError(f"drive-train source must open in {SOURCE_CONFIGURATION!r}")
    names = tuple(assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ())
    if names != (EXPLODED_VIEW_NAME,):
        raise RuntimeError(
            f"drive-train source exploded views {names!r} != {(EXPLODED_VIEW_NAME,)!r}"
        )
    instances = []
    configurations = {}
    numbers: dict[str, set[str]] = {}
    for raw_component in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw_component, "IComponent2")
        name = _component_name(component)
        stem = _component_stem(component)
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform").ArrayData
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform").ArrayData
        if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(total, base, strict=True)):
            raise RuntimeError(f"drive-train source must open collapsed: {name!r} is displaced")
        origin = tuple(float(value) * 1000.0 for value in tuple(base)[9:12])
        instances.append(Instance(name=name, stem=stem, origin_mm=origin))
        configurations[name] = str(component.ReferencedConfiguration or "")
        # A lightweight component has no loaded model; its Number is then
        # unreadable here (the offline registry test still pins it).
        model = component.GetModelDoc2()
        if model is not None:
            number = str(
                _early_bound(model, "IModelDoc2").GetCustomInfoValue("", "Number") or ""
            )
            numbers.setdefault(stem, set()).add(number)
    facts = SourceFacts(instances, configurations)
    findings = source_violations(facts.counts)
    for stem, seen in sorted(numbers.items()):
        want = BOM_PART_NUMBERS.get(stem)
        if want is not None and seen != {want}:
            findings.append(f"{stem} model Number {sorted(seen)!r} != released {want!r}")
    unread = sorted(set(facts.counts) - set(numbers))
    if unread:
        _telemetry.warn(f"drive-train source: Number unreadable (not loaded) for {unread!r}")
    _telemetry.event(
        "drawing.drive_train_source",
        counts=repr(facts.counts),
        numbers_read=tuple(sorted(numbers)),
        numbers_unread=tuple(unread),
        pending_present=tuple(sorted(PENDING_STEMS & set(facts.counts))),
        findings=tuple(findings),
    )
    if findings:
        raise RuntimeError("drive-train source refused: " + "; ".join(findings))
    return facts


# ============================ BOM ==============================================


def _validate_bom(
    adapter: Any, table: Any, facts: SourceFacts
) -> tuple[tuple[tuple[str, str], ...], int]:
    """Rewrite part numbers, prove identities/quantities; return (stem, item) and part column."""
    table = _early_bound(table, "ITableAnnotation")
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    components = facts.components
    if rows != len(components) + 1 or columns < 4:
        raise RuntimeError(
            f"drive-train BOM is {rows}x{columns}; expected {len(components) + 1} rows"
        )
    contents = tuple(
        tuple(str(table.DisplayedText(row, column) or "").strip() for column in range(columns))
        for row in range(rows)
    )
    header = tuple(cell.upper() for cell in contents[0])

    def column_named(predicate: Callable[[str], bool], label: str) -> int:
        matches = [index for index, cell in enumerate(header) if predicate(cell)]
        if len(matches) != 1:
            raise RuntimeError(f"drive-train BOM has no unique {label} column: {header!r}")
        return matches[0]

    item_column = column_named(lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
    part_column = column_named(lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = column_named(lambda cell: cell == "DESCRIPTION", "DESCRIPTION")
    quantity_column = column_named(lambda cell: cell.startswith("QTY"), "QTY.")
    for column, width in (
        (item_column, BOM_COLUMN_WIDTHS["item"]),
        (part_column, BOM_COLUMN_WIDTHS["part"]),
        (description_column, BOM_COLUMN_WIDTHS["description"]),
        (quantity_column, BOM_COLUMN_WIDTHS["quantity"]),
    ):
        actual_width = float(table.SetColumnWidth(column, width, 0))
        if abs(actual_width - width) > 1e-6:
            raise RuntimeError(
                f"drive-train BOM column {column} width did not persist: "
                f"{actual_width * 1000:.3f} mm"
            )

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        text = row[part_column].strip().casefold()
        stem = BOM_NORMALIZED_ALIASES.get(text, text)
        if stem in actual:
            raise RuntimeError(f"drive-train BOM repeats component family {stem!r}")
        actual[stem] = (row_index, row[item_column], row[description_column], row[quantity_column])
    if set(actual) != set(components):
        raise RuntimeError(
            f"drive-train BOM identities {sorted(actual)!r} != {sorted(components)!r}"
        )
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(components) + 1)}:
        raise RuntimeError(f"drive-train BOM item numbers {sorted(items)!r} are not contiguous")
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(f"drive-train BOM part-number cell for {stem!r} is not editable")
            table.SetText2(row_index, part_column, False, number)
            if str(table.DisplayedText2(row_index, part_column, False) or "").strip() != number:
                raise RuntimeError(f"drive-train BOM part number for {stem!r} did not persist")
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"drive-train BOM description mismatch for {stem!r}: {description!r}")
        if quantity != str(facts.count(stem)):
            raise RuntimeError(
                f"drive-train BOM quantity for {stem!r} is {quantity!r}, "
                f"model has {facts.count(stem)}"
            )
    header_count = int(table.GetHeaderCount())
    setter_heights = tuple(float(table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)) for row in range(rows))
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("drive-train BOM rebuild failed")
    for row, setter_height in enumerate(setter_heights):
        height = float(table.GetRowHeight(row))
        fit = bom_row_fit(BOM_ROW_HEIGHT, height)
        _telemetry.event(
            "drawing.bom_row_height",
            row=row,
            row_kind="header" if row < header_count else "data",
            fit=fit,
            setter_mm=setter_height * 1000.0,
            actual_mm=height * 1000.0,
            cells=contents[row],
        )
        if fit == "short":
            raise RuntimeError(f"drive-train BOM row {row} is {height * 1000:.3f} mm, below request")
        if fit == "grown" and row >= header_count:
            _telemetry.warn(f"drive-train BOM data row {row} grew to {height * 1000:.3f} mm")
    for stem, (row_index, *_rest) in actual.items():
        if str(table.DisplayedText(row_index, part_column) or "").strip() != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(f"drive-train BOM part number for {stem!r} reverted")
    return tuple((stem, actual[stem][1]) for stem in components), header_count


def _bom_feature_name(table: Any) -> str:
    bom = _early_bound(table, "IBomTableAnnotation")
    feature = _early_bound(bom.BomFeature, "IBomFeature")
    name = str(feature.Name or "")
    if not name:
        raise RuntimeError("drive-train BOM feature has no name")
    return name


def _split_bom(adapter: Any, table: Any, *, data_rows: int, header_count: int) -> None:
    """Split the BOM into two side-by-side columns and hold both to the sheet."""
    table = _early_bound(table, "ITableAnnotation")
    first_rows = bom_split_row(data_rows)
    split_after = header_count + first_rows - 1  # 0-based row index
    second = table.Split(2, split_after)  # swTableSplit_AfterRow
    if second is None:
        raise RuntimeError(f"drive-train BOM split after row {split_after} failed")
    second = _early_bound(second, "ITableAnnotation")
    annotation = _early_bound(second.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition(BOM_SECOND_COLUMN_X, BOM_ANCHOR[1], 0.0):
        raise RuntimeError("drive-train BOM second column refused its position")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("drive-train BOM split rebuild failed")
    findings = []
    for label, piece in (("first", table), ("second", second)):
        piece_annotation = _early_bound(piece.GetAnnotation(), "IAnnotation")
        position = tuple(float(value) for value in piece_annotation.GetPosition())
        # Row indexes stay those of the original table (ITableAnnotation::Split
        # remarks), so a piece's rows come from its split range, not RowCount.
        # The early-bound wrapper types the four outs as in/out VT_I4 BYREF, so
        # they must be passed; a bare call raises 'Type mismatch' (leaf
        # 20260923T044055Z-1-20b23f24). Same form as the layout audit's read.
        info = tuple(piece.GetSplitInformation(0, 0, 0, 0))
        if len(info) != 5:
            raise RuntimeError(f"{label} BOM column split information unreadable: {info!r}")
        _direction, _index, _count, start, end = (int(value) for value in info)
        piece_rows = sorted({*range(header_count), *range(start, end + 1)})
        rows = len(piece_rows)
        height = sum(float(piece.GetRowHeight(row)) for row in piece_rows)
        width = sum(float(piece.GetColumnWidth(column)) for column in range(int(piece.ColumnCount)))
        violations = bom_extent_violations((position[0], position[1]), width, height)
        _telemetry.event(
            "drawing.bom_piece",
            piece=label,
            anchor_mm=(position[0] * 1000.0, position[1] * 1000.0),
            rows=rows,
            split_range=(start, end),
            width_mm=width * 1000.0,
            height_mm=height * 1000.0,
            violations=tuple(violations),
        )
        findings.extend(f"{label} BOM column: {violation}" for violation in violations)
    if findings:
        raise RuntimeError("drive-train BOM split: " + "; ".join(findings))


def _link_view_to_bom(view: Any, bom_name: str, *, label: str) -> None:
    view = _early_bound(view, "IView")
    if not view.SetKeepLinkedToBOM(True, bom_name):
        raise RuntimeError(f"{label}: SetKeepLinkedToBOM({bom_name!r}) returned false")
    if not bool(view.GetKeepLinkedToBOM()) or str(view.GetKeepLinkedToBOMName() or "") != bom_name:
        raise RuntimeError(f"{label}: view is not linked to BOM {bom_name!r}")


# ============================ sheets ============================================


def _create_package_sheets(adapter: Any) -> None:
    new_project_drawing(adapter, layout=SPEC.layout, scale=ASSEMBLED_SCALE)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="drive-train assembly package")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet_number, sheet_name in enumerate(SHEET_NAMES, start=1):
        _activate_sheet(adapter, sheet_name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(f"failed to set drive-train sheet scale: {sheet_name}")
        _add_note_block(
            adapter,
            f"SHEET {sheet_number} OF {len(SHEET_NAMES)}",
            SHEET_NUMBER_XY,
            label="package sheet number",
        )


def _heading(
    adapter: Any, sheet_number: int, text: str = "", *, xy: tuple[float, float] = HEADING_XY
) -> None:
    lines = [f"{DRAWING_NUMBER} - {SHEET_NAMES[sheet_number - 1]}"]
    if text:
        lines.append(text)
    _add_note_block(adapter, "\n".join(lines), xy, label=f"sheet {sheet_number} heading")


def _reference_iso(
    adapter: Any,
    *,
    caption: str,
    label: str,
    center: tuple[float, float] = REFERENCE_ISO_CENTER,
) -> Any:
    """A small collapsed isometric: every sheet needs a view for its title block."""
    view = place_view(adapter, str(SOURCE), "*Isometric", *center, scale=REFERENCE_ISO_SCALE)
    _set_exploded_state(adapter, view, False, label=label)
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    _caption_under(adapter, view, caption, label=f"{label} caption")
    return view


def _place_assembled_sheet(adapter: Any) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[0])
    front = place_view(adapter, str(SOURCE), "*Front", 0.080, 0.110, scale=ASSEMBLED_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", 0.080, 0.200, scale=ASSEMBLED_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", 0.200, 0.110, scale=ASSEMBLED_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ASSEMBLED_ISO_CENTER, scale=ASSEMBLED_ISO_SCALE
    )
    for label, view in (("front", front), ("top", top), ("right", right), ("isometric", iso)):
        _set_exploded_state(adapter, view, False, label=f"assembled {label}")
    for view in (front, top, right):
        set_hidden_lines_removed(adapter, view)
    set_high_quality_shaded_with_edges(adapter, iso, label="drive-train assembled isometric")

    # ASME alignment on the model origin: top shares front's x, right shares y.
    origin = (0.0, 0.0, 0.0)
    front_origin = model_point_in_view(adapter, front, origin, label="front origin")
    top_origin = model_point_in_view(adapter, top, origin, label="top origin")
    right_origin = model_point_in_view(adapter, right, origin, label="right origin")
    _shift_view(adapter, top, (front_origin[0] - top_origin[0], 0.0), label="top alignment")
    _shift_view(adapter, right, (0.0, front_origin[1] - right_origin[1]), label="right alignment")
    front_box, top_box, right_box = (_view_outline(v) for v in (front, top, right))
    _shift_view(adapter, top, (0.0, front_box[3] + PROJECTED_GAP - top_box[1]), label="top gap")
    _shift_view(
        adapter, right, (front_box[2] + PROJECTED_GAP - right_box[0], 0.0), label="right gap"
    )
    boxes = [_view_outline(v) for v in (front, top, right)]
    group = (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
    delta = (PROJECTED_GROUP_ORIGIN[0] - group[0], PROJECTED_GROUP_ORIGIN[1] - group[1])
    for label, view in (("front", front), ("top", top), ("right", right)):
        _shift_view(adapter, view, delta, label=f"projected group {label}")
    group = (group[0] + delta[0], group[1] + delta[1], group[2] + delta[0], group[3] + delta[1])
    findings = [
        f"sheet 1 projected group {edge}"
        for edge, bad in (
            ("passes the right of its region", group[2] > PROJECTED_REGION[2]),
            ("passes the top of its region", group[3] > PROJECTED_REGION[3]),
        )
        if bad
    ]
    _telemetry.event(
        "drawing.projected_group",
        group_mm=tuple(value * 1000.0 for value in group),
        findings=tuple(findings),
    )
    _heading(adapter, 1, ASSEMBLED_HEADING, xy=ASSEMBLED_HEADING_XY)
    scale = f"{int(ASSEMBLED_SCALE[0])}:{int(ASSEMBLED_SCALE[1])}"
    _caption_under(adapter, front, f"FRONT {scale}", label="front caption")
    _caption_under(adapter, top, f"TOP {scale}", label="top caption")
    _caption_under(adapter, right, f"RIGHT {scale}", label="right caption")
    _caption_under(
        adapter,
        iso,
        f"ISOMETRIC {int(ASSEMBLED_ISO_SCALE[0])}:{int(ASSEMBLED_ISO_SCALE[1])}",
        label="isometric caption",
    )
    return findings


def _place_bom_sheet(adapter: Any, facts: SourceFacts) -> tuple[str, dict[str, str]]:
    _activate_sheet(adapter, SHEET_NAMES[1])
    view = place_view(
        adapter, str(SOURCE), "*Isometric", *BOM_REFERENCE_ISO_CENTER, scale=REFERENCE_ISO_SCALE
    )
    _set_exploded_state(adapter, view, False, label="BOM reference isometric")
    set_high_quality_shaded_with_edges(adapter, view, label="BOM reference isometric")
    table = insert_bom_table(
        adapter,
        view,
        anchor_xy=BOM_ANCHOR,
        expected_components=facts.components,
        descriptions={stem: BOM_DESCRIPTIONS[stem] for stem in facts.components},
        identity_aliases={BOM_PART_NUMBERS[stem]: stem for stem in facts.components},
        configuration_grouping="same-part",
        label="drive-train",
    )
    items, header_count = _validate_bom(adapter, table, facts)
    bom_name = _bom_feature_name(table)
    _split_bom(adapter, table, data_rows=len(facts.components), header_count=header_count)
    _heading(adapter, 2)
    _caption_under(
        adapter,
        view,
        BOM_REFERENCE_CAPTION,
        label="BOM reference caption",
    )
    return bom_name, dict(items)


def _place_cluster_sheet(
    adapter: Any,
    cluster: Cluster,
    facts: SourceFacts,
    *,
    bom_name: str,
    items: dict[str, str],
) -> None:
    number = CLUSTER_SHEETS[cluster]
    _activate_sheet(adapter, SHEET_NAMES[number - 1])
    label = f"{cluster} exploded isometric"
    view = place_view(adapter, str(SOURCE), "*Isometric", *CLUSTER_VIEW_CENTER, scale=CLUSTER_SCALE)
    _set_exploded_state(adapter, view, True, label=label)
    names = frozenset(facts.clusters[cluster])
    _isolate_instances(adapter, view, names, label=label)
    set_high_quality_shaded_with_edges(adapter, view, label=label)
    _link_view_to_bom(view, bom_name, label=label)
    outline = _view_outline(view)
    shift, overflows = ring_fit_shift(
        outline, CLUSTER_RING_REGION, grow=CLUSTER_BALLOON_MARGIN + BALLOON_DIAMETER
    )
    _telemetry.event(
        "drawing.cluster_ring_fit",
        cluster=cluster,
        outline_mm=tuple(value * 1000.0 for value in outline),
        shift_mm=tuple(value * 1000.0 for value in shift),
        overflows=tuple(overflows),
    )
    if overflows:
        _telemetry.warn(
            f"{label}: balloon ring estimate overflows ({'; '.join(overflows)}); the audit decides"
        )
    _shift_view(adapter, view, shift, label=f"{label} ring fit")
    stems = sorted(
        {instance.stem for instance in facts.instances if instance.name in names},
        key=lambda stem: int(items[stem]),
    )
    balloon_items = tuple((stem, items[stem]) for stem in stems)
    balloons = add_component_bom_balloons(
        adapter,
        view,
        items=balloon_items,
        label=f"drive-train {cluster} BOM coverage",
        margin=CLUSTER_BALLOON_MARGIN,
    )
    _uncross_balloon_leaders(adapter, balloons, label=label)
    _verify_balloon_attachments(balloons, balloon_items, label=label)
    _heading(
        adapter,
        number,
        f"{CLUSTER_TITLES[cluster]} - EXPLODED ISOMETRIC "
        f"{int(CLUSTER_SCALE[0])}:{int(CLUSTER_SCALE[1])}; ITEMS PER SHEET 2",
    )


def _place_sequence_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[SEQUENCE_SHEET - 1])
    _heading(adapter, SEQUENCE_SHEET)
    _reference_iso(
        adapter,
        caption="FINISHED ASSEMBLY 1:8",
        label="sequence reference isometric",
        center=SEQUENCE_REFERENCE_ISO_CENTER,
    )
    findings = _stack_note_field(
        adapter,
        (
            (
                "cone and crank sequence",
                CONE_CRANK_STEPS.format(cone_gears=facts.count("cone-gear")),
            ),
            ("cone station table", station_table_text(facts.cone_rows())),
        ),
        SEQUENCE_LEFT_FIELD,
        label=f"sheet {SEQUENCE_SHEET} left note field",
    )
    findings += _stack_note_field(
        adapter,
        (
            (
                "bank and rig sequence",
                BANK_RIG_STEPS.format(
                    cylinder_gears=facts.count("cylinder-gear"),
                    cam_pins=facts.count("pinion-cam-pin"),
                    pivot_blocks=facts.count("pinion-pivot-block"),
                    cams=facts.count("pinion-cam"),
                    slotted=facts.count("slotted-screw"),
                ),
            ),
        ),
        NOTE_FIELD_RIGHT,
        label=f"sheet {SEQUENCE_SHEET} right note field",
    )
    return findings


def _place_fit_sheet(adapter: Any) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[FIT_SHEET - 1])
    _heading(adapter, FIT_SHEET)
    _reference_iso(adapter, caption="FINISHED ASSEMBLY 1:8", label="fit reference isometric")
    return _stack_note_field(
        adapter,
        (("fit placeholder", FIT_PLACEHOLDER),),
        NOTE_FIELD_LEFT,
        label=f"sheet {FIT_SHEET} note field",
    )


def _place_checks_sheet(adapter: Any, facts: SourceFacts) -> list[str]:
    _activate_sheet(adapter, SHEET_NAMES[CHECKS_SHEET - 1])
    _heading(adapter, CHECKS_SHEET)
    _reference_iso(
        adapter, caption="FINISHED ASSEMBLY 1:8 - CHECK REFERENCE", label="checks reference isometric"
    )
    findings = _stack_note_field(
        adapter,
        (("functional checks", CHECKS.format(cone_gears=facts.count("cone-gear"))),),
        NOTE_FIELD_LEFT,
        label=f"sheet {CHECKS_SHEET} left note field",
    )
    right_field = (NOTE_FIELD_RIGHT[0], NOTE_FIELD_RIGHT[1], NOTE_FIELD_RIGHT[2], 0.140)
    findings += _stack_note_field(
        adapter,
        (
            ("saved pose", SETUP_NOTES),
            (
                "external interfaces",
                INTERFACE_NOTES.format(
                    slotted=facts.count("slotted-screw"), foot=facts.count("foot-screw")
                ),
            ),
        ),
        right_field,
        label=f"sheet {CHECKS_SHEET} right note field",
    )
    return findings


def _place_package(adapter: Any, facts: SourceFacts) -> None:
    _create_package_sheets(adapter)
    findings = _place_assembled_sheet(adapter)
    bom_name, items = _place_bom_sheet(adapter, facts)
    for cluster in CLUSTER_SHEETS:
        _place_cluster_sheet(adapter, cluster, facts, bom_name=bom_name, items=items)
    findings += _place_sequence_sheet(adapter, facts)
    findings += _place_fit_sheet(adapter)
    findings += _place_checks_sheet(adapter, facts)
    _check_package_layout(adapter, findings)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    fingerprint = _source_fingerprint(SOURCE)
    check("open drive-train drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    if bool(source_model.GetSaveFlag()):
        raise RuntimeError("drive-train source assembly is already dirty; refusing to discard changes")
    read_required_properties(
        source_model,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    source_title = str(source_model.GetTitle() or "")
    if not source_title:
        raise RuntimeError("drive-train source assembly has no document title")

    artifacts: dict[str, str] | None = None
    try:
        try:
            facts = _validate_source(source_model)
            _place_package(adapter, facts)
            artifacts = await finalize_drawing(
                adapter,
                OUTPUTS,
                layout=SPEC.layout,
                pdf_title="Drive-Train Assembly Drawing Package",
                scale=ASSEMBLED_SCALE,
                expected_sheet_names=SHEET_NAMES,
                sheet_layouts=SHEET_LAYOUTS,
                sheet_scales=SHEET_SCALES,
            )
        except Exception:
            _export_failure_pdf(adapter, "build")
            raise
    finally:
        primary_error = sys.exception()
        cleanup_errors: list[str] = []
        if artifacts is None:
            try:
                active_model = adapter.currentModel
                if active_model is not None:
                    active_model = _early_bound(active_model, "IModelDoc2")
                    if int(active_model.GetType()) == 3:
                        drawing_title = str(active_model.GetTitle() or "")
                        if drawing_title:
                            adapter.swApp.CloseDoc(drawing_title)
                        else:
                            cleanup_errors.append("generated drive-train drawing has no title")
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(f"failed to close generated drive-train drawing: {exc}")
        try:
            adapter.swApp.CloseDoc(source_title)
            if adapter.swApp.GetOpenDocumentByName(str(SOURCE.resolve())) is not None:
                cleanup_errors.append(f"drive-train source {source_title!r} remained open")
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(f"failed to close drive-train source {source_title!r}: {exc}")
        try:
            after = _source_fingerprint(SOURCE)
            if after != fingerprint:
                cleanup_errors.append(
                    "drive-train drawing generation changed the released source assembly: "
                    f"{fingerprint!r} -> {after!r}"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(f"failed to verify drive-train source fingerprint: {exc}")
        if cleanup_errors:
            message = "; ".join(cleanup_errors)
            if primary_error is not None:
                _telemetry.warn(f"drive-train drawing cleanup after failure: {message}")
            else:
                raise RuntimeError(message)

    if artifacts is None:
        raise RuntimeError("drive-train drawing package returned no artifacts")
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
