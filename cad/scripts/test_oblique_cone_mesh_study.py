"""Deterministic pure geometry regressions; no CAD or config-side verification."""
import math
import itertools
from dataclasses import replace

from types import SimpleNamespace
import numpy as np
import pytest

import diagnostics.oblique_cone_mesh_study as cone_study
from diagnostics.oblique_cone_mesh_study import (
    PoseDomain, cone_frame, cylinder_native_rows, exact_smooth_ff_exclusion,
    cutter_q_domain, json_safe, placement_from_geometry, pose_corner_records, root_domain_probe,
    complete_pose_errors, finite_circular_band_radial_lower,
)
from diagnostics.stock_form_contact_3d import ContactPair, ContactSearch, EndFacePatch, GapAngles, Placement
from diagnostics.stock_form_root_angles import RootAngularDomain
from stock_form_cutter import CutterTemplate, CustomSixCutter, StockFormProfile


def _geometry():
    incline = math.radians(13.0011)
    return {"cone_axis":(math.sin(incline),0.0,math.cos(incline)),
            "cone_centre_mm":(0.0,0.0,0.0),"cone_face_width_mm":7.0,
            "drum_axis_xy_mm":(40.0,0.0),"drum_z_limits_mm":(-1.5,1.5)}


def _pair():
    tool = CutterTemplate(26,48.0,20.0)
    a = StockFormProfile(32,tool,8.8,1.5875)
    btool = CutterTemplate(55,48.0,20.0)
    b = StockFormProfile(120,btool,32.2,17.197916666666668)
    pose = placement_from_geometry(_geometry(),(math.pi/32,-math.radians(15.0)))
    return ContactPair("actual explicit oblique fixture",a,b,pose)


def test_row_vector_pose_is_transposed_not_scalar_centre():
    tilt = math.radians(13.0011)
    frame = cone_frame(tilt)
    assert frame[:,2] == pytest.approx((math.sin(tilt),0,math.cos(tilt)))
    assert frame[:,0] == pytest.approx((math.cos(tilt),0,-math.sin(tilt)))
    assert frame.T@frame == pytest.approx(np.eye(3),abs=2e-15)
    p = np.array((2.0,1.0,3.0))
    world = frame@p
    assert world[0] == pytest.approx(math.cos(tilt)*2+math.sin(tilt)*3)
    assert world[2] == pytest.approx(-math.sin(tilt)*2+math.cos(tilt)*3)
    assert world[0] != pytest.approx(p[0])


def test_native_cylinder_flip_retains_clock_and_reverses_phase():
    lock = math.radians(15.0)
    rows = cylinder_native_rows(lock)
    assert rows[0] == pytest.approx((-math.cos(lock),math.sin(lock),0.0))
    assert rows[2] == pytest.approx((0.0,0.0,-1.0))
    assert np.linalg.det(rows) == pytest.approx(1.0)
    pose = placement_from_geometry(_geometry(),(math.pi/32,-lock))
    assert pose.driven_clocking_rad == pytest.approx(math.pi-lock)
    assert pose.driver_clocking_rad == pytest.approx(2*math.pi/32)
    assert pose.driver_face_mm == (-3.5,3.5)
    assert pose.driven_face_mm == (-1.5,1.5)


def test_pose_ball_records_do_not_masquerade_as_full_circle_certificate():
    tilt = math.radians(13.0011)
    domain = PoseDomain((0.0,0.8),(-0.55,0.2),(6.975,7.025),(2.95,3.05),
                        0.07,(tilt,tilt),("actual source-owned fixture",))
    rows = pose_corner_records(_geometry(),(math.pi/32,0.0),domain)
    assert len(rows) == 80
    assert {tuple(row["corner"]["radial_offset_mm"]) for row in rows} == {
        (0.0,0.0),(-0.07,0.0),(0.07,0.0),(0.0,-0.07),(0.0,0.07)}
    assert domain.relative_radial_ball_mm == 0.07
    with pytest.raises(ValueError,match="provenance"):
        PoseDomain((0,0),(0,0),(7,7),(3,3),0,(tilt,tilt),())


