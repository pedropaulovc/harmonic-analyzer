"""Actual-stock crossed-crank qualification, consumed without a solver import.

Dimensional grades live in crank_mesh_geometry. The frozen design payload
must qualify every retained corner before native assembly or drawing callers
publish a phase, backlash, STOCK-FORM COVERAGE or row figure. Former ideal-N
nine-phase slopes and Tredgold contact-ratio equations are intentionally gone.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from crank_mesh_calibration import CALIBRATION
import crank_mesh_geometry as geometry
from crank_drive_phase import geometry_sha256
from crank_mesh_requirements import (
    HANDOVER_JUMP_MAX_MM,POSITIVE_BACKLASH_MIN_MM,
    ROW_ENGAGEMENT_MIN,STOCK_FORM_COVERAGE_MIN,
)

# Physical dimensional receivers remain pure and are independent of whether
# the chosen stock-form tooth system qualifies at the current fixed centre.
R64 = geometry.R64
R16 = geometry.R16
FRAME_C2C = geometry.FRAME_C2C
FRAME_DY = geometry.FRAME_DY
FRAME_DX = geometry.FRAME_DX
DC_PER_DY = geometry.DC_PER_DY
DC_PER_DX = geometry.DC_PER_DX
GEAR64_POST_OFFSET = geometry.GEAR64_POST_OFFSET
CRANK_BEARING_LENGTH = geometry.CRANK_BEARING_LENGTH
CRANK_SUPPORT_NORTH_MIN = geometry.CRANK_SUPPORT_NORTH_MIN
PINION_HALF_FACE_MAX = geometry.PINION_HALF_FACE_MAX
CRANK_OVERHANG = geometry.CRANK_OVERHANG
CONE_OVERHANG = geometry.CONE_OVERHANG
MESH_LEVER = geometry.MESH_LEVER
POST_ANGLE_DEG = geometry.POST_ANGLE_DEG
TOOTH_RUNOUT_TIR_MM = geometry.TOOTH_RUNOUT_TIR_MM
TIP_ROOT_BAND_RADIAL = geometry.TIP_ROOT_BAND_RADIAL
SPACING_PRINTED = geometry.SPACING_PRINTED
GEAR64_TOOTH_THICKNESS_DEVIATIONS = geometry.gear64.TOOTH_THICKNESS_DEVIATIONS
TIP_DIA_LOW_16 = geometry.pinion.OUTSIDE_DIA-geometry.pinion.OUTSIDE_DIA_TOLERANCE_MM
TIP_DIA_LOW_64 = geometry.gear64.OUTSIDE_DIA-geometry.gear64.OUTSIDE_DIA_TOLERANCE_MM
CALIBRATION_CASES = CALIBRATION["cases"]


def required_calibration_case_names() -> frozenset[str]:
    return geometry.required_calibration_case_names()


def _same_numeric_tree(actual, expected) -> bool:
    if isinstance(expected,dict):
        return isinstance(actual,dict) and actual.keys() == expected.keys() and all(
            _same_numeric_tree(actual[key],value) for key,value in expected.items())
    if isinstance(expected,(tuple,list)):
        return isinstance(actual,(tuple,list)) and len(actual) == len(expected) and all(
            _same_numeric_tree(a,b) for a,b in zip(actual,expected))
    if isinstance(expected,bool):
        return actual is expected
    if isinstance(expected,(float,int)):
        return type(actual) in (float,int) and math.isfinite(actual) and actual == expected
    return actual == expected


def _finite_tree(value) -> bool:
    if isinstance(value,(float,int)):
        return math.isfinite(value)
    if isinstance(value,dict):
        return all((key in ("root_max_radial_clearance_screen_mm","terminal_lower_rad",
                            "t_fixed","z_fixed","driven_station_unknown_index",
                            "radial_cap_radius_mm","radial_cap_source") and item is None)
                   or _finite_tree(item) for key,item in value.items())
    if isinstance(value,(tuple,list)):
        return all(_finite_tree(item) for item in value)
    return value is not None


def _require_components(components, domain, *, contained_in=None) -> None:
    """Check the complete ordered interval set, not only its chosen member."""
    domain_low,domain_high = domain
    previous = domain_low
    if not math.isfinite(domain_low) or not math.isfinite(domain_high) or domain_low >= domain_high:
        raise ValueError("invalid physical phase domain")
    for low,high in components:
        if (not math.isfinite(low) or not math.isfinite(high)
                or not domain_low <= low < high <= domain_high or low < previous):
            raise ValueError("invalid ordered physical phase components")
        if contained_in is not None and not any(a <= low < high <= b for a,b in contained_in):
            raise ValueError("physical phase INNER exceeds its containing proof")
        previous = high

def _bound_add(a, b):
    """Replay outward certificate arithmetic without importing a solver."""
    if a[0] == a[1] == 0:
        return b
    if b[0] == b[1] == 0:
        return a
    return (math.nextafter(a[0]+b[0],-math.inf),math.nextafter(a[1]+b[1],math.inf))


def _bound_subtract(a, b):
    if a[0] == a[1] == b[0] == b[1]:
        return (0.0,0.0)
    return _bound_add(a,(-b[1],-b[0]))


def _bound_multiply(a, b):
    if a[0] == a[1] == 0 or b[0] == b[1] == 0:
        return (0.0,0.0)
    if a[0] == a[1] == 1:
        return b
    if b[0] == b[1] == 1:
        return a
    values = (a[0]*b[0],a[0]*b[1],a[1]*b[0],a[1]*b[1])
    return (math.nextafter(min(values),-math.inf),math.nextafter(max(values),math.inf))


def _require_continuous_side(case, domain, driver, driven, proof, *, closing_sense, operating) -> None:
    """Read one loaded direction without importing its diagnostic engine."""
    pitch = driver.angular_pitch_rad
    source = {name:list(limits) for name,limits in domain["correlated_pose_parameters"]}
    if (proof["proof_schema"] != "finite-stock-continuous-envelope/1"
            or proof["status"] != "PROVED" or proof["native_certificate"]
            or not _same_numeric_tree(proof["same_source_pose"],source)
            or not _same_numeric_tree(proof["phase_domain_rad"],[0.0,pitch])):
        raise ValueError("continuous contact proof has a different physical source/domain")
    if proof["closing_driven_sense"] != closing_sense:
        raise ValueError("continuous proof changed the physical loaded approach direction")

    def interval(value):
        if (not isinstance(value,(list,tuple)) or len(value) != 2
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in value)
                or value[0] > value[1]):
            raise ValueError("invalid finite continuation interval")
        return value

    def contains(outer,inner,strict=False):
        a,b = interval(outer)
        x,y = interval(inner)
        return a < x <= y < b if strict else a <= x <= y <= b

    def neighbourhood(record, branch, phase, cover):
        if (not isinstance(record,dict)
                or not _same_numeric_tree(record["phase_cell_rad"],phase)
                or not _same_numeric_tree(record["same_source_pose"],source)
                or record["angle_coordinate"] != cover["angle_coordinate"]
                or not contains(record["approach_driven_phase_rad"],cover["approach_driven_phase_rad"])
                or len(record["unknown_domain"]) != len(branch["unknown_domain"])
                or not all(contains(a,b) for a,b in zip(record["unknown_domain"],branch["unknown_domain"]))):
            raise ValueError("numeric minimum/separation belongs to a different chart neighbourhood or approach")

    def same_pose_difference(a, b, phase):
        delta = _bound_subtract(interval(b["center_driven_phase_enclosure_rad"]),
                                interval(a["center_driven_phase_enclosure_rad"]))
        if a["parameter_names"] != b["parameter_names"]:
            raise ValueError("same-pose comparison uses different derivative coordinates")
        for name,ga,gb in zip(a["parameter_names"],
                             a["driven_phase_parameter_derivatives"],
                             b["driven_phase_parameter_derivatives"],strict=True):
            limits = phase if name == "driver_phase_rad" else source[name]
            centre = limits[0]/2+limits[1]/2
            delta = _bound_add(delta,_bound_multiply(_bound_subtract(gb,ga),
                               _bound_subtract(limits,(centre,centre))))
        return delta

    def geometry_payment(branch, minimum):
        error = branch["geometry_error_bound_mm"]
        gradient = minimum["objective_gradient_magnitude_upper_per_mm"]
        slope = minimum["approach_derivative_magnitude_lower"]
        if error < 0 or gradient <= 0 or slope <= 0:
            raise ValueError("physical profile error lacks a positive objective/transversality payment")
        numerator = _bound_multiply((error,error),(gradient,gradient))
        if slope == 1:
            return numerator[1]
        reciprocal = (math.nextafter(1/slope,-math.inf),math.nextafter(1/slope,math.inf))
        return _bound_multiply(numerator,reciprocal)[1]

    physical_segments = {
        body:{segment.name:segment for segment in profile.external_boundary_segments()}
        for body,profile in (("driver",driver),("driven",driven))
    }
    perimeter = driven.external_boundary_segments()
    inventory = {
        f"{tooth}:{segment.name}{suffix}"
        for tooth in range(driven.teeth) for segment in perimeter
        for suffix in ("",":end_face:-1",":end_face:+1")
    }
    roots = {
        f"{tooth}:{segment.name}{suffix}"
        for tooth in range(driven.teeth) for segment in perimeter
        if segment.kind not in ("flank","radial","tip_arc")
        for suffix in ("",":end_face:-1",":end_face:+1")
    }
    noncarrying = roots | {name for name in inventory if ":end_face:" in name}
    cells = proof["phase_cells"]
    if not cells:
        raise ValueError("no continuous common-normal phase cells")
    previous,integral = 0.0,(0.0,0.0)
    guaranteed_rows = []
    validated_cells = []
    for cell in cells:
        phase = interval(cell["phase_cell_rad"])
        if phase[0] != previous or not phase[0] < phase[1] <= pitch:
            raise ValueError("continuous phase cells omit, overlap, or reorder the physical pitch")
        previous = phase[1]
        if not _same_numeric_tree(cell["same_source_pose"],source):
            raise ValueError("continuous phase cell narrowed the physical source domain")
        cover = cell["first_contact_cover"]
        if (cover["proof_schema"] != "finite-stock-first-contact-cover/1" or cover["native_certificate"]
                or not _same_numeric_tree(cover["phase_cell_rad"],phase)
                or not _same_numeric_tree(cover["same_source_pose"],source)
                or set(cover["physical_patch_inventory"]) != inventory
                or len(cover["physical_patch_inventory"]) != len(inventory)
                or set(cover["root_patch_ids"]) != roots
                or set(cover["noncarrying_patch_ids"]) != noncarrying
                or cover["required_root_air_mm"] != domain["required_root_air_mm"]
                or cover["backlash_lower_mm"] <= POSITIVE_BACKLASH_MIN_MM
                or cover["closing_driven_sense"] != closing_sense
                or cover["angle_coordinate"] not in ("physical","driven_material")):
            raise ValueError("continuous first-contact physical inventory/air/source is incomplete")
        approach = interval(cover["approach_driven_phase_rad"])
        reference = interval(cover["free_reference_driven_phase_rad"])
        if not contains(approach,reference) or interval(cover["free_reference_air_mm"])[0] <= 0:
            raise ValueError("first-contact approach has no actual strictly free reference")
        root = cell["root_proof"]
        raw = root["root_sweep"]
        pitch_domain = (-pitch/2,pitch/2)
        if (root["status"] != "PROVED" or raw["status"] != "resolved"
                or raw["root_is_carrying"] or raw["native_solid_certificate"]
                or not _same_numeric_tree(root["same_source_pose"],source)
                or not _same_numeric_tree(root["phase_cell_rad"],phase)
                or root["angle_coordinate"] != cover["angle_coordinate"]
                or not contains(root["driven_angle_domain_rad"],approach)
                or root["physical_driven_teeth"] != list(range(driven.teeth))
                or set(root["physical_patch_inventory"]) != inventory
                or len(root["physical_patch_inventory"]) != len(inventory)
                or not _same_numeric_tree(raw["offset_domain_rad"],pitch_domain)
                or raw["root_air_lower_bound_mm"] < domain["required_root_air_mm"]
                or raw["required_root_air_mm"] < domain["required_root_air_mm"]
                or not 0 <= raw["geometric_uncertainty_mm"] <= case["numerical_error_bounds"]["surface_mm"]):
            raise ValueError("continuous root enclosure is absent or from a different pose")
        _require_components(raw["free_outer"],pitch_domain)
        _require_components(raw["free_inner"],pitch_domain,contained_in=raw["free_outer"])
        _require_components(root["inverse_offset_free_components_rad"],pitch_domain,contained_in=raw["free_inner"])
        if not any(a <= 0 <= b for a,b in root["inverse_offset_free_components_rad"]):
            raise ValueError("continuous pose is outside the actual root-free INNER")
        if not _same_numeric_tree(cover["root_free_driven_components_rad"],root["root_free_driven_components_rad"]):
            raise ValueError("first-contact cover substituted a root-free component hull")
        branches = cell["branch_proofs"]
        names = {branch["chart"] for branch in branches}
        assigned = cover["chart_patch_ids"]
        excluded = cover["excluded_patch_air_mm"]
        included = {name for patches in assigned.values() for name in patches}
        if (not branches or len(names) != len(branches) or assigned.keys() != names
                or included & excluded.keys() or included | excluded.keys() != inventory
                or not roots <= excluded.keys()):
            raise ValueError("continuous physical surface cover is missing a branch or competitor")
        for name,air in excluded.items():
            if interval(air)[0] <= (domain["required_root_air_mm"] if name in roots else 0):
                raise ValueError("unexcluded physical root or first-contact competitor")
        minima = {item["chart"]:item for item in cover["chart_minimum_bounds"]}
        branch_by_name = {branch["chart"]:branch for branch in branches}
        if minima.keys() != names or len(minima) != len(cover["chart_minimum_bounds"]):
            raise ValueError("common-normal roots lack their actual local minimum proof")
        for item in minima.values():
            neighbourhood(item["neighbourhood"],branch_by_name[item["chart"]],phase,cover)
            derivative = interval(item["lagrangian_beta_derivative"])
            direction = item["objective_direction"]
            signed_lower = derivative[0] if direction == 1 else -derivative[1]
            if (type(item["tangent_dimension"]) is not int or item["tangent_dimension"] != 2
                    or item["lagrangian_hessian_lower"] <= 0
                    or direction != -closing_sense
                    or interval(item["outside_neighbourhood_air_mm"])[0] <= 0
                    or not 0 < item["approach_derivative_magnitude_lower"] <= signed_lower):
                raise ValueError("local constrained minimum or closing transversality is unproved")
            if item["objective_gradient_magnitude_upper_per_mm"] <= 0:
                raise ValueError("actual profile geometry error has no objective Lipschitz bound")
        expected_boundaries = {(patch,chart) for chart,patches in assigned.items()
                               for patch in patches if patch in noncarrying}
        boundaries = {(item["patch_id"],item["chart"]):item for item in cover["boundary_separations"]}
        if boundaries.keys() != expected_boundaries or len(boundaries) != len(cover["boundary_separations"]):
            raise ValueError("actual cap-edge neighbourhood lacks its one-sided separation")
        for item in boundaries.values():
            neighbourhood(item["neighbourhood"],branch_by_name[item["chart"]],phase,cover)
            if not _same_numeric_tree(item["neighbourhood"],minima[item["chart"]]["neighbourhood"]):
                raise ValueError("cap separation and local minimum excise different neighbourhoods")
            if (item["inward_gap_derivative_lower"] <= 0
                    or interval(item["outside_neighbourhood_air_mm"])[0] <= 0):
                raise ValueError("noncarrying cap interior has no actual inward separation")
        shared = {patch:{chart for chart,patches in assigned.items() if patch in patches}
                  for patch in included}
        shared = {patch:charts for patch,charts in shared.items() if len(charts) > 1}
        remainders = {item["patch_id"]:item for item in cover["patch_remainder_bounds"]}
        if remainders.keys() != shared.keys() or len(remainders) != len(cover["patch_remainder_bounds"]):
            raise ValueError("shared finite patch lacks complete outside-union exclusion")
        for patch,charts in shared.items():
            item = remainders[patch]
            if set(item["charts"]) != charts or len(item["charts"]) != len(charts) or interval(item["outside_union_air_mm"])[0] <= 0:
                raise ValueError("outside-union proof differs from its actual chart neighbourhoods")
            if item["neighbourhoods"].keys() != charts:
                raise ValueError("outside-union proof omitted a chart neighbourhood")
            for chart in charts:
                neighbourhood(item["neighbourhoods"][chart],branch_by_name[chart],phase,cover)
                if (not _same_numeric_tree(item["neighbourhoods"][chart],minima[chart]["neighbourhood"])
                        or minima[chart]["outside_neighbourhood_air_mm"][0] > item["outside_union_air_mm"][0]):
                    raise ValueError("outside-union clearance is not bound to its exact local minimum domains")
        for branch in branches:
            if (branch["proof_schema"] != "finite-stock-common-normal-continuation/1"
                    or branch["status"] != "PROVED" or branch["native_certificate"]
                    or not _same_numeric_tree(branch["phase_cell_rad"],phase)
                    or not _same_numeric_tree(branch["same_source_pose"],source)
                    or branch["parameter_names"] != ["driver_phase_rad",*source]
                    or not 0 <= branch["contraction_upper"] < 1):
                raise ValueError("common-normal branch is not a uniform physical-source proof")
            tooth = branch["driven_tooth"]
            if type(tooth) is not int or not 0 <= tooth < driven.teeth:
                raise ValueError("continuous branch names a nonphysical tooth")
            unknown,box = branch["unknown_domain"],branch["root_box"]
            if len(unknown) not in (5,6,7) or len(box) != len(unknown) or not all(
                    contains(a,b,strict=True) for a,b in zip(unknown,box)):
                raise ValueError("common-normal root lacks strict interval inclusion")
            derivatives = branch["driven_phase_parameter_derivatives"]
            if len(derivatives) != 1+len(source) or any(interval(v)[0] > v[1] for v in derivatives):
                raise ValueError("common-normal source derivatives are incomplete")
            if derivatives[0][1] >= 0:
                raise ValueError("continuous supported branch has non-opposed gear rotation")
            moments = branch["common_normal_moments"]
            if len(moments) != 2 or not (
                    interval(moments[0])[1] < 0 < interval(moments[1])[0]
                    or interval(moments[1])[1] < 0 < interval(moments[0])[0]):
                raise ValueError("continuous normals have no actual opposed shaft moments")
            margins = branch["support_margins"]
            if not {"opposed_nonzero_normal_cones","normal_cross_pivot_nonzero"} <= margins.keys() or any(
                    interval(value)[0] <= 0 for value in margins.values()):
                raise ValueError("continuous chart lost finite physical support")
            strata = branch["physical_strata"]
            if strata.keys() != {"driver","driven"}:
                raise ValueError("generic callback roots are not physical stock-contact evidence")
            expected_margins = {"opposed_nonzero_normal_cones","normal_cross_pivot_nonzero"}
            cursor,implicit_tips = 0,0
            station_index = None
            for body,profile in (("driver",driver),("driven",driven)):
                stratum = strata[body]
                segment = physical_segments[body].get(stratum["segment"])
                if (segment is None or stratum["kind"] != segment.kind
                        or segment.kind not in ("flank","radial","tip_arc")
                        or type(stratum["tooth"]) is not int or not 0 <= stratum["tooth"] < profile.teeth):
                    raise ValueError("continuous chart substituted a nonphysical finite stratum")
                if body == "driver" and (profile.helix_angle_deg != 0 or segment.kind not in ("flank","radial")
                                         or segment._side != -closing_sense):
                    raise ValueError("first-contact inverse uses the wrong physical working side")
                t,z = stratum["t_fixed"],stratum["z_fixed"]
                face = case["placement"][f"{body}_face_mm"]
                cap = stratum["radial_cap_radius_mm"]
                shoulder = stratum["axial_cap_source"] == "driver_shoulder"
                actual_shoulder = case["placement"]["driver_shoulder_z_mm"]
                actual_cap = case["placement"]["driver_turned_radius_mm"]
                if (t not in (None,0.0,1.0)
                        or stratum["axial_cap_source"] not in ("face","driver_shoulder")
                        or shoulder and (body != "driver" or z != actual_shoulder
                                         or not face[0] < z < face[1] or not math.isfinite(actual_cap))
                        or not shoulder and z is not None and z not in face):
                    raise ValueError("fixed chart coordinate is not an actual finite face/shoulder")
                if cap is not None:
                    if (body != "driver" or segment.kind not in ("flank","radial")
                            or cap != actual_cap or not 0 < cap < profile.blank_radius_mm
                            or not face[0] < actual_shoulder < face[1]
                            or t is not None or stratum["incident_segments"] or shoulder
                            or z not in (None,face[1])
                            or stratum["radial_cap_source"] != "Placement.driver_turned_radius_mm"):
                        raise ValueError("turned-cap chart does not use the actual retained material cut")
                elif stratum["radial_cap_source"] is not None:
                    raise ValueError("uncapped chart invented a radial material constraint")
                incidents = stratum["incident_segments"]
                if len(incidents) != int(t is not None):
                    raise ValueError("finite junction lacks its actual adjacent segment")
                order = list(physical_segments[body])
                index = order.index(segment.name)
                for adjacent in incidents:
                    other = physical_segments[body].get(adjacent["segment"])
                    expected_index = index+1 if t == 1 else index-1
                    if (not 0 <= expected_index < len(order) or other is None
                            or other.name != order[expected_index] or adjacent["kind"] != other.kind
                            or other.kind not in ("flank","radial","tip_arc")
                            or "tip_arc" not in (segment.kind,other.kind)
                            or adjacent["parameter"] != (0.0 if t == 1 else 1.0)):
                        raise ValueError("normal cone substituted a nonadjacent physical surface")
                implicit = cap is not None or (t is not None and segment.kind in ("flank","radial") and any(
                    item["kind"] == "tip_arc" for item in incidents))
                if stratum["implicit_tip"] is not implicit:
                    raise ValueError("finite tip intersection metadata is inconsistent")
                implicit_tips += implicit
                if t is None or implicit:
                    label = "finite_master_tip" if implicit else "finite_t"
                    expected_margins.update((f"{body}_{label}_lower",f"{body}_{label}_upper"))
                    if cap is not None:
                        expected_margins.update((f"{body}_turned_cap_finite_t_lower",
                                                 f"{body}_turned_cap_finite_t_upper"))
                    coordinate = interval(box[cursor])
                    if implicit:
                        parameter = _bound_add((segment._a,segment._a),
                            _bound_multiply((segment._b-segment._a,)*2,coordinate))
                        master = ((profile.template.flank_parameter_min,profile.template.flank_parameter_max)
                                  if segment._shape == "flank" else
                                  (profile.template.root_radius_mm,profile.template.base_radius_mm))
                        if not contains(master,parameter,strict=True):
                            raise ValueError("implicit finite tip left its actual cutter master")
                    if (not implicit or cap is not None) and not contains((0.0,1.0),coordinate,strict=True):
                        raise ValueError("carrying root extended an actual finite native segment")
                    cursor += 1
                if z is None:
                    if not contains(face,box[cursor],strict=True):
                        raise ValueError("carrying root extended the actual finite face width")
                    if cap is not None and box[cursor][0] <= actual_shoulder:
                        raise ValueError("turned-cap root crossed the actual concave shoulder join")
                    expected_margins.update((f"{body}_finite_z_lower",f"{body}_finite_z_upper"))
                    if body == "driven":
                        station_index = cursor
                    cursor += 1
                count = 1+len(incidents)+int(z is not None)+int(cap is not None)
                expected_margins.update(f"{body}_normal_cone_weight_{i}" for i in range(count))
                weights = branch["normal_cone_weights"][0 if body == "driver" else 1]
                generators = branch["normal_cone_generators_world"][0 if body == "driver" else 1]
                if (len(weights) != count or len(generators) != count
                        or any(interval(weight)[0] <= 0 for weight in weights)
                        or not sum(v[0] for v in weights) <= 1 <= sum(v[1] for v in weights)
                        or any(len(v) != 3 or any(interval(c)[0] > c[1] for c in v) for v in generators)):
                    raise ValueError("continuous branch lacks its actual positive normal cone")
            if (math.isfinite(case["placement"]["driver_shoulder_z_mm"])
                    and math.isfinite(case["placement"]["driver_turned_radius_mm"])):
                if strata["driver"]["radial_cap_radius_mm"] is not None:
                    expected_margins.add("driver_turned_cap_above_actual_shoulder")
                elif strata["driver"]["axial_cap_source"] == "driver_shoulder":
                    expected_margins.add("driver_shoulder_edge_outside_actual_turned_radius")
                else:
                    expected_margins.add("driver_retained_unturned_or_turned_material")
            if (margins.keys() != expected_margins
                    or set(branch["required_support_margin_names"]) != expected_margins
                    or len(branch["required_support_margin_names"]) != len(expected_margins)
                    or len(unknown) != 5+implicit_tips
                    or branch["driven_angle_unknown_index"] != cursor
                    or branch["driven_station_unknown_index"] != station_index
                    or strata["driven"]["tooth"] != tooth
                    or branch["unknown_angle_coordinate"] != "driven_material"
                    or branch["root_component_coordinate"] != cover["angle_coordinate"]
                    or not _same_numeric_tree(branch["driven_material_phase_enclosure_rad"],box[cursor])):
                raise ValueError("physical branch coordinate/support manifest is incomplete")
            material = interval(branch["driven_material_phase_enclosure_rad"])
            beta = interval(branch["driven_phase_enclosure_rad"])
            clock = source.get("driven_clock_rad",(0.0,0.0))
            if not contains(beta,_bound_subtract(material,clock)):
                raise ValueError("physical root dropped its same-source material-clock map")
            if "driven_clock_rad" in source:
                index = branch["parameter_names"].index("driven_clock_rad")
                if not contains(derivatives[index],(-1.0,-1.0)):
                    raise ValueError("material-angle gauge dropped the physical clock sensitivity")
            member = material if cover["angle_coordinate"] == "driven_material" else beta
            component = branch["root_free_component_rad"]
            if (not contains(approach,member) or not contains(component,member)
                    or not any(_same_numeric_tree(component,c) for c in cover["root_free_driven_components_rad"])
                    or closing_sense == 1 and reference[1] >= member[0]
                    or closing_sense == -1 and reference[0] <= member[1]):
                raise ValueError("supported branch lacks a same-coordinate root-free approach from actual air")
            centre_box = branch["center_root_box"]
            centre_phase = phase[0]/2+phase[1]/2
            centre_source = {key:[v[0]/2+v[1]/2]*2 for key,v in source.items()}
            centre_clock = clock[0]/2+clock[1]/2
            if (not _same_numeric_tree(branch["center_phase_cell_rad"],[centre_phase,centre_phase])
                    or not _same_numeric_tree(branch["center_source_pose"],centre_source)
                    or not 0 <= branch["center_contraction_upper"] < 1
                    or len(centre_box) != len(unknown)
                    or not all(contains(a,b,strict=True) for a,b in zip(unknown,centre_box))
                    or not contains(branch["center_driven_phase_enclosure_rad"],
                                    _bound_subtract(centre_box[cursor],(centre_clock,centre_clock)))):
                raise ValueError("same-source difference substituted an unproved numerical centre root")
            minimum_error = 0.0
            for body,profile in (("driver",driver),("driven",driven)):
                frame = case["placement"][f"{body}_frame"]
                norm_lower = math.nextafter(math.hypot(*(v for row in frame for v in row)),-math.inf)
                minimum_error = math.nextafter(minimum_error+norm_lower*profile.geometry_error_bound_mm,-math.inf)
            if branch["geometry_error_bound_mm"] < minimum_error:
                raise ValueError("branch discarded the actual finite-profile position enclosure")
        carrier_rows = {item["chart"]:item for item in cell["carrier_comparisons"]}
        if carrier_rows.keys() != names or len(carrier_rows) != len(cell["carrier_comparisons"]):
            raise ValueError("coverage omitted same-pose first-carrier comparisons")
        counted,uniformly_first = set(),set()
        payments = {name:geometry_payment(branch,minima[name]) for name,branch in branch_by_name.items()}
        for name,candidate in branch_by_name.items():
            receipt = carrier_rows[name]
            comparisons = {item["competitor_chart"]:item for item in receipt["same_pose_comparisons"]}
            if (comparisons.keys() != names-{name}
                    or len(comparisons) != len(receipt["same_pose_comparisons"])
                    or receipt["driven_tooth"] != candidate["driven_tooth"]):
                raise ValueError("coverage missed an actual common-normal competitor")
            eligible,first = True,True
            for competitor_name,comparison in comparisons.items():
                competitor = branch_by_name[competitor_name]
                delta = _bound_multiply((closing_sense,closing_sense),
                                       same_pose_difference(competitor,candidate,phase))
                a,b = payments[name],payments[competitor_name]
                error = _bound_add((a,a),(b,b))
                claimed_delta = interval(comparison["closing_root_excess_rad"])
                claimed_error = interval(comparison["physical_geometry_error_payment_rad"])
                if not contains(claimed_delta,delta) or not contains(claimed_error,error):
                    raise ValueError("coverage dropped correlated root spread or actual profile-error payment")
                excess = _bound_add((claimed_delta[1],claimed_delta[1]),claimed_error)
                paid_upper = _bound_multiply((driven.pitch_radius_mm,driven.pitch_radius_mm),excess)[1]
                if comparison["pitch_excess_upper_mm"] < paid_upper:
                    raise ValueError("coverage understated its same-pose driven-pitch separation")
                eligible &= comparison["pitch_excess_upper_mm"] <= HANDOVER_JUMP_MAX_MM
                first &= _bound_add((delta[1],delta[1]),error)[1] <= 0
            if type(receipt["eligible"]) is not bool or receipt["eligible"] != eligible:
                raise ValueError("coverage counts a deeper uncarried stationary root")
            if eligible:
                counted.add(candidate["driven_tooth"])
            if first:
                uniformly_first.add(name)
        if not counted or cell["counted_teeth"] != sorted(counted):
            raise ValueError("continuous cell has no admissible first/paid carrying tooth")
        width = _bound_subtract((phase[1],phase[1]),(phase[0],phase[0]))
        integral = _bound_add(integral,_bound_multiply((len(counted),len(counted)),width))
        validated_cells.append((phase,branch_by_name,uniformly_first))
    reciprocal = (math.nextafter(1/pitch,-math.inf),math.nextafter(1/pitch,math.inf))
    coverage = _bound_multiply(integral,reciprocal)[0]
    if previous != pitch or proof["stock_form_coverage_lower"] > coverage:
        raise ValueError("coverage exceeds the distinct first/paid supported-tooth phase union")
    for row in proof["row_branch_spans"]:
        first,last = row["first_cell_index"],row["last_cell_index"]
        if type(first) is not int or type(last) is not int or not 0 <= first <= last < len(validated_cells):
            raise ValueError("row image names an invalid continuous phase span")
        name = row["chart"]
        span = validated_cells[first:last+1]
        if (not _same_numeric_tree(row["phase_endpoints_rad"],[span[0][0][0],span[-1][0][1]])
                or any(name not in actual_first for _,_,actual_first in span)):
            raise ValueError("row image is not a uniformly first carrying branch throughout its span")
        for left,right in zip(span,span[1:]):
            a,b = left[1][name],right[1][name]
            if (not _same_numeric_tree(a["physical_strata"],b["physical_strata"])
                    or not (all(contains(x,y) for x,y in zip(a["unknown_domain"],b["root_box"],strict=True))
                            or all(contains(x,y) for x,y in zip(b["unknown_domain"],a["root_box"],strict=True)))):
                raise ValueError("row span jumped between distinct contact roots or physical strata")
        stations = []
        for endpoint,key,entry in ((span[0][0][0],"left_branch_proof",span[0]),
                                   (span[-1][0][1],"right_branch_proof",span[-1])):
            end,parent = row[key],entry[1][name]
            for field in ("proof_schema","status","native_certificate","chart","driven_tooth",
                          "same_source_pose","parameter_names","physical_strata","unknown_domain",
                          "unknown_angle_coordinate","root_component_coordinate",
                          "driven_station_unknown_index","driven_angle_unknown_index"):
                if not _same_numeric_tree(end[field],parent[field]):
                    raise ValueError("row endpoint is not the same physical-source contact chart")
            box = end["root_box"]
            if (not _same_numeric_tree(end["phase_cell_rad"],[endpoint,endpoint])
                    or not 0 <= end["contraction_upper"] < 1
                    or len(box) != len(parent["unknown_domain"])
                    or not all(contains(a,b,strict=True) for a,b in zip(parent["unknown_domain"],box))):
                raise ValueError("row endpoint lacks an actual numerical root inclusion")
            index = parent["driven_station_unknown_index"]
            station = interval(box[index]) if index is not None else (parent["physical_strata"]["driven"]["z_fixed"],)*2
            stations.append(station)
        a,b = stations
        inner = ([a[1],b[0]] if a[1] < b[0] else [b[1],a[0]] if b[1] < a[0] else None)
        if inner is None or not contains(inner,row["inner_station_interval_mm"]):
            raise ValueError("row claim exceeds the same-branch continuous INNER station image")
        guaranteed_rows.append(interval(row["inner_station_interval_mm"]))
    merged = []
    for lo,hi in sorted(guaranteed_rows):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1],hi)
        else:
            merged.append([lo,hi])
    for low,high in proof["row_available_intervals_mm"]:
        if not any(a <= low < high <= b for a,b in merged):
            raise ValueError("row occupancy uses an OUTER/root-box width instead of a continuous inner image")
    if operating and (case["stock_form_coverage_lower"] != proof["stock_form_coverage_lower"]
                      or not _same_numeric_tree(case["row_available_intervals_mm"],proof["row_available_intervals_mm"])):
        raise ValueError("published coverage/row differs from the actual operating-direction proof")


def _require_continuous_contact(case, domain, driver, driven) -> None:
    proofs = case["continuous_contact_proofs"]
    if proofs.keys() != {"lower","upper"} or case["operating_driver_sense"] not in (-1,1):
        raise ValueError("continuous loaded proof omits a physical direction")
    for side,sense in (("lower",1),("upper",-1)):
        _require_continuous_side(case,domain,driver,driven,proofs[side],
                                closing_sense=sense,operating=case["operating_driver_sense"] == sense)



def _qualified_payload(payload: dict | None = None) -> dict:
    """Refuse stale/incomplete evidence, with every unchanged floor enforced."""
    payload = CALIBRATION if payload is None else payload
    if not payload["qualified"]:
        raise ValueError(payload["refusal"])
    if payload["geometry_sha256"] != geometry_sha256():
        raise ValueError("actual stock-form calibration geometry identity is stale")
    sources = payload["measurement_engine_sources_sha256"]
    expected_sources = {
        "crank_mesh_backlash_study.py","crossed_mesh_study.py",
        "stock_form_contact_3d.py","stock_form_root_angles.py",
        "stock_form_root_sweep.py","stock_form_contact_continuation.py",
    }
    if not isinstance(sources,dict) or sources.keys() != expected_sources or any(
        not isinstance(value,str) or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in sources.values()
    ):
        raise ValueError("actual3D calibration lacks its complete measurement-engine identity")
    engine_digest = hashlib.sha256(
        json.dumps(sources,sort_keys=True,separators=(",",":")).encode()
    ).hexdigest()
    if payload["measurement_engine_sha256"] != engine_digest:
        raise ValueError("actual3D measurement-engine provenance is inconsistent")
    # Collection/central publication compares these bytes to the deployed
    # diagnostic engine. Native consumers never import or read that engine.
    cases = payload["cases"]
    required = required_calibration_case_names()
    if required != cases.keys():
        raise ValueError("actual3D calibration lacks the complete source-owned corner family")
    placements = geometry.calibration_case_placements()
    parameters = {row["name"]:row for row in geometry.calibration_case_parameters()}
    drivers = dict(geometry.pinion.STOCK_PROFILE_CORNERS,nominal=geometry.pinion.STOCK_PROFILE)
    driven = dict(geometry.gear64.STOCK_PROFILE_CORNERS,nominal=geometry.gear64.STOCK_PROFILE)
    def profile_record(profile):
        return {"teeth":profile.teeth,"reference_teeth":profile.template.reference_teeth,
                "dp":profile.template.diametral_pitch,"pa_deg":profile.template.pressure_angle_deg,
                "blank_radius_mm":profile.blank_radius_mm,"radial_translation_mm":profile.radial_translation_mm,
                "helix_angle_deg":profile.helix_angle_deg}
    for name,case in cases.items():
        if not _finite_tree(case):
            raise ValueError(f"{name}: actual3D payload contains missing or nonfinite evidence")
        if not _same_numeric_tree(case["placement"],placements[name]):
            raise ValueError(f"{name}: measured placement differs from its source-owned physical corner")
        source = parameters[name]
        domain = source["pose_domain"]
        if not _same_numeric_tree(case["pose_domain"],domain):
            raise ValueError(f"{name}: continuous pose domain differs from the source grades")
        for field,profile in (
            ("driver_profile",drivers[source["driver_profile_label"]]),
            ("driven_profile",driven[source["driven_profile_label"]]),
        ):
            if not _same_numeric_tree(case[field],profile_record(profile)):
                raise ValueError(f"{name}: measured {field} is not the source-owned manufactured corner")
        if case["metric"] != "STOCK-FORM COVERAGE" or case["is_conjugate"] or case["native_certificate"]:
            raise ValueError(f"{name}: actual3D evidence is mislabelled")
        if case["uncovered_phase_rad"] != 0.0:
            raise ValueError(f"{name}: an actual carrying phase gap remains")
        bounds = case["numerical_error_bounds"]
        if not {"surface_mm","phase_motion_mm","te_rad"} <= bounds.keys() or any(value < 0.0 for value in bounds.values()):
            raise ValueError(f"{name}: invalid numerical error payment")
        for field in ("radial","axial"):
            if not math.isclose(bounds[f"{field}_mm"],domain[f"{field}_error_mm"],rel_tol=0.0,abs_tol=1e-12):
                raise ValueError(f"{name}: {field} pose-grade uncertainty is unpaid")
        if case["loose_backlash_upper_mm"] < case["tight_backlash_lower_mm"]:
            raise ValueError(f"{name}: backlash interval is inverted")
        if not case["qualified"] or not case["tight_backlash_lower_mm"] > POSITIVE_BACKLASH_MIN_MM:
            raise ValueError(f"{name}: actual3D positive backlash is not qualified")
        if case["stock_form_coverage_lower"] < STOCK_FORM_COVERAGE_MIN:
            raise ValueError(f"{name}: STOCK-FORM COVERAGE is below .62")
        if case["row_available_fraction_lower"] < ROW_ENGAGEMENT_MIN:
            raise ValueError(f"{name}: actual supported row is below .85")
        if not case["continuous_carrying_contact"]:
            raise ValueError(f"{name}: a supported continuous carrying branch is absent")
        _require_continuous_contact(
            case,domain,drivers[source["driver_profile_label"]],driven[source["driven_profile_label"]],
        )
        if any(not handover["continuous"] or not 0.0 <= handover["pitch_displacement_jump_upper_mm"] <= HANDOVER_JUMP_MAX_MM
               for handover in case["handovers"]):
            raise ValueError(f"{name}: actual driven-pitch handover exceeds .005 mm")
        face_low,face_high = case["placement"]["driven_face_mm"]
        end = face_low
        covered = 0.0
        for low,high in case["row_available_intervals_mm"]:
            if not face_low <= low < high <= face_high or low < end:
                raise ValueError(f"{name}: row intervals overlap or exceed the physical face")
            covered += high-low
            end = high
        if not 0.0 <= case["row_available_fraction_lower"] <= covered/(face_high-face_low)+1e-12:
            raise ValueError(f"{name}: claimed row fraction exceeds supported station intervals")
        phases = case["phase_rows"]
        if len(phases) < 65 or phases[0]["driver_phase_rad"] != 0.0 or not math.isclose(
            phases[-1]["driver_phase_rad"],2*math.pi/geometry.pinion.TEETH,abs_tol=1e-12
        ):
            raise ValueError(f"{name}: actual study does not span one whole tooth pitch")
        phase_step = (phases[-1]["driver_phase_rad"]-phases[0]["driver_phase_rad"])/(len(phases)-1)
        previous = -math.inf
        for phase_index,row in enumerate(phases):
            if row["driver_phase_rad"] <= previous or row["error_rad"] < 0.0:
                raise ValueError(f"{name}: phase extrema are unordered or unbounded")
            previous = row["driver_phase_rad"]
            if not math.isclose(row["driver_phase_rad"],phase_index*phase_step,rel_tol=0.0,abs_tol=1e-12):
                raise ValueError(f"{name}: phase cells are not the uniformly bounded study grid")
            if row["root_contact"] or row["upper_rad"]-row["lower_rad"] <= 2*row["error_rad"]:
                raise ValueError(f"{name}: phase row has root contact or no positive free window")
            if row["phase_error_rad"] <= 0.0:
                raise ValueError(f"{name}: whole-cell phase uncertainty is absent or nonpositive")
            if row["surface_numerical_resolved"] is not True:
                raise ValueError(f"{name}: achieved surface numerical residual is unresolved")
            extrema = row["surface_extrema_enclosures_rad"]
            if len(extrema) != 2 or {item["side"] for item in extrema} != {"lower","upper"}:
                raise ValueError(f"{name}: complete paid surface extrema are absent")
            for extremum in extrema:
                lo,hi = extremum["lower_rad"],extremum["upper_rad"]
                expected = -row["lower_rad"] if extremum["side"] == "lower" else row["upper_rad"]
                if (not lo <= hi or hi-lo > row["error_rad"]
                        or not math.isclose(hi,expected,rel_tol=0.0,abs_tol=1e-12)
                        or not 0.0 < extremum["numerical_tolerance_rad"] <= bounds["surface_mm"]/geometry.R16+1e-12):
                    raise ValueError(f"{name}: surface extremum width is not paid by the phase row")
                for field in ("radial","axial"):
                    if not math.isclose(extremum[f"{field}_pose_error_mm"],domain[f"{field}_error_mm"],rel_tol=0.0,abs_tol=1e-12):
                        raise ValueError(f"{name}: surface extremum dropped an irreducible pose grade")
                branch_ids = set()
                for tooth,low,high in extremum["branches"]:
                    if (type(tooth) is not int or not 0 <= tooth < geometry.gear64.TEETH
                            or tooth in branch_ids or not lo <= low <= high
                            or high-low > row["error_rad"]):
                        raise ValueError(f"{name}: invalid paid physical branch enclosure")
                    branch_ids.add(tooth)
                for tooth,low in extremum["unwitnessed_branch_lower_rad"]:
                    if (type(tooth) is not int or not 0 <= tooth < geometry.gear64.TEETH
                            or tooth in branch_ids or low < lo):
                        raise ValueError(f"{name}: unwitnessed physical branch was discarded")
                    branch_ids.add(tooth)
                numerics = extremum["branch_numerics"]
                if len(numerics) != len(branch_ids) or {item["tooth"] for item in numerics} != branch_ids:
                    raise ValueError(f"{name}: numerical residual omits a physical branch")
                branch_lowers = {tooth:low for tooth,low,_ in extremum["branches"]}
                branch_lowers.update(extremum["unwitnessed_branch_lower_rad"])
                if (not numerics or any(item["lower_rad"] != branch_lowers[item["tooth"]] for item in numerics)
                        or lo != min(branch_lowers.values())
                        or extremum["relaxed_incumbent_rad"] != min(item["relaxed_incumbent_rad"] for item in numerics)):
                    raise ValueError(f"{name}: numerical residual is detached from its actual branch bounds")
                for proof in (extremum,*numerics):
                    residual = max(0.0,proof["relaxed_incumbent_rad"]-proof["lower_rad"])
                    if (not math.isclose(proof["achieved_residual_rad"],residual,rel_tol=0.0,abs_tol=1e-12)
                            or not 0.0 <= proof["achieved_residual_rad"] <= extremum["numerical_tolerance_rad"]):
                        raise ValueError(f"{name}: achieved numerical residual exceeds its surface payment")
                    terminals,terminal_lower = proof["terminal_boxes"],proof["terminal_lower_rad"]
                    if (type(terminals) is not int or terminals < 0
                            or (terminals == 0) != (terminal_lower is None)
                            or (terminals > 0 and terminal_lower < proof["lower_rad"])):
                        raise ValueError(f"{name}: terminal surface bounds were discarded")
            root = row["root_sweep"]
            required_root_fields = {
                "free_inner","free_outer","offset_domain_rad","status",
                "geometric_uncertainty_mm","required_root_air_mm","root_air_lower_bound_mm",
                "native_solid_certificate","root_is_carrying",
            }
            if not required_root_fields <= root.keys():
                raise ValueError(f"{name}: incomplete actual root-surface proof")
            if (root["status"] != "resolved" or root["root_is_carrying"]
                    or root["native_solid_certificate"]
                    or root["required_root_air_mm"] != domain["required_root_air_mm"]
                    or root["root_air_lower_bound_mm"] < root["required_root_air_mm"]
                    or not 0.0 <= root["geometric_uncertainty_mm"] <= bounds["root_surface_mm"]
                    or bounds["root_surface_mm"] > bounds["surface_mm"]):
                raise ValueError(f"{name}: actual noncarrying root/air enclosure is not qualified")
            common_low,common_high = payload["phase_window_rad"]
            for components in (row["free_intervals_rad"],row["root_free_intervals_rad"],
                               root["free_inner"],root["free_outer"]):
                if not any(low <= common_low < common_high <= high for low,high in components):
                    raise ValueError(f"{name}: common physical clock leaves a paid free component")
            if not root["offset_domain_rad"][0] <= common_low < common_high <= root["offset_domain_rad"][1]:
                raise ValueError(f"{name}: common clock is outside the proven root-offset domain")
            pitch_domain = (-math.pi/geometry.pinion.TEETH,math.pi/geometry.pinion.TEETH)
            if not _same_numeric_tree(root["offset_domain_rad"],pitch_domain):
                raise ValueError(f"{name}: root proof omits part of the physical pitch domain")
            _require_components(root["free_outer"],pitch_domain)
            _require_components(root["free_inner"],pitch_domain,contained_in=root["free_outer"])
            _require_components(row["root_free_intervals_rad"],pitch_domain,contained_in=root["free_inner"])
            _require_components(row["free_intervals_rad"],pitch_domain,contained_in=row["root_free_intervals_rad"])
            branch_proofs = row["supported_branch_contacts"]
            proof_teeth = {proof["tooth"] for proof in branch_proofs}
            if len(proof_teeth) != len(branch_proofs):
                raise ValueError(f"{name}: duplicate supported-branch identity")
            branch_contacts = []
            for proof in branch_proofs:
                if not proof["contacts"] or any(
                    item["side"] not in ("lower","upper")
                    or item["contact"]["driven_tooth"] != proof["tooth"]
                    for item in proof["contacts"]
                ):
                    raise ValueError(f"{name}: supported branch lacks its actual normal proof")
                branch_contacts.extend(item["contact"] for item in proof["contacts"])
            reserves = dict(row["branch_phase_reserves_rad"])
            if not reserves.keys() <= proof_teeth:
                raise ValueError(f"{name}: branch reserve has no genuine working common normal")
            for contact in [row["lower_contact"],row["upper_contact"],*branch_contacts]:
                if not isinstance(contact,dict) or any(term in contact["kind"] for term in ("root_arc","root_corner","axial_face","axial_interior")):
                    raise ValueError(f"{name}: contact is absent or outside working surface support")
                if (not contact["common_normal_supported"]
                        or contact["common_normal_error_bound"] < 0.0
                        or contact["opposed_normal_residual"] > contact["common_normal_error_bound"]
                        or not math.isfinite(contact["driven_per_driver_velocity"])
                        or contact["driven_per_driver_velocity"] >= 0.0):
                    raise ValueError(f"{name}: no bounded actual common-normal carrying contact")
                for field in ("world_point_mm","driven_normal_world","driver_normal_world"):
                    if len(contact[field]) != 3 or not _finite_tree(contact[field]):
                        raise ValueError(f"{name}: contact {field} is not a finite3D vector")
                normal_driver,normal_driven = contact["driver_normal_world"],contact["driven_normal_world"]
                arithmetic = 128*math.ulp(1.0)
                if any(abs(math.sqrt(sum(value*value for value in normal))-1.0) > arithmetic
                       for normal in (normal_driver,normal_driven)):
                    raise ValueError(f"{name}: common-normal evidence contains a non-unit vector")
                residual = math.sqrt(sum((a+b)**2 for a,b in zip(normal_driver,normal_driven)))
                if abs(residual-contact["opposed_normal_residual"]) > arithmetic:
                    raise ValueError(f"{name}: common-normal residual does not match its actual vectors")
        for side in ("lower","upper"):
            key = f"{side}_contact"
            # One driver pitch turns the mate by minus one physical tooth
            # pitch. Compare cyclic support after that exact tooth relabel.
            if ((phases[-1][key]["driven_tooth"]-phases[0][key]["driven_tooth"])
                    % geometry.gear64.TEETH != 1):
                raise ValueError(f"{name}: {side} carrying identity fails cyclic tooth-pitch closure")
        case_low,case_high = case["phase_window_rad"]
        if not any(low <= case_low < case_high <= high for low,high in case["phase_components_rad"]):
            raise ValueError(f"{name}: selected phase window is not in a complete-period free component")
        if not case_low < math.radians(payload["phase_seed_deg"]) < case_high:
            raise ValueError(f"{name}: assembly seed is outside the actual case phase window")
        common_low,common_high = payload["phase_window_rad"]
        if not case_low <= common_low < common_high <= case_high:
            raise ValueError(f"{name}: common phase window exceeds this manufactured corner")
    low,high = payload["phase_window_rad"]
    if not low < math.radians(payload["phase_seed_deg"]) < high:
        raise ValueError("printed assembly phase seed is outside the qualified common window")
    return payload


def require_qualified(payload: dict | None = None) -> dict:
    """Validate complete source-bound evidence or raise a deliberate refusal."""
    try:
        return _qualified_payload(payload)
    except (KeyError,TypeError,IndexError,AttributeError) as exc:
        raise ValueError(f"incomplete actual3D stock-form calibration payload: {exc}") from exc


@dataclass(frozen=True)
class RowQualification:
    case_name: str
    driver_face_mm: tuple[float,float]
    driver_shoulder_z_mm: float
    driver_turned_radius_mm: float
    driven_face_mm: tuple[float,float]
    driver_origin_mm: tuple[float,float,float]
    driven_origin_mm: tuple[float,float,float]
    driver_frame: tuple[tuple[float,float,float],...]
    driven_frame: tuple[tuple[float,float,float],...]
    supported_driven_station_intervals_mm: tuple[tuple[float,float],...]
    row_fraction_lower: float
    coverage_lower: float
    continuous_carrier: bool


def row_qualification(case_name: str) -> RowQualification:
    """Read a measured physical row case; never interpolate an unstudied pose."""
    payload = require_qualified()
    try:
        case = payload["cases"][case_name]
    except KeyError as exc:
        raise ValueError(f"no actual3D row qualification for {case_name!r}") from exc
    pose = case["placement"]
    return RowQualification(
        case_name,tuple(pose["driver_face_mm"]),pose["driver_shoulder_z_mm"],
        pose["driver_turned_radius_mm"],tuple(pose["driven_face_mm"]),
        tuple(pose["driver_origin_mm"]),tuple(pose["driven_origin_mm"]),
        tuple(tuple(row) for row in pose["driver_frame"]),
        tuple(tuple(row) for row in pose["driven_frame"]),
        tuple(tuple(interval) for interval in case["row_available_intervals_mm"]),
        case["row_available_fraction_lower"],case["stock_form_coverage_lower"],
        case["continuous_carrying_contact"],
    )


# None means unavailable, never zero. Callers must require_qualified() before
# using these manufacturing values; a refused design cannot silently build.
if CALIBRATION["qualified"]:
    require_qualified()
    NOMINAL_TIGHT_BACKLASH_MM = CALIBRATION_CASES["nominal"]["tight_backlash_lower_mm"]
    TIGHT_BACKLASH_MM = min(case["tight_backlash_lower_mm"] for case in CALIBRATION_CASES.values())
    STOCK_FORM_COVERAGE_NOMINAL = CALIBRATION_CASES["nominal"]["stock_form_coverage_lower"]
    STOCK_FORM_COVERAGE_WORST = min(case["stock_form_coverage_lower"] for case in CALIBRATION_CASES.values())
    ROW_ENGAGEMENT_FRACTION_WORST = min(case["row_available_fraction_lower"] for case in CALIBRATION_CASES.values())
    CONTINUOUS_CARRYING_CONTACT = True
    MAX_HANDOVER_JUMP_MM = max((handover["pitch_displacement_jump_upper_mm"] for case in CALIBRATION_CASES.values() for handover in case["handovers"]),default=0.0)
    PHASE_WINDOW_RAD = tuple(CALIBRATION["phase_window_rad"])
    MESH_WINDOW_CENTRE_DEG = CALIBRATION["phase_seed_deg"]
else:
    NOMINAL_TIGHT_BACKLASH_MM = None
    TIGHT_BACKLASH_MM = None
    STOCK_FORM_COVERAGE_NOMINAL = None
    STOCK_FORM_COVERAGE_WORST = None
    ROW_ENGAGEMENT_FRACTION_WORST = None
    CONTINUOUS_CARRYING_CONTACT = False
    MAX_HANDOVER_JUMP_MM = None
    PHASE_WINDOW_RAD = None
    MESH_WINDOW_CENTRE_DEG = None


def stack_text() -> str:
    payload = require_qualified()
    return "\n".join((
        f"actual stock-form crossed crank C {FRAME_C2C:.5f} mm",
        f"worst positive backlash {TIGHT_BACKLASH_MM:.6f} mm",
        f"STOCK-FORM COVERAGE {STOCK_FORM_COVERAGE_WORST:.6f}; row {ROW_ENGAGEMENT_FRACTION_WORST:.6f}",
        f"continuous carrying handover <= {MAX_HANDOVER_JUMP_MM:.6f} mm driven pitch displacement",
        f"geometry identity {payload['geometry_sha256']}",
        "offline3D design qualification; native assembly interference gate still required",
    ))
