r"""Create the curated machinist drawing for the platen clip (MHA-PD-03).

The clip is one .032 brass sheet, 3.29 long: a flat screw rail carrying the two
#2 loose screw holes, an open-ended slit from each end, and a spring rail
joined to the screw rail only at the centre bridge, formed into two shallow
bows.  The sheet runs at 3:1: the plan (front view) is the formed part seen
square to its screw rail (the length, called FORMED since forming draws the
spring tips back flush with the rail ends, the bridge's two ends
from the near end, the hole row, the screw rail's and the overall width
from the outer edge, the slit, the corner radii,
the hole stations), the profile (top view) above it the bows' rise and, as
references, the four stations where the bows leave and rejoin the flat, their
radius, the developed finger and the sheet stock; a 2:1 isometric shows the
form.

The sheet prints decimal inch (the part's ``drawing_unit: in``).  Every
printed dimension is an associative model dimension whose places the
part authors (``build_pd_platen_clip.DRAWING_PRECISION``); the overall width,
the rise, the stations and the developed finger live in hidden reference
sketches the views show to import them (``_drawing_hidden_sketches``).  The
hole size ships as a native Hole Wizard callout.

Run (SolidWorks already open)::

    uv run python cad\scripts\draw_pd_platen_clip.py pd-platen-clip
"""

from __future__ import annotations

