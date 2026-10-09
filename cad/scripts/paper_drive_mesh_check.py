"""Closed-form AGMA-style checks for the paper drive's two gear meshes.

Geometry comes only from the part specs: the 12T:120T 48DP PA20 reducer
(MHA-PD knob shaft on the MHA-PD-006 disc) and the 12T 32DP PA20 feed pinion
(MHA-PD-010) on the purchased 32DP PA20 rack (MHA-PD-005). Each mesh is
checked at its assembled (datum) state over every manufactured profile
corner the spec prints (tip band x translation band): contact ratio at the
minimum outside diameters, positive backlash at the tight extreme, root
clearance, and the interference (undercut) limit. Loaded service
displacement is not part of these gates (user decision 2026-10-09, as on
main); the native assembly's interference check covers the built pose.

Both pinions are stock #8 form cuts. The feed pinion's form is translated
rigidly outward by ``s`` along each gap bisector (the spec's RADIAL_SETTING);
translation keeps every flank normal, so against a straight rack it acts as
the untranslated involute with the rack and the tip both moved inward by the
radial part of that translation, s*cos(pi/N). The reducer pinion and the
disc are cut at standard depth, so they take the ordinary external-gear
formulas at the operating pressure angle.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import pd_platen_rack_spec as rack
import pd_rack_pinion_spec as disc
import pd_transgear_feed_pinion_spec as feed
import pd_transgear_knob_shaft_spec as knob

MM_PER_IN = 25.4
# AGMA's recommended minimum transverse contact ratio for spur gears.
CONTACT_RATIO_FLOOR = 1.2
# The rack mesh's existing physical gate (pd_paper_drive_assembly_steps).
RACK_ROOT_CLEARANCE_FLOOR_MM = 0.25
# AGMA fine-pitch standard clearance, 0.200/P + 0.002 in, at the reducer's
# 48DP: 0.00617 in.
REDUCER_ROOT_CLEARANCE_FLOOR_MM = (
    0.200 / disc.DIAMETRAL_PITCH + 0.002
) * MM_PER_IN


def _inv(angle: float) -> float:
    return math.tan(angle) - angle


@dataclass(frozen=True)
class MeshCheck:
    """One mesh's closed-form numbers at its worst manufactured corners."""

    label: str
    contact_ratio_min: float
    backlash_mm: tuple[float, float]
    root_clearance_min_mm: float
    root_clearance_floor_mm: float
    interference_margin_min_mm: float

    def failures(self) -> list[str]:
        problems = []
        if self.contact_ratio_min < CONTACT_RATIO_FLOOR:
            problems.append(
                f"contact ratio {self.contact_ratio_min:.3f} < {CONTACT_RATIO_FLOOR}"
            )
        if self.backlash_mm[0] <= 0.0:
            problems.append(f"backlash {self.backlash_mm[0]:.4f} mm at the tight extreme")
        if self.root_clearance_min_mm < self.root_clearance_floor_mm:
            problems.append(
                f"root clearance {self.root_clearance_min_mm:.3f} < "
                f"{self.root_clearance_floor_mm:.3f} mm"
            )
        if self.interference_margin_min_mm < 0.0:
            problems.append(
                f"tip reaches {-self.interference_margin_min_mm:.3f} mm past the "
                "interference point"
            )
        return problems

    def require(self) -> MeshCheck:
        problems = self.failures()
        if problems:
            raise ValueError(f"{self.label}: " + "; ".join(problems))
        return self

    @property
    def summary(self) -> str:
        low, high = self.backlash_mm
        return (
            f"{self.label}: CR {self.contact_ratio_min:.3f} min, backlash "
            f"{low:.3f}..{high:.3f}, root clearance {self.root_clearance_min_mm:.3f}, "
            f"interference margin {self.interference_margin_min_mm:.3f}"
        )


# --- Feed pinion on the purchased rack ------------------------------------------
_FEED_PA = math.radians(feed.PRESSURE_ANGLE_DEG)


