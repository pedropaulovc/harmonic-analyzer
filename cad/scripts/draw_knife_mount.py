r"""Create the curated machinist drawing for the knife-mount bearing block.

A machined, heat-treated steel block (24 wide x ~28.8 tall x 18 deep) with a
single Ø12 bore.  The bore is the knife-edge bearing: the summing-lever
trunnion's top vertex rides its upper inner wall in line contact (ch18 p.42:
unpainted hardened steel, close bore -- 2026-09-02 user re-read).  Every face
and the bore are real edges, so the block dimensions ride the auto-imported
profile marks while center section A-A shows the true tap-drill cone and
knife-bore crown.

Run with SolidWorks open::

    uv run python cad\scripts\draw_knife_mount.py knife-mount
"""

from __future__ import annotations

import argparse
from collections import Counter
import sys
from typing import Any, NamedTuple


from win32com.client.dynamic import Dispatch as dynamic_dispatch

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    add_native_hole_callout,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    rebuild_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hole_callout_precision,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from knife_mount_spec import (
    BLK_HALF_X,
    BORE_DIAMETER_TOLERANCE_MM,
    HOLE_CALLOUT_PRECISION,
    BLK_BOT,
    BLK_TOP,
    BORE_CY,
    SEAT_TOP,
    DRAWING_DIMENSIONS,
    DRAWING_NOMINALS_MM,
    DRAWING_PRECISION_BY_NAME,
    R_BORE,
    REFERENCE_DIMENSION_NOMINALS_MM,
    DRAWING_REFERENCE_PRECISION,
    STUD_TAP_DIA,
    STUD_TAP_SPEC,
    STUD_TAP_DRILL_DEPTH_TOLERANCE_TYPE,
    STUD_TAP_THREAD_DEPTH_TOLERANCE_TYPE,
    SUPPORT_Z_THICK,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["knife_mount"]
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

SHEET_SCALE = (2.0, 1.0)
# Model height the front/section views centre on: their outline runs from the
# block bottom to the seat-boss top.
_BLOCK_CY = (SEAT_TOP + BLK_BOT) / 2.0

# The seat boss makes the front/section outline 5 mm (10 mm on the sheet)
# taller; 0.115 put the SECTION A-A caption onto the title block's top rule
# (knife-cc-12), so the three views rise together, keeping their gaps.
FRONT_CENTER = (0.145, 0.122)
SECTION_CENTER = (0.255, 0.122)
TOP_CENTER = (0.145, 0.212)
ISO_CENTER = (0.345, 0.195)


_COSMETIC_THREAD_LAYER = "COSMETIC-THREADS-HIDDEN"
# SolidWorks' Hole Wizard thread description drops the number-size '#':
# draw_harmonic_base reads "10-32 UNF" back for its #10-32 tap.
_TAP_THREAD_DESCRIPTION = f"{STUD_TAP_SPEC.size.lstrip('#')} UNC"


def _cosmetic_thread_annotations(adapter: Any) -> list[tuple[str, Any]]:
    """Every swCThread in the drawing, named by sheet/view, skipping no view.

    SolidWorks attaches a feature's auto cosmetic 'Tapped Hole' annotation to
    whichever view imports that feature FIRST, and how many arrive is a lottery
    (7/8/5 across identical builds of one geometry -- draw_top_frame's measured
    case), so this walk inventories what THIS build produced and names it. It
    is evidence, never a gate on a count, and it never touches a native hole
    callout or note (``GetType()`` is ``swCThread`` only).
    """
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    found: list[tuple[str, Any]] = []
    for sheet_name in drawing.GetSheetNames() or ():
        sheet = _early_bound(drawing.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            label = f"{sheet_name}/{view_name(adapter, view)}"
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                if int(annotation.GetType()) != 1:  # swCThread, not swNote/hole callout
                    continue
                if int(annotation.OwnerType) != 0:  # swAnnotationOwner_DrawingView
                    raise RuntimeError(
                        f"{label}: cosmetic thread is not owned by its drawing view"
                    )
                if annotation.GetSpecificAnnotation() is None:
                    raise RuntimeError(
                        f"{label}: cosmetic thread has no native ICThread object"
                    )
                found.append((label, annotation))
    return found


def _hide_cosmetic_thread_annotations(adapter: Any) -> None:
    """Hide every cosmetic thread; the HIDE is the gate, never a census size.

    A build whose import produced no cosmetic thread is legal and passes. What
    must hold after the rebuild is that zero swCThread annotations remain on a
    printing layer, anywhere on any sheet -- so the proof re-walks every sheet
    and view and names whatever still refuses the hidden layer.
    """
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        status = manager.AddLayer(
            _COSMETIC_THREAD_LAYER,
            "redundant cosmetic thread annotations hidden",
            0,
            0,
            0,
        )
        if int(status) != 1:
            raise RuntimeError("failed to add hidden cosmetic-thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Printable):
        layer.Printable = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cosmetic-thread layer is not hidden and non-printing")

    for label, annotation in _cosmetic_thread_annotations(adapter):
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError(
                f"{label}: cosmetic-thread annotation refused hidden layer"
            )

    rebuild_drawing(adapter, label="hide redundant cosmetic threads")
    persisted_layer = _early_bound(
        manager.GetLayer(_COSMETIC_THREAD_LAYER), "ILayer"
    )
    if bool(persisted_layer.Visible) or bool(persisted_layer.Printable):
        raise RuntimeError("cosmetic-thread layer flags changed after rebuild")

    unhidden = [
        (label, annotation)
        for label, annotation in _cosmetic_thread_annotations(adapter)
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER
    ]
    if unhidden:
        for _label, annotation in unhidden:
            annotation.Layer = _COSMETIC_THREAD_LAYER
        refused = [
            (label, str(annotation.Layer or ""))
            for label, annotation in _cosmetic_thread_annotations(adapter)
            if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER
        ]
        if refused:
            raise RuntimeError(
                "cosmetic-thread annotations refused the hidden layer after a "
                "second hide: "
                + "; ".join(f"{label} on layer {name!r}" for label, name in refused)
            )


def _auto_tapped_hole_notes(adapter: Any) -> dict[str, int]:
    """Delete SolidWorks' own Hole Wizard notes, named per view, on every sheet.

    Importing model items brings SolidWorks' descriptive thread note ("#10-24
    Tapped Hole") along with the geometry, and this recipe replaces every one of
    them with an associative feature callout that also carries the process. A
    bare count cannot say WHICH view changed, and the count is not one per
    sheet: a note arrives once per view that imported a tapped feature, so a
    view added, re-scaled or switched to hidden-lines-removed moves it (the
    top-frame package printed 7, then 8, then 5 across three builds of the same
    geometry). This names them, and deletes them here rather than handing the
    substring to ``finalize_drawing``'s sweep: that sweep re-walked every
    annotation of every view, sheet by sheet (13 s of a 270 s build), to find
    the notes this walk -- ``ISheet::GetViews`` off the sheet objects, no sheet
    activation -- already holds. Each deletion is proved by the view's note list
    read back. The inventory is evidence, never a gate.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    counts: dict[str, int] = {}
    for sheet_name in drawing.GetSheetNames() or ():
        sheet = _early_bound(drawing.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            hits = [
                note for note in (
                    _early_bound(raw_note, "INote") for raw_note in (view.GetNotes() or ())
                )
                if "tapped hole" in str(note.GetText() or "").lower()
            ]
            if not hits:
                continue
            label = f"{sheet_name}/{view_name(adapter, view)}"
            for note in hits:
                draw.ClearSelection2(True)
                if not _early_bound(note.GetAnnotation(), "IAnnotation").Select2(False, 0):
                    raise RuntimeError(f"{label}: failed to select an automatic tapped-hole note")
                draw.EditDelete()  # VT_VOID: the re-read below is the proof
            draw.ClearSelection2(True)
            survivors = sum(
                1 for raw_note in (view.GetNotes() or ())
                if "tapped hole" in str(_early_bound(raw_note, "INote").GetText() or "").lower()
            )
            if survivors:
                raise RuntimeError(
                    f"{label}: {survivors} automatic tapped-hole note(s) survived deletion"
                )
            counts[label] = len(hits)
    return counts


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _BLOCK_CY) * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    "BlockWidth": (FRONT_CENTER[0], _front_y(BLK_BOT) - 0.016),
    # 28.8 sits 8 mm further out and the Ø12.00 callout 3 mm further in:
    # at -0.060/-0.048 the callout's shoulder crossed the height dimension line
    # and its Ø glyph straddled it (knife-cc-6 render).
    "BlockHeight": (FRONT_CENTER[0] - 0.068, FRONT_CENTER[1]),
    "BoreDia": (FRONT_CENTER[0] - 0.045, _front_y(BORE_CY) + 0.026),
    "BoreFromTop": (FRONT_CENTER[0] + 0.043, FRONT_CENTER[1]),
    # 12.0 at its own dimension-line midpoint (the bore centreline is only
    # 24 mm from the left edge), so it stops reading as '12.0 ->A' against
    # the section line's upper arrow; 0.021 above the seat-boss top keeps its
    # outside arrowhead clear of that arrow's stem.
    "BoreFromSide": (FRONT_CENTER[0] - 0.012, _front_y(SEAT_TOP) + 0.021),
}
SECTION_KEEP = {
    # The turned seat boss's revolve profile lies in this section's plane, so
    # its own Ø, height and end-face location import here (policy rules 2 and
    # 7). Above the boss: the Ø between its flanks, then the block depth.
    "Depth": (SECTION_CENTER[0], _front_y(SEAT_TOP) + 0.020),
    "BossDia": (SECTION_CENTER[0], _front_y(SEAT_TOP) + 0.009),
    # The boss height beside the section's right outline, where the cut shows
    # the boss and the tap drilled through it.
    "BossHeight": (
        SECTION_CENTER[0] + 0.030,
        (_front_y(BLK_TOP) + _front_y(SEAT_TOP)) / 2.0,
    ),
    # The boss axis from the block's near end face, below the section: the
    # profile's centerline runs to the block bottom, so both witness lines
    # leave the part downward, clear of the boss and its Ø above. Text at the
    # midpoint of that span (axis -> near end face).
    "BossFromEnd": (
        SECTION_CENTER[0] - SUPPORT_Z_THICK * SHEET_SCALE[0] / 4000.0,
        _front_y(BLK_BOT) - 0.012,
    ),
}
# The top view keeps only the tap callout and the (12.0) reference: the boss
# and tap location is on the section with the rest of the turned boss.
TOP_KEEP: dict[str, tuple[float, float]] = {}
# Drawing policy rule 6/7: a process word is allowed where it IS the
# requirement. The Ø12 knife-bearing bore carries Ra 1.6, which a drill does
# not leave and a reamer does -- REAM is the requirement (Main, 2026-09-22,
# reversing the knife-cc-10 DRILL/REAM rejection). The explicit ±0.2 stays:
# it is the band the crown and rock-clearance stacks assume, and without it
# the title block's DRILLED HOLES +0.10/0 row would be read instead.
DIMENSION_CALLOUTS = {
    "BoreDia": "REAM THRU",
}


def _uppercase_dimension_text(adapter: Any, drawing_model: Any) -> None:
    """Print the tap's MIN thread depth the ASME Y14.5 way, not 'min.'.

    SolidWorks renders a swTolMIN dimension with a lowercase 'min.' suffix
    (knife-cc-12/13). The supported switch is the drafting-standard document
    property 'All uppercase for dimensions and hole callouts'
    (DP_DraftingStandard), set here on this drawing's document and read back
    -- never a hand-typed override that would break the callout's model link.
    The id is read off this install's swconst.tlb (R2026x gen_py:
    swDraftingStandardAllUppercaseForDimensionsAndHoleCallouts=754), as
    draw_harmonic_base does for its section-label toggles: the drawing
    subprocess has no swconst constants loaded, so resolving the name failed
    on the farm (knife-cc-14).
    """
    name = "swDraftingStandardAllUppercaseForDimensionsAndHoleCallouts"
    preference = 754
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceToggle(preference, 0, True):
        raise RuntimeError(f"failed to set {name}")
    if not bool(extension.GetUserPreferenceToggle(preference, 0)):
        raise RuntimeError(f"{name} did not persist")


def _assert_callout_text_uppercase(display: Any, label: str) -> None:
    """The rendered tap callout prints the ASME 'MIN', never 'min.'.

    Reads the callout's rendered text (IDisplayData) plus its text
    compartments on a fresh handle, logs them as evidence, and requires an
    uppercase MIN with no lowercase 'min' anywhere.
    """
    annotation = _early_bound(
        _early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation"
    )
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    texts = {
        f"compartment_{index}": str(display.GetText(index) or "")
        for index in range(6)
    }
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    for index in range(int(data.GetTextCount())):
        texts[f"rendered_{index}"] = str(data.GetTextAtIndex(index) or "")
    _telemetry.info(f"{label} callout text: {texts!r}")
    combined = " ".join(texts.values())
    if "min" in combined or "MIN" not in combined:
        raise RuntimeError(f"{label} does not print an uppercase MIN: {texts!r}")


# The turned boss's controlling dimensions, all imported onto Section A-A.
_BOSS_CONTROLLING_DIMENSIONS = ("BossFromEnd", "BossDia", "BossHeight")


def _assert_boss_dimensions_print_plain(adapter: Any, annotations: list[Any]) -> None:
    """The imported boss dimensions are controlling, not reference reads.

    Equation-owned model dimensions read swDimensionDriven (BlockWidth/Depth
    alike, knife-cc-5), so DrivenState cannot tell a reference from a control.
    What the machinist reads can: no reference flag, no parentheses flag, no
    "(" / ")" text around the value; and BossDia, a doubled centerline
    dimension, must still read diametric.
    """
    for name in _BOSS_CONTROLLING_DIMENSIONS:
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"section carries {len(matches)} {name} dimensions")
        display = _early_bound(matches[0].GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        prefix = str(display.GetText(1) or "")  # swDimensionTextPrefix
        suffix = str(display.GetText(2) or "")  # swDimensionTextSuffix
        state = {
            "is_reference": bool(dimension.IsReference()),
            "show_parenthesis": bool(display.ShowParenthesis),
            "prefix": prefix,
            "suffix": suffix,
            "diametric": bool(_read_member(display, "Diametric")),
        }
        _telemetry.info(f"section {name}: {state!r}")
        if (
            state["is_reference"]
            or state["show_parenthesis"]
            or "(" in prefix
            or ")" in suffix
        ):
            raise RuntimeError(f"{name} prints as a reference dimension: {state!r}")
        if name == "BossDia" and not state["diametric"]:
            raise RuntimeError(f"BossDia lost its diametric display: {state!r}")


def _assert_imported_nominals(adapter: Any, annotations: list[Any]) -> None:
    """Prove every imported model dimension still measures the spec nominal."""
    remaining = dict(DRAWING_NOMINALS_MM)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        expected_mm = remaining.pop(name, None)
        if expected_mm is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        actual_mm = abs(float(dimension.SystemValue)) * 1000.0
        if abs(actual_mm - expected_mm) > 1e-5:
            raise RuntimeError(
                f"imported {name} measured {actual_mm:g}, expected {expected_mm:g} mm"
            )
    if remaining:
        raise RuntimeError(f"model dimensions never reached sheet: {sorted(remaining)}")


def _finish_tap_reference_dimension(
    adapter: Any, display: Any, dimension_name: str, *, label: str
) -> Any:
    """Center-anchor, parenthesize, and read back one actual-geometry locator."""
    expected_mm = REFERENCE_DIMENSION_NOMINALS_MM[dimension_name]
    precision = DRAWING_REFERENCE_PRECISION[dimension_name]
    display = set_arc_endpoints_to_center(adapter, display, label=label)
    display = _early_bound(display, "IDisplayDimension")
    display.SetPrecision3(
        DRAWING_REFERENCE_PRECISION[dimension_name], -1, -1, -1
    )
    if int(display.GetPrimaryPrecision2()) != precision:
        raise RuntimeError(f"{label} did not retain {precision}-place precision")
    display = set_reference_dimension(
        adapter, display.GetAnnotation(), label=label
    )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    actual_mm = abs(float(dimension.SystemValue)) * 1000.0
    if abs(actual_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label} measured {actual_mm:g} mm, expected {expected_mm:g} mm"
        )
    return display

@_telemetry.traced("drawing.knife_mount_boss_diameter")
def _assert_imported_tolerances(adapter: Any, annotations: list[Any]) -> None:
    # BoreDia keeps its native symmetric band (swTolSYMMETRIC 4); BoreFromTop
    # rides the title block's .XX (swTolNONE 0), so it must import bare.
    expected = {
        "BoreDia": (4, BORE_DIAMETER_TOLERANCE_MM),
        "BoreFromTop": (0, 0.0),
    }
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        contract = expected.pop(name, None)
        if contract is None:
            continue
        tolerance_type, limit_mm = contract
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != tolerance_type:
            raise RuntimeError(
                f"imported {name} tolerance type {int(tolerance.Type)}, "
                f"expected {tolerance_type}"
            )
        if tolerance_type == 0:
            continue
        limit_m = limit_mm / 1000.0
        if (
            abs(float(tolerance.GetMinValue()) + limit_m) > 1e-9
            or abs(float(tolerance.GetMaxValue()) - limit_m) > 1e-9
        ):
            raise RuntimeError(
                f"imported {name} lost its native symmetric tolerance"
            )
    if expected:
        raise RuntimeError(
            f"tolerance contracts never reached sheet: {sorted(expected)}"
        )


# swTolType_e of the two native depth variables: the drill depth rides the
# title-block .XX band (swTolNONE), the usable thread prints MIN (swTolMIN).
_TAP_DEPTH_TOLERANCE_TYPES = {
    "hw-tapdrldepth": STUD_TAP_DRILL_DEPTH_TOLERANCE_TYPE,
    "hw-threaddepth": STUD_TAP_THREAD_DEPTH_TOLERANCE_TYPE,
}


class _TapDepthContract(NamedTuple):
    precision: int
    tolerance_precision: int
    tolerance_type: int
    tolerance_lower_m: float
    tolerance_upper_m: float


def _read_source_tap_depth_contracts(
    adapter: Any,
) -> dict[str, _TapDepthContract]:
    """Read model-owned depth precision and tolerance before opening the drawing."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    feature = model.FeatureByName("StudTap")
    if feature is None:
        raise RuntimeError("source part has no StudTap Hole Wizard feature")
    feature = _early_bound(feature, "IFeature")
    targets = {
        "tapdrilldepth": "hw-tapdrldepth",
        "fullthreaddepth": "hw-threaddepth",
    }
    found: dict[str, list[_TapDepthContract]] = {
        variable: [] for variable in targets.values()
    }
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = display.GetDimension()
        if dimension is not None:
            dimension = _early_bound(dimension, "IDimension")
            normalized = "".join(
                character
                for character in str(dimension.FullName).lower()
                if character.isalnum()
            )
            for token, variable in targets.items():
                if token in normalized:
                    tolerance = _early_bound(
                        dimension.Tolerance, "IDimensionTolerance"
                    )
                    found[variable].append(
                        _TapDepthContract(
                            precision=int(display.GetPrimaryPrecision2()),
                            tolerance_precision=int(
                                display.GetPrimaryTolPrecision2()
                            ),
                            tolerance_type=int(tolerance.Type),
                            tolerance_lower_m=float(tolerance.GetMinValue()),
                            tolerance_upper_m=float(tolerance.GetMaxValue()),
                        )
                    )
        display = feature.GetNextDisplayDimension(display)
    result: dict[str, _TapDepthContract] = {}
    for variable, values in found.items():
        if len(values) != 1:
            raise RuntimeError(
                f"source StudTap has {len(values)} native {variable} dimensions"
            )
        contract = values[0]
        places = HOLE_CALLOUT_PRECISION[variable]
        if (
            (contract.precision, contract.tolerance_precision) != (places, places)
            or contract.tolerance_type != _TAP_DEPTH_TOLERANCE_TYPES[variable]
        ):
            raise RuntimeError(
                f"source StudTap {variable} contract is not the approved native "
                f"precision/tolerance: {contract!r}"
            )
        result[variable] = contract
    return result


def _propagate_source_tap_depth_contracts(
    adapter: Any,
    display: Any,
    source_contracts: dict[str, _TapDepthContract],
) -> None:
    """Apply the spec's callout places and the model-read depth tolerances.

    The part build writes HOLE_CALLOUT_PRECISION onto the native depth
    dimensions; the readback below fails if the model and the callout disagree.
    """
    set_hole_callout_precision(
        display,
        HOLE_CALLOUT_PRECISION,
        label="knife-mount tap source precision",
    )
    remaining = dict(source_contracts)
    for raw in display.GetHoleCalloutVariables() or ():
        late = dynamic_dispatch(raw._oleobj_)
        name = str(late.VariableName)
        expected = remaining.pop(name, None)
        if expected is None:
            continue
        length = _early_bound(raw, "ICalloutLengthVariable")
        length.TolerancePrecision = expected.tolerance_precision
        late.ToleranceType = expected.tolerance_type
        late.ToleranceMin = expected.tolerance_lower_m
        late.ToleranceMax = expected.tolerance_upper_m
        actual = _TapDepthContract(
            precision=int(length.Precision),
            tolerance_precision=int(length.TolerancePrecision),
            tolerance_type=int(late.ToleranceType),
            tolerance_lower_m=float(late.ToleranceMin),
            tolerance_upper_m=float(late.ToleranceMax),
        )
        if (
            actual.precision != expected.precision
            or actual.tolerance_precision != expected.tolerance_precision
            or actual.tolerance_type != expected.tolerance_type
            or abs(actual.tolerance_lower_m - expected.tolerance_lower_m) > 1e-9
            or abs(actual.tolerance_upper_m - expected.tolerance_upper_m) > 1e-9
        ):
            raise RuntimeError(
                f"knife-mount tap {name}: source contract did not persist; "
                f"expected={expected!r}, actual={actual!r}"
            )
    if remaining:
        raise RuntimeError(
            "knife-mount tap lacks native depth contract variables: "
            f"{sorted(remaining)}"
        )
    rebuild_drawing(adapter, label="knife-mount tap source contract")


@_telemetry.traced("drawing.knife_mount_tap_readback")
def _check_tap_callout(
    display: Any, source_contracts: dict[str, _TapDepthContract]
) -> None:
    """Prove the native callout carries both drill and usable-thread depths."""
    expected_lengths = {
        "hw-tapdrldia": STUD_TAP_DIA,
        "hw-tapdrldepth": STUD_TAP_SPEC.depth_mm,
        "hw-threaddepth": STUD_TAP_SPEC.overrides_mm["ThreadDepth"],
    }
    expected_strings = {
        "hw-threaddesc": _TAP_THREAD_DESCRIPTION,
        "hw-threadclass": STUD_TAP_SPEC.thread_class,
    }
    variables = tuple(display.GetHoleCalloutVariables() or ())
    found: set[str] = set()
    for raw in variables:
        late = dynamic_dispatch(raw._oleobj_)
        name = str(late.VariableName)
        if name in expected_strings:
            if int(late.Type) != 3:
                raise RuntimeError(f"knife-mount tap {name} is not a string")
            actual = str(_early_bound(raw, "ICalloutStringVariable").String or "")
            if actual.strip(" -") != expected_strings[name]:
                raise RuntimeError(
                    f"knife-mount tap {name}: {actual!r} != {expected_strings[name]!r}"
                )
            found.add(name)
            continue
        if name not in expected_lengths:
            raise RuntimeError(f"unexpected knife-mount tap variable {name!r}")
        if int(late.Type) != 1:
            raise RuntimeError(f"knife-mount tap {name} is not a length")
        length = _early_bound(raw, "ICalloutLengthVariable")
        actual_mm = float(length.Length) * 1000.0
        if abs(actual_mm - expected_lengths[name]) > 1e-5:
            raise RuntimeError(
                f"knife-mount tap {name}: {actual_mm} != "
                f"{expected_lengths[name]} mm"
            )
        if name in _TAP_DEPTH_TOLERANCE_TYPES:
            if (
                int(late.ToleranceType) != _TAP_DEPTH_TOLERANCE_TYPES[name]
                or (
                    int(length.Precision),
                    int(length.TolerancePrecision),
                )
                != (
                    source_contracts[name].precision,
                    source_contracts[name].tolerance_precision,
                )
            ):
                raise RuntimeError(
                    f"knife-mount tap {name}: native tolerance readback "
                    f"type={int(late.ToleranceType)}, "
                    f"nominal_precision={int(length.Precision)}, "
                    f"tolerance_precision={int(length.TolerancePrecision)}"
                )
        found.add(name)
    required = set(expected_lengths) | set(expected_strings)
    if found != required:
        raise RuntimeError(
            f"knife-mount tap callout is missing native variables: {required - found}"
        )


def _hole_callout_variable_snapshot(
    display: Any, label: str
) -> Counter[tuple[Any, ...]]:
    """Read a multiset of every native variable in a hole-callout definition."""
    display = _early_bound(display, "IDisplayDimension")
    variables: Counter[tuple[Any, ...]] = Counter()
    for raw in display.GetHoleCalloutVariables() or ():
        variable = dynamic_dispatch(raw._oleobj_)
        name = str(variable.VariableName)
        kind = int(variable.Type)
        if kind == 1:
            value = _early_bound(raw, "ICalloutLengthVariable")
            record = (
                name,
                kind,
                float(value.Length),
                int(value.Precision),
                int(value.TolerancePrecision),
            )
        elif kind == 2:
            value = _early_bound(raw, "ICalloutAngleVariable")
            record = (name, kind, float(value.Angle), int(value.Precision))
        elif kind == 3:
            value = _early_bound(raw, "ICalloutStringVariable")
            record = (name, kind, str(value.String or ""))
        else:
            raise RuntimeError(
                f"{label}: unsupported native variable type {kind} for {name!r}"
            )
        variables[record] += 1
    return variables


def _omit_default_thread_class(display: Any, expected_class: str, label: str) -> None:
    """Hide only the associative class token already covered by the title block."""
    display = _early_bound(display, "IDisplayDimension")
    variables_before = _hole_callout_variable_snapshot(display, label)
    class_records = [
        (record, count)
        for record, count in variables_before.items()
        if record[0] == "hw-threadclass"
    ]
    if sum(count for _record, count in class_records) != 1:
        raise RuntimeError(
            f"{label}: expected one thread-class occurrence, found {class_records!r}"
        )
    class_record = class_records[0][0]
    if class_record[1] != 3 or str(class_record[2]).strip(" -") != expected_class:
        raise RuntimeError(
            f"{label}: native thread class {class_record!r} != {expected_class!r}"
        )

    definitions = {
        part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)
    }
    matches = [
        part
        for part, definition in definitions.items()
        if "<hw-threadclass>" in definition
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one associative class token: {definitions!r}"
        )
    definition_part = matches[0]
    updated = definitions[definition_part]
    for fragment in (
        " - <hw-threadclass>",
        "- <hw-threadclass>",
        "-<hw-threadclass>",
        " <hw-threadclass>",
        "<hw-threadclass>",
    ):
        if fragment in updated:
            updated = updated.replace(fragment, "", 1)
            break
    if "<hw-threadclass>" in updated or updated == definitions[definition_part]:
        raise RuntimeError(f"{label}: failed to remove only the class token")
    display.SetText(definition_part - 4, updated)
    if str(display.GetText(definition_part) or "") != updated:
        raise RuntimeError(f"{label}: associative definition did not persist")
    if any(
        expected_class in str(display.GetText(part) or "")
        for part in (1, 2, 3, 4)
    ):
        raise RuntimeError(f"{label}: default thread class still prints")
    if any(
        str(display.GetText(part) or "") != definition
        for part, definition in definitions.items()
        if part != definition_part
    ):
        raise RuntimeError(f"{label}: unrelated callout definition changed")

    expected_variables = variables_before.copy()
    expected_variables[class_record] -= 1
    if not expected_variables[class_record]:
        del expected_variables[class_record]
    variables_after = _hole_callout_variable_snapshot(display, label)
    if variables_after != expected_variables:
        raise RuntimeError(
            f"{label}: associations changed beyond thread class: "
            f"before={variables_before!r}, after={variables_after!r}"
        )


def _assert_model_thread_class(
    source_part: Any, feature_name: str, expected_class: str, label: str
) -> None:
    """Verify drawing formatting did not alter Hole Wizard source metadata."""
    feature = _early_bound(source_part.FeatureByName(feature_name), "IFeature")
    definition = _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2")
    actual = str(definition.ThreadClass or "")
    if actual != expected_class:
        raise RuntimeError(
            f"{label}: model thread class {actual!r} != {expected_class!r}"
        )


def _assert_bore_diameter_presentation(display: Any, label: str) -> None:
    """Pin the bore callout as the same Ø12.00 ±0.2 diametric dimension."""
    display = _early_bound(display, "IDisplayDimension")
    if not bool(display.Diametric) or bool(display.DisplayAsLinear):
        raise RuntimeError(f"{label}: lost its diametric presentation")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    nominal_mm = DRAWING_NOMINALS_MM["BoreDia"]
    if abs(measured_mm - nominal_mm) > 1e-5:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {nominal_mm:g} mm"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    limit_m = BORE_DIAMETER_TOLERANCE_MM / 1000.0
    if (
        int(tolerance.Type) != 4
        or abs(float(tolerance.GetMinValue()) + limit_m) > 1e-9
        or abs(float(tolerance.GetMaxValue()) - limit_m) > 1e-9
    ):
        raise RuntimeError(f"{label}: lost its native symmetric tolerance")


_LEADER_LINE_NONE = 3  # swLeaderLineVisibility_e.swLeaderLineNone


def _suppress_dimension_line_pair(display: Any, label: str) -> None:
    """Leave only the broken-leader shoulder and its near-edge arrow.

    A leader-attached dimension (diametric dim, native hole callout) also draws
    its dimension LEADER-LINE pair from the feature straight past the text, on
    top of the broken leader's horizontal shoulder -- the two leaders crossing
    the Ø12 bore circle and the tap circle are that pair, not a mis-aimed
    attachment. ``OffsetText`` is unavailable on radial/diametric dimensions
    (``cad/docs/solidworks-drawing-layout-tuning.md`` refusal (a)), so the pair
    is hidden outright instead. ``swLeaderLineNone`` keeps the shoulder and its
    arrow (tube-frame's Ø5 cross-hole callout measured exactly one surviving
    arrowhead); the arrowhead count is read back here so a leader that vanished
    whole cannot pass for a cleaned one.
    """
    display = _sw_type_info.early_bound_or_flag(
        display,
        "IDisplayDimension",
        "GetAnnotation",
        "SetSecondArrow",
        "GetUseDocSecondArrow",
        "GetSecondArrow",
        "SetBrokenLeader2",
        "GetUseDocBrokenLeader",
        "GetBrokenLeader2",
    )
    display.ArrowSide = 1
    if int(display.ArrowSide) != 1:
        raise RuntimeError(f"{label}: outside arrow did not persist")
    display.SetSecondArrow(False, False)
    if bool(display.GetUseDocSecondArrow()) or bool(display.GetSecondArrow()):
        raise RuntimeError(f"{label}: kept its opposite-side arrow")
    display.SolidLeader = False
    if bool(display.SolidLeader):
        raise RuntimeError(f"{label}: solid leader did not clear")
    if display.SetBrokenLeader2(False, 2) != 0:
        raise RuntimeError(f"{label}: failed to apply broken horizontal leader")
    if bool(display.GetUseDocBrokenLeader()) or int(display.GetBrokenLeader2()) != 2:
        raise RuntimeError(f"{label}: broken leader style did not persist")
    display.LeaderVisibility = _LEADER_LINE_NONE
    if int(display.LeaderVisibility) != _LEADER_LINE_NONE:
        raise RuntimeError(f"{label}: kept its dimension leader-line pair")
    annotation = display.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label}: dimension has no annotation")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetDisplayData"
    )
    data = annotation.GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label}: dimension has no rendered display data")
    data = _sw_type_info.early_bound_or_flag(
        data, "IDisplayData", "GetArrowHeadCount"
    )
    arrowheads = int(data.GetArrowHeadCount())
    if arrowheads < 1:
        raise RuntimeError(
            f"{label}: hiding the leader-line pair took the arrowhead with it "
            f"({arrowheads} rendered)"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open knife-mount source", await adapter.open_model(str(SOURCE)))
    source_part = _early_bound(adapter.currentModel, "IPartDoc")
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    source_tap_contracts = _read_source_tap_depth_contracts(adapter)
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    _uppercase_dimension_text(adapter, drawing_model)
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Knife-Mount Bearing Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "knife mount; hardened steel bearing block; knife-edge bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    section = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - 0.045),
        line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.045),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="tap and knife-bore center section",
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # The manufacturing section and orthographic views use HLR; the shared
    # finalizer promotes the standard isometric to precise Shaded With Edges.
    for view in (front, section, top, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="section A-A",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    dimensions = [*front_annotations, *section_annotations, *top_annotations]
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    _assert_imported_nominals(adapter, dimensions)
    _assert_imported_tolerances(adapter, dimensions)
    assert_imported_precision(adapter, dimensions, DRAWING_PRECISION_BY_NAME)
    _assert_boss_dimensions_print_plain(adapter, section_annotations)

    # The Ø12.00 THRU callout is leader-attached, so SOLIDWORKS drew its
    # dimension leader-line pair straight across the bore circle. Suppress the
    # pair only after every writer (callout text, precision, tolerance checks)
    # has run, so nothing re-solves the dimension afterwards.
    bore_annotation = next(
        (
            annotation
            for annotation in front_annotations
            if dimension_name(adapter, annotation) == "BoreDia"
        ),
        None,
    )
    if bore_annotation is None:
        raise RuntimeError("front view lost its BoreDia dimension")
    bore_display = _early_bound(
        bore_annotation.GetSpecificAnnotation(), "IDisplayDimension"
    )
    _assert_bore_diameter_presentation(bore_display, "front bore diameter")
    _suppress_dimension_line_pair(bore_display, "front bore diameter")
    _assert_bore_diameter_presentation(bore_display, "front bore diameter")
    for view, label in ((front, "knife bore"), (top, "hanger tap")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center mark to {label}")

    # The tap's width-direction station is a parenthesized read of the model's
    # common-axis/mid-plane construction, derived from the actual finished
    # edges and the actual Hole Wizard circle: a sheet-side location with no
    # second driving acceptance requirement. Its thickness-direction location
    # is the concentric seat boss's own equation-owned BossFromEnd (on the
    # section, SECTION_KEEP above), a controlling 9.0, not a '(9.0)' reference.
    tap_radius_sheet = STUD_TAP_DIA * SHEET_SCALE[0] / 2000.0
    tap_from_side = add_edge_dimension(
        adapter,
        top,
        p0=(
            TOP_CENTER[0] - BLK_HALF_X * SHEET_SCALE[0] / 1000.0,
            TOP_CENTER[1],
        ),
        p1=(TOP_CENTER[0] - tap_radius_sheet, TOP_CENTER[1]),
        # Text at the dimension line's midpoint: centred on the tap (the old
        # TOP_CENTER x) the tap's own centreline ran up into '(12.0)'.
        text_xy=(
            TOP_CENTER[0] - BLK_HALF_X * SHEET_SCALE[0] / 2000.0,
            TOP_CENTER[1] + 0.027,
        ),
        label="hanger tap from finished side",
        orientation="horizontal",
    )
    _finish_tap_reference_dimension(
        adapter,
        tap_from_side,
        "TapFromSide",
        label="hanger tap from finished side",
    )


    # Native Hole Wizard callout owns the thread size/class and blind depth.
    tap_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + tap_radius_sheet, TOP_CENTER[1]),
        # 0.200 leaves the callout's second line ~5 mm clear of the block's
        # right outline (sheet x 0.169), which dropping '- 2B' had exposed.
        callout_xy=(0.200, TOP_CENTER[1] + 0.013),
        label="hanger-stud blind tap",
        # Policy rule 7: a hole callout states its process; the tap drill's
        # line reads DRILL Ø3.80 ↧ 14.65 (local Codex on #822, Main 2026-09-25).
        process="DRILL",
    )
    _propagate_source_tap_depth_contracts(
        adapter, tap_callout, source_tap_contracts
    )
    _check_tap_callout(tap_callout, source_tap_contracts)
    # The title block already carries THREADS UNC/UNF CLASS 2A/2B, so the
    # callout's associative class token is over-spec. It can only be dropped
    # AFTER `_check_tap_callout`, which still reads the hw-threadclass
    # variable `_omit_default_thread_class` removes from the definition.
    _omit_default_thread_class(
        tap_callout,
        STUD_TAP_SPEC.thread_class,
        "hanger-stud blind tap",
    )
    _assert_model_thread_class(
        source_part,
        "StudTap",
        STUD_TAP_SPEC.thread_class,
        "hanger-stud blind tap",
    )
    _suppress_dimension_line_pair(tap_callout, "hanger-stud blind tap callout")
    # Resolved callout text is only current after a rebuild, on a fresh handle.
    rebuild_drawing(adapter, label="hanger-stud blind tap text")
    _assert_callout_text_uppercase(tap_callout, "hanger-stud blind tap")

    # A surface-finish annotation's sheet position is its LOWER-LEFT corner,
    # which is also where its leader starts: hung left of the bore the leader
    # ran up-right through the symbol's own 'Ra 1.6' value text. Attach on the
    # bore's lower-right rim and hang the symbol below-right of it instead --
    # the leader then runs up-left, away from its text. Parked beside the block
    # rather than under it, the symbol clears the 24.00 width dimension's right
    # extension line; the leader crossing the block outline itself is normal.
    add_surface_finish(
        adapter,
        front,
        edge_xy=(
            FRONT_CENTER[0] + R_BORE * SHEET_SCALE[0] * 0.7071 / 1000.0,
            _front_y(BORE_CY) - R_BORE * SHEET_SCALE[0] * 0.7071 / 1000.0,
        ),
        symbol_xy=(FRONT_CENTER[0] + 0.032, _front_y(BORE_CY) - 0.014),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_bore"),
        label="knife bore finish",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.160)
    # Cosmetic-thread imports can be regenerated by dimension/callout rebuilds,
    # and SolidWorks attaches each to whichever view imports its feature first,
    # so hide every one across all sheets only after all recipe annotations
    # exist -- the hide is the gate, not any census size.
    _hide_cosmetic_thread_annotations(adapter)
    # SolidWorks' own '#10-24 Tapped Hole' is an INote, so the swCThread census
    # above can never see it: delete it per view here, after every recipe
    # annotation exists and immediately before finalize. The per-view counts
    # are evidence of which views imported the tapped feature this build, never
    # a gate -- the count is a lottery.
    auto_tapped_notes = _auto_tapped_hole_notes(adapter)
    _telemetry.info(f"knife-mount automatic tapped-hole notes: {auto_tapped_notes!r}")
    # The sweep deletes SolidWorks' notes, never our associative callout: prove
    # the tap callout still reads its thread description afterwards.
    tap_strings = {
        record[0]: record[2]
        for record in _hole_callout_variable_snapshot(
            tap_callout, "hanger-stud blind tap"
        )
        if record[1] == 3
    }
    if tap_strings.get("hw-threaddesc", "").strip(" -") != _TAP_THREAD_DESCRIPTION:
        raise RuntimeError(
            "hanger-stud blind tap lost its thread description to the "
            f"redundant-note sweep: {tap_strings!r}"
        )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Mount Bearing Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # The associative tap callout replaces SolidWorks' own descriptive
        # thread notes: the automatic "Tapped Hole" notes are already gone,
        # deleted and proved per view by ``_auto_tapped_hole_notes`` above.
        redundant_note_substrings=(),
        expected_redundant_notes=0,
    )




def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
