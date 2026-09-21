r"""Create the pinion-arbor manufacturing drawing under the simplicity policy.

The running journal keeps its native size fit and one bearing-surface finish.
No datum or geometric-control frame is warranted for this plain shaft.  The
sole horizontal longitudinal view looks along the transverse handle-retention
hole axis, so the match-reamed hole is a true circle rather than hidden lines.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    set_reference_dimensions,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_arbor_spec import (
    CAP_R,
    CAP_SAG,
    DRAWING_PRECISION_BY_NAME,
    RETENTION_HOLE_CALLOUT,
    SHAFT_DIA,
    SHAFT_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    delete_view,
    iter_views,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_arbor"]
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
OVERALL_LEN = SHAFT_LEN + CAP_SAG
PRINCIPAL_CENTER = (0.205, 0.180)
ISO_CENTER = (0.355, 0.115)

# ShaftDia is authored in the end-profile sketch, so a temporary end view
# donates that native dimension to the sole longitudinal manufacturing view.
DONOR_KEEP = {"ShaftDia": (0.030, 0.220)}
PRINCIPAL_KEEP = {
    "Depth": (PRINCIPAL_CENTER[0], PRINCIPAL_CENTER[1] - 0.025),
    "CapSagDim": (
        PRINCIPAL_CENTER[0] - OVERALL_LEN / 2000.0 - 0.020,
        PRINCIPAL_CENTER[1] + 0.035,
    ),
    "RetentionHoleDia": (0.344, PRINCIPAL_CENTER[1] + 0.055),
    "RetentionPinStation": (0.330, PRINCIPAL_CENTER[1] - 0.030),
}
SHAFT_DIAMETER_XY = (PRINCIPAL_CENTER[0] + 0.055, PRINCIPAL_CENTER[1] + 0.025)
SHAFT_FLANK_Y = PRINCIPAL_CENTER[1] + SHAFT_DIA / 2000.0
DIMENSION_CALLOUTS = {
    "CapSagDim": f"SR{CAP_R:.1f} CROWN",
    "RetentionHoleDia": RETENTION_HOLE_CALLOUT,
}


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a native model dimension and verify its new drawing-view owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name,
        "DIMENSION",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(f"failed to select model dimension {name}: {selection_name!r}")
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    matches = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(item, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-arbor source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Arbor Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion arbor; zeroing-drum shaft; handle retention pin",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    donor = place_view(adapter, str(SOURCE), "*Front", 0.030, 0.205, scale=(2, 1))
    # Looking along model Y shows the transverse retention hole as a true
    # circle.  Rotate that longitudinal view in the sheet so it is also the
    # single horizontal turning profile; a second long view would be redundant.
    principal = place_view(
        adapter, str(SOURCE), "*Top", *PRINCIPAL_CENTER, scale=SHEET_SCALE
    )
    principal_native = _early_bound(principal, "IView")
    principal_native.Angle = -math.pi / 2.0
    if abs(math.remainder(float(principal_native.Angle) + math.pi / 2.0, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to orient the retention-hole profile horizontally")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (donor, principal, iso):
        set_hidden_lines_removed(adapter, view)

    donor_annotations = curate_view_dimensions(
        adapter, donor, keep=DONOR_KEEP, view_label="diameter donor"
    )
    principal_annotations = curate_view_dimensions(
        adapter,
        principal,
        keep=PRINCIPAL_KEEP,
        view_label="principal retention-hole profile",
    )
    shaft_diameter = _move_dimension(
        adapter,
        donor_annotations[0],
        principal,
        SHAFT_DIAMETER_XY,
        source_view=donor,
    )
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")

    annotations = [shaft_diameter, *principal_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_reference_dimensions(adapter, annotations, {"RetentionHoleDia"})
    for name in ("CapSagDim", "RetentionPinStation"):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one arbor {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"arbor {name} reference")

    if not auto_center_marks(adapter, principal, holes=True, size=0.0025):
        raise RuntimeError("failed to add center mark to retention-hole view")
    add_view_centerline(
        adapter,
        principal,
        face_xy=(PRINCIPAL_CENTER[0], PRINCIPAL_CENTER[1] + 0.001),
        label="pinion arbor turning axis",
    )
    add_surface_finish(
        adapter,
        principal,
        edge_xy=(PRINCIPAL_CENTER[0] + 0.040, SHAFT_FLANK_Y),
        symbol_xy=(PRINCIPAL_CENTER[0] + 0.045, PRINCIPAL_CENTER[1] + 0.050),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="arbor bearing finish",
        entity_type="SILHOUETTE",
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Arbor Manufacturing Drawing",
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
