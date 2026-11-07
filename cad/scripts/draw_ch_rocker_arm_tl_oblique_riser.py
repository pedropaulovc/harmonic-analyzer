r"""Create the drawing for the oblique-trammel jig's 6061 riser (MHA-CH-06-TL-24)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _printed_limits import limits
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_riser_spec as part_spec
from ch_rocker_arm_tl_oblique_riser_spec import (
    BLANK_LENGTH,
    BLANK_WIDTH,
    CALLOUTS_ABOVE,
    CALLOUTS_BELOW,
    CL_HOLE,
    CR_HOLE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HUB_HOLE,
    REFERENCE_DIMENSIONS,
    ROW_COUNTS,
    SCREW_DIA,
    SCREW_DIA_PRINTED,
    SCREW_HOLES,
    STOP_DIA,
    STOP_HOLE_DIA,
    STOP_PIN_HOLES,
    THICKNESS,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_riser"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 350.52 x 42.926 x 6.096 blank: the plan view at 1:2 carries the outline,
# each carrier-located station as a REFERENCE value and the two end-stop
# holes' ordinary .XX stations (X stack below the view; row heights beside
# it), one callout per hole size above it for the carrier-located holes (the
# screw hole's and HUB relief's sizes from the part's blanked
# ScrewHoleReference and HubHoleReference sketches, the screw's countersink
# in its below text) and the stop holes' below and right of it (from the
# blanked StopHoleReference sketch on stop 2). Both #30 sizes print the .128
# design nominal over the actual .1285 cut, the HUB relief .472 over its
# 12 mm drill. Section A-A cuts across
# the width through screw hole 3 at 2:1 to show the thickness and the
# countersink's form; its caption sits below it. The shaded isometric sits
# bottom left.
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
SECTION_SCALE = (2, 1)
ISO_SCALE = (1, 4)
PLAN_CENTER = (0.150, 0.205)
SECTION_CENTER = (0.355, 0.215)
# Below the section's thickness dimension (review r5: the caption sat on the
# sectioned part).
CAPTION_XY = (0.355, 0.140)
# Bottom left, 8 mm (sheet) lower than before the stop stations joined the X
# stack: its last row (the length) now runs 20 mm lower, over the iso's high
# left end.
ISO_CENTER = (0.110, 0.062)
ISO_NOTE_XY = (0.060, 0.032)
# The cutting line runs across the width at screw hole 3, 7 mm (sheet) past
# both edges so its letters clear the outline; at screw 3 the arrows' letters
# fall between the Screw3X and Screw1X extension lines (jig-r6: at screw 1
# the letter sat on HubX's extension line and the row heights' baseline).
CUT_X = SCREW_HOLES[2][0]
CUT_Y = (-14.0, BLANK_WIDTH + 14.0)

_T = THICKNESS
# Sheet text runs about 2.05 mm a character, 4.5 mm tall. At 1:2 a model mm
# is half a sheet mm, so these pitches are twice the sheet's.
# X stack: rows 10 mm (sheet) apart, 5.5 mm of air between texts (jig-r6: at
# 5 mm the texts stood 0.48 apart).
_STACK_PITCH = 20.0
_STACK_TOP = -12.0
# Row heights right of the view: "2X (28.29)" is about 21 mm wide, so the
# dimensions stand 27 mm apart. The first stands 23 mm off the outline, the
# stops' outside "2X .19" and its shelf between them (machinist review of
# native run 26bb, FIX: at 14 mm the .19 line struck "2X (.64)" and the
# (.64) arrow struck "2X .19").
_ROW_PITCH = 54.0
_ROW_FIRST = BLANK_LENGTH + 46.0
# The stops' row height, 4 mm (sheet) off the outline. Native placement puts
# an outside text's left 1.5 mm right of its dimension line, its shelf
# running to 15.6 mm; its dimension and extension lines end left of the CL/CR
# row's centred text, and that row's outside arrow tail right of its shelf.
_STOP_ROW_X = BLANK_LENGTH + 8.0
# Callout blocks start this high, clear of the section arrows' letters.
_CALLOUT_Y = BLANK_WIDTH + 48.0


def _stack_row(index: int) -> float:
    return _STACK_TOP - index * _STACK_PITCH


# Model points (mm) off the part, mapped onto each view at run time.
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    # X stations from the left end, nearest the part first, length last. The
    # stop's and CL's spans are too short for their texts, which stand left of
    # the end (jig-r6: every baseline extension crossed it); CR's and stop
    # 2's texts stand right of the length's.
    "Stop1X": (-24.0, _stack_row(0), _T),
    "ClX": (-24.0, _stack_row(1), _T),
    "Screw3X": (SCREW_HOLES[2][0] / 2.0, _stack_row(2), _T),
    "Screw1X": (SCREW_HOLES[0][0] / 2.0, _stack_row(3), _T),
    "HubX": (HUB_HOLE[0] / 2.0, _stack_row(4), _T),
    "Screw2X": (SCREW_HOLES[1][0] / 2.0, _stack_row(5), _T),
    "Screw4X": (SCREW_HOLES[3][0] / 2.0, _stack_row(6), _T),
    "CrX": (CR_HOLE[0] - 45.0, _stack_row(7), _T),
    "Stop2X": (STOP_PIN_HOLES[1][0] - 45.0, _stack_row(8), _T),
    "BlankLength": (BLANK_LENGTH / 2.0, _stack_row(9), _T),
    # Row heights from the bottom edge, one line each ("2X (13.35)"), centred
    # in their spans. Each 2X pair's dimension stands right of the view, so
    # its extension line runs from the dimensioned left hole through its
    # partner (review r5), shortest nearest; the stock width stands right of
    # them, so its extension lines stop at the right end (jig-r6: on the left
    # they ran the length and crossed the section letter). The single HUB row
    # stands left. The stops' "2X .19" is the shortest, nearest the outline;
    # its span is too short for its text, which stands below the bottom edge
    # on a shelf right of its line (above it, it would meet the CL/CR row's
    # text).
    "StopY": (_STOP_ROW_X, -10.0, _T),
    "ClampY": (_ROW_FIRST, CL_HOLE[1] / 2.0, _T),
    "ScrewOuterY": (_ROW_FIRST + _ROW_PITCH, SCREW_HOLES[2][1] / 2.0, _T),
    "ScrewInnerY": (_ROW_FIRST + 2.0 * _ROW_PITCH, SCREW_HOLES[0][1] / 2.0, _T),
    "BlankWidth": (_ROW_FIRST + 2.0 * _ROW_PITCH + 44.0, BLANK_WIDTH / 2.0, _T),
    # Left of the CL station's text and its dimension line (review r7: this
    # dimension's lower arrow ran down through "(9.11)").
    "HubY": (-56.0, HUB_HOLE[1] / 2.0, _T),
    # One callout per carrier-located hole size above the view, left to
    # right: CL (2X), HUB, and the screw holes' (leader to screw 2, the
    # reference circle's hole), which carries the countersink. Each ends in
    # two location rows. The retained 0c3 CL ink/shelf needs 3 mm right and
    # 1.0 mm up on paper: the left border gains air and the diagonal stays
    # above A-A's upper tail. Moving right alone would repeat review r12's
    # crossing. (Up 1.0, not 0c3's 1.5: the 1.778 wider blank already lifts
    # every block above the view .445 on paper.)
    # The screw block stands past the right end
    # so its leader climbs past HUB's shoulder (jig-r8: with the location
    # rows HUB's shoulder ran to 189 mm on the sheet and screw 2's leader,
    # rising to a block centred at model X 300, crossed it at 175 mm).
    "ClampDia": (-20.0, _CALLOUT_Y + 12.0, _T),
    "HubDia": (HUB_HOLE[0], _CALLOUT_Y, _T),
    "ScrewDia": (BLANK_LENGTH + 10.0, _CALLOUT_Y + 8.0, _T),
    # The stop holes' block, below and right of stop 2 (the reference
    # circle's hole): its leader drops steeply past the right end's
    # extension line, under the stops' row-height shelf, and the block
    # stands right of every X-stack extension line and left of section A-A
    # (native run 26bb: centred at L + 50 its 48.7 mm ink came within 1.6 mm
    # of the length's extension line).
    "StopDia": (BLANK_LENGTH + 62.0, -80.0, _T),
}
# The thickness's text stands outside its 12 mm (sheet) span (jig-r6: its
# extension lines ran through "6.0 STOCK").
SECTION_KEEP: dict[str, tuple[float, float, float]] = {
    "BlankThick": (CUT_X, -6.0, _T + 9.0),
}

_UP = [0.0, 0.0, 1.0]
_CALC = "ch_rocker_arm_tl_oblique_trammel_spec"
_UNIT = part_spec.UNIT


def _limits(model: float, places: int) -> list[float]:
    """A general-band dimension's acceptance limits on the inch sheet: the
    title block's band about the value printed at ``places``."""
    return limits(model, places, unit=_UNIT)


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.THICKNESS),),
    requirements=("height", "length", "width"),
    fields={
        "normal": (_UP, ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.THICKNESS},
            ("THICKNESS",),
        ),
        "height": (
            _limits(part_spec.THICKNESS, part_spec.THICKNESS_PLACES),
            ("THICKNESS",),
        ),
        "height_nominal": (part_spec.THICKNESS, ("THICKNESS",)),
        "length": (
            _limits(part_spec.BLANK_LENGTH, part_spec.BLANK_PLACES),
            ("BLANK_LENGTH",),
        ),
        "length_nominal": (part_spec.BLANK_LENGTH, ("BLANK_LENGTH",)),
        "width": (
            _limits(part_spec.BLANK_WIDTH, part_spec.BLANK_PLACES),
            ("BLANK_WIDTH",),
        ),
        "width_nominal": (part_spec.BLANK_WIDTH, ("BLANK_WIDTH",)),
    },
    precision={
        "height": part_spec.THICKNESS_PLACES,
        "length": part_spec.BLANK_PLACES,
        "width": part_spec.BLANK_PLACES,
    },
)

