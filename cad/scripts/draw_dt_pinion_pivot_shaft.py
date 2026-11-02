r"""Create the curated machinist drawing for the pinion strap torque shaft
(MHA-DT-19).

A plain 1/4 in steel shaft with a shallow spherical crown at each end, drawn
like the MHA-CH-05 pivot shaft: one 1:1 side view carries the diameter, the
body length, the overall length (reference) and the match-drilled pin holes,
a 5:1 detail carries the crown, and a 1:2 isometric stays clear of the title
block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_pivot_shaft.py dt-pinion-pivot-shaft
"""

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

import _config
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
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_drive_train_steps import step_ref
from dt_pinion_pivot_shaft_spec import (
    CAP_SAG,
    CROWN_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OVERALL_LEN,
    PIN_HOLE_CALLOUT,
    PIN_HOLE_Z,
    SHAFT_DIA as SHAFT_DIA,
    SHAFT_LEN,
    SURFACE_FINISHES,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_pinion_pivot_shaft"]
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
# The side view is "*Right": the axis horizontal, as the bar sits in the
# lathe. Model -Z runs to the sheet's right, so the FRONT end (the part
# origin) is on the RIGHT and the body runs left. Every printed dimension is
# authored on a Right-plane sketch, so the view imports them natively
# (drawing-guidelines.md rule 11 (turned parts read like the lathe)). An end
# view would carry nothing, so this sheet has none.
PROFILE_CENTER = (0.170, 0.200)
_MM = SHEET_SCALE[0] / 1000.0
# The view centres on the bar's bounding box, crowns included.
FRONT_END_X = PROFILE_CENTER[0] + (OVERALL_LEN / 2.0 - CAP_SAG) * _MM
FRONT_TIP_X = FRONT_END_X + CAP_SAG * _MM
BACK_END_X = FRONT_END_X - SHAFT_LEN * _MM
FRONT_PIN_X = FRONT_END_X - PIN_HOLE_Z[0] * _MM
SHAFT_LOWER_FLANK_Y = PROFILE_CENTER[1] - SHAFT_DIA * _MM / 2.0
SHAFT_UPPER_FLANK_Y = PROFILE_CENTER[1] + SHAFT_DIA * _MM / 2.0
# 1:2: at 1:1 the ~190 mm isometric bar runs over the drawable band, so the
# pictorial is halved and says so. It stands in the open field under the
# profile, right of the notes and left of the title block (x 0.216).
ISO_CENTER = (0.150, 0.110)
ISO_SCALE = (1, 2)
ISO_NOTE_XY = (0.115, 0.082)

# The O.D.'s band is for the two pivot-block bores it runs in; the callout
# names them (drawing-guidelines.md rule 4 (tighten only for function, and
# name the mate)).
SHAFT_FIT_CALLOUT = (
    f"RUNNING FIT IN\n{_config.parts('dt-pinion-pivot-block')['number']} BORES"
)
# The holes are drilled at MHA-DT-00's SHAFT DRILL SET, so the callout points
# at that step through the registry (Codex #858, PRRT_kwDOPHDy386mTbPB). The
# +0.06/0 band is the spring pin's hole, so the callout names the pin and its
# fit (rule 4; r3 review), with the fleet's "FOR <pin> SPRING PIN" wording.
SHAFT_DRILL_STEP_KEY = "straps-pinned-to-torque-shaft"
STRAP_PIN_NUMBER = _config.parts("dt-vn-pinion-strap-pin")["number"]
PIN_HOLE_FIT = f"PRESS FIT FOR {STRAP_PIN_NUMBER} SPRING PIN"
DIMENSION_CALLOUTS = {
    "ShaftDia": SHAFT_FIT_CALLOUT,
    # The overall (reference) runs tip to tip over it; this is the cylinder.
    "ShaftLength": "CYLINDRICAL BODY",
    "PinHoleDia": (
        f"{PIN_HOLE_CALLOUT},\n{PIN_HOLE_FIT},\nPER {step_ref(SHAFT_DRILL_STEP_KEY)}"
    ),
}

PROFILE_KEEP = {
    # Over the bar, stacked: the overall (reference) outermost, tip to tip,
    # the body length under it, end face to end face.
    "OverallLength": (PROFILE_CENTER[0], 0.252),
    "ShaftLength": (PROFILE_CENTER[0], 0.234),
    # Right of the front end, between it and DETAIL A's fence, under the
    # bar's centre: outside the witness pair. Left of the back end (r3) the
    # fit callout ran over the inner border into the zone margin; the text
    # runs away from the dimension line (r3 audit: 43 mm wide there), so
    # 12 mm out it ends ~12 mm short of the fence.
    "ShaftDia": (FRONT_END_X + 0.012, PROFILE_CENTER[1] - 0.012),
    # Option E-a: the set-pin holes read as solid circles in the side view.
    # Only the size prints; the match-drill callout carries the location.
    # Under the bar, LEFT of the front hole, so the leader leaves the text
    # block's right end and rises onto the hole clear of the lettering (r3:
    # centred under the hole, the leader struck its own text).
    "PinHoleDia": (PROFILE_CENTER[0] - 0.005, PROFILE_CENTER[1] - 0.028),
}

# DETAIL A: the crown is a 1.2 mm feature. At 1:1 its height, its sphere and
# the overall and body witnesses all crowd the same 1.2 mm, so a native 5:1
# detail of the front end carries the crown, once, for BOTH ENDS. The fence
# centres on the axis just inside the end face and takes in the apex and the
# rim; the detail stands right of the profile, clear of the right border.
DETAIL_SCALE = (5, 1)
DETAIL_RADIUS_MM = 5.0
DETAIL_FENCE_Z_MM = 1.0
DETAIL_CENTER = (0.355, 0.200)
_DETAIL_MM = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
_DETAIL_FENCE_R = DETAIL_RADIUS_MM * _DETAIL_MM
if DETAIL_RADIUS_MM <= abs(
    -CAP_SAG - DETAIL_FENCE_Z_MM
) or DETAIL_RADIUS_MM <= math.hypot(DETAIL_FENCE_Z_MM, SHAFT_DIA / 2.0):
    raise AssertionError("DETAIL A's fence must take in the crown's apex and its rim")
# The label anchors at its top centre, under the crown's callout.
DETAIL_LABEL_XY = (DETAIL_CENTER[0], DETAIL_CENTER[1] - _DETAIL_FENCE_R - 0.032)
# The circle's letter on the profile: up-left of the front end, left of its
# two length witness lines, as on MHA-CH-05. Up-right (r4) the diameter's
# upper dimension line ran onto its foot.
DETAIL_LETTER_XY = (FRONT_END_X - 0.010, PROFILE_CENTER[1] + 0.012)

# A short dimension's callout is far wider than the span it measures, so its
# text stands OUTSIDE the witness pair. Callout text runs ~2.75 mm a character
# at the template's dimension height (MHA-CH-05 r743-3 render).
CALLOUT_CHAR_WIDTH = 0.00275
CALLOUT_WITNESS_GAP = 0.003


def _detail_x(z_mm: float) -> float:
    """Sheet x of part station z in the detail: model -Z runs to the right."""
    return DETAIL_CENTER[0] + (DETAIL_FENCE_Z_MM - z_mm) * _DETAIL_MM


def _right_of_witness(witness_x: float, callout: str) -> float:
    """Text centre x that starts a callout CALLOUT_WITNESS_GAP right of a witness."""
    return witness_x + CALLOUT_WITNESS_GAP + len(callout) * CALLOUT_CHAR_WIDTH / 2.0


DETAIL_KEEP = {
    # Under the fence, right of the apex's witness: a short .X height the
    # "BOTH ENDS" callout makes a 2X statement.
    "CapFrontSag": (
        _right_of_witness(_detail_x(-CAP_SAG), CROWN_CALLOUT),
        DETAIL_CENTER[1] - _DETAIL_FENCE_R - 0.010,
    ),
    # Up-right of the fence: the leader drops onto the crown's arc.
    "CapFrontR": (
        DETAIL_CENTER[0] + _DETAIL_FENCE_R + 0.012,
        DETAIL_CENTER[1] + 0.022,
    ),
}

# Ra on the running face, the body both pivot-block bores run on. A revolved
# flank is a drawing SILHOUETTE, not a model edge, so the pick names that
# entity type; the straight leader keeps off the geometry. The UPPER flank,
# as on MHA-CH-05: on the lower one (r2, swmaker000005) the symbol re-solved
# onto a silhouette of another face and the attachment check failed. Left of
# the body length's callout and right of the back pin hole. Note text height,
# as on the other part sheets: at the template default the symbol printed
# about twice the text height (#1015).
FINISH_CHAR_HEIGHT = 0.0025
BEARING_FINISH_EDGE = (PROFILE_CENTER[0] - 0.055, SHAFT_UPPER_FLANK_Y)
BEARING_FINISH_SYMBOL = (BEARING_FINISH_EDGE[0], SHAFT_UPPER_FLANK_Y + 0.013)


def _front_end_detail(adapter: Any, profile: Any) -> Any:
    """A native 5:1 detail of the front end: its crown."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(profile, "IView")
    if not drawing.ActivateView(view_name(adapter, profile)):
        raise RuntimeError("failed to activate the front-end detail's parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        profile,
        (0.0, 0.0, DETAIL_FENCE_Z_MM / 1000.0),
        label="front-end detail centre",
    )
    radius = DETAIL_RADIUS_MM * SHEET_SCALE[0] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create the front-end detail fence")
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
        raise RuntimeError("failed to create the front-end detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("the front-end detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position the front-end detail")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position the front-end detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"the front-end detail label did not persist: {actual}")
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(
            f"expected one detail circle on the profile, found {len(circles)}"
        )
    circle = _early_bound(circles[0], "IDetailCircle")
    circle.SetLabelPosition(*DETAIL_LETTER_XY)
    draw.EditRebuild3()
    letter = tuple(float(value) for value in circle.GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"the detail circle's letter did not persist: {letter}")
    return detail


def _set_spherical_reference(adapter: Any, annotation: Any, *, label: str) -> None:
    """Print the crown's model radius as the ASME spherical reference ``(SR4.8)``.

    The radius is read-only: a spherical cap of the printed crown height on
    the toleranced diameter already fixes it. Whatever radius prefix the
    display carries is kept behind the ``(S``; the readback proves it stuck
    (the MHA-CH-05 pivot shaft's dome prints the same way).
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
        raise RuntimeError(
            f"failed to mark {label} as a spherical reference: {applied}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-pivot-shaft source", await adapter.open_model(str(SOURCE)))
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
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Iso View Note",
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
            0: "Pinion Torque Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion torque shaft; pivot shaft; turned steel",
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
    detail = _front_end_detail(adapter, profile)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="front-end detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter,
        [*profile_annotations, *detail_annotations],
        DRAWING_PRECISION_BY_NAME,
    )
    set_dimension_callouts(adapter, profile_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, detail_annotations, {"CapFrontSag": CROWN_CALLOUT})
    # The overall length is the two crowns on the body: a reference. A plain
    # "(189.4)": the plural helper's "(<MOD-DIAM>" printed "(Ø189.4)" (r3).
    overall = [
        annotation
        for annotation in profile_annotations
        if dimension_name(adapter, annotation) == "OverallLength"
    ]
    if len(overall) != 1:
        raise RuntimeError("profile does not carry exactly one overall length")
    set_reference_dimension(adapter, overall[0], label="overall length")
    radius_annotations = [
        annotation
        for annotation in detail_annotations
        if dimension_name(adapter, annotation) == "CapFrontR"
    ]
    if len(radius_annotations) != 1:
        raise RuntimeError("front-end detail does not carry exactly one crown radius")
    _set_spherical_reference(
        adapter, radius_annotations[0], label="pinion pivot shaft crown radius"
    )

    # The axis says which pairs of lines are diameters and is what the shop
    # indicates the bar on. The face pick sits mid-body, clear of every
    # placed annotation.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0] + 0.030, PROFILE_CENTER[1]),
        label="pinion pivot shaft axis centerline",
    )
    add_surface_finish(
        adapter,
        profile,
        edge_xy=BEARING_FINISH_EDGE,
        entity_type="SILHOUETTE",
        symbol_xy=BEARING_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="pinion pivot bearing finish",
        char_height=FINISH_CHAR_HEIGHT,
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here,
    # clear of the 12.7 mm zone margin.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.085)
    add_property_linked_note(adapter, "Iso View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Torque Shaft Manufacturing Drawing",
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
