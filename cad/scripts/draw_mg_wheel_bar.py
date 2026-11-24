r"""Create the curated machinist drawing for the magnifying-wheel bar.

A .43 x .374 steel bar, 9.2 long (decimal-inch sheet), carrying the wheel axle
and the pen-hanger strap.
Four bores run along the depth (front-back), so the FRONT view (looking down the
bore axis) shows them as circles: the drilled axle bore, 2x #8 clamp-screw
clearance holes flanking the column and 1x #8 pen-hanger hole at the free end.
The bar length + section, the axle bore's Ø + station from the left end, the
screw holes' stations from the left end and the bore row's distance from the
top face ride the imported model marks (the row and its stations on the
part-hidden BoreRowReference sketch, shown in the front view); the depth is
added across the right-view section; the screw holes' sizes ride native
Hole Wizard callouts.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_wheel_bar.py mg-wheel-bar
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_edges import scan_view_edges
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _printed_limits import drilled_limits, limits
from _session import run_build
import _telemetry
from _column_clamp_interface import BAR_DEPTH
import mg_wheel_bar_callouts as callouts
from mg_wheel_bar_spec import (
    AXLE_BORE_DIA,
    AXLE_BORE_STATION,
    AXLE_BORE_X,
    BAR_DEPTH_BAND,
    BAR_LENGTH,
    BAR_SIDE,
    BAR_TOP_ABOVE_ROW,
    BORE_ROW_FROM_TOP,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_X,
    CLAMP_STATIONS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HANGER_STATION,
    LEFT_END_X,
    PEN_HANGER_HOLE_DIA,
    SCREW_HOLE_X,
    UNIT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["mg_wheel_bar"]
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

SHEET_SCALE = (1.0, 1.0)
# The front view stands far enough right that the hanger row's drop, off the
# bar's left end, clears the frame.
FRONT_CENTER = (0.161, 0.175)
# The end view stands far enough right that the height's callout runs
# between it and the bar end.
RIGHT_CENTER = (0.340, 0.175)
# The isometric falls from its upper-left end toward the title block; that
# end stands about 15 mm right of the front view's right-end extension line,
# the lower-right end about 5 mm over the title block.
ISO_CENTER = (0.336, 0.098)

_HALF_LEN = BAR_LENGTH * SHEET_SCALE[0] / 2000.0
LEFT_END = FRONT_CENTER[0] - _HALF_LEN
RIGHT_END = FRONT_CENTER[0] + _HALF_LEN
AXLE_BORE_SHEET_X = FRONT_CENTER[0] + AXLE_BORE_X * SHEET_SCALE[0] / 1000.0
# The view centres the bar's outline.
_BAR_BOTTOM = FRONT_CENTER[1] - BAR_SIDE * SHEET_SCALE[1] / 2000.0
_BAR_TOP = FRONT_CENTER[1] + BAR_SIDE * SHEET_SCALE[1] / 2000.0


def _sheet_x(model_x: float) -> float:
    return FRONT_CENTER[0] + model_x * SHEET_SCALE[0] / 1000.0


# Every station is a baseline dimension from the left end, stacked under the
# bar shortest first (8 mm rows, text y), the overall length outermost, so no
# dimension line crosses another's extension line. The rows stay below the bar
# because the hole callouts' leaders come down from above.
FRONT_KEEP = {
    # The hanger's 5 mm span is too short for its text: the value sits right
    # of the hole's extension line, ending short of the axle bore's extension
    # line.
    "HangerStation": (LEFT_END + 0.030, _BAR_BOTTOM - 0.010),
    "AxleBoreStation": ((LEFT_END + AXLE_BORE_SHEET_X) / 2.0, _BAR_BOTTOM - 0.030),
    "ClampStation1": (LEFT_END + 0.082, _BAR_BOTTOM - 0.038),
    "ClampStation2": (LEFT_END + 0.152, _BAR_BOTTOM - 0.046),
    "Length": (FRONT_CENTER[0], _BAR_BOTTOM - 0.054),
    # The bar height and the row's drop from the top face off the right end,
    # in the open sheet between the bar and the end view: off the left end
    # the height's text sat on the border's zone letter and frame line. Both
    # share the top face's extension line: the shorter row nearer the bar,
    # its value above the top face; the height's line outside it, its text
    # under the bottom face. The one row height, measured at the outer clamp
    # hole, locates all four holes on their shared centreline.
    "Side": (RIGHT_END + 0.040, _BAR_BOTTOM - 0.014),
    "ClampRowFromTop": (RIGHT_END + 0.021, _BAR_TOP + 0.015),
    # The drilled Ø up and right of the bore, the bond lines standing clear
    # of the bar.
    "AxleBoreDia": (AXLE_BORE_SHEET_X + 0.035, FRONT_CENTER[1] + 0.042),
}
# The bar depth (the extrude's model dimension at the title block's .XXX, a
# three-place size naming its stack) under the end view, its text right of the
# extension lines: the callout is wider than the 9.5.
RIGHT_KEEP = {
    "BarDepth": (
        RIGHT_CENTER[0] + BAR_DEPTH / 2000.0 + 0.034,
        RIGHT_CENTER[1] - BAR_SIDE / 2000.0 - 0.014,
    ),
}
# The native Hole Wizard callouts stand above the bar, the hanger's left of
# the drilled bore's Ø, the clamps' between that and the row's text.
HANGER_CALLOUT_XY = (_sheet_x(SCREW_HOLE_X) + 0.025, FRONT_CENTER[1] + 0.035)
CLAMP_CALLOUT_XY = (_sheet_x(CLAMP_HOLE_X[0]) + 0.010, FRONT_CENTER[1] + 0.035)
# Each clearance hole's native drill size prints .XXX.
HOLE_CALLOUT_PRECISION = {"hw-diam": 3}
# The clamp screw line's drill-wander shortfall at the worst corner, 0.0527
# (test_mg_wheel_bar_drawing derives it from the clamp's own modules, which
# stay out of this part's recipe), stated rounded up as a plain fact (rule
# 20): mg-wheel-bar RV-08. Numbered, the clamp holes' callout pointing to it
# (mg_wheel_bar_callouts.CLAMP_HOLE_CALLOUT). Under the front view's
# dimensions, left of the title block.
SCREW_LINE_NOTE = (
    "1. EACH .196 HOLE TO ITS MHA-SH-02 TAP:\n"
    "   OFFSET UP TO .003 OVER #8 SCREW CLEARANCE."
)
SCREW_LINE_NOTE_XY = (0.040, 0.095)
# The sheet's one manufacturing note, for the feature export (export_features
# reads DRAWING_NOTES from the drawing when neither a notes module nor the
# spec declares them, so the part's recipe does not re-key on it).
DRAWING_NOTES = SCREW_LINE_NOTE
# The one native through extent reads DRILL THRU ALL, after the size
# (rule 26: size, then process, then depth).
DRILL_EXTENT = "DRILL <hw-thru>"
# Each mate prints under its value, authored on the part's dimension
# (mg_wheel_bar_callouts): the bore's press fit on the axle and the depth's
# axle-end stack.
DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (build_mg_wheel_bar, mg_wheel_bar_geom: the bar along X centred on the
# origin, the left end at LEFT_END_X; Y up with the bore row at y = 0 and the
# top face BAR_TOP_ABOVE_ROW above it; Z through the depth, the front face at
# -BAR_DEPTH/2, every bore entering it along +Z). Stations run from the left
# end and the row from the top face, as printed; bands are the title block's
# rows at the printed places, the bore's and the depth's their native ones.
# The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_mg_wheel_bar"
_GEOM = "mg_wheel_bar_geom"
_FRAME = ((_GEOM, "LEFT_END_X"), (_GEOM, "BAR_TOP_ABOVE_ROW"), ("_column_clamp_interface", "BAR_DEPTH"))
_TOP_Y = BAR_TOP_ABOVE_ROW
_BOTTOM_Y = BAR_TOP_ABOVE_ROW - BAR_SIDE
_FRONT_Z = -BAR_DEPTH / 2.0
_INTO_FRONT = (0.0, 0.0, 1.0)


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    model_sources=(*_FRAME, (_GEOM, "BAR_LENGTH"), (_GEOM, "BAR_SIDE")),
    precision_sources=("DRAWING_PRECISION", (_SELF, "DRAWING_PRECISION_BY_NAME")),
)
requirement(
    "left_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -LEFT_END_X),),
    requirements=("plane",),
    fields={"plane": (_plane("x", LEFT_END_X), _FRAME)},
)
# The length 9.2 (FRONT_KEEP "Length"), from the left end.
requirement(
    "right_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), -LEFT_END_X),),
    requirements=("length",),
    fields={
        "plane": (_plane("x", -LEFT_END_X), (*_FRAME, (_GEOM, "BAR_LENGTH"))),
        "length": (
            limits(BAR_LENGTH, _P["Length"], unit=UNIT),
            ((_GEOM, "BAR_LENGTH"), (_GEOM, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "length_nominal": (BAR_LENGTH, ((_GEOM, "BAR_LENGTH"),)),
        "length_from": ("left_end", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"length": _P["Length"]},
)
# The top face: the bore row hangs from it (FRONT_KEEP "ClampRowFromTop").
requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), _TOP_Y),),
    requirements=("plane",),
    fields={"plane": (_plane("y", _TOP_Y), _FRAME)},
)
# The height .43 from the top face (FRONT_KEEP "Side").
requirement(
    "bottom_face",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), -_BOTTOM_Y),),
    requirements=("height",),
    fields={
        "plane": (_plane("y", _BOTTOM_Y), (*_FRAME, (_GEOM, "BAR_SIDE"))),
        "height": (
            limits(BAR_SIDE, _P["Side"], unit=UNIT),
            ((_GEOM, "BAR_SIDE"), (_GEOM, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "height_nominal": (BAR_SIDE, ((_GEOM, "BAR_SIDE"),)),
        "height_from": ("top_face", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"height": _P["Side"]},
)
requirement(
    "front_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -_FRONT_Z),),
    requirements=("plane",),
    fields={"plane": (_plane("z", _FRONT_Z), _FRAME)},
)
# The depth .374 at .XXX naming its axle-end stack (RIGHT_KEEP "BarDepth").
requirement(
    "back_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), -_FRONT_Z),),
    requirements=("depth",),
    fields={
        "plane": (_plane("z", -_FRONT_Z), _FRAME),
        "depth": (
            limits(BAR_DEPTH, _P["BarDepth"], BAR_DEPTH_BAND),
            (
                ("_column_clamp_interface", "BAR_DEPTH"),
                (_GEOM, "BAR_DEPTH_BAND"),
                (_SELF, "RIGHT_KEEP"),
            ),
        ),
        "depth_nominal": (BAR_DEPTH, (("_column_clamp_interface", "BAR_DEPTH"),)),
        "depth_from": ("front_face", ((_SELF, "RIGHT_KEEP"),)),
        "callout": (
            callouts.BAR_DEPTH_CALLOUT,
            (("mg_wheel_bar_callouts", "BAR_DEPTH_CALLOUT"),),
        ),
    },
    precision={"depth": _P["BarDepth"]},
)
# The bore row, every hole on it .197 from the top face (FRONT_KEEP
# "ClampRowFromTop": printed once, at the clamp pair, for all four holes).
_ROW = (
    limits(BORE_ROW_FROM_TOP, _P["ClampRowFromTop"], unit=UNIT),
    ("BORE_ROW_FROM_TOP", (_GEOM, "UNIT"), (_SELF, "FRONT_KEEP")),
)
_ROW_FIELDS: dict[str, Any] = {
    "height": _ROW,
    "height_nominal": (BORE_ROW_FROM_TOP, ("BORE_ROW_FROM_TOP",)),
    "height_from": ("top_face", ((_SELF, "FRONT_KEEP"),)),
}
# The drilled axle bore: 3/16 DRILL THRU under the DRILLED HOLES row (owner
# ruling 2026-11-24, fit audit question 18; FRONT_KEEP "AxleBoreDia"), the
# MHA-MG-07 axle bonded in it, its least wall; 2.40 from the left end
# (FRONT_KEEP "AxleBoreStation").
requirement(
    "axle_bore",
    kind="hole",
    faces=(CylinderFace(AXLE_BORE_DIA),),
    requirements=("dia", "thru", "process", "station", "height"),
    fields={
        "at": ([AXLE_BORE_X, 0.0, _FRONT_Z], ((_GEOM, "AXLE_BORE_X"), *_FRAME)),
        "axis": (_INTO_FRONT, _FRAME),
        "dia": (
            drilled_limits(AXLE_BORE_DIA, _P["AxleBoreDia"], unit=UNIT),
            ((_GEOM, "AXLE_BORE_DIA"), (_GEOM, "AXLE_BORE_BAND"), (_SELF, "FRONT_KEEP")),
        ),
        "nominal_dia": (AXLE_BORE_DIA, ((_GEOM, "AXLE_BORE_DIA"),)),
        "thru": (True, (("mg_wheel_bar_callouts", "AXLE_BORE_CALLOUT"),)),
        "process": ("drill", (("mg_wheel_bar_callouts", "AXLE_BORE_CALLOUT"),)),
        "callout": (
            callouts.AXLE_BORE_CALLOUT,
            (("mg_wheel_bar_callouts", "AXLE_BORE_CALLOUT"),),
        ),
        "station": (
            limits(AXLE_BORE_STATION, _P["AxleBoreStation"], unit=UNIT),
            ("AXLE_BORE_STATION", (_GEOM, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "station_nominal": (AXLE_BORE_STATION, ("AXLE_BORE_STATION",)),
        "station_from": ("left_end", ((_SELF, "FRONT_KEEP"),)),
        **_ROW_FIELDS,
    },
    precision={
        "dia": _P["AxleBoreDia"],
        "station": _P["AxleBoreStation"],
        "height": _P["ClampRowFromTop"],
    },
)
# The pen-hanger hole: native Ø.180 DRILL THRU ALL (HOLE_CALLOUT_PRECISION),
# its least end wall; .20 from the left end (FRONT_KEEP "HangerStation").
requirement(
    "hanger_hole",
    kind="hole",
    faces=(CylinderFace(PEN_HANGER_HOLE_DIA),),
    requirements=("dia", "thru", "station", "height"),
    fields={
        "at": ([SCREW_HOLE_X, 0.0, _FRONT_Z], ((_GEOM, "SCREW_HOLE_X"), *_FRAME)),
        "axis": (_INTO_FRONT, _FRAME),
        "dia": (
            drilled_limits(PEN_HANGER_HOLE_DIA, HOLE_CALLOUT_PRECISION["hw-diam"], unit=UNIT),
            ((_GEOM, "PEN_HANGER_HOLE_DIA"), (_GEOM, "UNIT"), (_SELF, "HOLE_CALLOUT_PRECISION")),
        ),
        "nominal_dia": (PEN_HANGER_HOLE_DIA, ((_GEOM, "PEN_HANGER_HOLE_DIA"),)),
        "thru": (True, ((_SELF, "DRILL_EXTENT"),)),
        "process": ("drill", ((_SELF, "DRILL_EXTENT"),)),
        "callout": (
            callouts.HANGER_HOLE_CALLOUT,
            (("mg_wheel_bar_callouts", "HANGER_HOLE_CALLOUT"),),
        ),
        "station": (
            limits(HANGER_STATION, _P["HangerStation"], unit=UNIT),
            ((_GEOM, "HANGER_STATION"), (_GEOM, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "station_nominal": (HANGER_STATION, ((_GEOM, "HANGER_STATION"),)),
        "station_from": ("left_end", ((_SELF, "FRONT_KEEP"),)),
        **_ROW_FIELDS,
    },
    precision={
        "dia": HOLE_CALLOUT_PRECISION["hw-diam"],
        "station": _P["HangerStation"],
        "height": _P["ClampRowFromTop"],
    },
)
# The two clamp-screw holes: native 2X Ø.196 DRILL THRU ALL, clearing the
# MHA-SH-02 taps (note 1), their least wall; 7.382 and 8.760 from the left
# end at the title block's .XXX (FRONT_KEEP "ClampStation1/2").
for _index, (_x, _station) in enumerate(zip(CLAMP_HOLE_X, CLAMP_STATIONS, strict=True), 1):
    _name = f"ClampStation{_index}"
    requirement(
        f"clamp_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(CLAMP_HOLE_DIA, contains_x_mm=_x),),
        requirements=("dia", "thru", "station", "height"),
        fields={
            "at": ([_x, 0.0, _FRONT_Z], ((_GEOM, "CLAMP_HOLE_X"), *_FRAME)),
            "axis": (_INTO_FRONT, _FRAME),
            "dia": (
                drilled_limits(CLAMP_HOLE_DIA, HOLE_CALLOUT_PRECISION["hw-diam"], unit=UNIT),
                ((_GEOM, "CLAMP_HOLE_DIA"), (_GEOM, "UNIT"), (_SELF, "HOLE_CALLOUT_PRECISION")),
            ),
            "nominal_dia": (CLAMP_HOLE_DIA, ((_GEOM, "CLAMP_HOLE_DIA"),)),
            "thru": (True, ((_SELF, "DRILL_EXTENT"),)),
            "process": ("drill", ((_SELF, "DRILL_EXTENT"),)),
            "callout": (
                callouts.CLAMP_HOLE_CALLOUT,
                (("mg_wheel_bar_callouts", "CLAMP_HOLE_CALLOUT"),),
            ),
            "note": (SCREW_LINE_NOTE, ((_SELF, "SCREW_LINE_NOTE"),)),
            "station": (
                limits(_station, _P[_name], unit=UNIT),
                ((_GEOM, "CLAMP_STATIONS"), (_GEOM, "UNIT"), "CLAMP_POSITION_BAND", (_SELF, "FRONT_KEEP")),
            ),
            "station_nominal": (_station, ((_GEOM, "CLAMP_STATIONS"),)),
            "station_from": ("left_end", ((_SELF, "FRONT_KEEP"),)),
            **_ROW_FIELDS,
        },
        precision={
            "dia": HOLE_CALLOUT_PRECISION["hw-diam"],
            "station": _P[_name],
            "height": _P["ClampRowFromTop"],
        },
    )


@_telemetry.traced("drawing.mg_wheel_bar.part_authored_text")
def _assert_part_authored_text(adapter: Any, annotations: list[Any]) -> None:
    """Every imported dimension prints the text lanes its part authored.

    The mates print nowhere else on the sheet, so a lost lane must fail the
    drawing.  Read-only: text set from the sheet would write through to the
    source part (#1942).
    """
    wanted = callouts.authored_by_name()
    displays: dict[str, list[Any]] = {name: [] for name in wanted}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in displays:
            displays[name].append(
                _early_bound(
                    _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                    "IDisplayDimension",
                )
            )
    counts = {name: len(found) for name, found in displays.items() if len(found) != 1}
    if counts:
        raise RuntimeError(f"authored dimensions not printed exactly once: {counts!r}")
    printed = {
        (name, lane): str(displays[name][0].GetText(lane) or "")
        for name, lanes in wanted.items()
        for lane in lanes
    }
    wrong = {
        key: text
        for key, text in printed.items()
        if callouts.callout_rows(text) != callouts.callout_rows(wanted[key[0]][key[1]])
    }
    if wrong:
        raise RuntimeError(
            f"imported dimension text differs from the part's: {wrong!r}"
        )


@_telemetry.traced("drawing.mg_wheel_bar.hole_callout_below", label_param="label")
def _add_below_rows(display: Any, rows: str, *, label: str) -> None:
    """Hang ``rows`` under a native hole callout (a drawing annotation, not an
    imported model dimension), after any native below text.

    swDimensionTextCalloutBelowDefinition (8) pairs with the writable
    swDimensionTextCalloutBelow (4); the prefix, size and depth definitions
    stay untouched, so the Hole Wizard variables stay associative
    (draw_ch_channel_lever._name_hole_mate)."""
    display = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7)}
    below = str(display.GetText(8) or "").rstrip()
    updated = f"{below}\n{rows}" if below else rows
    display.SetText(callouts.CALLOUT_BELOW, updated)
    # The definition (8) holds any native variable verbatim; the resolved
    # text (4) holds its value, so only the appended literal rows must end it.
    definition = callouts.callout_rows(str(display.GetText(8) or ""))
    resolved = callouts.callout_rows(str(display.GetText(callouts.CALLOUT_BELOW) or ""))
    appended = callouts.callout_rows(rows)
    if (
        definition != callouts.callout_rows(updated)
        or resolved[-len(appended) :] != appended
        or any(
            str(display.GetText(part) or "") != text
            for part, text in definitions.items()
        )
    ):
        raise RuntimeError(
            f"{label}: callout rows or native definitions did not persist: "
            f"definition={definition!r} resolved={resolved!r}"
        )


@_telemetry.traced("drawing.mg_wheel_bar.drill_extent", label_param="label")
def _drill_after_size(display: Any, *, label: str) -> None:
    """Put DRILL between the native size and its through extent.

    Only the one ``<hw-thru>`` token's definition text changes, so the
    quantity, diameter and extent stay Hole Wizard variables
    (draw_fr_top_frame._set_hanger_hole_callout)."""
    display = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    native = "\n".join(definitions.values())
    if (
        native.count("<hw-diam>") != 1
        or native.count("<hw-thru>") != 1
        or "DRILL" in native
        or native.index("<hw-diam>") > native.index("<hw-thru>")
    ):
        raise RuntimeError(f"{label}: unexpected native hole callout {definitions!r}")
    updated = {
        part: text.replace("<hw-thru>", DRILL_EXTENT) for part, text in definitions.items()
    }
    for definition, writable in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition] != definitions[definition]:
            display.SetText(writable, updated[definition])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = "\n".join(str(display.GetText(part) or "") for part in (1, 2, 3, 4))
    if persisted != updated or resolved.count("DRILL") != 1:
        raise RuntimeError(
            f"{label}: drill extent did not persist: {persisted!r}, resolved {resolved!r}"
        )


def _hole_rims(front: Any) -> list[Any]:
    """The hanger hole's and the first clamp hole's rims, picked as entities:
    the front view looks onto the model's +Z (back) face."""
    edges = scan_view_edges(front, label="wheel-bar front")
    return [
        edges.circle_at(
            (x, 0.0, BAR_DEPTH / 2.0),
            dia / 2.0,
            axis=(0.0, 0.0, 1.0),
            label=label,
            radius_tol_mm=0.025,
        ).edge
        for x, dia, label in (
            (SCREW_HOLE_X, PEN_HANGER_HOLE_DIA, "pen-hanger hole rim"),
            (CLAMP_HOLE_X[0], CLAMP_HOLE_DIA, "first clamp hole rim"),
        )
    ]


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-bar source", adapter.open_model(str(SOURCE)))
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
            0: "Wheel Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "wheel bar; steel support bar; drilled axle bore; clearance holes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)
    # Front carries the hole circles; the end view's hidden bores only repeat
    # the THRU callouts, so it is drawn hidden-lines-removed.
    set_hidden_lines_visible(adapter, front)
    set_hidden_lines_removed(adapter, right)

    # The front view shows the part-hidden BoreRowReference sketch that owns
    # the row's drop from the top face and the screw-hole stations
    # (_drawing_hidden_sketches).
    annotations = [
        *hidden_sketches.curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    _assert_part_authored_text(adapter, annotations)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to wheel-bar bores")

    hanger_rim, clamp_rim = _hole_rims(front)
    for edge, callout_xy, label, rows in (
        (
            hanger_rim,
            HANGER_CALLOUT_XY,
            "pen-hanger clearance hole",
            callouts.HANGER_HOLE_CALLOUT,
        ),
        (
            clamp_rim,
            CLAMP_CALLOUT_XY,
            "column-clamp clearance holes",
            callouts.CLAMP_HOLE_CALLOUT,
        ),
    ):
        callout = add_native_hole_callout(
            adapter,
            front,
            edge=edge,
            callout_xy=callout_xy,
            label=label,
        )
        _drill_after_size(callout, label=label)
        set_hole_callout_precision(callout, HOLE_CALLOUT_PRECISION, label=label)
        _add_below_rows(callout, rows, label=label)

    # Beside the isometric, over its lower-right run (the view falls from
    # its upper-left end): clear of the title block below and of the depth's
    # callout above.
    add_property_linked_note(adapter, "Isometric View Note", 0.335, 0.125)
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")
    if drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot leave view context for the screw-line note")
    # mg-wheel-bar RV-08 (SCREW_LINE_NOTE).
    if add_note(adapter, SCREW_LINE_NOTE, *SCREW_LINE_NOTE_XY) is None:
        raise RuntimeError("screw-line note: InsertNote failed")

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Wheel Bar Manufacturing Drawing",
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
