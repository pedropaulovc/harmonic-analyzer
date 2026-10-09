"""Pure replay of finite-stock contact certificates; never import a solver or parts.

Geometry/source domains and acceptance floors are supplied by their native owner.
This receiver does not generate measurements and is not a measurement-engine source.
"""
from __future__ import annotations

import math


def same_numeric_tree(actual, expected) -> bool:
    if isinstance(expected,dict):
        return isinstance(actual,dict) and actual.keys() == expected.keys() and all(
            same_numeric_tree(actual[key],value) for key,value in expected.items())
    if isinstance(expected,(tuple,list)):
        return isinstance(actual,(tuple,list)) and len(actual) == len(expected) and all(
            same_numeric_tree(a,b) for a,b in zip(actual,expected))
    if isinstance(expected,bool):
        return actual is expected
    if isinstance(expected,(float,int)):
        return type(actual) in (float,int) and math.isfinite(actual) and actual == expected
    return actual == expected


def finite_evidence(value) -> bool:
    if isinstance(value,(float,int)):
        return math.isfinite(value)
    if isinstance(value,dict):
        return all((key in ("root_max_radial_clearance_screen_mm","terminal_lower_rad",
                            "t_fixed","z_fixed","driven_station_unknown_index",
                            "radial_cap_radius_mm","radial_cap_source",
                            "driver_shoulder_z_mm","driver_turned_radius_mm",
                            "installed_axis_acceptance","datum_tare_rad",
                            "source_driver_retained_band_limits_mm") and item is None)
                   or finite_evidence(item) for key,item in value.items())
    if isinstance(value,(tuple,list)):
        return all(finite_evidence(item) for item in value)
    return value is not None


def require_components(components, domain, *, contained_in=None) -> None:
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


def _bound_divide(a, b):
    if b[0] <= 0 <= b[1]:
        raise ValueError("certificate division interval contains zero")
    if b[0] == b[1] == 1:
        return a
    return _bound_multiply(a,(math.nextafter(1/b[1],-math.inf),math.nextafter(1/b[0],math.inf)))


def _bound_sum(values):
    result = (0.0,0.0)
    for value in values:
        result = _bound_add(result,value)
    return result


def _bound_sqrt(value):
    if not all(math.isfinite(v) for v in value) or value[0] > value[1]:
        raise ValueError("certificate square-root endpoints must be finite and ordered")
    if value[0] < 0:
        raise ValueError("certificate square-root interval is negative")
    if value[1] == 0:
        return (0.0,0.0)
    lower_numerator, lower_denominator = value[0].as_integer_ratio()
    upper_numerator, upper_denominator = value[1].as_integer_ratio()
    low = max(0.0,math.nextafter(math.sqrt(value[0]),-math.inf))
    high = math.nextafter(math.sqrt(value[1]),math.inf)
    # Same exact dyadic-square certificates as the measuring helper: floating
    # outward products cannot certify endpoints efficiently under underflow.
    while low:
        numerator, denominator = low.as_integer_ratio()
        if numerator*numerator*lower_denominator <= lower_numerator*denominator*denominator:
            break
        low = math.nextafter(low,-math.inf)
    while True:
        numerator, denominator = high.as_integer_ratio()
        if numerator*numerator*upper_denominator >= upper_numerator*denominator*denominator:
            break
        high = math.nextafter(high,math.inf)
    return low,high


def _bound_squared_norm(values):
    squares = []
    for value in values:
        low = 0.0 if value[0] <= 0 <= value[1] else min(abs(v) for v in value)
        high = max(abs(v) for v in value)
        squares.append((max(0.0,_bound_multiply((low,low),(low,low))[0]),
                        _bound_multiply((high,high),(high,high))[1]))
    total = _bound_sum(squares)
    return max(0.0,total[0]),total[1]


def _bound_trig(angle,cosine=False):
    """Independent outward replay of the finite Taylor/remainder receipt."""
    pi = (3.141592653589793,3.1415926535897936)
    turns = round(angle/(2*math.pi))
    reduced = _bound_subtract((angle,angle),_bound_multiply((2*turns,)*2,pi))
    squared = _bound_multiply(reduced,reduced)
    term = (1.0,1.0) if cosine else reduced
    total = term
    for k in range(1,25):
        denominator = (2*k-1)*(2*k) if cosine else (2*k)*(2*k+1)
        term = _bound_divide(_bound_multiply((-term[1],-term[0]),squared),(denominator,denominator))
        total = _bound_add(total,term)
    remainder = (1.0,1.0)
    magnitude = max(abs(v) for v in reduced)
    for k in range(1,50 if cosine else 51):
        remainder = _bound_divide(_bound_multiply(remainder,(magnitude,magnitude)),(k,k))
    result = _bound_add(total,(-remainder[1],remainder[1]))
    return max(-1.0,result[0]),min(1.0,result[1])


def _periodic_source_evidence(driver,driven,placement,source):
    steps = math.lcm(driver.teeth,driven.teeth)
    turn = _bound_multiply((3.141592653589793,3.1415926535897936),(2.0,2.0))
    bodies,rotations = {},{}
    total = (0.0,0.0)
    for body,profile,sign in (("driver",driver,1),("driven",driven,-1)):
        pitch = profile.angular_pitch_rad
        errors = []
        for tooth in range(profile.teeth):
            mapped = (tooth+sign)%profile.teeth
            before,after = (tooth,mapped) if sign == 1 else (mapped,tooth)
            delta = _bound_subtract(_bound_add((pitch,pitch),(before*pitch,)*2),(after*pitch,)*2)
            if sign == 1 and mapped == 0 or sign == -1 and tooth == 0:
                delta = _bound_subtract(delta,turn)
            errors.append(delta)
        c,s = _bound_trig(pitch,True),_bound_trig(pitch)
        a,b = ((c,(-s[1],-s[0])),(s,c)),((c,s),((-s[1],-s[0]),c))
        closure = tuple(_bound_subtract(_bound_sum(_bound_multiply(a[i][k],b[k][j]) for k in range(2)),
                                         (int(i==j),)*2) for i in range(2) for j in range(2))
        norm = _bound_sqrt(_bound_squared_norm(tuple((max(abs(v) for v in value),)*2 for value in closure)))
        eccentricity = _bound_sqrt(_bound_squared_norm(tuple(source.get(f"{body}_ecc_{axis}_mm",(0.0,0.0))
                                                                  for axis in ("x","y"))))
        frame = _bound_sqrt(_bound_squared_norm(tuple(
            (v,v) for row in placement[f"{body}_frame"] for v in row)))
        radius = _bound_add((profile.blank_radius_mm,)*2,(profile.geometry_error_bound_mm,)*2)
        angle_error = max(abs(v) for value in errors for v in value)
        step = _bound_multiply(frame,_bound_add(
            _bound_multiply((angle_error,angle_error),_bound_add(radius,eccentricity)),
            _bound_multiply(norm,eccentricity)))
        displacement = _bound_multiply((steps,steps),step)
        total = _bound_add(total,(displacement[1],)*2)
        bodies[body] = {"tooth_relabel_angle_errors_rad":errors,"rotation_product_error":closure,
                        "frame_operator_upper":frame[1],"rectangular_eccentricity_radius_upper_mm":eccentricity[1],
                        "joint_period_tooth_steps":steps,"one_step_displacement_upper_mm":step[1],
                        "displacement_upper_mm":displacement[1]}
        c,s = _bound_trig(sign*pitch,True),_bound_trig(sign*pitch)
        rotations[body] = ((c,(-s[1],-s[0])),(s,c))
    return total[1],bodies,rotations


def _frame_distance_scale_limit(frame):
    """Replay the true-inverse nominal-frame metric, not approximate F.T."""
    rows = tuple(tuple((value,value) for value in row) for row in frame)
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        raise ValueError("physical frame is not three-dimensional")
    def cross(a,b):
        return tuple(_bound_subtract(_bound_multiply(a[(i+1)%3],b[(i+2)%3]),
                                     _bound_multiply(a[(i+2)%3],b[(i+1)%3])) for i in range(3))
    columns = cross(rows[1],rows[2]),cross(rows[2],rows[0]),cross(rows[0],rows[1])
    determinant = _bound_sum(_bound_multiply(a,b) for a,b in zip(rows[0],columns[0]))
    if determinant[0] <= 0:
        raise ValueError("stored physical frame has no positive determinant")
    inverse = tuple(tuple(_bound_divide(value,determinant) for value in row) for row in zip(*columns))
    gram = tuple(tuple(_bound_sum(_bound_multiply(inverse[k][i],inverse[k][j]) for k in range(3))
                       for j in range(3)) for i in range(3))
    squared = max(_bound_sum((max(abs(v[0]),abs(v[1])),)*2 for v in row)[1] for row in gram)
    norm = max(1.0,_bound_sqrt((squared,squared))[1])
    return _bound_divide((1.0,1.0),(norm,norm))[0]


def _profile_record(profile):
    return {"teeth":profile.teeth,"reference_teeth":profile.template.reference_teeth,
            "dp":profile.template.diametral_pitch,"pa_deg":profile.template.pressure_angle_deg,
            "blank_radius_mm":profile.blank_radius_mm,"radial_translation_mm":profile.radial_translation_mm,
            "helix_angle_deg":profile.helix_angle_deg}


def _patch_inventory(profile):
    return {f"{tooth}:{segment.name}{suffix}" for tooth in range(profile.teeth)
            for segment in profile.external_boundary_segments()
            for suffix in ("",":end_face:-1",":end_face:+1")}


def _require_material_sweep(receipt,driver,driven,placement,phase,source,approach,coordinate,
                            required_air,maximum_error,scope):
    """Admit the complete material/containment primitive, never boundary air."""
    raw = receipt["root_sweep"]
    inventory = _patch_inventory(driven)
    domain = (-driver.angular_pitch_rad/2,driver.angular_pitch_rad/2)
    expected_containment = ("driver-root axis point outside paid driven finite cylinder"
                            if scope == "driver_root_material"
                            else "driver-material axis point outside paid driven finite cylinder")
    scale = receipt["driver_local_to_world_distance_lower"]
    if (receipt["status"] != "PROVED" or receipt["native_certificate"] is not False
            or raw["status"] != "resolved" or raw["root_is_carrying"] is not False
            or raw["native_solid_certificate"] is not False
            or receipt["material_scope"] != scope or raw["material_scope"] != scope
            or raw["containment_proof"] != expected_containment
            or not same_numeric_tree(receipt["phase_cell_rad"],phase)
            or not same_numeric_tree(receipt["same_source_pose"],source)
            or receipt["angle_coordinate"] != coordinate
            or not same_numeric_tree(receipt["driven_angle_domain_rad"],approach)
            or receipt["physical_driven_teeth"] != list(range(driven.teeth))
            or raw["physical_driver_teeth"] != list(range(driver.teeth))
            or raw["physical_driven_teeth"] != list(range(driven.teeth))
            or set(receipt["physical_patch_inventory"]) != inventory
            or len(receipt["physical_patch_inventory"]) != len(inventory)
            or set(raw["physical_patch_inventory"]) != inventory
            or len(raw["physical_patch_inventory"]) != len(inventory)
            or not same_numeric_tree(raw["offset_domain_rad"],domain)
            or receipt["physical_required_root_air_mm"] != required_air
            or not 0 < scale <= _frame_distance_scale_limit(placement["driver_frame"])
            or raw["root_air_lower_bound_mm"] < raw["required_root_air_mm"]
            or receipt["physical_root_air_lower_bound_mm"] <= 0
            or receipt["physical_root_air_lower_bound_mm"] < required_air
            or receipt["physical_root_air_lower_bound_mm"] > _bound_multiply(
                (raw["root_air_lower_bound_mm"],)*2,(scale,scale))[0]
            or not 0 <= raw["geometric_uncertainty_mm"] <= maximum_error):
        raise ValueError("directed complete material/root/containment scope is not proved")
    require_components(raw["free_outer"],domain)
    require_components(raw["free_inner"],domain,contained_in=raw["free_outer"])
    require_components(receipt["inverse_offset_free_components_rad"],domain,contained_in=raw["free_inner"])
    if not any(a <= 0 <= b for a,b in receipt["inverse_offset_free_components_rad"]):
        raise ValueError("directed material query leaves actual all-component FREE INNER")
    if not same_numeric_tree(receipt["root_free_driven_components_rad"],[approach]):
        raise ValueError("directed material receipt does not certify its entire actual approach")


