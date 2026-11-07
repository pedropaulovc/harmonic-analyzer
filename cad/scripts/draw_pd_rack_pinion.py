r"""Create the curated manufacturing drawing for the rack-pinion reduction disc (MHA-PD-06).

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``). Drawn 1:1;
the 150 physical teeth use the finite 48DP stock #1/reference-135 master.
The face view (``*Front``, the rear face) prints the controlling native
17-tooth actual-flank span, supported blank and bore with its reamed limits.
The bore's fit and the native #0-80 tap callout's assembly transfer are
numbered notes their callouts link (``pd_rack_pinion_callouts``); the span
and the blank link the GEAR DATA block, which names the mesh once with its
backlash acceptance (no bolt-circle position). The edge view prints the disc
thickness; its size envelope holds the faces parallel, so no frame prints.
Decimal-inch sheet (#290); the model keeps its millimetre nominals.
"""

from __future__ import annotations

import argparse
import math
import re
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
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import set_near_side_diameter
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _machinist_review_mode import MachinistReviewMode
from _native_axis_datum import add_native_axis_datum
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
import _telemetry
from paper_drive_stock_drawing import add_toothspace_callout, require_source_control
from pd_rack_pinion_callouts import (
    BORE_CALLOUT,
    DRAWING_NOTES,
    FACE_WIDTH_CALLOUT,
    GEAR_DATA_NOTE,
    MESH_CALLOUT,
    SPAN_CALLOUT,
    TAP_CALLOUT_QUALIFIER,
)
from pd_rack_pinion_spec import (
    CUTTER_NUMBER,
    CUTTER_REFERENCE_TEETH,
    DIAMETRAL_PITCH,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    OUTSIDE_DIA,
    PRESSURE_ANGLE_DEG,
    STOCK_PROFILE,
    TAP_CENTRES,
    TAP_DRILL_DIA,
    TEETH,
    TOOTH_SPACE_GAUGE_PIN_DIA_MM,
    TOOTH_SPACE_CALLOUT,
    TOOTH_SPACE_CALLOUT_PROPERTY,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_rack_pinion"]
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
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.220, 0.175)
RIGHT_CENTER = (0.320, 0.175)
ISO_CENTER = (0.383, 0.210)  # 0.388 clipped the zone border right by 1.4 mm
# The bore is a static seat (clamped to the MHA-PD-17 flange): no finish
# symbol (machinist review, rule 6).
# The GEAR DATA block is the sheet's (pd_rack_pinion_callouts.GEAR_DATA_NOTE:
# the part's cutting rows, the mate and its backlash acceptance), top-left.
GEAR_DATA_XY = (0.018, 0.262)
GEAR_DATA_CHAR_HEIGHT = 0.0022
# The numbered notes the bore and tap callouts link stand in the clear
# lower-left lane: under the tap callout's shoulder, left of the title
# block (x 0.216), at the document's note font (about 2.6 mm a character,
# 69 characters: x 0.020-0.200).
NOTES_XY = (0.020, 0.080)
# Three rows use the clear upper-right lane, above all physical gear views.
# x 0.262, not 0.230: run 12's leader from 0.230 down to the gap-18 flank
# (237.7, 201.5 mm) ran 3.6 mm through the ToothSpan text [228-245, 226-230
# mm]; from 0.262 it passes that text 3 mm to its right.
TOOTH_SPACE_CALLOUT_XY = (0.262, 0.260)
TOOTH_SPACE_CALLOUT_CHAR_HEIGHT = 0.0035  # standard note font
TOOTH_SPACE_GAP_INDEX = 18  # actual upper-right flank under the control-note lane

HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
REAR_FACE_X = RIGHT_CENTER[0] + FACE_WIDTH * VIEW_SCALE[0] / 2000.0

