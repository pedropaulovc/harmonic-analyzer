"""Finite printed-setting design solve for the actual 48DP cone/drum forms.

This is a design calculation, not a native or loaded three-dimensional mesh
certificate.  The cutter module alone owns every curve.  The solver varies
printed blank OD (0.01 mm) and pitch tooth thickness (0.001 mm); thickness is
inverted on the actual translated cutter to obtain tool translation.  All
manufactured corners retain their source-owned grades.

Run from the repository with ``uv run python
cad/scripts/diagnostics/solve_stock_form_cones.py --six-pitch-thickness-mm 1.05
--out <outside-tree.json>``.
The JSON contains a row for every family member, including binding numerical
refusals.  A refused row is never a manufacturing setting.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _config
import cone_shaft_land_bands as lands
import dt_cone_gear_spec as cone_spec
import dt_cylinder_gear_spec as drum_spec
from stock_form_cutter import (
    CustomSixCutter, StockFormProfile, template_for_teeth,
    translation_for_pitch_tooth_thickness,
)


OD_STEP_MM = 0.01
THICKNESS_STEP_MM = 0.001
BLANK_DIA_BAND = (0.10, -0.10)
TOOTH_THICKNESS_BAND = (0.075, -0.075)
BACKLASH_ACCEPTANCE_MM = (0.06, 0.41)
FLOOR_AIR_MIN_MM = 0.02
DRUM_ROOT_AIR_MIN_MM = 0.10
GAP_FOOT_WIDTH_MIN_MM = 0.32
HANDOVER_JUMP_MAX_MM = 0.005
# The inherited low-count floors are historical planar screen comparisons.
# Main's release criterion is actual 3D union coverage >=1.1 for all20.
HISTORICAL_COVERAGE_MIN = {6: 0.65, 12: 0.80, 18: 0.90, 24: 0.98, 30: 1.03, 36: 1.08}
UNION_COVERAGE_MIN = 1.1


@dataclass(frozen=True)
class DesignInputs:
    diametral_pitch: float
    pressure_angle_deg: float
    drum_teeth: int
    drum_nominal: StockFormProfile
    drum_corners: tuple[StockFormProfile, ...]
    runout_mm: float
    opening_mm: float
    edge_slack_mm: float
    bore_band_upper_mm: float
    maximum_error_mm: float = 0.0002
    opening_components_mm: tuple[tuple[str,float], ...] = ()

    @property
    def module_mm(self) -> float:
        return 25.4 / self.diametral_pitch

    def centre_mm(self, teeth: int) -> float:
        return (teeth + self.drum_teeth) * self.module_mm / 2.0 + self.edge_slack_mm

    def maximum_bore_mm(self, teeth: int) -> float:
        nominal = cone_spec.bore_dia_mm(teeth)
        return math.ceil((nominal + self.bore_band_upper_mm) * 1000.0 - 1e-9) / 1000.0

    def web_min_mm(self, teeth: int) -> float:
        return 0.62 if teeth == 6 else 2.0

    def root_min_mm(self, teeth: int) -> float:
        web_root = self.maximum_bore_mm(teeth) / 2.0 + self.web_min_mm(teeth)
        return max(web_root, 1.173) if teeth == 6 else web_root

    def root_max_mm(self, teeth: int) -> float:
        return self.centre_mm(teeth) - self.runout_mm - max(
            gear.blank_radius_mm for gear in self.drum_corners
        ) - FLOOR_AIR_MIN_MM


def configured_inputs(*, maximum_error_mm: float = 0.0002) -> DesignInputs:
    """Read the retained fits and the fixed gear's actual process corner law."""
    bore_upper = cone_spec.BORE_DIA_BAND[0]
    cone_runout = (bore_upper - lands.GEAR_SEAT_BAND[1]) / 2.0
    drum_runout = drum_spec.BORE_DIAMETRAL_CLEARANCE_MM[1] / 2.0
    runout = cone_runout + drum_runout
    bearing_opening = float(max(_config.fit("shaft_in_bushing", "diametral_clearance_mm")))
    derived_opening = runout + bearing_opening
    booked_opening = float(_config.fit("cone_drum_oblique_mesh", "centre_opening_mm"))
    if not math.isfinite(booked_opening) or booked_opening < 0:
        raise ValueError("booked cone centre opening must be finite and nonnegative")
    return DesignInputs(
        float(_config.machine("gear_train", "diametral_pitch")),
        float(_config.machine("gear_train", "pressure_angle_deg")),
        int(_config.machine("gear_train", "cylinder_teeth")),
        drum_spec.STOCK_FORM,
        drum_spec.manufacturing_corner_profiles(),
        runout,
        max(booked_opening, derived_opening),
        float(_config.fit("cone_drum_oblique_mesh", "edge_slack_mm")),
        bore_upper,
        maximum_error_mm,
        opening_components_mm=(
            ("cone_gear_runout",cone_runout),("cylinder_gear_runout",drum_runout),
            ("bearing_opening",bearing_opening),("derived_total",derived_opening),
            ("booked_total",booked_opening),("selected_total",max(booked_opening,derived_opening))),
    )


