"""Focused contracts for part-owned surface-finish controls."""

from __future__ import annotations

import math

import pytest

from _gtol_cylinder import CylinderFace
from _surface_finish import (
    GROUND,
    GROUND_INCH,
    GROUND_UM,
    MACHINED,
    MACHINED_INCH,
    MACHINED_UM,
    SEAT,
    SEAT_INCH,
    SEAT_UM,
    SurfaceFinishControl,
    ra,
    surface_finish_by_key,
)


def _control(key: str) -> SurfaceFinishControl:
    return SurfaceFinishControl(
        key=key,
        roughness_um=1.6,
        face=CylinderFace(diameter_mm=5.0),
    )


def test_resolves_surface_finish_by_stable_key() -> None:
    bore = _control("bore")

    assert surface_finish_by_key((_control("journal"), bore), "bore") is bore


def test_rejects_unknown_native_attachment_mode() -> None:
    with pytest.raises(ValueError, match="native_attachment"):
        SurfaceFinishControl(
            key="bore",
            roughness_um=1.6,
            face=CylinderFace(diameter_mm=5.0),
            native_attachment="configuration",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "controls, expected_count",
    [
        ((), 0),
        ((_control("bore"), _control("bore")), 2),
    ],
)
def test_rejects_missing_or_ambiguous_surface_finish_keys(
    controls: tuple[SurfaceFinishControl, ...], expected_count: int
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"surface-finish key 'bore' resolved {expected_count} controls",
    ):
        surface_finish_by_key(controls, "bore")


@pytest.mark.parametrize(
    "grade_um, rendered",
    [(GROUND_UM, "0.8"), (MACHINED_UM, "1.6"), (SEAT_UM, "3.2"), (2.0, "2.0")],
)
def test_metric_rendering_is_unchanged(grade_um: float, rendered: str) -> None:
    assert ra(grade_um) == rendered
    assert ra(grade_um, unit="mm") == rendered


def test_metric_callout_strings_are_unchanged() -> None:
    assert (GROUND, MACHINED, SEAT) == ("0.8", "1.6", "3.2")


@pytest.mark.parametrize(
    "grade_um, rendered",
    [(MACHINED_UM, "63"), (GROUND_UM, "32"), (SEAT_UM, "125")],
)
def test_inch_rendering_prints_preferred_microinch_grades(
    grade_um: float, rendered: str
) -> None:
    assert ra(grade_um, unit="in") == rendered


def test_inch_callout_strings_print_microinches() -> None:
    assert (GROUND_INCH, MACHINED_INCH, SEAT_INCH) == ("32", "63", "125")


@pytest.mark.parametrize("grade_um", [1.0, 2.0, 0.81, 6.3])
def test_inch_rendering_refuses_a_grade_without_a_project_mapping(
    grade_um: float,
) -> None:
    with pytest.raises(ValueError, match="no preferred microinch grade"):
        ra(grade_um, unit="in")


@pytest.mark.parametrize("unit", ["cm", "inch", "IN", "MM", ""])
def test_rendering_refuses_an_unsupported_unit(unit: str) -> None:
    with pytest.raises(ValueError, match="display unit must be 'mm' or 'in'"):
        ra(MACHINED_UM, unit=unit)  # type: ignore[arg-type]


@pytest.mark.parametrize("unit", ["mm", "in"])
@pytest.mark.parametrize("grade_um", [0.0, -1.6, math.nan, math.inf, -math.inf])
def test_rendering_refuses_a_non_positive_or_non_finite_grade(
    grade_um: float, unit: str
) -> None:
    with pytest.raises(ValueError, match="must be positive and finite"):
        ra(grade_um, unit=unit)  # type: ignore[arg-type]


def test_control_defaults_to_metric_display() -> None:
    control = SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(diameter_mm=5.0))

    assert control.display_unit == "mm"
    assert control.roughness_ra == "1.6"


def test_inch_control_renders_microinches_and_keeps_metric_roughness() -> None:
    control = SurfaceFinishControl(
        key="bore",
        roughness_um=MACHINED_UM,
        face=CylinderFace(diameter_mm=5.0),
        display_unit="in",
    )

    assert control.roughness_um == 1.6
    assert control.roughness_ra == "63"


def test_control_rejects_unknown_display_unit() -> None:
    with pytest.raises(ValueError, match="display_unit must be 'mm' or 'in'"):
        SurfaceFinishControl(
            key="bore",
            roughness_um=MACHINED_UM,
            face=CylinderFace(diameter_mm=5.0),
            display_unit="inch",  # type: ignore[arg-type]
        )


def test_inch_control_rejects_a_grade_off_the_preferred_series() -> None:
    with pytest.raises(ValueError, match="no preferred microinch grade"):
        SurfaceFinishControl(
            key="bore",
            roughness_um=2.0,
            face=CylinderFace(diameter_mm=5.0),
            display_unit="in",
        )
