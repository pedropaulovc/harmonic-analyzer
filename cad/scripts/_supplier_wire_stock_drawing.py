"""The labelled supplier wire end view: the package's one native dimension."""

from __future__ import annotations

from collections.abc import Callable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

import _telemetry
from _com import _early_bound
from _construction_line_font import _construction_curves_as_outline
from _drawing_common import rebuild_drawing
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from _mcmaster_9666k56 import DIA
from _mcmaster_9666k56_reference import (
    SUPPLIER_DIAMETER_CALLOUT,
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
from _purchased_fastener_drawing import _box, _inside, assert_supplier_view_fits
from _supplier_spring_drawing import (
    assert_supplier_configuration_value,
    reacquire_supplier_dimensions,
)

STOCK_SCALE = (20, 1)
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
# Sheet metres: the circle (15.7 mm at 20:1) centred left of the title block,
# its Ø text up-right on the leader, the view label under the padded outline.
# The two-line REF (Ø, then PER SUPPLIER) hangs its shoulder under the second
# line: at y .183 that shoulder ran across the circle's top (177.9 mm), so the
# text sits 6 mm higher.
STOCK_CENTER = (0.150, 0.170)
STOCK_TEXT = (0.175, 0.189)
# An unhatched end view, not a section: the sheet has no cutting plane.
STOCK_LABEL = f"WIRE END VIEW SCALE {STOCK_SCALE[0]}:{STOCK_SCALE[1]}"
STOCK_LABEL_XY = (0.121, 0.152)
STOCK_FIELD = (0.100, 0.130, 0.260, 0.220)


def _delete_center_marks(adapter, view) -> None:
    """Delete the template's mark on the stock circle and read none back.

    Its arms scale with the 20:1 view (50 mm cross plus 8 mm extensions) and
    run off the sheet. The circle locates nothing; the native diameter is the
    replacement datum.
    """
    label = "supplier wire section centre mark"
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


def add_wire_section(adapter, source) -> Callable[[], None]:
    """Show/import the saved supplier circle, label it, return final readback."""
    line_font = _construction_curves_as_outline(adapter)
    view = _early_bound(
        place_view(adapter, str(source), "*Top", *STOCK_CENTER, scale=STOCK_SCALE),
        "IView",
    )
    view.ReferencedConfiguration = SUPPLIER_REFERENCE_CONFIGURATION
    if str(view.ReferencedConfiguration) != SUPPLIER_REFERENCE_CONFIGURATION:
        raise RuntimeError("wire section view references installed geometry")
    view.UseSheetScale = 0
    view.ScaleRatio = double_array(STOCK_SCALE)
    set_hidden_lines_removed(adapter, view)
    rebuild_drawing(adapter, label="supplier wire section configuration")
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep={SUPPLIER_REFERENCE_DIMENSION: STOCK_TEXT},
        view_label="supplier wire section",
        dimensions_by_feature=SUPPLIER_REFERENCE_DIMENSIONS,
    )
    if len(annotations) != 1:
        raise RuntimeError("supplier wire section needs one native diameter")
    view.UpdateViewDisplayGeometry()
    at = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="supplier circle centre")
    position = tuple(float(value) for value in view.Position)
    if not view.SetViewPosition(
        double_array(
            [position[index] + STOCK_CENTER[index] - at[index] for index in range(2)]
        ),
        False,
    ):
        raise RuntimeError("cannot centre supplier wire section")
    rebuild_drawing(adapter, label="supplier wire section position")
    _delete_center_marks(adapter, view)
    annotation = _early_bound(annotations[0], "IAnnotation")
    if not annotation.SetPosition(*STOCK_TEXT, 0.0):
        raise RuntimeError("cannot position native supplier wire diameter")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    options = {
        "label": "9666K56 supplier nominal wire diameter",
        "units": "in",
        "precision": SUPPLIER_DIAMETER_PRECISION,
        "expected_mm": DIA,
        "presentation": "diameter",
        "configuration": SUPPLIER_REFERENCE_CONFIGURATION,
        "callout": SUPPLIER_DIAMETER_CALLOUT,
    }
    supplier_reference_dimension(adapter, display, **options)
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")
    if not drawing.GetEditSheet() or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot restore sheet context for the wire section label")
    label = add_note(adapter, STOCK_LABEL, *STOCK_LABEL_XY)
    if label is None:
        raise RuntimeError("cannot create the wire section label")
    label = _early_bound(label, "INote")

    def settled() -> None:
        line_font()
        if (str(view.ReferencedConfiguration) != SUPPLIER_REFERENCE_CONFIGURATION
                or tuple(view.ScaleRatio) != STOCK_SCALE):
            raise RuntimeError("wire section view configuration/scale changed")
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
            raise RuntimeError("wire diameter lost its true native circle identity")
        assert_supplier_configuration_value(
            final,
            SUPPLIER_REFERENCE_CONFIGURATION,
            DIA,
            label="supplier wire circle",
        )
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError("supplier wire diameter acquired an unprovided band")
        assert_supplier_reference_dimension(adapter, final, **options)
        if view.GetAnnotationsByType(_CENTER_MARK_ANNOTATION):
            raise RuntimeError("supplier wire section regained a centre mark")
        assert_supplier_view_fits(
            adapter, view, STOCK_FIELD, label="supplier wire section"
        )
        if str(label.GetText() or "").replace("\r", "") != STOCK_LABEL:
            raise RuntimeError("wire section label changed")
        box = _box(label.GetExtent(), label="wire section label", kind="note")
        outline = _box(view.GetOutline(), label="supplier wire section")
        if not _inside(box, STOCK_FIELD) or (
            box[0] < outline[2]
            and outline[0] < box[2]
            and box[1] < outline[3]
            and outline[1] < box[3]
        ):
            raise RuntimeError(
                f"wire section label leaves its field or overlaps the view: {box!r}"
            )

    return settled
