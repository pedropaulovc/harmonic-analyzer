"""A native supplier stock circle, never a dimension on the installed wire."""

from __future__ import annotations

from collections.abc import Callable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

import _telemetry
from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from _mcmaster_9666k56 import DIA
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
from _purchased_fastener_drawing import assert_supplier_view_fits
from _supplier_spring_drawing import (
    assert_supplier_configuration_value,
    reacquire_supplier_dimensions,
)

STOCK_SCALE = (20, 1)
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
# Reserve these separate diagram fields without moving/refitting either of the
# existing member views or their independently checked Depth references. The
# native diameter is the only supplier datum here; SKU and material are in each
# member's Manufacturing Notes, so the view carries no caption.
STOCK_LAYOUTS = {
    "LeverWire": ((0.300, 0.155), (0.325, 0.168)),
    "PenWire": ((0.190, 0.241), (0.215, 0.252)),
}
STOCK_FIELDS = {
    "LeverWire": (0.240, 0.110, 0.410, 0.190),
    "PenWire": (0.145, 0.205, 0.260, 0.265),
}


def _delete_center_marks(adapter, view, *, member: str) -> None:
    """Delete the template's mark on the stock circle and read none back.

    Its arms scale with the 20:1 view (50 mm cross plus 8 mm extensions), so it
    crossed the PenWire top border. The stock circle locates nothing; the
    native diameter alone is the replacement datum.
    """
    label = f"{member} supplier stock centre mark"
    marks = tuple(view.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ())
    if not marks:
        _telemetry.info(f"{label}: none drawn")
        return
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    for index, mark in enumerate(marks):
        if not _early_bound(mark, "IAnnotation").Select2(index > 0, 0):
            raise RuntimeError(f"cannot select {label}")
    draw.EditDelete()  # VT_VOID: the re-read below is the proof
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"delete {label}")
    if view.GetAnnotationsByType(_CENTER_MARK_ANNOTATION):
        raise RuntimeError(f"{label} survived deletion")
    _telemetry.info(f"{label}: deleted {len(marks)}")


def add_nominal_stock_cross_section(adapter, source, *, member: str) -> Callable[[], None]:
    """Show/import the saved model circle and return final native readback."""
    center, text = STOCK_LAYOUTS[member]
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
    _delete_center_marks(adapter, view, member=member)
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
        if view.GetAnnotationsByType(_CENTER_MARK_ANNOTATION):
            raise RuntimeError(f"{member}: supplier stock view regained a centre mark")
        assert_supplier_view_fits(
            adapter, view, STOCK_FIELDS[member], label=f"{member} supplier stock",
        )

    return settled
