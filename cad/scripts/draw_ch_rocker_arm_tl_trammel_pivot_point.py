r"""Create the drawing for the rocker template trammel's pivot point (MHA-CH-006-TL-18)."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

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
    set_dimension_callouts,
    set_reference_dimensions,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_trammel_pivot_point_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_trammel_pivot_point_spec import (
    CONE_LENGTH,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HARDENED_LENGTH,
    POINT_LENGTH,
    REFERENCE_DIMENSIONS,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_trammel_pivot_point"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A sixty-millimetre point: 4:1 keeps the tip cone and its flat legible on
# the one turned profile.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
# One turned profile (axis horizontal, tip left) carries every size: the
# lengths as one baseline from the theoretical apex below the axis, the
# diameters and the cone angle above it.
# Centred 20 mm right of the sheet's half-width so the tip-flat callout,
# whose text stands left of its dimension line, clears the left border.
PROFILE_CENTER = (0.190, 0.175)
# The view centres on the model box (apex to back face).
APEX_X = PROFILE_CENTER[0] - POINT_LENGTH / 2.0 * _S
ISO_CENTER = (0.355, 0.200)
ISO_SCALE = (1, 1)
ISO_NOTE_XY = (0.325, 0.245)


def _below(station_mm: float, row: int) -> tuple[float, float]:
    """Text over the middle of an apex-to-station span, rows stacked downward."""
    return (APEX_X + station_mm / 2.0 * _S, PROFILE_CENTER[1] - 0.025 - row * 0.025)


PROFILE_KEEP = {
    # Shortest span nearest the part so no extension line crosses a row.
    "HardenedLength": _below(HARDENED_LENGTH, 0),
    "PointLength": _below(POINT_LENGTH, 1),
    # Ten millimetres right of the cone-to-back midpoint: its block shares
    # rows with the four-line tip-angle callout, whose last line and shelf
    # end at ~145 mm, so this block starts clear of them rather than 1.4 mm
    # above them.
    "RodDia": (
        APEX_X + (CONE_LENGTH + POINT_LENGTH) / 2.0 * _S + 0.010,
        PROFILE_CENTER[1] + 0.050,
    ),
    # The text stands left of its dimension line, just ahead of the apex.
    "TipFlatDia": (APEX_X - 0.010, PROFILE_CENTER[1] + 0.035),
    # The arc stays inside the narrow cone/axis wedge near the apex; only its
    # text moves outboard (TIP_ANGLE_TEXT_XY).
    "TipHalfAngle": (APEX_X + 0.012, PROFILE_CENTER[1] + 0.003),
}
# Four callout lines (value, side, the two seats by Number): higher and
# further right so the block clears the cone and the tip-flat callout.
TIP_ANGLE_TEXT_XY = (APEX_X + 0.040, PROFILE_CENTER[1] + 0.045)
# The axis pick sits on the shank face just off the axis, clear of the
# hardened-zone reference line the profile view shows on the axis (the
# pivot screw's pick).
CENTERLINE_PICK = (PROFILE_CENTER[0], PROFILE_CENTER[1] + 0.003)


_AXIS = ([1.0, 0.0, 0.0], ("__frame__",))
_FROM_APEX = ("tip_cone", (("draw_ch_rocker_arm_tl_trammel_pivot_point", "build"),))


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

# The printed half-angle each side of the axis, from the cone's surface.
requirement(
    "tip_cone",
    kind="face",
    faces=(ConeFace(part_spec.TIP_HALF_ANGLE),),
    requirements=("land_angle_deg",),
    fields={
        "axis": _AXIS,
        "angle_deg": (part_spec.TIP_ANGLE, ("TIP_ANGLE",)),
        "angle_tol_deg": (part_spec.TIP_ANGLE_TOL_DEG, ("TIP_ANGLE_TOL_DEG",)),
        "land_angle_deg": (
            [part_spec.TIP_HALF_ANGLE_MIN, part_spec.TIP_HALF_ANGLE_MAX],
            ("TIP_HALF_ANGLE_MIN", "TIP_HALF_ANGLE_MAX"),
        ),
        "land_angle_nominal_deg": (part_spec.TIP_HALF_ANGLE, ("TIP_HALF_ANGLE",)),
    },
    precision={"land_angle_deg": part_spec.TIP_HALF_ANGLE_PLACES},
)

# Drawing-guidelines rule 16: the flat truncating the point, MAX only.
requirement(
    "tip_flat",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -part_spec.TIP_FLAT_STATION),),
    requirements=("dia",),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": part_spec.TIP_FLAT_STATION},
            ("TIP_FLAT_STATION",),
        ),
        "dia": (
            limits(
                part_spec.TIP_FLAT_DIA,
                part_spec.TIP_FLAT_PLACES,
                part_spec.TIP_FLAT_DIA_BAND,
            ),
            ("TIP_FLAT_DIA", "TIP_FLAT_DIA_BAND"),
        ),
        "dia_nominal": (part_spec.TIP_FLAT_DIA, ("TIP_FLAT_DIA",)),
    },
    precision={"dia": part_spec.TIP_FLAT_PLACES},
)

requirement(
    "back_face",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part_spec.POINT_LENGTH),),
    requirements=("station",),
    fields={
        "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": part_spec.POINT_LENGTH},
            ("POINT_LENGTH",),
        ),
        "station": (
            limits(part_spec.POINT_LENGTH, part_spec.LENGTH_PLACES),
            ("POINT_LENGTH",),
        ),
        "station_nominal": (part_spec.POINT_LENGTH, ("POINT_LENGTH",)),
        "height_from": _FROM_APEX,
    },
    precision={"station": part_spec.LENGTH_PLACES},
)

# The drill rod's O.D. as supplied: a reference whose function rides on the
# callout naming the reamed point hole it slides in.
requirement(
    "shank",
    kind="boss",
    faces=(CylinderFace(part_spec.ROD_DIA),),
    requirements=("note",),
    fields={
        "axis": _AXIS,
        "dia_nominal": (part_spec.ROD_DIA, ("ROD_DIA",)),
        "note": (
            part_spec.ROD_NOTE,
            (
                "ROD_NOTE",
                ("ch_rocker_arm_tl_trammel_spec", "POINT_ROD_DIA_BAND"),
                ("ch_rocker_arm_tl_trammel_spec", "POINT_HOLE_DIA"),
            ),
        ),
    },
)


def _place_tip_angle(adapter: Any, annotations: list[Any]) -> None:
    """Keep the native cone/axis arc in its wedge and move only its text outboard."""
    name = "TipHalfAngle"
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"pivot point needs one native {name}, got {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    # An inherited offset would move only text, leaving the old long arc.
    display.OffsetText = False
    if bool(display.OffsetText):
        raise RuntimeError("pivot point tip angle offset could not be reset")
    if not annotation.SetPosition2(*PROFILE_KEEP[name], 0.0):
        raise RuntimeError("failed to position the pivot point tip angle arc")
    arc_position = annotation.GetPosition()
    if (
        not arc_position
        or math.dist(
            (float(arc_position[0]), float(arc_position[1])), PROFILE_KEEP[name]
        )
        > 1e-5
    ):
        raise RuntimeError(
            f"pivot point tip angle arc did not persist: {arc_position!r}"
        )
    offset_dimension_text(adapter, [annotation], {name: TIP_ANGLE_TEXT_XY})
    if not bool(display.OffsetText):
        raise RuntimeError("pivot point tip angle text did not stay offset")
    position = annotation.GetPosition()
    if (
        not position
        or math.dist((float(position[0]), float(position[1])), TIP_ANGLE_TEXT_XY) > 1e-5
    ):
        raise RuntimeError(f"pivot point tip angle text did not persist: {position!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-point source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Template Trammel Pivot Point Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker template trammel pivot point; O1 drill rod; MHA-CH-006-TL-18",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    profile = place_view(
        adapter, str(SOURCE), "*Front", *PROFILE_CENTER, scale=VIEW_SCALE
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
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_reference_dimensions(adapter, annotations, sorted(REFERENCE_DIMENSIONS))
    # drawing-guidelines.md rule 4: the rod reference names the hole it
    # slides in; the hardened extent and the flat say what they bound.
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="below")
    _place_tip_angle(adapter, annotations)
    add_view_centerline(
        adapter, profile, face_xy=CENTERLINE_PICK, label="pivot point axis"
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Template Trammel Pivot Point Drawing",
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
