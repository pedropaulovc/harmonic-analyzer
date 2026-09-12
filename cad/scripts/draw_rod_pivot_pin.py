"""Manufacturing blank and installed-state drawing for the peened rod pivot."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs, add_attached_note, add_edge_dimension,
    add_property_linked_note, curate_view_dimensions, finalize_drawing,
    model_point_in_view, new_project_drawing, read_required_properties,
    set_hidden_lines_visible, set_reference_dimension, stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from rod_pivot_pin_notes import (
    ASSEMBLY_CALLOUT, BLANK_LENGTH_CALLOUT, JOURNAL_CALLOUT, UPSET_CALLOUT,
    HEAD_DIAMETER_CALLOUT, HEAD_RIM_CALLOUT,
)
import rod_pivot_spec as pivot
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["rod_pivot_pin"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (10.0, 1.0)
# Right is the horizontal lathe-axis view of this Z-axis pin. Front is its
# third-angle end view to the LEFT; both share the same projected axis height.
SIDE_CENTER = (0.155, 0.200)
END_CENTER = (0.055, SIDE_CENTER[1])
ISO_CENTER = (0.330, 0.200)
INSTALLED_CENTER = (0.100, 0.092)


def _text(display: Any, *, below: str = "", diameter: bool = False) -> None:
    display = _early_bound(display, "IDisplayDimension")
    for compartment, text in ((1, "<MOD-DIAM>" if diameter else ""), (4, below)):
        if not text:
            continue
        display.SetText(compartment, text)  # SetText is void, not a bool.
        if str(display.GetText(compartment) or "") != text:
            raise RuntimeError(f"pivot dimension text did not persist: {text!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    check("open pivot source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        ("Number", "Material Specification", "Finish", "Quantity", "Manufacturing Notes"),
        required=("Number", "Material Specification", "Finish", "Quantity", "Manufacturing Notes"),
    )
    drawing, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
    )
    stamp_drawing_summary(adapter, drawing, {
        0: "Rod Pivot Pin — Blank and Installed State",
        1: "Harmonic Analyzer hobby-machinist book drawing",
        2: "Harmonic Analyzer Project",
        3: "one-headed blank; matched pivot; peened assembly",
        4: "Project-owned ASME B drawing standard",
    })

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SHEET_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    installed = place_view(adapter, str(SOURCE), "*Right", *INSTALLED_CENTER, scale=SHEET_SCALE)
    for view in (side, end, iso):
        view.ReferencedConfiguration = pivot.PIN_BLANK_CONFIGURATION
    installed.ReferencedConfiguration = "Default"
    drawing.EditRebuild3()
    for view in (side, end, installed):
        set_hidden_lines_visible(adapter, view)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add pivot end-view center mark")

    # The stock/grip boundary disappears on the merged cylinder. Import the
    # real extrusion-length dimension rather than inventing a visible edge.
    tail_annotations = curate_view_dimensions(
        adapter, side, keep={"UpsetAllowance": (0.103, 0.168)}, view_label="blank side",
    )
    for annotation in tail_annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        _text(annotation.GetSpecificAnnotation(), below=UPSET_CALLOUT)
    # Every dimension below is attached to actual source geometry. Project
    # model coordinates rather than assuming where an asymmetric blank's
    # bounding box/origin lands after switching the view configuration.
    def point(y: float, z: float, view: Any = side) -> tuple[float, float]:
        return model_point_in_view(adapter, view, (0.0, y / 1000.0, z / 1000.0), label="pivot geometry")

    grip_half = pivot.PIN_GRIP_LENGTH / 2.0
    head_outer = -grip_half - pivot.PIN_HEAD_THICKNESS
    tail_end = grip_half + pivot.PIN_UPSET_ALLOWANCE
    head_mid = -grip_half - pivot.PIN_HEAD_THICKNESS / 2.0
    diameter = add_edge_dimension(
        adapter, side,
        p0=point(-pivot.PIN_JOURNAL_DIA / 2.0, 0.0),
        p1=point(pivot.PIN_JOURNAL_DIA / 2.0, 0.0),
        text_xy=(0.105, 0.248), orientation="vertical", entity_type="SILHOUETTE",
        label="matched running journal diameter",
    )
    _text(diameter, diameter=True, below=JOURNAL_CALLOUT)
    set_reference_dimension(adapter, _early_bound(diameter, "IDisplayDimension").GetAnnotation(),
                            label="matched journal nominal", diameter=True)
    head_diameter = add_edge_dimension(
        adapter, side,
        p0=point(-pivot.PIN_HEAD_DIA / 2.0, head_mid),
        p1=point(pivot.PIN_HEAD_DIA / 2.0, head_mid),
        text_xy=(0.225, 0.225), orientation="vertical", entity_type="SILHOUETTE",
        label="preformed head diameter",
    )
    _text(head_diameter, diameter=True, below="PREFORMED HEAD")
    head_height = add_edge_dimension(
        adapter, side, p0=point(1.2, head_outer), p1=point(1.2, -grip_half),
        text_xy=(0.205, 0.165), orientation="horizontal", label="preformed head height",
    )
    _text(head_height)
    overall = add_edge_dimension(
        adapter, side, p0=point(0.6, head_outer), p1=point(0.6, tail_end),
        text_xy=(0.155, 0.142), orientation="horizontal", label="blank overall length",
    )
    _text(overall, below=BLANK_LENGTH_CALLOUT)
    set_reference_dimension(adapter, _early_bound(overall, "IDisplayDimension").GetAnnotation(),
                            label="matched blank length nominal")

    # Independent installed-state view, intentionally not an orthographic
    # projection of the blank. It shows the second head after assembly, not an
    # insertable two-headed stock item or a simulated forming operation.
    add_attached_note(
        adapter, installed, text=ASSEMBLY_CALLOUT,
        entity_xy=point(1.2, grip_half + pivot.PIN_HEAD_THICKNESS, installed),
        note_xy=(0.200, 0.105), label="post-peening assembly acceptance",
    )
    formed_diameter = add_edge_dimension(
        adapter, installed,
        p0=point(-pivot.PIN_HEAD_DIA / 2.0, grip_half + pivot.PIN_HEAD_THICKNESS / 2.0, installed),
        p1=point(pivot.PIN_HEAD_DIA / 2.0, grip_half + pivot.PIN_HEAD_THICKNESS / 2.0, installed),
        text_xy=(0.245, 0.145), orientation="vertical", entity_type="SILHOUETTE",
        label="formed head nominal envelope diameter",
    )
    _text(formed_diameter, diameter=True, below=HEAD_DIAMETER_CALLOUT)
    set_reference_dimension(adapter, _early_bound(formed_diameter, "IDisplayDimension").GetAnnotation(),
                            label="formed head nominal diameter", diameter=True)
    formed_height = add_edge_dimension(
        adapter, installed, p0=point(1.2, grip_half, installed),
        p1=point(1.2, grip_half + pivot.PIN_HEAD_THICKNESS, installed),
        text_xy=(0.090, 0.065), orientation="horizontal", label="formed head nominal envelope height",
    )
    _text(formed_height, below=HEAD_RIM_CALLOUT)
    set_reference_dimension(adapter, _early_bound(formed_height, "IDisplayDimension").GetAnnotation(),
                            label="formed head nominal height")
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.038)
    return await finalize_drawing(
        adapter, OUTPUTS, pdf_title="Rod Pivot Pin — Blank and Installed State",
        scale=SHEET_SCALE, layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