requirement(
    "carrier_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "height": (
            _limits(part_spec.THICKNESS, part_spec.THICKNESS_PLACES),
            ("THICKNESS",),
        ),
    },
    precision={"height": part_spec.THICKNESS_PLACES},
)


_SCREW_SOURCES = ("SCREW_HOLES", "BLANK_ORIGIN", (_CALC, "RISER_SCREWS"))
_SCREW_DIA_SOURCES = ("SCREW_DIA_PRINTED", "SCREW_DIA", "SCREW_SPEC", "SCREW_BODY_DIA")
# (name, xy, cut dia, printed dia, station sources, dia sources): the wizard
# cuts the unchanged #4 clearance (#30 drill) inside the design Ø.128 +.004/0
# band, and the HUB's literal 12 mm drill lies inside its Ø.472 +.004/0.
_HOLE_ROWS = (
    *(
        (
            f"screw_hole_{i}",
            xy,
            SCREW_DIA,
            SCREW_DIA_PRINTED,
            _SCREW_SOURCES,
            _SCREW_DIA_SOURCES,
        )
        for i, xy in enumerate(SCREW_HOLES, start=1)
    ),
    (
        "hub_hole",
        HUB_HOLE,
        part_spec.HUB_DIA,
        part_spec.HUB_DIA_PRINTED,
        ("HUB_HOLE", "BLANK_ORIGIN", (_CALC, "HUB")),
        ("HUB_DIA_PRINTED", "HUB_DIA", "HUB_DRILL"),
    ),
    *(
        (
            name,
            xy,
            part_spec.CLAMP_DIA,
            part_spec.CLAMP_DIA,
            (f"{calc}_HOLE", "BLANK_ORIGIN", (_CALC, calc)),
            ("CLAMP_DIA",),
        )
        for name, xy, calc in (("cl_hole", CL_HOLE, "CL"), ("cr_hole", CR_HOLE, "CR"))
    ),
)
for name, (x, y), cut_dia, dia, sources, dia_sources in _HOLE_ROWS:
    dia_places = DRAWING_PRECISION_BY_NAME[
        {"hub_hole": "HubDia", "cl_hole": "ClampDia", "cr_hole": "ClampDia"}.get(
            name, "ScrewDia"
        )
    ]
    requirement(
        name,
        kind="hole",
        faces=(CylinderFace(cut_dia, contains_x_mm=x),),
        # The location is spotted from the carrier at assembly: the stations
        # are reference values, not banded requirements.
        requirements=("dia", "thru"),
        fields={
            "at": ([x, y, part_spec.THICKNESS], (*sources, "THICKNESS")),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "station_nominal": (x, sources),
            "width_nominal": (y, sources),
            "dia": (
                limits(dia, dia_places, part_spec.DRILLED_BAND),
                (*dia_sources, "DRILLED_BAND"),
            ),
            "dia_nominal": (dia, dia_sources),
            "thru": (True, dia_sources),
        },
        precision={"dia": dia_places},
    )

