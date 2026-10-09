"""Reader-only synthetic contact receipts for isolated contract tests.

These records are NOT geometric qualification, diagnostic-engine output, a
manufacturing selection, or a native observation.  They exercise the real pure
receipt reader's arithmetic and source/physical-stratum bookkeeping.  Production
code must never import this module.  No calibration paths or file I/O belong here.
"""
from copy import deepcopy
import math

from stock_form_contact_certificate import (
    _bound_add, _bound_subtract, _bound_multiply, _frame_distance_scale_limit,
    _bound_divide,
    _periodic_source_evidence,
    _face_family_placements,
    _geometry_payment as _certificate_geometry_payment,
    _uniform_first_branch_names,
    _rectangle_remainder_nonempty,
)


_ORIGIN = "SYNTHETIC READER-ONLY FIXTURE; NOT GEOMETRIC QUALIFICATION"


def _point(value):
    return [value, value]


def _inflate(value, error):
    return [math.nextafter(value - error, -math.inf), math.nextafter(value + error, math.inf)]


def _profile_record(profile):
    return {
        "teeth": profile.teeth, "reference_teeth": profile.template.reference_teeth,
        "dp": profile.template.diametral_pitch, "pa_deg": profile.template.pressure_angle_deg,
        "blank_radius_mm": profile.blank_radius_mm,
        "radial_translation_mm": profile.radial_translation_mm,
        "helix_angle_deg": profile.helix_angle_deg,
    }


def _source(context):
    return {name: list(limits) for name, limits in context["domain"]["correlated_pose_parameters"]}


def _inventory(profile):
    segments = profile.external_boundary_segments()
    inventory = sorted(
        f"{tooth}:{segment.name}{suffix}"
        for tooth in range(profile.teeth) for segment in segments
        for suffix in ("", ":end_face:-1", ":end_face:+1")
    )
    roots = sorted(
        f"{tooth}:{segment.name}{suffix}"
        for tooth in range(profile.teeth) for segment in segments
        if segment.kind not in ("flank", "radial", "tip_arc")
        for suffix in ("", ":end_face:-1", ":end_face:+1")
    )
    return inventory, roots, sorted(set(roots) | {name for name in inventory if ":end_face:" in name})


def _segment(profile, side):
    return next(segment for segment in profile.external_boundary_segments()
                if segment.kind in ("flank", "radial") and segment._side == side)


def _stratum(segment, tooth):
    return {
        "segment": segment.name, "kind": segment.kind, "tooth": tooth,
        "t_fixed": None, "z_fixed": None, "axial_cap_source": "face",
        "radial_cap_radius_mm": None, "radial_cap_source": None,
        "incident_segments": [], "implicit_tip": False,
    }


def _driver_station(context):
    lo, hi = context["placement"]["driver_face_mm"]
    shoulder = context["placement"]["driver_shoulder_z_mm"]
    if shoulder is not None:
        hi = min(hi, shoulder)
    return lo + (hi - lo) * .25, lo + (hi - lo) * .75


def _station(context, phase):
    lo, hi = context["placement"]["driven_face_mm"]
    pitch = context["driver"].angular_pitch_rad
    u = (phase / pitch) % 1.0
    fraction = .04 + .92 * (3 * u if u <= 1 / 3 else 2 - 3 * u if u <= 2 / 3 else 0)
    return lo + (hi - lo) * fraction


