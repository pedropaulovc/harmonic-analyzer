"""Drawing-sheet drawable regions and zone margins.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from _drawing_layout_check import DrawableRegion
import _telemetry


# swZoneMargin_e -- the four margins reserved by the sheet format's zone band.
_ZONE_MARGINS = {"top": 0, "bottom": 1, "right": 2, "left": 3}


def sheet_drawable_region(
    adapter: Any, sheet: Any, *, width: float, height: float
) -> DrawableRegion:
    """The region inside the sheet's border/zone band, QUERIED from the sheet.

    The zone band is sheet metadata (``ISheet::GetZoneMargin``), so the audit
    reads it rather than carrying a measured copy: edit the zone margins in the
    DRWDOT and the keep-out follows automatically.

    A sheet format that declares no zone margins returns 0 for every side; that
    is reported as the whole sheet rather than treated as an error, so a plain
    unzoned sheet still audits.
    """
    margins: dict[str, float] = {}
    for side, code in _ZONE_MARGINS.items():
        value = adapter._attempt(lambda c=code: sheet.GetZoneMargin(c))
        if value is None:
            raise RuntimeError(
                f"cannot read the sheet's {side} zone margin -- the border "
                "keep-out cannot be audited"
            )
        margins[side] = float(value)
    if not any(margins.values()):
        _telemetry.warn(
            "sheet declares no zone margins; auditing against the full sheet"
        )
        return DrawableRegion.whole_sheet(width, height)
    region = DrawableRegion.from_margins(width, height, **margins)
    _telemetry.event(
        "drawing.zone_region",
        left=margins["left"],
        right=margins["right"],
        bottom=margins["bottom"],
        top=margins["top"],
    )
    return region