def oblique_section_geometry(teeth: int) -> dict[str, Any]:
    """Exact affine horizontal sections of the actual inclined spur extrusion.

    At world Z=z the cone section is NOT an unchanged circular gear with a
    different centre distance. Local radial x stretches by sec(i), and its
    finite axial faces clip local radial x. This transform is supplied for a
    true 3D/affine-contact consumer; it does not invent a scalar TE bound.
    """
    import cone_line

    face = math.floor(cone_line.SEAT_PITCH * 1e4) / 1e4
    j = (120 - teeth) // 6
    station = (cone_line.SHAFT_T120_STATION + cone_line.GEAR_AXIS_SHIFT
               + (cone_line.CONE_FACE_STATION_REFERENCE - face) / 2.0
               + j * cone_line.SEAT_PITCH)
    centre = cone_line.cone_station(station)
    drum_z = cone_line.Z_DRUM0 + j * cone_line.Z_PITCH
    return {
        "cone_centre_mm": centre,
        "cone_axis": (cone_line.SIN_I, 0.0, cone_line.COS_I),
        "cone_radial_x": (cone_line.COS_I, 0.0, -cone_line.SIN_I),
        "cone_radial_y": (0.0, 1.0, 0.0),
        "cone_face_width_mm": face,
        "drum_axis_xy_mm": (cone_line.X_DRUM, cone_line.Y_DRIVE),
        "drum_z_limits_mm": (drum_z - cone_line.DRUM_FACE / 2.0,
                             drum_z + cone_line.DRUM_FACE / 2.0),
        "radial_x_stretch": 1.0 / cone_line.COS_I,
        "section_centre_x_slope_per_z": cone_line.SIN_I / cone_line.COS_I,
        "axial_clip": "local_axial=(world_z-cone_centre_z+sin_i*local_radial_x)/cos_i",
        "oblique_phase_bound_rad": None,
        "qualification": "oblique bound unavailable",
    }


def cutter_for_count(teeth: int, inputs: DesignInputs, *, six_pitch_thickness_mm: float) -> Any:
    if teeth != 6:
        return template_for_teeth(teeth, inputs.diametral_pitch, inputs.pressure_angle_deg)
    return CustomSixCutter(
        inputs.diametral_pitch,
        inputs.pressure_angle_deg,
        1.491,
        2.35,
        six_pitch_thickness_mm,
        "DT6-FORM1",
        "Main-approved N6 PA20 working involute; physical root MIN2.346 mm; finite ground form",
    )


def _bisect_increasing(function: Any, target: float, lower: float, upper: float) -> float:
    """Invert a proven increasing scalar function; no sampled-grid inference."""
    if function(lower) > target or function(upper) < target:
        raise ValueError(f"target {target:g} outside monotone bounds [{lower:g}, {upper:g}]")
    for _ in range(64):
        midpoint = (lower + upper) / 2.0
        if function(midpoint) < target:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def lattice_ticks(lower: float, upper: float, step: float) -> range:
    """Inclusive, outward-safe finite printed lattice; boundaries are not rounded in."""
    return range(math.ceil(lower / step - 1e-9), math.floor(upper / step + 1e-9) + 1)


def _profile_probe(teeth: int, cutter: Any, translation: float) -> StockFormProfile:
    """Construct a real supported blank for geometry/inspection queries."""
    root_x, root_y = cutter.root_point(cutter.root_half_angle_rad)
    root_max = max(abs(translation + cutter.root_radius_mm),
                   math.hypot(translation + root_x, root_y))
    tip_x, tip_y = cutter.flank_point(cutter.flank_parameter_max)
    support = math.hypot(translation + tip_x, tip_y)
    blank = min(teeth * cutter.module_mm / 2.0, (root_max + support) / 2.0)
    return StockFormProfile(teeth, cutter, blank, translation)


