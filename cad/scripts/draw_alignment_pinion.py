r"""Create the simplicity-policy drawing for the alignment-pinion drum.

The end view owns the tooth-tip envelope and matched arbor bore.  The aligned
profile owns the full tooth-face width, and the standard isometric supplies
pictorial clarity without replacing either manufacturing view.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    property_link,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from alignment_pinion_spec import (
    BORE_DIA,
    DRAWING_PRECISION_BY_NAME,
    SURFACE_FINISHES,
    TEETH,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["alignment_pinion"]
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
FRONT_SCALE = (2, 1)
PROFILE_SCALE = (1, 1)
ISO_SCALE = (1, 2)
FRONT_CENTER = (0.150, 0.165)
RIGHT_CENTER = (0.285, 0.165)
ISO_CENTER = (0.350, 0.215)
GEAR_DATA_POS = (0.018, 0.262)
ISOMETRIC_NOTE_POS = (0.330, 0.262)
MANUFACTURING_NOTES_POS = (0.018, 0.095)


FRONT_KEEP = {
    "ArborBoreDia": (0.085, 0.155),
    "OutsideDia": (0.150, 0.210),
}
RIGHT_KEEP = {
    "FaceWidth": (RIGHT_CENTER[0], 0.125),
}
DIMENSION_CALLOUTS = {
    "ArborBoreDia": "REAM THRU",
    "FaceWidth": "OVERALL; TEETH FULL LENGTH",
}


def _bind_title_material_specification(
    drawing_model: Any, material_specification: str
) -> tuple[Any, str, str]:
    """Retarget this sheet's material cell to the make-critical stock grade."""
    if not material_specification.strip():
        raise RuntimeError("alignment-pinion material specification is blank")
    drawing = _early_bound(drawing_model, "IDrawingDoc")
    sheet_view = drawing.GetFirstView()
    if sheet_view is None:
        raise RuntimeError("alignment-pinion drawing template has no sheet view")
    sheet_view = _early_bound(sheet_view, "IView")
    generic_link = property_link("Material")
    specification_link = property_link("Material Specification")
    matched = 0
    binding: tuple[Any, str, str] | None = None
    for raw_annotation in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if annotation.GetType() != 6:  # swAnnotationType_e.swNote
            continue
        raw_note = annotation.GetSpecificAnnotation()
        if raw_note is None:
            raise RuntimeError("alignment-pinion title-block note has no INote")
        note = _early_bound(raw_note, "INote")
        raw = str(note.PropertyLinkedText)
        occurrences = raw.count(generic_link)
        if not occurrences:
            continue
        matched += occurrences
        linked_text = raw.replace(generic_link, specification_link)
        resolved_text = raw.replace(generic_link, material_specification)
        note.PropertyLinkedText = linked_text
        if str(note.PropertyLinkedText) != linked_text:
            raise RuntimeError("alignment-pinion material title link did not persist")
        binding = (note, linked_text, resolved_text)
    if matched != 1 or binding is None:
        raise RuntimeError(
            "alignment-pinion template must contain exactly one Material "
            f"property link, found {matched}"
        )
    return binding


def _verify_title_material_specification(
    drawing_model: Any, binding: tuple[Any, str, str]
) -> None:
    """Read the retargeted cell back once a model view can resolve it.

    ``$PRPSHEET`` resolves against the sheet's property view, which only
    exists after the first model view is placed (run 6da5050a failed reading
    it back on the bare template).  The explicit CustomPropertyView pin stays
    in ``finalize_drawing``'s guarded path; until then SolidWorks' default
    source is the first view, which is the front view here.
    """
    drawing_model.ForceRebuild3(False)
    note, linked_text, resolved_text = binding
    actual_link = str(note.PropertyLinkedText)
    actual_text = str(note.GetText())
    if actual_link != linked_text or actual_text != resolved_text:
        raise RuntimeError(
            "alignment-pinion material title link did not resolve: "
            f"expected {resolved_text!r}, got {actual_text!r} "
            f"from {actual_link!r}"
        )


