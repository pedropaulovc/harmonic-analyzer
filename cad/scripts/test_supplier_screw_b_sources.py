"""Supplier witness routes avoid wider heads and distinguish stock from trim."""

from __future__ import annotations

from importlib import import_module

import pytest


def test_disc_stock_length_is_not_the_installed_cut_span():
    import _mcmaster_91794a055 as source
    import vn_transgear_disc_screw_spec as finished

    stock_rows = [
        row
        for row in source.SUPPLIER_REFERENCE_DIMENSIONS
        if source.SUPPLIER_REFERENCE_FORMATS[row[0]][3] == "AS-SUPPLIED STOCK LENGTH"
    ]
    assert len(stock_rows) == 1
    name, value, orientation = stock_rows[0]
    assert orientation == "vertical"
    start_x, start_y = source.SUPPLIER_REFERENCE_STARTS[name]
    stock_tip_y = start_y + value
    # A separate nominal stock witness starts at the bearing datum and
    # reaches beyond the installed tip, not along its shortened solid.
    assert start_y == 0.0
    assert stock_tip_y == pytest.approx(-source.SHANK_LEN)
    assert stock_tip_y < -finished.CUT_LENGTH
    assert start_x < -source.HEAD_DIA / 2.0
    assert source.SHANK_LEN - finished.CUT_LENGTH > finished.CUT_END_BREAK_MAX


@pytest.mark.parametrize(
    "sku",
    (
        "90114a124",
        "90114a511",
        "90280a108",
        "90280a196",
        "90280a197",
        "90280a201",
        "90280a203",
        "90280a837",
        "91251a108",
        "91410a540",
        "91792a108",
        "91794a055",
        "91794a078",
        "91794a080",
        "91794a112",
        "92240a540",
        "92446a077",
        "93075a199",
        "93585a190",
    ),
)
def test_thread_witness_interval_does_not_cross_the_head(sku):
    from _supplier_screw_layout import supplier_screw_lane_plan, supplier_screw_margins

    source = import_module(f"_mcmaster_{sku}")
    rows = {
        name: (value, axis)
        for name, value, axis in source.SUPPLIER_REFERENCE_DIMENSIONS
    }
    starts = source.SUPPLIER_REFERENCE_STARTS
    planes = source.SUPPLIER_REFERENCE_PLANES
    name = "SupplierThreadDiameter"
    plane = planes.get(name, "Front")
    length = "SupplierStockLength" if "SupplierStockLength" in rows else "SupplierLength"
    assert rows[name][1] == "horizontal"
    assert (
        planes.get(length, "Front")
        == planes.get("SupplierHeadHeight", "Front")
        == plane
    )
    head_start = starts.get("SupplierHeadHeight", (0.0, 0.0))[1]
    head_end = head_start + rows["SupplierHeadHeight"][0]
    length_start = starts.get(length, (0.0, 0.0))[1]
    tip = length_start + rows[length][0]
    head_low, head_high = sorted((head_start, head_end))
    low, high = min(tip, head_low), max(tip, head_high)
    plan = supplier_screw_lane_plan(
        source.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=planes,
        sides=source.SUPPLIER_REFERENCE_SIDES,
    )
    side, offset = plan[name]
    destination = high + offset * 1000.0 if side == "top" else low - offset * 1000.0
    path_low, path_high = sorted((starts[name][1], destination))
    # This compares the actual axial interval traversed by both diameter
    # witnesses with the head's source interval, independent of side spelling.
    assert max(path_low, head_low) >= min(path_high, head_high)
    margins = supplier_screw_margins(
        source.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=planes,
        sides=source.SUPPLIER_REFERENCE_SIDES,
    )
    assert margins[f"*{plane}"][3 if side == "top" else 1] > offset


def test_shoulder_and_thread_witnesses_escape_below_the_pivot_head():
    import _mcmaster_91829a560 as source
    from _supplier_screw_layout import supplier_screw_lane_plan

    rows = {name: value for name, value, _ in source.SUPPLIER_REFERENCE_DIMENSIONS}
    starts = source.SUPPLIER_REFERENCE_STARTS
    plan = supplier_screw_lane_plan(
        source.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=source.SUPPLIER_REFERENCE_PLANES,
        sides=source.SUPPLIER_REFERENCE_SIDES,
    )
    tip = starts["SupplierThreadLength"][1] + rows["SupplierThreadLength"]
    head_high = rows["SupplierHeadHeight"]
    destinations = []
    for name in ("SupplierShoulderDiameter", "SupplierThreadDiameter"):
        side, offset = plan[name]
        destination = (
            head_high + offset * 1000.0
            if side == "top"
            else tip - offset * 1000.0
        )
        low, high = sorted((starts[name][1], destination))
        assert max(low, 0.0) >= min(high, head_high)
        destinations.append(destination)
    # Both chords are centred on the axis: their outward dimension lines
    # must occupy different lanes rather than overprinting at the same point.
    assert destinations[0] != destinations[1]