def _translation_domain(teeth: int, cutter: Any, inputs: DesignInputs) -> tuple[float, float]:
    """Bound all possible tool origins by physical root web and closing floor air.

    A reference root-arc endpoint has (x,y), and positive physical tool origins
    satisfy sqrt((T+x)^2+y^2)=R.  The opposite negative-origin branch would put
    the cutter through the axis and is rejected by the core.  Arc extrema are
    subsequently checked on every manufactured corner.
    """
    root = cutter.root_radius_mm
    x, y = cutter.root_point(cutter.root_half_angle_rad)
    minimum = inputs.root_min_mm(teeth)
    maximum = inputs.root_max_mm(teeth)
    if maximum < minimum or maximum < abs(y):
        return (1.0, 0.0)
    # Bisector and arc-endpoint radii are the only spur root extrema. Both
    # inequalities are required, including the negative-T case.
    lower = max(minimum - root, math.sqrt(max(0.0, minimum * minimum - y * y)) - x)
    upper = min(maximum - root, math.sqrt(maximum * maximum - y * y) - x)
    tip_x, tip_y = cutter.flank_point(cutter.flank_parameter_max)
    pitch = teeth * cutter.module_mm / 2.0
    # Pitch thickness is a declared inspection size. Its circle must lie on
    # finite working support; radial below-base continuation is not an
    # invented upper working flank.
    lower = max(lower, math.sqrt(max(0.0, pitch * pitch - tip_y * tip_y)) - tip_x)
    upper = min(upper, pitch - root)
    # Keep the physical root lobes from touching the next periodic gap.
    half_pitch = math.pi / teeth
    lower = max(lower, y / math.tan(half_pitch) - x + 1e-10)
    pitch_y = pitch * math.sin(half_pitch)
    if cutter.flank_point(cutter.flank_parameter_min)[1] <= pitch_y <= tip_y:
        u = _bisect_increasing(
            lambda parameter: cutter.flank_point(parameter)[1], pitch_y,
            cutter.flank_parameter_min, cutter.flank_parameter_max,
        )
        lower = max(lower, pitch * math.cos(half_pitch) - cutter.flank_point(u)[0] + 1e-10)
    return lower, upper


def _pitch_thickness(teeth: int, cutter: Any, translation: float) -> float:
    return _profile_probe(teeth, cutter, translation).pitch_tooth_thickness_mm


def thickness_translation(teeth: int, cutter: Any, thickness: float, domain: tuple[float, float]) -> float:
    """Use the sole core authority, then apply the physical manufacturing domain."""
    translation = translation_for_pitch_tooth_thickness(teeth, cutter, thickness)
    if not domain[0] - 1e-9 <= translation <= domain[1] + 1e-9:
        raise ValueError(f"actual thickness {thickness:g} lies outside root/web/floor domain")
    return translation


def _corner_translations(teeth: int, cutter: Any, thickness: float, domain: tuple[float, float]) -> tuple[float, float]:
    return tuple(
        thickness_translation(teeth, cutter, thickness + deviation, domain)
        for deviation in (TOOTH_THICKNESS_BAND[1], TOOTH_THICKNESS_BAND[0])
    )


def geometry_margins(teeth: int, outside_dia: float, translations: tuple[float, float], cutter: Any,
                     inputs: DesignInputs, *, probes: tuple[StockFormProfile, ...] | None = None) -> dict[str, float]:
    """Actual cutter gates before costly first-contact calculations."""
    if probes is None:
        probes = tuple(_profile_probe(teeth, cutter, translation) for translation in translations)
    maximum_tip = (outside_dia + BLANK_DIA_BAND[0]) / 2.0
    minimum_tip = (outside_dia + BLANK_DIA_BAND[1]) / 2.0
    root_min = min(profile.root_radius_min_mm for profile in probes)
    root_max = max(profile.root_radius_max_mm for profile in probes)
    support = min(profile.support_radius_max_mm for profile in probes)
    margins = {
        "finite_support_mm": support - maximum_tip,
        "blank_above_root_mm": minimum_tip - root_max,
        "web_mm": root_min - inputs.maximum_bore_mm(teeth) / 2.0 - inputs.web_min_mm(teeth),
        "floor_air_mm": inputs.root_max_mm(teeth) - root_max,
        "floor_window_dia_mm": 2.0 * (inputs.root_max_mm(teeth) - root_min) - 0.04,
        "drum_root_air_mm": inputs.centre_mm(teeth) - inputs.runout_mm - maximum_tip
        - max(gear.root_radius_max_mm for gear in inputs.drum_corners) - DRUM_ROOT_AIR_MIN_MM,
        "gap_foot_width_mm": 2.0 * abs(cutter.root_point(cutter.root_half_angle_rad)[1]) - GAP_FOOT_WIDTH_MIN_MM,
    }
    if teeth == 6:
        margins["special_root_min_mm"] = root_min - 1.173
    if margins["finite_support_mm"] >= 0.0 and margins["blank_above_root_mm"] > 0.0:
        try:
            land = min(
                StockFormProfile(teeth, cutter, maximum_tip, translation).tip_land_mm
                for translation in translations
            )
            margins["tip_land_mm"] = land - max(0.10, 0.25 * inputs.module_mm)
        except ValueError:
            # A failed finite periodic material constructor is a refusal,
            # never a substituted ideal-N land.
            margins["tip_land_mm"] = -math.inf
    else:
        margins["tip_land_mm"] = -math.inf
    return margins


