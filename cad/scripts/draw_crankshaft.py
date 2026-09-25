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
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
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
from _hole_spec import blind_cut_dia_mm, drill_process
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
    SHAFT_DOME_HEIGHT,
    SHAFT_LENGTH,
    SPHERICAL_DIMENSIONS,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from build_crankshaft import PINION_PIN_DIA, PINION_PIN_STATION_Y
from crank_pinion_spec import CRANKSHAFT_PIN_HOLE_PROCESS
from crank_pinion_spec import PIN_HOLE_SPEC as PINION_PIN_HOLE_SPEC
from crankshaft_notes import CROSS_HOLE_CALLOUT, PINION_PIN_NOTE
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
# dimension line ~5 mm below it.  The first row carries the two short ends:
# the 2.0 dome height at the far left and the 16T pin hole's reference
# station at the far right, where no other baseline reaches.
_ROW_Y = (0.150, 0.137, 0.124, 0.111, 0.098, 0.085)
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
    # Its 5.8-mm span is too short for its text, which sits outside to the
    # right of the far end.
    "PinionPinHoleStation": (FAR_END_X + 0.012, _ROW_Y[0]),
    "JournalInboardStation": ((JOURNAL_END_X + FAR_END_X) / 2.0 + 0.004, _ROW_Y[1]),
    "JournalOutboardStation": ((JOURNAL_START_X + FAR_END_X) / 2.0 - 0.020, _ROW_Y[2]),
    "PinHoleStation": ((PIN_X + FAR_END_X) / 2.0, _ROW_Y[3]),
    "Depth": ((DOME_ROOT_X + FAR_END_X) / 2.0, _ROW_Y[4]),
    "OverallLength": ((DOME_TIP_X + FAR_END_X) / 2.0, _ROW_Y[5]),
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
# The 16T retention-pin hole, 2.9 from the far end.  Its size is the native
# Hole Wizard callout (the 1/8 drill first) and its station the reference
# PinionPinHoleStation above, both read from the model; the match-drill
# prose reads under the size, as on the MHA-024 cross-hole.  The text is
# centred in the free field above the far-end seat, right of the Ø11.388
# text and left of the isometric, so its leader runs down to the hole
# without crossing a dimension.
PINION_PIN_X = _sheet_x(PINION_PIN_STATION_Y)
PINION_PIN_PROCESS = drill_process(PINION_PIN_HOLE_SPEC)
PINION_HOLE_CALLOUT_XY = (0.325, 0.236)
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
    pinion_hole = add_native_hole_callout(
        adapter,
        side,
        callout_xy=PINION_HOLE_CALLOUT_XY,
        label="16T retention-pin cross-hole",
        edge=_visible_cross_hole_edge(adapter, side, PINION_PIN_DIA),
        process=PINION_PIN_PROCESS,
    )
    _set_callout_below(pinion_hole, PINION_PIN_NOTE, "16T retention-pin cross-hole")
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
