"""MHA-SH-VN-58's sheet text: kept out of ``sh_vn_pivot_pin_spec``, which the
joint specs and the channel assembly import, so a sheet edit re-keys only the
pin and its drawing.

The purchase sheet names the supplier dowel on its ITEM row (the SKU and
supplier rows are property-linked) and its mates by Number at the supplier
diameter. Pressing and dressing the pins is MHA-CH-00's step text, and the
per-member quantities are the assembly BOM's: neither prints here
(drawing-simplicity-policy.md).
"""

from __future__ import annotations

import _config

# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø5/64 x 5/16 DOWEL PIN"

# The supplier diameter's below-callout: the parts each member presses into
# and runs in, by Number (rule 4), two lines.
PRESSED_IN = (
    _config.parts("ch-connecting-rod")["number"],
    _config.parts("ch-amplitude-bar")["number"],
)
RUNS_IN = (
    _config.parts("ch-rocker-arm")["number"],
    _config.parts("ch-channel-lever")["number"],
)
DIAMETER_CALLOUT = f"PRESS FIT IN {', '.join(PRESSED_IN)}\nRUNS IN {', '.join(RUNS_IN)}"
