r"""Create the manufacturing drawing for MHA-DT-03-TL-03, the keyed cutting arbor.

Shop tooling (issue #2465). The side view draws the arbor as it lies between
its centres (rule 11): every diameter on its own step, every length a
baseline from the grip's end face with the overall tying the thread's end
(rule 10), both centre holes in symbol form. The end view from the thread
end, projected left of it, prints the keyseat's width and S on the seat's
outline. One note states the seat's matched fit and the keyseat's key; the
kit's fitting steps (MHA-DT-03-TL-05) say how the key is set.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
import dt_cone_gear_tl_keyed_arbor_spec as spec
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

SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_keyed_arbor"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

# Sheet metres. The 2.58 arbor at 3:1 spans 197 mm of the B sheet, its grip
# end right; the end view from the thread end stands left of it at the same
# scale and height (third-angle), the keyseat's width between the two. The
# isometric sits right of the grip end above the title block, the note block
# lower left. Nothing stands in the field below the title block's top (0.066).
SHEET_SCALE = (3.0, 1.0)
SIDE_SCALE = (3, 1)
ISO_SCALE = (1, 1)
SIDE_CENTER = (0.2083, 0.170)
END_CENTER = (0.045, 0.170)
ISO_CENTER = (0.375, 0.150)
NOTES_XY = (0.020, 0.060)
ISO_NOTE_XY = (0.345, 0.112)

# Side view, above the arbor: each diameter's text stands off its own step's
# dimension line (TEXT_GAP) on one side, at a rise over the grip's top. A
# text that reaches over a neighbouring step's dimension line stands above
# that line's own text, so no line strikes it: the relief's goes toward the
# tail, low; the tail centre's above it, alone on the tail face's line (the
# thread's, there too, stands on the end view: machinist review of farm
# 20261113T090619426Z); the seat's and the pilot's toward the head in a
# staircase over the keyseat end's set (KEYSEAT_END_SET_RISE), the pilot's
# highest. The standoff's stands at its step's middle: at the shoulder its
# dimension line crossed the keyseat end set's outside arrow (machinist
# review of farm 20261113T071241685Z).
TOWARD_HEAD = 1.0
TOWARD_TAIL = -1.0
TEXT_GAP = 0.003
DIA_TEXT: dict[str, tuple[float, float, float]] = {
    # name: (model station z mm, side, rise over the grip's top, m)
    "TailCentreDia": (spec.ARBOR_END_Z, TOWARD_TAIL, 0.028),
    "ReliefDia": (spec.RELIEF_END_Z, TOWARD_TAIL, 0.011),
    "PilotDia": (spec.PILOT_END_Z, TOWARD_HEAD, 0.036),
    "SeatDia": (spec.SEAT_END_Z, TOWARD_HEAD, 0.023),
    "StandoffDia": ((spec.GRIP_LENGTH + spec.SHOULDER_Z) / 2.0, TOWARD_HEAD, 0.014),
    "GripDia": (0.0, TOWARD_TAIL, 0.014),
    "HeadCentreDia": (0.0, TOWARD_HEAD, 0.014),
}
# The keyseat end's set: its short text toward the tail of the key's end,
# clear of the seat's step, just over the grip's top.
KEYSEAT_END_SET_RUN = 0.0066
KEYSEAT_END_SET_RISE = 0.006
# Below the arbor: every length a baseline from the grip's end face, the
# shortest nearest, each text at its span's middle (a longer span's
# extension line ends above a nearer tier, so none strikes a text).
LENGTH_SPANS_Z: dict[str, tuple[float, float, int]] = {
    "GripLength": (0.0, spec.GRIP_LENGTH, 1),
    "Shoulder": (0.0, spec.SHOULDER_Z, 2),
    "SeatEnd": (0.0, spec.SEAT_END_Z, 3),
    "PilotEnd": (0.0, spec.PILOT_END_Z, 4),
    "ReliefEnd": (0.0, spec.RELIEF_END_Z, 5),
    "CentreOverall": (0.0, spec.ARBOR_END_Z, 6),
}
LENGTH_BASE = 0.012
LENGTH_TIER = 0.009
# The shoulder root's radius: toward the head of the shoulder, between the
# arbor and the first tier, where no extension line runs.
SHOULDER_R_RUN = 0.0176
SHOULDER_R_DROP = 0.006
# End view: S under the view, the width toward the side view. The width's
# stacked text (.0625 +.0020/.0000 over SEE NOTE 1) runs END_WIDTH_TEXT right
# of its position (farm 20261113T042822797Z's sheet); at END_WIDTH_RUN 0.027
# it reached over the tail centre's dimension line (machinist review r1-r3,
# rule 14), so it stands between the end view and that line. S's stacked text
# (.3355 +.0000/-.0040) prints END_S_TEXT wide, about the span between its
# extension lines, so centred there the floor's extension line struck its
# limits (machinist review of farm 20261113T071241685Z, rule 14): it stands
# outside, right of the floor's. The thread's circle sketch faces this view,
# so its designation leads to the circle from up and left, the one quarter
# free of S's extension lines, the width's and the side view's callouts
# (its diameter line runs through the centre).
END_S_DROP = 0.014
END_S_TEXT = 0.026
END_WIDTH_RUN = 0.015
END_WIDTH_RISE = 0.012
END_WIDTH_TEXT = 0.027
END_THREAD_RUN = 0.012
END_THREAD_RISE = 0.032


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
        "keyend": (0.0, 0.0, spec.KEY_END_Z),
        "shoulder": (0.0, 0.0, spec.SHOULDER_Z),
    }
    sheet = _sheet_points(adapter, side, points, "keyed arbor side stations")
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
    keep["KeyseatEndSet"] = (
        sheet["keyend"][0] - outward * KEYSEAT_END_SET_RUN,
        top_y + KEYSEAT_END_SET_RISE,
    )
    keep["ShoulderR"] = (
        sheet["shoulder"][0] + outward * SHOULDER_R_RUN,
        bottom_y - SHOULDER_R_DROP,
    )
    return keep


def _end_keep(adapter: Any, end: Any) -> dict[str, tuple[float, float]]:
    """The keyseat's S under the end view, its width toward the side view and
    the thread's designation up and away from it."""
    radius = spec.SEAT_DIA / 2.0
    z = spec.SEAT_END_Z
    sheet = _sheet_points(
        adapter,
        end,
        {
            "keyseat": (radius, 0.0, z),
            "far": (-radius, 0.0, z),
            "floor": (spec.KEYSEAT_FLOOR_OFFSET, 0.0, z),
            "centre": (0.0, 0.0, z),
            "bottom": (0.0, -spec.GRIP_DIA / 2.0, z),
        },
        "end view keyseat",
    )
    if sheet["keyseat"][0] <= sheet["far"][0]:
        raise RuntimeError(
            "the end view draws the keyseat away from the side view: "
            f"keyseat {sheet['keyseat']}, far side {sheet['far']}"
        )
    return {
        "KeyseatS": (
            sheet["floor"][0] + TEXT_GAP + END_S_TEXT / 2.0,
            sheet["bottom"][1] - END_S_DROP,
        ),
        "KeyseatWidth": (
            sheet["keyseat"][0] + END_WIDTH_RUN,
            sheet["centre"][1] + END_WIDTH_RISE,
        ),
        "ThreadDia": (
            sheet["centre"][0] - END_THREAD_RUN,
            sheet["centre"][1] + END_THREAD_RISE,
        ),
    }


