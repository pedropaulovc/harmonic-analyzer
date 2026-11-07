r"""Create the curated machinist drawing for the oblique-trammel hub stud.

The SLDPRT remains authoritative.  This recipe supplies only the stud's
views, the placement of its imported model dimensions, the nose-tap callout
and the fit-up reference; sheet/template and export behavior lives in
``_drawing_common``.  Places, bands and mate callouts are authored on the
part (``ch_rocker_arm_tl_oblique_hub_stud_spec``).

The sheet prints decimal inch (the part's ``drawing_unit: in``).  The side
view ("*Left", 3:1) lays the stud axis horizontal, flange left and nose
right (drawing-guidelines.md rule 11), and carries every diameter between
its flanks (flange, banded shank, banded nose), the flange thickness and the
shank length from the flange seat, the root's R MAX, and the fit-up pair
from the hidden ``FitReference`` sketch: the (.79) set-at-assembly reference
and the .82 MIN supply (rule 19).  The end view ("*Front", 3:1) is the
side view's true third-angle right-side projection: it stands right of the
side view and looks at the nose face, so the #10-24 blind tap it carries
(the native Hole Wizard callout) is drawn solid in the end it is cut in.  The
2:1 isometric sits right.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_hub_stud.py ch-rocker-arm-tl-oblique-hub-stud
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from ch_rocker_arm_tl_oblique_hub_stud_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FIT_LENGTH_PLACES,
    FLANGE_DIA,
    FLANGE_THICK,
    LENGTH,
    SHANK_DIA,
    SHANK_LENGTH,
    STEM,
    TAP_DEPTH_PLACES,
    TAP_DRILL_DIA,
    TAP_SPEC,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_stud"]
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
# Hole Wizard length variables of the blind nose tap's callout, by native
# name: the drill's Ø prints .XXX, both depths the spec's places (.XX).
TAP_PRECISION = {
    "hw-tapdrldia": 3,
    "hw-tapdrldepth": TAP_DEPTH_PLACES,
    "hw-threaddepth": TAP_DEPTH_PLACES,
}

# A Ø.71 x .91 stud: both orthographic views at 3:1 (54 mm across the
# flange, 69 mm along the axis), the isometric at 2:1.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
ISO_SCALE = (2, 1)
_K = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0

# Sheet layout (meters; title block x >= 0.2155, y <= 0.0655): the side view
# on the left two-thirds with its length rows under it and the diameters
# above, the end view right of it on the same row (third angle: the nose
# end's view on the nose's side), the isometric above-right.
SIDE_CENTER = (0.125, 0.160)
END_CENTER = (0.285, 0.160)
ISO_CENTER = (0.375, 0.200)


def _sx(model_z_mm: float) -> float:
    """Sheet x of a station along the stud axis in the "*Left" side view
    (looking from -X, model +Z points right; the view centres on the stud's
    bounding box, z 0..LENGTH)."""
    return SIDE_CENTER[0] + (model_z_mm - LENGTH / 2.0) * _K


def _sy(model_y_mm: float) -> float:
    """Sheet y of a model y in the side view (model +Y points up)."""
    return SIDE_CENTER[1] + model_y_mm * _K


_BELOW = _sy(-FLANGE_DIA / 2.0)
_ABOVE = _sy(FLANGE_DIA / 2.0)
# Side view: the length rows hang under the flange's bottom edge, each from
# the flange seat (rule 11: lengths from the faced end), the shortest
# nearest; the diameters stand above (shank, nose) or left of the flange.
# The nose callout stands right of the nose, clear of the shank callout's
# shelf (r2 review: the two had interleaved above the shank).
SIDE_KEEP = {
    "FlangeThick": (_sx(FLANGE_THICK / 2.0), _BELOW - 0.010),
    "ShankLength": (_sx(FLANGE_THICK + SHANK_LENGTH / 2.0), _BELOW - 0.020),
    "FitLength": (_sx((FLANGE_THICK + LENGTH) / 2.0), _BELOW - 0.032),
    "SupplyLength": (_sx((FLANGE_THICK + LENGTH) / 2.0), _BELOW - 0.046),
    "FlangeDia": (_sx(0.0) - 0.018, _sy(0.0)),
    "ShankDia": (_sx(FLANGE_THICK + SHANK_LENGTH / 2.0), _ABOVE + 0.018),
    "NoseDia": (_sx(LENGTH) + 0.036, _ABOVE + 0.008),
    "RootRadius": (_sx(FLANGE_THICK) + 0.004, _ABOVE + 0.036),
}
# The fit-up reference's two-row callout is wider than the .79 span between
# its extension lines (review r1-r3: both lines struck it), so its text leaves
# on a leader to the right of the nose's extension line, above the SUPPLY row
# and below the end view.
FIT_LENGTH_TEXT_XY = (_sx(LENGTH) + 0.048, _BELOW - 0.032)
TAP_CALLOUT_XY = (END_CENTER[0] + 0.020, END_CENTER[1] + 0.045)
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )


def _fit_length_reference(adapter: Any, annotations: list[Any]) -> None:
    """The (.79) fit-up length is a reference: the fitter faces the nose to
    the proud the callout states (rule 19), so it prints in parentheses."""
    found = [a for a in annotations if dimension_name(adapter, a) == "FitLength"]
    if len(found) != 1:
        raise RuntimeError(f"expected one FitLength on the side view, found {len(found)}")
    # set_reference_dimension hands back the early-bound IDisplayDimension it
    # parenthesized (None-guarded inside).
    display = set_reference_dimension(
        adapter, _early_bound(found[0], "IAnnotation"), label="hub stud fit length"
    )
    # IDisplayDimension::GetPrimaryPrecision2 is a METHOD returning VT_I4.
    if int(display.GetPrimaryPrecision2()) != FIT_LENGTH_PLACES:
        raise RuntimeError("hub stud fit length lost its places")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open hub stud source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Oblique Trammel Hub Stud Manufacturing Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "hub stud; turned steel; flange, slip shank, locating nose, tapped",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # "*Left" puts the nose (+Z) right, so "*Front" (the nose face) is its
    # right-side view in third angle; under "*Right" it stood on the flange's
    # side and read as a flange-end view (review r1-r3 blocker).
    side = place_view(adapter, str(SOURCE), "*Left", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    # Every dimension imports straight into the side view: the circles' Front-
    # parallel sketches stand edge-on there and their diameters land between
    # the flanks (the pn_pen_rod PivotDia precedent); the hidden FitReference
    # sketch is shown in this view only.
    annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    offset_dimension_text(adapter, annotations, {"FitLength": FIT_LENGTH_TEXT_XY})
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _fit_length_reference(adapter, annotations)

    # The template may centre-mark the tap as the view is placed; mark only a
    # bare view, then prove the tap carries exactly one (fleet issue #913).
    if _center_mark_count(end) == 0 and not auto_center_marks(
        adapter, end, holes=True, size=0.0025
    ):
        raise RuntimeError("failed to add ASME center mark to the nose tap")
    if (found := _center_mark_count(end)) != 1:
        raise RuntimeError(f"end view carries {found} centre marks, not the nose tap's one")

    # Pick the tap-drill rim, not the cosmetic thread or the hole centre
    # ("*Front": model +X points right).
    tap_callout = add_native_hole_callout(
        adapter,
        end,
        edge_xy=(END_CENTER[0] + TAP_DRILL_DIA / 2.0 * _K, END_CENTER[1]),
        callout_xy=TAP_CALLOUT_XY,
        label="hub screw blind tap",
        process="TAP",
    )
    # The title block's THREADS row owns the general thread class (rule 2).
    omit_title_block_thread_class(tap_callout, label="hub screw blind tap")
    set_hole_callout_precision(tap_callout, TAP_PRECISION, label="hub screw blind tap")

    # Materialize the iso's cosmetic thread before the strict final note
    # cleanup; otherwise its descriptive label first appears during the save.
    import_cosmetic_threads(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Oblique Trammel Hub Stud Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(f"{TAP_SPEC.size} Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
