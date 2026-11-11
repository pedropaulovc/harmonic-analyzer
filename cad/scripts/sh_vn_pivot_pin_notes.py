"""MHA-SH-VN-58's sheet text: kept out of ``sh_vn_pivot_pin_spec``, which the
joint specs and the channel assembly import, so a sheet edit re-keys only the
pin and its drawing.

The purchase sheet names the supplier dowel on its ITEM row (the SKU and
supplier rows are property-linked), its mates by Number at the supplier
diameter, and the assembly that presses and dresses each member; it carries
no process narration (drawing-simplicity-policy.md).
"""

from __future__ import annotations

import _config
import sh_vn_pivot_pin_bar_spec as bar_pin
import sh_vn_pivot_pin_rod_spec as rod_pin

# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø5/64 x 5/16 DOWEL PIN"

# The assembly that presses each member through its fork or bar and dresses
# both ends flush (ch_channel_assembly_steps.DRAWING_NUMBER, test-pinned).
ASSEMBLY_NUMBER = "MHA-CH-00"
DRAWING_NOTES = f"{ASSEMBLY_NUMBER} PRESSES EACH PIN AND DRESSES BOTH ENDS FLUSH."

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

# Installed-member captions under each reference pictorial, with the
# registry's per-member quantity.
_QUANTITIES = _config.parts("sh-vn-pivot-pin")["configuration_quantities"]
VARIANTS = tuple(
    (
        spec.CONFIGURATION,
        f"{spec.BOM_DESCRIPTION}, QTY {_QUANTITIES[spec.CONFIGURATION]}",
    )
    for spec in (rod_pin, bar_pin)
)
