r"""Create the drawing for the oblique-trammel jig's carrier plate (MHA-CH-06-TL-21).

The carrier uses one native hole table (#2151, owner Option B), with tags on
actual hole edges and X/Y from the actual A1 bore axis, +X along A1-B1, at
.XXX under the title block. Only A2/B2 Y carries the flagged .964 ±.002
note. The table's SIZE column is hidden: every size is its sheet-1 callout.
The HUB is not in the table: that ordinary #8-32 tap is drilled and tapped
at assembly (MHA-CH-06-TL-00 step 10). No chained hole-location dimensions
remain.

The CARRIER sheet keeps the outline, the reamed size, the native tap
callouts and section A-A (3:1, cropped to and identified as A1, carrying the
finished thickness and underside chamfer); the shaded isometric stands above
the title block. The HOLE TABLE sheet holds the twelve-row table and its
tagged plan. The HUB CLAMP sheet carries the HUB tap's native callout, which
says it is drilled and tapped at assembly, and its position from A1 as two
parenthesized REFERENCE dimensions.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any, Callable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    curate_dimensions,
    dimension_name,
    place_view,
    view_name,
    visible_component_entities,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    rebuild_drawing,
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_detail_projection import settle_detail_projection
import _drawing_hidden_sketches as hidden_sketches
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_hole_callout import add_native_hole_callout
from ch_rocker_arm_tl_oblique_callouts import (
    CALLOUT_PLACES,
    set_callout_lengths_to_three_places,
)
from _drawing_notes import add_note, add_property_linked_note
from _oblique_carrier_hole_table import create_carrier_hole_table
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_carrier_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _part_properties import part_drawing_unit
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_oblique_carrier_spec import (
    CALLOUT_PREFIXES,
    CALLOUTS_BELOW,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    TABLE_LOCATION_PLACES,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_carrier"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 520 x 130 x 12 plate: 1:2 puts the top view at 260 x 65 across the sheet
# (B landscape: border 12.7..419.1 x 12.7..266.7, title block x >= 216 and
# y <= 65). The outline lands on sheet x 92..352, y 152.5..217.5.
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
ISO_SCALE = part_spec.ISOMETRIC_VIEW_SCALE
TOP_CENTER = (0.222, 0.185)
# The HUB clamp tap is drilled and tapped at assembly, so it is not in the
# table; its own sheet carries its callout, which says so, and its reference
# position. The table and its tags take a sheet of their own.
SHEET_NAMES = ("CARRIER", "HOLE TABLE", "HUB CLAMP")
# The iso (~58 x 34 mm at 1:8) right of section A-A and its note under it,
# both above the title block (jig-r3: the note ran into it).
ISO_CENTER = (0.386, 0.103)
ISO_NOTE_XY = (0.356, 0.082)


def _xy(x: float, y: float) -> tuple[float, float, float]:
    """Carrier (X, Y) on the top face as model mm (model Z = -carrier Y)."""
    return (x, 0.0, -y)


_A1 = part_spec.PIN_HOLES["A1"]
# Every text position is a MODEL point (mm), mapped onto its view at run time
# (1:2: sheet x = 222 + X/2, y = 175 + Y/2). Only outline and native size
# controls remain; the table owns all locations. The left end's 34.9 from A1
# stands between the end and A1, under the REAM leader's reach, its arrows
# held inside so its line stops at the end (_arrows_inside).
_NEAR_Y_LANE_X = -350.0  # PlateNearY's dimension line, model X
TOP_KEEP: dict[str, tuple[float, float, float]] = {
    "PlateLength": _xy(56.0, -194.4),
    "PlateWidth": _xy(279.0, -8.0),
    "PlateNearY": _xy(_NEAR_Y_LANE_X, -24.0),
    "EdgeX": _xy(-242.5, -120.4),
    # B9e4's complete native/PDF glyph block reaches y 164.57: the whole block
    # stands 16 sheet mm lower, its mate wrapped to two rows (x ~21..84).
    "PinHoleDia": _xy(-339.0, -106.3),
}
# Machinist review 43452045 (r1/r3 clarity): the 1.77's upper extension line
# runs from the sketch origin (X 0, sheet x 221) on the pin line, so it ran
# through A1 and across the plate to end mid-air (A-A's end stubs are the
# thick ones). Main's ruling: it stops outside the part, a normal 1.5 sheet mm
# gap short of the plate's -X end. Capped (STOCK_WITNESS_MAX_M's
# MaxWitnessLineLength, the whole line from its overshoot), it runs from its
# 1 mm overshoot past the dimension line (43452045's two lines, both to
# x 46.0) to that gap; the lower one (from 1 mm off the same end) loses 0.5.
NEAR_Y_WITNESS_GAP_MM = 1.5
_WITNESS_OVERSHOOT_MM = 1.0
NEAR_Y_WITNESS_MAX_M = (
    (part_spec.OUTLINE_X[0] - _NEAR_Y_LANE_X) * VIEW_SCALE[0] / VIEW_SCALE[1]
    - NEAR_Y_WITNESS_GAP_MM
    + _WITNESS_OVERSHOOT_MM
) / 1000.0

# Section A-A along the pin line (model Z = 0), at 3:1, +Y up, its cut
# direction SolidWorks' own, cropped to A1's slab. It is a FULL section: the
# carrier-diag farm probe (run 20261017T063649278Z) measured that the PARTIAL
# section through a short interior line imports nothing at all (no marked
# dimension even from the entire model; selected SectionReference or Plate
# through the base view: an empty array), while a full section through the
# same line, same selection, imports PinChamferSize and StockThick. A full
# section's line must still cross the part: through that 18 mm interior line
# carrier r11 printed the slab uncut (unhatched, no bore), its stock
# extension lines ~800 mm long over the iso and the title block
# (_drawing_sections.create_section_view: a short line does not close the
# cut). So the line runs past both plate ends: its right end (sheet x 415)
# beyond the right lanes, its left (x 51) between the two outer left lanes.
# A full section at 3:1 is 1.6 m wide, so a Crop2 fence keeps the cut's own
# span (fr_nameplate's _crop_section). The finished thickness is the native
# SectionReference StockThick dimension (driven from Plate's depth). Its dimensions
# are imported BEFORE the crop: cropped (jig-r9, c4-r4), the same import
# delivered PinChamferSize but not StockThick, whose stock line stands 0.5 mm
# inside the fence's +X end and whose sketch text stands 5 mm past it.
# Already imported, they are placed again once the cropped view is centred.
# Carrier r11 and r13 printed the 12.0's extension lines from ~863 mm right
# of the slab (over the title block, past the border) wherever the view and
# its text stood, so the thickness text stands on A1's -X side and its
# extension lines are capped (STOCK_WITNESS_MAX_M, draw_dt_pinion_cam's
# _limit_witness_lines) to run from its dimension line to just short of the
# slab's -X end: from that side an origin anywhere at A1's +X side, the far
# one or the true stock line, leaves the same short pair.
SECTION_SCALE = (3, 1)
_SECTION_HALF = part_spec.SECTION_HALF_SPAN  # about A1's axis, model mm
_SECTION_LINE_X = (386.0, -342.0)  # carrier X, +X end first
SECTION_LINE_MODEL_MM = tuple((x, 0.0, 0.0) for x in _SECTION_LINE_X)
# The crop fence's corners, model mm on the cut plane: the cut's span, the
# stock's thickness and 1 mm above and below it.
SECTION_CROP_MODEL_MM = (
    (_A1[0] - _SECTION_HALF, -part_spec.THICKNESS - 1.0, 0.0),
    (_A1[0] + _SECTION_HALF, 1.0, 0.0),
)
# Machinist review mr4: the cropped slab's square hatch ends read as the
# part's own ends. A long-break line (thin, one Z: draw_fr_nameplate's
# SECTION_BREAK) stands on each crop edge across the cut, past the top and
# bottom faces by _SECTION_BREAK_OVERRUN (inside the fence's 1 mm), its Z at
# mid-thickness, one tip each side of the edge (model mm on the cut plane).
# At -X the thickness's witness lines stop 1.5 sheet mm short of it.
_SECTION_BREAK_OVERRUN = 0.6
_SECTION_BREAK_MID = -part_spec.THICKNESS / 2.0
SECTION_BREAKS = tuple(
    tuple(
        (x + dx, y, 0.0)
        for dx, y in (
            (0.0, _SECTION_BREAK_OVERRUN),
            (0.0, _SECTION_BREAK_MID + 1.5),
            (1.0, _SECTION_BREAK_MID + 0.75),
            (-1.0, _SECTION_BREAK_MID - 0.75),
            (0.0, _SECTION_BREAK_MID - 1.5),
            (0.0, -part_spec.THICKNESS - _SECTION_BREAK_OVERRUN),
        )
    )
    for x in (_A1[0] - _SECTION_HALF, _A1[0] + _SECTION_HALF)
)
_SECTION_ANCHOR_MM = (_A1[0], -part_spec.THICKNESS / 2.0, 0.0)
# Carrier r13 (4:1) squeezed the slab between the 260.0/520.0 lanes and the
# border, its caption cut off from it by the 520.0's extension line and the
# chamfer text against the border. At 3:1 the band under the bottom lanes
# (75) holds, left to right: the caption (x ~20..66), the thickness text
# (lane x 79) and the slab (91..145 x 34..70), the chamfer text under it.
SECTION_CENTER = (0.118, 0.052)
_STOCK_TEXT_DX = 13.0  # A1's axis to the thickness lane, model mm (-X side)
SECTION_KEEP_MODEL_MM: dict[str, tuple[float, float, float]] = {
    "StockThick": (_A1[0] - _STOCK_TEXT_DX, -part_spec.THICKNESS / 2.0, 0.0),
    # The chamfer leg's dimension line: 1 mm under the -X chamfer.
    "PinChamferSize": (_A1[0] - part_spec.PIN_HOLE_DIA / 2.0, -part_spec.THICKNESS - 1.0, 0.0),
}
# Machinist review (3 runs FIX): with its text beside the slab, the chamfer's
# dimension line ran back along the underside as the text's shelf. The text
# now hangs under the slab, A1's +X side (sheet ~121..178 x 16.5..30.5,
# its underline 3.8 mm over the inner border: review at bccedc541), on a
# short angled OffsetText leader from that line (the text centres on it).
SECTION_CHAMFER_TEXT_MODEL_MM = (_A1[0] + 10.5, -part_spec.THICKNESS - 3.5, 0.0)
# The thickness's extension lines from its lane (4 model mm, 12 sheet mm,
# outside the slab's -X end) stop 1.5 sheet mm short of the slab: sheet m.
STOCK_WITNESS_MAX_M = (
    (_STOCK_TEXT_DX - _SECTION_HALF) * SECTION_SCALE[0] / SECTION_SCALE[1] - 1.5
) / 1000.0
# The imported-precision contract is the DRAWING_DIMENSIONS this sheet imports
# (TOP_KEEP and SECTION_KEEP_MODEL_MM). The hidden PinHoleProfile, tap and
# StationReference drivers keep their part-authored .XXX on the model (the
# part build applies all of DRAWING_PRECISION), but #2151 Option B prints
# their locations as the native hole table's .XXX rows from A1
# (IHoleTable.GetHoleLocationPrecision, read back by the table's settled
# check) and A2/B2 Y as OUTER_Y_NOTE; no dimension of theirs reaches a sheet.
# The HUB's only printed position is HUB CLAMP's two drawing-native
# parenthesized references, not an imported driver.
IMPORTED_PRECISION: dict[str, int] = {
    name: DRAWING_PRECISION_BY_NAME[name]
    for names in DRAWING_DIMENSIONS.values()
    for name in sorted(names)
}
# Top centre of the caption: left of the thickness text, level with the slab.
SECTION_CAPTION_XY = (0.043, 0.052)
# Machinist review 43452045 (r2/r3 clarity): at (20, 83) the A1-only note
# stood apart from A-A and the 20.5's left extension line (x 91.8) struck its
# "NOT". Its top-left now stands directly under the caption (whose glyphs end
# at y 37.3), its two rows (the old row's 94.7 mm over 35 characters: ~51.5
# mm) inside the clear slot x 14..75, y 14..35 (R4NativeEye, 43452045 PDF):
# clear of the thickness lane (x >= 78), the slab and the bottom border.
SECTION_NOTE = "A1 ONLY — OTHER PIN\nHOLES NOT SHOWN"
SECTION_NOTE_XY = (0.020, 0.0335)

# Sheet metres: each callout block's centre; its leader lands on the near end
# of the first line. CR up-right into the margin right of the plate, its
# four rows (the native two and END_CLAMP_TAP_CALLOUT's two, mr4) ~219..241;
# CL up-right into the free band over the +Y edge, its four rows ~220..242
# (x ~215..265), left of the riser leader; the risers from the outermost +X
# screw straight up, their four rows (the native two and RISER_TAP_CALLOUT's
# two) ~238..258, under the border; the feed lever (the -Y hole) down-left,
# its three rows (with LEVER_TAP_CALLOUT) under the plate.
CR_CALLOUT_XY = (0.377, 0.230)
CL_CALLOUT_XY = (0.240, 0.231)
# The riser callout 2 mm right of jig-r10's 0.310: its leader from riser
# screw 4 then passes clear right of the CL callout.
RISER_CALLOUT_XY = (0.312, 0.248)
# The lever callout 2.5 mm right of 0.179 (round 8): its bottom row and
# shoulder stand at sheet x ~147..218, under the plate.
LEVER_CALLOUT_XY = (0.1815, 0.143)
# The HUB CLAMP sheet: the HUB tap's callout up-right of it, above the plate
# (sheet x ~237..291, y ~225..247), its leader from the tap (sheet ~222, 198).
HUB_CALLOUT_XY = (0.264, 0.236)
# The HUB tap is drilled and tapped at assembly (TL-00 step 10; farm 82129
# machinist review): its callout says so, and its position from A1 prints
# only as two parenthesized REFERENCE dimensions between the actual A1 and
# HUB edges. Keep both text and dimension lines outside the plate (rule 14):
# X is 18 paper mm below its lower edge, Y is 28 paper mm past its right edge.
# At 1:2 the plate is x 91.825..352.175, y 152.615..217.385 paper mm;
# X's anchor is (165.75, 134.615), Y's (380.175, 186.094). These lanes
# clear the callout/instructions above and the isometric/caption below.
# Only placement changes: the native witnesses still attach to A1 and HUB.
HUB_TAP_NOTE = "DRILL AND TAP AT ASSEMBLY\nTL-00 STEP 10"
# No SetPrecision3: a sheet may only pass a *_spec DRAWING_REFERENCE_PRECISION
# (_drawing_contract), and the part spec is not edited for this drawing-only
# change, so the references print at the document's own linear places.
HUB_REFERENCE_TEXT_MODEL_MM = {
    "X": _xy(-112.5, part_spec.OUTLINE_Y[0] - 36.0),
    "Y": _xy(part_spec.OUTLINE_X[1] + 56.0, 22.0),
}

part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        "TABLE_LOCATION_PLACES",
        ("_oblique_carrier_hole_table", "create_carrier_hole_table"),
        ("_drawing_hole_callout", "add_native_hole_callout"),
        ("ch_rocker_arm_tl_oblique_callouts", "set_callout_lengths_to_three_places"),
    )
)

_UNIT = part_spec.UNIT
_CALLOUT_PLACES = CALLOUT_PLACES  # every Hole Wizard length prints .XXX
_DRILLED = part_spec.DRILLED_BAND


def _limits(model: float, places: int) -> list[float]:
    """A general-band dimension's acceptance limits on the inch sheet: the
    title block's band about the value printed at ``places``."""
    return limits(model, places, unit=_UNIT)


