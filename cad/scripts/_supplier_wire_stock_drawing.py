"""Native supplier stock cross-sections, not installed wire envelopes."""

from __future__ import annotations

from collections.abc import Callable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from _mcmaster_9666k56 import CATALOG_LENGTH_FT, DIA, SKU
from _mcmaster_9666k56_reference import (
    SUPPLIER_DIAMETER_PRECISION,
    SUPPLIER_REFERENCE_CONFIGURATION,
    SUPPLIER_REFERENCE_DIMENSION,
    SUPPLIER_REFERENCE_FEATURE,
    SUPPLIER_REFERENCE_DIMENSIONS,
)
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)

STOCK_SCALE = (20, 1)
STOCK_CENTER = (0.210, 0.237)
STOCK_KEEP = {SUPPLIER_REFERENCE_DIMENSION: (0.247, 0.247)}
STOCK_CAPTION = (
    f"AS-SUPPLIED NOMINAL STOCK\nMcMASTER-CARR {SKU}\n"
    f"COIL PACKAGE: {CATALOG_LENGTH_FT} ft (NOT CUT LENGTH)\n"
    f"SCALE {STOCK_SCALE[0]}:{STOCK_SCALE[1]}"
)


def add_nominal_stock_cross_section(adapter, source) -> Callable[[], None]:
    """Show the actual stock circle and return its post-rebuild readback."""
    view = _early_bound(
        place_view(adapter, str(source), "*Top", *STOCK_CENTER, scale=STOCK_SCALE),
        "IView",
    )
    view.ReferencedConfiguration = SUPPLIER_REFERENCE_CONFIGURATION
    if str(view.ReferencedConfiguration) != SUPPLIER_REFERENCE_CONFIGURATION:
        raise RuntimeError(
            "stock cross-section does not reference nominal supplier stock"
        )
    rebuild_drawing(adapter, label="supplier stock configuration")
    set_hidden_lines_removed(adapter, view)
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=STOCK_KEEP,
        view_label="as-supplied nominal stock cross-section",
        dimensions_by_feature=SUPPLIER_REFERENCE_DIMENSIONS,
    )
    if len(annotations) != 1:
        raise RuntimeError("supplier nominal stock must carry one native diameter")
    # Do not assume a hidden-sketch-only view retains its original solid-view
    # origin after changing configuration. Centre the actual source circle.
    view.UpdateViewDisplayGeometry()
    at = model_point_in_view(
        adapter,
        view,
        (0.0, 0.0, 0.0),
        label="supplier stock circle centre",
    )
    position = tuple(float(value) for value in view.Position)
    position_set = view.SetViewPosition(
        double_array([position[i] + STOCK_CENTER[i] - at[i] for i in range(2)]),
        False,
    )
    if not position_set:
        raise RuntimeError("cannot centre supplier nominal stock cross-section")
    rebuild_drawing(adapter, label="supplier stock cross-section position")
    annotation = _early_bound(annotations[0], "IAnnotation")
    if not annotation.SetPosition(*STOCK_KEEP[SUPPLIER_REFERENCE_DIMENSION], 0.0):
        raise RuntimeError("cannot position supplier nominal diameter")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    supplier_reference_dimension(
        adapter,
        display,
        label="9666K56 as-supplied nominal stock diameter",
        units="in",
        precision=SUPPLIER_DIAMETER_PRECISION,
        expected_mm=DIA,
        presentation="diameter",
    )
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    # ActivateView documents False for a sheet; validate the native state
    # instead of treating that return value as a sheet-activation failure.
    drawing.ActivateView("")
    if not drawing.GetEditSheet() or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot restore sheet context for supplier stock caption")
    note = add_note(adapter, STOCK_CAPTION, 0.180, 0.217)
    if (
        note is None
        or str(_early_bound(note, "INote").GetText()).replace("\r", "") != STOCK_CAPTION
    ):
        raise RuntimeError("supplier stock caption did not persist")
    caption_annotation = _early_bound(note, "INote").GetAnnotation()
    if (
        caption_annotation is None
        or int(_early_bound(caption_annotation, "IAnnotation").OwnerType) != 1
    ):  # swAnnotationOwner_DrawingSheet
        raise RuntimeError("supplier stock caption is not sheet-owned")

    def assert_settled_stock() -> None:
        if str(view.ReferencedConfiguration) != SUPPLIER_REFERENCE_CONFIGURATION:
            raise RuntimeError("settled wire stock view changed configuration")
        displays = tuple(view.GetDisplayDimensions() or ())
        if len(displays) != 1:
            raise RuntimeError("settled nominal wire stock needs one native diameter")
        settled = _early_bound(displays[0], "IDisplayDimension")
        native = _early_bound(settled.GetDimension2(0), "IDimension")
        if str(native.FullName).split("@")[:2] != [
            SUPPLIER_REFERENCE_DIMENSION,
            SUPPLIER_REFERENCE_FEATURE,
        ]:
            raise RuntimeError("settled stock diameter lost its source sketch identity")
        assert_supplier_reference_dimension(
            adapter,
            settled,
            label="9666K56 settled as-supplied nominal stock diameter",
            units="in",
            precision=SUPPLIER_DIAMETER_PRECISION,
            expected_mm=DIA,
            presentation="diameter",
        )
        if (
            str(_early_bound(note, "INote").GetText()).replace("\r", "")
            != STOCK_CAPTION
        ):
            raise RuntimeError("settled wire stock package caption changed")
        caption_annotation = _early_bound(note, "INote").GetAnnotation()
        if (
            caption_annotation is None
            or int(_early_bound(caption_annotation, "IAnnotation").OwnerType) != 1
        ):  # swAnnotationOwner_DrawingSheet
            raise RuntimeError("settled supplier stock caption is not sheet-owned")

    return assert_settled_stock
