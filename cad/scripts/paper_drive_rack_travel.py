"""Finite cut-end operating window for the purchased MHA-PD-005 rack.

The feed pinion's contact path, projected on the rack, comes from the
closed-form mesh check (paper_drive_mesh_check). This contract clips that
footprint to the actual finished ends, reserving an end-affected pitch at
EACH unknown cut phase. It is an assembly/traveler requirement, NOT a
hardware stop. Reset with the hanger disengaged; engaged feeding is
permitted only inside the window.

The operator datum is the actual rack's -X cut face. Measure toward +rack X
(also +machine X) to the feed sleeve's running stud axis. Increasing machine
platen X DECREASES that distance. FIRST_GAP_X and the nominal CAD photo pose
are never physical end datums. Required paper stroke is checked separately;
an insufficient finite window is an error, never a reduced paper function.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import _config
from _printed_tolerance import angular_band_deg, printed_deviations
import pd_platen_rack_spec as rack

OPERATING_LIMIT_PLACES = 2
OPERATING_DATUM_TEXT = "FROM ACTUAL RACK -X CUT END TO FEED STUD AXIS, TOWARD +X"
OPERATING_DIRECTION_TEXT = "+MACHINE X PLATEN FEED DECREASES THIS DISTANCE"


def _ordered_band(values: tuple[float, float], label: str) -> tuple[float, float]:
    if (
        len(values) != 2
        or not all(not isinstance(value, bool) and math.isfinite(value) for value in values)
        or values[0] > values[1]
    ):
        raise ValueError(f"{label} must be finite and ordered")
    return values


def cut_end_finish_reach_mm(
    *, cut_end_section_maxima_mm: tuple[float, float]
) -> float:
    """Bound each cut end's affected X strip from actual maximum Y/Z section.

    Both section maxima must include made-size and measurement uncertainty.
    Reference stock/composite dimensions cannot supply these upper bounds.
    The native title block controls both projected cut slopes and the
    permitted radius/chamfer; the sum pays the whole section, not one corner.
    """
    if len(cut_end_section_maxima_mm) != 2 or not all(
        not isinstance(value, bool) and math.isfinite(value) and value > 0.0
        for value in cut_end_section_maxima_mm
    ):
        raise ValueError("actual cut-section maxima must be finite positive Y height/Z depth")
    height, depth = cut_end_section_maxima_mm
    angle_deg = angular_band_deg()
    edge = _config.title_block("edge_break")
    radius = float(edge["radius_mm"])
    chamfer = float(edge["chamfer_max_mm"])
    if (
        not math.isfinite(angle_deg)
        or not 0.0 <= angle_deg < 90.0
        or not all(math.isfinite(value) and value >= 0.0 for value in (radius, chamfer))
    ):
        raise ValueError("source cut-end angular/edge controls need finite physical bounds")
    slope = math.tan(math.nextafter(math.radians(angle_deg), math.inf))
    reach = math.fsum((height * slope, depth * slope, max(radius, chamfer)))
    if not math.isfinite(reach):
        raise ValueError("actual cut-end finish enclosure is non-finite")
    return math.nextafter(reach, math.inf)


@dataclass(frozen=True)
class RackOperatingDomain:
    """The engaged-feed window from the rack's -X cut end to the stud axis."""

    axis_from_left_end_limits_mm: tuple[float, float]
    minimum_cut_length_mm: float
    contact_footprint_x_limits_mm: tuple[float, float]
    profilecentre_x_offset_band_mm: tuple[float, float]
    cut_end_reserve_mm: float
    cut_end_section_maxima_mm: tuple[float, float]
    cut_end_finish_reach_mm: float

    @property
    def available_stroke_mm(self) -> float:
        low, high = self.axis_from_left_end_limits_mm
        return high - low

    @property
    def operating_window_text(self) -> str:
        low, high = self.axis_from_left_end_limits_mm
        return (
            f"ENGAGED FEED: {low:.{OPERATING_LIMIT_PLACES}f} TO "
            f"{high:.{OPERATING_LIMIT_PLACES}f} MM; {OPERATING_DATUM_TEXT}."
        )

    def require_axis_distance_mm(self, distance_mm: float) -> None:
        """Refuse even a pointwise overrun; no numerical/phase fallback."""
        self.require_axis_distance_band_mm((distance_mm, distance_mm))

    def require_axis_distance_band_mm(self, distances_mm: tuple[float, float]) -> None:
        """Enclose the ENTIRE requested travel, not only the installed pose."""
        low, high = _ordered_band(distances_mm, "rack end-to-axis travel")
        allowed_low, allowed_high = self.axis_from_left_end_limits_mm
        if low < allowed_low or high > allowed_high:
            raise ValueError(
                f"finite rack cut-end overrun: {low:.6f}..{high:.6f} mm "
                f"outside required {allowed_low:.6f}..{allowed_high:.6f} mm"
            )

    def require_machine_travel_mm(
        self,
        *,
        rack_left_end_x_band_mm: tuple[float, float],
        running_axis_x_band_mm: tuple[float, float],
    ) -> None:
        """Check physical machine-X trajectories, including their uncertainties."""
        left_low, left_high = _ordered_band(
            rack_left_end_x_band_mm, "actual rack left-cut-end machine X"
        )
        axis_low, axis_high = _ordered_band(
            running_axis_x_band_mm, "actual feed running-axis machine X"
        )
        self.require_axis_distance_band_mm(
            (axis_low - left_high, axis_high - left_low)
        )

    def require_requested_stroke_mm(self, required_stroke_mm: float) -> None:
        """A requested media/function stroke cannot be silently shortened."""
        if (
            isinstance(required_stroke_mm, bool)
            or not math.isfinite(required_stroke_mm)
            or required_stroke_mm <= 0
        ):
            raise ValueError("required paper stroke must be finite and positive")
        if required_stroke_mm > self.available_stroke_mm:
            raise ValueError(
                f"required paper stroke {required_stroke_mm:.6f} mm exceeds "
                f"finite rack operating window {self.available_stroke_mm:.6f} mm"
            )

    def require_recording_paper_sweep_mm(
        self,
        *,
        paper_left_inset_band_mm: tuple[float, float],
        paper_width_band_mm: tuple[float, float],
        pen_x_from_running_axis_band_mm: tuple[float, float],
    ) -> tuple[float, float]:
        """Enclose the LOCATED full paper sweep at its actual accepted grades.

        Each band is an absolute physical requirement from the media/marker
        source. Neither nominal paper width nor a zero-tolerance pen location
        substitutes for the accepted family. Treating the three intervals
        independently is conservative if their source errors correlate.
        """
        inset_low, inset_high = _ordered_band(
            paper_left_inset_band_mm, "actual paper left inset"
        )
        width_low, width_high = _ordered_band(
            paper_width_band_mm, "actual required paper width"
        )
        pen_low, pen_high = _ordered_band(
            pen_x_from_running_axis_band_mm, "actual pen-to-running-axis X"
        )
        if inset_low < 0 or width_low <= 0:
            raise ValueError("actual paper inset must be nonnegative and width positive")
        self.require_requested_stroke_mm(width_high)
        distances = (
            inset_low - pen_high,
            inset_high + width_high - pen_low,
        )
        self.require_axis_distance_band_mm(distances)
        return distances