def _printed(model: float, places: int) -> float:
    """The millimetres of ``model`` printed at ``places`` inch decimals."""
    return round(round(model / 25.4, places) * 25.4, 9)


requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), 0.0),),
    requirements=("length", "width"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "length": (_limits(part_spec.PLATE_LENGTH, 1), ("PLATE_LENGTH", "OUTLINE_X")),
        "length_nominal": (part_spec.PLATE_LENGTH, ("PLATE_LENGTH",)),
        "width": (_limits(part_spec.PLATE_WIDTH, 1), ("PLATE_WIDTH", "OUTLINE_Y")),
        "width_nominal": (part_spec.PLATE_WIDTH, ("PLATE_WIDTH",)),
    },
    precision={"length": 1, "width": 1},
)

requirement(
    "bottom_face",
    kind="face",
    # PlanarFace.offset_mm is n·p: the underside (y = -T) along -Y is +T.
    faces=(PlanarFace((0.0, -1.0, 0.0), part_spec.THICKNESS),),
    requirements=("height",),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": -part_spec.THICKNESS},
            ("THICKNESS",),
        ),
        "height": (
            _limits(part_spec.THICKNESS, part_spec.THICKNESS_PLACES), ("THICKNESS",)
        ),
        "height_nominal": (part_spec.THICKNESS, ("THICKNESS",)),
    },
    precision={"height": part_spec.THICKNESS_PLACES},
)

