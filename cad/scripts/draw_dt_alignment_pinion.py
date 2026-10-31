r"""Create the simplicity-policy drawing for the alignment-pinion drum.

The end view owns the tooth-tip envelope and matched arbor bore.  The aligned
profile owns the full tooth-face width, and the standard isometric supplies
pictorial clarity without replacing either manufacturing view.
The property-linked tooth-system block comes from the rebuilt part: configured
DP/PA, standard root/depth and the count-specific reference cutter, never the
retired shallow chord-floor description.
The owner-approved presentation uses 0.13 mm visible model edges in all three
views of this drawing, not only the isometric. This drawing-component override
does not alter the shared template, model appearance, geometry or other prints.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
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
import _drawing_hidden_sketches as hidden_sketches
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note, property_link
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_alignment_pinion_spec import (
    ARBOR_BORE_CALLOUT,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    OUTSIDE_DIA,
    OUTSIDE_DIA_CALLOUT,
    SURFACE_FINISHES,
    TEETH,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["dt_alignment_pinion"]
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
# The actual 1:1 trial struck the border and tooth note. At 1:2 the complete
# pictorial fits the upper-right field. Owner-approved fine model-edge ink
# across all three views keeps the full-length teeth and brass shading readable.
ISO_SCALE = (1, 2)
# The side view is the lathe view at the sheet scale; the end view projects
# to its left (third angle) at 2:1 so the teeth and bore read, and says so
# under itself (machinist review r1: an unlabelled 2:1 projected view).
FRONT_CENTER = (0.085, 0.150)
RIGHT_CENTER = (0.255, 0.150)
ISO_CENTER = (0.350, 0.230)
GEAR_DATA_POS = (0.018, 0.262)
ISOMETRIC_NOTE_POS = (0.330, 0.262)
END_VIEW_NOTE_POS = (0.066, 0.124)

_SIDE_SCALE = PROFILE_SCALE[0] / PROFILE_SCALE[1]
_SIDE_HALF_OD = OUTSIDE_DIA / 2000.0 * _SIDE_SCALE
_SIDE_LEFT_X = RIGHT_CENTER[0] - FACE_WIDTH / 2000.0 * _SIDE_SCALE
_SIDE_RIGHT_X = RIGHT_CENTER[0] + FACE_WIDTH / 2000.0 * _SIDE_SCALE
# The do-not-cut note is flagged to the teeth it governs (rule 7).  The leader
# tip lands on the tooth-tip outline past the note's right end, so the leader
# leaves from the end of the text and crosses none of it (machinist review r4
# of 7b8a6bebe: a tip under the note's left half struck the second line).
TOOTH_NOTE_POS = (0.190, 0.200)
TOOTH_NOTE_ATTACH = (_SIDE_RIGHT_X - 0.005, RIGHT_CENTER[1] + _SIDE_HALF_OD)

FRONT_KEEP = {
    "ArborBoreDia": (0.070, 0.192),
}
# Diameters on the side view beside the length (rule 11): the tip diameter's
# dimension line stands just right of the back face with its text below the
# part, clear of the face-width baseline under the view.  The callout reads
# left-to-right off its shelf from the dimension line, so the line stands close
# enough that the mate number ends well inside the border (machinist review
# r4: at +45 mm it printed cut off as "MHA-DT-0").
RIGHT_KEEP = {
    "FaceWidth": (RIGHT_CENTER[0], 0.122),
    "OutsideDia": (_SIDE_RIGHT_X + 0.015, 0.118),
}
DIMENSION_CALLOUTS = {
    "ArborBoreDia": ARBOR_BORE_CALLOUT,
    "FaceWidth": "OVERALL; TEETH FULL LENGTH",
    "OutsideDia": OUTSIDE_DIA_CALLOUT,
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


def _assert_tolerance_places(
    adapter: Any, annotations: list[Any], name: str, places: int
) -> None:
    """Read back that a band imported at the places the part authored.

    The part builder authors the places (``set_dimension_bilateral_tolerance``);
    the sheet only verifies, so the .SLDPRT stays the one source (Codex P1 on
    #1647).
    """
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} annotation, found {len(matches)}")
    annotation = _sw_type_info.early_bound_or_flag(
        matches[0], "IAnnotation", "GetSpecificAnnotation"
    )
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    applied = int(display.GetPrimaryTolPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{name} tolerance imported at {applied} places, not the part's {places}"
        )


def _prefix_diameter_symbol(adapter: Any, annotations: list[Any], name: str) -> None:
    """Print the Ø on a doubled centerline-to-witness (diametric linear) size.

    Imported into a side view it prints as a bare ".694", which reads as a
    linear height (machinist review r6 of 874c912e6, gating clarity).  The
    prefix compartment takes SolidWorks' own diameter token, read back.
    """
    matches = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} annotation, found {len(matches)}")
    annotation = _sw_type_info.early_bound_or_flag(
        matches[0], "IAnnotation", "GetSpecificAnnotation"
    )
    display = _sw_type_info.early_bound_or_flag(
        annotation.GetSpecificAnnotation(), "IDisplayDimension", "SetText", "GetText"
    )
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    if "<MOD-DIAM>" in existing:
        return
    prefix = "<MOD-DIAM>" + existing
    display.SetText(1, prefix)
    applied = str(display.GetText(1) or "")
    if applied != prefix:
        raise RuntimeError(f"{name}: diameter prefix did not persist ({applied!r})")


def _show_full_tooth_profile(adapter: Any, view: Any) -> None:
    """Keep the actual teeth in the manufacturing profile.

    Owner review of the v43-to-rolling drawing diff requested full tooth detail
    back. The blank-only simplified configuration must not stand in for it.
    """
    configuration = "Default"
    bound = _early_bound(view, "IView")
    bound.ReferencedConfiguration = configuration
    rebuild_drawing(adapter, label="side view configuration")
    observed = str(bound.ReferencedConfiguration)
    if observed != configuration:
        raise RuntimeError(
            f"side view references {observed!r} after setting {configuration!r}"
        )


def _set_drawing_model_edge_weight(adapter: Any, view: Any) -> float:
    """Use the owner-approved Thin model-edge ink across this part's views.

    Native trial 6d6b635 proved the part root's override affects all three views.
    The owner explicitly accepted that scope for this print after inspecting
    the complete thin-ink and thick-ink sheets side by side.
    """
    bound = _early_bound(view, "IView")
    raw_component = bound.RootDrawingComponent2(False)
    if raw_component is None:
        raise RuntimeError("alignment drawing has no part drawing component")
    component = _early_bound(raw_component, "IDrawingComponent")
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    thin_width = float(
        extension.GetUserPreferenceDouble(
            _sw_type_info.constant("swPageSetupPrinterThinLineWeight"),
            _sw_type_info.constant("swDetailingNoOptionSpecified"),
        )
    )
    if abs(thin_width - 0.00013) > 1e-9:
        raise RuntimeError(
            f"alignment template Thin slot is not the approved 0.13 mm: {thin_width}"
        )
    component.UseDocumentDefaults = False
    # Visible edges=1, swLW_THIN=0. The third argument is unused for a
    # standard weight; no custom-width or document-default setter is involved.
    component.SetLineThickness(1, 0, 0.0)
    _assert_drawing_model_edge_weight(adapter, view, thin_width)
    return thin_width


def _assert_drawing_model_edge_weight(
    adapter: Any, view: Any, expected_width: float
) -> None:
    # Reacquire after display regeneration/rebuild rather than retain a root
    # wrapper from the authoring stage.
    bound = _early_bound(view, "IView")
    raw_component = bound.RootDrawingComponent2(False)
    if raw_component is None:
        raise RuntimeError("alignment drawing lost its part drawing component")
    component = _early_bound(raw_component, "IDrawingComponent")
    weight, _custom_thickness = component.GetLineThickness(1)
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    thin_width = float(
        extension.GetUserPreferenceDouble(
            _sw_type_info.constant("swPageSetupPrinterThinLineWeight"),
            _sw_type_info.constant("swDetailingNoOptionSpecified"),
        )
    )
    if (
        bool(component.UseDocumentDefaults)
        or int(weight) != 0
        or abs(thin_width - expected_width) > 1e-9
    ):
        raise RuntimeError(
            "alignment drawing Thin model edges did not persist: "
            f"default={component.UseDocumentDefaults}, "
            f"weight={weight}, thin_width={thin_width}, expected={expected_width}"
        )


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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
            "Isometric View Note",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
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
    _show_full_tooth_profile(adapter, right)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    _verify_title_material_specification(drawing_model, material_binding)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="toothed end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The tip diameter's owner is the blanked OutsideDiaReference sketch,
    # shown in the side view only.
    right_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="full tooth face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_tolerance_places(
        adapter,
        front_annotations,
        "ArborBoreDia",
        DRAWING_PRECISION_BY_NAME["ArborBoreDia"],
    )
    # The inch tip band (+.000/-.004) prints at the nominal's three places.
    _assert_tolerance_places(
        adapter,
        right_annotations,
        "OutsideDia",
        DRAWING_PRECISION_BY_NAME["OutsideDia"],
    )
    _prefix_diameter_symbol(adapter, right_annotations, "OutsideDia")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to drum bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.045, FRONT_CENTER[1] - 0.030),
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
        "End View Note",
        *END_VIEW_NOTE_POS,
        char_height=0.0025,
    )
    add_leader_note(
        adapter,
        properties["Manufacturing Notes"],
        text_xy=TOOTH_NOTE_POS,
        attach_xy=TOOTH_NOTE_ATTACH,
        label="tooth do-not-cut note",
        view=right,
        height=0.0025,
    )
    model_edge_width = _set_drawing_model_edge_weight(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Alignment Pinion Drum Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_drawing_model_edge_weight(adapter, iso, model_edge_width),
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