def test_gap_inverse_negative_translation_uses_supported_actual_bound():
    tool = CutterTemplate(12,48.0,20.0)
    profile = StockFormProfile(12,tool,3.3,-0.1)
    inverse = GapAngles(profile)
    slope = inverse.radial_slope_bound()
    assert math.isfinite(slope) and slope > 0
    lo,hi = inverse.branch_range(inverse.minimum,inverse.maximum)
    assert lo <= min(inverse.angle(float(r)) for r in np.linspace(inverse.minimum,inverse.maximum,201))
    assert hi >= max(inverse.angle(float(r)) for r in np.linspace(inverse.minimum,inverse.maximum,201))
    # A real negative-T radial connector may make angle nonmonotone. No
    # positive-T tangent-limit surrogate or ideal-N continuation is allowed.
    for u in np.linspace(profile.flank_parameter_min,profile.flank_parameter_max,31):
        x,y = profile.flank_point(float(u))
        r = math.hypot(x,y)
        if r < inverse.minimum:
            continue
        z = tool.half_space_base_angle_rad+u
        exact = abs((tool.base_radius_mm*u+profile.radial_translation_mm*math.sin(z)) /
                    (r*(tool.base_radius_mm+profile.radial_translation_mm*math.cos(z))))
        assert exact <= slope


def test_custom_six_requires_provenance_and_has_general_slope_bound():
    tool = CustomSixCutter(48,20,1.173,4*25.4/48,0.818,
                          "DT6-FORM1","approved finite fixture")
    profile = StockFormProfile(6,tool,1.9,0.1)
    inverse = GapAngles(profile)
    assert math.isfinite(inverse.radial_slope_bound())
    assert inverse.branch_range(inverse.minimum,inverse.maximum)[0] <= inverse.branch_range(inverse.minimum,inverse.maximum)[1]


def test_smooth_common_normal_is_not_edge_union_coverage():
    result = exact_smooth_ff_exclusion(_pair())
    assert result["excluded"]
    assert result["opposed_normal_position_residual_lower_mm"] > 0
    assert result["common_normal_world"] == [0.0,1.0,0.0]
    assert result["branch"] == "all four smooth flank-side arrangements"
    assert "coverage" not in result


def test_endfaces_are_actual_two_parameter_patches_not_perimeter_only():
    pair = _pair()
    search = ContactSearch(pair,0.0)
    caps = [segment for segment in search.segments if isinstance(segment,EndFacePatch)]
    assert caps
    assert {segment.station_mm for segment in caps} == set(pair.placement.driven_face_mm)
    patch = next(segment for segment in caps if segment.boundary.kind == "tip_arc")
    world,local = search.point(patch,0,0.5,0.5)
    perimeter_world,_ = search.point(patch,0,0.5,1.0)
    origin = np.asarray(pair.placement.driven_origin_mm)
    assert np.linalg.norm((world-origin)[:2]) == pytest.approx(pair.driven.blank_radius_mm/2)
    assert np.linalg.norm((perimeter_world-origin)[:2]) == pytest.approx(pair.driven.blank_radius_mm)
    assert world[2] == pytest.approx(origin[2]+patch.station_mm)
    assert local == pytest.approx((world-np.asarray(pair.placement.driver_origin_mm))@pair.placement.driver_frame)
    assert search.surface_member(patch,0.5,0.5)


def test_position_uncertainty_is_irreducible_not_faked_zero():
    pair = _pair()
    exact = ContactSearch(pair,0.0)
    moved = ContactSearch(pair,0.0,position_error_mm=0.07)
    assert exact.position_angle_error_rad == 0
    assert moved.position_angle_error_rad > 0
    assert moved.position_angle_error_rad == pytest.approx(
        .07*(1/moved.gap.minimum+moved.gap.radial_slope_bound()))
    with pytest.raises(ValueError,match="nonnegative"):
        ContactSearch(pair,0.0,position_error_mm=-0.01)


def test_nonfinite_refusals_are_named_not_json_nan():
    value = json_safe({"bound":None,"root_gap":-math.inf,"phases":(0.0,math.inf)})
    assert value == {"bound":None,"root_gap":"-inf","phases":[0.0,"inf"]}
    scalars = json_safe({"qualified":np.bool_(True),"count":np.int64(20),"bound":np.float64(.002)})
    assert scalars == {"qualified":True,"count":20,"bound":.002}
    assert type(scalars["qualified"]) is bool