# Native table baselines: A1 is the origin, B1 defines +X and the Y=0 line.
# Every location is .XXX at the title block; A2/B2 Y carries the flagged
# .964 ±.002 local control from the A1-B1 axis line (RV-02).
_DIA_PLACES = part_spec.DRAWING_PRECISION_BY_NAME["PinHoleDia"]
_STATION_PLACES = part_spec.TABLE_LOCATION_PLACES


def _from_a1(x: float, places: int) -> float:
    """A hole's printed X: its table baseline from A1's axis."""
    return _printed(x - _A1[0], places)


_CHAIN: dict[str, dict[str, tuple[Any, tuple[Any, ...]]]] = {"A1": {}}
for _key in ("B1", "A2", "B2"):
    _x, _y = part_spec.PIN_HOLES[_key]
    _CHAIN[_key] = {
        "station": (
            _limits(_x - _A1[0], _STATION_PLACES),
            ("PIN_HOLES", "TABLE_LOCATION_PLACES"),
        ),
        "station_nominal": (_from_a1(_x, _STATION_PLACES), ("PIN_HOLES",)),
        "parent": ("pin_hole_a1", ("PIN_HOLES",)),
    }
    if _key != "B1":
        _CHAIN[_key].update({
            "height": (
                limits(part_spec.OUTER_Y_NOMINAL, _STATION_PLACES,
                       (part_spec.OUTER_Y_BAND, -part_spec.OUTER_Y_BAND)),
                ("OUTER_Y_NOMINAL", "OUTER_Y_BAND", "OUTER_Y_NOTE"),
            ),
            "height_nominal": (part_spec.OUTER_Y_NOMINAL, ("OUTER_Y_NOMINAL",)),
            "height_from": ("pin_hole_a1", ("PIN_HOLES",)),
        })

for _key, (_x, _y) in part_spec.PIN_HOLES.items():
    _chain = _CHAIN[_key]
    requirement(
        f"pin_hole_{_key.lower()}",
        kind="hole",
        faces=(
            CylinderFace(part_spec.PIN_HOLE_DIA, contains_x_mm=_x, contains_z_mm=-_y),
        ),
        requirements=(
            "dia",
            "thru",
            "note",
            *(name for name in ("station", "height") if name in _chain),
        ),
        fields={
            "at": ([_x, 0.0, -_y], ("PIN_HOLES",)),
            "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "dia": (
                limits(part_spec.PIN_HOLE_DIA, _DIA_PLACES, part_spec.PIN_HOLE_BAND),
                ("PIN_HOLE_DIA", "PIN_HOLE_BAND"),
            ),
            "dia_nominal": (part_spec.PIN_HOLE_DIA, ("PIN_HOLE_DIA",)),
            "thru": (True, ("PIN_HOLE_CALLOUT",)),
            "note": (
                " ".join(part_spec.CALLOUTS_BELOW["PinHoleDia"].splitlines()),
                ("CALLOUTS_BELOW", "PIN_HOLE_CALLOUT", "PIN_NUMBER"),
            ),
            **_chain,
        },
        precision={
            "dia": _DIA_PLACES,
            **{
                name: _STATION_PLACES
                for name in ("station", "height")
                if name in _chain
            },
        },
    )

