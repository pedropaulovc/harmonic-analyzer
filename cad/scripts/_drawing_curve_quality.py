"""Precise native curve resolution for one new drawing document.

Faceted=False selects precise HLR, but its curves still use the drawing's
wireframe-resolution slider, so a small hole prints as a polygon (machinist
review of ch-amplitude-bar on main 31cea0b73: the Ø1.968 pin hole read as
draft quality).  The high-curve option refines the angular tolerance at
settings 92..100 (SDK Document Properties > Image Quality).  Separate so only
the recipes that call it carry it in their closure;
``draw_fr_top_frame._set_precise_curve_quality`` is the same setting.
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _com import _early_bound

# SOLIDWORKS 2026 swconst typelib: document Image Quality, not application
# defaults or the source part's shaded/draft tessellation.
_IMAGE_QUALITY_WIREFRAME = 45
_IMAGE_QUALITY_WIREFRAME_VALUE = 46
_IMAGE_QUALITY_HIGH_CURVES = 527
_NO_PREFERENCE_OPTION = 0
_WIREFRAME_CUSTOM = 2
_CURVE_RESOLUTION = 100


def set_precise_curve_quality(adapter: Any, *, label: str) -> None:
    """Pin the active drawing's curve resolution to its finest setting.

    Call it on the new drawing before any model view computes its geometry.
    Every setter is read back; a value that does not persist raises.
    """
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    before = (
        extension.GetUserPreferenceInteger(
            _IMAGE_QUALITY_WIREFRAME, _NO_PREFERENCE_OPTION
        ),
        extension.GetUserPreferenceInteger(
            _IMAGE_QUALITY_WIREFRAME_VALUE, _NO_PREFERENCE_OPTION
        ),
        extension.GetUserPreferenceToggle(
            _IMAGE_QUALITY_HIGH_CURVES, _NO_PREFERENCE_OPTION
        ),
    )
    for preference, value in (
        (_IMAGE_QUALITY_WIREFRAME, _WIREFRAME_CUSTOM),
        (_IMAGE_QUALITY_WIREFRAME_VALUE, _CURVE_RESOLUTION),
    ):
        if (
            extension.SetUserPreferenceInteger(preference, _NO_PREFERENCE_OPTION, value)
            is not True
        ):
            raise RuntimeError(f"failed to set {label} drawing curve resolution")
    if (
        extension.SetUserPreferenceToggle(
            _IMAGE_QUALITY_HIGH_CURVES, _NO_PREFERENCE_OPTION, True
        )
        is not True
    ):
        raise RuntimeError(f"failed to improve {label} drawing curve quality")
    after = (
        extension.GetUserPreferenceInteger(
            _IMAGE_QUALITY_WIREFRAME, _NO_PREFERENCE_OPTION
        ),
        extension.GetUserPreferenceInteger(
            _IMAGE_QUALITY_WIREFRAME_VALUE, _NO_PREFERENCE_OPTION
        ),
        extension.GetUserPreferenceToggle(
            _IMAGE_QUALITY_HIGH_CURVES, _NO_PREFERENCE_OPTION
        ),
    )
    if after[:2] != (_WIREFRAME_CUSTOM, _CURVE_RESOLUTION) or after[2] is not True:
        raise RuntimeError(f"{label} drawing curve quality did not persist: {after!r}")
    _telemetry.info(
        f"{label} drawing precise curve resolution",
        curve_quality_before=before,
        curve_quality_after=after,
    )
