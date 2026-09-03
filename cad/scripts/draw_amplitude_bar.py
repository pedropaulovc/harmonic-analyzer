r"""Create the curated machinist drawing for the amplitude bar.

The SLDPRT remains authoritative.  This recipe supplies only the amplitude-bar
views, dimension layout, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The bar is ~808 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length only), a 1:4 right view beside it, a
4:1 top end view for the square section, and a small 1:8 isometric.  The
working features are edge-on at 1:4, so they are shown in three deterministic
4:1 cropped model views (policy rule 7, machinist review 2026-09-02):

* DETAIL A -- the top notch, from the front view: offset, width, and depth in
  a specification-derived note beside the enlarged profile.
* DETAIL B -- the bottom notch, from the front view: the same three values,
  plus the sliding floor's finish, in a specification-derived note.
* DETAIL C -- the top pin hole, from the RIGHT view (the only projection where
  the hole, drilled along X, is a visible circle): a specification-derived
  note gives its transverse centre station, drop below the top, nominal
  diameter, drill process, and through condition.

SolidWorks' derived-detail placement can detach the projected model geometry
from its circular crop on this unusually slender part.  Each close-up is
therefore a directly placed orthographic model view, translated so the
spec-owned feature point lands at the declared sheet centre, then cropped
around that point.  The crop has no decorative outline; its actual model
geometry and adjacent label carry the detail.  Derived-view edges remain
unreliable on this seat, so the manufacturing callouts come directly from the
shared part spec.  A marked dimension imports into ONE view only, so an import
into a close-up could claim the front view's overall length.  The sheet runs at
1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_amplitude_bar.py amplitude-bar
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    _sheet_to_view_sketch,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    model_point_in_view,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    view_name,
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
from solidworks_mcp.adapters.com_variant import double_array
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
# the left (202 mm tall); three outline-free 4:1 feature crops, the 4:1 top end
# view and the 1:8 isometric fill the right-hand field above the title block.
FRONT_CENTER = (0.110, 0.140)
RIGHT_CENTER = (0.140, 0.140)
END_CENTER = (0.330, 0.105)  # square-section top end view (4:1)
ISO_CENTER = (0.385, 0.150)
DETAIL_A_CENTER = (0.200, 0.190)  # top notch (from the front view)
DETAIL_B_CENTER = (0.190, 0.105)  # bottom notch (from the front view)
DETAIL_C_CENTER = (0.285, 0.190)  # top pin hole (from the right view)

# Each crop reaches beyond its feature in model space.  The source is a fresh
# orthographic model view at DETAIL_SCALE, so these radii are converted by the
# crop helper rather than by the 1:4 parent-view scale.
DETAIL_MODEL_RADIUS = 9.0
TOP_DETAIL_Y = BAR_LENGTH - 8.0
BOTTOM_DETAIL_Y = 8.0

_BBOX_CX = BAR_WIDTH / 2.0


def _place_feature_crop(
    adapter: Any,
    orientation: str,
    *,
    model_xyz: tuple[float, float, float],
    model_radius_mm: float,
    view_xy: tuple[float, float],
    scale: tuple[int, int],
    label: str,
) -> Any:
    """Place and crop a real model view with ``model_xyz`` at ``view_xy``.

    A derived detail can retain its circular outline while its projected
    geometry drifts elsewhere on this long, thin part.  A standalone
    orthographic view is deterministic: translate its actual model point to
    the declared sheet centre, then crop that same view around the point.
    """
    view = place_view(adapter, str(SOURCE), orientation, *view_xy, scale=scale)
    draw = adapter.currentModel
    sw_view = _early_bound(view, "IView")
    projected = model_point_in_view(adapter, view, model_xyz, label=label)
    position = tuple(float(value) for value in (sw_view.Position or ()))
    if len(position) < 2:
        raise RuntimeError(f"feature crop has no view position ({label})")
    translated = (
        position[0] + view_xy[0] - projected[0],
        position[1] + view_xy[1] - projected[1],
    )
    if not sw_view.SetViewPosition(double_array(list(translated)), False):
        raise RuntimeError(f"failed to position feature crop ({label})")
    draw.EditRebuild3()

    crop_center = model_point_in_view(adapter, view, model_xyz, label=label)
    crop_radius = model_radius_mm * scale[0] / scale[1] / 1000.0
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate feature crop ({label})")
    draw.ClearSelection2(True)
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    centre = _sheet_to_view_sketch(adapter, view, crop_center, label=label)
    rim = _sheet_to_view_sketch(
        adapter,
        view,
        (crop_center[0] + crop_radius, crop_center[1]),
        label=label,
    )
    if (
        sketch_manager.CreateCircle(
            float(centre[0]),
            float(centre[1]),
            0.0,
            float(rim[0]),
            float(rim[1]),
            0.0,
        )
        is None
    ):
        raise RuntimeError(f"failed to create feature crop ({label})")
    if int(sw_view.Crop2(False, True, 5)) != 1:
        raise RuntimeError(f"failed to crop feature view ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return view

FRONT_KEEP = {
    "BarLength": (0.075, FRONT_CENTER[1]),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}


# Cropped views expose no reliable selectable model edges on this seat.  State
# each complete, spec-owned manufacturing definition beside its real profile.
TOP_NOTCH_GEOMETRY_NOTE = "\n".join(
    (
        "DETAIL A — TOP NOTCH — SCALE 4:1",
        f"CHEEK OFFSET {NOTCH_OFFSET:.4f}",
        f"NOTCH WIDTH {TOP_NOTCH_WIDTH:.4f}",
        f"NOTCH DEPTH {TOP_NOTCH_HEIGHT:.4f}",
    )
)
_SLIDE_FLOOR_FINISH = surface_finish_by_key(SURFACE_FINISHES, "slide_floor")
BOTTOM_NOTCH_GEOMETRY_NOTE = "\n".join(
    (
        "DETAIL B — BOTTOM NOTCH — SCALE 4:1",
        f"CHEEK OFFSET {NOTCH_OFFSET:.4f}",
        f"NOTCH WIDTH {BOTTOM_NOTCH_WIDTH:.4f}",
        f"NOTCH DEPTH {BOTTOM_NOTCH_HEIGHT:.4f}",
        f"BOTTOM FLOOR FINISH Ra {_SLIDE_FLOOR_FINISH.roughness_ra}",
    )
)
TOP_PIN_GEOMETRY_NOTE = "\n".join(
    (
        "DETAIL C — TOP PIN — SCALE 4:1",
        f"PIN C/L {BAR_DEPTH / 2.0:.4f} FROM SIDE FACE",
        f"PIN C/L {TOP_PIN_DROP:.2f} BELOW TOP",
        f"#47 DRILL <MOD-DIAM>{TOP_PIN_DIA:.3f} THRU",
    )
)
BOTTOM_NOTCH_GEOMETRY_NOTE_XY = (0.235, 0.145)
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

    # Direct feature crops keep the real notch and bore geometry tied to their
    # declared sheet centres.  Crop2's NoOutline mode also removes the three
    # empty circles that previously dominated this slender-part drawing.
    detail_a = _place_feature_crop(
        adapter,
        "*Front",
        model_xyz=(
            _BBOX_CX / 1000.0,
            TOP_DETAIL_Y / 1000.0,
            0.0,
        ),
        model_radius_mm=DETAIL_MODEL_RADIUS,
        view_xy=DETAIL_A_CENTER,
        scale=DETAIL_SCALE,
        label="top notch detail",
    )
    detail_b = _place_feature_crop(
        adapter,
        "*Front",
        model_xyz=(
            _BBOX_CX / 1000.0,
            BOTTOM_DETAIL_Y / 1000.0,
            0.0,
        ),
        model_radius_mm=DETAIL_MODEL_RADIUS,
        view_xy=DETAIL_B_CENTER,
        scale=DETAIL_SCALE,
        label="bottom notch detail",
    )
    detail_c = _place_feature_crop(
        adapter,
        "*Right",
        model_xyz=(
            _BBOX_CX / 1000.0,
            TOP_DETAIL_Y / 1000.0,
            BAR_DEPTH / 2000.0,
        ),
        model_radius_mm=DETAIL_MODEL_RADIUS,
        view_xy=DETAIL_C_CENTER,
        scale=DETAIL_SCALE,
        label="top pin hole detail",
    )
    for view in (front, right, top, detail_a, detail_b, detail_c):
        set_hidden_lines_visible(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    # DETAIL A (top notch): the cropped view exposes no stable selectable
    # edges, so all three transverse sizes render from the shared spec beside
    # the actual enlarged profile.
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
