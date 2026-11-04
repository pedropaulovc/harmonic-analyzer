"""Draw the two installed members of one NUIBBYED HGR15 rail kit (MHA-CH-06-TL-VN-83).

Sheet 1 is the configured purchased-part reference: four native views of
each member (``[1] RAIL`` and ``[2] CARRIAGE``), its installed quantity, the
kit as the purchase unit, and the carriage's note (the owner's kit
description and the fit-up play acceptance in MHA-CH-06-TL-00).

Sheet 2, RAIL RECEIPT, is the rail's receipt check. The listing states no
hole pattern, so the received rail is measured before the base bar is
tapped: every hole station is the Rail member's own native model dimension
from the -X end face (rule 10, baseline), each carrying the base bar's
receipt band as its native tolerance, the length a parenthesised reference.
The callout under the stations flags them as the note's check, and the note
says what to do when one is out of band. FRONT (the hole face) and TOP stand
at the sheet's 1:2, the RIGHT end profile at 2:1 so its raceway grooves read,
and the isometric at 1:4.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)

import _telemetry
import ch_rocker_arm_tl_vn_oblique_rail_kit_carriage_spec as carriage
import ch_rocker_arm_tl_vn_oblique_rail_kit_rail_spec as rail
from _com import _early_bound
from _drawing_common import read_required_properties
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheet_region import sheet_drawable_region
from _drawing_types import DRAWING_TEMPLATES
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import (
    _FOOTER_RIGHT,
    _NOTE_X,
    _NOTES_BOTTOM,
    _box,
    _center_marks_without_lines,
    _inside,
    _literal_note,
    _purchased_title_block,
    _rebuild,
    footer_top,
)
from _purchased_title_fit import fit_purchased_title_block
from _purchased_variant_drawing import (
    build_purchased_variant_drawing,
    configure_reference_views,
)
from _session import run_build


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_rail_kit"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source

# --- Sheet 1: the configured purchased-part reference ---------------------------
# The footer's ITEM row: the kit's style designations in plain text.
ITEM = "GENERIC HIWIN-STYLE HGR15 RAIL + HGH15CA CARRIAGE KIT, NUIBBYED"
# Literal, as the source-property census reads it; the guard below ties it
# to the member specs' configurations and item tags.
VARIANTS = (
    ("Rail", "[1] RAIL"),
    ("Carriage", "[2] CARRIAGE"),
)
if VARIANTS != (
    (rail.CONFIGURATION, f"{rail.ITEM_TAG} RAIL"),
    (carriage.CONFIGURATION, f"{carriage.ITEM_TAG} CARRIAGE"),
):
    raise AssertionError("the sheet's member labels drifted from the member specs")
PURCHASE_UNIT = "ONE KIT OF 2 RAILS AND 4 CARRIAGES"
RECEIPT_SHEET_NAME = "RAIL RECEIPT"
SHEET_NAMES = (RECEIPT_SHEET_NAME,)
if SHEET_NAMES.index(RECEIPT_SHEET_NAME) + 2 != rail.RECEIPT_SHEET:
    raise AssertionError("the rail's receipt citations name the wrong sheet")
GENERAL_TEXT = (
    f"REFERENCE VIEWS; {rail.ITEM_TAG} RECEIPT CHECK PER SHEET {rail.RECEIPT_SHEET}; "
    f"{carriage.ITEM_TAG} AS SUPPLIED."
)
# Sheet 1's footer note is the carriage's: the rail's prints on its sheet.
FOOTER_NOTES = carriage.DRAWING_NOTES
# The source's document-level member notes (build_..._rail_kit).
NOTE_PROPERTIES = {
    f"{rail.CONFIGURATION} Manufacturing Notes": rail.DRAWING_NOTES,
    f"{carriage.CONFIGURATION} Manufacturing Notes": carriage.DRAWING_NOTES,
}
SOURCE_PROPERTIES = ("Number", "Material Specification", "Finish", *NOTE_PROPERTIES)

# --- Sheet 2: the rail receipt check --------------------------------------------
# ASME B landscape 431.8 x 279.4, all in sheet metres. The border is 12.7 mm
# in; the title block fills x >= 215.9 mm below y = 65.1 mm; the receipt
# note's three lines top out at footer_top (70 mm).
#
# The 450 rail is 225 mm long at 1:2, the largest project scale whose
# length fits the drawable width with the profile beside it.
SHEET_SCALE = (1, 2)
# The 15 x 15 profile prints 30 mm square at 2:1 (7.5 mm at the sheet's 1:2,
# where its R1.62 raceway grooves blur).
PROFILE_SCALE = (2, 1)
# The isometric at 1:4: about 80 x 50 mm, upper right.
ISO_SCALE = (1, 4)


def _sheet_mm(scale: tuple[int, int]) -> float:
    """Sheet metres per model mm at ``scale``."""
    return scale[0] / scale[1] / 1000.0


# IView.GetOutline pads the model box by a fixed 5.59 mm a side
# (draw_vn_pen_marker, farm run e31912e0).
_OUTLINE_PAD = 0.00559
_CELL_SLACK = 0.002  # reserved cell beyond the expected outline, each side

# Model-box half-extents on the sheet. FRONT looks down on the hole face
# (length x width), TOP at the flank (length x height), RIGHT along the rail
# at the end profile (width x height). The isometric's box is the r9 sheet's
# 1:4 pictorial of the 440 rail (about 81 x 48 mm) read off its PDF; the 450
# rail adds about 2 mm along it, inside the slack.
_FRONT_HALF = (
    rail.LENGTH / 2.0 * _sheet_mm(SHEET_SCALE),
    rail.WIDTH / 2.0 * _sheet_mm(SHEET_SCALE),
)
_TOP_HALF = (
    rail.LENGTH / 2.0 * _sheet_mm(SHEET_SCALE),
    rail.HEIGHT / 2.0 * _sheet_mm(SHEET_SCALE),
)
_RIGHT_HALF = (
    rail.HEIGHT / 2.0 * _sheet_mm(PROFILE_SCALE),
    rail.WIDTH / 2.0 * _sheet_mm(PROFILE_SCALE),
)
_ISO_HALF = (0.045, 0.028)

# View centres. FRONT spans x 57.5..282.5 mm: its -X end stands 45 mm in
# from the border so the first station's text fits left of the end face. Its
# eight station rows and the FRONT caption stand under it, the length row
# over it; TOP stands over FRONT, in projection with it. RIGHT stands level
# with FRONT, right of its end; the isometric fills the upper right, clear of
# TOP's end and over RIGHT's caption.
FRONT_CENTER = (0.170, 0.140)
TOP_CENTER = (FRONT_CENTER[0], 0.195)
RIGHT_CENTER = (0.340, FRONT_CENTER[1])
ISO_CENTER = (0.345, 0.215)
VIEWS = (
    ("*Front", FRONT_CENTER, _FRONT_HALF, SHEET_SCALE),
    ("*Top", TOP_CENTER, _TOP_HALF, SHEET_SCALE),
    ("*Right", RIGHT_CENTER, _RIGHT_HALF, PROFILE_SCALE),
    ("*Isometric", ISO_CENTER, _ISO_HALF, ISO_SCALE),
)


def view_cell(
    center: tuple[float, float], half: tuple[float, float]
) -> tuple[float, float, float, float]:
    """The reserved box a view's native outline must stay inside."""
    reach_x = half[0] + _OUTLINE_PAD + _CELL_SLACK
    reach_y = half[1] + _OUTLINE_PAD + _CELL_SLACK
    return (
        center[0] - reach_x,
        center[1] - reach_y,
        center[0] + reach_x,
        center[1] + reach_y,
    )


