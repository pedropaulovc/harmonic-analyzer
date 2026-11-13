r"""Create the fitting sheet for the keyed cutting arbor kit (MHA-DT-03-TL-05).

Shop fixture (issue #2465; ``dt_cone_gear_tl_arbor_assembly_spec``). One
sheet: the kit's side view at its 64T setup (the Ø1.75 collar and the nut on
the pilot, the other two collars beyond the arbor's end), every part
ballooned against the parts list; the blank's near face from the jaw step and
the seat's length as reference dimensions; three fitting steps; a shaded
isometric.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
import dt_cone_gear_tl_arbor_assembly_spec as spec
from _assembly_contract import assembly_contract
from _check import check
from _com import _early_bound
from _drawing_balloons import (
    BalloonAnchor,
    add_component_bom_balloons,
    assert_balloon_landings,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_high_quality_shaded_with_edges,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import _show_base_view_sketches, curate_view_dimensions
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_tables import bom_row_identities, insert_bom_table
from _drawing_types import DrawingLayout
from _drawing_view_configuration import (
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_arbor_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the arbor-kit sheet must remain landscape")

CONTRACT = assembly_contract("dt-cone-gear-tl-arbor")
DRAWING_NUMBER = CONTRACT.number
SHEET_SCALE = (2.0, 1.0)
SIDE_SCALE = (2.0, 1.0)
ISO_SCALE = (1.0, 1.0)
# Sheet metres. The side view's 4.0 in kit row spans 203 mm at 2:1 on the
# left; the parts list and the steps fill the right half above the title
# block (x >= 0.216 m, y <= 0.066 m); the isometric sits under the side view.
SIDE_CENTER = (0.120, 0.185)
ISO_CENTER = (0.110, 0.085)
ISO_NOTE_XY = (0.060, 0.050)
BOM_ANCHOR = (0.240, 0.262)
STEPS_XY = (0.240, 0.175)
BALLOON_MARGIN = 0.012
# The two settings' reference dimensions stand under the arbor, in tiers.
SETTING_DROP = {spec.STANDOFF_DIMENSION: 0.022, spec.SEAT_DIMENSION: 0.034}

BOM_COMPONENTS = spec.BOM_ORDER
# Each collar member's family (``<stem>--<member>``) is itself a leaf
# identity of its one occurrence (``_drawing_balloons._component_leaf``), so
# the default anchor finds it; an ``@<member>:1`` pin is a semantic reference
# selector, which only roles registered in ``_component_references`` resolve.
BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in BOM_COMPONENTS}
ISO_NOTE = f"ISOMETRIC VIEW SCALE {ISO_SCALE[0]:g}:{ISO_SCALE[1]:g}"


def _add_note(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> None:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the arbor-kit {label}")
    printed = (
        str(_early_bound(note, "INote").GetText() or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if printed != text:
        raise RuntimeError(f"arbor-kit {label} printed as {printed!r}")


def _bom_items(table: Any, configuration: str) -> dict[str, str]:
    """Each family's row, read through its native components: the steps cite
    the spec's item numbers, so the BOM must number the rows in BOM_ORDER."""
    rows = bom_row_identities(
        table,
        configuration=configuration,
        component_identities=dict(spec.COMPONENT_IDENTITIES),
    )
    printed = {stem: str(row) for stem, row in rows.items()}
    if printed != spec.BOM_ITEMS:
        raise RuntimeError(
            f"arbor-kit BOM numbers its rows {printed!r}, not {spec.BOM_ITEMS!r}"
        )
    return printed


def _settings(adapter: Any, side: Any) -> Any:
    """The two settings as reference dimensions under the arbor."""
    label = "arbor kit settings"
    _show_base_view_sketches(adapter, side, (spec.SETTINGS_SKETCH,), label=label)
    names = list(spec.SETTINGS)
    points = model_points_in_view(
        adapter,
        side,
        [
            (0.0, -radius / 1000.0, (start + end) / 2000.0)
            for radius, start, end in spec.SETTINGS.values()
        ],
        label=f"{label} stations",
        names=names,
    )
    keep = {
        name: (x, y - SETTING_DROP[name])
        for name, (x, y) in zip(names, points, strict=True)
    }
    annotations = curate_view_dimensions(
        adapter,
        side,
        keep=keep,
        view_label=label,
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    if len(annotations) != len(names):
        raise RuntimeError(f"{label}: expected {len(names)} dimensions")
    assert_imported_precision(
        adapter, annotations, dict(spec.DRAWING_PRECISION[spec.SETTINGS_SKETCH])
    )
    set_dimension_callouts(adapter, annotations, dict(spec.DIMENSION_CALLOUTS))
    displays = [
        set_reference_dimension(adapter, annotation, label=f"{label} reference")
        for annotation in annotations
    ]

    def settled() -> None:
        for display in displays:
            if (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != (
                "(",
                ")",
            ):
                raise RuntimeError(f"{label}: a setting is no longer a reference")

    return settled


def _place_sheet(adapter: Any) -> Any:
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SIDE_SCALE)
    set_hidden_lines_removed(adapter, side)
    configuration = apply_view_configuration(adapter, side, label="arbor kit *Right")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_high_quality_shaded_with_edges(adapter, iso, label="arbor kit isometric")
    apply_view_configuration(
        adapter, iso, role=ViewRole.FULL_DETAIL, label="arbor kit *Isometric"
    )
    assert_full_detail_view(adapter, label="arbor kit")

    table = insert_bom_table(
        adapter,
        side,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=dict(spec.BOM_DESCRIPTIONS),
        component_identities=dict(spec.COMPONENT_IDENTITIES),
        part_number_property="Number",
        label="arbor kit",
    )
    items = _bom_items(table, configuration)
    landings = add_component_bom_balloons(
        adapter,
        side,
        items=tuple((stem, items[stem]) for stem in BOM_COMPONENTS),
        anchors=BALLOON_ANCHORS,
        label="arbor-kit BOM coverage",
        margin=BALLOON_MARGIN,
        explode_offsets={},
    )
    if len(landings) != len(BOM_COMPONENTS):
        raise RuntimeError(
            f"arbor kit carries {len(landings)} balloons, expected {len(BOM_COMPONENTS)}"
        )
    settings_settled = _settings(adapter, side)
    for text, xy, label in (
        (spec.ASSEMBLY_STEPS, STEPS_XY, "fitting steps"),
        (ISO_NOTE, ISO_NOTE_XY, "isometric scale note"),
    ):
        _add_note(adapter, text, xy, label=label)

    def settled() -> None:
        assert_balloon_landings(adapter, landings)
        settings_settled()

    return settled


@_telemetry.traced("drawing.dt_cone_gear_tl_arbor_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open arbor-kit drawing source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        _early_bound(adapter.currentModel, "IModelDoc2"),
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != DRAWING_NUMBER:
        raise RuntimeError(
            f"arbor-kit source Number {properties['Number']!r} != {DRAWING_NUMBER!r}"
        )
    new_project_drawing(
        adapter, layout=SPEC.layout, scale=SHEET_SCALE, unit=CONTRACT.drawing_unit
    )
    settled = _place_sheet(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Keyed Cutting Arbor Kit Assembly Drawing",
        scale=SHEET_SCALE,
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
