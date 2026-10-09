"""Actual finite-face cone/drum contact and signed mechanical-datum studies.

The numerical surfaces belong to stock_form_contact_3d; this adapter never
replaces the inclined extrusion with an unchanged planar profile. Reports
are engineering evidence outside the checkout, not manufacturing settings.
A finite printed-domain refusal has precedence over a contact calculation:
there is no honest manufactured corner to analyse when that domain is empty.

The assembly flips the straight cylinder about Y. Its symmetric gear solid
can be reparameterised about world +Z, reversing native rotation and axial
station. This is an exact rigid-solid identity, not an obliquity correction.
Native canonical GAP clocks are pi/T and pi-lock-pi/120. Documented physical
NOTCH-up setup rotates the drum to beta=pi; saved-CAD bias is reported
separately. Signed TE uses the independent notch/cone-lock datum, not a
mean, nearest-tooth, loaded-home or placement-clock subtraction.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
from importlib.machinery import SourceFileLoader
import inspect
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any

# Capture the entry module's ACTUALLY COMPILED bytes too, before any project
# import. A direct-file Python launch otherwise cannot recover the bytes it
# compiled if another owner edits the file before the first hash read.
if __name__=="__main__" and "_ENTRY_SOURCE_SHA256" not in globals():
    _entry_path = Path(__file__).resolve()
    _entry_payload = _entry_path.read_bytes()
    globals()["_ENTRY_SOURCE_SHA256"] = hashlib.sha256(_entry_payload).hexdigest().upper()
    exec(compile(_entry_payload,str(_entry_path),"exec",dont_inherit=True),globals())
    raise RuntimeError("captured engineering entry returned without completing main")

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

def _byte_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


_ALGORITHM_PATHS = tuple(SCRIPTS/name for name in (
    "stock_form_cutter.py","stock_form_mesh.py",
    "diagnostics/stock_form_contact_3d.py","diagnostics/stock_form_root_angles.py",
    "diagnostics/stock_form_root_sweep.py","diagnostics/oblique_cone_mesh_study.py",
    "diagnostics/stock_form_contact_continuation.py",
    "diagnostics/solve_stock_form_cones.py","dt_cone_support_pose.py"))
_MEASUREMENT_ENGINE_PATHS = (
    "cad/scripts/stock_form_cutter.py",
    "cad/scripts/stock_form_mesh.py",
    "cad/scripts/diagnostics/stock_form_root_angles.py",
    "cad/scripts/diagnostics/stock_form_root_sweep.py",
    "cad/scripts/diagnostics/stock_form_contact_3d.py",
    "cad/scripts/diagnostics/stock_form_contact_continuation.py",
)
_BUDGET_EXCLUDED_TERMS = ("cone_flat_free_clock","BoreFlatClock","drum_tooth_to_cam_notch_clock")
_LOADED_ALGORITHM_SHA = {str(path):_byte_sha(path) for path in _ALGORITHM_PATHS if path.is_file()}
_LOADED_PROJECT_SHA = {str(Path(__file__).resolve()):
                      globals().get("_ENTRY_SOURCE_SHA256") or _byte_sha(Path(__file__).resolve())}
_LOADED_PROJECT_PAYLOADS = (
    {str(Path(__file__).resolve()):_entry_payload} if __name__=="__main__" else {})
_ORIGINAL_GET_CODE = SourceFileLoader.get_code


def _captured_project_code(loader,fullname):
    """CLI-only: compile the same project bytes whose preimport SHA is recorded."""
    path = Path(loader.path).resolve()
    if not path.is_relative_to(SCRIPTS) or path.suffix!=".py":
        return _ORIGINAL_GET_CODE(loader,fullname)
    payload = path.read_bytes()
    sha = hashlib.sha256(payload).hexdigest().upper()
    previous = _LOADED_PROJECT_SHA.setdefault(str(path),sha)
    if previous!=sha:
        raise RuntimeError(f"project source changed across imports: {path}")
    _LOADED_PROJECT_PAYLOADS.setdefault(str(path),payload)
    return compile(payload,str(path),"exec",dont_inherit=True)


if __name__=="__main__":
    SourceFileLoader.get_code = _captured_project_code

_PART_METADATA_KEYS = frozenset((
    "revision","confidence","number","description","material","material_family",
    "material_specification","material_tip_specification","finish","quantity",
    "process","source","notes","title","stock","installation_notes"))




class RegistryFieldReads(dict):
    """CLI instrumentation: record fields actually fetched, not unused wording."""
    def __init__(self,row,on_read):
        super().__init__(row)
        self.on_read = on_read

    def __getitem__(self,key):
        value = super().__getitem__(key)
        self.on_read(key,value,sys._getframe(1))
        return value

    def get(self,key,default=None):
        if key not in self:
            return default
        value = super().__getitem__(key)
        self.on_read(key,value,sys._getframe(1))
        return value

    def _record_all(self,caller):
        for key,value in super().items():
            self.on_read(key,value,caller)

    def __iter__(self):
        self._record_all(sys._getframe(1))
        return super().__iter__()

    def keys(self):
        self._record_all(sys._getframe(1))
        return super().keys()

    def values(self):
        self._record_all(sys._getframe(1))
        return super().values()

    def items(self):
        self._record_all(sys._getframe(1))
        return super().items()

    def copy(self):
        self._record_all(sys._getframe(1))
        return dict(super().items())


def source_identity(config_paths=(), *, captured_payloads=None) -> dict[str,str]:
    """Actual loaded project code plus configuration bytes, never a rebind."""
    paths = set()
    for module in tuple(sys.modules.values()):
        filename = getattr(module,"__file__",None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(SCRIPTS) and path.suffix == ".py":
                paths.add(path)
    paths.update(Path(path) for path in config_paths)
    identity = {}
    for path in sorted(paths):
        payload = path.read_bytes()
        identity[str(path)] = hashlib.sha256(payload).hexdigest().upper()
        if captured_payloads is not None:
            captured_payloads[str(path)] = payload
    return identity


def retain_raw_source_snapshot(root: Path, scope: str, payloads: dict) -> dict:
    """Retain the SAME captured bytes outside-tree, never reread compiled code."""
    if root.resolve().is_relative_to(SCRIPTS.parents[1]):
        raise ValueError("raw DESIGN source snapshots must be outside the repository")
    paths = {}
    for original,payload in payloads.items():
        destination = root/scope/Path(original).resolve().relative_to(SCRIPTS.parents[1])
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(payload)
        paths[original] = str(destination)
    return paths

class InputReadIdentity:
    """Delegating CLI-only provenance of configuration values actually read."""
    def __init__(self):
        import _config
        self.config = _config
        self.original = {}
        self.before = {}
        self.values = {}
        self.non_geometry_before = {}
        self.non_geometry_values = {}
        self.call_sites = {}
        self.loaded_config_sha = {}
        self.loaded_config_payloads = {}

    def _paths(self,name,keys):
        root = self.config.CONFIG_DIR
        if name == "machine":
            if not keys:
                raise ValueError("whole machine document read has no finite semantic subsystem identity")
            candidate = root/"machine"/f"{keys[0]}.yaml"
            return (candidate if candidate.is_file() else root/"machine.yaml",)
        if name == "fit":
            return (root/"tolerances.yaml",)
        documents = {"release_revision":"release","channels":"channels","cone_teeth":"channels",
                     "amplitudes":"channels","poses":"poses","title_block":"title_block",
                     "materials":"materials","palette":"materials"}
        if name in documents:
            return (root/f"{documents[name]}.yaml",)
        if name == "active_count":
            return (root/"machine"/"channels.yaml",)
        if name == "active_channels":
            return (root/"channels.yaml",root/"machine"/"channels.yaml")
        if name == "parts":
            if (root/"parts").is_dir():
                paths = [root/"parts"/"_defaults.yaml"]
                if keys and keys[0] is not None:
                    paths.append(root/"parts"/f"{keys[0]}.yaml")
                else:
                    paths.extend((root/"parts").glob("*.yaml"))
                return tuple(paths)
            return (root/"parts.yaml",)
        if name == "provenance" and keys:
            document,*node = keys
            if document=="machine":
                return self._paths("machine",node)
            if document=="parts":
                return self._paths("parts",node)
            return (root/f"{document}.yaml",)
        raise ValueError(f"unqualified configuration accessor source identity: {name}{keys}")

    def __enter__(self):
        if self.config._doc.cache_info().currsize or self.config._parts_registry.cache_info().currsize:
            raise ValueError("actual configuration source capture requires a fresh CLI process")
        self.original["_load"] = self.config._load
        def captured_load(path):
            path = Path(path).resolve()
            payload = path.read_bytes()
            sha = hashlib.sha256(payload).hexdigest().upper()
            previous = self.loaded_config_sha.setdefault(str(path),sha)
            if previous!=sha:
                raise RuntimeError(f"configuration source changed across actual parses: {path}")
            self.loaded_config_payloads.setdefault(str(path),payload)
            return self.config.yaml.safe_load(payload.decode("utf-8")) or {}
        self.config._load = captured_load
        for name,original in tuple(vars(self.config).items()):
            if name.startswith("_") or not inspect.isfunction(original) or original.__module__!=self.config.__name__:
                continue
            self.original[name] = original
            def traced(*args,_name=name,_original=original,**kwargs):
                bound = inspect.signature(_original).bind(*args,**kwargs)
                bound.apply_defaults()
                keys = tuple(item for parameter,value in bound.arguments.items()
                             for item in (value if isinstance(value,tuple) else (value,)))
                snapshots = {str(path):_byte_sha(path) for path in self._paths(_name,keys)}
                value = _original(*args,**kwargs)
                snapshots = {path:self.loaded_config_sha.get(path,sha)
                             for path,sha in snapshots.items()}
                if _name=="parts":
                    def registry_row(stem,row):
                        def record_field(field,item,caller):
                            metadata = field in _PART_METADATA_KEYS
                            hashes = self.non_geometry_before if metadata else self.before
                            values = self.non_geometry_values if metadata else self.values
                            for path in self._paths("parts",(stem,)):
                                path = str(path)
                                hashes.setdefault(path,self.loaded_config_sha[path])
                            identity = f"parts:{stem}/{field}"
                            values[identity] = json.loads(json.dumps(item))
                            site = (caller.f_code.co_filename,caller.f_code.co_name,caller.f_lineno)
                            self.call_sites.setdefault(identity,set()).add(site)
                        return RegistryFieldReads(row,record_field)
                    if keys and keys[0] is not None:
                        return registry_row(keys[0],value)
                    return {stem:registry_row(stem,row) for stem,row in value.items()}
                geometric,metadata = (None,value) if _name=="provenance" else (value,None)
                identity = f"{_name}:"+"/".join(str(key) for key in keys)
                if geometric is not None and (not isinstance(geometric,dict) or geometric):
                    for path,sha in snapshots.items():
                        self.before.setdefault(path,sha)
                    self.values[identity] = json.loads(json.dumps(geometric))
                if metadata is not None and (not isinstance(metadata,dict) or metadata):
                    for path,sha in snapshots.items():
                        self.non_geometry_before.setdefault(path,sha)
                    self.non_geometry_values[identity] = json.loads(json.dumps(metadata))
                caller = sys._getframe(1)
                site = (caller.f_code.co_filename,caller.f_code.co_name,caller.f_lineno)
                self.call_sites.setdefault(identity,set()).add(site)
                return value
            setattr(self.config,name,traced)
        return self

    def __exit__(self,*exc):
        for name,original in self.original.items():
            setattr(self.config,name,original)

    def consumed_config_payloads(self) -> dict:
        """Exclude unrelated registry rows parsed only by the shared cache."""
        return {path:self.loaded_config_payloads[path]
                for path in self.before.keys() | self.non_geometry_before.keys()
                if path in self.loaded_config_payloads}


from diagnostics.stock_form_contact_3d import (
    ContactPair, ContactSearch, EndFacePatch, GapAngles, Placement, analyse_3d_mesh,
    loaded_driven_contact, profile_record,
)
from stock_form_cutter import StockFormProfile
from diagnostics.stock_form_root_angles import RootAngularDomain
from diagnostics.stock_form_root_sweep import root_free_intervals
from dt_cone_mesh_domain import nominal_source_subdomain, budget_clock_subdomain


@dataclass(frozen=True)
class PoseDomain:
    """Retained source bands, not reduced tolerances for numerical convenience.

    Relative radial uncertainty is a BALL: every direction of both runouts
    and bearing opening is included. Enumerated axial/tilt endpoints below
    are report witnesses, not a certificate of that continuous ball.
    """

    cone_axial_shift_mm: tuple[float, float]
    drum_axial_shift_mm: tuple[float, float]
    cone_face_width_mm: tuple[float, float]
    drum_face_width_mm: tuple[float, float]
    relative_radial_ball_mm: float
    inclination_rad: tuple[float, float]
    sources: tuple[str, ...]
    drum_axis_angle_rad: float = 0.0
    drum_cock_pivot_lever_mm: float = 0.0
    cone_support_projection_mm: tuple[float,float,float] = (0.0,0.0,0.0)
    cone_support_projection_terms: tuple = ()
    installed_axis_acceptance: tuple = ()

    def __post_init__(self):
        for name in ("cone_axial_shift_mm", "drum_axial_shift_mm",
                     "cone_face_width_mm", "drum_face_width_mm", "inclination_rad"):
            lo, hi = getattr(self, name)
            if not all(math.isfinite(v) for v in (lo, hi)) or lo > hi:
                raise ValueError(f"{name} must be a finite ordered interval")
        if min(self.cone_face_width_mm + self.drum_face_width_mm) <= 0:
            raise ValueError("actual finite faces must be positive")
        if not math.isfinite(self.relative_radial_ball_mm) or self.relative_radial_ball_mm < 0:
            raise ValueError("relative radial uncertainty must be a finite nonnegative ball")
        if not math.isfinite(self.drum_axis_angle_rad) or not 0 <= self.drum_axis_angle_rad < math.pi/2:
            raise ValueError("drum bore-cock uncertainty must be finite and below a right angle")
        if not math.isfinite(self.drum_cock_pivot_lever_mm) or self.drum_cock_pivot_lever_mm < 0:
            raise ValueError("full-bore cock pivot lever must be finite and nonnegative")
        if len(self.cone_support_projection_mm)!=3 or any(
                not math.isfinite(value) or value<0 for value in self.cone_support_projection_mm):
            raise ValueError("source cone support projections must be finite nonnegative XYZ bounds")
        if not self.sources:
            raise ValueError("pose domain requires source provenance")


def cone_frame(inclination_rad: float) -> np.ndarray:
    """Transpose the assembly's ROT_Y_INCLINE row-vector matrix exactly."""
    c, s = math.cos(inclination_rad), math.sin(inclination_rad)
    return np.array(((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c)))


