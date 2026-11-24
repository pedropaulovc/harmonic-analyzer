r"""Create the manufacturing drawing for the transgear rear bushing (MHA-PD-24).

A turned brass ring: Ø.35 O.D. over a reamed Ø.126 bore, its length printed
to the band that holds the shim count, under the stack callout.  The profile
lies as it sits in the lathe (axis horizontal): the ``*Top`` view turned a
quarter turn, so model +Z runs LEFT and the arm face (z 0) is the profile's
right end, the sleeve face its left end.  The sleeve face carries its thrust
finish and the reason, the length sits under the profile and the O.D. moves
onto the profile (drawing-guidelines.md rule 11 (turned parts read like the lathe): diameters on the side view).  The end view to its left
(third angle, looking along -Z from the +Z end) keeps the bore, a solid
circle only end-on.  The sheet prints decimal inch (the part's
``drawing_unit``); the model keeps its millimetre nominals.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_transgear_rear_bushing.py pd-transgear-rear-bushing
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _printed_limits import limits
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from pd_transgear_pin_spec import PIN_NUMBER
from pd_transgear_rear_bushing_spec import (
    BORE_CALLOUT,
    BORE_DIA,
    BORE_DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ISOMETRIC_VIEW_SCALE,
    LENGTH,
    LENGTH_CALLOUT,
    OD,
    SURFACE_FINISHES,
    THRUST_FACE_CAPTION,
    UNIT,
    WALL_WORST,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_rear_bushing"]
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

# A Ø9 x 6 ring: 5:1 keeps the three sizes, the stack callout and the thrust
# face's finish legible on the landscape sheet.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # model mm -> sheet m
# The *Top view turned -90 degrees: model +Z runs to paper-left.
PROFILE_ANGLE = -math.pi / 2.0
PROFILE_CENTER = (0.200, 0.170)
# Third angle: the end view seen from the +Z end sits LEFT of the profile, on
# its axis.
END_CENTER = (0.090, PROFILE_CENTER[1])
ISO_CENTER = (0.340, 0.190)

_PROFILE_ARM_X = PROFILE_CENTER[0] + LENGTH * _S / 2.0  # z 0, right end
_PROFILE_SLEEVE_X = PROFILE_CENTER[0] - LENGTH * _S / 2.0  # z LENGTH, left end
_PROFILE_TOP = PROFILE_CENTER[1] + OD * _S / 2.0
_PROFILE_BOTTOM = PROFILE_CENTER[1] - OD * _S / 2.0

# The bore stays on the end view, where it is a circle: a reamed through
# hole, fully defined by its callout (drawing-guidelines.md rule 12 (hole and slot callouts say what to do)), it needs no section, and the
# profile is hidden-lines-removed (a dimension never lands on a hidden line).
# The O.D. arrives there too and is moved onto the profile below.  The bore's
# callout is centred 6 mm right of where its 30-character block stood: its
# mate row is 32 characters.
END_KEEP = {
    "BoreDia": (0.066, 0.225),
    "RingOd": (0.045, 0.120),  # donor: moved onto the profile
}
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "RingLength": LENGTH_CALLOUT,
}
# The length under the profile.  Its block is wider than the 6.0 between its
# extension lines, so it stands off to the right, under the O.D. dimension,
# where no extension line runs through it.
PROFILE_KEEP = {
    "RingLength": (_PROFILE_ARM_X + 0.045, _PROFILE_BOTTOM - 0.022),
}
OD_ON_PROFILE = (_PROFILE_ARM_X + 0.040, PROFILE_CENTER[1])

# The thrust face's pick lies on its edge line between the bore and O.D.
# radii; its symbol stands above-left, clear of every dimension, and the
# reason sits just above the symbol.
_FACE_PICK_UP = PROFILE_CENTER[1] + (BORE_DIA + OD) / 4.0 * _S
FACE_FINISHES = {
    "sleeve_face": (
        (_PROFILE_SLEEVE_X, _FACE_PICK_UP),
        (_PROFILE_SLEEVE_X - 0.022, _PROFILE_TOP + 0.014),
    ),
}
THRUST_CAPTION_XY = (
    FACE_FINISHES["sleeve_face"][1][0] - 0.009,
    FACE_FINISHES["sleeve_face"][1][1] + 0.0185,
)
ISO_NOTE_XY = (0.315, 0.145)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (build_pd_transgear_rear_bushing: one extrusion along model +Z).  The
# sleeve's thrust face at z = LENGTH is the datum end the length runs from,
# so the bar's faced end takes the finish; the arm face at z = 0 is the far
# end.  The O.D. takes the title block's .XX row and the length its .XXX
# row.  The bore prints the reamer's size, REAM and its acceptance by the
# MHA-PD-23 pin, no band: its ``dia`` field is the spec's ANALYSIS band
# (what the reamer is modelled to cut), carried only because the traveler's
# adapter needs a band to bind; it is not a requirement and no step quotes
# it as an acceptance.  Each ``span`` is a diameter's model-Z extent.
# The declarations print nothing.
# The sheet prints no manufacturing note: every requirement is a dimension,
# its band or its native callout, so the feature manifest's notes are empty.
DRAWING_NOTES = ""
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pd_transgear_rear_bushing"
part_metadata(
    model_sources=("LENGTH", "OD", "BORE_DIA"),
    precision_sources=("DRAWING_PRECISION_BY_NAME",),
)
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), LENGTH),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": LENGTH}, ("LENGTH",)),
        "outward": ([0.0, 0.0, 1.0], ("LENGTH",)),
    },
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("length",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("LENGTH",)),
        "outward": ([0.0, 0.0, -1.0], ("LENGTH",)),
        "length": (
            limits(LENGTH, _P["RingLength"], unit=UNIT),
            ("LENGTH", "UNIT", (_SELF, "PROFILE_KEEP")),
        ),
        "length_nominal": (LENGTH, ("LENGTH",)),
        "length_from": ("datum_end", ((_SELF, "PROFILE_KEEP"),)),
        "callout": (LENGTH_CALLOUT, ("LENGTH_CALLOUT",)),
    },
    precision={"length": _P["RingLength"]},
)
requirement(
    "outer",
    kind="diameter",
    faces=(CylinderFace(OD),),
    requirements=("dia",),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("OD",)),
        "at": ([0.0, 0.0, 0.0], ("OD",)),
        "span": ([0.0, LENGTH], ("LENGTH",)),
        "dia": (
            limits(OD, _P["RingOd"], unit=UNIT),
            ("OD", "UNIT", (_SELF, "OD_ON_PROFILE")),
        ),
        "dia_nominal": (OD, ("OD",)),
    },
    precision={"dia": _P["RingOd"]},
)
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(BORE_DIA),),
    # ``dia`` stays a traveler requirement, as MHA-PD-18's pin bore keeps
    # it: prechips' turned-bush adapter refuses a bore without one
    # ("bore.dia: missing drawing requirement"; the fit stack had dropped
    # it with the printed band, so the traveler no longer rendered).
    requirements=("dia", "thru", "mate"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("BORE_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("BORE_DIA",)),
        "span": ([0.0, LENGTH], ("LENGTH",)),
        "dia": (
            limits(BORE_DIA, _P["BoreDia"], BORE_DIA_BAND, unit=UNIT),
            ("BORE_DIA", "BORE_DIA_BAND", "UNIT", (_SELF, "END_KEEP")),
        ),
        "nominal_dia": (BORE_DIA, ("BORE_DIA",)),
        "thru": (True, ("BORE_CALLOUT",)),
        "process": ("ream", ("BORE_CALLOUT",)),
        "wall_min": (WALL_WORST, ("WALL_WORST",)),
        "mate": (PIN_NUMBER, (("pd_transgear_pin_spec", "PIN_NUMBER"), "BORE_CALLOUT")),
        "callout": (BORE_CALLOUT, ("BORE_CALLOUT",)),
    },
    precision={"dia": _P["BoreDia"]},
)


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a model dimension to the projection that shows its extension lines."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, source_view)):
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
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    drawing.DragModelDimension(
        view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0
    )
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


# swCenterMarkStyle_e.swCenterMark_Single: AutoInsertCenterMarks2 marks the
# concentric O.D. and bore circles separately, one mark printed over the other.
CENTER_MARK_SINGLE = 2


def _mark_bore_axis(adapter: Any, view: Any) -> None:
    """One centre mark on the bore, picked on its -X point."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the bushing end view")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        "",
        "EDGE",
        END_CENTER[0] - BORE_DIA * _S / 2.0,
        END_CENTER[1],
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError("failed to select the bushing bore circle")
    mark = drawing.InsertCenterMark3(CENTER_MARK_SINGLE, False, False)
    draw.ClearSelection2(True)
    if mark is None:
        raise RuntimeError("failed to centre-mark the bushing bore")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-rear-bushing source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Rear Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear cluster rear bushing; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    profile = place_view(
        adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=VIEW_SCALE
    )
    native_profile = _early_bound(profile, "IView")
    native_profile.Angle = PROFILE_ANGLE
    if (
        abs(math.remainder(float(native_profile.Angle) - PROFILE_ANGLE, 2.0 * math.pi))
        > 1e-9
    ):
        raise RuntimeError("failed to lay the bushing profile horizontal")
    drawing_model.EditRebuild3()
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISOMETRIC_VIEW_SCALE
    )
    for view in (end, profile, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="bushing end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="bushing profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    od_donors = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) == "RingOd"
    ]
    if len(od_donors) != 1:
        raise RuntimeError("expected one bushing O.D. donor dimension")
    moved_od = _move_dimension(
        adapter, od_donors[0], profile, OD_ON_PROFILE, source_view=end
    )
    end_annotations = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) != "RingOd"
    ]
    annotations = [*end_annotations, *profile_annotations, moved_od]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the bore's band are authored on the part; the sheet only proves the
    # import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _mark_bore_axis(adapter, end)
    # The turning axis, picked on the O.D. face above it.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0], PROFILE_CENTER[1] + OD * _S / 4.0),
        label="rear bushing axis centerline",
    )
    pick, symbol = FACE_FINISHES["sleeve_face"]
    add_surface_finish(
        adapter,
        profile,
        edge_xy=pick,
        symbol_xy=symbol,
        control=surface_finish_by_key(SURFACE_FINISHES, "sleeve_face"),
        label="bushing thrust face finish",
        char_height=0.0025,
    )
    if add_note(adapter, THRUST_FACE_CAPTION, *THRUST_CAPTION_XY) is None:
        raise RuntimeError("failed to add the bushing thrust face caption")

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Rear Bushing Manufacturing Drawing",
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
