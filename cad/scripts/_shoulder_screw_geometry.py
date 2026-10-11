"""Shared pure shoulder-screw geometry; separate SKU recipes limit cache blast radius."""

from __future__ import annotations

import math


def _slot_strip_area(r: float, w: float) -> float:
    """Plan area of a width-w strip across a radius-r circle (exact)."""
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


def _slotted_rim_chamfer_volume(r: float, chamfer: float, slot_w: float) -> float:
    """45-degree rim-chamfer volume remaining after a centered through-slot."""
    centroid_radius = r - chamfer / 3.0
    slot_half = slot_w / 2.0
    if not 0.0 < slot_half < centroid_radius:
        raise ValueError("slot must remove less than the full chamfer rim")
    full_volume = math.pi * chamfer**2 * centroid_radius
    missing_fraction = 2.0 * math.asin(slot_half / centroid_radius) / math.pi
    return full_volume * (1.0 - missing_fraction)


def _undercut_volume(major_r: float, land_r: float, land_w: float) -> float:
    """Vendor undercut: quarter-fillet + land + one 45-deg flank, revolved.

    Fillet band (height R = major_r - land_r, boundary radius
    ``major_r - sqrt(R^2 - t^2)``):  pi * ( (pi/2)*major_r*R^2 - (2/3)*R^3 ).
    """
    rise = major_r - land_r
    v_fillet = math.pi * ((math.pi / 2.0) * major_r * rise**2 - (2.0 / 3.0) * rise**3)
    v_land = math.pi * (major_r**2 - land_r**2) * land_w
    v_flank = math.pi * (major_r**2 * rise - (major_r**3 - land_r**3) / 3.0)
    return v_fillet + v_land + v_flank