def cylinder_native_rows(lock_rad: float) -> np.ndarray:
    """Actual compose_rows(ROT_Y_180, rot_z_rows(-lock)), no native import."""
    c, s = math.cos(lock_rad), math.sin(lock_rad)
    return np.array(((-c, s, 0.0), (s, c, 0.0), (0.0, 0.0, -1.0)))


def placement_from_geometry(geometry: dict[str, Any], *,
                            inclination_rad: float | None = None,
                            cone_shift_mm: float = 0.0, drum_shift_mm: float = 0.0,
                            cone_width_mm: float | None = None,
                            drum_width_mm: float | None = None,
                            radial_offset_mm: tuple[float, float] = (0.0, 0.0)) -> Placement:
    """Source assembly centres, finite faces and tooth/flat datum in mm.

    Rows native Ry180 are retained by pose_record; the symmetric straight
    cylinder is represented here in the mathematically positive world frame.
    The adapter accepts no helical-cylinder substitution.
    """
    axis = np.asarray(geometry["cone_axis"], dtype=float)
    tilt = math.atan2(axis[0], axis[2]) if inclination_rad is None else inclination_rad
    frame = cone_frame(tilt)
    origin = np.asarray(geometry["cone_centre_mm"], dtype=float) + cone_shift_mm * frame[:, 2]
    width = geometry["cone_face_width_mm"] if cone_width_mm is None else cone_width_mm
    zlo, zhi = geometry["drum_z_limits_mm"]
    drum_width = zhi-zlo if drum_width_mm is None else drum_width_mm
    dx, dy = geometry["drum_axis_xy_mm"]
    driven_origin = (dx+radial_offset_mm[0], dy+radial_offset_mm[1], (zlo+zhi)/2+drum_shift_mm)
    # Source supplies the ACTUAL native canonical-gap clocks. The cone
    # builder's pi/T is applied once; the reflected drum subtracts pi/N.
    driver_clock, driven_clock = geometry["native_gap_clocks_rad"]
    if not all(math.isfinite(value) for value in (driver_clock, driven_clock)):
        raise ValueError("actual native canonical-gap clocks must be finite")
    return Placement(tuple(float(v) for v in origin), driven_origin, frame, np.eye(3),
                     (-width/2, width/2), (-drum_width/2, drum_width/2),
                     driver_clocking_rad=driver_clock,
                     driven_clocking_rad=driven_clock)


def pose_record(pair: ContactPair, geometry: dict, home: tuple[float, float]) -> dict:
    datum = geometry["manufactured_datum_mapping"]
    setup = datum["physical_driven_setup_rotation_rad"]
    return {"placement": pair.placement.record(),
            "assembly_cone_rows": pair.placement.driver_frame.T.tolist(),
            "saved_cad_cylinder_rows": cylinder_native_rows(-home[1]).tolist(),
            "operating_cylinder_rows": cylinder_native_rows(-home[1]-setup).tolist(),
            "physical_driven_setup_rotation_rad":setup,
            "native_cylinder_local_face_mm": [0.0, geometry["drum_z_limits_mm"][1]-geometry["drum_z_limits_mm"][0]],
            "native_cylinder_origin_mm": [*geometry["drum_axis_xy_mm"], geometry["drum_z_limits_mm"][1]],
            "cylinder_reparameterisation": "native phase sign reversed, local Z reflected; explicit physical NOTCH-up setup rotates integral cam and teeth together",
            "phase_datum": datum,
            "mechanical_zero_rad": geometry["mechanical_zero_rad"]}


def cutter_q_domain(cutter, translations: tuple[float,float]) -> tuple[float,float] | None:
    """Exact Q extrema over the complete finite reference/T rectangle."""
    lo,hi = translations
    if lo>hi:
        return None
    rb,k = cutter.base_radius_mm,cutter.half_space_base_angle_rad
    u0,u1 = cutter.flank_parameter_min,cutter.flank_parameter_max
    values = []
    for shift in (lo,hi):
        parameters = [u0,u1]
        if shift != 0.0 and abs(rb/shift)<=1:
            angle = math.acos(-rb/shift)
            for sign in (-1,1):
                first = math.ceil((k+u0-sign*angle)/(2*math.pi))
                last = math.floor((k+u1-sign*angle)/(2*math.pi))
                parameters.extend(sign*angle+2*j*math.pi-k for j in range(first,last+1))
        values.extend(rb*u+shift*math.sin(k+u) for u in parameters)
    error = 512*np.finfo(float).eps*(1+rb*u1+max(abs(lo),abs(hi)))
    return min(values)-error,max(values)+error


def exact_smooth_ff_exclusion(pair: ContactPair) -> dict:
    """Necessary common-normal test for two straight, nonparallel XZ axes.

    The only smooth common normal is +/-Y. For either cutter-flank side,
    rotating its normal to sign*Y gives radial y=sign*Q. Opposed normals
    therefore require Q_A+Q_B=+/-centre_y_difference for ALL four side
    arrangements, with Q=rb*u+T*sin(k+u). Bound Q on actual finite support.
    A positive residual excludes smooth FF only, never allowed edge carry.
    """
    if pair.driver.helix_angle_deg or pair.driven.helix_angle_deg:
        raise ValueError("smooth straight-flank exclusion cannot be used for a helical solid")
    a, b = pair.placement.driver_frame[:, 2], pair.placement.driven_frame[:, 2]
    cross = np.cross(a, b)
    norm = float(np.linalg.norm(cross))
    if norm <= 1e-12 or abs(abs(cross[1]/norm)-1.0) > 1e-12:
        return {"excluded": False, "reason": "axes do not have the required nonparallel XZ common-normal geometry"}
    def q_min(profile):
        rb, shift = profile.template.base_radius_mm, profile.radial_translation_mm
        k, u0, u1 = profile.template.half_space_base_angle_rad, profile.flank_parameter_min, profile.flank_parameter_max
        # dQ/du=rb+T*cos(k+u) is the same positive radial-tangent certificate.
        GapAngles(profile).radial_slope_bound()
        return rb*u0+shift*math.sin(k+u0)
    qa, qb = q_min(pair.driver), q_min(pair.driven)
    dy = pair.placement.driver_origin_mm[1]-pair.placement.driven_origin_mm[1]
    error = pair.driver.geometry_error_bound_mm+pair.driven.geometry_error_bound_mm
    residual = qa+qb-abs(dy)-error
    return {"excluded": residual > 0.0,
            "branch": "all four smooth flank-side arrangements",
            "common_normal_world": [0.0, 1.0, 0.0],
            "driver_Q_min_mm": qa, "driven_Q_min_mm": qb,
            "opposed_normal_position_residual_lower_mm": residual,
            "smooth_ff_coverage_upper":0.0 if residual > 0.0 else None,
            "coverage_definition": "smooth FF branch only; finite tip and axial edges are not counted"}


def loaded_phase_at(pair: ContactPair, driver_phase_rad: float, *,
                    maximum_error_mm: float = 0.0002, driver_sense: int = -1,
                    position_error_mm: float = 0.0,
                    radial_error_mm: float = 0.0, axial_error_mm: float = 0.0) -> dict:
    """Root the saved native index, then report absolute physical notch TE.

    The connected-component seed is the actual source canonical-GAP clock,
    not the physical zero and not a fitted loaded home. Beta is the world
    positive canonical-GAP angle; its notch ray is beta minus pi/2.
    """
    if pair.driver.helix_angle_deg or pair.driven.helix_angle_deg:
        raise ValueError("the actual cone/drum train has two source-owned straight forms")
    ratio = pair.driver.teeth/pair.driven.teeth
    datum_tooth = pair.placement.driven_clocking_rad-ratio*driver_phase_rad
    half = pair.driven.angular_pitch_rad/2
    query = ContactSearch(pair, driver_phase_rad, driven_phase_rad=datum_tooth,
                          position_error_mm=position_error_mm,
                          radial_error_mm=radial_error_mm,axial_error_mm=axial_error_mm)
    initial = query.window(maximum_error_mm)
    if initial.root_contact:
        raise ValueError(f"actual pose has a root-material-limited nonworking window at cone phase {driver_phase_rad:.17g}")
    if not initial.no_overlap:
        raise ValueError(f"no interval-certified free carrying window at cone phase {driver_phase_rad:.17g}")
    # Search both sides of the indexed datum, never across a full tooth
    # discontinuity. Root API verifies both signs including surface errors.
    result = None
    failures = []
    for fraction in (0.0625, 0.125, 0.25, 0.375, 0.49):
        try:
            result = loaded_driven_contact(pair, driver_phase_rad, driver_sense=driver_sense,
                driven_bracket_rad=(datum_tooth-half*fraction, datum_tooth+half*fraction),
                maximum_error_mm=maximum_error_mm,position_error_mm=position_error_mm,
                radial_error_mm=radial_error_mm,axial_error_mm=axial_error_mm)
            break
        except (ValueError, RuntimeError) as error:
            failures.append(str(error))
    if result is None:
        raise ValueError("actual loaded edge refused: "+"; ".join(dict.fromkeys(failures)))
    contact = result["contact"]
    kind = contact["kind"]
    if "root_corner" in kind or "axial_interior" in kind or kind.split("/")[0] not in ("flank","radial","tip_arc"):
        raise ValueError(f"unsupported root/blank/axial-interior carrying: {kind}")
    if kind.startswith("tip_arc") and not any(feature in kind for feature in ("tip_corner","axial_edge")):
        raise ValueError("unsupported smooth blank carrying; tip land is not an active upper flank")
    if not contact["common_normal_supported"] or contact["opposed_normal_residual"] > contact["common_normal_error_bound"]:
        raise ValueError("actual carrying point has no bounded positive common-normal cone")
    if not math.isfinite(contact["driven_per_driver_velocity"]) or contact["driven_per_driver_velocity"] >= 0.0:
        raise ValueError("carrying normal has no certified negative driven/driver velocity")
    from dt_cone_mesh_domain import manufactured_datum_mapping
    mapping = manufactured_datum_mapping(pair.driver.teeth)
    zero = mapping["mechanical_zero_rad"]
    datum = zero["driven"]-ratio*(driver_phase_rad-zero["driver"])
    result.update(mechanical_datum_rad=datum,
                  manufactured_datum_mapping=mapping,
                  signed_running_te_rad=result["driven_phase_rad"]-datum,
                  signed_running_te_interval_rad=[value-datum for value in result["driven_phase_interval_rad"]],
                  datum_tare_rad=None,
                  cam_notch_cone_lock_home_retained=True)
    return result


def signed_read_matrix(pair: ContactPair, phases_rad: tuple[float, ...], *,
                       maximum_error_mm: float = 0.0002,
                       position_error_mm: float = 0.0,
                       radial_error_mm: float = 0.0, axial_error_mm: float = 0.0,
                       phase_intervals_rad: tuple[tuple[float,float],...] | None = None) -> dict:
    if not phases_rad or not all(math.isfinite(phase) for phase in phases_rad):
        raise ValueError("actual read stations must be explicitly finite and nonempty")
    intervals = tuple((phase,phase) for phase in phases_rad) if phase_intervals_rad is None else phase_intervals_rad
    if len(intervals)!=len(phases_rad) or any(
            not math.isfinite(lo) or not math.isfinite(hi) or lo>hi for lo,hi in intervals):
        raise ValueError("actual read intervals must match all read stations and have finite ordered bounds")
    rows = []
    for phase,(lo,hi) in zip(phases_rad,intervals):
        centre,half = (lo+hi)/2,(hi-lo)/2
        phase_ball = 2*(pair.driver.blank_radius_mm+position_error_mm)*math.sin(min(math.pi,half)/2)
        try:
            value = loaded_phase_at(pair, centre, maximum_error_mm=maximum_error_mm,
                position_error_mm=position_error_mm,radial_error_mm=radial_error_mm+phase_ball,
                axial_error_mm=axial_error_mm)
            datum_motion = pair.driver.teeth/pair.driven.teeth*half
            te_lo,te_hi = value["signed_running_te_interval_rad"]
            value["signed_running_te_interval_rad"] = [te_lo-datum_motion,te_hi+datum_motion]
            value["read_phase_interval_rad"] = [lo,hi]
            rows.append({"driver_phase_rad": phase,"actual_read_centre_rad":centre,
                         "qualification":"interval bounded" if half else "pointwise bounded",**value})
        except (ValueError, RuntimeError) as error:
            rows.append({"driver_phase_rad": phase,"read_phase_interval_rad":[lo,hi],"qualification": "refused",
                         "reason": str(error), "signed_running_te_rad": None,
                         "signed_running_te_interval_rad": None})
    return {"rows": rows, "all_reads_bounded": all(row["qualification"] != "refused" for row in rows),
            "read_phase_scope":"explicit caller intervals" if phase_intervals_rad is not None else "explicit held-driver nominal phases; crank uncertainty is not fabricated",
            "units": "signed cylinder radians", "datum": "physical CAM-NOTCH/cone-lock zero; no alignment-index feature or mean/home subtraction"}