# FRONT's receipt dimensions (rule 10, baseline from the -X end face): the
# shortest station in the row nearest the part, each longer one a row
# further out, so no extension line crosses a dimension line or a text.
# Each text's centre stands its row's drop under the rail's centreline,
# between its extension lines, except where ``TEXT_OUTSIDE_START`` moves it.
STATION_FIRST_DROP = 0.0135
STATION_ROW_PITCH = 0.0055
# The overall length, a reference, over the part.
LENGTH_ROW_RISE = 0.016
RECEIPT_DIMENSIONS = {
    name: (0.0, x, -(STATION_FIRST_DROP + index * STATION_ROW_PITCH))
    for index, (name, x) in enumerate(
        zip(rail.STATION_DIMENSIONS, rail.HOLE_X, strict=True)
    )
}
RECEIPT_DIMENSIONS["Length"] = (0.0, rail.LENGTH, LENGTH_ROW_RISE)
STATION_NOMINALS = dict(zip(rail.STATION_DIMENSIONS, rail.HOLE_X, strict=True))
# The first station spans 7.5 mm at 1:2, narrower than its "15.00 ±0.08"
# text (about 28 mm): the text stands outside the span, left of the -X end
# face, its centre this far (sheet metres) from the face's extension line.
TEXT_OUTSIDE_START = {rail.STATION_DIMENSIONS[0]: 0.016}
# Smart arrows put a short span's arrows outside, onto the end face's
# extension line; the 7.5 mm first span keeps two arrows inside.
ARROWS_INSIDE = (rail.STATION_DIMENSIONS[0],)
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
# The flag: under the outermost station row, naming the note's check.
RECEIPT_CALLOUTS = {rail.STATION_DIMENSIONS[-1]: rail.RECEIPT_CALLOUT}
_CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow
_TOL_SYMMETRIC = 4  # swTolType_e.swTolSYMMETRIC
FRONT_DIMENSION_PRECISION = {
    name: places
    for places_by_name in rail.DRAWING_PRECISION.values()
    for name, places in places_by_name.items()
}
# FRONT's caption tops out under the last station row and its callout line.
_FRONT_CAPTION_DROP = (
    STATION_FIRST_DROP + (len(rail.STATION_DIMENSIONS) - 1) * STATION_ROW_PITCH + 0.0095
)

