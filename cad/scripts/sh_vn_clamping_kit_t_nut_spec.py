r"""TNut envelope of the shared purchased kit (MHA-SH-VN-57).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_sh_vn_clamping_kit_hardware`` extrudes this member's ``PROFILE`` and
taps the thread; the jig assembly mates its ``ScrewAxis`` and foot.

The item is the T-nut of the Precision Matthews 52-piece clamping kit for
14 mm (9/16 in) T-slots (SKU 52PCCK-9/16-14mm, shop inventory
``fixtures.clamping-kit-pm-52pcck-14mm``). One sits in the PM-30MV table slot
under each of the four hold-down studs, its foot pulled up against the slot
undercut's roof, its neck in the slot throat.

datasheet-built: no vendor CAD obtained (Precision Matthews publishes no CAD
or component drawing for the kit, checked 2026-10-17 UTC).

Evidence (read 2026-10-17 UTC):

- Precision Matthews, https://www.precisionmatthews.com/products/52pcck-9-16-14mm :
  "14mm - 9/16" T Nut Size", "1/2"-13 Threaded Studs", hardened steel; no
  T-nut dimension is published. The product photograph shows the
  black-oxide T-nuts.
- Shop inventory ``fixtures.clamping-kit-pm-52pcck-14mm`` (the strap-pad-mill
  members): "T-nut estimates: 24 x 24 x 8 foot and 24 x 13 x 6 neck fit the
  manual p6 25/14 mm slot section" (PM-30MV manual p6: a 14 mm throat 14 deep
  over a 25 x 10 mm undercut); generic estimates, "verify kit dimensions".

Source of each number:

- SOURCED (the listing above): the 1/2-13 thread and the 14 mm slot size.
- C4 ESTIMATES (owned here; the jig assembly spec imports them):
  ``FOOT_HEIGHT`` 8 (the kit T-nut foot 24 x 24 x 8) and the slot's
  ``THROAT_DEPTH`` 14 (the PM-30MV throat depth to the undercut), which set
  the stud's bottom in the jig; verify on receipt.
- FROM C4 (imported): ``SLOT_WIDTH`` 14 is ``ch_rocker_arm_tl_oblique_trammel_spec.TSLOT_WIDTH``
  (a fit check only). ``THREAD`` "1/2-13" is
  ``ch_rocker_arm_tl_oblique_fasteners_spec.HOLD_DOWN_STUD_THREAD``.
- ESTIMATED (the inventory's generic T-nut estimates above; the kit
  publishes none; verify on receipt): ``FOOT_WIDTH`` 24 across the slot and
  ``LENGTH`` 24 along it, inside the 25 undercut; ``NECK_WIDTH`` 13, a
  running fit in the 14 throat; ``NECK_HEIGHT`` 6, so the nut stays below
  the table surface with the foot on the undercut's roof.
- The tapped hole is the 1/2-13 UNC-2B Hole Wizard thread, through all
  (tap drill ``TAP_DRILL_DIA`` from ``_hole_spec``).

Omitted: the edge chamfers and any face marking; the envelope is a plain
stepped block.

Part frame: the origin is on the thread axis at the foot's bottom face; +Y
runs up the thread axis, +X along the slot, Z across it. The section lies in
the Right Plane (Y, Z) and is extruded mid-plane along X. The thread axis is
Front Plane x Right Plane, published as ``ScrewAxis``.

Volume (closed form): foot ``LENGTH * FOOT_WIDTH * FOOT_HEIGHT`` plus neck
``LENGTH * NECK_WIDTH * NECK_HEIGHT``, less the tap-drill cylinder
``pi (TAP_DRILL_DIA / 2)^2 * (FOOT_HEIGHT + NECK_HEIGHT)``.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _hole_spec import HoleSpec, blind_cut_dia_mm

CONFIGURATION = "TNut"
SUPPLIER = "Precision Matthews"
SKU = "52PCCK-9/16-14mm"
SOURCE_URL = "https://www.precisionmatthews.com/products/52pcck-9-16-14mm"
MATERIAL = "Plain Carbon Steel"  # hardened steel (listing); library stand-in
QUANTITY = fasteners.HOLD_DOWN_STUD_COUNT  # one under each hold-down stud

# --- From C4 ----------------------------------------------------------------------
THREAD = fasteners.HOLD_DOWN_STUD_THREAD  # 1/2-13
FOOT_HEIGHT = 8.0  # C4 estimate (kit T-nut foot 24 x 24 x 8)
THROAT_DEPTH = 14.0  # C4 estimate: PM-30MV throat depth to the undercut
SLOT_WIDTH = trammel.TSLOT_WIDTH  # the PM-30MV slot throat; fit check only

# Preserve the installed jig's member description under the shared SKU.
BOM_DESCRIPTION = f"T-NUT, {SLOT_WIDTH:.0f} MM SLOT, {THREAD}"

# --- Estimated (verify on receipt) ---------------------------------------------
FOOT_WIDTH = 24.0  # across the slot
LENGTH = 24.0  # along the slot
NECK_WIDTH = 13.0
NECK_HEIGHT = 6.0
HEIGHT = FOOT_HEIGHT + NECK_HEIGHT

TAP_SPEC = HoleSpec("tapped", THREAD)  # UNC-2B, through all
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)

# Cross-section in the Right Plane, (z across the slot, y up), counter-clockwise
# from the foot's bottom corner at -z; symmetric about z = 0.
PROFILE: tuple[tuple[float, float], ...] = (
    (-FOOT_WIDTH / 2.0, 0.0),
    (FOOT_WIDTH / 2.0, 0.0),
    (FOOT_WIDTH / 2.0, FOOT_HEIGHT),
    (NECK_WIDTH / 2.0, FOOT_HEIGHT),
    (NECK_WIDTH / 2.0, HEIGHT),
    (-NECK_WIDTH / 2.0, HEIGHT),
    (-NECK_WIDTH / 2.0, FOOT_HEIGHT),
    (-FOOT_WIDTH / 2.0, FOOT_HEIGHT),
)

SECTION_AREA = FOOT_WIDTH * FOOT_HEIGHT + NECK_WIDTH * NECK_HEIGHT
TAP_VOLUME = math.pi * (TAP_DRILL_DIA / 2.0) ** 2 * HEIGHT
BLOCK_VOLUME = LENGTH * SECTION_AREA
VOLUME_MM3 = BLOCK_VOLUME - TAP_VOLUME

DRAWING_NOTES = (
    "FOOT UNDER THE SLOT UNDERCUT; VERIFY THE FIT IN THE TABLE SLOT ON RECEIPT."
)

# --- Import-time checks --------------------------------------------------------------
if not NECK_WIDTH < SLOT_WIDTH:
    raise ValueError("T-nut: the neck must pass the slot throat")
if not NECK_HEIGHT < THROAT_DEPTH:
    raise ValueError("T-nut: the neck must stay below the table surface")
if not TAP_DRILL_DIA < NECK_WIDTH:
    raise ValueError("T-nut: the thread must stay inside the neck")
