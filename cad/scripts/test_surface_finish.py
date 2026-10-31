"""Focused contracts for part-owned surface-finish controls."""

from __future__ import annotations

import pytest

from _gtol_cylinder import CylinderFace
from _surface_finish import (
    GROUND_UM,
    MACHINED_UM,
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
    ("grade_um", "mm", "inch"),
    [(GROUND_UM, "0.8", "32"), (MACHINED_UM, "1.6", "63"), (SEAT_UM, "3.2", "125")],
)
def test_inch_sheets_print_the_preferred_microinch_grade(grade_um, mm, inch) -> None:
    assert ra(grade_um) == mm
    assert ra(grade_um, unit="in") == inch
    control = SurfaceFinishControl(
        "bore", grade_um, CylinderFace(5.0), display_unit="in"
    )
    assert (control.roughness_um, control.roughness_ra) == (grade_um, inch)


@pytest.mark.parametrize(("grade_um", "unit"), [(2.0, "in"), (MACHINED_UM, "cm")])
def test_unmapped_grades_and_unknown_units_are_refused(grade_um, unit) -> None:
    with pytest.raises(ValueError):
        ra(grade_um, unit=unit)