# View captions (3 mm text, top edge at y, centred on the view): each under
# its view's outline, FRONT's under its dimensions.
_CAPTION_GAP = 0.0027
CAPTIONS = (
    ("FRONT", FRONT_CENTER[0], FRONT_CENTER[1] - _FRONT_CAPTION_DROP, SHEET_SCALE),
    (
        "TOP",
        TOP_CENTER[0],
        view_cell(TOP_CENTER, _TOP_HALF)[1] - _CAPTION_GAP,
        SHEET_SCALE,
    ),
    (
        "RIGHT",
        RIGHT_CENTER[0],
        view_cell(RIGHT_CENTER, _RIGHT_HALF)[1] - _CAPTION_GAP,
        PROFILE_SCALE,
    ),
    (
        "ISOMETRIC",
        ISO_CENTER[0],
        view_cell(ISO_CENTER, _ISO_HALF)[1] - _CAPTION_GAP,
        ISO_SCALE,
    ),
)
_CAPTION_HALF_WIDTH = 0.022  # "ISOMETRIC  1:4" at 3 mm is about 33 mm wide
# The member this sheet checks, in the top band; sheet 1 carries its quantity.
ITEM_LABEL = f"{VARIANTS[0][1]}: RECEIPT CHECK"
ITEM_LABEL_XY = (0.050, 0.262)
ITEM_LABEL_CELL = (0.045, 0.252, 0.200, 0.264)
# The receipt note in the footer's notes lines (rule 7's budget).
RECEIPT_NOTE_TOP = footer_top(rail.DRAWING_NOTES, label=PART_STEM)
RECEIPT_NOTE_CELL = (0.015, _NOTES_BOTTOM - 0.001, _FOOTER_RIGHT, RECEIPT_NOTE_TOP + 0.001)