def _set_affixes(adapter: Any, annotations: list[Any]) -> None:
    """Each DIMENSION_PREFIXES / DIMENSION_SUFFIXES text, read back
    (draw_pd_transgear_thumbnut's countersink form)."""
    wanted = {
        (name, part): text
        for part, table in ((1, spec.DIMENSION_PREFIXES), (2, spec.DIMENSION_SUFFIXES))
        for name, text in table.items()
    }
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        for (target, part), text in list(wanted.items()):
            if target != name:
                continue
            display = _early_bound(
                _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            )
            display.SetText(part, text)
            if str(display.GetText(part) or "") != text:
                raise RuntimeError(f"keyed arbor {name} text {text!r} did not persist")
            del wanted[(target, part)]
    if wanted:
        raise RuntimeError(f"keyed arbor affixes not applied: {sorted(wanted)}")
    rebuild_drawing(adapter, label="keyed arbor centre-hole affixes")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open keyed arbor source", await adapter.open_model(str(SOURCE)))
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
            0: "Keyed Cone Gear Cutting Arbor Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: f"keyed tooth-cutting arbor; low-carbon steel; {spec.PART_NUMBER}",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SIDE_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=SIDE_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=_end_keep(adapter, end),
        view_label="end",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=_side_keep(adapter, side),
        view_label="side",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *end_annotations]
    assert_imported_precision(adapter, annotations, spec.DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, dict(spec.CALLOUTS_BELOW))
    _set_affixes(adapter, annotations)
    set_dimension_text(adapter, annotations, dict(spec.DIMENSION_TEXT))
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Keyed Cone Gear Cutting Arbor Drawing",
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
