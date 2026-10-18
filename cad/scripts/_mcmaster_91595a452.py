r"""Pure 91595A452 dowel-pin dimensions; isolate this SKU's cache inputs.

McMaster 91595A452: 52100 alloy-steel dowel pin, 6 mm diameter, 20 mm long,
DIN 6325-m6 / ISO 8734, end shape "Round x Chamfer/Round" (product page
https://www.mcmaster.com/91595A452/, read live 2026-10-17).  The diameter is
the carrier's (``ch_rocker_arm_tl_oblique_carrier_spec.CL_DOWEL_DIA``),
imported; the length is the page's.

The end forms are read off McMaster's vendor model, downloaded 2026-10-17 from
the product page's CAD links (``91595A452_Dowel Pin.STEP``, SHA-256
``e9a95f5ef80acb723ff7825b2143e070cc86b2f69f07c3cc6b44caf55fd4bfd6``) and
measured with headless FreeCAD 1.1 on 2026-10-17 (dt-logs
``trammel-bought/vendor-cad/bd-freecad-harvest.json``; read for dimensions
only, not replica-gated, user ruling 2026-10-17): one solid, 536.845334
mm^3, 400.312896 mm^2, four surfaces (each split in two by the STEP export),
all on the Z axis with the pin's ends at z = +/-10:

* chamfered end (+z): a cone 15 deg to the axis from the Ø6 cylinder at
  z = 8.05 to Ø5.373 at z = 9.22 (1.17 long), then a spherical crown
  R5.016461 to the tip at z = 10 (0.78 high, not tangent to the cone);
* the Ø6 cylinder, z = -9.1 to 8.05;
* round end (-z): a spherical dome R5.45 from the cylinder at z = -9.1 to the
  tip at z = -10 (0.9 high, not tangent to the cylinder).

The pin has no flat end face, so ``_dowel_dimensions.DowelEnds`` (a flat-faced
chamfer and a tangent corner radius) cannot express it; the recipe draws its
own section.  The model is at nominal Ø6, as the vendor's is; the m6 band is
``CL_DOWEL_BAND``.
"""

from __future__ import annotations

import math

from ch_rocker_arm_tl_oblique_carrier_spec import CL_DOWEL_DIA as DIA

__all__ = [
    "CHAMFER_DEG",
    "CHAMFER_LEN",
    "CROWN_H",
    "DIA",
    "DOME_H",
    "LENGTH",
    "chamfer_rim_radius",
    "crown_radius",
    "dome_radius",
    "dowel_volume",
]

LENGTH = 20.0  # catalogue, tip to tip
# --- Vendor model (FreeCAD read of the STEP, 2026-10-17) --------------------
CHAMFER_DEG = 15.0  # the cone's half angle (0.2617994 rad in the STEP)
CHAMFER_LEN = 1.17  # axial, z 8.05..9.22
CROWN_H = 0.78  # the chamfered end's crown, z 9.22..10
DOME_H = 0.9  # the round end's dome, z -10..-9.1


def chamfer_rim_radius() -> float:
    """Radius where the chamfer cone meets the crown (2.686499 in the STEP)."""
    return DIA / 2.0 - CHAMFER_LEN * math.tan(math.radians(CHAMFER_DEG))


def crown_radius() -> float:
    """Sphere radius of the chamfered end's crown (5.016461 in the STEP)."""
    rim = chamfer_rim_radius()
    return (rim**2 + CROWN_H**2) / (2.0 * CROWN_H)


def dome_radius() -> float:
    """Sphere radius of the round end's dome (5.45 in the STEP)."""
    return ((DIA / 2.0) ** 2 + DOME_H**2) / (2.0 * DOME_H)


def _cap(rim: float, height: float) -> float:
    return math.pi * height * (3.0 * rim**2 + height**2) / 6.0


def dowel_volume() -> float:
    """Closed-form solid volume, mm^3: crown cap, chamfer frustum, cylinder
    and dome cap."""
    radius = DIA / 2.0
    rim = chamfer_rim_radius()
    frustum = math.pi / 3.0 * CHAMFER_LEN * (radius**2 + radius * rim + rim**2)
    cylinder = math.pi * radius**2 * (LENGTH - CROWN_H - CHAMFER_LEN - DOME_H)
    return _cap(rim, CROWN_H) + frustum + cylinder + _cap(radius, DOME_H)


if abs(crown_radius() - 5.016461) > 1e-6 or abs(dome_radius() - 5.45) > 1e-9:
    raise AssertionError("91595A452 end forms no longer reproduce the vendor STEP")
