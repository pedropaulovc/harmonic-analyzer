r"""Create the manufacturing drawing for the transgear thumbnut (MHA-PD-13).

The face view is the ``*Top`` orientation, looking at the dished front face:
it carries the native #8-32 UNC-2B through-thread callout. Both actual entry
cones print a model-owned MAX diameter and their half-angle in section.
Section A-A uses the Front plane through the axis and two knurl crests, so the
knurl diameter, the head, waist and flange, the overall length and the
flange length from the seat face (the waist is their remainder) and the
dish's rim and floor diameters and its depth to the floor print
on solid cut edges.  No roughness symbol: the seat face clamps the wheel
(drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from pd_transgear_thumbnut_spec import (
    CSK_DIA,
    CSK_QUALIFIER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_LENGTH,
    HEAD_DIA,
    HEAD_REAR_Y,
    KNURL_CALLOUT,
    OVERALL_LENGTH,
    TAP_DRILL_DIA,
    TAP_SPEC,
    WAIST_LENGTH,
    THREAD,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["pd_transgear_thumbnut"]
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

# A Ø.81 × .63 nut: 3:1 leaves room round the section for its nine
# dimensions and the knurl callout on the landscape sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FACE_CENTER = (0.085, 0.165)
SECTION_CENTER = (0.215, FACE_CENTER[1])
ISO_CENTER = (0.345, FACE_CENTER[1])
# Half the knurl diameter on the sheet, and the cutting line's overrun past it.
HALF_HEAD = HEAD_DIA * _S / 2000.0
SECTION_LINE_OVERRUN = 0.005
# Across the face view on the nut axis: sheet X is model X in *Top, so the
# cut is the Front plane, the plane of the turned profiles.
SECTION_LINE = (
    (FACE_CENTER[0] - HALF_HEAD - SECTION_LINE_OVERRUN, FACE_CENTER[1]),
    (FACE_CENTER[0] + HALF_HEAD + SECTION_LINE_OVERRUN, FACE_CENTER[1]),
)


def _section_x(model_x_mm: float) -> float:
    """Sheet X of a model-X offset from the axis on the section."""
    return SECTION_CENTER[0] + model_x_mm * _S / 1000.0


def _section_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y station on the section (rim up)."""
    return SECTION_CENTER[1] + (model_y_mm - OVERALL_LENGTH / 2.0) * _S / 1000.0


# The rim's diameters stack above it (knurl outermost, the dish floor
# innermost, so each one's extension lines stay inside the next one's) with
# only air below their extension lines; the overall length stands off the
# right of the silhouette and the dish depth off the left.  The flange
# length (inner lane) and the head's rear face (outer lane) read from the
# seat face on the left, baseline with the overall length, arrows inside;
# the waist length is the remainder and does not print.  The
# dish depth's text stands above its rim extension line: at 3:1 the depth is
# shorter than the text is tall.  The waist and the flange are dimensioned
# across their own cut, each dimension line at its feature's height and its
# text out to the right: an extension line run past the rim or seat would
# cross another feature's hatching. The cone diameter sits below the seat,
# left of the caption; the half-angle's short arc stays at the actual cone.
_STEM_TEXT_X = _section_x(HEAD_DIA / 2.0) + 0.021
SECTION_KEEP = {
    "HeadDia": (SECTION_CENTER[0], _section_y(OVERALL_LENGTH) + 0.030),
    "DishDia": (SECTION_CENTER[0], _section_y(OVERALL_LENGTH) + 0.014),
    "DishFloorDia": (SECTION_CENTER[0], _section_y(OVERALL_LENGTH) + 0.006),
    "DishDepth": (
        _section_x(-HEAD_DIA / 2.0) - 0.016,
        _section_y(OVERALL_LENGTH) + 0.004,
    ),
    "HeadRearY": (
        _section_x(-HEAD_DIA / 2.0) - 0.026,
        _section_y(HEAD_REAR_Y / 2.0),
    ),
    "OverallLength": (_section_x(HEAD_DIA / 2.0) + 0.032, SECTION_CENTER[1]),
    "FlangeLength": (
        _section_x(-HEAD_DIA / 2.0) - 0.016,
        _section_y(FLANGE_LENGTH / 2.0),
    ),
    "FlangeDia": (_STEM_TEXT_X, _section_y(FLANGE_LENGTH / 2.0)),
    "WaistDia": (_STEM_TEXT_X, _section_y(FLANGE_LENGTH + WAIST_LENGTH / 2.0)),
    # A sheet-outboard angular anchor makes the native cone/axis arc huge
    # (4e9a4df). First place its arc just beyond the actual rear cone, then
    # offset only its text; the imported model association stays unchanged.
    "CountersinkDia": (_section_x(-HEAD_DIA / 2.0) - 0.025, _section_y(0.0) - 0.008),
    "CountersinkHalfAngle": (_section_x(CSK_DIA / 2.0 + 0.6), _section_y(-0.6)),
}
COUNTERSINK_ANGLE_TEXT_XY = (0.264, _section_y(0.0) - 0.008)
# The baseline lengths' spans hold their text and arrows: inside, so no arrow
# hangs below the seat face into the cone diameter's "max." (run
# 20261024T025840809Z).
ARROWS_INSIDE = ("FlangeLength", "HeadRearY")
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
# The native caption's top centre.  The cone diameter's dimension line runs
# under its below-callout, 13.5 mm under the seat face (run
# 20261024T025840809Z): the caption hangs 6.5 mm under that line, clear of
# its extension lines.
SECTION_CAPTION_XY = (SECTION_CENTER[0], _section_y(0.0) - 0.020)
# The face view prints only the native thread callout.
FACE_KEEP: dict[str, tuple[float, float]] = {}
# Above the knurl diameter, the outermost of the rim's stack: the below lane
# would run into the dish chord.
DIMENSION_CALLOUTS_ABOVE = {"HeadDia": KNURL_CALLOUT}
DIMENSION_CALLOUTS_BELOW = {"CountersinkDia": CSK_QUALIFIER}


