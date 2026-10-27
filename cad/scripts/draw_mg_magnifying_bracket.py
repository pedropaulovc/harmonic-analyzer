r"""Native manufacturing sheet for the simple threaded L bracket.

Model sizes import from the saved SLDPRT. The ordinary end view and associative
1/4-20 UNC THRU callout define the simple tapped hole; no section is needed.
Its fit class, inside corners and ordinary edge breaks follow the title block.
The native neck prints 12.5; explicit 3.175 +/-0.13 retains the screw-grip stack
and is witnessed from the foot's free end, where its top and bottom are edges.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

from _check import check
from _com import _early_bound
from _drawing_annotation_extent import CalloutInk, gdt_box, move_annotation, require_clear, require_inside, sheet_region
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, rebuild_drawing, stamp_drawing_summary
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_arc_endpoints_to_max, set_reference_dimension
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_layout_audit import annotation_display
from _drawing_layout_check import LeaderSegment
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _layout_audit import _display_segments
from _layout_geometry import Box, Segment, estimate_text_box, segment_box_overlap_length, union_boxes
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _surface_finish import surface_finish_by_key
from _session import run_build
import _telemetry
from magnifying_bracket_joint_layout import BRACKET_HOLE_POINTS, CLEARANCE_DIA, SIDE_PLATE_X, SIDE_PLATE_Y, SIDE_PLATE_Z
from mg_lever_thread_joint import MOUTH_CHAMFER, NECK_HALF_X, NOSE_R, TAP_DRILL_DIA, THREAD
from mg_magnifying_bracket_spec import DIMENSION_CALLOUTS, DRAWING_DIMENSIONS, DRAWING_REFERENCE_PRECISION, MOUNTING_HOLE_PROCESS, TAP_PROCESS
from mg_magnifying_bracket_finish_spec import SURFACE_FINISHES

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["mg_magnifying_bracket"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (1, 1)
FRONT_CENTER = (0.079, 0.165)
BOTTOM_CENTER = (0.079, 0.080)
SIDE_CENTER = (0.228, 0.165)
ISO_CENTER = (0.350, 0.130)
ISO_SCALE = (1, 2)
FRONT_KEEP = {"NeckThickness": (0.118, 0.185), "FlangeWidth": (0.079, 0.098), "FlangeDepth": (0.044, 0.123)}
BOTTOM_KEEP = {"FlangeHeight": (0.132, 0.080)}
SIDE_KEEP = {"NoseR": (0.266, 0.229), "SeatToAxis": (0.196, 0.165)}
MOUNTING_KEEP = {"MountingX0": (0.045, 0.056), "MountingX1": (0.060, 0.046), "MountingY0": (0.030, 0.080)}
TAP_KEEP = {"TapFromTip": (0.206, 0.226), "TapFromSide": (0.240, 0.240)}
OVERALL_REFERENCE_XY = (0.174, 0.185)


def _mounting_rims(view: Any) -> tuple[Any, ...]:
    """The *Front HLR view sees the +Z mounting-face exits, not drill entries."""
    edges = scan_view_edges(view, label="unchanged bracket mounting holes")
    return tuple(
        edges.circle_at((point[0], point[1], SIDE_PLATE_Z[1]), CLEARANCE_DIA / 2.0, axis=(0.0, 0.0, 1.0), label=f"mounting-hole {index} exit rim")
        for index, point in enumerate(BRACKET_HOLE_POINTS)
    )


def _project_side_view(adapter: Any, front: Any, side: Any) -> None:
    """Measured third-angle projection: +Z down, +Y left, equal axis height."""
    native = _early_bound(side, "IView")
    origin = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label="side origin")
    down = model_point_in_view(adapter, native, (0.0, 0.0, 0.01), label="side +Z")
    native.Angle = float(native.Angle) - math.pi / 2.0 - math.atan2(down[1] - origin[1], down[0] - origin[0])
    rebuild_drawing(adapter, label="turn threaded bracket end view")
    target = (SIDE_CENTER[0], model_point_in_view(adapter, front, (0.0, 0.0, 0.0), label="front origin")[1])
    origin = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label="turned side origin")
    position = tuple(float(v) for v in native.Position)
    if native.SetViewPosition(double_array([position[i] + target[i] - origin[i] for i in range(2)]), False) is not True:
        raise RuntimeError("threaded bracket end view would not move into projection")
    rebuild_drawing(adapter, label="align threaded bracket end view")
    origin = model_point_in_view(adapter, native, (0.0, 0.0, 0.0), label="aligned side origin")
    for point, unit, label in (((0.0, 0.0, 0.01), (0.0, -1.0), "+Z down"), ((0.0, 0.01, 0.0), (-1.0, 0.0), "+Y left")):
        projected = model_point_in_view(adapter, native, point, label=label)
        delta = (projected[0] - origin[0], projected[1] - origin[1])
        length = math.hypot(*delta)
        if length <= 0.0 or math.dist((delta[0] / length, delta[1] / length), unit) > 1e-6:
            raise RuntimeError(f"threaded bracket end view is not in projection: {label}")
    if math.dist(origin, target) > 0.00005:
        raise RuntimeError("threaded bracket end view axis is not aligned")


def _assert_dimension_callouts(adapter: Any, annotations: list[Any]) -> None:
    """Import the source-owned reasons verbatim; never write through the drawing."""
    for callouts in DIMENSION_CALLOUTS.values():
        for name, text in callouts.items():
            matches = [item for item in annotations if dimension_name(adapter, item) == name]
            if len(matches) != 1:
                raise RuntimeError(f"{name}: expected one imported structural callout")
            display = _early_bound(_early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}: imported structural callout differs from the model")


def _dimension_text_boxes(display: dict[str, Any], *, label: str) -> tuple[Box, ...]:
    """Decode individual native runs: a dimension line may pass BETWEEN rows."""
    boxes = []
    texts = display.get("texts", ())
    if not texts:
        raise RuntimeError(f"{label}: missing native text extent")
    for row in texts:
        values = (*row.get("pos", ()), row.get("h", 0.0), row.get("w", 0.0), row.get("ang", math.nan))
        if len(row.get("pos", ())) != 3 or not all(math.isfinite(value) for value in values) or row.get("h", 0.0) <= 0.0 or row.get("w", 0.0) <= 0.0 or row.get("ref") not in range(6) or not row.get("t"):
            raise RuntimeError(f"{label}: missing native text extent: {row}")
        # Supply each native run's measured width to the existing anchor/
        # rotation decoder. Never infer text width from the dimension line.
        box = estimate_text_box(
            row["t"], anchor=tuple(row["pos"][:2]), height=row["h"],
            reference=row["ref"], angle=row["ang"],
            advance_ratio=row["w"] / (max(map(len, row["t"].split("\n"))) * row["h"]),
        )
        if box is None:
            raise RuntimeError(f"{label}: native text has no decoded extent")
        boxes.append(box)
    return tuple(boxes)


def _dimension_layout_ink(adapter: Any, annotation: Any, *, label: str) -> CalloutInk:
    """Use native text runs, not the longest line (a horizontal size is not a leader)."""
    display, errors = annotation_display(adapter, annotation)
    if errors or not display.get("lines"):
        raise RuntimeError(f"{label}: missing native text/line layout: {errors}")
    if any(len(row) != 10 or not all(math.isfinite(value) for value in row) for row in display["lines"]):
        raise RuntimeError(f"{label}: invalid native dimension lines")
    box = union_boxes(_dimension_text_boxes(display, label=label))
    if box is None:
        raise RuntimeError(f"{label}: native text has no decoded extent")
    # These are native layout envelopes, not exported PDF glyph proof.
    lines = tuple(LeaderSegment(label, "dim", line.x0, line.y0, line.x1, line.y1) for line in _display_segments(display))
    return CalloutInk(label, (box.xmin, box.ymin, box.xmax, box.ymax), lines)


def _curate_tap_callout(adapter: Any, view: Any, callout: Any) -> int:
    """Keep the native tap/mate, omit its default printed class and duplicate name."""
    from win32com.client.dynamic import Dispatch as dynamic_dispatch  # noqa: PLC0415

    display = _early_bound(callout, "IDisplayDimension")
    definition = str(display.GetText(5) or "")
    if not all(token in definition for token in ("<hw-threaddesc>", "<hw-threadclass>", "<hw-thru>")):
        raise RuntimeError("through-tap callout lacks native thread description/class/extent")
    resolved = str(display.GetText(1) or "")
    if THREAD not in resolved:
        raise RuntimeError("through-tap callout has no resolved native thread size")
    # As in set_hole_callout_precision, resolve metadata against the returned
    # dispatch, not ICalloutVariable's DISPIDs on a concrete variable pointer.
    # The makepy constructor can retain that pointer after E_NOINTERFACE.
    classes = []
    for raw in display.GetHoleCalloutVariables() or ():
        metadata = dynamic_dispatch(raw._oleobj_)
        if str(metadata.VariableName) == "hw-threadclass":
            if int(metadata.Type) != 3:
                raise RuntimeError("through-tap callout lacks one native string thread-class variable")
            classes.append(raw)
    if len(classes) != 1:
        raise RuntimeError("through-tap callout lacks one native string thread-class variable")
    thread_class = _early_bound(classes[0], "ICalloutStringVariable")
    original_class = str(thread_class.String or "")
    if original_class.strip(" -") != "2B":
        raise RuntimeError(f"through-tap class is not the title-block default 2B: {original_class!r}")
    omit_title_block_thread_class(display, label="quarter-inch lever through tap")
    if str(thread_class.String or "") != original_class:
        raise RuntimeError("omitting printed thread class changed its native variable")
    if THREAD not in str(display.GetText(1) or "") or any("2B" in str(display.GetText(part) or "") for part in (1, 2, 3, 4)):
        raise RuntimeError("classless native tap lost its resolved thread size or still prints 2B")
    native = _early_bound(view, "IView")
    text = f"{THREAD} Tapped Hole"
    notes = [
        note for note in (_early_bound(raw, "INote") for raw in (native.GetNotes() or ()))
        if str(note.GetText() or "").strip() == text
    ]
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    for note in notes:
        draw.ClearSelection2(True)
        if not _early_bound(note.GetAnnotation(), "IAnnotation").Select2(False, 0):
            raise RuntimeError("could not select the redundant tap feature-name note")
        draw.EditDelete()  # Native void; the view's re-read proves deletion.
    draw.ClearSelection2(True)
    if notes:
        rebuild_drawing(adapter, label="remove redundant tap feature-name note")
    if any(str(_early_bound(raw, "INote").GetText() or "").strip() == text for raw in (native.GetNotes() or ())):
        raise RuntimeError("redundant tap feature-name note survived deletion")
    _telemetry.info(f"removed {len(notes)} redundant tap feature-name note(s); native thread/extent retained and native class unchanged")
    return len(notes)


def _set_hole_process(display: Any, *, mate: str, tapped: bool) -> None:
    """Keep every native hole variable, adding process words to its own row."""
    display = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    tokens = re.findall(r"<hw-[^>]+>", "\n".join(definitions.values()))
    drill_tokens = ("<hw-tapdrldia>", "<hw-thrutapdrldia>") if tapped else ("<hw-diam>",)
    if not display.IsHoleCallout() or sum(tokens.count(token) for token in drill_tokens) != 1 or "<hw-thru>" not in tokens:
        raise RuntimeError("hole process requires native diameter and through variables")
    if tapped != ("<hw-threaddesc>" in tokens):
        raise RuntimeError("hole process does not match its native thread definition")
    revised = {}
    drill_rows = tap_rows = 0
    for part, text in definitions.items():
        rows = []
        for row in text.splitlines():
            if "<hw-threaddesc>" in row:
                if not re.search(r"\bTAP\b", row):
                    row = "TAP " + row
                tap_rows += 1
            elif any(token in row for token in drill_tokens):
                if not re.search(r"\bDRILL\b", row):
                    row = "DRILL " + row
                drill_rows += 1
            rows.append(row)
        revised[part] = "\n".join(rows)
    if drill_rows != 1 or tap_rows != int(tapped):
        raise RuntimeError("hole process requires one native drill row and its optional tap row")
    # The native drill is CalloutAbove (7), the thread is Prefix (5).
    # Put mate/shape BELOW the prefix, never above the drill or in a suffix.
    revised[5] = "\n".join(text for text in (revised[5], mate) if text)
    if re.findall(r"<hw-[^>]+>", "\n".join(revised.values())) != tokens:
        raise RuntimeError("hole process changed native quantity/size/extent variables")
    for part, text in revised.items():
        if text != definitions[part]:
            display.SetText(part - 4, text)
    if {part: str(display.GetText(part) or "") for part in revised} != revised:
        raise RuntimeError("native hole process words did not persist")


def _exterior_nose_radius(adapter: Any, annotations: list[Any]) -> None:
    """The R5.50 leader stops at the nose arc, outside the tapped hole.

    Native, it ran on from the arc to the hole centre, where the through-tap
    leader also passed: the two leaders crossed there and the tap callout read
    as pointing at the nose profile (machinist review, 3/3 runs). Arrow
    outside with no solid leader, as draw_ch_fulcrum_keeper's crown radius.
    """
    matches = [item for item in annotations if dimension_name(adapter, item) == "NoseR"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one NoseR dimension, found {len(matches)}")
    display = _early_bound(_early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
    display.ArcExtensionLineOrOppositeSide = False
    display.ArrowSide = 1  # swDimArrowsOutside
    display.SolidLeader = False
    if (
        bool(display.Diametric)
        or bool(display.ArcExtensionLineOrOppositeSide)
        or int(display.ArrowSide) != 1
        or bool(display.SolidLeader)
    ):
        raise RuntimeError("NoseR kept its leader to the hole centre")


def _overall_reference(adapter: Any, side: Any, edges: Any) -> Any:
    """Parenthesized seat-to-nose extreme, not another manufacturing control."""
    seat = edges.exact_line_through((NECK_HALF_X, 0.0, SIDE_PLATE_Z[1]), label="overall mounting seat")
    nose = edges.circle_at((NECK_HALF_X, 0.0, 0.0), NOSE_R, axis=(1.0, 0.0, 0.0), label="overall nose arc")
    points = (seat.midpoint_mm, (NECK_HALF_X, 0.0, -NOSE_R))
    picks = [model_point_in_view(adapter, side, tuple(v / 1000.0 for v in point), label="overall physical endpoint") for point in points]
    entities = (seat.edge, nose.edge)
    display = _early_bound(add_edge_dimension(
        adapter, side, p0=picks[0], p1=picks[1], entities=entities,
        text_xy=OVERALL_REFERENCE_XY, orientation="vertical", label="OverallHeight",
    ), "IDisplayDimension")
    set_arc_endpoints_to_max(adapter, display, label="OverallHeight")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    native.Name = "OverallHeight"
    native.DrivenState = 1  # swDimensionDriven: derived from the two physical edges.
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    set_reference_dimension(adapter, annotation, label="OverallHeight")
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION["OverallHeight"], -1, -1, -1)
    display.CenterText = False
    if not annotation.SetPosition2(*OVERALL_REFERENCE_XY, 0.0):
        raise RuntimeError("overall reference text would not move")
    if (
        str(native.Name) != "OverallHeight" or int(native.DrivenState) != 1
        or int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION["OverallHeight"]
        or int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0
        or str(display.GetText(1)) != "(" or str(display.GetText(2)) != ")"
    ):
        raise RuntimeError("overall height is not an unbanded native reference")
    assert_dimension_measures(
        adapter, display, expected_mm=SIDE_PLATE_Z[1] + NOSE_R,
        entities=entities, label="OverallHeight",
    )
    return annotation


def _layout_linear_annotations(
    adapter: Any, front: Any, bottom: Any, annotations: list[Any], *, overall_reference: Any, tap_callout: Any,
) -> None:
    """Place reviewed text from native witnesses, then guard neighbours."""
    names = ("NeckThickness", "FlangeDepth", "MountingX0", "MountingX1", "MountingY0", "NoseR", "TapFromTip", "TapFromSide", "OverallHeight")
    # Keep the actual drawing-created reference instead of rediscovering it
    # through the imported-model dimension-name reader.
    by_name = {"OverallHeight": overall_reference}
    for name, annotation in by_name.items():
        display = _early_bound(_early_bound(annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
        if str(_early_bound(display.GetDimension2(0), "IDimension").Name) != name:
            raise RuntimeError(f"{name}: retained native dimension name changed")
    # The native through-tap leader bounds the radius text lane. Retain its
    # handle too: its generated dimension name is not a stable model contract.
    by_name["LeverTapCallout"] = tap_callout
    annotations = [*annotations, overall_reference, tap_callout]
    for name in names:
        if name in by_name:
            continue
        matches = [item for item in annotations if dimension_name(adapter, item) == name]
        if len(matches) != 1:
            raise RuntimeError(f"bracket layout requires exactly one {name}")
        by_name[name] = matches[0]

    def capture(stage: str, measured: list[tuple[str, Any, CalloutInk]]) -> None:
        records = {}
        for name, annotation, ink in measured:
            raw, errors = annotation_display(adapter, annotation)
            records[name] = {
                "text_box": ink.text,
                "segments": [(line.x0, line.y0, line.x1, line.y1) for line in ink.leader],
                "native_display": raw, "read_errors": errors,
            }
        evidence = json.dumps({"stage": stage, "dimensions": records}, sort_keys=True)
        _telemetry.info(f"bracket linear layout geometry: {evidence}", operation_stage=stage, auditJSON=evidence)

    rebuild_drawing(adapter, label="measure bracket linear callouts")
    initial = {name: _dimension_layout_ink(adapter, item, label=name) for name, item in by_name.items()}
    capture("before_text_modes", [(name, by_name[name], ink) for name, ink in initial.items()])
    placed_names = ("NeckThickness", "FlangeDepth", "MountingX0", "MountingX1", "MountingY0", "TapFromTip", "TapFromSide")
    offset_names = ("NeckThickness", "FlangeDepth", "MountingY0", "TapFromTip", "TapFromSide")
    for name in placed_names:
        display = _early_bound(_early_bound(by_name[name], "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
        display.CenterText = False
        if name in offset_names:
            display.OffsetText = True
    # OffsetText creates a freely movable leader while its dimension and
    # extension lines stay fixed (IDisplayDimension SDK). Rebuild that mode
    # change BEFORE measuring the lines that bound the new text lane.
    rebuild_drawing(adapter, label="settle bracket linear text modes")
    for name in placed_names:
        display = _early_bound(_early_bound(by_name[name], "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension")
        if display.CenterText is not False or (name in offset_names and display.OffsetText is not True):
            raise RuntimeError(f"{name}: native text placement mode did not persist")
    before = {name: _dimension_layout_ink(adapter, item, label=name) for name, item in by_name.items()}
    capture("settled_text_modes", [(name, by_name[name], ink) for name, ink in before.items()])

    def verticals(name: str) -> list[LeaderSegment]:
        lines = [line for line in before[name].leader if abs(line.x0 - line.x1) < 1e-7 and abs(line.y0 - line.y1) > 0.001]
        if not lines:
            raise RuntimeError(f"{name} has no native vertical witness/extension line")
        return lines

    left_foot = min(line.x0 for line in verticals("MountingX0"))
    last_hole = max(line.x0 for line in verticals("MountingX1"))
    front_outline = tuple(float(v) for v in _early_bound(front, "IView").GetOutline())
    # The builder dimensions FlangeDepth on the free -X end: its witnesses
    # leave the real foot top/bottom corners. Read the solid's projected
    # foot and upright, so the offset text sits in the open L above the
    # foot's free end without touching either outline.
    foot_corners = [
        model_point_in_view(adapter, front, (x / 1000.0, 0.0, z / 1000.0), label="front foot outline")
        for x in SIDE_PLATE_X for z in SIDE_PLATE_Z
    ]
    arm_corners = [
        model_point_in_view(adapter, front, (x / 1000.0, 0.0, z / 1000.0), label="front upright outline")
        for x in (-NECK_HALF_X, NECK_HALF_X) for z in (-NOSE_R, SIDE_PLATE_Z[1])
    ]
    foot_end = model_point_in_view(adapter, front, (SIDE_PLATE_X[0] / 1000.0, 0.0, SIDE_PLATE_Z[0] / 1000.0), label="free foot end")[0]
    front_solids = {
        name: (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))
        for name, points in (("front foot", foot_corners), ("front upright", arm_corners))
    }
    targets = {
        "NeckThickness": (max(line.x0 for line in verticals("NeckThickness")) + 0.004, front_outline[3] + 0.004),
        "FlangeDepth": (foot_end, max(max(line.y0, line.y1) for line in before["FlangeDepth"].leader) + 0.004),
        "MountingX0": (left_foot - 0.004 - (before["MountingX0"].text[2] - before["MountingX0"].text[0]), before["MountingX0"].text[1]),
        "MountingX1": (last_hole + 0.004, before["MountingX1"].text[1]),
        "MountingY0": (
            left_foot - 0.004 - (before["MountingY0"].text[2] - before["MountingY0"].text[0]),
            max(max(line.y0, line.y1) for line in before["MountingY0"].leader) + 0.0022,
        ),
        # R7's associative through-tap leader ran within 2 mm of the radius
        # reason row. Use that retained leader's measured top, not a PDF nudge.
        "NoseR": (
            before["NoseR"].text[0],
            max(max(line.y0, line.y1) for line in before["LeverTapCallout"].leader) + 0.004,
        ),
        # Its old below-value row crossed the outward arrow flank. Keep the
        # complete offset text left of its witnesses and above its native ink.
        "TapFromTip": (
            min(line.x0 for line in verticals("TapFromTip")) - 0.004 - (before["TapFromTip"].text[2] - before["TapFromTip"].text[0]),
            max(max(line.y0, line.y1) for line in before["TapFromTip"].leader) + 0.004,
        ),
        "TapFromSide": (
            max(line.x0 for line in verticals("TapFromSide")) + 0.004,
            max(max(line.y0, line.y1) for line in before["TapFromSide"].leader) + 0.0022,
        ),
    }
    for name, target in targets.items():
        annotation = by_name[name]
        for _attempt in range(3):
            ink = _dimension_layout_ink(adapter, annotation, label=name)
            delta = (target[0] - ink.text[0], target[1] - ink.text[1])
            if max(abs(v) for v in delta) < 0.00005:
                break
            move_annotation(adapter, annotation, *delta, label=name)
        ink = _dimension_layout_ink(adapter, annotation, label=name)
        if math.dist(ink.text[:2], target) > 0.00005:
            raise RuntimeError(f"{name}: native text placement did not settle")
    settled = [(item, _dimension_layout_ink(adapter, item, label=f"bracket dimension {index}")) for index, item in enumerate(annotations)]
    # Emit every final box/line/arrow before the first guard can refuse. R2
    # stopped at MountingY0 without preserving that dimension's final geometry.
    capture("placed", [
        (next((name for name, known in by_name.items() if known is annotation), ink.label), annotation, ink)
        for annotation, ink in settled
    ])
    region = sheet_region(adapter)
    for name in names:
        annotation = by_name[name]
        ink = next(value for item, value in settled if item is annotation)
        require_inside(name, ink.text, region)
        native_display, errors = annotation_display(adapter, annotation)
        if errors:
            raise RuntimeError(f"{name}: native text read failed: {errors}")
        # Below-value reasons enlarge the union, but whitespace between native
        # runs is not glyph ink. Guard each real run without exempting a line.
        for box in _dimension_text_boxes(native_display, label=name):
            inner = Box(box.xmin + 0.00015, box.ymin + 0.00015, box.xmax - 0.00015, box.ymax - 0.00015)
            if any(segment_box_overlap_length(Segment(line.x0, line.y0, line.x1, line.y1), inner) > 1e-7 for line in ink.leader):
                raise RuntimeError(f"{name}: own native line/arrow crosses its text")
        expanded = Box(ink.text[0] - 0.002, ink.text[1] - 0.002, ink.text[2] + 0.002, ink.text[3] + 0.002)
        for other, other_ink in settled:
            if other is annotation:
                continue
            require_clear(name, ink.text, {other_ink.label: other_ink.text})
            if any(segment_box_overlap_length(Segment(line.x0, line.y0, line.x1, line.y1), expanded) > 1e-7 for line in other_ink.leader):
                raise RuntimeError(f"{name}: neighbouring native line crowds its text")
        for line in ink.leader:
            require_inside(name, (min(line.x0, line.x1), min(line.y0, line.y1), max(line.x0, line.x1), max(line.y0, line.y1)), region)
        _telemetry.info(f"{name} settled native text={ink.text}")
    require_clear("NeckThickness", next(ink.text for item, ink in settled if item is by_name["NeckThickness"]), {"front silhouette": front_outline})
    require_clear("FlangeDepth", next(ink.text for item, ink in settled if item is by_name["FlangeDepth"]), front_solids)
    foot_points = [
        model_point_in_view(adapter, bottom, (x / 1000.0, y / 1000.0, SIDE_PLATE_Z[1] / 1000.0), label="mounting-face silhouette")
        for x in SIDE_PLATE_X for y in SIDE_PLATE_Y
    ]
    foot_box = (min(p[0] for p in foot_points), min(p[1] for p in foot_points), max(p[0] for p in foot_points), max(p[1] for p in foot_points))
    for name in ("MountingX0", "MountingX1", "MountingY0"):
        require_clear(name, next(ink.text for item, ink in settled if item is by_name[name]), {"mounting-face silhouette": foot_box})


def _add_mounting_callout(adapter: Any, bottom: Any, edge: Any) -> Any:
    # Native quantity/diameter/extent remain live on their own process row.
    display = add_native_hole_callout(
        adapter, bottom, edge=edge, callout_xy=(0.166, 0.054),
        label="two mounting clearance holes",
    )
    _set_hole_process(display, mate=MOUNTING_HOLE_PROCESS, tapped=False)
    rebuild_drawing(adapter, label="settle native mounting drill process")
    annotation = _early_bound(display, "IDisplayDimension").GetAnnotation()
    ink = _dimension_layout_ink(adapter, annotation, label="mounting-hole callout")
    template = DRAWING_TEMPLATES[SPEC.layout]
    keep_out = {"title block": (template.title_block_left_m, 0.0, template.width_m, template.title_block_top_m)}
    region = sheet_region(adapter)
    require_inside("mounting-hole callout", ink.text, region)
    require_clear("mounting-hole callout", ink.text, keep_out)
    for line in ink.leader:
        box = (min(line.x0, line.x1), min(line.y0, line.y1), max(line.x0, line.x1), max(line.y0, line.y1))
        require_inside("mounting-hole line/leader", box, region)
        require_clear("mounting-hole line/leader", box, keep_out)
    _telemetry.info(f"mounting-hole layout: text={ink.text}, title_block={keep_out['title block']}")
    return display


def _assert_foot_finish_text_clear(display: dict[str, Any]) -> None:
    """Refuse own native strokes/arrows through individual finish-text runs."""
    label = "foot locating seat finish"
    if not display.get("lines") or not display.get("arrows"):
        raise RuntimeError(f"{label}: missing native leader/arrow ink")
    if any(
        len(row) != 10 or not all(math.isfinite(value) for value in row)
        for row in display["lines"]
    ) or any(
        len(row) < 8 or not all(math.isfinite(value) for value in row)
        or math.hypot(row[3], row[4]) == 0.0 or min(row[6:8]) <= 0.0
        for row in display["arrows"]
    ):
        raise RuntimeError(f"{label}: invalid native leader/arrow ink")
    segments = _display_segments(display)
    # Match the existing linear-callout guard's run inset/intersection limit.
    # This is not a new clearance band and does not erase whitespace between runs.
    for box in _dimension_text_boxes(display, label=label):
        inner = Box(box.xmin + 0.00015, box.ymin + 0.00015, box.xmax - 0.00015, box.ymax - 0.00015)
        if any(segment_box_overlap_length(segment, inner) > 1e-7 for segment in segments):
            raise RuntimeError(f"{label}: own native line/arrow crosses its text")


def _add_foot_finish(adapter: Any, front: Any, annotations: list[Any]) -> None:
    """Attach the source-owned grade to the real SM-facing +Z seat edge."""
    candidates = []
    for item in scan_view_edges(front, label="bracket locating seat").lines:
        a, b = item.line
        if (
            max(abs(a[2] - SIDE_PLATE_Z[1]), abs(b[2] - SIDE_PLATE_Z[1])) < 1e-6
            and max(abs(a[1] - NOSE_R), abs(b[1] - NOSE_R)) < 1e-6
            and abs(a[0] - b[0]) > NECK_HALF_X
        ):
            candidates.append(item)
    if len(candidates) != 1:
        raise RuntimeError(f"foot locating seat requires one visible physical edge, found {len(candidates)}")
    edge = candidates[0]
    landing = model_point_in_view(
        adapter, front, tuple(value / 1000.0 for value in edge.midpoint_mm),
        label="foot locating seat",
    )
    symbol = add_surface_finish(
        adapter, front, edge_entity=edge.edge, leader_attach_xy=landing,
        symbol_xy=(landing[0] + 0.010, landing[1] - 0.008),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="foot locating seat finish", char_height=0.0025,
    )
    annotation = _early_bound(symbol, "ISFSymbol").GetAnnotation()
    display, errors = annotation_display(adapter, annotation)
    evidence = json.dumps({"native_display": display, "read_errors": errors}, sort_keys=True)
    _telemetry.info(f"foot locating seat finish native ink: {evidence}", auditJSON=evidence)
    if errors:
        raise RuntimeError(f"foot locating seat finish: native ink read failed: {errors}")
    _assert_foot_finish_text_clear(display)
    box = gdt_box(adapter, annotation, label="foot locating seat finish")
    require_inside("foot locating seat finish", box, sheet_region(adapter))
    require_clear("foot locating seat finish", box, {
        f"bracket dimension {index}": _dimension_layout_ink(adapter, item, label=f"bracket dimension {index}").text
        for index, item in enumerate(annotations)
    })


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    check("open threaded bracket source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(adapter.currentModel, ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity", "Isometric View Note"), required=("Number", "Material Specification", "Finish", "Quantity", "Isometric View Note"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing, {0: "Magnifying Bracket Manufacturing Drawing", 1: "Harmonic Analyzer hobby-machinist book drawing", 2: "Harmonic Analyzer Project", 3: "blued low-carbon-steel L bracket; quarter-inch through thread", 4: "Generated from the project-owned ASME B drawing standard"})
    front = place_view(adapter, str(SOURCE), "*Top", *FRONT_CENTER, scale=SHEET_SCALE)
    bottom = place_view(adapter, str(SOURCE), "*Front", *BOTTOM_CENTER, scale=SHEET_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, bottom, side, iso):
        set_hidden_lines_removed(adapter, view)
    _project_side_view(adapter, front, side)
    imported = {}
    for view, keep, label in (
        (front, FRONT_KEEP, "front"),
        (bottom, BOTTOM_KEEP, "mounting face"),
        (side, SIDE_KEEP, "thread-axis end"),
    ):
        annotations = curate_view_dimensions(adapter, view, keep=keep, view_label=label, dimensions_by_feature=DRAWING_DIMENSIONS)
        imported[label] = annotations
    mounting_dimensions = curate_hidden_dimensions(adapter, bottom, keep=MOUNTING_KEEP, view_label="plate-tap mounting coordinates", dimensions_by_feature={"MountingCoordinates": DRAWING_DIMENSIONS["MountingCoordinates"]})
    annotations = curate_hidden_dimensions(adapter, side, keep=TAP_KEEP, view_label="ordinary thread locations", dimensions_by_feature={"TapCoordinates": DRAWING_DIMENSIONS["TapCoordinates"]})
    _assert_dimension_callouts(adapter, [
        *imported["front"], *imported["thread-axis end"], *mounting_dimensions, *annotations,
    ])
    rim = _mounting_rims(bottom)[1]
    mounting_callout = _add_mounting_callout(adapter, bottom, rim.edge)
    edges = scan_view_edges(side, label="bracket through thread")
    overall_reference = _overall_reference(adapter, side, edges)
    rim = edges.circle_at((NECK_HALF_X - MOUTH_CHAMFER, 0.0, 0.0), TAP_DRILL_DIA / 2.0, axis=(1.0, 0.0, 0.0), label="near through-tap inner rim")
    tap = add_native_hole_callout(adapter, side, edge=rim.edge, callout_xy=(0.345, 0.236), label="quarter-inch lever through tap")
    _curate_tap_callout(adapter, side, tap)
    _set_hole_process(tap, mate=TAP_PROCESS, tapped=True)
    tap_annotation = _early_bound(tap, "IDisplayDimension").GetAnnotation()
    # One arrow on the hole's own rim, no line through the centre, and an
    # R5.50 leader that stops at the nose arc: the two never meet.
    set_near_side_diameter(tap_annotation, "quarter-inch lever through tap")
    _exterior_nose_radius(adapter, imported["thread-axis end"])
    rebuild_drawing(adapter, label="tap near-side and nose-radius exterior leaders")
    ratio = tuple(float(value) for value in _early_bound(iso, "IView").ScaleRatio)
    if len(ratio) != 2 or any(not math.isfinite(value) or value <= 0.0 for value in ratio):
        raise RuntimeError("isometric view has no valid native scale ratio")
    caption = f"ISOMETRIC VIEW SCALE {ratio[0]:g}:{ratio[1]:g}"
    if caption != properties["Isometric View Note"]:
        raise RuntimeError("isometric scale caption does not match the native view")
    iso_outline = tuple(float(value) for value in _early_bound(iso, "IView").GetOutline())
    if len(iso_outline) != 4 or not all(math.isfinite(value) for value in iso_outline):
        raise RuntimeError("isometric view has no finite native outline")
    note = _early_bound(add_property_linked_note(adapter, "Isometric View Note", 0.320, iso_outline[1] - 0.004), "INote")
    rebuild_drawing(adapter, label="settle native isometric scale caption")
    if str(note.GetText()) != caption:
        raise RuntimeError("isometric scale caption did not resolve to the actual view ratio")
    extent = tuple(float(value) for value in note.GetExtent())
    if len(extent) != 6 or not all(math.isfinite(value) for value in extent) or extent[0] >= extent[3] or extent[1] >= extent[4]:
        raise RuntimeError("isometric scale caption has no finite native extent")
    box = (extent[0], extent[1], extent[3], extent[4])
    require_inside("isometric scale caption", box, sheet_region(adapter))
    template = DRAWING_TEMPLATES[SPEC.layout]
    require_clear("isometric scale caption", box, {
        "isometric view": iso_outline,
        "title block": (template.title_block_left_m, 0.0, template.width_m, template.title_block_top_m),
    })
    linear_annotations = [
        *imported["front"], *imported["mounting face"], *imported["thread-axis end"],
        *mounting_dimensions, *annotations,
        _early_bound(mounting_callout, "IDisplayDimension").GetAnnotation(),
    ]
    _layout_linear_annotations(
        adapter, front, bottom, linear_annotations,
        overall_reference=overall_reference, tap_callout=tap_annotation,
    )
    _add_foot_finish(adapter, front, [*linear_annotations, overall_reference, tap_annotation])
    return await finalize_drawing(adapter, OUTPUTS, pdf_title="Magnifying Bracket Manufacturing Drawing", scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
