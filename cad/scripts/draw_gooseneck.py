r"""Create the curated machinist drawing for the gooseneck counter-spring post.

The SLDPRT remains authoritative. Sheet 1 defines the formed tube: a 1:3
elevation, a 2:1 cut-surface section B-B across the post for the tube wall,
and the standard isometric. Sheet 2 is the arm-end fabrication: a small plan
view carries cutting line A-A along the arm axis in the plane of the bend, the
4:1 section exposes the separate brazed plug and slotted adjustment screw
(both Front-plane revolves, so their diameters import as side-view sizes), and
detail C enlarges the screw slot. Every displayed size is imported from the
model; every placement is keyed to projected model points, so a mirrored
section cannot strand a dimension on the wrong side.

Run with SolidWorks open::

    uv run python cad\scripts\draw_gooseneck.py gooseneck
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    create_blank_drawing_sheets,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view, view_name

from gooseneck_geom import (
    ARM_END_X,
    ARM_Y,
    BEND_R,
    PLUG_T,
    SCREW_HEAD_DIA,
    SCREW_HEAD_T,
    SCREW_SLOT_DEPTH,
    SCREW_THREAD_MAJOR_DIA,
    SPRING_SCREW_CLAMPED_GAP_MM,
    SPRING_SCREW_UNDERHEAD_LENGTH_MM,
    TUBE_DIA,
    WALL_T,
)
from gooseneck_spec import (
    DRAWING_PRECISION_BY_NAME,
    ELEVATION_DIMENSIONS,
    JOINT_DIMENSIONS,
    PLUG_FIT_CALLOUT,
    POST_SECTION_DIMENSIONS,
    SCREW_CALLOUT,
    SLOT_DETAIL_DIMENSIONS,
    TAP_CALLOUT,
)

SPEC = DRAWINGS_BY_NAME["gooseneck"]
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

SHEET_SCALE = (1.0, 3.0)
SHEET_NAMES = ("FORM + POST", "ARM-END FABRICATION")

# Model stations (mm, part frame) the placements key on.
TUBE_R = TUBE_DIA / 2.0
HEAD_X = ARM_END_X - SPRING_SCREW_CLAMPED_GAP_MM
SCREW_TIP_X = HEAD_X - SCREW_HEAD_T
SHANK_END_X = HEAD_X + SPRING_SCREW_UNDERHEAD_LENGTH_MM
PLUG_END_X = ARM_END_X + PLUG_T
POST_CUT_Y = 20.0  # above the Top-plane LegProfile sketch, below the bend
JOINT_CUT_END_X = SHANK_END_X + 8.0  # past the screw tip, still in the arm

# Sheet 1 (sheet metres). The 1:3 elevation stays left; the post section and
# its two diameters sit between it and the isometric, all above the title
# block (x > 218 mm is title block below y = 65 mm).
FRONT_CENTER = (0.095, 0.145)
POST_SECTION_CENTER = (0.175, 0.185)
POST_SECTION_SCALE = (2, 1)
ISO_CENTER = (0.330, 0.170)
ISO_SCALE = (1, 3)
ELEVATION_NOTE_XY = (0.058, 0.048)
ISO_NOTE_XY = (0.290, 0.085)
POST_LABEL_BELOW_MM = 30.0

# Sheet 2. The plan parent is only the carrier of cutting line A-A.
PLAN_CENTER = (0.085, 0.240)
PLAN_SCALE = (1, 2)
JOINT_CENTER = (0.165, 0.140)
JOINT_SCALE = (4, 1)
SLOT_DETAIL_CENTER = (0.340, 0.185)
SLOT_DETAIL_SCALE = (12, 1)
SLOT_FENCE_RADIUS_MM = 1.6
NOTES_XY = (0.250, 0.110)
LABEL_BELOW_MM = 12.0


def _sheet_point(
    adapter: Any, view: Any, x: float, y: float, z: float = 0.0, *, label: str
) -> tuple[float, float]:
    """Project a part point (mm) into sheet metres."""
    return model_point_in_view(
        adapter, view, (x / 1000.0, y / 1000.0, z / 1000.0), label=label
    )


def _offset(point: tuple[float, float], dx_mm: float, dy_mm: float) -> tuple[float, float]:
    return (point[0] + dx_mm / 1000.0, point[1] + dy_mm / 1000.0)


def _center_view(adapter: Any, view: Any, target: tuple[float, float], *, label: str) -> None:
    """Move ``view`` so its OUTLINE centre lands on ``target`` (sheet metres)."""
    bound = _early_bound(view, "IView")
    outline = tuple(float(value) for value in bound.GetOutline())
    position = tuple(float(value) for value in bound.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError(f"{label}: invalid view bounds")
    moved = [
        position[axis] + target[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not bound.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"{label}: failed to position view")
    rebuild_drawing(adapter, label=label)


def _cut_surface_only(view: Any, *, label: str) -> None:
    """Print only the cut faces: no ghost of the tube beyond the plane."""
    section = _early_bound(_early_bound(view, "IView").GetSection(), "IDrSection")
    section.SetDisplayOnlySurfaceCut(True)
    if not section.GetDisplayOnlySurfaceCut():
        raise RuntimeError(f"{label}: section retained geometry behind the cut")


def _place_view_label(
    adapter: Any, view: Any, xy: tuple[float, float], *, label: str
) -> None:
    """Park the native section/detail label (letter + scale) under its view."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    # A dynamic label follows sheet-scale changes; pin the final scale first.
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(f"{label}: cannot pin sheet scale before label placement")
    notes = tuple(_read_member(_early_bound(view, "IView"), "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"{label}: expected one native view label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    if not annotation.SetPosition2(xy[0], xy[1], 0.0):
        raise RuntimeError(f"{label}: cannot position native view label")


def _label_under(view: Any, below_mm: float) -> tuple[float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    return ((outline[0] + outline[2]) / 2.0, outline[1] - below_mm / 1000.0)


def _slot_detail(adapter: Any, joint: Any) -> Any:
    """Enlarge the 0.80 x 0.80 screw slot out of section A-A."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(joint, "IView")
    if not ddoc.ActivateView(view_name(adapter, joint)):
        raise RuntimeError("cannot activate slot detail parent")
    draw.ClearSelection2(True)
    center = _sheet_point(
        adapter, joint, SCREW_TIP_X + SCREW_SLOT_DEPTH / 2.0, ARM_Y, label="slot detail"
    )
    radius = SLOT_FENCE_RADIUS_MM * JOINT_SCALE[0] / JOINT_SCALE[1] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("cannot create slot detail fence")
    detail = ddoc.CreateDetailViewAt4(
        *SLOT_DETAIL_CENTER, 0.0, 0, *SLOT_DETAIL_SCALE, "C", 1, True, False, False, 5
    )
    if detail is None:
        raise RuntimeError("cannot create slot detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in SLOT_DETAIL_SCALE])
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="slot detail")
    _center_view(adapter, detail, SLOT_DETAIL_CENTER, label="slot detail")
    return detail


def _log_layout(adapter: Any) -> None:
    """Record every sheet's measured geometry in the build log (never fatal).

    Farm-only iteration has no seat to audit on; the sheet-millimetre dump and
    the audit findings in the leaf log are what the next placement is fitted to.
    """
    try:
        from diagnostics.drawing_layout_audit import collect_document, describe_sheet
        from _layout_geometry import audit_sheet, format_findings

        for sheet in collect_document(adapter):
            _telemetry.info("layout dump\n" + describe_sheet(sheet))
            findings = audit_sheet(sheet)
            if findings:
                _telemetry.warn(
                    f"layout findings on {sheet.name!r}:\n" + format_findings(findings)
                )
    except Exception as exc:  # diagnostics only: a dump failure must not cost the print
        _telemetry.warn(f"layout dump unavailable: {exc!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Elevation View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Elevation View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="gooseneck package")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Gooseneck Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "gooseneck; plated tube; brazed plug; spring adjustment screw",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    # ---- Sheet 1: formed tube -------------------------------------------------
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate gooseneck form sheet")
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 3))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_removed(adapter, front)
    _center_view(adapter, iso, ISO_CENTER, label="isometric")

    def front_at(x: float, y: float, dx: float = 0.0, dy: float = 0.0) -> tuple[float, float]:
        return _offset(_sheet_point(adapter, front, x, y, label="elevation"), dx, dy)

    leg_mid_y = (-330.0 + (ARM_Y - BEND_R)) / 2.0
    bend_45 = (-BEND_R + BEND_R * math.cos(math.pi / 4), ARM_Y - BEND_R + BEND_R * math.sin(math.pi / 4))
    front_dimensions = curate_view_dimensions(
        adapter,
        front,
        keep={
            "LegLength": front_at(TUBE_R, leg_mid_y, dx=16.0),
            "BendRadius": front_at(*bend_45, dx=26.0, dy=18.0),
            "ArmRun": front_at((-BEND_R + ARM_END_X) / 2.0, ARM_Y + TUBE_R, dy=12.0),
        },
        view_label="elevation",
        dimensions_by_feature=ELEVATION_DIMENSIONS,
    )

    post = create_section_view(
        adapter,
        front,
        line_start=front_at(-2.5 * TUBE_R, POST_CUT_Y),
        line_end=front_at(2.5 * TUBE_R, POST_CUT_Y),
        view_xy=POST_SECTION_CENTER,
        section_label="B",
        scale=POST_SECTION_SCALE,
        label="post wall section",
    )
    _cut_surface_only(post, label="post wall section")
    set_hidden_lines_removed(adapter, post)
    rebuild_drawing(adapter, label="post wall section")
    _center_view(adapter, post, POST_SECTION_CENTER, label="post wall section")
    post_center = _sheet_point(adapter, post, 0.0, POST_CUT_Y, label="post axis")
    post_dimensions = curate_view_dimensions(
        adapter,
        post,
        keep={
            "TubeDia": _offset(post_center, 26.0, 22.0),
            "TubeBoreDia": _offset(post_center, 26.0, -22.0),
        },
        view_label="post wall section",
        dimensions_by_feature=POST_SECTION_DIMENSIONS,
    )
    _place_view_label(
        adapter, post, _label_under(post, POST_LABEL_BELOW_MM), label="section B-B label"
    )
    add_property_linked_note(adapter, "Elevation View Note", *ELEVATION_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # ---- Sheet 2: arm-end fabrication -----------------------------------------
    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate gooseneck fabrication sheet")
    plan = place_view(adapter, str(SOURCE), "*Top", *PLAN_CENTER, scale=PLAN_SCALE)
    set_hidden_lines_removed(adapter, plan)
    joint = create_section_view(
        adapter,
        plan,
        line_start=_sheet_point(
            adapter, plan, SCREW_TIP_X - 3.0, ARM_Y, label="joint cut head end"
        ),
        line_end=_sheet_point(
            adapter, plan, JOINT_CUT_END_X, ARM_Y, label="joint cut arm end"
        ),
        view_xy=JOINT_CENTER,
        section_label="A",
        scale=JOINT_SCALE,
        partial=True,
        label="arm and brazed end joint",
    )
    _cut_surface_only(joint, label="arm and brazed end joint")
    set_hidden_lines_removed(adapter, joint)
    rebuild_drawing(adapter, label="arm and brazed end joint")
    _center_view(adapter, joint, JOINT_CENTER, label="arm and brazed end joint")

    # +X may print left or right, depending on the cut direction SolidWorks
    # chose; every horizontal offset follows the projected arm direction.
    axis_head = _sheet_point(adapter, joint, SCREW_TIP_X, ARM_Y, label="joint head")
    axis_far = _sheet_point(adapter, joint, SHANK_END_X, ARM_Y, label="joint far")
    sign = 1.0 if axis_far[0] >= axis_head[0] else -1.0
    _telemetry.info(f"section A-A prints part +X toward sheet {'right' if sign > 0 else 'left'}")

    def joint_at(x: float, y: float, dx: float = 0.0, dy: float = 0.0) -> tuple[float, float]:
        return _offset(
            _sheet_point(adapter, joint, x, y, label="joint"), sign * dx, dy
        )

    top = ARM_Y + TUBE_R
    bottom = ARM_Y - TUBE_R
    joint_dimensions = curate_view_dimensions(
        adapter,
        joint,
        keep={
            # Above: axial lengths, measured off the upper profile edges.
            "HeadThickness": joint_at((SCREW_TIP_X + HEAD_X) / 2.0, top, dy=10.0),
            "PlugDepth": joint_at((ARM_END_X + PLUG_END_X) / 2.0, top, dy=10.0),
            "UnderHeadLength": joint_at((HEAD_X + SHANK_END_X) / 2.0, top, dy=24.0),
            # Left of the head: its diameter.
            "ScrewHeadDia": joint_at(SCREW_TIP_X - 3.0, bottom, dy=-12.0),
            # In the open gap between head and arm end: shank and plug face.
            "ScrewShankDia": joint_at(HEAD_X + 1.4, bottom, dy=-30.0),
            "PlugDia": joint_at(ARM_END_X - 1.0, top, dy=44.0),
            # Past the plug's inner face, beyond the screw tip.
            "TapMinorDia": joint_at(SHANK_END_X + 3.0, bottom, dy=-12.0),
        },
        view_label="arm joint section",
        dimensions_by_feature=JOINT_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        joint_dimensions,
        {"PlugDia": PLUG_FIT_CALLOUT},
        location="above",
    )
    set_dimension_callouts(
        adapter,
        joint_dimensions,
        {"TapMinorDia": TAP_CALLOUT, "ScrewShankDia": SCREW_CALLOUT},
        location="below",
    )
    set_reference_dimensions(adapter, joint_dimensions, ("PlugDia",))
    _place_view_label(
        adapter, joint, _label_under(joint, 40.0), label="section A-A label"
    )

    detail = _slot_detail(adapter, joint)
    slot_mouth = _sheet_point(adapter, detail, SCREW_TIP_X, ARM_Y, label="slot mouth")
    slot_dimensions = curate_view_dimensions(
        adapter,
        detail,
        keep={
            "SlotWidth": _offset(slot_mouth, -sign * 14.0, 0.0),
            "SlotDepth": _offset(slot_mouth, sign * 5.0, 16.0),
        },
        view_label="screw slot detail",
        dimensions_by_feature=SLOT_DETAIL_DIMENSIONS,
    )
    _place_view_label(
        adapter, detail, _label_under(detail, LABEL_BELOW_MM), label="detail C label"
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    assert_imported_precision(
        adapter,
        [*front_dimensions, *post_dimensions, *joint_dimensions, *slot_dimensions],
        DRAWING_PRECISION_BY_NAME,
    )
    _telemetry.info(
        "arm-end stations mm: "
        f"tip {SCREW_TIP_X:g}, head {HEAD_X:g}, arm end {ARM_END_X:g}, "
        f"plug end {PLUG_END_X:g}, shank end {SHANK_END_X:g}; "
        f"head Ø{SCREW_HEAD_DIA:g}, thread major Ø{SCREW_THREAD_MAJOR_DIA:g}, "
        f"wall {WALL_T:g}"
    )
    _log_layout(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Post Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
