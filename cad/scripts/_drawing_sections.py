"""Drawing section-view cutting-line creation and verification.

Sectioned-part drawings create and prove cutting lines here without coupling
unsectioned sheets to section-authoring changes.
"""

from __future__ import annotations

from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
from _drawing_common import rebuild_drawing
import _telemetry


# The section cutting line is a GEOMETRIC DATUM, not annotation: the plane it
# defines is where every dimension taken off the section is measured, and a
# cut-face line carries that plane's own coordinate (which is what the part
# recipes pin dimensions to).  ``ISketchManager.CreateLine`` runs the new
# segment through the INFERENCE engine unless the sketch manager is in
# direct-to-DB mode, and sketch inference / automatic relations are
# APPLICATION-level preferences a seat carries from one leaf to the next
# (``diag_mcmaster_lib.SEAT_SKETCH_BASELINE`` restores all three ON), so an
# endpoint authored within snap distance of a view edge is pulled onto it --
# in SCREEN space, which makes the outcome depend on the seat's zoom rather
# than on this recipe.  A snap of a fraction of a millimetre on the sheet
# tilts the plane: top_frame's D-D was cut 4.29 degrees oblique, 0.674 mm off
# station at the rail face, by exactly that (leaf 2026-09-18T14:40Z).  Both
# mechanisms are shut off here, and the placement is then read back, because a
# preference the seat declines to write fails SILENTLY.
_SECTION_LINE_TOLERANCE_M = 1e-9


def _assert_section_line_placed(
    adapter: Any,
    segment: Any,
    points: list[tuple[float, ...]],
    *,
    label: str,
) -> None:
    """Read the created cutting line's endpoints back off the sketch.

    Suppression is not evidence.  Exactness is the right bar: nothing
    legitimately moves an endpoint authored in sketch coordinates, and the
    smallest snap observed on a seat is five orders of magnitude above this
    tolerance, so a real snap can never hide under it and float noise can
    never trip it.
    """
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor, which in (
        (points[0], "GetStartPoint2", "start"),
        (points[1], "GetEndPoint2", "end"),
    ):
        raw = adapter._get_attr_or_call(line, accessor)
        if raw is None:
            raise RuntimeError(f"{label}: the section line has no {which} point")
        point = _early_bound(raw, "ISketchPoint")
        actual = tuple(
            float(adapter._get_attr_or_call(point, axis)) for axis in ("X", "Y", "Z")
        )
        drift = max(abs(a - b) for a, b in zip(actual, expected))
        if drift > _SECTION_LINE_TOLERANCE_M:
            raise RuntimeError(
                f"{label}: the section cutting line's {which} point sits "
                f"{drift * 1000.0:.4g} mm from where it was authored "
                f"({actual} instead of {expected}) -- sketch inference snapped "
                "it onto nearby geometry, so the cut plane is not the requested "
                "one and every dimension taken off the section would be "
                "measured on the wrong plane"
            )


@_telemetry.traced("drawing.section_view", label_param="label")
def create_section_view(
    adapter: Any,
    parent_view: Any,
    *,
    line_start: tuple[float, float],
    line_end: tuple[float, float],
    view_xy: tuple[float, float],
    section_label: str,
    scale: tuple[int, int] = (1, 1),
    partial: bool = False,
    label: str,
) -> Any:
    """Create an unaligned section from one straight cutting-plane line.

    The public coordinates are drawing-sheet meters; convert them through the
    parent sketch's transform before CreateLine, which takes view-local sketch
    coordinates. Passing sheet coordinates directly offsets and scales the cut
    again (at 1:2, a centre cut can miss the part entirely).
    ``CreateLine`` is placed with the sketch manager in direct-to-DB mode and
    its endpoints are read back (:func:`_assert_section_line_placed`): an
    inferred endpoint snaps, and a snapped cutting line cuts an OBLIQUE plane.
    Direct-to-DB creation does not leave the new segment selected the way an
    inferred draw does, so it is selected explicitly for the
    ``CreateSectionViewAt5`` precondition.  The section is deliberately
    unaligned so a part recipe can place and scale it independently of the
    parent view.

    ``partial=True`` is the ASME removed section: the cutting line spans ONLY
    the feature of interest (one rail of a frame, not the whole plan), and
    with ``swCreateSectionView_Partial`` SolidWorks sections just that span
    instead of the full plane -- so a cut through a symmetric frame shows one
    T profile to dimension, not that profile and its unannotated twin 80 mm
    away. Without the flag a short line is the "olive, unhatched" failure the
    layout-tuning notes describe (the cut does not close); with it the line
    is allowed to stop inside the part. Pair it with
    ``IDrSection::SetDisplayOnlySurfaceCut`` (the recipes' cut-only mode) so
    nothing beyond the plane prints either.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    name = view_name(adapter, parent_view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate section parent view {name!r} ({label})")
    draw.ClearSelection2(True)
    parent = _early_bound(parent_view, "IView")
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (line_start, line_end):
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        segment = sketch_manager.CreateLine(*points[0], *points[1])
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError(f"failed to create section line ({label})")
    _assert_section_line_placed(adapter, segment, points, label=label)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = parent_view
    selectable = _sw_type_info.early_bound_or_flag(segment, "ISketchSegment", "Select4")
    if not selectable.Select4(False, selection_data):
        raise RuntimeError(f"failed to select the section line ({label})")
    selected = int(selection_manager.GetSelectedObjectCount2(-1))
    if selected != 1:
        raise RuntimeError(
            f"selecting the section line produced {selected} entities ({label})"
        )
    # swCreateSectionView_NotAligned | swCreateSectionView_ScaleWithModel
    # (| swCreateSectionView_Partial for a removed section).
    options = 0x1 | 0x8 | (0x10 if partial else 0)
    section = ddoc.CreateSectionViewAt5(
        float(view_xy[0]),
        float(view_xy[1]),
        0.0,
        section_label,
        options,
        None,
        0.0,
    )
    if section is None:
        raise RuntimeError(f"failed to create section view ({label})")
    section = _sw_type_info.early_bound_or_flag(
        section, "IView", "GetSection", "SetViewPosition"
    )
    section.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
    if not section.SetViewPosition(
        double_array([float(view_xy[0]), float(view_xy[1])]), False
    ):
        raise RuntimeError(f"failed to position section view ({label})")
    dr_section = section.GetSection()
    if dr_section is None:
        raise RuntimeError(f"section view has no section definition ({label})")
    dr_section = _sw_type_info.early_bound_or_flag(
        dr_section, "IDrSection", "SetAutoHatch", "SetLabel2"
    )
    dr_section.SetAutoHatch(True)
    if int(dr_section.SetLabel2(section_label)) < 0:
        raise RuntimeError(f"failed to persist section label ({label})")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="create_section_view")
    return section
