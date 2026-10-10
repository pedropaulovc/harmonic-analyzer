r"""Create the curated machinist drawing for the rocker pivot shaft (MHA-CH-005)."""

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
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from ch_pivot_shaft_spec import (
    DOME_CALLOUT,
    DOME_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLAT_LENGTH,
    LENGTH_CALLOUT,
    NORTH_FLAT_STATION,
    SHAFT_DIA,
    SURFACE_FINISHES,
)
from rocker_bank_layout import PIVOT_SHAFT_LENGTH
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view, view_name


SPEC = DRAWINGS_BY_NAME["ch_pivot_shaft"]
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

SHEET_SCALE = (1.0, 1.0)
# The side view is "*Right": the axis horizontal, as the bar sits in the lathe.
# Model -Z runs to the sheet's right: the north end (the part origin) is on
# the LEFT, the plain cut-to-fit end on the right. It carries the diameter,
# the length and the south flat's station (policy rule 7), all authored on
# Right-plane sketches, so the view imports them natively, both flats edge-on
# on its top silhouette. An end view would carry nothing, so this sheet has
# none; the north end's flat and dome go to DETAIL A.
PROFILE_CENTER = (0.150, 0.190)
_MM = SHEET_SCALE[0] / 1000.0
# The view centres on the bar's bounding box, domes included.
_OVERALL = PIVOT_SHAFT_LENGTH + 2.0 * DOME_HEIGHT
NORTH_END_X = PROFILE_CENTER[0] - (_OVERALL / 2.0 - DOME_HEIGHT) * _MM
SOUTH_END_X = NORTH_END_X + PIVOT_SHAFT_LENGTH * _MM
SHAFT_FLANK_Y = PROFILE_CENTER[1] + SHAFT_DIA * _MM / 2.0
# The 160 shaft's isometric silhouette is a slender bar taller than the
# drawable band at 1:1, so the pictorial renders at 1:2 and says so. It
# stands in the open field under the profile, right of the notes (x <= 0.105)
# and left of the title block (x 0.216), so DETAIL A can take the right side.
ISO_CENTER = (0.165, 0.115)
ISO_SCALE = (1, 2)
ISO_NOTE_XY = (0.135, 0.092)

# A short dimension's callout is far wider than the span it measures, so its
# text stands OUTSIDE the witness pair, clear of both lines, and the dimension
# line runs out under it: centred between them, both witnesses crossed "1.5
# BOTH ENDS" (r743-3 eye pass). Callout text runs ~2.75 mm a character at the
# template's dimension height (r743-3 render: "BOTH ENDS" 24.5 mm).
CALLOUT_CHAR_WIDTH = 0.00275
CALLOUT_WITNESS_GAP = 0.003


def _left_of_witness(witness_x: float, callout: str) -> float:
    """Text centre x that ends a callout CALLOUT_WITNESS_GAP left of a witness."""
    return witness_x - CALLOUT_WITNESS_GAP - len(callout) * CALLOUT_CHAR_WIDTH / 2.0


# The flats' length and across-flat print once, on the north flat, as 2X:
# the south flat is the same cut (FlatProfile), placed by its own station.
FLATS_CALLOUT = "2X"

PROFILE_KEEP = {
    # Under the bar, centred: the REF span the cut-to-fit callout governs.
    "ShaftLength": (PROFILE_CENTER[0], 0.158),
    # The diameter stands clear of the plain end it measures.
    "ShaftDia": (SOUTH_END_X + 0.018, PROFILE_CENTER[1]),
    # The south flat's station from the north end, across the whole bar.
    "SouthFlatStation": (PROFILE_CENTER[0], 0.242),
}

# DETAIL A: the north flat (5.0 x 0.5 deep), its station and the dome are
# 1.5-5 mm features. At 1:1 their dimensions crammed the north end, text on
# the witness lines and against the dome (PR #1317 eye pass), so a native 5:1
# detail carries them. The fence centres on the axis midway between the dome
# tip and the flat's far end and takes in both; the detail stands right of
# the profile's diameter callout (x <= 0.263), clear of the right border
# (0.419) with its dimensions.
DETAIL_SCALE = (5, 1)
DETAIL_RADIUS_MM = 6.0
DETAIL_CENTER = (0.345, 0.185)
DETAIL_FENCE_Z_MM = (DOME_HEIGHT - (NORTH_FLAT_STATION + FLAT_LENGTH / 2.0)) / 2.0
_DETAIL_MM = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
_DETAIL_FENCE_R = DETAIL_RADIUS_MM * _DETAIL_MM
# The dome tip (on the axis) and the flat's far rim corner both sit inside.
_FLAT_FAR_Z_MM = -(NORTH_FLAT_STATION + FLAT_LENGTH / 2.0)
if DETAIL_RADIUS_MM <= abs(DOME_HEIGHT - DETAIL_FENCE_Z_MM) or DETAIL_RADIUS_MM <= math.hypot(
    _FLAT_FAR_Z_MM - DETAIL_FENCE_Z_MM, SHAFT_DIA / 2.0
):
    raise AssertionError("DETAIL A's fence must take in the dome tip and the whole flat")
# The label anchors at its top centre, under the dome's callout.
DETAIL_LABEL_XY = (DETAIL_CENTER[0], DETAIL_CENTER[1] - _DETAIL_FENCE_R - 0.027)


def _detail_x(z_mm: float) -> float:
    """Sheet x of part station z in the detail: model -Z runs to the right."""
    return DETAIL_CENTER[0] - (z_mm - DETAIL_FENCE_Z_MM) * _DETAIL_MM


