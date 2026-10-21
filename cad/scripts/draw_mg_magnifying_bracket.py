r"""Native manufacturing sheet for the simple threaded L bracket.

All sizes/locations import from the saved SLDPRT, including the ordinary
side/tip hole-location chain and the independent internal-root MAX envelope.
Each dimension's callout is applied only after its owning view imports it;
the bore's axial/radial mouth chamfer belongs in its true-profile section.
The associative tap callout owns its thread description and extent; its class
is owned by the title block. The duplicate Wizard name leaves the wall's lane.
No press-fit, collar, finish-land or GD&T-frame convention remains.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

from _check import check
from _com import _early_bound
from _drawing_annotation_extent import CalloutInk, move_annotation, require_clear, require_inside, require_leader_clear, sheet_region
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, rebuild_drawing, stamp_drawing_summary
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_dimension_callouts
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_layout_audit import annotation_display
from _drawing_layout_check import DrawableRegion, LeaderSegment
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _drawing_sections import create_section_view
from _hole_callout_thread_class import omit_title_block_thread_class
from _layout_audit import _collinear_overlap, _display_segments, _segment_crossing
from _layout_geometry import Segment, estimate_text_box, union_boxes
from _paths import CAD_ROOT
from _session import run_build
from _section_axis import position_section_caption
import _telemetry
from magnifying_bracket_joint_layout import BRACKET_HOLE_POINTS, CLEARANCE_DIA, SIDE_PLATE_Z
from mg_lever_thread_joint import MOUTH_CHAMFER, NECK_HALF_X, NOSE_R, TAP_DRILL_DIA, THREAD
from mg_magnifying_bracket_spec import DRAWING_DIMENSIONS, FLANGE_DEPTH_CALLOUT, FOOT_CORNER_CALLOUT, MOUNTING_HOLE_PROCESS, MOUTH_CALLOUT, NECK_THICKNESS_CALLOUT, ROOT_CALLOUT, TAP_PROCESS, THREAD_ENVELOPE_CALLOUT, WALL_CALLOUT

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
# Creation seed only: cut-only sections retain the whole-model outline on R8.
# The final location is measured after rotation, not inferred from this point.
MOUTH_SECTION_SEED = (0.228, 0.080)
MOUTH_SECTION_SCALE = (3, 1)
FRONT_KEEP = {"NeckThickness": (0.118, 0.185), "FlangeWidth": (0.079, 0.098), "FlangeDepth": (0.140, 0.123), "RootR": (0.045, 0.145)}
BOTTOM_KEEP = {"FlangeHeight": (0.132, 0.080), "FootCornerR": (0.040, 0.100)}
SIDE_KEEP = {"NoseR": (0.266, 0.229), "SeatToAxis": (0.196, 0.165)}
MOUTH_KEEP = {"MouthChamfer": (0.330, 0.190)}
MOUNTING_KEEP = {"MountingX0": (0.045, 0.056), "MountingX1": (0.060, 0.046), "MountingY0": (0.030, 0.080)}
TAP_KEEP = {"TapFromTip": (0.206, 0.226), "TapFromSide": (0.240, 0.240), "ThreadRootEnvelope": (0.292, 0.214)}
WALL_TEXT_XY = (0.140, 0.250)
# Whitespace only; keep the native radius/MAX and all controlled corners.
ROOT_PRINT_CALLOUT = ROOT_CALLOUT.replace(" INSIDE ", "\nINSIDE ")
MOUTH_PRINT_CALLOUT = MOUTH_CALLOUT.replace(", ", ",\n", 1)


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


def _mouth_section(adapter: Any, side: Any, iso: Any) -> Any:
    """Cut Z=0 through the X-axis tap; an end view collapses its chamfer leg."""
    ends = [
        model_point_in_view(adapter, side, (0.0, sign * (NOSE_R + 3.0) / 1000.0, 0.0), label="mouth section cutting line")
        for sign in (1.0, -1.0)
    ]
    section = _early_bound(create_section_view(
        adapter, side, line_start=ends[0], line_end=ends[1],
        view_xy=MOUTH_SECTION_SEED, section_label="A", scale=MOUTH_SECTION_SCALE,
        label="thread-mouth true-profile section",
    ), "IView")
    cut = _early_bound(section.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    set_hidden_lines_removed(adapter, section)
    rebuild_drawing(adapter, label="thread-mouth section cut faces only")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("thread-mouth section retained geometry beyond the cutting plane")
    # R8's 3:1 outline was 49.276 x 158.926 mm, even in cut-only mode.
    # Its mouth was near the bottom of that outline, not at Position. Turn
    # the measured outline-to-mouth vector right, leaving the cut itself and
    # its scale intact. This fits the complete native outline above the iso.
    outline = tuple(float(value) for value in section.GetOutline())
    if len(outline) != 4 or not all(math.isfinite(value) for value in outline):
        raise RuntimeError("thread-mouth section has invalid native outline")
    origin = model_point_in_view(adapter, section, (0.0, 0.0, 0.0), label="mouth before rotation")
    offset = tuple(origin[i] - (outline[i] + outline[i + 2]) / 2.0 for i in range(2))
    if math.hypot(*offset) < 0.001:
        raise RuntimeError("thread-mouth section lost its measured whole-model/profile offset")
    section.Angle = float(section.Angle) - math.atan2(offset[1], offset[0])
    rebuild_drawing(adapter, label="orient thread-mouth profile into free sheet lane")
    outline = tuple(float(value) for value in section.GetOutline())
    position = tuple(float(value) for value in section.Position)
    region = sheet_region(adapter)
    iso_outline = tuple(float(value) for value in _early_bound(iso, "IView").GetOutline())
    # R8: iso top 154.0135; root-envelope text starts above 209 mm.
    # Reserve 3 mm above the ACTUAL iso and at least 2 mm below that text.
    if len(outline) != 4 or len(position) != 2 or len(iso_outline) != 4 or not all(math.isfinite(value) for value in (*outline, *position, *iso_outline)):
        raise RuntimeError("thread-mouth section has invalid placement readback")
    lane = DrawableRegion(0.250, iso_outline[3] + 0.003, region.xmax - 0.004, 0.207)
    width, height = outline[2] - outline[0], outline[3] - outline[1]
    if not (0.0 < width <= lane.xmax - lane.xmin - 0.0004 and 0.0 < height <= lane.ymax - lane.ymin - 0.0004):
        raise RuntimeError(f"thread-mouth native outline does not fit above isometric: {outline}, lane={lane}")
    delta = (lane.xmax - 0.0002 - outline[2], lane.ymin + 0.0002 - outline[1])
    if section.SetViewPosition(double_array([position[i] + delta[i] for i in range(2)]), False) is not True:
        raise RuntimeError("thread-mouth section refused its measured placement")
    rebuild_drawing(adapter, label="place complete thread-mouth native extent")
    placed = tuple(float(value) for value in section.GetOutline())
    expected_outline = tuple(outline[i] + delta[i % 2] for i in range(4))
    if len(placed) != 4 or any(not math.isfinite(value) for value in placed) or max(abs(a - b) for a, b in zip(placed, expected_outline)) > 0.00005:
        raise RuntimeError(f"thread-mouth section placement/alignment did not persist: {placed}, expected={expected_outline}")
    require_inside("complete thread-mouth outline", placed, lane)
    require_inside("complete thread-mouth outline", placed, region)
    require_clear("complete thread-mouth outline", placed, {"isometric": iso_outline})
    origin = model_point_in_view(adapter, section, (0.0, 0.0, 0.0), label="mouth section origin")
    axes = [
        model_point_in_view(adapter, section, point, label="mouth section profile axis")
        for point in ((0.01, 0.0, 0.0), (0.0, 0.01, 0.0))
    ]
    vectors = [tuple(point[i] - origin[i] for i in range(2)) for point in axes]
    expected = 0.01 * MOUTH_SECTION_SCALE[0] / MOUTH_SECTION_SCALE[1]
    if any(abs(math.hypot(*vector) - expected) > 1e-7 for vector in vectors) or abs(sum(a * b for a, b in zip(*vectors))) > 1e-9:
        raise RuntimeError("thread-mouth section does not show both chamfer legs in true profile")
    if abs(vectors[0][1]) > 1e-7 or abs(vectors[1][0]) > 1e-7:
        raise RuntimeError("thread-mouth section axial/radial directions are not horizontal/vertical")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("thread-mouth section lost cut-only display after placement")
    _telemetry.info(f"thread-mouth layout: before={outline}, after={placed}, lane={lane}, origin={origin}, profile_axes={vectors}")
    return section


def _mouth_profile_box(adapter: Any, section: Any) -> tuple[float, float, float, float]:
    """Project the complete Z=0 neck envelope, not the uncut foot's outline."""
    points = [
        model_point_in_view(adapter, section, (x / 1000.0, y / 1000.0, 0.0), label="mouth cut-profile envelope")
        for x in (-NECK_HALF_X, NECK_HALF_X) for y in (-NOSE_R, NOSE_R)
    ]
    if any(len(point) != 2 or not all(math.isfinite(value) for value in point) for point in points):
        raise RuntimeError("thread-mouth cut profile has invalid native projection")
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


