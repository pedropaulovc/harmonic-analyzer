"""Create the purchased-reference sheet for the HIWIN HGR15R linear rail cut to 440 (MHA-CH-06-TL-VN-50).

The rail is bought cut to length with a special-order hole pattern, so its
receipt check is dimensioned on the hole face: the cut length, the first
hole from the -X end face and one pitch for all six gaps. Each is the rail
part's own native model dimension, parenthesised as reference (the rail is
used as supplied), and the note only says the pattern is a special order.

The shared purchased-part builder lays four views by itself and prints no
dimension, so this sheet keeps its title block, captions and footer (as
``draw_pn_vn_pen_marker`` does) and lays its own views: FRONT (the hole face)
and TOP at the sheet's 1:2, the RIGHT end profile at 2:1 so its raceway
grooves read, and the isometric at 1:4.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    iter_views,
    place_view,
)

import _telemetry
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
from _drawing_dimensions import assert_imported_precision, set_reference_dimension
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _drawing_sheet_region import sheet_drawable_region
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _purchased_fastener_drawing import (
    _box,
    _fit_number,
    _center_marks_without_lines,
    _inside,
    _literal_note,
    _purchased_title_block,
    _rebuild,
    add_purchased_footer,
)
from _session import run_build
from ch_rocker_arm_tl_vn_oblique_rail_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HEIGHT,
    HOLE_PITCH_CALLOUT,
    HOLE_X,
    LENGTH,
    WIDTH,
)


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_rail"]
PART_STEM = SPEC.artifact_stem

# The source part's properties this sheet prints: the title block's
# material and finish, the summary's title, the footer's supplier/SKU lines
# and its note. finalize_drawing proves the tolerance block and revision.
SOURCE_PROPERTIES = (
    "Number",
    "Title",
    "Material Specification",
    "Finish",
    "Supplier",
    "Supplier SKUs",
    "Manufacturing Notes",
)
# The footer's ITEM row: the catalogue designation in plain text. The cut
# length is the FRONT view's dimension, not the item's.
ITEM = "HIWIN HGR15R LINEAR GUIDEWAY RAIL, CUT TO LENGTH"

# Sheet maths, ASME B landscape 431.8 x 279.4, all in sheet metres. The
# border is 12.7 mm in; the title block fills x >= 215.9 mm below y = 65.1
# mm; the purchased footer's one note line tops out at 61 mm.
#
# The 440 rail is 220 mm long at 1:2, the largest project scale whose
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
# 1:4 pictorial (about 81 x 48 mm) read off its PDF, with slack.
_FRONT_HALF = (
    LENGTH / 2.0 * _sheet_mm(SHEET_SCALE),
    WIDTH / 2.0 * _sheet_mm(SHEET_SCALE),
)
_TOP_HALF = (
    LENGTH / 2.0 * _sheet_mm(SHEET_SCALE),
    HEIGHT / 2.0 * _sheet_mm(SHEET_SCALE),
)
_RIGHT_HALF = (
    HEIGHT / 2.0 * _sheet_mm(PROFILE_SCALE),
    WIDTH / 2.0 * _sheet_mm(PROFILE_SCALE),
)
_ISO_HALF = (0.045, 0.028)

# View centres. FRONT spans x 40..260 mm with its two dimension rows and its
# caption under it (caption top 89 mm, 28 mm over the footer's note). TOP
# stands over FRONT, in projection with it. RIGHT stands level with FRONT,
# 44 mm right of its end; the isometric fills the upper right, clear of the
# border and over RIGHT's caption.
FRONT_CENTER = (0.150, 0.130)
TOP_CENTER = (FRONT_CENTER[0], 0.195)
RIGHT_CENTER = (0.330, FRONT_CENTER[1])
ISO_CENTER = (0.335, 0.215)
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


# FRONT's dimensions, under the rail (rule 10: from the -X end face): the
# end distance and the one pitch in the row nearest the part, the cut
# length in the row under it. Each text's centre stands this far under the
# rail's centreline, between its extension lines.
HOLE_ROW_DROP = 0.016
LENGTH_ROW_DROP = 0.029
# The printed pitch is the first gap's (HOLE_X[0] .. HOLE_X[1]).
RECEIPT_DIMENSIONS = {
    "HoleEnd": (0.0, HOLE_X[0], HOLE_ROW_DROP),
    "HolePitch": (HOLE_X[0], HOLE_X[1], HOLE_ROW_DROP),
    "Length": (0.0, LENGTH, LENGTH_ROW_DROP),
}
DIMENSION_PREFIXES = {"HolePitch": HOLE_PITCH_CALLOUT}
# Smart arrows put the 20 mm and 30 mm spans' arrows outside, where the end
# distance's and the pitch's met at the first hole (r1); both spans hold their
# value and arrows inside.
ARROWS_INSIDE = ("HoleEnd", "HolePitch")
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
FRONT_DIMENSION_PRECISION = {
    name: places
    for places_by_name in DRAWING_PRECISION.values()
    for name, places in places_by_name.items()
}
# FRONT's caption tops out under the length row's text (about 3.5 mm tall).
_FRONT_CAPTION_DROP = LENGTH_ROW_DROP + 0.010

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


def _receipt_positions(adapter: Any, front: Any) -> dict[str, tuple[float, float]]:
    """Each receipt dimension's text point: centred between the two model
    stations it spans on the rail's centreline, its row's drop under it."""
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
        name: (
            (points[start][0] + points[end][0]) / 2.0,
            (points[start][1] + points[end][1]) / 2.0 - drop,
        )
        for name, (start, end, drop) in RECEIPT_DIMENSIONS.items()
    }


@_telemetry.traced("drawing.rail_receipt_dimensions")
def _receipt_dimensions(adapter: Any, front: Any) -> list[Any]:
    """Import the order's three model dimensions into FRONT, as reference."""
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=_receipt_positions(adapter, front),
        view_label="rail hole face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, FRONT_DIMENSION_PRECISION)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        display = set_reference_dimension(adapter, annotation, label=name)
        if name in ARROWS_INSIDE:
            display.ArrowSide = _DIM_ARROWS_INSIDE
            if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
                raise RuntimeError(f"{name} did not keep its arrows inside")
        prefix = DIMENSION_PREFIXES.get(name)
        if prefix is None:
            continue
        # swDimensionTextPrefix: the count before the parenthesised value.
        display.SetText(1, f"{prefix} (")
        if str(display.GetText(1) or "") != f"{prefix} (":
            raise RuntimeError(f"{name}: the {prefix} count did not persist")
    return annotations