def _od_domain(teeth: int, translations: tuple[float, float], cutter: Any, inputs: DesignInputs,
               *, probes: tuple[StockFormProfile, ...] | None = None) -> tuple[float, float]:
    if probes is None:
        probes = tuple(_profile_probe(teeth, cutter, translation) for translation in translations)
    lower = 2.0 * max(profile.root_radius_max_mm for profile in probes) - BLANK_DIA_BAND[1]
    upper = min(
        2.0 * min(profile.support_radius_max_mm for profile in probes) - BLANK_DIA_BAND[0],
        2.0 * (inputs.centre_mm(teeth) - inputs.runout_mm
               - max(gear.root_radius_max_mm for gear in inputs.drum_corners)
               - DRUM_ROOT_AIR_MIN_MM) - BLANK_DIA_BAND[0],
    )
    return lower, upper


def _report_values(report: Any) -> dict[str, Any]:
    """Preserve public engineering fields, excluding engine query closures."""
    names = (
        "coverage", "uncovered_phase_rad", "tight_backlash_mm", "loose_backlash_mm",
        "root_air_mm", "transmission_error_driver_rad", "transmission_error_driven_rad",
        "driver_phase_samples_rad", "driven_phase_samples_rad", "handover_kinds",
        "numerical_error_bounds", "is_conjugate", "handover_jump_mm", "phase_reserves_rad",
        "max_other_pair_normal_gap_mm", "contact_feature_ids", "root_interference",
        "qualified_continuous_contact", "handover_phase_reserves_rad",
        "smooth_flank_coverage", "smooth_flank_coverage_interval",
        "corner_inclusive_coverage", "corner_inclusive_coverage_interval",
        "corner_carrying_phase_fraction", "corner_normal_angle_range_rad",
        "support_uncertain_phase_rad", "unsupported_contact_samples_rad",
    )
    return {name: getattr(report, name) for name in names}


def mesh_margins(teeth: int, reports: list[Any]) -> dict[str, float]:
    """Pay absolute engine bounds in every named acceptance inequality."""
    required = UNION_COVERAGE_MIN
    margins: dict[str, float] = {}
    margins["coverage"] = min(
        report.coverage - report.numerical_error_bounds["coverage"] - required
        for report in reports
    )
    margins["tight_backlash_mm"] = min(
        report.tight_backlash_mm - report.numerical_error_bounds["backlash_mm"]
        - BACKLASH_ACCEPTANCE_MM[0] for report in reports
    )
    margins["loose_backlash_mm"] = min(
        BACKLASH_ACCEPTANCE_MM[1] - report.loose_backlash_mm
        - report.numerical_error_bounds["backlash_mm"] for report in reports
    )
    margins["handover_jump_mm"] = min(
        HANDOVER_JUMP_MAX_MM - report.handover_jump_mm
        - report.numerical_error_bounds["handover_jump_mm"] for report in reports
    )
    margins["uncovered_phase_rad"] = -max(
        report.uncovered_phase_rad + report.numerical_error_bounds["uncovered_phase_rad"]
        for report in reports
    )
    margins["carrying_contact"] = 0.0 if all(
        report.qualified_continuous_contact and not report.root_interference
        for report in reports
    ) else -1.0
    margins["finite_numerical_bounds"] = 0.0 if all(
        math.isfinite(value) and value >= 0.0
        for report in reports for value in report.numerical_error_bounds.values()
    ) else -1.0
    return margins

def strict_mesh_refusal(teeth: int, reports: list[Any]) -> bool:
    """Distinguish a proven violated gate from a numerical non-qualification."""
    coverage_min = UNION_COVERAGE_MIN
    for report in reports:
        error = report.numerical_error_bounds
        if (
            report.coverage + error["coverage"] < coverage_min
            or report.tight_backlash_mm + error["backlash_mm"] < BACKLASH_ACCEPTANCE_MM[0]
            or report.loose_backlash_mm - error["backlash_mm"] > BACKLASH_ACCEPTANCE_MM[1]
            or report.handover_jump_mm - error["handover_jump_mm"] > HANDOVER_JUMP_MAX_MM
            or report.uncovered_phase_rad - error["uncovered_phase_rad"] > 0.0
        ):
            return True
    return False



