r"""Create the curated machinist drawing for the platen support bar (MHA-PD-007).

A 452 x 28 x 9 steel bar clamped across the frame columns. Its BACK face
carries the transgear pivot's flat-bottomed #8-32 tap and the latch hook's two
#4-40 through taps on one row; its FRONT face, which the platen slides on,
carries the four counterbored clamp-screw holes.

* The upper view looks on the back face (model +Z, ``*Front``): the length,
  the banded height, the hanger row's banded stations from the left end and
  its height from the top face (the part-hidden HangerRowReference sketch),
  the pivot drill's Ø with its tap, both countersinks' MAX Ø
  (CountersinkReference) and the latch-hook taps' native callout.
* The lower view looks on the front face (``*Back``, so the +X end is on the
  sheet's left): the clamp row's stations and height (ClampRowReference) and
  the counterbores' native callout.
* Section A-A cuts the pivot tap across the bar: the banded thickness, the
  drill's depth limits and the full thread's MIN (PivotThreadReference, in
  the cutting plane).

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

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
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
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import scan_view_edges
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
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
    PIVOT_TAP_DRILL_DEPTH,
    PIVOT_TAP_FULL_THREAD_MIN,
    PIVOT_TAP_X,
)
from pd_support_bar_drawing_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
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
ISO_CENTER = (0.350, 0.100)
NOTES_XY = (0.020, 0.064)
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
# shortest first (9 mm rows), the length outermost; their texts step right so
# none crosses a longer row's extension line. The row's height (from the top
# face, its rise on the right end) and the bar's height stand off the right
# end. The pivot's Ø and countersink stand up-left of it, clear of the
# section line; the latch-hook countersink and tap callout up-right.
FRONT_KEEP = {
    "PivotTapStation": (LEFT_END + 0.042, FACE_BOTTOM - 0.010),
    "BracketTapStation1": (LEFT_END + 0.100, FACE_BOTTOM - 0.019),
    "BracketTapStation2": (LEFT_END + 0.120, FACE_BOTTOM - 0.028),
    "Length": (FACE_CENTER[0], FACE_BOTTOM - 0.037),
    "Height": (RIGHT_END + 0.045, FACE_TOP + 0.016),
    "HangerRowHeight": (RIGHT_END + 0.022, FACE_BOTTOM - 0.010),
    "PivotTapDrillDia": (_face_x(PIVOT_TAP_X) - 0.040, FACE_TOP + 0.014),
    "PivotCskDia": (_face_x(PIVOT_TAP_X) - 0.040, FACE_TOP + 0.030),
    "BracketCskDia": (_face_x(BRACKET_TAP_X[0]) + 0.040, FACE_TOP + 0.014),
}
BRACKET_CALLOUT_XY = (_face_x(BRACKET_TAP_X[1]) + 0.030, FACE_TOP + 0.034)

# The clamp stations from the sheet-left (+X) end, shortest nearest the bar;
# the first's 11.5 span is too short for its text, which stands right of its
# extension lines, short of the second hole's.
BACK_KEEP = {
    "ClampStation1": (LEFT_END + 0.040, BACK_BOTTOM - 0.010),
    "ClampStation2": (LEFT_END + 0.012, BACK_BOTTOM - 0.018),
    "ClampStation3": (LEFT_END + 0.150, BACK_BOTTOM - 0.026),
    "ClampStation4": (LEFT_END + 0.170, BACK_BOTTOM - 0.034),
    "ClampRowHeight": (RIGHT_END + 0.016, BACK_BOTTOM - 0.008),
}
CLAMP_CALLOUT_XY = (_back_x(CLAMP_ROW_X[0]) + 0.020, BACK_TOP + 0.022)

# Section A-A: the thickness above the cut bar, the full thread and the drill
# depth below it (shorter nearer), the caption dropped under them.
SECTION_KEEP_NAMES = ("Depth", "ThreadMin", "DrillDepth")
SECTION_DEPTH_RISE = 0.016
SECTION_THREAD_DROP = 0.012
SECTION_DRILL_DROP = 0.028
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
    """Section A-A's text positions from its own projection: whichever way
    the cut looks, each depth's text centres between its two faces."""

    def point(z: float, y: float = HANGER_TAP_Y) -> tuple[float, float]:
        return _sheet(adapter, section, (PIVOT_TAP_X, y, z), "section A-A")

    top = point(0.0, BAR_HEIGHT / 2.0)
    bottom = point(0.0, -BAR_HEIGHT / 2.0)[1]
    mouth = point(BACK_FACE_Z)[0]
    thread_end = point(BACK_FACE_Z - PIVOT_TAP_FULL_THREAD_MIN)[0]
    floor = point(BACK_FACE_Z - PIVOT_TAP_DRILL_DEPTH)[0]
    return {
        "Depth": (top[0], top[1] + SECTION_DEPTH_RISE),
        "ThreadMin": ((mouth + thread_end) / 2.0, bottom - SECTION_THREAD_DROP),
        "DrillDepth": ((mouth + floor) / 2.0, bottom - SECTION_DRILL_DROP),
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
            (CLAMP_ROW_X[0], 0.0, -BAR_DEPTH / 2.0),
            CLAMP_CBORE_DIA / 2.0,
            axis=(0.0, 0.0, 1.0),
            label="clamp counterbore rim",
            radius_tol_mm=0.025,
        )
        .edge
    )
    return tap, cbore


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
        "Manufacturing Notes",
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
    for view, label in ((face, "back face"), (back, "front face")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks on the {label}")

    tap_edge, cbore_edge = _hole_rims(face, back)
    add_native_hole_callout(
        adapter,
        face,
        edge=tap_edge,
        callout_xy=BRACKET_CALLOUT_XY,
        label="latch-hook base taps",
        process="TAP",
    )
    add_native_hole_callout(
        adapter,
        back,
        edge=cbore_edge,
        callout_xy=CLAMP_CALLOUT_XY,
        label="clamp-screw counterbores",
        process="DRILL, C'BORE",
    )
    _lower_caption(adapter, section, CAPTION_DROP)

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Support Bar Manufacturing Drawing",
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
