r"""MHA-SH-VN-58: the purchased 5/64 x 5/16 dowel both channel pivot joints press.

PURE DATA, no SolidWorks/COM imports. One McMaster-Carr 90145A299 SKU (18-8
stainless, chamfered, passivated; ``_mcmaster_90145a299``) in two installed
members: ``RodPin`` closes each connecting rod's fork round its rocker arm
(``sh_vn_pivot_pin_rod_spec``) and ``BarPin`` each amplitude bar's top notch
round its channel lever (``sh_vn_pivot_pin_bar_spec``). Each pin is used as
supplied, pressed through its fork or bar and dressed flush with both faces
at assembly (MHA-CH-00), which takes the catalogue chamfers off; it runs in
the arm's or lever's #47 hole.

Why this SKU (#2339): its 0/+.0002 in diameter band against the hole the
.0775 reamer is modelled to cut (.0775-.0779) presses .000225-.000825 in,
inside ANSI FN2 (.0002-.00085), and leaves the #47 running clearance at
main's .000175 in. The hardened 98381A (alloy, Rc50) and 98380A (416, Rc36)
dowels run +.0001/+.0003: .000325-.000925 in, over the FN2 cap, with .000075
in running clearance; an Rc50 end cannot be file-dressed flush. The pins
carry only spring-level loads at hand-crank speed, and the drill rod they
replace was annealed.

Owner ruling 2026-11-24, fit audit question 3 ("APPROVED as recommended",
option A): each host hole is reamed .0775 and prints no band; the pin itself
is its gauge (it presses in, it does not enter by hand), and a pin that does
enter by hand is bonded with LOCTITE 641 instead of the bar or rod being
scrapped (MHA-CH-00).

Frame (part): pin axis = part Z, axial mid-plane = Front Plane (z = 0); Axis1
is the pin axis (Right Plane x Top Plane). Each member is the INSTALLED pin,
its member's PIN_INSTALLED_LENGTH long. The zero-body SUPPLIER_REFERENCE
configuration carries the catalogue 5/64 x 5/16 outline the drawing prints.
"""

from __future__ import annotations

import _config
from _mcmaster_90145a299 import DIA_BAND_IN, DOWEL_SIZE, LENGTH_GRADE_IN, MM_PER_IN, SKU
from _package_units import drawing_unit

PART_STEM = "sh-vn-pivot-pin"
UNIT = drawing_unit(f"parts/{PART_STEM}", _config.parts("sh-vn-pivot-pin"))

ROD_PIN_CONFIGURATION = "RodPin"
BAR_PIN_CONFIGURATION = "BarPin"
# The registry order: default member first.
CONFIGURATIONS = (ROD_PIN_CONFIGURATION, BAR_PIN_CONFIGURATION)

# --- The catalogue pin (mm). ---
PIN_DIA, PIN_LENGTH = DOWEL_SIZE  # 1.984375 x 7.9375
PIN_DIA_LIMITS = tuple(PIN_DIA + band * MM_PER_IN for band in DIA_BAND_IN)
PIN_LENGTH_LIMITS = (
    PIN_LENGTH - LENGTH_GRADE_IN * MM_PER_IN,
    PIN_LENGTH + LENGTH_GRADE_IN * MM_PER_IN,
)

# ANSI B4.1-1967 (R1987) FN2 "medium drive fit, suitable for ordinary steel
# parts", nominal size 0-0.12 in: interference .0002-.00085 in (mm).
FN2_INTERFERENCE = (0.0002 * MM_PER_IN, 0.00085 * MM_PER_IN)

# The host holes' .0775 reamer and the hole it is modelled to cut: an
# ANALYSIS band (the reamer's size to .0004 over), not a printed limit. The
# sheets print the reamer's size and no band (owner ruling 2026-11-24, fit
# audit question 3); the press budgets read this band.
HOLE_REAMER_DIA = 1.9685  # .0775 in
HOLE_REAMED_LIMITS = (HOLE_REAMER_DIA, 1.97866)  # .0775-.0779 in
# A pin that enters a hole by hand is bonded (MHA-CH-00). The largest hole
# that may be bonded is the one the .079 pin of the .061-.500 pin-gauge set
# (gauges.pin-gauges, a minus pin, .0788-.0790) does not enter: the bar and
# rod travelers try it only in a hole the pin entered. Delegated ruling
# 2026-11-24 (Main), no precedent; changes the number in the owner's
# 2026-11-24 fit-audit question 3 answer (.0785 → .079: the owned pin set
# has no .0785 pin; .079 is the nearest pin; HOLE WALL .078 MIN unchanged),
# #2144 (rulings.md D13): a single limit, .0005 looser: the gap to the
# smallest pin stays .0009, inside 641's gap fill (BOND_GAP), and the bar's
# hole wall is stated at this hole (.078 MIN, MHA-CH-01 RV-06).
BOND_HOLE_MAX = 0.0790 * MM_PER_IN  # 2.0066
# LOCTITE 641's gap fill (pd_transgear_knob_cup_spec.LOCTITE_641_GAP_MAX,
# Henkel's product page: "Gap fill: 0.15 mm"); 641 is the removable grade
# (drawing-guidelines.md rule 23: "641 where the part must come out"), so a
# bonded pin still comes out hot for channel service.
LOCTITE_641_GAP_MAX = 0.15
BOND_GAP = (0.0, BOND_HOLE_MAX - PIN_DIA_LIMITS[0])
if BOND_GAP[1] > LOCTITE_641_GAP_MAX:
    raise AssertionError("the largest bonded hole passes LOCTITE 641's gap fill")

# --- The zero-body supplier outline the purchase drawing dimensions. ---
SUPPLIER_REFERENCE_CONFIGURATION = "SUPPLIER_REFERENCE"
SUPPLIER_FEATURE = "SupplierPinNominalSide"
DIAMETER_DIMENSION = "SupplierPinDiameter"
LENGTH_DIMENSION = "SupplierPinLength"
DIMENSIONS_BY_FEATURE = {SUPPLIER_FEATURE: {DIAMETER_DIMENSION, LENGTH_DIMENSION}}

if PIN_DIA_LIMITS[0] != PIN_DIA or PIN_DIA_LIMITS[1] <= PIN_DIA:
    raise AssertionError(f"{SKU}: the catalogue band must sit on and over nominal")