async def build(adapter: Any) -> dict[str, str]:
    source = SPEC.source
    if SPEC.source_kind != "part" or not source.is_file():
        raise FileNotFoundError(f"source purchased part is missing: {source}")
    check(f"open {PART_STEM} source", await adapter.open_model(str(source)))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if Path(model.GetPathName()).resolve() != source.resolve():
        raise RuntimeError(f"opened purchased part is not {source}")
    properties = read_required_properties(
        model, SOURCE_PROPERTIES, required=SOURCE_PROPERTIES
    )

    draw, sheet = new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE)
    title_block_notes = _purchased_title_block(
        adapter,
        draw,
        material=properties["Material Specification"],
        finish=properties["Finish"],
        material_property="Material Specification",
    )
    title = f"{properties['Title']} — Purchased Part Reference Drawing"
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: title,
            1: "Harmonic Analyzer purchased-part identification; reference only",
            2: "Harmonic Analyzer Project",
            3: f"{PART_STEM}; {properties['Supplier']}; {properties['Supplier SKUs']}",
            4: "Front, Top, Right and Isometric; reference receipt dimensions, no PMI",
        },
    )

    views = {}
    with _telemetry.span("drawing.rail_views"):
        for name, center, _, scale in VIEWS:
            view = _early_bound(
                place_view(adapter, str(source), name, *center, scale=scale), "IView"
            )
            # A prism with plain holes: no hidden edge names a feature.
            set_hidden_lines_removed(adapter, view)
            views[name] = view
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

    _receipt_dimensions(adapter, views["*Front"])

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
        notes.extend(
            add_purchased_footer(
                adapter,
                draw,
                properties,
                item=ITEM,
                notes=properties["Manufacturing Notes"],
                label=PART_STEM,
            )
        )

    with _telemetry.span("drawing.rail_native_contract"):
        _rebuild(draw, phase="rail notes and final layout")
        for note, linked_text, resolved_text in title_block_notes:
            if (
                note.PropertyLinkedText != linked_text
                or note.GetText() != resolved_text
            ):
                raise RuntimeError(
                    "purchased title-block property did not resolve from its "
                    f"expected source: {linked_text!r}"
                )
        actual = list(iter_views(adapter))
        orientations = tuple(view.GetOrientationName() for view in actual)
        if len(actual) != len(VIEWS) or set(orientations) != {
            name for name, _, _, _ in VIEWS
        }:
            raise RuntimeError(f"rail sheet must have its four views: {orientations!r}")
        template = DRAWING_TEMPLATES[SPEC.layout]
        region = sheet_drawable_region(
            adapter, sheet, width=template.width_m, height=template.height_m
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        for name, _, _, scale in VIEWS:
            view = views[name]
            if Path(view.GetReferencedModelName()).resolve() != source.resolve():
                raise RuntimeError(f"{name}: rail view references the wrong model")
            if tuple(view.ScaleRatio) != tuple(float(value) for value in scale):
                raise RuntimeError(f"{name}: final rail view scale changed")
            box = _box(view.GetOutline(), label=name)
            if not _inside(box, border):
                raise RuntimeError(f"{name}: rail view leaves the border: {box!r}")
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
        # The 18-character registry number overruns the template's DWG. NO.
        # cell into REV; fit it there, measured, once its link resolves.
        number_fit = _fit_number(
            adapter, draw, layout=SPEC.layout, number=properties["Number"]
        )

    paths = SPEC.outputs
    return await finalize_drawing(
        adapter,
        DrawingOutputs(slddrw=paths["slddrw"], pdf=paths["pdf"], png=paths["png"]),
        layout=SPEC.layout,
        pdf_title=title,
        scale=SHEET_SCALE,
        settled_checks=(number_fit,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