def configured_pose_domain(teeth: int, inputs, *, cone_radius_upper_mm: float,
                           installed=None) -> PoseDomain:
    """Source OUTER intersected with optional observable installed shaft limits."""
    import cone_line
    import cone_stack_end_play as endplay
    import cylinder_bank_layout as bank
    import dt_cone_gear_stack as stack
    import dt_cone_gear_spec as cone
    import dt_cylinder_gear_spec as drum
    import _config
    import dt_cone_support_pose as support
    j = (120-teeth)//6
    south, north = stack.face_band(j,"south"), stack.face_band(j,"north")
    axial_lo = min(south[1],north[1])
    axial_hi = max(south[0],north[0])+endplay.CONE_FLOAT_NORTH
    bank_hi, bank_lo = bank.partial_stack_band(bank.COUNT-1-j)
    drum_lo = -bank_hi-bank.BANK_END_PLAY[1]-drum.FACE_WIDTH_TOLERANCE_MM/2
    drum_hi = -bank_lo+drum.FACE_WIDTH_TOLERANCE_MM/2
    tilt = math.radians(cone_line.INCLINE_DEG)
    if not math.isfinite(cone_radius_upper_mm) or cone_radius_upper_mm<=0:
        raise ValueError("actual manufactured cone blank radius upper bound required")
    angle = support.cone_axis_angle_bound_rad(installed=installed)
    station = (cone_line.SHAFT_T120_STATION+cone_line.GEAR_AXIS_SHIFT
               +(cone_line.CONE_FACE_STATION_REFERENCE-cone.FACE_WIDTH)/2+j*cone_line.SEAT_PITCH)
    face_max = cone.FACE_WIDTH+max(cone.FACE_WIDTH_BAND)
    stations = (station-face_max/2+axial_lo,station+face_max/2+axial_hi)
    frame = cone_frame(tilt)
    ledgers = tuple(support.collar_projection_closure_terms_mm(
        *stations,cone_radius_upper_mm,tuple(frame[:,axis]),installed=installed) for axis in range(3))
    projections = tuple(sum(ledger.values()) for ledger in ledgers)
    drum_angle = math.atan(drum.BORE_DIAMETRAL_CLEARANCE_MM[1] /
                           (drum.OVERALL_THICKNESS+min(drum.OVERALL_THICKNESS_BAND)))
    return PoseDomain((axial_lo,axial_hi),(drum_lo,drum_hi),
        (cone.FACE_WIDTH+cone.FACE_WIDTH_BAND[1],cone.FACE_WIDTH+cone.FACE_WIDTH_BAND[0]),
        (drum.FACE_WIDTH-drum.FACE_WIDTH_TOLERANCE_MM,drum.FACE_WIDTH+drum.FACE_WIDTH_TOLERANCE_MM),
        inputs.opening_mm,(tilt-angle,tilt+angle),
        ("build_dt_drive_train_assembly: ROT_Y_INCLINE, Ry180*Rz(-lock), _place_on_shaft",
         "dt_cone_gear_stack.face_band + cone_stack_end_play.CONE_FLOAT_NORTH",
         "cylinder_bank_layout.partial_stack_band + BANK_END_PLAY + cylinder face grade",
         "solve_stock_form_cones.configured_inputs: relative radial ball bounds runout at EVERY angle and journal opening",
         "dt_cone_support_pose complete finite post BOTH ends intersect retained tip; whole source budgets, common translations once; BASIC incline/CRANK FCF are not cone angular grades",
         "drum bore cock=atan(max matched bore clearance/min full bore length); every pivot within full max bore and every yaw direction enclosed"),
         drum_axis_angle_rad=drum_angle,
         drum_cock_pivot_lever_mm=drum.OVERALL_THICKNESS+max(drum.OVERALL_THICKNESS_BAND)
             -(drum.FACE_WIDTH-drum.FACE_WIDTH_TOLERANCE_MM)/2,
         cone_support_projection_mm=projections,
         cone_support_projection_terms=tuple(tuple(ledger.items()) for ledger in ledgers),
         installed_axis_acceptance=tuple(asdict(installed).items()) if installed is not None else ())


def pose_corner_records(geometry: dict, domain: PoseDomain) -> list[dict]:
    rows = []
    # Radial directions are explicit witnesses. The continuous ball is NOT
    # certified by these four directions, and is retained separately.
    r = domain.relative_radial_ball_mm
    offsets = ((0.0,0.0),(-r,0.0),(r,0.0),(0.0,-r),(0.0,r))
    for cs,ds,cw,dw,tilt,offset in itertools.product(
            sorted(set(domain.cone_axial_shift_mm)),sorted(set(domain.drum_axial_shift_mm)),
            sorted(set(domain.cone_face_width_mm)),sorted(set(domain.drum_face_width_mm)),
            sorted(set(domain.inclination_rad)),offsets):
        pose = placement_from_geometry(geometry,inclination_rad=tilt,
            cone_shift_mm=cs,drum_shift_mm=ds,cone_width_mm=cw,drum_width_mm=dw,
            radial_offset_mm=offset)
        rows.append({"corner": {"cone_axial_mm":cs,"drum_axial_mm":ds,
            "cone_face_mm":cw,"drum_face_mm":dw,"inclination_rad":tilt,
            "radial_offset_mm":offset}, "placement":pose.record()})
    return rows


def profile_motion_ball(nominal: StockFormProfile, corners: tuple[StockFormProfile,...]) -> float:
    """Hausdorff enclosure for the actual finite translated straight forms.

    Tool curves translate by deltaT. Moving their blank intersections costs
    at most (deltaR+deltaT)/cos(radial tangent). Include radial continuation
    and every translation endpoint; a polar fold refuses this enclosure.
    """
    if any(profile.template != nominal.template or profile.teeth != nominal.teeth or profile.helix_angle_deg
           for profile in corners):
        raise ValueError("manufacturing motion ball requires the same finite straight cutter")
    translations = [nominal.radial_translation_mm, *(p.radial_translation_mm for p in corners)]
    template = nominal.template
    rb,k = template.base_radius_mm,template.half_space_base_angle_rad
    u0,u1 = template.flank_parameter_min,template.flank_parameter_max
    angles = [k+u0,k+u1]
    angles.extend(j*math.pi for j in range(math.ceil((k+u0)/math.pi),math.floor((k+u1)/math.pi)+1))
    smin = min(rb+translation*math.cos(z) for translation in translations for z in angles)
    if u0 == 0 and template.root_radius_mm < rb:
        smin = min(smin,*(template.root_radius_mm+t*math.cos(k) for t in translations))
    rmax = max(p.blank_radius_mm for p in (nominal,*corners))
    if smin <= 0:
        raise ValueError("manufacturing corner crosses a polar radial fold")
    cosine = min(1.0,smin/rmax)
    return max((abs(p.radial_translation_mm-nominal.radial_translation_mm)
                +(abs(p.blank_radius_mm-nominal.blank_radius_mm)
                  +abs(p.radial_translation_mm-nominal.radial_translation_mm))/cosine)
               for p in corners)


def complete_pose_errors(pair: ContactPair, domain: PoseDomain, *,
                         profile_motion_mm: float = 0.0) -> tuple[float,float]:
    """Driver-local radial/axial enclosure of EVERY booked source pose.

    Cone float moves along its own physical axis: it cannot be silently paid
    as radial runout. Drum axial motion projects by sin/cos of the actual
    incline. Arbitrary bore-cock azimuths use the exact small-rotation radial
    and axial envelopes, not cardinal sampling or a fabricated scalar C.
    """
    p = pair.placement
    if not math.isfinite(profile_motion_mm) or profile_motion_mm < 0:
        raise ValueError("manufacturing profile motion must be finite and nonnegative")
    cone_width = p.driver_face_mm[1]-p.driver_face_mm[0]
    drum_width = p.driven_face_mm[1]-p.driven_face_mm[0]
    cone_axial = max(map(abs,domain.cone_axial_shift_mm))
    drum_axial = max(map(abs,domain.drum_axial_shift_mm))
    cone_face = max(abs(width-cone_width) for width in domain.cone_face_width_mm)/2
    drum_face = max(abs(width-drum_width) for width in domain.drum_face_width_mm)/2
    lo,hi = domain.inclination_rad
    critical = [lo,hi,*(j*math.pi/2 for j in range(math.ceil(2*lo/math.pi),math.floor(2*hi/math.pi)+1))]
    sine,cosine = max(abs(math.sin(angle)) for angle in critical),max(abs(math.cos(angle)) for angle in critical)
    nominal_tilt = math.atan2(p.driver_frame[0,2],p.driver_frame[2,2])
    tilt = max(abs(value-nominal_tilt) for value in domain.inclination_rad)
    # A potentially colliding point lies inside the actual finite driver.
    # Bound frame rotation on that interaction neighbourhood, not on the far
    # side of the entire drum. Its nominal preimage includes every booked
    # centre/cock/axial/profile displacement before applying the frame error.
    beta = domain.drum_axis_angle_rad
    axial_reach = max(map(abs,p.driven_face_mm))+drum_face+domain.drum_cock_pivot_lever_mm
    drum_radius = pair.driven.blank_radius_mm+profile_motion_mm
    drum_radial = drum_radius*(1-math.cos(beta))+axial_reach*math.sin(beta)
    drum_z = drum_radius*math.sin(beta)+axial_reach*(1-math.cos(beta))
    reach = (math.hypot(pair.driver.blank_radius_mm+profile_motion_mm,
                       max(domain.cone_face_width_mm)/2)+cone_axial
             +domain.relative_radial_ball_mm+drum_axial+drum_face
             +math.hypot(drum_radial,drum_z)+profile_motion_mm)
    frame_error = 0.0 if domain.cone_support_projection_terms else 2*reach*math.sin(tilt/2)
    radial = (domain.relative_radial_ball_mm+sine*(drum_axial+drum_face)
              +frame_error+drum_radial+sine*drum_z+math.hypot(*domain.cone_support_projection_mm[:2]))
    axial = (domain.relative_radial_ball_mm+cone_axial+cone_face
             +cosine*(drum_axial+drum_face)+frame_error+sine*drum_radial+cosine*drum_z
             +domain.cone_support_projection_mm[2])
    return radial,axial


def finite_circular_band_radial_lower(pair: ContactPair, radius_mm: float,
                                     local_z_band_mm: tuple[float,float]) -> float:
    """Exact lower distance to the inclined axis for a finite vertical disk.

    The full disk is a conservative superset of actual eccentric cam material.
    On the XZ pose its squared radial distance on the circumference is a
    concave quadratic in cos(theta), so the nearest point lies on +/-X unless
    the inclined axis intersects the disk. Finite axial endpoints suffice.
    """
    p = pair.placement
    if (not math.isfinite(radius_mm) or radius_mm<0 or
            not all(math.isfinite(z) for z in local_z_band_mm) or local_z_band_mm[0]>local_z_band_mm[1]):
        raise ValueError("finite circular radius and ordered axial interval required")
    if not np.allclose(p.driven_frame,np.eye(3),rtol=0,atol=1e-14) or abs(p.driver_frame[1,2])>1e-14:
        raise ValueError("circular-band proof requires the actual XZ cone and vertical drum axes")
    centre = np.asarray(p.driven_origin_mm)-p.driver_origin_mm
    if abs(centre[1])>1e-12:
        raise ValueError("circular-band centre must use the actual common-Y source datum")
    c,s = p.driver_frame[0,0],p.driver_frame[0,2]
    endpoints = tuple(c*centre[0]-s*(centre[2]+z) for z in local_z_band_mm)
    lo,hi = min(endpoints),max(endpoints)
    nearest = 0.0 if lo<=0<=hi else min(abs(lo),abs(hi))
    guard = 128*np.finfo(float).eps*(1+abs(centre[0])+abs(centre[2])+radius_mm+max(map(abs,local_z_band_mm)))
    return max(0.0,nearest-abs(c)*radius_mm-guard)


def configured_cam_exclusion(pair: ContactPair, *, radial_error_mm: float,
                              profile_motion_mm: float) -> dict:
    import dt_cylinder_gear_spec as drum
    cam_radius = ((drum.CAM_DIA+max(drum.CAM_DIA_BAND))/2+drum.ECCENTRICITY
                  +drum.ECCENTRICITY_TOLERANCE_MM+drum.SET_ECCENTRICITY_RANGE_MM)
    face_min = drum.FACE_WIDTH-drum.FACE_WIDTH_TOLERANCE_MM
    z_band = (-(drum.OVERALL_THICKNESS+max(drum.OVERALL_THICKNESS_BAND)-face_min/2),-face_min/2)
    minimum = finite_circular_band_radial_lower(pair,cam_radius,z_band)
    clearance = minimum-radial_error_mm-profile_motion_mm-pair.driver.blank_radius_mm
    return {"qualified":bool(clearance>0),"cam_outer_radius_upper_mm":cam_radius,
            "native_cam_local_z_band_mm":(face_min,drum.OVERALL_THICKNESS+max(drum.OVERALL_THICKNESS_BAND)),
            "world_positive_cam_local_z_band_mm":z_band,
            "nominal_radial_distance_lower_mm":minimum,"clearance_lower_mm":clearance,
            "source":"dt_cylinder_gear_spec CAM/OVERALL/E bands; full-bore pivot and every yaw already enclosed",
            "proof":"full eccentric-cam circular/axial superset outside actual cone blank for every retained pose; no cap/shoulder carrying substitution"}


