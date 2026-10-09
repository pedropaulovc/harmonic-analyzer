"""Source-captured actual 16/64 finite-material whole-period design collector.

No native CAD, sampled-pose substitute, old surface-budget retry or fabricated
phase is used. Output and raw before/compiled/parsed/after receipts stay outside
the checkout. Conditional engineering domains can never publish native data.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
from importlib.machinery import SourceFileLoader
import inspect
import json
import math
from pathlib import Path
import sys
import time

# As in the cone collector, even the entry module executes captured bytes.
if __name__ == "__main__" and "_ENTRY_PAYLOAD" not in globals():
    _entry_path = Path(__file__).resolve()
    _ENTRY_PAYLOAD: bytes = _entry_path.read_bytes()
    exec(compile(_ENTRY_PAYLOAD,str(_entry_path),"exec",dont_inherit=True),globals())
    raise RuntimeError("captured crank collector returned without completing main")

SCRIPTS = Path(__file__).resolve().parents[1]
REPOSITORY = SCRIPTS.parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0,str(SCRIPTS))
_COMPILED_PAYLOADS = {str(Path(__file__).resolve()):_ENTRY_PAYLOAD} if __name__ == "__main__" else {}
_PARSED_PAYLOADS, _READ_CONFIG_PATHS, _ACCESSOR_READS = {},set(),{}
_ORIGINAL_GET_CODE = SourceFileLoader.get_code


def _captured_project_code(loader,fullname):
    path = Path(loader.path).resolve()
    if not path.is_relative_to(SCRIPTS) or path.suffix != ".py":
        return _ORIGINAL_GET_CODE(loader,fullname)
    payload = path.read_bytes()
    if _COMPILED_PAYLOADS.setdefault(str(path),payload) != payload:
        raise RuntimeError(f"source changed across actual project imports: {path}")
    return compile(payload,str(path),"exec",dont_inherit=True)


if __name__ == "__main__":
    SourceFileLoader.get_code = _captured_project_code

import _config


def _config_paths(name,keys):
    root = _config.CONFIG_DIR
    if name == "machine":
        if not keys:
            raise ValueError("whole-machine access has no finite consumed subsystem identity")
        candidate = root/"machine"/f"{keys[0]}.yaml"
        return (candidate if candidate.is_file() else root/"machine.yaml",)
    if name == "parts":
        if (root/"parts").is_dir():
            return (root/"parts"/"_defaults.yaml",root/"parts"/f"{keys[0]}.yaml") if keys and keys[0] is not None else tuple((root/"parts").glob("*.yaml"))
        return (root/"parts.yaml",)
    if name == "provenance" and keys:
        document,*node = keys
        return _config_paths(document,node) if document in ("machine","parts") else (root/f"{document}.yaml",)
    if name == "active_channels":
        return (root/"channels.yaml",root/"machine"/"channels.yaml")
    if name == "active_count":
        return (root/"machine"/"channels.yaml",)
    documents = {"fit":"tolerances","release_revision":"release","channels":"channels",
                 "cone_teeth":"channels","amplitudes":"channels","poses":"poses",
                 "title_block":"title_block","materials":"materials","palette":"materials"}
    if name not in documents:
        raise ValueError(f"unbound configuration accessor identity: {name}{keys}")
    return (root/f"{documents[name]}.yaml",)


def _capture_config_reads():
    if _config._doc.cache_info().currsize or _config._parts_registry.cache_info().currsize:
        raise ValueError("source capture requires a fresh CLI configuration cache")
    def load(path):
        path = Path(path).resolve()
        payload = path.read_bytes()
        if _PARSED_PAYLOADS.setdefault(str(path),payload) != payload:
            raise RuntimeError(f"configuration changed across actual parses: {path}")
        return _config.yaml.safe_load(payload.decode("utf-8")) or {}
    _config._load = load
    for name,original in tuple(vars(_config).items()):
        if name.startswith("_") or not inspect.isfunction(original) or original.__module__ != _config.__name__:
            continue
        def traced(*args,_name=name,_original=original,**kwargs):
            bound = inspect.signature(_original).bind(*args,**kwargs)
            bound.apply_defaults()
            keys = tuple(item for value in bound.arguments.values() for item in (value if isinstance(value,tuple) else (value,)))
            paths = _config_paths(_name,keys)
            value = _original(*args,**kwargs)
            _READ_CONFIG_PATHS.update(str(path.resolve()) for path in paths)
            # These are fetched accessor values, not a claim that every field
            # of a returned registry row contributes to physical geometry.
            _ACCESSOR_READS[f"{_name}:{keys!r}"] = json.loads(json.dumps(value))
            return value
        setattr(_config,name,traced)


if __name__ == "__main__":
    _capture_config_reads()

import numpy as np
import crossed_mesh_study as cms
import crank_mesh_geometry as geometry
from crank_mesh_requirements import (
    HANDOVER_JUMP_MAX_MM, POSITIVE_BACKLASH_MIN_MM,
    ROW_ENGAGEMENT_MIN, STOCK_FORM_COVERAGE_MIN,
)
from stock_form_cutter import StockFormProfile
from diagnostics.stock_form_contact_3d import (
    ContactPair, Placement, ContinuousContactRefusal, analyse_3d_mesh, profile_record,
    read_actual_phases, selected_driver_clock_transport,
)
from diagnostics.stock_form_root_angles import intersect_intervals

_ENGINE_SOURCES = (
    "crank_mesh_backlash_study.py","crossed_mesh_study.py","stock_form_contact_3d.py",
    "stock_form_root_angles.py","stock_form_root_sweep.py","stock_form_contact_continuation.py",
)


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def measurement_engine_identity() -> dict:
    """Exact SIX measuring sources, separate from the pure physical digest."""
    root = Path(__file__).resolve().parent
    sources = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in _ENGINE_SOURCES}
    return {"measurement_engine_sha256":_digest(sources),"measurement_engine_sources_sha256":sources}


def crank_pair(name: str,driver: StockFormProfile,driven: StockFormProfile,
               pose: cms.Placement | None = None,*,selected_phase_offset_deg=None) -> ContactPair:
    pose_record = geometry.calibration_case_parameters()[0]["pose"] if pose is None else asdict(pose)
    return ContactPair(name,driver,driven,Placement(**geometry.placement_record(
        pose_record,selected_phase_offset_deg=selected_phase_offset_deg)))


def design_cases(centre_shift_mm: float = 0.0,*,conditional_source=None) -> tuple[ContactPair,...]:
    drivers = dict(cms.pinion_spec.STOCK_PROFILE_CORNERS,nominal=cms.pinion_spec.STOCK_PROFILE)
    driven = dict(cms.gear64_spec.STOCK_PROFILE_CORNERS,nominal=cms.gear64_spec.STOCK_PROFILE)
    return tuple(crank_pair(row["name"],drivers[row["driver_profile_label"]],driven[row["driven_profile_label"]],
                            cms.Placement(**row["pose"])) for row in geometry.calibration_case_parameters(
                                centre_shift_mm=centre_shift_mm,conditional_source=conditional_source))


def json_safe(value):
    """A refusal's nonfinite diagnostic is null, never a finite proof fallback."""
    if isinstance(value,np.generic):
        return json_safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):
        return None
    if isinstance(value,np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value,dict):
        return {key:json_safe(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)):
        return [json_safe(item) for item in value]
    return value


