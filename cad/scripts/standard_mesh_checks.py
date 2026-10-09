"""Closed-form standard mesh checks for the drive-train gear pairs.

Each mesh is checked as a standard involute pair in one plane, from spec
values only: the printed tip and thickness corners of each gear's actual
stock-form profile and the configured centre-distance range. The four
quantities are the usual AGMA/ISO hand checks:

* contact ratio at the nominal centre with nominal tips, and at the open
  corner (largest centre, smallest tips) as a reference figure;
* involute interference at the closing corner (largest tips, smallest
  centre): each mate's tip must stay outside the other gear's interference
  point, the form-cut equivalent of the generated-gear undercut/min-teeth rule;
* circular backlash on the operating pitch circles over the whole corner set;
* radial root clearance at the closing corner, tip MAX against root MAX.

A rotary stock cutter's flank is the involute of its range's reference count,
not of the cut count, so the involute here is the cut count's ideal one. That
is the standard shop approximation; the native SolidWorks assembly
interference/soundness gate is the geometric check of the real flanks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from stock_form_cutter import StockFormProfile


def involute(angle_rad: float) -> float:
    return math.tan(angle_rad) - angle_rad


# Generated (hobbed/shaped) full-depth 20 deg teeth undercut below this count.
# Rotary form cutting copies the cutter instead, so the governing check for
# the shop-cut gears is involute interference, evaluated per mesh below.
def generated_min_teeth(pressure_angle_deg: float, addendum_factor: float = 1.0) -> float:
    return 2.0 * addendum_factor / math.sin(math.radians(pressure_angle_deg)) ** 2


@dataclass(frozen=True)
class PlaneGear:
    """One gear's sizes in the check plane (mm)."""

    teeth: int
    pitch_radius: float
    tip_radius: float
    root_radius_max: float
    pitch_thickness: float  # circular, on ``pitch_radius``


@dataclass(frozen=True)
class MeshCheck:
    name: str
    contact_ratio_nominal: float
    contact_ratio_min: float
    interference_margin_min_mm: float
    backlash_min_mm: float
    backlash_max_mm: float
    root_clearance_min_mm: float

    def text(self) -> str:
        return (
            f"{self.name}: contact ratio {self.contact_ratio_nominal:.3f} nominal, "
            f"{self.contact_ratio_min:.3f} open corner (REF), "
            f"interference margin {self.interference_margin_min_mm:.3f} mm, "
            f"backlash {self.backlash_min_mm:.3f}..{self.backlash_max_mm:.3f} mm, "
            f"root clearance {self.root_clearance_min_mm:.3f} mm"
        )


def plane_gear(profile: StockFormProfile, module_mm: float, *, radius_growth: float = 0.0,
               thickness_scale: float = 1.0) -> PlaneGear:
    """A stock-form corner in the check plane.

    ``radius_growth`` moves every radius out by the same amount (a helical
    gear's virtual-gear growth in its normal section); ``thickness_scale``
    converts its transverse pitch thickness to that section (cos helix).
    """
    pitch = profile.teeth * module_mm / 2.0
    return PlaneGear(
        profile.teeth,
        pitch + radius_growth,
        profile.blank_radius_mm + radius_growth,
        profile.root_radius_max_mm + radius_growth,
        profile.pitch_tooth_thickness_mm * thickness_scale,
    )


def _operating_angle(a: PlaneGear, b: PlaneGear, centre: float, alpha: float) -> float:
    base = (a.pitch_radius + b.pitch_radius) * math.cos(alpha)
    if centre <= base:
        raise ValueError("centre distance is inside the base-circle sum")
    return math.acos(base / centre)


def contact_ratio(a: PlaneGear, b: PlaneGear, centre: float, alpha: float, module_mm: float) -> float:
    alpha_w = _operating_angle(a, b, centre, alpha)
    rba, rbb = a.pitch_radius * math.cos(alpha), b.pitch_radius * math.cos(alpha)
    approach = math.sqrt(a.tip_radius**2 - rba**2) + math.sqrt(b.tip_radius**2 - rbb**2)
    return (approach - centre * math.sin(alpha_w)) / (math.pi * module_mm * math.cos(alpha))


def interference_margin(a: PlaneGear, b: PlaneGear, centre: float, alpha: float) -> float:
    """Line-of-action reserve before either tip reaches the mate's base tangent."""
    alpha_w = _operating_angle(a, b, centre, alpha)
    line = centre * math.sin(alpha_w)
    rba, rbb = a.pitch_radius * math.cos(alpha), b.pitch_radius * math.cos(alpha)
    return min(line - math.sqrt(a.tip_radius**2 - rba**2),
               line - math.sqrt(b.tip_radius**2 - rbb**2))


def backlash(a: PlaneGear, b: PlaneGear, centre: float, alpha: float) -> float:
    """Circular backlash on the operating pitch circles (exact involute form)."""
    alpha_w = _operating_angle(a, b, centre, alpha)
    shift = involute(alpha_w) - involute(alpha)
    total = 0.0
    for gear in (a, b):
        rw = centre * gear.pitch_radius / (a.pitch_radius + b.pitch_radius)
        total += rw * (gear.pitch_thickness / gear.pitch_radius - 2.0 * shift)
    rw_a = centre * a.pitch_radius / (a.pitch_radius + b.pitch_radius)
    return 2.0 * math.pi * rw_a / a.teeth - total


def root_clearance(a: PlaneGear, b: PlaneGear, centre: float) -> float:
    return min(centre - a.tip_radius - b.root_radius_max,
               centre - b.tip_radius - a.root_radius_max)


def check_mesh(
    name: str,
    nominal: tuple[PlaneGear, PlaneGear, float],
    corners_a: Iterable[PlaneGear],
    corners_b: Iterable[PlaneGear],
    centre_range: tuple[float, float],
    pressure_angle_deg: float,
    module_mm: float,
) -> MeshCheck:
    """``nominal`` is (gear a, gear b, centre); every corner pair is taken at
    both centre extremes and the worst of each quantity is reported."""
    alpha = math.radians(pressure_angle_deg)
    corners_a, corners_b = tuple(corners_a), tuple(corners_b)
    lo, hi = centre_range
    if not 0.0 < lo <= nominal[2] <= hi:
        raise ValueError(f"{name}: centre range must be ordered, positive and hold the nominal")
    pairs = [(a, b) for a in corners_a for b in corners_b]
    return MeshCheck(
        name,
        contact_ratio(*nominal, alpha, module_mm),
        min(contact_ratio(a, b, hi, alpha, module_mm) for a, b in pairs),
        min(interference_margin(a, b, lo, alpha) for a, b in pairs),
        min(backlash(a, b, c, alpha) for a, b in pairs for c in centre_range),
        max(backlash(a, b, c, alpha) for a, b in pairs for c in centre_range),
        min(root_clearance(a, b, lo) for a, b in pairs),
    )
