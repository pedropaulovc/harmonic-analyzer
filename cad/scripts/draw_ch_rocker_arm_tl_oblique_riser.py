r"""Create the drawing for the oblique-trammel jig's 6061 riser (MHA-CH-06-TL-24).

Nine hole axes on one view: rule 10 puts them in one native hole table (tags
R1-R4, HUB, CL, CR, P1, P2; X/Y LOC from the blank's lower-left corner, the
corner an edge finder picks up; owner review 2026-11-07, never a hole
centre). The R, HUB, CL and CR tags repeat the TL-21 carrier's own table
tags, because each riser hole is spotted through that carrier hole at
assembly: their LOC cells are REF (one note), and each row's MATE cell names
the TL-21 hole it is spotted from. The P1/P2 stop holes are drilled at their
ordinary .XX table locations. The SIZE column is SolidWorks' own, never
edited (farm r1: generated cells refuse SetText2): each cell must print an
inch rounding of the actual cut (the #30 .1285, the 12 mm relief's .4724,
the #9 .196) or the #30 drill number, under the title block's DRILLED HOLES
+.004/0; a plain cut's blank SIZE is given in its NOTE cell instead. The
inserted NOTE column carries the screw rows' countersink by its symbol, the
inserted MATE column each row's mate. The plan keeps the two overalls;
section A-A (2:1, its cutting plane a whole line across the width at R3)
the thickness and the countersink's form.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any, Callable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    place_view,
    visible_component_entities,
)
from solidworks_mcp.adapters.sw_type_info import constant

from _check import check
from _com import _early_bound
import _config
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_tables import insert_hole_table
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _printed_limits import limits
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_riser_spec as part_spec
from ch_rocker_arm_tl_oblique_riser_spec import (
    BLANK_LENGTH,
    BLANK_WIDTH,
    CL_HOLE,
    CR_HOLE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HUB_HOLE,
    SCREW_DIA,
    SCREW_DIA_PRINTED,
    SCREW_HOLES,
    STOP_DIA,
    STOP_HOLE_DIA,
    STOP_PIN_HOLES,
    THICKNESS,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_riser"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

_DRAW = "draw_ch_rocker_arm_tl_oblique_riser"
INCH = 25.4

# A 350.52 x 42.926 x 6.096 blank: the plan view at 1:2 carries the outline,
# its two overalls and the table tags; the hole table stands under it on the
# left, its two notes under the table. Section A-A cuts across the width
# through R3 at 2:1 (it stands upright right of the plan) to show the
# thickness and the countersink's form; its caption sits below it. The
# shaded isometric stands between the table and the section, above the title
# block.
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
SECTION_SCALE = (2, 1)
ISO_SCALE = (1, 4)
PLAN_CENTER = (0.150, 0.205)
SECTION_CENTER = (0.355, 0.215)
# Below the section's thickness dimension (review r5: the caption sat on the
# sectioned part).
CAPTION_XY = (0.355, 0.140)
# Right of the table and left of section A-A, above the title block (y 65):
# the 1:4 iso spans about 76 x 50 mm.
ISO_CENTER = (0.270, 0.115)
ISO_NOTE_XY = (0.240, 0.080)
# The cutting line runs across the width at R3 (screw hole 3), 7 mm (sheet)
# past both edges so its letters clear the outline; the arrows point +X and
# each letter stands 12-22 mm (sheet) right of the line.
CUT_X = SCREW_HOLES[2][0]
CUT_Y = (-14.0, BLANK_WIDTH + 14.0)
# Owner review 2026-11-07 (rule 9): a cutting plane is one whole line from
# one arrow to the other. A-A shows the whole cross-section, so its line runs
# across the whole width. swDetailingSectionViewLineStyleDisplay (542) =
# swDetailingSectionViewLineStyleDisplay_StandardWithConnector, as the
# TL-21 carrier's.
SECTION_LINE_STYLE_PREFERENCE = 542
SECTION_LINE_STYLE = 0

_T = THICKNESS

# Model points (mm) off the part, mapped onto each view at run time. Only the
# overalls remain on the plan; the table owns every hole location. The
# length stands 14 mm (sheet) under the bottom edge, below the lower tags; the
# width 12 mm right of the right end.
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    "BlankLength": (BLANK_LENGTH / 2.0, -28.0, _T),
    "BlankWidth": (BLANK_LENGTH + 24.0, BLANK_WIDTH / 2.0, _T),
}
# The thickness's text stands outside its 12 mm (sheet) span (jig-r6: its
# extension lines ran through "6.0 STOCK").
SECTION_KEEP: dict[str, tuple[float, float, float]] = {
    "BlankThick": (CUT_X, -6.0, _T + 9.0),
}
# The sheet prints only the overalls and the thickness as dimensions; the
# hole stations and sizes the part marks for the drawing print as the
# table's rows, so their reference sketches stay hidden and unimported.
IMPORTED_PRECISION: dict[str, int] = {
    name: DRAWING_PRECISION_BY_NAME[name] for name in (*PLAN_KEEP, *SECTION_KEEP)
}

_UP = [0.0, 0.0, 1.0]
_CALC = "ch_rocker_arm_tl_oblique_trammel_spec"
_UNIT = part_spec.UNIT


def _inch(mm: float, places: int) -> str:
    """An inch sheet value at ``places``, with no leading zero."""
    text = f"{mm / INCH:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# --- Hole table ----------------------------------------------------------------
# Every hole's tag: (model centre, cut diameter). R1-R4 are the four screw
# holes in the order of the carrier's R1-R4 taps; P1/P2 the stop holes.
TABLE_HOLES: dict[str, tuple[tuple[float, float], float]] = {
    **{f"R{i}": (xy, SCREW_DIA) for i, xy in enumerate(SCREW_HOLES, start=1)},
    "HUB": (HUB_HOLE, part_spec.HUB_DIA),
    "CL": (CL_HOLE, part_spec.CLAMP_DIA),
    "CR": (CR_HOLE, part_spec.CLAMP_DIA),
    **{f"P{i}": (xy, STOP_DIA) for i, xy in enumerate(STOP_PIN_HOLES, start=1)},
}
if sorted(xy for xy, _dia in TABLE_HOLES.values()) != sorted(
    xy for xy, _dia in part_spec.HOLES.values()
):
    raise AssertionError("the riser hole table does not list every hole once")
# The holes spotted through the TL-21 carrier at assembly; their tags are the
# carrier table's own, so a carrier hole maps onto its riser hole.
SPOTTED = ("R1", "R2", "R3", "R4", "HUB", "CL", "CR")
for _tag in SPOTTED:
    _x, _y, _dia = part_spec.carrier.TABLE_HOLES[_tag]
    if math.dist(part_spec.to_riser((_x, _y)), TABLE_HOLES[_tag][0]) > 1e-9:
        raise AssertionError(f"riser {_tag} is not spotted from carrier {_tag}")
# The table's location places: the stop holes' ordinary .XX stations and the
# spotted holes' 2-place reference stations.
TABLE_LOCATION_PLACES = 2
if part_spec.STATION_PLACES != TABLE_LOCATION_PLACES or any(
    DRAWING_PRECISION_BY_NAME[name] != TABLE_LOCATION_PLACES
    for name in ("Stop1X", "Stop2X", "StopY")
):
    raise AssertionError("the riser table's .XX locations differ from its stations")


def table_location(tag: str) -> tuple[float, float]:
    """A hole's X/Y LOC from the blank's lower-left corner, model mm."""
    return TABLE_HOLES[tag][0]


_PRINTED_LOCATIONS = {
    tag: tuple(round(value / INCH, TABLE_LOCATION_PLACES) for value in table_location(tag))
    for tag in TABLE_HOLES
}
if len(set(_PRINTED_LOCATIONS.values())) != len(TABLE_HOLES):
    raise AssertionError("two riser holes print the same table location")

# Same-parent short forms (rule 4): on MHA-CH-06-TL-24, TL-21 is
# MHA-CH-06-TL-21 and TL-VN-nn is MHA-CH-06-TL-VN-nn; MHA-CH-13 and
# MHA-SM-VN-53 lie outside MHA-CH-06 and print in full.
_OWN_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
_PARENT_PREFIX = _OWN_NUMBER[: _OWN_NUMBER.index("TL-")]


def _short(number: str) -> str:
    if not number.startswith(_PARENT_PREFIX):
        raise AssertionError(f"{number} is not in the riser's parent assembly")
    return number[len(_PARENT_PREFIX) :]


CARRIER_SHORT = _short(part_spec.CARRIER_NUMBER)
STRAP_NUMBER = _config.parts("ch-rocker-strap")["number"]
if STRAP_NUMBER.startswith(_PARENT_PREFIX) or part_spec.STOP_PIN_NUMBER.startswith(
    _PARENT_PREFIX
):
    raise AssertionError("an outside mate would print as a short form")

# SIZE is the native column: each cell prints the actual cut, rounded to
# three or four places (an inch value, never millimetres), or the wizard's
# #30 drill number on the #30 rows. The title block's DRILLED HOLES +.004/0
# is its band. The HUB, CL and CR holes are plain sketch cuts, not wizard
# holes: a table may leave their SIZE blank (MHA-FR-01's plain A1-A4 bores
# print none), and then the NOTE cell carries the design size instead.
_DIAM = "\u00d8"
NATIVE_DRILL_NUMBERS: dict[str, str] = {
    **{f"R{i}": part_spec.SCREW_DRILL for i in range(1, 5)},
    "P1": part_spec.STOP_DRILL,
    "P2": part_spec.STOP_DRILL,
}
# The inch cut each SIZE cell rounds: the wizard rows' exact #30 drill
# (.1285; the spec's 3.264 mm is its 3-decimal pin), the plain cuts' own
# diameters (12 mm, the #9's .196).
NATIVE_SIZE_CUTS_IN: dict[str, float] = {
    tag: (part_spec.SCREW_DRILL_DIA if tag in NATIVE_DRILL_NUMBERS else diameter) / INCH
    for tag, (_xy, diameter) in TABLE_HOLES.items()
}
if part_spec.STOP_DRILL != part_spec.SCREW_DRILL:
    raise AssertionError("the stop and screw holes no longer share the #30 drill")


def native_size_problem(tag: str, text: str) -> str | None:
    """Why a generated SIZE cell misstates its hole, or None when it is an
    inch rounding of the actual cut (or the wizard's drill number) THRU, or a
    plain cut's blank cell."""
    plain = text.replace("<MOD-DIAM>", _DIAM).replace("\u2300", _DIAM).upper()
    if not plain.strip() and tag in PLAIN_CUT_SIZES:
        return None
    if "THRU" not in plain:
        return "no THRU"
    if re.search(r"\d\s*MM\b", plain):
        return "millimetres on the inch sheet"
    drill = re.search(r"#(\d+)", plain)
    if drill is not None:
        if NATIVE_DRILL_NUMBERS.get(tag) != f"#{drill.group(1)}":
            return f"drill #{drill.group(1)} is not this hole's"
        return None
    size = re.search(r"(?<![\d.])(\d*)\.(\d+)", plain)
    if size is None:
        return "no decimal size"
    places = len(size.group(2))
    if places < 3:
        return f"{places}-place size cannot carry the drilled cut"
    value = float(size.group(0))
    if abs(value - NATIVE_SIZE_CUTS_IN[tag]) > 0.5 * 10.0**-places + 1e-9:
        return f"{size.group(0)} is not the cut {NATIVE_SIZE_CUTS_IN[tag]:.4f}"
    return None


# NOTE: the screw rows' countersink by its symbol (rule 26); the flat head's
# own 82 degrees. A plain cut whose native SIZE is blank prints its design
# size and process here, size first (rule 26).
CSK_TEXT = (
    f"<HOLE-SINK> {_DIAM}{_inch(part_spec.CSK_DIA, part_spec.CSK_PLACES)}"
    f" X {part_spec.CSK_ANGLE:.0f}\u00b0"
)
PLAIN_CUT_SIZES: dict[str, str] = {
    "HUB": f"{_DIAM}{_inch(part_spec.HUB_DIA_PRINTED, part_spec.HUB_PLACES)} DRILL THRU",
    "CL": f"{_DIAM}{_inch(part_spec.CLAMP_DIA, part_spec.CLAMP_PLACES)} DRILL THRU",
    "CR": f"{_DIAM}{_inch(part_spec.CLAMP_DIA, part_spec.CLAMP_PLACES)} DRILL THRU",
}
NOTE_HEADING = "NOTE"


def row_notes(native_sizes: dict[str, str]) -> dict[str, str]:
    """Each row's NOTE cell, given the table's generated SIZE cells."""
    return {
        tag: CSK_TEXT
        if tag.startswith("R")
        else (
            PLAIN_CUT_SIZES[tag]
            if tag in PLAIN_CUT_SIZES and not native_sizes[tag].strip()
            else ""
        )
        for tag in TABLE_HOLES
    }


# MATE: the TL-21 hole each spotted hole is transferred from, the part the
# HUB relief clears, and the pin each stop hole takes (rules 4, 10).
MATE_HEADING = "MATE"
ROW_MATES: dict[str, str] = {
    **{tag: f"{CARRIER_SHORT} {tag}" for tag in SPOTTED if tag != "HUB"},
    "HUB": f"{CARRIER_SHORT} HUB\nCLEARS {STRAP_NUMBER} HUB REAMER",
    # Rule 26: 'LOOSE' is no standard fit name (restack farm r1
    # 20261108T040030048Z); the pin drops through its clearance.
    "P1": f"CLEARS {part_spec.STOP_PIN_NUMBER} STOP PIN",
    "P2": f"CLEARS {part_spec.STOP_PIN_NUMBER} STOP PIN",
}
if set(ROW_MATES) != set(TABLE_HOLES):
    raise AssertionError("every riser table row needs its MATE")
# The table's two notes: the spotted rows' REF locations and their route
# (rule 4 L1: the pattern shows as REF with its transfer named), then the
# origin.
SPOT_NOTE = (
    "R1-R4, HUB, CL, CR: X/Y LOC REF; "
    f"SPOT FROM {CARRIER_SHORT} AT ASSEMBLY"
)
ORIGIN_NOTE = "X/Y LOC FROM THE LOWER-LEFT CORNER"
TABLE_NOTES = (SPOT_NOTE, ORIGIN_NOTE)

# Sheet metres: the table's top-left corner, left under the plan (the
# length's dimension line stands at 0.180, the lower tags' text ends 0.185).
TABLE_ANCHOR = (0.020, 0.172)
# SIZE at 38: SolidWorks holds the native cell to its text, and farm r3
# (20261108T014606685Z, 1850057757) measured "Ø.129 THRU ALL" at 37.4 mm.
TABLE_WIDTHS = (0.012, 0.016, 0.016, 0.038, 0.036, 0.058)
_TABLE_SIZE_COLUMN = 3
_TABLE_NOTE_COLUMN = 4
_TABLE_MATE_COLUMN = 5
# Each note's top 4 mm under the one above (or under the table).
_NOTE_PITCH = 0.008
# The title block (top y 65 mm) starts at x 216 mm; the notes, at x 20 mm,
# end left of it, so below y 68 mm only the border (y 15 mm with air) bounds
# them (farm r4 20261108T022716612Z: an 84 mm table put the notes' bottom
# at 67.8 mm against a 68 mm bound that assumed the title block's height).
_TITLE_BLOCK_TOP = 0.068
_TITLE_BLOCK_LEFT = 0.216
_BORDER_BOTTOM = 0.015
_NOTE_GLYPH = 0.0027
# Tags stand outside the outline (rule 14), each on a leader to its hole,
# model mm: the upper holes' tags 6 mm (sheet) above the top edge, the lower
# ones' 6 mm under the bottom edge; left of the A-A line's upper end (R3)
# and clear of both section letters (12-22 mm sheet right of the line).
TAG_XY_MM: dict[str, tuple[float, float]] = {
    "R3": (38.0, BLANK_WIDTH + 12.0),
    "R1": (143.0, BLANK_WIDTH + 12.0),
    "HUB": (185.0, BLANK_WIDTH + 12.0),
    "R2": (223.0, BLANK_WIDTH + 12.0),
    "R4": (303.0, BLANK_WIDTH + 12.0),
    "P1": (10.0, -12.0),
    "CL": (34.0, -12.0),
    "CR": (BLANK_LENGTH - 34.0, -12.0),
    "P2": (BLANK_LENGTH - 10.0, -12.0),
}
if set(TAG_XY_MM) != set(TABLE_HOLES):
    raise AssertionError("every riser table tag needs a position")
# Hole identity on the view: centre to a micron, diameter to the pinned
# 3-decimal mm rounding (the wizard cuts the exact .1285 inch drill).
_CENTRE_TOLERANCE_MM = 1e-3
_DIAMETER_TOLERANCE_MM = 5e-4
# Inch sheets drop the leading zero (ASME Y14.5): the hole table's document
# option, before the table exists (draw_fr_rocker_arm_support).
HOLE_TABLE_LEADING_ZERO = "swLeadingZero_DoNotShow"


def _limits(model: float, places: int) -> list[float]:
    """A general-band dimension's acceptance limits on the inch sheet: the
    title block's band about the value printed at ``places``."""
    return limits(model, places, unit=_UNIT)


part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        (_DRAW, "TABLE_LOCATION_PLACES"),
        (_DRAW, "native_size_problem"),
    )
)

requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.THICKNESS),),
    requirements=("height", "length", "width"),
    fields={
        "normal": (_UP, ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.THICKNESS},
            ("THICKNESS",),
        ),
        "height": (
            _limits(part_spec.THICKNESS, part_spec.THICKNESS_PLACES),
            ("THICKNESS",),
        ),
        "height_nominal": (part_spec.THICKNESS, ("THICKNESS",)),
        "length": (
            _limits(part_spec.BLANK_LENGTH, part_spec.BLANK_PLACES),
            ("BLANK_LENGTH",),
        ),
        "length_nominal": (part_spec.BLANK_LENGTH, ("BLANK_LENGTH",)),
        "width": (
            _limits(part_spec.BLANK_WIDTH, part_spec.BLANK_PLACES),
            ("BLANK_WIDTH",),
        ),
        "width_nominal": (part_spec.BLANK_WIDTH, ("BLANK_WIDTH",)),
    },
    precision={
        "height": part_spec.THICKNESS_PLACES,
        "length": part_spec.BLANK_PLACES,
        "width": part_spec.BLANK_PLACES,
    },
)

requirement(
    "carrier_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "height": (
            _limits(part_spec.THICKNESS, part_spec.THICKNESS_PLACES),
            ("THICKNESS",),
        ),
    },
    precision={"height": part_spec.THICKNESS_PLACES},
)


