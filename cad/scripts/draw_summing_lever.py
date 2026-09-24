r"""Create the two-sheet manufacturing drawing for MHA-073.

The SLDPRT owns every nominal, decimal place, tolerance and surface control.
Sheet ``FORM-KNIFE`` defines the lever envelope, boss and knife trunnions at
native 1:2 sheet scale, with a native 2:1 Detail A for the functional knife
end. Sheet ``SPRING-PATTERN`` locates both terminal holes of the authoritative
20-hole field from the same plate end, with an equal-spacing reference.
All orthographic views are HLR; the standard isometric is finalized as
precision Shaded With Edges.

Run with SolidWorks open::

    uv run python cad\scripts\draw_summing_lever.py summing-lever
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from typing import Any

from win32com.client.dynamic import Dispatch as dynamic_dispatch

import _telemetry
from _hole_spec import blind_cut_dia_mm
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    _drawing_component_name,
    add_edge_dimension,
    add_native_hole_callout,
    add_note,
    add_surface_finish,
    assert_imported_precision,
    create_blank_drawing_sheets,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    scan_view_edges,
    stamp_drawing_summary,
    set_reference_dimension,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import format_findings as format_layout_findings
from diagnostics.drawing_layout_audit import audit_document
from _surface_finish import surface_finish_by_key
from summing_lever_spec import (
    ANCHOR_R,
    CYL_R,
    COUNTER_HOLE_SPEC,
    DRAWING_REFERENCE_PRECISION,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEX_H,
    HEX_W,
    HEX_Z_OUTER,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_LAST,
    PLATE_W,
    SURFACE_FINISHES,
    TIP_X,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["summing_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
# Tap-drill diameter of the boss's counter-anchor tap; the rim points below
# pick its circular edge, and the native callout prints the thread itself.
COUNTER_R = blind_cut_dia_mm(COUNTER_HOLE_SPEC) / 2.0

SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 2.0)
SHEET_NAMES = ("FORM-KNIFE", "SPRING-PATTERN")

FORM_FRONT_SCALE = SHEET_SCALE
FORM_TOP_SCALE = SHEET_SCALE
ISO_SCALE = SHEET_SCALE
PATTERN_SCALE = SHEET_SCALE

# Front (down -Z) and top (down -Y) share this X envelope.
_BBOX_CX = (TIP_X - ANCHOR_R + PLATE_W) / 2.0

FORM_FRONT_CENTER = (0.150, 0.220)
FORM_TOP_CENTER = (0.150, 0.105)  # same X: true third-angle projection
# The isometric lives on sheet 2 so Detail A can keep its visible parent on sheet 1.
ISO_CENTER = (0.340, 0.195)
PATTERN_CENTER = (0.165, 0.145)
# Sheet-1 Detail A, cut from the real (still visible) *Front view.
DETAIL_CENTER = (0.330, 0.155)
DETAIL_SCALE = (2.0, 1.0)
DETAIL_RADIUS_MM = CYL_R + 3.3
# The parent circle's "A", from the front view's model origin: lower right of the
# fence, below the edge-rib flank and above the 76.2 / 35.75 chain.  SolidWorks'
# default seat printed it on that flank.
DETAIL_LETTER_OFFSET = (0.0115, -0.0125)


def _top_xy(
    mx: float,
    mz: float,
    *,
    center: tuple[float, float],
    scale: tuple[float, float],
) -> tuple[float, float]:
    """Project model X/Z millimetres into one explicit top-view sheet frame."""
    factor = scale[0] / scale[1]
    return (
        center[0] + (mx - _BBOX_CX) * factor / 1000.0,
        center[1] + mz * factor / 1000.0,
    )


def _assert_uses_sheet_scale(view: Any, label: str) -> None:
    """Prove a view follows the native sheet scale printed in the title block."""
    bound = _early_bound(view, "IView")
    if int(bound.UseSheetScale) != 1:
        raise RuntimeError(f"{label} does not use its native sheet scale")


def _attach_radial_leaders(
    adapter: Any, annotations: Any, names: tuple[str, ...], label: str
) -> None:
    """Attach radial leaders to their own arcs instead of extending across the view.

    ``ArcExtensionLineOrOppositeSide`` defaults to True, which sweeps the R138.8
    summation arc through the top view and trails the R15.2 edge-rib leader
    across the front view.  ``SolidLeader`` defaults to True on this template,
    which rules each leader on from the arc to its centre: the R3 render drew the
    R138.8 leader out to its off-view centre across the (195.83) extension line
    and the 2X R15.2 leader through the 35.75 dimension line.  Both are bool
    get/set properties, so each assignment is only proven by reading it back.
    """
    wanted = set(names)
    seen = set()
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in wanted:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArcExtensionLineOrOppositeSide = False
        if bool(display.ArcExtensionLineOrOppositeSide):
            raise RuntimeError(
                f"{label}: {name} leader still attaches to the arc extension line"
            )
        display.SolidLeader = False
        if bool(display.SolidLeader):
            raise RuntimeError(f"{label}: {name} leader still runs to the arc centre")
        seen.add(name)
    missing = sorted(wanted - seen)
    if missing:
        raise RuntimeError(f"{label}: no radial dimension named {missing!r}")


# Codex raised the mid-rib ends three times (R7, R11, R12) although 76.2 / 35.8
# locate them: nothing told the reader those stations are the rib's own apexes
# (on its mid-plane, inside the boss and the plate), so the visible ends -- the
# flanks running out into web and plate -- looked unlocated.  Name them where
# they print.  Fable R14b then could not tell the two R15.2 callouts apart (the
# mid rib's and the end ribs', one outline in the front view), and the plate's
# 5.08 now governs the web as well.  (dimension, callout part, text):
# 3 = swDimensionTextCalloutAbove, 4 = swDimensionTextCalloutBelow.
DIMENSION_CALLOUTS = (
    ("MidRibRightX", 3, "RIB APEX"),
    ("MidRibLeftX", 3, "RIB APEX"),
    ("MiddleRibThickness", 4, "MID RIB"),
    ("MidRibArcR", 4, "MID RIB"),
    ("EdgeRibFrontArcR", 4, "END RIBS"),
    ("PlateThickness", 4, "PLATE AND WEB"),
)


def _label_dimensions(
    adapter: Any, annotations: Any, names: tuple[str, ...], label: str
) -> None:
    """Write and read back the callouts on the named dimensions."""
    wanted = {
        name: (part, text) for name, part, text in DIMENSION_CALLOUTS if name in names
    }
    seen = set()
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in wanted:
            continue
        part, text = wanted[name]
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(part, text)
        if str(display.GetText(part) or "") != text:
            raise RuntimeError(f"{label}: {name} callout {text!r} did not persist")
        seen.add(name)
    missing = sorted(set(wanted) - seen)
    if missing:
        raise RuntimeError(f"{label}: no callout dimension named {missing!r}")


def _assert_arc_centre_text(
    adapter: Any, annotations: Any, names: tuple[str, ...], label: str
) -> None:
    """Read back that the imported R138.8 centre locations print as controlling.

    The part authors a bare "2X " on both (build_summing_lever); R11 printed
    them parenthesized, which left the arc with no controlling location (Codex
    R11 B2), so a stray "(" or ")" fails here.
    """
    seen = set()
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in names:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        texts = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        if texts != ("2X ", "") or bool(display.ShowParenthesis):
            raise RuntimeError(
                f"{label}: {name} prints {texts!r}, not as a controlling 2X location"
            )
        seen.add(name)
    missing = sorted(set(names) - seen)
    if missing:
        raise RuntimeError(f"{label}: no arc-centre dimension named {missing!r}")


FORM_FRONT_KEEP = {
    # Dimension line close to the boss: its long witness lines read as a bar
    # beside the boss to two blind reviewers (Fable R14b B2, R15c B1).
    "AnchorHeight": (0.1080, 0.2300),
    # "MID RIB" below: 2 mm right of R14b so the label clears its own leader.
    "MidRibArcR": (0.1720, 0.2420),
    # Past its own arrows (between them the witness lines ruled through the
    # text), below the plate so "PLATE AND WEB" clears the note block, and close
    # to the plate end: longer witness lines read as the plate running on
    # (Fable R15c B1).
    "PlateThickness": (0.1950, 0.2120),
    # Both carry "RIB APEX" above the value (DIMENSION_CALLOUTS).  35.8 sits past
    # its +X witness so that label clears the shared cylinder-axis witness.
    # 2.5 mm lower than R14b: room for "END RIBS" under the 2X R15.2 above,
    # one text height clear of the top view's 2X 123.2 below (3 mm crowded it:
    # R15b census).
    "MidRibRightX": (0.1413, 0.1935),
    "MidRibLeftX": (0.1943, 0.1935),
    # Lower left, onto the edge rib's own (-X) semicircle, above the 76.2 / 35.75
    # chain: from the lower right its leader crossed the 35.75 dimension line.
    "EdgeRibFrontArcR": (0.1350, 0.2080),
}
FORM_TOP_KEEP = {
    "PlateWidth": (0.1714, 0.1650),
    "PlateLength": (0.2350, 0.1050),
    # Below the boss, so the counter-tap callout above can reach its hole clear.
    "AnchorOuterDia": (0.1036, 0.0955),
    "AnchorOuterX": (0.1350, 0.0450),
    # Both "2X" callouts sit beside the -Z instance they measure: parked at the
    # top, each drew a dimension line the length of the view.
    # 4 mm left of R9's seat: the census's width-estimated text box reached the
    # cylinder-axis witness of AnchorOuterX at x 160.3 mm (R10 text-on-line).
    "HexKnifeFrontDepth": (0.1430, 0.0617),
    "EdgeRibThickness": (0.1900, 0.0590),
    # Below its own arrows: between them the witness lines ruled through the text.
    "MiddleRibThickness": (0.1985, 0.0950),
    # Inside the arc, on the radial 50 deg below the located centre, 0.6 R out:
    # the dimension line runs from the centre's cross to the arc.  Beyond the
    # centre (R5-R7) the leader crossed the corner where the 2X 123.2 / 2X 64.0
    # witness lines meet (Main's R7 eye pass).
    "SummationArcRadius": (0.1251, 0.1431),
    # The R138.8 centre from the plate end face on the cylinder axis; both
    # dimensions sit in the clear field above the web, their witness lines
    # crossing at the centre.
    "SummationArcCentreX": (0.1295, 0.1833),
    "SummationArcCentreZ": (0.2029, 0.1591),
    "BossAxialLocation": (0.0900, 0.0860),
    # In the clear web field left of the tube; its dimension line lands on the
    # construction chord (build_summing_lever.CYLINDER_REFERENCE_Z).  The census sizes the text from its string, "<MOD-DIAM>"
    # token included (27 mm estimated for "Ø25.4"), and R15b's seat put that
    # box across the cylinder-axis witness of PlateWidth: this one keeps the
    # estimate short of it while the real text stays clear of the web arc.
    "CylRefDia": (0.1380, 0.1115),
}
DETAIL_KEEP = {
    "HexWidth": (0.330, 0.113),
    "HexHeight": (0.378, 0.155),
    # On the +X flat, inside the 10.27 and short of the R15.2 outline: from the
    # -X flat its witness lines ran collinear with the 5.08 web edges (Fable R14b).
    "HexKnifeFrontSideFlat": (0.3577, 0.1550),
}
PATTERN_KEEP = {
    "HoleSeedX": (0.190, 0.205),
    # Left of the baseline dimension's line, so that line runs clear of the text.
    "HolePitch": (0.215, 0.128),
    # Both terminal holes from the model +Z plate end, the sheet's LOWER end.
    # Below its own arrows: between them the witness lines ruled through the text.
    "HoleEndOffsetLast": (0.252, 0.100),
    "HoleFirstFromEnd": (0.2656, 0.147),
}

# The whole general-note block: four lines, sheet 1 upper right beside Detail A.
# Pinned to four on purpose -- the drawing simplicity policy treats a growing
# note block as the disease the migration cures, not as the cure.
MANUFACTURING_NOTES: tuple[tuple[str, float, float], ...] = (
    ("CLOCK KNIFE RIDGE TO BOSS AXIS", 0.230, 0.255),
    ("NONREGULAR 6-SIDED PROFILE; SYMMETRIC ABOUT BOTH CENTERLINES", 0.230, 0.246),
    ("KNIFE RIDGES SHARP; NO EDGE BREAK", 0.230, 0.237),
    # The Ra value lives on the model's finish control (Detail A's symbol); the
    # note only scopes it, so the sheet never restates a manufacturing value.
    (
        "DETAIL A FINISH ON THE TWO FLATS AT THE KNIFE RIDGE, BOTH TRUNNIONS",
        0.230,
        0.228,
    ),
)


def _knife_detail(adapter: Any, front: Any) -> Any:
    """Create a native 2:1 crop of the actual hex trunnion end."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not ddoc.ActivateView(view_name(adapter, front)):
        raise RuntimeError("failed to activate knife-detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        front,
        (0.0, 0.0, 0.0),
        label="knife-detail center",
    )
    radius = DETAIL_RADIUS_MM * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if sketch_manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create knife-detail fence")
    detail = ddoc.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        "A",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create native knife-end detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    initial_outline = tuple(float(value) for value in detail.GetOutline())
    initial_position = tuple(float(value) for value in detail.Position)
    if len(initial_outline) != 4 or len(initial_position) != 2:
        raise RuntimeError(
            f"invalid knife-detail bounds: {initial_outline!r}, {initial_position!r}"
        )
    positioned_origin = tuple(
        initial_position[axis]
        + DETAIL_CENTER[axis]
        - (initial_outline[axis] + initial_outline[axis + 2]) / 2.0
        for axis in range(2)
    )
    if not detail.SetViewPosition(double_array(list(positioned_origin)), False):
        raise RuntimeError("failed to position knife-end detail")
    draw.EditRebuild3()
    final_outline = tuple(float(value) for value in detail.GetOutline())
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    outline_center = (
        (final_outline[0] + final_outline[2]) / 2.0,
        (final_outline[1] + final_outline[3]) / 2.0,
    )
    if (
        len(ratio) != 2
        or not math.isclose(ratio[0] / ratio[1], DETAIL_SCALE[0] / DETAIL_SCALE[1])
        or math.dist(outline_center, DETAIL_CENTER) > 0.0001
    ):
        raise RuntimeError(
            f"knife-detail scale/position did not persist: "
            f"ratio={ratio!r}, outline={final_outline!r}"
        )
    return detail