def home_clocking_rad(teeth: int) -> tuple[float, float]:
    """Physical home in the engine's canonical-gap mechanical datum.

    The cone native gap is pi/N from tooth/flat +X, and ROT_Y_INCLINE maps
    that +X into (cos(i),0,-sin(i)): the line of centres has azimuth zero.
    Cylinder rows are Ry(180) composed with Rz(-lock), so its local native
    gap pi/120 maps to world pi-lock-pi/120. The engine's driven mechanical
    datum is pi-pi/120+driven_clocking, hence driven_clocking=-lock.
    """
    return math.pi / teeth, -math.radians(float(
        _config.machine("gear_train", "cylinder_lock_phase_deg")
    ))


def first_phase_backlash_counterexample(
    teeth: int, outside_dia: float, translations: tuple[float, float],
    cutter: Any, inputs: DesignInputs,
) -> dict[str, Any] | None:
    """A strict actual phase-zero violation rejects a printed setting.

    This is a necessary prefilter, not a sampled no-gap/coverage certificate.
    A single counterexample suffices, whereas passing this query never
    substitutes for the whole-period enclosure below.
    """
    from stock_form_mesh import planar_contact

    for drum in inputs.drum_corners:
        for closing in (True, False):
            centre = inputs.centre_mm(teeth) + (-inputs.runout_mm if closing else inputs.opening_mm)
            translation = translations[1 if closing else 0]
            od_deviation = BLANK_DIA_BAND[0 if closing else 1]
            profile = StockFormProfile(teeth, cutter, (outside_dia + od_deviation) / 2.0, translation)
            driver_clocking, driven_clocking = home_clocking_rad(teeth)
            engine = planar_contact(profile, drum, centre,
                                    driver_clocking_rad=driver_clocking,
                                    driven_clocking_rad=driven_clocking,
                                    maximum_error_mm=inputs.maximum_error_mm)
            phase = engine.contact_at(0.0)
            error = 2.0 * phase.phase_error_rad * engine.operating_radius
            if not math.isfinite(error):
                continue
            bounds = (phase.backlash_mm - error, phase.backlash_mm + error)
            constraint = (
                "tight_backlash_mm" if closing and bounds[1] < BACKLASH_ACCEPTANCE_MM[0] else
                "loose_backlash_mm" if not closing and bounds[0] > BACKLASH_ACCEPTANCE_MM[1] else None
            )
            if constraint is not None:
                margin = (bounds[1] - BACKLASH_ACCEPTANCE_MM[0] if closing
                          else BACKLASH_ACCEPTANCE_MM[1] - bounds[0])
                return {
                    "constraint": constraint, "margin": margin,
                    "driver_phase_rad": 0.0, "backlash_interval_mm": bounds,
                    "cone_blank_dia_mm": 2.0 * profile.blank_radius_mm,
                    "cone_tool_translation_mm": translation,
                    "drum_blank_dia_mm": 2.0 * drum.blank_radius_mm,
                    "drum_tool_translation_mm": drum.radial_translation_mm,
                    "centre_mm": centre,
                }
    return None


