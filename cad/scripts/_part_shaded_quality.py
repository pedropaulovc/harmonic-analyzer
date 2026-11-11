"""Finest shaded tessellation for one part document.

A drawing's shaded views tessellate the referenced part with the part's own
Image Quality "Shaded and draft quality" setting; the drawing's wireframe
resolution (``_drawing_curve_quality``) only refines the inked edges. At the
template's default deviation the 16T crank pinion's 3:1 isometric shaded each
involute flank as a few flat strips (machinist review of MHA-DT-10 on #2482,
rule 8: visibly faceted pictorial). The part saves the setting, so every
drawing of it inherits the setting. Separate so only the builders that call it
carry it in their recipe closure.
"""

from __future__ import annotations

from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info

import _telemetry
from _com import _early_bound


@_telemetry.traced("part.precise_shaded_quality", label_param="label")
def set_precise_shaded_quality(adapter: Any, *, label: str) -> None:
    """Pin the active part's shaded tessellation to its finest deviation.

    Custom quality at the minimum chordal deviation SolidWorks reports for
    this document, with edge-length optimisation on. Every setter is read
    back; a value that does not persist raises.
    """
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    option = _sw_type_info.constant("swDetailingNoOptionSpecified")
    quality = _sw_type_info.constant("swImageQualityShaded")
    custom = _sw_type_info.constant("swShadedImageQualityCustom")
    deviation = _sw_type_info.constant("swImageQualityShadedDeviation")
    edge_length = _sw_type_info.constant("swImageQualityUseHighQualityEdgeSize")

    # The three doubles are [in, out] in the typelib (makepy flag 3), so the
    # early-bound call needs placeholders; it returns them in the tuple.
    status, current, minimum, maximum = extension.GetUserPreferenceDoubleValueRange(
        deviation, 0.0, 0.0, 0.0
    )
    if status != 0 or not 0.0 < minimum <= maximum:
        raise RuntimeError(
            f"{label}: shaded deviation range unavailable "
            f"(status {status!r}, min {minimum!r}, max {maximum!r})"
        )
    before = (
        extension.GetUserPreferenceInteger(quality, option),
        current,
        extension.GetUserPreferenceToggle(edge_length, option),
    )
    if extension.SetUserPreferenceInteger(quality, option, custom) is not True:
        raise RuntimeError(f"failed to set {label} shaded image quality to custom")
    if extension.SetUserPreferenceDouble(deviation, option, minimum) is not True:
        raise RuntimeError(f"failed to set {label} shaded deviation to {minimum!r}")
    if extension.SetUserPreferenceToggle(edge_length, option, True) is not True:
        raise RuntimeError(f"failed to optimise {label} shaded edge length")
    after = (
        extension.GetUserPreferenceInteger(quality, option),
        extension.GetUserPreferenceDouble(deviation, option),
        extension.GetUserPreferenceToggle(edge_length, option),
    )
    # SolidWorks stores the deviation on its own slider grid: farm r9c asked
    # for the reported minimum and read back 1.0119e-05. So accept the
    # readback within 5 % of the minimum, and require it finer than before.
    if (
        after[0] != custom
        or not after[1] <= minimum * 1.05
        or not after[1] < current
        or after[2] is not True
    ):
        raise RuntimeError(
            f"{label} shaded image quality did not persist: {after!r} "
            f"(requested deviation {minimum!r} of range {minimum!r}..{maximum!r}, "
            f"was {current!r})"
        )
    _telemetry.info(
        f"{label} precise shaded tessellation",
        shaded_quality_before=before,
        shaded_quality_after=after,
        shaded_deviation_range=(minimum, maximum),
    )
