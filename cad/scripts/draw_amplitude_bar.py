r"""Create the curated machinist drawing for the amplitude bar.

The SLDPRT remains authoritative.  This recipe supplies only the amplitude-bar
views, dimension layout, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The bar is ~808 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length only), a 1:4 right view beside it, a
4:1 top end view for the square section, and a small 1:8 isometric.  The
working features are edge-on at 1:4, so they are dimensioned in three 4:1
details (policy rule 7, machinist review 2026-09-02):

* DETAIL A -- the top notch, from the front view: width and depth as sheet
  dimensions, with the cheek offset stated beside the detail.
* DETAIL B -- the bottom notch, from the front view: the same three, plus the
  roughness symbol on the floor that slides on the rocker.
* DETAIL C -- the top pin hole, from the RIGHT view (the only projection where
  the hole, drilled along X, is a visible circle): its drop below the bar top,
  its station across the depth, and the ``#47 DRILL`` callout.

The details carry sheet dimensions (edge picks) except for the top cheek
offset, whose clipped outer edge is not a reliable derived-view selection and
is therefore stated beside DETAIL A from the shared spec.  A marked dimension
imports into ONE view only, so an import into a detail could claim the front
view's overall length.  The sheet runs at 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_amplitude_bar.py amplitude-bar
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    create_detail_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from amplitude_bar_spec import (
    BAR_DEPTH,
    BAR_LENGTH,
    BAR_WIDTH,
    BOTTOM_NOTCH_HEIGHT,
    BOTTOM_NOTCH_WIDTH,
    NOTCH_OFFSET,
    SURFACE_FINISHES,
    TOP_NOTCH_FLOOR_Y,
    TOP_NOTCH_WIDTH,
    TOP_PIN_DIA,
    TOP_PIN_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["amplitude_bar"]
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

SHEET_SCALE = (1.0, 4.0)  # 1:4
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.25)
DETAIL_SCALE = (4, 1)
_D = DETAIL_SCALE[0] / DETAIL_SCALE[1]  # sheet-mm per model-mm in a detail (4.0)

# Sheet layout (meters).  The 1:4 front and right views stand side by side on
# the left (202 mm tall); the three 4:1 details, the 4:1 top end view and the
# 1:8 isometric fill the right-hand field above the title block.
FRONT_CENTER = (0.110, 0.140)
RIGHT_CENTER = (0.140, 0.140)
END_CENTER = (0.300, 0.105)  # square-section top end view (4:1)
ISO_CENTER = (0.385, 0.150)
DETAIL_A_CENTER = (0.200, 0.190)  # top notch (from the front view)
DETAIL_B_CENTER = (0.180, 0.104)  # bottom notch (from the front view)
DETAIL_C_CENTER = (0.300, 0.190)  # top pin hole (from the right view)

# Detail boundaries in model mm: each circle is centred on the bar's width
# (or depth) mid-line, 8 mm in from the end it enlarges, and reaches 9 mm --
# past the 12.7 top-notch floor / the 2.38 bottom-notch floor / the pin hole.
DETAIL_MODEL_RADIUS = 9.0
TOP_DETAIL_Y = BAR_LENGTH - 8.0
BOTTOM_DETAIL_Y = 8.0

_BBOX_CX = BAR_WIDTH / 2.0  # the front view is bbox-centred on the bar
_BBOX_CY = BAR_LENGTH / 2.0
_BBOX_CZ = BAR_DEPTH / 2.0  # the right view likewise across the depth


def _front_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Y) point in the 1:4 front view."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


def _right_xy(mz: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (Z, Y) point in the 1:4 right view.

    The pin hole and the two side faces are symmetric about the depth
    mid-line, so the view's Z mirror (SolidWorks' choice) cannot matter.
    """
    return (
        RIGHT_CENTER[0] + (mz - _BBOX_CZ) * _S / 1000.0,
        RIGHT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


def _detail_xy(
    center: tuple[float, float],
    model_center: tuple[float, float],
    mu: float,
    mv: float,
) -> tuple[float, float]:
    """Sheet (x, y) of a model point in a 4:1 detail centred on ``model_center``."""
    return (
        center[0] + (mu - model_center[0]) * _D / 1000.0,
        center[1] + (mv - model_center[1]) * _D / 1000.0,
    )


def _detail_a(mx: float, my: float) -> tuple[float, float]:
    return _detail_xy(DETAIL_A_CENTER, (_BBOX_CX, TOP_DETAIL_Y), mx, my)


def _detail_b(mx: float, my: float) -> tuple[float, float]:
    return _detail_xy(DETAIL_B_CENTER, (_BBOX_CX, BOTTOM_DETAIL_Y), mx, my)


def _detail_c(mz: float, my: float) -> tuple[float, float]:
    return _detail_xy(DETAIL_C_CENTER, (_BBOX_CZ, TOP_DETAIL_Y), mz, my)


FRONT_KEEP = {
    "BarLength": (0.075, FRONT_CENTER[1]),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}

# Detail pick stations (model mm): the cheeks are picked clear of the floors
# and of the hidden pin-hole band; the floors at their mid-width.
_TOP_CHEEK_Y = TOP_NOTCH_FLOOR_Y + 3.0
_BOTTOM_CHEEK_Y = BOTTOM_NOTCH_HEIGHT / 2.0
_INNER_CHEEK_X = NOTCH_OFFSET + TOP_NOTCH_WIDTH  # 4.7625 (both notches)
_SLIDE_FLOOR_PICK_X = NOTCH_OFFSET + 0.6  # left part of the floor, clear of the depth pick
_DEPTH_PICK_X = _INNER_CHEEK_X - 0.6

# DETAIL A's clipped stock-face edge is not reliably selectable.  State the
# same spec-owned offset beside the view instead of guessing a new pick.
TOP_CHEEK_OFFSET_NOTE = f"CHEEK OFFSET {NOTCH_OFFSET:.4f}"
TOP_CHEEK_OFFSET_NOTE_XY = (
    _detail_a(NOTCH_OFFSET / 2.0, 0.0)[0],
    _detail_a(_BBOX_CX, BAR_LENGTH)[1] + 0.014,
)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open amplitude-bar source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Amplitude Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "amplitude bar; chrome steel; coefficient bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 4))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 4))
    top = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 8))
    set_hidden_lines_removed(adapter, iso)

    # The three enlarged end details (policy rule 7).
    detail_a = create_detail_view(
        adapter,
        front,
        center=_front_xy(_BBOX_CX, TOP_DETAIL_Y),
        radius=DETAIL_MODEL_RADIUS * _S / 1000.0,
        view_xy=DETAIL_A_CENTER,
        detail_label="A",
        scale=DETAIL_SCALE,
        label="top notch detail",
    )
    detail_b = create_detail_view(
        adapter,
        front,
        center=_front_xy(_BBOX_CX, BOTTOM_DETAIL_Y),
        radius=DETAIL_MODEL_RADIUS * _S / 1000.0,
        view_xy=DETAIL_B_CENTER,
        detail_label="B",
        scale=DETAIL_SCALE,
        label="bottom notch detail",
    )
    detail_c = create_detail_view(
        adapter,
        right,
        center=_right_xy(_BBOX_CZ, TOP_DETAIL_Y),
        radius=DETAIL_MODEL_RADIUS * _S / 1000.0,
        view_xy=DETAIL_C_CENTER,
        detail_label="C",
        scale=DETAIL_SCALE,
        label="top pin hole detail",
    )
    for view in (front, right, top, detail_a, detail_b, detail_c):
        set_hidden_lines_visible(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    # DETAIL A (top notch): the clipped stock-face cheek is stated from the
    # shared spec; width remains chained above the end and depth stays right.
    if add_note(adapter, TOP_CHEEK_OFFSET_NOTE, *TOP_CHEEK_OFFSET_NOTE_XY) is None:
        raise RuntimeError("failed to add top-notch cheek-offset note")
    add_edge_dimension(
        adapter,
        detail_a,
        p0=_detail_a(NOTCH_OFFSET, _TOP_CHEEK_Y),
        p1=_detail_a(_INNER_CHEEK_X, _TOP_CHEEK_Y),
        text_xy=(_detail_a(_BBOX_CX, 0.0)[0], a_row),
        label="top notch width",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        detail_a,
        p0=_detail_a(NOTCH_OFFSET / 2.0, BAR_LENGTH),
        p1=_detail_a(_DEPTH_PICK_X, TOP_NOTCH_FLOOR_Y),
        text_xy=(
            DETAIL_A_CENTER[0] + 0.030,
            _detail_a(0.0, (BAR_LENGTH + TOP_NOTCH_FLOOR_Y) / 2.0)[1],
        ),
        label="top notch depth",
        orientation="vertical",
    )

    # DETAIL B (bottom notch): the same chain below the end, the depth at
    # right, and the Ra on the floor that slides on the rocker's top edge.
    b_row = _detail_b(_BBOX_CX, 0.0)[1] - 0.014
    add_edge_dimension(
        adapter,
        detail_b,
        p0=_detail_b(0.0, _BOTTOM_CHEEK_Y),
        p1=_detail_b(NOTCH_OFFSET, _BOTTOM_CHEEK_Y),
        text_xy=(_detail_b(NOTCH_OFFSET / 2.0, 0.0)[0], b_row),
        label="bottom notch cheek offset",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        detail_b,
        p0=_detail_b(NOTCH_OFFSET, _BOTTOM_CHEEK_Y),
        p1=_detail_b(_INNER_CHEEK_X, _BOTTOM_CHEEK_Y),
        text_xy=(_detail_b(_BBOX_CX, 0.0)[0], b_row),
        label="bottom notch width",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        detail_b,
        p0=_detail_b(NOTCH_OFFSET / 2.0, 0.0),
        p1=_detail_b(_DEPTH_PICK_X, BOTTOM_NOTCH_HEIGHT),
        text_xy=(
            DETAIL_B_CENTER[0] + 0.030,
            _detail_b(0.0, BOTTOM_NOTCH_HEIGHT / 2.0)[1],
        ),
        label="bottom notch depth",
        orientation="vertical",
    )
    slide_floor = _detail_b(_SLIDE_FLOOR_PICK_X, BOTTOM_NOTCH_HEIGHT)
    add_surface_finish(
        adapter,
        detail_b,
        edge_xy=slide_floor,
        symbol_xy=(DETAIL_B_CENTER[0] - 0.032, slide_floor[1] + 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "slide_floor"),
        label="slide floor finish",
    )

    # DETAIL C (top pin hole, right view): drop below the bar top, station
    # from the side face (mid-depth), and the native #47 callout.
    pin_rim_left = _detail_c(_BBOX_CZ - TOP_PIN_DIA / 2.0, TOP_PIN_Y)
    pin_rim_top = _detail_c(_BBOX_CZ, TOP_PIN_Y + TOP_PIN_DIA / 2.0)
    pin_rim_bottom = _detail_c(_BBOX_CZ, TOP_PIN_Y - TOP_PIN_DIA / 2.0)
    add_edge_dimension(
        adapter,
        detail_c,
        p0=_detail_c(0.0, TOP_PIN_Y + 2.0),
        p1=pin_rim_left,
        text_xy=(
            _detail_c(_BBOX_CZ / 2.0, 0.0)[0],
            _detail_c(0.0, TOP_NOTCH_FLOOR_Y)[1] - 0.016,
        ),
        label="top pin station across the depth",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        detail_c,
        p0=_detail_c(_BBOX_CZ + 2.0, BAR_LENGTH),
        p1=pin_rim_top,
        text_xy=(
            DETAIL_C_CENTER[0] + 0.028,
            _detail_c(0.0, (BAR_LENGTH + TOP_PIN_Y) / 2.0)[1],
        ),
        label="top pin drop",
        orientation="vertical",
    )
    add_native_hole_callout(
        adapter,
        detail_c,
        edge_xy=pin_rim_bottom,
        callout_xy=(DETAIL_C_CENTER[0] + 0.040, DETAIL_C_CENTER[1] - 0.014),
        label="top pin hole",
        process="#47 DRILL",
    )

    # Notes along the top; the end-view and isometric captions under their
    # views (the end view runs 16x the sheet scale -- label it or "do not
    # scale drawing" leaves its size unreadable).
    add_property_linked_note(adapter, "Manufacturing Notes", 0.150, 0.258)
    add_property_linked_note(adapter, "End View Note", 0.272, 0.084)
    add_property_linked_note(adapter, "Isometric View Note", 0.360, 0.088)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Amplitude Bar Manufacturing Drawing",
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
