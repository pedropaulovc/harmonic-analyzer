"""Create the shared purchased reference sheet for McMaster 90280A201."""

from __future__ import annotations

import argparse
import sys
from functools import partial
from math import dist, isfinite
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import iter_views

import _telemetry
from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M, sheet_region
from _drawing_common import is_pictorial_orientation, rebuild_drawing
from _drawing_layout_audit import _Reader, _dump_annotation
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from _supplier_screw_reference_names import FEATURE_BY_PLANE
from _layout_audit import (
    FindingSeverity,
    annotation_geometry,
    audit_dump,
    calibrate_sheet_advance,
    display_box,
    severity,
)
import sh_vn_clamp_screw_spec as supplier
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["sh_vn_clamp_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#8-32 x 1-1/4 NARROW FILLISTER HEAD SLOTTED SCREW"
# The actual 90280A201 supplier drawing (supplier.SUPPLIER_DRAWING_URL) shows
# the four sizes and 8-32 on a readable axial profile. Keep those native
# references, but give the vertical Top profile its own taller sheet band.
_POSITION_TOLERANCE_M = 1e-5
_ORIENTATIONS = {
    name: orientation
    for name, _value, orientation in supplier.SUPPLIER_REFERENCE_DIMENSIONS
}


def _supplier_displays(adapter: Any) -> dict[str, Any]:
    """Reacquire exact native identities without the annotation-name convenience path."""
    expected = {}
    for name in _ORIENTATIONS:
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


def _native_geometry(adapter: Any, display: Any, name: str) -> dict[str, Any]:
    """Measure current text, witnesses and tip-incident line/arrow reach."""
    reader = _Reader(adapter)
    record = _dump_annotation(reader, display.GetAnnotation())
    errors = reader.take_errors()
    if errors or record is None or int(record.get("type", 0)) != 4:
        raise RuntimeError(f"{name}: unreadable clamp supplier annotation: {errors}")
    data = record.get("display") or {}
    texts = data.get("texts") or ()
    if not texts or any(
        not isfinite(float(row.get(key) or 0.0)) or float(row.get(key) or 0.0) <= 0.0
        for row in texts
        for key in ("w", "h")
    ):
        raise RuntimeError(f"{name}: clamp supplier text has no measured native size")
    text = display_box({"texts": texts})
    arrows = data.get("arrows") or ()
    if (
        text is None
        or len(arrows) != 2
        or any(
            len(row) < 8 or not all(isfinite(float(value)) for value in row)
            for row in arrows
        )
    ):
        raise RuntimeError(f"{name}: unreadable clamp supplier arrow/text geometry")
    axis = 0 if _ORIENTATIONS[name] == "horizontal" else 1
    tips = tuple(
        sorted((tuple(map(float, row[:2])) for row in arrows), key=lambda p: p[axis])
    )
    if (
        tips[1][axis] <= tips[0][axis]
        or abs(tips[0][1 - axis] - tips[1][1 - axis]) > _POSITION_TOLERANCE_M
    ):
        raise RuntimeError(f"{name}: clamp supplier dimension line changed orientation")
    geometry = annotation_geometry(
        record, owner=name, advance=calibrate_sheet_advance((record,))
    )
    if geometry is None:
        raise RuntimeError(f"{name}: no clamp supplier native line geometry")
    physical = [
        segment
        for segment in geometry.segments
        if segment.role == "dim-line"
        and abs((segment.y1 - segment.y0) if axis == 0 else (segment.x1 - segment.x0))
        <= _POSITION_TOLERANCE_M
        and any(
            dist(tip, endpoint) <= _POSITION_TOLERANCE_M
            for tip in tips
            for endpoint in ((segment.x0, segment.y0), (segment.x1, segment.y1))
        )
    ]
    # OffsetText adds a connector and underline which the audit may also
    # classify as ext-line. Only perpendicular runs on each actual arrow
    # station are physical witnesses; keep all other ink in the audit record.
    witnesses = []
    for tip in tips:
        runs = [
            segment
            for segment in geometry.segments
            if segment.role == "ext-line"
            and abs(
                (segment.x1 - segment.x0) if axis == 0 else (segment.y1 - segment.y0)
            )
            < 1e-7
            and abs((segment.x0 if axis == 0 else segment.y0) - tip[axis])
            <= _POSITION_TOLERANCE_M
        ]
        if not runs:
            raise RuntimeError(f"{name}: clamp supplier lost a native witness")
        across = [
            value
            for segment in runs
            for value in (
                (segment.y0, segment.y1) if axis == 0 else (segment.x0, segment.x1)
            )
        ]
        witnesses.append((tip[axis], min(across), max(across)))
    if any(
        not any(
            dist(tip, endpoint) <= _POSITION_TOLERANCE_M
            for segment in physical
            for endpoint in ((segment.x0, segment.y0), (segment.x1, segment.y1))
        )
        for tip in tips
    ):
        raise RuntimeError(f"{name}: clamp supplier lost native witness/line ink")
    reach = max(
        coordinate
        for segment in (
            *physical,
            *(segment for segment in geometry.segments if segment.role == "arrow"),
        )
        for coordinate in (
            (segment.x0, segment.x1) if axis == 0 else (segment.y0, segment.y1)
        )
    )
    return dict(
        record=record,
        text=text,
        axis=axis,
        tips=tips,
        witnesses=tuple(witnesses),
        reach=reach,
    )


def _assert_stations(name: str, before: dict[str, Any], after: dict[str, Any]) -> None:
    for key in ("tips", "witnesses"):
        if len(before[key]) != len(after[key]) or any(
            dist(old, new) > _POSITION_TOLERANCE_M
            for old, new in zip(before[key], after[key], strict=True)
        ):
            raise RuntimeError(f"{name}: clamp supplier native {key} moved")


def _shelf_target(
    geometry: dict[str, Any], position: tuple[float, ...], transverse: float
) -> tuple[float, float]:
    """Place the complete native text beyond the measured outside-arrow tail."""
    axis = geometry["axis"]
    text = geometry["text"]
    low = text.xmin if axis == 0 else text.ymin
    target = [position[0], position[1]]
    target[axis] += geometry["reach"] + CLEAR_GAP_M + PLACE_SETTLE_M - low
    target[1 - axis] = transverse
    return target[0], target[1]


def _assert_supplier_layout(adapter: Any, expected: dict[str, dict[str, Any]]) -> None:
    """Reacquire all four references; native paths and settled shelves must clear."""
    found = _supplier_displays(adapter)
    records = {}
    for name, display in found.items():
        actual = _native_geometry(adapter, display, name)
        records[name] = actual["record"]
        if name in expected:
            _assert_stations(name, expected[name], actual)
            text = actual["text"]
            low = text.xmin if actual["axis"] == 0 else text.ymin
            if display.OffsetText is not True or low < actual["reach"] + CLEAR_GAP_M:
                raise RuntimeError(
                    f"{name}: clamp supplier text crowds its native line"
                )
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
    rebuild_drawing(adapter, label="clamp supplier reference text measured")
    expected = {}
    positions = {}
    anchors = {}
    found = _supplier_displays(adapter)
    for name, display in found.items():
        geometry = _native_geometry(adapter, display, name)
        axis = geometry["axis"]
        extent = geometry["text"].width if axis == 0 else geometry["text"].height
        span = geometry["tips"][1][axis] - geometry["tips"][0][axis]
        if extent + 2 * (CLEAR_GAP_M + PLACE_SETTLE_M) <= span:
            continue
        expected[name] = geometry
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        position = tuple(float(value) for value in annotation.GetPosition())
        if len(position) != 3 or not all(map(isfinite, position)):
            raise RuntimeError(f"{name}: unreadable clamp supplier text position")
        positions[name] = position
        # As on the thumb sheet, seed offset mode from the measured arrow
        # station, not a guessed font-to-dimension-line distance.
        anchor = list(position)
        anchor[1 - axis] = sum(tip[1 - axis] for tip in geometry["tips"]) / 2
        anchors[name] = tuple(anchor)
        if display.OffsetText is not False or not annotation.SetPosition2(*anchor):
            raise RuntimeError(f"{name}: cannot seed clamp supplier offset text")
    rebuild_drawing(adapter, label="clamp supplier measured offset anchors")
    found = _supplier_displays(adapter)
    for name in expected:
        display = found[name]
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        actual = tuple(float(value) for value in annotation.GetPosition())
        anchor = anchors[name]
        if (
            len(actual) != 3
            or not all(map(isfinite, actual))
            or dist(actual, anchor) > _POSITION_TOLERANCE_M
        ):
            raise RuntimeError(f"{name}: measured clamp supplier anchor did not settle")
        display.OffsetText = True
        if not annotation.SetPosition2(*anchor):
            raise RuntimeError(f"{name}: cannot enable clamp supplier offset text")
    rebuild_drawing(adapter, label="clamp supplier native offset mode")
    found = _supplier_displays(adapter)
    for name, before in expected.items():
        display = found[name]
        geometry = _native_geometry(adapter, display, name)
        _assert_stations(name, before, geometry)
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        current = tuple(float(value) for value in annotation.GetPosition())
        target = _shelf_target(geometry, current, positions[name][1 - geometry["axis"]])
        if not annotation.SetPosition2(*target, 0.0):
            raise RuntimeError(f"{name}: cannot shelf clamp supplier text")
    rebuild_drawing(adapter, label="clamp supplier measured text shelves")
    _assert_supplier_layout(adapter, expected)
    settled_checks.append(partial(_assert_supplier_layout, adapter, expected))


async def build(adapter: Any) -> dict[str, str]:
    checks = []
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        view_layout="tall_top",
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
        unit=part_drawing_unit("sh-vn-clamp-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