# (stem, points, thread, tap drill, spec name, station places, height places)
_TAPS = (
    *(
        (
            f"{_key.lower()}_tap",
            (_point,),
            part_spec.CLAMP_THREAD,
            part_spec.CLAMP_TAP_DRILL,
            "CLAMP_SPEC",
            _STATION_PLACES,
            _STATION_PLACES,
        )
        for _key, _point in part_spec.END_CLAMPS.items()
    ),
    (
        "riser_tap",
        part_spec.RISER_SCREWS,
        part_spec.RISER_THREAD,
        part_spec.RISER_TAP_DRILL,
        "RISER_SPEC",
        part_spec.RISER_STATION_PLACES,
        part_spec.RISER_STATION_PLACES,
    ),
    (
        # On the tap axis, X 8.861 from A1 in the table.
        "lever_tap",
        part_spec.LEVER_HOLES,
        part_spec.LEVER_THREAD,
        part_spec.LEVER_TAP_DRILL,
        "LEVER_SPEC",
        _STATION_PLACES,
        _STATION_PLACES,
    ),
)


def _tap_fields(
    x: float, y: float, thread: str, drill: float, spec_name: str
) -> dict[str, tuple[Any, tuple[Any, ...]]]:
    """The native Hole Wizard callout's own content: thread, tap drill, THRU."""
    drill_printed = _printed(drill, _CALLOUT_PLACES)
    return {
        "at": ([x, 0.0, -y], (spec_name,)),
        "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
        "thread": (f"{thread} UNC-2B", (spec_name,)),
        "tap_drill_mm": (drill, (spec_name,)),
        "dia": (
            limits(drill_printed, _CALLOUT_PLACES, _DRILLED),
            (spec_name, "DRILLED_BAND"),
        ),
        "dia_nominal": (drill_printed, (spec_name,)),
        "thru": (True, (spec_name,)),
    }


for _stem, _points, _thread, _drill, _spec_name, _places, _y_places in _TAPS:
    for _index, (_x, _y) in enumerate(_points, start=1):
        requirement(
            f"{_stem}_{_index}",
            kind="hole",
            faces=(CylinderFace(_drill, contains_x_mm=_x, contains_z_mm=-_y),),
            requirements=("thread", "dia", "station", "height", "thru"),
            fields={
                **_tap_fields(_x, _y, _thread, _drill, _spec_name),
                "station": (_limits(_x - _A1[0], _places), (_spec_name, "PIN_HOLES")),
                "station_nominal": (_from_a1(_x, _places), (_spec_name, "PIN_HOLES")),
                "parent": ("pin_hole_a1", ("PIN_HOLES",)),
                "height": (_limits(_y, _y_places), (_spec_name,)),
                "height_nominal": (_printed(_y, _y_places), (_spec_name,)),
            },
            precision={"dia": _CALLOUT_PLACES, "station": _places, "height": _y_places},
        )

# The HUB clamp tap is drilled and tapped at assembly: no controlled station
# (its sheet's two dimensions are parenthesized REFERENCE), its callout says so.
requirement(
    "hub_tap_1",
    kind="hole",
    faces=(
        CylinderFace(
            part_spec.CLAMP_TAP_DRILL,
            contains_x_mm=part_spec.HUB[0],
            contains_z_mm=-part_spec.HUB[1],
        ),
    ),
    requirements=("thread", "dia", "thru", "note"),
    fields={
        **_tap_fields(
            *part_spec.HUB, part_spec.HUB_THREAD, part_spec.CLAMP_TAP_DRILL, "HUB_SPEC"
        ),
        "note": (
            " ".join(HUB_TAP_NOTE.splitlines()),
            (("draw_ch_rocker_arm_tl_oblique_carrier", "HUB_TAP_NOTE"),),
        ),
    },
    precision={"dia": _CALLOUT_PLACES},
)


# Copied from _trammel_block_drawing (the old trammel kit is being retired;
# the new jig must not import it).
def _circle_edge(
    adapter: Any,
    view: Any,
    diameter_mm: float,
    label: str,
    *,
    center_x_mm: float | None = None,
    center_y_mm: float | None = None,
) -> Any:
    """The first visible circular edge of ``diameter_mm`` in ``view``.

    ``center_x_mm`` / ``center_y_mm`` (carrier X / Y; model Z = -Y) pick one
    of several equal holes, as draw_dt_cone_pivot_post's ``_circular_edge``
    does: without them SolidWorks' enumeration order chooses, and a leader
    routed for one hole can cross another callout to reach the other.
    """
    radius_m = diameter_mm / 2000.0
    for component in (
        adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    ):
        for raw in visible_component_entities(view, component, 1) or ():
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = curve.CircleParams
            if abs(float(params[6]) - radius_m) > 1e-6:
                continue
            if (
                center_x_mm is not None
                and abs(float(params[0]) * 1000.0 - center_x_mm) > 0.05
            ):
                continue
            if (
                center_y_mm is not None
                and abs(-float(params[2]) * 1000.0 - center_y_mm) > 0.05
            ):
                continue
            return edge
    raise RuntimeError(f"carrier view shows no {label}")




