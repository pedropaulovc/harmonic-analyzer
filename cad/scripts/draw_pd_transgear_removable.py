r"""Create the manufacturing drawing for the removable #25 sprocket (MHA-PD-009).

One sheet for the three configurations: the main views draw the saved T24,
and the property-linked SPROCKET DATA block lists what differs between T12,
T18 and T24 (the tooth count and the diameters it sets).  The face view
(``*Front``) carries the bore, the two drive-pin holes and their locations;
the edge view (``*Top``, third-angle above it) carries the plate thickness
and the outside diameter, whose dimensions lie in the revolve sketch's Top
plane.  The supplied outside diameter is reference-only, not a turning
operation.  T12 and T18 each get a labelled edge view of their configuration
carrying the same model dimension, read back at that configuration's value.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    _INSERT_DIMS_MARKED,
    DrawingOutputs,
    add_note,
    add_property_linked_note,
    assert_imported_precision,
    curate_dimensions,
    curate_view_dimensions,
    delete_unnamed_imports,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimensions,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)
from pd_transgear_removable_spec import (
    DEFAULT_CONFIG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_DIMENSIONS,
    PLATE,
    TEETH,
    outside_dia,
)

SPEC = DRAWINGS_BY_NAME["pd_transgear_removable"]
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

# The T24 is Ø52 over the tips: 2:1 draws it 104 wide and the Ø2.5 pin holes
# 5 wide, with room for the pin-location chain beside the face view.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.110, 0.150)
# Third-angle top view: the plate seen edge-on, 5.6 tall, above the face view.
TOP_CENTER = (FRONT_CENTER[0], 0.228)
ISO_CENTER = (0.335, 0.150)
GEAR_DATA_XY = (0.225, 0.262)
MANUFACTURING_NOTES_XY = (0.018, 0.060)

# Each pin centre dimension runs from the bore axis to its hole; the two
# stack into one vertical chain right of the teeth.  Each one's text sits
# beyond its own hole, above the chain for +Y and below it for -Y: printed
# inside the chain, each text was struck by the other's outside arrow tail.
_PIN_CHAIN_X = FRONT_CENTER[0] + 0.070
FRONT_KEEP = {
    "BoreDiaDim": (FRONT_CENTER[0] + 0.070, FRONT_CENTER[1] - 0.052),
    "PinPosDia": (FRONT_CENTER[0] - 0.075, FRONT_CENTER[1] + 0.060),
    "PinPosY": (_PIN_CHAIN_X, FRONT_CENTER[1] + 0.021),
    "PinNegY": (_PIN_CHAIN_X, FRONT_CENTER[1] - 0.021),
}
# The outside diameter stands above the edge view, between the tips'
# extension lines; the thickness right of it.
_TOP_EDGE_Y = TOP_CENTER[1] + PLATE * _S / 2000.0
TOP_KEEP = {
    "BlankDia": (TOP_CENTER[0], _TOP_EDGE_Y + 0.010),
    "BlankWidth": (TOP_CENTER[0] + 0.065, _TOP_EDGE_Y),
}
# The two pin holes share one size: the +Y hole's diameter prints for both.
# Both holes and the bore are drilled through: the title block's DRILLED
# HOLES row governs their sizes.
CALLOUTS_ABOVE = {"PinPosDia": "2X"}
CALLOUTS_BELOW = {"BoreDiaDim": "DRILL THRU", "PinPosDia": "DRILL THRU"}

# T12 and T18 differ from the T24 only in their teeth, so each is drawn once
# more as a small edge view of its own configuration, carrying its outside
# diameter.  At 1:1 they stack in the free band between the pin-location
# chain and the isometric view, under SPROCKET DATA.
CONFIGURATION_VIEW_SCALE = (1, 1)
_CONFIGURATION_S = CONFIGURATION_VIEW_SCALE[0] / CONFIGURATION_VIEW_SCALE[1]
CONFIGURATION_VIEW_CENTERS = {
    "T12": (0.2525, 0.185),
    "T18": (0.2525, 0.135),
}
# Above each view, its outside diameter; below it, its label.
CONFIGURATION_DIMENSION_RISE = 0.008
CONFIGURATION_LABEL_DROP = 0.010


def configuration_keep(configuration: str) -> dict[str, tuple[float, float]]:
    """The one dimension a configuration view keeps, and where it prints."""
    x, y = CONFIGURATION_VIEW_CENTERS[configuration]
    edge = y + PLATE * _CONFIGURATION_S / 2000.0
    return {"BlankDia": (x, edge + CONFIGURATION_DIMENSION_RISE)}


def configuration_label(configuration: str) -> str:
    numerator, denominator = CONFIGURATION_VIEW_SCALE
    return f"{configuration}  SCALE {numerator:g}:{denominator:g}"


def configuration_label_xy(configuration: str) -> tuple[float, float]:
    """Upper-left of the label: under the view, flush with its left tip."""
    x, y = CONFIGURATION_VIEW_CENTERS[configuration]
    half_width = outside_dia(TEETH[configuration]) * _CONFIGURATION_S / 2000.0
    edge = y - PLATE * _CONFIGURATION_S / 2000.0
    return (x - half_width, edge - CONFIGURATION_LABEL_DROP)


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
    """Import a model dimension the T24 views already print, into ``view``.

    ``InsertModelAnnotations3``'s ``DuplicateDims`` means *eliminate*
    duplicates when true, which would refuse the outside diameter the T24
    edge view already carries; each configuration view must print it again
    (the ``draw_cone_gear`` package pattern), so this passes false and
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
            False,  # allow the dimension the T24 edge view already prints
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


