"""Cone-to-drum centres with the swing set at assembly on T120.

User ruling 2026-10-10. Assembly order (drive-train assembly steps and the
assembly drawing's CHECKS note): arbor-pedestal screws snug-loose, swing the
platform in on shims at T012 and T120 so the arbor aligns to the cone line,
tighten the pedestals, then set T120 with a radial tip-to-root feeler at the
standard clearance plus ``SET_ABOVE_STANDARD_MM`` and lock the cone-lock-knob.
The other cones follow the swing's rotation about the pivot: a T120 setting
error reaches cone i scaled by r = d_i / d_T120 (distances from the pivot),
and a pivot translation the set cannot see reaches it scaled by 1 - r.

Every centre is the running mean, std + set + TIR/2 (the T120 set is made
at its tightest phase), with symmetric half-range terms combined by RSS:

* running runout: the cone and the drum each ``TOOTH_RUNOUT_TIR_MM`` about
  their bores, so the centre swings +/- TIR about its mean;
* T120 set phase, feeler leaf step, T120 tip and drum root as cut: the T120
  setting error, through the swing (x r);
* pivot translation (x (1 - r)): the platform's reamed pivot bore on the
  stock shoulder, the base seat's position to the pedestal seats, the #10-24
  thread centring and the arbor's running float in the pedestal bores. The
  pedestal float itself is booked at zero: the shim alignment sets the drum
  line parallel to the cone line before the pedestals are tightened;
* seat float: the cone's and the drum's running clearance on their shafts,
  and the T120 pair's through the swing (x r).

T120 itself sees the running runout and its own setting error only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import cone_stations
import dt_arbor_pedestal_spec as pedestal
import dt_cone_gear_spec as cone
import dt_cone_swing_platform_pivot_spec as platform
import dt_cylinder_gear_shaft_spec as arbor
import vn_cone_pivot_screw_spec as pivot_screw
from cone_pitch import SEAT_PITCH
from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT
from dt_cylinder_gear_spec import BORE_DIAMETRAL_CLEARANCE_MM as DRUM_SEAT_CLEARANCE
from dt_cylinder_gear_spec import ROOT_ENVELOPE_DIA_MM, TEETH as DRUM_TEETH
from gear_seat_fit import GEAR_SEAT_CLEARANCE

SET_ABOVE_STANDARD_MM = float(_config.fit("cone_drum_oblique_mesh", "edge_slack_mm"))
SET_FEELER_READING_MM = float(_config.fit("cone_drum_oblique_mesh", "set_feeler_reading_mm"))
PIVOT_SEAT_POSITION_MM = float(_config.fit("cone_drum_oblique_mesh", "pivot_seat_position_mm"))
TOOTH_RUNOUT_TIR_MM = float(
    _config.fit("cone_drum_oblique_mesh", "tooth_cutting_runout_tir_mm")
)

# ASME B1.1 #10-24 UNC: 2B internal pitch diameter max 0.1672 in, 2A external
# min 0.1586 in; the screw can centre anywhere in that radial play.
PIVOT_THREAD_CENTRING_MM = (0.1672 - 0.1586) * 25.4 / 2.0
PIVOT_BORE_FLOAT_MM = (
    platform.PIVOT_HOLE_DIA + platform.PIVOT_HOLE_BAND[0]
    - (pivot_screw.SHOULDER_DIA + pivot_screw.SHOULDER_DIA_BAND[1])
) / 2.0
ARBOR_RUNNING_FLOAT_MM = (
    pedestal.BORE_DIA + pedestal.BORE_DIA_BAND[0] - (arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[1])
) / 2.0
PIVOT_TRANSLATION_MM = math.sqrt(
    PIVOT_BORE_FLOAT_MM**2 + PIVOT_SEAT_POSITION_MM**2
    + PIVOT_THREAD_CENTRING_MM**2 + ARBOR_RUNNING_FLOAT_MM**2
)
CONE_SEAT_FLOAT_MM = GEAR_SEAT_CLEARANCE[1] / 2.0
DRUM_SEAT_FLOAT_MM = DRUM_SEAT_CLEARANCE[1] / 2.0
T120_SET_MM = math.sqrt(
    (TOOTH_RUNOUT_TIR_MM / 2.0) ** 2 + SET_FEELER_READING_MM**2
    + ((cone.blank_dia_band(120)[0] - cone.blank_dia_band(120)[1]) / 2.0) ** 2
    + ((ROOT_ENVELOPE_DIA_MM[1] - ROOT_ENVELOPE_DIA_MM[0]) / 4.0) ** 2
)


def pivot_distance_mm(teeth: int) -> float:
    """Pivot to cone ``teeth``'s mesh station along the cone line."""
    if teeth % 6 or not 6 <= teeth <= 120:
        raise ValueError(f"no cone T{teeth:03d}")
    j = (120 - teeth) // 6
    return cone_stations.PIVOT_STATION - (
        cone_stations.SHAFT_T120_STATION + GEAR_AXIS_SHIFT + j * SEAT_PITCH
    )


def standard_centre_mm(teeth: int) -> float:
    return (teeth + DRUM_TEETH) * cone.MODULE_MM / 2.0


@dataclass(frozen=True)
class ConeCentre:
    teeth: int
    swing_ratio: float
    terms: tuple[tuple[str, float], ...]  # (name, half-range mm)

    @property
    def mean_mm(self) -> float:
        return standard_centre_mm(self.teeth) + SET_ABOVE_STANDARD_MM + TOOTH_RUNOUT_TIR_MM / 2.0

    @property
    def rss_half_range_mm(self) -> float:
        return math.sqrt(sum(value**2 for _name, value in self.terms))

    @property
    def rss_range_mm(self) -> tuple[float, float]:
        half = self.rss_half_range_mm
        return self.mean_mm - half, self.mean_mm + half


def cone_centre(teeth: int) -> ConeCentre:
    r = pivot_distance_mm(teeth) / pivot_distance_mm(120)
    terms = [("running runout", TOOTH_RUNOUT_TIR_MM), ("T120 set", r * T120_SET_MM)]
    if teeth != 120:
        terms += [
            ("pivot translation", (1.0 - r) * PIVOT_TRANSLATION_MM),
            ("cone seat float", CONE_SEAT_FLOAT_MM),
            ("drum seat float", DRUM_SEAT_FLOAT_MM),
            ("T120 seat float", r * math.hypot(CONE_SEAT_FLOAT_MM, DRUM_SEAT_FLOAT_MM)),
        ]
    return ConeCentre(teeth, r, tuple(terms))


def feeler_gap_mm(teeth: int) -> float:
    """The radial set reading at a cone: its printed tip to the drum's mid
    root, with the swing at the set centre (the T120 feeler, and the shim at
    T012 and T120 while the pedestals are snug-loose)."""
    return (standard_centre_mm(teeth) + SET_ABOVE_STANDARD_MM
            - cone.outside_dia_mm(teeth) / 2.0 - sum(ROOT_ENVELOPE_DIA_MM) / 4.0)
