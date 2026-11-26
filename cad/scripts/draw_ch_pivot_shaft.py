r"""Create the curated machinist drawing for the rocker pivot shaft (MHA-CH-05)."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)

from _machinist_review_mode import MachinistReviewMode
import ch_pivot_shaft_spec as shaft
import rocker_bank_layout as bank
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits as _band
from _gtol_planar import PlanarFace
from _gtol_sphere import SphereFace
from _check import check
from _com import _early_bound, _read_member
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
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _supplier_dimensions import supplier_reference_dimension
import _telemetry
from ch_pivot_shaft_spec import (
    DOME_CALLOUT,
    DOME_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLAT_LENGTH,
    FLAT_STATION_CALLOUT,
    NORTH_FLAT_STATION,
    SHAFT_DIA,
    SHAFT_DIA_FRACTION_DENOMINATOR,
)
from rocker_bank_layout import PIVOT_SHAFT_LENGTH


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

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
# the LEFT, the south end on the right. It carries the diameter and the
# overall length, tip to tip (drawing-guidelines.md rule 11 (turned parts read like the lathe)), both authored on
# Right-plane sketches, so the view imports them natively, both flats edge-on
# on its top silhouette. An end view would carry nothing, so this sheet has
# none; the north end's flat and dome go to DETAIL A, and the bar is the same
# either way round, so they print once for BOTH ENDS.
# Left of 0.150 so the 6.85 bar (#1038 .300 pitch) keeps its diameter
# callout, east of the south end, short of DETAIL A's fence.
PROFILE_CENTER = (0.144, 0.190)
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
# the south flat is the same cut (FlatProfile). Its station prints once too,
# from the north tip, for BOTH ENDS: each flat is stationed from its own tip.
FLATS_CALLOUT = "2X"

_P = shaft.DRAWING_PRECISION_BY_NAME
part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))
# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md), as the turned shafts declare theirs: the north dome
# is the datum end (its apex z = +DOME_HEIGHT, the part origin on the north
# cylinder end), the south dome the far end, the tip-to-tip length between
# their apexes; the O.D. runs the cylinder between the dome roots; each flat
# is stationed to its centre (the ear's mid-plane) from its own end's tip.
# The declarations print nothing.
_SOUTH_TIP_Z = -(bank.PIVOT_SHAFT_LENGTH + shaft.DOME_HEIGHT)
for _side, _station in zip(("south", "north"), bank.PIVOT_SHAFT_FLAT_STATIONS, strict=True):
    requirement(
        f"flat_{_side}", kind="flat",
        faces=(PlanarFace((0, 1, 0), shaft.FLAT_AF - shaft.SHAFT_DIA / 2, contains_z_mm=-_station),),
        requirements=("across", "length", "station"), fields={
            "normal": ([0.0, 1.0, 0.0], ("FLAT_AF",)),
            "span": (
                [round(-_station - shaft.FLAT_LENGTH / 2, 12), round(-_station + shaft.FLAT_LENGTH / 2, 12)],
                (("rocker_bank_layout", "PIVOT_SHAFT_FLAT_STATIONS"), "FLAT_LENGTH"),
            ),
            "across": (_band(shaft.FLAT_AF, _P["FlatAF"], unit=shaft.UNIT), ("FLAT_AF",)),
            "across_nominal": (shaft.FLAT_AF, ("FLAT_AF",)),
            "length": (_band(shaft.FLAT_LENGTH, _P["FlatLength"], unit=shaft.UNIT), ("FLAT_LENGTH",)),
            "length_nominal": (shaft.FLAT_LENGTH, ("FLAT_LENGTH",)),
            "station": (_band(shaft.FLAT_TIP_STATION, _P["FlatStation"], unit=shaft.UNIT), ("FLAT_TIP_STATION",)),
            "station_nominal": (shaft.FLAT_TIP_STATION, ("FLAT_TIP_STATION",)),
            # Each from its own end's dome tip, to the flat's centre.
            "station_from": ("far_end" if _side == "south" else "datum_end", ("FLAT_TIP_STATION",)),
            "station_to": ("centre", ("FLAT_TIP_STATION",)),
            "note": (shaft.FLAT_STATION_CALLOUT, ("FLAT_STATION_CALLOUT",)),
        }, precision={"across": _P["FlatAF"], "length": _P["FlatLength"], "station": _P["FlatStation"]},
    )

# The O.D. is the bought 1/4 ground rod, never cut: it prints the stock as a
# fraction reference with this line under it, not limits of size
# (drawing-guidelines.md rule 4; owner ruling 2026-11-20, #2346: buy ground
# rod). The rocker and bracket bores name this shaft as their mate (owner
# ruling 2026-11-24, fit audit question 1), so it carries no fit statement.
SHAFT_DIA_CALLOUT = "GROUND ROD, AS SUPPLIED"

PROFILE_KEEP = {
    # Over the bar, centred: the overall length, tip to tip.
    "OverallLength": (PROFILE_CENTER[0], 0.242),
    # Right of the south end and under the bar's lower flank: inside the
    # witness pair the text and its callout sat on the lower extension line
    # (baseline machinist review). Low enough that the callout passes under
    # DETAIL A's fence.
    "ShaftDia": (SOUTH_END_X + 0.030, PROFILE_CENTER[1] - 0.020),
}

requirement(
    "outer", kind="diameter", faces=(shaft.BEARING_FACE,),
    requirements=("stock",), fields={
        "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        # The cylinder's extent, root to root; the domes run on to the tips.
        "span": ([round(-bank.PIVOT_SHAFT_LENGTH, 12), 0.0], (("rocker_bank_layout", "PIVOT_SHAFT_LENGTH"),)),
        "dia_ref": (shaft.SHAFT_DIA, ("SHAFT_DIA", "SHAFT_DIA_FRACTION_DENOMINATOR")),
        "stock": (SHAFT_DIA_CALLOUT, (("draw_ch_pivot_shaft", "SHAFT_DIA_CALLOUT"),)),
        "callout": (SHAFT_DIA_CALLOUT, (("draw_ch_pivot_shaft", "SHAFT_DIA_CALLOUT"),)),
    }, precision={"dia_ref": _P["ShaftDia"]},
)

# DETAIL A: the north flat (.24 long, .04 deep), its station and the dome are
# 1.5-6 mm features. At 1:1 their dimensions crammed the north end, text on
# the witness lines and against the dome (PR #1317 eye pass), so a native 5:1
# detail carries them. The fence centres on the axis midway between the dome
# tip and the flat's far end and takes in both; the detail stands right of
# the profile's diameter callout (x <= 0.33 with its ground-stock route row),
# clear of the right border (0.419) with its dimensions.
DETAIL_SCALE = (5, 1)
DETAIL_RADIUS_MM = 6.0
DETAIL_CENTER = (0.355, 0.185)
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
# The circle's letter on the profile: up-left of the 6 mm circle, left of the
# north tip's witness line (the overall length starts there), 2 mm or more
# off both whichever corner SolidWorks anchors. Left where SolidWorks put it,
# the 6.35 mm "A" sat on the bar (cd4151166 render).
DETAIL_LETTER_XY = (NORTH_END_X - 0.014, PROFILE_CENTER[1] + 0.010)


def _detail_x(z_mm: float) -> float:
    """Sheet x of part station z in the detail: model -Z runs to the right."""
    return DETAIL_CENTER[0] - (z_mm - DETAIL_FENCE_Z_MM) * _DETAIL_MM


DETAIL_KEEP = {
    # The station and the flat's length stack above the fence. The length is
    # centred over the flat; the station's text, with its BOTH ENDS callout,
    # stands left of the tip's witness: centred on its span it sat on the
    # flat's near witness (cd4151166 render).
    "FlatStation": (
        _left_of_witness(_detail_x(DOME_HEIGHT), FLAT_STATION_CALLOUT),
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

for _name, _tip, _centre in (
    ("datum_end", shaft.DOME_HEIGHT, shaft.DOME_HEIGHT - shaft.DOME_SPHERE_RADIUS),
    ("far_end", _SOUTH_TIP_Z, -bank.PIVOT_SHAFT_LENGTH + shaft.DOME_SPHERE_RADIUS - shaft.DOME_HEIGHT),
):
    _far = _name == "far_end"
    # The overall length runs tip to tip, from the north (datum) tip.
    _overall = {
        "length": (_band(bank.PIVOT_SHAFT_OVERALL_LENGTH, _P["OverallLength"], unit=shaft.UNIT), (("rocker_bank_layout", "PIVOT_SHAFT_OVERALL_LENGTH"),)),
        "length_nominal": (bank.PIVOT_SHAFT_OVERALL_LENGTH, (("rocker_bank_layout", "PIVOT_SHAFT_OVERALL_LENGTH"),)),
        "length_from": ("datum_end", (("rocker_bank_layout", "PIVOT_SHAFT_OVERALL_LENGTH"),)),
    } if _far else {}
    requirement(
        _name, kind="dome", faces=(SphereFace(2 * shaft.DOME_SPHERE_RADIUS, (0, 0, _centre)),),
        requirements=("height", "length") if _far else ("height",), fields={
            # The dome's apex, on the axis.
            "plane": (
                {"frame": "model", "axis": "z", "value": round(_tip, 12)},
                ("DOME_HEIGHT", ("rocker_bank_layout", "PIVOT_SHAFT_LENGTH")),
            ),
            "outward": ([0.0, 0.0, -1.0] if _far else [0.0, 0.0, 1.0], ("__frame__",)),
            "height": (_band(shaft.DOME_HEIGHT, _P["DomeHeight"], unit=shaft.UNIT), ("DOME_HEIGHT",)),
            "height_nominal": (shaft.DOME_HEIGHT, ("DOME_HEIGHT",)),
            # The sphere's radius prints as a REF.
            "radius_ref": (shaft.DOME_SPHERE_RADIUS, ("DOME_SPHERE_RADIUS",)),
            "note": (shaft.DOME_CALLOUT, ("DOME_CALLOUT",)),
            **_overall,
        }, precision={"height": _P["DomeHeight"], **({"length": _P["OverallLength"]} if _far else {})},
    )


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
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"expected one detail circle on the profile, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    circle.SetLabelPosition(*DETAIL_LETTER_XY)
    draw.EditRebuild3()
    letter = tuple(float(value) for value in circle.GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"the detail circle's letter did not persist: {letter}")
    return detail


def _set_spherical_reference(adapter: Any, annotation: Any, *, label: str) -> None:
    """Print the dome's model radius as the ASME spherical reference ``(SR.16)``.

    The radius is read-only: a spherical cap of the printed dome height on the
    toleranced diameter already fixes it. Whatever radius prefix the display
    carries is kept behind the ``(S``; the readback proves it stuck (the
    MHA-DT-01 crankshaft's dome prints the same way).
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


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-shaft source", adapter.open_model(str(SOURCE)))
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-pivot-shaft"),
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
        {
            "FlatLength": FLATS_CALLOUT,
            "FlatAF": FLATS_CALLOUT,
            "FlatStation": FLAT_STATION_CALLOUT,
            "DomeHeight": DOME_CALLOUT,
        },
    )
    # The bought rod's diameter: an untoleranced fraction reference with its
    # stock line (rule 4), as draw_dt_crank_pinion_pin prints its rod.
    (shaft_dia,) = (
        annotation
        for annotation in profile_annotations
        if dimension_name(adapter, annotation) == "ShaftDia"
    )
    supplier_reference_dimension(
        adapter,
        _early_bound(shaft_dia, "IAnnotation").GetSpecificAnnotation(),
        label="pivot shaft rod diameter",
        units="in",
        precision=_P["ShaftDia"],
        expected_mm=SHAFT_DIA,
        presentation="diameter",
        fraction_denominator=SHAFT_DIA_FRACTION_DENOMINATOR,
        callout=SHAFT_DIA_CALLOUT,
    )
    radius_annotations = [
        annotation
        for annotation in detail_annotations
        if dimension_name(adapter, annotation) == "Radius"
    ]
    if len(radius_annotations) != 1:
        raise RuntimeError("north-end detail does not carry exactly one dome radius")
    _set_spherical_reference(adapter, radius_annotations[0], label="pivot shaft dome radius")

    # The axis says which pairs of lines are diameters and is what the shop
    # indicates the bar on. The face pick sits mid-body, clear of every
    # placed annotation.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0] - 0.030, PROFILE_CENTER[1]),
        label="pivot shaft axis centerline",
    )
    # Re-assert the detail's hidden-lines-removed display now its annotations
    # have landed: left as placed, the 5:1 dome printed as straight segments
    # (machinist review; draw_dt_cone_gear_shaft does the same for its
    # sections).
    set_hidden_lines_removed(adapter, detail)

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127); 0.020 clears it, and the
    # audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.085)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return finalize_drawing(
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
