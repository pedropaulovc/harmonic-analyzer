r"""Create the curated machinist drawing for the amplitude bar.

The SLDPRT remains authoritative.  This recipe supplies only the amplitude-bar
views, dimension layout, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The bar is ~808 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length only), a 1:4 right view beside it, a
4:1 top end view for the square section, and a small 1:8 isometric.  The
working features are edge-on at 1:4, so they are dimensioned in three 4:1
details (policy rule 7, machinist review 2026-09-02):

* DETAIL A -- the top notch, from the front view: offset, width, and depth in
  a specification-derived note beside the enlarged profile.
* DETAIL B -- the bottom notch, from the front view: the same three values,
  plus the sliding floor's finish, in a specification-derived note.
* DETAIL C -- the top pin hole, from the RIGHT view (the only projection where
  the hole, drilled along X, is a visible circle): a specification-derived
  note gives its transverse centre station, drop below the top, nominal
  diameter, drill process, and through condition.

All three derived details expose no stable selectable model edges on this seat,
so their complete manufacturing callouts come directly from the shared part
spec.  A marked dimension imports into ONE view only, so an import into a
detail could claim the front view's overall length.  The sheet runs at 1:4.

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
    add_property_linked_note,
    create_detail_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    model_point_in_view,
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
    TOP_NOTCH_HEIGHT,
    TOP_NOTCH_WIDTH,
    TOP_PIN_DIA,
    TOP_PIN_DROP,
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
END_CENTER = (0.330, 0.105)  # square-section top end view (4:1)
ISO_CENTER = (0.385, 0.150)
DETAIL_A_CENTER = (0.200, 0.190)  # top notch (from the front view)
DETAIL_B_CENTER = (0.180, 0.095)  # bottom notch (from the front view)
DETAIL_C_CENTER = (0.285, 0.190)  # top pin hole (from the right view)

# Detail boundaries in model mm: each circle is centred on the bar's width
# (or depth) mid-line, 8 mm in from the end it enlarges, and reaches 9 mm --
# past the 12.7 top-notch floor / the 2.38 bottom-notch floor / the pin hole.
DETAIL_MODEL_RADIUS = 9.0
TOP_DETAIL_Y = BAR_LENGTH - 8.0
BOTTOM_DETAIL_Y = 8.0

_BBOX_CX = BAR_WIDTH / 2.0


def _detail_source_center(
    adapter: Any,
    view: Any,
    *,
    x_mm: float,
    y_mm: float,
    z_mm: float,
    label: str,
) -> tuple[float, float]:
    """Project an actual model point to the parent drawing view.

    A placed SolidWorks view is not guaranteed to be centred on its model
    bounding box.  Detail-circle centres therefore come from the view's
    ModelToViewTransform rather than from hand-derived sheet offsets.
    """
    return model_point_in_view(
        adapter,
        view,
        (x_mm / 1000.0, y_mm / 1000.0, z_mm / 1000.0),
        label=label,
    )
FRONT_KEEP = {
    "BarLength": (0.075, FRONT_CENTER[1]),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}


# The derived details expose no reliable selectable model edges on this seat.
# State each complete, spec-owned manufacturing definition beside its profile.
TOP_NOTCH_GEOMETRY_NOTE = "\n".join(
    (
        f"CHEEK OFFSET {NOTCH_OFFSET:.4f}",
        f"NOTCH WIDTH {TOP_NOTCH_WIDTH:.4f}",
        f"NOTCH DEPTH {TOP_NOTCH_HEIGHT:.4f}",
    )
)
_SLIDE_FLOOR_FINISH = surface_finish_by_key(SURFACE_FINISHES, "slide_floor")
BOTTOM_NOTCH_GEOMETRY_NOTE = "\n".join(
    (
        f"CHEEK OFFSET {NOTCH_OFFSET:.4f}",
        f"NOTCH WIDTH {BOTTOM_NOTCH_WIDTH:.4f}",
        f"NOTCH DEPTH {BOTTOM_NOTCH_HEIGHT:.4f}",
        f"BOTTOM FLOOR FINISH Ra {_SLIDE_FLOOR_FINISH.roughness_ra}",
    )
)
TOP_PIN_GEOMETRY_NOTE = "\n".join(
    (
        f"PIN C/L {BAR_DEPTH / 2.0:.4f} FROM SIDE FACE",
        f"PIN C/L {TOP_PIN_DROP:.2f} BELOW TOP",
        f"#47 DRILL <MOD-DIAM>{TOP_PIN_DIA:.3f} THRU",
    )
)
BOTTOM_NOTCH_GEOMETRY_NOTE_XY = (0.220, 0.145)
TOP_PIN_GEOMETRY_NOTE_XY = (0.255, 0.242)
TOP_NOTCH_GEOMETRY_NOTE_XY = (0.150, 0.242)
MANUFACTURING_NOTES_XY = (0.150, 0.265)
END_VIEW_NOTE_XY = (0.300, 0.074)
ISOMETRIC_VIEW_NOTE_XY = (0.325, 0.088)


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

    # Use the model-to-view transforms for the three source circles.  Hand
    # centring against an assumed bounding box can leave a valid detail view
    # pointed at blank sheet space when SolidWorks shifts a placed view.
    top_notch_source = _detail_source_center(
        adapter,
        front,
        x_mm=_BBOX_CX,
        y_mm=TOP_DETAIL_Y,
        z_mm=0.0,
        label="top notch detail source",
    )
    bottom_notch_source = _detail_source_center(
        adapter,
        front,
        x_mm=_BBOX_CX,
        y_mm=BOTTOM_DETAIL_Y,
        z_mm=0.0,
        label="bottom notch detail source",
    )
    top_pin_source = _detail_source_center(
        adapter,
        right,
        x_mm=_BBOX_CX,
        y_mm=TOP_DETAIL_Y,
        z_mm=BAR_DEPTH / 2.0,
        label="top pin detail source",
    )
    detail_a = create_detail_view(
        adapter,
        front,
        center=top_notch_source,
        radius=DETAIL_MODEL_RADIUS * _S / 1000.0,
        view_xy=DETAIL_A_CENTER,
        detail_label="A",
        scale=DETAIL_SCALE,
        label="top notch detail",
    )
    detail_b = create_detail_view(
        adapter,
        front,
        center=bottom_notch_source,
        radius=DETAIL_MODEL_RADIUS * _S / 1000.0,
        view_xy=DETAIL_B_CENTER,
        detail_label="B",
        scale=DETAIL_SCALE,
        label="bottom notch detail",
    )
    detail_c = create_detail_view(
        adapter,
        right,
        center=top_pin_source,
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

    # DETAIL A (top notch): the derived view exposes no stable edges on this
    # seat, so all three transverse sizes render from the shared spec beside
    # the useful enlarged profile.
    if (
        add_note(
            adapter,
            TOP_NOTCH_GEOMETRY_NOTE,
            *TOP_NOTCH_GEOMETRY_NOTE_XY,
        )
        is None
    ):
        raise RuntimeError("failed to add top-notch geometry note")

    # DETAIL B (bottom notch): as for DETAIL A, keep the enlarged profile
    # useful without depending on unselectable derived-view edges.
    if (
        add_note(
            adapter,
            BOTTOM_NOTCH_GEOMETRY_NOTE,
            *BOTTOM_NOTCH_GEOMETRY_NOTE_XY,
        )
        is None
    ):
        raise RuntimeError("failed to add bottom-notch geometry note")

    # DETAIL C (top pin hole, right view): the derived view's circular profile
    # is useful context, but its edges are not selectable on this seat.  Give
    # the complete, spec-owned location, size, process and extent beside it.
    if (
        add_note(
            adapter,
            TOP_PIN_GEOMETRY_NOTE,
            *TOP_PIN_GEOMETRY_NOTE_XY,
        )
        is None
    ):
        raise RuntimeError("failed to add top-pin geometry note")

    # Property notes occupy their own bands: feature notes above/between the
    # details, captions below their views, and neither in the title block.
    add_property_linked_note(adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_XY)
    add_property_linked_note(adapter, "End View Note", *END_VIEW_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISOMETRIC_VIEW_NOTE_XY)

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
