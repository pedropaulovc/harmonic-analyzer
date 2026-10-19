"""Create the purchased reference drawing for the frame tube cap."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_hidden_sketches import curate_view_dimensions
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
import vn_tube_frame_cap_spec as cap
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing


SPEC = DRAWINGS_BY_NAME["vn_tube_frame_cap"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "PUSH-ON ROUND TUBE CAP"


def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> Callable[[], None]:
    """Import only actual inside depth and straight bore, never exterior/flare."""
    references = []
    for orientation, feature, name, expected, precision, presentation, callout in (
        (
            "*Front", "CapSupplierDepth", "SupplierInsideDepth", cap.INSIDE_HEIGHT,
            cap.SUPPLIER_DEPTH_PRECISION, "length", "INSIDE DEPTH",
        ),
        (
            "*Top", "CapSupplierBore", "SupplierTubeOD", cap.INNER_DIAMETER,
            cap.SUPPLIER_TUBE_OD_PRECISION, "diameter", "FOR TUBE OD",
        ),
    ):
        view = views[orientation]
        x0, y0, x1, y1 = (float(v) for v in view.GetOutline())
        text_xy = (
            (x1 + 0.014, (y0 + y1) / 2.0)
            if orientation == "*Front"
            else (x1 + 0.012, y1 + 0.006)
        )
        annotations = curate_view_dimensions(
            adapter, view, keep={name: text_xy}, view_label=f"9275K141 {orientation}",
            dimensions_by_feature={feature: cap.SUPPLIER_DIMENSIONS[feature]},
        )
        if len(annotations) != 1:
            raise RuntimeError(f"9275K141: expected only {name}, got {len(annotations)}")
        display = _early_bound(
            _early_bound(annotations[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if int(native.DrivenState) != 1 or str(native.Name) != name:
            raise RuntimeError(f"9275K141: {name} is not its native driven source reference")
        settings = dict(
            label=f"9275K141 {name}", units="in", precision=precision,
            expected_mm=expected, presentation=presentation, callout=callout,
        )
        supplier_reference_dimension(adapter, display, **settings)
        references.append((display, feature, name, settings))

    def settled() -> None:
        if len(references) != 2:
            raise RuntimeError("9275K141: expected exactly two authored supplier references")
        for orientation, expected_count in (
            ("*Front", 1), ("*Top", 1), ("*Right", 0), ("*Isometric", 0),
        ):
            count = int(_early_bound(views[orientation], "IView").GetDisplayDimensionCount())
            if count != expected_count:
                raise RuntimeError(
                    f"9275K141 {orientation}: expected {expected_count} native references, got {count}"
                )
        for display, feature, name, settings in references:
            assert_supplier_reference_dimension(adapter, display, **settings)
            native = _early_bound(display.GetDimension2(0), "IDimension")
            owner = str(native.FullName).split("@")
            annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
            if (
                int(native.DrivenState) != 1 or str(native.Name) != name
                or len(owner) < 2 or owner[1] != feature
                or int(annotation.Visible) != 1
            ):
                raise RuntimeError(f"9275K141: settled {name} lost its visible driven source reference")

    return settled


async def build(adapter: Any) -> dict[str, str]:
    checks: list[Callable[[], None]] = []

    def dimensions(active_adapter: Any, views: dict[str, Any]) -> None:
        checks.append(supplier_dimensions(active_adapter, views))

    def settled() -> None:
        if len(checks) != 1:
            raise RuntimeError("9275K141: supplier references must be authored exactly once")
        checks[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=dimensions,
        settled_checks=(settled,),
        supplier_margins={
            "*Front": (0.020, 0.020, 0.040, 0.020),
            "*Top": (0.020, 0.020, 0.035, 0.020),
        },
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
