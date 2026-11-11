"""Purchase drawing for MHA-SH-VN-58, McMaster 90145A299 pivot pins.

The catalogue 5/64 x 5/16 outline lives in the part's zero-body
SUPPLIER_REFERENCE configuration, not in either installed member: the sheet
prints its diameter and length as untoleranced supplier REF (the catalogue's
tolerance governs), the diameter naming the parts each pin presses into and
runs in. The two installed members (RodPin, BarPin) show as reference
pictorials with their quantities; the footer carries the property-linked
supplier and SKU and the pointer to MHA-CH-00, which presses and dresses
them.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name

import _telemetry
import sh_vn_pivot_pin_notes as notes
import sh_vn_pivot_pin_spec as pin
from _com import _early_bound
from _construction_line_font import _construction_curves_as_outline
from _drawing_dimensions import offset_dimension_text
from _drawing_hidden_sketches import _show_hidden_owners, curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _session import run_build
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_spring_drawing import (
    assert_supplier_configuration_value,
    build_supplier_spring_drawing,
    reacquire_supplier_dimensions,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sh_vn_pivot_pin"]
PART_STEM = SPEC.artifact_stem
VIEW = "free_front"
SOURCE_FEATURES = {VIEW: (pin.SUPPLIER_FEATURE,)}
# Supplier decimals, as the other purchased dowel sheets print them: .0781
# and .3125.
PRECISION = 4
# Sheet metres. The length prints over the outline. The diameter's dimension
# line stands DIAMETER_LINE_GAP left of the outline and its three-row text
# (value, then the two mate rows) shelves DIAMETER_TEXT_SHELF further left on
# a leader, clear of its own arrows; the left lane reserves that text.
LENGTH_TEXT_RISE = 0.008
DIAMETER_LINE_GAP = 0.010
DIAMETER_TEXT_SHELF = 0.052
SUPPLIER_MARGINS = {VIEW: (0.110, 0.015, 0.020, 0.020)}
# (dimension, expected mm, presentation, below-callout)
DIMENSIONS = (
    (pin.DIAMETER_DIMENSION, pin.PIN_DIA, "diameter", notes.DIAMETER_CALLOUT),
    (pin.LENGTH_DIMENSION, pin.PIN_LENGTH, "length", None),
)


def prepare_pin_outline(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> tuple[Callable[[], None], ...]:
    """Show the saved-hidden supplier outline before the native view fit.

    The outline is construction geometry: this SLDDRW draws construction
    curves solid and thick, so it prints as the pin's edges, not as dashes.
    """
    line_font = _construction_curves_as_outline(adapter)
    view = _early_bound(views[VIEW], "IView")
    if str(view.ReferencedConfiguration) != pin.SUPPLIER_REFERENCE_CONFIGURATION:
        raise RuntimeError(
            f"{VIEW}: the supplier outline references an installed member"
        )
    owners = SOURCE_FEATURES[VIEW]
    shown = _show_hidden_owners(adapter, view, owners, view_label=f"{PART_STEM} {VIEW}")
    if tuple(shown) != owners:
        raise RuntimeError(f"{VIEW}: the supplier outline sketch is not saved hidden")
    return (line_font,)


def annotate_pin_outline(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> tuple[Callable[[], None], ...]:
    """Import the outline's two native sizes as supplier REF; re-read them settled."""
    view = _early_bound(views[VIEW], "IView")
    xmin, ymin, xmax, ymax = reference_bounds(VIEW)
    middle_y = (ymin + ymax) / 2.0
    positions = {
        pin.DIAMETER_DIMENSION: (xmin - DIAMETER_LINE_GAP, middle_y),
        pin.LENGTH_DIMENSION: ((xmin + xmax) / 2.0, ymax + LENGTH_TEXT_RISE),
    }
    imported = curate_view_dimensions(
        adapter,
        view,
        keep=positions,
        view_label=f"{PART_STEM} supplier outline",
        dimensions_by_feature=pin.DIMENSIONS_BY_FEATURE,
    )
    by_name = {
        dimension_name(adapter, annotation): annotation for annotation in imported
    }
    if len(imported) != len(DIMENSIONS) or set(by_name) != set(positions):
        raise RuntimeError(f"{PART_STEM}: native supplier dimension inventory differs")
    options = {}
    for name, expected, presentation, callout in DIMENSIONS:
        display = _early_bound(
            by_name[name].GetSpecificAnnotation(), "IDisplayDimension"
        )
        options[name] = {
            "label": f"{pin.SKU} supplier {name}",
            "units": "in",
            "precision": PRECISION,
            "expected_mm": expected,
            "presentation": presentation,
            "callout": callout,
            "configuration": pin.SUPPLIER_REFERENCE_CONFIGURATION,
        }
        supplier_reference_dimension(adapter, display, **options[name])
    # Keep the diameter's native line and witnesses where curation put them;
    # shelf its text, with the mate rows, left of them.
    shelf = {
        pin.DIAMETER_DIMENSION: (
            positions[pin.DIAMETER_DIMENSION][0] - DIAMETER_TEXT_SHELF,
            middle_y,
        )
    }
    offset_dimension_text(adapter, imported, shelf)
    expected = {
        key: (
            {name: pin.SUPPLIER_FEATURE for name, *_ in DIMENSIONS}
            if key == VIEW
            else {}
        )
        for key in views
    }
    configurations = {
        key: str(_early_bound(each, "IView").ReferencedConfiguration)
        for key, each in views.items()
    }

    def settled() -> None:
        found = reacquire_supplier_dimensions(
            adapter, views, expected=expected, configurations=configurations
        )
        for name, presentation in options.items():
            display = found[name]
            assert_supplier_configuration_value(
                display,
                pin.SUPPLIER_REFERENCE_CONFIGURATION,
                presentation["expected_mm"],
                label=name,
            )
            native = _early_bound(display.GetDimension2(0), "IDimension")
            if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
                raise RuntimeError(f"{name}: unprovided supplier tolerance appeared")
            assert_supplier_reference_dimension(adapter, display, **presentation)
            if name in shelf and display.OffsetText is not True:
                raise RuntimeError(
                    f"{name}: supplier text returned to its dimension line"
                )

    return (settled,)


async def build(adapter: Any) -> dict[str, str]:
    return await build_supplier_spring_drawing(
        adapter,
        SPEC,
        item=notes.ITEM,
        supplier_dimensions=annotate_pin_outline,
        supplier_margins=SUPPLIER_MARGINS,
        supplier_reference_features=SOURCE_FEATURES,
        stock_configuration=pin.SUPPLIER_REFERENCE_CONFIGURATION,
        prepare_views=prepare_pin_outline,
        include_right=False,
        include_top=False,
        installed_variants=notes.VARIANTS,
        installed_configuration=notes.VARIANTS[0][0],
        stock_caption="SUPPLIER PIN AS PURCHASED",
        spring_metadata=True,
        unit=part_drawing_unit(PART_STEM),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM], nargs="?", default=PART_STEM)
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
