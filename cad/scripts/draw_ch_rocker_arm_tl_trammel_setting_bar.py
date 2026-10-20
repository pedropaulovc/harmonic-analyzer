r"""Create the drawing for the rocker trammel setting bar (MHA-CH-06-TL-17)."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _layout_audit import arc_segments
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_trammel_setting_bar_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_trammel_setting_bar_spec import (
    BAR_THICKNESS,
    BAR_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SEAT_DIA,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_trammel_setting_bar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 914 x 25.4 x 6.35 bar: 1:4 fits its length across the sheet with the
# stations from H0; section A-A through H0 at 4:1 carries the seat sizes.
SHEET_SCALE = (1.0, 4.0)
VIEW_SCALE = (1, 4)
SECTION_SCALE = (4, 1)
# The PDF carries a shaded view as a fixed ~120 dpi bitmap (every sheet of
# run 20261015T092257793Z), its edges as vectors over it. At 1:10 the bar's
# 6.35 mm side face is a 2-3 px band, so its raster steps show between the
# edge lines as a sawtooth; 1:5 doubles the band. The view stays in the
# empty lower-left, its outline clear of the title block and the notes'
# lines clear of the bar.
ISO_SCALE = (1, 5)
# The broad (seat) face, the edge view under it (third angle) carrying the
# cutting line through H0, the section to the right, the isometric below.
# x 0.160 leaves the pivot seat's callout clear of the border and the H0
# extension line.
TOP_CENTER = (0.160, 0.215)
FRONT_CENTER = (0.160, 0.165)
SECTION_CENTER = (0.330, 0.150)
ISO_CENTER = (0.140, 0.112)
ISO_NOTE_XY = (0.020, 0.118)
NOTES_XY = (0.020, 0.090)
# Top-view text offsets (sheet m) from H0's centre.
TOP_OFFSETS = {
    "BarLength": (0.102, -0.017),
    # Above the bar, clear of both extension lines.
    "BarWidth": (0.252, 0.012),
    # Outside the end's extension line: the H0 station chains on from it. Its
    # line shares H800X's row, which clears the 3X 12.7 arrow's tail.
    "H0FromEnd": (-0.022, 0.0168),
    # Left of the bar's end and under it, clear of both extension lines.
    "H0FromSide": (-0.020, -0.010),
    # The first row 8 mm above the bar's edge (the saw cradle's _GAP), the
    # second at the old 19 mm pitch: a value's dimension line sits 7.3 mm
    # under its text position, the PIVOT SEAT one's 5.6 mm.
    "H800X": (0.102, 0.0185),
    "H816X": (0.102, 0.0375),
}
# Cutting line through H0 on the edge view: past both faces.
CUT_OVERRUN = 0.008
# Section text offsets (sheet m) from H0's axis on the seat face; ``side`` is
# +1 where the flank-angle vertex lands right of the axis. The angle imports
# measuring the wedge inside the seat, so its arc ran through the pilot and
# the 1.98 dimension line; flipped to the vertically opposite wedge (above
# the face, outboard of the flank, the same 60 deg) its arc stays clear of
# both diameters. Its text sits about 20 mm out from the vertex, so the arc
# keeps both arrows inside beside it; the diameters go to the other side.
SECTION_OFFSETS = {
    "SeatFlankAngle": (0.025, 0.010),
    "PilotDia": (-0.035, 0.010),
    "SeatDia": (-0.035, 0.029),
}
# swDimArrowsInside: the 1.98 dimension's outside arrow tail ran out past
# the flank's extension line.
ARROWS_INSIDE = 0
INSIDE_ARROW_DIMENSIONS = ("PilotDia", "SeatFlankAngle")
# A drawn flank-angle arc may overrun its wedge's legs by this (sheet m), as
# cone gear's flat clock does.
ANGLE_ARC_OVERRUN = 0.0003
THICKNESS_TEXT_GAP = 0.010

# Functional acceptance sits on the dimension it governs, not in the notes;
# each scriber seat names the trammel part it holds. The pivot seat's mate
# (MHA-CH-06-TL-18) stays off its callout: above, it ran past the border in
# round 4; below, it would land on the bar and the 3X 12.7 extension line.
CALLOUTS_ABOVE = {
    "H0FromEnd": "PIVOT SEAT",
    "H0FromSide": "3X",
    "H800X": "INNER SCRIBER SEAT FOR MHA-CH-06-TL-16",
    "H816X": "OUTER SCRIBER SEAT FOR MHA-CH-06-TL-16",
    "SeatDia": "3X",
    "PilotDia": "3X",
}
# The length and thickness are the supply stock's (the bar is used at its
# 36 in supply length), read at their exact sizes; only the stations are cut.
CALLOUTS_BELOW = {
    "PilotDia": "DRILL THRU",
    "BarLength": "STOCK",
    "BarThickness": "STOCK",
}

_DOWN = [0.0, -1.0, 0.0]


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement(
    "seat_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), 0.0),),
    requirements=("thickness", "length", "width"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "thickness": (limits(part_spec.BAR_THICKNESS, 2), ("BAR_THICKNESS",)),
        "thickness_nominal": (part_spec.BAR_THICKNESS, ("BAR_THICKNESS",)),
        "length": (limits(part_spec.BAR_LENGTH, 1), ("BAR_LENGTH",)),
        "length_nominal": (part_spec.BAR_LENGTH, ("BAR_LENGTH",)),
        "width": (limits(part_spec.BAR_WIDTH, 1), ("BAR_WIDTH",)),
        "width_nominal": (part_spec.BAR_WIDTH, ("BAR_WIDTH",)),
    },
    precision={"thickness": 2, "length": 1, "width": 1},
)

requirement(
    "back_face",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), part_spec.BAR_THICKNESS),),
    requirements=("thickness",),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": -part_spec.BAR_THICKNESS},
            ("BAR_THICKNESS",),
        ),
        "thickness": (limits(part_spec.BAR_THICKNESS, 2), ("BAR_THICKNESS",)),
    },
    precision={"thickness": 2},
)

for label, x in part_spec.SEAT_STATIONS.items():
    station = (
        {
            "station": (
                limits(part_spec.H0_FROM_END, 1),
                ("H0_FROM_END", "BAR_LENGTH", "H816"),
            ),
            "station_nominal": (part_spec.H0_FROM_END, ("H0_FROM_END",)),
        }
        if x == 0.0
        else {
            "station": (
                limits(x, 2, part_spec.STATION_BAND),
                ("SEAT_STATIONS", "STATION_BAND"),
            ),
            "station_nominal": (x, ("SEAT_STATIONS",)),
        }
    )
    requirement(
        f"seat_{label.lower()}",
        kind="countersink",
        faces=(ConeFace(part_spec.SEAT_HALF_ANGLE_DEG, contains_x_mm=x),),
        requirements=("station", "dia", "land_angle_deg"),
        fields={
            "at": ([x, 0.0, 0.0], ("SEAT_STATIONS",)),
            "axis": (_DOWN, ("__frame__",)),
            **station,
            "dia": (
                limits(part_spec.SEAT_DIA, 2),
                ("SEAT_DIA", "CENTRE_DRILL_BODY_DIA"),
            ),
            "dia_nominal": (part_spec.SEAT_DIA, ("SEAT_DIA",)),
            "land_angle_deg": (
                limits(part_spec.SEAT_FLANK_ANGLE_DEG, 0, part_spec.SEAT_ANGLE_BAND),
                ("SEAT_FLANK_ANGLE_DEG", "SEAT_HALF_ANGLE_DEG", "SEAT_ANGLE_BAND"),
            ),
            "land_angle_nominal_deg": (
                part_spec.SEAT_FLANK_ANGLE_DEG,
                ("SEAT_FLANK_ANGLE_DEG",),
            ),
        },
        precision={
            "station": 1 if x == 0.0 else 2,
            "dia": DRAWING_PRECISION_BY_NAME["SeatDia"],
            "land_angle_deg": DRAWING_PRECISION_BY_NAME["SeatFlankAngle"],
        },
    )
    requirement(
        f"seat_{label.lower()}_pilot",
        kind="hole",
        faces=(CylinderFace(part_spec.PILOT_DIA, contains_x_mm=x),),
        requirements=("dia", "thru"),
        fields={
            "parent": (
                f"seat_{label.lower()}",
                (
                    "SEAT_STATIONS",
                    ("draw_ch_rocker_arm_tl_trammel_setting_bar", "build"),
                ),
            ),
            "dia": (
                limits(part_spec.PILOT_DIA, 2, part_spec.DRILLED_BAND),
                ("PILOT_DIA", "DRILLED_BAND"),
            ),
            "dia_nominal": (part_spec.PILOT_DIA, ("PILOT_DIA",)),
            "thru": (True, ("PILOT_DIA",)),
        },
        precision={"dia": 2},
    )


def _set_cut_face_only(adapter: Any, section: Any) -> None:
    cut = _early_bound(section.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="setting bar section A-A cut face only")
    if not cut.GetDisplayOnlySurfaceCut():
        raise RuntimeError(
            "setting bar section A-A retained geometry beyond the cutting plane"
        )


def _section_display(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [
        _early_bound(a, "IAnnotation")
        for a in annotations
        if dimension_name(adapter, _early_bound(a, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"section A-A: expected one {name}, found {len(matches)}")
    return matches[0], _early_bound(
        matches[0].GetSpecificAnnotation(), "IDisplayDimension"
    )


def _flank_angle_strays(
    display: Any, vertex: tuple[float, float], side: float
) -> list[tuple[float, float]]:
    """Drawn flank-angle arc points outside the wedge above the face and
    outboard of the flank's extension (0..60 deg from the face, outboard)."""
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    points = []
    for index in range(int(data.GetArcCount())):
        raw = tuple(float(value) for value in (data.GetArcAtIndex2(index) or ()))
        segments = arc_segments(raw)
        points += [(s.x0, s.y0) for s in segments] + [(s.x1, s.y1) for s in segments]
    if not points:
        raise RuntimeError("section A-A: the flank angle draws no arc")
    flank = math.radians(part_spec.SEAT_FLANK_ANGLE_DEG)
    strays = []
    for x, y in points:
        u, v = side * (x - vertex[0]), y - vertex[1]
        if (
            v < -ANGLE_ARC_OVERRUN
            or v * math.cos(flank) - u * math.sin(flank) > ANGLE_ARC_OVERRUN
        ):
            strays.append((x, y))
    return strays