def _match_bore_tolerance_places(adapter: Any, annotations: list[Any]) -> None:
    """Print the bore band with its nominal's two places (+0.10 / 0.00).

    The model's tolerance helper stores the fewest places that spell the band
    (+0.1 / 0.0), which reads as a one-place tolerance on a two-place size.
    Only the tolerance places move here; the primary places stay the part's.
    """
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "ArborBoreDia"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one ArborBoreDia annotation, found {len(matches)}")
    annotation = _sw_type_info.early_bound_or_flag(
        matches[0], "IAnnotation", "GetSpecificAnnotation"
    )
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    places = DRAWING_PRECISION_BY_NAME["ArborBoreDia"]
    # -1 = swDimensionPrecisionSettings_e do-not-change: primary and dual stay.
    display.SetPrecision3(-1, -1, places, -1)
    if int(display.GetPrimaryTolPrecision2()) != places:
        raise RuntimeError(
            f"ArborBoreDia tolerance did not take the nominal's {places} places"
        )


def _use_single_arrow_od_leader(adapter: Any, annotations: list[Any]) -> None:
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "OutsideDia"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one OutsideDia annotation, found {len(matches)}")
    annotation = _sw_type_info.early_bound_or_flag(
        matches[0], "IAnnotation", "GetSpecificAnnotation"
    )
    display = annotation.GetSpecificAnnotation()
    if display is None:
        raise RuntimeError("OutsideDia annotation has no display dimension")
    display = _sw_type_info.early_bound_or_flag(
        display,
        "IDisplayDimension",
        "SetSecondArrow",
        "GetUseDocSecondArrow",
        "GetSecondArrow",
        "SetBrokenLeader2",
        "GetUseDocBrokenLeader",
        "GetBrokenLeader2",
    )
    display.Diametric = True
    display.ArrowSide = 1
    display.SetSecondArrow(False, False)
    display.SolidLeader = False
    if display.SetBrokenLeader2(False, 2) != 0:
        raise RuntimeError("failed to apply broken horizontal OutsideDia leader")
    if (
        bool(display.SolidLeader)
        or bool(display.GetUseDocBrokenLeader())
        or int(display.GetBrokenLeader2()) != 2
        or bool(display.GetUseDocSecondArrow())
        or bool(display.GetSecondArrow())
    ):
        raise RuntimeError("OutsideDia single-arrow leader style did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open alignment-pinion source", await adapter.open_model(str(SOURCE)))
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
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    material_binding = _bind_title_material_specification(
        drawing_model, properties["Material Specification"]
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Alignment Pinion Drum Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"alignment pinion; brass drum; {TEETH}T; zeroing drive",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(
        adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=FRONT_SCALE
    )
    right = place_view(
        adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=PROFILE_SCALE
    )
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE
    )
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    _verify_title_material_specification(drawing_model, material_binding)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="toothed end"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="full tooth face"
    )
    _use_single_arrow_od_leader(adapter, front_annotations)
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _match_bore_tolerance_places(adapter, front_annotations)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to drum bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    add_surface_finish(
        adapter,
        front,
        symbol_xy=(0.190, 0.135),
        control=surface_finish_by_key(SURFACE_FINISHES, "drum_bore"),
        label="drum bore finish",
        entity=bore_edge,
        leader_attach_xy=(
            FRONT_CENTER[0],
            FRONT_CENTER[1] - BORE_DIA * FRONT_SCALE[0] / FRONT_SCALE[1] / 2000.0,
        ),
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025)
    add_property_linked_note(
        adapter,
        "Isometric View Note",
        *ISOMETRIC_NOTE_POS,
        char_height=0.0025,
    )
    add_property_linked_note(
        adapter,
        "Manufacturing Notes",
        *MANUFACTURING_NOTES_POS,
        char_height=0.0025,
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Alignment Pinion Drum Manufacturing Drawing",
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