def test_shared_engine_requires_actual_frames_and_faces():
    with pytest.raises(ValueError,match="right-handed"):
        Placement((0,0,0),(40,0,0),np.eye(3),np.diag((1,1,-1)),(-3,3),(-1.5,1.5))
    with pytest.raises(ValueError,match="nonempty"):
        Placement((0,0,0),(40,0,0),np.eye(3),np.eye(3),(0,0),(-1.5,1.5))


def test_actual_oblique_side_endface_normal_cone_is_not_cap_only():
    pair = _pair()
    driver,driven = pair.driver,pair.driven
    tilt = math.radians(13.0011)
    frame = cone_frame(tilt)
    u = (driver.flank_parameter_min+driver.flank_parameter_max)/2
    v = (driven.flank_parameter_min+driven.flank_parameter_max)/2
    # Mate upper flank faces left after a pi rotation. Choose the genuine
    # driver flank normal whose XY projection opposes it; its oblique Z
    # component is supplied by the mate's actual NORTH endface normal.
    n_b = -np.asarray(driven.flank_normal(v))
    desired_xy = -n_b
    alpha = math.atan2(desired_xy[1],desired_xy[0]/math.cos(tilt))
    original = driver.flank_normal(u)
    driver_gap_clock = alpha-math.atan2(original[1],original[0])
    def rotate(point,clock):
        c,s = math.cos(clock),math.sin(clock)
        return np.array((c*point[0]-s*point[1],s*point[0]+c*point[1]))
    a_point = rotate(driver.flank_point(u),driver_gap_clock)
    b_point = rotate(driven.flank_point(v),math.pi)
    world = np.array((b_point[0],b_point[1],1.5))
    origin = world-frame@np.r_[a_point,0.0]
    pose = Placement(tuple(origin),(0.0,0.0,0.0),frame,np.eye(3),(-3.5,3.5),(-1.5,1.5),
                     driver_clocking_rad=driver_gap_clock+driver.angular_pitch_rad/2,
                     driven_clocking_rad=math.pi+driven.angular_pitch_rad/2)
    case = ContactPair("exact local axial-edge normal fixture",driver,driven,pose)
    search = ContactSearch(case,0.0)
    segment = next(s for s in search.segments if not isinstance(s,EndFacePatch)
                   and s.kind == "flank" and s.point(.5)[1] < 0)
    parameter = (v-driven.flank_parameter_min)/(driven.flank_parameter_max-driven.flank_parameter_min)
    contact = search.contact(segment,0,parameter,1.5,1)
    assert "driven_axial_edge" in contact.kind
    assert contact.common_normal_supported
    assert contact.opposed_normal_residual <= contact.common_normal_error_bound
    assert math.isfinite(contact.driven_per_driver_velocity)
    assert contact.driven_per_driver_velocity < 0
    # The mate normal is a positive combination of the REAL flank and cap,
    # not an invented assignment of the negative driver normal.
    actual = np.asarray(contact.driven_normal_world)
    assert actual[2] > 0
    assert actual[0]*n_b[1]-actual[1]*n_b[0] == pytest.approx(0.0,abs=1e-11)


def test_supported_Q_domain_covers_negative_translation_stationary_points():
    cutter = CutterTemplate(12,48,20)
    shifts = (-2*cutter.base_radius_mm,-cutter.base_radius_mm)
    lo,hi = cutter_q_domain(cutter,shifts)
    values = [
        cutter.base_radius_mm*u+shift*math.sin(cutter.half_space_base_angle_rad+u)
        for shift in shifts
        for u in np.linspace(cutter.flank_parameter_min,cutter.flank_parameter_max,1001)
    ]
    assert lo <= min(values) <= max(values) <= hi
    assert cutter_q_domain(cutter,(1.0,0.0)) is None


def test_root_domain_witness_is_actual_material_not_a_physical_no_solution_claim():
    source = _pair()
    pose = Placement((0,0,0),(0,0,0),np.eye(3),np.eye(3),(-1,1),(-1,1))
    witness = root_domain_probe(ContactPair("coincident finite profile witness",
                                           source.driver,source.driven,pose))
    assert witness is not None
    assert witness["driven_actual_material_member"]
    assert witness["point_below_root_max"]
    assert witness["driver_radius_mm"] < witness["driver_root_max_mm"]
    assert witness["position_ball_mm"] == 0
    assert "no_solution_certificate" not in witness


