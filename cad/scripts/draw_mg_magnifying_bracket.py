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
from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _com import _early_bound
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, rebuild_drawing, stamp_drawing_summary
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_dimension_callouts
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_leader_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _drawing_sections import create_section_view
from _hole_callout_thread_class import omit_title_block_thread_class
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
MOUTH_SECTION_CENTER = (0.228, 0.080)
MOUTH_SECTION_SCALE = (3, 1)
FRONT_KEEP = {"NeckThickness": (0.118, 0.185), "FlangeWidth": (0.079, 0.098), "FlangeDepth": (0.140, 0.123), "RootR": (0.045, 0.145)}
BOTTOM_KEEP = {"FlangeHeight": (0.132, 0.080), "FootCornerR": (0.040, 0.100)}
SIDE_KEEP = {"NoseR": (0.266, 0.229), "SeatToAxis": (0.196, 0.165)}
MOUTH_KEEP = {"MouthChamfer": (0.290, 0.095)}
MOUNTING_KEEP = {"MountingX0": (0.045, 0.056), "MountingX1": (0.060, 0.046), "MountingY0": (0.030, 0.080)}
TAP_KEEP = {"TapFromTip": (0.206, 0.226), "TapFromSide": (0.240, 0.240), "ThreadRootEnvelope": (0.292, 0.214)}
WALL_TEXT_XY = (0.140, 0.250)


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


def _mouth_section(adapter: Any, side: Any) -> Any:
    """Cut Z=0 through the X-axis tap; an end view collapses its chamfer leg."""
    ends = [
        model_point_in_view(adapter, side, (0.0, sign * (NOSE_R + 3.0) / 1000.0, 0.0), label="mouth section cutting line")
        for sign in (1.0, -1.0)
    ]
    section = _early_bound(create_section_view(
        adapter, side, line_start=ends[0], line_end=ends[1],
        view_xy=MOUTH_SECTION_CENTER, section_label="A", scale=MOUTH_SECTION_SCALE,
        label="thread-mouth true-profile section",
    ), "IView")
    cut = _early_bound(section.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    set_hidden_lines_removed(adapter, section)
    rebuild_drawing(adapter, label="thread-mouth section cut faces only")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("thread-mouth section retained geometry beyond the cutting plane")
    origin = model_point_in_view(adapter, section, (0.0, 0.0, 0.0), label="mouth section origin")
    axes = [
        model_point_in_view(adapter, section, point, label="mouth section profile axis")
        for point in ((0.01, 0.0, 0.0), (0.0, 0.01, 0.0))
    ]
    vectors = [tuple(point[i] - origin[i] for i in range(2)) for point in axes]
    expected = 0.01 * MOUTH_SECTION_SCALE[0] / MOUTH_SECTION_SCALE[1]
    if any(abs(math.hypot(*vector) - expected) > 1e-7 for vector in vectors) or abs(sum(a * b for a, b in zip(*vectors))) > 1e-9:
        raise RuntimeError("thread-mouth section does not show both chamfer legs in true profile")
    position_section_caption(adapter, section, (0.209, 0.048), label="thread mouth A-A")
    return section


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
    mouth = _mouth_section(adapter, side)
    for view, keep, label, callouts in (
        (front, FRONT_KEEP, "front", {"NeckThickness": NECK_THICKNESS_CALLOUT, "FlangeDepth": FLANGE_DEPTH_CALLOUT, "RootR": ROOT_CALLOUT}),
        (bottom, BOTTOM_KEEP, "mounting face", {"FootCornerR": FOOT_CORNER_CALLOUT}),
        (side, SIDE_KEEP, "thread-axis end", {}),
        (mouth, MOUTH_KEEP, "thread-mouth section", {"MouthChamfer": MOUTH_CALLOUT}),
    ):
        annotations = curate_view_dimensions(adapter, view, keep=keep, view_label=label, dimensions_by_feature=DRAWING_DIMENSIONS)
        set_dimension_callouts(adapter, annotations, callouts)
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
    return await finalize_drawing(adapter, OUTPUTS, pdf_title="Magnifying Bracket Manufacturing Drawing", scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