def _printable_above_callouts(callouts: dict[str, str]) -> dict[str, str]:
    """Refuse an above-callout SolidWorks would keep but not print.

    A line break in the above compartment is stored (``GetDisplayData`` reads
    it back) yet nothing of the callout reaches the PDF: the two-line knurl
    designation over Ø20.5 (run 20261001T154021634Z) and the drive collar's
    two-line slot callout (run 20261001T151531763Z) both went unprinted,
    while one-line above callouts ("2X") print.
    """
    broken = sorted(name for name, text in callouts.items() if "\n" in text)
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return callouts


# Centred over the face view's left half, so its widest line (the
# countersink) stays inside the left border.
THREAD_CALLOUT_XY = (FACE_CENTER[0] - 0.020, FACE_CENTER[1] + 0.060)

# How far the section's seat-face point may land from where SECTION_KEEP
# assumes it (sheet metres).
_SEAT_PLACEMENT_TOL = 0.001
# How far the section's outline centre may land from SECTION_CENTER, and its
# extent from the nut's silhouette stood on end (sheet metres).
_OUTLINE_TOL = 0.0002


def _rim_is_up(seat: tuple[float, float], rim: tuple[float, float]) -> bool:
    """Whether a section whose seat and rim project at ``seat`` and ``rim``
    stands the rim straight above the seat; refuses a tilted axis."""
    dx, dy = rim[0] - seat[0], rim[1] - seat[1]
    if abs(dx) > 1e-3 * abs(dy):
        raise RuntimeError(f"thumbnut section axis is not vertical: {dx=}, {dy=}")
    return dy > 0.0


def _outline_centre(outline: tuple[float, ...]) -> tuple[float, float]:
    return ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)


def _outline_is_the_nut_on_end(outline: tuple[float, ...]) -> bool:
    """Whether ``outline`` boxes the nut's silhouette with its axis vertical.

    SolidWorks pads a view's outline by one margin all round (5.588 mm on
    both axes of the 19e33c6c2 section and face views), so the margin drops
    out of height minus width: that is the overall length less the knurl
    diameter, at the sheet scale, exactly when the axis stands vertical.
    """
    width, height = outline[2] - outline[0], outline[3] - outline[1]
    expected = (OVERALL_LENGTH - HEAD_DIA) * _S / 1000.0
    return abs((height - width) - expected) <= _OUTLINE_TOL


