r"""Create the curated machinist drawing for the platen support bar (MHA-PD-007).

A 452 x 28 x 9 steel bar clamped across the frame columns. Its BACK face
carries the transgear pivot's flat-bottomed #8-32 tap and the latch hook's two
#4-40 through taps on one row; its FRONT face, which the platen slides on,
carries the four counterbored clamp-screw holes.

* The upper view looks on the back face (model +Z, ``*Front``): the length,
  the hanger row's banded stations from the left end, each naming its mate,
  and its height from the top face (the part-hidden HangerRowReference
  sketch), the pivot drill's Ø with its tap, both countersinks' MAX Ø
  (CountersinkReference), the latch-hook taps' native callout (its thread
  class left to the title block) and the top face's slide roughness.
* The lower view looks on the front face (``*Back``, so the left end is on
  the sheet's right): the banded height, the clamp row's stations from the
  same end and its height (ClampRowReference), the counterbores' native
  callout (depth at .XX) and the front face's slide roughness. Each
  roughness symbol has its reason beside it; the sheet has no general note.
* Each face view carries its caption; section A-A cuts the pivot tap across
  the bar: the banded thickness, the drill's depth limits and the full
  thread's MIN (PivotThreadReference, in the cutting plane).

Every value and band is a native model dimension authored by
``build_pd_support_bar``; the sheet only places and curates them.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_support_bar.py pd-support-bar
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

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
from _drawing_annotation_extent import move_annotation
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import scan_view_edges
from _drawing_finish import add_surface_finish
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face_resolve import resolve_faces
from _hole_spec import blind_cut_dia_mm
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _surface_finish import surface_finish_by_key
from build_pd_support_bar import (
    BAR_LENGTH,
    CLAMP_CBORE_DIA,
    CLAMP_ROW_X,
)
from pd_support_bar_spec import (
    BACK_FACE_Z,
    BAR_DEPTH,
    BAR_HEIGHT,
    BRACKET_TAP_CSK_DIA,
    BRACKET_TAP_SPEC,
    BRACKET_TAP_X,
    HANGER_TAP_Y,
    PIVOT_TAP_X,
)
from pd_support_bar_drawing_spec import (
    BACK_VIEW_CAPTION,
    CLAMP_CBORE_CALLOUT,
    CLAMP_CBORE_DEPTH_PLACES,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_VIEW_CAPTION,
    FRONT_FINISH_REASON,
    SURFACE_FINISHES,
    TOP_FINISH_REASON,
)


SPEC = DRAWINGS_BY_NAME["pd_support_bar"]
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

SHEET_SCALE = (1, 2)
FACE_SCALE = (1, 2)
SECTION_SCALE = (2, 1)
ISO_SCALE = (1, 6)
_S = FACE_SCALE[0] / FACE_SCALE[1] / 1000.0  # sheet metres per model mm

# The back face above, the front face below, both at 1:2 with their ends
# aligned; section A-A right of the back face's end, the isometric under it.
FACE_CENTER = (0.170, 0.222)
BACK_CENTER = (0.170, 0.122)
SECTION_CENTER = (0.385, 0.200)
ISO_CENTER = (0.365, 0.098)
ISO_NOTE_XY = (0.300, 0.076)

LEFT_END = FACE_CENTER[0] - BAR_LENGTH * _S / 2.0
RIGHT_END = FACE_CENTER[0] + BAR_LENGTH * _S / 2.0
FACE_TOP = FACE_CENTER[1] + BAR_HEIGHT * _S / 2.0
FACE_BOTTOM = FACE_CENTER[1] - BAR_HEIGHT * _S / 2.0
BACK_TOP = BACK_CENTER[1] + BAR_HEIGHT * _S / 2.0
BACK_BOTTOM = BACK_CENTER[1] - BAR_HEIGHT * _S / 2.0


def _face_x(model_x: float) -> float:
    """Sheet x of a model x in the back-face view (model +X to the right)."""
    return FACE_CENTER[0] + model_x * _S


def _back_x(model_x: float) -> float:
    """Sheet x of a model x in the front-face view (model +X to the left)."""
    return BACK_CENTER[0] - model_x * _S


# The hanger stations are baselines from the left end, stacked under the bar
# shortest first (13 mm rows: each value carries its mate's line), the length
# outermost; their texts step right so none crosses a longer row's extension
# line, and stand clear of the pivot station's. The row's height (from the
# top face, its rise on the right end) stands off the right end. The section
# line runs up through the pivot, its arrows and letters left of it, so the
# pivot's Ø and countersink stand right of it, the Ø higher and further left
# (its leader passes left of the countersink's text, slanting off the line);
# the latch-hook taps' callout (high) and countersink (low) stand right of the
# pivot's, their leaders between the two pairs.
ROW_STEP = 0.013
FRONT_KEEP = {
    "PivotTapStation": (LEFT_END + 0.042, FACE_BOTTOM - ROW_STEP),
    "BracketTapStation1": (LEFT_END + 0.115, FACE_BOTTOM - 2.0 * ROW_STEP),
    "BracketTapStation2": (LEFT_END + 0.118, FACE_BOTTOM - 3.0 * ROW_STEP),
    "Length": (FACE_CENTER[0], FACE_BOTTOM - 4.0 * ROW_STEP),
    "HangerRowHeight": (RIGHT_END + 0.022, FACE_BOTTOM - 0.010),
    "PivotTapDrillDia": (_face_x(PIVOT_TAP_X) + 0.032, FACE_TOP + 0.030),
    "PivotCskDia": (_face_x(PIVOT_TAP_X) + 0.043, FACE_TOP + 0.014),
    "BracketCskDia": (_face_x(BRACKET_TAP_X[0]) + 0.059, FACE_TOP + 0.014),
}
BRACKET_CALLOUT_XY = (_face_x(BRACKET_TAP_X[1]) + 0.056, FACE_TOP + 0.031)
# The top face's slide roughness on its edge, left of the section line.
TOP_FINISH_MODEL_X = -178.0
TOP_FINISH_SYMBOL_XY = (LEFT_END + 0.030, FACE_TOP + 0.014)
TOP_REASON_TOP = (TOP_FINISH_SYMBOL_XY[0] + 0.003, FACE_TOP + 0.032)
FACE_CAPTION_TOP = (0.200, FACE_BOTTOM - 4.0 * ROW_STEP - 0.008)

# The clamp stations from the same left (x = -226) end, on the sheet's right
# here, shortest nearest the bar; the first's 5.75 mm span is too short for
# its text, which stands left of its hole between it and the second's. The
# bar height reads off that end too (the BarProfile dimension's model edge),
# the clamp row's height off the other end, where its rise is.
BACK_KEEP = {
    "ClampStation1": (RIGHT_END - 0.015, BACK_BOTTOM - 0.010),
    "ClampStation2": (RIGHT_END - 0.012, BACK_BOTTOM - 0.018),
    "ClampStation3": (RIGHT_END - 0.150, BACK_BOTTOM - 0.026),
    "ClampStation4": (RIGHT_END - 0.170, BACK_BOTTOM - 0.034),
    "Height": (RIGHT_END + 0.016, BACK_TOP + 0.016),
    "ClampRowHeight": (LEFT_END - 0.020, BACK_BOTTOM - 0.008),
}
# The counterbores' callout stands wholly right of the hole it points at, so
# its leader slants right, off the clamp row height's extension line.
CLAMP_CALLOUT_XY = (_back_x(max(CLAMP_ROW_X)) + 0.047, BACK_TOP + 0.016)
# The front face's slide roughness, seen face-on: a leader to a point clear
# of the holes, the symbol above the view.
FRONT_FINISH_MODEL_XY = (-150.0, 6.0)
FRONT_FINISH_SYMBOL_XY = (0.252, BACK_TOP + 0.014)
# Its reason stands left of it, under the face view's caption.
FRONT_REASON_TOP = (0.2175, BACK_TOP + 0.013)
BACK_CAPTION_TOP = (BACK_CENTER[0], BACK_BOTTOM - 0.042)
FINISH_CHAR_HEIGHT = 0.0025
CAPTION_SETTLE_M = 0.0006

# Section A-A: the thickness up-left of the cut bar, the full thread and the
# drill depth below it (shorter nearer). Each text stands outside its
# extension lines, beyond the tap's mouth, since the 2:1 spans are narrower
# than the texts. The caption drops under them.
SECTION_KEEP_NAMES = ("Depth", "ThreadMin", "DrillDepth")
SECTION_DEPTH_RISE = 0.010
SECTION_DEPTH_SIDE = 0.028
SECTION_DEPTH_TEXT_SIDE = 0.016
SECTION_THREAD_DROP = 0.010
SECTION_DRILL_DROP = 0.027
CAPTION_DROP = 0.035
SECTION_OVERRUN = 3.0  # mm the cutting line runs past each long edge

DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}


def _sheet(
    adapter: Any, view: Any, xyz_mm: tuple[float, float, float], label: str
) -> tuple[float, float]:
    return model_point_in_view(
        adapter, view, tuple(v / 1000.0 for v in xyz_mm), label=label
    )


def _direction(
    adapter: Any, view: Any, axis: tuple[float, float, float], label: str
) -> tuple[float, float]:
    origin = _sheet(adapter, view, (0.0, 0.0, 0.0), f"{label} origin")
    tip = _sheet(adapter, view, axis, f"{label} axis")
    return tip[0] - origin[0], tip[1] - origin[1]


def _turn_y_up(adapter: Any, view: Any, *, label: str) -> None:
    """Turn ``view`` about its centre until model +Y points sheet-up
    (draw_dt_cone_pivot_post_tl_bond_cradle._turn)."""
    native = _early_bound(view, "IView")
    dx, dy = _direction(adapter, native, (0.0, 1.0, 0.0), label)
    native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(dy, dx)
    rebuild_drawing(adapter, label=f"turn {label}")
    dx, dy = _direction(adapter, native, (0.0, 1.0, 0.0), label)
    if dy <= 0.0 or abs(dx) > 1e-9:
        raise RuntimeError(f"{label}: model +Y is not sheet-up ({dx:g}, {dy:g})")


def _section_keep(adapter: Any, section: Any) -> dict[str, tuple[float, float]]:
    """Section A-A's text positions from its own projection, whichever way the
    cut looks: the thickness left of the bar's left face, the depths beyond
    the tap's mouth."""

    def point(z: float, y: float = HANGER_TAP_Y) -> tuple[float, float]:
        return _sheet(adapter, section, (PIVOT_TAP_X, y, z), "section A-A")

    top = point(0.0, BAR_HEIGHT / 2.0)[1]
    bottom = point(0.0, -BAR_HEIGHT / 2.0)[1]
    mouth = point(BACK_FACE_Z)[0]
    front = point(-BACK_FACE_Z)[0]
    outside = mouth + math.copysign(SECTION_DEPTH_TEXT_SIDE, mouth - front)
    return {
        "Depth": (min(mouth, front) - SECTION_DEPTH_SIDE, top + SECTION_DEPTH_RISE),
        "ThreadMin": (outside, bottom - SECTION_THREAD_DROP),
        "DrillDepth": (outside, bottom - SECTION_DRILL_DROP),
    }