def rack_operating_domain_mm(
    *,
    contact_half_width_mm: float,
    lateral_deviation_mm: float,
    profilecentre_x_offset_band_mm: tuple[float, float],
    cut_end_section_maxima_mm: tuple[float, float],
) -> RackOperatingDomain:
    """Derive the one inward-rounded operating window.

    ``contact_half_width_mm`` is the furthest rack-X reach of a contact point
    from the pitch point (paper_drive_mesh_check.feed_rack_contact_half_width_mm).
    The required X band is physical profile centre minus the running stud
    axis. ``lateral_deviation_mm`` bounds the relative lateral offset between
    the physical constraint points. Actual upper Y-height/Z-depth bounds of
    the entire cut section are REQUIRED; no general tolerance is silently
    assigned to a reference dimension.

    The one-pitch exclusion is a conservative end-affected region, not a
    tooth-phase registration requirement. It exceeds the nominal root tooth
    width p/2 + 2*dedendum*tan(PA) for the sourced 32DP PA20 form. The
    shortest accepted finished rack, rather than its nominal 269.64 mm,
    supplies the far cut edge. Printed limits round INWARD and are the limits
    used by every checker as well as the assembly sheet/traveler.
    """
    for value, label in (
        (contact_half_width_mm, "contact half-width"),
        (lateral_deviation_mm, "relative lateral deviation"),
    ):
        if isinstance(value, bool) or not math.isfinite(value) or value < 0.0:
            raise ValueError(f"{label} must be finite and nonnegative")
    offset_low, offset_high = _ordered_band(
        profilecentre_x_offset_band_mm, "profile centre relative to running stud axis X"
    )
    finish_reach = cut_end_finish_reach_mm(
        cut_end_section_maxima_mm=cut_end_section_maxima_mm
    )
    if finish_reach > rack.PITCH:
        raise ValueError("actual cut-end finish exceeds the one-pitch end-affected strip")
    root_tooth_width = rack.PITCH / 2.0 + 2.0 * rack.DEDENDUM * rack.TAN_PA
    if not 0.0 < root_tooth_width < rack.PITCH:
        raise ValueError("source rack form exceeds the one-pitch end-affected strip")
    footprint = (-contact_half_width_mm, contact_half_width_mm)
    reserve = rack.PITCH + lateral_deviation_mm
    cut_lower, _cut_upper = printed_deviations(
        rack.CUT_LENGTH_MM, rack.DRAWING_PRECISION["BarProfile"]["Length"]
    )
    minimum_length = rack.CUT_LENGTH_MM + cut_lower
    contact_low, contact_high = footprint
    exact_low = reserve - offset_low - contact_low
    exact_high = minimum_length - reserve - offset_high - contact_high
    factor = 10**OPERATING_LIMIT_PLACES
    # nextafter charges outward arithmetic error before rounding inward.
    low = math.ceil(math.nextafter(exact_low * factor, math.inf)) / factor
    high = math.floor(math.nextafter(exact_high * factor, -math.inf)) / factor
    if low >= high:
        raise ValueError("finite rack material has no positive operating window")
    return RackOperatingDomain(
        (low, high), minimum_length, footprint,
        (offset_low, offset_high), reserve,
        (cut_end_section_maxima_mm[0], cut_end_section_maxima_mm[1]), finish_reach,
    )
