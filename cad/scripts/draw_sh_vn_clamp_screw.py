"""Create the shared purchased reference sheet for McMaster 90280A201."""

from __future__ import annotations

import argparse
import sys
from functools import partial
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import iter_views

import _telemetry
from _com import _early_bound
from _drawing_annotation_extent import sheet_region
from _drawing_common import is_pictorial_orientation
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_reference_text import measure_reference_text, shelve_reference_text
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from _supplier_screw_reference_names import FEATURE_BY_PLANE
from _layout_audit import FindingSeverity, audit_dump, severity
import sh_vn_clamp_screw_spec as supplier


SPEC = DRAWINGS_BY_NAME["sh_vn_clamp_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#8-32 x 1-1/4 NARROW FILLISTER HEAD SLOTTED SCREW"
# The actual 90280A201 supplier drawing (supplier.SUPPLIER_DRAWING_URL) shows
# the four sizes and 8-32 on a readable axial profile. Keep those native
# references, but give the vertical Top profile its own taller sheet band.
# Shelf axis of each reference: 0 along a horizontal row, 1 along a vertical.
_AXES = {
    name: 0 if orientation == "horizontal" else 1
    for name, _value, orientation in supplier.SUPPLIER_REFERENCE_DIMENSIONS
}


def _supplier_displays(adapter: Any) -> dict[str, Any]:
    """Reacquire exact native identities without the annotation-name convenience path."""
    expected = {}
    for name in _AXES:
        plane = supplier.SUPPLIER_REFERENCE_PLANES.get(name, "Front")
        expected[name] = (FEATURE_BY_PLANE[plane], f"*{plane}")
    found = {}
    actual = []
    invalid = False
    for raw_view in iter_views(adapter):
        view = _early_bound(raw_view, "IView")
        owner = str(view.GetOrientationName())
        display = view.GetFirstDisplayDimension6()
        while display is not None:
            display = _early_bound(display, "IDisplayDimension")
            native = display.GetDimension2(0)
            full_name = (
                str(_early_bound(native, "IDimension").FullName)
                if native is not None
                else ""
            )
            actual.append((full_name, owner))
            identity = full_name.split("@")
            name = identity[0]
            if (
                len(identity) < 2
                or name in found
                or expected.get(name) != (identity[1], owner)
            ):
                invalid = True
            else:
                found[name] = display
            display = display.GetNext5()
    if invalid or set(found) != set(expected):
        expected_inventory = sorted(
            (f"{name}@{feature}", owner) for name, (feature, owner) in expected.items()
        )
        raise RuntimeError(
            "clamp supplier dimension inventory changed: "
            f"expected={expected_inventory}; actual={actual}; "
            f"missing={sorted(set(expected) - set(found))}"
        )
    return found


def _assert_supplier_layout(adapter: Any) -> None:
    """Reacquire all four references; every native path must clear on the sheet."""
    records = {
        name: measure_reference_text(
            adapter, display, axis=_AXES[name], label=f"clamp supplier {name}"
        )["record"]
        for name, display in _supplier_displays(adapter).items()
    }
    views = []
    for view in iter_views(adapter):
        view = _early_bound(view, "IView")
        orientation = str(view.GetOrientationName())
        views.append(
            dict(
                name=str(view.GetName2()),
                orientation=orientation,
                pictorial=is_pictorial_orientation(orientation),
                outline=tuple(float(value) for value in view.GetOutline()),
                annotations=[
                    record
                    for name, record in records.items()
                    if orientation
                    == f"*{supplier.SUPPLIER_REFERENCE_PLANES.get(name, 'Front')}"
                ],
            )
        )
    template = DRAWING_TEMPLATES[SPEC.layout]
    region = sheet_region(adapter)
    findings = [
        finding
        for finding in audit_dump(
            dict(
                sheet="clamp supplier sheet",
                width=template.width_m,
                height=template.height_m,
                zone=dict(
                    left=region.xmin,
                    bottom=region.ymin,
                    right=template.width_m - region.xmax,
                    top=template.height_m - region.ymax,
                ),
                views=views,
                read_errors={},
            )
        )
        if severity(finding) is FindingSeverity.GATING
    ]
    if findings:
        raise RuntimeError(
            "clamp supplier paths are not clear:\n"
            + "\n".join(finding.format() for finding in findings)
        )


def _annotate_supplier_dimensions(
    adapter: Any, views: dict[str, Any], *, settled_checks: list
) -> None:
    annotate_supplier_screw(
        adapter,
        views,
        dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        formats=supplier.SUPPLIER_REFERENCE_FORMATS,
        starts=supplier.SUPPLIER_REFERENCE_STARTS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
        settled_checks=settled_checks,
    )
    # The core rebuilds, measures every row, shelves the short ones beyond
    # their native tails in three batched transitions and returns a read-only
    # station/shelf proof. This recipe keeps the exact inventory binding and
    # the whole-sheet native path audit on the settled state.
    proof = shelve_reference_text(
        adapter,
        reacquire=partial(_supplier_displays, adapter),
        axes=_AXES,
        label="clamp supplier",
    )
    _assert_supplier_layout(adapter)

    def settled() -> None:
        proof()
        _assert_supplier_layout(adapter)

    settled_checks.append(settled)


async def build(adapter: Any) -> dict[str, str]:
    checks = []
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        view_layout="tall_top",
        align_orthographic=True,
        supplier_dimensions=partial(
            _annotate_supplier_dimensions,
            settled_checks=checks,
        ),
        supplier_margins=supplier_screw_margins(
            supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
        ),
        settled_checks=checks,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