def _centre_section_outline(adapter: Any, view: Any) -> tuple[float, ...]:
    """Move section A-A until its outline (the ink) is centred on SECTION_CENTER.

    Reversing the cut swings the section's ink without moving the Position
    that ``SetViewPosition`` measures its move from: on run
    20261001T142942518Z, ``SetViewPosition(SECTION_CENTER)`` after the
    reversal left the seat projected at y 0.18915 -- where it sat rim-down,
    and one nut length (48.3 mm at 3:1) above where a centred rim-up section
    puts it.  As for a fresh detail view (layout-tuning catalogue j), the
    view is placed by its outline: ``SetViewPosition`` moves the ink by the
    difference from the Position it reads.
    """
    for attempt in range(4):
        outline = tuple(float(value) for value in view.GetOutline())
        position = tuple(float(value) for value in view.Position)
        centre = _outline_centre(outline)
        _telemetry.info(
            f"thumbnut section pass {attempt}: position={position} "
            f"outline={outline} outline_centre={centre}"
        )
        if math.dist(centre, SECTION_CENTER) <= _OUTLINE_TOL:
            break
        moved = [
            position[axis] + SECTION_CENTER[axis] - centre[axis] for axis in (0, 1)
        ]
        if not view.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre thumbnut section A-A")
        rebuild_drawing(adapter, label="thumbnut section re-centred")
    else:
        raise RuntimeError(
            f"thumbnut section A-A outline centre stayed at {centre}, "
            f"requested {SECTION_CENTER}"
        )
    if not _outline_is_the_nut_on_end(outline):
        raise RuntimeError(
            f"thumbnut section A-A outline {outline} is not the nut standing on its axis"
        )
    return outline


def _stand_section_rim_up(adapter: Any, section: Any) -> None:
    """Turn section A-A so the dished rim is up and the seat face down.

    The 19e33c6c2 render hung the rim at the bottom, under every dimension
    placed for a rim-up section and with the stem's diameters below the seat
    face on the SECTION A-A caption.  Looking from the other side of the cut
    should stand the nut up; if it does not, the view turns 180° instead.
    The rim test reads only the projection's direction; the section is then
    centred by its ink, and its projection re-read until the seat lands
    where SECTION_KEEP puts it.
    """
    native = _early_bound(section, "IView")

    def rim_is_up() -> bool:
        return _rim_is_up(*_seat_and_rim(adapter, native))

    if not rim_is_up():
        cut = _early_bound(native.GetSection(), "IDrSection")
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="thumbnut section reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("thumbnut section cut direction did not persist")
        if not rim_is_up():
            native.Angle = float(native.Angle) + math.pi
            rebuild_drawing(adapter, label="thumbnut section turned")
    outline = _centre_section_outline(adapter, native)
    expected = (SECTION_CENTER[0], _section_y(0.0))
    for attempt in range(3):
        seat, rim = _seat_and_rim(adapter, native)
        if _rim_is_up(seat, rim) and math.dist(seat, expected) <= _SEAT_PLACEMENT_TOL:
            break
        rebuild_drawing(adapter, label=f"settle thumbnut section, read {attempt}")
    else:
        raise RuntimeError(
            f"thumbnut section A-A is not rim up on its centre: seat={seat} "
            f"(expected {expected}), rim={rim}, outline={outline}"
        )
    _telemetry.info(
        f"thumbnut section rim up: angle={float(native.Angle):.6f} rad, "
        f"seat={seat}, rim={rim}, outline={outline}"
    )