def _branch(context, phase, family, rank, sense):
    driver, driven = context["driver"], context["driven"]
    source = _source(context)
    middle = phase[0] / 2 + phase[1] / 2
    source_middle = {name: limits[0] / 2 + limits[1] / 2 for name, limits in source.items()}
    ratio = driver.teeth / driven.teeth
    pitch = driver.angular_pitch_rad
    gap = .0001 / driven.pitch_radius_mm
    slope = (1 if family == 0 else -1) * sense * gap / pitch
    derivatives = [_point(-ratio + slope)]
    for name in source:
        derivatives.append(_point(-ratio + slope if name == "driver_clock_rad" else -1.0 if name == "driven_clock_rad" else 0.0))
    clock = source.get("driven_clock_rad", [0.0, 0.0])
    driver_clock = source.get("driver_clock_rad", [0.0, 0.0])
    angle_centre = (-ratio + slope) * (middle + source_middle.get("driver_clock_rad", 0.0)) - slope * pitch / 2 + sense * (.1 / driven.pitch_radius_mm + rank * gap)
    angle_error = context["geometry_error_mm"]
    spread = abs(-ratio + slope) * ((phase[1] - phase[0]) / 2 + (driver_clock[1] - driver_clock[0]) / 2)
    material = _inflate(angle_centre, spread + angle_error)
    beta = list(_bound_subtract(material, clock))
    driver_segment, driven_segment = _segment(driver, -sense), _segment(driven, sense)
    driver_tooth = 0 if family == 0 else driver.teeth - 1
    driven_tooth = rank if family == 0 else (rank + 1) % driven.teeth
    chart = f"synthetic:{sense}:{family}:{rank}"
    driver_z = _driver_station(context)
    driven_z_values = (_station(context, phase[0]), _station(context, phase[1]))
    if phase[0] == phase[1]:
        z = _station(context, middle)
        driven_z = _inflate(z, min((context["placement"]["driven_face_mm"][1] - context["placement"]["driven_face_mm"][0]) * .00001, angle_error))
    else:
        width = context["placement"]["driven_face_mm"][1] - context["placement"]["driven_face_mm"][0]
        driven_z = [min(driven_z_values) - width * .001, max(driven_z_values) + width * .001]
    box = [[.45, .55], list(driver_z), [.45, .55], driven_z, material]
    unknown = [[0.0, 1.0], list(context["placement"]["driver_face_mm"]),
               [0.0, 1.0], list(context["placement"]["driven_face_mm"]),
               [-context["angle_extent"], context["angle_extent"]]]
    centre_box = [_inflate(.5, angle_error), _inflate(sum(driver_z) / 2, angle_error),
                  _inflate(.5, angle_error), _inflate(_station(context, middle), angle_error),
                  _inflate(angle_centre, angle_error)]
    centre_clock = source_middle.get("driven_clock_rad", 0.0)
    margins = {"opposed_nonzero_normal_cones": [1.0, 1.0], "normal_cross_pivot_nonzero": [1.0, 1.0]}
    for body, t_index, z_index in (("driver", 0, 1), ("driven", 2, 3)):
        face = context["placement"][f"{body}_face_mm"]
        margins.update({
            f"{body}_finite_t_lower": _point(box[t_index][0]),
            f"{body}_finite_t_upper": _point(1 - box[t_index][1]),
            f"{body}_finite_z_lower": _point(box[z_index][0] - face[0]),
            f"{body}_finite_z_upper": _point(face[1] - box[z_index][1]),
            f"{body}_normal_cone_weight_0": [1.0, 1.0],
        })
    if context["placement"]["driver_shoulder_z_mm"] is not None:
        margins["driver_retained_unturned_or_turned_material"] = _point(context["placement"]["driver_shoulder_z_mm"] - box[1][1])
    return {
        "proof_schema": "finite-stock-common-normal-continuation/1", "status": "PROVED",
        "native_certificate": False, "reason": _ORIGIN, "chart": chart,
        "driven_tooth": driven_tooth, "phase_cell_rad": list(phase), "same_source_pose": source,
        "parameter_names": ["driver_phase_rad", *source], "contraction_upper": .25,
        "driven_phase_parameter_derivatives": derivatives, "unknown_domain": unknown,
        "root_box": box, "driven_surface_root_box": [box[2], box[3]],
        "center_root_box": centre_box, "center_contraction_upper": .25,
        "center_phase_cell_rad": _point(middle),
        "center_source_pose": {name: _point(value) for name, value in source_middle.items()},
        "driven_phase_enclosure_rad": beta,
        "driven_material_phase_enclosure_rad": material,
        "center_driven_phase_enclosure_rad": list(_bound_subtract(centre_box[4], _point(centre_clock))),
        "root_free_component_rad": [-context["angle_extent"], context["angle_extent"]],
        "unknown_angle_coordinate": "driven_material", "root_component_coordinate": "driven_material",
        "driven_angle_unknown_index": 4, "driven_station_unknown_index": 3,
        "physical_strata": {"driver": _stratum(driver_segment, driver_tooth), "driven": _stratum(driven_segment, driven_tooth)},
        "support_margins": margins, "required_support_margin_names": sorted(margins),
        "common_normal_moments": [[-1.0, -1.0], [1.0, 1.0]],
        "normal_cone_weights": [[[1.0, 1.0]], [[1.0, 1.0]]],
        "normal_cone_generators_world": [
            [[[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
            [[[0.0, 0.0], [-1.0, -1.0], [0.0, 0.0]]],
        ],
        "geometry_error_bound_mm": angle_error,
        "active_set_contract": "fixed physical stratum; unresolved zero-weight mode transitions refuse",
    }


def _root(context, phase, *, angle_coordinate="driven_material", approach=None,
          material_scope="driver_root_material", additional_geometry_error_mm=None):
    context = {**context, "placement": context["material_placement"]}
    pitch = context["driver"].angular_pitch_rad
    scale = _frame_distance_scale_limit(context["placement"]["driver_frame"]) / 2
    driver_floor = context["domain"]["root_air_requirements_mm"]["driver"]
    raw_air = max(.5, driver_floor / scale * 2)
    component = list(approach) if approach is not None else [-context["angle_extent"], context["angle_extent"]]
    arc = _periodicity(context)[0] if additional_geometry_error_mm is None else additional_geometry_error_mm
    return {
        "status": "PROVED", "native_certificate": False, "fixture_origin": _ORIGIN,
        "phase_cell_rad": list(phase), "same_source_pose": _source(context),
        "angle_coordinate": angle_coordinate, "driven_angle_domain_rad": component,
        "root_free_driven_components_rad": [component],
        "physical_driver_teeth": list(range(context["driver"].teeth)),
        "physical_driven_teeth": list(range(context["driven"].teeth)),
        "physical_patch_inventory": context["inventory"],
        "material_scope": material_scope,
        "physical_required_root_air_mm": driver_floor,
        "driver_local_to_world_distance_lower": scale,
        "physical_root_air_lower_bound_mm": min(raw_air * scale / 2, .25),
        "additional_geometry_error_mm": arc,
        "inverse_offset_free_components_rad": [[-pitch * .4, pitch * .4]],
        "root_sweep": {
            "status": "resolved", "root_is_carrying": False, "native_solid_certificate": False,
            "material_scope": material_scope,
            "containment_proof": (
                "driver-root axis point outside paid driven finite cylinder"
                if material_scope == "driver_root_material"
                else "driver-material axis point outside paid driven finite cylinder"
            ),
            "physical_driver_teeth": list(range(context["driver"].teeth)),
            "physical_driven_teeth": list(range(context["driven"].teeth)),
            "physical_patch_inventory": deepcopy(context["inventory"]),
            "offset_domain_rad": [-pitch / 2, pitch / 2],
            "free_outer": [[-pitch / 2, pitch / 2]], "free_inner": [[-pitch * .45, pitch * .45]],
            "required_root_air_mm": driver_floor / scale, "root_air_lower_bound_mm": raw_air,
            "geometric_uncertainty_mm": context["geometry_error_mm"] + arc / scale,
        },
    }


def _directed_root(context, phase, approach):
    """Mirror the real directed-material protocol, never its geometry proof."""
    context = {**context, "placement": context["material_placement"]}
    driver, driven, placement = context["driver"], context["driven"], context["placement"]
    required = context["domain"]["root_air_requirements_mm"]["driven"]
    result = {
        "proof_schema": "finite-stock-directed-root-material/1", "status": "PROVED",
        "physical_no_solution": False, "native_certificate": False, "fixture_origin": _ORIGIN,
        "root_owner": "driven", "other_material_owner": "driver",
        "phase_cell_rad": list(phase), "same_source_pose": _source(context),
        "angle_coordinate": "driven_material", "approach_driven_phase_rad": list(approach),
        "required_root_air_mm": required, "source_driver_profile": _profile_record(driver),
        "source_driven_profile": _profile_record(driven), "source_placement": deepcopy(placement),
    }
    query = dict(context)
    query["domain"] = deepcopy(context["domain"])
    query["domain"]["root_air_requirements_mm"]["driver"] = required
    if driven.helix_angle_deg == 0:
        relabel = {
            name: ("driven_" + name[7:] if name.startswith("driver_") else "driver_" + name[7:])
            for name in _source(context) if name != "driven_clock_rad"
        }
        query_source = {relabel[name]: list(value) for name, value in _source(context).items() if name in relabel}
        reverse_placement = {
            **{f"{body}_{suffix}": deepcopy(placement[f"{other}_{suffix}"])
               for body, other in (("driver", "driven"), ("driven", "driver"))
               for suffix in ("origin_mm", "frame", "face_mm")},
            "driver_clocking_rad": 0.0, "driven_clocking_rad": 0.0,
            "driver_shoulder_z_mm": None, "driver_turned_radius_mm": None,
        }
        query.update(driver=driven, driven=driver, placement=reverse_placement)
        query["inventory"], query["roots"], query["noncarrying"] = _inventory(driver)
        query["material_placement"] = reverse_placement
        query["domain"]["correlated_pose_parameters"] = list(query_source.items())
        query_phase = list(approach)
        query_angle = list(_bound_add(phase, _point(placement["driver_clocking_rad"])))
        result.update(
            method="reversed_actual_straight_root_sweep",
            query_driver_profile=_profile_record(driven), query_driven_profile=_profile_record(driver),
            query_placement=reverse_placement, query_driver_phase_rad=query_phase,
            query_driven_phase_rad=query_angle, query_source_pose=query_source,
            source_axis_relabel=relabel, removed_material_clock_axis="driven_clock_rad",
            other_material_enclosure="complete untrimmed finite stock; any original driver band only removes material",
        )
        angle_coordinate, material_scope = "physical", "driver_root_material"
    else:
        from stock_form_cutter import StockFormProfile
        radius = min(driven.blank_radius_mm, math.nextafter(driven.root_radius_max_mm + driven.geometry_error_bound_mm, math.inf))
        clipped = StockFormProfile(driven.teeth, driven.template, radius, driven.radial_translation_mm, driven.helix_angle_deg)
        query["driven"] = clipped
        query["inventory"], query["roots"], query["noncarrying"] = _inventory(clipped)
        query_phase, query_angle = list(phase), list(approach)
        result.update(
            method="actual_cutter_gapped_root_material_radial_enclosure",
            query_driver_profile=_profile_record(driver), query_driven_profile=_profile_record(clipped),
            query_placement=deepcopy(placement), query_driver_phase_rad=query_phase,
            query_driven_phase_rad=query_angle, query_source_pose=_source(context),
            root_subset_enclosure={
                "operation": "intersect actual finite stock material with a concentric local radial cylinder",
                "source_root_radius_upper_mm": driven.root_radius_max_mm,
                "source_profile_geometry_error_mm": driven.geometry_error_bound_mm,
                "radial_clip_radius_mm": radius, "source_blank_radius_mm": driven.blank_radius_mm,
                "retained_teeth": driven.teeth, "retained_helix_angle_deg": driven.helix_angle_deg,
                "retained_face_interval_mm": list(placement["driven_face_mm"]),
                "scope": "all physical teeth and axial stations; cutter gaps and actual cap material retained",
                "extra_working_material_policy": "UNKNOWN on refusal, not physical infeasibility",
            },
        )
        angle_coordinate, material_scope = "driven_material", "driver_full_material"
    receipt = _root(
        query, query_phase, angle_coordinate=angle_coordinate, approach=query_angle,
        material_scope=material_scope, additional_geometry_error_mm=_periodicity(context)[0],
    )
    result.update(material_sweep=receipt, root_air_lower_mm=receipt["physical_root_air_lower_bound_mm"])
    return result



def _cover(context, phase, branches, sense):
    source = _source(context)
    extent = context["angle_extent"]
    assigned = {branch["chart"]: [f"{branch['driven_tooth']}:{branch['physical_strata']['driven']['segment']}"] for branch in branches}
    included = {patch for patches in assigned.values() for patch in patches}
    minima = []
    for branch in branches:
        face = context["material_placement"]["driven_face_mm"]
        neighbourhood = {
            "phase_cell_rad": list(phase), "same_source_pose": source,
            "angle_coordinate": "driven_material", "approach_driven_phase_rad": [-extent, extent],
            "unknown_domain": branch["unknown_domain"],
            "driven_surface_domain": [[.1, .9], list(face)],
        }
        minima.append({
            "chart": branch["chart"], "neighbourhood": neighbourhood,
            "tangent_dimension": 2, "lagrangian_hessian_lower": 1.0,
            "objective_direction": -sense, "lagrangian_beta_derivative": _point(-sense),
            "outside_neighbourhood_air_mm": [.25, .5],
            "approach_derivative_magnitude_lower": 1.0,
            "objective_gradient_magnitude_upper_per_mm": 1.0,
            "objective_gradient_padding_mm": _bound_add(
                _point(branch["geometry_error_bound_mm"]), _point(_periodicity(context)[0]),
            )[1],
        })
    minimum_by_name = {minimum["chart"]: minimum for minimum in minima}
    shared = {patch: [name for name, patches in assigned.items() if patch in patches] for patch in included}
    remainders = [{
        "patch_id": patch, "charts": names, "outside_union_air_mm": [.25, .5],
        "neighbourhoods": {name: minimum_by_name[name]["neighbourhood"] for name in names},
        "patch_parameter_names": ["native_t", "z_mm"],
        "patch_parameter_domains": {
            name: deepcopy(minimum_by_name[name]["neighbourhood"]["driven_surface_domain"])
            for name in names
        },
    } for patch, names in sorted(shared.items()) if len(names) > 1]
    return {
        "proof_schema": "finite-stock-first-contact-cover/1", "native_certificate": False,
        "phase_cell_rad": list(phase), "same_source_pose": source,
        "additional_geometry_error_mm": _periodicity(context)[0],
        "angle_coordinate": "driven_material", "closing_driven_sense": sense,
        "backlash_lower_mm": .1, "required_root_air_mm": context["domain"]["root_air_requirements_mm"]["driven"],
        "root_free_driven_components_rad": [[-extent, extent]],
        "approach_driven_phase_rad": [-extent, extent],
        "free_reference_driven_phase_rad": _point(-extent * .999999 if sense == 1 else extent * .999999),
        "free_reference_air_mm": [.25, .5],
        "physical_patch_inventory": context["inventory"], "root_patch_ids": context["roots"],
        "noncarrying_patch_ids": context["noncarrying"], "chart_patch_ids": assigned,
        "excluded_patch_air_mm": {patch: [.25, .5] for patch in context["inventory"] if patch not in included},
        "chart_minimum_bounds": minima, "boundary_separations": [], "patch_remainder_bounds": remainders,
    }


def _difference(a, b, phase, source):
    delta = _bound_subtract(b["center_driven_phase_enclosure_rad"], a["center_driven_phase_enclosure_rad"])
    for name, ga, gb in zip(a["parameter_names"], a["driven_phase_parameter_derivatives"], b["driven_phase_parameter_derivatives"], strict=True):
        limits = phase if name == "driver_phase_rad" else source[name]
        centre = limits[0] / 2 + limits[1] / 2
        delta = _bound_add(delta, _bound_multiply(_bound_subtract(gb, ga), _bound_subtract(limits, _point(centre))))
    return list(delta)


def _geometry_payment(branch, additional_geometry_error_mm):
    # Fixture minima have objective-gradient upper=1 and approach-slope lower=1.
    return _certificate_geometry_payment(branch, {
        "objective_gradient_magnitude_upper_per_mm": 1.0,
        "approach_derivative_magnitude_lower": 1.0,
    }, additional_geometry_error_mm)


def _surface_receipts(context, cell, *, reference_only):
    cover = cell["first_contact_cover"]
    minima = {value["chart"]: value for value in cover["chart_minimum_bounds"]}
    phase, source = cell["phase_cell_rad"], cell["same_source_pose"]
    offset = [-context["driver"].angular_pitch_rad / 2, context["driver"].angular_pitch_rad / 2]
    records = []
    for patch in cover["physical_patch_inventory"]:
        cap = ":end_face:" in patch
        full = [[0.0, 1.0], [0.0, 1.0] if cap else list(context["material_placement"]["driven_face_mm"])]
        cuts = [] if reference_only else [
            deepcopy(minima[chart]["neighbourhood"]["driven_surface_domain"])
            for chart, patches in cover["chart_patch_ids"].items() if patch in patches
        ]
        empty = not _rectangle_remainder_nonempty(full, cuts)
        required = (context["domain"]["root_air_requirements_mm"]["driven"]
                    if not reference_only and patch in cover["root_patch_ids"] else 0.0)
        records.append({
            "status": "PROVED", "native_certificate": False, "physical_no_solution": False,
            "scope": "boundary patch against complete cutter-gapped driver material",
            "patch_id": patch, "phase_cell_rad": list(phase), "same_source_pose": deepcopy(source),
            "angle_coordinate": "driven_material",
            "approach_driven_phase_rad": deepcopy(
                cover["free_reference_driven_phase_rad"] if reference_only else cover["approach_driven_phase_rad"]),
            "patch_parameter_names": ["native_t", "radial_fraction" if cap else "z_mm"],
            "patch_parameter_domain": full, "excluded_patch_parameter_domains": cuts,
            "required_air_mm": required, "air_lower_mm": max(.5, math.nextafter(required, math.inf)),
            "additional_geometry_error_mm": cover["additional_geometry_error_mm"],
            "empty_remainder": empty, "boxes": 0 if empty else len(cuts) + 1,
            "terminal_boxes": 0 if empty else len(cuts) + 1,
            "largest_terminal_parameter_radius_mm": 0.0,
            "parameter_radius_metric_upper": 1.0,
            "inverse_offset_domain_rad": list(offset),
            "free_outer_inverse_offset_components_rad": [list(offset)],
            "free_inner_inverse_offset_components_rad": [[offset[0] * .8, offset[1] * .8]],
            "fixture_origin": _ORIGIN,
        })
    return records


def _cell(context, phase, families, count, sense):
    branches = [_branch(context, phase, family, rank, sense) for family in families for rank in range(count)]
    cover = _cover(context, phase, branches, sense)
    carriers = []
    for candidate in branches:
        comparisons = []
        for competitor in branches:
            if competitor is candidate:
                continue
            delta = _bound_multiply(_point(sense), _difference(competitor, candidate, phase, _source(context)))
            error = _bound_add(
                _point(_geometry_payment(candidate, cover["additional_geometry_error_mm"])),
                _point(_geometry_payment(competitor, cover["additional_geometry_error_mm"])),
            )
            excess = _bound_add(_point(delta[1]), error)
            paid = _bound_multiply(_point(context["driven"].pitch_radius_mm), excess)[1]
            comparisons.append({
                "competitor_chart": competitor["chart"], "closing_root_excess_rad": list(delta),
                "physical_geometry_error_payment_rad": list(error), "pitch_excess_upper_mm": max(0.0, paid),
            })
        carriers.append({"chart": candidate["chart"], "driven_tooth": candidate["driven_tooth"],
                         "eligible": True, "same_pose_comparisons": comparisons})
    cell = {"phase_cell_rad": list(phase), "same_source_pose": _source(context),
            "branch_proofs": branches, "first_contact_cover": cover, "root_proof": _root(context, phase),
            "driven_root_material_proof": _directed_root(context, phase, cover["approach_driven_phase_rad"]),
            "counted_teeth": sorted({branch["driven_tooth"] for branch in branches}),
            "carrier_comparisons": carriers}
    cell["surface_exclusion_receipts"] = _surface_receipts(context, cell, reference_only=False)
    cell["free_reference_exclusion_receipts"] = _surface_receipts(context, cell, reference_only=True)
    return cell


def _handover(context, phase, sense, count):
    full = [_branch(context, phase, family, rank, sense) for family in (0, 1) for rank in range(count)]
    branches = [full[0], full[count]]
    cover = _cover(context, phase, full, sense)
    endpoints = []
    for endpoint in phase:
        pair = [_branch(context, _point(endpoint), family, 0, sense) for family in (0, 1)]
        difference = _difference(pair[0], pair[1], _point(endpoint), _source(context))
        endpoints.append({
            "phase_rad": endpoint, "branch_proofs": pair,
            "closing_difference_rad": list(_bound_multiply(_point(sense), difference)),
            "same_pose_driven_root_difference_rad": difference,
            "difference_parameter_names": list(_source(context)),
            "difference_parameter_derivatives": [list(_bound_subtract(b, a)) for a, b in zip(pair[0]["driven_phase_parameter_derivatives"][1:], pair[1]["driven_phase_parameter_derivatives"][1:], strict=True)],
            "native_certificate": False,
        })
    error = _bound_add(*[
        _point(_geometry_payment(branch, cover["additional_geometry_error_mm"]))
        for branch in branches
    ])
    difference = _difference(branches[0], branches[1], phase, _source(context))
    payment = _bound_add(_point(max(abs(value) for value in difference)), error)
    jump = _bound_multiply(_point(context["driven"].pitch_radius_mm), payment)[1]
    middle = phase[0] / 2 + phase[1] / 2
    centred = dict(context)
    centred["domain"] = deepcopy(context["domain"])
    centred["domain"]["correlated_pose_parameters"] = [
        [name, _point(limits[0] / 2 + limits[1] / 2)] for name, limits in _source(context).items()
    ]
    centres = [_branch(centred, _point(middle), family, 0, sense) for family in (0, 1)]
    competitors = []
    for competitor in full:
        if competitor in branches:
            continue
        comparisons = []
        for selected in branches:
            excess = _bound_multiply(_point(sense), _difference(selected, competitor, phase, _source(context)))
            payment = _bound_add(
                _point(_geometry_payment(selected, cover["additional_geometry_error_mm"])),
                _point(_geometry_payment(competitor, cover["additional_geometry_error_mm"])),
            )
            paid = _bound_subtract(excess, payment)
            comparisons.append({
                "chart": selected["chart"], "closing_competitor_excess_rad": list(excess),
                "physical_geometry_error_payment_rad": list(payment),
                "paid_competitor_excess_lower_rad": paid[0],
            })
        competitors.append({"competitor_chart": competitor["chart"], "pair_comparisons": comparisons})
    return {
        "status": "PROVED", "continuous": True, "native_certificate": False, "physical_no_solution": False,
        "fixture_origin": _ORIGIN, "pair": [branch["driven_tooth"] for branch in branches],
        "phase_bracket_rad": list(phase), "same_source_pose": _source(context),
        "first_contact_cover": cover, "branch_proofs": branches,
        "first_contact_branch_proofs": full, "full_cell_competitor_exclusions": competitors,
        "center_branch_proofs": centres,
        "endpoint_difference_proofs": endpoints,
        "endpoint_difference_enclosures_rad": [record["closing_difference_rad"] for record in endpoints],
        "same_pose_driven_root_difference_rad": difference,
        "physical_geometry_error_payment_rad": list(error),
        "pitch_displacement_jump_upper_mm": math.nextafter(jump, math.inf),
        "root_component_coordinate": "driven_material",
        "root_free_component_rad": [-context["angle_extent"], context["angle_extent"]],
        "bound_definition": "reader-only coherent same-source endpoint difference plus physical geometry payment",
    }


def _periodicity(context):
    # Reuse the pure arithmetic reader's exact floating-angle/frame ledger;
    # this is not a diagnostic geometry solver or a production certificate.
    return _periodic_source_evidence(
        context["driver"], context["driven"], context["placement"], _source(context),
    )



def _seam(context, first, last, count, sense):
    pitch = context["driver"].angular_pitch_rad
    mate_pitch = context["driven"].angular_pitch_rad
    start = [_branch(context, [0.0, 0.0], 0, rank, sense) for rank in range(count)]
    end = [_branch(context, [pitch, pitch], 1, rank, sense) for rank in range(count)]
    displacement, evidence, rotations = _periodicity(context)
    pairs = []
    source = _source(context)
    for a, b in zip(start, end, strict=True):
        ga = dict(zip(list(source), a["driven_phase_parameter_derivatives"][1:], strict=True))
        transformed = dict(ga)
        for body, rotation in rotations.items():
            x, y = f"{body}_ecc_x_mm", f"{body}_ecc_y_mm"
            transformed[x] = _bound_add(_bound_multiply(ga[x], rotation[0][0]), _bound_multiply(ga[y], rotation[1][0]))
            transformed[y] = _bound_add(_bound_multiply(ga[x], rotation[0][1]), _bound_multiply(ga[y], rotation[1][1]))
        gradients = [list(_bound_subtract(transformed[name], value)) for name, value in zip(source, b["driven_phase_parameter_derivatives"][1:], strict=True)]
        centre = _bound_subtract(_bound_subtract(a["center_driven_phase_enclosure_rad"], _point(mate_pitch)), b["center_driven_phase_enclosure_rad"])
        difference = centre
        for limits, derivative in zip(source.values(), gradients, strict=True):
            middle = limits[0] / 2 + limits[1] / 2
            difference = _bound_add(difference, _bound_multiply(derivative, _bound_subtract(limits, _point(middle))))
        geometry, arc = (0.0, 0.0), (0.0, 0.0)
        for branch in (a, b):
            geometry = _bound_add(geometry, _point(_geometry_payment(branch, 0.0)))
            arc = _bound_add(arc, _bound_divide(_bound_multiply(_point(displacement), _point(1.0)), _point(1.0)))
        magnitude = _point(max(abs(value) for value in difference))
        payment = _bound_add(_bound_add(magnitude, geometry), arc)
        jump = _bound_multiply(_point(context["driven"].pitch_radius_mm), payment)[1]
        pairs.append({
            "start_chart": a["chart"], "end_chart": b["chart"],
            "centre_difference_rad": list(centre), "difference_parameter_names": list(source),
            "difference_parameter_derivatives": gradients,
            "same_pose_driven_root_difference_rad": list(difference), "source_relabel": rotations,
            "source_domain": "same physical centred disks within certified boxes; other axes unchanged",
            "native_certificate": False, "physical_geometry_error_payment_rad": list(geometry),
            "periodicity_error_payment_rad": list(arc),
            "periodicity_displacement_upper_mm": displacement,
            "mapped_start_material_root_rad": list(_bound_subtract(a["driven_material_phase_enclosure_rad"], _point(mate_pitch))),
            "end_material_root_rad": b["driven_material_phase_enclosure_rad"],
            "pitch_displacement_jump_upper_mm": math.nextafter(jump, math.inf),
        })
    return {
        "proof_schema": "finite-stock-periodic-seam/1", "status": "PROVED", "continuous": True,
        "native_certificate": False, "physical_no_solution": False, "fixture_origin": _ORIGIN,
        "phase_endpoints_rad": [0.0, pitch], "same_source_pose": source,
        "source_eccentricity_disks": deepcopy(context["domain"]["source_eccentricity_disks"]),
        "root_air_requirements_mm": deepcopy(context["domain"]["root_air_requirements_mm"]),
        "source_relabel": rotations, "closing_driven_sense": sense,
        "start_full_cell_branch_proofs": first["branch_proofs"],
        "end_full_cell_branch_proofs": last["branch_proofs"],
        "start_endpoint_branch_proofs": start, "end_endpoint_branch_proofs": end,
        "start_first_contact_cover": first["first_contact_cover"], "end_first_contact_cover": last["first_contact_cover"],
        "chart_pairs": pairs, "root_proof": _root(context, [pitch, pitch]),
        "driven_root_material_proof": _directed_root(context, [pitch, pitch], [-context["angle_extent"], context["angle_extent"]]),
        "periodicity_displacement_evidence": evidence,
        "joint_period_tooth_steps": math.lcm(context["driver"].teeth, context["driven"].teeth),
        "driven_pitch_radius_mm": context["driven"].pitch_radius_mm,
        "pitch_displacement_jump_upper_mm": max(pair["pitch_displacement_jump_upper_mm"] for pair in pairs),
        "maximum_jump_mm": .005,
        "bound_definition": "reader-only min/max paired-root envelope with real finite arithmetic payments",
    }


def _first_branches(cell):
    first = _uniform_first_branch_names(cell, cell["same_source_pose"])
    return [branch for branch in cell["branch_proofs"] if not first or branch["chart"] in first]




def _phase_envelope(context, cell, branch):
    zero = context["domain"]["mechanical_zero_rad"]
    ratio = _bound_divide(_point(context["driver"].teeth), _point(context["driven"].teeth))
    phase = cell["phase_cell_rad"]
    centre = phase[0] / 2 + phase[1] / 2
    displacement = _periodicity(context)[0]
    geometry = _geometry_payment(branch, 0.0)
    periodic = _bound_divide(_bound_multiply(_point(displacement), _point(1.0)), _point(1.0))[1]
    payment = _geometry_payment(branch, displacement)
    te = _bound_add(
        _bound_subtract(branch["center_driven_phase_enclosure_rad"], _point(zero["driven"])),
        _bound_multiply(ratio, _bound_subtract(_point(centre), _point(zero["driver"]))),
    )
    for name, derivative in zip(branch["parameter_names"], branch["driven_phase_parameter_derivatives"], strict=True):
        limits = phase if name == "driver_phase_rad" else cell["same_source_pose"][name]
        middle = limits[0] / 2 + limits[1] / 2
        slope = _bound_add(derivative, ratio) if name == "driver_phase_rad" else derivative
        te = _bound_add(te, _bound_multiply(slope, _bound_subtract(limits, _point(middle))))
    return {
        "chart": branch["chart"],
        "signed_running_te_interval_rad": list(_bound_add(te, [-payment, payment])),
        "physical_driven_phase_interval_rad": list(_bound_add(branch["driven_phase_enclosure_rad"], [-payment, payment])),
        "material_driven_phase_interval_rad": list(_bound_add(branch["driven_material_phase_enclosure_rad"], [-payment, payment])),
        "physical_geometry_payment_rad": geometry, "joint_period_displacement_upper_mm": displacement,
        "joint_period_error_payment_rad": periodic, "total_geometric_payment_rad": payment,
        "mechanical_zero_rad": deepcopy(zero),
        "definition": "physical beta-beta0 + exact tooth-count ratio*(actual phi-phi0); shared parameter derivatives",
    }


def _period_record(context, cells, driver_sense):
    zero = context["domain"]["mechanical_zero_rad"]
    records, envelopes, selected = {}, {}, {}
    for side, cell in cells.items():
        selected[side] = _first_branches(cell)
        records[side] = [_phase_envelope(context, cell, branch) for branch in selected[side]]
        choose = max if cell["first_contact_cover"]["closing_driven_sense"] == -1 else min
        envelopes[side] = {
            name: [choose(record[name][0] for record in records[side]),
                   choose(record[name][1] for record in records[side])]
            for name in ("signed_running_te_interval_rad", "physical_driven_phase_interval_rad", "material_driven_phase_interval_rad")
        }
    phase, source = cells["lower"]["phase_cell_rad"], cells["lower"]["same_source_pose"]
    payments = {record["chart"]: record["total_geometric_payment_rad"] for values in records.values() for record in values}
    pairs = []
    for lower in selected["lower"]:
        for upper in selected["upper"]:
            difference = _difference(lower, upper, phase, source)
            payment = _bound_add(_point(payments[lower["chart"]]), _point(payments[upper["chart"]]))[1]
            pairs.append({
                "lower_chart": lower["chart"], "upper_chart": upper["chart"],
                "same_pose_root_difference_rad": difference,
                "geometry_and_period_payment_rad": payment,
                "paid_root_difference_rad": list(_bound_add(difference, [-payment, payment])),
            })
    angular = [min(pair["paid_root_difference_rad"][0] for pair in pairs),
               min(pair["paid_root_difference_rad"][1] for pair in pairs)]
    arc = list(_bound_multiply(angular, _point(context["driven"].pitch_radius_mm)))
    backlash = {
        "same_source_pose": deepcopy(source), "phase_cell_rad": list(phase),
        "branch_pairs": pairs, "backlash_interval_rad": angular, "backlash_interval_mm": arc,
        "pitch_radius_mm": context["driven"].pitch_radius_mm,
        "definition": "min of same-q upper-minus-lower root differences; source derivatives subtracted before propagation",
    }
    side = "lower" if driver_sense == -1 else "upper"
    root, reverse = cells[side]["root_proof"], cells[side]["driven_root_material_proof"]
    return {
        "phase_cell_rad": list(phase),
        "actual_driver_interval_rad": list(_bound_subtract(phase, _point(zero["driver"]))),
        "actual_driven_lower_interval_rad": list(_bound_subtract(envelopes["lower"]["physical_driven_phase_interval_rad"], _point(zero["driven"]))),
        "actual_driven_upper_interval_rad": list(_bound_subtract(envelopes["upper"]["physical_driven_phase_interval_rad"], _point(zero["driven"]))),
        "material_driven_lower_interval_rad": envelopes["lower"]["material_driven_phase_interval_rad"],
        "material_driven_upper_interval_rad": envelopes["upper"]["material_driven_phase_interval_rad"],
        "signed_running_te_interval_rad": envelopes[side]["signed_running_te_interval_rad"],
        "mechanical_zero_rad": deepcopy(zero), "operating_driver_sense": driver_sense,
        "side_branch_envelopes": records,
        "correlated_backlash": backlash, "correlated_backlash_interval_mm": arc,
        "root_air": {
            "qualified": True, "root_is_carrying": False,
            "root_air_requirements_mm": deepcopy(context["domain"]["root_air_requirements_mm"]),
            "driver_root_air_lower_mm": root["physical_root_air_lower_bound_mm"],
            "driven_root_air_lower_mm": reverse["root_air_lower_mm"],
            "driver_root_proof": deepcopy(root), "driven_root_material_proof": deepcopy(reverse),
        },
        "same_source_pose": deepcopy(source),
        "whole_joint_period_scope": {
            "tooth_steps": math.lcm(context["driver"].teeth, context["driven"].teeth),
            "source_relabel": "actual rotation-invariant body eccentricity disks; all physical tooth identities",
            "displacement_payment_mm": _periodicity(context)[0],
        },
        "fixture_origin": _ORIGIN,
    }


def _actual_read_record(context, phase, count, driver_sense):
    cells = {side: _cell(context, _point(phase), (0,), count, sense)
             for side, sense in (("lower", -1), ("upper", 1))}
    for cell in cells.values():
        cell.update(proof_schema="finite-stock-first-contact-cell/1", status="PROVED", native_certificate=False)
        cell["numerical_initializations"] = {
            branch["chart"]: [low / 2 + high / 2 for low, high in branch["center_root_box"]]
            for branch in cell["branch_proofs"]
        }
        for branch in cell["branch_proofs"]:
            # TESTONLY analytic trace residuals, never measured stock evidence.
            branch["center_point"] = list(cell["numerical_initializations"][branch["chart"]])
            branch["center_point_residual_intervals"] = [[0.0,0.0] for _ in branch["center_point"]]
            branch["center_root_residual_intervals"] = [[-1e-9,1e-9] for _ in branch["center_point"]]
    row = _period_record(context, cells, driver_sense)
    side = "lower" if driver_sense == -1 else "upper"
    choose = max if driver_sense == -1 else min
    cover = cells[side]["first_contact_cover"]
    minima = {value["chart"]:value for value in cover["chart_minimum_bounds"]}
    centres = {}
    for branch in cells[side]["branch_proofs"]:
        payment = _certificate_geometry_payment(branch,minima[branch["chart"]],cover["additional_geometry_error_mm"])
        centres[branch["chart"]] = _bound_add(branch["center_driven_phase_enclosure_rad"],(-payment,payment))
    first = (choose(value[0] for value in centres.values()),choose(value[1] for value in centres.values()))
    _,name = choose(((value[0] if side == "lower" else value[1]),name) for name,value in centres.items())
    selected = next(branch for branch in cells[side]["branch_proofs"] if branch["chart"] == name)
    point = selected["center_point"]
    centre_source = {name: _point(low / 2 + high / 2) for name, (low, high) in _source(context).items()}
    beta = point[selected["driven_angle_unknown_index"]] - centre_source["driven_clock_rad"][0]
    zero = context["domain"]["mechanical_zero_rad"]
    reference = math.fsum((beta, -zero["driven"], context["driver"].teeth / context["driven"].teeth * (phase - zero["driver"])))
    error_interval = _bound_subtract(row["signed_running_te_interval_rad"], _point(reference))
    centre_error = _bound_subtract(first,_point(beta))
    return {
        **row, "actual_driver_phase_rad": phase,
        "reference_signed_running_te_rad": reference, "reference_driven_phase_rad": beta,
        "reference_source_pose": centre_source, "reference_chart": selected["chart"],
        "reference_common_normal_point": list(point),
        "reference_residual_intervals": [[0.0, 0.0] for _ in point],
        "reference_root_proof": deepcopy(selected),
        "reference_error_bound_rad": max(abs(value) for value in error_interval),
        "reference_center_first_root_interval_rad":list(first),
        "reference_center_first_candidates":sorted(name for name,value in centres.items()
            if value[0] <= first[1] and value[1] >= first[0]),
        "reference_center_first_root_error_rad":list(centre_error),
        "reference_center_first_root_error_bound_rad":max(abs(value) for value in centre_error),
        "actual_interval_error_from_reference_rad": list(error_interval),
        "direct_first_contact_sides": cells,
        "finite_face_material_enclosure": deepcopy(context["finite_face_material_enclosure"]),
        "reference_definition": "TESTONLY canonical certified centre-root midpoint; midpoint-to-true-first-root error retained",
        "direct_actual_phase_query": True, "periodic_point_substitution": False,
        "fixture_origin": _ORIGIN,
    }


def synthetic_case(driver, driven, placement, domain, *, coverage_floor=1.1, row_floor=0.0, operating_driver_sense=-1, read_phases_rad=()):
    """Return isolated receiver data; never a claim that these gears mesh.

    Callers provide actual core objects and a TEST-ONLY source/placement record.
    Both loaded directions retain every source coordinate and every physical
    mate patch.  The numbers describe a coherent synthetic root trace, not the
    real stock surfaces' common-normal equations.  Real qualification must be
    collected separately from the actual six diagnostic sources.
    """
    if (not math.isfinite(coverage_floor) or coverage_floor <= 0
            or not math.isfinite(row_floor) or not 0 <= row_floor <= .89
            or type(operating_driver_sense) is not int or operating_driver_sense not in (-1, 1)):
        raise ValueError("synthetic reader fixture cannot support the requested floors/direction")
    if (placement["driver_shoulder_z_mm"] is None) != (placement["driver_turned_radius_mm"] is None):
        raise ValueError("synthetic placement has a partial absent material band")
    read_phases_rad = tuple(read_phases_rad)
    if any(type(phase) not in (int, float) or not math.isfinite(phase) for phase in read_phases_rad):
        raise ValueError("synthetic direct phase queries must be finite physical angles")
    inventory, roots, noncarrying = _inventory(driven)
    support, material = _face_family_placements(placement, domain)
    support_width = _bound_subtract(_point(support["driven_face_mm"][1]), _point(support["driven_face_mm"][0]))
    material_width = _bound_subtract(_point(material["driven_face_mm"][1]), _point(material["driven_face_mm"][0]))
    row_fraction = _bound_divide(_bound_multiply(_point(.89), support_width), material_width)[0]
    if row_fraction < row_floor:
        raise ValueError("synthetic interior row does not support the requested all-family row floor")
    profile_error = sum(math.hypot(*(v for row in placement[f"{body}_frame"] for v in row)) * profile.geometry_error_bound_mm
                        for body, profile in (("driver", driver), ("driven", driven)))
    context = {
        "driver": driver, "driven": driven, "placement": deepcopy(support),
        "material_placement": deepcopy(material), "domain": deepcopy(domain),
        "inventory": inventory, "roots": roots, "noncarrying": noncarrying,
        "geometry_error_mm": max(1e-8, profile_error * 2),
        "angle_extent": max((2.0, *(abs(phase) * driver.teeth / driven.teeth + 1.0 for phase in read_phases_rad))),
    }
    count = math.floor(coverage_floor) + 1
    pitch = driver.angular_pitch_rad
    coverage = min(count - .1, coverage_floor + .05)
    sides = {}
    for side, sense in (("lower", -1), ("upper", 1)):
        phases = [[0.0, pitch / 3], [pitch / 3, 2 * pitch / 3], [2 * pitch / 3, pitch]]
        cells = [_cell(context, phase, families, count, sense) for phase, families in zip(phases, ((0,), (0, 1), (1,)), strict=True)]
        left, right = (_branch(context, _point(endpoint), 0, 0, sense) for endpoint in phases[0])
        lo, hi = support["driven_face_mm"]
        row = [lo + .05 * (hi - lo), hi - .05 * (hi - lo)]
        sides[side] = {
            "proof_schema": "finite-stock-continuous-envelope/1", "status": "PROVED", "native_certificate": False,
            "same_source_pose": _source(context), "phase_domain_rad": [0.0, pitch], "closing_driven_sense": sense,
            "stock_form_coverage_lower": coverage, "phase_cells": cells,
            "boundary_continuations": [{
                "left_cell_index": index, "right_cell_index": index + 1,
                "phase_rad": phases[index][1],
                "chart": _branch(context, _point(phases[index][1]), index, 0, sense)["chart"],
                "left_branch_proof": _branch(context, _point(phases[index][1]), index, 0, sense),
                "right_branch_proof": _branch(context, _point(phases[index][1]), index, 0, sense),
            } for index in range(2)],
            "row_branch_spans": [{"chart": cells[0]["branch_proofs"][0]["chart"], "first_cell_index": 0, "last_cell_index": 0,
                                  "phase_endpoints_rad": phases[0], "left_branch_proof": left, "right_branch_proof": right,
                                  "inner_station_interval_mm": row}],
            "row_available_intervals_mm": [row], "row_available_fraction_lower": row_fraction,
            "handovers": [_handover(context, phases[1], sense, count)],
            "periodic_seam": _seam(context, cells[0], cells[-1], count, sense),
        }
    certificate = {
        "proof_schema": "finite-stock-continuous-envelope/1", "status": "PROVED", "native_certificate": False,
        "same_source_pose": _source(context), "phase_domain_rad": [0.0, pitch], "sides": sides,
        "fixture_origin": _ORIGIN,
        "finite_face_material_enclosure": {
            "method": "nested actual finite-stock material with common physical side/tip support",
            "reference_placement": deepcopy(placement),
            "support_placement": deepcopy(support), "material_placement": deepcopy(material),
            "source_face_width_limits_mm": deepcopy(domain["finite_face_width_limits_mm"]),
            "source_face_anchor_fraction": deepcopy(domain["finite_face_anchor_fraction"]),
            "source_driver_retained_band_limits_mm": deepcopy(domain.get("driver_retained_band_limits_mm")),
            "moving_band_cap_carrying": False,
            "moving_face_cap_carrying": False, "native_certificate": False,
        },
    }
    context["finite_face_material_enclosure"] = certificate["finite_face_material_enclosure"]
    result = {
        "source_domain_proved": True, "production_source_qualified": domain["production_source_domain"],
        "metric": "STOCK-FORM COVERAGE", "is_conjugate": False, "native_certificate": False,
        "driver_profile": _profile_record(driver), "driven_profile": _profile_record(driven),
        "placement": deepcopy(placement), "continuous_source_domain": deepcopy(domain),
        "continuous_contact_certificate": certificate,
        "operating_driver_sense": operating_driver_sense, "continuous_carrying_contact": True,
        "stock_form_coverage_lower": coverage, "uncovered_phase_rad": 0.0,
        "row_available_intervals_mm": sides["lower"]["row_available_intervals_mm"], "row_available_fraction_lower": row_fraction,
        "numerical_error_bounds": {
            "surface_mm": 2 * (context["geometry_error_mm"] + _periodicity(context)[0] / (_frame_distance_scale_limit(placement["driver_frame"]) / 2)),
            "phase_motion_mm": 1e-7, "te_rad": 1e-7,
        },
        "handovers": sides["lower" if operating_driver_sense == -1 else "upper"]["handovers"],
        "phase_reserve_rad": .01, "noncarrying_pair_normal_gap_upper_mm": .001,
        "fixture_origin": _ORIGIN,
    }
    if read_phases_rad:
        result["full_period_cells"] = [
            _period_record(context, {side: proof["phase_cells"][index] for side, proof in sides.items()}, operating_driver_sense)
            for index in range(len(sides["lower"]["phase_cells"]))
        ]
        lag = [
            min(row["signed_running_te_interval_rad"][0] for row in result["full_period_cells"]),
            max(row["signed_running_te_interval_rad"][1] for row in result["full_period_cells"]),
        ]
        result["whole_period_signed_running_te_interval_rad"] = lag
        certificate["whole_period_signed_running_te_interval_rad"] = list(lag)
        certificate["whole_period_signed_running_te_scope"] = {
            "operating_driver_sense": operating_driver_sense,
            "source_domain": deepcopy(domain),
            "phase_cells": len(result["full_period_cells"]),
            "all_physical_tooth_identities": True,
            "periodicity_authority": "both actual source-relabelled periodic_seam receipts",
            "bound_authority": "same-q branch derivatives plus actual geometry and full joint-period displacement",
        }
        result["actual_read_phases"] = [
            _actual_read_record(context, phase, count, operating_driver_sense)
            for phase in read_phases_rad
        ]
    return result