DETAIL_KEEP = {
    # The station and the flat's length stack above the fence, each centred
    # over the span it measures: the station from the end face to the flat's
    # centre, the length over the flat.
    "NorthFlatStation": (
        (_detail_x(0.0) + _detail_x(-NORTH_FLAT_STATION)) / 2.0,
        DETAIL_CENTER[1] + _DETAIL_FENCE_R + 0.008,
    ),
    "FlatLength": (
        _detail_x(-NORTH_FLAT_STATION),
        DETAIL_CENTER[1] + _DETAIL_FENCE_R + 0.024,
    ),
    # Right of the fence, on the axis: its witnesses run along the body, not
    # over the dome.
    "FlatAF": (DETAIL_CENTER[0] + _DETAIL_FENCE_R + 0.014, DETAIL_CENTER[1]),
    # Under the fence, left of the dome tip's witness: a short .X height the
    # "BOTH ENDS" callout makes a 2X statement.
    "DomeHeight": (
        _left_of_witness(_detail_x(DOME_HEIGHT), DOME_CALLOUT),
        DETAIL_CENTER[1] - _DETAIL_FENCE_R - 0.010,
    ),
    # Up-left of the fence: the leader drops onto the dome's arc.
    "Radius": (
        DETAIL_CENTER[0] - _DETAIL_FENCE_R - 0.016,
        DETAIL_CENTER[1] + 0.022,
    ),
}
# Ra on the running face: the body the 20 hubs rock on and the two ears
# journal. A revolved flank is a drawing SILHOUETTE, not a model edge, so the
# pick names that entity type; the straight leader keeps off the geometry.
# Note text height, as on the other part sheets: at the template default the
# symbols printed ~18 mm tall (r743-2R render).
FINISH_CHAR_HEIGHT = 0.0025
BEARING_FINISH_EDGE = (PROFILE_CENTER[0] + 0.030, SHAFT_FLANK_Y)
BEARING_FINISH_SYMBOL = (BEARING_FINISH_EDGE[0], 0.206)


def _north_end_detail(adapter: Any, profile: Any) -> Any:
    """A native 5:1 detail of the north end: its dome and its flat."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(profile, "IView")
    if not drawing.ActivateView(view_name(adapter, profile)):
        raise RuntimeError("failed to activate the north-end detail's parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        profile,
        (0.0, 0.0, DETAIL_FENCE_Z_MM / 1000.0),
        label="north-end detail centre",
    )
    radius = DETAIL_RADIUS_MM * SHEET_SCALE[0] / 1000.0
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
        raise RuntimeError("failed to create the north-end detail fence")
    detail = drawing.CreateDetailViewAt4(
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
        raise RuntimeError("failed to create the north-end detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("the north-end detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position the north-end detail")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position the north-end detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"the north-end detail label did not persist: {actual}")
    return detail


def _set_spherical_reference(adapter: Any, annotation: Any, *, label: str) -> None:
    """Print the dome's model radius as the ASME spherical reference ``(SR4.1)``.

    The radius is read-only: a spherical cap of the printed dome height on the
    toleranced diameter already fixes it. Whatever radius prefix the display
    carries is kept behind the ``(S``; the readback proves it stuck (the
    MHA-DT-001 crankshaft's dome prints the same way).
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

    check("open pivot-shaft source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pivot Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pivot shaft; rocker bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    profile = place_view(adapter, str(SOURCE), "*Right", *PROFILE_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (profile, iso):
        set_hidden_lines_removed(adapter, view)

    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail = _north_end_detail(adapter, profile)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="north-end detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter,
        [*profile_annotations, *detail_annotations],
        DRAWING_PRECISION_BY_NAME,
    )
    set_dimension_callouts(
        adapter,
        detail_annotations,
        {"FlatLength": FLATS_CALLOUT, "FlatAF": FLATS_CALLOUT},
    )
    set_dimension_callouts(adapter, detail_annotations, {"DomeHeight": DOME_CALLOUT})
    radius_annotations = [
        annotation
        for annotation in detail_annotations
        if dimension_name(adapter, annotation) == "Radius"
    ]
    if len(radius_annotations) != 1:
        raise RuntimeError("north-end detail does not carry exactly one dome radius")
    _set_spherical_reference(adapter, radius_annotations[0], label="pivot shaft dome radius")
    # #743 PR2: the plain end is cut to fit the installed brackets, so the
    # modelled length prints as a REFERENCE value and the callout under it is
    # the requirement. Keyed on the parametric name.
    length_annotations = [
        annotation
        for annotation in profile_annotations
        if dimension_name(adapter, annotation) == "ShaftLength"
    ]
    if len(length_annotations) != 1:
        raise RuntimeError("profile view does not carry exactly one shaft length")
    set_reference_dimension(adapter, length_annotations[0], label="pivot shaft length")
    set_dimension_callouts(adapter, length_annotations, {"ShaftLength": LENGTH_CALLOUT})

    # The axis says which pairs of lines are diameters and is what the shop
    # indicates the bar on. The face pick sits mid-body, clear of every
    # placed annotation.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0] - 0.030, PROFILE_CENTER[1]),
        label="pivot shaft axis centerline",
    )
    add_surface_finish(
        adapter,
        profile,
        edge_xy=BEARING_FINISH_EDGE,
        entity_type="SILHOUETTE",
        symbol_xy=BEARING_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bearing"),
        label="pivot bearing finish",
        char_height=FINISH_CHAR_HEIGHT,
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127); 0.020 clears it, and the
    # audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.085)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pivot Shaft Manufacturing Drawing",
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