# The two loose end-stop pin holes are drilled at ordinary .XX stations from
# the blank's left end and lower edge, not spotted from the carrier, so their
# stations are banded requirements. The wizard cuts the actual #30 inside the
# .128 +.004/0 design band, as the screw holes'.
_STOP_SOURCES = ("STOP_PIN_HOLES", "BLANK_ORIGIN", "STOP_PIN_CARRIER_POINTS")
_STOP_DIA_SOURCES = ("STOP_HOLE_DIA", "STOP_DIA", "STOP_SPEC", "STOP_DRILL")
for index, ((x, y), x_name) in enumerate(
    zip(STOP_PIN_HOLES, ("Stop1X", "Stop2X"), strict=True), start=1
):
    x_places = DRAWING_PRECISION_BY_NAME[x_name]
    y_places = DRAWING_PRECISION_BY_NAME["StopY"]
    dia_places = DRAWING_PRECISION_BY_NAME["StopDia"]
    requirement(
        f"stop_hole_{index}",
        kind="hole",
        faces=(CylinderFace(STOP_DIA, contains_x_mm=x),),
        requirements=("dia", "thru", "station", "height"),
        fields={
            "at": ([x, y, part_spec.THICKNESS], (*_STOP_SOURCES, "THICKNESS")),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "station": (_limits(x, x_places), _STOP_SOURCES),
            "station_nominal": (x, _STOP_SOURCES),
            "height": (_limits(y, y_places), _STOP_SOURCES),
            "height_nominal": (y, _STOP_SOURCES),
            "dia": (
                limits(STOP_HOLE_DIA, dia_places, part_spec.DRILLED_BAND),
                (*_STOP_DIA_SOURCES, "DRILLED_BAND"),
            ),
            "dia_nominal": (STOP_HOLE_DIA, _STOP_DIA_SOURCES),
            "thru": (True, _STOP_DIA_SOURCES),
        },
        precision={"dia": dia_places, "station": x_places, "height": y_places},
    )

