r"""Bar pivot pin (MHA-CH-011) drawing prose: the manufacturing notes the part
build stamps into the SLDPRT.

Kept out of ``ch_bar_pivot_pin_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and ``test_ch_bar_pivot_fit`` import the spec, so prose there
would re-key them on every wording edit. Imported ONLY by
``build_ch_bar_pivot_pin`` and the offline tests.

Policy rule 6: four lines a machinist cannot read off the views. The model is
the INSTALLED pin, so the blank's cut length is the one size the views cannot
show; the press and its removal are the retention requirement (user ruling
2026-10); the flush dressing is the bar-to-bar gap's requirement (#1038); the
running fit names its mating part. The title block owns the drill rod
(MATERIAL) and its finish.
"""

from __future__ import annotations

import ch_bar_pivot_pin_spec as pin

if pin.PIN_BLANK_LENGTH_BAND[0] != -pin.PIN_BLANK_LENGTH_BAND[1]:
    raise AssertionError("the blank note prints a symmetric band")
if pin.PIN_END_PROUD_MAX != 0.0:
    raise AssertionError("note 3 states flush ends")

DRAWING_NOTES = "\n".join(
    (
        f"1. CUT BLANK {pin.PIN_BLANK_LENGTH:.2f} "
        f"\u00b1{pin.PIN_BLANK_LENGTH_BAND[0]:.2f} LONG; INSTALLED STATE SHOWN.",
        "2. PRESS IN; REMOVABLE WITH PUNCH.",
        "3. PRESSED IN THE MHA-CH-001 REAMED TOP PIN HOLE;"
        " DRESS BOTH ENDS FLUSH, NEVER PROUD.",
        "4. RUNS FREE IN THE MHA-CH-002 #47 BAR-PIN HOLE.",
    )
)