def caption_text(label: str, scale: tuple[int, int]) -> str:
    return f"{label}  {scale[0]}:{scale[1]}"


def _center_outline(view: Any, name: str, center: tuple[float, float]) -> None:
    position = tuple(float(value) for value in view.Position)
    if len(position) != 2 or not all(map(math.isfinite, position)):
        raise RuntimeError(f"{name}: invalid native view position {position!r}")
    box = _box(view.GetOutline(), label=name)
    target = [
        position[0] + center[0] - (box[0] + box[2]) / 2,
        position[1] + center[1] - (box[1] + box[3]) / 2,
    ]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"{name}: failed to position the view")


def receipt_text_point(
    name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    offset: float,
) -> tuple[float, float]:
    """A receipt dimension's text point from the sheet points of the two
    stations it spans: centred between them, or ``TEXT_OUTSIDE_START`` left
    of the start, ``offset`` off the rail's centreline (negative: under it)."""
    y = (start[1] + end[1]) / 2.0 + offset
    outside = TEXT_OUTSIDE_START.get(name)
    if outside is not None:
        return start[0] - outside, y
    return (start[0] + end[0]) / 2.0, y


def _receipt_positions(adapter: Any, front: Any) -> dict[str, tuple[float, float]]:
    """Each receipt dimension's text point (``receipt_text_point``) from its
    model stations on the rail's centreline."""
    stations = sorted(
        {x for start, end, _ in RECEIPT_DIMENSIONS.values() for x in (start, end)}
    )
    points = dict(
        zip(
            stations,
            model_points_in_view(
                adapter,
                front,
                [(x / 1000.0, 0.0, 0.0) for x in stations],
                label="rail stations",
                names=[f"x {x:g}" for x in stations],
            ),
            strict=True,
        )
    )
    return {
        name: receipt_text_point(name, points[start], points[end], offset)
        for name, (start, end, offset) in RECEIPT_DIMENSIONS.items()
    }


def _display(annotation: Any) -> Any:
    specific = _early_bound(annotation, "IAnnotation").GetSpecificAnnotation()
    if specific is None:
        raise RuntimeError("receipt dimension has no display dimension")
    return _early_bound(specific, "IDisplayDimension")


def assert_receipt_controls(adapter: Any, annotations: list[Any]) -> None:
    """Every station reads its nominal, the receipt band at the receipt
    places and no reference brackets; the length reads parenthesised; the
    last station carries the flag. Never repairs native state."""
    found = {}
    for annotation in annotations:
        found[dimension_name(adapter, annotation)] = _display(annotation)
    if set(found) != set(RECEIPT_DIMENSIONS):
        raise RuntimeError(
            f"receipt dimensions {sorted(found)} != {sorted(RECEIPT_DIMENSIONS)}"
        )
    band = rail.RECEIPT_BAND / 1000.0
    for name, display in found.items():
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        brackets = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        callout = str(display.GetText(_CALLOUT_BELOW) or "").replace("\r\n", "\n")
        value = abs(float(dimension.SystemValue))
        if name == "Length":
            if (
                abs(value - rail.LENGTH / 1000.0) > 1e-8
                or brackets != ("(", ")")
                or callout
            ):
                raise RuntimeError(
                    f"rail length: value {value!r}, brackets {brackets!r}, "
                    f"callout {callout!r}"
                )
            continue
        if (
            abs(value - STATION_NOMINALS[name] / 1000.0) > 1e-8
            or int(tolerance.Type) != _TOL_SYMMETRIC
            or abs(float(tolerance.GetMaxValue()) - band) > 1e-9
            or abs(float(tolerance.GetMinValue()) + band) > 1e-9
            or int(display.GetPrimaryTolPrecision2()) != rail.RECEIPT_PLACES
            or "(" in brackets[0]
            or ")" in brackets[1]
            or callout != RECEIPT_CALLOUTS.get(name, "")
        ):
            raise RuntimeError(
                f"rail {name}: value {value!r} (nominal {STATION_NOMINALS[name]!r}), "
                f"tolerance type {int(tolerance.Type)} "
                f"{float(tolerance.GetMinValue())!r}..{float(tolerance.GetMaxValue())!r}"
                f" (band {band!r}), tol places {int(display.GetPrimaryTolPrecision2())}, "
                f"brackets {brackets!r}, callout {callout!r}"
            )
        if name in ARROWS_INSIDE and int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"rail {name} did not keep its arrows inside")