def analyse_case(case,continuous_source_domain,*,phases=129,maximum_error_mm=.001):
    return analyse_3d_mesh(case,continuous_source_domain=continuous_source_domain,
                          phases=phases,maximum_error_mm=maximum_error_mm,
                          coverage_min=STOCK_FORM_COVERAGE_MIN,row_min=ROW_ENGAGEMENT_MIN,
                          handover_max_mm=HANDOVER_JUMP_MAX_MM,
                          positive_backlash_min_mm=POSITIVE_BACKLASH_MIN_MM,driver_sense=1)


def measure_read_stalls(selected_case,continuous_source_domain,*,maximum_error_mm=.001):
    """Fresh actual selected-placement material/root/first-contact queries."""
    return read_actual_phases(selected_case,continuous_source_domain=continuous_source_domain,
                              driver_phases_rad=tuple(4*math.pi*index for index in range(21)),driver_sense=1,
                              maximum_error_mm=maximum_error_mm,maximum_jump_mm=HANDOVER_JUMP_MAX_MM)


def calibration_payload(results,identity,centre_shift_mm,engine_identity):
    complete = set(results) == geometry.required_calibration_case_names()
    pitch = geometry.pinion.STOCK_PROFILE.angular_pitch_rad
    common = ((-pitch/2,pitch/2),)
    for result in results.values():
        common = intersect_intervals(common,result.get("phase_components_rad",()))
    window = max(common,key=lambda value:value[1]-value[0]) if common else None
    candidate = complete and all(value.get("source_domain_proved") is True for value in results.values()) and window is not None
    source = candidate and centre_shift_mm == 0 and all(value.get("production_source_qualified") is True for value in results.values())
    return {
        "family":"dt_crank_stock_form","schema_version":1,
        "qualified":False,"candidate_source_domain_proved":candidate,"production_source_domain_proved":source,
        "geometry_sha256":identity,**engine_identity,"native_certificate":False,
        "refusal":"Actual selected native degree datum, all-source full-period transport, fresh 21 read proofs and stable captured source remain required.",
        "method":"actual supported finite common normals, exhaustive cutter-gapped material/root exclusions and paid continuous same-source handovers",
        "design_centre_shift_mm":centre_shift_mm,"phase_components_rad":common,"phase_window_rad":window,
        "phase_seed_deg":None,"required_case_names":sorted(geometry.required_calibration_case_names()),"cases":results,
    }


