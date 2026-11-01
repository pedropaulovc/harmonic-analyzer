r"""Create the drawing for the oblique-trammel jig's feed nut (MHA-CH-06-TL-27).

One part, one off. A 1-1/4 x 3/4 x .40 brass block at 2:1: the face view
(*Front, looking at the screw heads' face) carries everything but the length:
the hole stations over it (the first hole from the bore, the pair's .680 with
its mate, text clear above its line), the bore's .63 and the stock width
under it, the bore's .38 and the stock height left of it, the 2X Ø.144
callout up-right on the +X hole and the Tr8x2 bore callout right of it, each
leader clear of every extension line; the side view (*Right), projected right
of the face, carries the faced length over it; the shaded isometric rides top
right at 1:1. No datums (drawing-guidelines.md rule 5).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_feed_nut.py ch-rocker-arm-tl-oblique-feed-nut
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
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
from _drawing_dimensions import assert_imported_precision
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _supplier_dimensions import supplier_reference_dimension
from ch_rocker_arm_tl_oblique_feed_nut_spec import (
    BORE_X,
    BORE_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEIGHT,
    HOLE_X,
    LENGTH,
    STOCK_CALLOUTS,
    STOCK_FRACTION_DENOMINATORS,
    WIDTH,
)

MACHINIST_REVIEW = MachinistReviewMode.LEARN

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_feed_nut"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)

# The 31.75 x 19.05 face at 2:1 spans sheet x 118.25..181.75, y 155.95..194.05
# about FACE_CENTER; the bore lands at 150.25, 175.25, the holes at x 133.0 and
# 167.5. The side view projects right of it on the same centreline, clear of
# the bore callout (x 192..236, y 155..165) left of it. The 1:1
# isometric and its note stand top right, above the title block.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FACE_CENTER = (0.150, 0.175)
SIDE_CENTER = (0.255, FACE_CENTER[1])
ISO_CENTER = (0.345, 0.225)
ISO_NOTE_XY = (0.320, 0.190)

# Every text position is a MODEL point (mm) off the part, mapped onto its
# view at run time (TL-28's sheet). A keep point is its text block's centre;
# SolidWorks hangs the dimension line about TEXT_DROP under a one-line block,
# TWO_LINE_DROP under a two-line one and THREE_LINE_DROP under a three-line
# one (TL-28's readbacks, one 5.8 mm row pitch apart).
TEXT_DROP = 2.7 / _S
TWO_LINE_DROP = 5.6 / _S
THREE_LINE_DROP = 8.5 / _S
TEXT_GAP = 2.5 / _S
FIRST_LANE = 8.0 / _S
GLYPH = 2.75 / _S
ROW_PITCH = 5.56 / _S


def text_half(text: str) -> float:
    """Half the widest line of ``text`` (model mm)."""
    return max(len(line) for line in text.split("\n")) * GLYPH / 2.0


def text_half_high(rows: int) -> float:
    """Half a ``rows``-line block's height (model mm), 3.5 mm glyphs."""
    return ((rows - 1) * ROW_PITCH + 3.5 / _S) / 2.0