def test_pose_ball_root_touch_is_distinguished_from_an_actual_point():
    source = _pair()
    pose = Placement((0,0,0),(45,0,0),np.eye(3),np.eye(3),(-1,1),(-1,1))
    pair = ContactPair("separated finite profile domain",source.driver,source.driven,pose)
    assert root_domain_probe(pair) is None
    witness = root_domain_probe(pair,position_error_mm=6.0)
    assert witness is not None
    assert not witness["point_below_root_max"]
    assert not witness["profile_solid_interference_certified"]
    assert witness["driver_radius_mm"]-6.0 < witness["driver_root_max_mm"]


@pytest.mark.parametrize("translation",(-0.1,0.1))
def test_exact_root_strip_encloses_core_material_not_root_max_disk(translation):
    tool = CutterTemplate(26,48,20)
    profile = StockFormProfile(26,tool,7.1,translation)
    root = RootAngularDomain(profile,GapAngles(profile))
    radius = (profile.root_radius_min_mm+profile.root_radius_max_mm)/2
    intervals = root.bounds(radius,radius)
    assert not intervals.root_is_carrying
    assert intervals.reaches_root_strip
    assert len(intervals.inner) == (2 if translation>0 else 1)
    assert profile.contains_material(radius,0) == (translation>0)
    for lo,hi in intervals.inner:
        angle = (lo+hi)/2
        assert not profile.contains_material(radius*math.cos(angle),radius*math.sin(angle))
    for angle in np.linspace(-profile.angular_pitch_rad/2,profile.angular_pitch_rad/2,81):
        if not profile.contains_material(radius*math.cos(angle),radius*math.sin(angle)):
            assert any(lo <= angle <= hi for lo,hi in intervals.outer)


def test_root_tangency_and_zero_translation_have_paid_material_transitions():
    tool = CutterTemplate(26,48,20)
    profile = StockFormProfile(26,tool,7.1,0.0)
    root = RootAngularDomain(profile,GapAngles(profile))
    radius = profile.root_radius_min_mm
    assert root.bounds(radius-0.01,radius-0.01).outer == ()
    assert root.bounds(radius,radius).inner == ()
    assert len(root.bounds(radius+0.01,radius+0.01).inner) == 1
    shifted = StockFormProfile(26,tool,7.1,0.1)
    authority = RootAngularDomain(shifted,GapAngles(shifted))
    across = authority.bounds(shifted.root_radius_min_mm-1e-9,
                              shifted.root_radius_max_mm+1e-9)
    assert across.inner == ()
    assert across.outer
    assert all(math.isfinite(value) for interval in across.outer for value in interval)


def test_root_offsets_preserve_disconnected_components_and_periodic_phase():
    tool = CutterTemplate(26,48,20)
    profile = StockFormProfile(26,tool,7.1,0.1)
    root = RootAngularDomain(profile,GapAngles(profile))
    radius = (profile.root_radius_min_mm+profile.root_radius_max_mm)/2
    direct = root.offset_bounds(radius,radius,0.0,0.0)
    repeated = root.offset_bounds(radius,radius,profile.angular_pitch_rad,0.0)
    assert np.asarray(repeated.inner) == pytest.approx(np.asarray(direct.inner))
    assert np.asarray(repeated.outer) == pytest.approx(np.asarray(direct.outer))
    at_seam = root.offset_bounds(radius,radius,profile.angular_pitch_rad/2,1e-5,root_only=True)
    assert any(lo < 0 < hi for lo,hi in at_seam.inner)
    assert len(at_seam.inner) == 1


def test_cone_axial_float_is_not_radial_runout():
    pair = _pair()
    tilt = math.radians(13.0011)
    base = PoseDomain((0,0),(0,0),(7,7),(3,3),0,(tilt,tilt),("fixed source fixture",))
    nominal = complete_pose_errors(pair,base)
    floating = complete_pose_errors(pair,replace(base,cone_axial_shift_mm=(0,0.8)))
    assert nominal == pytest.approx((0,0),abs=1e-14)
    assert floating == pytest.approx((0,0.8),abs=1e-14)
    shifted = complete_pose_errors(pair,replace(base,drum_axial_shift_mm=(0,0.55)))
    assert shifted == pytest.approx((0.55*math.sin(tilt),0.55*math.cos(tilt)))


