r"""Manufacturing print for the composite platen rack, MHA-PD-05.

The long front/top group is aligned at 1:1. A 4:1 VIEW A, lettered with its
viewing arrow on the front view's right end, defines the stepped brass
section and soft-solder seam in solid lines. The standard shaded-with-edges
isometric supplements those views. All sizes and decimal places come from
the saved part and its pure-data spec; the solder and flush-end requirements
stand at leaders on the features they control (rule 7). The sheet prints
decimal inch (the part's ``drawing_unit: in``).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name

from _check import check
from _com import _early_bound
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
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
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from pd_platen_rack_spec import (
    BACKER_HEIGHT,
    BAR_HEIGHT,
    BAR_LENGTH,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_NOMINALS_MM,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_DIMENSIONS,
    RACK_Z0,
)
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

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
    # Left of the left end: the right end carries VIEW A's arrow.
    "OverallHeight": (0.038, FRONT_CENTER[1]),
}
END_KEEP = {
    "BackerDepth": (END_CENTER[0], 0.082),
    "RackDepth": (END_CENTER[0], 0.156),
    "RackHeight": (0.390, 0.135),
    "RackInset": (0.375, 0.095),
    "SeamHeight": (0.321, 0.112),
}
GEAR_DATA_XY = (0.020, 0.254)
# Under the isometric's label (y ~0.077, run 9 touched its first line), left
# of the title block (x 0.216) and above the border.
NOTES_XY = (0.020, 0.064)
# Rule 7: the one part fact the views cannot carry; the mesh is set by the
# MHA-PD-00 assembly steps, not on this part sheet.
NOTES_TEXT = "END TOOTH PHASE NOT CONTROLLED."
# Rule 9: the enlarged end view is VIEW A, its viewing arrow on the front
# view's right end face, approaching from the right (third-angle right view).
VIEW_LETTER = "A"
VIEW_LETTER_HEIGHT = 0.005
VIEW_ARROW_RUN = 0.012
END_CAPTION = f"VIEW {VIEW_LETTER}\nSCALE {END_SCALE[0]}:{END_SCALE[1]}"
# Centred under the 4:1 end view (axis x ~0.355), between the BackerDepth
# dimension line (y ~0.0795) and the title block top (y 0.066); left-anchored.
END_NOTE_XY = (0.343, 0.077)
ISO_NOTE_XY = (0.104, 0.077)
# Rule 7 (flag it where it applies): the soft-solder joint is called out at
# its seam's corner beside the rack on VIEW A, the flush ends at the front
# view's right end.  Each text stands up-left of its tip, clear of the views:
# the solder note right of the isometric and under VIEW A's top dimension,
# the flush note under the front view, left of its right end.
NOTE_HEIGHT = 0.0025
SOLDER_NOTE = "SOFT-SOLDER RACK TO BACKER\n(TIN-LEAD OR LEAD-FREE)"
SOLDER_NOTE_XY = (0.250, 0.150)
FLUSH_NOTE = "RACK AND BACKER ENDS FLUSH,\nBOTH ENDS"
FLUSH_NOTE_XY = (0.240, 0.174)


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
        # The callout-carrying stock REFs print their parentheses as the
        # value's own prefix/suffix (set_reference_dimension), so the plain
        # MAX above reads outside them; the others keep the native ones.
        if name in DIMENSION_CALLOUTS:
            text = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
            if bool(display.ShowParenthesis) or text != ("(", ")"):
                raise RuntimeError(f"rack size {name!r} lost its value-only parentheses: {text!r}")
        elif bool(display.ShowParenthesis) != reference:
            raise RuntimeError(f"rack size {name!r} has wrong reference state")
        if bool(annotation.IsDangling()):
            raise RuntimeError(f"rack size {name!r} is dangling")
    missing = DRAWING_NOMINALS_MM.keys() - found
    if missing:
        raise RuntimeError(f"rack sheet is missing sizes {sorted(missing)}")


def _parenthesize_values_only(adapter: Any, annotations: list[Any]) -> None:
    """The callout-carrying stock REFs: native parentheses off (they would
    wrap the callout too), the value's own instead."""
    done: set[str] = set()
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in DIMENSION_CALLOUTS:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShowParenthesis = False
        if bool(display.ShowParenthesis):
            raise RuntimeError(f"rack size {name!r} kept its native parentheses")
        set_reference_dimension(adapter, annotation, label=name)
        done.add(name)
    missing = set(DIMENSION_CALLOUTS) - done
    if missing:
        raise RuntimeError(f"rack stock REFs never reached the sheet: {sorted(missing)}")


def _add_sheet_notes(adapter: Any, front: Any, end: Any) -> None:
    """VIEW A's arrow and caption, the leadered requirements and the note."""
    mm = 1.0 / 1000.0
    tip = model_point_in_view(
        adapter, front, (BAR_LENGTH * mm, BAR_HEIGHT / 2.0 * mm, 0.0),
        label="VIEW A arrow tip",
    )
    add_leader_note(
        adapter, VIEW_LETTER,
        text_xy=(tip[0] + VIEW_ARROW_RUN, tip[1] + VIEW_LETTER_HEIGHT / 2.0),
        attach_xy=tip, view=front, height=VIEW_LETTER_HEIGHT,
        label=f"view {VIEW_LETTER} viewing arrow",
    )
    seam = model_point_in_view(
        adapter, end, (BAR_LENGTH * mm, BACKER_HEIGHT * mm, RACK_Z0 * mm),
        label="rack/backer seam corner",
    )
    add_leader_note(
        adapter, SOLDER_NOTE, text_xy=SOLDER_NOTE_XY, attach_xy=seam, view=end,
        height=NOTE_HEIGHT, label="soft-solder joint note",
    )
    end_face = model_point_in_view(
        adapter, front, (BAR_LENGTH * mm, BACKER_HEIGHT / 2.0 * mm, 0.0),
        label="right end face",
    )
    add_leader_note(
        adapter, FLUSH_NOTE, text_xy=FLUSH_NOTE_XY, attach_xy=end_face, view=front,
        height=NOTE_HEIGHT, label="flush ends note",
    )
    # The free notes belong to the sheet, not the last view a leader used.
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")
    if drawing.ActiveDrawingView is not None:
        raise RuntimeError("rack sheet notes: cannot leave view context for the sheet")
    for text, xy, label in (
        (END_CAPTION, END_NOTE_XY, "VIEW A caption"),
        (NOTES_TEXT, NOTES_XY, "sheet note"),
    ):
        if add_note(adapter, text, *xy, height=NOTE_HEIGHT) is None:
            raise RuntimeError(f"failed to insert the {label}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open platen rack source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
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
    # Above the value, outside its parentheses: the end view's outline sits
    # just under both REF lines.
    _parenthesize_values_only(adapter, annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="above")
    # Showing EndStockProfile prints the section's real stock outline and seam;
    # it remains hidden in the source part and in the isometric/assembly views.
    for property_name, position in (
        ("Gear Data", GEAR_DATA_XY),
        ("Isometric View Note", ISO_NOTE_XY),
    ):
        add_property_linked_note(adapter, property_name, *position, char_height=NOTE_HEIGHT)
    _add_sheet_notes(adapter, front, end)
    for view in (front, top, end):
        set_hidden_lines_removed(adapter, view)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Rack and Backer Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(lambda: _assert_native_dimensions(adapter, annotations),),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", nargs="?", default=PART_STEM, choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))