# Over the face, nearest first: the first hole from the bore, then the pair
# with its mate row; each text stands over its own line, so no extension line
# reaches it.
_OFFSET_LINE = HEIGHT + FIRST_LANE
# (r1 audit: one TEXT_GAP left the rows 3.51 mm apart, under one text height.)
_SPACING_LINE = _OFFSET_LINE + TEXT_DROP + text_half_high(1) + 1.5 * TEXT_GAP
# Under the face: the bore's station, then the stock width, each text between
# its extension lines, over its own line. The width's text stands right of
# the bore's extension line, which ends at the station's line just over it
# (review of farm run 20261101T175835750Z: centred, the line struck "1").
_BORE_X_LINE = -FIRST_LANE
_WIDTH_LINE = _BORE_X_LINE - TEXT_GAP - THREE_LINE_DROP - text_half_high(3)
# Left of the face: the bore's height, then the stock height outboard.
_BORE_Y_LINE = -FIRST_LANE
_BORE_Y_TEXT = _BORE_Y_LINE - TEXT_GAP - text_half(".38")
_HEIGHT_LINE = _BORE_Y_TEXT - text_half(".38") - TEXT_GAP
_HEIGHT_TEXT = _HEIGHT_LINE - TEXT_GAP - text_half(STOCK_CALLOUTS["NutHeight"])
FACE_KEEP: dict[str, tuple[float, float, float]] = {
    "HoleOffset": ((HOLE_X[0] + BORE_X) / 2.0, _OFFSET_LINE + TEXT_DROP, LENGTH),
    "HoleSpacing": (BORE_X, _SPACING_LINE + TWO_LINE_DROP, LENGTH),
    "BoreX": (BORE_X / 2.0, _BORE_X_LINE + TEXT_DROP, LENGTH),
    "NutWidth": ((BORE_X + WIDTH) / 2.0, _WIDTH_LINE + THREE_LINE_DROP, LENGTH),
    "BoreY": (_BORE_Y_TEXT, BORE_Y / 2.0, LENGTH),
    "NutHeight": (_HEIGHT_TEXT, HEIGHT / 2.0, LENGTH),
    # The +X hole's 2X Ø.144 DRILL THRU up-right, its leader outboard of that
    # hole's extension line; the bore's two rows right, level with the face's
    # lower edge, its leader in through the +X side under the +X hole and
    # over the stock width's extension line (which runs down from the face).
    "HoleDia": (HOLE_X[1] + 10.0 + text_half("2X Ø.144 DRILL THRU"), HEIGHT + 5.5, LENGTH),
    "BoreDia": (WIDTH + 16.0, 2.0, LENGTH),
}
# The side view (*Right): the faced length over it.
SIDE_KEEP: dict[str, tuple[float, float, float]] = {
    "NutLength": (0.0, HEIGHT + FIRST_LANE + TEXT_DROP, LENGTH / 2.0),
}


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


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    """Make ``view`` the active view (a note lands in the active view)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} view {name!r}")


_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
FACE_CENTER_MARKS = 3  # the Tr8 bore and the two screw holes


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION)
        or ()
    )


_STOCK_SIZES = {"NutWidth": WIDTH, "NutHeight": HEIGHT}


def _stock_references(adapter: Any, annotations: list[Any]) -> None:
    """The as-bought width and height print as REF stock fractions over
    STOCK and the supplier's band (TL-28's ``_stock_references``)."""
    by_name: dict[str, list[Any]] = {}
    for item in annotations:
        by_name.setdefault(dimension_name(adapter, item), []).append(item)
    for name, size in _STOCK_SIZES.items():
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        display = _early_bound(
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=f"feed nut stock {name}",
            units="in",
            precision=DRAWING_PRECISION_BY_NAME[name],
            expected_mm=size,
            fraction_denominator=STOCK_FRACTION_DENOMINATORS[name],
            callout=STOCK_CALLOUTS[name],
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open feed nut source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Oblique Trammel Feed Nut Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel feed nut; brass rectangle bar; MHA-CH-06-TL-27",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (face, side, iso):
        set_hidden_lines_removed(adapter, view)

    on_face = _view_mapper(adapter, face)
    on_side = _view_mapper(adapter, side)
    # The face shows the hidden HolePatternReference, the side the hidden
    # NutLengthReference, each printing its own stations.
    annotations = [
        *curate_view_dimensions(
            adapter,
            face,
            keep={name: on_face(xyz) for name, xyz in FACE_KEEP.items()},
            view_label="feed nut face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            side,
            keep={name: on_side(xyz) for name, xyz in SIDE_KEEP.items()},
            view_label="feed nut side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places and callout rows are authored on the part; the sheet only proves
    # the import kept the places, then writes the stock references.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _stock_references(adapter, annotations)
    # The template centre-marks the face's circles as the view is placed; a
    # second AutoInsertCenterMarks2 printed all three twice (r1 layout audit,
    # #913). Mark only a bare view, then prove one mark per hole.
    if _center_mark_count(face) == 0 and not auto_center_marks(
        adapter, face, holes=True, size=0.0025
    ):
        raise RuntimeError("failed to add ASME center marks to the face")
    found = _center_mark_count(face)
    if found != FACE_CENTER_MARKS:
        raise RuntimeError(
            f"expected {FACE_CENTER_MARKS} centre marks on the face, found {found}"
        )

    # The property-linked block lands in the active view: the face.
    _activate_view(adapter, face, label="face")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Feed Nut Drawing",
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
