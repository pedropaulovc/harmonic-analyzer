"""Turning-axis centerline and caption placement for a turned part's section.

The longitudinal section is a turned part's length view (policy rule 7): its
explicit centerline says which edges are the faced ends, and the cut exposes
the bores so their diameters never land on hidden lines.  Lifted from
``draw_crank_pinion`` for the small turned parts that share the layout
(MHA-150, MHA-153); only their drawings import it.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _common import _early_bound
from _drawing_common import rebuild_drawing, view_name


@_telemetry.traced("drawing.section_axis", label_param="label")
def create_section_axis_centerline(
    adapter: Any, view: Any, *, length_mm: float, label: str
) -> Any:
    """Draw the turning axis across a longitudinal section's full length.

    A section view's sketch is centred on the view, in model metres, so the
    line runs symmetric about it and 1 mm past each end whichever way the
    section lays the part.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not drawing.ActivateView(name):
        raise RuntimeError(f"failed to activate section view {name!r} ({label})")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    previous_display = bool(sketch_manager.DisplayWhenAdded)
    sketch_manager.AddToDB = True
    sketch_manager.DisplayWhenAdded = True
    half = length_mm / 2000.0 + 0.001
    try:
        centerline = sketch_manager.CreateCenterLine(-half, 0.0, 0.0, half, 0.0, 0.0)
    finally:
        sketch_manager.AddToDB = previous_add_to_db
        sketch_manager.DisplayWhenAdded = previous_display
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError(f"failed to create section-axis centerline ({label})")
    return centerline


def position_section_caption(
    adapter: Any, view: Any, target: tuple[float, float], *, label: str
) -> None:
    """Move the native linked section caption to ``target`` and verify it."""
    bound_view = _early_bound(view, "IView")
    candidates = []
    for raw_note in bound_view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")):
            candidates.append((note, linked_text))
    if len(candidates) != 1:
        raise RuntimeError(
            f"{label}: expected one native linked section caption, found {len(candidates)}"
        )
    note, linked_text = candidates[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError(f"{label}: failed to position the section caption")
    rebuild_drawing(adapter, label=f"position {label} section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError(f"{label}: section caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError(f"{label}: section caption lost its native fields")
