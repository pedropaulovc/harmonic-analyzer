r"""Create the altered-item drawing for the MHA-DT-VN-61 cone pivot post mount screw.

MSC 40923906 is bought as 4 in stock and cut to length (ASME Y14.24 tier 3,
#2886): a Front view carrying the cut length -- the part's hidden
reference-sketch dimension, imported at its model-owned places -- and an
isometric, both 1:1. The Front lies on a horizontal axis, head left, as the
screw sits in the lathe (drawing-guidelines.md rule 11). No single length
suits every in-band post and plate (dt_vn_post_mount_screw_spec's U27 check),
so the length prints as a REFERENCE at CUT_LENGTH_MM, with no band and
'SEE NOTE 1' beneath it (rule 7): note 1 (CUT_LENGTH_NOTE) gives the cut end's
acceptance, flush to the spec band's allowance short of the MHA-DT-20
underside, and the engagement minimum as a plain fact (rule 20). The cut
end's break is the title block's general edge break; the sheet carries no
part-local break limit (Main's ruling on the run-7 sheet). The other note
says the undimensioned purchased geometry is reference; the stock rows name
what it is made from.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_vn_post_mount_screw.py dt-vn-post-mount-screw
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
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
import _drawing_hidden_sketches as hidden_sketches
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed
from _purchased_fastener_drawing import _literal_note
from _session import run_build
import _telemetry
from dt_vn_post_mount_screw_spec import (
    CUT_LENGTH_DIMENSION,
    CUT_LENGTH_MM,
    CUT_LENGTH_SKETCH,
    CUT_TO_FIT_SHORT_PLACES,
    DRAWING_PRECISION_BY_NAME,
    FRONT_VIEW_DIMENSIONS,
    POST_MOUNT_ENGAGEMENT_PRINTED,
    POST_SCREW_CUT_TO_FIT_SHORT,
    SKU,
    inch_text,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_vn_post_mount_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
TITLE = "Cone Pivot Post Mount Screw — Altered Item Drawing"
DRAWING_SUMMARY = {
    0: TITLE,
    1: "Cut length of purchased screw stock",
    2: "Harmonic Analyzer Project",
    3: f"MHA-DT-VN-61; MSC Industrial Supply {SKU}",
    4: "Native dimension-driven cut length",
}

SHEET_SCALE = (1.0, 1.0)
# The screw lies head left in the turned Front (_lay_front_head_left): the
# under-head face (model y 0) and the cut end (model y -CUT_LENGTH_MM) sit
# on one horizontal line whose midpoint is FRONT_AXIS_MID; the head reaches
# ~6 mm further left.
FRONT_CENTER = (0.115, 0.190)
FRONT_AXIS_MID = (0.118, 0.190)
ISO_CENTER = (0.270, 0.185)
# The cut length reads below the shank, its text under the span's midpoint,
# its one word line beneath it, between its own extension lines.
FRONT_KEEP = {
    CUT_LENGTH_DIMENSION: (FRONT_AXIS_MID[0], FRONT_AXIS_MID[1] - 0.024),
}
# Rule 7: the acceptance does not fit between the extension lines in two
# word lines (round 1: the lines struck the text, rule 14), so it is a
# numbered note the callout links to. The note gives the cut end's
# acceptance against its mate, at the spec band's own places, and the
# engagement minimum as a plain fact (rule 20, the spec's floored worst case).
CUT_LENGTH_NOTE_NUMBER = 1
CUT_LENGTH_CALLOUT = f"SEE NOTE {CUT_LENGTH_NOTE_NUMBER}"
DIMENSION_CALLOUTS = {CUT_LENGTH_DIMENSION: CUT_LENGTH_CALLOUT}
CUT_LENGTH_NOTE = (
    f"{CUT_LENGTH_NOTE_NUMBER}. CUT END FLUSH TO "
    f"{inch_text(POST_SCREW_CUT_TO_FIT_SHORT, CUT_TO_FIT_SHORT_PLACES)} "
    "SHORT OF MHA-DT-20 UNDERSIDE.\n"
    f"    ENGAGEMENT {POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN."
)

FRONT_PRECISION = {
    CUT_LENGTH_DIMENSION: DRAWING_PRECISION_BY_NAME[CUT_LENGTH_DIMENSION]
}
# Below the Front's cut-length callout, above the stock rows: note 1 first,
# then the general reference note.
CUT_LENGTH_NOTE_XY = (0.016, 0.118)
NOTES_XY = (0.016, 0.100)
STOCK_ROWS = (
    ("Supplier", 0.016, 0.060),
    ("Supplier SKUs", 0.080, 0.060),
    ("Stock Name", 0.016, 0.049),
)
# The turned Front's axis must read horizontal to within AXIS_TOL_M, and its
# midpoint land within MID_TOL_M of FRONT_AXIS_MID, in sheet metres.
AXIS_TOL_M = 1e-6
MID_TOL_M = 0.00005


def activate_front_for_notes(adapter: Any, front: Any) -> None:
    """Make the Front the active view before the property-linked notes: a
    note lands in the ACTIVE view."""
    name = view_name(adapter, front)
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate the Front view {name!r} for the notes")


def _lay_front_head_left(adapter: Any, front: Any) -> None:
    """Turn the finished Front so the screw lies on a horizontal axis, head
    left, as it reads in the lathe (rule 11). The turn is measured from the
    projected axis, under-head face to cut end, not assumed; then the axis
    midpoint is set on FRONT_AXIS_MID.
    """
    view = _early_bound(front, "IView")
    axis = ((0.0, 0.0, 0.0), (0.0, -CUT_LENGTH_MM / 1000.0, 0.0))
    label = "finished Front axis"
    head, tip = model_points_in_view(adapter, view, axis, label=label)
    view.Angle = float(view.Angle) - math.atan2(tip[1] - head[1], tip[0] - head[0])
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("cannot rebuild the turned finished Front")
    view.UpdateViewDisplayGeometry()
    head, tip = model_points_in_view(adapter, view, axis, label=label)
    position = tuple(float(value) for value in view.Position)
    if not view.SetViewPosition(
        double_array(
            [
                position[index]
                + FRONT_AXIS_MID[index]
                - (head[index] + tip[index]) / 2.0
                for index in range(2)
            ]
        ),
        False,
    ):
        raise RuntimeError("cannot position the turned finished Front")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("cannot rebuild the positioned finished Front")
    view.UpdateViewDisplayGeometry()
    head, tip = model_points_in_view(adapter, view, axis, label=label)
    _telemetry.info(
        f"{label}: head_m={head!r} tip_m={tip!r} angle={float(view.Angle)!r}"
    )
    if (
        abs(tip[0] - head[0] - CUT_LENGTH_MM / 1000.0) > AXIS_TOL_M
        or abs(tip[1] - head[1]) > AXIS_TOL_M
        or math.dist(
            ((head[0] + tip[0]) / 2.0, (head[1] + tip[1]) / 2.0), FRONT_AXIS_MID
        )
        > MID_TOL_M
    ):
        raise RuntimeError(
            f"finished Front is not head-left on its axis: {head!r} -> {tip!r}"
        )


def _view_dimension_names(adapter: Any, view: Any) -> list[str]:
    return [
        dimension_name(adapter, _early_bound(item, "IAnnotation"))
        for item in (_early_bound(view, "IView").GetAnnotations() or ())
    ]


def _reference_cut_length(adapter: Any, annotations: list[Any]) -> None:
    """Re-read the imported cut length, then mark it reference.

    It must be the model's nominal and carry NO band (swTolNONE): a band
    would promise a fixed length the post and plate bands cannot honour.
    """
    for annotation in annotations:
        if dimension_name(adapter, annotation) != CUT_LENGTH_DIMENSION:
            continue
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - CUT_LENGTH_MM / 1000.0) > 1e-9:
            raise RuntimeError(
                f"cut length {float(dimension.SystemValue)!r} m is not the "
                f"modelled {CUT_LENGTH_MM} mm"
            )
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 0:  # swTolNONE
            raise RuntimeError("cut length carries a band; it must be reference")
        set_reference_dimension(adapter, annotation, label="cut length")
        return
    raise RuntimeError("Front view has no cut length to mark reference")


def _verify_finished_controls(adapter, front, installed_configuration) -> None:
    """Read the finished cut/fit control after final rebuild."""
    if (
        str(_early_bound(front, "IView").ReferencedConfiguration)
        != installed_configuration
    ):
        raise RuntimeError("finished view no longer references the installed solid")
    front_names = [name for name in _view_dimension_names(adapter, front) if name]
    if front_names != [CUT_LENGTH_DIMENSION]:
        raise RuntimeError("finished Front no longer carries only its cut length")
    annotations = [
        _early_bound(raw, "IAnnotation")
        for raw in (_early_bound(front, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(raw, "IAnnotation"))
        == CUT_LENGTH_DIMENSION
    ]
    if len(annotations) != 1:
        raise RuntimeError("finished sheet lost its one cut-to-fit reference length")
    assert_imported_precision(adapter, annotations, FRONT_PRECISION)
    display = _early_bound(annotations[0].GetSpecificAnnotation(), "IDisplayDimension")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    if (
        str(native.FullName).split("@")[:2] != [CUT_LENGTH_DIMENSION, CUT_LENGTH_SKETCH]
        or abs(float(native.SystemValue) * 1000.0 - CUT_LENGTH_MM) > 1e-6
        or int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0
        or str(display.GetText(1) or "") != "("
        or str(display.GetText(2) or "") != ")"
        or str(display.GetText(4) or "") != CUT_LENGTH_CALLOUT
        or display.GetOverride()
        or not display.ShowDimensionValue
        or annotations[0].IsDangling()
        or not any(annotations[0].GetAttachedEntities3() or ())
    ):
        raise RuntimeError("finished cut-to-fit reference changed")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open post mount screw", await adapter.open_model(str(SOURCE)))
    installed_configuration = str(
        _early_bound(
            _early_bound(
                adapter.currentModel.ConfigurationManager, "IConfigurationManager"
            ).ActiveConfiguration,
            "IConfiguration",
        ).Name
    )
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(adapter, draw, DRAWING_SUMMARY)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    _lay_front_head_left(adapter, front)

    # The cut length lives on a part-hidden reference sketch, so the Front
    # view takes the opt-in curation that shows it in this view only.
    annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="cut length",
        dimensions_by_feature=FRONT_VIEW_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, FRONT_PRECISION)
    _reference_cut_length(adapter, annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)

    activate_front_for_notes(adapter, front)
    cut_note = _literal_note(adapter, CUT_LENGTH_NOTE, *CUT_LENGTH_NOTE_XY)
    if str(cut_note.GetText()).split() != CUT_LENGTH_NOTE.split():
        raise RuntimeError("cut-length note 1 did not keep its text")
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.003
    )
    for name, x, y in STOCK_ROWS:
        add_property_linked_note(adapter, name, x, y, char_height=0.003)
    set_hidden_lines_removed(adapter, front)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title=TITLE,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _verify_finished_controls(adapter, front, installed_configuration),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
