r"""Create the manufacturing drawing for MHA-DT-03-TL-03, the keyed cutting arbor.

Shop tooling (issue #2465). The side view draws the arbor as it lies on the
lathe (rule 11): every diameter on its own step, the grip's length from the
grip's end face, the standoff from the shoulder back to the jaw step, every
blank-side station from the shoulder, both centre holes in symbol form. A
removed section B-B across the seat prints the keyseat's width and S
(MHA-DT-04's section A-A form). One note names the seat's and keyseat's mates;
the kit's fitting steps (MHA-DT-03-TL-05) say how the key is set.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
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
from _drawing_sections import create_section_view
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

# The 2.58 arbor at 3:1 spans 197 mm of the B sheet's field; section B-B at
# 6:1 stands right of it, the isometric under B-B, the note block lower left.
SHEET_SCALE = (3.0, 1.0)
SIDE_SCALE = (3, 1)
SECTION_SCALE = (6, 1)
ISO_SCALE = (1, 1)
SIDE_CENTER = (0.165, 0.165)
SECTION_CENTER = (0.345, 0.185)
ISO_CENTER = (0.345, 0.105)
NOTES_XY = (0.020, 0.060)
ISO_NOTE_XY = (0.310, 0.080)
SECTION_LABEL = "B"
# The cutting line crosses the seat midway between the shoulder and the
# keyseat's straight run's end, reaching past the seat by this much (m).
SECTION_Z = spec.SHOULDER_Z + (spec.KEY_END_SET + spec.SEAT_LENGTH) / 2.0
SECTION_REACH_MM = spec.SEAT_DIA / 2.0 + 3.0

# Sheet tiers (m) off the arbor's silhouette: diameters stand above or below
# it, each at the station its circle's sketch occupies (MHA-DT-04's rule);
# lengths stand in tiers below.
DIA_RISE = {
    "GripDia": 0.022,
    "StandoffDia": 0.030,
    "SeatDia": -0.030,
    "PilotDia": 0.020,
    "ReliefDia": -0.050,
    "ThreadDia": 0.030,
}
DIA_STATION_Z = {
    "GripDia": 0.0,
    "StandoffDia": spec.SHOULDER_Z,
    "SeatDia": spec.SEAT_END_Z,
    "PilotDia": spec.PILOT_END_Z,
    "ReliefDia": spec.RELIEF_END_Z,
    "ThreadDia": spec.ARBOR_END_Z,
}
LENGTH_SPANS_Z = {
    "GripLength": (0.0, spec.GRIP_LENGTH, 1),
    "Standoff": (spec.GRIP_LENGTH, spec.SHOULDER_Z, 1),
    "SeatLength": (spec.SHOULDER_Z, spec.SEAT_END_Z, 3),
    "PilotEnd": (spec.SHOULDER_Z, spec.PILOT_END_Z, 4),
    "ReliefEnd": (spec.SHOULDER_Z, spec.RELIEF_END_Z, 5),
    "ThreadLength": (spec.RELIEF_END_Z, spec.ARBOR_END_Z, 1),
}
LENGTH_TIER = 0.011
LENGTH_BASE = 0.016
KEYSEAT_END_SET_RISE = 0.040
CENTRE_RUN = 0.030
SHOULDER_R_DROP = 0.020


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
        **{f"{name}@": (0.0, 0.0, z) for name, z in DIA_STATION_Z.items()},
        **{
            f"{name}@": (0.0, 0.0, (a + b) / 2.0)
            for name, (a, b, _tier) in LENGTH_SPANS_Z.items()
        },
        "top": (0.0, top, 0.0),
        "bottom": (0.0, -top, 0.0),
        "head": (0.0, 0.0, 0.0),
        "tail": (0.0, 0.0, spec.ARBOR_END_Z),
        "keyend": (0.0, 0.0, spec.KEY_END_Z),
        "shoulder": (0.0, -spec.STANDOFF_DIA / 2.0, spec.SHOULDER_Z),
    }
    sheet = _sheet_points(adapter, side, points, "keyed arbor side stations")
    top_y, bottom_y = sheet["top"][1], sheet["bottom"][1]
    if top_y <= bottom_y:
        raise RuntimeError("the side view does not draw model +Y up")
    outward = math.copysign(1.0, sheet["head"][0] - sheet["tail"][0])
    keep: dict[str, tuple[float, float]] = {}
    for name, rise in DIA_RISE.items():
        x = sheet[f"{name}@"][0]
        keep[name] = (x, top_y + rise if rise > 0 else bottom_y + rise)
    for name, (_a, _b, tier) in LENGTH_SPANS_Z.items():
        keep[name] = (sheet[f"{name}@"][0], bottom_y - LENGTH_BASE - tier * LENGTH_TIER)
    keep["KeyseatEndSet"] = (sheet["keyend"][0], top_y + KEYSEAT_END_SET_RISE)
    keep["HeadCentreDia"] = (sheet["head"][0] + outward * CENTRE_RUN, top_y + 0.012)
    keep["TailCentreDia"] = (sheet["tail"][0] - outward * CENTRE_RUN, top_y + 0.050)
    keep["ShoulderR"] = (
        sheet["shoulder"][0],
        sheet["shoulder"][1] - SHOULDER_R_DROP,
    )
    return keep


def _prepare_section(adapter: Any, view: Any) -> None:
    """Keep only the seat's cut face, at the section's own scale
    (draw_dt_cone_gear_shaft._prepare_d_section)."""
    bound = _early_bound(view, "IView")
    bound.UseParentScale = False
    bound.UseSheetScale = 0
    bound.ScaleRatio = double_array([float(SECTION_SCALE[0]), float(SECTION_SCALE[1])])
    cut = _early_bound(bound.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="section B cut face and scale")
    ratio = tuple(float(value) for value in bound.ScaleRatio)
    if bool(bound.UseParentScale) or not math.isclose(
        ratio[0] / ratio[1], SECTION_SCALE[0] / SECTION_SCALE[1]
    ):
        raise RuntimeError(f"section B scale did not persist: {ratio}")
    if not bool(cut.GetDisplayOnlySurfaceCut()):
        raise RuntimeError("section B kept geometry beyond the cut")


def _section(adapter: Any, side: Any) -> list[Any]:
    """Section B-B across the seat, carrying the keyseat's width and S."""
    reach = SECTION_REACH_MM
    ends = _sheet_points(
        adapter,
        side,
        {
            "start": (0.0, -reach, SECTION_Z),
            "end": (0.0, reach, SECTION_Z),
        },
        "section B cutting line",
    )
    view = create_section_view(
        adapter,
        side,
        line_start=ends["start"],
        line_end=ends["end"],
        view_xy=SECTION_CENTER,
        section_label=SECTION_LABEL,
        scale=SECTION_SCALE,
        partial=False,
        label="seat section",
    )
    _prepare_section(adapter, view)
    keyseat = _sheet_points(
        adapter,
        view,
        {
            "keyseat": (spec.SEAT_DIA / 2.0, 0.0, SECTION_Z),
            "far": (-spec.SEAT_DIA / 2.0, 0.0, SECTION_Z),
        },
        "section B keyseat side",
    )
    side_sign = math.copysign(1.0, keyseat["keyseat"][0] - keyseat["far"][0])
    keep = {
        "KeyseatS": (SECTION_CENTER[0], SECTION_CENTER[1] + 0.040),
        "KeyseatWidth": (
            keyseat["keyseat"][0] + side_sign * 0.025,
            SECTION_CENTER[1] + 0.012,
        ),
    }
    return curate_view_dimensions(
        adapter,
        view,
        keep=keep,
        view_label="section B",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )


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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, iso):
        set_hidden_lines_removed(adapter, view)

    section_annotations = _section(adapter, side)
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=_side_keep(adapter, side),
        view_label="side",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *section_annotations]
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