# The bore's and the blank's diameters print near-side: one arrow on the rim
# nearest the text, no line through the centre (machinist review: their
# native rim-to-rim lines, and the root REF's, which no longer prints, met
# the bore's leader at the bore).  Each leader leaves its block's lower
# corner on the part's side (SolidWorks' shoulder), so each block is placed
# by that corner; each *_TEXT_BLOCK is the block's estimated (width, height).
BORE_TEXT_BLOCK = (0.032, 0.021)
OD_TEXT_BLOCK = (0.035, 0.0138)
# The bore's text stands left of the face view, its shoulder 15° above the
# horizontal through the centre: its leader crosses the rim to the bore's
# 165° point, clear of datum A below and the 120° tap above.
_BORE_SHOULDER = (
    FRONT_CENTER[0] - 0.048,
    FRONT_CENTER[1] + 0.048 * math.tan(math.radians(15.0)),
)
# The blank's text stands below the face view, right of the tap's leader,
# its shoulder on the -80° ray, far enough out that the block clears the
# rim: its leader rises to the rim's -80° point, clear of the tap's leader
# (left of it) and far from the span's upper-right extension lines.
_OD_SHOULDER = (
    FRONT_CENTER[0] + 0.065 * math.cos(math.radians(-80.0)),
    FRONT_CENTER[1] + 0.065 * math.sin(math.radians(-80.0)),
)
NEAR_SIDE_DIAMETERS = ("BoreDia", "OutsideDia")
FRONT_KEEP = {
    "BoreDia": (
        _BORE_SHOULDER[0] - BORE_TEXT_BLOCK[0] / 2.0,
        _BORE_SHOULDER[1] + BORE_TEXT_BLOCK[1] / 2.0,
    ),
    "OutsideDia": (
        _OD_SHOULDER[0] + OD_TEXT_BLOCK[0] / 2.0,
        _OD_SHOULDER[1] + OD_TEXT_BLOCK[1] / 2.0,
    ),
    "ToothSpan": (FRONT_CENTER[0], FRONT_CENTER[1] + 0.050),
}
# Below the edge-on disc, clear of the isometric to the right;
# the whole text block (value and its ~.046-wide callout) stands right of
# the rear face's extension line, so neither extension line nor the
# dimension line strikes it (machinist review, r3: centred on the line, the
# callout straddled both extension lines).
RIGHT_KEEP = {
    "FaceWidth": (REAR_FACE_X + 0.028, RIGHT_CENTER[1] - HALF_OD - 0.012),
}
# The bore's process and its note link stand under its size, on the bore
# dimension's own leader: a separate fit-note leader converged on the small
# bore with the size, datum, diameter and finish leaders (machinist review,
# stack6: clarity).  The tip and the span link the GEAR DATA block, which
# names their one mate (rule 4); the span's above its value, clear of the rim
# below.  The thickness names the screw engagement its .XXX band holds.
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "OutsideDia": MESH_CALLOUT,
}
DIMENSION_CALLOUTS_ABOVE = {"ToothSpan": SPAN_CALLOUT}
RIGHT_DIMENSION_CALLOUTS = {"FaceWidth": FACE_WIDTH_CALLOUT}
# Lower-left of the face view, off the rim: the leader rises almost straight
# to the lower-left tap from the block's lower-right corner, left of the
# tap's centre, so it crosses neither the OD's line (lower right) nor datum
# A's leader (machinist review: from the block's right end past the tap, it
# crossed the OD's line).  The pick is on that tap's drill circle at 225°
# about its centre, off the centre-mark lines.  The face view is symmetric
# about its horizontal axis, so the sheet's lower-left tap is the model's
# x < 0 centre drawn under the axis whichever way the view mirrors.
# (19e33c6c2 let visible_circle_edge break the tie between the two x < 0
# taps on float noise: it took the upper one and the leader crossed the bore.)
# Four rows (the native drill and thread lines and TAP_CALLOUT_LINES): the
# block grows upward from the fixed shoulder, well under the tip circle; its
# widest line, the mouth breaks', sets its width.
TAP_TEXT_BLOCK = (0.100, 0.0215)
_TAP_SHOULDER = (FRONT_CENTER[0] - 0.015, FRONT_CENTER[1] - 0.085)
TAP_CALLOUT_XY = (
    _TAP_SHOULDER[0] - TAP_TEXT_BLOCK[0] / 2.0,
    _TAP_SHOULDER[1] + TAP_TEXT_BLOCK[1] / 2.0,
)
_TAP_X, _TAP_Y = min(TAP_CENTRES)  # either x < 0 centre: only |y| is drawn
TAP_SHEET_CENTER = (
    FRONT_CENTER[0] + _TAP_X * VIEW_SCALE[0] / 1000.0,
    FRONT_CENTER[1] - abs(_TAP_Y) * VIEW_SCALE[0] / 1000.0,
)
_TAP_SHEET_RADIUS = TAP_DRILL_DIA * VIEW_SCALE[0] / 2000.0
TAP_PICK = (
    TAP_SHEET_CENTER[0] + _TAP_SHEET_RADIUS * math.cos(math.radians(225.0)),
    TAP_SHEET_CENTER[1] + _TAP_SHEET_RADIUS * math.sin(math.radians(225.0)),
)


_THREAD_CLASS = re.compile(r"\s*-\s*<hw-threadclass>|<hw-threadclass>", re.IGNORECASE)