for index, (x, _y) in enumerate(SCREW_HOLES, start=1):
    requirement(
        f"screw_hole_{index}_countersink",
        kind="countersink",
        faces=(ConeFace(part_spec.CSK_ANGLE / 2.0, contains_x_mm=x),),
        requirements=("dia", "angle_deg"),
        fields={
            "parent": (
                f"screw_hole_{index}",
                ("SCREW_DIA", ("draw_ch_rocker_arm_tl_oblique_riser", "build")),
            ),
            "dia": (
                _limits(part_spec.CSK_DIA, part_spec.CSK_PLACES),
                ("CSK_DIA", "SCREW_HEAD_DIA_MAX", "CSK_DEPTH_MAX", "CSK_CALLOUT"),
            ),
            "dia_nominal": (part_spec.CSK_DIA, ("CSK_DIA",)),
            "angle_deg": (part_spec.CSK_ANGLE, ("CSK_ANGLE", "CSK_CALLOUT")),
            "angle_tol_deg": (
                part_spec.INCLUDED_ANGLE_TOL_DEG,
                ("INCLUDED_ANGLE_TOL_DEG",),
            ),
        },
        precision={"dia": part_spec.CSK_PLACES, "angle_deg": 0},
    )


def _view_mapper(adapter: Any, view: Any):
    """Return model point (mm) -> sheet xy (m) through the view's transform."""
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sheet(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([c / 1000.0 for c in model_mm])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    return to_sheet


def _set_row_count(adapter: Any, display: Any, name: str, prefix: str) -> None:
    display.SetText(1, prefix)  # swDimensionTextPrefix
    got = str(display.GetText(1) or "")
    if got != prefix:
        raise RuntimeError(f"{name} count prefix did not take: {got!r}")


def _mark_reference(adapter: Any, annotation: Any, name: str) -> None:
    """Parenthesise one station as a REFERENCE value; a row height shared by a
    hole pair carries its count in the same prefix, "2X (13.35)", one line
    (jig-r6: a count above the value overflowed the 6.7 mm span)."""
    display = set_reference_dimension(adapter, annotation, label=name)
    count = ROW_COUNTS.get(name)
    if count is not None:
        _set_row_count(adapter, display, name, f"{count} (")


def _mark_ordinary_row_count(adapter: Any, annotation: Any, name: str) -> None:
    """An ordinary (banded) row height shared by a hole pair: "2X .19"."""
    display = _early_bound(
        _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    _set_row_count(adapter, display, name, f"{ROW_COUNTS[name]} ")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open riser source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
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
            0: "Rocker Oblique Trammel Riser Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel riser; 6061 blank; MHA-CH-06-TL-24",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    on_plan = _view_mapper(adapter, plan)
    section = create_section_view(
        adapter,
        plan,
        line_start=on_plan((CUT_X, CUT_Y[0], _T)),
        line_end=on_plan((CUT_X, CUT_Y[1], _T)),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="riser screw-hole section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="riser")
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (plan, section):
        set_hidden_lines_removed(adapter, view)

    on_section = _view_mapper(adapter, section)
    annotations = [
        *curate_view_dimensions(
            adapter,
            plan,
            keep={name: on_plan(xyz) for name, xyz in PLAN_KEEP.items()},
            view_label="plan view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            section,
            keep={name: on_section(xyz) for name, xyz in SECTION_KEEP.items()},
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    # The carrier-located stations are REFERENCE values; the stop holes'
    # ordinary stations keep the title block's .XX band.
    referenced: set[str] = set()
    counted: set[str] = set()
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in REFERENCE_DIMENSIONS:
            _mark_reference(adapter, annotation, name)
            referenced.add(name)
        elif name in ROW_COUNTS:
            _mark_ordinary_row_count(adapter, annotation, name)
            counted.add(name)
    if referenced != REFERENCE_DIMENSIONS:
        raise RuntimeError(
            f"reference stations not marked: {sorted(REFERENCE_DIMENSIONS - referenced)}"
        )
    if counted != set(ROW_COUNTS) - REFERENCE_DIMENSIONS:
        raise RuntimeError(f"ordinary row counts not marked: {sorted(counted)}")
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Riser Drawing",
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