def _flip_flank_angle_above_face(
    adapter: Any,
    section: Any,
    annotations: list[Any],
    vertex: tuple[float, float],
    side: float,
    text_xy: tuple[float, float],
) -> Any:
    """Flip the imported flank angle into the wedge above the face, as cone
    gear flips its flat clock: select it alone in its view, flip, re-seat the
    text, and read the drawn arc and the value back."""
    annotation, display = _section_display(adapter, annotations, "SeatFlankAngle")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name:
        raise RuntimeError("section A-A: the flank angle has no selection name")
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    imported = float(_read_member(dimension, "SystemValue"))
    flips: list[str] = []
    for flip in ("", "VerticallyOppositeAngle"):
        if flip:
            if not drawing.ActivateView(view_name(adapter, section)):
                raise RuntimeError("section A-A: failed to activate the view")
            model.ClearSelection2(True)
            if not model.Extension.SelectByID2(
                selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
            ):
                raise RuntimeError(
                    f"section A-A: failed to select the flank angle {selection_name!r}"
                )
            flipped = getattr(display, flip)()
            model.ClearSelection2(True)
            if not flipped:
                raise RuntimeError(f"section A-A: {flip} refused on the flank angle")
            flips.append(flip)
            if not annotation.SetPosition2(*text_xy, 0.0):
                raise RuntimeError("section A-A: failed to re-seat the flank angle")
            rebuild_drawing(adapter, label=f"setting bar flank angle {flip}")
        measured = float(_read_member(dimension, "SystemValue"))
        if abs(measured - imported) > 1e-9:
            raise RuntimeError(
                f"section A-A: {flips} changed the flank angle from "
                f"{math.degrees(imported):.4f} to {math.degrees(measured):.4f} deg"
            )
        strays = _flank_angle_strays(display, vertex, side)
        _telemetry.info(
            f"setting bar flank angle after {flips or ['import']}: "
            f"{len(strays)} arc point(s) outside the wedge above the face",
            flank_angle_flips=len(flips),
            flank_angle_stray_points=len(strays),
        )
        if not strays:
            return display
    raise RuntimeError(
        f"section A-A: flank angle arc still leaves the wedge above the face after "
        f"{flips}; first stray points "
        f"{[tuple(round(v * 1000, 1) for v in p) for p in strays[:3]]} mm"
    )