def _finish_selected_source(payload,pairs,parameters,*,maximum_error_mm):
    if not payload["production_source_domain_proved"]:
        return
    from diagnostics.stock_form_contact_continuation import Interval
    window = payload["phase_window_rad"]
    datum = geometry.pinion._PINION_DATUM_CLOCK_DEG
    selection = [max(window[0],math.radians(-datum)),
                 min(window[1],math.radians(360.0/geometry.pinion.TEETH-datum))]
    if not selection[0] < selection[1]:
        raise ValueError("actual common phase leaves the existing manufactured retention-hole pitch domain")
    selected_deg = math.degrees(selection[0]/2+selection[1]/2)
    if not 0 <= datum+selected_deg < 360.0/geometry.pinion.TEETH:
        raise ValueError("selected native degree arithmetic leaves the manufactured retention datum")
    selected_reads,transports = {},{}
    for pair in pairs:
        source = parameters[pair.name]
        selected = replace(pair,placement=Placement(**geometry.placement_record(
            source["pose"],selected_phase_offset_deg=selected_deg)))
        transports[pair.name] = selected_driver_clock_transport(
            pair,selected,payload["cases"][pair.name],selected_phase_offset_deg=selected_deg,
            base_geometry_sha256=payload["geometry_sha256"],measurement_engine_sha256=payload["measurement_engine_sha256"])
        delta = transports[pair.name]["effective_driver_material_delta_rad"]
        if not window[0] < delta[0] <= delta[1] < window[1]:
            raise ValueError("actual native clock subtraction is not inside the proved common source window")
        selected_reads[pair.name] = measure_read_stalls(
            selected,source["continuous_source_domain"],maximum_error_mm=maximum_error_mm)
    lag = Interval(min(row["selected_whole_period_signed_running_te_interval_rad"][0] for row in transports.values()),
                   max(row["selected_whole_period_signed_running_te_interval_rad"][1] for row in transports.values()))
    source = parameters["nominal"]
    nominal_pair = next(pair for pair in pairs if pair.name == "nominal")
    nominal_pair = replace(nominal_pair,placement=Placement(**geometry.placement_record(
        source["pose"],selected_phase_offset_deg=selected_deg)))
    nominal_domain = geometry.nominal_reference_domain(source["continuous_source_domain"],source["pose"])
    nominal_packet = measure_read_stalls(nominal_pair,nominal_domain,maximum_error_mm=maximum_error_mm)
    nominal = nominal_packet["actual_read_phases"]
    bounds = []
    for index,reference in enumerate(nominal):
        actual = Interval(min(value["actual_read_phases"][index]["signed_running_te_interval_rad"][0] for value in selected_reads.values()),
                          max(value["actual_read_phases"][index]["signed_running_te_interval_rad"][1] for value in selected_reads.values()))
        bounds.append((actual-reference["reference_signed_running_te_rad"]).magnitude)
    payload.update({"phase_seed_deg":selected_deg,"selected_phase_transports":transports,"selected_read_cases":selected_reads,
                    "nominal_reference_read_case":nominal_packet,
                    "phase_qualification":{
                        "qualified":True,"CONE_SHAFT_SENSE":-1,"CERTIFIED_PHASE_OFFSET_DEG":selected_deg,
                        "STALL_DRIVER_RAD":[row["actual_driver_phase_rad"] for row in nominal],
                        "CONE_SHAFT_LAG_RAD":[row["reference_signed_running_te_rad"] for row in nominal],
                        "BOUND_RAD":bounds,"CONE_SHAFT_LAG_INTERVAL_RAD":lag.record(),
                        "geometry_sha256":payload["geometry_sha256"],"measurement_engine_sha256":payload["measurement_engine_sha256"],
                        "alignment_zero_subtracted":False,
                        "scope":"actual signed running cone-shaft radians; all profiles and the whole continuous physical source/joint period",
                    }})


