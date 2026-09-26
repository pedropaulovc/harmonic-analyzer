r"""Create the crankshaft MHA-026 manufacturing drawing under the simplicity policy.

The SLDPRT remains authoritative.  A shaft carries no datum and no
geometric-control frame (policy rule 3): the two running/seat diameters keep
their native size bands, the journal keeps one bearing-surface finish, and
every length is an ordinary model dimension at its part-authored places.

The model's shaft axis runs along +Y from the dome root (local y=0, the plane
where MHA-020 and MHA-137 finish flush).  The single longitudinal view is the
``*Right`` orientation rotated a quarter turn in the sheet so the shaft lies
horizontal, as it sits in the lathe: dome on the left, far end on the right,
the MHA-024 cross-hole seen as a true circle.  The crank-end view is the
``*Bottom`` orientation, which is exactly the third-angle LEFT view of that
rotated profile, so it sits on the profile's axis to its left at sheet scale.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crankshaft.py crankshaft
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any, Sequence

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _surface_finish import surface_finish_by_key
from crankshaft_spec import (
    CROSS_HOLE_PROCESS,
    DRAWING_PRECISION_BY_NAME,
    JOURNAL_DIA,
    JOURNAL_LENGTH,
    JOURNAL_START,
    PIN_HOLE_HEIGHT,
    PIN_HOLE_SPEC,
    REFERENCE_DIMENSIONS,
    SHAFT_DIA,
    SHAFT_DOME_HEIGHT,
    SHAFT_LENGTH,
    SPHERICAL_DIMENSIONS,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from build_crankshaft import PINION_PIN_DIA, PINION_PIN_STATION_Y
from crank_pinion_spec import CRANKSHAFT_PIN_HOLE_PROCESS
from crankshaft_notes import CROSS_HOLE_CALLOUT
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crankshaft"]
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
_PIN_HOLE_DIA = blind_cut_dia_mm(PIN_HOLE_SPEC)

# Both orthographic views print at the sheet scale, so neither needs a caption.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.210, 0.170)
# Third-angle left view of the dome end, on the profile's axis.
END_CENTER = (0.036, SIDE_CENTER[1])
ISO_CENTER = (0.390, SIDE_CENTER[1])
ISO_SCALE = (1, 1)
# The *Right view rotated -90 degrees: model +Y runs to paper-right.
SIDE_VIEW_ANGLE = -math.pi / 2.0

# The side view is centred on the model bbox, dome tip (-DomeHeight) through
# the far end (+ShaftLength).
_BBOX_MID_Y = (SHAFT_LENGTH - SHAFT_DOME_HEIGHT) / 2.0


def _sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the horizontal side view."""
    return SIDE_CENTER[0] + (model_y_mm - _BBOX_MID_Y) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the shaft axis (model +Z up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


DOME_TIP_X = _sheet_x(-SHAFT_DOME_HEIGHT)
DOME_ROOT_X = _sheet_x(0.0)
PIN_X = _sheet_x(PIN_HOLE_HEIGHT)
JOURNAL_START_X = _sheet_x(JOURNAL_START)
JOURNAL_END_X = _sheet_x(JOURNAL_START + JOURNAL_LENGTH)
FAR_END_X = _sheet_x(SHAFT_LENGTH)
JOURNAL_FLANK_Y = _sheet_y(JOURNAL_DIA / 2.0)

# Baseline rows below the profile, all from the FAR END and stacked
# shortest-first so no extension line crosses a dimension line; rows are 13
# mm apart because the text sits ~3 mm above its requested point and the
# dimension line ~5 mm below it.  The 2.0 dome height shares the first row at
# the far left, where no baseline reaches.
_ROW_Y = (0.150, 0.137, 0.124, 0.111, 0.096)
# The two diameters are authored in end-profile sketches; the end view
# receives them first and they are then dragged onto the profile (rule 7:
# diameters on the side view).  Their temporary end-view spots are clear of
# everything else on the sheet.
END_KEEP = {
    "ShaftDiaDim": (0.036, 0.215),
    "JournalDiaDim": (0.036, 0.230),
}
SIDE_KEEP = {
    "DomeHeight": (DOME_TIP_X - 0.016, _ROW_Y[0]),
    "JournalInboardStation": ((JOURNAL_END_X + FAR_END_X) / 2.0 + 0.004, _ROW_Y[0]),
    "JournalOutboardStation": ((JOURNAL_START_X + FAR_END_X) / 2.0 - 0.020, _ROW_Y[1]),
    "PinHoleStation": ((PIN_X + FAR_END_X) / 2.0, _ROW_Y[2]),
    "Depth": ((DOME_ROOT_X + FAR_END_X) / 2.0, _ROW_Y[3]),
    "OverallLength": ((DOME_TIP_X + FAR_END_X) / 2.0, _ROW_Y[4]),
    # Above-left of the dome, where no extension line rises: the radial
    # leader runs down-right to the dome silhouette.
    "DomeSphereRadius": (DOME_TIP_X - 0.022, 0.205),
}
# A dragged diameter prints its dimension line at the requested X with the
# text running to its RIGHT (run 20260923T030252135Z-49e46990).  Its
# extension lines run parallel to the axis from the profile SKETCH that owns
# it, so each must sit on the section that sketch starts: the Ø9.525 circle
# lies at the dome root, and placed on the far-end seat its extension lines
# drew solid through the journal (run 20260923T031747843Z-94724e44).
# Ø9.525 on the dome-side seat right of the cross-hole; Ø11.388 on the
# journal right of its finish symbol.
DIAMETER_POSITIONS = {
    "ShaftDiaDim": (JOURNAL_START_X - 0.022, 0.200),
    "JournalDiaDim": (JOURNAL_END_X - 0.052, 0.200),
}
# One Ø9.525 dimension governs both 3/8-in seats.
CALLOUTS_ABOVE = {"ShaftDiaDim": "2X"}
CALLOUTS_BELOW = {"OverallLength": "OVERALL"}
FINISH_PICK = (JOURNAL_START_X + 0.040, JOURNAL_FLANK_Y)
FINISH_SYMBOL = (JOURNAL_START_X + 0.050, 0.203)
# Text centred up-right of the cross-hole, above the Ø9.525 dimension: the
# callout's leader leaves the text's left end and runs down-left at ~64 deg
# through the hole centre, a clean crossing of the 118.0 station's extension
# line rather than a near parallel one (run 20260923T030252135Z-49e46990),
# left of the Ø9.525 text and clear of the SR on the left.
HOLE_CALLOUT_XY = (PIN_X + 0.054, 0.247)
# The 16T retention-pin hole is match-drilled through the seated pinion's
# boss at assembly, so the sheet prints the pinion sheet's own matched-fit
# note with the mates swapped (crank_pinion_spec.CRANKSHAFT_PIN_HOLE_PROCESS,
# also the part property checked below): the operation, where it runs, the
# pin it is reamed to, the fit's acceptance and flush -- no size, no station.
# A bare transfer note gave the shaft's machinist none of these (machinist
# review of 4d4e038e3).  The note is attached to the hole's own visible rim edge: a radial hole in a
# round shaft has a saddle rim, not a circle, so a native Hole Wizard
# callout cannot bind to it (run1-61671871a).  Its TEXT sits, anchored
# upper-left, in the free field above the far-end seat, right of the Ø11.388
# text and left of the isometric; it is placed from its own measured box.
# Its leader must end on the hole, which the side view shows straddling the
# axis -- below the field's floor -- so the leader is held to the hole's
# window instead (run1b-e7fd1a2ec: the leader tip, not the text, read 0.3 mm
# under the floor).
PINION_PIN_X = _sheet_x(PINION_PIN_STATION_Y)
PINION_PIN_NOTE_XY = (0.258, 0.250)
PINION_PIN_NOTE_FIELD = (
    DIAMETER_POSITIONS["JournalDiaDim"][0] + 0.010,
    SIDE_CENTER[1],
    ISO_CENTER[0] - 0.012,
    0.2657,  # 1 mm inside the ASME B inner border
)
# Every point of the rim lies within the hole's half-width (plus 0.5 mm of
# pick slack) of its station and inside the shaft's silhouette.
PINION_PIN_HOLE_WINDOW = (
    PINION_PIN_X - (PINION_PIN_DIA / 2.0 + 0.5) * _S / 1000.0,
    _sheet_y(-SHAFT_DIA / 2.0),
    PINION_PIN_X + (PINION_PIN_DIA / 2.0 + 0.5) * _S / 1000.0,
    _sheet_y(SHAFT_DIA / 2.0),
)
NOTE_FIELD_MARGIN = 0.001
NOTES_XY = (0.016, 0.062)
ISO_NOTE_XY = (0.368, 0.108)


def _set_callout_below(display: Any, text: str, label: str) -> None:
    """Put the matched-operation prose UNDER a native hole callout.

    The drill size reads first, in the order the work is done; the fit and
    mate prose follows in the callout-below compartment (the Ø9.550 bore
    callout's order).  ``SetText`` reports nothing, so it is read back.
    """
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(4, text)  # swDimensionTextCalloutBelow
    applied = str(display.GetText(4) or "")
    if applied.replace("\r", "") != text:
        raise RuntimeError(f"{label}: callout-below text did not persist: {applied!r}")


Box = tuple[float, float, float, float]


def _shift_into_field(text: Box, field: Box, margin: float) -> tuple[float, float]:
    """Return the (dx, dy) that brings a measured text box ``margin`` inside ``field``.

    Boxes are (x0, y0, x1, y1) in sheet metres.  A box already inside moves
    (0, 0); one too big for the field fails loud, naming the overflow.
    """
    x0, y0, x1, y1 = text
    fx0, fy0, fx1, fy1 = field
    spare_x = (fx1 - fx0 - 2.0 * margin) - (x1 - x0)
    spare_y = (fy1 - fy0 - 2.0 * margin) - (y1 - y0)
    if spare_x < 0.0 or spare_y < 0.0:
        raise RuntimeError(
            f"text box {text} cannot sit {margin} inside field {field}: "
            f"over by {max(-spare_x, 0.0):.4f} wide, {max(-spare_y, 0.0):.4f} tall"
        )
    dx = max(0.0, fx0 + margin - x0) - max(0.0, x1 - (fx1 - margin))
    dy = max(0.0, fy0 + margin - y0) - max(0.0, y1 - (fy1 - margin))
    return dx, dy


def _leader_tip(points: Sequence[float], target: tuple[float, float]) -> tuple[float, float]:
    """Return the leader point (flat x, y, z triples) nearest ``target``."""
    triples = [
        (float(points[i]), float(points[i + 1])) for i in range(0, len(points) - 2, 3)
    ]
    if not triples:
        raise RuntimeError("note reports no leader points")
    return min(triples, key=lambda p: math.hypot(p[0] - target[0], p[1] - target[1]))


def _inside(point: tuple[float, float], box: Box) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _note_text_box(drawing_model: Any, annotation: Any, note: Any, label: str) -> Box:
    """Measure a leadered note's TEXT box: GetExtent includes the leader.

    The leader is hidden for the read and restored (straight, as
    ``add_attached_note`` makes it), then re-verified to still attach once.
    """
    if annotation.SetLeader3(0, 0, True, False, False, False) != 0:  # swNO_LEADER
        raise RuntimeError(f"{label}: could not hide the leader to measure the text")
    drawing_model.GraphicsRedraw2()
    extent = tuple(float(v) for v in (note.GetExtent() or ()))
    if annotation.SetLeader3(1, 0, True, False, False, False) != 0:  # swSTRAIGHT
        raise RuntimeError(f"{label}: could not restore the leader")
    drawing_model.GraphicsRedraw2()
    if int(annotation.GetLeaderCount()) != 1 or int(annotation.GetAttachedEntityCount3()) != 1:
        raise RuntimeError(f"{label}: note lost its one attached leader while measured")
    if len(extent) < 5:
        raise RuntimeError(f"{label}: note text extent unreadable: {extent}")
    return extent[0], extent[1], extent[3], extent[4]


def _place_note_text_in_field(
    drawing_model: Any, note: Any, field: Box, *, hole: Box, label: str
) -> None:
    """Move a leadered note's text inside ``field`` from its measured box.

    Its leader must still end inside ``hole``.  Everything read is logged.
    """
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text = _note_text_box(drawing_model, annotation, note, label)
    dx, dy = _shift_into_field(text, field, NOTE_FIELD_MARGIN)
    if dx or dy:
        x, y = (float(v) for v in tuple(annotation.GetPosition())[:2])
        if not annotation.SetPosition2(x + dx, y + dy, 0.0):
            raise RuntimeError(f"{label}: failed to move the note by ({dx}, {dy})")
        text = _note_text_box(drawing_model, annotation, note, label)
    leader = tuple(float(v) for v in (note.GetLeaderInfo() or ()))
    centre = ((hole[0] + hole[2]) / 2.0, (hole[1] + hole[3]) / 2.0)
    tip = _leader_tip(leader, centre)
    _telemetry.info(
        f"{label}: text box {text} moved ({dx:.4f}, {dy:.4f}); leader {leader}; tip {tip}"
    )
    if _shift_into_field(text, field, 0.0) != (0.0, 0.0):
        raise RuntimeError(f"{label}: text box {text} left its field {field}")
    if not _inside(tip, hole):
        raise RuntimeError(f"{label}: leader tip {tip} is off the hole window {hole}")


def _visible_cross_hole_edge(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return a visible rim edge adjacent to a modeled cross-hole cylinder."""
    expected_radius_m = diameter_mm / 2000.0
    candidates: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(
                    c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            adjacent_faces = edge.GetTwoAdjacentFaces2() or ()
            for face in adjacent_faces:
                if face is None:
                    continue
                face = _early_bound(face, "IFace2")
                surface = _early_bound(face.GetSurface(), "ISurface")
                if not surface.IsCylinder():
                    continue
                parameters = surface.CylinderParams
                if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                    continue
                candidates.append(edge)
                break
    if not candidates:
        raise RuntimeError(
            "crankshaft side view has no visible edge adjacent to the pin-hole "
            f"cylindrical face at radius {expected_radius_m:g} m"
        )
    return candidates[0]


def _visible_cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the requested modeled OD face in the crankshaft side view."""
    expected_radius_m = diameter_mm / 2000.0
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        faces = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(
                    c, 3
                ),  # swViewEntityType_Face
                default=(),
            )
            or ()
        )
        for face in faces:
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if not surface.IsCylinder():
                continue
            parameters = surface.CylinderParams
            if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                continue
            candidates.append((float(face.GetArea()), face))
    if not candidates:
        raise RuntimeError(
            f"crankshaft side view has no visible cylindrical face at "
            f"radius {expected_radius_m:g} m"
        )
    return max(candidates, key=lambda candidate: candidate[0])[1]


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a native model dimension and verify its new drawing-view owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name,
        "DIMENSION",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(f"failed to select model dimension {name}: {selection_name!r}")
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    matches = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(item, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


def _set_spherical_reference(adapter: Any, annotation: Any, *, label: str) -> None:
    """Print a model radius as the ASME spherical reference ``(SR6.7)``.

    The radius is read-only: a spherical cap of the printed dome height on the
    toleranced end diameter already fixes it.  Whatever radius prefix the
    display carries is kept behind the ``(S``; the readback proves it stuck.
    """
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    prefix = "(S" + existing
    display.SetText(1, prefix)
    display.SetText(2, ")")  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    _telemetry.info(
        f"{label}: spherical reference prefix {existing!r} -> {applied[0]!r}, "
        f"suffix {applied[1]!r}"
    )
    if applied != (prefix, ")"):
        raise RuntimeError(f"failed to mark {label} as a spherical reference: {applied}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crankshaft source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "Pinion Pin Hole Process",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "Pinion Pin Hole Process",
        ),
    )
    # The note prints the property's words re-wrapped; a part built from a
    # different process text must not be printed with this one.
    pinion_process = properties["Pinion Pin Hole Process"].replace("\r", "")
    if pinion_process != CRANKSHAFT_PIN_HOLE_PROCESS:
        raise RuntimeError(
            f"crankshaft Pinion Pin Hole Process {pinion_process!r} != "
            f"crank_pinion_spec {CRANKSHAFT_PIN_HOLE_PROCESS!r}"
        )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crankshaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crankshaft; domed nose; hub taper pin; punched fiducial",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    native_side = _early_bound(side, "IView")
    native_side.Angle = SIDE_VIEW_ANGLE
    if abs(math.remainder(float(native_side.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to lay the crankshaft profile horizontal")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="crank-end"
    )
    side_annotations = curate_view_dimensions(
        adapter, side, keep=SIDE_KEEP, view_label="side"
    )
    moved = [
        _move_dimension(
            adapter,
            annotation,
            side,
            DIAMETER_POSITIONS[dimension_name(adapter, annotation)],
            source_view=end,
        )
        for annotation in end_annotations
    ]
    annotations = [*moved, *side_annotations]
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one crankshaft {name} reference dimension")
        if name in SPHERICAL_DIMENSIONS:
            _set_spherical_reference(adapter, matches[0], label=f"crankshaft {name}")
            continue
        set_reference_dimension(adapter, matches[0], label=f"crankshaft {name}")

    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; the end view gets the
    # ASME centre mark, the side view marks the cross-hole circle.
    for view, label in ((end, "end"), (side, "side")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
    add_view_centerline(
        adapter,
        side,
        label="crankshaft turning axis",
        face=_visible_cylindrical_face(adapter, side, JOURNAL_DIA),
    )

    cross_hole = add_native_hole_callout(
        adapter,
        side,
        callout_xy=HOLE_CALLOUT_XY,
        label="tapered-pin cross-hole",
        edge=_visible_cross_hole_edge(adapter, side, _PIN_HOLE_DIA),
        process=CROSS_HOLE_PROCESS,
    )
    _set_callout_below(cross_hole, CROSS_HOLE_CALLOUT, "tapered-pin cross-hole")
    pinion_note = add_attached_note(
        adapter,
        side,
        text=CRANKSHAFT_PIN_HOLE_PROCESS,
        entity=_visible_cross_hole_edge(adapter, side, PINION_PIN_DIA),
        note_xy=PINION_PIN_NOTE_XY,
        label="16T retention-pin transfer",
    )
    _place_note_text_in_field(
        drawing_model,
        pinion_note,
        PINION_PIN_NOTE_FIELD,
        hole=PINION_PIN_HOLE_WINDOW,
        label="16T retention-pin transfer",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing_journal"),
        label="crankshaft bearing-journal finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # The end view's hidden lines show the cross-hole running across the
    # dome end, which clocks the punched fiducial to it (rule 7: a cross-hole
    # through a turned part).  Re-asserted last so the export regenerates the
    # dashed edges after every annotation (layout-tuning refusal e).
    set_hidden_lines_visible(adapter, end)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crankshaft Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
