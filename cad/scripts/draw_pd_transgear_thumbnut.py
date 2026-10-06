r"""Create the manufacturing drawing for the transgear thumbnut (MHA-PD-013).

The face view is the ``*Top`` orientation, looking at the dished front face:
it carries the native 1/4-20 through-thread callout with both countersinks
named under its thread line.  Section A-A cuts it on the nut axis through the
Front plane, the plane of the turned profiles and of two knurl crests, so the
knurl diameter, the head, waist and flange, the overall length from the seat
face and the dish's rim and floor diameters and its depth to the floor print
on solid cut edges.  No roughness symbol: the seat face clamps the wheel
(policy rule 5).
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
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from pd_transgear_thumbnut_spec import (
    CSK_QUALIFIER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_LENGTH,
    HEAD_DIA,
    HEAD_LENGTH,
    KNURL_CALLOUT,
    OVERALL_LENGTH,
    TAP_DRILL_DIA,
    WAIST_LENGTH,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


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

# A Ø20.5 × 16.1 nut: 3:1 leaves room round the section for its nine
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
# only air below their extension lines; the lengths stand off the right
# (head, overall) and the left (waist, dish depth) of the silhouette.  The
# dish depth's text stands above its rim extension line: at 3:1 the depth is
# shorter than the text is tall.  The waist and the flange are dimensioned
# across their own cut, each dimension line at its feature's height and its
# text out to the right: an extension line from either, run past the rim or
# the seat face, would cross the other's hatching, and nothing prints below
# the seat face, where the native SECTION A-A caption hangs.
_STEM_TEXT_X = _section_x(HEAD_DIA / 2.0) + 0.021
SECTION_KEEP = {
    "HeadDia": (SECTION_CENTER[0], _section_y(OVERALL_LENGTH) + 0.030),
    "DishDia": (SECTION_CENTER[0], _section_y(OVERALL_LENGTH) + 0.014),
    "DishFloorDia": (SECTION_CENTER[0], _section_y(OVERALL_LENGTH) + 0.006),
    "DishDepth": (
        _section_x(-HEAD_DIA / 2.0) - 0.016,
        _section_y(OVERALL_LENGTH) + 0.004,
    ),
    "HeadLength": (
        _section_x(HEAD_DIA / 2.0) + 0.014,
        _section_y(OVERALL_LENGTH - HEAD_LENGTH / 2.0),
    ),
    "OverallLength": (_section_x(HEAD_DIA / 2.0) + 0.032, SECTION_CENTER[1]),
    "WaistLength": (
        _section_x(-HEAD_DIA / 2.0) - 0.016,
        _section_y(FLANGE_LENGTH + WAIST_LENGTH / 2.0),
    ),
    "FlangeDia": (_STEM_TEXT_X, _section_y(FLANGE_LENGTH / 2.0)),
    "WaistDia": (_STEM_TEXT_X, _section_y(FLANGE_LENGTH + WAIST_LENGTH / 2.0)),
}
# The face view prints only the native thread callout.
FACE_KEEP: dict[str, tuple[float, float]] = {}
# Above the knurl diameter, the outermost of the rim's stack: the below lane
# would run into the dish chord.
DIMENSION_CALLOUTS_ABOVE = {"HeadDia": KNURL_CALLOUT}


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


def _thread_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Append the countersink line to the one compartment holding the thread."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected thread callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(f"thread line is not in one callout part: {definitions!r}")
    updated = dict(definitions)
    part = thread_parts[0]
    updated[part] = f"{updated[part].rstrip()}\n{CSK_QUALIFIER}"
    return updated


def _set_thread_callout_text(display: Any) -> None:
    """Name both countersinks under the native through-thread line."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _thread_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    thread = [text for text in resolved.values() if "UNC" in text]
    if (
        persisted != updated
        or len(thread) != 1
        or not thread[0].rstrip().endswith(CSK_QUALIFIER)
    ):
        raise RuntimeError(
            "thumbnut countersink line did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the thumbnut face view")
    # The tap-drill edge under the front countersink: the one visible circle
    # of the Hole Wizard feature from the front.
    thread_callout = add_native_hole_callout(
        adapter,
        face,
        edge=visible_circle_edge(adapter, face, TAP_DRILL_DIA),
        callout_xy=THREAD_CALLOUT_XY,
        label="1/4-20 through thread",
    )
    _set_thread_callout_text(thread_callout)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Thumbnut Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "1/4-20 Tapped Hole" note to the face view
        # once the tap carries a hole callout; the callout already states the
        # thread.  Its leader drops onto the countersink right beside the
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