def root_domain_probe(pair: ContactPair, *, position_error_mm: float = 0.0,
                      radial_error_mm: float = 0.0, axial_error_mm: float = 0.0) -> dict | None:
    """Actual root-strip evidence only; full RootArc material is not refused."""
    search = ContactSearch(pair,0.0,position_error_mm=position_error_mm,
                           radial_error_mm=radial_error_mm,axial_error_mm=axial_error_mm)
    root = RootAngularDomain(pair.driver,search.gap)
    for tooth in range(pair.driven.teeth):
        for segment in search.segments:
            stations = (0.25,0.5,0.75,1.0) if isinstance(segment,EndFacePatch) else (
                pair.placement.driven_face_mm[0],sum(pair.placement.driven_face_mm)/2,
                pair.placement.driven_face_mm[1])
            for parameter,station in itertools.product((0.0,0.5,1.0),stations):
                if not search.surface_member(segment,parameter,station):
                    continue
                _,local = search.point(segment,tooth,parameter,station)
                radius = math.hypot(local[0],local[1])
                lo,hi = pair.placement.driver_face_mm
                if (radius-search.radial_error_mm < pair.driver.root_radius_max_mm
                        and lo-search.axial_error_mm <= local[2] <= hi+search.axial_error_mm):
                    world,_ = search.point(segment,tooth,parameter,station)
                    return {
                        "driven_tooth":tooth,"segment":segment.name,"parameter":parameter,
                        "physical_station_mm":segment.station_mm if isinstance(segment,EndFacePatch) else station,
                        "world_point_mm":tuple(float(value) for value in world),
                        "driver_local_point_mm":tuple(float(value) for value in local),
                        "driver_radius_mm":radius,"driver_root_max_mm":pair.driver.root_radius_max_mm,
                        "driver_root_min_mm":pair.driver.root_radius_min_mm,
                        "position_ball_mm":position_error_mm,"radial_error_mm":search.radial_error_mm,
                        "axial_error_mm":search.axial_error_mm,
                        "point_below_root_max":radius<pair.driver.root_radius_max_mm,
                        "driven_actual_material_member":True,
                        "driver_actual_material_member_at_declared_phase":pair.driver.contains_material(
                            float(local[0]),float(local[1]),
                            rotate_rad=pair.placement.driver_clocking_rad+pair.driver.angular_pitch_rad/2),
                        "exact_root_gap_enclosure":asdict(root.bounds(max(0.0,radius-search.radial_error_mm),
                                                                     radius+search.radial_error_mm)),
                        "profile_solid_interference_certified":radius<pair.driver.root_radius_min_mm-pair.driver.geometry_error_bound_mm
                            and lo<local[2]<hi,
                        "physical_native_or_bore_certificate":False,
                        "proof":"actual finite material point plus full RootArc interval authority; root-strip reach is not working contact or a no-solution certificate",
                    }
    return None


def loaded_root_air_bounds(pair: ContactPair, driver_phase_rad: float,
                           driven_gap_interval_rad: tuple[float,float], *,
                           driver_phase_half_width_rad: float = 0.0,
                           position_error_mm: float = 0.0,
                           radial_error_mm: float = 0.0, axial_error_mm: float = 0.0,
                           maximum_error_mm: float = 0.0002,
                           extra_root_air_mm: float = 0.0) -> dict:
    """Actual RootArc air .02/.10 plus an explicitly tested uniform reserve."""
    if not math.isfinite(extra_root_air_mm) or extra_root_air_mm<0:
        raise ValueError("extra RootArc air must be finite and nonnegative")
    gap_lo,gap_hi = driven_gap_interval_rad
    if not all(math.isfinite(v) for v in (gap_lo,gap_hi,driver_phase_half_width_rad)) or gap_lo>gap_hi or driver_phase_half_width_rad<0:
        raise ValueError("finite ordered actual loaded phase enclosure required")
    tooth_phase = (gap_lo+gap_hi)/2+pair.driven.angular_pitch_rad/2
    mate_half = (gap_hi-gap_lo)/2
    mate_motion = 2*pair.driven.blank_radius_mm*math.sin(min(math.pi,mate_half)/2)
    forward = root_free_intervals(ContactSearch(pair,driver_phase_rad,
        driven_phase_rad=tooth_phase,position_error_mm=position_error_mm,
        radial_error_mm=radial_error_mm+mate_motion,axial_error_mm=axial_error_mm+mate_motion),
        maximum_error_mm=maximum_error_mm,required_root_air_mm=.02+extra_root_air_mm)
    p = pair.placement
    reverse_pose = Placement(p.driven_origin_mm,p.driver_origin_mm,
        p.driven_frame,p.driver_frame,p.driven_face_mm,p.driver_face_mm,
        driver_clocking_rad=tooth_phase,
        driven_clocking_rad=p.driver_clocking_rad+driver_phase_rad)
    reverse_pair = ContactPair(pair.name+" reverse root-air",pair.driven,pair.driver,reverse_pose)
    # The inverse relative rigid transform preserves the Cartesian norm of
    # its displacement. Isotropically enclose the complete directional box.
    pose_norm = math.hypot(position_error_mm+radial_error_mm,
                           position_error_mm+axial_error_mm)
    cone_motion = 2*pair.driver.blank_radius_mm*math.sin(min(math.pi,driver_phase_half_width_rad)/2)
    reverse = root_free_intervals(ContactSearch(reverse_pair,0.0,
        position_error_mm=pose_norm+cone_motion),
        maximum_error_mm=maximum_error_mm,required_root_air_mm=.10+extra_root_air_mm)
    def contains(bounds,half):
        return bounds.status=="resolved" and any(lo < -half and half < hi for lo,hi in bounds.free_inner)
    forward_ok,reverse_ok = contains(forward,driver_phase_half_width_rad),contains(reverse,mate_half)
    return {"qualified":forward_ok and reverse_ok,
            "cone_root_air_lower_mm":forward.root_air_lower_bound_mm if forward_ok else None,
            "drum_root_air_lower_mm":reverse.root_air_lower_bound_mm if reverse_ok else None,
            "driver_phase_half_width_rad":driver_phase_half_width_rad,
            "loaded_driven_phase_half_width_rad":mate_half,
            "forward":asdict(forward),"reverse":asdict(reverse),
            "requested_extra_air_mm":extra_root_air_mm,
            "required_cone_air_mm":.02+extra_root_air_mm,
            "required_drum_air_mm":.10+extra_root_air_mm,
            "root_is_carrying":False,
            "proof":"full continuous actual-material RootArc sweeps inflated by retained .02/.10 Euclidean air; entire actual phase intervals lie strictly in FREE INNER"}


def maximum_certified_root_air_capacity(
        pair: ContactPair,cells: list[dict],*,maximum_error_mm: float,
        position_error_mm: float = 0.0,radial_error_mm: float = 0.0,
        axial_error_mm: float = 0.0) -> dict:
    """Search actual full-phase FREE INNER proofs, never subtract floor flags.

    The returned positive lower bound is certified for every booked cell.
    A solver refusal only bounds this certification search, not physical air
    or stock feasibility. The separate finite upper bound follows because
    nonempty root and mate surfaces lie inside their actual finite solids.
    """
    if not math.isfinite(maximum_error_mm) or maximum_error_mm<=0:
        raise ValueError("air-capacity search needs a finite positive spatial tolerance")
    if not cells or not all(cell.get("root_air",{}).get("qualified",False) for cell in cells):
        return {"status":"baseline air unresolved","certified_extra_air_lower_mm":None,
                "physical_infeasibility_certified":False}
    p = pair.placement
    radius_a = math.hypot(pair.driver.blank_radius_mm,max(map(abs,p.driver_face_mm)))
    radius_b = math.hypot(pair.driven.blank_radius_mm,max(map(abs,p.driven_face_mm)))
    origin_distance = float(np.linalg.norm(np.asarray(p.driver_origin_mm)-p.driven_origin_mm))
    guard = 512*np.finfo(float).eps*(1+origin_distance+radius_a+radius_b)
    physical_upper = origin_distance+radius_a+radius_b+guard
    lo,hi = 0.0,physical_upper
    accepted = [cell["root_air"] for cell in cells]
    trials = []
    while hi-lo>maximum_error_mm:
        extra = (lo+hi)/2
        proofs = []
        failed = None
        for index,cell in enumerate(cells):
            phi_lo,phi_hi = cell["driver_interval_rad"]
            air = loaded_root_air_bounds(pair,(phi_lo+phi_hi)/2,
                tuple(cell["actual_driven_lower_interval_rad"]),
                driver_phase_half_width_rad=(phi_hi-phi_lo)/2,
                position_error_mm=position_error_mm,radial_error_mm=radial_error_mm,
                axial_error_mm=axial_error_mm,maximum_error_mm=maximum_error_mm,
                extra_root_air_mm=extra)
            if not air["qualified"]:
                failed = {"phase_cell_index":index,"root_air":air}
                break
            proofs.append(air)
        trials.append({"extra_air_mm":extra,"all_phase_cells_certified":failed is None,
                       "first_unresolved_cell":failed})
        if failed is None:
            lo,accepted = extra,proofs
        else:
            hi = extra
    return {"status":"positive reserve certified" if lo>0 else "no positive reserve certified",
        "certified_extra_air_lower_mm":lo,
        "cone_root_air_lower_mm":.02+lo,"drum_root_air_lower_mm":.10+lo,
        "certification_search_bracket_mm":[lo,hi],"search_tolerance_mm":maximum_error_mm,
        "finite_physical_extra_air_upper_mm":physical_upper,
        "finite_upper_proof":"any actual root point and actual mate material point are within the two finite body radii plus origin separation",
        "all_phase_cells":len(cells),"last_certified_phase_proofs":accepted,"trials":trials,
        "physical_infeasibility_certified":False,
        "scope":"maximum certified common extra .02/.10 air to stated search tolerance; an unresolved trial is not a physical upper or no-solution proof"}






def actual3d_nominal_te_enclosure(report: dict) -> tuple[float,float]:
    """Paid actual q=0 full-period range, never a fitted or mean reference."""
    if report.get("source_domain_proved") is not True:
        raise ValueError("nominal mathematical source subdomain is not proved")
    if not report["full_period_cells"]:
        raise ValueError("actual nominal full-period TE cells are missing")
    lower,upper = report["whole_period_signed_running_te_interval_rad"]
    if not math.isfinite(lower) or not math.isfinite(upper) or lower>upper:
        raise ValueError("actual nominal TE range is unresolved")
    return lower,upper


def stock_phase_3d_packet(cases: list[dict], reference: dict, *,
                          driver_read_phases_rad: tuple[float,...], ratio: float,
                          datum: dict) -> dict:
    """True point reference and paid same-stall/source profile half-widths."""
    if (len(cases)!=17 or len(driver_read_phases_rad)!=21
            or type(ratio) not in (int,float) or not math.isfinite(ratio) or not 0<ratio<=1
            or not all(type(phase) in (int,float) and math.isfinite(phase) for phase in driver_read_phases_rad)):
        raise ValueError("operating stock phase requires nominal/all16, all21 finite stalls and actual tooth ratio")
    full_profile_case_records(cases[0],cases[1:])
    rows = reference["actual_read_phases"]
    if (reference.get("source_domain_proved") is not True
            or tuple(row["actual_driver_phase_rad"] for row in rows)!=driver_read_phases_rad):
        raise ValueError("nominal q=0 actual read references are missing/reordered")
    reports = {"robust":[],"nominal_pose":[]}
    for case in cases:
        calculation = case["calculation"]
        for label,key in (("robust","budget_actual3d"),("nominal_pose","nominal_actual3d")):
            report = calculation[key]
            if (report.get("source_domain_proved") is not True or not report["full_period_cells"]
                    or tuple(row["actual_driver_phase_rad"] for row in report["actual_read_phases"])
                    !=driver_read_phases_rad):
                raise ValueError(f"{case['case_id']}: genuine phase/source/stall TE proof is absent")
            reports[label].append(report)
            for interval in itertools.chain(
                    (row["signed_running_te_interval_rad"] for row in report["actual_read_phases"]),
                    (cell["signed_running_te_interval_rad"] for cell in report["full_period_cells"])):
                if (len(interval)!=2 or any(type(value) not in (int,float) or not math.isfinite(value) for value in interval)
                        or interval[0]>interval[1]):
                    raise ValueError(f"{case['case_id']}: invalid actual signed TE interval")
    nominal_te,nominal_advance,numerical,robust,nominal_pose = [],[],[],[],[]
    for index,(phase,row) in enumerate(zip(driver_read_phases_rad,rows)):
        value = row["reference_signed_running_te_rad"]
        bound = row["reference_error_bound_rad"]
        lo,hi = row["signed_running_te_interval_rad"]
        if (type(value) not in (int,float) or type(bound) not in (int,float)
                or not math.isfinite(value) or not math.isfinite(bound) or bound<0
                or not math.isfinite(lo) or not math.isfinite(hi) or lo>hi
                or math.nextafter(value-bound,-math.inf)>lo or math.nextafter(value+bound,math.inf)<hi):
            raise ValueError("nominal point root/reference numerical bound is absent or does not enclose its genuine point proof")
        nominal_te.append(value)
        nominal_advance.append(value-ratio*phase)
        numerical.append(bound)
        def half_width(label):
            intervals = [report["actual_read_phases"][index]["signed_running_te_interval_rad"]
                         for report in reports[label]]
            values = [max(abs(low-value),abs(high-value)) for low,high in intervals]
            if not all(math.isfinite(item) for item in values):
                raise ValueError("source/profile half-width is not a finite actual TE enclosure")
            return math.nextafter(max(bound,max(values)),math.inf)
        robust.append(half_width("robust"))
        nominal_pose.append(half_width("nominal_pose"))
    def whole_period(label):
        intervals = [report["whole_period_signed_running_te_interval_rad"]
                     for report in reports[label]]
        lower,upper = min(row[0] for row in intervals),max(row[1] for row in intervals)
        if not math.isfinite(lower) or not math.isfinite(upper) or lower>upper:
            raise ValueError("residual TE phase-change interval is unresolved")
        return [lower,upper]
    return {
        "schema":"dt-cone-operating-stock-phase/1","operating_source_state":"OPERATING_NOTCH_UP",
        "driver_read_phases_rad":list(driver_read_phases_rad),"operating_driver_sense":-1,
        "nominal_driven_advance_rad":nominal_advance,"nominal_signed_running_te_rad":nominal_te,
        "nominal_reference_numerical_bound_rad":numerical,
        "robust_half_width_rad":robust,"nominal_pose_half_width_rad":nominal_pose,
        "robust_signed_te_interval_rad":whole_period("robust"),
        "nominal_pose_signed_te_interval_rad":whole_period("nominal_pose"),
        "half_width_scope":"nominal/all16 SAME requested stall; numerical reference bound included once",
        "phase_change_scope":"genuine whole-period intervals bound residual TE(psi+s)-TE(psi); pay the relevant width once when adding crank shaft advance",
        "shaft_advance_included":False,
        "excluded_terms":list(_BUDGET_EXCLUDED_TERMS),
        "manufactured_datum_mapping":datum,"datum_tare_rad":None,
    }




