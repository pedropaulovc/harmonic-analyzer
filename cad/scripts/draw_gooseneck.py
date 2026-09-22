r"""Create the curated machinist drawing for the gooseneck counter-spring post.

The SLDPRT remains authoritative. Sheet 1 defines the formed tube: a 1:3
elevation, a 2:1 cut-surface section B-B across the post for the tube wall,
and the standard isometric. Sheet 2 is the arm-end fabrication: a small plan
view carries cutting line A-A along the arm axis in the plane of the bend; the
4:1 section shows the separate brazed plug in the tube bore with the screw
installed, and a 7:1 side view of the screw body alone carries the screw.
Plug and screw are Front-plane revolves, so their diameters import as
side-view sizes. Every displayed size is imported from the
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
    add_edge_dimension,
    curate_view_dimensions,
    dimension_name,
    find_edge_near,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.com_variant import dispatch_array, double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

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
from build_gooseneck import LEG_BOTTOM
from gooseneck_spec import (
    BEND_RADIUS_CALLOUT,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    ELEVATION_DIMENSIONS,
    JOINT_DIMENSIONS,
    PLUG_FIT_CALLOUT,
    POST_SECTION_DIMENSIONS,
    SCREW_CALLOUT,
    SCREW_DIMENSIONS,
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
BORE_R = TUBE_R - WALL_T
OVERALL_HEIGHT = ARM_Y + TUBE_R - LEG_BOTTOM  # leg bottom to arm top, 501.3
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
POST_SECTION_CENTER = (0.190, 0.175)  # where the post AXIS lands
POST_SECTION_SCALE = (2, 1)
ISO_CENTER = (0.330, 0.170)
ISO_SCALE = (1, 3)
ELEVATION_NOTE_XY = (0.058, 0.048)
# The overall height stands LEFT of the elevation: right of it, its upper
# extension line would graze the bend and cross the R51 leader.
OVERALL_HEIGHT_X = 0.060
ISO_NOTE_XY = (0.290, 0.085)
POST_LABEL_BELOW_MM = 44.0  # below the post axis: ring, the Ø12 row, air
# The two diameters print as LINEAR dimensions above and below the ring:
# as diameter leaders both run through the centre and cross (farm r5).
POST_DIAMETER_ROW_MM = 24.0

# Sheet 2. The plan parent is only the carrier of cutting line A-A. Views
# are placed by where a model point lands, not by outline: a cut-surface
# section's outline still spans geometry it does not print.
PLAN_CENTER = (0.085, 0.240)
PLAN_SCALE = (1, 2)
# A diametric dimension parked beyond its extension lines prints its text on a
# shoulder running the SAME way as the extension lines (feature -> dim line,
# measured r5). The plug diameter stands left of the plug, so its long fit
# callout runs left: the arm end sits far enough right to hold it.
JOINT_AXIS_AT_ARM_END = (0.150, 0.140)  # section A-A: arm end face on the axis
JOINT_SCALE = (4, 1)
JOINT_LABEL_BELOW_MM = 62.0
SCREW_AXIS_AT_HEAD = (0.300, 0.185)  # screw view: head underside on the axis
SCREW_SCALE = (7, 1)
SCREW_NOTE_BELOW_MM = 80.0
NOTES_XY = (0.020, 0.042)


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


def _move_to(
    adapter: Any,
    view: Any,
    point_mm: tuple[float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> tuple[float, float]:
    """Move ``view`` so the part point ``point_mm`` (x, y at z=0) lands on
    ``target``; returns where it landed (sheet metres)."""
    bound = _early_bound(view, "IView")
    for _ in range(2):
        landed = _sheet_point(adapter, view, *point_mm, label=label)
        position = tuple(float(value) for value in bound.Position)
        moved = [position[axis] + target[axis] - landed[axis] for axis in range(2)]
        if not bound.SetViewPosition(double_array(moved), False):
            raise RuntimeError(f"{label}: failed to position view")
        rebuild_drawing(adapter, label=label)
    landed = _sheet_point(adapter, view, *point_mm, label=label)
    if math.dist(landed, target) > 1e-4:
        raise RuntimeError(f"{label}: view point landed at {landed}, wanted {target}")
    return landed


def _axis_signs(adapter: Any, view: Any, *, label: str) -> tuple[float, float]:
    """Sheet direction (+1/-1) of part +X and +Y in ``view``."""
    origin = _sheet_point(adapter, view, ARM_END_X, ARM_Y, label=label)
    along_x = _sheet_point(adapter, view, ARM_END_X + 1.0, ARM_Y, label=label)
    along_y = _sheet_point(adapter, view, ARM_END_X, ARM_Y + 1.0, label=label)
    sx = 1.0 if along_x[0] > origin[0] else -1.0
    sy = 1.0 if along_y[1] > origin[1] else -1.0
    if abs(along_x[1] - origin[1]) > 1e-9 or abs(along_y[0] - origin[0]) > 1e-9:
        raise RuntimeError(f"{label}: arm axis is not horizontal on the sheet")
    _telemetry.info(f"{label}: part +X -> sheet {sx:+.0f} x, part +Y -> sheet {sy:+.0f} y")
    return sx, sy


def _add_overall_height(
    adapter: Any, front: Any, front_at: Any, leg_mid_y: float
) -> None:
    """Reference overall height, leg bottom to arm top (Codex r6 clarity).

    The 442.3 leg length stops at the bend tangent, so without this a reader
    can take it for the overall height. Derived from model-owned sizes, so it
    prints as a REFERENCE at the spec's reference places.
    """
    label = "overall height reference"
    # Leg bottom: pick the end face's outer circle between bore and wall
    # (edge-on, it lies wholly at LEG_BOTTOM); arm top: its silhouette.
    bottom = find_edge_near(
        adapter, front, front_at((BORE_R + TUBE_R) / 2.0, LEG_BOTTOM), axis="y", label=label
    )
    top = find_edge_near(
        adapter,
        front,
        front_at((-BEND_R + ARM_END_X) / 2.0, ARM_Y + TUBE_R),
        axis="y",
        label=label,
        entity_type="SILHOUETTE",
    )
    display = _early_bound(
        add_edge_dimension(
            adapter,
            front,
            p0=bottom,
            p1=top,
            text_xy=(OVERALL_HEIGHT_X, front_at(0.0, leg_mid_y)[1]),
            label=label,
            orientation="vertical",
            entity_types=("EDGE", "SILHOUETTE"),
        ),
        "IDisplayDimension",
    )
    measured_mm = float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue) * 1000.0
    if abs(measured_mm - OVERALL_HEIGHT) > 1e-5:
        raise RuntimeError(f"{label}: measured {measured_mm!r}, expected {OVERALL_HEIGHT!r} mm")
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label}: reference precision did not persist")
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)


def _diameters_as_linear(
    adapter: Any, annotations: list[Any], positions: dict[str, tuple[float, float]]
) -> None:
    """Print named diameter dimensions as linear ones, then place them."""
    remaining = dict(positions)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        xy = remaining.pop(name, None)
        if xy is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.DisplayAsLinear = True
        if not bool(display.DisplayAsLinear):
            raise RuntimeError(f"{name}: DisplayAsLinear did not persist")
        if not annotation.SetPosition2(xy[0], xy[1], 0.0):
            raise RuntimeError(f"{name}: cannot place linear diameter")
    if remaining:
        raise RuntimeError(f"linear diameters not found: {sorted(remaining)}")
    rebuild_drawing(adapter, label="linear diameters")


# swAreaHatchFillStyle_e
_HATCH_NONE = 1


def _face_hatches(adapter: Any, view: Any, *, label: str) -> list[Any]:
    """Every face hatch in ``view``, or RAISE with the counts.

    Farm r10 (swmaker000004) got ``None`` entries from ``GetFaceHatches``
    straight after a rebuild. A view's display geometry is computed lazily (see
    ``_drawing_common`` on the HLR flag), so each read is retried once after a
    display-geometry update and once after a redraw. Every stage is recorded;
    a ``None`` entry is never skipped.
    """
    bound = _early_bound(view, "IView")
    stages = (
        ("after rebuild", None),
        ("after UpdateViewDisplayGeometry", bound.UpdateViewDisplayGeometry),
        ("after GraphicsRedraw2", adapter.currentModel.GraphicsRedraw2),
    )
    readings = []
    for stage, refresh in stages:
        if refresh is not None:
            refresh()
        count = int(bound.GetFaceHatchCount())
        raw = tuple(bound.GetFaceHatches() or ())
        missing = sum(item is None for item in raw)
        readings.append(f"{stage}: count {count}, returned {len(raw)}, None {missing}")
        _telemetry.event(
            "drawing.face_hatches",
            label=label,
            stage=stage,
            count=count,
            returned=len(raw),
            missing=missing,
        )
        _telemetry.info(f"{label}: face hatches {readings[-1]}")
        if raw and not missing and len(raw) == count:
            return [_early_bound(item, "IFaceHatch") for item in raw]
    raise RuntimeError(f"{label}: face hatches unreadable ({'; '.join(readings)})")


def _screw_hatches(adapter: Any, view: Any, *, label: str) -> tuple[list[Any], int]:
    """The view's face hatches on the screw's cut faces, and the total count.

    Only the screw reaches beyond the arm end (its head sits a clamped gap
    outboard); tube and plug cut faces both stop at ``ARM_END_X``.
    """
    hatches = _face_hatches(adapter, view, label=label)
    beyond_arm_end = (ARM_END_X - 1.0) / 1000.0
    screw = [
        hatch
        for hatch in hatches
        if float(_early_bound(hatch.Face, "IFace2").GetBox()[0]) < beyond_arm_end
    ]
    return screw, len(hatches)


def _leave_screw_unsectioned(adapter: Any, view: Any) -> None:
    """Show the screw unsectioned in section A-A, per the Y14.3 fastener rule.

    A part drawing cannot exclude one body from a section: the IDrSection and
    CreateSectionViewAt5 exclusions take assembly components, and
    ISectionViewData's selective sectioning is for model views. So instead the
    screw's cut-face hatch fill is cleared. Its cut outline is the same as its
    unsectioned side-view outline, because the cut runs along the axis.
    """
    label = "section A-A screw hatch"
    screw, total = _screw_hatches(adapter, view, label=label)
    if not screw or len(screw) == total:
        raise RuntimeError(f"{label}: {len(screw)} of {total} hatches are the screw's")
    for hatch in screw:
        hatch.HatchType = _HATCH_NONE
    rebuild_drawing(adapter, label=label)
    screw, total = _screw_hatches(adapter, view, label=label)
    kept = [int(hatch.HatchType) for hatch in screw]
    if not screw or any(kind != _HATCH_NONE for kind in kept):
        raise RuntimeError(f"{label}: screw hatch fill did not clear: {kept}")
    _telemetry.info(
        f"{label}: cleared {len(screw)} screw hatch(es), kept {total - len(screw)}",
        screw_hatches=len(screw),
        kept_hatches=total - len(screw),
    )


def _show_only_screw(adapter: Any, view: Any) -> None:
    """Restrict ``view`` to the adjustment-screw body (the body reaching
    furthest toward -X: the head face sits beyond the arm end)."""
    bound = _early_bound(view, "IView")
    model = _early_bound(bound.ReferencedDocument, "IPartDoc")
    bodies = [_early_bound(raw, "IBody2") for raw in model.GetBodies2(0, True) or ()]
    if len(bodies) != 3:
        raise RuntimeError(f"screw view: expected 3 solid bodies, found {len(bodies)}")
    screw = min(bodies, key=lambda body: float(body.GetBodyBox()[0]))
    bound.Bodies = dispatch_array([screw])
    shown = int(bound.GetBodiesCount())
    if shown != 1:
        raise RuntimeError(f"screw view shows {shown} bodies, expected the screw alone")


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
            "Screw View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Elevation View Note",
            "Isometric View Note",
            "Screw View Note",
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

    leg_mid_y = (LEG_BOTTOM + (ARM_Y - BEND_R)) / 2.0
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
    set_dimension_callouts(
        adapter, front_dimensions, {"BendRadius": BEND_RADIUS_CALLOUT}, location="below"
    )
    _add_overall_height(adapter, front, front_at, leg_mid_y)

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
    post_center = _move_to(
        adapter, post, (0.0, POST_CUT_Y), POST_SECTION_CENTER, label="post wall section"
    )
    post_dimensions = curate_view_dimensions(
        adapter,
        post,
        keep={
            "TubeDia": _offset(post_center, 0.0, POST_DIAMETER_ROW_MM),
            "TubeBoreDia": _offset(post_center, 0.0, -POST_DIAMETER_ROW_MM),
        },
        view_label="post wall section",
        dimensions_by_feature=POST_SECTION_DIMENSIONS,
    )
    _diameters_as_linear(
        adapter,
        post_dimensions,
        {
            "TubeDia": _offset(post_center, 0.0, POST_DIAMETER_ROW_MM),
            "TubeBoreDia": _offset(post_center, 0.0, -POST_DIAMETER_ROW_MM),
        },
    )
    _place_view_label(
        adapter, post, _offset(post_center, 0.0, -POST_LABEL_BELOW_MM),
        label="section B-B label",
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
        view_xy=JOINT_AXIS_AT_ARM_END,
        section_label="A",
        scale=JOINT_SCALE,
        partial=True,
        label="arm and brazed end joint",
    )
    _cut_surface_only(joint, label="arm and brazed end joint")
    set_hidden_lines_removed(adapter, joint)
    rebuild_drawing(adapter, label="arm and brazed end joint")
    _leave_screw_unsectioned(adapter, joint)
    arm_end = _move_to(
        adapter, joint, (ARM_END_X, ARM_Y), JOINT_AXIS_AT_ARM_END,
        label="arm and brazed end joint",
    )
    jx, jy = _axis_signs(adapter, joint, label="section A-A")

    def joint_at(x: float, y: float, dx: float = 0.0, dy: float = 0.0) -> tuple[float, float]:
        """Part point, then an offset in sheet mm along part +X / +Y."""
        return _offset(_sheet_point(adapter, joint, x, y, label="joint"), jx * dx, jy * dy)

    # The profile anchors sit on the +Y side, so the axial length lives there;
    # every diameter text goes to the -Y side, its callout between it and the
    # part. The plug diameter's line stands in the open gap left of the tube
    # end, clear of the tap callout that spans the plug.
    plus_y, minus_y = ARM_Y + TUBE_R, ARM_Y - TUBE_R
    joint_dimensions = curate_view_dimensions(
        adapter,
        joint,
        keep={
            "PlugDepth": joint_at((ARM_END_X + PLUG_END_X) / 2.0, plus_y, dy=12.0),
            # Right of the plug's inner face, so its callout runs right,
            # away from the plug diameter's leftward one: no shared lane.
            "TapMinorDia": joint_at(PLUG_END_X + 0.8, minus_y, dy=-16.0),
            "PlugDia": joint_at(ARM_END_X - 1.5, minus_y, dy=-21.0),
        },
        view_label="arm joint section",
        dimensions_by_feature=JOINT_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        joint_dimensions,
        {"PlugDia": PLUG_FIT_CALLOUT, "TapMinorDia": TAP_CALLOUT},
        location="below",
    )
    # Thread sizes are set by the callouts: the modelled diameters (the #36
    # tap drill, the #6 major) print as REFERENCE (Codex r6 over-spec).
    set_reference_dimensions(adapter, joint_dimensions, ("PlugDia", "TapMinorDia"))
    _place_view_label(
        adapter,
        joint,
        (arm_end[0], arm_end[1] - JOINT_LABEL_BELOW_MM / 1000.0),
        label="section A-A label",
    )

    screw = place_view(adapter, str(SOURCE), "*Front", *SCREW_AXIS_AT_HEAD, scale=SCREW_SCALE)
    _show_only_screw(adapter, screw)
    set_hidden_lines_removed(adapter, screw)
    rebuild_drawing(adapter, label="screw view")
    head = _move_to(adapter, screw, (HEAD_X, ARM_Y), SCREW_AXIS_AT_HEAD, label="screw view")
    sx, sy = _axis_signs(adapter, screw, label="screw view")

    def screw_at(x: float, y: float, dx: float = 0.0, dy: float = 0.0) -> tuple[float, float]:
        return _offset(_sheet_point(adapter, screw, x, y, label="screw"), sx * dx, sy * dy)

    head_plus, head_minus = ARM_Y + SCREW_HEAD_DIA / 2.0, ARM_Y - SCREW_HEAD_DIA / 2.0
    screw_dimensions = curate_view_dimensions(
        adapter,
        screw,
        keep={
            # +Y side: axial lengths (their profile anchors are there).
            # Text outside, past the slotted face: between its extension lines
            # it crowded the shared one at the head underside (farm r6 audit).
            "HeadThickness": screw_at(SCREW_TIP_X - 1.4, head_plus, dy=10.0),
            "UnderHeadLength": screw_at(
                (HEAD_X + SHANK_END_X) / 2.0, head_plus, dy=22.0
            ),
            # Slot width and head diameter stand OFF the slotted face: to the
            # right, the head-diameter line crossed the shank (farm r6). The
            # slot-width text sits just past its upper arrow, so it reads
            # with the slot it sizes and clears the head-diameter lines.
            "SlotWidth": screw_at(SCREW_TIP_X - 2.0, ARM_Y, dy=9.0),
            # -Y side: diameters and the slot depth (its sketch edge is -Y).
            "ScrewHeadDia": screw_at(SCREW_TIP_X - 4.5, head_minus, dy=-10.0),
            # Text past the slot floor: between its extension lines it
            # straddled them (farm r6).
            "SlotDepth": screw_at(
                SCREW_TIP_X + SCREW_SLOT_DEPTH + 1.2, head_minus, dy=-22.0
            ),
            "ScrewShankDia": screw_at(HEAD_X + 7.0, head_minus, dy=-22.0),
        },
        view_label="adjustment screw",
        dimensions_by_feature=SCREW_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter, screw_dimensions, {"ScrewShankDia": SCREW_CALLOUT}, location="below"
    )
    set_reference_dimensions(adapter, screw_dimensions, ("ScrewShankDia",))
    add_property_linked_note(
        adapter,
        "Screw View Note",
        head[0] - 0.040,
        head[1] - SCREW_NOTE_BELOW_MM / 1000.0,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    assert_imported_precision(
        adapter,
        [*front_dimensions, *post_dimensions, *joint_dimensions, *screw_dimensions],
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