_SCREW_SOURCES = ("SCREW_HOLES", "BLANK_ORIGIN", (_CALC, "RISER_SCREWS"))
_SCREW_DIA_SOURCES = (
    "SCREW_DIA_PRINTED",
    "SCREW_DIA",
    "SCREW_SPEC",
    "SCREW_BODY_DIA",
    (_DRAW, "NATIVE_SIZE_CUTS_IN"),
)
# (name, xy, cut dia, printed dia, station sources, dia sources): the wizard
# cuts the unchanged #4 clearance (#30 drill) inside the design Ø.128 +.004/0
# band, and the HUB's literal 12 mm drill lies inside its Ø.472 +.004/0.
_HOLE_ROWS = (
    *(
        (
            f"screw_hole_{i}",
            xy,
            SCREW_DIA,
            SCREW_DIA_PRINTED,
            _SCREW_SOURCES,
            _SCREW_DIA_SOURCES,
        )
        for i, xy in enumerate(SCREW_HOLES, start=1)
    ),
    (
        "hub_hole",
        HUB_HOLE,
        part_spec.HUB_DIA,
        part_spec.HUB_DIA_PRINTED,
        ("HUB_HOLE", "BLANK_ORIGIN", (_CALC, "HUB")),
        (
            "HUB_DIA_PRINTED",
            "HUB_DIA",
            (_DRAW, "NATIVE_SIZE_CUTS_IN"),
            (_DRAW, "PLAIN_CUT_SIZES"),
        ),
    ),
    *(
        (
            name,
            xy,
            part_spec.CLAMP_DIA,
            part_spec.CLAMP_DIA,
            (f"{calc}_HOLE", "BLANK_ORIGIN", (_CALC, calc)),
            ("CLAMP_DIA", (_DRAW, "NATIVE_SIZE_CUTS_IN"), (_DRAW, "PLAIN_CUT_SIZES")),
        )
        for name, xy, calc in (("cl_hole", CL_HOLE, "CL"), ("cr_hole", CR_HOLE, "CR"))
    ),
)
for name, (x, y), cut_dia, dia, sources, dia_sources in _HOLE_ROWS:
    dia_places = DRAWING_PRECISION_BY_NAME[
        {"hub_hole": "HubDia", "cl_hole": "ClampDia", "cr_hole": "ClampDia"}.get(
            name, "ScrewDia"
        )
    ]
    requirement(
        name,
        kind="hole",
        faces=(CylinderFace(cut_dia, contains_x_mm=x),),
        # The location is spotted from the carrier at assembly: the stations
        # are reference values, not banded requirements.
        requirements=("dia", "thru"),
        fields={
            "at": ([x, y, part_spec.THICKNESS], (*sources, "THICKNESS")),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "station_nominal": (x, sources),
            "width_nominal": (y, sources),
            "dia": (
                limits(dia, dia_places, part_spec.DRILLED_BAND),
                (*dia_sources, "DRILLED_BAND"),
            ),
            "dia_nominal": (dia, dia_sources),
            "thru": (True, dia_sources),
        },
        precision={"dia": dia_places},
    )