def _assert_settled_flank_angle(
    display: Any, vertex: tuple[float, float], side: float
) -> None:
    """After finalize's settling rebuild the arc still stays above the face
    (cone gear's clock was drawn as outside stubs after it, run
    20261010T073917031Z)."""
    strays = _flank_angle_strays(display, vertex, side)
    if strays or int(display.ArrowSide) != ARROWS_INSIDE:
        raise RuntimeError(
            f"section A-A: settled flank angle has {len(strays)} arc point(s) "
            f"outside its wedge, arrow side {int(display.ArrowSide)}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open trammel setting bar source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Trammel Setting Bar Drawing",
            1: "Harmonic Analyzer shop gauge drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker trammel setting bar; 1018 CF flat; MHA-CH-06-TL-17",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    seat_face, back_face = model_points_in_view(
        adapter,
        front,
        ((0.0, 0.0, 0.0), (0.0, -BAR_THICKNESS / 1000.0, 0.0)),
        label="H0 on the edge view",
        names=("seat face", "back face"),
    )
    section = create_section_view(
        adapter,
        front,
        line_start=(seat_face[0], seat_face[1] + CUT_OVERRUN),
        line_end=(back_face[0], back_face[1] - CUT_OVERRUN),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="setting bar section through H0",
    )
    _set_cut_face_only(adapter, section)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, front, section, iso):
        set_hidden_lines_removed(adapter, view)

    (h0,) = model_points_in_view(
        adapter, top, ((0.0, 0.0, 0.0),), label="H0 on the seat face"
    )
    top_keep = {
        name: (h0[0] + dx, h0[1] + dy) for name, (dx, dy) in TOP_OFFSETS.items()
    }
    axis, vertex, edge = model_points_in_view(
        adapter,
        section,
        (
            (0.0, 0.0, 0.0),
            # The H0 profile's mouth vertex: Right plane u = -z.
            (0.0, 0.0, -SEAT_DIA / 2000.0),
            (0.0, 0.0, BAR_WIDTH / 2000.0),
        ),
        label="H0 seat on section A-A",
        names=("seat axis", "flank vertex", "bar edge"),
    )
    side = 1.0 if vertex[0] > axis[0] else -1.0
    far_edge = axis[0] + abs(edge[0] - axis[0])
    section_keep = {
        name: (axis[0] + side * dx, axis[1] + dy)
        for name, (dx, dy) in SECTION_OFFSETS.items()
    }
    section_keep["BarThickness"] = (
        far_edge + THICKNESS_TEXT_GAP,
        axis[1] - BAR_THICKNESS * SECTION_SCALE[0] / SECTION_SCALE[1] / 2000.0,
    )

    annotations = [
        *curate_view_dimensions(
            adapter,
            top,
            keep=top_keep,
            view_label="seat face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            section,
            keep=section_keep,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    for name in INSIDE_ARROW_DIMENSIONS:
        _annotation, display = _section_display(adapter, annotations, name)
        display.ArrowSide = ARROWS_INSIDE
        if int(display.ArrowSide) != ARROWS_INSIDE:
            raise RuntimeError(f"section A-A: {name} did not keep its arrows inside")
    flank_vertex = (vertex[0], vertex[1])
    flank_angle = _flip_flank_angle_above_face(
        adapter,
        section,
        annotations,
        flank_vertex,
        side,
        section_keep["SeatFlankAngle"],
    )
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # No explicit centre marks: the round-2 auto-insert printed identical
    # duplicate marks at H800 and H816 (layout audit, duplicate-annotation).
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Trammel Setting Bar Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_settled_flank_angle(flank_angle, flank_vertex, side),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