def test_bore_cock_projection_encloses_every_azimuth_not_cardinals_only():
    pair = _pair()
    tilt,beta = math.radians(13.0011),0.012
    domain = PoseDomain((0,0),(0,0),(7,7),(3,3),0,(tilt,tilt),
                        ("arbitrary source bore-cock axis and full-bore pivot",),
                        drum_axis_angle_rad=beta,drum_cock_pivot_lever_mm=5.6)
    radial,axial = complete_pose_errors(pair,domain)
    for yaw,phase,station,pivot_station in itertools.product(np.linspace(0,2*math.pi,9),
            np.linspace(0,2*math.pi,11),(-1.5,1.5),np.linspace(-5.6,1.5,5)):
        axis = np.array((math.cos(yaw),math.sin(yaw),0))
        point = np.array((pair.driven.blank_radius_mm*math.cos(phase),
                          pair.driven.blank_radius_mm*math.sin(phase),station))
        pivot = np.array((0,0,pivot_station))
        relative = point-pivot
        actual = (relative*math.cos(beta)+np.cross(axis,relative)*math.sin(beta)
                  +axis*(axis@relative)*(1-math.cos(beta))+pivot)
        local = (actual-point)@pair.placement.driver_frame
        assert math.hypot(local[0],local[1]) <= radial+1e-13
        assert abs(local[2]) <= axial+1e-13


def test_integral_cam_disk_axial_projection_is_not_scalar_centre_clearance():
    pair = _pair()
    radius,z_band = 20.0,(-6.0,-1.0)
    lower = finite_circular_band_radial_lower(pair,radius,z_band)
    assert lower>0
    assert lower != pytest.approx(40-radius)
    for phase,z,radial in itertools.product(np.linspace(0,2*math.pi,51),z_band,(0,radius)):
        point = (np.asarray(pair.placement.driven_origin_mm)
                 +np.array((radial*math.cos(phase),radial*math.sin(phase),z)))
        local = (point-np.asarray(pair.placement.driver_origin_mm))@pair.placement.driver_frame
        assert math.hypot(local[0],local[1]) >= lower-1e-13
    intersecting = replace(pair,placement=replace(pair.placement,driven_origin_mm=(10,0,0)))
    assert finite_circular_band_radial_lower(intersecting,20,(-1,1)) == 0


def test_root_air_forward_oblique_mate_rotation_pays_driver_axial_chord(monkeypatch):
    pair = _pair()
    radius = pair.driven.blank_radius_mm
    point = np.array((-radius*math.cos(.05),-radius*math.sin(.05),pair.placement.driven_face_mm[1]))
    normal = pair.placement.driver_frame[:,2]
    origin = np.asarray(pair.placement.driven_origin_mm).copy()
    local_z = float((origin+point-np.asarray(pair.placement.driver_origin_mm))@normal)
    origin[2] += (pair.placement.driver_face_mm[1]-1e-8-local_z)/normal[2]
    pair = replace(pair,placement=replace(pair.placement,driven_origin_mm=tuple(origin)))
    searches = []
    def bounded_free(search, **kwargs):
        searches.append(search)
        half = search.case.driver.angular_pitch_rad/2
        return SimpleNamespace(status="resolved",free_inner=((-half,half),),
                               free_outer=((-half,half),),
                               root_air_lower_bound_mm=kwargs["required_root_air_mm"])
    monkeypatch.setattr(cone_study,"root_free_intervals",bounded_free)
    monkeypatch.setattr(cone_study,"asdict",lambda value:vars(value))
    half_width = .001
    cone_study.loaded_root_air_bounds(pair,0.0,(-half_width,half_width),
        radial_error_mm=.003,axial_error_mm=.004)
    chord = 2*pair.driven.blank_radius_mm*math.sin(half_width/2)
    assert searches[0].radial_error_mm >= .003+chord
    axial_factor = math.sqrt(1-float(pair.placement.driver_frame[:,2]@pair.placement.driven_frame[:,2])**2)
    assert searches[0].axial_error_mm >= .004+chord*axial_factor
    moved = np.array((point[0]*math.cos(half_width)-point[1]*math.sin(half_width),
                      point[0]*math.sin(half_width)+point[1]*math.cos(half_width),point[2]))
    axial_motion = float((moved-point)@normal)
    before_z = float((origin+point-np.asarray(pair.placement.driver_origin_mm))@normal)
    assert before_z < pair.placement.driver_face_mm[1] < before_z+axial_motion
    assert 0 < axial_motion <= chord*axial_factor


