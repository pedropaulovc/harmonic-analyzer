r"""Create the manufacturing drawing for the rocker hub (MHA-CH-12).

Under ``cad/docs/drawing-guidelines.md``, in decimal inch (the part's
``drawing_unit: in``): the turned hub of the built-up rocker arm MHA-CH-06 as
SUPPLIED to the joint (``ch_rocker_hub_spec``), on three native model
dimensions: the Ø.400 land as a reference, turned to slide into the MHA-CH-13
strap hole with the diametral clearance and the compound stated below it
(rule 4, made to fit; owner ruling 2026-11-24, fit audit question 2), the
supply bore with
the title block's DRILLED HOLES row, and the supply length as a single MIN
limit (rule 19). The face view carries the bore; the side view, where a
turned part's diameter sits beside its length (rule 11), carries the land and
the length on its axis centerline. One property-linked note says where the
finished bore and length are given. No datums, no frames, no roughness
symbol (rule 6: a bonded land carries none). The decimal places and bands are
the PART's (``ch_rocker_hub_notes.DRAWING_PRECISION``); this script only reads
them back off the sheet.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_hub.py ch-rocker-hub
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _printed_limits import drilled_limits
import _telemetry
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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    move_model_dimension,
    set_dimension_callouts,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from ch_rocker_hub_notes import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LAND_CALLOUT,
    REFERENCE_DIMENSIONS,
    REFERENCE_PREFIX,
    REFERENCE_SUFFIX,
    SUPPLY_BORE_CALLOUT,
    SUPPLY_LENGTH_CALLOUT,
)
from ch_rocker_hub_fit import BOND_CLEARANCE
from ch_rocker_hub_spec import (
    LAND_DIA,
    STRAP_NUMBER,
    SUPPLY_BORE_DIA,
    SUPPLY_LENGTH_MIN,
    SUPPLY_WALL_MIN,
    UNIT,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_hub"]
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

# A Ø.400 x .32 hub at 4:1: the face view, the side view and the land's
# two-row callout right of it share one row midway between the top border and
# the title block; the isometric stands above-right of that callout.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FRONT_CENTER = (0.065, 0.175)  # face view: the land and bore circles
RIGHT_CENTER = (0.160, 0.175)  # side view: the hub along its axis
# Lower right, between the title block and the land's callout, which hangs
# east of its dimension line above the side view (round 6: at y .205 the
# pictorial sat under that block).
ISO_CENTER = (0.360, 0.125)
NOTES_XY = (0.020, 0.090)  # left of the title block, below the views
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
HALF_DIA = LAND_DIA / 2.0 * _S  # 0.0203
HALF_LEN = SUPPLY_LENGTH_MIN / 2.0 * _S  # 0.0163

# Both diameters import on the face view, where every diameter line runs
# through the centre: two would cross there. The bore keeps the face view, its
# value and two rows up-right of the circles; the land is a donor there
# (parked left, clear of the bore's leader) and moves onto the side view,
# right of the hub, where its callout block (~115 mm wide at its route row)
# clears both the hub and the isometric. Its text stands above the land's
# upper extension line, so the dimension line runs up to the block instead of
# through it (fan-out local repeat after round 5: between the arrows the
# lower half of the line struck the '(' of the REF row). The supply length
# hangs under the side view.
FRONT_KEEP = {
    "SupplyBore": (FRONT_CENTER[0] + 0.040, FRONT_CENTER[1] + HALF_DIA + 0.022),
    "LandDia": (FRONT_CENTER[0] - 0.030, FRONT_CENTER[1] - HALF_DIA - 0.020),
}
# "SUPPLY .32 MIN" outruns the 32.5 mm hub: centred (r1) it sat on
# both extension lines, so it stands right of the right one, the dimension
# line carried out to it, below the land's lower extension line; its note
# link hangs under it.
RIGHT_KEEP = {
    "SupplyLength": (
        RIGHT_CENTER[0] + HALF_LEN + 0.028,
        RIGHT_CENTER[1] - HALF_DIA - 0.016,
    ),
}
LAND_ON_SIDE = (RIGHT_CENTER[0] + HALF_LEN + 0.075, RIGHT_CENTER[1] + HALF_DIA + 0.022)
DIMENSION_CALLOUTS = {
    "LandDia": LAND_CALLOUT,
    "SupplyBore": SUPPLY_BORE_CALLOUT,
    "SupplyLength": SUPPLY_LENGTH_CALLOUT,
}

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (build_ch_rocker_hub: the hub axis is model Z through the origin, the
# annulus extruded mid-plane, so the two end faces sit at z = -/+ half the
# supply length). The end at -Z is the datum end the turned-part stations run
# from; each ``span`` is a diameter's model-Z extent. The land prints its Ø
# as a reference and the bond clearance that governs; the supply bore
# the title block's DRILLED HOLES row; the supply length a single MIN limit.
# The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_HALF = SUPPLY_LENGTH_MIN / 2.0
_NOTES = "ch_rocker_hub_notes"
_SELF = "draw_ch_rocker_hub"
part_metadata(
    model_sources=("LAND_DIA", "SUPPLY_BORE_DIA", "SUPPLY_LENGTH_MIN"),
    precision_sources=(
        (_NOTES, "DRAWING_PRECISION"),
        (_NOTES, "DRAWING_PRECISION_BY_NAME"),
    ),
)
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), _HALF),),
    requirements=("plane",),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": -_HALF},
            ("SUPPLY_LENGTH_MIN",),
        ),
        "outward": ([0.0, 0.0, -1.0], ("SUPPLY_LENGTH_MIN",)),
    },
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), _HALF),),
    requirements=("length_min",),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": _HALF},
            ("SUPPLY_LENGTH_MIN",),
        ),
        "outward": ([0.0, 0.0, 1.0], ("SUPPLY_LENGTH_MIN",)),
        "length_min": (
            SUPPLY_LENGTH_MIN,
            ("SUPPLY_LENGTH_MIN", "SUPPLY_LENGTH_TOL_TYPE"),
        ),
        "length_nominal": (SUPPLY_LENGTH_MIN, ("SUPPLY_LENGTH_MIN",)),
        "length_from": ("datum_end", ((_SELF, "RIGHT_KEEP"),)),
        "supply": (True, ((_NOTES, "SUPPLY_LENGTH_PREFIX"), (_NOTES, "DRAWING_NOTES"))),
        "callout": (SUPPLY_LENGTH_CALLOUT, ((_NOTES, "SUPPLY_LENGTH_CALLOUT"),)),
    },
    precision={"length_min": _P["SupplyLength"]},
)
# The land: the finished O.D. bonded into the strap's reamed hole, a
# reference turned to slide into it with the stated clearance (owner ruling
# 2026-11-24, fit audit question 2; LAND_CALLOUT).
requirement(
    "outer",
    kind="diameter",
    faces=(CylinderFace(LAND_DIA),),
    requirements=("diametral_clearance",),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("LAND_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("LAND_DIA",)),
        "span": ([-_HALF, _HALF], ("SUPPLY_LENGTH_MIN",)),
        "dia_ref": (
            LAND_DIA,
            ("LAND_DIA", (_NOTES, "REFERENCE_DIMENSIONS"), (_SELF, "LAND_ON_SIDE")),
        ),
        "diametral_clearance": (
            list(BOND_CLEARANCE),
            (("ch_rocker_hub_fit", "BOND_CLEARANCE"), (_NOTES, "LAND_CALLOUT")),
        ),
        "mate": (
            f"{STRAP_NUMBER} STRAP HOLE",
            ("STRAP_NUMBER", (_NOTES, "LAND_CALLOUT")),
        ),
        "mate_nominal_dia": (LAND_DIA, ("LAND_DIA",)),
        "bond": ("LOCTITE 638", ((_NOTES, "LAND_CALLOUT"),)),
        "callout": (LAND_CALLOUT, ((_NOTES, "LAND_CALLOUT"),)),
    },
    precision={"dia_ref": _P["LandDia"]},
)
# The supply bore: a D drill through, under the joined part's F drill (note 1).
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(SUPPLY_BORE_DIA),),
    requirements=("dia", "thru"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("SUPPLY_BORE_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("SUPPLY_BORE_DIA",)),
        "span": ([-_HALF, _HALF], ("SUPPLY_LENGTH_MIN",)),
        "dia": (
            drilled_limits(SUPPLY_BORE_DIA, _P["SupplyBore"], unit=UNIT),
            ("SUPPLY_BORE_DIA", "UNIT", (_SELF, "FRONT_KEEP")),
        ),
        "nominal_dia": (SUPPLY_BORE_DIA, ("SUPPLY_BORE_DIA",)),
        "thru": (True, ((_NOTES, "SUPPLY_BORE_CALLOUT"),)),
        "process": ("drill", ((_NOTES, "SUPPLY_BORE_CALLOUT"),)),
        "supply": (True, ((_NOTES, "SUPPLY_BORE_CALLOUT"), (_NOTES, "DRAWING_NOTES"))),
        "wall_min": (
            SUPPLY_WALL_MIN,
            ("SUPPLY_WALL_MIN", (_NOTES, "SUPPLY_WALL_TEXT")),
        ),
        "callout": (SUPPLY_BORE_CALLOUT, ((_NOTES, "SUPPLY_BORE_CALLOUT"),)),
    },
    precision={"dia": _P["SupplyBore"]},
)


def _assert_reference_brackets(adapter: Any, annotations: list[Any]) -> None:
    """The part brackets the land Ø as a reference (build_ch_rocker_hub); the
    import and the move must carry the brackets unchanged, or the sheet
    would print a bare Ø.400 under the title block's .XXX row
    (draw_ch_rocker_strap_tl_hub_plug._assert_part_text)."""
    names = set().union(*REFERENCE_DIMENSIONS.values())
    expected = {
        (slot, name): text
        for name in names
        for slot, text in ((1, REFERENCE_PREFIX), (2, REFERENCE_SUFFIX))
    }
    found: dict[tuple[int, str], str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in names:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        for slot in (1, 2):  # swDimensionTextPrefix, swDimensionTextSuffix
            found[(slot, name)] = str(display.GetText(slot) or "")
    if found != expected:
        raise RuntimeError(
            f"hub land reference brackets did not import: {found!r} != {expected!r}"
        )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-hub source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-rocker-hub"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Hub Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker hub; supply state; turned 1018",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # The bore reads as its circle on the face view; hidden lines off
    # everywhere (drawing-guidelines.md rule 9).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    land_donors = [
        a for a in front_annotations if dimension_name(adapter, a) == "LandDia"
    ]
    if len(land_donors) != 1:
        raise RuntimeError("expected one hub land donor dimension")
    moved_land = move_model_dimension(
        adapter, land_donors[0], right, LAND_ON_SIDE, source_view=front
    )
    annotations = [
        *(a for a in front_annotations if dimension_name(adapter, a) != "LandDia"),
        *right_annotations,
        moved_land,
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_reference_brackets(adapter, annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The template centre-marks the face view's circles as the view is placed
    # (draw_mg_wheel_drum: a second AutoInsertCenterMarks2 printed a duplicate).
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + HALF_DIA / 2.0),
        label="rocker hub axis centerline",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Hub Manufacturing Drawing",
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