def _dimension_layout_ink(adapter: Any, annotation: Any, *, label: str) -> CalloutInk:
    """Use native text runs, not the longest line (a horizontal size is not a leader)."""
    display, errors = annotation_display(adapter, annotation)
    texts = display.get("texts", ())
    if errors or not texts or not display.get("lines"):
        raise RuntimeError(f"{label}: missing native text/line layout: {errors}")
    if any(len(row) != 10 or not all(math.isfinite(value) for value in row) for row in display["lines"]):
        raise RuntimeError(f"{label}: invalid native dimension lines")
    boxes = []
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
    box = union_boxes(boxes)
    if box is None:
        raise RuntimeError(f"{label}: native text has no decoded extent")
    # These are native layout envelopes, not exported PDF glyph proof.
    lines = tuple(LeaderSegment(label, "dim", line.x0, line.y0, line.x1, line.y1) for line in _display_segments(display))
    return CalloutInk(label, (box.xmin, box.ymin, box.xmax, box.ymax), lines)


def _layout_mouth_annotations(adapter: Any, section: Any, iso: Any, annotations: list[Any]) -> None:
    """Seat the unchanged native dimension and linked caption beside the cut."""
    if len(annotations) != 1 or dimension_name(adapter, annotations[0]) != "MouthChamfer":
        raise RuntimeError("thread-mouth layout requires its one imported MouthChamfer")
    region = sheet_region(adapter)
    iso_outline = tuple(float(value) for value in _early_bound(iso, "IView").GetOutline())
    if len(iso_outline) != 4 or not all(math.isfinite(value) for value in iso_outline):
        raise RuntimeError("thread-mouth layout has invalid isometric outline")
    lane = DrawableRegion(0.250, iso_outline[3] + 0.003, region.xmax - 0.004, 0.207)
    profile = _mouth_profile_box(adapter, section)
    annotation = annotations[0]
    rebuild_drawing(adapter, label="measure complete thread-mouth callout")
    ink = _dimension_layout_ink(adapter, annotation, label="both mouth legs/ends")
    # The complete text block sits left of both real mouth ends; moving the
    # dimension leaves its model attachments, tolerance and qualifier intact.
    move_annotation(adapter, annotation, profile[0] - 0.006 - ink.text[2], profile[3] - ink.text[3], label="both mouth legs/ends")
    ink = _dimension_layout_ink(adapter, annotation, label="both mouth legs/ends")
    if math.dist((ink.text[2], ink.text[3]), (profile[0] - 0.006, profile[3])) > 0.00005:
        raise RuntimeError("thread-mouth callout placement did not persist")
    notes = [
        note for note in (_early_bound(raw, "INote") for raw in (_early_bound(section, "IView").GetNotes() or ()))
        if "<VLLABEL>" in str(note.PropertyLinkedText or "")
    ]
    if len(notes) != 1:
        raise RuntimeError("thread-mouth layout requires one native linked section caption")
    note = notes[0]
    extent = tuple(float(value) for value in note.GetExtent())
    if len(extent) != 6 or not all(math.isfinite(value) for value in extent) or extent[0] >= extent[3] or extent[1] >= extent[4]:
        raise RuntimeError("thread-mouth caption has invalid native extent")
    position = tuple(float(value) for value in _early_bound(note.GetAnnotation(), "IAnnotation").GetPosition())
    caption_center_x = min(
        (ink.text[0] + ink.text[2]) / 2.0,
        profile[0] - 0.004 - (extent[3] - extent[0]) / 2.0,
    )
    target = (
        position[0] + caption_center_x - (extent[0] + extent[3]) / 2.0,
        position[1] + ink.text[1] - 0.004 - extent[4],
    )
    position_section_caption(adapter, section, target, label="thread mouth A-A")
    extent = tuple(float(value) for value in note.GetExtent())
    if len(extent) != 6 or not all(math.isfinite(value) for value in extent) or extent[0] >= extent[3] or extent[1] >= extent[4]:
        raise RuntimeError("thread-mouth caption lost its native extent")
    caption = (extent[0], extent[1], extent[3], extent[4])
    outline = tuple(float(value) for value in _early_bound(section, "IView").GetOutline())
    if len(outline) != 4 or not all(math.isfinite(value) for value in outline) or outline[0] >= outline[2] or outline[1] >= outline[3]:
        raise RuntimeError("thread-mouth layout lost its final native outline")
    require_inside("final complete thread-mouth outline", outline, lane)
    require_inside("final complete thread-mouth outline", outline, region)
    require_clear("final complete thread-mouth outline", outline, {"isometric": iso_outline})
    for label, box in (("mouth profile", profile), ("mouth callout", ink.text), ("mouth caption", caption)):
        require_inside(label, box, lane)
        require_inside(label, box, region)
        require_clear(label, box, {"isometric": iso_outline})
    require_clear("mouth callout", ink.text, {"profile": profile, "caption": caption})
    require_clear("mouth caption", caption, {"profile": profile})
    # R8 also retained the two uncut-foot centre marks in this section.
    # Keep them: screen position alone does not prove removable attachments.
    # The wrapped qualifier sits right of their arms; the caption sits below.
    mark_lines = {}
    mark_segments = []
    for index, mark in enumerate(_early_bound(section, "IView").GetAnnotationsByType(13) or ()):
        display, errors = annotation_display(adapter, mark)
        lines = display.get("lines", ())
        if errors or not lines or any(len(row) != 10 or not all(math.isfinite(value) for value in row) for row in lines):
            raise RuntimeError(f"thread-mouth centre mark {index} has unreadable native ink: {errors}")
        for line_index, line in enumerate(_display_segments(display)):
            mark_lines[f"section centre mark {index}/{line_index}"] = (min(line.x0, line.x1), min(line.y0, line.y1), max(line.x0, line.x1), max(line.y0, line.y1))
            mark_segments.append((f"section centre mark {index}/{line_index}", line))
    require_clear("mouth callout", ink.text, mark_lines)
    require_clear("mouth caption", caption, mark_lines)
    # Text clearance accepts zero-area line bounds; box-interior crossing
    # does not. Keep the actual segments for dimension-line/mark crossings.
    for line in ink.leader:
        segment = Segment(line.x0, line.y0, line.x1, line.y1)
        for label, mark_segment in mark_segments:
            if _segment_crossing(segment, mark_segment) is not None or _collinear_overlap(segment, mark_segment, tol=0.0) is not None:
                raise RuntimeError(f"thread-mouth dimension line intersects {label}")
    require_leader_clear(ink, {"caption": caption, "isometric": iso_outline})
    for line in ink.leader:
        require_inside("mouth dimension line/witness", (min(line.x0, line.x1), min(line.y0, line.y1), max(line.x0, line.x1), max(line.y0, line.y1)), lane)
    _telemetry.info(f"thread-mouth annotation layout: profile={profile}, text={ink.text}, caption={caption}")