def _continuous_analysis(pair: ContactPair, domain: dict, *, phases: int,
                         maximum_error_mm: float, read_phases_rad: tuple[float,...]) -> dict:
    from stock_form_contact_certificate import (
        require_continuous_certificate,require_whole_period_envelope,require_actual_read_phase)
    report = analyse_3d_mesh(pair,continuous_source_domain=domain,
        phases=phases,maximum_error_mm=maximum_error_mm,coverage_min=1.1,row_min=0.0,
        handover_max_mm=.005,positive_backlash_min_mm=0.0,driver_sense=-1,
        read_driver_phases_rad=read_phases_rad)
    try:
        if report.get("source_domain_proved") is not True:
            raise ValueError("actual supplied source domain has not been mathematically proved")
        certificate = report["continuous_contact_certificate"]
        require_continuous_certificate(report,domain,pair.driver,pair.driven,
            certificate,coverage_floor=1.1,row_floor=0.0,handover_max_mm=.005)
        require_whole_period_envelope(report,domain,pair.driver,pair.driven)
        reads = report["actual_read_phases"]
        if tuple(row["actual_driver_phase_rad"] for row in reads)!=read_phases_rad:
            raise ValueError("actual mechanical read phases are missing or reordered")
        for phase,row in zip(read_phases_rad,reads):
            require_actual_read_phase(report,domain,pair.driver,pair.driven,row,
                expected_phase_rad=phase)
    except (KeyError,TypeError,ValueError) as error:
        report.update(source_domain_proved=False,production_source_qualified=False,
            qualified=False,certificate_replay_error=str(error))
    return report


def _te_discrepancy_upper(report: dict, reference_te: tuple[float,float]) -> float:
    cells = report["full_period_cells"]
    if not cells:
        raise ValueError("same-source actual driven endpoint cells are absent")
    bounds = [max(abs(cell["signed_running_te_interval_rad"][0]-reference_te[1]),
                  abs(cell["signed_running_te_interval_rad"][1]-reference_te[0]))
              for cell in cells]
    if not all(math.isfinite(value) for value in bounds):
        raise ValueError("nonfinite actual signed TE enclosure")
    return math.nextafter(max(bounds),math.inf)


def full_source_cam_exclusion(pair: ContactPair, domain: dict) -> dict:
    """Exclude the integral cam using the actual named source coordinates."""
    import dt_cylinder_gear_spec as drum
    axes = dict(domain["correlated_pose_parameters"])
    def magnitude(name):
        lo,hi = axes.get(name,(0.0,0.0))
        if not math.isfinite(lo) or not math.isfinite(hi) or lo>hi:
            raise ValueError("cam exclusion requires finite actual source axes")
        return max(abs(lo),abs(hi))
    def motion(body, radius):
        translation = math.sqrt(math.fsum(magnitude(f"{body}_d{axis}_mm")**2 for axis in "xyz"))
        eccentricity = math.sqrt(math.fsum(magnitude(f"{body}_ecc_{axis}_mm")**2 for axis in "xy"))
        angle = min(math.pi,math.fsum(magnitude(f"{body}_r{axis}_rad") for axis in "xyz"))
        return translation+eccentricity+2*radius*math.sin(angle/2)
    cone_width = max(domain["finite_face_width_limits_mm"]["driver"])
    cone_radius = math.hypot(pair.driver.blank_radius_mm,cone_width/2)
    cam_radius = ((drum.CAM_DIA+max(drum.CAM_DIA_BAND))/2+drum.ECCENTRICITY
                  +drum.ECCENTRICITY_TOLERANCE_MM+drum.SET_ECCENTRICITY_RANGE_MM)
    cam_reach = drum.OVERALL_THICKNESS+max(drum.OVERALL_THICKNESS_BAND)
    motions = {"driver":motion("driver",cone_radius),
               "driven":motion("driven",math.hypot(cam_radius,cam_reach))}
    error = math.nextafter(math.fsum(motions.values())+
        128*np.finfo(float).eps*(1+cone_radius+cam_radius+cam_reach),math.inf)
    record = configured_cam_exclusion(pair,radial_error_mm=error,profile_motion_mm=0.0)
    record.update(continuous_source_domain=domain,source_body_motion_upper_mm=motions,
        proof="finite integral cam circular/axial superset; actual named rigid/source eccentricity motions paid once, all printed profiles are evaluated separately")
    return record


def qualify_actual_pair(pair: ContactPair, *, continuous_source_domain: dict,
                        phases: int, maximum_error_mm: float,
                        read_phases_rad: tuple[float,...], planar_centre_mm: float,
                        selected_nominal_te_rad: tuple[float,float],
                        nominal_pose_report: dict) -> dict:
    """Consume genuine whole-q continuation/endpoints; never a scalar pose ball."""
    result = {"qualification":"refused","oblique_phase_bound_rad":None,
        "nominal_oblique_phase_bound_rad":None,"continuous_source_domain":continuous_source_domain,
        "smooth_3d_ff_screen":exact_smooth_ff_exclusion(pair),
        "nominal_actual3d_te_enclosure_rad":selected_nominal_te_rad,
        "reference_scope":"selected NOMINAL printed profiles, actual3D mathematical q=0 notch-up/cone-lock; no planar oracle or range mean",
        "oblique_phase_bound_excluded_terms":list(_BUDGET_EXCLUDED_TERMS)}
    try:
        robust = _continuous_analysis(pair,continuous_source_domain,phases=phases,
            maximum_error_mm=maximum_error_mm,read_phases_rad=read_phases_rad)
        result["all_corner_actual3d"] = robust
        result["actual_signed_read_phases"] = robust.get("actual_read_phases",[])
        if (continuous_source_domain.get("scope")!="FULL_PRODUCTION_SOURCE_DOMAIN"
                or continuous_source_domain.get("production_source_domain") is not True
                or robust.get("production_source_qualified") is not True
                or robust.get("source_domain_proved") is not True):
            raise ValueError("whole retained physical source domain is not production qualified")
        budget_domain = budget_clock_subdomain(continuous_source_domain)
        budget = _continuous_analysis(pair,budget_domain,phases=phases,
            maximum_error_mm=maximum_error_mm,read_phases_rad=read_phases_rad)
        result["budget_actual3d"] = budget
        if (budget.get("source_domain_proved") is not True
                or nominal_pose_report.get("source_domain_proved") is not True):
            raise ValueError("actual budget-clock or nominal-pose mathematical source proof is incomplete")
        cam = full_source_cam_exclusion(pair,continuous_source_domain)
        result["integral_cam_body_exclusion"] = cam
        if not cam["qualified"]:
            raise ValueError("actual integral cam-body exclusion unresolved")
        cells, arcs, inspection_cells, root_records = [], [], [], []
        rop = planar_centre_mm*pair.driven.teeth/(pair.driver.teeth+pair.driven.teeth)
        for source_cell in robust["full_period_cells"]:
            angular = source_cell["correlated_backlash"]["backlash_interval_rad"]
            arc = (math.nextafter(angular[0]*rop,-math.inf),math.nextafter(angular[1]*rop,math.inf))
            root = source_cell["root_air"]
            required = continuous_source_domain["root_air_requirements_mm"]
            if (root["root_air_requirements_mm"] != required or root["qualified"] is not True
                    or root["driver_root_air_lower_mm"] < required["driver"]
                    or root["driven_root_air_lower_mm"] < required["driven"]
                    or root["root_is_carrying"] is not False):
                raise ValueError("directed same-q driver/driven actual ROOT MATERIAL proofs are incomplete")
            arcs.append(arc)
            root_records.append(root)
            cells.append(source_cell)
            inspection_cells.append({
                "actual_driver_interval_rad":source_cell["actual_driver_interval_rad"],
                "correlated_backlash_interval_rad":angular,
                "source_calibrated_backlash_interval_mm":arc,
                "physical_pitch_arc_backlash_interval_mm":source_cell["correlated_backlash_interval_mm"]})
        if not cells:
            raise ValueError("whole-phase genuine endpoint/root-air cells are absent")
        reads = robust["actual_read_phases"]
        if tuple(row["actual_driver_phase_rad"] for row in reads) != read_phases_rad:
            raise ValueError("actual source-aware read stalls are missing, reordered or substituted")
        read_rows = []
        for row in reads:
            te = row["signed_running_te_interval_rad"]
            if len(te)!=2 or not all(math.isfinite(value) for value in te) or te[0]>te[1]:
                raise ValueError("unresolved actual signed operating-stall TE")
            phase = row["actual_driver_phase_rad"]
            read_rows.append({**row,"driver_phase_rad":phase,
                "read_phase_interval_rad":[phase,phase],
                "qualification":"interval bounded","datum_tare_rad":None})
        result["signed_read_matrix"] = {"rows":read_rows,"all_reads_bounded":True,
            "read_phase_scope":"genuine mechanical requested stalls over WHOLE physical source domain",
            "units":"signed cylinder radians","datum":continuous_source_domain["manufactured_datum_mapping"]}
        tight,loose = min(arc[0] for arc in arcs),max(arc[1] for arc in arcs)
        handover = max((row["pitch_displacement_jump_upper_mm"] for row in robust["handovers"]),default=0.0)
        margins = {"supported_union_coverage":robust["stock_form_coverage_lower"]-1.1,
            "handover_jump_mm":.005-handover,"tight_backlash_mm":tight-.06,"loose_backlash_mm":.41-loose,
            "cone_root_air_mm":min(row["driver_root_air_lower_mm"] for row in root_records)-required["driver"],
            "drum_root_air_mm":min(row["driven_root_air_lower_mm"] for row in root_records)-required["driven"]}
        result.update(margins=margins,full_period_cells=cells,
            source_inspection_backlash_cells=inspection_cells,root_air_proofs=root_records,
            actual_driven_backlash={"tight_lower_mm":tight,"loose_upper_mm":loose,
                "source_inspection_radius_mm":rop,"physical_driven_pitch_radius_mm":pair.driven.pitch_radius_mm,
                "definition":"same-q independently rooted original-index physical LOWER/UPPER differences; Rop calibration is not inverse-window conversion"},
            nominal_actual3d=nominal_pose_report)
        if any(not math.isfinite(value) or value<0 for value in margins.values()):
            raise ValueError("actual union/handover/.06..41 backlash/directed root-air gate refused")
        result.update(qualification="qualified",
            oblique_phase_bound_rad=_te_discrepancy_upper(budget,selected_nominal_te_rad),
            nominal_oblique_phase_bound_rad=_te_discrepancy_upper(nominal_pose_report,selected_nominal_te_rad),
            reason=None)
    except (KeyError,TypeError,ValueError,RuntimeError) as error:
        result["reason"] = str(error)
    return result


def measure_nominal_for_inspection(pair: ContactPair, *, phases: int,
                                   maximum_error_mm: float, read_phases_rad: tuple[float,...],
                                   planar_centre_mm: float) -> dict:
    """Actual stationary-root DESIGN; no UNION or old handover call.

    Whole phase cells pay material motion. The result may derive a required
    inspection envelope, but is never an installed/full-source certificate.
    """
    if phases<3:
        raise ValueError("engineering phase domain requires endpoints and interior")
    cam = configured_cam_exclusion(pair,radial_error_mm=0,profile_motion_mm=0)
    result = {"qualification":"nominal engineering only","production_qualified":False,
        "oblique_phase_bound_rad":None,"nominal_oblique_phase_bound_rad":None,
        "integral_cam_body_exclusion":cam,"smooth_3d_ff_screen":exact_smooth_ff_exclusion(pair),
        "signed_read_matrix":signed_read_matrix(pair,read_phases_rad,maximum_error_mm=maximum_error_mm),
        "scope":"actual immutable printed-profile case at held source nominal pose; no preset-zero engaged acceptance",
        "union_qualification":None,"handover_qualification":None,"phase_cell_envelopes":[]}
    from stock_form_mesh import supported_flank_coverage
    try:
        result["planar_ff_screen"] = asdict(supported_flank_coverage(
            pair.driver,pair.driven,planar_centre_mm,maximum_error_mm=maximum_error_mm))
    except (ValueError,RuntimeError) as error:
        result["planar_ff_screen"] = {"qualification":"unresolved","reason":str(error)}
    operating_radius = planar_centre_mm*pair.driven.teeth/(pair.driver.teeth+pair.driven.teeth)
    step = pair.driver.angular_pitch_rad/(phases-1)
    half = step/2
    phase_ball = 2*pair.driver.blank_radius_mm*math.sin(half/2)
    for centre in np.linspace(half,pair.driver.angular_pitch_rad-half,phases-1):
        cell = {"driver_interval_rad":[float(centre)-half,float(centre)+half],
                "phase_motion_ball_mm":phase_ball,"qualification":"unresolved"}
        try:
            window = ContactSearch(pair,float(centre)).window(maximum_error_mm,
                phase_half_width_rad=half)
            cell["actual_inverse_window"] = asdict(window)
            lower = loaded_phase_at(pair,float(centre),maximum_error_mm=maximum_error_mm,
                driver_sense=-1,radial_error_mm=phase_ball)
            upper = loaded_phase_at(pair,float(centre),maximum_error_mm=maximum_error_mm,
                driver_sense=1,radial_error_mm=phase_ball)
            llo,lhi = lower["driven_phase_interval_rad"]
            ulo,uhi = upper["driven_phase_interval_rad"]
            arc = ((ulo-lhi)*operating_radius,(uhi-llo)*operating_radius)
            air = loaded_root_air_bounds(pair,float(centre),(llo,lhi),
                driver_phase_half_width_rad=half,maximum_error_mm=maximum_error_mm)
            datum_motion = pair.driver.teeth/pair.driven.teeth*half
            te_lo,te_hi = lower["signed_running_te_interval_rad"]
            cell.update(lower_loaded=lower,upper_loaded=upper,root_air=air,
                actual_driven_lower_interval_rad=[llo,lhi],
                actual_driven_upper_interval_rad=[ulo,uhi],
                actual_driven_backlash_interval_mm=arc,
                actual_driven_pitch_arc_backlash_interval_mm=[
                    (ulo-lhi)*pair.driven.pitch_radius_mm,(uhi-llo)*pair.driven.pitch_radius_mm],
                signed_lower_te_interval_rad=[te_lo-datum_motion,te_hi+datum_motion],
                margins={"tight_backlash_mm":arc[0]-.06,"loose_backlash_mm":.41-arc[1],
                    "cone_root_air_mm":air["cone_root_air_lower_mm"]-.02 if air["qualified"] else None,
                    "drum_root_air_mm":air["drum_root_air_lower_mm"]-.10 if air["qualified"] else None},
                qualification="bounded" if window.no_overlap and air["qualified"] else "unresolved",
                reason=None if window.no_overlap and air["qualified"] else
                    "actual phase-cell window or required .02/.10 air unresolved")
        except (ValueError,RuntimeError) as error:
            cell["reason"] = str(error)
        result["phase_cell_envelopes"].append(cell)
    cells = result["phase_cell_envelopes"]
    bounded = all(cell["qualification"]=="bounded" for cell in cells)
    result["all_cells_bounded"] = bounded
    result["source_inspection_radius_mm"] = operating_radius
    result["physical_driven_pitch_radius_mm"] = pair.driven.pitch_radius_mm
    result["engineering_complete"] = bounded and cam["qualified"] and result["signed_read_matrix"]["all_reads_bounded"]
    capacity = maximum_certified_root_air_capacity(pair,cells,maximum_error_mm=maximum_error_mm)
    result["root_air_capacity"] = capacity
    reserve = capacity["certified_extra_air_lower_mm"]
    result["root_air_extra_reserve_mm"] = reserve
    result["installation_margin_available"] = reserve is not None and reserve>0
    if bounded:
        result["margins"] = {name:min(cell["margins"][name] for cell in cells)
                            for name in cells[0]["margins"]}
        if reserve is not None:
            result["margins"].update(cone_root_air_mm=reserve,drum_root_air_mm=reserve)
    return result


