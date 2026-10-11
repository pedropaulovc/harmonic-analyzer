r"""Manufacturing print for the composite platen rack, MHA-PD-005.

The long front/top/end group is aligned at 1:1. A separately labelled 4:1
end view defines the stepped brass section and soft-solder seam in solid
lines. The standard shaded-with-edges isometric supplements those views.
All sizes, decimal places and note contents come from the saved part and
its pure-data spec; this recipe owns only placement.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_callout,
    add_property_linked_note,
    assert_dimension_measures,
    assert_imported_precision,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    property_link,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from pd_platen_rack_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOMINALS_MM,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_DIMENSIONS,
    FIRST_GAP_X,
    PITCH_LINE_Y,
    RACK_FLANK_INSPECTION_PROPERTY,
    RACK_THICKNESS,
    RACK_Z0,
    half_width,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["pd_platen_rack"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.190, 0.185)
TOP_CENTER = (FRONT_CENTER[0], 0.230)
END_CENTER = (0.355, 0.120)
END_SCALE = (4, 1)
ISO_CENTER = (0.155, 0.115)
ISO_SCALE = (1, 2)
FRONT_KEEP = {
    "Length": (FRONT_CENTER[0], 0.205),
    "OverallHeight": (0.340, FRONT_CENTER[1]),
}
END_KEEP = {
    "BackerDepth": (END_CENTER[0], 0.082),
    "RackDepth": (END_CENTER[0], 0.156),
    "RackHeight": (0.390, 0.135),
    "RackInset": (0.375, 0.095),
    "SeamHeight": (0.321, 0.112),
}
INCOMING_INSPECTION_XY = (0.020, 0.263)
GEAR_DATA_XY = (0.020, 0.254)
# One-line requirement (option (c)) ending at x ~48, left of the first gap
# flank at x ~55: SolidWorks takes the leader from the nearer, right end,
# so it runs down-right clear of its own text and left of the Length
# dimension line's start.
FLANK_INSPECTION_XY = (0.016, 0.214)
# Under the isometric's label (y ~0.077, run 9 touched its first line), left
# of the title block (x 0.216) and above the border.
NOTES_XY = (0.020, 0.064)
# Centred under the 4:1 end view (axis x ~0.355), between the BackerDepth
# dimension line (y ~0.0795) and the title block top (y 0.066).
END_NOTE_XY = (0.330, 0.074)
ISO_NOTE_XY = (0.104, 0.077)


def _assert_native_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Retain native controls and purchased-stock/composite reference sizes."""
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    found: set[str] = set()
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name in found or name not in DRAWING_NOMINALS_MM:
            raise RuntimeError(f"rack sheet has unexpected or duplicate size {name!r}")
        found.add(name)
        raw_display = annotation.GetSpecificAnnotation()
        if raw_display is None:
            raise RuntimeError(f"rack size {name!r} has no display dimension")
        display = _early_bound(raw_display, "IDisplayDimension")
        assert_dimension_measures(
            adapter,
            display,
            expected_mm=DRAWING_NOMINALS_MM[name],
            label=name,
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        # swTolNONE = 0: fabricated .XX controls use the title block. Bought
        # sizes and their composite height keep part-authored parentheses.
        # Every size here is equation-owned, and an equation-owned dimension
        # reads DrivenState 1, never 2 (build_dt_cone_gear_shaft's station
        # ownership gate); "not a driven reference" is IsReference() False.
        tolerance_type = int(tolerance.Type)
        is_reference = bool(dimension.IsReference())
        if tolerance_type != 0 or is_reference:
            raise RuntimeError(
                f"rack size {name!r} lost its native tolerance state "
                f"(tolerance type {tolerance_type}, IsReference {is_reference}, "
                f"DrivenState {int(dimension.DrivenState)})"
            )
        reference = name in DRAWING_REFERENCE_DIMENSIONS
        if bool(display.ShowParenthesis) != reference or bool(annotation.IsDangling()):
            raise RuntimeError(f"rack size {name!r} has wrong reference state or is dangling")
    missing = DRAWING_NOMINALS_MM.keys() - found
    if missing:
        raise RuntimeError(f"rack sheet is missing sizes {sorted(missing)}")


def _add_rack_flank_callout(adapter: Any, view: Any) -> Any:
    """Link the flank inspection to a real finite nominal SeedGap flank.

    CAD phase locates graphics ONLY. It supplies neither the physical
    inspection datum nor manufactured end-phase acceptance.
    """
    edge_xy = model_point_in_view(
        adapter, view,
        ((FIRST_GAP_X + half_width(PITCH_LINE_Y)) / 1000.0,
         PITCH_LINE_Y / 1000.0, (RACK_Z0 + RACK_THICKNESS) / 1000.0),
        label="rack finite nominal flank inspection leader",
    )
    note = _early_bound(add_property_linked_callout(
        adapter, view, property_name=RACK_FLANK_INSPECTION_PROPERTY,
        edge_xy=edge_xy, note_xy=FLANK_INSPECTION_XY,
    ), "INote")
    raw_annotation = note.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError("rack flank inspection has no native annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError("rack flank inspection has no native text format")
    # Same native font path as add_property_linked_note; no helper fork.
    text_format.CharHeight = 0.0025
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError("rack flank inspection text height did not persist")
    return note


def _assert_rack_flank_callout(note: Any, source_text: str) -> None:
    """Retain model-linked ink and an actual non-dangling EDGE/leader."""
    if note.PropertyLinkedText != property_link(RACK_FLANK_INSPECTION_PROPERTY):
        raise RuntimeError("rack flank inspection lost its source property link")
    resolved = note.GetText()
    if type(resolved) is not str or resolved.replace("\r\n", "\n") != source_text.replace("\r\n", "\n"):
        raise RuntimeError("rack flank inspection differs from the saved source property")
    raw_annotation = note.GetAnnotation()
    if raw_annotation is None:
        raise RuntimeError("rack flank inspection lost its native annotation")
    annotation = _early_bound(raw_annotation, "IAnnotation")
    attached_types = annotation.GetAttachedEntityTypes()
    if (attached_types is None or tuple(attached_types) != (1,)
            or int(annotation.GetAttachedEntityCount3()) != 1
            or int(annotation.GetLeaderCount()) != 1 or bool(annotation.IsDangling())):
        raise RuntimeError("rack flank inspection lost its real edge/leader association")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open platen rack source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Incoming Rack Inspection",
            "Manufacturing Notes",
            RACK_FLANK_INSPECTION_PROPERTY,
            "Isometric View Note",
            "Enlarged End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Incoming Rack Inspection",
            "Manufacturing Notes",
            RACK_FLANK_INSPECTION_PROPERTY,
            "Isometric View Note",
            "Enlarged End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Platen Rack and Backer Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "composite platen rack; stepped section; soft-soldered joint",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=END_SCALE)
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, top, end):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="rack front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            end,
            keep=END_KEEP,
            view_label="rack enlarged end",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Showing EndStockProfile prints the section's real stock outline and seam;
    # it remains hidden in the source part and in the isometric/assembly views.
    for property_name, position in (
        ("Incoming Rack Inspection", INCOMING_INSPECTION_XY),
        ("Gear Data", GEAR_DATA_XY),
        ("Manufacturing Notes", NOTES_XY),
        ("Enlarged End View Note", END_NOTE_XY),
        ("Isometric View Note", ISO_NOTE_XY),
    ):
        add_property_linked_note(adapter, property_name, *position, char_height=0.0025)
    flank_callout = _add_rack_flank_callout(adapter, front)
    for view in (front, top, end):
        set_hidden_lines_removed(adapter, view)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Rack and Backer Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_native_dimensions(adapter, annotations),
            lambda: _assert_rack_flank_callout(flank_callout, properties[RACK_FLANK_INSPECTION_PROPERTY]),
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", nargs="?", default=PART_STEM, choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))