def _assert_outside_diameter(
    adapter: Any, annotations: list[Any], configuration: str
) -> None:
    """Prove a view prints THIS configuration's outside diameter natively.

    One model dimension carries all three diameters; each view reads the one
    of its referenced configuration, at the part's places and reference-only.
    """
    found = [a for a in annotations if dimension_name(adapter, a) == "BlankDia"]
    if len(found) != 1:
        raise RuntimeError(
            f"{configuration}: expected one BlankDia on its view, found {len(found)}"
        )
    display = _early_bound(
        _early_bound(found[0], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    places = int(display.GetPrimaryPrecision2())
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    prefix, suffix = str(display.GetText(1) or ""), str(display.GetText(2) or "")
    tolerance_type = int(_early_bound(dimension.Tolerance, "IDimensionTolerance").Type)
    if (prefix, suffix) != ("(<MOD-DIAM>", ")") or tolerance_type != 0:
        raise RuntimeError(
            f"{configuration}: BlankDia must be reference-only and unbanded; "
            f"prefix={prefix!r}, suffix={suffix!r}, tolerance type={tolerance_type}"
        )
    values = dimension.GetSystemValue3(_SPECIFY_CONFIGURATION, configuration)
    if not isinstance(values, (list, tuple)) or len(values) != 1:
        raise RuntimeError(
            f"{configuration}: BlankDia value readback returned {values!r}"
        )
    measured_mm = abs(float(values[0])) * 1000.0
    expected_mm = outside_dia(TEETH[configuration])
    expected_places = DRAWING_PRECISION_BY_NAME["BlankDia"]
    if abs(measured_mm - expected_mm) > 1e-4 or places != expected_places:
        raise RuntimeError(
            f"{configuration}: sheet BlankDia reads {measured_mm:g} mm at {places} "
            f"places, expected {expected_mm:g} mm at {expected_places}"
        )
    _telemetry.success(
        f"{configuration}: sheet outside diameter {measured_mm:.{places}f} mm"
    )


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    """Make ``view`` the active view (a note lands in the active view)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} view {name!r}")


def _label_configuration_view(adapter: Any, view: Any, configuration: str) -> None:
    """Title a configuration view with its configuration and scale.

    A model view has no native label the API can show, so the label is a note
    inserted while the view is ACTIVE: the view owns it and moves with it.
    Read back: the view carries that label exactly once.
    """
    _activate_view(adapter, view, label=configuration)
    text = configuration_label(configuration)
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

    check("open transgear-removable source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Removable Chain Sprocket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "removable ANSI #25 sprocket; T12 / T18 / T24; McMaster blank reworked",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    _configure_views(adapter, DEFAULT_CONFIG, (front, top, iso))
    configuration_views = {
        configuration: place_view(
            adapter, str(SOURCE), "*Top", *center, scale=CONFIGURATION_VIEW_SCALE
        )
        for configuration, center in CONFIGURATION_VIEW_CENTERS.items()
    }
    for configuration, view in configuration_views.items():
        _configure_views(adapter, configuration, (view,))
    for view in (front, top, iso, *configuration_views.values()):
        set_hidden_lines_removed(adapter, view)

    face = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    edge = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="edge",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_reference_dimensions(adapter, edge, DRAWING_REFERENCE_DIMENSIONS)
    _assert_outside_diameter(adapter, edge, DEFAULT_CONFIG)
    annotations = [*face, *edge]
    # The T24 edge view imports first, so its import keeps eliminating
    # duplicates; each configuration view then prints the same dimension again.
    for configuration, view in configuration_views.items():
        curated = _curate_repeated_dimensions(
            adapter,
            view,
            keep=configuration_keep(configuration),
            view_label=f"{configuration} edge",
        )
        set_reference_dimensions(adapter, curated, DRAWING_REFERENCE_DIMENSIONS)
        _assert_outside_diameter(adapter, curated, configuration)
        annotations += curated
        _label_configuration_view(adapter, view, configuration)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    # Decimal places and bands are part-authored; the sheet proves they
    # survived import.  Parenthesized supplied ODs claim no general tolerance.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the sprocket face view")

    # The property-linked blocks land in the active view: the T24 edge view,
    # as before the configuration views and their labels were added.
    _activate_view(adapter, top, label="edge")
    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_XY, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_XY, char_height=0.0025
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Removable Chain Sprocket Manufacturing Drawing",
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