def printed_profile_cases(cone_corners: tuple, drum_corners: tuple):
    """The sixteen distinct OD/process pairs; no nominal-corner substitution."""
    for name,profiles in (("cone",cone_corners),("drum",drum_corners)):
        keys = {(profile.blank_radius_mm,profile.radial_translation_mm) for profile in profiles}
        if len(profiles)!=4 or len(keys)!=4:
            raise ValueError(f"{name} requires four distinct actual printed-profile corners")
    for (ci,cone),(di,drum) in itertools.product(enumerate(cone_corners),enumerate(drum_corners)):
        yield ci,di,cone,drum


def actual_candidate_settings(teeth: int, source: dict, inputs, *,
                              six_pitch_thickness_mm: float, allow_fresh_lattice: bool,
                              lattice_record: dict):
    """Try supplied settings, then the CURRENT real printed lattice if needed.

    The caller stops after an accepted actual matrix. Resuming this generator
    means the supplied settings failed; identical OD/thickness inputs are not
    queried again. Old-domain refusal flags never certify this current lattice.
    """
    seen = set()
    for setting in source.get("geometry_candidates",()):
        key = (setting["outside_dia_mm"],setting["pitch_thickness_mm"])
        if key not in seen:
            seen.add(key)
            yield setting
    if not allow_fresh_lattice:
        return
    from diagnostics.solve_stock_form_cones import solve_count
    fresh = solve_count(teeth,inputs,six_pitch_thickness_mm=six_pitch_thickness_mm,
                        analyse_mesh=False)
    lattice_record.update(
        current_dimensional_lattice=fresh,
        scope="fresh captured-source finite dimensional lattice only; no physical all-family contact refusal")
    for setting in fresh["geometry_candidates"]:
        key = (setting["outside_dia_mm"],setting["pitch_thickness_mm"])
        if key not in seen:
            seen.add(key)
            yield setting


def study_family(domain_report: dict, inputs, *, six_pitch_thickness_mm: float,
                 phases_rad: tuple[float,...] = tuple(-k*math.pi for k in range(21)),
                 maximum_error_mm: float = 0.0002, contact_phases: int = 129,
                 nominal_engineering_only: bool = False,
                 source_inputs_only: bool = False, installed=None) -> dict:
    """Every physical count, retaining finite-domain and numerical refusals.

    No finite bound is exported for a row whose manufactured domain or
    continuous-pose enclosure is not qualified. Pointwise measured TE is
    still retained as evidence, never consumed as a whole-period guarantee.
    """
    from diagnostics.solve_stock_form_cones import (
        BLANK_DIA_BAND,TOOTH_THICKNESS_BAND,
        cutter_for_count,geometry_margins,home_clocking_rad,oblique_section_geometry)
    from stock_form_cutter import translation_for_pitch_tooth_thickness
    required = tuple(range(6,121,6))
    if nominal_engineering_only and source_inputs_only:
        raise ValueError("nominal contact engineering and source-only export are distinct scopes")
    indexed = {row["teeth"]:row for row in domain_report["rows"]}
    if tuple(sorted(indexed)) != required or len(domain_report["rows"]) != len(required):
        raise ValueError("actual family report must contain exactly T006..T120 once each")
    if contact_phases < 3:
        raise ValueError("contact phase domain requires endpoints and interior")
    rows = []
    for teeth in required:
        source = indexed[teeth]
        geometry,home = oblique_section_geometry(teeth),home_clocking_rad(teeth)
        source_candidates = source.get("geometry_candidates",())
        current_lattice_loaded = False
        if not source_candidates and not source_inputs_only:
            from diagnostics.solve_stock_form_cones import solve_count
            source = solve_count(teeth,inputs,six_pitch_thickness_mm=six_pitch_thickness_mm,
                                 analyse_mesh=False)
            current_lattice_loaded = True
            source_candidates = source["geometry_candidates"]
        if not source_candidates:
            rows.append({"teeth":teeth,"qualification":"refused","oblique_phase_bound_rad":None,
                "actual3d_mesh_evaluated":False,"reason":"current finite dimensional lattice has no manufactured profile",
                "dimensional_lattice":source,"domain_refusal_certified":False})
            continue
        radius_upper = max(setting["outside_dia_mm"]+max(BLANK_DIA_BAND)
                           for setting in source_candidates)/2
        domain = configured_pose_domain(
            teeth,inputs,cone_radius_upper_mm=radius_upper,installed=installed) if source_inputs_only else None
        source_domain = None
        if not (nominal_engineering_only or source_inputs_only):
            from dt_cone_mesh_domain import continuous_source_domain, SourceDomainUnknown
            try:
                source_domain = continuous_source_domain(teeth,installed_axis_acceptance=installed)
            except SourceDomainUnknown as error:
                rows.append({"teeth":teeth,"qualification":"source domain unknown",
                    "oblique_phase_bound_rad":None,"actual3d_mesh_evaluated":False,
                    "reason":str(error),"domain_refusal_certified":False})
                continue
        row = {"teeth":teeth,"qualification":"refused", "oblique_phase_bound_rad":None,
            "nominal_oblique_phase_bound_rad":None,"actual3d_mesh_evaluated":False,
            "geometry":geometry,"pose_domain":asdict(domain) if domain is not None else source_domain,
            "pose_corners":pose_corner_records(geometry,domain) if domain is not None else [],
            "continuous_source_domain":source_domain,
            "pose_corner_scope":"whole source coordinates; Cartesian OUTERs are not independent engaged corners" if source_domain is not None else
                ("source-only OUTER witnesses" if domain is not None else "held operating nominal engineering; no installed acceptance supplied"),
            "read_phases_rad":phases_rad,
            "coverage_required":1.1,
            "coverage_definition":"Main-final actual 3D union of supported flank/tip/axial-edge branches; smooth FF is screen only",
            "dimensional_certificate":{name:source.get(name) for name in (
                "translation_domain_mm","pitch_thickness_domain_mm","available_thickness_span_mm",
                "required_thickness_span_mm","thickness_domain_deficit_mm","root_min_required_mm",
                "finite_lattice_exhausted","no_solution_certificate","lattice_points")}}
        cutter = cutter_for_count(teeth,inputs,six_pitch_thickness_mm=six_pitch_thickness_mm)
        cone_q = cutter_q_domain(cutter,tuple(source["translation_domain_mm"]))
        drum_q = [
            cutter_q_domain(profile.template,(profile.radial_translation_mm,profile.radial_translation_mm))
            for profile in inputs.drum_corners
        ]
        minimum_drum_q = min(values[0] for values in drum_q)
        residual = None if cone_q is None else cone_q[0]+minimum_drum_q
        row["smooth_3d_ff_domain_screen"] = {
            "cone_Q_enclosure_mm":cone_q,"drum_Q_min_mm":minimum_drum_q,
            "nominal_XZ_pose_Q_sum_lower_mm":residual,
            "smooth_ff_coverage_upper":0.0 if residual is not None and residual>0 else None,
            "scope":"nominal XZ axes and full finite cutter/translation domain; screen only, never an edge-union refusal"}
        lattice_record = {}
        if current_lattice_loaded:
            lattice_record.update(current_dimensional_lattice=source,
                scope="fresh captured-source finite dimensional lattice only; no physical all-family contact refusal")
        row["actual_lattice_search"] = lattice_record
        candidate_reports = []
        for setting in actual_candidate_settings(teeth,source,inputs,
                six_pitch_thickness_mm=six_pitch_thickness_mm,
                allow_fresh_lattice=not source_inputs_only and not current_lattice_loaded,lattice_record=lattice_record):
            nominal_translation = translation_for_pitch_tooth_thickness(teeth,cutter,setting["pitch_thickness_mm"])
            actual_translations = tuple(translation_for_pitch_tooth_thickness(
                teeth,cutter,setting["pitch_thickness_mm"]+deviation)
                for deviation in (TOOTH_THICKNESS_BAND[1],TOOTH_THICKNESS_BAND[0]))
            fresh_margins = geometry_margins(teeth,setting["outside_dia_mm"],actual_translations,cutter,inputs)
            fresh_setting = {**setting,"tool_translation_mm":nominal_translation,
                             "translation_limits_mm":actual_translations,
                             "geometry_margins":fresh_margins}
            if any(not math.isfinite(value) or value < 0 for value in fresh_margins.values()):
                candidate_reports.append({"setting":fresh_setting,"qualification":"refused",
                    "reason":"actual final-core manufactured dimensional gates refused",
                    "binding_constraints":[name for name,value in fresh_margins.items() if not math.isfinite(value) or value<0],
                    "oblique_phase_bound_rad":None,"nominal_oblique_phase_bound_rad":None,
                    "actual3d_mesh_evaluated":False,"dimensional_no_solution_certificate":False})
                continue
            setting = fresh_setting
            profile = StockFormProfile(teeth,cutter,setting["outside_dia_mm"]/2,nominal_translation)
            setting.update(nominal_plunge_mm=profile.plunge_mm,
                           root_envelope_mm=(profile.root_radius_min_mm,profile.root_radius_max_mm),
                           actual_pitch_tooth_thickness_mm=profile.pitch_tooth_thickness_mm,
                           reconstructed_from_actual_loaded_core=True)
            pair = ContactPair(f"cone T{teeth:03d} nominal",profile,inputs.drum_nominal,
                               placement_from_geometry(geometry))
            cone_corners = tuple(StockFormProfile(teeth,cutter,
                (setting["outside_dia_mm"]+od)/2,translation)
                for od,translation in itertools.product(BLANK_DIA_BAND,actual_translations))
            ball = radial = axial = cam = None
            if domain is not None:
                ball = (profile_motion_ball(profile,cone_corners)
                        +profile_motion_ball(inputs.drum_nominal,inputs.drum_corners))
                radial,axial = complete_pose_errors(pair,domain,profile_motion_mm=ball)
                cam = configured_cam_exclusion(pair,radial_error_mm=radial,profile_motion_mm=ball)
            if source_inputs_only:
                calculation = {"qualification":"source inputs prepared",
                    "oblique_phase_bound_rad":None,"nominal_oblique_phase_bound_rad":None,
                    "position_ball_mm":ball,"radial_pose_error_mm":radial,"axial_pose_error_mm":axial,
                    "reason":"explicit source-only dimensional/pose design export; no contact qualification executed"}
            elif nominal_engineering_only:
                calculation = {"qualification":"nominal engineering only","oblique_phase_bound_rad":None,
                    "nominal_oblique_phase_bound_rad":None,"position_ball_mm":ball,
                    "radial_pose_error_mm":radial,"axial_pose_error_mm":axial,
                    "reason":"actual source nominal and printed-profile corners measured for inspection design; complete engaged-pose qualification not asserted",
                    "nominal_engineering":measure_nominal_for_inspection(pair,
                        phases=contact_phases,maximum_error_mm=maximum_error_mm,
                        read_phases_rad=phases_rad,planar_centre_mm=inputs.centre_mm(teeth)),
                    "manufactured_corner_engineering":[]}
                for ci,di,cone_corner,drum_corner in printed_profile_cases(cone_corners,inputs.drum_corners):
                    corner_pair = ContactPair(f"{pair.name} manufactured C{ci:02d}-D{di:02d}",
                        cone_corner,drum_corner,pair.placement)
                    calculation["manufactured_corner_engineering"].append({
                        "case_id":f"C{ci:02d}-D{di:02d}",
                        "cone_corner_index":ci,
                        "drum_corner_index":di,
                        "cone":profile_record(cone_corner),"drum":profile_record(drum_corner),
                        "actual_source_nominal_pose":True,
                        "calculation":measure_nominal_for_inspection(corner_pair,
                            phases=contact_phases,maximum_error_mm=maximum_error_mm,
                            read_phases_rad=phases_rad,planar_centre_mm=inputs.centre_mm(teeth))})
                matrix = [calculation["nominal_engineering"],*(
                    record["calculation"] for record in calculation["manufactured_corner_engineering"])]
                calculation["inspection_design_matrix"] = {
                    "expected_cases":17,"actual_cases":len(matrix),
                    "all_profile_cases_bounded":len(matrix)==17 and all(
                        case["engineering_complete"] for case in matrix),
                    "margin_lower":{name:min(case["margins"][name] for case in matrix)
                        for name in set.intersection(*(set(case.get("margins",{})) for case in matrix))},
                    "all_cases_have_positive_certified_extra_air":all(
                        case["installation_margin_available"] for case in matrix),
                    "certified_uniform_extra_air_lower_mm":min(
                        case["root_air_extra_reserve_mm"] for case in matrix) if all(
                            case["root_air_extra_reserve_mm"] is not None for case in matrix) else None,
                    "installation_limits_derived":False,
                    "scope":"one actual nominal and sixteen distinct printed-profile corners; no installed-pose certificate or numerical zero preset"}
            else:
                actual_cases = []
                nominal_comparison = None
                calculation = {"qualification":"refused","oblique_phase_bound_rad":None,
                    "nominal_oblique_phase_bound_rad":None}
                try:
                    nominal_comparison = _continuous_analysis(pair,nominal_source_subdomain(pair.placement.record(),source_domain),
                        phases=contact_phases,maximum_error_mm=maximum_error_mm,read_phases_rad=phases_rad)
                    reference_te = actual3d_nominal_te_enclosure(nominal_comparison)
                    calculation = qualify_actual_pair(pair,continuous_source_domain=source_domain,
                        phases=contact_phases,maximum_error_mm=maximum_error_mm,read_phases_rad=phases_rad,
                        planar_centre_mm=inputs.centre_mm(teeth),selected_nominal_te_rad=reference_te,
                        nominal_pose_report=nominal_comparison)
                    actual_cases = [{"case_id":"nominal","cone_corner_index":None,"drum_corner_index":None,
                        "cone":profile_record(profile),"drum":profile_record(inputs.drum_nominal),
                        "calculation":calculation}]
                    for ci,di,cone_corner,drum_corner in printed_profile_cases(cone_corners,inputs.drum_corners):
                        corner_pair = ContactPair(f"{pair.name} C{ci:02d}-D{di:02d}",
                            cone_corner,drum_corner,pair.placement)
                        corner_nominal = _continuous_analysis(corner_pair,
                            nominal_source_subdomain(corner_pair.placement.record(),source_domain),phases=contact_phases,
                            maximum_error_mm=maximum_error_mm,read_phases_rad=phases_rad)
                        actual_cases.append({"case_id":f"C{ci:02d}-D{di:02d}",
                            "cone_corner_index":ci,"drum_corner_index":di,
                            "cone":profile_record(cone_corner),"drum":profile_record(drum_corner),
                            "calculation":qualify_actual_pair(corner_pair,continuous_source_domain=source_domain,
                                phases=contact_phases,maximum_error_mm=maximum_error_mm,read_phases_rad=phases_rad,
                                planar_centre_mm=inputs.centre_mm(teeth),selected_nominal_te_rad=reference_te,
                                nominal_pose_report=corner_nominal)})
                    calculation = dict(calculation)
                    calculation["actual_profile_cases"] = actual_cases
                    if all(case["calculation"]["qualification"]=="qualified" for case in actual_cases):
                        full_profile_case_records(actual_cases[0],actual_cases[1:])
                        calculation["oblique_phase_bound_rad"] = max(
                            case["calculation"]["oblique_phase_bound_rad"] for case in actual_cases)
                        calculation["stock_phase_3d"] = stock_phase_3d_packet(actual_cases,nominal_comparison,
                            driver_read_phases_rad=phases_rad,ratio=teeth/inputs.drum_teeth,
                            datum=source_domain["manufactured_datum_mapping"])
                    else:
                        calculation.update(qualification="refused",oblique_phase_bound_rad=None,
                            reason="one or more actual nominal/all16 full-source printed-profile certificates unresolved")
                    cam = calculation.get("integral_cam_body_exclusion")
                except (KeyError,TypeError,ValueError,RuntimeError) as error:
                    calculation = dict(calculation)
                    calculation.update(qualification="refused",oblique_phase_bound_rad=None,
                        nominal_oblique_phase_bound_rad=None,reason=str(error),
                        actual_profile_cases=actual_cases,
                        actual_profile_case_count=len(actual_cases),
                        profile_matrix_complete=len(actual_cases)==17)
                    if nominal_comparison is not None:
                        calculation.setdefault("nominal_actual3d",nominal_comparison)
            if source_inputs_only and not cam["qualified"]:
                calculation.update(qualification="refused",oblique_phase_bound_rad=None,
                    reason="integral cam-body source OUTER exclusion unresolved; no physical no-solution inference")
            candidate_reports.append({"setting":setting,"actual_pose":pose_record(pair,geometry,home),
                "actual3d_mesh_evaluated":not source_inputs_only,
                "driver_profile":profile_record(profile),"driven_profile":profile_record(inputs.drum_nominal),
                "manufactured_cone_corners":[profile_record(p) for p in cone_corners],
                "manufactured_drum_corners":[profile_record(p) for p in inputs.drum_corners],
                "integral_cam_body_exclusion":cam,
                **calculation})
            if not (nominal_engineering_only or source_inputs_only):
                candidate_reports[-1].update(
                    cutter=actual_cutter_record(cutter),
                    printed_profile_root_envelope_mm=printed_root_radius_envelope(cone_corners),
                )
            if not source_inputs_only:
                engineering = calculation.get("inspection_design_matrix",{})
                if calculation["qualification"]=="qualified" or (
                        nominal_engineering_only and engineering.get("all_profile_cases_bounded") is True
                        and engineering.get("all_cases_have_positive_certified_extra_air") is True
                        and all(value>=0 for value in engineering.get("margin_lower",{}).values())):
                    break
        qualified = [report for report in candidate_reports if report["qualification"] == "qualified"]
        selected = min(qualified,key=lambda report:report["oblique_phase_bound_rad"]) if qualified else None
        row.update(actual3d_mesh_evaluated=any(report.get("actual3d_mesh_evaluated",False) for report in candidate_reports),
                   candidates=candidate_reports,selected=selected["setting"] if selected else None,
                   qualification="qualified" if selected else "refused",
                   reason=None if selected else "actual supplied/current-lattice studies unresolved or refused; no physical all-family no-solution inferred",
                   domain_refusal_certified=False,
                   binding_constraints=[] if selected else ["actual_3d_contact"],
                   oblique_phase_bound_rad=selected["oblique_phase_bound_rad"] if selected else None,
                   nominal_oblique_phase_bound_rad=selected["nominal_oblique_phase_bound_rad"] if selected else None,
                   signed_read_matrix=(selected or candidate_reports[0]).get("signed_read_matrix"))
        if not (nominal_engineering_only or source_inputs_only):
            row["cutter"] = actual_cutter_record(cutter)
            if selected is not None:
                row["printed_profile_root_envelope_mm"] = selected["printed_profile_root_envelope_mm"]
                row["oblique_phase_bound_excluded_terms"] = selected.get(
                    "oblique_phase_bound_excluded_terms")
                row["stock_phase_3d"] = selected["stock_phase_3d"]
        if source_inputs_only:
            row.update(qualification="source inputs prepared",reason="no contact calculation requested",
                       selected=None,binding_constraints=[],domain_refusal_certified=False)
        if nominal_engineering_only:
            row.update(qualification="nominal engineering only",reason="source engaged-pose inspection remains to be derived from actual margins",
                       selected=None,binding_constraints=["engaged_pose_inspection"],domain_refusal_certified=False)
        rows.append(row)
    return {"qualified":all(row["qualification"] == "qualified" for row in rows),"native_certificate":False,"rows":rows,
        "source_inputs_only":source_inputs_only,
        "nominal_engineering_only":nominal_engineering_only,
        "installed_axis_acceptance":asdict(installed) if installed is not None else None,
        "centre_stack_source_mm":{"closing_runout":inputs.runout_mm,
            "opening_total":inputs.opening_mm,
            "opening_components":dict(inputs.opening_components_mm),
            "opening_rule":"max(booked total, derived runout+bearing total); opening not added twice",
            "measured_in_this_scope":not nominal_engineering_only and not source_inputs_only},
        "scope":"actual finite 3D surfaces and source corner domains; explicit refusals, no planar/profile fallback",
        "read_phase_source":"explicit actual cone phases supplied by caller; default operating stalls -k*pi, k=0..20",
        "runout_enclosure":"actual body-fixed full eccentricity disks are bounded by named source coordinates; cardinal samples alone never qualify them",
        "numerical_error_policy":"actual continuous source/cell certificates bind whole-period endpoint/root/material proofs; true q0 point-reference bounds are separate and paid once"}