def tap_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Drop the thread class the title block's thread row already states, and
    append the mouth-break and transfer lines, in the one thread compartment."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(
            f"tap thread line is not in one callout part: {definitions!r}"
        )
    updated = dict(definitions)
    part = thread_parts[0]
    thread = _THREAD_CLASS.sub("", updated[part]).rstrip()
    updated[part] = f"{thread}\n{TAP_CALLOUT_QUALIFIER}"
    return updated


def _set_near_side_diameters(adapter: Any, annotations: list[Any]) -> None:
    """One arrow on the near rim, no line through the centre, for each of
    NEAR_SIDE_DIAMETERS."""
    for name in NEAR_SIDE_DIAMETERS:
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        set_near_side_diameter(matches[0], f"disc {name} near-side leader")
    rebuild_drawing(adapter, label="disc near-side diameter leaders")


def _set_tap_callout_text(display: Any) -> None:
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = tap_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    thread = [text for text in resolved.values() if "UNF" in text]
    if (
        persisted != updated
        or len(thread) != 1
        or not thread[0].rstrip().endswith(TAP_CALLOUT_QUALIFIER)
    ):
        raise RuntimeError(
            "rack-pinion tap callout lines did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


def _add_sheet_note(
    adapter: Any,
    text: str,
    xy: tuple[float, float],
    *,
    label: str,
    char_height: float | None = None,
) -> None:
    """Place one free note of the sheet's own text at ``xy`` (its top-left),
    at ``char_height`` when given, and read its text back."""
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(note, "INote")
    if char_height is not None:
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        text_format = annotation.GetTextFormat(0)
        if text_format is None:
            raise RuntimeError(f"the {label} note has no text format")
        text_format.CharHeight = float(char_height)
        if annotation.SetTextFormat(0, False, text_format) is not True:
            raise RuntimeError(f"failed to set the {label} note's text height")
    printed = str(note.GetText() or "").replace("\r\n", "\n")
    if printed != text:
        raise RuntimeError(f"the {label} note reads {printed!r}, not {text!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rack-pinion source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
    )
    require_source_control(
        properties[TOOTH_SPACE_CALLOUT_PROPERTY], TOOTH_SPACE_CALLOUT,
        label="rack-pinion tooth-space control",
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("pd-rack-pinion"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rack-Pinion Disc Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: (
                f"reducer disc; brass; {TEETH} physical teeth; {DIAMETRAL_PITCH:g}DP "
                f"PA{PRESSURE_ANGLE_DEG:g}; stock #{CUTTER_NUMBER}/ref{CUTTER_REFERENCE_TEETH}"
            ),
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="edge",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*front_annotations, *right_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(
        adapter, front_annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    set_dimension_callouts(adapter, right_annotations, RIGHT_DIMENSION_CALLOUTS)
    _set_near_side_diameters(adapter, front_annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to disc bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    add_native_axis_datum(
        adapter,
        front,
        entity=bore_edge,
        source_path=SOURCE,
        radius_m=BORE_DIA / 2000.0,
        datum="A",
        label="disc bore axis",
        shoulder=True,
        stability_tolerance_m=0.0001,
    )
    # The tooth-space control reads datum A above, the bore, at the shop row;
    # the assembled limit is MHA-PD-00's centring at the transfer step.
    add_toothspace_callout(
        adapter,
        front,
        profile=STOCK_PROFILE,
        actual_pin_diameter_mm=TOOTH_SPACE_GAUGE_PIN_DIA_MM,
        rotate_rad=math.pi / TEETH + TOOTH_SPACE_GAP_INDEX * 2.0 * math.pi / TEETH,
        axial_station_mm=FACE_WIDTH,
        property_name=TOOTH_SPACE_CALLOUT_PROPERTY,
        note_xy=TOOTH_SPACE_CALLOUT_XY,
    )

    # The native thread and drill ride the callout; the mouth breaks and the
    # link to the assembly-transfer note are the sheet's lines under it.
    tap_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=TAP_PICK,
        callout_xy=TAP_CALLOUT_XY,
        label="#0-80 transferred disc taps",
    )
    _set_tap_callout_text(tap_callout)
    set_hole_callout_precision(
        tap_callout, {"hw-thrutapdrldia": 3}, label="#0-80 transferred disc taps"
    )

    _add_sheet_note(
        adapter,
        GEAR_DATA_NOTE,
        GEAR_DATA_XY,
        label="gear data",
        char_height=GEAR_DATA_CHAR_HEIGHT,
    )
    _add_sheet_note(adapter, DRAWING_NOTES, NOTES_XY, label="numbered")
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rack-Pinion Disc Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "... Tapped Hole" note to the face view once
        # the tap carries a hole callout; the callout already states it.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
