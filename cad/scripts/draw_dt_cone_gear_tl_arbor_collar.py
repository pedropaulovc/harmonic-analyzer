r"""Create the drawing for MHA-DT-03-TL-04, the keyed arbor's backing collars.

Shop tooling (issue #2465). One sheet per member (the base bar's recipe,
``draw_ch_rocker_arm_tl_oblique_base_bar``): the side view prints the outside
diameter (stock) and the length, the end view the drilled bore's callout,
and the member's caption names it as the kit's parts list does.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

import _telemetry
import dt_cone_gear_tl_arbor_collar_spec as spec
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
    move_model_dimension,
    set_dimension_callouts,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _printed_limits import drilled_limits, limits
from _purchased_variant_drawing import configure_reference_views
from _session import run_build

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_arbor_collar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
MEMBER_SHEETS = dict(zip(spec.SHEET_NAMES, spec.CONFIGURATIONS, strict=True))

# Every sheet at 2:1: the Ø1.75 end view spans 89 mm, the side view stands
# right of it in line, the isometric right of the side view with its label
# under it, both clear above the title block's top (0.066).
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 1)
END_CENTER = (0.110, 0.165)
SIDE_CENTER = (0.240, 0.165)
ISO_CENTER = (0.340, 0.150)
NOTE_XY = (0.030, 0.060)
ISO_NOTE_XY = (0.305, 0.110)
# Both diameters import on the end view, where every diameter line runs
# through the centre: two crossed there (machinist review r1-r3 of farm
# 20261113T042822797Z). The bore keeps the end view, its callout up and right
# of it; the outside diameter is a donor there and moves onto the side view,
# right of the collar (rule 11: turned parts read like the lathe), the
# wheel-axle spacer's recipe (draw_mg_wheel_axle_spacer).
OD_DONOR_RISE = 0.012
OD_SIDE_RUN = 0.020
BORE_RUN = 0.030
# The bore's leader climbs at least this far to its text, clear of the
# horizontal centreline on the smallest member.
BORE_RISE_MIN = 0.015
LENGTH_DROP = 0.014
# The outside diameter's text on the side view: right of the collar at its
# axis, so its dimension line stands off the part.
OD_ON_SIDE = (
    SIDE_CENTER[0] + spec.LENGTH * VIEW_SCALE[0] / 2000.0 + OD_SIDE_RUN,
    SIDE_CENTER[1],
)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what the member sheets print, in the part frame
# (build_dt_cone_gear_tl_arbor_collar: axis +Z through the origin; the face
# on the blank at z = 0, the datum end the length runs from; the face under
# the nut at z = LENGTH). Every member shares the bore and the length; each
# outside diameter is round bar left at stock (STOCK_CALLOUT), so it carries
# no band. The saved default member (C175) owns the shared faces; the other
# members name only their own outside diameter (their member STEPs). Each
# ``span`` is a diameter's model-Z extent. The declarations print nothing.
_P = spec.DRAWING_PRECISION_BY_NAME
_DEFAULT = spec.CONFIGURATIONS[0]
part_metadata(
    model_sources=("LENGTH", "BORE", "OD_BY_CONFIGURATION"),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("LENGTH",)),
        "outward": ([0.0, 0.0, -1.0], ("LENGTH",)),
    },
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), spec.LENGTH),),
    requirements=("length",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": spec.LENGTH}, ("LENGTH",)),
        "outward": ([0.0, 0.0, 1.0], ("LENGTH",)),
        "length": (
            limits(spec.LENGTH, _P[spec.length_name(_DEFAULT)], unit=spec.UNIT),
            ("LENGTH", "UNIT", "DRAWING_PRECISION_BY_NAME"),
        ),
        "length_nominal": (spec.LENGTH, ("LENGTH",)),
        "length_from": ("datum_end", ("LENGTH",)),
    },
    precision={"length": _P[spec.length_name(_DEFAULT)]},
)
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(spec.BORE),),
    requirements=("dia", "thru"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("BORE",)),
        "at": ([0.0, 0.0, 0.0], ("BORE",)),
        "span": ([0.0, spec.LENGTH], ("LENGTH",)),
        "dia": (
            drilled_limits(spec.BORE, _P[spec.bore_name(_DEFAULT)], unit=spec.UNIT),
            ("BORE", "UNIT", "DRAWING_PRECISION_BY_NAME"),
        ),
        "nominal_dia": (spec.BORE, ("BORE",)),
        "thru": (True, ("BORE_CALLOUT",)),
        "process": ("drill", ("BORE_CALLOUT",)),
        "callout": (spec.BORE_CALLOUT, ("BORE_CALLOUT",)),
    },
    precision={"dia": _P[spec.bore_name(_DEFAULT)]},
)
_OD_FIELDS = {
    "axis": ([0.0, 0.0, 1.0], ("OD_BY_CONFIGURATION",)),
    "at": ([0.0, 0.0, 0.0], ("OD_BY_CONFIGURATION",)),
    "span": ([0.0, spec.LENGTH], ("LENGTH",)),
    "stock": (spec.STOCK_CALLOUT, ("STOCK_CALLOUT",)),
    "callout": (spec.STOCK_CALLOUT, ("STOCK_CALLOUT",)),
}
requirement(
    "outer",
    kind="diameter",
    faces=(CylinderFace(spec.OD_BY_CONFIGURATION["C175"]),),
    requirements=("stock",),
    fields={
        **_OD_FIELDS,
        "dia_ref": (
            spec.OD_BY_CONFIGURATION["C175"],
            ("OD_BY_CONFIGURATION", "DRAWING_PRECISION_BY_NAME"),
        ),
        "member": ("C175", ("CONFIGURATIONS",)),
        "quantity": (
            spec.QUANTITY_BY_CONFIGURATION["C175"],
            ("QUANTITY_BY_CONFIGURATION",),
        ),
    },
    precision={"dia_ref": _P[spec.od_name("C175")]},
)
requirement(
    "outer_c100",
    kind="diameter",
    faces=(CylinderFace(spec.OD_BY_CONFIGURATION["C100"]),),
    requirements=("stock",),
    configuration="C100",
    fields={
        **_OD_FIELDS,
        "dia_ref": (
            spec.OD_BY_CONFIGURATION["C100"],
            ("OD_BY_CONFIGURATION", "DRAWING_PRECISION_BY_NAME"),
        ),
        "member": ("C100", ("CONFIGURATIONS",)),
        "quantity": (
            spec.QUANTITY_BY_CONFIGURATION["C100"],
            ("QUANTITY_BY_CONFIGURATION",),
        ),
    },
    precision={"dia_ref": _P[spec.od_name("C100")]},
)
requirement(
    "outer_c050",
    kind="diameter",
    faces=(CylinderFace(spec.OD_BY_CONFIGURATION["C050"]),),
    requirements=("stock",),
    configuration="C050",
    fields={
        **_OD_FIELDS,
        "dia_ref": (
            spec.OD_BY_CONFIGURATION["C050"],
            ("OD_BY_CONFIGURATION", "DRAWING_PRECISION_BY_NAME"),
        ),
        "member": ("C050", ("CONFIGURATIONS",)),
        "quantity": (
            spec.QUANTITY_BY_CONFIGURATION["C050"],
            ("QUANTITY_BY_CONFIGURATION",),
        ),
    },
    precision={"dia_ref": _P[spec.od_name("C050")]},
)


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} view {name!r}")


def _draw_member_sheet(adapter: Any, configuration: str) -> None:
    """One member's sheet on the active sheet."""
    od = spec.OD_BY_CONFIGURATION[configuration]
    half = od * VIEW_SCALE[0] / 2000.0
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)
    configure_reference_views(adapter, configuration, [end, side, iso])
    od_name = spec.od_name(configuration)
    end_keep = {
        od_name: (END_CENTER[0], END_CENTER[1] + half + OD_DONOR_RISE),
        spec.bore_name(configuration): (
            END_CENTER[0] + half + BORE_RUN,
            END_CENTER[1] + max(half / 2.0, BORE_RISE_MIN),
        ),
    }
    side_keep = {
        spec.length_name(configuration): (
            SIDE_CENTER[0],
            SIDE_CENTER[1] - half - LENGTH_DROP,
        ),
    }
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=end_keep,
        view_label=f"{configuration} end",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=side_keep,
        view_label=f"{configuration} side",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    od_donors = [a for a in end_annotations if dimension_name(adapter, a) == od_name]
    if len(od_donors) != 1:
        raise RuntimeError(f"expected one {od_name} donor dimension on the end view")
    moved_od = move_model_dimension(
        adapter, od_donors[0], side, OD_ON_SIDE, source_view=end
    )
    annotations = [
        *(a for a in end_annotations if dimension_name(adapter, a) != od_name),
        *side_annotations,
        moved_od,
    ]
    printed = set(end_keep) | set(side_keep)
    assert_imported_precision(
        adapter,
        annotations,
        {n: p for n, p in spec.DRAWING_PRECISION_BY_NAME.items() if n in printed},
    )
    set_dimension_callouts(
        adapter,
        annotations,
        {
            od_name: spec.STOCK_CALLOUT,
            spec.bore_name(configuration): spec.BORE_CALLOUT,
        },
    )
    _activate_view(adapter, end, label=f"{configuration} end")
    if add_note(adapter, spec.member_label(configuration), *NOTE_XY) is None:
        raise RuntimeError(f"failed to add the {configuration} member caption")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open arbor collar source", adapter.open_model(str(SOURCE)))
    required = ("Number", "Material Specification", "Finish", "Quantity")
    read_required_properties(
        adapter.currentModel,
        ("Revision", "Title", *required, "Isometric View Note"),
        required=required,
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
            0: "Keyed Cutting Arbor Backing Collar Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: f"keyed arbor backing collars; low-carbon steel; {spec.PART_NUMBER}",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    create_blank_drawing_sheets(adapter, spec.SHEET_NAMES, label="arbor collar members")
    for sheet_name, configuration in MEMBER_SHEETS.items():
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"cannot activate the collar sheet {sheet_name!r}")
        _draw_member_sheet(adapter, configuration)
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Keyed Cutting Arbor Backing Collar Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=spec.SHEET_NAMES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