def evaluate_setting(teeth: int, outside_dia: float, thickness: float, cutter: Any, inputs: DesignInputs, domain: tuple[float, float]) -> dict[str, Any]:
    from stock_form_mesh import MeshCertificationError, analyse_planar_mesh

    translations = _corner_translations(teeth, cutter, thickness, domain)
    margins = geometry_margins(teeth, outside_dia, translations, cutter, inputs)
    result: dict[str, Any] = {"outside_dia_mm": outside_dia, "pitch_thickness_mm": thickness,
        "tool_translation_mm": thickness_translation(teeth, cutter, thickness, domain),
        "tool_translation_limits_mm": translations, "geometry_margins": margins}
    if min(margins.values()) < 0.0:
        result["qualified"] = False
        result["binding_constraints"] = [name for name, margin in margins.items() if margin < 0.0]
        return result
    try:
        counterexample = first_phase_backlash_counterexample(
            teeth, outside_dia, translations, cutter, inputs,
        )
    except MeshCertificationError as error:
        result.update(qualified=False, binding_constraints=["numerical_contact_unresolved"],
                      mesh_margins={"numerical_contact_unresolved": -math.inf},
                      numerical_refusal=str(error), no_solution_certificate=False)
        return result
    if counterexample is not None:
        result.update(qualified=False, binding_constraints=[counterexample["constraint"]],
                      mesh_margins={counterexample["constraint"]: counterexample["margin"]},
                      actual_phase_counterexample=counterexample, no_solution_certificate=True)
        return result
    reports = []
    for od_deviation, translation, drum, centre in itertools.product(
        BLANK_DIA_BAND, translations, inputs.drum_corners,
        (inputs.centre_mm(teeth) - inputs.runout_mm, inputs.centre_mm(teeth) + inputs.opening_mm),
    ):
        profile = StockFormProfile(teeth, cutter, (outside_dia + od_deviation) / 2.0, translation)
        try:
            driver_clocking, driven_clocking = home_clocking_rad(teeth)
            reports.append(analyse_planar_mesh(profile, drum, centre,
                driver_clocking_rad=driver_clocking, driven_clocking_rad=driven_clocking,
                maximum_error_mm=inputs.maximum_error_mm))
        except MeshCertificationError as error:
            result.update(qualified=False, binding_constraints=["numerical_contact_unresolved"],
                          mesh_margins={"numerical_contact_unresolved": -math.inf},
                          numerical_refusal=str(error), no_solution_certificate=False)
            return result
    result["mesh_margins"] = mesh_margins(teeth, reports)
    all_margins = {**margins, **result["mesh_margins"]}
    result["binding_constraints"] = [
        name for name, margin in all_margins.items()
        if not math.isfinite(margin) or margin < 0.0
    ]
    result["qualified"] = not result["binding_constraints"]
    result["no_solution_certificate"] = not result["qualified"] and strict_mesh_refusal(teeth, reports)
    result["mesh_data"] = {
        "coverage_min": min(report.coverage - report.numerical_error_bounds["coverage"] for report in reports),
        "phase_reserve_rad": min(min(report.phase_reserves_rad, default=0.0) for report in reports),
        "handover_phase_reserve_rad": min(
            (min(reserves) for report in reports for reserves in report.handover_phase_reserves_rad),
            default=0.0,
        ),
        "noncarrying_gap_mm": max(
            report.max_other_pair_normal_gap_mm + report.numerical_error_bounds["normal_gap_mm"]
            for report in reports
        ),
        "te_bound_rad": max(
            max(abs(value) for value in report.transmission_error_driven_rad)
            + report.numerical_error_bounds["transmission_error_driven_rad"]
            for report in reports
        ),
    }
    if result["qualified"]:
        nominal = StockFormProfile(teeth, cutter, outside_dia / 2.0, result["tool_translation_mm"])
        driver_clocking, driven_clocking = home_clocking_rad(teeth)
        report = analyse_planar_mesh(nominal, inputs.drum_nominal, inputs.centre_mm(teeth),
            driver_clocking_rad=driver_clocking, driven_clocking_rad=driven_clocking,
            maximum_error_mm=inputs.maximum_error_mm)
        result["nominal_report"] = _report_values(report)
        result["nominal_plunge_mm"] = nominal.plunge_mm
        result["root_envelope_mm"] = (nominal.root_radius_min_mm, nominal.root_radius_max_mm)
        result["floor_min_dia_mm"] = math.floor(
            2.0 * min(_profile_probe(teeth, cutter, translation).root_radius_min_mm
                      for translation in translations) * 1000.0 + 1e-9
        ) / 1000.0
        result["floor_max_dia_mm"] = math.floor(inputs.root_max_mm(teeth) * 2000.0 + 1e-9) / 1000.0
    return result

def setting_score(margins: dict[str, float], module_mm: float) -> float:
    """Prefer manufacturing/contact reserve, not zero-valued proof flags."""
    flags = {"carrying_contact", "finite_numerical_bounds", "uncovered_phase_rad"}
    return min(value * module_mm if name == "coverage" else value
               for name, value in margins.items() if name not in flags)



