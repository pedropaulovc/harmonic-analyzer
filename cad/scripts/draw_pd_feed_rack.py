r"""Manufacturing print for the MHA-PD-26 feed rack.

The long front/bottom group is aligned at 1:1: the bottom view looks at the
strip's flat top and its four #0-80 taps, located on tooth centres. A 4:1
VIEW A, lettered with its viewing arrow on the front view's right end,
defines the purchased square section. The standard shaded-with-edges
isometric supplements those views. All sizes and decimal places come from
the saved part and its pure-data spec; the taps carry one native Hole
Wizard callout. The sheet prints decimal inch (the part's
``drawing_unit: in``).
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name

import _telemetry
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
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from _named_views import octant_view_name
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _hole_callout_thread_class import omit_title_block_thread_class
from _holes import DIAMETER_TOLERANCE_MM, _verify_tap_metadata
from pd_feed_rack_spec import (
    BAR_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOMINALS_MM,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_DIMENSIONS,
    ENGAGEMENT_STATEMENT,
    RACK_HEIGHT,
    TAP_CALLOUT_PRECISION,
    TAP_DRILL_DEPTH,
    TAP_DRILL_DIA,
    TAP_FACE_WALL_STATEMENT,
    TAP_SPACING_PITCHES,
    TAP_SPEC,
    TAP_THREAD_DEPTH,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    place_view,
    remove_notes_matching,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_feed_rack"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.190, 0.205)
# Third-angle: the view of the flat top (local -Y) stands under the front.
BOTTOM_CENTER = (FRONT_CENTER[0], 0.180)
END_CENTER = (0.355, 0.120)
END_SCALE = (4, 1)
ISO_CENTER = (0.160, 0.108)
ISO_SCALE = (1, 2)
_LEFT_END_X = FRONT_CENTER[0] - BAR_LENGTH / 2000.0
FRONT_KEEP = {
    "Length": (FRONT_CENTER[0], 0.225),
}
# The tap stations run under the bottom view, the first two on one line
# (TapStart ends where TapStation2 begins), the longer two stepped below;
# the tap's place across the strip stands left of the first tap.
BOTTOM_KEEP = {
    "TapStart": (_LEFT_END_X + 0.026, 0.170),
    "TapStation2": (_LEFT_END_X + 0.080, 0.170),
    "TapStation3": (_LEFT_END_X + 0.107, 0.164),
    "TapStation4": (_LEFT_END_X + 0.134, 0.158),
    "TapFromFront": (_LEFT_END_X + 0.044, 0.192),
}
END_KEEP = {
    "RackDepth": (END_CENTER[0], 0.156),
    # Right of the rack's outline, inside the border.
    "RackHeight": (0.3925, 0.135),
}
GEAR_DATA_XY = (0.020, 0.254)
# Under the isometric's label, left of the title block (x 0.216) and above
# the border.
NOTES_XY = (0.020, 0.064)
# Rule 7: the part facts the views cannot carry; the mesh is set by the
# MHA-PD-00 assembly steps, not on this part sheet. Rule 20: the taps' walls
# to the strip's faces and to the tooth root (RV-03).
NOTES_TEXT = f"END TOOTH PHASE NOT CONTROLLED.\n{TAP_FACE_WALL_STATEMENT}"
# The tap callout (~69 x 26 mm, centred here) stands right of the bottom
# view's right end (x 324.8) and above VIEW A, its leader on the fourth tap.
# At (0.330, 0.192) its top came 1.9 mm under VIEW A's letter and the audit
# read them as one block (r6), so it sits wholly right of the bottom view and
# lower, its centre dropped a further half row for the tooth-count line (r7):
# its top ~6 mm under the letter, clear of the border.
TAP_CALLOUT_XY = (0.365, 0.185)
# Rule 7/20/26: where the four taps stand, as tooth counts the builder steps
# off (machinist review r7: the REF decimals alone left the pattern to a
# sentence), and their engagement (RV-02).
TAP_CALLOUT_BELOW = (
    f"ON TOOTH CENTRES,\n{TAP_SPACING_PITCHES} TEETH APART\n{ENGAGEMENT_STATEMENT}"
)
# The cut ends' tooth phase is not controlled, so the first tap takes the
# tooth centre nearest its REF station from the cut end, printed under it.
TAP_START_CALLOUT = "NEAREST\nTOOTH CENTRE"
TAPPED_HOLE_NOTE = "Tapped Hole"
# Rule 9: the enlarged end view is VIEW A, its viewing arrow on the front
# view's right end face, approaching from the right (third-angle right view).
VIEW_LETTER = "A"
VIEW_LETTER_HEIGHT = 0.005
VIEW_ARROW_RUN = 0.012
END_CAPTION = f"VIEW {VIEW_LETTER}\nSCALE {END_SCALE[0]}:{END_SCALE[1]}"
# Centred under the 4:1 end view (axis x ~0.355), above the title block top
# (y 0.066); left-anchored.
END_NOTE_XY = (0.343, 0.077)
ISO_NOTE_XY = (0.104, 0.077)
NOTE_HEIGHT = 0.0025
# swDisplayMode_e.swSHADED; the getter may read it or swSHADED_EDGES (7).
_SW_SHADED = 3
_SHADED_MODES = (3, 7)


def _require_saved_taps(model: Any) -> None:
    """Require the saved native taps' size, class, blind end, drill Ø and
    both depths."""
    feature = _early_bound(model, "IPartDoc").FeatureByName("RackTaps")
    if feature is None:
        raise RuntimeError("saved feed rack has no native RackTaps")
    feature = _early_bound(feature, "IFeature")
    if str(feature.GetTypeName2()) != "HoleWzd":
        raise RuntimeError("saved feed rack RackTaps is not a native Hole Wizard tap")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError("saved feed rack RackTaps has no hole definition")
    definition = _early_bound(definition, "IWizardHoleFeatureData2")
    if str(definition.FastenerSize).strip() != TAP_SPEC.size:
        raise RuntimeError("saved feed rack RackTaps has the wrong thread size")
    _verify_tap_metadata(definition, TAP_SPEC, "saved feed rack RackTaps")
    for member, expected, what in (
        ("TapDrillDiameter", TAP_DRILL_DIA, "tap drill"),
        ("TapDrillDepth", TAP_DRILL_DEPTH, "tap drill depth"),
        ("ThreadDepth", TAP_THREAD_DEPTH, "thread depth"),
    ):
        value = float(getattr(definition, member)) * 1000.0
        if not math.isfinite(value) or abs(value - expected) > DIAMETER_TOLERANCE_MM:
            raise RuntimeError(f"saved feed rack {what} {value:.3f} != {expected:.3f} mm")


@_telemetry.traced("drawing.hole_callout_below")
def _set_tap_callout_below(display: Any, text: str) -> None:
    """Write ``text`` under the native tap callout and read it back
    (draw_sm_gooseneck_end_plug._set_tap_callout_below)."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    below = definitions[8].replace("\r", "").rstrip()
    updated = f"{below}\n{text}" if below else text
    display.SetText(4, updated)
    if str(display.GetText(8) or "").replace("\r", "") != updated or any(
        str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(
            "feed rack tap callout rows or native definitions did not persist: "
            f"{[str(display.GetText(part) or '') for part in (5, 6, 7, 8)]!r}"
        )


def _assert_native_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Retain native controls and purchased-stock and tap-station reference sizes."""
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
        # sizes and the rack's tap stations keep part-authored parentheses.
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
        if bool(display.ShowParenthesis) != reference:
            raise RuntimeError(f"rack size {name!r} has wrong reference state")
        if bool(annotation.IsDangling()):
            raise RuntimeError(f"rack size {name!r} is dangling")
    missing = DRAWING_NOMINALS_MM.keys() - found
    if missing:
        raise RuntimeError(f"rack sheet is missing sizes {sorted(missing)}")


def _add_sheet_notes(adapter: Any, front: Any) -> None:
    """VIEW A's arrow and caption and the sheet note."""
    mm = 1.0 / 1000.0
    tip = model_point_in_view(
        adapter, front, (BAR_LENGTH * mm, RACK_HEIGHT / 2.0 * mm, 0.0),
        label="VIEW A arrow tip",
    )
    add_leader_note(
        adapter, VIEW_LETTER,
        text_xy=(tip[0] + VIEW_ARROW_RUN, tip[1] + VIEW_LETTER_HEIGHT / 2.0),
        attach_xy=tip, view=front, height=VIEW_LETTER_HEIGHT,
        label=f"view {VIEW_LETTER} viewing arrow",
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


def _set_shaded_with_edges(view: Any) -> None:
    """Put ``view`` in precise Shaded With Edges and read the mode back."""
    bound = _early_bound(view, "IView")
    bound.SetDisplayMode4(False, _SW_SHADED, False, True, True)
    mode = int(bound.GetDisplayMode2())
    if mode not in _SHADED_MODES or not bool(bound.GetDisplayEdgesInShadedMode()):
        raise RuntimeError(f"feed rack isometric did not go Shaded With Edges ({mode})")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open feed rack source", await adapter.open_model(str(SOURCE)))
    _require_saved_taps(adapter.currentModel)
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
            0: "Feed Rack Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "feed rack; purchased brass rack strip; four #0-80 taps",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=END_SCALE)
    # The built-in isometric looks from +Y, the teeth, and hides the four taps
    # that open on the flat top (-Y); the FRONT-BOTTOM-RIGHT octant the part
    # names shows the tapped flat (draw_dt_pinion_cam).
    iso = place_view(
        adapter, str(SOURCE), octant_view_name(1, -1, 1), *ISO_CENTER, scale=ISO_SCALE
    )
    # The taps are fully defined by their native callout (rule 9). The
    # isometric joins the loop so finalize can lift its cosmetic threads to
    # precise Shaded With Edges (PR #1436).
    for view in (front, bottom, end, iso):
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
            bottom,
            keep=BOTTOM_KEEP,
            view_label="rack bottom",
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
    # The four taps, natively called out on the bottom view: the title
    # block's THREADS row owns the 2B class (rule 2), the drill and both
    # depths print .XXX, and their place and engagement print below.
    tap_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge=visible_circle_edge(adapter, bottom, TAP_DRILL_DIA),
        callout_xy=TAP_CALLOUT_XY,
        label=f"feed rack {TAP_SPEC.size} taps",
    )
    omit_title_block_thread_class(tap_callout, label="feed rack taps")
    set_hole_callout_precision(tap_callout, TAP_CALLOUT_PRECISION, label="feed rack taps")
    _set_tap_callout_below(tap_callout, TAP_CALLOUT_BELOW)
    set_dimension_callouts(adapter, annotations, {"TapStart": TAP_START_CALLOUT})
    rebuild_drawing(adapter, label="feed rack tap callout")
    for property_name, position in (
        ("Gear Data", GEAR_DATA_XY),
        ("Isometric View Note", ISO_NOTE_XY),
    ):
        add_property_linked_note(adapter, property_name, *position, char_height=NOTE_HEIGHT)
    _add_sheet_notes(adapter, front)
    # Every view, the isometric included, through HLR once more: an annotation
    # attached after placement can leave a view's edge set unregenerated.
    for view in (front, bottom, end, iso):
        set_hidden_lines_removed(adapter, view)
    # On this part every SetDisplayMode4 leaves the views' cosmetic threads at
    # draft quality and only the cosmetic-thread import's rebuild lifts them to
    # precise (farm probe 959ae11: True after the import, False again after
    # the HLR loop and after a shaded transition, on the octant and the
    # standard isometric alike; r2-r5 failed finalize on it). So the isometric
    # goes Shaded With Edges first and the import follows; finalize's own
    # SetDisplayMode4 then finds the mode already set and leaves the threads.
    _set_shaded_with_edges(iso)
    import_cosmetic_threads(adapter, iso)
    # SolidWorks pins its own "Tapped Hole" note beside a tap's native callout
    # (and the import may pin one); the callout already states the thread.
    removed = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed} automatic tapped-hole label(s)")
    if not bool(_early_bound(iso, "IView").GetCThreadQuality()):
        raise RuntimeError("feed rack isometric: cosmetic threads still draft quality")
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Feed Rack Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(lambda: _assert_native_dimensions(adapter, annotations),),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", nargs="?", default=PART_STEM, choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))
