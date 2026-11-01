"""Issue #290: a package's ``drawing_unit`` resolves from its own registry row."""

from __future__ import annotations

import pytest

from _assembly_contract import assembly_contract
from _package_units import drawing_unit
from _part_properties import part_drawing_unit, part_properties

PILOT_INCH_PARTS = (
    "ms-stick",
    "ms-stop-block",
    "ms-stop-plate",
    "dt-pinion-cam",
    "fr-vn-gooseneck-set-screw",
)


@pytest.mark.parametrize(
    ("row", "unit"),
    [
        (None, "mm"),
        ({}, "mm"),
        ({"drawing_unit": "mm"}, "mm"),
        ({"drawing_unit": "in"}, "in"),
    ],
)
def test_an_undeclared_package_prints_millimetres(row, unit):
    assert drawing_unit("parts/x", row) == unit


@pytest.mark.parametrize("value", ["cm", "inch", "IN", True, None])
def test_an_unknown_unit_is_refused(value):
    with pytest.raises(ValueError, match="parts/x: drawing_unit must be 'mm' or 'in'"):
        drawing_unit("parts/x", {"drawing_unit": value})


@pytest.mark.parametrize("part", PILOT_INCH_PARTS)
def test_pilot_parts_print_inches_and_stamp_inch_rows(part):
    assert part_drawing_unit(part) == "in"
    assert part_properties(part)["TOL_LIN_XX"] == "±.01"


def test_the_metric_supplier_rail_and_unconverted_parts_stay_millimetres():
    for part in ("ch-rocker-arm-tl-vn-oblique-rail", "fr-harmonic-base", "no-such-part"):
        assert part_drawing_unit(part) == "mm"
    assert part_properties("ch-rocker-arm-tl-vn-oblique-rail")["TOL_LIN_XX"] == "±0.51"


def test_the_pilot_assembly_declares_inches_and_others_do_not():
    assert assembly_contract("ms-measuring-stick").drawing_unit == "in"
    assert assembly_contract("dt-drive-train").drawing_unit == "mm"
