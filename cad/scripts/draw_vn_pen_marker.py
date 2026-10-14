"""Create the four-view purchased-reference sheet for the Sharpie Mini pen marker (MHA-VN-060).

Identification only: the marker as installed (uncapped), its stock and
ordering item number, and its fitting note on a leader to the grip band; no
fabrication dimensions.

The shared purchased-part builder picks the largest scale that fits its
fastener cells. For this marker that is 1:2: the 1:1 isometric outline
(79.5 mm) overran its 79 mm cell, and every view shrank to 35 mm tall on an
empty sheet. Its installation note also printed as a general note with no
leader. So this sheet keeps the builder's title block, captions and footer,
but lays out its own views at 1:1 in third-angle alignment. The part's
Manufacturing Notes go on one leadered note from the grip band in the FRONT
view, so they print once, on the feature they name.
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import iter_views, place_view

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
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note, property_link
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _drawing_sheet_region import sheet_drawable_region
from _drawing_view_display import set_hidden_lines_removed
from _purchased_fastener_drawing import (
    _box,
    _inside,
    _literal_note,
    _purchased_title_block,
    _rebuild,
)
from _session import run_build
from vn_pen_marker_spec import (
    BARREL_DIA,
    BARREL_END_Y,
    BARREL_START_Y,
    MAX_DIA,
    OVERALL_LENGTH,
)


SPEC = DRAWINGS_BY_NAME["vn_pen_marker"]
PART_STEM = SPEC.artifact_stem

# The source part's properties this sheet prints: the title block's number,
# title, material and finish, the footer's stock/supplier/SKU lines and the
# grip note. finalize_drawing proves the tolerance block and revision.
SOURCE_PROPERTIES = (
    "Number",
    "Title",
    "Material Specification",
    "Finish",
    "Stock Name",
    "Supplier",
    "Supplier SKUs",
    "Manufacturing Notes",
)

# Sheet maths, ASME B landscape 431.8 x 279.4, all in sheet metres.
#
# Every view sits at the sheet scale, so the title block's SCALE field says
# it and the captions carry no scale. The free field is the border (12.7 mm
# all round) above the purchased footer (its notes reach y = 73 mm) and the
# title block (x >= 215.9 mm, y <= 65.1 mm), read from farm run e31912e0's PNG.
# That leaves 194 mm of height. At 2:1 the FRONT outline (154.0 mm) and the
# TOP outline (35.8 mm) alone stack to 190 mm, and their two captions add
# about 18 mm. So 1:1 is the largest project scale that keeps TOP above FRONT.
SHEET_SCALE = (1, 1)
_MODEL_M = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
# IView.GetOutline pads the model box by a fixed 5.59 mm a side: at 1:2 the
# FRONT outline read 17.33 x 46.88 mm over a 6.15 x 35.70 mm model box (farm
# run e31912e0, layout audit).
_OUTLINE_PAD = 0.00559
_CELL_SLACK = 0.002  # reserved cell beyond the expected outline, each side

# Model box half-extents at the sheet scale. FRONT and RIGHT show the revolved
# marker's side, MAX_DIA wide and OVERALL_LENGTH tall with the nib at the
# bottom. TOP looks down the axis at a MAX_DIA circle. The isometric's 1:1 box
# is the 1:2 audit's 8.69 x 34.17 mm doubled.
_SIDE_HALF = (MAX_DIA / 2.0 * _MODEL_M, OVERALL_LENGTH / 2.0 * _MODEL_M)
_END_HALF = (MAX_DIA / 2.0 * _MODEL_M, MAX_DIA / 2.0 * _MODEL_M)
_ISO_HALF = (0.00869, 0.03417)

# View centres. GetOutline is centred on the model box, so each view's outline
# is centred here. TOP shares FRONT's x and RIGHT shares FRONT's y.
#   FRONT model box x 173.9..186.1, y 109.3..180.7 mm (outline 103.7..186.3).
#   TOP circle y 208.9..221.1 mm: 28 mm above FRONT, outline gap 17 mm.
#   RIGHT model box x 248.9..261.1 mm: 63 mm right of FRONT.
#   ISOMETRIC x 336.3..353.7, y 135.8..204.2 mm (outline right edge 359.3,
#   60 mm inside the border; outline bottom 130.3, 65 mm above the title block).
FRONT_CENTER = (0.180, 0.145)
TOP_CENTER = (FRONT_CENTER[0], 0.215)
RIGHT_CENTER = (0.255, FRONT_CENTER[1])
ISO_CENTER = (0.345, 0.170)
VIEWS = (
    ("*Front", FRONT_CENTER, _SIDE_HALF),
    ("*Top", TOP_CENTER, _END_HALF),
    ("*Right", RIGHT_CENTER, _SIDE_HALF),
    ("*Isometric", ISO_CENTER, _ISO_HALF),
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


# View captions (3 mm text, top edge at y, centred on the view): FRONT and RIGHT
# 4.7 mm below their outlines (y 94.7..99.0 mm), the ISOMETRIC caption 4.8 mm
# below its outline, and TOP 5.4 mm above its outline, 30 mm under the border.
_SIDE_CAPTION_Y = view_cell(FRONT_CENTER, _SIDE_HALF)[1] - 0.0027
CAPTIONS = (
    ("FRONT", FRONT_CENTER[0], _SIDE_CAPTION_Y),
    ("TOP", TOP_CENTER[0], view_cell(TOP_CENTER, _END_HALF)[3] + 0.0077),
    ("RIGHT", RIGHT_CENTER[0], _SIDE_CAPTION_Y),
    ("ISOMETRIC", ISO_CENTER[0], view_cell(ISO_CENTER, _ISO_HALF)[1] - 0.0028),
)
_CAPTION_HALF_WIDTH = 0.020  # "ISOMETRIC" at 3 mm is about 20 mm wide

# The grip note's leader tip: on the grip band's left silhouette in FRONT,
# halfway along the band. The nib sits at the bottom of the model box.
GRIP_TIP = (
    FRONT_CENTER[0] - BARREL_DIA / 2.0 * _MODEL_M,
    FRONT_CENTER[1] - _SIDE_HALF[1] + (BARREL_START_Y + BARREL_END_Y) / 2.0 * _MODEL_M,
)
# Its text (3.5 mm, top-left at GRIP_NOTE_XY) sits left of FRONT. It has three
# lines of at most GRIP_NOTE_WIDTH characters, about 77 mm x 14 mm at the
# repo's widest 2.75 mm per character (pen-hanger audit). So it spans
# x 60..137 mm, y 136..150 mm, 31 mm clear of FRONT's outline. The leader
# drops about 42 mm to the tip.
GRIP_NOTE_WIDTH = 28
GRIP_NOTE_XY = (0.060, 0.150)
GRIP_NOTE_BOX = (0.055, 0.130, 0.160, 0.155)


def grip_note(manufacturing_notes: str) -> str:
    """The part's installation note, broken after its first clause for the leader."""
    head, tail = manufacturing_notes.split("; ", 1)
    return "\n".join((f"{head};", *textwrap.wrap(tail, GRIP_NOTE_WIDTH)))


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
    grip_text = grip_note(properties["Manufacturing Notes"])

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
            4: "Front, Top, Right and Isometric; no fabrication dimensions or PMI",
        },
    )

    views = {}
    with _telemetry.span("drawing.marker_views"):
        for name, center, _ in VIEWS:
            view = _early_bound(
                place_view(adapter, str(source), name, *center, scale=SHEET_SCALE),
                "IView",
            )
            # A solid of revolution: no hidden edge names a feature.
            set_hidden_lines_removed(adapter, view)
            views[name] = view
        # Later insertions may drift the sheet scale; pin each view explicitly.
        for view in views.values():
            view.UseSheetScale = 0
            view.ScaleRatio = double_array([float(value) for value in SHEET_SCALE])
        _rebuild(draw, phase="marker view extents")
        for name, center, _ in VIEWS:
            _center_outline(views[name], name, center)
        _rebuild(draw, phase="centre marker views")

    notes = []
    with _telemetry.span("drawing.marker_annotations"):
        for label, x, y in CAPTIONS:
            note = _literal_note(adapter, label, x, y)
            bounds = _box(note.GetExtent(), label=label, kind="note")
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            if not annotation.SetPosition(2 * x - (bounds[0] + bounds[2]) / 2, y, 0.0):
                raise RuntimeError(f"{label}: failed to centre view caption")
            box = (
                x - _CAPTION_HALF_WIDTH,
                y - 0.006,
                x + _CAPTION_HALF_WIDTH,
                y + 0.001,
            )
            notes.append((note, label, label, box))
        text = (
            "PURCHASED PART / REFERENCE GEOMETRY\n"
            "ORDER BY SUPPLIER SKU; INSTALL PER NOTES WHERE SHOWN.\n"
            "GENERAL TOLERANCES AND EDGE-BREAK NOTES DO NOT APPLY."
        )
        note = _literal_note(adapter, text, 0.018, 0.072)
        notes.append((note, text, text, (0.015, 0.057, 0.260, 0.073)))
        for name, y, label in (
            ("Stock Name", 0.050, "STOCK:"),
            ("Supplier", 0.038, "SUPPLIER:"),
            ("Supplier SKUs", 0.026, "SKU:"),
        ):
            label_note = _literal_note(adapter, label, 0.018, y)
            notes.append(
                (label_note, label, label, (0.015, y - 0.007, 0.050, y + 0.001))
            )
            note = add_property_linked_note(adapter, name, 0.052, y, char_height=0.003)
            notes.append(
                (
                    _early_bound(note, "INote"),
                    property_link(name),
                    properties[name],
                    (0.050, y - 0.007, 0.260, y + 0.001),
                )
            )
        # Rule 7: the fitting requirement is flagged on the grip it names.
        note = add_leader_note(
            adapter,
            grip_text,
            text_xy=GRIP_NOTE_XY,
            attach_xy=GRIP_TIP,
            label="marker grip in the v-block groove",
            view=views["*Front"],
        )
        notes.append((_early_bound(note, "INote"), grip_text, grip_text, GRIP_NOTE_BOX))

    with _telemetry.span("drawing.marker_native_contract"):
        _rebuild(draw, phase="marker notes and final layout")
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
            name for name, _, _ in VIEWS
        }:
            raise RuntimeError(
                f"marker sheet must have its four views: {orientations!r}"
            )
        template = DRAWING_TEMPLATES[SPEC.layout]
        region = sheet_drawable_region(
            adapter, sheet, width=template.width_m, height=template.height_m
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        scale = tuple(float(value) for value in SHEET_SCALE)
        for name, center, half in VIEWS:
            view = views[name]
            if Path(view.GetReferencedModelName()).resolve() != source.resolve():
                raise RuntimeError(f"{name}: marker view references the wrong model")
            if tuple(view.ScaleRatio) != scale:
                raise RuntimeError(f"{name}: final marker view scale changed")
            box = _box(view.GetOutline(), label=name)
            if not _inside(box, view_cell(center, half)) or not _inside(box, border):
                raise RuntimeError(
                    f"{name}: marker view leaves its cell/border: {box!r}"
                )
        for note, linked_text, resolved_text, cell in notes:
            actual_link = note.PropertyLinkedText
            actual_text = note.GetText().replace("\r\n", "\n")
            if actual_link != linked_text or actual_text != resolved_text:
                raise RuntimeError(
                    f"marker note readback mismatch: expected link={linked_text!r}, "
                    f"actual link={actual_link!r}, expected text={resolved_text!r}, "
                    f"actual text={actual_text!r}"
                )
            box = _box(note.GetExtent(), label=linked_text, kind="note")
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"marker note leaves its reserved space/border: {linked_text!r}: {box!r}"
                )

    paths = SPEC.outputs
    return await finalize_drawing(
        adapter,
        DrawingOutputs(slddrw=paths["slddrw"], pdf=paths["pdf"], png=paths["png"]),
        layout=SPEC.layout,
        pdf_title=title,
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