# The two loose end-stop pin holes are drilled at their ordinary .XX table
# locations from the blank's lower-left corner, not spotted from the
# carrier, so their stations are banded requirements. The wizard cuts the
# actual #30 inside the .128 +.004/0 design band, as the screw holes'.
_STOP_SOURCES = ("STOP_PIN_HOLES", "BLANK_ORIGIN", "STOP_PIN_CARRIER_POINTS")
_STOP_DIA_SOURCES = (
    "STOP_HOLE_DIA",
    "STOP_DIA",
    "STOP_SPEC",
    "STOP_DRILL",
    (_DRAW, "NATIVE_SIZE_CUTS_IN"),
)
for index, (x, y) in enumerate(STOP_PIN_HOLES, start=1):
    dia_places = DRAWING_PRECISION_BY_NAME["StopDia"]
    requirement(
        f"stop_hole_{index}",
        kind="hole",
        faces=(CylinderFace(STOP_DIA, contains_x_mm=x),),
        requirements=("dia", "thru", "station", "height"),
        fields={
            "at": ([x, y, part_spec.THICKNESS], (*_STOP_SOURCES, "THICKNESS")),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "station": (_limits(x, TABLE_LOCATION_PLACES), _STOP_SOURCES),
            "station_nominal": (x, _STOP_SOURCES),
            "height": (_limits(y, TABLE_LOCATION_PLACES), _STOP_SOURCES),
            "height_nominal": (y, _STOP_SOURCES),
            "dia": (
                limits(STOP_HOLE_DIA, dia_places, part_spec.DRILLED_BAND),
                (*_STOP_DIA_SOURCES, "DRILLED_BAND"),
            ),
            "dia_nominal": (STOP_HOLE_DIA, _STOP_DIA_SOURCES),
            "thru": (True, _STOP_DIA_SOURCES),
        },
        precision={
            "dia": dia_places,
            "station": TABLE_LOCATION_PLACES,
            "height": TABLE_LOCATION_PLACES,
        },
    )