def _snapshots(root,scope,payloads):
    paths = {}
    for original,data in payloads.items():
        destination = root/scope/Path(original).relative_to(REPOSITORY)
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data)
        paths[original] = str(destination)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--phases",type=int,default=129)
    parser.add_argument("--maximum-error-mm",type=float,default=.001)
    parser.add_argument("--centre-shift-mm",type=float,default=0.0)
    parser.add_argument("--case",action="append")
    parser.add_argument("--conditional-lateral-origin-half-width-mm",type=float)
    parser.add_argument("--conditional-driver-clock-half-width-rad",type=float)
    parser.add_argument("--conditional-driven-clock-half-width-rad",type=float)
    args = parser.parse_args()
    args.out = args.out.resolve()
    if args.out.is_relative_to(REPOSITORY):
        raise ValueError("DESIGN report and raw source snapshots must remain outside the checkout")
    assumptions = {name:getattr(args,name) for name in (
        "conditional_lateral_origin_half_width_mm","conditional_driver_clock_half_width_rad",
        "conditional_driven_clock_half_width_rad") if getattr(args,name) is not None}
    parameters = {row["name"]:row for row in geometry.calibration_case_parameters(
        centre_shift_mm=args.centre_shift_mm,conditional_source=assumptions)}
    pairs = design_cases(args.centre_shift_mm,conditional_source=assumptions)
    if args.case and not set(args.case) <= parameters.keys():
        raise ValueError("requested case is not in the actual source-owned manufacturing family")
    identity,engine = geometry.geometry_sha256(),measurement_engine_identity()
    descriptor = {"pure_current_geometry_sha256":identity,"design_centre_shift_mm":args.centre_shift_mm,
                  "conditional_source_assumptions":assumptions,"parameters":parameters,
                  "cases":{pair.name:{"placement":pair.placement.record(),"driver_profile":profile_record(pair.driver),
                                       "driven_profile":profile_record(pair.driven)} for pair in pairs},
                  "requested_cases":args.case,"phases":args.phases,"maximum_error_mm":args.maximum_error_mm}
    nominal_source = parameters["nominal"]
    descriptor["nominal_reference_domain"] = (
        geometry.nominal_reference_domain(nominal_source["continuous_source_domain"],nominal_source["pose"])
        if not nominal_source["continuous_source_domain"]["unbound_sources"] else None)
    descriptor["actual_selected_read_driver_phases_rad"] = [4*math.pi*index for index in range(21)]
    compiled = dict(_COMPILED_PAYLOADS)
    parsed = {path:_PARSED_PAYLOADS[path] for path in _READ_CONFIG_PATHS}
    paths = compiled.keys() | parsed.keys()
    before = {path:Path(path).read_bytes() for path in paths}
    if any(before[path] != data for path,data in (*compiled.items(),*parsed.items())):
        raise RuntimeError("source changed before the actual calculation; no DESIGN launched")
    for name,sha in engine["measurement_engine_sources_sha256"].items():
        path = str((Path(__file__).resolve().parent/name).resolve())
        if path not in compiled or hashlib.sha256(compiled[path]).hexdigest() != sha:
            raise RuntimeError(f"measurement manifest is not the actual compiled source: {name}")
    raw = args.out.with_suffix(".raw-source")
    raw.mkdir(parents=True,exist_ok=True)
    source = {"before":_snapshots(raw,"before",before),"compiled":_snapshots(raw,"compiled",compiled),
              "parsed":_snapshots(raw,"parsed",parsed)}
    basis = {"state":"BEFORE only; no result claimed","consumed_input":descriptor,"consumed_input_sha256":_digest(descriptor),
             "accessor_return_values":_ACCESSOR_READS,"raw_source_snapshots":source,
             "before_sha256":{path:hashlib.sha256(data).hexdigest() for path,data in before.items()},
             "compiled_sha256":{path:hashlib.sha256(data).hexdigest() for path,data in compiled.items()},
             "parsed_sha256":{path:hashlib.sha256(data).hexdigest() for path,data in parsed.items()}}
    args.out.with_suffix(".basis.json").write_text(json.dumps(basis,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    results = {}
    case_directory = args.out.with_suffix(".cases")
    case_directory.mkdir(parents=True,exist_ok=True)
    payload = None
    try:
        for index,pair in enumerate(pairs):
            if args.case and pair.name not in args.case:
                continue
            started = time.perf_counter()
            try:
                result = analyse_case(pair,parameters[pair.name]["continuous_source_domain"],phases=args.phases,
                                      maximum_error_mm=args.maximum_error_mm)
            except (ValueError,RuntimeError,ArithmeticError) as exc:
                result = {"case":pair.name,"qualified":False,"source_domain_proved":False,"physical_no_solution":False,
                          "refusal":str(exc),"evidence":getattr(exc,"evidence",{})}
            result["seconds"] = time.perf_counter()-started
            results[pair.name] = json_safe(result)
            (case_directory/f"{index:04d}.json").write_text(json.dumps(results[pair.name],allow_nan=False)+"\n",encoding="utf-8")
            print(json.dumps({key:result.get(key) for key in ("case","qualified","refusal","seconds")}),flush=True)
        payload = calibration_payload(results,identity,args.centre_shift_mm,engine)
        try:
            _finish_selected_source(payload,pairs,parameters,maximum_error_mm=args.maximum_error_mm)
        except (ValueError,RuntimeError,ArithmeticError) as exc:
            payload["refusal"] = str(exc)
            payload["selected_source_refusal"] = json_safe(getattr(exc,"evidence",{}))
    finally:
        after = {path:Path(path).read_bytes() for path in paths | _COMPILED_PAYLOADS.keys() | _READ_CONFIG_PATHS}
        source["after"] = _snapshots(raw,"after",after)
        source["compiled"] = _snapshots(raw,"compiled",_COMPILED_PAYLOADS)
        stable = (before == after and compiled == _COMPILED_PAYLOADS
                  and all(after[path] == data for path,data in parsed.items()))
        receipt = {**basis,"raw_source_snapshots":source,"source_bytes_stable":stable,
                   "after_sha256":{path:hashlib.sha256(data).hexdigest() for path,data in after.items()},
                   "actual_compiled_sha256":{path:hashlib.sha256(data).hexdigest() for path,data in _COMPILED_PAYLOADS.items()},
                   "state":"complete source receipt; changed bytes make observations historical DESIGN only"}
        if payload is None:
            payload = {"qualified":False,"refusal":"collector interrupted before complete results","cases":results}
        phase = payload.get("phase_qualification",{})
        payload["qualified"] = stable and payload.get("production_source_domain_proved") is True and phase.get("qualified") is True
        if not payload["qualified"]:
            phase["qualified"] = False
            payload["phase_seed_deg"] = None
        else:
            payload["refusal"] = ""
        payload["source_identity"] = receipt
        payload["consumed_input_sha256"] = basis["consumed_input_sha256"]
        args.out.write_text(json.dumps(json_safe(payload),separators=(",",":"),allow_nan=False)+"\n",encoding="utf-8")
    return 0 if payload["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