def actual_cutter_record(cutter) -> dict:
    """Actual captured tool, including a non-default caller-supplied N6 thickness."""
    return {
        "reference_teeth":cutter.reference_teeth,
        "cutter_number":cutter.cutter_number,
        "teeth_range":list(cutter.teeth_range),
        "diametral_pitch":cutter.diametral_pitch,
        "pressure_angle_deg":cutter.pressure_angle_deg,
        "root_radius_mm":cutter.root_radius_mm,
        "base_radius_mm":cutter.base_radius_mm,
        "tip_radius_mm":cutter.tip_radius_mm,
        "pitch_tooth_thickness_mm":cutter.pitch_tooth_thickness_mm,
        "name":cutter.name,
        "source":cutter.source,
    }


def printed_root_radius_envelope(profiles) -> list[float]:
    """Manufactured RootArc extrema in RADIUS mm, never a fictitious MAX floor."""
    profiles = tuple(profiles)
    if (len(profiles)!=4 or len({
            (profile.blank_radius_mm,profile.radial_translation_mm)
            for profile in profiles})!=4):
        raise ValueError("root envelope needs four distinct actual printed profiles")
    low = min(profile.root_radius_min_mm for profile in profiles)
    high = max(profile.root_radius_max_mm for profile in profiles)
    if not (math.isfinite(low) and math.isfinite(high) and 0<low<=high):
        raise ValueError("actual printed RootArc radius envelope is invalid")
    return [low,high]


def _canonical_sha256(record) -> str:
    return hashlib.sha256(json.dumps(
        record,sort_keys=True,separators=(",",":"),allow_nan=False,
    ).encode("utf-8")).hexdigest().upper()


def _manifest_value(manifest: dict[str,str], relative_path: str) -> str:
    """Match one authentic path without reading or rebinding live source."""
    if (not isinstance(manifest,dict)
            or any(not isinstance(path,str) for path in manifest)):
        raise ValueError("actual source manifest needs named file paths")
    matches = [
        value for path,value in manifest.items()
        if path.replace("\\","/")==relative_path
        or path.replace("\\","/").endswith("/"+relative_path)
    ]
    if len(matches)!=1:
        raise ValueError(f"actual source receipt needs exactly one {relative_path}")
    value = matches[0]
    if (not isinstance(value,str) or len(value)!=64
            or any(character not in "0123456789ABCDEF" for character in value)):
        raise ValueError(f"actual source receipt has invalid SHA256 for {relative_path}")
    return value


def compiled_measurement_identity(source: dict) -> dict:
    """The genuine SIX measured files, never a current-file hash substitution."""
    manifests = [
        source[name] for name in (
            "before_design_sha256","actual_preimport_project_sha256",
            "after_design_sha256","loaded_algorithm_sha256",
        )
    ]
    if source.get("source_bytes_stable") is not True:
        raise ValueError("changed live source cannot release a measurement identity")
    measured = {}
    for path in _MEASUREMENT_ENGINE_PATHS:
        values = [_manifest_value(manifest,path) for manifest in manifests]
        if len(set(values))!=1:
            raise ValueError(f"compiled/before/after/loaded source differs for {path}")
        measured[path.rsplit("/",1)[1]] = values[0]
    return {
        "measurement_engine_sources_sha256":measured,
        "measurement_engine_sha256":_canonical_sha256(measured),
    }


def full_profile_case_records(nominal: dict, manufactured: list[dict]) -> list[dict]:
    """Preserve seventeen real full reports; an engineering summary is not one."""
    expected = {(ci,di) for ci in range(4) for di in range(4)}
    indices = [(case["cone_corner_index"],case["drum_corner_index"]) for case in manufactured]
    if len(indices)!=16 or set(indices)!=expected:
        raise ValueError("full factory evidence needs each distinct C00-D00..C03-D03 once")
    if (nominal.get("case_id")!="nominal"
            or nominal.get("cone_corner_index") is not None
            or nominal.get("drum_corner_index") is not None):
        raise ValueError("nominal profile report has the wrong physical case label")
    cases = [nominal,*sorted(manufactured,key=lambda case:(
        case["cone_corner_index"],case["drum_corner_index"]))]
    for case in cases:
        ci,di = case["cone_corner_index"],case["drum_corner_index"]
        if ci is not None and case["case_id"]!=f"C{ci:02d}-D{di:02d}":
            raise ValueError("full factory profile labels differ from their actual corner indices")
        if (case.get("actual_source_nominal_pose") is True
                or not {"cone","drum","calculation"} <= case.keys()):
            raise ValueError("held-nominal engineering evidence is not full source qualification")
        calculation = case["calculation"]
        if (calculation.get("production_qualified") is False
                or calculation.get("qualification")!="qualified"):
            raise ValueError(f"{case['case_id']}: actual full-profile calculation is not qualified")
        robust = calculation.get("all_corner_actual3d",{})
        certificate = robust.get("continuous_contact_certificate",{})
        if (certificate.get("proof_schema")!="finite-stock-continuous-envelope/1"
                or certificate.get("status")!="PROVED"
                or certificate.get("native_certificate") is not False
                or set(certificate.get("sides",{}))!={"lower","upper"}):
            raise ValueError(f"{case['case_id']}: full directional continuous-contact proof is absent")
        if (robust.get("production_source_qualified") is not True
                or robust.get("source_domain_proved") is not True):
            raise ValueError(f"{case['case_id']}: actual full physical source admission is absent")
        for side in certificate["sides"].values():
            required = {
                "same_source_pose","phase_domain_rad","phase_cells",
                "row_branch_spans","handovers","periodic_seam",
            }
            if (not isinstance(side,dict) or not required<=side.keys()
                    or not side["same_source_pose"] or not side["phase_cells"]
                    or not isinstance(side["row_branch_spans"],(list,tuple))):
                raise ValueError(f"{case['case_id']}: continuous proof omits its actual source/cell evidence")
            domain = side["phase_domain_rad"]
            if (len(domain)!=2 or not all(math.isfinite(value) for value in domain)
                    or domain[0]!=0.0 or domain[1]<=0.0):
                raise ValueError(f"{case['case_id']}: continuous proof has no closed whole-phase domain")
            seam = side["periodic_seam"]
            if seam.get("status")!="PROVED" or seam.get("continuous") is not True:
                raise ValueError(f"{case['case_id']}: actual periodic seam remains unproved")
        lower,upper = (certificate["sides"][name] for name in ("lower","upper"))
        if (lower["same_source_pose"]!=upper["same_source_pose"]
                or lower["phase_domain_rad"]!=upper["phase_domain_rad"]):
            raise ValueError(f"{case['case_id']}: directional proofs do not retain the same source/phase domain")
    return cases


