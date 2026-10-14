r"""Create the drawing for the rocker arm's riser block (MHA-CH-006-TL-10).

One sheet for both configurations: the main views draw the saved L036 (four
off); L045 (two off) differs only in length, so it gets one labelled front
view of its own configuration carrying the same model dimension, read back
at that configuration's value (the ``draw_pd_transgear_removable`` pattern).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    curate_dimensions,
    dimension_name,
    place_view,
    view_name,
)

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
from _drawing_dimension_import import (
    _INSERT_DIMS_MARKED,
    curate_view_dimensions,
    delete_unnamed_imports,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_riser_block_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_riser_block_spec import (
    BLOCK_HEIGHT,
    DEFAULT_CONFIG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTHS,
    QUANTITIES,
    SET_EQUALITY,
    configuration_number,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_riser_block"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 36-45 x 38.1 x 18.5 block: 2:1 keeps every view and its text legible.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# L036's front (length and height) with its right-side view (third angle,
# the stock width) and the shaded isometric; L045's front below L036's.
FRONT_CENTER = (0.125, 0.195)
RIGHT_CENTER = (0.225, 0.195)
ISO_CENTER = (0.345, 0.185)
ISO_NOTE_XY = (0.300, 0.255)
MANUFACTURING_NOTES_XY = (0.020, 0.070)
_HALF_HEIGHT = BLOCK_HEIGHT * _S / 2000.0
FRONT_KEEP = {
    "BlockLength": (FRONT_CENTER[0], FRONT_CENTER[1] + _HALF_HEIGHT + 0.0145),
    # The height alone left of the view, its two callout lanes in the margin.
    "BlockHeight": (0.050, FRONT_CENTER[1]),
}
RIGHT_KEEP = {"BlockWidth": (RIGHT_CENTER[0], RIGHT_CENTER[1] + _HALF_HEIGHT + 0.0145)}
# The height governs all six blocks of both lengths; the set requirement
# rides on it as the result, not the method. The width is the bar's own.
CALLOUTS_ABOVE = {"BlockHeight": "MATCHED SET OF SIX"}
CALLOUTS_BELOW = {
    "BlockHeight": f"EQUAL WITHIN {SET_EQUALITY:.2f}",
    "BlockWidth": "STOCK",
}

CONFIGURATION_VIEW_CENTERS = {
    DEFAULT_CONFIG: FRONT_CENTER,
    "L045": (0.130, 0.115),
}
# Above each configuration view, its length; below it, its label.
CONFIGURATION_DIMENSION_RISE = 0.0145
CONFIGURATION_LABEL_DROP = 0.010
if set(CONFIGURATION_VIEW_CENTERS) != set(LENGTHS):
    raise AssertionError("every riser block configuration needs its own view")


def configuration_keep(configuration: str) -> dict[str, tuple[float, float]]:
    """The one dimension a configuration view keeps, and where it prints."""
    x, y = CONFIGURATION_VIEW_CENTERS[configuration]
    return {"BlockLength": (x, y + _HALF_HEIGHT + CONFIGURATION_DIMENSION_RISE)}


def configuration_label(number: str, configuration: str) -> str:
    return f"{configuration_number(number, configuration)}  QTY {QUANTITIES[configuration]}"


def configuration_label_xy(configuration: str) -> tuple[float, float]:
    """Upper-left of the label: under the view, flush with its left end."""
    x, y = CONFIGURATION_VIEW_CENTERS[configuration]
    half_length = LENGTHS[configuration] * _S / 2000.0
    return (x - half_length, y - _HALF_HEIGHT - CONFIGURATION_LABEL_DROP)


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement(
    "support_top",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), part_spec.BLOCK_HEIGHT),),
    requirements=("height", "width"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": part_spec.BLOCK_HEIGHT},
            ("BLOCK_HEIGHT",),
        ),
        "height": (limits(part_spec.BLOCK_HEIGHT, 2), ("BLOCK_HEIGHT", "BAR_THICK")),
        "height_nominal": (part_spec.BLOCK_HEIGHT, ("BLOCK_HEIGHT",)),
        "width": (limits(part_spec.BLOCK_WIDTH, 1), ("BLOCK_WIDTH",)),
        "width_nominal": (part_spec.BLOCK_WIDTH, ("BLOCK_WIDTH",)),
    },
    precision={"height": 2, "width": 1},
)

requirement(
    "table_seat",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "height": (limits(part_spec.BLOCK_HEIGHT, 2), ("BLOCK_HEIGHT", "BAR_THICK")),
    },
    precision={"height": 2},
)


def _configure_views(adapter: Any, configuration: str, views: tuple[Any, ...]) -> None:
    """Point views at one source configuration and read every one back."""
    bound_views = tuple(_early_bound(view, "IView") for view in views)
    for view in bound_views:
        view.ReferencedConfiguration = configuration
    rebuild_drawing(adapter, label=f"{configuration} view configuration")
    for view in bound_views:
        observed = str(view.ReferencedConfiguration)
        if observed != configuration:
            raise RuntimeError(
                f"view configuration readback {observed!r} != {configuration!r}"
            )


def _curate_repeated_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
) -> list[Any]:
    """Import a model dimension the L036 front view already prints, into ``view``.

    ``InsertModelAnnotations3``'s ``DuplicateDims`` means *eliminate*
    duplicates when true, which would refuse the length the L036 front view
    already carries; the L045 view must print it again (the
    ``draw_pd_transgear_removable`` pattern), so this passes false and
    curates only the returned objects.
    """
    declared = set().union(*DRAWING_DIMENSIONS.values())
    unknown = sorted(set(keep) - declared)
    if unknown:
        raise RuntimeError(f"{view_label} keeps undeclared dimensions: {unknown}")
    drawing = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(drawing, "IDrawingDoc")
    name = view_name(adapter, view)
    if not bool(ddoc.ActivateView(name)):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    drawing.ClearSelection2(True)
    extension = _early_bound(drawing.Extension, "IModelDocExtension")
    if not bool(
        extension.SelectByID2(
            name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
        )
    ):
        raise RuntimeError(f"failed to select drawing view {name!r}")
    result = adapter._attempt(
        lambda: ddoc.InsertModelAnnotations3(
            0,  # swImportModelItemsFromEntireModel
            _INSERT_DIMS_MARKED,
            False,  # selected view only
            False,  # allow the dimension the L036 front view already prints
            True,  # include dimensions on construction/hidden features
            False,
        ),
        default=None,
    )
    drawing.ClearSelection2(True)
    if not result or isinstance(result, str):
        raise RuntimeError(f"{view_label} imported no marked model dimensions")
    annotations = delete_unnamed_imports(adapter, list(result))
    names = {dimension_name(adapter, annotation) for annotation in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=dict(keep)
    )
    present = {dimension_name(adapter, annotation) for annotation in curated}
    missing = sorted(set(keep) - present)
    if missing:
        raise RuntimeError(
            f"{view_label} is missing model dimensions {missing}; "
            f"available={sorted(present)}"
        )
    return curate_dimensions(adapter, curated, reposition=dict(keep))


_SPECIFY_CONFIGURATION = 3  # swInConfigurationOpts_e.swSpecifyConfiguration


def _assert_length(adapter: Any, annotations: list[Any], configuration: str) -> None:
    """Prove a view prints THIS configuration's length natively, at its places."""
    found = [a for a in annotations if dimension_name(adapter, a) == "BlockLength"]
    if len(found) != 1:
        raise RuntimeError(
            f"{configuration}: expected one BlockLength on its view, found {len(found)}"
        )
    display = _early_bound(
        _early_bound(found[0], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    places = int(display.GetPrimaryPrecision2())
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    values = dimension.GetSystemValue3(_SPECIFY_CONFIGURATION, configuration)
    if not isinstance(values, (list, tuple)) or len(values) != 1:
        raise RuntimeError(
            f"{configuration}: BlockLength value readback returned {values!r}"
        )
    measured_mm = abs(float(values[0])) * 1000.0
    expected_mm = LENGTHS[configuration]
    expected_places = DRAWING_PRECISION_BY_NAME["BlockLength"]
    if abs(measured_mm - expected_mm) > 1e-4 or places != expected_places:
        raise RuntimeError(
            f"{configuration}: sheet BlockLength reads {measured_mm:g} mm at {places} "
            f"places, expected {expected_mm:g} mm at {expected_places}"
        )
    _telemetry.success(f"{configuration}: sheet length {measured_mm:.{places}f} mm")


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    """Make ``view`` the active view (a note lands in the active view)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} view {name!r}")


def _label_configuration_view(
    adapter: Any, view: Any, number: str, configuration: str
) -> None:
    """Title a configuration view with its qualified Number and quantity.

    A model view has no native label the API can show, so the label is a note
    inserted while the view is ACTIVE: the view owns it and moves with it.
    Read back: the view carries that label exactly once.
    """
    _activate_view(adapter, view, label=configuration)
    text = configuration_label(number, configuration)
    if add_note(adapter, text, *configuration_label_xy(configuration)) is None:
        raise RuntimeError(f"failed to add the {configuration} view label")
    owned = [
        str(_early_bound(note, "INote").GetText() or "")
        for note in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if owned.count(text) != 1:
        raise RuntimeError(
            f"{configuration} view label did not land in its view: {owned!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open riser block source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    properties = read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    number = properties["Number"]
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Riser Block Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker riser block; L036 / L045; 1018 CR; MHA-CH-006-TL-10",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    _configure_views(adapter, DEFAULT_CONFIG, (front, right, iso))
    configuration_views = {
        configuration: place_view(
            adapter, str(SOURCE), "*Front", *center, scale=VIEW_SCALE
        )
        for configuration, center in CONFIGURATION_VIEW_CENTERS.items()
        if configuration != DEFAULT_CONFIG
    }
    for configuration, view in configuration_views.items():
        _configure_views(adapter, configuration, (view,))
    for view in (front, right, iso, *configuration_views.values()):
        set_hidden_lines_removed(adapter, view)

    face = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label=f"{DEFAULT_CONFIG} front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _assert_length(adapter, face, DEFAULT_CONFIG)
    annotations = [
        *face,
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    _label_configuration_view(adapter, front, number, DEFAULT_CONFIG)
    # The L036 front view imports first, so its import keeps eliminating
    # duplicates; each other configuration view prints the length again.
    for configuration, view in configuration_views.items():
        curated = _curate_repeated_dimensions(
            adapter,
            view,
            keep=configuration_keep(configuration),
            view_label=f"{configuration} front",
        )
        _assert_length(adapter, curated, configuration)
        annotations += curated
        _label_configuration_view(adapter, view, number, configuration)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    # The property-linked blocks land in the active view: the L036 front.
    _activate_view(adapter, front, label=f"{DEFAULT_CONFIG} front")
    add_property_linked_note(adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Riser Block Drawing",
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
