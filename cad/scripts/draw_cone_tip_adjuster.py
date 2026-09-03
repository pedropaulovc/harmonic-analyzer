r"""Create the curated machinist drawing for the cone tip adjuster set screw.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
slotted set screw carries no datums, no feature-control frames and no
roughness symbols -- the two fitted features (cup bore, driver slot) carry
their bands on the model dimensions and the title block governs the rest.
The blind cup and the driver slot are dimensioned in SECTION A-A, cut
through the screw axis, never to a hidden line.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimensions,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_tip_adjuster_spec import (
    BODY_DIA,
    BODY_LEN,
    CHAMFER,
    CHAMFER_NOTE,
    CUP_DEPTH,
    SLOT_D,
    THREAD,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_tip_adjuster"]
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

SHEET_SCALE = (4.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# The screw is 14 mm long x nominal Ø6.2: at 4:1 the elevation is compact.
# Third angle: the slotted head and cup-end views sit below the elevation;
# SECTION A-A stands higher beside the elevation so its generated two-line
# caption cannot overprint the CUP END VIEW label below.
FRONT_CENTER = (0.095, 0.180)
END_CENTER = (0.095, 0.100)
CUP_CENTER = (0.190, 0.100)
SECTION_CENTER = (0.205, 0.210)
ISO_CENTER = (0.300, 0.160)
# Cutting line projected from the model-axis endpoints, then extended past both
# ends of the 14 mm elevation.  IView position is the model origin, not the
# body's bounding-box centre, so a sheet-space half-span about FRONT_CENTER
# does not reliably cross the whole part.
SECTION_LINE_OVERSHOOT = 0.011

FRONT_KEEP = {
    "BodyLenDim": (FRONT_CENTER[0] - 0.045, FRONT_CENTER[1]),
    "BodyDiaDim": (FRONT_CENTER[0] + 0.060, FRONT_CENTER[1] + 0.010),
}
END_KEEP = {
    "SlotWDim": (END_CENTER[0] + 0.055, END_CENTER[1] - 0.015),
}
CUP_KEEP = {
    "CupDiaDim": (CUP_CENTER[0] + 0.050, CUP_CENTER[1]),
}
# Section A-A: the cup depth (from the north end) and the slot depth (from
# the head end), placed beside the cut at their model stations.  The cutting
# line is vertical in the front view, so the section plane is x = 0 and its
# in-plane sideways direction is model Z: offsets are (z mm, y mm), and the
# section's own transform places them (either side of the axis is fine).
SECTION_KEEP_MODEL_MM = {
    "CupDepth": (BODY_DIA / 2.0 + 9.0, BODY_LEN - CUP_DEPTH / 2.0),
    "SlotDepth": (BODY_DIA / 2.0 + 9.0, SLOT_D / 2.0),
}
# Only NON-tolerance annotation survives here. Every band moved onto the model
# dimension in build_cone_tip_adjuster (cone_tip_adjuster_spec.GENERAL_TOL_MM /
# CUP_DIA_BAND), where SolidWorks renders it natively.
#
# The two entries that remain are sheet annotation, not specification:
#   BodyDiaDim - the thread designation, already derived from the spec's THREAD.
#   CupDiaDim  - the process for the blind flat-floored cup.
DIMENSION_CALLOUTS = {
    "BodyDiaDim": f"{THREAD} UNC",
    "CupDiaDim": "END MILL, FLAT FLOOR",
}
CHAMFER_NOTE_XY = (0.125, 0.220)


def _chamfer_rim(adapter: Any, view: Any) -> Any:
    """The north thread-start chamfer's boundary with the body, by entity.

    A circle of the body radius at ``BODY_LEN - CHAMFER``: an edge-on circle
    in the elevation, selectable by entity where a sheet pick is not.
    """
    radius_mm = BODY_DIA / 2.0
    center_y_mm = BODY_LEN - CHAMFER
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="adjuster chamfer rims"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        candidates.append(
            (abs(params[6] - radius_mm) + abs(params[1] - center_y_mm), edge)
        )
    if not candidates or min(candidates, key=lambda item: item[0])[0] > 0.02:
        raise RuntimeError(
            f"elevation has no chamfer rim of radius {radius_mm:.3f} mm at "
            f"y={center_y_mm:.3f} mm"
        )
    return min(candidates, key=lambda item: item[0])[1]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-adjuster source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Adjuster Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"cone tip adjuster; {THREAD} slotted set screw; black oxide",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=(4, 1))
    cup = place_view(adapter, str(SOURCE), "*Top", *CUP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # SECTION A-A: project the actual axial endpoints into the placed view and
    # extend them in model space.  This makes the cutting line cross the whole
    # screw instead of assuming that FRONT_CENTER is the body's mid-length.
    # A complete cut exposes the blind cup's walls and flat floor as visible
    # profile geometry; no duplicate sketch geometry is drawn over the view.
    axis_overshoot_mm = SECTION_LINE_OVERSHOOT / _S
    section_line_start = model_point_in_view(
        adapter,
        front,
        (0.0, -axis_overshoot_mm / 1000.0, 0.0),
        label="adjuster section start",
    )
    section_line_end = model_point_in_view(
        adapter,
        front,
        (0.0, (BODY_LEN + axis_overshoot_mm) / 1000.0, 0.0),
        label="adjuster section end",
    )
    section = create_section_view(
        adapter,
        front,
        line_start=section_line_start,
        line_end=section_line_end,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(4, 1),
        label="adjuster axial section",
    )
    # A set screw is a fastener by project/catalog intent, but this is its part
    # drawing: the section must cut it.  Rebuild after explicit inclusion, then
    # verify both that inclusion persisted and that the resulting section owns
    # real face hatches.
    section_view = _early_bound(section, "IView")
    section_definition = section_view.GetSection()
    if section_definition is None:
        raise RuntimeError("adjuster axial section has no section definition")
    section_definition = _early_bound(section_definition, "IDrSection")
    section_definition.ExcludeFasteners = False
    check("rebuild adjuster axial section", drawing_model.EditRebuild3())
    if bool(section_definition.ExcludeFasteners):
        raise RuntimeError("adjuster axial section still excludes fasteners")
    hatch_count = int(
        adapter._attempt(lambda: section_view.GetFaceHatchCount(), default=-1)
    )
    if hatch_count <= 0:
        raise RuntimeError(
            f"adjuster axial section has no visible face hatch (count={hatch_count})"
        )
    # Hidden lines remain useful in the three ordinary orthographic views.
    # SECTION A-A is HLR so the newly exposed cup walls/floor are solid cut
    # edges, with no dashed hidden cavity competing with the hatch.
    for view in (front, end, cup):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, section)
    thread_seeds, thread_instances = import_cosmetic_threads(adapter, front)
    if (thread_seeds, thread_instances) != (1, 1):
        raise RuntimeError(
            "expected one cosmetic external thread in front view, got "
            f"{thread_seeds} seeds / {thread_instances} instances"
        )

    # The section claims its two depths FIRST: SolidWorks imports each marked
    # model dimension into one view only (draw_pinion_bracket).
    section_keep = {
        name: model_point_in_view(
            adapter, section, (0.0, y_mm / 1000.0, z_mm / 1000.0), label=name
        )
        for name, (z_mm, y_mm) in SECTION_KEEP_MODEL_MM.items()
    }
    section_annotations = curate_view_dimensions(
        adapter, section, keep=section_keep, view_label="section"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    cup_annotations = curate_view_dimensions(
        adapter, cup, keep=CUP_KEEP, view_label="cup end"
    )
    set_dimension_callouts(
        adapter,
        [*section_annotations, *front_annotations, *end_annotations, *cup_annotations],
        {
            name: text
            for name, text in DIMENSION_CALLOUTS.items()
            if name != "BodyDiaDim"
        },
    )
    set_dimension_callouts(
        adapter,
        front_annotations,
        {"BodyDiaDim": DIMENSION_CALLOUTS["BodyDiaDim"]},
        location="above",
    )
    set_reference_dimensions(adapter, front_annotations, ("BodyDiaDim",))
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the head end view")
    if not auto_center_marks(adapter, cup, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the cup-end view")

    # Both thread-start chamfers, flagged from the north chamfer rim.
    add_attached_note(
        adapter,
        front,
        text=CHAMFER_NOTE,
        entity=_chamfer_rim(adapter, front),
        note_xy=CHAMFER_NOTE_XY,
        label="thread-start chamfers",
    )

    if add_note(adapter, "SLOT END VIEW", 0.070, 0.132) is None:
        raise RuntimeError("failed to label slot end view")
    if add_note(adapter, "CUP END VIEW", 0.165, 0.132) is None:
        raise RuntimeError("failed to label cup end view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Adjuster Manufacturing Drawing",
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