def _require_driven_root_material(receipt,case,domain,driver,driven,phase,source,approach):
    floor = domain["root_air_requirements_mm"]["driven"]
    placement = case["placement"]
    if (receipt["proof_schema"] != "finite-stock-directed-root-material/1"
            or receipt["status"] != "PROVED" or receipt["native_certificate"] is not False
            or receipt["physical_no_solution"] is not False
            or receipt["root_owner"] != "driven" or receipt["other_material_owner"] != "driver"
            or receipt["angle_coordinate"] != "driven_material"
            or receipt["required_root_air_mm"] != floor
            or not same_numeric_tree(receipt["phase_cell_rad"],phase)
            or not same_numeric_tree(receipt["same_source_pose"],source)
            or not same_numeric_tree(receipt["approach_driven_phase_rad"],approach)
            or not same_numeric_tree(receipt["source_driver_profile"],_profile_record(driver))
            or not same_numeric_tree(receipt["source_driven_profile"],_profile_record(driven))
            or not same_numeric_tree(receipt["source_placement"],placement)):
        raise ValueError("driven root-MATERIAL proof is not bound to the actual directed source query")
    if driven.helix_angle_deg == 0:
        if receipt["method"] != "reversed_actual_straight_root_sweep":
            raise ValueError("straight driven roots require their genuine reversed root sweep")
        qdriver,qdriven = driven,driver
        qplacement = {f"{body}_{field}":placement[f"{other}_{field}"]
                      for body,other in (("driver","driven"),("driven","driver"))
                      for field in ("origin_mm","frame","face_mm")}
        qplacement.update(driver_clocking_rad=0.0,driven_clocking_rad=0.0,
                          driver_shoulder_z_mm=None,driver_turned_radius_mm=None)
        relabel = {name:("driven_"+name[7:] if name.startswith("driver_") else "driver_"+name[7:])
                   for name in source if name != "driven_clock_rad"}
        qsource = {relabel[name]:value for name,value in source.items() if name in relabel}
        qphase = approach
        qapproach = _bound_add(phase,(placement["driver_clocking_rad"],)*2)
        scope,coordinate = "driver_root_material","physical"
        if (receipt["removed_material_clock_axis"] != "driven_clock_rad"
                or not same_numeric_tree(receipt["source_axis_relabel"],relabel)):
            raise ValueError("reverse root proof changed its actual material-phase/source coordinate map")
    else:
        if receipt["method"] != "actual_cutter_gapped_root_material_radial_enclosure":
            raise ValueError("helical driven roots lack the actual cutter-gapped material enclosure")
        subset = receipt["root_subset_enclosure"]
        radius = min(driven.blank_radius_mm,
                     _bound_add((driven.root_radius_max_mm,)*2,(driven.geometry_error_bound_mm,)*2)[1])
        if (subset["operation"] != "intersect actual finite stock material with a concentric local radial cylinder"
                or subset["source_root_radius_upper_mm"] != driven.root_radius_max_mm
                or subset["source_profile_geometry_error_mm"] != driven.geometry_error_bound_mm
                or subset["radial_clip_radius_mm"] != radius
                or subset["source_blank_radius_mm"] != driven.blank_radius_mm
                or subset["retained_teeth"] != driven.teeth
                or subset["retained_helix_angle_deg"] != driven.helix_angle_deg
                or not same_numeric_tree(subset["retained_face_interval_mm"],placement["driven_face_mm"])):
            raise ValueError("helical root subset lost its real clip/gaps/helix/finite faces")
        qdriver = driver
        qdriven = type(driven)(driven.teeth,driven.template,radius,driven.radial_translation_mm,driven.helix_angle_deg)
        qplacement,qphase,qsource,qapproach = placement,phase,source,approach
        scope,coordinate = "driver_full_material","driven_material"
    if (not same_numeric_tree(receipt["query_driver_profile"],_profile_record(qdriver))
            or not same_numeric_tree(receipt["query_driven_profile"],_profile_record(qdriven))
            or not same_numeric_tree(receipt["query_placement"],qplacement)
            or not same_numeric_tree(receipt["query_driver_phase_rad"],qphase)
            or not same_numeric_tree(receipt["query_driven_phase_rad"],qapproach)
            or not same_numeric_tree(receipt["query_source_pose"],qsource)):
        raise ValueError("directed root material query substituted geometry, face scope, or physical phase")
    _require_material_sweep(receipt["material_sweep"],qdriver,qdriven,qplacement,qphase,qsource,
                            qapproach,coordinate,floor,case["numerical_error_bounds"]["surface_mm"],scope)
    if receipt["root_air_lower_mm"] != receipt["material_sweep"]["physical_root_air_lower_bound_mm"]:
        raise ValueError("directed root air is not the actual complete material lower bound")


def _face_family_placements(reference,domain):
    support,material = dict(reference),dict(reference)
    widths,anchors = domain["finite_face_width_limits_mm"],domain["finite_face_anchor_fraction"]
    if set(widths) != {"driver","driven"} or set(anchors) != {"driver","driven"}:
        raise ValueError("finite source faces lack both width and physical anchor authorities")
    for body in ("driver","driven"):
        low,high = widths[body]
        fraction = anchors[body]
        old = reference[f"{body}_face_mm"]
        if (any(type(value) not in (int,float) or not math.isfinite(value) for value in (low,high,fraction))
                or not 0 < low <= old[1]-old[0] <= high or not 0 <= fraction <= 1):
            raise ValueError("unbound finite material/source face family")
        if low == high:
            continue
        anchor = old[0]+fraction*(old[1]-old[0])
        support[f"{body}_face_mm"] = [
            _bound_subtract((anchor,anchor),_bound_multiply((fraction,fraction),(low,low)))[1],
            _bound_add((anchor,anchor),_bound_multiply((1-fraction,)*2,(low,low)))[0]]
        material[f"{body}_face_mm"] = [
            _bound_subtract((anchor,anchor),_bound_multiply((fraction,fraction),(high,high)))[0],
            _bound_add((anchor,anchor),_bound_multiply((1-fraction,)*2,(high,high)))[1]]
    band = domain.get("driver_retained_band_limits_mm")
    shoulder = reference["driver_shoulder_z_mm"]
    if shoulder is not None:
        if not isinstance(band,dict) or band.keys() != {"shoulder_z","turned_radius"}:
            raise ValueError("actual retained driver band has no complete source family")
        for name,field in (("shoulder_z","driver_shoulder_z_mm"),("turned_radius","driver_turned_radius_mm")):
            low,high = band[name]
            if (any(type(value) not in (int,float) or not math.isfinite(value) for value in (low,high))
                    or not 0 < low <= reference[field] <= high):
                raise ValueError("retained driver band omitted its actual physical reference")
            support[field],material[field] = low,high
    elif band is not None:
        raise ValueError("unbanded driver acquired a synthetic material band")
    return support,material


def _require_face_family(case,domain,record):
    support,material = _face_family_placements(case["placement"],domain)
    if (record["method"] != "nested actual finite-stock material with common physical side/tip support"
            or record["moving_face_cap_carrying"] is not False or record["native_certificate"] is not False
            or not same_numeric_tree(record["reference_placement"],case["placement"])
            or not same_numeric_tree(record["support_placement"],support)
            or not same_numeric_tree(record["material_placement"],material)
            or not same_numeric_tree(record["source_face_width_limits_mm"],domain["finite_face_width_limits_mm"])
            or not same_numeric_tree(record["source_face_anchor_fraction"],domain["finite_face_anchor_fraction"])):
        raise ValueError("finite face proof changed material/support bounds or manufactured anchor")
    band = domain.get("driver_retained_band_limits_mm")
    if (not same_numeric_tree(record.get("source_driver_retained_band_limits_mm"),band)
            or band is not None and record.get("moving_band_cap_carrying") is not False):
        raise ValueError("retained-band enclosure omitted the source family or invented a carrying MIN cap")
    return support,material


def _certificate_interval(value):
    if (not isinstance(value,(list,tuple)) or len(value) != 2
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in value)
            or value[0] > value[1]):
        raise ValueError("invalid finite continuation interval")
    return value


def _contains_interval(outer,inner,strict=False):
    a,b = _certificate_interval(outer)
    x,y = _certificate_interval(inner)
    return a < x <= y < b if strict else a <= x <= y <= b


def _same_pose_difference(a,b,phase,source):
    delta = _bound_subtract(_certificate_interval(b["center_driven_phase_enclosure_rad"]),
                            _certificate_interval(a["center_driven_phase_enclosure_rad"]))
    if a["parameter_names"] != b["parameter_names"]:
        raise ValueError("same-pose comparison uses different derivative coordinates")
    for name,ga,gb in zip(a["parameter_names"],a["driven_phase_parameter_derivatives"],
                         b["driven_phase_parameter_derivatives"],strict=True):
        limits = phase if name == "driver_phase_rad" else source[name]
        centre = limits[0]/2+limits[1]/2
        delta = _bound_add(delta,_bound_multiply(_bound_subtract(gb,ga),
                           _bound_subtract(limits,(centre,centre))))
    return delta


def _geometry_payment(branch,minimum,additional_geometry_error_mm):
    error = branch["geometry_error_bound_mm"]
    gradient = minimum["objective_gradient_magnitude_upper_per_mm"]
    slope = minimum["approach_derivative_magnitude_lower"]
    if (any(type(v) not in (float,int) or not math.isfinite(v)
            for v in (error,gradient,slope,additional_geometry_error_mm))
            or min(error,additional_geometry_error_mm) < 0 or gradient <= 0 or slope <= 0):
        raise ValueError("physical profile error lacks a positive objective/transversality payment")
    profile = _bound_divide(_bound_multiply((error,error),(gradient,gradient)),(slope,slope))[1]
    if additional_geometry_error_mm == 0:
        return profile
    extra = _bound_divide(_bound_multiply((additional_geometry_error_mm,)*2,(gradient,gradient)),(slope,slope))[1]
    return _bound_add((profile,profile),(extra,extra))[1]


def _rectangle_remainder_nonempty(domain,cuts):
    """Replay the exact closed native-parameter UNION, without a point probe."""
    grids = []
    for axis in (0,1):
        lo,hi = domain[axis]
        grids.append(sorted({lo,hi,*(max(lo,min(hi,value)) for cut in cuts for value in cut[axis])}))
    for x0,x1 in zip(grids[0],grids[0][1:]):
        for y0,y1 in zip(grids[1],grids[1][1:]):
            if not any(cut[0][0] <= x0 < x1 <= cut[0][1]
                       and cut[1][0] <= y0 < y1 <= cut[1][1] for cut in cuts):
                return True
    return False