for index, (x, _y) in enumerate(SCREW_HOLES, start=1):
    requirement(
        f"screw_hole_{index}_countersink",
        kind="countersink",
        faces=(ConeFace(part_spec.CSK_ANGLE / 2.0, contains_x_mm=x),),
        requirements=("dia", "angle_deg"),
        fields={
            "parent": (
                f"screw_hole_{index}",
                ("SCREW_DIA", (_DRAW, "build")),
            ),
            "dia": (
                _limits(part_spec.CSK_DIA, part_spec.CSK_PLACES),
                ("CSK_DIA", "SCREW_HEAD_DIA_MAX", "CSK_DEPTH_MAX", (_DRAW, "CSK_TEXT")),
            ),
            "dia_nominal": (part_spec.CSK_DIA, ("CSK_DIA",)),
            "angle_deg": (part_spec.CSK_ANGLE, ("CSK_ANGLE", (_DRAW, "CSK_TEXT"))),
            "angle_tol_deg": (
                part_spec.INCLUDED_ANGLE_TOL_DEG,
                ("INCLUDED_ANGLE_TOL_DEG",),
            ),
        },
        precision={"dia": part_spec.CSK_PLACES, "angle_deg": 0},
    )


def _view_mapper(adapter: Any, view: Any):
    """Return model point (mm) -> sheet xy (m) through the view's transform."""
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sheet(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([c / 1000.0 for c in model_mm])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    return to_sheet


def _set_whole_section_line(drawing_model: Any) -> None:
    """Draw A-A's cutting plane as one whole line (owner review, rule 9)."""
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(
        SECTION_LINE_STYLE_PREFERENCE, 0, SECTION_LINE_STYLE
    ):
        raise RuntimeError("failed to set the whole section cutting line")
    if extension.GetUserPreferenceInteger(SECTION_LINE_STYLE_PREFERENCE, 0) != (
        SECTION_LINE_STYLE
    ):
        raise RuntimeError("section cutting-line style did not persist")


def _drop_hole_table_leading_zeros(adapter: Any) -> None:
    """Set the drawing's hole-table leading-zero option before the table exists."""
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    preference = constant("swDetailingLeadingZero")
    option = constant("swDetailingHoleTable")
    value = constant(HOLE_TABLE_LEADING_ZERO)
    if not extension.SetUserPreferenceInteger(preference, option, value):
        raise RuntimeError("failed to drop the riser hole table's leading zeros")
    if int(extension.GetUserPreferenceInteger(preference, option)) != value:
        raise RuntimeError("riser hole-table leading-zero option did not persist")


def _circle_parameters(edge: Any) -> tuple[float, ...] | None:
    curve = _early_bound(_early_bound(edge, "IEdge").GetCurve(), "ICurve")
    if not curve.IsCircle():
        return None
    values = tuple(float(v) for v in curve.CircleParams)
    if len(values) != 7 or not all(math.isfinite(v) for v in values):
        raise RuntimeError("riser table edge has invalid circle parameters")
    return values


def _hole_tag(values: tuple[float, ...]) -> str | None:
    """The one table hole whose centre, Z axis and cut size fit ``values``."""
    cx, cy, _cz, ax, ay, az, radius = values
    if max(abs(ax), abs(ay), abs(abs(az) - 1.0)) > 1e-8:
        return None
    matches = [
        tag
        for tag, ((x, y), diameter) in TABLE_HOLES.items()
        if math.dist((cx * 1000.0, cy * 1000.0), (x, y)) <= _CENTRE_TOLERANCE_MM
        and abs(2000.0 * radius - diameter) <= _DIAMETER_TOLERANCE_MM
    ]
    return matches[0] if len(matches) == 1 else None


def _hole_edges(view: Any) -> dict[str, Any]:
    """Each table hole's highest visible rim on the plan, by tag.

    A screw hole's own rim in the plan is where its #30 bore meets the
    revolved countersink (the wizard's bottom rim is hidden, jig-r4); every
    other hole's is its top-face rim. Circles of another size on the same
    axis (the countersink's mouth) are not hole rims.
    """
    found: dict[str, tuple[float, Any]] = {}
    for component in view.GetVisibleComponents() or ():
        for raw in visible_component_entities(view, component, 1) or ():
            values = _circle_parameters(raw)
            if values is None:
                continue
            tag = _hole_tag(values)
            if tag is None:
                continue
            if tag not in found or values[2] > found[tag][0]:
                found[tag] = (values[2], _early_bound(raw, "IEdge"))
    if set(found) != set(TABLE_HOLES):
        raise RuntimeError(
            f"riser plan is missing hole rims: {sorted(set(TABLE_HOLES) - set(found))}"
        )
    return {tag: edge for tag, (_z, edge) in found.items()}


def _row_holes(table: Any) -> dict[int, str]:
    """Each row's physical hole, from its own generated X/Y LOC cells.

    The nine holes' .XX locations are distinct, so a row identifies exactly
    one hole (within the half unit SolidWorks' rounding may differ by) or the
    table is refused.
    """
    if int(table.RowCount) != len(TABLE_HOLES) + 1:
        raise RuntimeError(f"riser table has {int(table.RowCount)} rows")
    exact = {
        tag: tuple(value / INCH for value in table_location(tag)) for tag in TABLE_HOLES
    }
    half_unit = 0.5 * 10.0**-TABLE_LOCATION_PLACES + 1e-9
    holes: dict[int, str] = {}
    for row in range(1, int(table.RowCount)):
        texts = tuple(
            str(table.DisplayedText2(row, column, False) or "").strip()
            for column in (1, 2)
        )
        if not all(
            re.fullmatch(rf"-?\d*\.\d{{{TABLE_LOCATION_PLACES}}}", text) for text in texts
        ):
            raise RuntimeError(f"riser table row {row} lost its .XX locations: {texts!r}")
        matches = [
            tag
            for tag, location in exact.items()
            if all(
                abs(float(text) - value) <= half_unit
                for text, value in zip(texts, location, strict=True)
            )
        ]
        if len(matches) != 1 or matches[0] in holes.values():
            raise RuntimeError(
                f"riser table row {row} is not exactly one hole from the corner: {texts!r}"
            )
        holes[row] = matches[0]
    return holes


def _hole_tag_reader(feature: Any, current: dict[int, str]) -> int:
    """Measured offset of IHoleTable.HoleTag's index from the table row index."""
    offsets = []
    for offset in (1, 0):
        try:
            if all(
                str(feature.HoleTag(row - offset) or "").strip() == tag
                for row, tag in current.items()
            ):
                offsets.append(offset)
        except Exception:  # an out-of-range probe index is simply not this convention
            continue
    if len(offsets) != 1:
        raise RuntimeError("riser HoleTag does not read back the generated TAG cells")
    return offsets[0]


def _assign_tags(feature: Any, table: Any) -> None:
    """Rename SolidWorks' default A1..A9 tags to the riser tags, collision-free.

    As the TL-21 carrier's: IHoleTable.HoleTag's setter refuses a name another
    row still holds, so every row moves to an unused temporary first, then to
    its tag, each write read back.
    """
    holes = _row_holes(table)
    current = {
        row: str(table.DisplayedText2(row, 0, False) or "").strip() for row in holes
    }
    if len(set(current.values())) != len(current) or not all(current.values()):
        raise RuntimeError(f"riser table generated duplicate or empty tags: {current!r}")
    offset = _hole_tag_reader(feature, current)
    temporary = {row: f"TMP{row}" for row in holes}
    if set(temporary.values()) & (set(current.values()) | set(TABLE_HOLES)):
        raise AssertionError("riser temporary tags collide with a live or final tag")
    feature.EnableUpdate = False
    try:
        for names in (temporary, holes):
            for row, name in names.items():
                feature.SetHoleTag(row - offset, name)
                if str(feature.HoleTag(row - offset) or "").strip() != name:
                    raise RuntimeError(f"riser hole tag {name!r} was not assigned to row {row}")
    finally:
        feature.EnableUpdate = True


def _rows_by_tag(table: Any) -> dict[str, int]:
    """Each tag's CURRENT row: its TAG cell agrees with its own LOC cells."""
    rows: dict[str, int] = {}
    for row, tag in _row_holes(table).items():
        printed = str(table.DisplayedText2(row, 0, False) or "").strip()
        if printed != tag:
            raise RuntimeError(f"riser table row {row} is tagged {printed!r}, not {tag!r}")
        rows[tag] = row
    return rows


def _cell_text(table: Any, row: int, column: int) -> str:
    """A cell's driving text, its line breaks read back as LF."""
    text = str(table.Text2(row, column, False) or "")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _write_cell(table: Any, row: int, column: int, text: str, *, label: str) -> None:
    if not table.IsCellTextEditable(row, column):
        raise RuntimeError(f"riser table {label} cell (row {row}) is not editable")
    table.SetText2(row, column, False, text)  # void put: read back below
    written = _cell_text(table, row, column)
    displayed = str(table.DisplayedText2(row, column, False) or "").strip()
    if written != text or not displayed:
        raise RuntimeError(
            f"riser table {label} (row {row}) did not take: expected={text!r} "
            f"driving={written!r} displayed={displayed!r}"
        )


def _native_sizes(table: Any) -> dict[str, str]:
    """Each tag's generated SIZE cell, refused unless it states its hole."""
    sizes = {
        tag: str(table.DisplayedText2(row, _TABLE_SIZE_COLUMN, False) or "").strip()
        for tag, row in _rows_by_tag(table).items()
    }
    _telemetry.info(f"riser hole-table native SIZE cells: {sizes!r}")
    problems = {
        tag: problem
        for tag, text in sizes.items()
        if (problem := native_size_problem(tag, text)) is not None
    }
    if problems:
        raise RuntimeError(
            f"riser hole-table SIZE cells misstate their holes: {problems!r}; "
            f"cells={sizes!r}"
        )
    return sizes


def _check_rows(table: Any, generated: dict[str, str]) -> None:
    """Every row: its tag, its corner locations, its generated SIZE as first
    read, and its NOTE and MATE."""
    if int(table.ColumnCount) != len(TABLE_WIDTHS):
        raise RuntimeError(
            f"riser table has {int(table.ColumnCount)} columns; "
            "expected TAG/X/Y/SIZE/NOTE/MATE"
        )
    for column, title in (
        (_TABLE_NOTE_COLUMN, NOTE_HEADING),
        (_TABLE_MATE_COLUMN, MATE_HEADING),
    ):
        heading = str(table.DisplayedText2(0, column, False) or "").strip()
        if heading.upper() != title:
            raise RuntimeError(f"riser table column {column} heading reads {heading!r}")
    if _native_sizes(table) != generated:
        raise RuntimeError("riser table's generated SIZE cells changed")
    for tag, row in _rows_by_tag(table).items():
        for column, expected in (
            (_TABLE_NOTE_COLUMN, row_notes(generated)[tag]),
            (_TABLE_MATE_COLUMN, ROW_MATES[tag]),
        ):
            written = _cell_text(table, row, column)
            if written != expected:
                raise RuntimeError(
                    f"riser table {tag} column {column} (row {row}) changed: "
                    f"expected={expected!r} actual={written!r}"
                )


def _tags(
    adapter: Any,
    view: Any,
    edges: dict[str, Any],
    on_plan: Callable[[tuple[float, float, float]], tuple[float, float]],
    *,
    place: bool,
) -> None:
    """Each table tag: one note on the view, on a leader to its own hole."""
    found = {}
    for raw in view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:  # swNote
            continue
        tag = str(_early_bound(annotation.GetSpecificAnnotation(), "INote").GetText()).strip()
        if tag not in edges:
            if re.fullmatch(r"(?:[A-Z]+\d+|HUB|CL|CR)", tag):
                raise RuntimeError(f"orphan native riser hole tag: {tag}")
            continue
        if tag in found:
            raise RuntimeError(f"duplicate native riser hole tag: {tag}")
        found[tag] = annotation
        attached = tuple(annotation.GetAttachedEntities3() or ())
        if (
            len(attached) != 1
            or attached[0] is None
            or int(adapter.swApp.IsSame(attached[0], edges[tag])) != 1
            or annotation.IsDangling()
        ):
            raise RuntimeError(f"riser tag {tag} is not attached to its physical hole")
        if place:
            if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
                raise RuntimeError(f"riser tag {tag} leader rejected")
            x, y = TAG_XY_MM[tag]
            if not annotation.SetPosition2(*on_plan((x, y, _T)), 0.0):
                raise RuntimeError(f"riser tag {tag} position rejected")
        if int(annotation.Visible) != 1 or int(annotation.GetLeaderCount()) != 1:
            raise RuntimeError(f"riser tag {tag} is hidden or lacks one leader")
    if set(found) != set(edges):
        raise RuntimeError(f"riser plan is missing table tags: {set(edges) - set(found)}")


def _table_size(table: Any) -> tuple[float, float]:
    width = sum(float(table.GetColumnWidth(col)) for col in range(int(table.ColumnCount)))
    height = sum(float(table.GetRowHeight(row)) for row in range(int(table.RowCount)))
    return width, height


@_telemetry.traced("drawing.riser_hole_table.create")
def _hole_table(
    adapter: Any,
    plan: Any,
    on_plan: Callable[[tuple[float, float, float]], tuple[float, float]],
) -> Callable[[], None]:
    """The native table from the blank's lower-left corner, its NOTE and MATE
    columns, tags and notes; returns its settled readback. Generated cells
    are only read, never written."""
    plan = _early_bound(plan, "IView")
    edges = _hole_edges(plan)
    _drop_hole_table_leading_zeros(adapter)
    order = sorted(TABLE_HOLES, key=table_location)
    table = insert_hole_table(
        adapter,
        plan,
        # The corner vertex an edge finder picks up (rule 10), not a hole
        # centre or a constructed point.
        datum_xy=on_plan((0.0, 0.0, _T)),
        hole_points=[
            on_plan((x + diameter / 2.0, y, _T))
            for (x, y), diameter in (TABLE_HOLES[tag] for tag in order)
        ],
        hole_entities=[edges[tag] for tag in order],
        anchor_xy=TABLE_ANCHOR,
        basic_locations=False,
        label="riser corner baseline",
        unit=_UNIT,
        location_places=TABLE_LOCATION_PLACES,
    )
    feature = _early_bound(
        _early_bound(table, "IHoleTableAnnotation").HoleTable, "IHoleTable"
    )
    origin = _early_bound(feature.DatumOrigin, "IDatumOrigin")
    _assign_tags(feature, table)
    rebuild_drawing(adapter, label="riser table tags")
    generated = _native_sizes(table)
    # Custom columns after SIZE (swTableItemInsertPosition_After): NOTE, then
    # MATE after NOTE.
    for after, column, title in (
        (_TABLE_SIZE_COLUMN, _TABLE_NOTE_COLUMN, NOTE_HEADING),
        (_TABLE_NOTE_COLUMN, _TABLE_MATE_COLUMN, MATE_HEADING),
    ):
        if not table.InsertColumn2(3, after, title, 0):
            raise RuntimeError(f"riser table refused the {title} column")
        if not table.SetColumnTitle2(column, title, False):
            raise RuntimeError(f"riser table refused the {title} title")
        rebuild_drawing(adapter, label=f"riser table {title} column")
    # A regenerated table may reorder its rows: each cell is written to its
    # tag's CURRENT row; the generated columns are only read.
    notes = row_notes(generated)
    for tag, row in _rows_by_tag(table).items():
        if notes[tag]:
            _write_cell(table, row, _TABLE_NOTE_COLUMN, notes[tag], label=f"{tag} NOTE")
        _write_cell(table, row, _TABLE_MATE_COLUMN, ROW_MATES[tag], label=f"{tag} MATE")
    for column, width in enumerate(TABLE_WIDTHS):
        actual = float(table.SetColumnWidth(column, width, 0))
        if abs(actual - width) > 1e-6:
            raise RuntimeError(
                f"riser table column {column} rejected its width: "
                f"expected={width} actual={actual}"
            )
    rebuild_drawing(adapter, label="riser table cells")
    _check_rows(table, generated)
    _tags(adapter, plan, edges, on_plan, place=True)
    _width, height = _table_size(table)
    note_y = TABLE_ANCHOR[1] - height - 0.004
    for index, text in enumerate(TABLE_NOTES):
        if add_note(adapter, text, TABLE_ANCHOR[0], note_y - index * _NOTE_PITCH) is None:
            raise RuntimeError(f"failed to add the riser table note {text!r}")
    rebuild_drawing(adapter, label="riser table and tags")

    def settled() -> None:
        current = _hole_edges(plan)
        if (
            feature.CombineSameSize
            or feature.CombineTags
            or bool(feature.GetHoleLocationUseDocPrecision())
            or int(feature.GetHoleLocationPrecision()) != TABLE_LOCATION_PLACES
        ):
            raise RuntimeError("riser table lost its individual .XX rows")
        annotation = _early_bound(origin.GetAnnotation(), "IAnnotation")
        attached = tuple(annotation.GetAttachedEntities3() or ())
        if (
            len(attached) != 1
            or attached[0] is None
            or any(
                int(adapter.swApp.IsSame(attached[0], edge)) == 1
                for edge in current.values()
            )
            or annotation.IsDangling()
        ):
            raise RuntimeError("riser table datum left its corner vertex")
        _check_rows(table, generated)
        _tags(adapter, plan, current, on_plan, place=False)
        width, table_height = _table_size(table)
        notes_bottom = (
            TABLE_ANCHOR[1] - table_height - 0.004 - len(TABLE_NOTES) * _NOTE_PITCH
        )
        notes_right = TABLE_ANCHOR[0] + max(map(len, TABLE_NOTES)) * _NOTE_GLYPH
        if (
            notes_bottom < _BORDER_BOTTOM
            or (notes_bottom < _TITLE_BLOCK_TOP and notes_right > _TITLE_BLOCK_LEFT)
            or TABLE_ANCHOR[0] + width > ISO_NOTE_XY[0]
        ):
            raise RuntimeError(
                f"riser table ({width:.4f} x {table_height:.4f} m) and its notes "
                "crowd the isometric, the title block or the border"
            )

    settled()
    return settled


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open riser source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    # Three document places: the native hole table's SIZE cells print at the
    # document precision (farm r2 at 6dc18abb3d: '.13', '.20' at two), as
    # draw_fr_rocker_arm_support does; the LOC columns keep their own .XX.
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        decimals=3,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Riser Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel riser; 6061 blank; MHA-CH-06-TL-24",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    _set_whole_section_line(drawing_model)

    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    on_plan = _view_mapper(adapter, plan)
    section = create_section_view(
        adapter,
        plan,
        line_start=on_plan((CUT_X, CUT_Y[0], _T)),
        line_end=on_plan((CUT_X, CUT_Y[1], _T)),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="riser screw-hole section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="riser")
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (plan, section):
        set_hidden_lines_removed(adapter, view)

    on_section = _view_mapper(adapter, section)
    annotations = [
        *curate_view_dimensions(
            adapter,
            plan,
            keep={name: on_plan(xyz) for name, xyz in PLAN_KEEP.items()},
            view_label="plan view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            section,
            keep={name: on_section(xyz) for name, xyz in SECTION_KEEP.items()},
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    assert_imported_precision(adapter, annotations, IMPORTED_PRECISION)
    table_settled = _hole_table(adapter, plan, on_plan)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Riser Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(table_settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
