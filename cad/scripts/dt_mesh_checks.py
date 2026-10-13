"""Standard closed-form checks for the cone/drum meshes.

Every value comes from the part specs and config:

* cone T006..T120 against the 120T drum: the centre is set at assembly on
  T120 and the other cones follow the swing (cone_set_stack books each
  cone's running mean and RSS half-range). Gated (test_standard_mesh_checks,
  user ruling 2026-10-10): nominal contact ratio >= 1.0 at the mean centre,
  and no binding and no interference at the RSS corner. The RSS contact
  ratio and the arithmetic worst-corner interference are reported only;
* the T006 named exception: its DT6-FORM1 relief must stay clear of every
  printed drum-tip corner's path over the RSS centre range
  (``t006_relief_clearance_mm``).

The 32T alignment check lives in alignment_mesh_check, the crossed 16T:64T
crank check with its stack in crank_mesh_stack.
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass, replace

import numpy as np
from scipy.spatial import cKDTree

import cone_set_stack
import dt_cone_gear_spec as cone
import dt_cylinder_gear_spec as drum
from standard_mesh_checks import (
    backlash,
    contact_ratio,
    interference_margin,
    involute,
    plane_gear,
    root_clearance,
)


@functools.cache
def _drum_corners():
    return tuple(plane_gear(p, drum.MODULE_MM) for p in drum.manufacturing_corner_profiles())


@dataclass(frozen=True)
class ConeMeshCheck:
    name: str
    centre: cone_set_stack.ConeCentre
    contact_ratio_nominal: float
    contact_ratio_rss: float  # REF
    backlash_nominal_mm: float
    backlash_rss_mm: float
    backlash_corner_min_mm: float  # every printed corner pair at the RSS-closed centre
    interference_margin_rss_mm: float
    root_clearance_rss_mm: float
    interference_margin_worst_mm: float  # REF: arithmetic worst corner, a fit-up note

    def text(self) -> str:
        lo, hi = self.centre.rss_range_mm
        return (
            f"{self.name}: centre {self.centre.mean_mm:.3f} mean, {lo:.3f}..{hi:.3f} RSS; "
            f"contact ratio {self.contact_ratio_nominal:.3f} nominal, "
            f"{self.contact_ratio_rss:.3f} RSS (REF); "
            f"backlash {self.backlash_nominal_mm:.3f} nominal, {self.backlash_rss_mm:.3f} RSS; "
            f"interference margin {self.interference_margin_rss_mm:.3f} RSS, "
            f"{self.interference_margin_worst_mm:.3f} worst corner (REF); "
            f"root clearance {self.root_clearance_rss_mm:.3f} RSS"
        )


@functools.cache
def cone_check(teeth: int) -> ConeMeshCheck:
    """The set-at-assembly cone mesh. Nominal: the printed profiles (cone at
    standard thickness and printed OD, drum at mid thickness) at the mean
    centre. RSS: each centre term, both tooth-thickness half-bands and both
    tip bands, by their sensitivity at nominal."""
    alpha, module = math.radians(cone.PRESSURE_ANGLE_DEG), cone.MODULE_MM
    centre = cone_set_stack.cone_centre(teeth)
    mean, half = centre.mean_mm, centre.rss_half_range_mm
    lo = mean - half
    gear = plane_gear(cone.stock_form_profile(teeth), module)
    gear_corners = [plane_gear(p, module) for p in cone.manufacturing_corner_profiles(teeth)]
    drum_corners = _drum_corners()
    drum_thickness = [c.pitch_thickness for c in drum_corners]
    mate = replace(plane_gear(drum.STOCK_FORM, drum.MODULE_MM),
                   pitch_thickness=(max(drum_thickness) + min(drum_thickness)) / 2.0)
    cr = contact_ratio(gear, mate, mean, alpha, module)
    cr_terms = (
        contact_ratio(gear, mate, mean + half, alpha, module) - cr,
        contact_ratio(replace(gear, tip_radius=min(c.tip_radius for c in gear_corners)),
                      mate, mean, alpha, module) - cr,
        contact_ratio(gear, replace(mate, tip_radius=min(c.tip_radius for c in drum_corners)),
                      mean, alpha, module) - cr,
    )
    gear_thickness = [c.pitch_thickness for c in gear_corners]
    nominal_backlash = backlash(gear, mate, mean, alpha)
    backlash_terms = (
        backlash(gear, mate, lo, alpha) - nominal_backlash,
        (max(gear_thickness) - min(gear_thickness)) / 2.0,
        (max(drum_thickness) - min(drum_thickness)) / 2.0,
    )
    pairs = [(a, b) for a in gear_corners for b in drum_corners]
    worst = mean - sum(value for _name, value in centre.terms)
    return ConeMeshCheck(
        f"cone T{teeth:03d}/drum",
        centre,
        cr,
        cr - math.sqrt(sum(d * d for d in cr_terms)),
        nominal_backlash,
        nominal_backlash - math.sqrt(sum(d * d for d in backlash_terms)),
        min(backlash(a, b, lo, alpha) for a, b in pairs),
        min(interference_margin(a, b, lo, alpha) for a, b in pairs),
        min(root_clearance(a, b, lo) for a, b in pairs),
        min(interference_margin(a, b, worst, alpha) for a, b in pairs),
    )


def cone_checks() -> tuple[ConeMeshCheck, ...]:
    return tuple(cone_check(teeth) for teeth in cone.CONFIGURATION_TEETH)


# Drum-tip path sampling for the T006 relief check. A 2.5e-5 rad step of the
# six-tooth gear moves a drum-tip point by under 2 um in the T006 frame; the
# path is then thinned to one sample per micrometre of travel (the step
# between kept samples is asserted below the clearance found), the 33 land
# points sit ~14 um apart on the 0.43 mm drum tip land, and the 4000-sample
# boundary chords sag far below 1 um.
_T006_ROTATION_STEP_RAD = 2.5e-5
_T006_PATH_SPACING_MM = 0.001
_T006_LAND_POINTS = 33
_T006_BOUNDARY_SAMPLES = 4000
_T006_QUERY_BOUND_MM = 0.05


def _drum_tip_lands_in_six_frame(centre: float, six, drum_corner, drum_profile, theta) -> np.ndarray:
    """Every drum tip-land point's path in the T006 frame: (land, step, xy).

    Conjugate involute kinematics with the T006 tooth's upper flank driving
    (backlash taken up on that side): at T006 rotation theta the line of
    action leaves its base circle at the operating angle aw, so the drum
    flank in contact starts at aw + pi - (C sin aw - (aw - k6 - theta) rb6)/rbD
    about the drum centre, the drum tooth's centre lies s/(2 r) + inv(alpha)
    further on, and its tip land spans +/- the drum's tip tooth half-angle.
    The lower-flank drive is the mirror image of this one.
    """
    alpha = math.radians(cone.PRESSURE_ANGLE_DEG)
    r6, rd = six.pitch_radius, drum_corner.pitch_radius
    rb6, rbd = r6 * math.cos(alpha), rd * math.cos(alpha)
    aw = math.acos((r6 + rd) * math.cos(alpha) / centre)
    k6 = math.pi / six.teeth - six.pitch_thickness / (2.0 * r6) - involute(alpha)
    tip_half = math.pi / drum_profile.teeth - drum_profile.tip_half_angle_rad
    start = aw + math.pi - (centre * math.sin(aw) - (aw - k6 - theta) * rb6) / rbd
    middle = start + drum_corner.pitch_thickness / (2.0 * rd) + involute(alpha)
    c, s = np.cos(-theta), np.sin(-theta)
    paths = []
    for offset in np.linspace(-tip_half, tip_half, _T006_LAND_POINTS):
        wx = centre + drum_corner.tip_radius * np.cos(middle + offset)
        wy = drum_corner.tip_radius * np.sin(middle + offset)
        paths.append(np.stack([c * wx - s * wy, s * wx + c * wy], axis=1))
    return np.stack(paths)


def _engagement_rotations(centre: float, six, drum_corner, drum_profile, blank_radius: float) -> np.ndarray:
    """Fine T006 rotations spanning every pass of a drum tip inside its blank.

    A coarse sweep over two full T006 turns finds where any tip-land point is
    within the blank; the fine window is that, widened by two coarse steps so
    both ends lie outside it again.
    """
    coarse_step = 1e-3
    coarse = np.arange(-2.0 * math.pi, 2.0 * math.pi, coarse_step)
    paths = _drum_tip_lands_in_six_frame(centre, six, drum_corner, drum_profile, coarse)
    inside = (np.hypot(paths[..., 0], paths[..., 1]) < blank_radius + 0.01).any(axis=0)
    if not inside.any() or inside[0] or inside[-1]:
        raise AssertionError("T006 drum-tip engagement is not bracketed by the coarse sweep")
    lo, hi = coarse[inside].min() - 2 * coarse_step, coarse[inside].max() + 2 * coarse_step
    return np.arange(lo, hi, _T006_ROTATION_STEP_RAD)


def _t006_material_boundary(profile) -> np.ndarray:
    """Dense samples of the whole T006 material boundary: six gaps and lands."""
    n = _T006_BOUNDARY_SAMPLES
    gap = [segment.point(i / n) for segment in profile.gap_segments()
           if segment.kind != "tip_arc" for i in range(n + 1)]
    pitch = profile.angular_pitch_rad
    land = [(profile.blank_radius_mm * math.cos(a), profile.blank_radius_mm * math.sin(a))
            for a in np.linspace(profile.tip_half_angle_rad, pitch - profile.tip_half_angle_rad, n)]
    one = np.array(gap + land)
    copies = []
    for j in range(profile.teeth):
        c, s = math.cos(j * pitch), math.sin(j * pitch)
        copies.append(np.stack([c * one[:, 0] - s * one[:, 1], s * one[:, 0] + c * one[:, 1]], axis=1))
    return np.concatenate(copies)


@functools.cache
def t006_relief_clearance_mm() -> float:
    """Least distance from any drum tip-land path to the T006 material.

    Every T006 thickness/OD corner against every printed drum corner at both
    centre limits. Each path starts outside the T006 blank, so it can enter
    material only by crossing the boundary; with every step shorter than the
    least distance found, no sample pair can straddle a crossing.
    """
    worst, longest_step = math.inf, 0.0
    for profile in cone.manufacturing_corner_profiles(6):
        six = plane_gear(profile, cone.MODULE_MM)
        tree = cKDTree(_t006_material_boundary(profile))
        for centre in cone_set_stack.cone_centre(6).rss_range_mm:
            for drum_profile, drum_corner in zip(drum.manufacturing_corner_profiles(), _drum_corners()):
                theta = _engagement_rotations(centre, six, drum_corner, drum_profile, profile.blank_radius_mm)
                paths = _drum_tip_lands_in_six_frame(centre, six, drum_corner, drum_profile, theta)
                radius = np.hypot(paths[..., 0], paths[..., 1])
                if not (radius[:, 0] > profile.blank_radius_mm).all() or not (radius[:, -1] > profile.blank_radius_mm).all():
                    raise AssertionError("T006 drum-tip paths must start and end outside the blank")
                for path, path_radius in zip(paths, radius):
                    # Keep one sample per micrometre of path: the fine
                    # rotation step dwells near the root, where the tip
                    # barely moves in this frame.
                    length = np.concatenate(([0.0], np.cumsum(np.hypot(*np.diff(path, axis=0).T))))
                    bins = np.floor(length / _T006_PATH_SPACING_MM)
                    keep = np.concatenate(([True], bins[1:] != bins[:-1]))
                    keep[-1] = True
                    kept, kept_radius = path[keep], path_radius[keep]
                    longest_step = max(longest_step, float(np.hypot(*np.diff(kept, axis=0).T).max()))
                    near = kept[kept_radius < profile.blank_radius_mm + 0.01]
                    if len(near):
                        # Only distances under the bound matter; farther
                        # points report inf and leave ``worst`` at the bound.
                        found = tree.query(near, distance_upper_bound=_T006_QUERY_BOUND_MM, workers=-1)[0]
                        worst = min(worst, _T006_QUERY_BOUND_MM, float(found.min()))
    if not longest_step < worst:
        raise AssertionError(f"T006 path step {longest_step:.6f} mm does not resolve clearance {worst:.6f} mm")
    return worst