def test_thumb_collar_and_thread_witnesses_do_not_traverse_the_larger_head():
    import _mcmaster_99607a213 as source
    from _supplier_screw_layout import supplier_screw_lane_plan, supplier_screw_margins

    rows = {name: value for name, value, _ in source.SUPPLIER_REFERENCE_DIMENSIONS}
    starts = source.SUPPLIER_REFERENCE_STARTS
    head_start = starts.get("SupplierHeadHeight", (0.0, 0.0))[0]
    head_end = head_start + rows["SupplierHeadHeight"]
    tip = starts["SupplierLength"][0] + rows["SupplierLength"]
    plan = supplier_screw_lane_plan(
        source.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=source.SUPPLIER_REFERENCE_PLANES,
        sides=source.SUPPLIER_REFERENCE_SIDES,
    )
    destinations = []
    for name in ("SupplierCollarDiameter", "SupplierThreadDiameter"):
        side, offset = plan[name]
        destination = (
            tip + offset * 1000.0
            if side == "right"
            else head_start - offset * 1000.0
        )
        low, high = sorted((starts[name][0], destination))
        assert rows[name] < rows["SupplierHeadDiameter"]
        assert max(low, head_start) >= min(high, head_end)
        if rows[name] < rows["SupplierCollarDiameter"]:
            assert max(low, head_end) >= min(high, starts["SupplierLength"][0])
        destinations.append(destination)
    assert destinations[0] != destinations[1]
    side, offset = plan["SupplierHeadDiameter"]
    head_destination = (
        tip + offset * 1000.0 if side == "right" else head_start - offset * 1000.0
    )
    head_station = starts["SupplierHeadDiameter"][0]
    # The largest chord can escape either way; choose the nearer free end,
    # rather than claiming the smaller collar obstructs its wider witnesses.
    shortest = min(head_station - head_start, tip - head_station)
    assert abs(head_destination - head_station) == pytest.approx(
        shortest + offset * 1000.0
    )
    margins = supplier_screw_margins(
        source.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=source.SUPPLIER_REFERENCE_PLANES,
        sides=source.SUPPLIER_REFERENCE_SIDES,
    )
    assert set(margins) == {"*Front"}  # no padding on unannotated views


@pytest.mark.parametrize(
    "sku,pair",
    (
        ("91829a560", ("SupplierShoulderDiameter", "SupplierThreadDiameter")),
        ("99607a213", ("SupplierCollarDiameter", "SupplierThreadDiameter")),
    ),
)
def test_nested_diameter_witnesses_do_not_cross_the_other_dimension_line(sku, pair):
    from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
    from _supplier_screw_layout import supplier_screw_lane_plan

    source = import_module(f"_mcmaster_{sku}")
    points = {}
    for name, value, orientation in source.SUPPLIER_REFERENCE_DIMENSIONS:
        if source.SUPPLIER_REFERENCE_PLANES.get(name, "Front") != "Front":
            continue
        if orientation == "angle":
            continue
        x, y = source.SUPPLIER_REFERENCE_STARTS.get(name, (0.0, 0.0))
        end = (x + value, y) if orientation == "horizontal" else (x, y + value)
        points[name] = ((x, y), end)
    all_points = [point for ends in points.values() for point in ends]
    bounds = (
        min(x for x, _ in all_points),
        min(y for _, y in all_points),
        max(x for x, _ in all_points),
        max(y for _, y in all_points),
    )
    plan = supplier_screw_lane_plan(
        source.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=source.SUPPLIER_REFERENCE_PLANES,
        sides=source.SUPPLIER_REFERENCE_SIDES,
    )

    def segments(routes):
        result = []
        for name in pair:
            side, offset = routes[name]
            start, end = points[name]
            offset_mm = offset * 1000.0
            if side in ("left", "right"):
                x = (
                    bounds[0] - offset_mm
                    if side == "left"
                    else bounds[2] + offset_mm
                )
                first, second = (x, start[1]), (x, end[1])
            else:
                y = (
                    bounds[1] - offset_mm
                    if side == "bottom"
                    else bounds[3] + offset_mm
                )
                first, second = (start[0], y), (end[0], y)
            for a, b in ((start, first), (end, second), (first, second)):
                result.append(
                    LeaderSegment(
                        name,
                        "dim",
                        a[0] / 1000.0,
                        a[1] / 1000.0,
                        b[0] / 1000.0,
                        b[1] / 1000.0,
                        "*Front",
                    )
                )
        return result

    assert not find_leader_leader_crossings(segments(plan), shared_terminus=0.0)
    # Positive control: reversing the nesting recreates the independently
    # observed smaller-chord witness crossing the larger dimension line.
    crossed = dict(plan)
    first, second = pair
    crossed[first] = (plan[first][0], plan[second][1])
    crossed[second] = (plan[second][0], plan[first][1])
    assert find_leader_leader_crossings(segments(crossed), shared_terminus=0.0)
