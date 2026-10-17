r"""Pure-data envelope of the purchased 1/2-13 flange nut (MHA-CH-006-TL-40).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_oblique_flange_nut`` extrudes the flange and
hex and taps the thread; the jig assembly mates its ``ScrewAxis`` and flange
face.

The item is the flange nut of the Precision Matthews 52-piece clamping kit
for 14 mm (9/16 in) T-slots (SKU 52PCCK-9/16-14mm, shop inventory
``fixtures.clamping-kit-pm-52pcck-14mm``). One runs down each of the four
hold-down studs onto the oblique-trammel base bar's top face, its flange
bearing on the bar across the hold-down slot.

datasheet-built: no vendor CAD obtained (Precision Matthews publishes no CAD
or component drawing for the kit, checked 2026-10-17 UTC).

Evidence (read 2026-10-17 UTC):

- Precision Matthews, https://www.precisionmatthews.com/products/52pcck-9-16-14mm :
  "1/2"-13 Threaded Studs", "Studs, Nuts", hardened steel; no nut dimension
  is published. The product photograph shows six black-oxide flange nuts: a
  hex body on a round flange, the flange plain where it shows.
- TE-CO 41605, 1/2-13 flange nut (a TCMAI-class clamping-kit flange nut;
  not PM data), https://catalog.te-co.com/viewitems/flange-nuts-1/flange-nuts :
  OD 1.125 in, thickness 0.688 in, flange thickness 0.188 in, 0.875 in
  across flats.

Source of each number:

- SOURCED (the PM listing): the 1/2-13 thread, ``THREAD`` imported from
  ``ch_rocker_arm_tl_oblique_fasteners_spec.HOLD_DOWN_STUD_THREAD``.
- FROM C4, owned here (C4's own ESTIMATES; the jig assembly spec imports them):
  ``FLANGE_DIA`` 28 and ``HEIGHT`` 13, which the jig assembly stacks on the
  bar. UNVERIFIED: a TCMAI-class nut (TE-CO 41605 above) is 28.6 across the
  flange and 17.5 high, 4.5 higher than C4's estimate; the kit's own nut is
  to be measured on receipt.
- ESTIMATED from TE-CO 41605 (the kit's nut is unmeasured):
  ``ACROSS_FLATS`` 7/8 in (22.225), also the ASME B18.2.2 heavy-hex size for
  1/2 in; ``FLANGE_THICK`` 3/16 in (4.7625).
- The tapped hole is the 1/2-13 UNC-2B Hole Wizard thread, through all (tap
  drill ``TAP_DRILL_DIA`` from ``_hole_spec``).

Omitted: the hex's top chamfer, any flange serration and the thread
countersinks; the envelope is a plain hex on a plain flange.

Part frame: the nut axis is +Y; y = 0 is the flange's bearing face, the body
runs to y = ``HEIGHT``. Two hex corners lie on the Z axis, the flats facing
+/-X. The axis is Front Plane x Right Plane, published as ``ScrewAxis``.

Volume (closed form): flange disc ``pi (FLANGE_DIA / 2)^2 * FLANGE_THICK``
plus the hex prism above it ``(sqrt(3) / 2) * ACROSS_FLATS^2 *
(HEIGHT - FLANGE_THICK)``, less the tap-drill cylinder
``pi (TAP_DRILL_DIA / 2)^2 * HEIGHT``.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _hole_spec import HoleSpec, blind_cut_dia_mm
from ch_rocker_arm_tl_oblique_trammel_spec import INCH

SUPPLIER = "Precision Matthews"
SKU = "52PCCK-9/16-14mm"
SOURCE_URL = "https://www.precisionmatthews.com/products/52pcck-9-16-14mm"
COMPARISON_URL = "https://catalog.te-co.com/viewitems/flange-nuts-1/flange-nuts"
MATERIAL = "Plain Carbon Steel"  # hardened steel (listing); library stand-in
QUANTITY = fasteners.HOLD_DOWN_STUD_COUNT  # one on each hold-down stud

# --- C4 estimates ----------------------------------------------------------------
THREAD = fasteners.HOLD_DOWN_STUD_THREAD  # 1/2-13
FLANGE_DIA = 28.0  # C4 estimate
HEIGHT = 13.0  # C4 estimate; TCMAI-class is 17.5 (UNVERIFIED)

# --- Estimated (TE-CO 41605 proportions; verify on receipt) ----------------------
ACROSS_FLATS = 7.0 / 8.0 * INCH
FLANGE_THICK = 3.0 / 16.0 * INCH

TAP_SPEC = HoleSpec("tapped", THREAD)  # UNC-2B, through all
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)

HEX_CORNER_RADIUS = ACROSS_FLATS / math.sqrt(3.0)

# The hex's corners in the nut's cross-section, (x, z): from the +Z corner every
# 60 deg toward +X; two corners on the Z axis, the flats facing +/-X.
HEX_OUTLINE: tuple[tuple[float, float], ...] = tuple(
    (
        HEX_CORNER_RADIUS * math.sin(math.radians(angle)),
        HEX_CORNER_RADIUS * math.cos(math.radians(angle)),
    )
    for angle in range(0, 360, 60)
)


HEX_AREA = math.sqrt(3.0) / 2.0 * ACROSS_FLATS**2
FLANGE_VOLUME = math.pi * (FLANGE_DIA / 2.0) ** 2 * FLANGE_THICK
SOLID_VOLUME = FLANGE_VOLUME + HEX_AREA * (HEIGHT - FLANGE_THICK)
TAP_VOLUME = math.pi * (TAP_DRILL_DIA / 2.0) ** 2 * HEIGHT
VOLUME_MM3 = SOLID_VOLUME - TAP_VOLUME

DRAWING_NOTES = "FLANGE FACE DOWN ON THE BASE BAR."

# --- Import-time checks --------------------------------------------------------------
if not HEX_CORNER_RADIUS < FLANGE_DIA / 2.0:
    raise ValueError("flange nut: the hex corners must stay inside the flange")
if not FLANGE_THICK < HEIGHT:
    raise ValueError("flange nut: the flange must be thinner than the nut")
if not TAP_DRILL_DIA < ACROSS_FLATS:
    raise ValueError("flange nut: the thread must stay inside the hex")