def solve_count(teeth: int, inputs: DesignInputs, *, six_pitch_thickness_mm: float,
                analyse_mesh: bool = True) -> dict[str, Any]:
    """Exhaust the bounded, printed manufacturing lattice for one real cutter."""
    cutter = cutter_for_count(teeth, inputs, six_pitch_thickness_mm=six_pitch_thickness_mm)
    domain = _translation_domain(teeth, cutter, inputs)
    row: dict[str, Any] = {"teeth": teeth, "qualified": False, "selected": None,
        "production_qualified": False,
        "qualification_scope": "transverse_planar_diagnostic_only" if analyse_mesh else "dimensional_only",
        "planar_mesh_evaluated": analyse_mesh, "geometry_candidates": [],
        "translation_domain_mm": domain, "root_min_required_mm": inputs.root_min_mm(teeth),
        "root_max_air_mm": inputs.root_max_mm(teeth), "coverage_required": UNION_COVERAGE_MIN,
        "historical_coverage_floor": HISTORICAL_COVERAGE_MIN.get(teeth, 1.1),
        "cutter": {"reference_teeth": cutter.reference_teeth, "root_radius_mm": cutter.root_radius_mm,
                   "tip_radius_mm": cutter.tip_radius_mm,
                   "pitch_thickness_mm": six_pitch_thickness_mm
                   if teeth == 6 else math.pi * inputs.module_mm / 2.0,
                   "name": cutter.name, "source": cutter.source}}
    if domain[0] > domain[1]:
        row.update(binding_constraints=["root_web_support_vs_floor_air"], lattice_points=0,
                   finite_lattice_exhausted=True, no_solution_certificate=True)
        return row
    row["certificate_scope"] = (
        "transverse_planar_model_only" if analyse_mesh else "finite_manufacturing_geometry"
    )
    thickness_bounds = (
        _pitch_thickness(teeth, cutter, domain[0]) - TOOTH_THICKNESS_BAND[1],
        _pitch_thickness(teeth, cutter, domain[1]) - TOOTH_THICKNESS_BAND[0],
    )
    row["pitch_thickness_domain_mm"] = thickness_bounds
    row["actual_pitch_thickness_limits_mm"] = (
        thickness_bounds[0] + TOOTH_THICKNESS_BAND[1],
        thickness_bounds[1] + TOOTH_THICKNESS_BAND[0],
    )
    row["available_thickness_span_mm"] = (
        row["actual_pitch_thickness_limits_mm"][1] - row["actual_pitch_thickness_limits_mm"][0]
    )
    row["required_thickness_span_mm"] = TOOTH_THICKNESS_BAND[0] - TOOTH_THICKNESS_BAND[1]
    ticks = lattice_ticks(*thickness_bounds, THICKNESS_STEP_MM)
    if not ticks:
        row.update(binding_constraints=["thickness_band_vs_root_web_floor_air"], lattice_points=0,
                   thickness_domain_deficit_mm=thickness_bounds[0] - thickness_bounds[1],
                   finite_lattice_exhausted=True, no_solution_certificate=True)
        return row
    rejections: Counter[str] = Counter()
    points = 0
    actual = 0
    unresolved_settings = 0
    best = None
    nearest_refusal = None
    best_geometry = None
    thickness_sections = []
    for tick in ticks:
        thickness = round(tick * THICKNESS_STEP_MM, 3)
        translations = _corner_translations(teeth, cutter, thickness, domain)
        probes = tuple(_profile_probe(teeth, cutter, translation) for translation in translations)
        od_bounds = _od_domain(teeth, translations, cutter, inputs, probes=probes)
        thickness_sections.append({"pitch_thickness_mm": thickness,
            "translation_limits_mm": translations, "outside_dia_domain_mm": od_bounds})
        for od_tick in lattice_ticks(*od_bounds, OD_STEP_MM):
            points += 1
            outside_dia = round(od_tick * OD_STEP_MM, 2)
            margins = geometry_margins(teeth, outside_dia, translations, cutter, inputs, probes=probes)
            failed = [name for name, margin in margins.items() if margin < 0.0]
            if failed:
                rejections.update(failed)
                if not any(math.isfinite(value) and value < -1e-9 for value in margins.values()):
                    unresolved_settings += 1
                continue
            score_geometry = min(margins.values())
            if best_geometry is None or score_geometry > best_geometry[0]:
                best_geometry = (score_geometry, {"outside_dia_mm": outside_dia,
                    "pitch_thickness_mm": thickness, "geometry_margins": margins})
            nominal_translation = thickness_translation(teeth, cutter, thickness, domain)
            nominal = StockFormProfile(teeth, cutter, outside_dia / 2.0, nominal_translation)
            row["geometry_candidates"].append({
                "outside_dia_mm": outside_dia, "pitch_thickness_mm": thickness,
                "tool_translation_mm": nominal_translation,
                "translation_limits_mm": translations,
                "nominal_plunge_mm": nominal.plunge_mm,
                "root_envelope_mm": (nominal.root_radius_min_mm, nominal.root_radius_max_mm),
                "geometry_margins": margins,
            })
            if not analyse_mesh:
                continue
            actual += 1
            setting = evaluate_setting(teeth, outside_dia, thickness, cutter, inputs, domain)
            if setting["qualified"]:
                score = setting_score({**margins, **setting["mesh_margins"]}, inputs.module_mm)
                if best is None or score > best[0]:
                    best = (score, setting)
            else:
                rejections.update(setting["binding_constraints"])
                if not setting.get("no_solution_certificate", False):
                    unresolved_settings += 1
                score = setting_score({**margins, **setting["mesh_margins"]}, inputs.module_mm)
                if nearest_refusal is None or score > nearest_refusal[0]:
                    nearest_refusal = (score, setting)
    row.update(lattice_points=points, actual_mesh_settings=actual, rejection_counts=dict(rejections),
               thickness_sections=thickness_sections,
               nearest_refused_setting=None if nearest_refusal is None else nearest_refusal[1],
               best_geometry=None if best_geometry is None else best_geometry[1])
    if best is not None:
        row.update(qualified=True, selected=best[1], binding_constraints=[])
    elif not analyse_mesh and row["geometry_candidates"]:
        row["binding_constraints"] = ["planar_and_actual_3d_mesh_studies_pending"]
    else:
        row["binding_constraints"] = list(rejections) or ["printed_od_domain_empty"]
    row["finite_lattice_exhausted"] = True
    row["unresolved_setting_count"] = unresolved_settings
    row["no_solution_certificate"] = (
        not row["qualified"] and unresolved_settings == 0
        and (analyse_mesh or not row["geometry_candidates"])
    )
    return row