def _require_surface_cover_receipts(cell,material_placement,driver,domain):
    cover = cell["first_contact_cover"]
    inventory = set(cover["physical_patch_inventory"])
    roots = set(cover["root_patch_ids"])
    branches = {value["chart"]:value for value in cell["branch_proofs"]}
    minima = {value["chart"]:value for value in cover["chart_minimum_bounds"]}
    boundaries = {(value["patch_id"],value["chart"]):value for value in cover["boundary_separations"]}
    owners = {patch:[name for name,patches in cover["chart_patch_ids"].items() if patch in patches]
              for patch in inventory}
    cuts = {}
    for patch,names in owners.items():
        rectangles = []
        for name in names:
            stratum = branches[name]["physical_strata"]["driven"]
            main = f"{stratum['tooth']}:{stratum['segment']}"
            rectangles.append(minima[name]["neighbourhood"]["driven_surface_domain"] if patch == main
                              else boundaries[patch,name]["patch_parameter_domain"])
        cuts[patch] = rectangles
    groups = {}
    def rectangle_multiset(values):
        if any(len(value) != 2 for value in values):
            raise ValueError("physical patch remainder has no two-dimensional native parameter domain")
        return sorted(tuple(_certificate_interval(axis) for axis in value) for value in values)
    for field,reference_only in (("surface_exclusion_receipts",False),("free_reference_exclusion_receipts",True)):
        records = {value["patch_id"]:value for value in cell[field]}
        if records.keys() != inventory or len(records) != len(cell[field]):
            raise ValueError("complete finite material exclusion omitted an actual tooth/side/cap patch")
        groups[field] = records
        for patch,record in records.items():
            cap = ":end_face:" in patch
            names = ["native_t","radial_fraction" if cap else "z_mm"]
            full = [[0.0,1.0],[0.0,1.0] if cap else material_placement["driven_face_mm"]]
            expected_cuts = [] if reference_only else cuts[patch]
            approach = cover["free_reference_driven_phase_rad"] if reference_only else cover["approach_driven_phase_rad"]
            required = 0.0 if reference_only or patch not in roots else domain["root_air_requirements_mm"]["driven"]
            empty = not _rectangle_remainder_nonempty(full,expected_cuts)
            if (record["status"] != "PROVED" or record["native_certificate"] is not False
                    or record["physical_no_solution"] is not False
                    or record["scope"] != "boundary patch against complete cutter-gapped driver material"
                    or not same_numeric_tree(record["phase_cell_rad"],cell["phase_cell_rad"])
                    or not same_numeric_tree(record["same_source_pose"],cell["same_source_pose"])
                    or record["angle_coordinate"] != "driven_material"
                    or not same_numeric_tree(record["approach_driven_phase_rad"],approach)
                    or not same_numeric_tree(record["patch_parameter_names"],names)
                    or not same_numeric_tree(record["patch_parameter_domain"],full)
                    or rectangle_multiset(record["excluded_patch_parameter_domains"]) != rectangle_multiset(expected_cuts)
                    or record["required_air_mm"] != required or record["air_lower_mm"] <= required
                    or record["additional_geometry_error_mm"] < cover["additional_geometry_error_mm"]
                    or record["empty_remainder"] is not empty or "unresolved" in record):
                raise ValueError("surface exclusion changed actual source/approach/material/cap domain or dropped paid geometry")
            count,terminal = record["boxes"],record["terminal_boxes"]
            if (type(count) is not int or type(terminal) is not int or not 0 <= terminal <= count
                    or empty and (count != 0 or terminal != 0)
                    or not empty and terminal == 0
                    or record["largest_terminal_parameter_radius_mm"] < 0
                    or record["parameter_radius_metric_upper"] <= 0):
                raise ValueError("surface exclusion has no complete achieved terminal enclosure")
            offset = [-driver.angular_pitch_rad/2,driver.angular_pitch_rad/2]
            if not same_numeric_tree(record["inverse_offset_domain_rad"],offset):
                raise ValueError("surface exclusion changed its physical inverse-offset domain")
            outer = record["free_outer_inverse_offset_components_rad"]
            inner = record["free_inner_inverse_offset_components_rad"]
            require_components(outer,offset)
            require_components(inner,offset,contained_in=outer)
            if not any(lo <= 0 <= hi for lo,hi in inner):
                raise ValueError("surface exclusion did not prove the actual held pose inside its INNER set")
    air = {name:value["air_lower_mm"] for name,value in groups["surface_exclusion_receipts"].items()}
    if cover["free_reference_air_mm"][0] > min(
            value["air_lower_mm"] for value in groups["free_reference_exclusion_receipts"].values()):
        raise ValueError("free-reference air exceeds the complete actual physical patch proof")
    if any(value[0] > air[name] for name,value in cover["excluded_patch_air_mm"].items()):
        raise ValueError("noncarrying/competitor air is detached from its finite material receipt")
    for name,minimum in minima.items():
        if minimum["outside_neighbourhood_air_mm"][0] > min(air[patch] for patch in cover["chart_patch_ids"][name]):
            raise ValueError("chart minimum claims more remainder air than its actual patch exclusions")
    for record in (*cover["boundary_separations"],*cover["patch_remainder_bounds"]):
        field = "outside_neighbourhood_air_mm" if "chart" in record else "outside_union_air_mm"
        if record[field][0] > air[record["patch_id"]]:
            raise ValueError("incident/cap/outside-UNION air is detached from its physical patch")


