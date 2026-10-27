r"""Create the MHA-SM-04 gooseneck spring screw manufacturing drawing.

The SLDPRT remains authoritative.  MHA-SM-04 is a slotted fillister shoulder
screw (owner ruling 2026-10-26 (#1951, option B)): a plain Ø3.50 loop seat
under the head, a 45-degree lead, an #8-32 UNC thread.  A screw carries no
datum and no geometric-control frame (drawing-guidelines.md rule 5 (avoid
excessive GD&T)): the seat diameter and the shoulder length (to the lead's
foot) print as the part's stacked LIMIT bands, the full-thread station as
the part's single "5.67 MAX" from the under-head face, the crown's sphere as
the reference "(SR20.03)" on its arc, and every other size is an ordinary
model dimension at its part-authored places under the title block's band for
those places (.X for the tip chamfer, .XX for the rest).  The lead itself is
unprinted: the two diameters fix it and the shoulder length's callout names
it.

The screw axis is model +Z, so the ``*Right`` view already lays it horizontal
as it sits in the lathe: model +Z runs to paper-LEFT, putting the crowned head
on the left and the thread tip on the right.  Axial sizes baseline from the
under-head face, the face that clamps the spring eye.  The head-end view is
the ``*Front`` orientation (looking down -Z onto the crown), which is exactly
the third-angle LEFT view of that profile, so it sits on the profile's axis
to its left and shows the slot.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_gooseneck_spring_screw.py sm-gooseneck-spring-screw
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from sm_gooseneck_spring_screw_geom import (
    CROWN_CENTER_Z,
    CROWN_RADIUS,
    CROWN_RISE,
    FULL_THREAD_STATION_MAX,
    FULL_THREAD_STATION_MAX_TOL_TYPE,
    HEAD_CYL_H,
    HEAD_DIA,
    HEAD_H,
    LENGTH,
    MAJOR_DIA,
    OVERALL_LENGTH,
    SEAT_DIA,
    SEAT_DIA_LOWER,
    SEAT_DIA_TOL_TYPE,
    SEAT_DIA_UPPER,
    SHOULDER_LENGTH,
    SHOULDER_LENGTH_LOWER,
    SHOULDER_LENGTH_TOL_TYPE,
    SHOULDER_LENGTH_UPPER,
    SLOT_DEPTH,
    SLOT_FLOOR_Z,
    SLOT_WIDTH,
    STEP_LEAD,
    TIP_CHAMFER,
)
from sm_gooseneck_spring_screw_spec import (
    CROWN_RADIUS_PREFIX,
    DIMENSION_CALLOUTS_ABOVE_BY_NAME,
    DIMENSION_CALLOUTS_BY_NAME,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
    THREAD_CALLOUT,
)


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_gooseneck_spring_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# Both orthographic views print at the sheet scale, so neither needs a caption.
# 4:1 lays the 24.5 profile 98 mm long and the 1.6 slot 6.4 mm wide.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# The under-head face stays at sheet x 0.197, where farm run
# 20261027T053051351Z rendered it (SHIP): the head, its stack and the two
# rows over the shank keep their places, and the 17.50 under-head length
# (16.00 there) grows the profile 6 mm toward the tip, the view's outline
# then 0.1634-0.2726 by 0.1344-0.1956.
SIDE_CENTER = (0.218, 0.165)
# Third-angle left view of the crowned head end, on the profile's axis.
END_CENTER = (0.085, SIDE_CENTER[1])
ISO_CENTER = (0.360, 0.215)
ISO_SCALE = (2, 1)
# The view centre is the model bounding box's: apex z=HEAD_H to tip z=-LENGTH.
_BOX_MID_Z = (HEAD_H - LENGTH) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left)."""
    return SIDE_CENTER[0] + (_BOX_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the screw axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


APEX_X = _sheet_x(HEAD_H)
RIM_X = _sheet_x(HEAD_CYL_H)
SLOT_FLOOR_X = _sheet_x(SLOT_FLOOR_Z)
UNDERHEAD_X = _sheet_x(0.0)
TIP_X = _sheet_x(-LENGTH)
# Where the full thread meets the tip chamfer.
THREAD_START_X = _sheet_x(-(LENGTH - TIP_CHAMFER))
HEAD_TOP_Y = _sheet_y(HEAD_DIA / 2.0)
THREAD_TOP_Y = _sheet_y(MAJOR_DIA / 2.0)
THREAD_BOTTOM_Y = _sheet_y(-MAJOR_DIA / 2.0)
SEAT_BOTTOM_Y = _sheet_y(-SEAT_DIA / 2.0)
# The 45-degree lead: its foot ends the seat, its top meets the thread major.
LEAD_FOOT_X = _sheet_x(-SHOULDER_LENGTH)
LEAD_TOP_X = _sheet_x(-(SHOULDER_LENGTH + STEP_LEAD))
# The printed full-thread station on the thread's major silhouette.
FULL_THREAD_X = _sheet_x(-FULL_THREAD_STATION_MAX)
# The crown sphere's centre on the axis, right of the apex by its radius.
CROWN_CENTER_X = _sheet_x(CROWN_CENTER_Z)

# Text blocks as rendered at this text height (layout audit of farm run
# 20261027T034356887Z): a dimension's block centres on its anchor,
# both ways; its last line sits on the dimension line (the underline), its
# ink ~1.0 mm over the line however the anchor is set (0.96 mm under
# 'CLEARS LEAD', 1.04 mm under 'MHA-SM-01', farm run 20261027T053051351Z);
# lines above it step 5.56 mm (a callout line, or the value over its
# callout) and 4.53 mm (a stacked LIMIT's upper over its lower); the first
# line's ink tops out 4.50 mm above its baseline.  Widths are the widest
# line's: the measured ones where that line rendered, else its Century
# Gothic advance at the scale the measured lines fix (4.667 um per font unit
# at 1000 units, ten rendered strings agreeing within 0.3 %).
_CALLOUT_PITCH = 0.00556
_LIMIT_PITCH = 0.00453
_FIRST_LINE_INK = 0.0045


def block_height(value_lines: int, callout_lines: int) -> float:
    """Sheet height of a dimension block from its underline to its top ink."""
    return (
        callout_lines * _CALLOUT_PITCH
        + (value_lines - 1) * _LIMIT_PITCH
        + _FIRST_LINE_INK
    )


def _callout_lines(name: str) -> int:
    text = (
        DIMENSION_CALLOUTS_BY_NAME.get(name) or DIMENSION_CALLOUTS_ABOVE_BY_NAME[name]
    )
    return len(text.splitlines())


# 'MHA-SM-VN-51 LOOP', 48.41 mm as rendered.
SEAT_DIA_TEXT_WIDTH = 0.0484
SEAT_DIA_TEXT_HEIGHT = block_height(2, _callout_lines("SeatDia"))
# 'MHA-SM-VN-51 LOOP', 48.41 mm as rendered (the seat Ø's widest line too).
SHOULDER_LENGTH_TEXT_WIDTH = SEAT_DIA_TEXT_WIDTH
SHOULDER_LENGTH_TEXT_HEIGHT = block_height(2, _callout_lines("ShoulderLength"))
# 'TO FULL THREAD' 35.69 mm (font advance) over '5.67 max.', 21.44 mm as
# rendered, on one line.
FULL_THREAD_TEXT_WIDTH = 0.0357
FULL_THREAD_VALUE_WIDTH = 0.0214
FULL_THREAD_TEXT_HEIGHT = block_height(1, _callout_lines("FullThread"))
# ' (SR20.03) ' 22.83 mm (font advance).
CROWN_RADIUS_TEXT_WIDTH = 0.0228

# Rows below the profile, 15 mm apart, the first 38 mm under the head
# (text sits ~3 mm above its requested point, the dimension line ~5 mm
# below it), clear of the seat Ø's text block above them.  Row 0 chains the
# head height and the under-head length from the under-head face; row 1
# carries the reference overall.
_ROW_Y = (HEAD_TOP_Y - 0.093, HEAD_TOP_Y - 0.108)
# ' 1.00 ' as rendered (farm run 20261010T190631112Z).
CROWN_RISE_TEXT_WIDTH = 0.0116
# The seat Ø's dimension line stands on the seat near the under-head face,
# leaving the seat's run toward the lead to its text.
SEAT_DIA_X = UNDERHEAD_X + 0.004
# The thread callout's leader lands on the edge where the full thread meets
# the tip chamfer, never on the lead.  The note stands up and right so the
# leader slants down-left onto that edge.
THREAD_PICK = (THREAD_START_X, SIDE_CENTER[1] + 0.004)
# 11 mm right of the pick (13 at the 16.00 length): the leader keeps its
# down-left slant and the note stays under the shoulder length's block, its
# line 13 mm over the note, rather than walking toward the isometric.
THREAD_NOTE_XY = (THREAD_START_X + 0.011, SIDE_CENTER[1] + 0.035)
# Two rows over the shank, both from the under-head face, the longer
# dimension outside.  The shoulder length's dimension line runs 13 mm
# over the thread note's text row (where it rendered clear in farm run
# 20261027T034356887Z); the full-thread limit's 10 mm above it.
SHOULDER_LENGTH_LINE_Y = THREAD_NOTE_XY[1] + 0.013
FULL_THREAD_LINE_Y = SHOULDER_LENGTH_LINE_Y + 0.010
# The full-thread block centres over its own 22.7-mm span, above its line.
# Its extension lines rise 1.0 mm past the line, to the ink of the line on
# it, so that line must fit between them: the value '5.67 max.' (21.44 mm)
# does, its ink 0.86 / 0.92 mm inside the two lines (Century Gothic
# outlines), and its callout stands above it (a below callout put 'MHA-SM-01'
# on the line and the under-head line into its 'M', farm run
# 20261027T053051351Z).
FULL_THREAD_TEXT_XY = (
    (UNDERHEAD_X + FULL_THREAD_X) / 2.0,
    FULL_THREAD_LINE_Y + FULL_THREAD_TEXT_HEIGHT / 2.0,
)
# The shoulder length's span (3.9 mm) is far narrower than its block, so the
# block stands right of every line it would otherwise meet: 3 mm clear of
# the full-thread block, which it shares a height with, and so of the 5.67
# station's extension line too.
SHOULDER_LENGTH_TEXT_LEFT = (
    FULL_THREAD_TEXT_XY[0] + FULL_THREAD_TEXT_WIDTH / 2.0 + 0.003
)
# The crown radius reads lower-left of the crown.  A radial leader runs
# along the radius, so it leaves the arc 17 degrees below the axis (the arc
# spans +/-18.2 degrees, asin(6.25 / 20.03)) and runs down-left to its bend,
# under the head Ø's lower end and over row 0, left of the apex extension
# lines.  The bend stands 1.6 mm right of the text's box and 2.8 mm under its
# anchor (radial SR dimensions as rendered: dt-pinion-arbor BackCapR and
# dt-pinion-lift-rod CapR, farm run 20261027T025804097Z).
CROWN_RADIUS_LEADER_DEG = 17.0
CROWN_RADIUS_BEND_Y = SIDE_CENTER[1] - 0.033
CROWN_RADIUS_BEND_X = CROWN_CENTER_X - (SIDE_CENTER[1] - CROWN_RADIUS_BEND_Y) / (
    math.tan(math.radians(CROWN_RADIUS_LEADER_DEG))
)
RADIAL_BEND_GAP = 0.0016
RADIAL_SHOULDER_DROP = 0.0028
CROWN_RADIUS_ARC_XY = (
    CROWN_CENTER_X
    - CROWN_RADIUS * _S / 1000.0 * math.cos(math.radians(CROWN_RADIUS_LEADER_DEG)),
    SIDE_CENTER[1]
    - CROWN_RADIUS * _S / 1000.0 * math.sin(math.radians(CROWN_RADIUS_LEADER_DEG)),
)
SIDE_KEEP = {
    "HeadHeight": ((APEX_X + UNDERHEAD_X) / 2.0, _ROW_Y[0]),
    "UnderHeadLength": ((UNDERHEAD_X + TIP_X) / 2.0, _ROW_Y[0]),
    "OverallLength": ((APEX_X + TIP_X) / 2.0, _ROW_Y[1]),
    # Diameters on the side view (drawing-guidelines.md rule 11 (turned parts read like the lathe)): the head's stands clear of the
    # crown, between the profile and the head-end view.
    "HeadDia": (APEX_X - 0.019, SIDE_CENTER[1]),
    # The crown rise and the slot depth both read from the apex, stacked
    # above the head.  The rise is too narrow for its text, so the text
    # stands outside, left of the apex: centred between the two extension
    # lines it sat on the slot depth's apex extension (layout audit of farm
    # run 20261010T190631112Z, 6c56fd769).
    "CrownRise": (
        APEX_X - 0.003 - CROWN_RISE_TEXT_WIDTH / 2.0,
        HEAD_TOP_Y + 0.012,
    ),
    "SlotDepth": ((APEX_X + SLOT_FLOOR_X) / 2.0, HEAD_TOP_Y + 0.024),
    "CrownRadius": (
        CROWN_RADIUS_BEND_X - RADIAL_BEND_GAP - CROWN_RADIUS_TEXT_WIDTH / 2.0,
        CROWN_RADIUS_BEND_Y + RADIAL_SHOULDER_DROP,
    ),
    "FullThread": FULL_THREAD_TEXT_XY,
    "ShoulderLength": (
        SHOULDER_LENGTH_TEXT_LEFT + SHOULDER_LENGTH_TEXT_WIDTH / 2.0,
        SHOULDER_LENGTH_LINE_Y + SHOULDER_LENGTH_TEXT_HEIGHT / 2.0,
    ),
    # The seat Ø stands on the seat; its text is offset below (see below).
    "SeatDia": (SEAT_DIA_X, SIDE_CENTER[1] - 0.012),
    # The tip chamfer's axial leg reads below-right of the tip.
    "TipChamfer": (TIP_X + 0.012, SIDE_CENTER[1] - 0.016),
}
# The seat Ø's text goes on an OffsetText leader, hung right of its own
# dimension line: the leader meets the text's LEFT end, so with that end
# right of the line the leader descends beside the text, not through it, and
# the text stays clear of the under-head extension line (layout audit of farm
# run 20261010T190631112Z, 6c56fd769).  Its right end stops short of the tip
# chamfer's extension lines and its upper limit's top stays below the
# thread silhouette.  The block is the stacked limits over the callout; as
# rendered in farm run 20261027T034356887Z the leader's foot stood 2.1 mm
# right of the Ø line, and the machinist review read it clear.
SEAT_DIA_LEADER_GAP = 0.0021
SEAT_DIA_TEXT_XY = (
    SEAT_DIA_X + SEAT_DIA_LEADER_GAP + SEAT_DIA_TEXT_WIDTH / 2.0,
    SIDE_CENTER[1] - 0.023,
)
# The slot width reads right of the head-end view, left of the head Ø.
END_KEEP = {
    "SlotWidth": (
        END_CENTER[0] + HEAD_DIA * _S / 2000.0 + 0.010,
        END_CENTER[1] + 0.010,
    ),
}
# A point on the thread's cylindrical face, clear of every dimension line.
CENTERLINE_PICK = ((LEAD_TOP_X + THREAD_START_X) / 2.0, SIDE_CENTER[1] + 0.003)
ISO_NOTE_XY = (0.340, 0.180)
# Bottom-left, above the title-block line, like the other screw sheets.
NOTES_XY = (0.016, 0.070)

# Policy: native generation verifies persisted values, tolerances and
# reference state.  swTolType_e: NONE leaves the title block's band, LIMIT
# prints the model value plus each deviation, MAX prints the model value as
# the part's single limit.  Each row is (nominal mm, tolerance type).
_TOL_NONE, _TOL_LIMIT, _TOL_MAX = 0, 3, 6
if (
    SEAT_DIA_TOL_TYPE != _TOL_LIMIT
    or SHOULDER_LENGTH_TOL_TYPE != _TOL_LIMIT
    or FULL_THREAD_STATION_MAX_TOL_TYPE != _TOL_MAX
):
    raise AssertionError(
        "MHA-SM-04 seat/shoulder bands are no longer LIMIT or full thread MAX"
    )
PRINTED_DIMENSIONS: dict[str, tuple[float, int]] = {
    "HeadDia": (HEAD_DIA, _TOL_NONE),
    "HeadHeight": (HEAD_H, _TOL_NONE),
    "CrownRise": (CROWN_RISE, _TOL_NONE),
    "CrownRadius": (CROWN_RADIUS, _TOL_NONE),
    "UnderHeadLength": (LENGTH, _TOL_NONE),
    "SeatDia": (SEAT_DIA, _TOL_LIMIT),
    "ShoulderLength": (SHOULDER_LENGTH, _TOL_LIMIT),
    "FullThread": (FULL_THREAD_STATION_MAX, _TOL_MAX),
    "TipChamfer": (TIP_CHAMFER, _TOL_NONE),
    "SlotWidth": (SLOT_WIDTH, _TOL_NONE),
    "SlotDepth": (SLOT_DEPTH, _TOL_NONE),
    "OverallLength": (OVERALL_LENGTH, _TOL_NONE),
}
# The crown radius prints "(SR20.03)": the part authors "SR", the drawing
# wraps it as a reference.  Every other reference takes the plain parentheses.
CROWN_RADIUS_PRINTED_PREFIX = "(" + CROWN_RADIUS_PREFIX
_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
# Every LIMIT row's (lower, upper) deviations, mm: a LIMIT row without its
# band would skip the deviation readback, so the two must name the same rows.
LIMIT_DEVIATIONS: dict[str, tuple[float, float]] = {
    "SeatDia": (SEAT_DIA_LOWER, SEAT_DIA_UPPER),
    "ShoulderLength": (SHOULDER_LENGTH_LOWER, SHOULDER_LENGTH_UPPER),
}
if set(LIMIT_DEVIATIONS) != {
    name for name, (_, kind) in PRINTED_DIMENSIONS.items() if kind == _TOL_LIMIT
}:
    raise AssertionError("MHA-SM-04 LIMIT rows and their deviations disagree")
# Unprinted controls: the lead's axial leg (held at 45 degrees by equation
# from the two diameters) and the thread major the callout defines.
SOURCE_ONLY_DIMENSIONS: dict[str, tuple[float, int]] = {
    "StepLead@ShankProfile": (STEP_LEAD, _TOL_NONE),
    "ThreadDia@ShankProfile": (MAJOR_DIA, _TOL_NONE),
}


def _check_dimension_state(
    label: str, dimension: Any, expected: tuple[float, int]
) -> None:
    """Raise unless one native dimension holds its spec nominal and type."""
    nominal, tolerance_type = expected
    dimension = _early_bound(dimension, "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    value_mm = float(dimension.SystemValue) * 1000.0
    if not math.isclose(value_mm, nominal, abs_tol=1e-6):
        raise RuntimeError(
            f"MHA-SM-04 {label}: persisted nominal {value_mm!r} mm, spec "
            f"{nominal!r} mm; rebuild the source part"
        )
    if int(tolerance.Type) != tolerance_type:
        raise RuntimeError(
            f"MHA-SM-04 {label}: tolerance type {int(tolerance.Type)}, "
            f"spec {tolerance_type}; rebuild the source part"
        )
    if label in LIMIT_DEVIATIONS:
        lower, upper = LIMIT_DEVIATIONS[label]
        read = (
            float(tolerance.GetMinValue()) * 1000.0,
            float(tolerance.GetMaxValue()) * 1000.0,
        )
        if not all(
            math.isclose(a, b, abs_tol=1e-6) for a, b in zip(read, (lower, upper))
        ):
            raise RuntimeError(
                f"MHA-SM-04 {label}: LIMIT deviations {read!r} mm, spec "
                f"{(lower, upper)!r} mm; rebuild the source part"
            )


@_telemetry.traced("drawing.sm_gooseneck_spring_screw.crown_radius")
def _dress_crown_radius(adapter: Any, annotations: Sequence[Any]) -> None:
    """Print the crown's CrownRadius as the spherical reference "(SR20.03)"
    and stop its leader at the arc (draw_ch_fulcrum_keeper._dress_crown_radius):
    the head Ø and the crown rise fix the sphere, and with the arrow outside
    and no solid leader the 80-mm radius draws no line through the head and
    the shank to its centre."""
    (annotation,) = [
        item for item in annotations if dimension_name(adapter, item) == "CrownRadius"
    ]
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("MHA-SM-04 CrownRadius imported diametric, not radial")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    if existing != CROWN_RADIUS_PREFIX:
        raise RuntimeError(
            f"MHA-SM-04 CrownRadius prefix {existing!r} is not the part's "
            f"{CROWN_RADIUS_PREFIX!r}; rebuild the source part"
        )
    display.SetText(1, CROWN_RADIUS_PRINTED_PREFIX)
    display.SetText(2, ")")  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    if applied != (CROWN_RADIUS_PRINTED_PREFIX, ")"):
        raise RuntimeError(
            f"failed to mark MHA-SM-04 CrownRadius a reference: {applied}"
        )
    display.ShortenedRadius = False
    display.ArcExtensionLineOrOppositeSide = False
    display.ArrowSide = _ARROWS_OUTSIDE
    display.SolidLeader = False
    if (
        bool(display.ShortenedRadius)
        or bool(display.ArcExtensionLineOrOppositeSide)
        or int(display.ArrowSide) != _ARROWS_OUTSIDE
        or bool(display.SolidLeader)
    ):
        raise RuntimeError("MHA-SM-04 crown radius kept its leader to the centre")


def _verify_source_dimensions(model: Any) -> None:
    """The unprinted callout controls, read from the opened source part."""
    for full_name, expected in SOURCE_ONLY_DIMENSIONS.items():
        dimension = model.Parameter(full_name)
        if dimension is None:
            raise RuntimeError(f"MHA-SM-04 source part lacks {full_name}")
        _check_dimension_state(full_name, dimension, expected)


def _verify_printed_dimensions(adapter: Any, views: Sequence[Any]) -> None:
    """Re-read every printed size after the last rebuild (settled check)."""
    found: dict[str, list[Any]] = {name: [] for name in PRINTED_DIMENSIONS}
    for view in views:
        for item in _early_bound(view, "IView").GetAnnotations() or ():
            annotation = _early_bound(item, "IAnnotation")
            name = dimension_name(adapter, annotation)
            if name in found:
                found[name].append(annotation)
    for name, expected in PRINTED_DIMENSIONS.items():
        if len(found[name]) != 1:
            raise RuntimeError(
                f"MHA-SM-04 sheet prints {name} {len(found[name])} times, not once"
            )
        display = _early_bound(
            found[name][0].GetSpecificAnnotation(), "IDisplayDimension"
        )
        _check_dimension_state(name, display.GetDimension2(0), expected)
        parenthesized = str(display.GetText(1) or "").startswith("(") and str(
            display.GetText(2) or ""
        ).endswith(")")
        if parenthesized != (name in REFERENCE_DIMENSIONS):
            raise RuntimeError(f"MHA-SM-04 {name}: reference state did not persist")
        if (
            name == "CrownRadius"
            and str(display.GetText(1) or "") != CROWN_RADIUS_PRINTED_PREFIX
        ):
            raise RuntimeError("MHA-SM-04 CrownRadius: SR prefix did not persist")
        if int(display.GetPrimaryPrecision2()) != DRAWING_PRECISION_BY_NAME[name]:
            raise RuntimeError(f"MHA-SM-04 {name}: display places did not persist")
        if (
            name in LIMIT_DEVIATIONS
            and int(display.GetPrimaryTolPrecision2())
            != DRAWING_PRECISION_BY_NAME[name]
        ):
            raise RuntimeError(f"MHA-SM-04 {name}: limit places did not persist")
        # The part authors every callout (swDimensionTextCalloutBelow = 4,
        # swDimensionTextCalloutAbove = 3); the drawing only reads them back.
        # SOLIDWORKS may hand lines back as CRLF.
        for slot, expected_by_name in (
            (4, DIMENSION_CALLOUTS_BY_NAME),
            (3, DIMENSION_CALLOUTS_ABOVE_BY_NAME),
        ):
            callout = str(display.GetText(slot) or "").replace("\r\n", "\n")
            if callout != expected_by_name.get(name, ""):
                raise RuntimeError(
                    f"MHA-SM-04 {name}: callout {callout!r} is not the part's"
                )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck-spring-screw source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    _verify_source_dimensions(adapter.currentModel)
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Gooseneck Spring Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: (
                "gooseneck spring clamp; slotted fillister shoulder screw; "
                f"{THREAD_CALLOUT}; steel"
            ),
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="head-end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *end_annotations]
    offset_dimension_text(adapter, side_annotations, {"SeatDia": SEAT_DIA_TEXT_XY})
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The crown radius keeps its part-authored "SR" inside the parentheses;
    # the plain references then rebuild the sheet.
    _dress_crown_radius(adapter, side_annotations)
    for name in sorted(REFERENCE_DIMENSIONS - {"CrownRadius"}):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one MHA-SM-04 {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"MHA-SM-04 {name}")

    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-SM-04 head-end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-SM-04 turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-SM-04 thread callout",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Spring Screw Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(lambda: _verify_printed_dimensions(adapter, (side, end)),),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