def feed_rack_axis_distance_mm(backlash_mm: float, translation_mm: float) -> float:
    """Pinion axis to rack pitch line at a tooth-centred datum backlash.

    The spec's translated-form law (pd_transgear_feed_pinion_spec):
    b = 2(H - r)tan(a) - 2s*sin(a + pi/N)/cos(a).
    """
    return feed.PITCH_DIA / 2.0 + (
        backlash_mm
        + 2.0 * translation_mm * math.sin(_FEED_PA + math.pi / feed.TEETH)
        / math.cos(_FEED_PA)
    ) / (2.0 * math.tan(_FEED_PA))


def _rack_contact(profile, axis_distance_mm: float) -> tuple[float, float, float]:
    """(approach, recess, rack working depth) along the line of action, mm."""
    radius = feed.PITCH_DIA / 2.0
    base = radius * math.cos(_FEED_PA)
    shift = profile.radial_translation_mm * math.cos(math.pi / feed.TEETH)
    tip = profile.blank_radius_mm - shift
    depth = rack.ADDENDUM - (axis_distance_mm - shift - radius)
    approach = math.sqrt(tip**2 - base**2) - radius * math.sin(_FEED_PA)
    recess = min(depth / math.sin(_FEED_PA), radius * math.sin(_FEED_PA))
    return approach, recess, depth


def feed_rack_mesh(
    backlash_band_mm: tuple[float, float] = feed.RACK_BACKLASH_RANGE,
    extra_opening_mm: float = 0.0,
) -> MeshCheck:
    """The rack mesh over the datum backlash band and every printed corner.

    ``extra_opening_mm`` adds a set opening to the loose end (the latch
    pin's drop when it is set with travel left).
    """
    low, high = backlash_band_mm
    radius = feed.PITCH_DIA / 2.0
    pitch = math.pi * feed.MODULE_MM * math.cos(_FEED_PA)
    interference_depth = radius * math.sin(_FEED_PA) ** 2
    ratios, clearances, margins = [], [], []
    for profile in feed.manufactured_profiles():
        s = profile.radial_translation_mm
        tight = feed_rack_axis_distance_mm(low, s)
        loose = feed_rack_axis_distance_mm(high, s) + extra_opening_mm
        approach, recess, _depth = _rack_contact(profile, loose)
        ratios.append((approach + recess) / pitch)
        _approach, _recess, depth = _rack_contact(profile, tight)
        margins.append(interference_depth - depth)
        clearances.append(min(
            tight - rack.ADDENDUM - profile.root_radius_max_mm,
            tight + rack.DEDENDUM - profile.blank_radius_mm,
        ))
    return MeshCheck(
        "feed pinion on rack",
        min(ratios),
        (low, high),
        min(clearances),
        RACK_ROOT_CLEARANCE_FLOOR_MM,
        min(margins),
    )


def feed_rack_contact_half_width_mm(
    backlash_band_mm: tuple[float, float] = feed.RACK_BACKLASH_RANGE,
) -> float:
    """Largest rack-X reach of a contact point either side of the pitch point.

    The path of contact projected on the rack: the longer of approach and
    recess times cos(a), over every corner, at the tight end where the
    recess is longest. The feed reverses, so both sides take the larger.
    """
    reach = 0.0
    for profile in feed.manufactured_profiles():
        tight = feed_rack_axis_distance_mm(backlash_band_mm[0], profile.radial_translation_mm)
        approach, recess, _depth = _rack_contact(profile, tight)
        reach = max(reach, max(approach, recess) * math.cos(_FEED_PA))
    return reach


# --- 12T:120T reducer -------------------------------------------------------------
_REDUCER_PA = math.radians(disc.PRESSURE_ANGLE_DEG)


def _operating_angle(centre_distance_mm: float) -> float:
    base_sum = (knob.PITCH_DIA + disc.PITCH_DIA) / 2.0 * math.cos(_REDUCER_PA)
    return math.acos(base_sum / centre_distance_mm)