def solve_family(inputs: DesignInputs, *, six_pitch_thickness_mm: float,
                 analyse_mesh: bool = True) -> dict[str, Any]:
    teeth = range(6, int(_config.machine("gear_train", "fundamental_cone_teeth")) + 1, 6)
    rows = []
    for count in teeth:
        row = solve_count(count, inputs, six_pitch_thickness_mm=six_pitch_thickness_mm,
                          analyse_mesh=analyse_mesh)
        rows.append(row)
        print(json.dumps(json_evidence({
            "teeth": count, "qualified": row["qualified"],
            "binding_constraints": row["binding_constraints"],
            "no_solution_certificate": row["no_solution_certificate"],
            "translation_domain_mm": row["translation_domain_mm"],
            "pitch_thickness_domain_mm": row.get("pitch_thickness_domain_mm"),
            "selected": row["selected"],
        })), flush=True)
    for row in rows:
        row["centre_mm"] = inputs.centre_mm(row["teeth"])
        row["home_clocking_rad"] = home_clocking_rad(row["teeth"])
        row["oblique_section_geometry"] = oblique_section_geometry(row["teeth"])
    return {"qualified": all(row["qualified"] for row in rows), "rows": rows,
            "scope": ("actual finite forms, retained corners, deep transverse planar design"
                      if analyse_mesh else "actual finite forms, retained corners, geometry-only domains"),
            "inputs": {
                "diametral_pitch": inputs.diametral_pitch,
                "pressure_angle_deg": inputs.pressure_angle_deg,
                "runout_mm": inputs.runout_mm, "opening_mm": inputs.opening_mm,
                "opening_components_mm":dict(inputs.opening_components_mm),
                "opening_rule":"max(total booked opening, retained runout+bearing total); not their sum",
                "edge_slack_mm": inputs.edge_slack_mm,
                "bore_band_upper_mm": inputs.bore_band_upper_mm,
                "maximum_error_mm": inputs.maximum_error_mm,
                "drum_corners": [
                    {"blank_dia_mm": 2.0 * gear.blank_radius_mm,
                     "tool_translation_mm": gear.radial_translation_mm,
                     "plunge_mm": gear.plunge_mm,
                     "root_envelope_mm": (gear.root_radius_min_mm, gear.root_radius_max_mm)}
                    for gear in inputs.drum_corners
                ],
            },
            "manufacturing_lattice": {"outside_dia_step_mm": OD_STEP_MM, "pitch_thickness_step_mm": THICKNESS_STEP_MM}}


def json_evidence(value: Any) -> Any:
    """Write unbounded/uncertified results explicitly, never as a fake number."""
    if isinstance(value, dict):
        return {key: json_evidence(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_evidence(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if hasattr(value, "tolist"):
        return json_evidence(value.tolist())
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--six-pitch-thickness-mm", type=float, required=True)
    parser.add_argument("--maximum-error-mm", type=float, default=0.0002)
    parser.add_argument("--geometry-only", action="store_true",
                        help="calculate core-only domains and candidates; never qualify a mesh")
    args = parser.parse_args()
    output = args.out.resolve()
    repository = SCRIPTS.parents[1]
    if output.is_relative_to(repository):
        parser.error("design evidence must be written outside the repository")
    result = solve_family(configured_inputs(maximum_error_mm=args.maximum_error_mm),
                          six_pitch_thickness_mm=args.six_pitch_thickness_mm,
                          analyse_mesh=not args.geometry_only)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(json_evidence(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"qualified": result["qualified"], "rows": len(result["rows"]), "output": str(output)}))
    return 0 if result["qualified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
