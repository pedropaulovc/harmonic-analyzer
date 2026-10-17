r"""Create the curated machinist drawing for the magnifying-lever clamp.

A 28.65 length of 7/16 hex brass (#1559): the Ø6.2 lever bore drilled across
the corners, a #4-40 thumb-screw tap from the top face into the bore and a
blind #4-40 rod tap from the bottom face, both on the hex axis.

Views (3:1, hidden lines removed throughout, drawing-guidelines.md rule 9):

* FRONT (``*Right``, looking along the lever bore at a corner): the block
  height, the bore's height from the bottom seat, its distance from the flat
  on the right (along the bore's centreline) and its Ø callout, which states
  the wall that location leaves.
* TOP and BOTTOM, turned and pinned into third-angle projection above and
  below the front (corners up and down, the flats square to the sheet): the
  flats (stock REF) over the top view, and each tap's native callout.
* SECTION A-A, cut on the hex axis through the corners from the front: the
  bore through the corners, both blind taps in solid lines and the floor
  between the rod tap and the bore, under a solid-line hatch with the
  cosmetic threads kept off it; the bottom seat carries its flag note.
* Shaded isometric, 2:1.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_clamp.py mg-magnifying-clamp
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    remove_notes_matching,
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from mg_magnifying_clamp_spec import (
    BLOCK_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEX_AC,
    HEX_AF,
    LEVER_BORE_CALLOUT,
    LEVER_BORE_Y,
    REFERENCE_DIMENSIONS,
    ROD_TAP_DRILL_DIA,
    ROD_TAP_PROCESS,
    SEAT_NOTE,
    TAP_CALLOUT_PRECISION,
    TAP_DRILL_DEPTH_VARIABLE,
    TAP_THREAD_DEPTH_VARIABLE,
    THUMB_TAP_PROCESS,
)


SPEC = DRAWINGS_BY_NAME["mg_magnifying_clamp"]
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

# A 12.8 x 11.1 x 28.65 hex: 3:1 stacks the 39 mm top view, the 86 mm front
# and the 39 mm bottom view in one column, the section and isometric beside.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
ISO_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet m per model mm

# The projection column: the front at mid-height, the top and bottom views in
# line with it (their centres pinned to the front's hex axis).
RIGHT_CENTER = (0.085, 0.1272)
TOP_CENTER = (RIGHT_CENTER[0], 0.2175)
BOTTOM_CENTER = (RIGHT_CENTER[0], 0.045)
# The section high enough that its caption clears the title block
# (x > ~0.216, y < ~0.066); the isometric right of it, inside the border.
SECTION_CENTER = (0.250, 0.170)
ISO_CENTER = (0.365, 0.190)
# Note positions are their text's top-left corners.
NOTES_XY = (0.225, 0.082)
ISO_NOTE_XY = (0.335, 0.150)
SEAT_NOTE_XY = (0.287, 0.116)

_HALF_AF = HEX_AF / 2.0 * _S
_HALF_AC = HEX_AC / 2.0 * _S


def _elev_y(center: tuple[float, float], model_y_mm: float) -> float:
    """Sheet y of a height above the bottom face in the front view or the
    section (both centred on the block's height)."""
    return center[1] + (model_y_mm - BLOCK_HEIGHT / 2.0) * _S


_BORE_SHEET_Y = _elev_y(RIGHT_CENTER, LEVER_BORE_Y)
_RIGHT_FLAT_X = RIGHT_CENTER[0] + _HALF_AF
_RIGHT_LEFT_X = RIGHT_CENTER[0] - _HALF_AF

# The front view: both heights to the left; the bore's distance from the
# right-hand flat along its own centreline (the A-A line stands on the hex
# axis, so a vertical witness from the bore centre would run along it); the
# Ø callout up and to the right, its leader above that dimension.
RIGHT_KEEP = {
    "Height": (_RIGHT_LEFT_X - 0.028, RIGHT_CENTER[1]),
    "LeverBoreYDim": (_RIGHT_LEFT_X - 0.012, _elev_y(RIGHT_CENTER, LEVER_BORE_Y / 2.0)),
    "LeverBoreFromFlat": (_RIGHT_FLAT_X + 0.010, _BORE_SHEET_Y),
    "LeverBoreDiaDim": (0.150, _BORE_SHEET_Y + 0.037),
}
# The top view: the flats (Z, sheet horizontal) above it, between its upper
# vertices.
TOP_KEEP = {"HexAf": (TOP_CENTER[0], TOP_CENTER[1] + _HALF_AC + 0.010)}

DIMENSION_CALLOUTS = {"LeverBoreDiaDim": LEVER_BORE_CALLOUT}

# The tap callouts (their text centres) out to the right of each end view,
# low enough that each leader crosses the right-hand flat, under the flat's
# upper vertex and the HexAf witness standing on it.
THUMB_TAP_CALLOUT_XY = (0.165, TOP_CENTER[1] + 0.010)
ROD_TAP_CALLOUT_XY = (0.150, BOTTOM_CENTER[1] + 0.008)
# SolidWorks' own descriptive note for a Hole Wizard tap ("#4-40 Tapped Hole").
TAPPED_HOLE_NOTE = "Tapped Hole"

# The section's cutting line: vertical through the hex axis on the front view,
# past the block top and bottom.
_SECTION_OVERSHOOT = 0.006
# The seat flag's pick stands a third of the half-width off the hex axis,
# clear of the rod tap; the section is symmetric about the axis, so a
# mirrored section lands it on the same face.
_PICK_DX = 0.35 * _HALF_AC

# Third-angle projection of the front (``*Right``: +Z to sheet left, +Y up):
# the top view sees +X (toward the front's viewer) down the sheet, the bottom
# view up it; both keep +Z to the left.  Model axes, 1 mm long, in metres.
_AXES = {"+X": (0.001, 0.0, 0.0), "+Y": (0.0, 0.001, 0.0), "+Z": (0.0, 0.0, 0.001)}
FRONT_AXES = {"+Z": math.pi, "+Y": math.pi / 2.0}
TOP_AXES = {"+X": -math.pi / 2.0, "+Z": math.pi}
BOTTOM_AXES = {"+X": math.pi / 2.0, "+Z": math.pi}
PROJECTION_ANGLE_SLOP = 1e-6
PROJECTION_SLOP_M = 1e-5

# swAnnotationType_e: swCosmeticThread, swCenterMarkSym.
_COSMETIC_THREAD_ANNOTATION = 1
_CENTER_MARK_ANNOTATION = 13
_SECTION_THREAD_LAYER = "MG-CLAMP-SECTION-THREADS-HIDDEN"
# The section's hatch: ANSI31's continuous 45 deg lines, not the brass
# material's dashed ANSI33.
SECTION_HATCH_PATTERN = "ANSI31"

# swDimensionTextParts_e definitions (5-8) and the writable part each is set
# through (1-4) -- the draw_mg_output_fixture convention.
_CALLOUT_DEFINITION_PARTS = {5: 1, 6: 2, 7: 3, 8: 4}
_THREAD_DEPTH_TOKEN = f"<{TAP_THREAD_DEPTH_VARIABLE}>"
_DRILL_DEPTH_TOKEN = f"<{TAP_DRILL_DEPTH_VARIABLE}>"


def reference_thread_depth_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """The thumb tap callout's definitions with the thread depth's variable
    bracketed REF, ``(<hw-threaddepth>)``: the lever bore ends that thread
    (ASME Y14.5 reference); the drill depth governs and stays bare."""
    joined = "\n".join(definitions.values())
    if (
        joined.count(_THREAD_DEPTH_TOKEN) != 1
        or f"({_THREAD_DEPTH_TOKEN}" in joined
        or joined.count(_DRILL_DEPTH_TOKEN) != 1
        or f"({_DRILL_DEPTH_TOKEN}" in joined
    ):
        raise RuntimeError(
            f"expected one bare {_THREAD_DEPTH_TOKEN} and one bare "
            f"{_DRILL_DEPTH_TOKEN} in the thumb tap callout: {definitions!r}"
        )
    return {
        part: text.replace(_THREAD_DEPTH_TOKEN, f"({_THREAD_DEPTH_TOKEN})")
        for part, text in definitions.items()
    }


def _reference_thread_depth(display: Any) -> None:
    before = {
        part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    wanted = reference_thread_depth_definitions(before)
    (part,) = [part for part in before if wanted[part] != before[part]]
    display.SetText(_CALLOUT_DEFINITION_PARTS[part], wanted[part])
    after = {
        part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS
    }
    if after != wanted:
        raise RuntimeError(
            f"thumb tap thread depth did not persist as REF: wanted {wanted!r}, "
            f"read {after!r}"
        )
    _telemetry.success(f"thumb tap thread depth bracketed REF: {wanted[part]!r}")


def _axis_direction(
    adapter: Any, view: Any, axis: tuple[float, float, float], label: str
) -> tuple[float, float]:
    origin = model_point_in_view(
        adapter, view, (0.0, 0.0, 0.0), label=f"{label} origin"
    )
    tip = model_point_in_view(adapter, view, axis, label=f"{label} tip")
    return tip[0] - origin[0], tip[1] - origin[1]


def _require_axes(adapter: Any, view: Any, axes: dict[str, float], label: str) -> None:
    for name, angle in axes.items():
        dx, dy = _axis_direction(adapter, view, _AXES[name], f"{label} {name}")
        if (
            abs(math.hypot(dx, dy) - _S) > PROJECTION_SLOP_M
            or abs(math.remainder(math.atan2(dy, dx) - angle, math.tau))
            > PROJECTION_ANGLE_SLOP
        ):
            raise RuntimeError(
                f"{label} {name}: projected axis {(dx, dy)} is not at {angle:g} rad"
            )


def _project_end_view(
    adapter: Any,
    front: Any,
    end: Any,
    *,
    axes: dict[str, float],
    center_y: float,
    label: str,
) -> None:
    """Turn a named end view into the front's third-angle projection and pin
    its hex axis under the front's (the draw_mg_output_fixture recipe)."""
    native = _early_bound(end, "IView")
    dx, dy = _axis_direction(adapter, native, _AXES["+X"], f"{label} +X before")
    if math.hypot(dx, dy) <= PROJECTION_SLOP_M:
        raise RuntimeError(f"{label} +X has no measurable projected direction")
    # No assumed quarter turn: rotate the measured +X onto its projection.
    native.Angle = float(native.Angle) + axes["+X"] - math.atan2(dy, dx)
    rebuild_drawing(adapter, label=f"turn clamp {label} view")
    _require_axes(adapter, native, axes, label)
    front_origin = model_point_in_view(
        adapter, front, (0.0, 0.0, 0.0), label="front origin"
    )
    target = (front_origin[0], center_y)
    at = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label=f"{label} origin")
    position = tuple(float(value) for value in native.Position)
    moved = [position[axis] + target[axis] - at[axis] for axis in range(2)]
    if native.SetViewPosition(double_array(moved), False) is not True:
        raise RuntimeError(f"failed to pin the clamp {label} view in projection")
    rebuild_drawing(adapter, label=f"pin clamp {label} view")
    at = model_point_in_view(
        adapter, native, (0.0, 0.0, 0.0), label=f"{label} origin pinned"
    )
    if math.dist(at, target) > PROJECTION_SLOP_M:
        raise RuntimeError(
            f"clamp {label} origin {at} is not in line with the front's {target}"
        )
    _telemetry.success(f"clamp {label} view in projection: origin {at}")


def _face_hatches(section: Any) -> list[Any]:
    """The section's IFaceHatch objects.  The returned array can carry null
    slots (the API's own VBA example reads from index 1), so drop them."""
    view = _early_bound(section, "IView")
    return [
        _early_bound(raw, "IFaceHatch")
        for raw in (view.GetFaceHatches() or ())
        if raw is not None
    ]


def _solid_line_hatch(adapter: Any, section: Any) -> None:
    """Swap the brass material hatch (dashed ANSI33) for continuous lines.

    IFaceHatch.Pattern is get-only (setting it raises "Unable to write
    read-only property"); clearing UseMaterialHatch falls back to the
    document's area hatch, which must read back as ANSI31."""
    hatches = _face_hatches(section)
    if not hatches:
        view = _early_bound(section, "IView")
        raise RuntimeError(
            "section A-A has no face hatch: GetFaceHatchCount "
            f"{view.GetFaceHatchCount()}, slots {len(view.GetFaceHatches() or ())}"
        )
    for hatch in hatches:
        hatch.UseMaterialHatch = False
    rebuild_drawing(adapter, label="section A-A solid-line hatch")
    read = [
        (bool(hatch.UseMaterialHatch), str(hatch.Pattern))
        for hatch in _face_hatches(section)
    ]
    if len(read) != len(hatches) or any(
        material or not pattern.upper().startswith(SECTION_HATCH_PATTERN)
        for material, pattern in read
    ):
        raise RuntimeError(
            f"section A-A hatch is not {SECTION_HATCH_PATTERN}: {read!r}"
        )
    _telemetry.success(
        f"section A-A: {len(read)} face hatch(es) {SECTION_HATCH_PATTERN}"
    )


def _hide_cosmetic_threads(adapter: Any, view: Any, *, label: str) -> int:
    """Keep the taps' cosmetic-thread ink out of a section (rule 9: a section
    never carries hidden lines); the callouts state both threads.  The
    draw_dt_cone_tip_block hidden-layer recipe."""
    manager = _early_bound(adapter.currentModel.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_SECTION_THREAD_LAYER)
    if layer is None:
        if (
            int(
                manager.AddLayer(
                    _SECTION_THREAD_LAYER, "clamp section thread ink hidden", 0, 0, 0
                )
            )
            != 1
        ):
            raise RuntimeError("failed to add the clamp section thread layer")
        layer = manager.GetLayer(_SECTION_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("the clamp section thread layer is not hidden")
    hidden = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != _COSMETIC_THREAD_ANNOTATION:
            continue
        annotation.Layer = _SECTION_THREAD_LAYER
        if str(annotation.Layer or "") != _SECTION_THREAD_LAYER:
            raise RuntimeError(
                f"clamp {label} cosmetic thread refused the hidden layer"
            )
        hidden += 1
    if not hidden:
        raise RuntimeError(f"clamp {label} has no cosmetic thread to hide")
    rebuild_drawing(adapter, label=f"hide clamp {label} cosmetic threads")
    return hidden


def _require_one_center_mark(view: Any, label: str) -> None:
    """The template's own tap centre mark, once."""
    marks = tuple(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(
            f"expected one tap centre mark on the {label} view, found {len(marks)}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-clamp source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Clamp Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying clamp; 7/16 hex brass; lever bore across corners; two #4-40 taps",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (right, top, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    _require_axes(adapter, _early_bound(right, "IView"), FRONT_AXES, "front")
    _project_end_view(
        adapter, right, top, axes=TOP_AXES, center_y=TOP_CENTER[1], label="top"
    )
    _project_end_view(
        adapter,
        right,
        bottom,
        axes=BOTTOM_AXES,
        center_y=BOTTOM_CENTER[1],
        label="bottom",
    )
    section = create_section_view(
        adapter,
        right,
        line_start=(
            RIGHT_CENTER[0],
            _elev_y(RIGHT_CENTER, BLOCK_HEIGHT) + _SECTION_OVERSHOOT,
        ),
        line_end=(RIGHT_CENTER[0], _elev_y(RIGHT_CENTER, 0.0) - _SECTION_OVERSHOOT),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="hex-axis section through the corners",
    )
    set_hidden_lines_removed(adapter, section)
    _solid_line_hatch(adapter, section)
    hidden = _hide_cosmetic_threads(adapter, section, label="section A-A")
    _telemetry.info(f"hid {hidden} cosmetic thread(s) in section A-A")

    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        bottom,
        keep={},
        view_label="bottom",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*right_annotations, *top_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, right_annotations, DIMENSION_CALLOUTS)
    # The flats are the bar's as supplied: a stock reference.
    top_by_name = {dimension_name(adapter, a): a for a in top_annotations}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, top_by_name[name], label=f"MHA-MG-002 {name} stock reference"
        )

    # The template marks each end view's tap; a second, scripted mark doubled
    # it (the r1 audit's duplicate-annotation), so the sheet only proves the one.
    for view, label in ((top, "top"), (bottom, "bottom")):
        _require_one_center_mark(view, label)
    # Each end view shows one visible tap-drill circle: its native callout
    # prints the drill and thread rows with the process ahead of the thread.
    thumb_callout = add_native_hole_callout(
        adapter,
        top,
        edge=visible_circle_edge(adapter, top, ROD_TAP_DRILL_DIA),
        callout_xy=THUMB_TAP_CALLOUT_XY,
        label="#4-40 thumb-screw tap",
        process=THUMB_TAP_PROCESS,
    )
    _reference_thread_depth(thumb_callout)
    set_hole_callout_precision(
        thumb_callout, TAP_CALLOUT_PRECISION, label="#4-40 thumb-screw tap depths"
    )
    rod_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge=visible_circle_edge(adapter, bottom, ROD_TAP_DRILL_DIA),
        callout_xy=ROD_TAP_CALLOUT_XY,
        label="#4-40 vertical-rod tap",
        process=ROD_TAP_PROCESS,
    )
    set_hole_callout_precision(
        rod_callout, TAP_CALLOUT_PRECISION, label="#4-40 vertical-rod tap depths"
    )
    # SolidWorks pins its own "#4-40 Tapped Hole" note beside a tap's native
    # callout; the callout already states the thread. Farm run r1
    # (20261016T211740899Z) measured one on the bottom view, its leader
    # crossing the rod tap callout's (leader-crosses-leader). How many the
    # two taps bring is logged here, after both callouts; finalize_drawing's
    # census then proves none reached the print.
    removed = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed} automatic {TAPPED_HOLE_NOTE!r} note(s)")

    # The bottom seat's "leave it flat" flag (rule 7), on section A-A's bottom
    # line beside the rod tap, down and to the right clear of the caption.
    add_attached_note(
        adapter,
        section,
        text=SEAT_NOTE,
        entity_xy=(SECTION_CENTER[0] + _PICK_DX, _elev_y(SECTION_CENTER, 0.0)),
        note_xy=SEAT_NOTE_XY,
        label="MHA-MG-004 shoulder seat",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Clamp Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
