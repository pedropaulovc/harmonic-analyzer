"""A native supplier stock circle, never a dimension on the installed wire.

Stock captions use the supplier sheet's standard 3 mm lettering. Seat their
measured complete extents, not their insertion points, below the stock circle;
the unchanged field guard rechecks the whole caption after the final rebuild.
"""

from __future__ import annotations

from collections.abc import Callable
from math import isfinite

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

import _telemetry
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
from _purchased_fastener_drawing import (
    _box, _inside, _literal_note, assert_supplier_view_fits,
)
from _supplier_spring_drawing import (
    assert_supplier_configuration_value,
    reacquire_supplier_dimensions,
)

STOCK_SCALE = (20, 1)
# Reserve these separate diagram fields without moving/refitting either of the
# existing member views or their independently checked Depth references.
STOCK_LAYOUTS = {
    "LeverWire": ((0.300, 0.155), (0.325, 0.168), (0.255, 0.135)),
    "PenWire": ((0.190, 0.241), (0.215, 0.252), (0.155, 0.223)),
}
STOCK_FIELDS = {
    "LeverWire": (0.240, 0.110, 0.410, 0.190),
    "PenWire": (0.145, 0.205, 0.260, 0.265),
}
STOCK_CAPTION = (
    f"SUPPLIER NOMINAL STOCK — NOT INSTALLED\nMcMASTER-CARR {SKU}\n"
    f"COIL PACKAGE: {CATALOG_LENGTH_FT} ft (NOT CUT LENGTH)\n"
    f"SCALE {STOCK_SCALE[0]}:{STOCK_SCALE[1]}"
)


