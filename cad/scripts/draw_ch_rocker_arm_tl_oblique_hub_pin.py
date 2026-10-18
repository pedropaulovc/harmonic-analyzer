r"""Create the drawing for the oblique trammel's HUB locator pin (MHA-CH-006-TL-25)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
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
    dimension_name,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_hub_pin_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_oblique_hub_pin_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEAD_DIA,
    HEAD_LENGTH,
    OVERALL_LENGTH,
    PIN_LENGTH_REFERENCE,
    REFERENCE_CALLOUTS,
    SEAT_STATION,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_pin"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 24 mm pin: 4:1 keeps the lead chamfer legible on the one turned profile.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
# The *Right view lies the pin as it is turned: model +Z runs left, the head
# on the right (drawing-guidelines rule 11).
PROFILE_CENTER = (0.200, 0.165)
ISO_CENTER = (0.365, 0.215)
ISO_SCALE = (2, 1)
ISO_NOTE_XY = (0.335, 0.255)
_HEAD_HALF = HEAD_DIA / 2.0 * _S


def side_view_x(z_mm: float) -> float:
    """Sheet X of model station ``z_mm`` on the profile (+Z runs left)."""
    return PROFILE_CENTER[0] - (z_mm - OVERALL_LENGTH / 2.0) * _S


def _mid(z0: float, z1: float) -> float:
    return side_view_x((z0 + z1) / 2.0)


_ABOVE = PROFILE_CENTER[1] + _HEAD_HALF
_BELOW = PROFILE_CENTER[1] - _HEAD_HALF
# Above the view (sheet mm, as run 20261017T022004769Z printed them): a
# length's dimension line stands about 2.8 under its text position, and a
# chamfer's extension lines end about 4.6 under its own. Rule 11: the head
# thickness and the press seat are a baseline from the seating face (their
# shared extension line rises from the head's outer corner) on the row
# nearest the part, each carrying the dimension-origin circle there
# (close-c3-r3 review read the 12.0 as chained off the 4.0). The overall
# stands above them, high enough that its four-row fit-up (about 5.5 mm a
# row under its dimension line, about 84 mm wide inside its 96 mm of
# extension lines) clears the baseline row's text.
BASELINE_Y = _ABOVE + 0.012
OVERALL_Y = _ABOVE + 0.045
ORIGIN_DIMENSIONS = ("HeadLength", "SeatLength")
_ORIGIN_ARROWHEAD = 4  # swArrowStyle_e.swORIGIN_ARROWHEAD
_CLOSED_ARROWHEAD = 1  # swArrowStyle_e.swCLOSED_ARROWHEAD
# The chamfer stands under the overall's dimension line, so the overall
# crosses neither of its extension lines. Its callout block (about 59 mm
# wide with the MAX limit, centred on its position) ends 7.5 mm outboard of
# the top face, clear of the overall's extension line rising there.
CHAMFER_Y = _ABOVE + 0.009
CHAMFER_OUTBOARD = 0.037
# Below the view: a radius text is centred on its position, its shoulder
# 2.8 under it and its knee 13.7 toward the corner (the pivot pin's
# calibration from the same run). The head radius sits under the press seat,
# its knee 4.3 short of the head face and above the head's bottom outline;
# the press seat's diameter line moves 12 mm toward the locator (to z 13) so
# the radius text clears it by about 9 mm.
FILLET_XY = (side_view_x(HEAD_LENGTH) - 0.018, _BELOW + 0.004)
SEAT_DIA_STATION = 13.0
PROFILE_KEEP = {
    "HeadLength": (_mid(0.0, HEAD_LENGTH), BASELINE_Y),
    "SeatLength": (_mid(HEAD_LENGTH, SEAT_STATION), BASELINE_Y),
    "PinLength": (_mid(0.0, OVERALL_LENGTH), OVERALL_Y),
    "LeadChamfer": (side_view_x(OVERALL_LENGTH) - CHAMFER_OUTBOARD, CHAMFER_Y),
    "HeadDia": (side_view_x(0.0) + 0.030, PROFILE_CENTER[1]),
    "SeatDia": (side_view_x(SEAT_DIA_STATION), _BELOW - 0.020),
    "LocatorDia": (_mid(SEAT_STATION, OVERALL_LENGTH) - 0.045, _BELOW - 0.020),
    "HeadFilletR": FILLET_XY,
}
# The axis pick sits on the seat face just off the axis.
CENTERLINE_PICK = (_mid(HEAD_LENGTH, SEAT_STATION), PROFILE_CENTER[1] + 0.003)

_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
_FROM_HEAD = ("head_bottom", (("draw_ch_rocker_arm_tl_oblique_hub_pin", "build"),))
_FROM_SEATING = (
    "seating_face",
    (("draw_ch_rocker_arm_tl_oblique_hub_pin", "build"),),
)

part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

# Rule 11: the head's seating face (its top, bearing on the TL-21 carrier)
# is the baseline for the head thickness and the press seat.
requirement(
    "seating_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.HEAD_LENGTH),),
    requirements=(),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.HEAD_LENGTH},
            ("HEAD_LENGTH",),
        ),
    },
)

requirement(
    "head_bottom",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("station",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "station": (
            limits(part_spec.HEAD_LENGTH, part_spec.LENGTH_PLACES),
            ("HEAD_LENGTH",),
        ),
        "station_nominal": (part_spec.HEAD_LENGTH, ("HEAD_LENGTH",)),
        "height_from": _FROM_SEATING,
    },
    precision={"station": part_spec.LENGTH_PLACES},
)

# The step from the press seat down to the strap locator.
requirement(
    "seat_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.SEAT_STATION),),
    requirements=("station",),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.SEAT_STATION},
            ("SEAT_STATION",),
        ),
        "station": (
            limits(part_spec.SEAT_LENGTH, part_spec.LENGTH_PLACES),
            ("SEAT_LENGTH",),
        ),
        "station_nominal": (part_spec.SEAT_LENGTH, ("SEAT_LENGTH",)),
        "height_from": _FROM_SEATING,
    },
    precision={"station": part_spec.LENGTH_PLACES},
)

requirement(
    "head",
    kind="boss",
    faces=(CylinderFace(part_spec.HEAD_DIA),),
    requirements=("dia",),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(part_spec.HEAD_DIA, part_spec.HEAD_PLACES),
            ("HEAD_DIA", "HEAD_PLACES"),
        ),
        "dia_nominal": (part_spec.HEAD_DIA, ("HEAD_DIA",)),
    },
    precision={"dia": part_spec.HEAD_PLACES},
)

# The p6 press seat, modelled at its 10.218 low limit and printed +0.011/0:
# the matched fit on the carrier's HUB hole.
requirement(
    "press_seat",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.SEAT_DIA,
            contains_z_mm=(part_spec.HEAD_LENGTH + part_spec.SEAT_STATION) / 2.0,
        ),
    ),
    requirements=("dia",),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(part_spec.SEAT_DIA, part_spec.FIT_PLACES, part_spec.SEAT_PRINT_BAND),
            ("SEAT_DIA", "SEAT_PRINT_BAND"),
        ),
        "dia_nominal": (part_spec.SEAT_DIA, ("SEAT_DIA",)),
        "note": (part_spec.SEAT_NOTE, ("SEAT_NOTE", "HUB_HOLE_BAND")),
    },
    precision={"dia": part_spec.FIT_PLACES},
)

# The g6 strap locator, modelled at its 10.183 low limit and printed
# +0.011/0: the matched fit on the strap's hole (user ruling).
requirement(
    "strap_locator",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.LOCATOR_DIA,
            contains_z_mm=(part_spec.SEAT_STATION + part_spec.OVERALL_LENGTH) / 2.0,
        ),
    ),
    requirements=("dia",),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(
                part_spec.LOCATOR_DIA,
                part_spec.FIT_PLACES,
                part_spec.LOCATOR_PRINT_BAND,
            ),
            ("LOCATOR_DIA", "LOCATOR_PRINT_BAND"),
        ),
        "dia_nominal": (part_spec.LOCATOR_DIA, ("LOCATOR_DIA",)),
        "note": (part_spec.LOCATOR_NOTE, ("LOCATOR_NOTE", "STRAP_HOLE_BAND")),
    },
    precision={"dia": part_spec.FIT_PLACES},
)

# Rule 19: the top is faced to fit at assembly, so its 24.0 station is a
# reference; the requirement is the set height its note states.
requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.OVERALL_LENGTH),),
    requirements=(),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.OVERALL_LENGTH},
            ("OVERALL_LENGTH",),
        ),
        "station_nominal": (part_spec.OVERALL_LENGTH, ("OVERALL_LENGTH",)),
        "height_from": _FROM_HEAD,
        "note": (
            part_spec.PIN_LENGTH_NOTE,
            ("PIN_LENGTH_CALLOUT", "SUPPLY_LENGTH_MIN", "LOCATOR_SET_BAND"),
        ),
    },
)


def _arrowheads(annotation: Any, label: str) -> list[tuple[float, int]]:
    """Each arrowhead's tip x on the sheet and its style (draw_mg_wheel_axle).

    ``IDisplayData::GetArrowHeadAtIndex2`` returns tip[3], dir[3], width,
    height, style, normal[3]; a length dimension carries exactly two.
    """
    data = annotation.GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label} has no display data")
    data = _early_bound(data, "IDisplayData")
    heads = []
    for index in range(int(data.GetArrowHeadCount() or 0)):
        values = [float(value) for value in (data.GetArrowHeadAtIndex2(index) or ())]
        if len(values) < 9:
            raise RuntimeError(f"{label} arrowhead {index} is incomplete: {values!r}")
        heads.append((values[0], round(values[8])))
    if len(heads) != 2:
        raise RuntimeError(f"{label} has {len(heads)} arrowheads, expected 2")
    return heads


def _set_dimension_origin(
    adapter: Any, annotation: Any, *, origin_x: float, label: str
) -> None:
    """Put the dimension-origin circle on the arrowhead at ``origin_x``.

    Which arrowhead ``SetArrowHeadStyle2``'s first style lands on is the
    dimension's own order, so the styles are read back from the ink: if the
    circle came out at the far end, the pair is applied swapped and read
    again (draw_mg_wheel_axle).
    """
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    heads = _arrowheads(annotation, label)
    near = min(range(2), key=lambda index: abs(heads[index][0] - origin_x))
    styles = [_CLOSED_ARROWHEAD, _CLOSED_ARROWHEAD]
    styles[near] = _ORIGIN_ARROWHEAD
    for attempt in (styles, styles[::-1]):
        if not display.SetArrowHeadStyle2(False, *attempt):
            raise RuntimeError(f"failed to set the {label} arrowhead styles")
        rebuild_drawing(adapter, label=f"{label} dimension origin")
        heads = _arrowheads(annotation, label)
        at_origin = min(heads, key=lambda head: abs(head[0] - origin_x))
        far = max(heads, key=lambda head: abs(head[0] - origin_x))
        if (at_origin[1], far[1]) == (_ORIGIN_ARROWHEAD, _CLOSED_ARROWHEAD):
            return
    raise RuntimeError(f"{label} origin circle is not at the seating face: {heads!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open hub-pin source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel HUB Locator Pin Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "oblique trammel HUB locator pin; 1144 stress-proof; MHA-CH-006-TL-25",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    profile = place_view(
        adapter, str(SOURCE), "*Right", *PROFILE_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (profile, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="turned profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places and both fit bands are authored on the part; the sheet only
    # proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # drawing-guidelines rule 4: each fit names its mate on its callout.
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="below")
    # Rule 19: the overall is faced to fit at assembly; the modelled length
    # prints as a REFERENCE with its supply and set height above it.
    length_annotations = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == PIN_LENGTH_REFERENCE
    ]
    if len(length_annotations) != 1:
        raise RuntimeError("profile does not carry exactly one hub pin overall")
    set_reference_dimension(adapter, length_annotations[0], label="hub pin overall")
    set_dimension_callouts(adapter, annotations, REFERENCE_CALLOUTS, location="below")
    # Rule 11: the head and the press seat read from the seating face.
    origins = {
        dimension_name(adapter, annotation): annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) in ORIGIN_DIMENSIONS
    }
    if set(origins) != set(ORIGIN_DIMENSIONS):
        raise RuntimeError(
            f"profile is missing seating-face lengths: {sorted(origins)}"
        )
    for name in ORIGIN_DIMENSIONS:
        _set_dimension_origin(
            adapter, origins[name], origin_x=side_view_x(HEAD_LENGTH), label=name
        )
    add_view_centerline(adapter, profile, face_xy=CENTERLINE_PICK, label="hub pin axis")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel HUB Locator Pin Drawing",
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
