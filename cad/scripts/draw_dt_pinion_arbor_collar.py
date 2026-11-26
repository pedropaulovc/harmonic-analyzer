r"""Create the curated machinist drawing for the pinion-arbor collar (R1a).

A plain turned steel collar: Ø.59 x .66, a drilled Ø5/16 slide bore, and one
1/16 in spring-pin hole through both walls at the length's centre.  The
profile lies as it sits in the lathe (axis horizontal) and looks along the
pin hole, so the hole is a solid circle located from the right-hand end face;
the end view to its left owns the bore callout, and its OD moves onto the
profile (drawing-guidelines.md rule 11 (turned parts read like the lathe): diameters on the side view).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_arbor_collar.py dt-pinion-arbor-collar
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
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
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import drilled_limits, limits
from dt_pinion_arbor_collar_spec import (
    ARBOR_NUMBER,
    BORE,
    COLLAR_LEN,
    COLLAR_OD,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_HOLE,
    PIN_HOLE_BAND,
    PIN_HOLE_CALLOUT,
    PIN_HOLE_Z,
    PIN_NUMBER,
    UNIT,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["dt_pinion_arbor_collar"]
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

SHEET_SCALE = (3.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # model mm -> sheet m

# Third angle: the profile turns *Top by -90 deg, so model +Z runs LEFT and
# the end face the collar is dimensioned from (z 0) is the profile's right
# end.  The end view looks along -Z from the +Z end, so it projects on the
# LEFT of the profile, sharing its axis height.
PROFILE_CENTER = (0.205, 0.165)
END_CENTER = (0.085, PROFILE_CENTER[1])
ISO_CENTER = (0.345, 0.205)

_PROFILE_RIGHT = PROFILE_CENTER[0] + COLLAR_LEN * _S / 2.0  # z 0 face, 0.235
_PROFILE_TOP = PROFILE_CENTER[1] + COLLAR_OD * _S / 2.0  # 0.1875
_PROFILE_BOTTOM = PROFILE_CENTER[1] - COLLAR_OD * _S / 2.0  # 0.1425

# The bore is a solid circle only end-on, so its callout stays there (a
# standard drilled hole is defined by its callout, drawing-guidelines.md rule 12 (hole and slot callouts say what to do)); its leader runs
# up-left, clear of the OD centre mark.
END_KEEP = {
    "BoreDia": (0.040, 0.210),
    "CollarOd": (0.040, 0.120),  # moved onto the profile below
}
# Length and pin station under the profile, the shorter station nearer the
# part, both from the right end face; the pin hole's leader runs up-left to
# its circle (round 1 review: with the station above the profile the leader
# crossed its dimension line); the OD right of the part.
PROFILE_KEEP = {
    "Depth": (PROFILE_CENTER[0], _PROFILE_BOTTOM - 0.022),
    "PinHoleCz": (_PROFILE_RIGHT - 0.012, _PROFILE_BOTTOM - 0.010),
    "PinHoleDia": (0.160, _PROFILE_TOP + 0.030),
}
OD_ON_PROFILE = (_PROFILE_RIGHT + 0.025, PROFILE_CENTER[1])
# The bore prints the model's three-place Ø.313 under DRILLED HOLES, so its
# callout names no fractional drill: a named 5/16 drill would be .3125, and
# the rounded decimal under it read as two controlling numbers (rule 3).  The
# pin hole's +.0025/0 band is the spring pin's (B18.8.2's recommended hole):
# its callout is the shared one, the pin as its own gauge (fit audit F15).
DIMENSION_CALLOUTS = {
    "BoreDia": f"DRILL THRU\nSLIDES ON {ARBOR_NUMBER}",
    "PinHoleDia": PIN_HOLE_CALLOUT,
}

# Feature requirements (package:features; the drilled_block adapter's kinds):
# the collar in its model frame, the bore axis along +Z from the z 0 end
# face, the spring-pin hole along Y through both walls at the centred
# station.  The declarations print nothing; each band is the one the sheet
# prints (DRAWING_PRECISION_BY_NAME places, the title block's rows, the pin
# hole's own +.0025/.0000).
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_dt_pinion_arbor_collar"
_GEOM = "dt_pinion_arbor_collar_geometry"
_FRAME = ("build_dt_pinion_arbor_collar", "__frame__")
part_metadata(
    model_sources=(_FRAME, (_GEOM, "COLLAR_OD"), (_GEOM, "COLLAR_LEN"), (_GEOM, "BORE")),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, (_FRAME,)),
        "outward": ([0.0, 0.0, -1.0], (_FRAME,)),
    },
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), COLLAR_LEN),),
    requirements=("plane", "length"),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": COLLAR_LEN},
            (_FRAME, (_GEOM, "COLLAR_LEN")),
        ),
        "outward": ([0.0, 0.0, 1.0], (_FRAME,)),
        "length": (
            limits(COLLAR_LEN, _P["Depth"], unit=UNIT),
            ((_GEOM, "COLLAR_LEN"), "UNIT", "DRAWING_PRECISION_BY_NAME"),
        ),
        "length_nominal": (COLLAR_LEN, ((_GEOM, "COLLAR_LEN"),)),
        "length_from": ("datum_end", ((_GEOM, "COLLAR_LEN"),)),
    },
    precision={"length": _P["Depth"]},
)
requirement(
    "outer",
    kind="outside_cylinder",
    faces=(CylinderFace(COLLAR_OD),),
    requirements=("dia",),
    fields={
        "at": ([0.0, 0.0, 0.0], (_FRAME,)),
        "axis": ([0.0, 0.0, 1.0], (_FRAME,)),
        "dia": (
            limits(COLLAR_OD, _P["CollarOd"], unit=UNIT),
            ((_GEOM, "COLLAR_OD"), "UNIT", "DRAWING_PRECISION_BY_NAME"),
        ),
        "nominal_dia": (COLLAR_OD, ((_GEOM, "COLLAR_OD"),)),
        "length_nominal": (COLLAR_LEN, ((_GEOM, "COLLAR_LEN"),)),
    },
    precision={"dia": _P["CollarOd"]},
)
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(BORE),),
    requirements=("dia", "thru"),
    fields={
        "at": ([0.0, 0.0, 0.0], (_FRAME,)),
        "axis": ([0.0, 0.0, 1.0], (_FRAME,)),
        "dia": (
            drilled_limits(BORE, _P["BoreDia"], unit=UNIT),
            ((_GEOM, "BORE"), "UNIT", "DRAWING_PRECISION_BY_NAME"),
        ),
        "nominal_dia": (BORE, ((_GEOM, "BORE"),)),
        "thru": (True, ((_SELF, "DIMENSION_CALLOUTS"),)),
        "process": ("drill", ((_SELF, "DIMENSION_CALLOUTS"),)),
        "callout": (DIMENSION_CALLOUTS["BoreDia"], ((_SELF, "DIMENSION_CALLOUTS"),)),
        "mates": (ARBOR_NUMBER, ("ARBOR_NUMBER",)),
    },
    precision={"dia": _P["BoreDia"]},
)
requirement(
    "pin_hole",
    kind="hole",
    faces=(CylinderFace(PIN_HOLE),),
    requirements=("dia", "thru", "station"),
    fields={
        "at": ([0.0, COLLAR_OD / 2.0, PIN_HOLE_Z], (_FRAME, (_GEOM, "PIN_HOLE_Z"))),
        "axis": ([0.0, -1.0, 0.0], (_FRAME, ("build_dt_pinion_arbor_collar", "build"))),
        "dia": (
            limits(PIN_HOLE, _P["PinHoleDia"], PIN_HOLE_BAND, unit=UNIT),
            ("PIN_HOLE", "PIN_HOLE_BAND", "UNIT", "DRAWING_PRECISION_BY_NAME"),
        ),
        "nominal_dia": (PIN_HOLE, ("PIN_HOLE",)),
        "thru": (True, ((_SELF, "DIMENSION_CALLOUTS"),)),
        "process": ("drill", ((_SELF, "DIMENSION_CALLOUTS"),)),
        "callout": (
            DIMENSION_CALLOUTS["PinHoleDia"],
            ((_SELF, "DIMENSION_CALLOUTS"),),
        ),
        "mates": (PIN_NUMBER, (("dt_pinion_arbor_pin_spec", "PIN_NUMBER"),)),
        "station": (
            limits(PIN_HOLE_Z, _P["PinHoleCz"], unit=UNIT),
            ((_GEOM, "PIN_HOLE_Z"), "UNIT", "DRAWING_PRECISION_BY_NAME"),
        ),
        "station_nominal": (PIN_HOLE_Z, ((_GEOM, "PIN_HOLE_Z"),)),
        "station_from": ("datum_end", ((_GEOM, "PIN_HOLE_Z"),)),
    },
    precision={"dia": _P["PinHoleDia"], "station": _P["PinHoleCz"]},
)
# swAnnotationType_e.swCenterMarkSym.  The template centre-marks a view's
# circles as it is placed; an unconditional auto_center_marks printed a second
# identical mark over the end view's (layout audit duplicate-annotation,
# DetailItem347/350 on r0 of #1697; the dt_pinion_cam_pin precedent), so each
# view gets one only if the template did not, and proves exactly one.
_CENTER_MARK_ANNOTATION = 13


def _ensure_one_center_mark(adapter: Any, view: Any, size: float, label: str) -> None:
    """Leave exactly one centre mark in ``view``, adding it only if missing."""
    native = _early_bound(view, "IView")
    if not (native.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()):
        if not auto_center_marks(adapter, view, holes=True, size=size):
            raise RuntimeError(f"failed to add the centre mark to the {label}")
    found = len(native.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ())
    if found != 1:
        raise RuntimeError(f"expected 1 centre mark in the {label}, found {found}")


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
        raise RuntimeError(f"failed to select model dimension {name}: {selection_name!r}")
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


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-arbor-collar source", adapter.open_model(str(SOURCE)))
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
        unit=part_drawing_unit("dt-pinion-arbor-collar"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Arbor Collar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion arbor retention collar; spring-pinned; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=(3, 1))
    # Looking along model Y presents the pin hole as a true circle; -90 deg
    # lays the axis horizontal, as the collar sits in the lathe.
    profile = place_view(adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=(3, 1))
    native_profile = _early_bound(profile, "IView")
    native_profile.Angle = -math.pi / 2.0
    if abs(math.remainder(float(native_profile.Angle) + math.pi / 2.0, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to orient the collar profile horizontally")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (end, profile, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="collar end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="collar profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    od_donors = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) == "CollarOd"
    ]
    if len(od_donors) != 1:
        raise RuntimeError("expected one collar OD donor dimension")
    moved_od = _move_dimension(
        adapter, od_donors[0], profile, OD_ON_PROFILE, source_view=end
    )
    end_annotations = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) != "CollarOd"
    ]
    annotations = [*end_annotations, *profile_annotations, moved_od]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _ensure_one_center_mark(adapter, end, 0.0025, "collar end view")
    _ensure_one_center_mark(adapter, profile, 0.0015, "collar profile pin hole")
    # The turning axis, picked on the OD face between the pin hole and the
    # left end so the pick cannot land on the hole.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0] - 0.015, PROFILE_CENTER[1] + COLLAR_OD * _S / 4.0),
        label="pinion arbor collar axis centerline",
    )

    add_property_linked_note(adapter, "Isometric View Note", 0.320, 0.160)
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Arbor Collar Manufacturing Drawing",
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
