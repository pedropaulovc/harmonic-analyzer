r"""Create the manufacturing drawing for MHA-DT-03-TL-07, the round cutting arbor.

Shop tooling (issue #2356; owner ruling 2026-11-20, Option 2). The keyed
arbor's sheet (``draw_dt_cone_gear_tl_keyed_arbor``) without its keyseat and
centre holes: the side view draws the arbor as it lies in the lathe (rule
11), every diameter on its own step, every length a baseline from the grip's
end face with the overall tying the thread's end (rule 10). No end view: with
no keyseat it would only repeat the side view's diameters as concentric
circles. One note states the seat's matched fit.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

import _telemetry
import dt_cone_gear_tl_round_arbor_spec as spec
from _check import check
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
    set_dimension_text,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_round_arbor"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

# Sheet metres. The 2.33 arbor at 3:1 spans 178 mm of the B sheet, its grip
# end right (the keyed arbor's side view); the isometric sits right of the
# grip end above the title block, the note block lower left. Nothing stands
# in the field below the title block's top (0.066).
SHEET_SCALE = (3.0, 1.0)
SIDE_SCALE = (3, 1)
ISO_SCALE = (1, 1)
SIDE_CENTER = (0.190, 0.170)
ISO_CENTER = (0.375, 0.150)
NOTES_XY = (0.020, 0.060)
ISO_NOTE_XY = (0.345, 0.112)

# Side view, above the arbor: each diameter's text stands off its own step's
# dimension line (TEXT_GAP) on one side, at a rise over the grip's top (the
# keyed arbor's layout). A text that reaches over a neighbouring step's
# dimension line stands above that line's own text, so no line strikes it:
# the thread's designation toward the head, low, over its own step; the
# relief's toward the tail above it; the seat's and the pilot's toward the
# head in a staircase, the pilot's highest; the standoff's at its step's
# middle.
TOWARD_HEAD = 1.0
TOWARD_TAIL = -1.0
TEXT_GAP = 0.003
DIA_TEXT: dict[str, tuple[float, float, float]] = {
    # name: (model station z mm, side, rise over the grip's top, m)
    "ThreadDia": (spec.ARBOR_END_Z, TOWARD_HEAD, 0.011),
    "ReliefDia": (spec.RELIEF_END_Z, TOWARD_TAIL, 0.021),
    "PilotDia": (spec.PILOT_END_Z, TOWARD_HEAD, 0.036),
    "SeatDia": (spec.SEAT_END_Z, TOWARD_HEAD, 0.023),
    "StandoffDia": ((spec.GRIP_LENGTH + spec.SHOULDER_Z) / 2.0, TOWARD_HEAD, 0.014),
    "GripDia": (0.0, TOWARD_TAIL, 0.014),
}
# Below the arbor: every length a baseline from the grip's end face, the
# shortest nearest, each text at its span's middle (a longer span's
# extension line ends above a nearer tier, so none strikes a text).
LENGTH_SPANS_Z: dict[str, tuple[float, float, int]] = {
    "GripLength": (0.0, spec.GRIP_LENGTH, 1),
    "Shoulder": (0.0, spec.SHOULDER_Z, 2),
    "SeatEnd": (0.0, spec.SEAT_END_Z, 3),
    "PilotEnd": (0.0, spec.PILOT_END_Z, 4),
    "ReliefEnd": (0.0, spec.RELIEF_END_Z, 5),
    "Overall": (0.0, spec.ARBOR_END_Z, 6),
}
LENGTH_BASE = 0.012
LENGTH_TIER = 0.009
# The shoulder root's radius: toward the head of the shoulder, between the
# arbor and the first tier, where no extension line runs.
SHOULDER_R_RUN = 0.0176
SHOULDER_R_DROP = 0.006


def _sheet_points(
    adapter: Any,
    view: Any,
    points_mm: dict[str, tuple[float, float, float]],
    label: str,
) -> dict[str, tuple[float, float]]:
    names = list(points_mm)
    projected = model_points_in_view(
        adapter,
        view,
        [tuple(value / 1000.0 for value in points_mm[name]) for name in names],
        label=label,
        names=names,
    )
    return dict(zip(names, projected, strict=True))


def _side_keep(adapter: Any, side: Any) -> dict[str, tuple[float, float]]:
    """Every side-view dimension's text position from the projected model."""
    top = spec.GRIP_DIA / 2.0
    points = {
        **{f"{name}@": (0.0, 0.0, z) for name, (z, _side, _rise) in DIA_TEXT.items()},
        **{
            f"{name}@": (0.0, 0.0, (a + b) / 2.0)
            for name, (a, b, _tier) in LENGTH_SPANS_Z.items()
        },
        "top": (0.0, top, 0.0),
        "bottom": (0.0, -top, 0.0),
        "head": (0.0, 0.0, 0.0),
        "tail": (0.0, 0.0, spec.ARBOR_END_Z),
        "shoulder": (0.0, 0.0, spec.SHOULDER_Z),
    }
    sheet = _sheet_points(adapter, side, points, "round arbor side stations")
    top_y, bottom_y = sheet["top"][1], sheet["bottom"][1]
    if top_y <= bottom_y:
        raise RuntimeError("the side view does not draw model +Y up")
    outward = math.copysign(1.0, sheet["head"][0] - sheet["tail"][0])
    keep: dict[str, tuple[float, float]] = {}
    for name, (_z, toward, rise) in DIA_TEXT.items():
        x = sheet[f"{name}@"][0] + toward * outward * TEXT_GAP
        keep[name] = (x, top_y + rise)
    for name, (_a, _b, tier) in LENGTH_SPANS_Z.items():
        keep[name] = (
            sheet[f"{name}@"][0],
            bottom_y - LENGTH_BASE - (tier - 1) * LENGTH_TIER,
        )
    keep["ShoulderR"] = (
        sheet["shoulder"][0] + outward * SHOULDER_R_RUN,
        bottom_y - SHOULDER_R_DROP,
    )
    return keep


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open round arbor source", adapter.open_model(str(SOURCE)))
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
            0: "Round Cutting Arbor Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: f"round tooth-cutting arbor; low-carbon steel; {spec.PART_NUMBER}",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SIDE_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        side,
        keep=_side_keep(adapter, side),
        view_label="side",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, spec.DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, dict(spec.CALLOUTS_BELOW))
    set_dimension_text(adapter, annotations, dict(spec.DIMENSION_TEXT))
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Round Cutting Arbor Drawing",
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