def _seat_and_rim(
    adapter: Any, view: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet points of the seat face and the rim on the nut axis."""
    seat = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="thumbnut seat")
    rim = model_point_in_view(
        adapter, view, (0.0, OVERALL_LENGTH / 1000.0, 0.0), label="thumbnut rim"
    )
    return seat, rim


def _assert_native_thread(display: Any) -> None:
    """Read the real Hole Wizard callout; never substitute typed dimensions."""
    display = _early_bound(display, "IDisplayDimension")
    texts = [display.GetText(part) for part in (1, 2, 3, 4)]
    if any(not isinstance(text, str) for text in texts):
        raise RuntimeError("thumbnut native thread callout has an invalid readback")
    resolved = "".join(texts).replace(" ", "").replace("#", "").upper()
    if THREAD.replace("#", "") not in resolved or "UNC" not in resolved or "2B" not in resolved:
        raise RuntimeError(f"thumbnut native thread callout does not carry the source thread: {texts!r}")


@_telemetry.traced("drawing.thumbnut.tap_callout_thread_class")
def _omit_thread_class(display: Any) -> None:
    """Rule 2: the title block's THREADS row owns class 2B; the native tap
    variables stay live (draw_dt_cone_swing_platform's pattern).  Run
    20261024T041438788Z's review gated on the callout restating it."""
    if TAP_SPEC.thread_class != "2B":
        raise RuntimeError(
            "thumbnut tap: only the title block's default class 2B may be "
            f"omitted, got {TAP_SPEC.thread_class!r}"
        )
    omit_title_block_thread_class(display, label="thumbnut #8-32 tap")
    native = _early_bound(display, "IDisplayDimension")
    resolved = [str(native.GetText(part) or "") for part in (1, 2, 3, 4)]
    if any(TAP_SPEC.thread_class in text for text in resolved):
        raise RuntimeError(f"thumbnut tap callout still prints its class: {resolved!r}")


def _place_countersink_angle(adapter: Any, annotations: list[Any]) -> None:
    """Keep the native rear cone/axis arc local and move only its text outboard."""
    name = "CountersinkHalfAngle"
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"thumbnut needs one native {name}, got {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    # An inherited offset would move only text, leaving the old long arc.
    display.OffsetText = False
    if bool(display.OffsetText):
        raise RuntimeError("thumbnut countersink angle offset could not be reset")
    if not annotation.SetPosition2(*SECTION_KEEP[name], 0.0):
        raise RuntimeError("failed to position the thumbnut countersink angle arc")
    arc_position = annotation.GetPosition()
    if not arc_position or math.dist(
        (float(arc_position[0]), float(arc_position[1])), SECTION_KEEP[name]
    ) > 1e-5:
        raise RuntimeError(f"thumbnut countersink angle arc did not persist: {arc_position!r}")
    offset_dimension_text(adapter, [annotation], {name: COUNTERSINK_ANGLE_TEXT_XY})
    if not bool(display.OffsetText):
        raise RuntimeError("thumbnut countersink angle text did not stay offset")
    position = annotation.GetPosition()
    if not position or math.dist(
        (float(position[0]), float(position[1])), COUNTERSINK_ANGLE_TEXT_XY
    ) > 1e-5:
        raise RuntimeError(f"thumbnut countersink angle text did not persist: {position!r}")


@_telemetry.traced("drawing.thumbnut.arrows_inside")
def _set_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    """Stand each ARROWS_INSIDE dimension's arrows inside its extension lines,
    read back (draw_mg_magnifying_wheel's _set_arrows_inside)."""
    remaining = set(ARROWS_INSIDE)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        remaining.discard(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"thumbnut {name} did not keep its arrows inside")
    if remaining:
        raise RuntimeError(f"no thumbnut dimension to set arrows inside: {sorted(remaining)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open thumbnut source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Thumbnut Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear thumbnut; turned and knurled brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Top", *FACE_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        face,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="thumbnut axial section",
    )
    _stand_section_rim_up(adapter, section)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, section, iso):
        set_hidden_lines_removed(adapter, view)

    face_annotations = curate_view_dimensions(
        adapter,
        face,
        keep=FACE_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="axial section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*face_annotations, *section_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(
        adapter,
        section_annotations,
        _printable_above_callouts(DIMENSION_CALLOUTS_ABOVE),
        location="above",
    )
    set_dimension_callouts(
        adapter, section_annotations, DIMENSION_CALLOUTS_BELOW, location="below"
    )
    _place_countersink_angle(adapter, section_annotations)
    _set_arrows_inside(adapter, section_annotations)
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="thumbnut section A-A"
    )
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the thumbnut face view")
    # The tap-drill edge under the front countersink: the one visible circle
    # of the Hole Wizard feature from the front.
    thread_callout = add_native_hole_callout(
        adapter,
        face,
        edge=visible_circle_edge(adapter, face, TAP_DRILL_DIA),
        callout_xy=THREAD_CALLOUT_XY,
        label=f"{THREAD} UNC-2B through thread",
    )
    _assert_native_thread(thread_callout)
    _omit_thread_class(thread_callout)
    set_hole_callout_precision(
        thread_callout, {"hw-thrutapdrldia": 3}, label=f"{THREAD} through thread"
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Thumbnut Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own tapped-hole note to the face view once the
        # real native callout exists; it repeats the same thread.
        # tap drill, so the callout's radial leader crossed it (run
        # 20261001T151531763Z), and it cannot route clear while the callout's
        # text stays inside the left border.  finalize removes it before its
        # layout audit.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
