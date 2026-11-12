r"""MHA-SH-VN-58: the purchased 5/64 x 5/16 dowel both channel pivot joints press.

PURE DATA, no SolidWorks/COM imports. One McMaster-Carr 90145A299 SKU (18-8
stainless, chamfered, passivated; ``_mcmaster_90145a299``) in two installed
members: ``RodPin`` closes each connecting rod's fork round its rocker arm
(``sh_vn_pivot_pin_rod_spec``) and ``BarPin`` each amplitude bar's top notch
round its channel lever (``sh_vn_pivot_pin_bar_spec``). Each pin is used as
supplied, pressed through its fork or bar and dressed flush with both faces
at assembly (MHA-CH-00), which takes the catalogue chamfers off; it runs in
the arm's or lever's #47 hole.

Why this SKU (#2339): its 0/+.0002 in diameter band against the owner-ruled
reamed hole (.0775-.0779) presses .000225-.000825 in, inside ANSI FN2
(.0002-.00085) by limits alone, and leaves the #47 running clearance at main's
.000175 in. The hardened 98381A (alloy, Rc50) and 98380A (416, Rc36) dowels
run +.0001/+.0003: .000325-.000925 in, over the FN2 cap the hole ruling was
sized to, with .000075 in running clearance; an Rc50 end cannot be
file-dressed flush. The pins carry only spring-level loads at hand-crank
speed, and the drill rod they replace was annealed.

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

# --- The zero-body supplier outline the purchase drawing dimensions. ---
SUPPLIER_REFERENCE_CONFIGURATION = "SUPPLIER_REFERENCE"
SUPPLIER_FEATURE = "SupplierPinNominalSide"
DIAMETER_DIMENSION = "SupplierPinDiameter"
LENGTH_DIMENSION = "SupplierPinLength"
DIMENSIONS_BY_FEATURE = {SUPPLIER_FEATURE: {DIAMETER_DIMENSION, LENGTH_DIMENSION}}

if PIN_DIA_LIMITS[0] != PIN_DIA or PIN_DIA_LIMITS[1] <= PIN_DIA:
    raise AssertionError(f"{SKU}: the catalogue band must sit on and over nominal")
