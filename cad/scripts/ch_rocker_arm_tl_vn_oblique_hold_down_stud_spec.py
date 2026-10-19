r"""Pure-data envelope of the purchased 1/2-13 x 3 in hold-down stud (MHA-CH-06-TL-VN-58).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_ch_rocker_arm_tl_vn_oblique_hold_down_stud`` revolves
``PROFILE`` and the jig assembly mates its ``ScrewAxis``.

The item is the 3 in threaded stud of the Precision Matthews 52-piece
clamping kit for 14 mm (9/16 in) T-slots (SKU 52PCCK-9/16-14mm, shop
inventory ``fixtures.clamping-kit-pm-52pcck-14mm``). Four hold the two
oblique-trammel base bars down to the PM-30MV table: each stud screws into a
kit T-nut in the table slot, passes the base bar's hold-down slot and takes a
kit flange nut on the bar's top face.

datasheet-built: no vendor CAD obtained (Precision Matthews publishes no CAD
or component drawing for the kit, checked 2026-10-17 UTC).

Evidence (read 2026-10-17 UTC):

- Precision Matthews, https://www.precisionmatthews.com/products/52pcck-9-16-14mm :
  "1/2"-13 Threaded Studs", "14mm - 9/16" T Nut Size", hardened steel; the
  stud lengths are not listed. The product photograph shows black-oxide
  studs of several lengths.

Source of each number:

- FROM C4 (imported, never retyped): ``THREAD`` "1/2-13" and ``LENGTH``
  3 in (76.2) from ``ch_rocker_arm_tl_oblique_fasteners_spec``
  (``HOLD_DOWN_STUD_THREAD`` / ``HOLD_DOWN_STUD_LENGTH_MM``; the kit's
  3 in stud); ``MAJOR_DIA`` 12.7 from
  ``ch_rocker_arm_tl_oblique_base_bar_spec.HOLD_DOWN_STUD_DIA``. SOURCED as
  a 1/2-13 stud by the kit listing above; the length is the stud C4 picked
  from the kit's assortment, UNVERIFIED against the delivered kit.
- ESTIMATED: ``END_CHAMFER`` 1.0 x 45 deg at each end, a little under the
  1/2-13 external thread depth ((12.70 - 10.30) / 2 = 1.2), the usual
  rolled-stud end chamfer; the listing gives none. It sets where the stud's
  full diameter starts, which is all that matters to the jig's fit.

Modelling: the external thread is a plain cylinder at the major diameter
(thread not modelled); one solid of revolution.

Part frame: the stud axis is +Y; y = 0 is the T-nut end (the end that
bottoms flush with the T-nut's foot), y = ``LENGTH`` the nut end. The axis is
Front Plane x Right Plane, published as ``ScrewAxis``.

Volume (closed form): the full cylinder ``pi R^2 L`` less a 45 deg end
chamfer at each end, each the ring between the cylinder and a frustum of
height ``c`` from radius ``R - c`` to ``R``:
``V = pi R^2 (L - 2c) + 2 (pi c / 3) (R^2 + R (R - c) + (R - c)^2)``.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners

SUPPLIER = "Precision Matthews"
SKU = "52PCCK-9/16-14mm"
SOURCE_URL = "https://www.precisionmatthews.com/products/52pcck-9-16-14mm"
MATERIAL = "Plain Carbon Steel"  # hardened steel (listing); library stand-in
QUANTITY = fasteners.HOLD_DOWN_STUD_COUNT  # near + far on each of the two bars

# --- From C4 ----------------------------------------------------------------------
THREAD = fasteners.HOLD_DOWN_STUD_THREAD  # 1/2-13
LENGTH = fasteners.HOLD_DOWN_STUD_LENGTH_MM  # the kit's 3 in stud
MAJOR_DIA = base_bar.HOLD_DOWN_STUD_DIA

# --- Estimated ---------------------------------------------------------------------
END_CHAMFER = 1.0  # ESTIMATED, 45 deg, both ends

RADIUS = MAJOR_DIA / 2.0

# (y, radius) envelope stations, T-nut end to nut end; revolved about +Y.
PROFILE: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (0.0, RADIUS - END_CHAMFER),
    (END_CHAMFER, RADIUS),
    (LENGTH - END_CHAMFER, RADIUS),
    (LENGTH, RADIUS - END_CHAMFER),
    (LENGTH, 0.0),
)

CHAMFER_FRUSTUM_VOLUME = (
    math.pi
    * END_CHAMFER
    / 3.0
    * (RADIUS**2 + RADIUS * (RADIUS - END_CHAMFER) + (RADIUS - END_CHAMFER) ** 2)
)
VOLUME_MM3 = (
    math.pi * RADIUS**2 * (LENGTH - 2.0 * END_CHAMFER) + 2.0 * CHAMFER_FRUSTUM_VOLUME
)

DRAWING_NOTES = "THREAD NOT MODELLED; BOTTOMS IN THE T-NUT, FLUSH WITH ITS FOOT."

if not 0.0 < END_CHAMFER < RADIUS:
    raise ValueError("hold-down stud: the end chamfer must be inside the radius")
