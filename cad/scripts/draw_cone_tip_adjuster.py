r"""Create the curated machinist drawing for the cone tip adjuster set screw."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_feature_control_frame,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_tip_adjuster_spec import (
    BODY_DIA,
    BODY_LEN,
    CHAMFER,
    CUP_DIA,
    SLOT_W,
    THREAD,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
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

# The screw is 14 mm long x nominal Ø7.9375: at 4:1 the elevation is compact.
# Third angle: the slotted head and cup-end views sit below the elevation.
FRONT_CENTER = (0.095, 0.180)
END_CENTER = (0.095, 0.100)
CUP_CENTER = (0.190, 0.100)
ISO_CENTER = (0.300, 0.160)

FRONT_KEEP = {
    "BodyLenDim": (FRONT_CENTER[0] - 0.045, FRONT_CENTER[1]),
}
END_KEEP = {
    "BodyDiaDim": (END_CENTER[0] + 0.055, END_CENTER[1] + 0.015),
    "SlotWDim": (END_CENTER[0] + 0.055, END_CENTER[1] - 0.015),
}
CUP_KEEP = {
    "CupDiaDim": (CUP_CENTER[0] + 0.050, CUP_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "BodyDiaDim": f"{THREAD} UNC-2A",
    "BodyLenDim": "+/-0.10",
    "SlotWDim": "+/-0.10",
    "CupDiaDim": "+0.05/-0.00 X 6.00 +/-0.10 DEEP",
}


def _circular_edge(
    view: Any, *, radius_mm: float, center_y_mm: float
) -> Any:
    """Return the visible circular model edge at the requested axis station."""
    drawing_view = _early_bound(view, "IView")
    candidates: list[tuple[float, float, Any]] = []
    for component in drawing_view.GetVisibleComponents() or []:
        for raw_edge in drawing_view.GetVisibleEntities2(component, 1) or []:
            edge = _early_bound(raw_edge, "IEdge")
            curve = edge.GetCurve()
            if curve is None:
                continue
            curve = _early_bound(curve, "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
            candidates.append((params[6], params[1], edge))
    if not candidates:
        raise RuntimeError("drawing view has no circular model edges")
    radius, center_y, edge = min(
        candidates,
        key=lambda item: abs(item[0] - radius_mm) + abs(item[1] - center_y_mm),
    )
    if abs(radius - radius_mm) > 0.01 or abs(center_y - center_y_mm) > 0.01:
        raise RuntimeError(
            f"no circular edge matches radius {radius_mm:.4f} mm at "
            f"axis station {center_y_mm:.3f} mm"
        )
    return edge


def _add_axis_datum_to_dimension(
    adapter: Any,
    annotation: Any,
    *,
    datum: str,
    symbol_xy: tuple[float, float],
) -> None:
    """Attach a datum axis to the cylindrical feature-of-size dimension."""
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    annotation = _early_bound(annotation, "IAnnotation", "Select2")
    if not annotation.Select2(False, 0):
        raise RuntimeError("failed to select thread diameter dimension for datum A")
    tag = draw.InsertDatumTag2()
    if tag is None:
        raise RuntimeError("failed to insert datum A on thread diameter dimension")
    tag = _early_bound(tag, "IDatumTag", "SetLabel", "GetAnnotation", "GetLabel")
    if not tag.SetLabel(datum):
        raise RuntimeError(f"failed to label thread-axis datum {datum}")
    tag_annotation = _early_bound(tag.GetAnnotation(), "IAnnotation", "SetPosition2")
    if not tag_annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position thread-axis datum {datum}")
    if str(tag.GetLabel()) != datum:
        raise RuntimeError(f"thread-axis datum {datum} did not persist")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


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
            3: "cone tip adjuster; 5/16-18 slotted set screw; black oxide",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=(4, 1))
    cup = place_view(adapter, str(SOURCE), "*Top", *CUP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # The elevation shows the blind cup as hidden lines; the head end view
    # exposes the driver slot across the OD.
    for view in (front, end, cup):
        set_hidden_lines_visible(adapter, view)
    thread_seeds, thread_instances = import_cosmetic_threads(adapter, front)
    if (thread_seeds, thread_instances) != (1, 1):
        raise RuntimeError(
            "expected one cosmetic external thread in front view, got "
            f"{thread_seeds} seeds / {thread_instances} instances"
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
        [*front_annotations, *end_annotations, *cup_annotations],
        DIMENSION_CALLOUTS,
    )
    set_reference_dimensions(adapter, end_annotations, ("BodyDiaDim",))
    end_by_name = {
        dimension_name(adapter, annotation): annotation
        for annotation in end_annotations
    }
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the head end view")
    if not auto_center_marks(adapter, cup, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the cup-end view")

    _add_axis_datum_to_dimension(
        adapter,
        end_by_name["BodyDiaDim"],
        datum="A",
        symbol_xy=(END_CENTER[0] + 0.075, END_CENTER[1] + 0.028),
    )
    cup_edge = _circular_edge(cup, radius_mm=CUP_DIA / 2.0, center_y_mm=BODY_LEN)
    add_feature_control_frame(
        adapter,
        cup,
        edge_xy=(CUP_CENTER[0] + 0.004, CUP_CENTER[1]),
        frame_xy=(CUP_CENTER[0] + 0.050, CUP_CENTER[1] + 0.032),
        characteristic="position",
        tolerance="0.05",
        datums=("A",),
        diameter=True,
        label="cup axis position",
        entity=cup_edge,
    )
    add_feature_control_frame(
        adapter,
        end,
        edge_xy=(
            END_CENTER[0],
            END_CENTER[1] + SLOT_W / 2.0 * SHEET_SCALE[0] / 1000.0,
        ),
        frame_xy=(END_CENTER[0] + 0.065, END_CENTER[1] - 0.040),
        characteristic="position",
        tolerance="0.10",
        datums=("A",),
        quantity="SLOT MEDIAN PLANE",
        label="driver-slot median-plane position",
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
