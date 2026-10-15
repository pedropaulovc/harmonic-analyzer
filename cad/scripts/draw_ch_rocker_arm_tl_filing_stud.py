r"""Create the drawing for the rocker arm hub filing stud (MHA-CH-006-TL-05)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    delete_view,
    dimension_name,
    iter_views,
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
from _drawing_dimensions import (
    assert_imported_precision,
    move_model_dimension,
    set_dimension_callouts,
    set_dimension_text,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import ch_rocker_arm_tl_filing_stud_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_filing_stud_spec import (
    BODY_DIA,
    BODY_LENGTH,
    DIMENSION_TEXT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEAD_LENGTH,
    REFERENCE_CALLOUTS,
    REFERENCE_DIMENSIONS,
    RELIEF_ROOTS_CALLOUT,
    RELIEF_WIDTH,
    SHOULDER_CALLOUT,
    STACK_CALLOUT,
    SURFACE_FINISHES,
    TAIL_END,
    THREAD_END,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_filing_stud"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A sixty-millimetre stud: 2:1 keeps the four steps legible on one turned profile.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
# One turned profile (axis horizontal, thread right) carries every size: the
# axial sizes as one baseline from the faced tip, each diameter beside its
# own step. The end view only donates the sketch diameters and is deleted.
PROFILE_CENTER = (0.170, 0.170)
# The view centres on the model box (tail end to thread end).
SEAT_X = PROFILE_CENTER[0] + (TAIL_END - THREAD_END) / 2.0 * _S
DONOR_CENTER = (0.330, 0.100)
ISO_CENTER = (0.355, 0.195)  # clear of the two-line fit callout
ISO_NOTE_XY = (0.295, 0.240)
NOTES_XY = (0.020, 0.075)
_TIP_X = SEAT_X + THREAD_END * _S
# Rows 15 mm apart: the seat row's stack callout stands between its value
# and its dimension line.
_ROW = 0.015


def _row(station_x_mm: float, row: int) -> tuple[float, float]:
    """Text over the middle of a tip-to-station span, rows stacked upward."""
    return (
        (_TIP_X + SEAT_X + station_x_mm * _S) / 2.0,
        PROFILE_CENTER[1] + 0.022 + row * _ROW,
    )


# Shortest span lowest so no extension line crosses another row's text. The
# seat's value and stack callout sit in the middle of their span, the
# callout's ends clear of the seat's and the tip's extension lines (Claude
# review: 2 mm left, the seat's line ran into "HOLDS"). The shoulder's value
# and its function callout are wider than its span: they stand right of the
# tip's extension line, clear of the profile.
_SHOULDER_TEXT_X = _TIP_X + 0.031
PROFILE_KEEP = {
    "ReliefEndStation": _row(BODY_LENGTH + RELIEF_WIDTH, 0),
    "ShoulderStation": (_SHOULDER_TEXT_X, _row(BODY_LENGTH, 1)[1]),
    "SeatStation": _row(0.0, 2),
    "HeadBackStation": _row(-HEAD_LENGTH, 3),
    "TailEndStation": _row(-TAIL_END, 4),
    # Corner radii, each a MAX. The seat's stands just up and right of its
    # corner and the relief roots' "2X" pair a full text gap above it, so
    # each reads as its own block (round-4 layout audit: 2.66 mm read as
    # one); both sit between the seat's and the shoulder's extension lines,
    # below the shoulder row. The tail root's text stands below and left of
    # its lower step corner, under the tail and clear of the head diameter's
    # text (round 4: led from above, its leader crossed that text).
    "SeatFilletR": (SEAT_X + 0.014, PROFILE_CENTER[1] + 0.0135),
    "ReliefRootR": (SEAT_X + 0.015, PROFILE_CENTER[1] + 0.026),
    "TailRootR": (SEAT_X - 0.021, PROFILE_CENTER[1] - 0.023),
}
# The diameter sketches sit on the seat plane (X0), so the tail's and the
# thread's extension lines ran from the seat through the head and the body
# and read as phantom steps (Claude review). Capped from their dimension
# lines (draw_dt_pinion_cam's _limit_witness_lines), each stays on its own
# step's silhouette: the tail's from its mid-length, the thread's within its
# ten-millimetre run (sheet metres).
WITNESS_CAPS = {"TailDia": 0.008, "ThreadDia": 0.006}
# swDimensionArrowsSide_e.swDimArrowsInside on the two shortest rows: left to
# the document's arrows outside, the relief end's dimension line ran left
# across the shoulder's extension line (round-3 layout audit) and the
# shoulder row's ran toward the relief roots' text.
ARROWS_INSIDE = 0
INSIDE_ARROW_ROWS = ("ReliefEndStation", "ShoulderStation")


_AXIS = ([1.0, 0.0, 0.0], ("__frame__",))
_FROM_TIP = ("tip_face", (("draw_ch_rocker_arm_tl_filing_stud", "build"),))


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME", ("_surface_finish", "ra")))

requirement("tip_face",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part_spec.THREAD_END),),
    requirements=(),
    fields={
        "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": part_spec.THREAD_END},
            ("THREAD_END",),
        ),
    },
)

requirement("button_seat",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), 0.0),),
    requirements=("dia", "station"),
    fields={
        "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "x", "value": 0.0}, ("__frame__",)),
        "dia": (limits(part_spec.HEAD_DIA, part_spec.HEAD_PLACES), ("HEAD_DIA",)),
        "dia_nominal": (part_spec.HEAD_DIA, ("HEAD_DIA",)),
        "station": (limits(part_spec.THREAD_END, part_spec.STATION_PLACES), ("THREAD_END",)),
        "station_nominal": (part_spec.THREAD_END, ("THREAD_END",)),
        "height_from": _FROM_TIP,
    },
    precision={"dia": part_spec.HEAD_PLACES, "station": part_spec.STATION_PLACES},
)

requirement("head_back_face",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), part_spec.HEAD_LENGTH),),
    requirements=("station",),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": -part_spec.HEAD_LENGTH},
            ("HEAD_LENGTH",),
        ),
        "station": (limits(part_spec.HEAD_BACK, part_spec.STOCK_PLACES), ("HEAD_BACK",)),
        "station_nominal": (part_spec.HEAD_BACK, ("HEAD_BACK",)),
        "height_from": _FROM_TIP,
    },
    precision={"station": part_spec.STOCK_PLACES},
)

requirement("body_shoulder",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part_spec.BODY_LENGTH),),
    requirements=("station",),
    fields={
        "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": part_spec.BODY_LENGTH},
            ("BODY_LENGTH",),
        ),
        "station": (
            limits(part_spec.SHOULDER_STATION, part_spec.STATION_PLACES),
            ("SHOULDER_STATION", ("ch_rocker_arm_spec", "HUB_LENGTH")),
        ),
        "station_nominal": (part_spec.SHOULDER_STATION, ("SHOULDER_STATION",)),
        "height_from": _FROM_TIP,
    },
    precision={"station": part_spec.STATION_PLACES},
)

# The full thread runs from the faced tip to the printed relief end; the
# relief takes the die's incomplete threads against the body shoulder.
requirement("thread",
    kind="boss",
    faces=(CylinderFace(part_spec.THREAD_MODEL_DIA),),
    requirements=("thread", "length"),
    fields={
        "axis": _AXIS,
        "thread": (part_spec.THREAD, ("THREAD",)),
        "length": (
            limits(part_spec.RELIEF_END_STATION, part_spec.STOCK_PLACES),
            ("RELIEF_END_STATION",),
        ),
        "length_nominal": (part_spec.RELIEF_END_STATION, ("RELIEF_END_STATION",)),
        "height_from": _FROM_TIP,
    },
    precision={"length": part_spec.STOCK_PLACES},
)

requirement("thread_relief",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.RELIEF_DIA,
            contains_x_mm=part_spec.BODY_LENGTH + part_spec.RELIEF_WIDTH / 2.0,
        ),
    ),
    requirements=("dia",),
    fields={
        "axis": _AXIS,
        "dia": (limits(part_spec.RELIEF_DIA, part_spec.RELIEF_PLACES), ("RELIEF_DIA",)),
        "dia_nominal": (part_spec.RELIEF_DIA, ("RELIEF_DIA",)),
    },
    precision={"dia": part_spec.RELIEF_PLACES},
)

DONOR_KEEP = {
    "TailDia": (0.300, 0.060),
    "HeadDia": (0.360, 0.060),
    "ReliefDia": (0.330, 0.060),
    "BodyDia": (0.300, 0.140),
    "ThreadDia": (0.360, 0.140),
}
PROFILE_DIAMETER_XY = {
    # Below the middle of the tail, clear of the vise-end extension line.
    "TailDia": (
        SEAT_X - (HEAD_LENGTH + TAIL_END) / 2.0 * _S,
        PROFILE_CENTER[1] - 0.030,
    ),
    "HeadDia": (SEAT_X - 0.020, PROFILE_CENTER[1] + 0.024),
    # Each diameter's dimension line stands inside its own step (codex round
    # 15): the fit callout on the journal (seat to shoulder), the relief floor
    # in its groove and the thread on the threaded tip (relief end to the
    # tip), all below so no leader crosses a row. The relief's value sits
    # under the thread's so its dimension line passes left of that text. The
    # journal's line stands near the shoulder: the finish symbol hangs under
    # the journal's seat end (the corner radii took the space above it).
    "BodyDia": (SEAT_X + (BODY_LENGTH - 2.5) * _S, PROFILE_CENTER[1] - 0.065),
    "ReliefDia": (
        SEAT_X + (BODY_LENGTH + RELIEF_WIDTH / 2.0) * _S,
        PROFILE_CENTER[1] - 0.045,
    ),
    "ThreadDia": (
        SEAT_X + (BODY_LENGTH + RELIEF_WIDTH + THREAD_END) / 2.0 * _S,
        PROFILE_CENTER[1] - 0.030,
    ),
}


requirement("locating_body",
    kind="boss",
    faces=(
        CylinderFace(part_spec.BODY_DIA, contains_x_mm=part_spec.BODY_LENGTH / 2.0),
    ),
    requirements=("note", "finish_ra"),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": _AXIS,
        "dia_nominal": (part_spec.BODY_DIA, ("BODY_DIA",)),
        "note": (
            part_spec.BODY_FIT_NOTE,
            (
                "BODY_FIT_NOTE",
                ("ch_rocker_arm_spec", "PIVOT_HOLE_DIA"),
                ("ch_rocker_arm_spec", "PIVOT_HOLE_BAND"),
            ),
        ),
        "finish_ra": (part_spec.MACHINED_UM, ("SURFACE_FINISHES",)),
    },
    precision={"finish_ra": 1},
)

requirement("vise_tail",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.TAIL_DIA,
            contains_x_mm=-(part_spec.HEAD_LENGTH + part_spec.TAIL_END) / 2.0,
        ),
    ),
    requirements=("dia", "station"),
    fields={
        "axis": _AXIS,
        "dia": (limits(part_spec.TAIL_DIA, part_spec.TAIL_PLACES), ("TAIL_DIA",)),
        "dia_nominal": (part_spec.TAIL_DIA, ("TAIL_DIA",)),
        "station": (limits(part_spec.OVERALL_LENGTH, part_spec.STOCK_PLACES), ("OVERALL_LENGTH",)),
        "station_nominal": (part_spec.OVERALL_LENGTH, ("OVERALL_LENGTH",)),
        "height_from": _FROM_TIP,
    },
    precision={"dia": part_spec.TAIL_PLACES, "station": part_spec.STOCK_PLACES},
)



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open filing-stud source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Arm Hub Filing Stud Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm hub filing stud; turned 4140; MHA-CH-006-TL-05",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    donor = place_view(adapter, str(SOURCE), "*Right", *DONOR_CENTER, scale=VIEW_SCALE)
    profile = place_view(
        adapter, str(SOURCE), "*Front", *PROFILE_CENTER, scale=VIEW_SCALE
    )
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (donor, profile, iso):
        set_hidden_lines_removed(adapter, view)

    donor_annotations = curate_view_dimensions(
        adapter,
        donor,
        keep=DONOR_KEEP,
        view_label="diameter donor",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="turned profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    diameters = [
        move_model_dimension(
            adapter,
            annotation,
            profile,
            PROFILE_DIAMETER_XY[dimension_name(adapter, annotation)],
            source_view=donor,
        )
        for annotation in donor_annotations
    ]
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")

    annotations = [*diameters, *profile_annotations]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_text(adapter, annotations, DIMENSION_TEXT)
    # drawing-guidelines.md rule 4: the seat station's stack reason rides it.
    set_dimension_callouts(
        adapter,
        annotations,
        {"SeatStation": STACK_CALLOUT, "ShoulderStation": SHOULDER_CALLOUT},
        location="below",
    )
    set_dimension_callouts(
        adapter, annotations, {"ReliefRootR": RELIEF_ROOTS_CALLOUT}, location="above"
    )
    for name, length in WITNESS_CAPS.items():
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one filing-stud {name} diameter dimension")
        display = _early_bound(
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        display.MaxWitnessLineLength = length
        if abs(float(display.MaxWitnessLineLength) - length) > 1e-9:
            raise RuntimeError(f"filing stud {name}: witness-line cap did not persist")
    for name in INSIDE_ARROW_ROWS:
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one filing-stud {name} station dimension")
        annotation = _early_bound(matches[0], "IAnnotation")
        row = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        row.ArrowSide = ARROWS_INSIDE
        if int(row.ArrowSide) != ARROWS_INSIDE:
            raise RuntimeError(f"filing stud {name} did not keep its arrows inside")
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one filing-stud {name} reference dimension")
        display = set_reference_dimension(
            adapter,
            matches[0],
            label=f"filing stud {name}",
            diameter=name.endswith("Dia"),
        )
        # drawing-guidelines.md rule 4 (tighten only for function, and name the mate) and drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the matched fit rides the callout.
        for part, text in zip((3, 4), REFERENCE_CALLOUTS.get(name, ())):
            if text:  # swDimensionTextCalloutAbove / CalloutBelow
                display.SetText(part, text)
                if str(display.GetText(part) or "") != text:
                    raise RuntimeError(f"filing stud {name} fit callout did not take")
    add_view_centerline(
        adapter, profile, face_xy=PROFILE_CENTER, label="stud turning axis"
    )
    # The sliding journal is a required machined surface (codex round 14):
    # on its lower silhouette near the seat, symbol hanging below it, left of
    # the journal's fit-callout line (the corner radii stand above).
    body_pick = (SEAT_X + 0.006, PROFILE_CENTER[1] - BODY_DIA / 2.0 * _S)
    add_surface_finish(
        adapter,
        profile,
        edge_xy=body_pick,
        entity_type="SILHOUETTE",
        symbol_xy=(SEAT_X + 0.004, PROFILE_CENTER[1] - 0.022),
        leader_attach_xy=body_pick,
        control=surface_finish_by_key(SURFACE_FINISHES, "locating_body"),
        label="filing stud locating diameter finish",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Hub Filing Stud Drawing",
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