def reducer_contact_ratio(
    centre_distance_mm: float, pinion_tip_mm: float, disc_tip_mm: float
) -> float:
    angle = _operating_angle(centre_distance_mm)
    pinion_base = knob.PITCH_DIA / 2.0 * math.cos(_REDUCER_PA)
    disc_base = disc.PITCH_DIA / 2.0 * math.cos(_REDUCER_PA)
    path = (
        math.sqrt(pinion_tip_mm**2 - pinion_base**2)
        + math.sqrt(disc_tip_mm**2 - disc_base**2)
        - centre_distance_mm * math.sin(angle)
    )
    return path / (math.pi * disc.MODULE_MM * math.cos(_REDUCER_PA))


def reducer_backlash_mm(
    centre_distance_mm: float, pinion_thickness_mm: float, disc_thickness_mm: float
) -> float:
    """Circular backlash on the operating pitch circles."""
    angle = _operating_angle(centre_distance_mm)
    scale = math.cos(_REDUCER_PA) / math.cos(angle)
    pinion_r, disc_r = knob.PITCH_DIA / 2.0, disc.PITCH_DIA / 2.0
    involute = 2.0 * (_inv(_REDUCER_PA) - _inv(angle))
    pinion_w = pinion_r * scale * (pinion_thickness_mm / pinion_r + involute)
    disc_w = disc_r * scale * (disc_thickness_mm / disc_r + involute)
    return 2.0 * math.pi * pinion_r * scale / knob.TEETH - pinion_w - disc_w


def reducer_runout_shift_mm() -> float:
    """Worst centre change from tooth-space runout: each eccentricity is TIR/2."""
    return (knob.TOOTH_SPACE_RUNOUT_TIR_MM + disc.TOOTH_SPACE_RUNOUT_TIR_MM) / 2.0


def reducer_mesh(centre_distance_mm: float = disc.CENTRE_DISTANCE) -> MeshCheck:
    """The reducer at its assembled centre over every printed corner.

    Contact ratio at the nominal centre and minimum tips; backlash at the
    runout-shifted centres with the thickest and thinnest printed teeth;
    root clearance and the interference points at the tight centre with the
    largest tips.
    """
    pinions = knob.manufactured_profiles()
    discs = disc.manufactured_profiles()
    shift = reducer_runout_shift_mm()
    tight, loose = centre_distance_mm - shift, centre_distance_mm + shift
    pinion_tip_min = min(p.blank_radius_mm for p in pinions)
    disc_tip_min = min(p.blank_radius_mm for p in discs)
    pinion_tip_max = max(p.blank_radius_mm for p in pinions)
    disc_tip_max = max(p.blank_radius_mm for p in discs)
    pinion_t = [p.pitch_tooth_thickness_mm for p in pinions]
    disc_t = [p.pitch_tooth_thickness_mm for p in discs]
    backlash = (
        reducer_backlash_mm(tight, max(pinion_t), max(disc_t)),
        reducer_backlash_mm(loose, min(pinion_t), min(disc_t)),
    )
    clearance = min(
        tight - pinion_tip_max - max(p.root_radius_max_mm for p in discs),
        tight - disc_tip_max - max(p.root_radius_max_mm for p in pinions),
    )
    # The other gear's tip must meet the line of action outside this gear's
    # base-circle tangency point, so contact stays on the involute.
    angle = _operating_angle(tight)
    line = tight * math.sin(angle)
    pinion_base = knob.PITCH_DIA / 2.0 * math.cos(_REDUCER_PA)
    disc_base = disc.PITCH_DIA / 2.0 * math.cos(_REDUCER_PA)
    margin = min(
        line - math.sqrt(disc_tip_max**2 - disc_base**2),
        line - math.sqrt(pinion_tip_max**2 - pinion_base**2),
    )
    return MeshCheck(
        "12T:120T reducer",
        reducer_contact_ratio(centre_distance_mm, pinion_tip_min, disc_tip_min),
        backlash,
        clearance,
        REDUCER_ROOT_CLEARANCE_FLOOR_MM,
        margin,
    )