def _place_detail_letter(adapter: Any, front: Any) -> None:
    """Seat the parent circle's letter in clear air, proved by read-back."""
    circles = tuple(
        _read_member(_early_bound(front, "IView"), "GetDetailCircles") or ()
    )
    if len(circles) != 1:
        raise RuntimeError(f"expected one knife-detail circle, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    origin = model_point_in_view(
        adapter, front, (0.0, 0.0, 0.0), label="knife-detail letter reference"
    )
    target = tuple(origin[i] + DETAIL_LETTER_OFFSET[i] for i in range(2))
    circle.SetLabelPosition(*target)  # VT_VOID: the read-back is the proof
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in circle.GetLabelPosition())
    if len(actual) != 2 or math.dist(actual, target) > 1e-8:
        raise RuntimeError(f"knife-detail letter position did not persist: {actual}")


def _show_view_sketch(adapter: Any, view: Any, sketch: str) -> None:
    """Show one model reference sketch in one drawing view, as a print mark.

    The part saves every drawing-reference sketch hidden
    (``build_summing_lever.DRAWING_REFERENCE_SKETCHES``), so they stay out of
    its renders and every assembly, and the targeted import shows each one only
    for its own call (``_drawing_common.insert_feature_dimensions``).  Two are
    print marks and are shown for good: the R138.8 centre cross in the top view
    (Main's R7 "unmarked centres") and the knife envelope's centre "+" in the
    front view and Detail A.  ``UnblankSketch`` is VT_VOID and there is no
    per-view read-back, so the selection is the gate and the render the proof.
    """
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not _early_bound(draw, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate {name} to show {sketch}")
    draw.ClearSelection2(True)
    # The middle qualifier is the view's own model instance ("summing-lever-N",
    # numbered per view), not the file stem: the stem refused on R4.
    qualified = f"{sketch}@{_drawing_component_name(adapter, view)}@{name}"
    if not draw.Extension.SelectByID2(
        qualified, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {qualified}")
    draw.UnblankSketch()
    draw.ClearSelection2(True)


@_telemetry.traced("drawing.lever_layout_census")
def _audit_lines_through_text(adapter: Any) -> None:
    """Fail the drawing when any line runs through another annotation's text.

    The shared layout gate boxes dimensions nominally and checks leaders only
    against view outlines, so nothing caught R8's 2X 123.2 witness line running
    up through the front view's 5.08 text (Main's R8 eye pass).  The
    annotation-level census reads every dimension's real rendered lines and
    text; its text-on-line finding is policy rule 8's "no text on a line".  The
    other finding kinds are logged for the eye pass, not gated here.
    """
    findings = audit_document(adapter)
    if findings:
        _telemetry.info("lever layout census:\n" + format_layout_findings(findings))
    blocking = [finding for finding in findings if finding.kind == "text-on-line"]
    if blocking:
        raise RuntimeError(
            "a line runs through annotation text:\n" + format_layout_findings(blocking)
        )


def _hole_callout_variable_snapshot(
    display: Any, label: str
) -> Counter[tuple[Any, ...]]:
    """Read a multiset of native variables in the current callout definition."""
    display = _early_bound(display, "IDisplayDimension")
    variables: Counter[tuple[Any, ...]] = Counter()
    for raw in display.GetHoleCalloutVariables() or ():
        variable = dynamic_dispatch(raw._oleobj_)
        name = str(variable.VariableName)
        kind = int(variable.Type)
        if kind == 1:  # swCalloutVariableType_Length
            value = _early_bound(raw, "ICalloutLengthVariable")
            record = (
                name,
                kind,
                float(value.Length),
                int(value.Precision),
                int(value.TolerancePrecision),
            )
        elif kind == 2:  # swCalloutVariableType_Angle
            value = _early_bound(raw, "ICalloutAngleVariable")
            record = (name, kind, float(value.Angle), int(value.Precision))
        elif kind == 3:  # swCalloutVariableType_String
            value = _early_bound(raw, "ICalloutStringVariable")
            record = (name, kind, str(value.String or ""))
        else:
            raise RuntimeError(
                f"{label}: unsupported native callout variable type {kind} for {name!r}"
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
            f"{label}: expected exactly one native thread-class occurrence, "
            f"found {class_records!r}"
        )
    class_record = class_records[0][0]
    if class_record[1] != 3 or str(class_record[2]).strip(" -") != expected_class:
        raise RuntimeError(
            f"{label}: native thread class {class_record!r} != "
            f"string {expected_class!r}"
        )

    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    matches = [
        part
        for part, definition in definitions.items()
        if "<hw-threadclass>" in definition
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one associative thread-class token: {definitions!r}"
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
        raise RuntimeError(f"{label}: failed to remove only the thread-class token")
    resolved_part = definition_part - 4
    display.SetText(resolved_part, updated)
    if str(display.GetText(definition_part) or "") != updated:
        raise RuntimeError(f"{label}: associative callout definition did not persist")
    resolved = tuple(str(display.GetText(part) or "") for part in (1, 2, 3, 4))
    if any(expected_class in text for text in resolved):
        raise RuntimeError(f"{label}: default thread class still prints: {resolved!r}")
    if any(
        str(display.GetText(part) or "") != definition
        for part, definition in definitions.items()
        if part != definition_part
    ):
        raise RuntimeError(f"{label}: unrelated native callout definition changed")

    expected_variables = variables_before.copy()
    expected_variables[class_record] -= 1
    if not expected_variables[class_record]:
        del expected_variables[class_record]
    variables_after = _hole_callout_variable_snapshot(display, label)
    if variables_after != expected_variables:
        raise RuntimeError(
            f"{label}: native callout associations changed beyond thread class: "
            f"before={variables_before!r}, after={variables_after!r}"
        )


def _assert_model_thread_class(
    source_part: Any, feature_name: str, expected_class: str, label: str
) -> None:
    """Verify the drawing-only format edit did not alter Hole Wizard metadata."""
    feature = _early_bound(source_part.FeatureByName(feature_name), "IFeature")
    definition = _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2")
    actual = str(definition.ThreadClass or "")
    if actual != expected_class:
        raise RuntimeError(
            f"{label}: model Hole Wizard thread class {actual!r} != {expected_class!r}"
        )


# SolidWorks attaches one of its own automatic "Tapped Hole" notes to a view
# that imports a tapped feature's marked dimensions.  Neither the COUNT nor the
# SET of views is specification: draw_top_frame measured 7, then 8, then 5
# across three builds of the same geometry, and a change that only moved three
# annotation texts attached one to a different view -- SolidWorks attaches a
# feature's note to whichever view imports that feature FIRST, and which
# instance a re-pick lands on is not ours to choose.  So this inventory is
# evidence, not a gate.  The invariant that reaches the print is the deletion:
# exactly the inventoried notes must go, each proved by a read-back of its view.


@_telemetry.traced("drawing.auto_tapped_hole_notes")
def _auto_tapped_hole_notes(adapter: Any) -> dict[str, int]:
    """Delete SolidWorks' own Hole Wizard notes, named per view, on every sheet.

    The sheet states each thread in its own associative feature callout, which
    carries the process too.  Deleting here rather than handing the substring to
    ``finalize_drawing`` skips that sweep's re-walk of every annotation of every
    view, sheet by sheet, for notes this walk -- ``ISheet::GetViews`` off the
    sheet objects, no sheet activation -- already holds.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    counts: dict[str, int] = {}
    for sheet_name in drawing.GetSheetNames() or ():
        sheet = _early_bound(drawing.Sheet(str(sheet_name)), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            hits = [
                note
                for note in (
                    _early_bound(raw_note, "INote")
                    for raw_note in (view.GetNotes() or ())
                )
                if "tapped hole" in str(note.GetText() or "").lower()
            ]
            if not hits:
                continue
            label = f"{sheet_name}/{view_name(adapter, view)}"
            for note in hits:
                draw.ClearSelection2(True)
                if not _early_bound(note.GetAnnotation(), "IAnnotation").Select2(
                    False, 0
                ):
                    raise RuntimeError(
                        f"{label}: failed to select an automatic tapped-hole note"
                    )
                draw.EditDelete()  # VT_VOID: the re-read below is the proof
            draw.ClearSelection2(True)
            survivors = sum(
                1
                for raw_note in (view.GetNotes() or ())
                if "tapped hole"
                in str(_early_bound(raw_note, "INote").GetText() or "").lower()
            )
            if survivors:
                raise RuntimeError(
                    f"{label}: {survivors} automatic tapped-hole note(s) "
                    f"survived deletion"
                )
            counts[label] = len(hits)
    return counts


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="summing-lever manufacturing package"
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; ferrous; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate summing-lever form sheet")
    front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *FORM_FRONT_CENTER,
    )
    top = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *FORM_TOP_CENTER,
    )
    for label, view in (("form front", front), ("form top", top)):
        _assert_uses_sheet_scale(view, label)
    for view in (front, top):
        set_hidden_lines_removed(adapter, view)

    front_dimensions = curate_view_dimensions(
        adapter,
        front,
        keep=FORM_FRONT_KEEP,
        view_label="form front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_dimensions = curate_view_dimensions(
        adapter,
        top,
        keep=FORM_TOP_KEEP,
        view_label="form top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Radial leaders attach to their own arcs: on the default setting the R138.8
    # summation arc sweeps through the top view and the R15.2 edge-rib leader
    # trails across the front view.
    _attach_radial_leaders(
        adapter, front_dimensions, ("MidRibArcR", "EdgeRibFrontArcR"), "form front"
    )
    _attach_radial_leaders(adapter, top_dimensions, ("SummationArcRadius",), "form top")
    _label_dimensions(
        adapter,
        front_dimensions,
        (
            "MidRibRightX",
            "MidRibLeftX",
            "MidRibArcR",
            "EdgeRibFrontArcR",
            "PlateThickness",
        ),
        "form front",
    )
    _label_dimensions(adapter, top_dimensions, ("MiddleRibThickness",), "form top")
    _assert_arc_centre_text(
        adapter,
        top_dimensions,
        ("SummationArcCentreX", "SummationArcCentreZ"),
        "form top",
    )
    # This is a read-only measurement of the actual knife-ridge endpoints,
    # not a second calculated model dimension.  Resolve the two model vertices
    # from one native visible-edge sweep and select those exact entities; sheet
    # hit-testing near the end edges can otherwise choose a perpendicular edge
    # and silently create an angular dimension.
    top_edges = scan_view_edges(top, label="form top overall reference")
    overall_vertices = tuple(
        top_edges.exact_vertex_at(
            (0.0, HEX_H / 2.0, z),
            label=f"knife-ridge endpoint z={z:g}",
        )
        for z in (-HEX_Z_OUTER, HEX_Z_OUTER)
    )
    overall = _early_bound(
        add_edge_dimension(
            adapter,
            top,
            p0=_top_xy(
                0.0,
                -HEX_Z_OUTER,
                center=FORM_TOP_CENTER,
                scale=FORM_TOP_SCALE,
            ),
            p1=_top_xy(
                0.0,
                HEX_Z_OUTER,
                center=FORM_TOP_CENTER,
                scale=FORM_TOP_SCALE,
            ),
            text_xy=(0.075, FORM_TOP_CENTER[1]),
            label="overall trunnion length reference",
            orientation="vertical",
            entity_types=("VERTEX", "VERTEX"),
            entities=overall_vertices,
        ),
        "IDisplayDimension",
    )
    dimension_type = int(overall.Type2)
    if dimension_type not in (2, 11, 12):
        raise RuntimeError(
            "overall trunnion reference is not linear: "
            f"IDisplayDimension.Type2={dimension_type}"
        )
    overall_annotation = _early_bound(overall.GetAnnotation(), "IAnnotation")
    set_reference_dimension(
        adapter,
        overall_annotation,
        label="overall trunnion length reference",
    )
    overall.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(overall.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("overall trunnion reference precision did not persist")
    overall_dimension = _early_bound(overall.GetDimension2(0), "IDimension")
    measured_overall_mm = abs(float(overall_dimension.SystemValue) * 1000.0)
    expected_overall_mm = 2.0 * HEX_Z_OUTER
    if abs(measured_overall_mm - expected_overall_mm) > 1e-5:
        raise RuntimeError(
            "overall trunnion reference measured "
            f"{measured_overall_mm:g}, expected {expected_overall_mm:g} mm"
        )
    if int(overall_dimension.GetToleranceType()) != 0:  # swTolNONE
        raise RuntimeError(
            "overall trunnion reference unexpectedly carries a tolerance"
        )
    overall_text_xy = (0.045, 0.105)
    if not overall_annotation.SetPosition2(*overall_text_xy, 0.0):
        raise RuntimeError("failed to position overall trunnion reference text")
    overall_text_position = tuple(
        float(value) for value in overall_annotation.GetPosition()
    )
    if math.dist(overall_text_position[:2], overall_text_xy) > 0.0001:
        raise RuntimeError(
            "overall trunnion reference text position did not persist: "
            f"{overall_text_position[:2]!r}"
        )

    counter_tap_edge = _top_xy(
        TIP_X,
        COUNTER_R,
        center=FORM_TOP_CENTER,
        scale=FORM_TOP_SCALE,
    )
    counter_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=counter_tap_edge,
        # Under the (195.83) extension line so the leader reaches the tap
        # without crossing it.
        callout_xy=(0.0719, 0.1390),
        label="counter-spring anchor tap",
    )
    _omit_default_thread_class(
        counter_callout,
        COUNTER_HOLE_SPEC.thread_class,
        "counter-spring anchor tap",
    )
    _assert_model_thread_class(
        source_part,
        "CounterAnchorTap",
        COUNTER_HOLE_SPEC.thread_class,
        "counter-spring anchor tap",
    )

    _show_view_sketch(adapter, top, "SummationArcReference")
    # Before the detail, which takes its sketch display from its parent.
    _show_view_sketch(adapter, front, "KnifeEnvelopeReference")
    detail = _knife_detail(adapter, front)
    _place_detail_letter(adapter, front)
    set_hidden_lines_removed(adapter, detail)
    detail_dimensions = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="knife-end detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Again: the detail's import shows and re-blanks the knife envelope through
    # its parent's model-item path, which undoes the parent's mark.
    _show_view_sketch(adapter, front, "KnifeEnvelopeReference")
    knife_surface_mm = (HEX_W / 4.0, 3.0 * HEX_H / 8.0, HEX_Z_OUTER)
    detail_edges = scan_view_edges(detail, label="knife-end detail finish")
    knife_surface_edge = detail_edges.exact_line_through(
        knife_surface_mm,
        label="upper-right knife face at outboard end",
    ).edge
    knife_surface_xy = model_point_in_view(
        adapter,
        detail,
        tuple(value / 1000.0 for value in knife_surface_mm),
        label="knife-ridge finish attachment",
    )
    add_surface_finish(
        adapter,
        detail,
        edge_entity=knife_surface_edge,
        symbol_xy=(0.360, 0.206),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge"),
        label="knife-edge ridge finish",
        leader_attach_xy=knife_surface_xy,
        char_height=0.0025,
    )
    for note_text, note_x, note_y in MANUFACTURING_NOTES:
        if add_note(adapter, note_text, note_x, note_y) is None:
            raise RuntimeError(f"failed to state {note_text!r}")

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate summing-lever spring-pattern sheet")
    pattern = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *PATTERN_CENTER,
    )
    iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *ISO_CENTER,
    )
    for label, view in (
        ("spring-pattern plan", pattern),
        ("spring-pattern pictorial", iso),
    ):
        _assert_uses_sheet_scale(view, label)
    for view in (pattern, iso):
        set_hidden_lines_removed(adapter, view)
    pattern_dimensions = curate_view_dimensions(
        adapter,
        pattern,
        keep=PATTERN_KEEP,
        view_label="spring-pattern plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    seed_rim_right = _top_xy(
        HOLE_X + HOLE_DIA / 2.0,
        HOLE_Z_LAST,
        center=PATTERN_CENTER,
        scale=PATTERN_SCALE,
    )
    # Above the staggered pattern-dimension lanes, left of the pictorial.
    spring_callout = add_native_hole_callout(
        adapter,
        pattern,
        edge_xy=seed_rim_right,
        # 10 mm right of R14b: the leader from the shelf's left end ran
        # through the estimated "39.85 +-0.15" box (R15b census, 1.48 mm).
        callout_xy=(0.255, 0.222),
        label="spring-hole pattern",
    )
    _omit_default_thread_class(
        spring_callout,
        HOLE_SPEC.thread_class,
        "spring-hole pattern",
    )
    _assert_model_thread_class(
        source_part,
        "SpringHoleSeed",
        HOLE_SPEC.thread_class,
        "spring-hole pattern",
    )

    for sheet_index, sheet_name in enumerate(SHEET_NAMES, start=1):
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to label drawing sheet {sheet_name}")
        if (
            add_note(
                adapter,
                f"SHEET {sheet_index} OF {len(SHEET_NAMES)}",
                0.350,
                0.263,
            )
            is None
        ):
            raise RuntimeError(f"failed to stamp sheet count on {sheet_name}")

    tap_notes = _auto_tapped_hole_notes(adapter)
    _telemetry.info(f"automatic tapped-hole notes per view: {tap_notes!r}")
    _audit_lines_through_text(adapter)
    assert_imported_precision(
        adapter,
        [*front_dimensions, *top_dimensions, *detail_dimensions, *pattern_dimensions],
        DRAWING_PRECISION_BY_NAME,
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # The automatic "Tapped Hole" notes are already gone, deleted and proved
        # per view by _auto_tapped_hole_notes above: the sheet states each thread
        # in its own associative feature callout, which carries the process too.
        redundant_note_substrings=(),
        expected_redundant_notes=0,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales={name: SHEET_SCALE for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