def _assert_ream_control(adapter: Any, annotation: Any) -> None:
    """The complete acceptance must remain on the real banded bore dimension."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = _early_bound(dimension.GetFeatureOwner(), "IFeature")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if (
        str(owner.Name) != "PinHoleProfile"
        or str(dimension.FullName).split("@")[:2] != ["PinHoleDia", "PinHoleProfile"]
        or int(display.Type2) != 6  # swDiameterDimension
        or not math.isclose(
            float(dimension.SystemValue), part_spec.PIN_HOLE_DIA / 1000.0,
            abs_tol=1e-12, rel_tol=0.0,
        )
        or not math.isclose(
            float(tolerance.GetMinValue()), part_spec.PIN_HOLE_BAND[1] / 1000.0,
            abs_tol=1e-12, rel_tol=0.0,
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), part_spec.PIN_HOLE_BAND[0] / 1000.0,
            abs_tol=1e-12, rel_tol=0.0,
        )
        or not display.ShowDimensionValue
        or int(annotation.Visible) != 1
        or annotation.IsDangling()
        or str(display.GetText(8) or "") != CALLOUTS_BELOW["PinHoleDia"]
        or str(display.GetText(4) or "") != CALLOUTS_BELOW["PinHoleDia"]
    ):
        raise RuntimeError("4X REAM lost its native bore size or shoulder-screw fit")




_THREAD_LABEL_LAYER = "OBLIQUE-CARRIER-THREAD-LABEL-HIDDEN"


def _hide_thread_labels(adapter: Any, view: Any) -> int:
    """Hide a view's cosmetic-thread labels; the hole callouts already state
    every thread (draw_dt_cone_tip_block's hidden-layer recipe, as in
    draw_ch_rocker_arm_tl_inspection_box)."""
    manager = _early_bound(adapter.currentModel.GetLayerManager(), "ILayerMgr")
    if (
        manager.GetLayer(_THREAD_LABEL_LAYER) is None
        and int(
            manager.AddLayer(_THREAD_LABEL_LAYER, "duplicate thread labels", 0, 0, 0)
        )
        != 1
    ):
        raise RuntimeError("failed to add the carrier thread-label layer")
    layer = _early_bound(manager.GetLayer(_THREAD_LABEL_LAYER), "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("carrier thread-label layer is not hidden")
    hidden = 0
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        kind = int(annotation.GetType())
        # swCosmeticThread, or the thread's own "Tapped Hole" label note.
        if kind != 1 and not (
            kind == 6
            and "Tapped Hole"
            in str(
                _early_bound(annotation.GetSpecificAnnotation(), "INote").GetText()
                or ""
            )
        ):
            continue
        annotation.Layer = _THREAD_LABEL_LAYER
        if str(annotation.Layer or "") != _THREAD_LABEL_LAYER:
            raise RuntimeError("carrier cosmetic thread refused the hidden layer")
        hidden += 1
    rebuild_drawing(adapter, label="hide carrier thread labels")
    return hidden


# draw_pd_transgear_arm's tap_callout_definitions: the title block's
# "THREADS UNC/UNF CLASS 2A/2B" already states the class.
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)


def _thread_class_free_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Drop the one native thread-class token; every Hole Wizard variable
    stays."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(
            f"tap thread line is not in one callout part: {definitions!r}"
        )
    part = thread_parts[0]
    without_class = re.sub(r" {2,}", " ", _THREAD_CLASS.sub(" ", definitions[part]))
    updated = dict(definitions)
    updated[part] = without_class.rstrip()
    return updated


def _strip_thread_class(display: Any, *, label: str, thread: str) -> None:
    """Print a tap callout without its title-block thread class, loudly; the
    resolved callout must still name its thread (``4-40 UNC``, not only the
    tap drill)."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _thread_class_free_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = "\n".join(str(native.GetText(part) or "") for part in (1, 2, 3, 4))
    if (
        persisted != updated
        or re.search(r"\b2B\b", resolved)
        or f"{thread.lstrip('#')} UNC" not in resolved
    ):
        raise RuntimeError(
            f"{label} must name its thread without the class: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


def _append_callout_below(display: Any, text: str, *, label: str) -> None:
    """Append ``text`` as rows under a native callout's own, through the same
    IDisplayDimension text parts ``_strip_thread_class`` edits (definition 8,
    writable 4: callout below), loudly."""
    native = _early_bound(display, "IDisplayDimension")
    existing = str(native.GetText(8) or "")
    updated = f"{existing}\n{text}" if existing else text
    native.SetText(4, updated)
    persisted = str(native.GetText(8) or "")
    resolved = str(native.GetText(4) or "")
    if persisted != updated or not resolved.endswith(text):
        raise RuntimeError(
            f"{label} did not take its function rows: "
            f"definition={persisted!r}, resolved={resolved!r}"
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


def _set_callout_texts(
    adapter: Any, annotations: list[Any], texts: dict[str, str], *, part: int
) -> None:
    """Write each named dimension's native prefix (part 1,
    swDimensionTextPrefix) or suffix (part 2) and read it back
    (draw_ch_rocker_arm_tl_trammel_pivot_plate)."""
    remaining = dict(texts)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        text = remaining.pop(dimension_name(adapter, annotation), None)
        if text is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(part, text)
        got = str(display.GetText(part) or "")
        if got != text:
            raise RuntimeError(f"dimension text {text!r} did not persist: {got!r}")
    if remaining:
        raise RuntimeError(f"dimension texts not applied: {sorted(remaining)}")


_ARROWS_INSIDE = 0  # swDimArrowsInside


def _arrows_inside(adapter: Any, annotations: list[Any], name: str) -> None:
    """Hold one short dimension's arrows inside its extension lines, read
    back (_oblique_block_drawing). Machinist review of
    07a678696 (r1-r3 clarity): SolidWorks put the 34.9's arrows outside its
    17.5 sheet mm span, and its dimension line ran on past the left end into
    the REAM leader."""
    (annotation,) = [
        item for item in annotations if dimension_name(adapter, item) == name
    ]
    display = _early_bound(
        _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    display.ArrowSide = _ARROWS_INSIDE
    rebuild_drawing(adapter, label=f"{name} arrows inside")
    if int(display.ArrowSide) != _ARROWS_INSIDE:
        raise RuntimeError(f"{name}: arrows did not move inside")


@_telemetry.traced("drawing.carrier_near_y_witness_cap")
def _cap_near_y_witness(adapter: Any, annotations: list[Any]) -> Callable[[], None]:
    """Cap the 1.77's extension lines (NEAR_Y_WITNESS_MAX_M) so both stop
    outside the part, a gap short of its -X end, instead of the upper one
    running through A1 to the sketch origin; read back after the rebuild
    (_reposition_section_dimensions' stock cap). Returns that readback for
    the final settled check: persistence across later rebuilds is not
    documented."""
    (annotation,) = [
        item for item in annotations if dimension_name(adapter, item) == "PlateNearY"
    ]
    display = _early_bound(
        _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    display.MaxWitnessLineLength = NEAR_Y_WITNESS_MAX_M
    rebuild_drawing(adapter, label="carrier 1.77 witness cap")

    def check() -> None:
        if abs(float(display.MaxWitnessLineLength) - NEAR_Y_WITNESS_MAX_M) > 1e-9:
            raise RuntimeError("carrier 1.77: extension-line cap did not persist")

    check()
    return check


def _metres(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(value / 1000.0 for value in point_mm)


def _section_axes(
    adapter: Any, native: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet directions of model +X and +Y (1 mm each) in section A-A, read
    behind the projection barrier (draw_pn_pen_v_block ``_section_axes``)."""
    native.UpdateViewDisplayGeometry()
    x, y, z = _SECTION_ANCHOR_MM
    origin, plus_x, plus_y = model_points_in_view(
        adapter,
        native,
        (_metres((x, y, z)), _metres((x + 1.0, y, z)), _metres((x, y + 1.0, z))),
        label="carrier section A-A axes",
        names=("origin", "plus x", "plus y"),
    )
    return (
        (plus_x[0] - origin[0], plus_x[1] - origin[1]),
        (plus_y[0] - origin[0], plus_y[1] - origin[1]),
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Turn section A-A until model +Y runs up the sheet (draw_pd_platen
    ``_orient_section``), keeping the cut direction SolidWorks gives it: a
    reversed section showing its far side imported nothing (jig-r4).
    +X then reads right or left; the layout holds either way, and the log
    says which."""
    native = _early_bound(section, "IView")
    right, up = _section_axes(adapter, native)
    native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(up[1], up[0])
    rebuild_drawing(adapter, label="carrier section turned")
    right, up = _section_axes(adapter, native)
    tolerance = 1e-7
    if (
        up[1] <= 0.0
        or abs(up[0]) > tolerance
        or abs(right[1]) > tolerance
        or abs(right[0]) <= tolerance
    ):
        raise RuntimeError(f"carrier section A-A is not +Y up: {right=}, {up=}")
    _telemetry.info(
        f"carrier section A-A angle={float(native.Angle):.6f} rad, "
        f"+X reads {'right' if right[0] > 0.0 else 'left'} (cut not reversed)"
    )


def _crop_section(adapter: Any, section: Any) -> None:
    """Crop the full section A-A to SECTION_CROP_MODEL_MM, the cut's own span
    through A1 (draw_fr_nameplate ``_crop_section``'s sequence): a rectangle
    sketched in the view's own sketch round the projected fence corners, no
    crop outline, so the cut face stops where the partial cut used to."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(section, "IView")
    rebuild_drawing(adapter, label="carrier section before crop")
    sheet_corners = model_points_in_view(
        adapter,
        native,
        [_metres(point) for point in SECTION_CROP_MODEL_MM],
        label="carrier section A-A crop corners",
    )
    if not ddoc.ActivateView(view_name(adapter, native)):
        raise RuntimeError("failed to activate carrier section A-A for its crop")
    draw.ClearSelection2(True)
    before = tuple(float(value) for value in native.GetOutline())
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    corners = _view_sketch_points(adapter, native, sheet_corners)
    segments = tuple(
        sketch_manager.CreateCornerRectangle(*corners[0], *corners[1]) or ()
    )
    if len(segments) != 4:
        raise RuntimeError(
            f"carrier section A-A crop fence has {len(segments)} segments"
        )
    for segment in segments:
        if not _early_bound(segment, "ISketchSegment").Select4(True, None):
            raise RuntimeError("failed to select the carrier section A-A crop fence")
    # Crop2(jagged, no outline, intensity) returns swCropViewErrors_e; 1 is
    # NoError.
    status = int(native.Crop2(False, True, 0))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="carrier section crop")
    native.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in native.GetOutline())
    _telemetry.info(
        f"carrier section A-A Crop2 status {status}: outline {before!r} -> "
        f"{outline!r}, fence corners {sheet_corners!r}"
    )
    # The outline carries a margin past the fence (fr_nameplate r3: +19 mm on
    # a 69 mm fence; jig-r8 here: +25.6 mm on 72 mm), so it is not held to
    # the fence's width: the proof is that it still contains the fence and
    # shrank from the 2.1 m full cut.
    width = 2.0 * _SECTION_HALF * SECTION_SCALE[0] / SECTION_SCALE[1] / 1000.0
    fence_x = sorted(float(x) for x, _ in sheet_corners)
    fence_y = sorted(float(y) for _, y in sheet_corners)
    contains = (
        outline[0] <= fence_x[0]
        and outline[2] >= fence_x[-1]
        and outline[1] <= fence_y[0]
        and outline[3] >= fence_y[-1]
    )
    if (
        status != 1
        or not bool(native.IsCropped())
        or not contains
        or outline[2] - outline[0] > 0.25 * (before[2] - before[0])
    ):
        raise RuntimeError(
            f"carrier section A-A did not crop to its {width * 1000.0:.1f} mm "
            f"fence: status {status}, outline {before!r} -> {outline!r}, "
            f"fence corners {sheet_corners!r}"
        )


def _view_sketch_points(
    adapter: Any, native: Any, sheet_points: list[tuple[float, float]]
) -> list[tuple[float, ...]]:
    """Sheet points (metres) in the active view's own sketch frame, through
    its ModelToSketchTransform."""
    sketch = _early_bound(native.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_points:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    return points


def _sketch_section_breaks(adapter: Any, section: Any) -> None:
    """Draw SECTION_BREAKS into A-A's own sketch as thin lines
    (draw_fr_nameplate ``_sketch_section_break``). AddToDB keeps sketch
    inference from snapping the short Z segments onto the cut face's edges."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(section, "IView")
    if not ddoc.ActivateView(view_name(adapter, native)):
        raise RuntimeError("failed to activate carrier section A-A for its break lines")
    draw.ClearSelection2(True)
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        for end, polyline in enumerate(SECTION_BREAKS):
            sheet_points = model_points_in_view(
                adapter,
                native,
                [_metres(point) for point in polyline],
                label=f"carrier section A-A break line {end}",
            )
            points = _view_sketch_points(adapter, native, sheet_points)
            for index in range(len(points) - 1):
                if sketch_manager.CreateLine(*points[index], *points[index + 1]) is None:
                    raise RuntimeError(
                        f"carrier section A-A break line {end} segment {index} failed"
                    )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="carrier section A-A break lines")


def _centre_section(adapter: Any, section: Any) -> None:
    """Land the cut's centre (A1's axis at mid-thickness) on SECTION_CENTER:
    a section's Position is its cut-plane origin, not its outline's centre
    (draw_pn_pen_v_block ``_centre_section``)."""
    native = _early_bound(section, "IView")
    anchor = _metres(_SECTION_ANCHOR_MM)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"carrier section A-A centre, pass {attempt}"
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre carrier section A-A")
        rebuild_drawing(adapter, label="carrier section re-centred")
    settle_detail_projection(
        adapter,
        native,
        anchor,
        ink_xy=SECTION_CENTER,
        tolerance_xy=(0.0005, 0.0005),
        label="carrier section A-A",
    )


def _section_keep(adapter: Any, section: Any) -> dict[str, tuple[float, float]]:
    return {
        name: model_point_in_view(
            adapter, section, _metres(point), label=f"section A-A {name} text"
        )
        for name, point in SECTION_KEEP_MODEL_MM.items()
    }


def _reposition_section_dimensions(
    adapter: Any, section: Any, annotations: list[Any]
) -> list[Any]:
    """Place the dimensions imported into the uncropped section again on
    their SECTION_KEEP_MODEL_MM points of the cropped, centred view, prove the
    crop kept every one of them, visible, and cap the thickness's extension
    lines (STOCK_WITNESS_MAX_M) at the slab's -X end."""
    keep = _section_keep(adapter, section)
    placed = curate_dimensions(adapter, annotations, reposition=keep)
    states = {
        dimension_name(adapter, annotation): int(
            _early_bound(annotation, "IAnnotation").Visible
        )
        for annotation in placed
    }
    if set(states) != set(keep) or any(state != 1 for state in states.values()):
        raise RuntimeError(
            f"carrier section A-A lost dimensions to its crop: kept {states}, "
            f"want {sorted(keep)} visible"
        )
    (stock,) = (a for a in placed if dimension_name(adapter, a) == "StockThick")
    display = _early_bound(
        _early_bound(stock, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
    )
    display.MaxWitnessLineLength = STOCK_WITNESS_MAX_M
    rebuild_drawing(adapter, label="carrier stock witness cap")
    if abs(float(display.MaxWitnessLineLength) - STOCK_WITNESS_MAX_M) > 1e-9:
        raise RuntimeError(
            "carrier section A-A: finished thickness witness cap did not persist"
        )
    return placed


def _pin_section(adapter: Any, source_model: Any, top: Any) -> tuple[list[Any], Any]:
    """Full section A-A along the pin line, cropped to A1's slab, carrying the
    finished thickness and the chamfer leg, both from SectionReference.

    The hidden owner sketch lies in the cutting plane; a derived view takes it
    from the part as it stands when cut and selects it through its base view,
    so the section is cut and curated while the part shows it (draw_pd_platen
    ``_floor_section``). Full, not partial: through a short interior line the
    partial cut imported nothing (carrier-diag); the line crosses the whole
    plate, so the cut closes (carrier r11). Curated before it is
    cropped (the cropped import dropped StockThick), then cropped (fr_nameplate
    A-A), centred, and its dimensions placed again. A section shows no hidden
    lines.
    """
    line = [
        model_point_in_view(adapter, top, _metres(point), label="section A-A line")
        for point in SECTION_LINE_MODEL_MM
    ]
    with hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        (part_spec.SECTION_REFERENCE,),
        label="section A-A reference",
        base_view=top,
    ):
        section = create_section_view(
            adapter,
            top,
            line_start=line[0],
            line_end=line[1],
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=SECTION_SCALE,
            partial=False,
            label="pin-hole chamfer section",
        )
        _orient_section(adapter, section)
        set_hidden_lines_removed(adapter, section)
        annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep=_section_keep(adapter, section),
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        _crop_section(adapter, section)
        _centre_section(adapter, section)
        annotations = _reposition_section_dimensions(adapter, section, annotations)
        chamfer_text = model_point_in_view(
            adapter, section, _metres(SECTION_CHAMFER_TEXT_MODEL_MM),
            label="section A-A chamfer text",
        )
        offset_dimension_text(adapter, annotations, {"PinChamferSize": chamfer_text})
    _sketch_section_breaks(adapter, section)
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="carrier section A-A"
    )
    add_note(adapter, SECTION_NOTE, *SECTION_NOTE_XY)
    return annotations, section


@_telemetry.traced("drawing.carrier_hub_reference_position")
def _hub_reference_position(adapter: Any, top: Any) -> Callable[[], None]:
    """The HUB's position from A1 as two drawing-native dimensions between the
    actual A1 and HUB edges, centred on both axes, parenthesized as ASME
    REFERENCE (set_reference_dimension) at the document's places. Returns
    their readback: the same two edges, values and parentheses after the
    final rebuild."""
    to_sheet = _view_mapper(adapter, top)

    def edges() -> tuple[Any, Any]:
        return (
            _circle_edge(adapter, top, part_spec.PIN_HOLE_DIA, "A1 pin hole",
                         center_x_mm=_A1[0], center_y_mm=_A1[1]),
            _circle_edge(adapter, top, part_spec.CLAMP_TAP_DRILL, "HUB clamp tap",
                         center_x_mm=part_spec.HUB[0], center_y_mm=part_spec.HUB[1]),
        )

    a1, hub = edges()
    centres = (to_sheet(_xy(*_A1)), to_sheet(_xy(*part_spec.HUB)))
    references = []
    for axis, orientation, expected in (
        ("X", "horizontal", abs(part_spec.HUB[0] - _A1[0])),
        ("Y", "vertical", abs(part_spec.HUB[1] - _A1[1])),
    ):
        label = f"HUB reference {axis} from A1"
        dimension = add_edge_dimension(
            adapter, top, p0=centres[0], p1=centres[1],
            text_xy=to_sheet(HUB_REFERENCE_TEXT_MODEL_MM[axis]), label=label,
            orientation=orientation, entities=(a1, hub),
        )
        set_arc_endpoints_to_center(adapter, dimension, label=label)
        display = _early_bound(dimension, "IDisplayDimension")
        # ShowParenthesis can add a second pair (document "parentheses by
        # default") or read True and render bare: clear it, then use the
        # proven prefix/suffix form (_supplier_dimensions).
        display.ShowParenthesis = False
        if display.ShowParenthesis is not False:
            raise RuntimeError(f"{label}: native ShowParenthesis did not clear")
        set_reference_dimension(adapter, display.GetAnnotation(), label=label)
        _telemetry.info(
            f"{label}: places={display.GetPrimaryPrecision2()} "
            f"use_doc_precision={display.GetUseDocPrecision()} "
            f"is_reference={display.IsReferenceDim()} "
            f"driven_state={_early_bound(display.GetDimension2(0), 'IDimension').DrivenState}"
        )
        references.append((display, expected, label))

    def check() -> None:
        current = edges()
        for display, expected, label in references:
            model = _early_bound(display.GetDimension2(0), "IDimension")
            if any(int(model.GetArcEndCondition(index)) != 1 for index in (1, 2)):
                raise RuntimeError(f"{label}: both endpoints must stay on the hole axes")
            assert_dimension_measures(
                adapter, display, expected_mm=expected, label=label, entities=current,
            )
            marks = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
            if marks != ("(", ")") or display.ShowParenthesis is not False:
                raise RuntimeError(
                    f"{label} is not one parenthesized REFERENCE: prefix/suffix={marks!r} "
                    f"ShowParenthesis={display.ShowParenthesis!r}"
                )

    check()
    return check


def _hub_sheet(adapter: Any) -> Callable[[], None]:
    """The HUB clamp tap's own sheet: its native callout, which says it is
    drilled and tapped at assembly, and its reference position from A1.
    Returns the references' settled readback, run on this sheet."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("cannot activate the HUB clamp sheet")
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)
    x, y = part_spec.HUB
    label = "HUB clamp tap"
    callout = add_native_hole_callout(
        adapter, top, callout_xy=HUB_CALLOUT_XY, label=label,
        edge=_circle_edge(
            adapter, top, part_spec.CLAMP_TAP_DRILL, label,
            center_x_mm=x, center_y_mm=y,
        ),
    )
    _strip_thread_class(callout, label=f"{label} callout", thread=part_spec.HUB_THREAD)
    set_callout_lengths_to_three_places(callout, label=f"{label} callout")
    _append_callout_below(callout, HUB_TAP_NOTE, label=f"{label} callout")
    check_references = _hub_reference_position(adapter, top)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    import_cosmetic_threads(adapter, iso)
    for view in (top, iso):
        _hide_thread_labels(adapter, view)
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot restore the carrier sheet")

    @_telemetry.traced("drawing.carrier_hub_reference_position.settled")
    def settled() -> None:
        previous = str(_early_bound(drawing.GetCurrentSheet(), "ISheet").GetName())
        if not drawing.ActivateSheet(SHEET_NAMES[2]):
            raise RuntimeError("HUB clamp sheet cannot be activated for final readback")
        try:
            check_references()
        finally:
            if not drawing.ActivateSheet(previous):
                raise RuntimeError("HUB reference readback could not restore the active sheet")

    return settled


def _hole_table_sheet(adapter: Any, source_model: Any) -> Any:
    """The native hole table and its tagged plan; returns its settled readback."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate the carrier hole-table sheet")
    top = place_view(adapter, str(SOURCE), "*Top", 0.222, 0.210, scale=VIEW_SCALE)
    set_hidden_lines_removed(adapter, top)
    _hide_thread_labels(adapter, top)
    settled = create_carrier_hole_table(adapter, top, source_model, SOURCE)
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot restore the carrier sheet")
    return settled


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open carrier source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
        "Outer Pin Row Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="carrier")
    if not _early_bound(drawing_model, "IDrawingDoc").ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate the carrier sheet")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Carrier Plate Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel carrier plate; 6061-T6511; MHA-CH-06-TL-21",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # swDetailingSectionViewLineStyleDisplay (542) = StandardWithoutConnector
    # (1): A-A's line prints its end segments only (draw_fr_rocker_arm_support).
    # Carrier-r1 review: drawn whole along the pin line, it read as the origin
    # of every Y dimension instead of the reamed holes' axes.
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set the end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    on_top = _view_mapper(adapter, top)
    # Every X station from A1 lives on StationReference, a sketch the part
    # saves hidden: _drawing_hidden_sketches shows it in the view that
    # imports it.
    annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        top,
        keep={name: on_top(xyz) for name, xyz in TOP_KEEP.items()},
        view_label="top view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations, section = _pin_section(adapter, source_model, top)
    annotations.extend(section_annotations)
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    _set_callout_texts(adapter, annotations, CALLOUT_PREFIXES, part=1)
    _arrows_inside(adapter, annotations, "EdgeX")
    near_y_cap_settled = _cap_near_y_witness(adapter, annotations)
    ream = [
        item for item in annotations if dimension_name(adapter, item) == "PinHoleDia"
    ]
    if len(ream) != 1:
        raise RuntimeError("expected one actual 4X REAM size dimension")
    _assert_ream_control(adapter, ream[0])

    # Native Hole Wizard callouts, no process words (the base bar's TL-20
    # convention: "4X Ø2.26 THRU ALL / #4-40 UNC THRU ALL"); the CL/CR and
    # riser taps add the function their stations serve (rule 4; machinist
    # review mr3 for CR), the lever taps their full-thread shortfall (rule 20).
    for label, xy, drill, (x, y), thread, function in (
        *(
            (
                f"{key} clamp tap",
                xy,
                part_spec.CLAMP_TAP_DRILL,
                part_spec.END_CLAMPS[key],
                part_spec.CLAMP_THREAD,
                part_spec.END_CLAMP_TAP_CALLOUT,
            )
            for key, xy in (("CL", CL_CALLOUT_XY), ("CR", CR_CALLOUT_XY))
        ),
        (
            "riser screw taps",
            RISER_CALLOUT_XY,
            part_spec.RISER_TAP_DRILL,
            part_spec.RISER_SCREWS[3],
            part_spec.RISER_THREAD,
            part_spec.RISER_TAP_CALLOUT,
        ),
        (
            "feed lever taps",
            LEVER_CALLOUT_XY,
            part_spec.LEVER_TAP_DRILL,
            part_spec.LEVER_HOLES[1],
            part_spec.LEVER_THREAD,
            part_spec.LEVER_TAP_CALLOUT,
        ),
    ):
        callout = add_native_hole_callout(
            adapter,
            top,
            callout_xy=xy,
            label=label,
            edge=_circle_edge(adapter, top, drill, label, center_x_mm=x, center_y_mm=y),
        )
        _strip_thread_class(callout, label=f"{label} callout", thread=thread)
        set_callout_lengths_to_three_places(callout, label=f"{label} callout")
        if function is not None:
            _append_callout_below(callout, function, label=f"{label} callout")

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    import_cosmetic_threads(adapter, iso)
    for view in (top, iso):
        _hide_thread_labels(adapter, view)
    table_settled = _hole_table_sheet(adapter, source_model)
    hub_settled = _hub_sheet(adapter)
    assert_imported_precision(adapter, annotations, IMPORTED_PRECISION)

    @_telemetry.traced("drawing.carrier_pin_controls.settled")
    def pin_controls_settled() -> None:
        # The 1.77 cap is read back on its own sheet after every later
        # rebuild (_hub_sheet's settled pattern), restoring the active sheet.
        sheets = _early_bound(drawing_model, "IDrawingDoc")
        previous = str(_early_bound(sheets.GetCurrentSheet(), "ISheet").GetName())
        if not sheets.ActivateSheet(SHEET_NAMES[0]):
            raise RuntimeError("carrier sheet cannot be activated for final readback")
        try:
            _assert_ream_control(adapter, ream[0])
            near_y_cap_settled()
        finally:
            if not sheets.ActivateSheet(previous):
                raise RuntimeError("carrier readback could not restore the active sheet")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Carrier Plate Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(pin_controls_settled, table_settled, hub_settled),
        expected_sheet_names=SHEET_NAMES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
