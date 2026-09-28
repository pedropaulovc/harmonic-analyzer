"""The simplified-view configuration policy (SolidWorks-free)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from _drawing_common import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    view_configuration,
)
from _drawing_simplified import bom_identity_for_child, is_simplified, simplified_name

HLV, HLR, SHADED, SHADED_EDGES = 1, 2, 3, 7


class FakeView:
    """An IView whose configuration switch lands only when the drawing rebuilds."""

    def __init__(
        self,
        scale: tuple[float, float],
        orientation: str,
        mode: int,
        configuration: str = ASSEMBLY_VIEW_CONFIGURATION,
        *,
        accepts: bool = True,
    ) -> None:
        self.ScaleRatio = scale
        self.orientation = orientation
        self.mode = mode
        self.configuration = configuration
        self.accepts = accepts
        self.pending: str | None = None

    def GetOrientationName(self) -> str:
        return self.orientation

    def GetDisplayMode2(self) -> int:
        return self.mode

    @property
    def ReferencedConfiguration(self) -> str:
        return self.configuration

    @ReferencedConfiguration.setter
    def ReferencedConfiguration(self, value: str) -> None:
        if self.accepts:
            self.pending = value


class FakeDrawing:
    """One sheet of ``FakeView``s; ``EditRebuild3`` regenerates them."""

    def __init__(self, views: list[FakeView]) -> None:
        self.views = views
        self.rebuilds = 0

    def EditRebuild3(self) -> bool:
        self.rebuilds += 1
        for view in self.views:
            if view.pending is not None:
                view.configuration, view.pending = view.pending, None
        return True

    def GetSheetNames(self) -> list[str]:
        return ["Sheet1"]

    def Sheet(self, _name: str) -> SimpleNamespace:
        return SimpleNamespace(GetViews=lambda: list(self.views))


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


def _apply(view: FakeView, role: ViewRole = ViewRole.PLAIN) -> tuple[str, FakeDrawing]:
    drawing = FakeDrawing([view])
    applied = apply_view_configuration(
        SimpleNamespace(currentModel=drawing), view, role=role, label="fixture"
    )
    return applied, drawing


@pytest.mark.parametrize(
    ("view", "role", "expected"),
    [
        (FakeView((1.0, 4.0), "*Front", HLR), ViewRole.PLAIN, SIMPLIFIED_VIEW_CONFIGURATION),
        (FakeView((1.0, 2.0), "*Right", HLV), ViewRole.PLAIN, SIMPLIFIED_VIEW_CONFIGURATION),
        # A pictorial view is judged shaded whatever its current line mode.
        (FakeView((1.0, 4.0), "*Isometric", HLR), ViewRole.PLAIN, ASSEMBLY_VIEW_CONFIGURATION),
        (FakeView((1.0, 4.0), "*Front", HLR), ViewRole.BOM, ASSEMBLY_VIEW_CONFIGURATION),
        # A view enlarged past 1:2 goes back to full detail.
        (
            FakeView((1.0, 1.0), "*Front", HLR, SIMPLIFIED_VIEW_CONFIGURATION),
            ViewRole.PLAIN,
            ASSEMBLY_VIEW_CONFIGURATION,
        ),
    ],
)
def test_a_view_is_left_on_its_policy_configuration(view, role, expected) -> None:
    applied, _drawing = _apply(view, role)
    assert applied == expected
    assert view.ReferencedConfiguration == expected


def test_a_view_already_on_its_configuration_is_not_regenerated() -> None:
    view = FakeView((1.0, 4.0), "*Front", HLR, SIMPLIFIED_VIEW_CONFIGURATION)
    _applied, drawing = _apply(view)
    assert drawing.rebuilds == 0


def test_a_view_that_does_not_take_its_configuration_is_refused() -> None:
    view = FakeView((1.0, 4.0), "*Front", HLR, accepts=False)
    with pytest.raises(RuntimeError, match="Default Simplified"):
        _apply(view)