def test_complete_support_projection_is_not_paid_again_as_independent_cone_tilt():
    pair = _pair()
    nominal = math.atan2(pair.placement.driver_frame[0,2],pair.placement.driver_frame[2,2])
    domain = PoseDomain((0,0),(0,0),(7,7),(3,3),0,
        (nominal-.01,nominal+.01),("exact complete support envelope",),
        cone_support_projection_mm=(.003,.004,.006),
        cone_support_projection_terms=((("all correlated source motions",.003),),
                                       (("all correlated source motions",.004),),
                                       (("all correlated source motions",.006),)))
    radial,axial = complete_pose_errors(pair,domain)
    assert radial == pytest.approx(.005)
    assert axial == pytest.approx(.006)


def test_registry_wording_does_not_enter_geometric_config_identity():
    row = {"title":"CONE","stock":"C36000","process":"48DP PA20",
           "installation_notes":"indicate the retained axis","notes":["shop acceptance"],
           "fit_class":"gear_mesh","face_width_mm":6.8756,"unknown_field":{"limit":.02}}
    def partition(actual):
        geometry,metadata = {},{}
        recorded = cone_study.RegistryFieldReads(actual,lambda key,value,caller:
            (metadata if key in cone_study._PART_METADATA_KEYS else geometry).__setitem__(key,value))
        recorded.copy()
        return geometry,metadata
    geometry,metadata = partition(row)
    assert geometry == {"fit_class":"gear_mesh","face_width_mm":6.8756,"unknown_field":{"limit":.02}}
    assert set(metadata) == {"title","stock","process","installation_notes","notes"}
    changed = {**row,"title":"REVISED TITLE","stock":"REVISED STOCK WORDING",
               "process":"REVISED PROCESS WORDING","installation_notes":"REVISED SETUP WORDING"}
    assert partition(changed)[0] == geometry
    assert partition({**row,"face_width_mm":6.9})[0] != geometry


def test_printed_profile_matrix_is_every_distinct_four_by_four_pair():
    pair = _pair()
    def corners(profile):
        return tuple(StockFormProfile(profile.teeth,profile.template,
            profile.blank_radius_mm+radius,profile.radial_translation_mm+translation)
            for radius,translation in itertools.product((-.001,.001),(-.001,.001)))
    cones,drums = corners(pair.driver),corners(pair.driven)
    cases = tuple(cone_study.printed_profile_cases(cones,drums))
    assert len(cases) == 16
    assert {(ci,di) for ci,di,_,_ in cases} == set(itertools.product(range(4),repeat=2))
    assert {(id(cone),id(drum)) for _,_,cone,drum in cases} == set(
        itertools.product(map(id,cones),map(id,drums)))
    with pytest.raises(ValueError,match="four distinct"):
        tuple(cone_study.printed_profile_cases(cones[:3],drums))
    with pytest.raises(ValueError,match="four distinct"):
        tuple(cone_study.printed_profile_cases(cones,(drums[0],)*4))


