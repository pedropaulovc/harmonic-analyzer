"""The simplified-view configuration policy (SolidWorks-free)."""

from __future__ import annotations

import pytest

from _drawing_common import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    view_configuration,
)
from _drawing_simplified import bom_identity_for_child, is_simplified, simplified_name

HLV, HLR, SHADED, SHADED_EDGES = 1, 2, 3, 7


def test_the_simplified_view_configuration_is_the_derived_default() -> None:
    assert SIMPLIFIED_VIEW_CONFIGURATION == simplified_name("Default") == "Default Simplified"
    assert is_simplified(SIMPLIFIED_VIEW_CONFIGURATION)
    assert not is_simplified(ASSEMBLY_VIEW_CONFIGURATION)


@pytest.mark.parametrize("mode", [HLV, HLR])
@pytest.mark.parametrize(
    ("scale", "expected"),
    [
        ((1.0, 2.0), SIMPLIFIED_VIEW_CONFIGURATION),  # the boundary is inclusive
        ((2.0, 4.0), SIMPLIFIED_VIEW_CONFIGURATION),  # the ratio, not the numbers
        ((1.0, 3.0), SIMPLIFIED_VIEW_CONFIGURATION),
        ((1.0, 8.0), SIMPLIFIED_VIEW_CONFIGURATION),
        ((2.0, 3.0), ASSEMBLY_VIEW_CONFIGURATION),
        ((1.0, 1.0), ASSEMBLY_VIEW_CONFIGURATION),
        ((2.0, 1.0), ASSEMBLY_VIEW_CONFIGURATION),
    ],
)
def test_a_line_view_is_simplified_at_one_to_two_or_smaller(mode, scale, expected) -> None:
    assert view_configuration(scale, mode) == expected


@pytest.mark.parametrize("mode", [SHADED, SHADED_EDGES, 0])
def test_a_shaded_or_wireframe_view_keeps_full_detail(mode) -> None:
    assert view_configuration((1.0, 8.0), mode) == ASSEMBLY_VIEW_CONFIGURATION


@pytest.mark.parametrize(
    "role", [ViewRole.EXPLODED, ViewRole.BOM, ViewRole.BALLOONS, ViewRole.FULL_DETAIL]
)
def test_a_view_that_carries_more_than_geometry_keeps_full_detail(role) -> None:
    assert view_configuration((1.0, 8.0), HLR, role) == ASSEMBLY_VIEW_CONFIGURATION


@pytest.mark.parametrize("scale", [(0.0, 2.0), (1.0, 0.0), (-1.0, 2.0)])
def test_a_degenerate_scale_is_refused(scale) -> None:
    with pytest.raises(ValueError, match="positive"):
        view_configuration(scale, HLR)


@pytest.mark.parametrize(
    ("parent", "child"),
    [
        (1, 1),  # document name: the child already prints the file name
        (2, 4),  # configuration name would print "<P> Simplified": use the parent's
        (4, 4),
        (8, 8),  # user specified: the AlternateName is copied with it
    ],
)
def test_a_derived_configuration_prints_its_parents_part_number(parent, child) -> None:
    assert bom_identity_for_child(parent) == child
