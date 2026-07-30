"""Focused contracts for part-owned surface-finish controls."""

from __future__ import annotations

import pytest

from _gtol_spec import CylinderFace
from _surface_finish import SurfaceFinishControl, surface_finish_by_key


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