def attach_factory_transport(report: dict, geometry_inputs: dict) -> None:
    """Add input/output identities only to genuine full-production transport.

    The output JSON is not a geometry input. This serializer never solves a
    mesh, manufactures a missing proof, changes a signed datum or sets a
    refused numerical report green.
    """
    import dt_cone_gear_spec as spec
    if report.get("source_inputs_only") or report.get("nominal_engineering_only"):
        raise ValueError("engineering/source-prep output is not a native factory packet")
    report.update(
        family="dt_cone_stock_form",schema_version=1,
        geometry_inputs=geometry_inputs,
        geometry_inputs_sha256=spec.geometry_sha256(geometry_inputs),
    )
    rows = report["rows"]
    required = tuple(range(6,121,6))
    try:
        if (len(rows)!=20 or tuple(sorted(row["teeth"] for row in rows))!=required
                or report.get("qualified") is not True):
            raise ValueError("factory family lacks twenty fully qualified actual rows")
        for row in rows:
            if (row.get("qualification")!="qualified" or not row.get("selected")
                    or row.get("oblique_phase_bound_excluded_terms")!=list(_BUDGET_EXCLUDED_TERMS)):
                raise ValueError("selected factory row or budget geometric scope is incomplete")
            chosen = [candidate for candidate in row["candidates"]
                      if candidate["setting"]==row["selected"]]
            if len(chosen)!=1:
                raise ValueError("selected factory setting does not identify one actual report")
            cases = chosen[0]["actual_profile_cases"]
            full_profile_case_records(cases[0],cases[1:])
        report.update(compiled_measurement_identity(report["source_identity"]))
        report["selected_geometry_sha256"] = spec.geometry_sha256(
            spec.selected_geometry_record(rows))
    except (KeyError,ValueError,TypeError) as error:
        report["qualified"] = False
        report["selected_geometry_sha256"] = None
        report["factory_transport_refusal"] = str(error)


def json_safe(value):
    if isinstance(value,np.generic):
        return json_safe(value.item())
    if isinstance(value,dict):
        return {key:json_safe(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)):
        return [json_safe(item) for item in value]
    if isinstance(value,float) and not math.isfinite(value):
        return str(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain-report",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--six-pitch-thickness-mm",type=float,required=True)
    parser.add_argument("--maximum-error-mm",type=float,default=0.0002)
    parser.add_argument("--source-inputs-only",action="store_true",
                        help="Export actual twenty-row dimensional/pose engineering inputs and byte scope; never a mesh certificate")
    parser.add_argument("--nominal-engineering-only",action="store_true",
                        help="Calculate actual nominal and every printed-profile corner for deriving engaged inspection; not production qualification")
    parser.add_argument("--contact-phases",type=int,default=129)
    args = parser.parse_args()
    output = args.out.resolve()
    if output.is_relative_to(SCRIPTS.parents[1]):
        parser.error("engineering evidence must be outside the repository")
    with InputReadIdentity() as reads:
        from diagnostics.solve_stock_form_cones import (
            BLANK_DIA_BAND,configured_inputs,home_clocking_rad,oblique_section_geometry)
        inputs = configured_inputs(maximum_error_mm=args.maximum_error_mm)
        domain_bytes = args.domain_report.read_bytes()
        domain_sha = hashlib.sha256(domain_bytes).hexdigest().upper()
        domain_report = json.loads(domain_bytes)
        source_rows = {row["teeth"]:row for row in domain_report["rows"]}
        if tuple(sorted(source_rows))!=tuple(range(6,121,6)) or len(domain_report["rows"])!=20:
            raise ValueError("exactly twenty unique actual cone rows required")
        pose_identity = {}
        factory_inputs = None
        stationary_runout_authority = None
        if args.nominal_engineering_only:
            from dt_cone_mesh_domain import SourceDomainUnknown,tooth_cutting_runout_tir_mm
            stationary_runout_authority = {
                "scope":"mathematical held q0 for margin selection only; no manufacturing TIR band is assumed or qualified",
                "assumed_tir_band_mm":None,
                "conditional_manufacturing_acceptance":False,
                "source_requirements":{}}
            for body in ("cone","drum"):
                try:
                    value = tooth_cutting_runout_tir_mm(body)
                    state = {"state":"source requirement","tir_mm":value,
                        "applied_to_this_held_q0_design":False}
                except SourceDomainUnknown as error:
                    state = {"state":"UNKNOWN","reason":str(error)}
                stationary_runout_authority["source_requirements"][body] = state
        if not args.source_inputs_only:
            import stock_form_mesh
            import diagnostics.stock_form_root_sweep
        if not (args.nominal_engineering_only or args.source_inputs_only):
            import diagnostics.stock_form_contact_continuation
            import stock_form_contact_certificate
            import dt_cone_gear_spec as spec
            factory_inputs = spec.geometry_inputs()
        for teeth in range(6,121,6):
            if args.source_inputs_only and not source_rows[teeth].get("geometry_candidates"):
                pose_identity[teeth] = {"domain":None,"refusal":"source-only supplied lattice has no finite manufactured profile",
                    "geometry":oblique_section_geometry(teeth),
                    "saved_planar_gap_clocking_rad":home_clocking_rad(teeth)}
                continue
            if args.nominal_engineering_only:
                pose_identity[teeth] = {"domain":None,
                    "scope":"held source nominal engineering; no installed acceptance supplied",
                    "geometry":oblique_section_geometry(teeth),
                    "saved_planar_gap_clocking_rad":home_clocking_rad(teeth)}
                continue
            if args.source_inputs_only:
                domain = asdict(configured_pose_domain(teeth,inputs,cone_radius_upper_mm=max(
                    setting["outside_dia_mm"]+max(BLANK_DIA_BAND)
                    for setting in source_rows[teeth]["geometry_candidates"])/2))
            else:
                from dt_cone_mesh_domain import continuous_source_domain
                domain = continuous_source_domain(teeth)
            pose_identity[teeth] = {
                "domain":domain,
                "geometry":oblique_section_geometry(teeth),
                "saved_planar_gap_clocking_rad":home_clocking_rad(teeth)}
        before_payloads = {}
        before = source_identity(reads.before,captured_payloads=before_payloads)
        active_algorithms = {path:sha for path,sha in _LOADED_ALGORITHM_SHA.items() if path in before}
        loaded_algorithm_consistent = all(before[path]==sha for path,sha in active_algorithms.items())
        if not loaded_algorithm_consistent or not all(
                before.get(path)==sha for path,sha in _LOADED_PROJECT_SHA.items()):
            raise RuntimeError("source bytes changed before DESIGN; no calculation launched")
        basis_path = output.with_suffix(output.suffix+".basis.json")
        basis_path.parent.mkdir(parents=True,exist_ok=True)
        raw_root = output.with_suffix(output.suffix+".capture")
        raw_snapshots = {
            "before":retain_raw_source_snapshot(raw_root,"before",before_payloads),
            "compiled":retain_raw_source_snapshot(raw_root,"compiled",_LOADED_PROJECT_PAYLOADS),
            "parsed":retain_raw_source_snapshot(raw_root,"parsed",reads.consumed_config_payloads()),
            "domain_pack":str(raw_root/"domain-input.json")}
        (raw_root/"domain-input.json").write_bytes(domain_bytes)
        basis = {"state":"before DESIGN only; after-design stability not yet observed",
            "actual_compiled_project_sha256":dict(_LOADED_PROJECT_SHA),
            "before_design_sha256":before,"loaded_algorithm_sha256":active_algorithms,
            "actual_parsed_config_sha256":{path:reads.loaded_config_sha[path]
                for path in reads.consumed_config_payloads()},
            "raw_source_snapshots":raw_snapshots,
            "actual_geometric_config_reads":dict(reads.values),
            "non_geometric_metadata_reads":dict(reads.non_geometry_values),
            "source_pose_inputs":pose_identity,"domain_pack_sha256":domain_sha,
            "stationary_tooth_runout_authority":stationary_runout_authority,
            "centre_stack_source_mm":{"closing_runout":inputs.runout_mm,
                "opening_total":inputs.opening_mm,
                "opening_components":dict(inputs.opening_components_mm)},
            "calculation_arguments":{"six_pitch_thickness_mm":args.six_pitch_thickness_mm,
                "maximum_error_mm":args.maximum_error_mm,"contact_phases":args.contact_phases,
                "nominal_engineering_only":args.nominal_engineering_only,
                "source_inputs_only":args.source_inputs_only},
            "production_qualified":False}
        if factory_inputs is not None:
            basis["geometry_inputs"] = factory_inputs
            basis["geometry_inputs_sha256"] = spec.geometry_sha256(factory_inputs)
        basis_path.write_text(json.dumps(json_safe(basis),indent=2,allow_nan=False)+"\n",encoding="utf-8")
        print(json.dumps({"before_design_basis":str(basis_path),
                          "frozen_project_paths":len(_LOADED_PROJECT_SHA),
                          "scope":"source captured before actual DESIGN; no result claimed"}),flush=True)
        calculation_failure = None
        try:
            report = study_family(domain_report,inputs,
                six_pitch_thickness_mm=args.six_pitch_thickness_mm,maximum_error_mm=args.maximum_error_mm,
                contact_phases=args.contact_phases,
                source_inputs_only=args.source_inputs_only,nominal_engineering_only=args.nominal_engineering_only)
        except Exception as error:
            calculation_failure = error
            report = {"qualified":False,"native_certificate":False,"rows":[],
                "calculation_status":"failed before a family result was returned",
                "calculation_exception":{"type":type(error).__name__,"message":str(error)},
                "unreturned_numeric_rows":"absent from this receipt; no completed-count or partial-row claim",
                "source_inputs_only":args.source_inputs_only,
                "nominal_engineering_only":args.nominal_engineering_only}
    after_payloads = {}
    after = source_identity(reads.before,captured_payloads=after_payloads)
    raw_snapshots.update(
        after=retain_raw_source_snapshot(raw_root,"after",after_payloads),
        compiled=retain_raw_source_snapshot(raw_root,"compiled",_LOADED_PROJECT_PAYLOADS),
        parsed=retain_raw_source_snapshot(raw_root,"parsed",reads.consumed_config_payloads()))
    domain_after_sha = _byte_sha(args.domain_report)
    config_consistent = all(after.get(path)==sha for path,sha in reads.before.items())
    loaded_project_consistent = all(before.get(path)==after.get(path)==sha
                                   for path,sha in _LOADED_PROJECT_SHA.items())
    stable = (before==after and loaded_algorithm_consistent and loaded_project_consistent
              and config_consistent and domain_sha==domain_after_sha)
    report["source_identity"] = {
        "loaded_algorithm_sha256":active_algorithms,
        "entry_source_capture":"CLI recompiles its exact captured entry bytes before project imports",
        "before_design_basis_path":str(basis_path),
        "raw_source_snapshots":raw_snapshots,
        "actual_preimport_project_sha256":_LOADED_PROJECT_SHA,
        "project_code_capture":"CLI compiles the exact preimport bytes, bypassing timestamp-only bytecode caches",
        "actual_parsed_config_sha256":{path:reads.loaded_config_sha[path] for path in reads.before
                                     if path in reads.loaded_config_sha},
        "before_design_sha256":before,"after_design_sha256":after,
        "source_bytes_stable":stable,"all_source_pose_inputs":pose_identity,
        "stationary_tooth_runout_authority":stationary_runout_authority,
        "non_geometric_metadata_reads":reads.non_geometry_values,
        "non_geometric_metadata_before_sha256":reads.non_geometry_before,
        "metadata_exclusion_scope":"known registry title/stock/process/installation/material wording and provenance only; unknown fields and fit/tolerance classes stay geometric",
        "actual_config_value_reads":reads.values,"actual_config_before_sha256":reads.before,
        "actual_config_read_sites":{key:sorted(sites) for key,sites in reads.call_sites.items()},
        "geometric_config_value_sha256":hashlib.sha256(json.dumps(
            json_safe(reads.values),sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest().upper(),
        "configuration_byte_scope":"authentic raw provenance; metadata fields are not part of the geometric value identity",
        "calculation_arguments":{"six_pitch_thickness_mm":args.six_pitch_thickness_mm,
            "maximum_error_mm":args.maximum_error_mm,"contact_phases":args.contact_phases,
            "source_inputs_only":args.source_inputs_only,
            "nominal_engineering_only":args.nominal_engineering_only},
        "domain_pack_sha256":domain_sha,"domain_pack_after_sha256":domain_after_sha,
        "source_input_factory":"diagnostics.solve_stock_form_cones.configured_inputs",
        "core_loaded_sha256":_LOADED_ALGORITHM_SHA[str(SCRIPTS/"stock_form_cutter.py")],
        "units":"actual loaded file bytes, uppercase SHA256; unknown historical baseline is not rebound"}
    if not stable:
        report["qualified"] = False
        for row in report["rows"]:
            row["qualification"] = "refused"
            row["oblique_phase_bound_rad"] = None
            row["reason"] = "source bytes changed during actual design calculation; no qualification rebind"
    if factory_inputs is not None and calculation_failure is None:
        attach_factory_transport(report,factory_inputs)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(json_safe(report),indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"qualified":report["qualified"],"rows":len(report["rows"]),
                      "actual3d_mesh_rows":sum(row["actual3d_mesh_evaluated"] for row in report["rows"]),
                      "output":str(output)}),flush=True)
    if calculation_failure is not None:
        raise calculation_failure
    return 0 if report["qualified"] or ((args.source_inputs_only or args.nominal_engineering_only) and stable) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        SourceFileLoader.get_code = _ORIGINAL_GET_CODE
