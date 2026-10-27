r"""Create the MHA-SM-04 gooseneck spring screw manufacturing drawing.

The SLDPRT remains authoritative.  A screw carries no datum and no
geometric-control frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the relief diameter
prints as the part's stacked LIMIT band, its 45-degree lead as the part's
single MAX limit, and every other size is an ordinary model dimension at its
part-authored places under the title block's band for those places (.X for
the tip chamfer, .XX for the rest).  The overall length and the crown's
sphere radius print as references.

The screw axis is model +Z, so the ``*Right`` view already lays it horizontal
as it sits in the lathe: model +Z runs to paper-LEFT, putting the crowned head
on the left and the thread tip on the right.  Axial sizes baseline from the
under-head face, the face that clamps the spring eye.  The head-end view is
the ``*Front`` orientation (looking down -Z onto the crown), which is exactly
the third-angle LEFT view of that profile, so it sits on the profile's axis
to its left and shows the slot.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_gooseneck_spring_screw.py sm-gooseneck-spring-screw
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
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
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from sm_gooseneck_spring_screw_geom import (
    CROWN_CENTER_Z,
    CROWN_RADIUS,
    CROWN_RISE,
    HEAD_CYL_H,
    HEAD_DIA,
    HEAD_H,
    LENGTH,
    MAJOR_DIA,
    OVERALL_LENGTH,
    RELIEF_DIA,
    RELIEF_DIA_LOWER,
    RELIEF_DIA_TOL_TYPE,
    RELIEF_DIA_UPPER,
    RELIEF_LEAD,
    RELIEF_LEAD_TOL_TYPE,
    RELIEF_WIDTH,
    SLOT_DEPTH,
    SLOT_FLOOR_Z,
    SLOT_WIDTH,
    TIP_CHAMFER,
)
from sm_gooseneck_spring_screw_spec import (
    DIMENSION_CALLOUTS_BY_NAME,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
    SPHERICAL_DIMENSIONS,
    THREAD_CALLOUT,
)


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_gooseneck_spring_screw"]
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

# Both orthographic views print at the sheet scale, so neither needs a caption.
# 4:1 lays the 23.0 profile 92 mm long and the 1.6 slot 6.4 mm wide.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.215, 0.165)
# Third-angle left view of the crowned head end, on the profile's axis.
END_CENTER = (0.085, SIDE_CENTER[1])
ISO_CENTER = (0.360, 0.215)
ISO_SCALE = (2, 1)
# The view centre is the model bounding box's: apex z=HEAD_H to tip z=-LENGTH.
_BOX_MID_Z = (HEAD_H - LENGTH) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left)."""
    return SIDE_CENTER[0] + (_BOX_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the screw axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


APEX_X = _sheet_x(HEAD_H)
RIM_X = _sheet_x(HEAD_CYL_H)
SLOT_FLOOR_X = _sheet_x(SLOT_FLOOR_Z)
UNDERHEAD_X = _sheet_x(0.0)
RELIEF_END_X = _sheet_x(-RELIEF_WIDTH)
TIP_X = _sheet_x(-LENGTH)
# The crown's sphere centre, on the axis inside the shank.
CROWN_CENTER_X = _sheet_x(CROWN_CENTER_Z)
# Where the full thread meets the tip chamfer.
THREAD_START_X = _sheet_x(-(LENGTH - TIP_CHAMFER))
HEAD_TOP_Y = _sheet_y(HEAD_DIA / 2.0)
THREAD_TOP_Y = _sheet_y(MAJOR_DIA / 2.0)
RELIEF_TOP_Y = _sheet_y(RELIEF_DIA / 2.0)
RELIEF_MID_X = (UNDERHEAD_X + RELIEF_END_X) / 2.0
# The 45-degree lead's foot on the relief floor.
LEAD_FOOT_X = _sheet_x(-RELIEF_LEAD)
NECK_BOTTOM_Y = _sheet_y(-RELIEF_DIA / 2.0)
# The relief Ø's dimension line stands on the floor next to the flank,
# leaving the air under the floor's head end to the lead's extension line.
RELIEF_DIA_X = RELIEF_END_X - 0.0015

# Rows below the profile, 15 mm apart, the first 38 mm under the head
# (text sits ~3 mm above its requested point, the dimension line ~5 mm
# below it), clear of the lead's text block above them.  Row 0 chains the
# head height and the under-head length from the under-head face; row 1
# carries the reference overall.
_ROW_Y = (HEAD_TOP_Y - 0.093, HEAD_TOP_Y - 0.108)
# ' 1.00 ' as rendered (farm run 20261010T190631112Z).
CROWN_RISE_TEXT_WIDTH = 0.0116
# The lead's text block: '0.3 max.' over its three-line callout, the widest
# line (the spring's number) 48.2 mm as rendered (farm run
# 20261024T031009457Z, 9d8923584).
LEAD_TEXT_WIDTH = 0.049
# Its top line stood 10.7 mm above the anchor in that run.
LEAD_TEXT_TOP_ABOVE_ANCHOR = 0.011
# '(SR20.0)' at the sheet's dimension font, estimated from the ' 1.00 ' and
# 'Ø12.50' widths of the same runs (about 2.6 mm a character).
CROWN_RADIUS_TEXT_WIDTH = 0.018
SIDE_KEEP = {
    "HeadHeight": ((APEX_X + UNDERHEAD_X) / 2.0, _ROW_Y[0]),
    "UnderHeadLength": ((UNDERHEAD_X + TIP_X) / 2.0, _ROW_Y[0]),
    "OverallLength": ((APEX_X + TIP_X) / 2.0, _ROW_Y[1]),
    # Diameters on the side view (drawing-guidelines.md rule 11 (turned parts read like the lathe)): the head's stands clear of the
    # crown, between the profile and the head-end view, far enough left that
    # the crown's radius reads between its dimension line and the apex.
    "HeadDia": (APEX_X - 0.031, SIDE_CENTER[1]),
    # The crown's (SR) reads left of the crown and under the slot, inside the
    # head Ø's extension lines, so its radial leader lands on the lower arc
    # without crossing the Ø line or either extension line.
    "CrownRadius": (APEX_X - 0.0165, SIDE_CENTER[1] - 0.015),
    # The crown rise and the slot depth both read from the apex, stacked
    # above the head.  The rise is too narrow for its text, so the text
    # stands outside, left of the apex: centred between the two extension
    # lines it sat on the slot depth's apex extension (layout audit of farm
    # run 20261010T190631112Z, 6c56fd769).
    "CrownRise": (
        APEX_X - 0.003 - CROWN_RISE_TEXT_WIDTH / 2.0,
        HEAD_TOP_Y + 0.012,
    ),
    "SlotDepth": ((APEX_X + SLOT_FLOOR_X) / 2.0, HEAD_TOP_Y + 0.024),
    # The die relief against the under-head face.  Its width reads above it,
    # clear of the head; its Ø below it, the dimension line standing on the
    # floor.
    "ReliefWidth": (RELIEF_MID_X, HEAD_TOP_Y + 0.005),
    "ReliefDia": (RELIEF_DIA_X, SIDE_CENTER[1] - 0.012),
    # The lead reads under the relief from the lower silhouette's reference
    # line: its text stands right of its 1.2 mm span, under the relief Ø's
    # LIMIT block and above row 0, its left end clear of the lead's extension
    # line.
    "HeadLead": (LEAD_FOOT_X + 0.0035 + LEAD_TEXT_WIDTH / 2.0, HEAD_TOP_Y - 0.076),
    # The tip chamfer's axial leg reads below-right of the tip.
    "TipChamfer": (TIP_X + 0.012, SIDE_CENTER[1] - 0.016),
}
# The relief Ø's text goes on an OffsetText leader, hung right of its own
# dimension line: the leader meets the text's LEFT end, so with that end
# right of the line the leader descends beside the text, not through it, and
# the text stays clear of the under-head and lead extension lines (layout
# audit of farm run 20261010T190631112Z, 6c56fd769).  Its right end stops
# short of the tip chamfer's extension lines and the Ø line stays below the
# thread silhouette.  The block is the stacked limits over the callout.  As
# rendered in farm run 20261024T052013556Z (e71509a34), its upper limit's top
# stood 9.8 mm above the anchor, where the shank's lower outline struck it;
# 'CLAMP TORQUE' measured 35.8 mm (3.0 mm a character), and the underline of
# the two-line callout sat 9.7 mm below the anchor at a 5.5 mm line pitch.
# The three-line callout's widest line, 'UNDER DIE ROOT,', is scaled from
# those, and its underline one more pitch down.
RELIEF_DIA_TEXT_WIDTH = 0.046
RELIEF_DIA_TEXT_TOP_ABOVE_ANCHOR = 0.010
RELIEF_DIA_TEXT_BOTTOM_DROP = 0.0155
RELIEF_DIA_LEADER_GAP = 0.0008
RELIEF_DIA_TEXT_XY = (
    RELIEF_DIA_X + RELIEF_DIA_LEADER_GAP + RELIEF_DIA_TEXT_WIDTH / 2.0,
    SIDE_CENTER[1] - 0.0205,
)
# The slot width reads right of the head-end view, left of the head Ø.
END_KEEP = {
    "SlotWidth": (
        END_CENTER[0] + HEAD_DIA * _S / 2000.0 + 0.010,
        END_CENTER[1] + 0.010,
    ),
}
# The thread callout's leader lands on the edge where the full thread meets
# the tip chamfer, never on the relief groove.  The note stands up and
# right so the leader slants down-left onto that edge.
THREAD_PICK = (THREAD_START_X, SIDE_CENTER[1] + 0.004)
THREAD_NOTE_XY = (THREAD_START_X + 0.013, SIDE_CENTER[1] + 0.035)
# A point on the thread's cylindrical face, clear of every dimension line.
CENTERLINE_PICK = ((RELIEF_END_X + THREAD_START_X) / 2.0, SIDE_CENTER[1] + 0.003)
ISO_NOTE_XY = (0.340, 0.180)
# Bottom-left, above the title-block line, like the other screw sheets.
NOTES_XY = (0.016, 0.070)

# Policy: native generation verifies persisted values, tolerances and
# reference state.  swTolType_e: NONE leaves the title block's .XX band, MAX
# prints the model value as the part's single limit, LIMIT prints the model
# value plus each deviation.  Each row is (nominal mm, tolerance type).
_TOL_NONE, _TOL_LIMIT, _TOL_MAX = 0, 3, 6
_ARROWS_OUTSIDE = 1  # swDimArrowsOutside: the (SR)'s arrow on the arc
if RELIEF_DIA_TOL_TYPE != _TOL_LIMIT or RELIEF_LEAD_TOL_TYPE != _TOL_MAX:
    raise AssertionError("MHA-SM-04 relief limits are no longer LIMIT / MAX")
PRINTED_DIMENSIONS: dict[str, tuple[float, int]] = {
    "HeadDia": (HEAD_DIA, _TOL_NONE),
    "HeadHeight": (HEAD_H, _TOL_NONE),
    "CrownRise": (CROWN_RISE, _TOL_NONE),
    "CrownRadius": (CROWN_RADIUS, _TOL_NONE),
    "UnderHeadLength": (LENGTH, _TOL_NONE),
    "ReliefDia": (RELIEF_DIA, _TOL_LIMIT),
    "ReliefWidth": (RELIEF_WIDTH, _TOL_NONE),
    "HeadLead": (RELIEF_LEAD, _TOL_MAX),
    "TipChamfer": (TIP_CHAMFER, _TOL_NONE),
    "SlotWidth": (SLOT_WIDTH, _TOL_NONE),
    "SlotDepth": (SLOT_DEPTH, _TOL_NONE),
    "OverallLength": (OVERALL_LENGTH, _TOL_NONE),
}
# Every LIMIT row's (lower, upper) deviations, mm: a LIMIT row without its
# band would skip the deviation readback, so the two must name the same rows.
LIMIT_DEVIATIONS: dict[str, tuple[float, float]] = {
    "ReliefDia": (RELIEF_DIA_LOWER, RELIEF_DIA_UPPER),
}
if set(LIMIT_DEVIATIONS) != {
    name for name, (_, kind) in PRINTED_DIMENSIONS.items() if kind == _TOL_LIMIT
}:
    raise AssertionError("MHA-SM-04 LIMIT rows and their deviations disagree")
# Unprinted controls: the profile's lead (the printed lead's reference line
# follows it by equation) and the thread major the callout defines.
SOURCE_ONLY_DIMENSIONS: dict[str, tuple[float, int]] = {
    "ReliefLead@ShankProfile": (RELIEF_LEAD, _TOL_NONE),
    "ThreadDia@ShankProfile": (MAJOR_DIA, _TOL_NONE),
}


def _check_dimension_state(
    label: str, dimension: Any, expected: tuple[float, int]
) -> None:
    """Raise unless one native dimension holds its spec nominal and type."""
    nominal, tolerance_type = expected
    dimension = _early_bound(dimension, "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    value_mm = float(dimension.SystemValue) * 1000.0
    if not math.isclose(value_mm, nominal, abs_tol=1e-6):
        raise RuntimeError(
            f"MHA-SM-04 {label}: persisted nominal {value_mm!r} mm, spec "
            f"{nominal!r} mm; rebuild the source part"
        )
    if int(tolerance.Type) != tolerance_type:
        raise RuntimeError(
            f"MHA-SM-04 {label}: tolerance type {int(tolerance.Type)}, "
            f"spec {tolerance_type}; rebuild the source part"
        )
    if label in LIMIT_DEVIATIONS:
        lower, upper = LIMIT_DEVIATIONS[label]
        read = (
            float(tolerance.GetMinValue()) * 1000.0,
            float(tolerance.GetMaxValue()) * 1000.0,
        )
        if not all(
            math.isclose(a, b, abs_tol=1e-6) for a, b in zip(read, (lower, upper))
        ):
            raise RuntimeError(
                f"MHA-SM-04 {label}: LIMIT deviations {read!r} mm, spec "
                f"{(lower, upper)!r} mm; rebuild the source part"
            )


def _verify_source_dimensions(model: Any) -> None:
    """The unprinted callout controls, read from the opened source part."""
    for full_name, expected in SOURCE_ONLY_DIMENSIONS.items():
        dimension = model.Parameter(full_name)
        if dimension is None:
            raise RuntimeError(f"MHA-SM-04 source part lacks {full_name}")
        _check_dimension_state(full_name, dimension, expected)


def _verify_printed_dimensions(adapter: Any, views: Sequence[Any]) -> None:
    """Re-read every printed size after the last rebuild (settled check)."""
    found: dict[str, list[Any]] = {name: [] for name in PRINTED_DIMENSIONS}
    for view in views:
        for item in _early_bound(view, "IView").GetAnnotations() or ():
            annotation = _early_bound(item, "IAnnotation")
            name = dimension_name(adapter, annotation)
            if name in found:
                found[name].append(annotation)
    for name, expected in PRINTED_DIMENSIONS.items():
        if len(found[name]) != 1:
            raise RuntimeError(
                f"MHA-SM-04 sheet prints {name} {len(found[name])} times, not once"
            )
        display = _early_bound(
            found[name][0].GetSpecificAnnotation(), "IDisplayDimension"
        )
        _check_dimension_state(name, display.GetDimension2(0), expected)
        parenthesized = str(display.GetText(1) or "").startswith("(") and str(
            display.GetText(2) or ""
        ).endswith(")")
        if parenthesized != (name in REFERENCE_DIMENSIONS):
            raise RuntimeError(f"MHA-SM-04 {name}: reference state did not persist")
        if name in SPHERICAL_DIMENSIONS:
            _check_spherical_reference(found[name][0], display, label=name)
        if int(display.GetPrimaryPrecision2()) != DRAWING_PRECISION_BY_NAME[name]:
            raise RuntimeError(f"MHA-SM-04 {name}: display places did not persist")
        if (
            name in LIMIT_DEVIATIONS
            and int(display.GetPrimaryTolPrecision2())
            != DRAWING_PRECISION_BY_NAME[name]
        ):
            raise RuntimeError(f"MHA-SM-04 {name}: limit places did not persist")
        # The part authors every callout (swDimensionTextCalloutBelow); the
        # drawing only reads it back.  SOLIDWORKS may hand lines back as CRLF.
        callout = str(display.GetText(4) or "").replace("\r\n", "\n")
        if callout != DIMENSION_CALLOUTS_BY_NAME.get(name, ""):
            raise RuntimeError(
                f"MHA-SM-04 {name}: callout {callout!r} is not the part's"
            )


def _spherical_reference_text(name: str) -> str:
    """The ink a spherical reference prints, e.g. ``(SR20.0)`` for CrownRadius."""
    value = PRINTED_DIMENSIONS[name][0]
    return f"(SR{value:.{DRAWING_PRECISION_BY_NAME[name]}f})"


def _printed_text(annotation: Any) -> str:
    """A dimension's printed text items joined (IDisplayData, the ink the
    layout audit reads)."""
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    return "".join(
        str(data.GetTextAtIndex(index) or "").strip()
        for index in range(int(data.GetTextCount() or 0))
    )


def _check_spherical_reference(annotation: Any, display: Any, *, label: str) -> None:
    """Raise unless the reference prints its whole intended text with the
    arrow outside the arc and no solid leader to the centre."""
    expected = _spherical_reference_text(label)
    printed = _printed_text(_early_bound(annotation, "IAnnotation"))
    if printed != expected:
        raise RuntimeError(f"MHA-SM-04 {label}: prints {printed!r}, not {expected!r}")
    if int(display.ArrowSide) != _ARROWS_OUTSIDE or bool(display.SolidLeader):
        raise RuntimeError(
            f"MHA-SM-04 {label}: the outside leader did not persist "
            f"(ArrowSide {int(display.ArrowSide)}, SolidLeader "
            f"{bool(display.SolidLeader)})"
        )


def _set_spherical_reference(annotation: Any, *, name: str) -> None:
    """Print the crown's model radius as the ASME spherical reference ``(SR20.0)``.

    The radius is read-only: the head Ø and the controlling rise already fix
    the dome.  Whatever radius prefix the display carries stays behind the
    ``(S`` (draw_dt_pinion_pivot_shaft prints its crown the same way); a
    ``(S`` already there is stripped first, so a second pass never prints
    ``(S(SR``.  The arrow sits outside the arc with no solid leader on to the
    centre, which lies inside the shank, so the leader runs from the text to
    the crown and stops there (draw_dt_pinion_arbor's SR crown).  Prefix,
    suffix and leader are read back here; the whole printed text after the
    last rebuild, in the settled check (_verify_printed_dimensions).
    """
    label = f"MHA-SM-04 {name}"
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    radius_prefix = existing.removeprefix("(S")
    prefix = "(S" + radius_prefix
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
    display.ArrowSide = _ARROWS_OUTSIDE
    if int(display.ArrowSide) != _ARROWS_OUTSIDE:
        raise RuntimeError(f"{label} did not keep its arrow outside the arc")
    display.SolidLeader = False
    if bool(display.SolidLeader):
        raise RuntimeError(f"{label} still draws its solid leader to the centre")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck-spring-screw source", await adapter.open_model(str(SOURCE)))
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
    _verify_source_dimensions(adapter.currentModel)
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Gooseneck Spring Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"gooseneck spring clamp; slotted fillister screw; {THREAD_CALLOUT}; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="head-end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *end_annotations]
    offset_dimension_text(adapter, side_annotations, {"ReliefDia": RELIEF_DIA_TEXT_XY})
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one MHA-SM-04 {name} reference dimension")
        if name in SPHERICAL_DIMENSIONS:
            _set_spherical_reference(matches[0], name=name)
            continue
        set_reference_dimension(adapter, matches[0], label=f"MHA-SM-04 {name}")

    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-SM-04 head-end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-SM-04 turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-SM-04 thread callout",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Spring Screw Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(lambda: _verify_printed_dimensions(adapter, (side, end)),),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