def _require_continuous_side(case, domain, driver, driven, proof, *, closing_sense, operating,
                             coverage_floor, row_floor, handover_max_mm, face_enclosure,
                             direct_phase_rad=None) -> None:
    """Read one loaded direction without importing its diagnostic engine."""
    pitch = driver.angular_pitch_rad
    source = {name:list(limits) for name,limits in domain["correlated_pose_parameters"]}
    support,material_placement = _require_face_family(case,domain,face_enclosure)
    material_case = {**case,"placement":material_placement}
    case = {**case,"placement":support}
    direct = direct_phase_rad is not None
    if direct and (type(direct_phase_rad) not in (int,float) or not math.isfinite(direct_phase_rad)):
        raise ValueError("direct physical contact requires its actual finite driver angle")
    schema = "finite-stock-first-contact-cell/1" if direct else "finite-stock-continuous-envelope/1"
    actual_domain = proof["phase_cell_rad"] if direct else proof["phase_domain_rad"]
    expected_domain = [direct_phase_rad,direct_phase_rad] if direct else [0.0,pitch]
    if (proof["proof_schema"] != schema or proof["status"] != "PROVED" or proof["native_certificate"]
            or not same_numeric_tree(proof["same_source_pose"],source)
            or not same_numeric_tree(actual_domain,expected_domain)):
        raise ValueError("contact proof has a different physical source/domain")
    declared_sense = proof["first_contact_cover"]["closing_driven_sense"] if direct else proof["closing_driven_sense"]
    if declared_sense != closing_sense:
        raise ValueError("contact proof changed the physical loaded approach direction")

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

    distance_scale_limit = _frame_distance_scale_limit(case["placement"]["driver_frame"])
    period_displacement,_,_ = _periodic_source_evidence(driver,driven,material_placement,source)

    def neighbourhood(record, branch, phase, cover):
        if (not isinstance(record,dict)
                or not same_numeric_tree(record["phase_cell_rad"],phase)
                or not same_numeric_tree(record["same_source_pose"],source)
                or record["angle_coordinate"] != cover["angle_coordinate"]
                or not contains(record["approach_driven_phase_rad"],cover["approach_driven_phase_rad"])
                or len(record["unknown_domain"]) != len(branch["unknown_domain"])
                or not all(contains(a,b) for a,b in zip(record["unknown_domain"],branch["unknown_domain"]))):
            raise ValueError("numeric minimum/separation belongs to a different chart neighbourhood or approach")
        rectangle = record["driven_surface_domain"]
        root_rectangle = branch["driven_surface_root_box"]
        if (len(rectangle) != 2 or len(root_rectangle) != 2
                or any(interval(v)[0] >= v[1] for v in rectangle)
                or not all(contains(a,b) for a,b in zip(rectangle,root_rectangle))):
            raise ValueError("physical two-coordinate neighbourhood omits its actual free/fixed root")

    def patch_domain(names,rectangle,branch,patch):
        stratum = branch["physical_strata"]["driven"]
        suffix = next((value for value in (":end_face:-1",":end_face:+1") if patch.endswith(value)),"")
        side = patch[:-len(suffix)] if suffix else patch
        main = f"{stratum['tooth']}:{stratum['segment']}"
        if side == main:
            t = interval(branch["driven_surface_root_box"][0])
        else:
            incident = {f"{stratum['tooth']}:{item['segment']}":item["parameter"]
                        for item in stratum["incident_segments"]}
            if side not in incident:
                raise ValueError("patch domain is not on an actual incident native segment")
            t = (incident[side],)*2
        if suffix:
            face_index = 0 if suffix.endswith("-1") else 1
            if stratum["z_fixed"] != material_placement["driven_face_mm"][face_index]:
                raise ValueError("cap parameter domain names a different actual face")
            expected,root = ["native_t","radial_fraction"],(t,(1.0,1.0))
        else:
            expected,root = ["native_t","z_mm"],(t,interval(branch["driven_surface_root_box"][1]))
        master_extension = side == main and stratum["implicit_tip"] is True
        t_bound = interval(rectangle[0]) if len(rectangle) == 2 else (math.inf,-math.inf)
        finite_t = (max(t_bound[0],0.0) <= min(t_bound[1],1.0) if master_extension
                    else contains((0.0,1.0),t_bound))
        if (list(names) != expected or len(rectangle) != 2
                or any(interval(value)[0] >= value[1] for value in rectangle)
                or not all(contains(a,b) for a,b in zip(rectangle,root))
                or not finite_t
                or suffix and not contains((0.0,1.0),rectangle[1])):
            raise ValueError("native patch domain substituted main/incident/cap coordinates")



    def endpoint_proof(record,parent,point,expected_source=None):
        actual_source = source if expected_source is None else expected_source
        for field in ("proof_schema","chart","driven_tooth","physical_strata","unknown_domain",
                      "parameter_names","driven_angle_unknown_index","driven_station_unknown_index",
                      "unknown_angle_coordinate","root_component_coordinate","geometry_error_bound_mm"):
            if not same_numeric_tree(record[field],parent[field]):
                raise ValueError("endpoint/centre root changed its physical chart or finite source model")
        if (record["status"] != "PROVED" or record["native_certificate"] is not False
                or not same_numeric_tree(record["phase_cell_rad"],[point,point])
                or not same_numeric_tree(record["same_source_pose"],actual_source)
                or not 0 <= record["contraction_upper"] < 1
                or len(record["root_box"]) != len(parent["unknown_domain"])
                or not all(contains(a,b,strict=True) for a,b in zip(parent["unknown_domain"],record["root_box"]))
                or len(record["driven_phase_parameter_derivatives"]) != 1+len(source)
                or any(interval(value)[0] <= 0 for value in record["support_margins"].values())):
            raise ValueError("endpoint/centre does not have actual uniform supported root inclusion")

    def handover(record,phase,branches,cover):
        pair = record["branch_proofs"]
        if (record["status"] != "PROVED" or record["continuous"] is not True
                or record["physical_no_solution"] is not False or record["native_certificate"] is not False
                or not same_numeric_tree(record["phase_bracket_rad"],phase)
                or not same_numeric_tree(record["same_source_pose"],source)
                or not same_numeric_tree(record["first_contact_cover"],cover)
                or len(pair) != 2 or pair[0]["chart"] == pair[1]["chart"]
                or any(p["chart"] not in branches or not same_numeric_tree(p,branches[p["chart"]]) for p in pair)):
            raise ValueError("paid handover does not bind two actual branches in one whole-source first-contact cell")
        full = {p["chart"]:p for p in record["first_contact_branch_proofs"]}
        if (full.keys() != branches.keys() or len(full) != len(record["first_contact_branch_proofs"])
                or any(not same_numeric_tree(full[name],value) for name,value in branches.items())):
            raise ValueError("paid handover discarded a physical first-contact competitor")
        minima = {value["chart"]:value for value in cover["chart_minimum_bounds"]}
        a,b = pair
        delta = _same_pose_difference(a,b,phase,source)
        errors = [_geometry_payment(value,minima[value["chart"]],cover["additional_geometry_error_mm"]) for value in pair]
        error = _bound_add((errors[0],)*2,(errors[1],)*2)
        if (not contains(record["same_pose_driven_root_difference_rad"],delta)
                or not contains(record["physical_geometry_error_payment_rad"],error)
                or record["root_component_coordinate"] != cover["angle_coordinate"]
                or not same_numeric_tree(record["root_free_component_rad"],a["root_free_component_rad"])
                or not same_numeric_tree(a["root_free_component_rad"],b["root_free_component_rad"])
                or record["pair"] != [a["driven_tooth"],b["driven_tooth"]]):
            raise ValueError("handover used independent root uncertainty or changed its actual root-free component")
        centre_source = {name:[limits[0]/2+limits[1]/2]*2 for name,limits in source.items()}
        centre = phase[0]/2+phase[1]/2
        centres = record["center_branch_proofs"]
        if len(centres) != 2:
            raise ValueError("handover has no two actual numerical centre-root proofs")
        for value,parent in zip(centres,pair):
            endpoint_proof(value,parent,centre,centre_source)
            if not same_numeric_tree(value["driven_phase_enclosure_rad"],parent["center_driven_phase_enclosure_rad"]):
                raise ValueError("handover centre substituted a manufacturing-range midpoint")
        endpoints = record["endpoint_difference_proofs"]
        if len(endpoints) != 2 or len(record["endpoint_difference_enclosures_rad"]) != 2:
            raise ValueError("handover lacks its genuine continuous crossing bracket")
        for index,point in enumerate(phase):
            endpoint = endpoints[index]
            roots_at_end = endpoint["branch_proofs"]
            if endpoint["phase_rad"] != point or len(roots_at_end) != 2:
                raise ValueError("handover endpoint is not its actual phase boundary")
            for value,parent in zip(roots_at_end,pair):
                endpoint_proof(value,parent,point)
            difference = _bound_multiply((closing_sense,)*2,
                                         _same_pose_difference(*roots_at_end,[point,point],source))
            claimed = interval(record["endpoint_difference_enclosures_rad"][index])
            if not contains(claimed,difference) or not same_numeric_tree(endpoint["closing_difference_rad"],claimed):
                raise ValueError("handover endpoint discarded same-source difference payment")
            if index == 0 and claimed[0] <= error[1] or index == 1 and claimed[1] >= -error[1]:
                raise ValueError("supported first-contact exchange is not uniformly bracketed after geometry payment")
        expected_competitors = branches.keys()-{a["chart"],b["chart"]}
        competitors = {item["competitor_chart"]:item for item in record["full_cell_competitor_exclusions"]}
        if competitors.keys() != expected_competitors or len(competitors) != len(record["full_cell_competitor_exclusions"]):
            raise ValueError("handover omitted a possibly earlier physical root")
        for name,item in competitors.items():
            comparisons = {v["chart"]:v for v in item["pair_comparisons"]}
            if comparisons.keys() != {a["chart"],b["chart"]} or len(item["pair_comparisons"]) != 2:
                raise ValueError("handover competitor lacks both same-pose pair comparisons")
            paid_lowers = []
            for selected in pair:
                value = comparisons[selected["chart"]]
                excess = _bound_multiply((closing_sense,)*2,_same_pose_difference(selected,branches[name],phase,source))
                ga = _geometry_payment(selected,minima[selected["chart"]],cover["additional_geometry_error_mm"])
                gb = _geometry_payment(branches[name],minima[name],cover["additional_geometry_error_mm"])
                payment = _bound_add((ga,ga),(gb,gb))
                paid = _bound_subtract(excess,payment)[0]
                if (not contains(value["closing_competitor_excess_rad"],excess)
                        or not contains(value["physical_geometry_error_payment_rad"],payment)
                        or value["paid_competitor_excess_lower_rad"] > paid):
                    raise ValueError("handover understated an intervening root's correlated uncertainty")
                paid_lowers.append(value["paid_competitor_excess_lower_rad"])
            if max(paid_lowers) < 0:
                raise ValueError("another physical root may precede both handover branches")
        magnitude = max(abs(value) for value in record["same_pose_driven_root_difference_rad"])
        payment = _bound_add((magnitude,magnitude),record["physical_geometry_error_payment_rad"])
        minimum_jump = _bound_multiply((driven.pitch_radius_mm,)*2,payment)[1]
        if not minimum_jump <= record["pitch_displacement_jump_upper_mm"] <= handover_max_mm:
            raise ValueError("handover displacement is not an actual paid same-pose bound")
        return {a["chart"]},{b["chart"]}

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
    cells = [proof] if direct else proof["phase_cells"]
    if not cells:
        raise ValueError("no continuous common-normal phase cells")
    previous,integral = direct_phase_rad if direct else 0.0,(0.0,0.0)
    guaranteed_rows = []
    validated_cells = []
    handover_records = [] if direct else proof["handovers"]
    handovers = {tuple(item["phase_bracket_rad"]):item for item in handover_records}
    if len(handovers) != len(handover_records):
        raise ValueError("continuous contact has duplicate handover cells")
    used_handovers,endpoint_first = set(),[]
    for cell in cells:
        phase = interval(cell["phase_cell_rad"])
        if ((direct and not same_numeric_tree(phase,[direct_phase_rad,direct_phase_rad]))
                or (not direct and (phase[0] != previous or not phase[0] < phase[1] <= pitch))):
            raise ValueError("contact cells omit, overlap, or replace the actual driver domain")
        previous = phase[1]
        if not same_numeric_tree(cell["same_source_pose"],source):
            raise ValueError("continuous phase cell narrowed the physical source domain")
        cover = cell["first_contact_cover"]
        if (cover["proof_schema"] != "finite-stock-first-contact-cover/1" or cover["native_certificate"]
                or not same_numeric_tree(cover["phase_cell_rad"],phase)
                or not same_numeric_tree(cover["same_source_pose"],source)
                or set(cover["physical_patch_inventory"]) != inventory
                or len(cover["physical_patch_inventory"]) != len(inventory)
                or set(cover["root_patch_ids"]) != roots
                or set(cover["noncarrying_patch_ids"]) != noncarrying
                or cover["required_root_air_mm"] != domain["root_air_requirements_mm"]["driven"]
                or cover["backlash_lower_mm"] <= 0.0
                or cover["closing_driven_sense"] != closing_sense
                or cover["angle_coordinate"] not in ("physical","driven_material")):
            raise ValueError("continuous first-contact physical inventory/air/source is incomplete")
        additional = cover["additional_geometry_error_mm"]
        if (type(additional) not in (float,int) or not math.isfinite(additional)
                or additional < period_displacement):
            raise ValueError("first-contact cover dropped the actual joint-period geometry payment")
        approach = interval(cover["approach_driven_phase_rad"])
        reference = interval(cover["free_reference_driven_phase_rad"])
        if not contains(approach,reference) or interval(cover["free_reference_air_mm"])[0] <= 0:
            raise ValueError("first-contact approach has no actual strictly free reference")
        root = cell["root_proof"]
        raw = root["root_sweep"]
        pitch_domain = (-pitch/2,pitch/2)
        if (root["status"] != "PROVED" or raw["status"] != "resolved"
                or raw["root_is_carrying"] or raw["native_solid_certificate"]
                or not same_numeric_tree(root["same_source_pose"],source)
                or not same_numeric_tree(root["phase_cell_rad"],phase)
                or root["angle_coordinate"] != cover["angle_coordinate"]
                or not contains(root["driven_angle_domain_rad"],approach)
                or root["physical_driven_teeth"] != list(range(driven.teeth))
                or set(root["physical_patch_inventory"]) != inventory
                or len(root["physical_patch_inventory"]) != len(inventory)
                or not same_numeric_tree(raw["offset_domain_rad"],pitch_domain)
                or raw["root_air_lower_bound_mm"] < raw["required_root_air_mm"]
                or root["physical_required_root_air_mm"] != domain["root_air_requirements_mm"]["driver"]
                or not 0 < root["driver_local_to_world_distance_lower"] <= distance_scale_limit
                or root["physical_root_air_lower_bound_mm"] <= 0
                or root["physical_root_air_lower_bound_mm"] < domain["root_air_requirements_mm"]["driver"]
                or root["physical_root_air_lower_bound_mm"] > _bound_multiply(
                    (raw["root_air_lower_bound_mm"],)*2,(root["driver_local_to_world_distance_lower"],)*2)[0]
                or not 0 <= raw["geometric_uncertainty_mm"] <= case["numerical_error_bounds"]["surface_mm"]):
            raise ValueError("continuous root enclosure is absent or from a different pose")
        require_components(raw["free_outer"],pitch_domain)
        require_components(raw["free_inner"],pitch_domain,contained_in=raw["free_outer"])
        require_components(root["inverse_offset_free_components_rad"],pitch_domain,contained_in=raw["free_inner"])
        if not any(a <= 0 <= b for a,b in root["inverse_offset_free_components_rad"]):
            raise ValueError("continuous pose is outside the actual root-free INNER")
        if not same_numeric_tree(cover["root_free_driven_components_rad"],root["root_free_driven_components_rad"]):
            raise ValueError("first-contact cover substituted a root-free component hull")
        require_components(root["root_free_driven_components_rad"],root["driven_angle_domain_rad"])
        if not any(contains(component,approach) for component in root["root_free_driven_components_rad"]):
            raise ValueError("loaded approach bridges disconnected root-free INNER components")
        _require_material_sweep(root,driver,driven,material_placement,phase,source,approach,
                                cover["angle_coordinate"],domain["root_air_requirements_mm"]["driver"],
                                case["numerical_error_bounds"]["surface_mm"],"driver_root_material")
        _require_driven_root_material(cell["driven_root_material_proof"],material_case,domain,
                                      driver,driven,phase,source,approach)
        if (root["additional_geometry_error_mm"] < additional
                or cell["driven_root_material_proof"]["material_sweep"]["additional_geometry_error_mm"] < additional):
            raise ValueError("complete root material does not enclose the paid first-contact family")
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
            if interval(air)[0] <= (domain["root_air_requirements_mm"]["driven"] if name in roots else 0):
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
            needed = _bound_add((branch_by_name[item["chart"]]["geometry_error_bound_mm"],)*2,(additional,additional))[1]
            if item["objective_gradient_padding_mm"] is None or item["objective_gradient_padding_mm"] < needed:
                raise ValueError("first-contact Lipschitz region omits its profile-plus-joint-period geometry")
        expected_boundaries = {(patch,chart) for chart,patches in assigned.items()
                               for patch in patches if patch in noncarrying}
        expected_boundaries |= {
            (patch,chart) for chart,patches in assigned.items() for patch in patches
            if patch != f"{branch_by_name[chart]['physical_strata']['driven']['tooth']}:{branch_by_name[chart]['physical_strata']['driven']['segment']}"}
        boundaries = {(item["patch_id"],item["chart"]):item for item in cover["boundary_separations"]}
        if boundaries.keys() != expected_boundaries or len(boundaries) != len(cover["boundary_separations"]):
            raise ValueError("actual cap-edge neighbourhood lacks its one-sided separation")
        for item in boundaries.values():
            neighbourhood(item["neighbourhood"],branch_by_name[item["chart"]],phase,cover)
            if not same_numeric_tree(item["neighbourhood"],minima[item["chart"]]["neighbourhood"]):
                raise ValueError("cap separation and local minimum excise different neighbourhoods")
            if (item["inward_gap_derivative_lower"] <= 0
                    or interval(item["outside_neighbourhood_air_mm"])[0] <= 0):
                raise ValueError("noncarrying cap interior has no actual inward separation")
            patch_domain(item["patch_parameter_names"],item["patch_parameter_domain"],
                         branch_by_name[item["chart"]],item["patch_id"])
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
                if (not same_numeric_tree(item["neighbourhoods"][chart],minima[chart]["neighbourhood"])
                        or minima[chart]["outside_neighbourhood_air_mm"][0] > item["outside_union_air_mm"][0]):
                    raise ValueError("outside-union clearance is not bound to its exact local minimum domains")
            if item["patch_parameter_domains"].keys() != charts:
                raise ValueError("outside-union proof omitted actual per-patch coordinate rectangles")
            for chart in charts:
                rectangle = item["patch_parameter_domains"][chart]
                branch = branch_by_name[chart]
                patch_domain(item["patch_parameter_names"],rectangle,branch,patch)
                stratum = branch["physical_strata"]["driven"]
                main = f"{stratum['tooth']}:{stratum['segment']}"
                expected = (minima[chart]["neighbourhood"]["driven_surface_domain"] if patch == main else
                            boundaries[(patch,chart)]["patch_parameter_domain"])
                if not same_numeric_tree(rectangle,expected):
                    raise ValueError("outside-union exclusion detached its incident/cap domain")
        _require_surface_cover_receipts(cell,material_placement,driver,domain)
        for branch in branches:
            if (branch["proof_schema"] != "finite-stock-common-normal-continuation/1"
                    or branch["status"] != "PROVED" or branch["native_certificate"]
                    or not same_numeric_tree(branch["phase_cell_rad"],phase)
                    or not same_numeric_tree(branch["same_source_pose"],source)
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
                if (z is not None and not shoulder
                        and material_placement[f"{body}_face_mm"][face.index(z)] != z):
                    raise ValueError("artificial MIN-width face normal is not a real all-family carrying surface")
                if body == "driver" and (
                        shoulder and actual_shoulder != material_placement["driver_shoulder_z_mm"]
                        or cap is not None and actual_cap != material_placement["driver_turned_radius_mm"]):
                    raise ValueError("artificial MIN shoulder/radial cap is not a real all-family carrying normal")
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
                actual_t = (t,t)
                if t is None or implicit:
                    label = "finite_master_tip" if implicit else "finite_t"
                    expected_margins.update((f"{body}_{label}_lower",f"{body}_{label}_upper"))
                    if cap is not None:
                        expected_margins.update((f"{body}_turned_cap_finite_t_lower",
                                                 f"{body}_turned_cap_finite_t_upper"))
                    coordinate = interval(box[cursor])
                    actual_t = coordinate
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
                actual_z = (z,z)
                if z is None:
                    actual_z = interval(box[cursor])
                    if not contains(face,box[cursor],strict=True):
                        raise ValueError("carrying root extended the actual finite face width")
                    if cap is not None and box[cursor][0] <= actual_shoulder:
                        raise ValueError("turned-cap root crossed the actual concave shoulder join")
                    expected_margins.update((f"{body}_finite_z_lower",f"{body}_finite_z_upper"))
                    if body == "driven":
                        station_index = cursor
                    cursor += 1
                if body == "driven" and not same_numeric_tree(
                        branch["driven_surface_root_box"],[actual_t,actual_z]):
                    raise ValueError("physical neighbourhood substituted its free/fixed root coordinates")
                count = 1+len(incidents)+int(z is not None)+int(cap is not None)
                expected_margins.update(f"{body}_normal_cone_weight_{i}" for i in range(count))
                weights = branch["normal_cone_weights"][0 if body == "driver" else 1]
                generators = branch["normal_cone_generators_world"][0 if body == "driver" else 1]
                if (len(weights) != count or len(generators) != count
                        or any(interval(weight)[0] <= 0 for weight in weights)
                        or not sum(v[0] for v in weights) <= 1 <= sum(v[1] for v in weights)
                        or any(len(v) != 3 or any(interval(c)[0] > c[1] for c in v) for v in generators)):
                    raise ValueError("continuous branch lacks its actual positive normal cone")
            if (case["placement"]["driver_shoulder_z_mm"] is not None
                    and case["placement"]["driver_turned_radius_mm"] is not None
                    and math.isfinite(case["placement"]["driver_shoulder_z_mm"])
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
                    or not same_numeric_tree(branch["driven_material_phase_enclosure_rad"],box[cursor])):
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
                    or not any(same_numeric_tree(component,c) for c in cover["root_free_driven_components_rad"])
                    or closing_sense == 1 and reference[1] >= member[0]
                    or closing_sense == -1 and reference[0] <= member[1]):
                raise ValueError("supported branch lacks a same-coordinate root-free approach from actual air")
            centre_box = branch["center_root_box"]
            centre_phase = phase[0]/2+phase[1]/2
            centre_source = {key:[v[0]/2+v[1]/2]*2 for key,v in source.items()}
            centre_clock = clock[0]/2+clock[1]/2
            if (not same_numeric_tree(branch["center_phase_cell_rad"],[centre_phase,centre_phase])
                    or not same_numeric_tree(branch["center_source_pose"],centre_source)
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
        if direct:
            # A single actual phase needs the SAME complete physical root,
            # material, common-normal, minimum and exclusion proofs above.
            # It does not masquerade as a whole-period coverage certificate.
            return
        carrier_rows = {item["chart"]:item for item in cell["carrier_comparisons"]}
        if carrier_rows.keys() != names or len(carrier_rows) != len(cell["carrier_comparisons"]):
            raise ValueError("coverage omitted same-pose first-carrier comparisons")
        counted,uniformly_first = set(),set()
        payments = {name:_geometry_payment(branch,minima[name],cover["additional_geometry_error_mm"])
                    for name,branch in branch_by_name.items()}
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
                                       _same_pose_difference(competitor,candidate,phase,source))
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
                eligible &= comparison["pitch_excess_upper_mm"] <= handover_max_mm
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
        if tuple(phase) in handovers:
            endpoint_first.append(handover(handovers[tuple(phase)],phase,branch_by_name,cover))
            used_handovers.add(tuple(phase))
        elif uniformly_first:
            endpoint_first.append((uniformly_first,uniformly_first))
        else:
            raise ValueError("possibly switching first roots lack their actual continuous paid handover")
        validated_cells.append((phase,branch_by_name,uniformly_first))
    reciprocal = (math.nextafter(1/pitch,-math.inf),math.nextafter(1/pitch,math.inf))
    coverage = _bound_multiply(integral,reciprocal)[0]
    if previous != pitch or proof["stock_form_coverage_lower"] > coverage:
        raise ValueError("coverage exceeds the distinct first/paid supported-tooth phase union")
    if used_handovers != handovers.keys():
        raise ValueError("handover proof is detached from the actual continuous phase partition")
    boundaries = proof["boundary_continuations"]
    if len(boundaries) != len(validated_cells)-1:
        raise ValueError("continuous partition lacks every actual shared-boundary root")
    for index,(left,right) in enumerate(zip(validated_cells,validated_cells[1:])):
        record = boundaries[index]
        name,point = record["chart"],left[0][1]
        if (record["left_cell_index"] != index or record["right_cell_index"] != index+1
                or record["phase_rad"] != point or point != right[0][0]
                or name not in endpoint_first[index][1] & endpoint_first[index+1][0]):
            raise ValueError("shared-boundary proof is not the actual first-contact continuation")
        a,b = record["left_branch_proof"],record["right_branch_proof"]
        endpoint_proof(a,left[1][name],point)
        endpoint_proof(b,right[1][name],point)
        if (not same_numeric_tree(a["physical_strata"],b["physical_strata"])
                or not (all(contains(x,y,strict=True) for x,y in zip(a["unknown_domain"],b["root_box"]))
                        or all(contains(x,y,strict=True) for x,y in zip(b["unknown_domain"],a["root_box"])))):
            raise ValueError("adjacent first contacts lack actual boundary-root uniqueness")
    seam = proof["periodic_seam"]
    if (seam["proof_schema"] != "finite-stock-periodic-seam/1" or seam["status"] != "PROVED"
            or seam["native_certificate"] is not False or seam["physical_no_solution"] is not False
            or seam["closing_driven_sense"] != closing_sense
            or not same_numeric_tree(seam["phase_endpoints_rad"],[0.0,pitch])
            or not same_numeric_tree(seam["same_source_pose"],source)
            or not same_numeric_tree(seam["source_eccentricity_disks"],domain["source_eccentricity_disks"])
            or not same_numeric_tree(seam["root_air_requirements_mm"],domain["root_air_requirements_mm"])
            or seam["driven_pitch_radius_mm"] != driven.pitch_radius_mm
            or not 0 < seam["maximum_jump_mm"] <= handover_max_mm):
        raise ValueError("whole-period seam lacks actual same-source mechanical/root provenance")
    ends = []
    for label,index,point in (("start",0,0.0),("end",-1,pitch)):
        parent = validated_cells[index][1]
        full = {v["chart"]:v for v in seam[f"{label}_full_cell_branch_proofs"]}
        end = {v["chart"]:v for v in seam[f"{label}_endpoint_branch_proofs"]}
        if (full.keys() != parent.keys() or end.keys() != parent.keys()
                or len(full) != len(seam[f"{label}_full_cell_branch_proofs"])
                or len(end) != len(seam[f"{label}_endpoint_branch_proofs"])
                or not same_numeric_tree(seam[f"{label}_first_contact_cover"],cells[index]["first_contact_cover"])
                or any(not same_numeric_tree(full[name],value) for name,value in parent.items())):
            raise ValueError("periodic seam omitted a possible actual first-contact stratum")
        for name,value in end.items():
            endpoint_proof(value,parent[name],point)
        ends.append(end)
    displacement,evidence,rotations = _periodic_source_evidence(driver,driven,case["placement"],source)
    if (seam["joint_period_tooth_steps"] != math.lcm(driver.teeth,driven.teeth)
            or not same_numeric_tree(seam["source_relabel"],rotations)
            or not same_numeric_tree(seam["periodicity_displacement_evidence"],evidence)):
        raise ValueError("periodic source relabel omitted physical disk rotation or full joint-period rounding")
    root = seam["root_proof"]
    root_domain = interval(root["driven_angle_domain_rad"])
    _require_material_sweep(root,driver,driven,material_placement,[pitch,pitch],source,root_domain,
                            "driven_material",domain["root_air_requirements_mm"]["driver"],
                            case["numerical_error_bounds"]["surface_mm"],"driver_root_material")
    _require_driven_root_material(seam["driven_root_material_proof"],material_case,domain,
                                  driver,driven,[pitch,pitch],source,root_domain)
    if (root["additional_geometry_error_mm"] < displacement
            or seam["driven_root_material_proof"]["material_sweep"]["additional_geometry_error_mm"] < displacement):
        raise ValueError("periodic complete root-material proofs omitted joint-period displacement")
    used_start,used_end = set(),set()
    paid_maximum = 0.0
    endpoint_minima = [{v["chart"]:v for v in cells[index]["first_contact_cover"]["chart_minimum_bounds"]}
                      for index in (0,-1)]
    for item in seam["chart_pairs"]:
        start_name,end_name = item["start_chart"],item["end_chart"]
        if start_name in used_start or end_name in used_end or start_name not in ends[0] or end_name not in ends[1]:
            raise ValueError("periodic stratum relabel is not an all-branch bijection")
        used_start.add(start_name)
        used_end.add(end_name)
        a,b = ends[0][start_name],ends[1][end_name]
        for body,profile,step in (("driver",driver,1),("driven",driven,-1)):
            mapped = dict(b["physical_strata"][body])
            mapped["tooth"] = (mapped["tooth"]+step)%profile.teeth
            if not same_numeric_tree(a["physical_strata"][body],mapped):
                raise ValueError("periodic seam changed native segment, cap, incident normal, or physical tooth")
        start_gradient = dict(zip(list(source),a["driven_phase_parameter_derivatives"][1:],strict=True))
        transformed = dict(start_gradient)
        for body,matrix in rotations.items():
            x,y = f"{body}_ecc_x_mm",f"{body}_ecc_y_mm"
            transformed[x] = _bound_add(_bound_multiply(start_gradient[x],matrix[0][0]),
                                         _bound_multiply(start_gradient[y],matrix[1][0]))
            transformed[y] = _bound_add(_bound_multiply(start_gradient[x],matrix[0][1]),
                                         _bound_multiply(start_gradient[y],matrix[1][1]))
        derivatives = [_bound_subtract(transformed[name],value)
                       for name,value in zip(source,b["driven_phase_parameter_derivatives"][1:],strict=True)]
        centre = _bound_subtract(_bound_subtract(a["center_driven_phase_enclosure_rad"],
                                                 (driven.angular_pitch_rad,)*2),
                                  b["center_driven_phase_enclosure_rad"])
        difference = centre
        for limits,derivative in zip(source.values(),derivatives,strict=True):
            midpoint = limits[0]/2+limits[1]/2
            difference = _bound_add(difference,_bound_multiply(derivative,_bound_subtract(limits,(midpoint,midpoint))))
        if (item["difference_parameter_names"] != list(source)
                or not same_numeric_tree(item["source_relabel"],rotations)
                or not contains(item["centre_difference_rad"],centre)
                or len(item["difference_parameter_derivatives"]) != len(derivatives)
                or not all(contains(x,y) for x,y in zip(item["difference_parameter_derivatives"],derivatives))
                or not contains(item["same_pose_driven_root_difference_rad"],difference)):
            raise ValueError("periodic comparison dropped the R-transpose same-source chain rule")
        mapped = _bound_subtract(a["driven_material_phase_enclosure_rad"],(driven.angular_pitch_rad,)*2)
        end_material = b["driven_material_phase_enclosure_rad"]
        if (not same_numeric_tree(item["mapped_start_material_root_rad"],mapped)
                or not same_numeric_tree(item["end_material_root_rad"],end_material)
                or not contains(root_domain,mapped) or not contains(root_domain,end_material)
                or not any(contains(component,mapped) and contains(component,end_material)
                           for component in root["root_free_driven_components_rad"])):
            raise ValueError("periodic material roots bridge disconnected or unpaid root clearance")
        geometry,arc = (0.0,0.0),(0.0,0.0)
        for branch,minimum in ((a,endpoint_minima[0][start_name]),(b,endpoint_minima[1][end_name])):
            needed = _bound_add((branch["geometry_error_bound_mm"],)*2,(displacement,displacement))[1]
            if minimum["objective_gradient_padding_mm"] < needed:
                raise ValueError("periodic objective Lipschitz bound lacks geometry-plus-joint-arc neighbourhood")
            payment = _geometry_payment(branch,minimum,0.0)
            geometry = _bound_add(geometry,(payment,payment))
            arc = _bound_add(arc,_bound_divide(_bound_multiply((displacement,displacement),
                              (minimum["objective_gradient_magnitude_upper_per_mm"],)*2),
                              (minimum["approach_derivative_magnitude_lower"],)*2))
        if (item["periodicity_displacement_upper_mm"] < displacement
                or not contains(item["physical_geometry_error_payment_rad"],geometry)
                or not contains(item["periodicity_error_payment_rad"],arc)):
            raise ValueError("periodic seam silently discarded physical profile or accumulated angular rounding")
        magnitude = max(abs(v) for v in item["same_pose_driven_root_difference_rad"])
        payment = _bound_add(_bound_add((magnitude,magnitude),item["physical_geometry_error_payment_rad"]),
                             item["periodicity_error_payment_rad"])
        jump = _bound_multiply((driven.pitch_radius_mm,)*2,payment)[1]
        if not jump <= item["pitch_displacement_jump_upper_mm"] <= handover_max_mm:
            raise ValueError("periodic source-relabelled envelope has no honest paid displacement bound")
        paid_maximum = max(paid_maximum,item["pitch_displacement_jump_upper_mm"])
    if (used_start != ends[0].keys() or used_end != ends[1].keys()
            or not paid_maximum <= seam["pitch_displacement_jump_upper_mm"] <= handover_max_mm):
        raise ValueError("periodic min/max envelope is not covered by every actual paired branch")
    for row in proof["row_branch_spans"]:
        first,last = row["first_cell_index"],row["last_cell_index"]
        if type(first) is not int or type(last) is not int or not 0 <= first <= last < len(validated_cells):
            raise ValueError("row image names an invalid continuous phase span")
        name = row["chart"]
        span = validated_cells[first:last+1]
        if (not same_numeric_tree(row["phase_endpoints_rad"],[span[0][0][0],span[-1][0][1]])
                or any(name not in actual_first for _,_,actual_first in span)):
            raise ValueError("row image is not a uniformly first carrying branch throughout its span")
        if any(boundaries[index]["chart"] != name for index in range(first,last)):
            raise ValueError("row span jumped between distinct shared-boundary contact roots")
        stations = []
        for endpoint,key,entry in ((span[0][0][0],"left_branch_proof",span[0]),
                                   (span[-1][0][1],"right_branch_proof",span[-1])):
            end,parent = row[key],entry[1][name]
            for field in ("proof_schema","status","native_certificate","chart","driven_tooth",
                          "same_source_pose","parameter_names","physical_strata","unknown_domain",
                          "unknown_angle_coordinate","root_component_coordinate",
                          "driven_station_unknown_index","driven_angle_unknown_index"):
                if not same_numeric_tree(end[field],parent[field]):
                    raise ValueError("row endpoint is not the same physical-source contact chart")
            box = end["root_box"]
            if (not same_numeric_tree(end["phase_cell_rad"],[endpoint,endpoint])
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
    face = case["placement"]["driven_face_mm"]
    require_components(proof["row_available_intervals_mm"],face)
    row_width = (0.0,0.0)
    for low,high in proof["row_available_intervals_mm"]:
        row_width = _bound_add(row_width,_bound_subtract((high,high),(low,low)))
    maximum_face = material_placement["driven_face_mm"]
    face_width = _bound_subtract((maximum_face[1],maximum_face[1]),(maximum_face[0],maximum_face[0]))
    reciprocal = (math.nextafter(1/face_width[1],-math.inf),
                  math.nextafter(1/face_width[0],math.inf))
    row_fraction = _bound_multiply(row_width,reciprocal)[0]
    if not 0 <= proof["row_available_fraction_lower"] <= row_fraction:
        raise ValueError("row fraction exceeds its actual continuous INNER image")
    if operating and (proof["stock_form_coverage_lower"] < coverage_floor
                      or proof["row_available_fraction_lower"] < row_floor
                      or case["row_available_fraction_lower"] != proof["row_available_fraction_lower"]):
        raise ValueError("actual operating-direction coverage or row floor is not proved")
    if operating and (case["stock_form_coverage_lower"] != proof["stock_form_coverage_lower"]
                      or not same_numeric_tree(case["row_available_intervals_mm"],proof["row_available_intervals_mm"])):
        raise ValueError("published coverage/row differs from the actual operating-direction proof")
    if operating and not same_numeric_tree(case["handovers"],proof["handovers"]):
        raise ValueError("published handovers differ from the actual operating-direction proof")


def require_continuous_certificate(case, domain, driver, driven, certificate, *,
                                   coverage_floor, row_floor, handover_max_mm=0.005) -> None:
    """Admit a complete source-bound certificate without executing its solver.

    ``domain`` must come from the caller's CURRENT pure physical supplier,
    never from the certificate being admitted. Floors belong to that caller.
    """
    try:
        if (any(type(v) not in (int,float) or not math.isfinite(v)
                for v in (coverage_floor,row_floor,handover_max_mm))
                or coverage_floor <= 0 or not 0 <= row_floor <= 1
                or not 0 < handover_max_mm <= 0.005):
            raise ValueError("invalid physical contact acceptance floors")
        source = {name:list(limits) for name,limits in domain["correlated_pose_parameters"]}
        if len(source) != len(domain["correlated_pose_parameters"]) or not finite_evidence(domain):
            raise ValueError("source domain has duplicate coordinates or nonfinite bounds")
        allowed = {f"{body}_{suffix}" for body in ("driver","driven")
                   for suffix in ("dx_mm","dy_mm","dz_mm","rx_rad","ry_rad","rz_rad",
                                  "ecc_x_mm","ecc_y_mm","clock_rad")}
        if not source.keys() <= allowed or any(
                len(bounds) != 2 or any(type(v) not in (int,float) for v in bounds)
                or bounds[0] > bounds[1] for bounds in source.values()):
            raise ValueError("source pose contains an unsupported physical coordinate or interval")
        floors = domain["root_air_requirements_mm"]
        if floors.keys() != {"driver","driven"} or any(
                type(v) not in (int,float) or not math.isfinite(v) or v < 0 for v in floors.values()):
            raise ValueError("driver/driven physical root-air floors are absent or conflated")
        disks = domain["source_eccentricity_disks"]
        if disks.keys() != {"driver","driven"}:
            raise ValueError("both actual physical eccentricity disks are required")
        widths = domain["finite_face_width_limits_mm"]
        if widths.keys() != {"driver","driven"}:
            raise ValueError("nonrigid finite material-cap families are missing")
        for body in ("driver","driven"):
            disk = disks[body]
            radius,terms = disk["radius_mm"],disk["source_terms_mm"]
            if (disk["shape"] != "closed_disk" or disk["centre_mm"] != [0.0,0.0]
                    or type(radius) not in (int,float) or radius < 0 or not terms
                    or any(not isinstance(name,str) or not name or type(v) not in (int,float) or v < 0
                           for name,v in terms.items())
                    or radius < _bound_sum((v,v) for v in terms.values())[1]
                    or any(source.get(f"{body}_ecc_{axis}_mm") != [-radius,radius] for axis in ("x","y"))):
                raise ValueError("eccentricity disk does not enclose its actual named source grades")
            limits = widths[body]
            face = case["placement"][f"{body}_face_mm"]
            if (len(limits) != 2 or any(type(v) not in (int,float) for v in limits)
                    or not 0 < limits[0] <= limits[1] or len(face) != 2
                    or not limits[0] <= face[1]-face[0] <= limits[1]):
                raise ValueError("finite face-width source family does not contain the actual reference body")
        shoulder = case["placement"]["driver_shoulder_z_mm"]
        turned = case["placement"]["driver_turned_radius_mm"]
        if (shoulder is None) != (turned is None):
            raise ValueError("retained-material band cannot be partially absent")
        if shoulder is not None and (type(shoulder) not in (int,float)
                or type(turned) not in (int,float) or not math.isfinite(shoulder)
                or not math.isfinite(turned) or turned <= 0):
            raise ValueError("retained-material band needs finite physical dimensions")
        if (not isinstance(certificate,dict) or not finite_evidence(certificate)
                or certificate["proof_schema"] != "finite-stock-continuous-envelope/1"
                or certificate["status"] != "PROVED" or certificate["native_certificate"] is not False
                or not same_numeric_tree(certificate["same_source_pose"],source)
                or not same_numeric_tree(certificate["phase_domain_rad"],[0.0,driver.angular_pitch_rad])
                or not same_numeric_tree(case["continuous_source_domain"],domain)
                or case["continuous_carrying_contact"] is not True):
            raise ValueError("continuous certificate is incomplete or differs from its actual source")
        proofs = certificate["sides"]
        if proofs.keys() != {"lower","upper"} or type(case["operating_driver_sense"]) is not int or case["operating_driver_sense"] not in (-1,1):
            raise ValueError("continuous loaded proof omits a physical direction")
        for side,sense in (("lower",-1),("upper",1)):
            _require_continuous_side(
                case,domain,driver,driven,proofs[side],closing_sense=sense,
                operating=case["operating_driver_sense"] == sense,
                coverage_floor=coverage_floor,row_floor=row_floor,handover_max_mm=handover_max_mm,
                face_enclosure=certificate["finite_face_material_enclosure"],
            )
    except (KeyError,TypeError,IndexError,ArithmeticError) as exc:
        raise ValueError("incomplete or invalid physical continuous-contact certificate") from exc


def _uniform_first_branch_names(cell,source):
    branches = cell["branch_proofs"]
    minima = {value["chart"]:value for value in cell["first_contact_cover"]["chart_minimum_bounds"]}
    sense = cell["first_contact_cover"]["closing_driven_sense"]
    payments = {value["chart"]:_geometry_payment(value,minima[value["chart"]],
                cell["first_contact_cover"]["additional_geometry_error_mm"]) for value in branches}
    first = set()
    for a in branches:
        for b in branches:
            if a["chart"] == b["chart"]:
                continue
            delta = _bound_multiply((sense,sense),_same_pose_difference(a,b,cell["phase_cell_rad"],source))
            error = _bound_add((payments[a["chart"]],)*2,(payments[b["chart"]],)*2)
            if _bound_subtract(delta,error)[0] < 0:
                break
        else:
            first.add(a["chart"])
    return first


def _require_branch_phase_envelope(record,branch,minimum,phase,source,zero,ratio,displacement):
    """Replay signed physical TE after cancelling ideal phase algebraically."""
    interval,contains = _certificate_interval,_contains_interval
    geometry = _geometry_payment(branch,minimum,0.0)
    gradient,slope = minimum["objective_gradient_magnitude_upper_per_mm"],minimum["approach_derivative_magnitude_lower"]
    arc = _bound_divide(_bound_multiply((displacement,displacement),(gradient,gradient)),(slope,slope))[1]
    claimed_displacement = record["joint_period_displacement_upper_mm"]
    claimed_geometry,claimed_arc = record["physical_geometry_payment_rad"],record["joint_period_error_payment_rad"]
    total = record["total_geometric_payment_rad"]
    if (record["chart"] != branch["chart"] or claimed_geometry != geometry or claimed_arc != arc
            or claimed_displacement != displacement
            or minimum["objective_gradient_padding_mm"] < _bound_add(
                (branch["geometry_error_bound_mm"],)*2,(claimed_displacement,)*2)[1]
            or total != _geometry_payment(branch,minimum,displacement)
            or not same_numeric_tree(record["mechanical_zero_rad"],zero)):
        raise ValueError("physical TE changed, dropped or double-paid its actual geometry/whole-period payment or datum")
    centre = phase[0]/2+phase[1]/2
    te = _bound_add(_bound_subtract(branch["center_driven_phase_enclosure_rad"],(zero["driven"],)*2),
                    _bound_multiply(ratio,_bound_subtract((centre,centre),(zero["driver"],)*2)))
    for name,derivative in zip(branch["parameter_names"],branch["driven_phase_parameter_derivatives"],strict=True):
        limits = phase if name == "driver_phase_rad" else source[name]
        slope = _bound_add(derivative,ratio) if name == "driver_phase_rad" else derivative
        centre = limits[0]/2+limits[1]/2
        te = _bound_add(te,_bound_multiply(slope,_bound_subtract(limits,(centre,centre))))
    te = _bound_add(te,(-total,total))
    physical = _bound_add(interval(branch["driven_phase_enclosure_rad"]),(-total,total))
    material = _bound_add(interval(branch["driven_material_phase_enclosure_rad"]),(-total,total))
    for field,expected in (("signed_running_te_interval_rad",te),
                           ("physical_driven_phase_interval_rad",physical),
                           ("material_driven_phase_interval_rad",material)):
        if not contains(record[field],expected):
            raise ValueError("phase envelope substitutes independent roots or drops actual source sensitivity")


def _require_phase_envelope_row(case,domain,driver,driven,row,cells,face_enclosure):
    """Bind transport to already-admitted complete physical first-contact cells."""
    if not finite_evidence(row):
        raise ValueError("phase transport has missing or nonfinite evidence")
    source = {name:list(bounds) for name,bounds in domain["correlated_pose_parameters"]}
    phase = _certificate_interval(row["phase_cell_rad"])
    zero = domain["mechanical_zero_rad"]
    if (not same_numeric_tree(row["same_source_pose"],source)
            or not same_numeric_tree(row["mechanical_zero_rad"],zero)
            or row["operating_driver_sense"] != case["operating_driver_sense"]
            or row["operating_driver_sense"] not in (-1,1)
            or set(cells) != {"lower","upper"}):
        raise ValueError("phase transport changed its actual source, mechanical datum or running direction")
    _,material = _require_face_family(case,domain,face_enclosure)
    displacement,_,_ = _periodic_source_evidence(driver,driven,material,source)
    ratio = _bound_divide((driver.teeth,)*2,(driven.teeth,)*2)
    envelopes,branch_maps,payment_maps = {},{},{}
    for side,sense in (("lower",-1),("upper",1)):
        cell = cells[side]
        if (not same_numeric_tree(cell["phase_cell_rad"],phase)
                or not same_numeric_tree(cell["same_source_pose"],source)
                or cell["first_contact_cover"]["closing_driven_sense"] != sense):
            raise ValueError("phase transport borrowed a different first-contact cell")
        branches = {value["chart"]:value for value in cell["branch_proofs"]}
        minima = {value["chart"]:value for value in cell["first_contact_cover"]["chart_minimum_bounds"]}
        first = _uniform_first_branch_names(cell,source)
        names = first or branches.keys()
        records = {value["chart"]:value for value in row["side_branch_envelopes"][side]}
        if set(records) != set(names) or len(records) != len(row["side_branch_envelopes"][side]):
            raise ValueError("phase envelope omitted an actual possible first root")
        for name,record in records.items():
            _require_branch_phase_envelope(record,branches[name],minima[name],phase,source,zero,ratio,
                                           cell["first_contact_cover"]["additional_geometry_error_mm"])
        select = max if sense == -1 else min
        envelopes[side] = {
            field:(select(value[field][0] for value in records.values()),
                   select(value[field][1] for value in records.values()))
            for field in ("signed_running_te_interval_rad","physical_driven_phase_interval_rad","material_driven_phase_interval_rad")}
        branch_maps[side] = {name:branches[name] for name in names}
        payment_maps[side] = {name:record["total_geometric_payment_rad"] for name,record in records.items()}
    backlash = row["correlated_backlash"]
    pairs = {(value["lower_chart"],value["upper_chart"]):value for value in backlash["branch_pairs"]}
    expected_pairs = {(a,b) for a in branch_maps["lower"] for b in branch_maps["upper"]}
    if (pairs.keys() != expected_pairs or len(pairs) != len(backlash["branch_pairs"])
            or not same_numeric_tree(backlash["same_source_pose"],source)
            or not same_numeric_tree(backlash["phase_cell_rad"],phase)
            or backlash["pitch_radius_mm"] != driven.pitch_radius_mm):
        raise ValueError("backlash lacks every actual same-source lower/upper branch pair")
    for (a,b),record in pairs.items():
        difference = _same_pose_difference(branch_maps["lower"][a],branch_maps["upper"][b],phase,source)
        paid = _bound_add((payment_maps["lower"][a],)*2,(payment_maps["upper"][b],)*2)[1]
        if (not _contains_interval(record["same_pose_root_difference_rad"],difference)
                or record["geometry_and_period_payment_rad"] < paid
                or not _contains_interval(record["paid_root_difference_rad"],_bound_add(
                    record["same_pose_root_difference_rad"],(-record["geometry_and_period_payment_rad"],
                                                            record["geometry_and_period_payment_rad"])))):
            raise ValueError("backlash dropped same-q derivatives or actual root/period uncertainty")
    angle = (min(value["paid_root_difference_rad"][0] for value in pairs.values()),
             min(value["paid_root_difference_rad"][1] for value in pairs.values()))
    if (not _contains_interval(backlash["backlash_interval_rad"],angle)
            or not _contains_interval(backlash["backlash_interval_mm"],_bound_multiply(
                backlash["backlash_interval_rad"],(driven.pitch_radius_mm,)*2))
            or not same_numeric_tree(row["correlated_backlash_interval_mm"],backlash["backlash_interval_mm"])):
        raise ValueError("published backlash is not the paid correlated first-contact envelope")
    running_side = "lower" if case["operating_driver_sense"] == -1 else "upper"
    expected = {
        "actual_driver_interval_rad":_bound_subtract(phase,(zero["driver"],)*2),
        "signed_running_te_interval_rad":envelopes[running_side]["signed_running_te_interval_rad"],
    }
    for side in ("lower","upper"):
        expected[f"actual_driven_{side}_interval_rad"] = _bound_subtract(
            envelopes[side]["physical_driven_phase_interval_rad"],(zero["driven"],)*2)
        expected[f"material_driven_{side}_interval_rad"] = envelopes[side]["material_driven_phase_interval_rad"]
    if any(not _contains_interval(row[field],value) for field,value in expected.items()):
        raise ValueError("physical phase transport narrowed or re-zeroed a paid envelope")
    scope = row["whole_joint_period_scope"]
    if (scope["tooth_steps"] != math.lcm(driver.teeth,driven.teeth)
            or scope["displacement_payment_mm"] < displacement):
        raise ValueError("phase transport omits the actual whole joint tooth period")
    root = cells[running_side]["root_proof"]
    reverse = cells[running_side]["driven_root_material_proof"]
    air = row["root_air"]
    if (air["qualified"] is not True or air["root_is_carrying"] is not False
            or not same_numeric_tree(air["root_air_requirements_mm"],domain["root_air_requirements_mm"])
            or not same_numeric_tree(air["driver_root_proof"],root)
            or not same_numeric_tree(air["driven_root_material_proof"],reverse)
            or air["driver_root_air_lower_mm"] != root["physical_root_air_lower_bound_mm"]
            or air["driven_root_air_lower_mm"] != reverse["root_air_lower_mm"]
            or min(air["driver_root_air_lower_mm"],air["driven_root_air_lower_mm"]) <= 0):
        raise ValueError("phase transport replaced directed actual positive root-material evidence")


def require_period_cell_envelope(case,domain,driver,driven,row,certificate):
    """Replay one row after the caller admits the complete continuous certificate."""
    try:
        if not same_numeric_tree(certificate,case["continuous_contact_certificate"]):
            raise ValueError("period transport belongs to another continuous certificate")
        cells = {}
        for side in ("lower","upper"):
            matches = [cell for cell in certificate["sides"][side]["phase_cells"]
                       if same_numeric_tree(cell["phase_cell_rad"],row["phase_cell_rad"])]
            if len(matches) != 1:
                raise ValueError("period transport is not one actual proved phase cell")
            cells[side] = matches[0]
        _require_phase_envelope_row(case,domain,driver,driven,row,cells,certificate["finite_face_material_enclosure"])
    except (KeyError,TypeError,IndexError,ArithmeticError) as exc:
        raise ValueError("incomplete actual continuous phase-envelope transport") from exc


def require_actual_read_phase(case,domain,driver,driven,row,*,expected_phase_rad):
    """Admit an actual requested point and its genuine numerical root reference."""
    try:
        if (type(expected_phase_rad) not in (int,float) or not math.isfinite(expected_phase_rad)
                or row["actual_driver_phase_rad"] != expected_phase_rad
                or not same_numeric_tree(row["phase_cell_rad"],[expected_phase_rad,expected_phase_rad])
                or row["direct_actual_phase_query"] is not True or row["periodic_point_substitution"] is not False):
            raise ValueError("read transport substituted a periodic/home point for the actual requested driver angle")
        cells = row["direct_first_contact_sides"]
        face = row["finite_face_material_enclosure"]
        if set(cells) != {"lower","upper"}:
            raise ValueError("direct physical read omitted a closing direction")
        for side,sense in (("lower",-1),("upper",1)):
            _require_continuous_side(
                case,domain,driver,driven,cells[side],closing_sense=sense,operating=False,
                coverage_floor=0.0,row_floor=0.0,handover_max_mm=.005,face_enclosure=face,
                direct_phase_rad=expected_phase_rad)
        _require_phase_envelope_row(case,domain,driver,driven,row,cells,face)
        side = "lower" if case["operating_driver_sense"] == -1 else "upper"
        cell = cells[side]
        branches = {value["chart"]:value for value in cell["branch_proofs"]}
        cover = cell["first_contact_cover"]
        minima = {value["chart"]:value for value in cover["chart_minimum_bounds"]}
        source = {name:list(bounds) for name,bounds in domain["correlated_pose_parameters"]}
        centre_source = {name:[bounds[0]/2+bounds[1]/2]*2 for name,bounds in source.items()}
        clock = centre_source.get("driven_clock_rad",(0.0,0.0))[0]
        points,centres = {},{}
        for name,branch in branches.items():
            box = branch["center_root_box"]
            point = [low/2+high/2 for low,high in box]
            if (not same_numeric_tree(branch["center_point"],point)
                    or not _contains_interval(branch["center_driven_phase_enclosure_rad"],
                        (point[branch["driven_angle_unknown_index"]]-clock,)*2)):
                raise ValueError("direct reference is not the canonical certified centre-root point")
            residuals = branch["center_point_residual_intervals"]
            root_residuals = branch["center_root_residual_intervals"]
            if len(residuals) != len(point) or len(root_residuals) != len(point):
                raise ValueError("centre residual receipt has the wrong physical chart dimension")
            for actual,enclosure in zip(residuals,root_residuals):
                _certificate_interval(actual)
                _certificate_interval(enclosure)
                if not _contains_interval(enclosure,(0.0,0.0)) or not _contains_interval(enclosure,actual):
                    raise ValueError("centre-point residual is detached from its certified root enclosure")
            points[name] = point
            payment = _geometry_payment(branch,minima[name],cover["additional_geometry_error_mm"])
            centres[name] = _bound_add(branch["center_driven_phase_enclosure_rad"],(-payment,payment))
        choose = max if side == "lower" else min
        first = (choose(value[0] for value in centres.values()),choose(value[1] for value in centres.values()))
        _,name = choose(((value[0] if side == "lower" else value[1]),name) for name,value in centres.items())
        eligible = sorted(name for name,value in centres.items() if value[0] <= first[1] and value[1] >= first[0])
        beta = points[name][branches[name]["driven_angle_unknown_index"]]-clock
        zero = domain["mechanical_zero_rad"]
        reference = math.fsum((beta,-zero["driven"],driver.teeth/driven.teeth*(expected_phase_rad-zero["driver"])))
        if (row["reference_chart"] != name or row["reference_driven_phase_rad"] != beta
                or row["reference_signed_running_te_rad"] != reference
                or not same_numeric_tree(row["reference_source_pose"],centre_source)
                or not same_numeric_tree(row["reference_common_normal_point"],points[name])
                or not same_numeric_tree(row["reference_root_proof"],branches[name])
                or not same_numeric_tree(row["reference_residual_intervals"],branches[name]["center_point_residual_intervals"])
                or not same_numeric_tree(row["reference_center_first_root_interval_rad"],first)
                or row["reference_center_first_candidates"] != eligible
                or not _contains_interval(first,(beta,beta))):
            raise ValueError("read reference is not the certified centre-root first-contact representative")
        centre_error = _bound_subtract(first,(beta,beta))
        if (not same_numeric_tree(row["reference_center_first_root_error_rad"],centre_error)
                or row["reference_center_first_root_error_bound_rad"] != max(abs(v) for v in centre_error)):
            raise ValueError("read reference discarded its midpoint-to-true-first-root numerical payment")
        centre_te = _bound_add(_bound_subtract(first,(zero["driven"],)*2),
            _bound_multiply(_bound_divide((driver.teeth,)*2,(driven.teeth,)*2),
                            _bound_subtract((expected_phase_rad,)*2,(zero["driver"],)*2)))
        if not _contains_interval(row["signed_running_te_interval_rad"],centre_te):
            raise ValueError("actual read envelope omits the already-paid true centre first-root uncertainty")
        delta = _bound_subtract(row["signed_running_te_interval_rad"],(reference,reference))
        if (not _contains_interval(row["actual_interval_error_from_reference_rad"],delta)
                or row["reference_error_bound_rad"] < max(abs(value) for value in delta)):
            raise ValueError("actual read reference discarded source or numerical root uncertainty")
    except (KeyError,TypeError,IndexError,ArithmeticError) as exc:
        raise ValueError("incomplete actual signed contact read-point evidence") from exc


def require_whole_period_envelope(case,domain,driver,driven):
    """Bind every real period cell and its signed all-source running-lag hull.

    The caller must first admit require_continuous_certificate. This adds no
    nominal sample, new scatter allowance, datum removal, or second solver.
    """
    try:
        certificate = case["continuous_contact_certificate"]
        rows = case["full_period_cells"]
        phases = [row["phase_cell_rad"] for row in rows]
        if not rows or any(not same_numeric_tree(
                phases,[cell["phase_cell_rad"] for cell in certificate["sides"][side]["phase_cells"]])
                for side in ("lower","upper")):
            raise ValueError("whole-period lag transport omitted or duplicated an actual first-contact cell")
        for row in rows:
            require_period_cell_envelope(case,domain,driver,driven,row,certificate)
        lag = [min(row["signed_running_te_interval_rad"][0] for row in rows),
               max(row["signed_running_te_interval_rad"][1] for row in rows)]
        scope = certificate["whole_period_signed_running_te_scope"]
        if (not same_numeric_tree(case["whole_period_signed_running_te_interval_rad"],lag)
                or not same_numeric_tree(certificate["whole_period_signed_running_te_interval_rad"],lag)
                or scope["operating_driver_sense"] != case["operating_driver_sense"]
                or not same_numeric_tree(scope["source_domain"],domain)
                or scope["phase_cells"] != len(rows) or scope["all_physical_tooth_identities"] is not True
                or scope["periodicity_authority"] != "both actual source-relabelled periodic_seam receipts"
                or scope["bound_authority"] != "same-q branch derivatives plus actual geometry and full joint-period displacement"):
            raise ValueError("whole-period running lag is not the actual paid all-source physical envelope")
        return tuple(lag)
    except (KeyError,TypeError,IndexError,AttributeError,ZeroDivisionError) as exc:
        raise ValueError("incomplete whole-period signed running-lag evidence") from exc


def require_selected_driver_clock_transport(case,domain,driver,driven,record,*,selected_placement,
                                            selected_phase_offset_deg,base_geometry_sha256,
                                            measurement_engine_sha256):
    """Replay same-q physical driver-clock placement plus the admitted seam.

    This follows complete base certificate/whole-period admission. The caller
    independently supplies the actual native degree-derived selected placement
    and must separately admit fresh actual selected-placement read points.
    """
    import hashlib
    import json
    def digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    try:
        if not finite_evidence(record):
            raise ValueError("selected physical clock transport has nonfinite or missing evidence")
        source = {name:list(value) for name,value in domain["correlated_pose_parameters"]}
        certificate,base = case["continuous_contact_certificate"],case["placement"]
        if (type(selected_phase_offset_deg) not in (float,int) or not math.isfinite(selected_phase_offset_deg)
                or record["proof_schema"] != "finite-stock-selected-driver-clock/1"
                or record["native_certificate"] is not False
                or record["selected_phase_offset_deg"] != selected_phase_offset_deg
                or record["base_geometry_sha256"] != base_geometry_sha256
                or record["measurement_engine_sha256"] != measurement_engine_sha256
                or record["base_certificate_sha256"] != digest(certificate)
                or not same_numeric_tree(record["base_placement"],base)
                or not same_numeric_tree(record["selected_placement"],selected_placement)
                or any(not same_numeric_tree(selected_placement[key],value)
                       for key,value in base.items() if key != "driver_clocking_rad")):
            raise ValueError("selected phase changed geometry/source or does not match the actual manufactured material clock")
        delta = _bound_subtract((base["driver_clocking_rad"],)*2,(selected_placement["driver_clocking_rad"],)*2)
        ratio = _bound_divide((driver.teeth,)*2,(driven.teeth,)*2)
        conversion = _bound_multiply(ratio,delta)
        lag = case["whole_period_signed_running_te_interval_rad"]
        if (not same_numeric_tree(record["effective_driver_material_delta_rad"],delta)
                or record["source_map_before_period_reduction"] != {name:name for name in source}
                or record["driver_parameter_relation"] != "psi = physical_driver_phi - effective_driver_material_delta"
                or record["driven_parameter_relation"] != "physical_beta unchanged"
                or record["unchanged_rectangular_source_axes"] != [name for name in source if "_ecc_" not in name]
                or not same_numeric_tree(record["source_eccentricity_disks"],domain["source_eccentricity_disks"])
                or record["joint_period_tooth_steps"] != math.lcm(driver.teeth,driven.teeth)
                or record["period_relabelling_authority"] != {
                    side:digest(certificate["sides"][side]["periodic_seam"]) for side in ("lower","upper")}
                or not same_numeric_tree(record["signed_running_te_conversion_rad"],conversion)
                or not same_numeric_tree(record["base_whole_period_signed_running_te_interval_rad"],lag)
                or not same_numeric_tree(record["selected_whole_period_signed_running_te_interval_rad"],
                                         _bound_add(lag,conversion))
                or record["geometry_payment"] != "the SAME geometry and joint-period displacement already paid in every first-contact cell; not added again"
                or record["selected_read_requirement"] != "fresh complete material/first-contact queries at every actual requested selected-placement angle"):
            raise ValueError("selected clock lost actual delta correlation, paid source-equivariant seam or signed physical lag")
        if record["selected_source_identity_sha256"] != digest(
                {key:value for key,value in record.items() if key != "selected_source_identity_sha256"}):
            raise ValueError("derived selected identity is not bound to the unchanged raw base evidence")
        return tuple(record["selected_whole_period_signed_running_te_interval_rad"])
    except (KeyError,TypeError,IndexError,AttributeError,ZeroDivisionError) as exc:
        raise ValueError("incomplete selected driver material-clock evidence") from exc