def _require_root_callout_inside(adapter: Any, front: Any, annotations: list[Any]) -> None:
    """The wrapped native radius stays inside the border and left of the neck."""
    roots = [annotation for annotation in annotations if dimension_name(adapter, annotation) == "RootR"]
    if len(roots) != 1:
        raise RuntimeError("inside-corner layout requires one native RootR")
    rebuild_drawing(adapter, label="measure wrapped inside-corner callout")
    ink = _dimension_layout_ink(adapter, roots[0], label="all neck/foot inside corners")
    region = sheet_region(adapter)
    require_inside("inside-corner callout", ink.text, region)
    neck_left = min(
        model_point_in_view(adapter, front, (x / 1000.0, 0.0, 0.0), label="inside-corner neck clearance")[0]
        for x in (-NECK_HALF_X, NECK_HALF_X)
    )
    if ink.text[2] + 0.003 > neck_left:
        raise RuntimeError("inside-corner callout text crosses the neck")
    for line in ink.leader:
        require_inside("inside-corner leader", (min(line.x0, line.x1), min(line.y0, line.y1), max(line.x0, line.x1), max(line.y0, line.y1)), region)


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


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    check("open threaded bracket source", await adapter.open_model(str(SOURCE)))
    read_required_properties(adapter.currentModel, ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity", "Isometric View Note"), required=("Number", "Material Specification", "Finish", "Quantity", "Isometric View Note"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing, {0: "Magnifying Bracket Manufacturing Drawing", 1: "Harmonic Analyzer hobby-machinist book drawing", 2: "Harmonic Analyzer Project", 3: "blued 1018 simple L bracket; quarter-inch through thread", 4: "Generated from the project-owned ASME B drawing standard"})
    front = place_view(adapter, str(SOURCE), "*Top", *FRONT_CENTER, scale=SHEET_SCALE)
    bottom = place_view(adapter, str(SOURCE), "*Front", *BOTTOM_CENTER, scale=SHEET_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, bottom, side, iso):
        set_hidden_lines_removed(adapter, view)
    _project_side_view(adapter, front, side)
    mouth = _mouth_section(adapter, side, iso)
    imported = {}
    for view, keep, label, callouts in (
        (front, FRONT_KEEP, "front", {"NeckThickness": NECK_THICKNESS_CALLOUT, "FlangeDepth": FLANGE_DEPTH_CALLOUT, "RootR": ROOT_PRINT_CALLOUT}),
        (bottom, BOTTOM_KEEP, "mounting face", {"FootCornerR": FOOT_CORNER_CALLOUT}),
        (side, SIDE_KEEP, "thread-axis end", {}),
        (mouth, MOUTH_KEEP, "thread-mouth section", {"MouthChamfer": MOUTH_PRINT_CALLOUT}),
    ):
        annotations = curate_view_dimensions(adapter, view, keep=keep, view_label=label, dimensions_by_feature=DRAWING_DIMENSIONS)
        set_dimension_callouts(adapter, annotations, callouts)
        imported[label] = annotations
    curate_hidden_dimensions(adapter, bottom, keep=MOUNTING_KEEP, view_label="unchanged mounting coordinates", dimensions_by_feature={"MountingCoordinates": DRAWING_DIMENSIONS["MountingCoordinates"]})
    annotations = curate_hidden_dimensions(adapter, side, keep=TAP_KEEP, view_label="ordinary thread locations and root limit", dimensions_by_feature={feature: DRAWING_DIMENSIONS[feature] for feature in ("TapCoordinates", "ThreadEnvelope")})
    set_dimension_callouts(adapter, annotations, {"ThreadRootEnvelope": THREAD_ENVELOPE_CALLOUT})
    rim = _mounting_rims(bottom)[1]
    add_native_hole_callout(adapter, bottom, edge=rim.edge, callout_xy=(0.166, 0.054), label="two mounting clearance holes", process=MOUNTING_HOLE_PROCESS)
    edges = scan_view_edges(side, label="bracket through thread")
    rim = edges.circle_at((NECK_HALF_X - MOUTH_CHAMFER, 0.0, 0.0), TAP_DRILL_DIA / 2.0, axis=(1.0, 0.0, 0.0), label="near through-tap inner rim")
    tap = add_native_hole_callout(adapter, side, edge=rim.edge, callout_xy=(0.345, 0.236), label="quarter-inch lever through tap", process=TAP_PROCESS)
    _curate_tap_callout(adapter, side, tap)
    landing = model_point_in_view(adapter, side, (NECK_HALF_X / 1000.0, 0.0, -4.5e-3), label="minimum thread-mouth wall")
    add_leader_note(adapter, WALL_CALLOUT, text_xy=WALL_TEXT_XY, attach_xy=landing, view=side, label="honest manufactured minimum wall")
    add_property_linked_note(adapter, "Isometric View Note", 0.320, 0.092)
    _require_root_callout_inside(adapter, front, imported["front"])
    _layout_mouth_annotations(adapter, mouth, iso, imported["thread-mouth section"])
    return await finalize_drawing(adapter, OUTPUTS, pdf_title="Magnifying Bracket Manufacturing Drawing", scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
