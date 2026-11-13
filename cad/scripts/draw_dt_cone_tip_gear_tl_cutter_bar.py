r"""Manufacturing drawing of the DT6-FORM1 fly-cutter bar (MHA-DT-37-TL-02).

Issue #2358: one sheet at 2:1 -- the front view with the bar's Ø and length,
the right view with the reamed cross hole end-on and its station from the
cutting end, the bottom view with the #4-40 tap's native callout (TO CROSS
HOLE), and the isometric.  Every number is the part's own
(``dt_cone_tip_gear_tl_cutter_bar_spec``), imported from the model.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any, Callable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    remove_notes_matching,
)

import _telemetry
import dt_cone_tip_gear_tl_cutter_bar_spec as part
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
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_tip_gear_tl_cutter_bar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A Ø.375 x 1.75 bar: 2:1 prints it 89 mm long and the .089 tap drill 4.5 mm.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
RATIO = VIEW_SCALE[0] / VIEW_SCALE[1]
_S = RATIO / 1000.0
# The cutting end's centre (the model origin) on each view: the front view
# standing up from it, the right view beside it, the bottom view (the cutting
# end, end-on) projected below; the isometric in the free upper right.
FRONT_ORIGIN = (0.110, 0.100)
RIGHT_ORIGIN = (0.200, FRONT_ORIGIN[1])
BOTTOM_ORIGIN = (FRONT_ORIGIN[0], 0.060)
ISO_CENTER = (0.320, 0.200)
ISO_SCALE = VIEW_SCALE
ISO_NOTE = f"ISOMETRIC VIEW SCALE {ISO_SCALE[0]}:{ISO_SCALE[1]}"
ISO_NOTE_XY = (0.290, 0.150)
_R = part.BAR_RADIUS

FRONT_KEEP = {
    "BarDia": (
        FRONT_ORIGIN[0] - (_R + 12.0) * _S,
        FRONT_ORIGIN[1] + part.BAR_LENGTH * 0.6 * _S,
    ),
    "BarLength": (
        FRONT_ORIGIN[0] + (_R + 8.0) * _S,
        FRONT_ORIGIN[1] + part.BAR_LENGTH * 0.5 * _S,
    ),
}
RIGHT_KEEP = {
    "CrossHoleDia": (
        RIGHT_ORIGIN[0] + (_R + 18.0) * _S,
        RIGHT_ORIGIN[1] + (part.CROSS_HOLE_STATION + 10.0) * _S,
    ),
    "CrossHoleStation": (
        RIGHT_ORIGIN[0] - (_R + 6.0) * _S,
        RIGHT_ORIGIN[1] + part.CROSS_HOLE_STATION / 2.0 * _S,
    ),
}
_TAP_R = part.TAP_DRILL_DIA / 2.0 * _S
TAP_EDGE_XY = (BOTTOM_ORIGIN[0] - _TAP_R, BOTTOM_ORIGIN[1])
TAP_CALLOUT_XY = (BOTTOM_ORIGIN[0] + (_R + 10.0) * _S, BOTTOM_ORIGIN[1] - 0.004)
TAP_PROCESS = "TAP"
TAP_PRECISION = {"hw-tapdrldia": part.HOLE_CALLOUT_PRECISION}
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)


def sheet_dimension_names() -> set[str]:
    return set().union(*part.DRAWING_DIMENSIONS.values())


if {*FRONT_KEEP, *RIGHT_KEEP} != sheet_dimension_names():
    raise AssertionError("every marked bar dimension prints once, in one view")


def tap_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Rewrite the native tap callout's definition parts (5..8)
    (draw_dt_arbor_pedestal's apex tap): both ``<hw-thru>`` extents become TO
    CROSS HOLE and the thread class goes (the title block states it)."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    if "\n".join(definitions.values()).count("<hw-thru>") != 2:
        raise RuntimeError(f"tap callout lacks its two native extents: {definitions!r}")
    updated = {
        key: text.replace("<hw-thru>", part.SET_SCREW_EXTENT)
        for key, text in definitions.items()
    }
    thread_parts = [
        key for key, text in updated.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(f"tap thread line is not in one callout part: {updated!r}")
    key = thread_parts[0]
    updated[key] = re.sub(r" {2,}", " ", _THREAD_CLASS.sub(" ", updated[key])).rstrip()
    return updated


def _rewrite_callout_definitions(
    display: Any, rewrite: Callable[[dict[int, str]], dict[int, str]]
) -> dict[int, str]:
    """Write a native hole callout's rewritten definitions, prove they
    persisted and return the resolved text parts."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {key: str(native.GetText(key) or "") for key in (5, 6, 7, 8)}
    updated = rewrite(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {key: str(native.GetText(key) or "") for key in (5, 6, 7, 8)}
    if persisted != updated:
        raise RuntimeError(f"callout definitions did not persist: {persisted!r}")
    return {key: str(native.GetText(key) or "") for key in (1, 2, 3, 4)}


def _place_point(
    adapter: Any,
    view: Any,
    point_mm: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``view`` so the model point lands on ``target`` (sheet m)."""
    view = _early_bound(view, "IView")
    point = tuple(value / 1000.0 for value in point_mm)
    here = model_point_in_view(adapter, view, point, label=label)
    position = tuple(float(value) for value in view.Position)
    moved = [position[i] + target[i] - here[i] for i in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label}")
    rebuild_drawing(adapter, label=f"place {label}")
    here = model_point_in_view(adapter, view, point, label=label)
    if math.dist(here, target) > 1e-4:
        raise RuntimeError(f"{label}: point sits at {here!r}, not {target!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source fly-cutter bar missing: {SOURCE}")
    check("open fly-cutter bar", await adapter.open_model(str(SOURCE)))
    required = ("Number", "Material Specification", "Finish", "Quantity")
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part.UNIT,
    )
    stamp_drawing_summary(
        adapter,
        drawing,
        {
            0: "Cone Tip Gear Fly Cutter Bar Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: "fly-cutter bar for the DT6-FORM1 bit; MHA-DT-37-TL-02",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_ORIGIN, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_ORIGIN, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_ORIGIN, scale=VIEW_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    origin = (0.0, 0.0, 0.0)
    _place_point(adapter, front, origin, FRONT_ORIGIN, label="front view")
    _place_point(adapter, right, origin, RIGHT_ORIGIN, label="right view")
    _place_point(adapter, bottom, origin, BOTTOM_ORIGIN, label="bottom view")
    # The iso too (draw_pn_pen_rod): a new view already reads Shaded With
    # Edges, so finalize_drawing's SetDisplayMode4 is a no-op that leaves the
    # tap's cosmetic thread at draft quality (farm run 20261112T203021325Z:
    # readback cosmetic_threads=False). From HLR the shading call really
    # changes the mode and takes precision.
    for view in (front, right, bottom, iso):
        set_hidden_lines_removed(adapter, view)

    annotations: list[Any] = []
    for view, keep, label in (
        (front, FRONT_KEEP, "front view"),
        (right, RIGHT_KEEP, "right view"),
    ):
        annotations += curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=label,
            dimensions_by_feature=part.DRAWING_DIMENSIONS,
        )
    printed = {dimension_name(adapter, annotation) for annotation in annotations}
    if printed != sheet_dimension_names():
        raise RuntimeError(
            f"sheet prints {sorted(printed)}, the part marks {sorted(sheet_dimension_names())}"
        )
    assert_imported_precision(adapter, annotations, part.DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, part.DIMENSION_CALLOUTS)

    # The set-screw tap, end-on in the bottom view: native callout, TAP first,
    # its extent the cross hole it stops at.
    adapter.currentModel.GraphicsRedraw2()
    tap_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge_xy=TAP_EDGE_XY,
        callout_xy=TAP_CALLOUT_XY,
        label="set-screw tap",
        process=TAP_PROCESS,
    )
    resolved = _rewrite_callout_definitions(tap_callout, tap_callout_definitions)
    joined = "\n".join(resolved.values())
    if joined.count(part.SET_SCREW_EXTENT) != 2 or "2B" in joined:
        raise RuntimeError(f"set-screw tap callout text did not resolve: {resolved!r}")
    set_hole_callout_precision(tap_callout, TAP_PRECISION, label="set-screw tap")
    for view in (front, right, bottom):
        set_hidden_lines_removed(adapter, view)

    drawing.ClearSelection2(True)
    _early_bound(drawing, "IDrawingDoc").EditSheet()
    if add_note(adapter, ISO_NOTE, *ISO_NOTE_XY) is None:
        raise RuntimeError("failed to add the fly-cutter bar's isometric scale note")
    # Materialize the iso's cosmetic thread before the strict final note
    # cleanup (draw_fr_rocker_arm_support), so any "#4-40 Tapped Hole" label
    # SolidWorks pins to it exists when it is counted rather than first
    # appearing during the native save. The tap is stated once, on its native
    # callout, so any such label goes and the count is logged.
    import_cosmetic_threads(adapter, iso)
    removed_tap_labels = remove_notes_matching(adapter, "Tapped Hole")
    _telemetry.info(f"removed {removed_tap_labels} automatic tapped-hole label(s)")
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Gear Fly Cutter Bar Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # The sweep stays, so a label that appears after the removal above
        # fails the count instead of printing.
        redundant_note_substrings=("Tapped Hole",),
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