def test_robust_signed_stalls_are_computed_even_when_union_search_refuses(monkeypatch):
    import stock_form_mesh
    pair = _pair()
    received = {}
    def measured_reads(actual,phases,**kwargs):
        received.update(kwargs)
        return {"all_reads_bounded":True,"rows":[{"signed_running_te_rad":-.003}]}
    def unresolved(*args,**kwargs):
        raise ValueError("explicit unresolved union fixture")
    monkeypatch.setattr(cone_study,"signed_read_matrix",measured_reads)
    monkeypatch.setattr(cone_study,"analyse_3d_mesh",unresolved)
    monkeypatch.setattr(stock_form_mesh,"supported_flank_coverage",unresolved)
    result = cone_study.qualify_actual_pair(pair,pose_ball_mm=.01,phases=3,
        maximum_error_mm=.0002,read_phases_rad=(0.0,),planar_centre_mm=40,
        home=(math.pi/32,0.0),radial_error_mm=.02,axial_error_mm=.03)
    assert received == {"maximum_error_mm":.0002,"position_error_mm":.01,
                        "radial_error_mm":.02,"axial_error_mm":.03}
    assert result["qualification"] == "refused"
    assert result["oblique_phase_bound_rad"] is None
    assert result["signed_read_matrix"]["rows"][0]["signed_running_te_rad"] == -.003
    assert "unresolved union fixture" in result["reason"]


def test_cli_preimport_identity_compiles_captured_bytes_not_cached_code(tmp_path,monkeypatch):
    import hashlib
    from importlib.machinery import SourceFileLoader
    path = tmp_path/"captured_geometry.py"
    payload = b"captured_value = 17\n"
    path.write_bytes(payload)
    monkeypatch.setattr(cone_study,"SCRIPTS",tmp_path)
    identities = {}
    monkeypatch.setattr(cone_study,"_LOADED_PROJECT_SHA",identities)
    loader = SourceFileLoader("captured_geometry",str(path))
    code = cone_study._captured_project_code(loader,"captured_geometry")
    namespace = {}
    exec(code,namespace)
    assert namespace["captured_value"] == 17
    assert identities == {str(path.resolve()):hashlib.sha256(payload).hexdigest().upper()}
    path.write_bytes(b"captured_value = 19\n")
    with pytest.raises(RuntimeError,match="changed across imports"):
        cone_study._captured_project_code(loader,"captured_geometry")


def test_cli_import_capture_does_not_replace_external_package_loader(tmp_path,monkeypatch):
    from importlib.machinery import SourceFileLoader
    monkeypatch.setattr(cone_study,"SCRIPTS",tmp_path/"project")
    expected = object()
    monkeypatch.setattr(cone_study,"_ORIGINAL_GET_CODE",lambda loader,name:expected)
    loader = SourceFileLoader("external",str(tmp_path/"external.py"))
    assert cone_study._captured_project_code(loader,"external") is expected


def test_registry_capture_records_only_fields_consumed_by_geometry_or_wording():
    fetched = []
    row = cone_study.RegistryFieldReads(
        {"material_specification":"C36000","description":"CONE","unused_limit_mm":.02},
        lambda key,value,caller:fetched.append((key,value,caller.f_code.co_name)))
    assert row["material_specification"] == "C36000"
    assert row.get("description") == "CONE"
    assert row.get("not_provided","fallback wording") == "fallback wording"
    assert [(key,value) for key,value,_ in fetched] == [
        ("material_specification","C36000"),("description","CONE")]
    assert all(name=="test_registry_capture_records_only_fields_consumed_by_geometry_or_wording"
               for _,_,name in fetched)
    assert "material_specification" in cone_study._PART_METADATA_KEYS
    assert "description" in cone_study._PART_METADATA_KEYS
    assert "unused_limit_mm" not in cone_study._PART_METADATA_KEYS
    fetched.clear()
    assert row.copy()["unused_limit_mm"] == .02
    assert {key for key,_,_ in fetched} == set(row)


def test_extra_air_capacity_search_uses_actual_distinct_inflated_sweeps(monkeypatch):
    pair = _pair()
    cells = [{"driver_interval_rad":[i,i+1],"actual_driven_lower_interval_rad":[.01,.02],
              "root_air":{"qualified":True}} for i in range(2)]
    requested = []
    def swept(actual,phase,loaded,**kwargs):
        extra = kwargs["extra_root_air_mm"]
        requested.append((phase,extra,kwargs["driver_phase_half_width_rad"]))
        return {"qualified":extra <= (.005 if phase<1 else .0035),
                "requested_extra_air_mm":extra}
    monkeypatch.setattr(cone_study,"loaded_root_air_bounds",swept)
    capacity = cone_study.maximum_certified_root_air_capacity(pair,cells,maximum_error_mm=.0002)
    lower,upper = capacity["certification_search_bracket_mm"]
    assert 0 < lower <= .0035 < upper
    assert upper-lower <= .0002
    assert capacity["cone_root_air_lower_mm"] == pytest.approx(.02+lower)
    assert capacity["drum_root_air_lower_mm"] == pytest.approx(.10+lower)
    assert capacity["finite_physical_extra_air_upper_mm"] > upper
    assert len(capacity["last_certified_phase_proofs"]) == 2
    assert all(proof["requested_extra_air_mm"]==lower for proof in capacity["last_certified_phase_proofs"])
    assert all(half==.5 for _,_,half in requested)
    assert len({extra for _,extra,_ in requested}) > 1
    assert not capacity["physical_infeasibility_certified"]


