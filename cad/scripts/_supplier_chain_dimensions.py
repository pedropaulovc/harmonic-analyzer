"""Native supplier dimensions on explicitly nominal stock/application diagrams.

The installed 1.3-mm pins and 3.30-mm bushings are never source carriers for
2.2987-mm supplier pins or 3.302-mm rollers. No helical/physical edge identity
is claimed: every imported reference belongs to its named model sketch.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from solidworks_mcp.adapters.sw_type_info import constant

from _com import _early_bound
from _drawing_dimensions import offset_dimension_text
from _drawing_hidden_sketches import _show_hidden_owners, curate_view_dimensions
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_spring_drawing import (
    assert_supplier_configuration_value,
    reacquire_supplier_dimensions,
)
import _supplier_chain_stock as stock

SOURCE_FEATURES = {
    "free_front": (stock.FRONT_FEATURE,),
    "free_top": (stock.SECTION_FEATURE,),
}

SUPPLIER_MARGINS = {
    "free_front": (0.030, 0.020, 0.030, 0.020),
    "free_top": (0.030, 0.016, 0.045, 0.020),
}
# The diagram sketches are construction geometry (the zero-body diagram
# contract); this SLDDRW prints construction curves as visible outline, as
# _supplier_wire_stock_drawing does. The installed pictorial keeps its
# sketches blanked, so only the two diagrams change.
_CONSTRUCTION_LINE_FONT = (
    ("swLineFontConstructionCurvesStyle", "swLineCONTINUOUS"),
    ("swLineFontConstructionCurvesThickness", "swLW_THICK"),
)


def _construction_curves_as_outline(adapter: Any) -> Callable[[], None]:
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    option = constant("swDetailingNoOptionSpecified")
    settings = tuple(
        (name, constant(name), constant(value))
        for name, value in _CONSTRUCTION_LINE_FONT
    )

    def readback() -> None:
        for name, preference, value in settings:
            if int(extension.GetUserPreferenceInteger(preference, option)) != value:
                raise RuntimeError(f"chain diagram line font {name} readback differs")

    for name, preference, value in settings:
        if not extension.SetUserPreferenceInteger(preference, option, value):
            raise RuntimeError(f"failed to set chain diagram line font {name}")
    readback()
    return readback


def prepare_chain_diagrams(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> tuple[Callable[[], None], ...]:
    """Show the source sketch owners before scale selection, not afterward."""
    line_font = _construction_curves_as_outline(adapter)
    for key, owners in SOURCE_FEATURES.items():
        view = _early_bound(views[key], "IView")
        if str(view.ReferencedConfiguration) != stock.SUPPLIER_REFERENCE_CONFIGURATION:
            raise RuntimeError(f"{key}: chain diagram references an installed member")
        shown = _show_hidden_owners(adapter, view, owners, view_label=key)
        if tuple(shown) != owners:
            raise RuntimeError(f"{key}: supplier diagram sketch is not saved hidden")
    return (line_font,)


def annotate_chain_stock(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
    connecting: bool = False,
) -> tuple[Callable[[], None], ...]:
    """Import exact source dimensions and re-resolve them after final rebuild."""
    front = (
        (stock.PIN_DIMENSION, stock.PIN_DIAMETER, 3, "diameter", "PIN"),
        (
            stock.ROLLER_DIMENSION,
            stock.ROLLER_DIAMETER,
            3,
            "diameter",
            "FOR ROLLER" if connecting else "ROLLER",
        ),
        (stock.PITCH_DIMENSION, stock.PITCH, 3, "length", "PITCH"),
    )
    top = (
        (
            stock.WIDTH_DIMENSION,
            stock.ROLLER_WIDTH,
            3,
            "length",
            "FOR ROLLER WIDTH" if connecting else "ROLLER WIDTH",
        ),
    )
    if connecting:
        top += (
            (stock.PLATE_DIMENSION, stock.PLATE_THICKNESS, 3, "length", "PLATE"),
            (
                stock.LENGTH_DIMENSION,
                stock.CONNECTING_PIN_LENGTH,
                3,
                "length",
                "OVERALL PIN",
            ),
        )
    expected_by_view = {"free_front": front, "free_top": top}
    options_by_view = {}
    for key, rows in expected_by_view.items():
        view = _early_bound(views[key], "IView")
        xmin, ymin, xmax, ymax = reference_bounds(key)
        middle = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0)
        if key == "free_front":
            positions = {
                stock.PIN_DIMENSION: (xmin - 0.014, ymin - 0.008),
                stock.ROLLER_DIMENSION: (xmax + 0.014, ymin - 0.008),
                stock.PITCH_DIMENSION: (middle[0], ymax + 0.008),
            }
        else:
            positions = {stock.WIDTH_DIMENSION: (xmin - 0.014, middle[1])}
            if connecting:
                # The plate span is too short for inside arrows, so its REF
                # hangs left of the line on a shoulder ~5.6 mm under the text
                # anchor, out across the roller-width line and its 6.35 mm
                # outside-arrow stub.  At ymax + 15 mm the shoulder clears that
                # stub (the pin length bounds ymax) whatever the REF's width.
                positions.update(
                    {
                        stock.PLATE_DIMENSION: (middle[0], ymax + 0.015),
                        stock.LENGTH_DIMENSION: (xmax + 0.020, middle[1]),
                    }
                )
        imported = curate_view_dimensions(
            adapter,
            view,
            keep=positions,
            view_label=f"supplier chain {key}",
            dimensions_by_feature=stock.DIMENSIONS_BY_FEATURE,
        )
        by_name = {
            dimension_name(adapter, annotation): annotation for annotation in imported
        }
        if len(imported) != len(rows) or set(by_name) != set(positions):
            raise RuntimeError(f"{key}: native supplier dimension inventory differs")
        options = {}
        for name, expected, precision, presentation, callout in rows:
            display = _early_bound(
                by_name[name].GetSpecificAnnotation(), "IDisplayDimension"
            )
            options[name] = {
                "label": f"supplier chain {name}",
                "units": "in",
                "precision": precision,
                "expected_mm": expected,
                "presentation": presentation,
                "callout": callout,
                "configuration": stock.SUPPLIER_REFERENCE_CONFIGURATION,
            }
            supplier_reference_dimension(adapter, display, **options[name])
        options_by_view[key] = options
        if key == "free_top" and not connecting:
            # Keep the native vertical line/witnesses where curation put them;
            # shelf the complete two-row width label to their left.
            width_x, width_y = positions[stock.WIDTH_DIMENSION]
            offset_dimension_text(
                adapter,
                imported,
                {stock.WIDTH_DIMENSION: (width_x - 0.024, width_y)},
            )

    expected = {
        key: {
            row[0]: stock.FRONT_FEATURE
            if key == "free_front"
            else stock.SECTION_FEATURE
            for row in expected_by_view.get(key, ())
        }
        for key in views
    }
    configurations = {
        key: str(_early_bound(view, "IView").ReferencedConfiguration)
        for key, view in views.items()
    }

    def settled() -> None:
        found = reacquire_supplier_dimensions(
            adapter,
            views,
            expected=expected,
            configurations=configurations,
        )
        for options in options_by_view.values():
            for name, presentation in options.items():
                display = found[name]
                assert_supplier_configuration_value(
                    display,
                    stock.SUPPLIER_REFERENCE_CONFIGURATION,
                    presentation["expected_mm"],
                    label=name,
                )
                native = _early_bound(display.GetDimension2(0), "IDimension")
                if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
                    raise RuntimeError(
                        f"{name}: unprovided supplier tolerance appeared"
                    )
                assert_supplier_reference_dimension(adapter, display, **presentation)
                if (
                    name == stock.WIDTH_DIMENSION
                    and not connecting
                    and display.OffsetText is not True
                ):
                    raise RuntimeError(
                        f"{name}: roller width text returned to its native dimension line"
                    )

    return (settled,)