def add_nominal_stock_cross_section(adapter, source, *, member: str) -> Callable[[], None]:
    """Show/import the saved model circle and return final native readback."""
    center, text, caption = STOCK_LAYOUTS[member]
    view = _early_bound(
        place_view(adapter, str(source), "*Top", *center, scale=STOCK_SCALE), "IView",
    )
    view.ReferencedConfiguration = SUPPLIER_REFERENCE_CONFIGURATION
    if str(view.ReferencedConfiguration) != SUPPLIER_REFERENCE_CONFIGURATION:
        raise RuntimeError("wire stock view references installed geometry")
    view.UseSheetScale = 0
    view.ScaleRatio = double_array(STOCK_SCALE)
    set_hidden_lines_removed(adapter, view)
    rebuild_drawing(adapter, label=f"{member} supplier stock configuration")
    annotations = curate_view_dimensions(
        adapter, view, keep={SUPPLIER_REFERENCE_DIMENSION: text},
        view_label=f"{member} supplier nominal stock circle",
        dimensions_by_feature=SUPPLIER_REFERENCE_DIMENSIONS,
    )
    if len(annotations) != 1:
        raise RuntimeError("supplier nominal stock needs one native diameter")
    view.UpdateViewDisplayGeometry()
    at = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="supplier circle centre")
    position = tuple(float(value) for value in view.Position)
    if not view.SetViewPosition(
        double_array([position[index] + center[index] - at[index] for index in range(2)]), False,
    ):
        raise RuntimeError("cannot centre supplier nominal stock circle")
    rebuild_drawing(adapter, label=f"{member} supplier circle position")
    annotation = _early_bound(annotations[0], "IAnnotation")
    if not annotation.SetPosition(*text, 0.0):
        raise RuntimeError("cannot position native supplier stock diameter")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    options = {
        "label": "9666K56 supplier nominal stock diameter", "units": "in",
        "precision": SUPPLIER_DIAMETER_PRECISION, "expected_mm": DIA,
        "presentation": "diameter",
        "configuration": SUPPLIER_REFERENCE_CONFIGURATION,
    }
    supplier_reference_dimension(adapter, display, **options)
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")
    if not drawing.GetEditSheet() or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot restore sheet context for stock caption")
    note = _literal_note(adapter, STOCK_CAPTION, *caption)
    # Use the supplier sheet's standard 3 mm note, not the document default.
    # Its insertion point is not its measured upper-left extent; seat the
    # complete four-line block below the circle without moving either member.
    rebuild_drawing(adapter, label=f"{member} supplier stock caption format")
    adapter.currentModel.GraphicsRedraw2()
    bounds = _box(note.GetExtent(), label=f"{member} stock caption", kind="note")
    caption_annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in (caption_annotation.GetPosition() or ()))
    if len(position) != 3 or not all(map(isfinite, position)):
        raise RuntimeError(
            f"{member}: supplier stock caption has invalid position: {position!r}; "
            f"extent_m={bounds!r}; reserved_m={STOCK_FIELDS[member]!r}"
        )
    target = (
        position[0] + caption[0] - bounds[0],
        position[1] + caption[1] - bounds[3],
        position[2],
    )
    if not caption_annotation.SetPosition2(*target):
        raise RuntimeError(
            f"{member}: cannot position supplier stock caption: "
            f"position_m={position!r} -> {target!r}; extent_m={bounds!r}; "
            f"reserved_m={STOCK_FIELDS[member]!r}"
        )
    rebuild_drawing(adapter, label=f"{member} supplier stock caption position")
    adapter.currentModel.GraphicsRedraw2()
    positioned = _box(note.GetExtent(), label=f"{member} stock caption", kind="note")
    placed_position = tuple(
        float(value) for value in (caption_annotation.GetPosition() or ())
    )
    placement = (
        f"position_m={position!r} -> {placed_position!r}; "
        f"extent_m={bounds!r} -> {positioned!r}; reserved_m={STOCK_FIELDS[member]!r}"
    )
    _telemetry.info(
        f"{member} supplier stock caption: {placement}", configuration=member,
    )
    if not _inside(positioned, STOCK_FIELDS[member]):
        raise RuntimeError(
            f"{member}: supplier stock caption leaves its reserved field: "
            f"extent_m={positioned!r}; {placement}"
        )

    def settled() -> None:
        if (str(view.ReferencedConfiguration) != SUPPLIER_REFERENCE_CONFIGURATION
                or tuple(view.ScaleRatio) != STOCK_SCALE):
            raise RuntimeError("wire stock view configuration/scale changed")
        found = reacquire_supplier_dimensions(
            adapter, {"stock": view},
            expected={"stock": {
                SUPPLIER_REFERENCE_DIMENSION: SUPPLIER_REFERENCE_FEATURE,
            }},
            configurations={"stock": SUPPLIER_REFERENCE_CONFIGURATION},
        )
        final = found[SUPPLIER_REFERENCE_DIMENSION]
        native = _early_bound(final.GetDimension2(0), "IDimension")
        if (str(native.FullName).split("@")[:2]
                != [SUPPLIER_REFERENCE_DIMENSION, SUPPLIER_REFERENCE_FEATURE]
                or int(final.Type2) != 6):
            raise RuntimeError("stock diameter lost its true native circle identity")
        assert_supplier_configuration_value(
            final, SUPPLIER_REFERENCE_CONFIGURATION, DIA, label="supplier stock circle",
        )
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError("supplier stock diameter acquired an unprovided band")
        assert_supplier_reference_dimension(adapter, final, **options)
        if str(_early_bound(note, "INote").GetText()).replace("\r", "") != STOCK_CAPTION:
            raise RuntimeError("supplier stock caption changed")
        owner = _early_bound(note, "INote").GetAnnotation()
        if owner is None or int(_early_bound(owner, "IAnnotation").OwnerType) != 1:
            raise RuntimeError("supplier stock caption must remain sheet-owned")
        assert_supplier_view_fits(
            adapter, view, STOCK_FIELDS[member], label=f"{member} supplier stock",
        )
        final_bounds = _box(
            _early_bound(note, "INote").GetExtent(),
            label=f"{member} stock caption", kind="note",
        )
        if not _inside(final_bounds, STOCK_FIELDS[member]):
            raise RuntimeError(
                f"{member}: supplier stock caption leaves its reserved field: "
                f"extent_m={final_bounds!r}; reserved_m={STOCK_FIELDS[member]!r}; "
                f"placement: {placement}"
            )

    return settled
