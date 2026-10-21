r"""MHA-CH-06-TL-VN-52 oblique-trammel pivot bearing: McMaster 5972K41 6200-2RS.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture (cad/docs/subsystem-identities.md): two sealed 6200-2RS
deep-groove ball bearings per pivot block (``trammel.BEARINGS_PER_PIN``), one
block per rail, so four; inventory ``fixtures.trammel-6200-2rs``.  Each block
seats its pair in N6 bores from either face (``pivot_block.BORE_DIA``), the
pivot pin's k5 bearing section is pressed through both inner rings
(``pivot_pin.BEARING_DIA``), and the pin's narrow lower boss seats on the
upper inner ring.

Sources:

* SOURCED, https://www.mcmaster.com/5972K41/ read live 2026-10-17,
  rechecked live 2026-10-21: steel, Buna-N seals, ABEC 1, C3 radial
  clearance 0.008-0.023, DIN 625-1; bore 10 -0.008/0, OD 30 -0.009/0,
  width 9 -0.12/0.
* FROM THE CALCULATOR (imported): ``trammel.BEARING_BORE`` / ``BEARING_OD`` /
  ``BEARING_WIDTH`` (10 / 30 / 9) and ``BEARING_RADIAL_PLAY``. Purchased
  size deviations are owned by the pure SKU provider ``_mcmaster_5972k41``;
  the pin and block own their mating fits and interference ranges.
* VENDOR MODEL: rings, raceway grooves, 0.45 x 45 deg chamfers, seals and the
  seven balls are read off McMaster's STEP (``_mcmaster_5972k41``); the
  recipe is ``diagnostics/diag_build_5972K41.py``.  The vendor SLDPRT/STEP
  (downloaded 2026-10-17) is read for dimensions only and NOT replica-gated
  (user ruling 2026-10-17); the recipe's standalone run is catalog-only.
* RECEIVING: the VN-52 purchased drawing owns the catalogue OD/width limits.
  The OD acceptance names its press fit in the bearing bores of pivot block
  MHA-CH-06-TL-22. The purchased 9 mm nominal bearing width controls that
  block's two-bearing stack; this does not model the complete internal axial
  endplay or retention geometry.
  The drawing also requires an intact full-circumference cylindrical OD land
  including its axial mid-plane. Actual identity traceable to valid SKU-specific
  supplier dimensional authority can establish the catalogue size bands;
  redundant micrometer records are not required. Physical OD-land inspection
  before pressing remains necessary: vendor CAD is not its acceptance.
  Possession and qualification of an actual bearing are not established here.

Part frame: bearing axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right): a part-level reference axis, coaxial with the
``InnerRing`` bore and the ``OuterRing`` OD (no body owns it).  One side face
at y = 0 (the Top Plane: both rings' side faces), the other at y = WIDTH; the
model is symmetric about y = WIDTH/2, so either face may be mated.  Bodies:
``OuterRing``, ``InnerRing``, ``NearSeal``, ``FarSeal``, ``Ball1``..``Ball7``.
"""

from __future__ import annotations

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_pivot_pin_spec as pivot_pin
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

SKU = "5972K41"
INVENTORY_ID = "fixtures.trammel-6200-2rs"
# One pair per pivot block, one block per rail.
QUANTITY = trammel.BEARINGS_PER_PIN * fasteners.RAILS

BORE = trammel.BEARING_BORE
OD = trammel.BEARING_OD
WIDTH = trammel.BEARING_WIDTH
RADIAL_PLAY = trammel.BEARING_RADIAL_PLAY  # C3, unmounted (min, max)

# Joints: the pin's k5 section and the block's N6 seat, diametral
# interference (min, max), owned by their specs.
PIN_SECTION_DIA = pivot_pin.BEARING_DIA  # modelled at the k5 low limit
PIN_INTERFERENCE = (
    pivot_pin.BEARING_INTERFERENCE_MIN,
    pivot_pin.BEARING_INTERFERENCE_MAX,
)
SEAT_DIA = pivot_block.BORE_DIA  # modelled at the N6 low limit
SEAT_INTERFERENCE = (pivot_block.INTERFERENCE_MIN, pivot_block.INTERFERENCE_MAX)
for _name, (_low, _high) in (("pin", PIN_INTERFERENCE), ("seat", SEAT_INTERFERENCE)):
    if not 0.0 < _low <= _high:
        raise AssertionError(f"the bearing's {_name} joint is not a press")