@_telemetry.traced("drawing.rail_receipt_dimensions")
def _receipt_dimensions(adapter: Any, front: Any) -> list[Any]:
    """Import the rail's station and length dimensions into FRONT."""
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=_receipt_positions(adapter, front),
        view_label="rail hole face",
        dimensions_by_feature=rail.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, FRONT_DIMENSION_PRECISION)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name == "Length":
            set_reference_dimension(adapter, annotation, label=name)
            continue
        if name in ARROWS_INSIDE:
            display = _display(annotation)
            display.ArrowSide = _DIM_ARROWS_INSIDE
    set_dimension_callouts(adapter, annotations, RECEIPT_CALLOUTS, location="below")
    assert_receipt_controls(adapter, annotations)
    return annotations


def _source_properties(model: Any) -> dict[str, str]:
    """The source's sheet-2 facts, its member notes the specs' own."""
    properties = read_required_properties(
        model, SOURCE_PROPERTIES, required=SOURCE_PROPERTIES
    )
    for name, expected in NOTE_PROPERTIES.items():
        if properties[name].replace("\r\n", "\n") != expected:
            raise RuntimeError(f"{PART_STEM}: stale source note {name!r}")
    return properties


def append_rail_receipt_sheet(adapter: Any) -> tuple[Callable[[], None], ...]:
    """Author RAIL RECEIPT: the Rail member's views, stations and note."""
    draw = adapter.currentModel
    document = _early_bound(draw, "IDrawingDoc")
    if not document.ActivateSheet(RECEIPT_SHEET_NAME):
        raise RuntimeError("failed to activate the rail RECEIPT sheet")
    sheet = _early_bound(document.GetCurrentSheet(), "ISheet")

    views = {}
    with _telemetry.span("drawing.rail_views"):
        for name, center, _, scale in VIEWS:
            view = _early_bound(
                place_view(adapter, str(SOURCE), name, *center, scale=scale), "IView"
            )
            views[name] = view
        configure_reference_views(adapter, rail.CONFIGURATION, list(views.values()))
        # A prism with plain holes: no hidden edge names a feature.
        for view in views.values():
            set_hidden_lines_removed(adapter, view)
        # Later insertions may drift the sheet scale; pin each view explicitly.
        for name, _, _, scale in VIEWS:
            views[name].UseSheetScale = 0
            views[name].ScaleRatio = double_array([float(value) for value in scale])
        _rebuild(draw, phase="rail view extents")
        for name, center, _, _ in VIEWS:
            _center_outline(views[name], name, center)
        _rebuild(draw, phase="centre rail views")
        # Before any annotation: GetOutline grows to take a view's own.
        for name, center, half, _ in VIEWS:
            box = _box(views[name].GetOutline(), label=name)
            if not _inside(box, view_cell(center, half)):
                raise RuntimeError(f"{name}: rail view leaves its cell: {box!r}")
        _center_marks_without_lines(
            [views[name] for name, _, _, _ in VIEWS],
            tuple((name, center, None) for name, center, _, _ in VIEWS),
        )
    front = views["*Front"]
    sheet.CustomPropertyView = view_name(adapter, front)
    properties = _source_properties(_early_bound(front.ReferencedDocument, "IModelDoc2"))

    annotations = _receipt_dimensions(adapter, front)

    notes = []
    with _telemetry.span("drawing.rail_annotations"):
        for label, x, y, scale in CAPTIONS:
            text = caption_text(label, scale)
            note = _literal_note(adapter, text, x, y)
            bounds = _box(note.GetExtent(), label=text, kind="note")
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            if not annotation.SetPosition(2 * x - (bounds[0] + bounds[2]) / 2, y, 0.0):
                raise RuntimeError(f"{text}: failed to centre view caption")
            box = (
                x - _CAPTION_HALF_WIDTH,
                y - 0.006,
                x + _CAPTION_HALF_WIDTH,
                y + 0.001,
            )
            notes.append((note, text, text, box))
        note = _literal_note(adapter, ITEM_LABEL, *ITEM_LABEL_XY)
        notes.append((note, ITEM_LABEL, ITEM_LABEL, ITEM_LABEL_CELL))
        note = _literal_note(adapter, rail.DRAWING_NOTES, _NOTE_X, RECEIPT_NOTE_TOP)
        notes.append((note, rail.DRAWING_NOTES, rail.DRAWING_NOTES, RECEIPT_NOTE_CELL))
        title_notes = _purchased_title_block(
            adapter,
            draw,
            material=properties["Material Specification"],
            finish=properties["Finish"],
            material_property="Material Specification",
        )
    _rebuild(draw, phase="rail receipt notes")
    title_fit = fit_purchased_title_block(adapter, spec=SPEC)

    def settled() -> None:
        if not document.ActivateSheet(RECEIPT_SHEET_NAME):
            raise RuntimeError("failed to activate the rail RECEIPT sheet for readback")
        template = DRAWING_TEMPLATES[SPEC.layout]
        region = sheet_drawable_region(
            adapter, sheet, width=template.width_m, height=template.height_m
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        for name, _, _, scale in VIEWS:
            view = views[name]
            if (
                str(view.ReferencedConfiguration) != rail.CONFIGURATION
                or Path(view.GetReferencedModelName()).resolve() != SOURCE.resolve()
                or tuple(view.ScaleRatio) != tuple(float(value) for value in scale)
            ):
                raise RuntimeError(f"{name}: rail receipt view source/member/scale changed")
            box = _box(view.GetOutline(), label=name)
            if not _inside(box, border):
                raise RuntimeError(f"{name}: rail view leaves the border: {box!r}")
        _source_properties(_early_bound(front.ReferencedDocument, "IModelDoc2"))
        assert_receipt_controls(adapter, annotations)
        for note, linked_text, resolved_text in title_notes:
            if (
                note.PropertyLinkedText != linked_text
                or note.GetText().replace("\r\n", "\n") != resolved_text
            ):
                raise RuntimeError(
                    "rail receipt title-block property did not resolve from its "
                    f"expected source: {linked_text!r}"
                )
        for note, linked_text, resolved_text, cell in notes:
            actual_link = note.PropertyLinkedText
            actual_text = note.GetText().replace("\r\n", "\n")
            if actual_link != linked_text or actual_text != resolved_text:
                raise RuntimeError(
                    f"rail note readback mismatch: expected link={linked_text!r}, "
                    f"actual link={actual_link!r}, expected text={resolved_text!r}, "
                    f"actual text={actual_text!r}"
                )
            box = _box(note.GetExtent(), label=linked_text, kind="note")
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"rail note leaves its reserved space/border: {linked_text!r}: {box!r}"
                )
        title_fit()

    settled()
    return (settled,)


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_variant_drawing(
        adapter,
        SPEC,
        variants=VARIANTS,
        item=ITEM,
        purchase_unit=PURCHASE_UNIT,
        general_text=GENERAL_TEXT,
        notes=FOOTER_NOTES,
        additional_sheet_scales={RECEIPT_SHEET_NAME: SHEET_SCALE},
        append_sheets=append_rail_receipt_sheet,
        additional_sheets_title="Rail Receipt Check",
        title_fit=True,
        unit=part_drawing_unit(PART_STEM),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