def test_zero_requested_floor_margin_is_not_extra_capacity(monkeypatch):
    pair = _pair()
    cells = [{"driver_interval_rad":[0,1],"actual_driven_lower_interval_rad":[.01,.02],
              "root_air":{"qualified":True,"cone_root_air_lower_mm":.02,"drum_root_air_lower_mm":.10}}]
    monkeypatch.setattr(cone_study,"loaded_root_air_bounds",
        lambda *args,**kwargs:{"qualified":False})
    capacity = cone_study.maximum_certified_root_air_capacity(pair,cells,maximum_error_mm=.0002)
    assert capacity["certified_extra_air_lower_mm"] == 0
    assert capacity["status"] == "no positive reserve certified"
    assert not capacity["physical_infeasibility_certified"]


def test_stationary_design_matrix_never_calls_full_analysis_or_handover(monkeypatch):
    import stock_form_mesh
    pair = _pair()
    def forbidden(*args,**kwargs):
        pytest.fail("stationary DESIGN must not call full analysis or handovers")
    monkeypatch.setattr(cone_study,"analyse_3d_mesh",forbidden)
    monkeypatch.setattr(cone_study,"qualify_actual_pair",forbidden)
    monkeypatch.setattr(stock_form_mesh,"analyse_planar_mesh",forbidden)
    monkeypatch.setattr(stock_form_mesh,"supported_flank_coverage",
        lambda *args,**kwargs:SimpleNamespace(screen_only=True))
    monkeypatch.setattr(cone_study,"asdict",vars)
    monkeypatch.setattr(cone_study,"configured_cam_exclusion",
        lambda *args,**kwargs:{"qualified":True})
    monkeypatch.setattr(cone_study,"signed_read_matrix",
        lambda *args,**kwargs:{"all_reads_bounded":True,"rows":[{"signed_running_te_rad":-.003}]})
    monkeypatch.setattr(cone_study,"ContactSearch",
        lambda *args,**kwargs:SimpleNamespace(window=lambda *args,**kwargs:
            SimpleNamespace(no_overlap=True,root_contact=False)))
    senses = []
    def rooted(actual,phase,**kwargs):
        sense = kwargs["driver_sense"]
        senses.append(sense)
        return {"driven_phase_interval_rad":[.01,.011] if sense<0 else [.013,.014],
                "signed_running_te_interval_rad":[-.004,-.003]}
    monkeypatch.setattr(cone_study,"loaded_phase_at",rooted)
    monkeypatch.setattr(cone_study,"loaded_root_air_bounds",
        lambda *args,**kwargs:{"qualified":True,"cone_root_air_lower_mm":.02,"drum_root_air_lower_mm":.10})
    monkeypatch.setattr(cone_study,"maximum_certified_root_air_capacity",
        lambda *args,**kwargs:{"certified_extra_air_lower_mm":.004})
    measured = cone_study.measure_nominal_for_inspection(pair,phases=3,
        maximum_error_mm=.0002,read_phases_rad=(0,),planar_centre_mm=40,
        home=(math.pi/32,0))
    assert senses == [-1,1,-1,1]
    assert measured["engineering_complete"]
    assert not measured["production_qualified"]
    assert measured["union_qualification"] is None
    assert measured["handover_qualification"] is None
    assert measured["signed_read_matrix"]["rows"][0]["signed_running_te_rad"] == -.003
    assert measured["source_inspection_radius_mm"] == pytest.approx(40*120/152)
    assert measured["physical_driven_pitch_radius_mm"] == pair.driven.pitch_radius_mm
    assert measured["margins"]["cone_root_air_mm"] == .004