def _lower_caption(adapter: Any, view: Any, drop: float) -> None:
    """Move a section's native caption down the sheet by ``drop`` metres,
    keeping its linked fields
    (draw_dt_cone_pivot_post_tl_bond_cradle._lower_caption)."""
    view = _early_bound(view, "IView")
    captions = []
    for raw_note in view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(
            token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")
        ):
            captions.append((note, linked_text))
    if len(captions) != 1:
        raise RuntimeError(
            f"expected one native linked view caption, found {len(captions)}"
        )
    note, linked_text = captions[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    x, y = (float(value) for value in tuple(annotation.GetPosition())[:2])
    target = (x, y - drop)
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position native view caption")
    rebuild_drawing(adapter, label="lower section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("native view caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("view caption lost its native view-label fields")


def _hole_rims(face: Any, back: Any) -> tuple[Any, Any]:
    """The first latch-hook tap's drill edge under its back-face countersink
    (a Hole Wizard tap edge, so its callout is native) and the first clamp
    counterbore's rim on the front face."""
    tap_dia = blind_cut_dia_mm(BRACKET_TAP_SPEC)
    tap_csk_depth = (BRACKET_TAP_CSK_DIA - tap_dia) / 2.0
    tap = (
        scan_view_edges(face, label="support-bar back face")
        .circle_at(
            (BRACKET_TAP_X[0], HANGER_TAP_Y, BACK_FACE_Z - tap_csk_depth),
            tap_dia / 2.0,
            axis=(0.0, 0.0, 1.0),
            label="latch-hook tap edge",
            radius_tol_mm=0.025,
        )
        .edge
    )
    cbore = (
        scan_view_edges(back, label="support-bar front face")
        .circle_at(
            (max(CLAMP_ROW_X), 0.0, -BAR_DEPTH / 2.0),
            CLAMP_CBORE_DIA / 2.0,
            axis=(0.0, 0.0, 1.0),
            label="clamp counterbore rim",
            radius_tol_mm=0.025,
        )
        .edge
    )
    return tap, cbore


_THREAD_CLASS_TOKEN = " <hw-threadclass>"


def _drop_thread_class(adapter: Any, display: Any) -> None:
    """Drop the Hole Wizard's thread-class token from the native TAP
    callout's definition (rule 2: the title block's THREADS row carries the
    class); the other tokens stay live (draw_sm_knife_mount precedent)."""
    display = _early_bound(display, "IDisplayDimension")
    before = str(display.GetText(5) or "")  # swDimensionTextPrefixDefinition
    if before.count(_THREAD_CLASS_TOKEN) != 1:
        raise RuntimeError(
            f"latch-hook tap callout has no lone class token: {before!r}"
        )
    wanted = before.replace(_THREAD_CLASS_TOKEN, "")
    display.SetText(1, wanted)
    if str(display.GetText(5) or "") != wanted:
        raise RuntimeError(
            f"latch-hook tap callout class did not drop: {display.GetText(5)!r}"
        )
    rebuild_drawing(adapter, label="latch-hook tap callout class")


def _name_clamp_screws(display: Any) -> None:
    """Hang the screws' part number under the counterbores' native callout,
    and print its depth at the .XX its head clearance takes."""
    set_hole_callout_precision(
        display,
        {"hw-cbdepth": CLAMP_CBORE_DEPTH_PLACES},
        label="clamp-screw counterbores",
    )
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(4, CLAMP_CBORE_CALLOUT)  # swDimensionTextCalloutBelow
    if str(display.GetText(4) or "") != CLAMP_CBORE_CALLOUT:
        raise RuntimeError("clamp counterbore callout's mate line did not persist")


def _place_caption(adapter: Any, text: str, top_centre: tuple[float, float]) -> None:
    """A view caption whose measured box's top centre lands on ``top_centre``
    (INote.GetExtent; draw_pd_transgear_feed_pinion._place_rear_caption)."""
    raw_note = add_note(adapter, text, *top_centre)
    if raw_note is None:
        raise RuntimeError(f"caption {text!r} was not inserted")
    note = _early_bound(raw_note, "INote")
    for _attempt in range(4):
        extent = tuple(float(value) for value in note.GetExtent())
        error = (
            top_centre[0] - (extent[0] + extent[3]) / 2.0,
            top_centre[1] - extent[4],
        )
        if max(abs(error[0]), abs(error[1])) < CAPTION_SETTLE_M:
            break
        move_annotation(adapter, note.GetAnnotation(), *error, label=text)
    else:
        raise RuntimeError(f"caption {text!r} stayed at {extent}, asked {top_centre}")
    _telemetry.info(f"caption {text!r}: extent {extent}")


def _add_slide_finishes(adapter: Any, face: Any, back: Any) -> None:
    """The platen's two slide faces: the top face on its edge in the back-face
    view, the front face seen face-on, a leader to a point on it."""
    top = _sheet(
        adapter, face, (TOP_FINISH_MODEL_X, BAR_HEIGHT / 2.0, BACK_FACE_Z), "top finish"
    )
    add_surface_finish(
        adapter,
        face,
        edge_xy=top,
        leader_attach_xy=top,
        symbol_xy=TOP_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "top_slide"),
        label="top slide finish",
        char_height=FINISH_CHAR_HEIGHT,
    )
    control = surface_finish_by_key(SURFACE_FINISHES, "front_slide")
    front_face = resolve_faces(
        _early_bound(_early_bound(back, "IView").ReferencedDocument, "IModelDoc2"),
        {control.key: control.face},
    )[control.key]
    add_surface_finish(
        adapter,
        back,
        entity=front_face,
        entity_type="FACE",
        leader_attach_xy=_sheet(
            adapter, back, (*FRONT_FINISH_MODEL_XY, -BAR_DEPTH / 2.0), "front finish"
        ),
        symbol_xy=FRONT_FINISH_SYMBOL_XY,
        control=control,
        label="front slide finish",
        char_height=FINISH_CHAR_HEIGHT,
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open support-bar source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        source_model, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet_model = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Support Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "support bar; steel bar; counterbored clamp holes; tapped hanger holes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=FACE_SCALE)
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=FACE_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (face, back, iso):
        set_hidden_lines_removed(adapter, view)

    # Each face view shows the part-hidden row sketch that owns its stations
    # and height (_drawing_hidden_sketches); the back face also the
    # countersinks' reference circles.
    face_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        face,
        keep=FRONT_KEEP,
        view_label="back face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    back_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        back,
        keep=BACK_KEEP,
        view_label="front face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )

    # Section A-A cuts down the pivot axis across the whole height; its
    # full-thread line lies in the cutting plane and is shown while it is cut.
    with hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        ("PivotThreadReference",),
        label="pivot section",
        base_view=face,
    ):
        reach = BAR_HEIGHT / 2.0 + SECTION_OVERRUN
        section = create_section_view(
            adapter,
            face,
            line_start=_sheet(adapter, face, (PIVOT_TAP_X, reach, 0.0), "cut top"),
            line_end=_sheet(adapter, face, (PIVOT_TAP_X, -reach, 0.0), "cut foot"),
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=SECTION_SCALE,
            label="section A-A",
        )
        _turn_y_up(adapter, section, label="section A-A")
        set_hidden_lines_removed(adapter, section)
        section_annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep=_section_keep(adapter, section),
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )

    annotations = [*face_annotations, *back_annotations, *section_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's band or limit) are authored on the part;
    # the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    tap_edge, cbore_edge = _hole_rims(face, back)
    _drop_thread_class(
        adapter,
        add_native_hole_callout(
            adapter,
            face,
            edge=tap_edge,
            callout_xy=BRACKET_CALLOUT_XY,
            label="latch-hook base taps",
            process="TAP",
        ),
    )
    _name_clamp_screws(
        add_native_hole_callout(
            adapter,
            back,
            edge=cbore_edge,
            callout_xy=CLAMP_CALLOUT_XY,
            label="clamp-screw counterbores",
            process="DRILL, C'BORE",
        )
    )
    _add_slide_finishes(adapter, face, back)
    _lower_caption(adapter, section, CAPTION_DROP)
    _place_caption(adapter, FACE_VIEW_CAPTION, FACE_CAPTION_TOP)
    _place_caption(adapter, BACK_VIEW_CAPTION, BACK_CAPTION_TOP)
    _place_caption(adapter, TOP_FINISH_REASON, TOP_REASON_TOP)
    _place_caption(adapter, FRONT_FINISH_REASON, FRONT_REASON_TOP)

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # The native TAP callout restates the taps, so the Hole Wizard's own
    # "Tapped Hole" note is the one redundant automatic note.
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Support Bar Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
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