import argparse
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
    set_dimension_callouts,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from build_pd_platen_clip import (
    ARCH_RISE,
    BRIDGE_X0,
    BRIDGE_X1,
    CLIP_LENGTH,
    CLIP_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWN_TANGENT_STATIONS,
    DRAWING_PRECISION_BY_NAME,
    FAR_CREST_X,
    FLAT_FINGER_LENGTH,
    HOLE_CALLOUT_PRECISION,
    HOLE_DIA,
    HOLE_INSET,
    HOLE_Y,
    REFERENCE_DIMENSIONS,
    SCREW_RAIL_SLIT_RADIUS,
    SCREW_RAIL_WIDTH,
    SHEET_T,
    SPRING_RAIL_Y0,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_platen_clip"]
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

SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
ISO_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet m per model mm, 3:1

# Sheet layout (meters; the B-size field is x 0.0127..0.4191, y 0.0127..0.2667
# and the title block holds x >= 0.216, y <= 0.066).  The plan (250.5 x 34.1
# at 3:1) sits mid-sheet with its hole stations below and its bridge and
# length above; the profile, third-angle above it, hangs its four bow stations
# between the two and carries the developed finger and the bend radius above
# itself; the 2:1 isometric runs down-right in the free field
# bottom-centre, clear of the title block and of the plan's left-side texts,
# its note in the empty corner above it.
FRONT_CENTER = (0.200, 0.140)
TOP_CENTER = (0.200, 0.2405)
ISO_CENTER = (0.145, 0.058)
ISO_NOTE_XY = (0.160, 0.092)
# The profile's sheet-normal span (Top-plane s = -Z): the sheet's back face
# at s = -SHEET_T up to the bows' crests at s = ARCH_RISE.
_PROFILE_S_MID = (ARCH_RISE - SHEET_T) / 2.0


def _plan_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the plan or the profile (bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - CLIP_LENGTH / 2.0) * _S


def _plan_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the plan (bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - CLIP_WIDTH / 2.0) * _S


def _profile_y(s_mm: float) -> float:
    """Sheet Y of a Top-plane s (= -Z) point in the profile (bbox-centred)."""
    return TOP_CENTER[1] + (s_mm - _PROFILE_S_MID) * _S


LEFT_EDGE_X = _plan_x(0.0)
RIGHT_EDGE_X = _plan_x(CLIP_LENGTH)
BOTTOM_EDGE_Y = _plan_y(0.0)
TOP_EDGE_Y = _plan_y(CLIP_WIDTH)
PROFILE_BOTTOM_Y = _profile_y(-SHEET_T)
PROFILE_TOP_Y = _profile_y(ARCH_RISE)
HOLE_FAR_X = CLIP_LENGTH - HOLE_INSET

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (each text block's centre).  Plan: the two hole stations stack
# below it from the near end; above it the bridge's two ends and the overall
# length stack from the near end (smallest nearest), the slit's text offset
# beneath them.  Left of it, from the outer edge, the hole row's height, the
# screw rail's width and the overall width stand in their own columns
# (smallest nearest), the spring rail's width in a column of its own beside
# its span.  Each of those texts stands past its own span's end, so no
# dimension or extension line runs through it: the hole row's below the
# plan, the screw rail's below that, the spring rail's and the overall
# width's above the plan.  A vertical dimension's text stands left of its own
# dimension line on a shoulder that runs from the line to the text's far end
# (r5: the hole row's "2X 3.300" spans 21 mm), so each column is its text's
# right end: the hole row's widest line ("MHA-PD-02", ~23 mm) ends right of
# the screw rail's line, the hole row's three-line block stands under the
# near hole station's dimension line (r7 audit: at 0.112 that line,
# y ~0.1132, ran 2.7 mm into it), the spring rail's right of the overall
# width's text, and the overall width's
# inside the border.  The outer and the slit-side corner radii stand off the
# right end.
_BELOW_PLAN_ROWS = (0.116, 0.110)
# The length's text block carries the FORMED line above its value, so its
# dimension line runs a line lower than its centre (r8a audit: at 0.184 that
# line, y 0.1784, ran through the bridge end's text); its row stands that
# much higher.
_ABOVE_PLAN_ROWS = (0.172, 0.178, 0.189)
_HOLE_ROW_COLUMN = 0.0725
_RAIL_COLUMN = 0.042
_SPRING_RAIL_COLUMN = 0.066
_OVERALL_COLUMN = 0.030
FRONT_KEEP = {
    "LeftX": (_plan_x(HOLE_INSET / 2.0), _BELOW_PLAN_ROWS[0]),
    "RightX": (_plan_x(HOLE_FAR_X / 2.0), _BELOW_PLAN_ROWS[1]),
    "BridgeX0": (_plan_x(BRIDGE_X0 / 2.0), _ABOVE_PLAN_ROWS[0]),
    "BridgeX1": (_plan_x(BRIDGE_X1 / 2.0), _ABOVE_PLAN_ROWS[1]),
    "Length": (FRONT_CENTER[0], _ABOVE_PLAN_ROWS[2]),
    "LeftZ": (_HOLE_ROW_COLUMN, 0.1025),
    "RailWidth": (_RAIL_COLUMN, 0.0900),
    "SpringRailWidth": (_SPRING_RAIL_COLUMN, 0.1652),
    "OverallWidth": (_OVERALL_COLUMN, 0.1625),
    # The slit's dimension line stands inside the slit just short of its
    # rounded end at the bridge; its text is offset above the plan.
    "SlitWidth": (
        _plan_x(BRIDGE_X0) - 0.003,
        _plan_y(SCREW_RAIL_WIDTH + (SPRING_RAIL_Y0 - SCREW_RAIL_WIDTH) / 2.0),
    ),
    "EndR1": (0.345, 0.112),
    "SlitCornerR1": (0.355, 0.158),
}
# swDimensionArrowsSide_e.swDimArrowsInside (draw_fr_harmonic_base's form):
# left to the document's smart arrows, the near hole station's outside arrow
# tail ran left of the plan's near end, across the hole row's 2X 3.300
# dimension line on its way down to its text (reviewfix-r3 machinist
# review).  The station's 21.6 mm span holds its value and both arrows.
ARROWS_INSIDE = ("LeftX",)
_DIM_ARROWS_INSIDE = 0
# Profile: the four bow stations (where the bows leave and rejoin the flat)
# stack below it from the near end, smallest nearest, so no station's
# extension line crosses another's dimension line; each value stands just
# short of its own station, its arrows outside, clear of the previous
# station's outside arrow.  The developed finger stands above it, the bend
# radius above the far crown (its leader stops on the crown), the rise off the
# far end and the sheet off the near end.
_STATION_ROW_PITCH = 0.008
_STATION_ROWS = tuple(
    PROFILE_BOTTOM_Y - 0.0075 - _STATION_ROW_PITCH * index
    for index in range(len(DRAWN_TANGENT_STATIONS))
)
# A reference station's printed width ("(3.007)", r4's audit) and the air
# between its right end and its own station.
_STATION_CHAR_WIDTH = 0.00205
_STATION_TEXT_GAP = 0.001


def _station_text_x(name: str, x: float) -> float:
    text = f"({x / 25.4:.{DRAWING_PRECISION_BY_NAME[name]}f})".replace("(0.", "(.")
    return _plan_x(x) - _STATION_TEXT_GAP - len(text) * _STATION_CHAR_WIDTH / 2.0


TOP_KEEP = {
    **{
        name: (_station_text_x(name, x), row)
        for (name, x, _drive), row in zip(DRAWN_TANGENT_STATIONS, _STATION_ROWS)
    },
    "CrestRise": (RIGHT_EDGE_X + 0.008, _profile_y(ARCH_RISE / 2.0)),
    "FlatFinger": (_plan_x(BRIDGE_X0 - FLAT_FINGER_LENGTH / 2.0), 0.2555),
    "BendR5": (_plan_x(FAR_CREST_X), 0.256),
    "SheetDepth": (LEFT_EDGE_X - 0.008, _profile_y(-SHEET_T / 2.0)),
}
# Narrow linear dimensions whose text would sit between their own arrows:
# each moves off its line on a leader to clear field.
OFFSET_TEXT = {
    "SlitWidth": (0.150, 0.1645),
    "CrestRise": (RIGHT_EDGE_X + 0.024, 0.2515),
    "SheetDepth": (0.040, 0.2515),
}
# Native prefix and suffix per imported dimension: one printed size stands
# for its equal set ("2X", "6X") and the references print parenthesised, the
# count outside the parentheses.  A custom prefix replaces SolidWorks' own
# radius "R", so a radius's prefix carries it.
_COUNTS = {
    "LeftZ": "2X ",
    "SlitWidth": "2X ",
    "EndR1": "2X ",
    "SlitCornerR1": "2X ",
    "CrestRise": "2X ",
    "FlatFinger": "2X ",
    "BendR5": "6X ",
}
_RADII = frozenset({"EndR1", "SlitCornerR1", "BendR5"})
DIMENSION_AFFIXES = {
    name: (
        _COUNTS.get(name, "")
        + ("(" if name in REFERENCE_DIMENSIONS else "")
        + ("R" if name in _RADII else ""),
        ")" if name in REFERENCE_DIMENSIONS else "",
    )
    for name in sorted({*_COUNTS, *REFERENCE_DIMENSIONS})
}
# What each callout-bearing size is for: the hole row's .XXX height, with the
# hole stations, matches the platen's tap pattern (the holes float over the
# shanks by both patterns' zones only at .XXX; the r7 review read a bare .XXX
# row as over-spec).  The sheet is the stock's;
# the slit and the spring rail end in full rounds; the developed finger is
# measured along the bows from the bridge to the tip, not across the formed
# profile (r2 read it as a span); the rise is each bow's crest height.
DIMENSION_CALLOUTS = {
    "LeftZ": "MATCHES\nMHA-PD-02",  # pd-platen-clip RV-01
    "RailWidth": "SCREW RAIL",
    "SheetDepth": "SHEET STOCK",
    "SpringRailWidth": "FULL R ENDS",
    "SlitWidth": "SLIT, FULL R END",
    "FlatFinger": "DEVELOPED FINGER LENGTH\nBRIDGE TO TIP, ALONG BOWS",
    "CrestRise": "BOW RISE",
}
# The plan is the formed clip, not the blank (r7 review): the length says so,
# and that the spring tips stand flush with the rail ends there; the blank's
# fingers are the profile's developed length.
DIMENSION_CALLOUTS_ABOVE = {"Length": "FORMED, SPRING TIPS FLUSH WITH RAIL ENDS"}
# The bend radius's arrow stands outside its arc with no line on to the
# centre, which lies below the views: drawn to it, the leader crossed every
# station and the plan (r2).
RADIUS_LEADER_OUTSIDE = "BendR5"

# The callout rides the far hole, its leader dropping from the rim to text
# below the clip's right end, left of the outer radius's centre so it
# crosses neither that radius's line (r2) nor the overall length's
# extension line up the right end; it names the platen whose taps the .XXX
# hole pattern matches.
_DIAG = math.sqrt(0.5)
HOLE_R_SHEET = HOLE_DIA / 2.0 * _S
HOLE_EDGE_XY = (
    _plan_x(HOLE_FAR_X) + HOLE_R_SHEET * _DIAG,
    _plan_y(HOLE_Y) - HOLE_R_SHEET * _DIAG,
)
HOLE_CALLOUT_XY = (0.360, 0.098)
HOLE_CALLOUT_PROCESS = "PATTERN MATCHES MHA-PD-02\nDRILL"  # pd-platen-clip RV-01
# Where the slit-side corner radius lands (its leader target), for the layout
# tests: the screw rail's top-right corner.
SLIT_CORNER_XY = (
    _plan_x(CLIP_LENGTH - SCREW_RAIL_SLIT_RADIUS),
    _plan_y(SCREW_RAIL_WIDTH - SCREW_RAIL_SLIT_RADIUS),
)

_VIEW_KEEPS = {"front": FRONT_KEEP, "top": TOP_KEEP}
if set().union(*_VIEW_KEEPS.values()) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError(
        "the platen-clip views must keep exactly the marked dimensions"
    )


def _set_dimension_affixes(
    adapter: Any, annotations: list[Any], affixes: dict[str, tuple[str, str]]
) -> None:
    """Write a native prefix and suffix on named imported dimensions, read back."""
    remaining = dict(affixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        affix = remaining.pop(dimension_name(adapter, annotation), None)
        if affix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        prefix, suffix = affix
        display.SetText(1, prefix)  # swDimensionTextPrefix
        display.SetText(2, suffix)  # swDimensionTextSuffix
        written = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        if written != affix:
            raise RuntimeError(f"dimension affixes {affix!r} read back {written!r}")
    if remaining:
        raise RuntimeError(f"dimension affixes not applied: {sorted(remaining)}")


def _radius_leader_outside(adapter: Any, annotations: list[Any], name: str) -> None:
    """Put a radius's arrow outside its arc, with no line on to its centre.

    The arrow outside alone (swDimArrowsOutside) keeps the solid line from the
    arrow to the centre (draw_dt_pinion_arbor); with the solid leader off as
    well, the leader reaches the arc from its text and stops there.
    """
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    display.ArrowSide = 1  # swDimArrowsOutside
    display.SolidLeader = False
    if int(display.ArrowSide) != 1 or bool(display.SolidLeader):
        raise RuntimeError(f"{name} kept its leader to the arc's centre")


def _set_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    """Stand each ARROWS_INSIDE dimension's arrows inside its extension lines,
    read back (draw_fr_harmonic_base's _set_pads_arrows_inside)."""
    remaining = set(ARROWS_INSIDE)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        remaining.discard(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"{name} did not keep its arrows inside")
    if remaining:
        raise RuntimeError(f"no dimension to set arrows inside: {sorted(remaining)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open platen-clip source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Platen Clip Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen clip; manufacturing drawing; sheet brass spring; #2 holes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The through holes are fully defined by their callout; the formed sheet
    # seen edge-on needs no hidden lines.
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)
    # The plan reads as one flat outline: the bows' tangent lines and the
    # split between the bridge web and the spring rail read as cuts there
    # (r2); the profile locates the tangents.
    front.SetDisplayTangentEdges2(0)  # swTangentEdgesHidden
    if int(front.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError("failed to hide the plan's tangent edges")
    front.UpdateViewDisplayGeometry()
    # The overall width's and the profile references' owner sketches are
    # saved hidden (build_pd_platen_clip); each view shows its own to import
    # the dimensions.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_affixes(adapter, annotations, DIMENSION_AFFIXES)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    _radius_leader_outside(adapter, annotations, RADIUS_LEADER_OUTSIDE)
    _set_arrows_inside(adapter, annotations)
    offset_dimension_text(adapter, annotations, OFFSET_TEXT)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=HOLE_EDGE_XY,
        callout_xy=HOLE_CALLOUT_XY,
        label="platen-clip screw holes",
        process=HOLE_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        callout, HOLE_CALLOUT_PRECISION, label="platen-clip screw holes"
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    _telemetry.info("platen-clip sheet: views, dimensions and callouts placed")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Clip Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
