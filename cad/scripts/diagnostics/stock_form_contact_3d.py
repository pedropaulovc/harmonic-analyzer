"""Pure bounded contact of finite stock-form solids on explicit 3D axes.

This is a design calculation, not a native CAD certificate. No machine
configuration, part specification, assembly, COM or CadQuery is imported.
A straight driver is required by the angular-gap interval method. The
complete driven transverse perimeter is screw swept about its own axis.
Unsupported root-lobe contact is refused rather than idealised.
"""
from __future__ import annotations

from copy import copy
from dataclasses import asdict, dataclass, replace
import heapq
import itertools
import math

import numpy as np
from scipy.optimize import brentq, linprog, minimize, root

from stock_form_cutter import StockFormProfile
from diagnostics.stock_form_root_angles import intersect_intervals
from diagnostics.stock_form_root_sweep import root_free_intervals


@dataclass(frozen=True)
class Placement:
    """Explicit local-to-world frames (columns X,Y,axis), centres and faces.

    Origins locate local axial station zero; face tuples are actual minimum
    and maximum local Z. Clocks rotate material-tooth-zero about each axis.
    Driver phase is positive about its declared axis, and the driven nominal
    phase is minus the physical tooth ratio times driver phase.
    """

    driver_origin_mm: tuple[float,float,float]
    driven_origin_mm: tuple[float,float,float]
    driver_frame: np.ndarray
    driven_frame: np.ndarray
    driver_face_mm: tuple[float,float]
    driven_face_mm: tuple[float,float]
    driver_clocking_rad: float = 0.0
    driven_clocking_rad: float = 0.0
    driver_shoulder_z_mm: float = math.inf
    driver_turned_radius_mm: float = math.inf

    def __post_init__(self):
        for name in ("driver_frame","driven_frame"):
            frame = np.asarray(getattr(self,name),dtype=float)
            if frame.shape != (3,3) or not np.allclose(frame.T@frame,np.eye(3),atol=1e-12,rtol=0.0) or np.linalg.det(frame) < 0.0:
                raise ValueError(f"{name} must be an explicit right-handed orthonormal frame")
            object.__setattr__(self,name,frame)
        if self.driver_face_mm[0] >= self.driver_face_mm[1] or self.driven_face_mm[0] >= self.driven_face_mm[1]:
            raise ValueError("both physical face intervals must be nonempty")

    def record(self) -> dict:
        values = asdict(self)
        values["driver_frame"] = self.driver_frame.tolist()
        values["driven_frame"] = self.driven_frame.tolist()
        # An absent band is a named absence, not JSON Infinity.
        for field in ("driver_shoulder_z_mm","driver_turned_radius_mm"):
            if not math.isfinite(values[field]):
                values[field] = None
        return values


@dataclass(frozen=True)
class ContactPair:
    name: str
    driver: StockFormProfile
    driven: StockFormProfile
    placement: Placement


def screw_point(profile: StockFormProfile, point, station: float, tooth: int,
                phase_rad: float, placement: Placement) -> np.ndarray:
    angle = tooth*profile.angular_pitch_rad + phase_rad + station/profile.lead_per_radian_mm
    c,s = math.cos(angle),math.sin(angle)
    x,y = point
    return np.asarray(placement.driven_origin_mm) + placement.driven_frame @ np.array([c*x-s*y,s*x+c*y,station])

class GapAngles:
    """Monotone radial inverse of the actual straight-pinion gap boundary.

    The core supplies every curve. Polar interpolation has a separate
    outward geometric error bound; no ideal-N equation enters this inverse.
    Below the root-arc envelope a gap may have disconnected strips and must
    not be treated as a single interval. The surface search refuses there.
    """

    def __init__(self, profile: StockFormProfile, samples: int = 2048):
        if profile.helix_angle_deg != 0.0:
            raise ValueError("the angular-inverse driver must be a straight finite stock profile")
        self.profile = profile
        self.minimum = profile.root_radius_min_mm
        self.maximum = profile.blank_radius_mm
        # Arithmetic allowance for the table's material-frame rotation/hypot
        # versus the canonical evaluator's radius. This is NOT a shop/model
        # tolerance and cannot bridge a missing finite cutter segment.
        self.endpoint_radius_error_mm = 64*np.finfo(float).eps*max(
            1.0,profile.blank_radius_mm,profile.template.tip_radius_mm,
            abs(profile.radial_translation_mm),
        )
        self.working_parameter_domains = []
        points = []
        geometric_error = profile.geometry_error_bound_mm
        for segment in profile.external_boundary_segments():
            if segment.kind not in ("radial", "flank"):
                continue
            if segment.point(0.5)[1] < 0.0:
                continue
            low,high = sorted((segment._a,segment._b))
            evaluator = profile.flank_point if segment.kind == "flank" else profile.radial_point
            rlow,rhigh = math.hypot(*evaluator(low)),math.hypot(*evaluator(high))
            if rhigh < rlow:
                raise ValueError("actual finite working branch folds in radius")
            self.working_parameter_domains.append((segment.kind,low,high,rlow,rhigh))
            points.extend(segment.point(float(t)) for t in np.linspace(0.0, 1.0, samples + 1))
            # Curve-to-chord deviation plus polar interpolation deviation.
            geometric_error = max(geometric_error, (
                segment.second_derivative_bound_mm
                + segment.speed_bound_mm ** 2 / self.minimum
            ) / (8.0 * samples * samples))
        if not points:
            raise ValueError("actual pinion has no supported material flank")
        xy = np.asarray(points)
        rr = np.hypot(xy[:, 0], xy[:, 1])
        aa = profile.angular_pitch_rad / 2.0 - np.arctan2(xy[:, 1], xy[:, 0])
        order = np.argsort(rr)
        self.r, self.a = rr[order], aa[order]
        self.branch_minimum = float(self.r[0])
        self.minimum = self.branch_minimum
        # Angle may turn at Q=0 for negative tool translation; a single
        # radial boundary remains valid. Range queries include every knot.
        canonical_top = max(domain[4] for domain in self.working_parameter_domains)
        if (self.r[0] > profile.root_radius_max_mm+profile.geometry_error_bound_mm+self.endpoint_radius_error_mm
                or abs(canonical_top-self.maximum) > self.endpoint_radius_error_mm):
            raise ValueError("finite pinion boundary does not span its working radial interval within arithmetic enclosure")
        geometric_error += self.endpoint_radius_error_mm
        if geometric_error >= self.branch_minimum:
            raise ValueError("radial interpolation geometry error reaches the actual root envelope")
        # Cartesian curve/chord error changes both polar angle AND the
        # radius at which the inverse is read. Pay the actual inverse
        # slope, which can be arbitrarily large near a translated fold.
        self.error_rad = (math.asin(min(1.0,geometric_error/(self.branch_minimum-geometric_error)))
                          +self.radial_slope_bound()*geometric_error)

    def angle(self, radius: float) -> float:
        return float(np.interp(radius, self.r, self.a))


    def branch_range(self, lower_radius: float, upper_radius: float) -> tuple[float,float]:
        """Actual finite flank/radial inverse, including positive-T root strip."""
        lo,hi = max(float(self.r[0]),lower_radius),min(self.maximum,upper_radius)
        if lo > hi:
            raise ValueError("radial interval misses the finite actual cutter branch")
        first,last = np.searchsorted(self.r,(lo,hi))
        values = self.a[first:last]
        endpoints = (self.angle(lo),self.angle(hi))
        return min(*endpoints,float(np.min(values,initial=math.inf))), max(*endpoints,float(np.max(values,initial=-math.inf)))

    def _working_parameter(self, radius: float):
        """Invert only real native branch domains; return kind, parameter, snap.

        ``snap`` denotes an arithmetic-enclosed endpoint projection. Its entire
        radial allowance is paid in error_rad; projected queries never enable
        the Taylor lower-bound shortcut. No exception from brentq is hidden.
        """
        if not math.isfinite(radius):
            raise ValueError("working inverse radius must be finite")
        p = self.profile
        for kind,low,high,rlow,rhigh in self.working_parameter_domains:
            if not rlow <= radius <= rhigh:
                continue
            if radius == rlow:
                return kind,low,False
            if radius == rhigh:
                return kind,high,False
            if kind == "radial":
                shift,k = p.radial_translation_mm,p.template.half_space_base_angle_rad
                q = shift*math.sin(k)
                parameter = math.sqrt((radius-abs(q))*(radius+abs(q)))-shift*math.cos(k)
                parameter = min(high,max(low,parameter))
                if abs(math.hypot(*p.radial_point(parameter))-radius) > self.endpoint_radius_error_mm:
                    raise ValueError("actual radial inverse exceeds its arithmetic enclosure")
            else:
                parameter = brentq(
                    lambda u:math.hypot(*p.flank_point(u))-radius,low,high,
                    xtol=math.ulp(1.0),rtol=4*np.finfo(float).eps,
                )
            return kind,parameter,False
        distance,kind,parameter = min(
            (abs(radius-r),kind,u)
            for kind,low,high,rlow,rhigh in self.working_parameter_domains
            for u,r in ((low,rlow),(high,rhigh))
        )
        if distance <= self.endpoint_radius_error_mm:
            return kind,parameter,True
        raise ValueError("radius leaves actual finite working-side support beyond arithmetic enclosure")

    def _slope_at_parameter(self, kind: str, parameter: float) -> float:
        """Actual finite endpoint/interior derivative, without inverse rooting."""
        p = self.profile
        rb,shift,k = p.template.base_radius_mm,p.radial_translation_mm,p.template.half_space_base_angle_rad
        if kind == "radial":
            point = p.radial_point(parameter)
            S,Q = parameter+shift*math.cos(k),shift*math.sin(k)
        else:
            point = p.flank_point(parameter)
            S,Q = rb+shift*math.cos(k+parameter),rb*parameter+shift*math.sin(k+parameter)
        if S <= 0:
            raise ValueError("actual finite working branch is not polar-monotone")
        return Q/(math.hypot(*point)*S)

    def exact_angle(self, radius: float) -> float:
        """Actual core point angle; endpoint arithmetic remains explicitly paid."""
        radius = min(self.maximum,max(self.branch_minimum,radius))
        kind,parameter,_ = self._working_parameter(radius)
        point = (self.profile.radial_point(parameter) if kind == "radial"
                 else self.profile.flank_point(parameter))
        return math.atan2(point[1],point[0])

    def exact_slope(self, radius: float) -> float:
        radius = min(self.maximum,max(self.branch_minimum,radius))
        kind,parameter,_ = self._working_parameter(radius)
        return self._slope_at_parameter(kind,parameter)

    def radial_slope_bound(self) -> float:
        """Bound |d gap-angle/dr| on the complete finite straight flank.

        For the translated reference involute, its unit tangent gives
        S=p.dot(t)=rb+T*cos(k+u), Q=p.cross(t)=rb*u+T*sin(k+u).
        Thus d polar-angle/dr=Q/(r*S), including negative T and custom6.
        Radial continuation has S=r_ref+T*cos(k), Q=T*sin(k).
        A nonpositive S is a genuine polar-fold refusal, not an ideal flank.
        """
        p = self.profile
        rb, shift = p.template.base_radius_mm, p.radial_translation_mm
        k = p.template.half_space_base_angle_rad
        u0, u1 = p.flank_parameter_min, p.flank_parameter_max
        angles = [k+u0, k+u1]
        angles.extend(j*math.pi for j in range(math.ceil((k+u0)/math.pi),
                                              math.floor((k+u1)/math.pi)+1))
        smin = min(rb+shift*math.cos(z) for z in angles)
        qmax = rb*u1+abs(shift)
        for kind,low,_,_,_ in self.working_parameter_domains:
            if kind == "radial":
                smin = min(smin,low+shift*math.cos(k))
        if smin <= 0.0:
            raise ValueError("finite actual cutter has no positive polar radial derivative")
        if shift >= 0.0 and 0.0 <= k+u0 <= k+u1 <= math.pi:
            # On the involute, d[Q/(rS)]/du is positive: its first two
            # terms combine through r²-Q*rb*u=S²+Q*T*sin(k+u) >= 0,
            # and the remaining term is nonnegative. The radial
            # continuation decreases with radius, so only its first
            # endpoint and the final involute endpoint can be maximal.
            endpoint = max(abs(self._slope_at_parameter(kind,parameter))
                           for kind,low,high,_,_ in self.working_parameter_domains
                           for parameter in (low,high))
            return endpoint+256*np.finfo(float).eps*(1.0+endpoint)
        return qmax/(self.branch_minimum*smin)

    def derivatives(self, radius: float, minimum_radius: float):
        """Exact radial slope and conservative Cartesian Hessian enclosure.

        A cusp or radial/flank transition retains the original Lipschitz
        enclosure. The smooth bound uses the actual translated tangent,
        not a positive-T pressure-angle surrogate.
        """
        p = self.profile
        u0,u1 = p.flank_parameter_min,p.flank_parameter_max
        base = math.hypot(*p.flank_point(u0))
        if u1 <= u0 or minimum_radius <= base+1e-10 or not self.minimum <= radius <= self.maximum:
            return None
        rb, shift = p.template.base_radius_mm,p.radial_translation_mm
        k = p.template.half_space_base_angle_rad
        try:
            kind,u,projected = self._working_parameter(radius)
            lower_kind,ulo,lower_projected = self._working_parameter(minimum_radius)
        except ValueError:
            return None  # Retain the ordinary outward Lipschitz enclosure.
        if kind != "flank" or lower_kind != "flank" or projected or lower_projected:
            return None
        angles = [k+ulo,k+u1]
        angles.extend(j*math.pi for j in range(math.ceil((k+ulo)/math.pi),
                                              math.floor((k+u1)/math.pi)+1))
        smin = min(rb+shift*math.cos(z) for z in angles)
        if smin <= 0.0 or ulo <= 0.0:
            return None
        qmax = rb*u1+abs(shift)
        s = rb+shift*math.cos(k+u)
        q = rb*u+shift*math.sin(k+u)
        slope = q/(radius*s)
        first = qmax/(minimum_radius*smin)
        second = (1.0/(rb*ulo*smin)+qmax/(minimum_radius**2*smin)
                  +qmax*abs(shift)/(rb*ulo*smin**3))
        # Hessian of a(r)-direction*atan2(y,x).
        return slope, second+first/minimum_radius+2.0/minimum_radius**2


@dataclass(frozen=True)
class Contact:
    phase_offset_rad: float
    driven_tooth: int
    segment: str
    kind: str
    parameter: float
    station_mm: float
    world_point_mm: tuple[float, float, float]
    driver_radius_mm: float
    driver_z_mm: float
    driven_normal_world: tuple[float, float, float]
    driver_normal_world: tuple[float, float, float]
    opposed_normal_residual: float
    driven_per_driver_velocity: float
    common_normal_supported: bool
    common_normal_error_bound: float


@dataclass(frozen=True)
class Window:
    driver_phase_rad: float
    lower_rad: float
    upper_rad: float
    error_rad: float
    lower_contact: Contact | None
    upper_contact: Contact | None
    branch_intervals: tuple[tuple[int, float, float], ...]
    boxes: int
    root_contact: bool
    branch_phase_reserves_rad: tuple[tuple[int, float], ...] = ()
    row_intervals_mm: tuple[tuple[float, float], ...] = ()
    phase_error_rad: float = 0.0
    root_free_intervals_rad: tuple[tuple[float,float], ...] = ()
    free_intervals_rad: tuple[tuple[float,float], ...] = ()
    root_sweep: dict | None = None
    supported_branch_contacts: tuple[dict, ...] = ()
    surface_extrema_enclosures_rad: tuple[dict, ...] = ()
    surface_numerical_resolved: bool = False

    @property
    def open(self) -> bool:
        return math.isfinite(self.lower_rad) and math.isfinite(self.upper_rad)

    @property
    def no_overlap(self) -> bool:
        return (self.open and self.surface_numerical_resolved and not self.root_contact and bool(self.free_intervals_rad)
                and self.upper_rad-self.lower_rad > 2*(self.error_rad+self.phase_error_rad))


def grounded_contact(contact: Contact | None) -> bool:
    """Only real finite working side/corner normals may support a branch."""
    return (contact is not None and contact.common_normal_supported
            and not any(kind in contact.kind for kind in ("root_arc","root_corner","axial_face"))
            and math.isfinite(contact.driven_per_driver_velocity)
            and contact.driven_per_driver_velocity < 0.0
            and contact.opposed_normal_residual <= contact.common_normal_error_bound)


@dataclass(frozen=True)
class EndFacePatch:
    """Conservative radial fan of one exact perimeter at a physical end face.

    Fan parameter v is radial fraction, not axial station. Fans enclose
    non-star-shaped material too. Removed fan regions are culled with an
    independent perimeter-distance bound; witnesses use contains_material.
    """

    boundary: object
    station_mm: float
    outward_sign: int

    @property
    def name(self):
        return f"{self.boundary.name}:end_face:{self.outward_sign:+d}"

    kind = "axial_face"

    @property
    def speed_bound_mm(self):
        return self.boundary.speed_bound_mm

    @property
    def second_derivative_bound_mm(self):
        return self.boundary.second_derivative_bound_mm

    def point(self, t):
        return self.boundary.point(t)

    def derivative(self, t):
        return self.boundary.derivative(t)


class ContactSearch:
    """Actual surface-envelope search at one crank phase (radians)."""

    def __init__(
        self, case: ContactPair, driver_phase_rad: float, *,
        driven_phase_rad: float | None = None, driven_teeth: tuple[int,...] | None = None,
        position_error_mm: float = 0.0,
        radial_error_mm: float = 0.0, axial_error_mm: float = 0.0,
    ):
        self.case = case
        self.phase = driver_phase_rad
        if any(not math.isfinite(value) or value < 0.0
               for value in (position_error_mm,radial_error_mm,axial_error_mm)):
            raise ValueError("position/radial/axial errors must be finite nonnegative enclosures")
        self.position_error_mm = position_error_mm
        self.radial_error_mm = position_error_mm+radial_error_mm
        self.axial_error_mm = position_error_mm+axial_error_mm
        self.driven_teeth = tuple(range(case.driven.teeth)) if driven_teeth is None else driven_teeth
        if not self.driven_teeth or any(type(tooth) is not int or not 0 <= tooth < case.driven.teeth for tooth in self.driven_teeth):
            raise ValueError("driven_teeth must identify actual physical teeth")
        self.gap = GapAngles(case.driver)
        self.position_angle_error_rad = self.radial_error_mm*math.hypot(
            1.0/self.gap.minimum,self.gap.radial_slope_bound())
        self.placement = case.placement
        self.seed = -self.placement.driver_clocking_rad
        self.ratio = case.driver.teeth / case.driven.teeth
        self.gear_phase = (self.placement.driven_clocking_rad-self.phase*self.ratio
                           if driven_phase_rad is None else driven_phase_rad)
        self.frame = self.placement.driver_frame
        self.centre = np.asarray(self.placement.driver_origin_mm)
        self.pitch = case.driver.angular_pitch_rad
        perimeter = case.driven.external_boundary_segments()
        self.segments = (*perimeter, *(
            EndFacePatch(segment, station, sign)
            for station, sign in zip(self.placement.driven_face_mm, (-1, 1))
            for segment in perimeter
        ))
        self.perimeter = perimeter
        self.twist = math.tan(math.radians(case.driven.helix_angle_deg)) / case.driven.pitch_radius_mm
        self.axial_speed = math.hypot(1.0, case.driven.blank_radius_mm * self.twist)
        self.root_contact = False
        self.root_domain_witness = None
        self.surface_extrema = {}
        self.support_reserves = {}
        self.row_intervals = {}

    def point(self, segment, tooth: int, t: float, station: float) -> tuple[np.ndarray, np.ndarray]:
        point = segment.point(t)
        if isinstance(segment, EndFacePatch):
            point = (station*point[0], station*point[1])
            station = segment.station_mm
        world = screw_point(self.case.driven, point, station, tooth, self.gear_phase, self.placement)
        local = (world - self.centre) @ self.frame
        return world, local

    def surface_member(self, segment, t, station) -> bool:
        if not isinstance(segment, EndFacePatch):
            return True
        x,y = segment.point(t)
        return self.case.driven.contains_material(station*x, station*y,
                                                 rotate_rad=self.case.driven.angular_pitch_rad/2)

    def cap_removed(self, segment, t, fraction, rho) -> bool:
        """Cull only when the exact perimeter is farther than the fan box.

        A fixed polygon error cannot disappear under surface subdivision.
        Refine ambiguous perimeter chords instead of keeping a fictitious
        material strip of that fixed width on every physical end cap.
        """
        if not isinstance(segment, EndFacePatch) or self.surface_member(segment,t,fraction):
            return False
        point = fraction*np.asarray(segment.point(t))
        pitch = self.case.driven.angular_pitch_rad
        pending = []
        for clock in (-pitch,0.0,pitch):
            c,s = math.cos(clock),math.sin(clock)
            q = np.array([c*point[0]+s*point[1],-s*point[0]+c*point[1]])
            for boundary in self.perimeter:
                pending.append((boundary,q,0.0,1.0))
        geometric = self.case.driven.geometry_error_bound_mm
        while pending:
            boundary,q,lo,hi = pending.pop()
            a,b = np.asarray(boundary.point(lo)),np.asarray(boundary.point(hi))
            delta = b-a
            denominator = float(delta@delta)
            parameter = min(1.0,max(0.0,float((q-a)@delta)/denominator)) if denominator else 0.0
            distance = float(np.linalg.norm(q-a-parameter*delta))
            error = boundary.second_derivative_bound_mm*(hi-lo)**2/8+geometric
            if distance-error > rho:
                continue
            if distance+error <= rho or error <= 2*geometric:
                return False
            middle = (lo+hi)/2
            if middle in (lo,hi):
                return False
            pending.extend(((boundary,q,lo,middle),(boundary,q,middle,hi)))
        return True

    def second_speed(self, segment):
        return self.case.driven.blank_radius_mm if isinstance(segment,EndFacePatch) else self.axial_speed

    def surface_tangents(self, segment, tooth, t, station):
        x,y = segment.point(t)
        dx,dy = segment.derivative(t)
        cap = isinstance(segment,EndFacePatch)
        physical_station = segment.station_mm if cap else station
        angle = tooth*self.case.driven.angular_pitch_rad+self.gear_phase+physical_station*self.twist
        c,s = math.cos(angle),math.sin(angle)
        tangent = np.array([c*dx-s*dy,s*dx+c*dy,0.0])
        if cap:
            return self.placement.driven_frame@(station*tangent), self.placement.driven_frame@np.array([c*x-s*y,s*x+c*y,0.0])
        axial = np.array([-self.twist*(s*x+c*y),self.twist*(c*x-s*y),1.0])
        return self.placement.driven_frame@tangent,self.placement.driven_frame@axial

    def angles(self, local: np.ndarray) -> tuple[float, float]:
        radius = math.hypot(local[0], local[1])
        theta = math.atan2(local[1], local[0]) + self.seed - self.phase - self.pitch / 2.0
        theta = (theta + self.pitch / 2.0) % self.pitch - self.pitch / 2.0
        half_gap = self.gap.angle(radius)
        return -half_gap - theta, half_gap - theta

    def feasible(self, local: np.ndarray) -> bool:
        radius = math.hypot(local[0], local[1])
        p = self.placement
        tip = self.gap.maximum if local[2] <= p.driver_shoulder_z_mm else min(self.gap.maximum, p.driver_turned_radius_mm)
        return self.gap.minimum <= radius <= tip and p.driver_face_mm[0] <= local[2] <= p.driver_face_mm[1]

    def contact(self, segment, tooth: int, t: float, station: float, direction: int) -> Contact:
        world,local = self.point(segment,tooth,t,station)
        low,high = self.angles(local)
        p = self.placement
        cap = isinstance(segment,EndFacePatch)
        boundary = segment.boundary if cap else segment
        physical_station = segment.station_mm if cap else station
        point = np.asarray(boundary.point(t))*(station if cap else 1.0)
        radius = math.hypot(local[0],local[1])
        angular_correction = self.gap.exact_angle(radius)-self.gap.angle(radius)
        low,high = low-angular_correction,high+angular_correction
        radial = np.array([local[0]/radius,local[1]/radius,0.0])
        azimuthal = np.array([-radial[1],radial[0],0.0])
        normal_driver = self.frame@(radius*self.gap.exact_slope(radius)*radial-direction*azimuthal)
        normal_driver /= np.linalg.norm(normal_driver)
        driver_normals = [normal_driver]
        driven_normals = []
        tolerance = (self.case.driver.geometry_error_bound_mm+self.case.driven.geometry_error_bound_mm
                     +1e-13*self.case.driver.template.base_radius_mm*self.case.driver.flank_parameter_max
                     +1024*np.finfo(float).eps*(1+float(np.linalg.norm(world))))
        cap_edge = cap and abs(station-1.0)*self.case.driven.blank_radius_mm <= tolerance
        kind = boundary.kind if not cap or cap_edge else "axial_face"
        if not cap or cap_edge:
            tangent,axial = self.surface_tangents(boundary,tooth,t,physical_station)
            side = np.cross(tangent,axial)
            if np.linalg.norm(side) > 1e-15:
                driven_normals.append(side/np.linalg.norm(side))
            # Include every genuine adjacent native segment at an endpoint.
            # No interpolated radial normal can replace a finite tip joint.
            if min(abs(t),abs(1.0-t)) < 1e-5:
                for other in self.segments:
                    if isinstance(other,EndFacePatch):
                        continue
                    for endpoint in (0.0,1.0):
                        if np.linalg.norm(np.asarray(other.point(endpoint))-point)>tolerance:
                            continue
                        if other.kind=="root_arc" and "/driven_root_corner" not in kind:
                            kind += "/driven_root_corner"
                        tangent,axial = self.surface_tangents(other,tooth,endpoint,physical_station)
                        normal = np.cross(tangent,axial)
                        if np.linalg.norm(normal)>1e-15:
                            driven_normals.append(normal/np.linalg.norm(normal))
        if abs(math.hypot(*point)-self.case.driven.blank_radius_mm)<=tolerance and (
                boundary.kind in ("flank","radial") or min(abs(t),abs(1-t))<1e-5):
            kind += "/driven_tip_corner"
        if abs(radius-self.gap.branch_minimum)<=tolerance:
            kind += "/driver_root_corner"
        tip = self.gap.maximum if local[2] <= p.driver_shoulder_z_mm else min(self.gap.maximum,p.driver_turned_radius_mm)
        if abs(radius-tip)<=tolerance:
            driver_normals.append(self.frame@radial)
            kind += "/driver_tip_corner"
        for edge,sign in zip(p.driver_face_mm,(-1,1)):
            if abs(local[2]-edge)<=tolerance:
                driver_normals.append(sign*self.frame[:,2])
                kind += "/driver_axial_edge"
        if abs(local[2]-p.driver_shoulder_z_mm)<=tolerance and radius>=p.driver_turned_radius_mm-tolerance:
            driver_normals.append(self.frame[:,2])
            kind += "/driver_shoulder_edge"
        for edge,sign in zip(p.driven_face_mm,(-1,1)):
            if abs(physical_station-edge)<=tolerance:
                driven_normals.append(sign*p.driven_frame[:,2])
                kind += "/driven_axial_interior" if cap and not cap_edge else "/driven_axial_edge"
        driver_velocity = np.cross(self.frame[:,2],world-self.centre)
        driven_velocity = np.cross(p.driven_frame[:,2],world-np.asarray(p.driven_origin_mm))
        if not driven_normals:
            raise ValueError("physical surface has no finite outward normal")
        a,b = np.column_stack(driver_normals),np.column_stack(driven_normals)
        matrix = np.column_stack((a,b))
        equality = np.vstack((matrix,np.ones(matrix.shape[1])))
        target = np.array([0.0,0.0,0.0,1.0])
        candidates = []
        # Find a genuine positive-cone intersection with a usable torque.
        # Both moment extrema are probed because the reverse flank changes
        # its sign. Coefficients and reconstructed opposition are checked;
        # never assign -driver_normal as a manufactured mate normal.
        moment = np.r_[np.zeros(a.shape[1]),driven_velocity@b]
        profile = self.case.driver
        rb = profile.template.base_radius_mm
        umax = profile.flank_parameter_max
        qmax = rb*umax+abs(profile.radial_translation_mm)
        eps = np.finfo(float).eps
        # brentq's declared u tolerance and floating tangent normalization;
        # not the optimizer residual and not an elastic contact allowance.
        normal_roundoff = ((1e-13+4*eps*umax)*(1+rb*umax*qmax/self.gap.minimum**2)
                           +2048*eps*(1+radius/self.gap.minimum+abs(profile.radial_translation_mm)/rb))
        common_error = normal_roundoff
        for sign in (-1,1):
            if a.shape[1] == 1 and b.shape[1] == 1:
                coefficients = np.array([0.5,0.5])
            else:
                solved = linprog(sign*moment,A_eq=equality,b_eq=target,
                                 bounds=(0.0,None),method="highs",
                                 options={"primal_feasibility_tolerance":1e-9,
                                          "dual_feasibility_tolerance":1e-9})
                if not solved.success or np.min(solved.x)<-1e-10:
                    continue
                coefficients = solved.x
            na,nb = a@coefficients[:a.shape[1]],b@coefficients[a.shape[1]:]
            minimum = min(np.linalg.norm(na),np.linalg.norm(nb))
            if minimum<1e-10:
                continue
            error_bound = 4*normal_roundoff/minimum
            na,nb = na/np.linalg.norm(na),nb/np.linalg.norm(nb)
            residual = float(np.linalg.norm(na+nb))
            denominator = float(driven_velocity@nb)
            numerator = float(driver_velocity@nb)
            if (residual <= error_bound
                    and abs(denominator)>np.linalg.norm(driven_velocity)*error_bound
                    and abs(numerator)>np.linalg.norm(driver_velocity)*error_bound
                    and numerator*denominator < 0.0):
                candidates.append((abs(denominator),na,nb,numerator/denominator,residual,error_bound))
        if candidates:
            _,normal_driver,normal_driven,velocity_ratio,residual,common_error = max(candidates,key=lambda row:row[0])
        else:
            normal_driven = driven_normals[0]
            residual = float(np.linalg.norm(normal_driver+normal_driven))
            velocity_ratio = math.nan
        return Contact(high if direction==1 else low,tooth,segment.name,kind,t,physical_station,
                       tuple(float(v) for v in world),radius,float(local[2]),
                       tuple(float(v) for v in normal_driven),tuple(float(v) for v in normal_driver),
                       residual,velocity_ratio,bool(candidates),common_error)

    def optimise(self, segment, tooth: int, box, direction: int, *, initial=None):
        t0, t1, s0, s1 = box

        def objective(q):
            _, local = self.point(segment, tooth, float(q[0]), float(q[1]))
            low, high = self.angles(local)
            return high if direction == 1 else -low

        def constraints(q):
            _, local = self.point(segment, tooth, float(q[0]), float(q[1]))
            r = math.hypot(local[0], local[1])
            p = self.placement
            tip = self.gap.maximum if local[2] <= p.driver_shoulder_z_mm else min(self.gap.maximum, p.driver_turned_radius_mm)
            return np.array([r-self.gap.minimum,tip-r,local[2]-p.driver_face_mm[0],p.driver_face_mm[1]-local[2]])

        def gradient(q):
            _,local = self.point(segment,tooth,float(q[0]),float(q[1]))
            r = math.hypot(local[0],local[1])
            er = np.array([local[0]/r,local[1]/r,0.0])
            et = np.array([-er[1],er[0],0.0])
            g = self.gap.exact_slope(r)*er-direction*et/r
            pt,ps = self.surface_tangents(segment,tooth,float(q[0]),float(q[1]))
            return np.array([g@(pt@self.frame),g@(ps@self.frame)])

        def constraint_gradient(q):
            _,local = self.point(segment,tooth,float(q[0]),float(q[1]))
            r = math.hypot(local[0],local[1])
            er = np.array([local[0]/r,local[1]/r,0.0])
            pt,ps = self.surface_tangents(segment,tooth,float(q[0]),float(q[1]))
            jac = np.column_stack((pt@self.frame,ps@self.frame))
            radial = er@jac
            return np.vstack((radial,-radial,jac[2],-jac[2]))

        seed = [(t0+t1)/2,(s0+s1)/2] if initial is None else initial
        solved = minimize(objective,seed,method="SLSQP",jac=gradient,
                          bounds=((t0,t1),(s0,s1)),
                          constraints={"type":"ineq","fun":constraints,"jac":constraint_gradient},
                          options={"ftol":1e-13,"maxiter":120})
        if not solved.success:
            return None
        q = np.asarray(solved.x)
        bounds = ((t0,t1),(s0,s1))
        for j,(lo,hi) in enumerate(bounds):
            if abs(q[j]-lo)<1e-8:
                q[j] = lo
            elif abs(q[j]-hi)<1e-8:
                q[j] = hi
        free = [j for j in range(2) if min(abs(q[j]-bounds[j][0]),abs(q[j]-bounds[j][1]))>1e-8]
        active = [j for j,value in enumerate(constraints(q)) if abs(value)<1e-8]
        active = active[:len(free)]
        if free:
            original = q.copy()
            jac = constraint_gradient(q)[active][:,free]
            multipliers = np.linalg.lstsq(jac.T,gradient(q)[free],rcond=None)[0] if active else np.empty(0)
            def stationarity(unknown):
                point = original.copy()
                point[free] = unknown[:len(free)]
                try:
                    grad = gradient(point)[free]
                    matrix = constraint_gradient(point)[active][:,free]
                    return np.r_[grad-matrix.T@unknown[len(free):],constraints(point)[active]]
                except (ValueError,OverflowError):
                    return np.full(len(unknown),1e10)
            polished = root(stationarity,np.r_[q[free],multipliers],tol=1e-11)
            if polished.success:
                candidate = original.copy()
                candidate[free] = polished.x[:len(free)]
                if all(lo<=value<=hi for value,(lo,hi) in zip(candidate,bounds)) and np.min(constraints(candidate))>=-1e-10:
                    q = candidate
        margins = np.array([self.radial_error_mm,self.radial_error_mm,
                            self.axial_error_mm,self.axial_error_mm])
        _,admitted_local = self.point(segment,tooth,float(q[0]),float(q[1]))
        if (math.hypot(admitted_local[0],admitted_local[1])+self.radial_error_mm
                > self.placement.driver_turned_radius_mm
                and admitted_local[2]+self.axial_error_mm > self.placement.driver_shoulder_z_mm):
            return None
        if np.min(constraints(q)-margins)>=-1e-9 and self.surface_member(segment,float(q[0]),float(q[1])):
            point = self.contact(segment,tooth,float(q[0]),float(q[1]),direction)
            return float(objective(q))+self.position_angle_error_rad,point
        return None

    def relaxed_value(self, segment, tooth, t, station, direction):
        """Value of the paid *lower-envelope model*, not a contact witness.

        Every displaced physical point is enclosed by this radial/azimuthal
        rectangle. Minimising its lower edge over the expanded physical
        domain supplies a lower bound, but never a carrying normal or an
        attainable pose. Its witnesses may therefore lie outside the eroded
        domain required of the independent guaranteed-contact upper bound.
        """
        if not self.surface_member(segment,t,station):
            return math.inf
        _,local = self.point(segment,tooth,t,station)
        r = math.hypot(local[0],local[1])
        p = self.placement
        if (local[2]+self.axial_error_mm < p.driver_face_mm[0]
                or local[2]-self.axial_error_mm > p.driver_face_mm[1]):
            return math.inf
        tip = self.gap.maximum if local[2]-self.axial_error_mm <= p.driver_shoulder_z_mm else min(self.gap.maximum,p.driver_turned_radius_mm)
        lo,hi = max(self.gap.minimum,r-self.radial_error_mm),min(tip,r+self.radial_error_mm)
        if lo > hi:
            return math.inf
        a0,_ = self.gap.branch_range(lo,hi)
        theta = math.atan2(local[1],local[0])+self.seed-self.phase-self.pitch/2
        theta = (theta+self.pitch/2)%self.pitch-self.pitch/2
        angular = math.asin(min(1.0,self.radial_error_mm/max(r,self.radial_error_mm))) if self.radial_error_mm else 0.0
        if abs(theta)+angular >= self.pitch/2:
            return a0-self.pitch/2-self.gap.error_rad
        return a0-direction*theta-angular-self.gap.error_rad

    def optimise_relaxed(self, segment, tooth, box, direction):
        """Improve only the enclosure-model incumbent, never physical proof."""
        t0,t1,s0,s1 = box
        def objective(q):
            value = self.relaxed_value(segment,tooth,float(q[0]),float(q[1]),direction)
            return value if math.isfinite(value) else 1e6
        def constraints(q):
            _,local = self.point(segment,tooth,float(q[0]),float(q[1]))
            r = math.hypot(local[0],local[1])
            p = self.placement
            tip = self.gap.maximum if local[2]-self.axial_error_mm <= p.driver_shoulder_z_mm else min(self.gap.maximum,p.driver_turned_radius_mm)
            return np.array([r+self.radial_error_mm-self.gap.minimum,tip-r+self.radial_error_mm,
                             local[2]+self.axial_error_mm-p.driver_face_mm[0],
                             p.driver_face_mm[1]-local[2]+self.axial_error_mm])
        solved = minimize(objective,[(t0+t1)/2,(s0+s1)/2],method="SLSQP",
                          bounds=((t0,t1),(s0,s1)),
                          constraints={"type":"ineq","fun":constraints},
                          options={"ftol":1e-13,"maxiter":120})
        if not solved.success:
            return math.inf
        return self.relaxed_value(segment,tooth,float(solved.x[0]),float(solved.x[1]),direction)

    def bound(self, segment, tooth: int, box: tuple[float, float, float, float], direction: int):
        t0, t1, s0, s1 = box
        t, s = (t0 + t1) / 2.0, (s0 + s1) / 2.0
        world, local = self.point(segment, tooth, t, s)
        rho = segment.speed_bound_mm*(t1-t0)/2.0+self.second_speed(segment)*(s1-s0)/2.0
        if self.cap_removed(segment,t,s,rho):
            return None
        axial_rho = rho+self.axial_error_mm
        rho += self.radial_error_mm
        r = math.hypot(local[0], local[1])
        p = self.placement
        tip = self.gap.maximum if local[2] - axial_rho <= p.driver_shoulder_z_mm else min(self.gap.maximum, p.driver_turned_radius_mm)
        if r-self.radial_error_mm < self.case.driver.root_radius_max_mm and p.driver_face_mm[0]-self.axial_error_mm <= local[2] <= p.driver_face_mm[1]+self.axial_error_mm and self.surface_member(segment,t,s):
            self.root_contact = True
            if self.root_domain_witness is None or r < self.root_domain_witness["driver_radius_mm"]:
                physical_station = segment.station_mm if isinstance(segment,EndFacePatch) else s
                self.root_domain_witness = {
                    "driven_tooth":tooth,"segment":segment.name,"parameter":t,
                    "physical_station_mm":physical_station,
                    "world_point_mm":tuple(float(value) for value in world),
                    "driver_local_point_mm":tuple(float(value) for value in local),
                    "driver_radius_mm":r,"driver_root_max_mm":self.case.driver.root_radius_max_mm,
                    "driver_root_min_mm":self.case.driver.root_radius_min_mm,
                    "position_ball_mm":self.position_error_mm,
                    "radial_error_mm":self.radial_error_mm,"axial_error_mm":self.axial_error_mm,
                    "point_below_root_max":r < self.case.driver.root_radius_max_mm,
                    "driven_actual_material_member":True,
                    "driver_actual_material_member_at_declared_phase":self.case.driver.contains_material(
                        float(local[0]),float(local[1]),
                        rotate_rad=p.driver_clocking_rad+self.phase+self.pitch/2),
                    "proof":"exact material witness below supported radial-inverse domain; pose-ball touch is distinguished from actual point",
                    "profile_solid_interference_certified":r < self.case.driver.root_radius_min_mm-self.case.driver.geometry_error_bound_mm
                        and p.driver_face_mm[0] < local[2] < p.driver_face_mm[1],
                }
        if r-rho > tip or r+rho < self.gap.minimum or local[2]+axial_rho < p.driver_face_mm[0] or local[2]-axial_rho > p.driver_face_mm[1]:
            return None
        angular = math.asin(min(1.0, rho / max(r, rho))) if rho else 0.0
        theta = math.atan2(local[1], local[0]) + self.seed - self.phase - self.pitch / 2.0
        theta = (theta + self.pitch / 2.0) % self.pitch - self.pitch / 2.0
        a0,a1 = self.gap.branch_range(max(self.gap.minimum,r-rho),min(tip,r+rho))
        # Work as a minimisation: direction +1 seeks the upper edge;
        # direction -1 seeks minus the lower edge.
        lower_bound = a0 - direction * theta - angular - self.gap.error_rad
        upper_bound = a1 - direction * theta + angular + self.gap.error_rad
        if abs(theta) + angular >= self.pitch / 2.0:
            lower_bound = a0 - self.pitch / 2.0 - self.gap.error_rad
            upper_bound = a1 + self.pitch / 2.0 + self.gap.error_rad
        elif self.radial_error_mm == 0.0 and self.gap.minimum <= r <= tip:
            derivatives = self.gap.derivatives(r,max(self.gap.minimum,r-rho))
            if derivatives is not None:
                slope,hessian = derivatives
                er = np.array([local[0]/r,local[1]/r,0.0])
                et = np.array([-er[1],er[0],0.0])
                gradient = slope*er-direction*et/r
                pt,ps = self.surface_tangents(segment,tooth,t,s)
                pt,ps = pt@self.frame,ps@self.frame
                ht,hs = (t1-t0)/2.0,(s1-s0)/2.0
                remainder = segment.second_derivative_bound_mm*ht*ht/2.0
                if isinstance(segment,EndFacePatch):
                    remainder += segment.speed_bound_mm*ht*hs
                else:
                    remainder += (abs(self.twist)*segment.speed_bound_mm*ht*hs
                                  +self.case.driven.blank_radius_mm*self.twist**2*hs*hs/2.0)
                taylor = (self.gap.angle(r)-direction*theta
                          -abs(float(gradient@pt))*ht-abs(float(gradient@ps))*hs
                          -float(np.linalg.norm(gradient))*remainder
                          -self.position_angle_error_rad
                          -hessian*rho*rho/2.0-self.gap.error_rad)
                lower_bound = max(lower_bound,taylor)
        candidate = None
        if self.feasible(local) and self.surface_member(segment,t,s):
            actual_tip = self.gap.maximum if local[2] <= p.driver_shoulder_z_mm else min(self.gap.maximum,p.driver_turned_radius_mm)
            margin = min(r-self.gap.minimum-self.radial_error_mm,
                         actual_tip-r-self.radial_error_mm,
                         local[2]-p.driver_face_mm[0]-self.axial_error_mm,
                         p.driver_face_mm[1]-local[2]-self.axial_error_mm)
            if r+self.radial_error_mm > p.driver_turned_radius_mm:
                margin = min(margin,p.driver_shoulder_z_mm-local[2]-self.axial_error_mm)
            if segment.kind in ("flank","radial") and margin > 0.0:
                reserve = margin/(self.ratio*self.case.driven.blank_radius_mm)
                self.support_reserves[tooth] = max(self.support_reserves.get(tooth,0.0),reserve)
                half = margin/self.axial_speed
                self.row_intervals.setdefault(tooth,[]).append((
                    max(p.driven_face_mm[0],s-half),min(p.driven_face_mm[1],s+half),
                ))
            lo, hi = self.angles(local)
            value = (hi if direction == 1 else -lo)+self.position_angle_error_rad
            if margin >= 0.0:
                candidate = (value, self.contact(segment, tooth, t, s, direction))
        return lower_bound, upper_bound, candidate

    def extremum(self, direction: int, tolerance_rad: float, max_boxes: int):
        queue = []
        serial = itertools.count()
        best = math.inf
        contact = None
        per_tooth = {}
        per_tooth_contacts = {}
        relaxed = {}
        retained = {}
        terminal_lower = {}
        terminal_count = {}
        count = 0
        axial_stations = np.linspace(*self.placement.driven_face_mm,9)
        for tooth in self.driven_teeth:
            for index, segment in enumerate(self.segments):
                stations = np.linspace(0.0,1.0,9) if isinstance(segment,EndFacePatch) else axial_stations
                # Initial station tiles cheaply cull the far side of the gear.
                for s0,s1 in zip(stations[:-1],stations[1:]):
                    box = (0.0, 1.0, float(s0), float(s1))
                    result = self.bound(segment, tooth, box, direction)
                    if result is None:
                        continue
                    lower, _, candidate = result
                    model = self.optimise_relaxed(segment,tooth,box,direction)
                    relaxed[tooth] = min(relaxed.get(tooth,math.inf),model)
                    fitted = self.optimise(segment, tooth, box, direction)
                    if fitted is not None and (candidate is None or fitted[0] < candidate[0]):
                        candidate = fitted
                    if candidate is not None:
                        value, point = candidate
                        if value < per_tooth.get(tooth,math.inf):
                            per_tooth[tooth],per_tooth_contacts[tooth] = value,point
                        if value < best:
                            best, contact = value, point
                    heapq.heappush(queue, (lower, next(serial), index, tooth, box))
        while queue:
            lower, _, index, tooth, box = heapq.heappop(queue)
            if lower >= relaxed.get(tooth,math.inf)-tolerance_rad:
                retained[tooth] = min(retained.get(tooth,math.inf),lower)
                continue
            if count >= max_boxes:
                raise RuntimeError(f"{self.case.name}: lower-envelope model unresolved after {count} boxes; numerical residual {(relaxed.get(tooth,math.inf)-lower)*self.case.driver.pitch_radius_mm:.6g} mm; pose enclosure is separate")
            count += 1
            t0, t1, s0, s1 = box
            segment = self.segments[index]
            motion = segment.speed_bound_mm*(t1-t0)/2+self.second_speed(segment)*(s1-s0)/2
            angular_motion = motion*math.hypot(1/self.gap.minimum,self.gap.radial_slope_bound())
            if angular_motion <= tolerance_rad/2:
                # A grazing or discontinuous feasibility boundary need not
                # contain an admissible midpoint. Retain its conservative
                # lower edge, rather than erase it or refine pose error.
                retained[tooth] = min(retained.get(tooth,math.inf),lower)
                terminal_lower[tooth] = min(terminal_lower.get(tooth,math.inf),lower)
                terminal_count[tooth] = terminal_count.get(tooth,0)+1
                continue
            if segment.speed_bound_mm * (t1-t0) > self.second_speed(segment) * (s1-s0):
                middle = (t0+t1)/2.0
                children = ((t0,middle,s0,s1),(middle,t1,s0,s1))
            else:
                middle = (s0+s1)/2.0
                children = ((t0,t1,s0,middle),(t0,t1,middle,s1))
            for child in children:
                result = self.bound(segment, tooth, child, direction)
                if result is None:
                    continue
                bound, _, candidate = result
                t0c,t1c,s0c,s1c = child
                model = self.relaxed_value(segment,tooth,(t0c+t1c)/2,(s0c+s1c)/2,direction)
                relaxed[tooth] = min(relaxed.get(tooth,math.inf),model)
                if candidate is not None:
                    value, point = candidate
                    if value < per_tooth.get(tooth,math.inf):
                        per_tooth[tooth],per_tooth_contacts[tooth] = value,point
                    if value < best:
                        best, contact = value, point
                if bound < relaxed.get(tooth,math.inf)-tolerance_rad:
                    heapq.heappush(queue, (bound,next(serial),index,tooth,child))
                else:
                    retained[tooth] = min(retained.get(tooth,math.inf),bound)
        # Box-midpoint witnesses bracket the value but need not be stationary.
        # Refit every selected branch on its PHYSICAL face bounds, not an
        # artificial subdivision edge, before claiming a contact normal.
        for tooth,point in tuple(per_tooth_contacts.items()):
            if point.common_normal_supported:
                continue
            segment = next(item for item in self.segments if item.name==point.segment)
            station = point.station_mm
            if isinstance(segment,EndFacePatch):
                driven_local = (np.asarray(point.world_point_mm)-np.asarray(self.placement.driven_origin_mm))@self.placement.driven_frame
                station = math.hypot(driven_local[0],driven_local[1])/math.hypot(*segment.point(point.parameter))
                s0,s1 = 0.0,1.0
            else:
                s0,s1 = self.placement.driven_face_mm
            fitted = self.optimise(segment,tooth,(0.0,1.0,s0,s1),direction,
                                   initial=(point.parameter,min(s1,max(s0,station))))
            if fitted is not None and fitted[1].common_normal_supported:
                value,polished = fitted
                # The polished physical witness changes the upper edge;
                # its distance from the independently retained lower edge
                # is paid below, including all irreducible pose uncertainty.
                per_tooth[tooth],per_tooth_contacts[tooth] = value,polished
            # Eligibility is decided after BOTH extrema: an unsupported
            # second side must not erase a genuine supported first side.
        if per_tooth:
            selected = min(per_tooth,key=per_tooth.get)
            best,contact = per_tooth[selected],per_tooth_contacts[selected]
        branch_enclosures = {
            tooth:(lower,per_tooth.get(tooth,math.inf))
            for tooth,lower in retained.items()
        }
        lower = min(retained.values(),default=math.inf)
        incumbent = min(relaxed.values(),default=math.inf)
        def residual(lo,inc):
            return max(0.0,inc-lo) if math.isfinite(lo) and math.isfinite(inc) else math.inf
        branch_numerics = tuple({
            "tooth":tooth,"lower_rad":lo,
            "relaxed_incumbent_rad":relaxed.get(tooth,math.inf),
            "achieved_residual_rad":residual(lo,relaxed.get(tooth,math.inf)),
            "terminal_lower_rad":terminal_lower.get(tooth),
            "terminal_boxes":terminal_count.get(tooth,0),
        } for tooth,lo in sorted(retained.items()))
        self.surface_extrema[direction] = {
            "lower_rad":lower,
            "upper_rad":best,
            "branches":tuple((tooth,low,high) for tooth,(low,high) in sorted(branch_enclosures.items())
                             if math.isfinite(high)),
            "unwitnessed_branch_lower_rad":tuple((tooth,low) for tooth,(low,high) in sorted(branch_enclosures.items())
                                                 if not math.isfinite(high)),
            "numerical_tolerance_rad":tolerance_rad,
            "relaxed_incumbent_rad":incumbent,
            "achieved_residual_rad":residual(lower,incumbent),
            "terminal_lower_rad":min(terminal_lower.values()) if terminal_lower else None,
            "terminal_boxes":sum(terminal_count.values()),
            "branch_numerics":branch_numerics,
            "radial_pose_error_mm":self.radial_error_mm,
            "axial_pose_error_mm":self.axial_error_mm,
        }
        return best, contact, per_tooth, count, per_tooth_contacts

    def window(
        self, maximum_error_mm: float = 0.001, max_boxes: int = 500000, *,
        phase_half_width_rad: float = 0.0, driven_phase_half_width_rad: float = 0.0,
        required_root_air_mm: float = 0.0,
    ) -> Window:
        if not math.isfinite(maximum_error_mm) or maximum_error_mm <= 0.0:
            raise ValueError("surface error must be finite and positive")
        if any(not math.isfinite(value) or value < 0.0 for value in
               (phase_half_width_rad,driven_phase_half_width_rad,required_root_air_mm)):
            raise ValueError("phase-cell and root-air bounds must be finite and nonnegative")
        # Numerical subdivision and irreducible manufacturing-domain width
        # are different quantities. The latter is retained in the resulting
        # extrema enclosure, never used as a hoped-for convergence target.
        tolerance = maximum_error_mm/self.case.driver.pitch_radius_mm
        self.surface_extrema.clear()
        upper, up_contact, up_pairs, up_count, up_contacts = self.extremum(1, tolerance, max_boxes)
        negative_lower, low_contact, low_pairs, low_count, low_contacts = self.extremum(-1, tolerance, max_boxes)
        branches = tuple((tooth, -low_pairs.get(tooth, math.inf), up_pairs.get(tooth, math.inf)) for tooth in sorted(up_pairs.keys() | low_pairs.keys()))
        proofs = tuple(
            {"tooth":tooth,"contacts":tuple(
                {"side":side,"contact":asdict(contact)}
                for side,contact in (("lower",low_contacts.get(tooth)),("upper",up_contacts.get(tooth)))
                if grounded_contact(contact)
            )}
            for tooth,_,_ in branches
        )
        proofs = tuple(proof for proof in proofs if proof["contacts"])
        eligible = {proof["tooth"] for proof in proofs}
        error = max(
            enclosure["upper_rad"]-enclosure["lower_rad"]
            for enclosure in self.surface_extrema.values()
        )+self.gap.error_rad
        for enclosure in self.surface_extrema.values():
            error = max(error,max((high-low for _,low,high in enclosure["branches"]
                                   if math.isfinite(high)),default=0.0)+self.gap.error_rad)
        numerical_resolved = all(
            enclosure["achieved_residual_rad"] <= tolerance
            and all(branch["achieved_residual_rad"] <= tolerance
                    for branch in enclosure["branch_numerics"])
            for enclosure in self.surface_extrema.values()
        )
        active = {tooth for tooth,low,high in branches if tooth in eligible and high-low > 2*error}
        intervals = tuple(interval for tooth,values in self.row_intervals.items() if tooth in active for interval in values)
        lipschitz = 1.0+self.ratio*self.case.driven.blank_radius_mm*math.hypot(
            1.0/self.gap.minimum,self.gap.radial_slope_bound())
        phase_error = phase_half_width_rad*lipschitz
        root_search = copy(self)
        root_search.driven_teeth = tuple(range(self.case.driven.teeth))
        mate_half_width = self.ratio*phase_half_width_rad+driven_phase_half_width_rad
        rotation_ball = 2*self.case.driven.blank_radius_mm*math.sin(min(math.pi,mate_half_width)/2)
        root_search.radial_error_mm += rotation_ball
        root_search.axial_error_mm += rotation_ball
        root_bounds = root_free_intervals(
            root_search,maximum_error_mm=maximum_error_mm,max_boxes=max_boxes,
            required_root_air_mm=required_root_air_mm,
        )
        root_inner = erode_periodic_intervals(root_bounds.free_inner,phase_half_width_rad,self.pitch)
        lower = -negative_lower
        finite = math.isfinite(lower) and math.isfinite(upper)
        working_range = (lower-phase_error,upper+phase_error)
        root_limited = not (finite and root_bounds.status == "resolved" and any(
            low <= working_range[0] and high >= working_range[1] for low,high in root_inner))
        flank_inner = ((lower+error+phase_error,upper-error-phase_error),) if finite and upper-lower > 2*(error+phase_error) else ()
        free = intersect_intervals(root_inner,flank_inner)
        return Window(
            self.phase,lower,upper,error,low_contact,up_contact,branches,
            up_count+low_count+root_bounds.boxes,root_limited,
            tuple(sorted((tooth,reserve) for tooth,reserve in self.support_reserves.items() if tooth in eligible)),
            merge_intervals(intervals),phase_error,root_inner,free,asdict(root_bounds),proofs,
            tuple({"side":side,**self.surface_extrema[direction]}
                  for side,direction in (("lower",-1),("upper",1))),
            numerical_resolved,
        )


def erode_periodic_intervals(intervals, amount: float, pitch: float):
    """Pay angle motion without inventing a forbidden periodic seam."""
    half = pitch/2
    copies = merge_intervals((low+k*pitch,high+k*pitch)
                             for low,high in intervals for k in (-1,0,1))
    eroded = ((low+amount,high-amount) for low,high in copies if high-low > 2*amount)
    return intersect_intervals(tuple(eroded),((-half,half),))


def window(pose: ContactSearch, *, maximum_error_mm: float = 0.001) -> Window:
    return pose.window(maximum_error_mm)


def profile_record(profile: StockFormProfile) -> dict:
    return {"teeth": profile.teeth, "reference_teeth": profile.template.reference_teeth,
            "dp": profile.template.diametral_pitch, "pa_deg": profile.template.pressure_angle_deg,
            "blank_radius_mm": profile.blank_radius_mm,
            "radial_translation_mm": profile.radial_translation_mm,
            "helix_angle_deg": profile.helix_angle_deg}


def merge_intervals(intervals) -> tuple[tuple[float,float], ...]:
    merged = []
    for low,high in sorted(intervals):
        if high <= low:
            continue
        if merged and low <= merged[-1][1]:
            merged[-1] = (merged[-1][0],max(merged[-1][1],high))
        else:
            merged.append((low,high))
    return tuple(merged)






def loaded_driven_contact(
    pair: ContactPair, driver_phase_rad: float, *, driver_sense: int,
    driven_bracket_rad: tuple[float,float], maximum_error_mm: float = 0.001,
    driven_teeth: tuple[int,...] | None = None, position_error_mm: float = 0.0,
    radial_error_mm: float = 0.0, axial_error_mm: float = 0.0,
    required_root_air_mm: float = 0.0,
) -> dict:
    """Hold the actual driver fixed and bracket its loaded mate rotation.

    The declared driver clock includes the final assembly clock. Positive
    physical driver rotation loads the lower inverse-offset edge; negative
    loads the upper. A sign-changing interval of CERTIFIED edge signs,
    rather than an optimizer's nominal root, bounds driven phase error.
    Both endpoints must retain a finite window and supported carrying pair.
    """
    if driver_sense not in (-1,1):
        raise ValueError("driver_sense must be +1 or -1 about the declared axis")
    cache = {}
    def evaluate(angle):
        if angle not in cache:
            result = ContactSearch(
                pair,driver_phase_rad,driven_phase_rad=angle,driven_teeth=driven_teeth,
                position_error_mm=position_error_mm,
                radial_error_mm=radial_error_mm,axial_error_mm=axial_error_mm,
            ).window(maximum_error_mm,required_root_air_mm=required_root_air_mm)
            if not result.open or not result.surface_numerical_resolved:
                raise ValueError("loaded driven solve has no numerically resolved actual working-flank window")
            value = result.lower_rad if driver_sense == 1 else result.upper_rad
            cache[angle] = (value,result)
        return cache[angle]
    low,high = sorted(driven_bracket_rad)
    vlo,wlo = evaluate(low)
    vhi,whi = evaluate(high)
    def sign(value,result):
        return -1 if value < -result.error_rad else 1 if value > result.error_rad else 0
    slo,shi = sign(vlo,wlo),sign(vhi,whi)
    if not slo or not shi or slo == shi:
        raise ValueError("loaded driven phase bracket needs opposite interval-certified edge signs")
    target = maximum_error_mm/pair.driven.pitch_radius_mm
    for _ in range(64):
        if high-low <= 2*target:
            break
        middle = (low+high)/2.0
        value,result = evaluate(middle)
        side = sign(value,result)
        if side == slo:
            low = middle
        elif side == shi:
            high = middle
        else:
            # Uncertainty at the root cannot be discarded. Probe each half
            # of the remaining bracket and retain only certified signs.
            moved = False
            for probe in ((low+middle)/2.0,(middle+high)/2.0):
                pv,pw = evaluate(probe)
                ps = sign(pv,pw)
                if ps == slo and probe > low:
                    low,moved = probe,True
                elif ps == shi and probe < high:
                    high,moved = probe,True
            if not moved:
                break
    actual = (low+high)/2.0
    measured = ContactSearch(
        pair,driver_phase_rad,driven_phase_rad=actual,driven_teeth=driven_teeth,
        position_error_mm=position_error_mm,radial_error_mm=radial_error_mm,
        axial_error_mm=axial_error_mm,
    ).window(maximum_error_mm,driven_phase_half_width_rad=(high-low)/2,
             required_root_air_mm=required_root_air_mm)
    if (measured.root_sweep["status"] != "resolved"
            or not any(lo <= 0.0 <= hi for lo,hi in measured.root_free_intervals_rad)):
        raise ValueError("loaded root interval reaches actual noncarrying root material or its required air")
    contact = measured.lower_contact if driver_sense == 1 else measured.upper_contact
    if (contact is None or "axial_face" in contact.kind or "root_arc" in contact.kind
            or not contact.common_normal_supported
            or not math.isfinite(contact.driven_per_driver_velocity)
            or contact.opposed_normal_residual > contact.common_normal_error_bound):
        raise ValueError("loaded driven phase has no supported working-flank/corner carrying contact")
    ideal = pair.placement.driven_clocking_rad-driver_phase_rad*pair.driver.teeth/pair.driven.teeth
    driven_sense = -driver_sense
    return {
        "driver_phase_rad":driver_phase_rad,"driven_phase_rad":actual,
        "driven_phase_interval_rad":[low,high],"bound_rad":(high-low)/2.0,
        "driven_lag_rad":driven_sense*(ideal-actual),
        "driven_sense":driven_sense,"contact":asdict(contact),
        "backlash_driver_lower_mm":(measured.upper_rad-measured.lower_rad-2*measured.error_rad)*pair.driver.pitch_radius_mm,
        "root_sweep":measured.root_sweep,
        "numerical_error_bounds":{"surface_mm":maximum_error_mm,"driven_rad":(high-low)/2.0,
                                  "radial_mm":position_error_mm+radial_error_mm,
                                  "axial_mm":position_error_mm+axial_error_mm},
        "native_certificate":False,
    }


def source_pose(parameters=()) -> continuation.SourcePose:
    """Read named physical source coordinates, never infer them from point balls."""
    from diagnostics import stock_form_contact_continuation as continuation
    return continuation.SourcePose(tuple(
        (name,continuation.Interval(*limits)) for name,limits in parameters
    ))


def _geometry_cell_for_angle(cell, angle_coordinate):
    from diagnostics import stock_form_contact_continuation as continuation
    if angle_coordinate == "physical":
        return cell
    if angle_coordinate != "driven_material":
        raise ValueError("driven angle coordinate must be physical or driven_material")
    # beta*=beta+clock is the helper's actual material-coordinate gauge.
    # Remove its clock column exactly, rather than subtracting and adding
    # independent intervals. The caller retains the ORIGINAL source receipt.
    return continuation.PhaseCell(cell.driver_phase_rad, continuation.SourcePose(tuple(
        (name, value) for name, value in cell.source_pose.axes if name != "driven_clock_rad"
    )))


def _frame_operator_norm_upper(frame):
    """Tight outward Euclidean norm bound for a stored nominal frame."""
    from diagnostics import stock_form_contact_continuation as continuation
    return continuation.operator_norm_upper(frame)


def _physical_surface_inventory(pair):
    from diagnostics import stock_form_contact_continuation as continuation
    return continuation.physical_patch_inventory(pair)


def pose_cell_search(pair: ContactPair, cell: continuation.PhaseCell,
                     driven_phase_rad: continuation.Interval, *, angle_coordinate="physical",
                     additional_geometry_error_mm=0.0):
    """Enclose a correlated rigid-pose cell in true driver-local coordinates.

    The reference search has an identity driver frame; its old transpose-based
    point transform is therefore exactly the inverse. Interval residuals use
    F_driver^-1 F_driven, including stored-frame non-isometry. This does not
    alter the stationary Window implementation or either root helper.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    if not math.isfinite(additional_geometry_error_mm) or additional_geometry_error_mm < 0:
        raise ValueError("additional physical geometry enclosure must be finite and nonnegative")
    geometry_cell = _geometry_cell_for_angle(cell, angle_coordinate)
    phi, beta = geometry_cell.driver_phase_rad, driven_phase_rad
    sources = dict(geometry_cell.source_pose.axes)
    driver_clock = sources.get("driver_clock_rad", I.point(0))
    driven_clock = sources.get("driven_clock_rad", I.point(0))
    poses = {
        body: continuation.body_pose_bounds(pair, geometry_cell.source_pose, phi, beta, body=body)
        for body in ("driver", "driven")
    }
    centres = {
        body: continuation.body_pose_bounds(
            pair, geometry_cell.source_pose.centre(), I.point(phi.midpoint),
            I.point(beta.midpoint), body=body,
        ) for body in ("driver", "driven")
    }
    def relative_transform(driver, driven):
        matrix = tuple(tuple(
            sum(driver.inverse_frame[i][k]*driven.frame[k][j] for k in range(3))
            for j in range(3)) for i in range(3))
        shift = tuple(sum(
            driver.inverse_frame[i][k]*(driven.origin_mm[k]-driver.origin_mm[k])
            for k in range(3)) for i in range(3))
        return matrix, shift
    relative, translation = relative_transform(poses["driver"], poses["driven"])
    centre_matrix, centre_shift = relative_transform(centres["driver"], centres["driven"])
    reference = np.array([[value.midpoint for value in row] for row in centre_matrix])
    reference_translation = np.array([value.midpoint for value in centre_shift])
    support = (pair.driven.blank_radius_mm, pair.driven.blank_radius_mm,
               max(abs(value) for value in pair.placement.driven_face_mm))
    displacement = tuple((
        I.point((translation[i]-float(reference_translation[i])).magnitude)
        +sum(I.point((relative[i][j]-float(reference[i, j])).magnitude)*radius
             for j, radius in enumerate(support))
    ).upper for i in range(3))
    # Source Euler factors are exact real rotations. Only the stored nominal
    # matrices need a metric payment, independent of those rotation angles.
    inverse_norm = _frame_operator_norm_upper(
        continuation.frame_inverse_bounds(pair.placement.driver_frame))
    relative_norm = (I.point(inverse_norm)
                     *_frame_operator_norm_upper(pair.placement.driven_frame)).upper
    reference_beta = beta.midpoint+driven_clock.midpoint
    angular = (beta+driven_clock-I.point(reference_beta)).magnitude
    rotation = (I.point(min((I.point(pair.driven.blank_radius_mm)*angular).upper,
                           (I.point(pair.driven.blank_radius_mm)*2).upper))*relative_norm).upper
    reference_norm = _frame_operator_norm_upper(reference)
    geometry_extra = (I.point(max(0.0,(I.point(relative_norm)-reference_norm).upper))
                      *pair.driven.geometry_error_bound_mm).upper
    radial_norm = math.nextafter(math.nextafter(
        math.hypot(displacement[0], displacement[1]), math.inf), math.inf)
    padding = (I.point(inverse_norm)*additional_geometry_error_mm).upper
    radial = (I.point(radial_norm)+rotation+geometry_extra+padding).upper
    axial = (I.point(displacement[2])+rotation+geometry_extra+padding).upper
    placement = replace(
        pair.placement, driver_origin_mm=(0.0, 0.0, 0.0),
        driven_origin_mm=tuple(map(float, reference_translation)),
        driver_frame=np.eye(3), driven_frame=reference,
        driver_clocking_rad=pair.placement.driver_clocking_rad+driver_clock.midpoint,
    )
    search = ContactSearch(
        replace(pair, placement=placement), phi.midpoint,
        driven_phase_rad=reference_beta,
        radial_error_mm=radial, axial_error_mm=axial,
    )
    driver_motion = (phi+pair.placement.driver_clocking_rad+driver_clock
                     -I.point(phi.midpoint+placement.driver_clocking_rad)).magnitude
    return search, driver_motion


def root_free_pose_cell(pair: ContactPair, cell: continuation.PhaseCell,
                        driven_phase_rad: continuation.Interval, *,
                        maximum_error_mm: float, required_root_air_mm: float,
                        angle_coordinate="physical", additional_geometry_error_mm=0.0,
                        root_only=True):
    """Actual all-tooth/cap INNER root proof, with its declared angle gauge."""
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    if not math.isfinite(required_root_air_mm) or required_root_air_mm < 0:
        raise ValueError("source root-air floor must be finite and nonnegative")
    search, driver_motion = pose_cell_search(
        pair, cell, driven_phase_rad, angle_coordinate=angle_coordinate,
        additional_geometry_error_mm=additional_geometry_error_mm)
    inverse_norm = max(1.0, _frame_operator_norm_upper(
        continuation.frame_inverse_bounds(pair.placement.driver_frame)))
    frame_norm = max(1.0, _frame_operator_norm_upper(pair.placement.driver_frame))
    distance_scale = (I.point(1)/inverse_norm).lower
    # Zero is a specification floor, not a positive-air certificate. Query
    # a strictly positive amount grounded in the actual primitive arithmetic
    # enclosure; failure still means UNKNOWN, not a new manufacturing grade.
    rounding_air = sum(
        I.point(_frame_operator_norm_upper(getattr(pair.placement,f"{body}_frame")))
        *getattr(pair,body).geometry_error_bound_mm for body in ("driver","driven")
    ).upper
    physical_target = max(required_root_air_mm,rounding_air)
    if physical_target <= 0:
        raise ArithmeticError("actual primitive error gives no positive root-air query")
    local_required = (I.point(physical_target)/distance_scale).upper
    while (I.point(local_required)*distance_scale).lower < physical_target:
        local_required = math.nextafter(local_required,math.inf)
    bounded = root_free_intervals(
        search, maximum_error_mm=(I.point(maximum_error_mm)/frame_norm).lower,
        required_root_air_mm=local_required, root_only=root_only,
    )
    inner = erode_periodic_intervals(bounded.free_inner, driver_motion, search.pitch)
    resolved = bounded.status == "resolved" and any(lo <= 0.0 <= hi for lo,hi in inner)
    physical_air = ((I.point(bounded.root_air_lower_bound_mm)*distance_scale).lower
                    if resolved and bounded.root_air_lower_bound_mm is not None else None)
    resolved = resolved and physical_air is not None and physical_air > 0 and physical_air >= required_root_air_mm
    inventory, _, _ = _physical_surface_inventory(pair)
    return {
        "status": "PROVED" if resolved else "UNKNOWN",
        "root_free_driven_components_rad": (driven_phase_rad.record(),) if resolved else (),
        "inverse_offset_free_components_rad": inner,
        "driver_phase_motion_rad": driver_motion,
        "phase_cell_rad": cell.driver_phase_rad.record(),
        "same_source_pose": cell.source_pose.record(),
        "angle_coordinate": angle_coordinate,
        "driven_angle_domain_rad": driven_phase_rad.record(),
        "physical_driven_teeth": list(range(pair.driven.teeth)),
        "physical_patch_inventory": inventory,
        "source_frame_radial_error_mm": search.radial_error_mm,
        "source_frame_axial_error_mm": search.axial_error_mm,
        "additional_geometry_error_mm": additional_geometry_error_mm,
        "material_scope":bounded.material_scope,
        "driver_local_to_world_distance_lower": distance_scale,
        "physical_root_air_lower_bound_mm": physical_air,
        "physical_required_root_air_mm": required_root_air_mm,
        "root_sweep": asdict(bounded),
        "native_certificate": False,
    }


def _interval_dot(a, b):
    from diagnostics import stock_form_contact_continuation as continuation
    return sum((x*y for x,y in zip(a,b)),continuation.Interval.point(0.0))


def _interval_square(value):
    from diagnostics import stock_form_contact_continuation as continuation
    interval = continuation.Interval
    if value.lower <= 0 <= value.upper:
        upper = (interval.point(value.magnitude)*value.magnitude).upper
        return interval(0.0,upper)
    return value*value


def _relative_surface_derivatives(pair, cell, beta, segment, tooth, t, z, *,
                                  finite_master_extension=False, radial_fraction=None):
    """Exact screw-map point, t/z derivatives, and held-driver beta velocity."""
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    point,tangent = continuation.segment_bounds(
        segment,t,finite_master_extension=finite_master_extension)
    second = continuation.segment_second_derivative_bounds(
        segment,t,finite_master_extension=finite_master_extension)
    parameters = dict(cell.source_pose.axes)
    clock = parameters.get("driven_clock_rad",I.point(0.0))
    twist = 0.0 if math.isinf(pair.driven.lead_per_radian_mm) else 1.0/pair.driven.lead_per_radian_mm
    sigma = beta+clock+tooth*pair.driven.angular_pitch_rad+z*twist
    c,s = continuation.cos_bounds(sigma),continuation.sin_bounds(sigma)
    zero = I.point(0.0)
    def rotate(x,y,axial=zero):
        return c*x-s*y,s*x+c*y,axial
    if radial_fraction is None:
        local = rotate(*point,z)
        first = (rotate(*tangent),rotate(-twist*point[1],twist*point[0],I.point(1.0)))
        seconds = ((rotate(*second),rotate(-twist*tangent[1],twist*tangent[0])),
                   (rotate(-twist*tangent[1],twist*tangent[0]),
                    rotate(-twist*twist*point[0],-twist*twist*point[1])))
    else:
        boundary_point,boundary_tangent = point,tangent
        point = tuple(radial_fraction*v for v in point)
        tangent = tuple(radial_fraction*v for v in tangent)
        second = tuple(radial_fraction*v for v in second)
        local = rotate(*point,z)
        first = (rotate(*tangent),rotate(*boundary_point))
        seconds = ((rotate(*second),rotate(*boundary_tangent)),
                   (rotate(*boundary_tangent),(zero,zero,zero)))
    driver = continuation.body_pose_bounds(pair,cell.source_pose,cell.driver_phase_rad,beta,body="driver")
    driven = continuation.body_pose_bounds(pair,cell.source_pose,cell.driver_phase_rad,beta,body="driven")
    matrix = tuple(tuple(sum(driver.inverse_frame[i][k]*driven.frame[k][j] for k in range(3))
                         for j in range(3)) for i in range(3))
    shift = tuple(sum(driver.inverse_frame[i][k]*(driven.origin_mm[k]-driver.origin_mm[k])
                      for k in range(3)) for i in range(3))
    transform = lambda value:tuple(_interval_dot(row,value) for row in matrix)
    q = tuple(v+d for v,d in zip(transform(local),shift))
    qt = tuple(transform(v) for v in first)
    qtt = tuple(tuple(transform(v) for v in row) for row in seconds)
    ecc = (parameters.get("driven_ecc_x_mm",zero),parameters.get("driven_ecc_y_mm",zero))
    cb,sb = continuation.cos_bounds(beta+clock),continuation.sin_bounds(beta+clock)
    eccentric_velocity = (-cb*ecc[1]-sb*ecc[0],-sb*ecc[1]+cb*ecc[0],zero)
    beta_velocity = tuple(a+b for a,b in zip(rotate(-point[1],point[0]),eccentric_velocity))
    return q,qt,qtt,transform(beta_velocity),driver.inverse_frame,point,tangent,second


def _working_angle_derivatives(profile, kind, radius):
    """Analytic extension of this actual native working-side equation.

    Extension is only for a Lagrangian derivative enclosure, never material
    support. Finite chart and first-contact cover still enforce every cap.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    if profile.helix_angle_deg != 0.0:
        raise ValueError("working angular inverse requires a straight physical driver")
    rb,T = profile.template.base_radius_mm,profile.radial_translation_mm
    k = profile.template.half_space_base_angle_rad
    if radius.lower <= 0:
        raise ArithmeticError("working-angle derivative reaches the axis")
    if kind == "radial":
        Q = I.point(T)*continuation.sin_bounds(I.point(k))
        S = continuation.sqrt_bounds(_interval_square(radius)-_interval_square(Q))
        if S.lower <= 0:
            raise ArithmeticError("actual radial continuation is not polar-monotone")
        return Q/(radius*S),-Q/(_interval_square(radius)*S)-Q/(S*S*S)
    if kind != "flank" or rb <= abs(T):
        raise ArithmeticError("actual working-side derivative branch is unresolved")
    def sq(u):
        return rb+T*continuation.cos_bounds(k+u),rb*u+T*continuation.sin_bounds(k+u)
    def radial(u):
        S,Q = sq(u)
        return continuation.sqrt_bounds(continuation._squared_norm((S,Q)))
    upper = 2.0*(radius.upper+rb+abs(T))/rb+2.0
    if radial(I.point(0.0)).upper >= radius.lower or radial(I.point(upper)).lower <= radius.upper:
        raise ArithmeticError("finite flank curvature reaches its base singularity")
    brackets = []
    for target in (radius.lower,radius.upper):
        lo,hi = 0.0,upper
        for _ in range(64):
            mid = (lo+hi)/2.0
            if mid in (lo,hi):
                break
            bound = radial(I.point(mid))
            if bound.upper < target:
                lo = mid
            elif bound.lower > target:
                hi = mid
            else:
                break
        brackets.append((lo,hi))
    u = I(brackets[0][0],brackets[1][1])
    S,Q = sq(u)
    if u.lower <= 0 or S.lower <= 0:
        raise ArithmeticError("actual flank has unresolved polar curvature")
    dr = rb*u*S/radius
    slope = Q/(radius*S)
    derivative_u = 1.0/radius-Q*dr/(_interval_square(radius)*S)+Q*T*continuation.sin_bounds(k+u)/(radius*S*S)
    return slope,derivative_u/dr


def _root_objective_multipliers(chart,proof,direction):
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    pair = chart.pair
    cell = _geometry_cell_for_angle(proof.cell,chart.unknown_angle_coordinate)
    root_t,root_z = proof.driven_surface_root_box
    q,_,_,_,inverse,_,_,_ = _relative_surface_derivatives(
        pair,cell,proof.driven_material_phase_rad,chart.driven_stratum.segment,
        chart.driven_tooth,root_t,root_z,finite_master_extension=chart.driven_stratum.implicit_tip)
    radius = continuation.sqrt_bounds(continuation._squared_norm(q[:2]))
    slope,_ = _working_angle_derivatives(pair.driver,chart.driver_stratum.segment.kind,radius)
    er = q[0]/radius,q[1]/radius
    et = -er[1],er[0]
    gradient = tuple(slope*er[i]-direction*et[i]/radius for i in range(2))+(I.point(0),)
    world = tuple(sum(inverse[j][i]*gradient[j] for j in range(3)) for i in range(3))
    return continuation.objective_kkt_multipliers(chart,proof,world)


def chart_neighbourhood_minimum(pair, chart, proof, t, z, *,
                                direction, outside_air_mm, approach_driven_phase_rad,
                                neighbourhood):
    """A full-rectangle, whole-approach constrained local minimum.

    ROOT multipliers are held fixed per source throughout the approach.
    They multiply LOCAL-mm constraints in incident -> radial-cap -> face
    order. A Placement shoulder/cylinder constraint is valid only on the
    corresponding arm of the retained-material UNION over this WHOLE box.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    if (chart.pair is not pair or pair.driver.helix_angle_deg != 0.0
            or chart.driver_stratum.segment.kind not in ("flank", "radial")
            or direction not in (-1, 1) or direction != chart.driver_stratum.segment._side):
        raise ValueError("local minimum does not use the actual straight driver's working side")
    coordinate = chart.unknown_angle_coordinate
    refusal = neighbourhood.refusal(proof, approach_driven_phase_rad, coordinate)
    if refusal or neighbourhood.driven_surface_domain != (t, z):
        raise ValueError(refusal or "minimum rectangle differs from its bound physical neighbourhood")
    beta = approach_driven_phase_rad
    root_beta = proof.driven_material_phase_rad if coordinate == "driven_material" else proof.driven_phase_rad
    if root_beta is None or not beta.contains(root_beta):
        raise ValueError("local minimum approach omits its actual same-coordinate contact root")
    geometry_cell = _geometry_cell_for_angle(proof.cell, coordinate)
    q,qt,qtt,velocity,inverse_frame,p,dp,ddp = _relative_surface_derivatives(
        pair,geometry_cell,beta,chart.driven_stratum.segment,chart.driven_tooth,t,z,
        finite_master_extension=chart.driven_stratum.implicit_tip)
    radius = continuation.sqrt_bounds(continuation._squared_norm(q[:2]))
    slope,curvature = _working_angle_derivatives(pair.driver,chart.driver_stratum.segment.kind,radius)
    er = (q[0]/radius,q[1]/radius)
    et = (-er[1],er[0])
    gradient = tuple(slope*er[i]-direction*et[i]/radius for i in range(2))+(I.point(0.0),)
    hxy = tuple(tuple(curvature*er[i]*er[j]+slope/radius*et[i]*et[j]
                     +direction/_interval_square(radius)*(er[i]*et[j]+et[i]*er[j])
                     for j in range(2)) for i in range(2))
    hessian = [[sum(qt[i][a]*hxy[a][b]*qt[j][b] for a in range(2) for b in range(2))
                +_interval_dot(gradient,qtt[i][j]) for j in range(2)] for i in range(2)]

    # Compute the actual root scale, not a newly chosen multiplier at each
    # beta in the approach. F^-T maps LOCAL objective covectors to world.
    multipliers = _root_objective_multipliers(chart,proof,direction)
    inverse_norm = _frame_operator_norm_upper(
        continuation.frame_inverse_bounds(pair.placement.driver_frame))
    padding = (I.point(chart.geometry_error_bound_mm)
               +continuation.periodicity_displacement_bound_mm(pair,proof.cell.source_pose)).upper
    local_geometry_error = (I.point(padding)*inverse_norm).upper
    expanded_radius = radius+I(-local_geometry_error,local_geometry_error)
    expanded_slope,_ = _working_angle_derivatives(
        pair.driver,chart.driver_stratum.segment.kind,expanded_radius)
    gradient_norm = (I.point(inverse_norm)*continuation.sqrt_bounds(continuation._squared_norm((
        I.point(expanded_slope.magnitude),I.point(1)/expanded_radius.lower)))).upper
    approach = _interval_dot(gradient,velocity)
    for body,stratum in (("driver",chart.driver_stratum),("driven",chart.driven_stratum)):
        constraints = []
        for incident,_ in stratum.incident_segments:
            if incident.kind != "tip_arc" or not stratum.implicit_tip:
                raise ArithmeticError("noncanonical incident constraint has no actual local covector scale")
            constraints.append(("radial",getattr(pair,body).blank_radius_mm))
        if stratum.radial_cap_radius_mm is not None:
            if (body != "driver" or stratum.radial_cap_radius_mm != pair.placement.driver_turned_radius_mm
                    or (q[2]-local_geometry_error).lower <= pair.placement.driver_shoulder_z_mm):
                raise ArithmeticError("whole neighbourhood/approach does not lie above the shoulder cut")
            constraints.append(("radial",stratum.radial_cap_radius_mm))
        if stratum.z_fixed is not None:
            face = getattr(pair.placement,f"{body}_face_mm")
            if stratum.axial_cap_source == "driver_shoulder":
                if (body != "driver" or stratum.z_fixed != pair.placement.driver_shoulder_z_mm
                        or expanded_radius.lower <= pair.placement.driver_turned_radius_mm):
                    raise ArithmeticError("whole neighbourhood/approach is not outside the turned cylinder")
            elif stratum.axial_cap_source != "face" or stratum.z_fixed not in face:
                raise ValueError("axial multiplier does not refer to an actual face or shoulder")
            constraints.append(("axial",stratum.z_fixed))
        # A truncated zip would silently omit a real active constraint.
        for multiplier,(kind,station) in zip(multipliers[body],constraints,strict=True):
            if body == "driven":
                if kind == "radial":
                    r = continuation.sqrt_bounds(continuation._squared_norm(p[:2]))
                    numerator = _interval_dot(dp,dp)+_interval_dot(p,ddp)-_interval_square(_interval_dot(p,dp)/r)
                    hessian[0][0] += multiplier*numerator/r
                continue  # Driven local face constraints are linear, beta-independent.
            sign = -1 if kind == "axial" and station == pair.placement.driver_face_mm[0] else 1
            if kind == "axial":
                approach += multiplier*sign*velocity[2]
            else:
                approach += multiplier*_interval_dot(er,velocity[:2])
            for i in range(2):
                for j in range(2):
                    if kind == "axial":
                        constraint_hessian = sign*qtt[i][j][2]
                    else:
                        constraint_hessian = ((_interval_dot(qt[i][:2],qt[j][:2])
                                               -_interval_dot(er,qt[i][:2])*_interval_dot(er,qt[j][:2]))/radius
                                              +_interval_dot(er,qtt[i][j][:2]))
                    hessian[i][j] += multiplier*constraint_hessian
    cross = max(hessian[0][1].magnitude,hessian[1][0].magnitude)
    determinant = I.point(hessian[0][0].lower)*hessian[1][1].lower-I.point(cross)*cross
    trace = hessian[0][0]+hessian[1][1]
    lower = ((determinant/I.point(trace.upper)).lower
             if hessian[0][0].lower > 0 and determinant.lower > 0 and trace.upper > 0 else -math.inf)
    transversality = max(0.0,(direction*approach).lower)
    return continuation.ChartMinimumBound(
        chart.name,2,lower,outside_air_mm,transversality,
        lagrangian_beta_derivative=approach,objective_direction=direction,
        neighbourhood=neighbourhood,objective_gradient_magnitude_upper_per_mm=gradient_norm,
        objective_gradient_padding_mm=padding,
    )


def _patch_rectangles_outside_union(full, excluded):
    """Partition in THIS patch's coordinates; never use a neighbourhood hull."""
    cuts = [set((full[0],full[1])),set((full[2],full[3]))]
    for rectangle in excluded:
        if len(rectangle) != 4 or any(not math.isfinite(v) for v in rectangle):
            raise ValueError("physical patch excisions require finite two-coordinate rectangles")
        if rectangle[0] >= rectangle[1] or rectangle[2] >= rectangle[3]:
            raise ValueError("physical patch excision is degenerate")
        for axis,(low,high) in enumerate(((rectangle[0],rectangle[1]),(rectangle[2],rectangle[3]))):
            cuts[axis].update(v for v in (low,high) if full[2*axis] < v < full[2*axis+1])
    first,second = (sorted(values) for values in cuts)
    result = []
    for a,b in zip(first,first[1:]):
        for c,d in zip(second,second[1:]):
            if not any(x <= a <= b <= y and z <= c <= d <= w for x,y,z,w in excluded):
                result.append((a,b,c,d))
    return result


def finite_surface_patch_air(pair, cell, driven_phase_rad, patch_id, *,
                             required_air_mm, maximum_error_mm,
                             patch_parameter_domains=(), additional_geometry_error_mm=0.0,
                             max_boxes=500000):
    """Actual finite material exclusion outside bound physical patch domains.

    The existing RootAngularDomain FULL-material inverse supplies INNER and
    OUTER sets; no root-radius disk or selected point replaces the solid.
    This is a boundary-patch receipt, NOT a volume-containment certificate.
    Unresolved source/approach spread is not manufactured infeasibility.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    from diagnostics.stock_form_root_angles import RootAngularDomain
    I = continuation.Interval
    if (not math.isfinite(required_air_mm) or required_air_mm < 0
            or not math.isfinite(maximum_error_mm) or maximum_error_mm <= 0
            or type(max_boxes) is not int or max_boxes <= 0):
        raise ValueError("physical exclusion requires finite air/error and a positive box limit")
    search,motion = pose_cell_search(pair,cell,driven_phase_rad,angle_coordinate="driven_material",
                                    additional_geometry_error_mm=additional_geometry_error_mm)
    candidates = {f"{tooth}:{segment.name}":(tooth,segment)
                  for tooth in search.driven_teeth for segment in search.segments}
    if patch_id not in candidates:
        raise ValueError("exclusion names no actual physical tooth/surface/cap")
    tooth,segment = candidates[patch_id]
    cap = isinstance(segment,EndFacePatch)
    names = ("native_t","radial_fraction" if cap else "z_mm")
    full = (0.0,1.0,0.0,1.0) if cap else (0.0,1.0,*pair.placement.driven_face_mm)
    excluded = tuple(tuple(value for interval in rectangle for value in interval)
                     for rectangle in patch_parameter_domains)
    pending = _patch_rectangles_outside_union(full,excluded)
    empty = not pending
    angle_domain = (-search.pitch/2,search.pitch/2)
    inner = outer = (angle_domain,)
    domain = RootAngularDomain(pair.driver,search.gap)
    inverse_norm = max(1.0,_frame_operator_norm_upper(
        continuation.frame_inverse_bounds(pair.placement.driver_frame)))
    scale = (I.point(1)/inverse_norm).lower
    rounding = sum(I.point(_frame_operator_norm_upper(getattr(pair.placement,f"{body}_frame")))
                   *getattr(pair,body).geometry_error_bound_mm for body in ("driver","driven")).upper
    target = (I.point(required_air_mm)+rounding).upper
    if target <= required_air_mm:
        target = math.nextafter(required_air_mm,math.inf)
    local_air = (I.point(target)/scale).upper
    while (I.point(local_air)*scale).lower < target:
        local_air = math.nextafter(local_air,math.inf)
    count,terminal = 0,0
    unresolved = None
    parameter_metric = _frame_operator_norm_upper(search.placement.driven_frame)
    primitive_error = (I.point(parameter_metric)*pair.driven.geometry_error_bound_mm).upper
    largest_terminal_radius = 0.0
    def material_bound(local,numerical_radius):
        r = math.hypot(local[0],local[1])
        arithmetic = 128*np.finfo(float).eps*(1+sum(abs(float(v)) for v in local))
        radial = (I.point(numerical_radius)+search.radial_error_mm
                  +primitive_error+arithmetic+local_air).upper
        axial = (I.point(numerical_radius)+search.axial_error_mm
                 +primitive_error+arithmetic+local_air).upper
        rlo,rhi = max(0.0,(I.point(r)-radial).lower),(I.point(r)+radial).upper
        zlo,zhi = (I.point(float(local[2]))-axial).lower,(I.point(float(local[2]))+axial).upper
        p = search.placement
        if (zhi < p.driver_face_mm[0] or zlo > p.driver_face_mm[1]
                or zlo > p.driver_shoulder_z_mm and rlo > p.driver_turned_radius_mm):
            return None
        if zlo > p.driver_shoulder_z_mm:
            rhi = min(rhi,p.driver_turned_radius_mm)
        angular = math.pi if radial >= r else math.asin(radial/r)
        theta = math.atan2(local[1],local[0])+search.seed-search.phase-search.pitch/2
        return domain.offset_bounds(rlo,rhi,theta,angular+motion,root_only=False)
    while pending:
        limits = pending.pop()
        if count >= max_boxes:
            unresolved = {"reason":"finite patch material enclosure reached its box limit","limits":limits}
            break
        count += 1
        t0,t1,s0,s1 = limits
        t,s = t0/2+t1/2,s0/2+s1/2
        radius = (I.point(segment.speed_bound_mm)*(I.point(t1)-t0)/2
                  +I.point(search.second_speed(segment))*(I.point(s1)-s0)/2).upper
        if search.cap_removed(segment,t,s,radius):
            terminal += 1
            continue
        _,local = search.point(segment,tooth,t,s)
        numerical_radius = (I.point(radius)*parameter_metric).upper
        bound = material_bound(local,numerical_radius)
        if bound is None:
            terminal += 1
            largest_terminal_radius = max(largest_terminal_radius,numerical_radius)
            continue
        if any(a <= 0 <= b for a,b in bound.inner):
            inner = intersect_intervals(inner,bound.inner)
            outer = intersect_intervals(outer,bound.outer)
            terminal += 1
            largest_terminal_radius = max(largest_terminal_radius,numerical_radius)
            continue
        point_bound = material_bound(local,0.0) if search.surface_member(segment,t,s) else None
        if point_bound is not None and not any(a <= 0 <= b for a,b in point_bound.inner):
            unresolved = {
                "reason":"paid source/approach point enclosure unresolved independently of parameter refinement",
                "limits":limits,"numerical_parameter_radius_mm":numerical_radius,
                "paid_point_free_inner":point_bound.inner,"paid_point_free_outer":point_bound.outer,
            }
            break
        first = segment.speed_bound_mm*(t1-t0)
        second = search.second_speed(segment)*(s1-s0)
        axis = 0 if first >= second else 1
        low,high = limits[2*axis:2*axis+2]
        middle = low/2+high/2
        if middle in (low,high):
            unresolved = {"reason":"fixed source/approach enclosure remains unresolved at finite parameter precision",
                          "limits":limits,"free_inner":bound.inner,"free_outer":bound.outer}
            break
        left,right = list(limits),list(limits)
        left[2*axis+1],right[2*axis] = middle,middle
        pending.extend((tuple(right),tuple(left)))
    result = {"status":"PROVED" if unresolved is None else "UNKNOWN",
            "physical_no_solution":False,"native_certificate":False,
            "scope":"boundary patch against complete cutter-gapped driver material",
            "patch_id":patch_id,"patch_parameter_names":names,
            "patch_parameter_domain":((full[0],full[1]),(full[2],full[3])),
            "excluded_patch_parameter_domains":patch_parameter_domains,
            "empty_remainder":empty,"phase_cell_rad":cell.driver_phase_rad.record(),
            "same_source_pose":cell.source_pose.record(),"angle_coordinate":"driven_material",
            "approach_driven_phase_rad":driven_phase_rad.record(),
            "required_air_mm":required_air_mm,
            "air_lower_mm":(I.point(local_air)*scale).lower if unresolved is None else None,
            "additional_geometry_error_mm":additional_geometry_error_mm,
            "inverse_offset_domain_rad":angle_domain,
            "free_inner_inverse_offset_components_rad":inner if unresolved is None else (),
            "free_outer_inverse_offset_components_rad":outer if unresolved is None else (angle_domain,),
            "boxes":count,"terminal_boxes":terminal,
            "largest_terminal_parameter_radius_mm":largest_terminal_radius,
            "parameter_radius_metric_upper":parameter_metric}
    if unresolved is not None:
        result["unresolved"] = unresolved
    return result


def driven_root_material_clearance(pair, cell, driven_phase_rad, *,
                                   maximum_error_mm, required_root_air_mm,
                                   additional_geometry_error_mm=0.0):
    """Complete directed driven-ROOT material clearance, including containment.

    Straight mates use the genuine reversed root sweep. A helical mate stays
    on the driven side: its actual cutter-gapped material is radially clipped
    at an outward root bound and swept against COMPLETE straight-driver
    material. Extra working material can only refuse this sufficient proof.
    Neither route replaces the stock by a filled root-radius disk.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    result = {"proof_schema":"finite-stock-directed-root-material/1",
              "status":"UNKNOWN","physical_no_solution":False,"native_certificate":False,
              "root_owner":"driven","other_material_owner":"driver",
              "phase_cell_rad":cell.driver_phase_rad.record(),
              "same_source_pose":cell.source_pose.record(),"angle_coordinate":"driven_material",
              "approach_driven_phase_rad":driven_phase_rad.record(),
              "required_root_air_mm":required_root_air_mm,
              "source_driver_profile":profile_record(pair.driver),
              "source_driven_profile":profile_record(pair.driven),
              "source_placement":pair.placement.record()}
    try:
        if pair.driven.helix_angle_deg == 0:
            p = pair.placement
            geometry_cell = _geometry_cell_for_angle(cell,"driven_material")
            swapped = tuple((("driven_"+name[7:] if name.startswith("driver_") else "driver_"+name[7:]),value)
                            for name,value in geometry_cell.source_pose.axes)
            reverse_source = continuation.SourcePose(swapped)
            reverse_cell = continuation.PhaseCell(driven_phase_rad,reverse_source)
            reverse_placement = Placement(
                p.driven_origin_mm,p.driver_origin_mm,p.driven_frame,p.driver_frame,
                p.driven_face_mm,p.driver_face_mm,0.0,0.0,
            )
            reverse = ContactPair(pair.name+":reverse-root-material",pair.driven,pair.driver,reverse_placement)
            other_angle = cell.driver_phase_rad+p.driver_clocking_rad
            receipt = root_free_pose_cell(
                reverse,reverse_cell,other_angle,maximum_error_mm=maximum_error_mm,
                required_root_air_mm=required_root_air_mm,angle_coordinate="physical",
                additional_geometry_error_mm=additional_geometry_error_mm,
            )
            result.update({
                "method":"reversed_actual_straight_root_sweep",
                "query_driver_profile":profile_record(reverse.driver),
                "query_driven_profile":profile_record(reverse.driven),
                "query_placement":reverse_placement.record(),
                "query_driver_phase_rad":driven_phase_rad.record(),
                "query_driven_phase_rad":other_angle.record(),
                "query_source_pose":reverse_source.record(),
                "source_axis_relabel":{name:("driven_"+name[7:] if name.startswith("driver_") else "driver_"+name[7:])
                                       for name,_ in geometry_cell.source_pose.axes},
                "removed_material_clock_axis":"driven_clock_rad",
                "other_material_enclosure":"complete untrimmed finite stock; any original driver band only removes material",
            })
        else:
            profile = pair.driven
            radius = min(profile.blank_radius_mm,
                         (I.point(profile.root_radius_max_mm)+profile.geometry_error_bound_mm).upper)
            clipped = StockFormProfile(profile.teeth,profile.template,radius,
                                       profile.radial_translation_mm,profile.helix_angle_deg)
            enclosed = ContactPair(pair.name+":driven-root-material-enclosure",pair.driver,clipped,pair.placement)
            receipt = root_free_pose_cell(
                enclosed,cell,driven_phase_rad,maximum_error_mm=maximum_error_mm,
                required_root_air_mm=required_root_air_mm,angle_coordinate="driven_material",
                additional_geometry_error_mm=additional_geometry_error_mm,root_only=False,
            )
            result.update({
                "method":"actual_cutter_gapped_root_material_radial_enclosure",
                "query_driver_profile":profile_record(enclosed.driver),
                "query_driven_profile":profile_record(enclosed.driven),
                "query_placement":pair.placement.record(),
                "query_driver_phase_rad":cell.driver_phase_rad.record(),
                "query_driven_phase_rad":driven_phase_rad.record(),
                "query_source_pose":cell.source_pose.record(),
                "root_subset_enclosure":{
                    "operation":"intersect actual finite stock material with a concentric local radial cylinder",
                    "source_root_radius_upper_mm":profile.root_radius_max_mm,
                    "source_profile_geometry_error_mm":profile.geometry_error_bound_mm,
                    "radial_clip_radius_mm":radius,
                    "source_blank_radius_mm":profile.blank_radius_mm,
                    "retained_teeth":profile.teeth,"retained_helix_angle_deg":profile.helix_angle_deg,
                    "retained_face_interval_mm":list(pair.placement.driven_face_mm),
                    "scope":"all physical teeth and axial stations; cutter gaps and actual cap material retained",
                    "extra_working_material_policy":"UNKNOWN on refusal, not physical infeasibility",
                },
            })
        result["material_sweep"] = receipt
        if receipt["status"] != "PROVED":
            result["reason"] = "complete directed material/root/containment enclosure unresolved"
            return result
        air = receipt["physical_root_air_lower_bound_mm"]
        if air <= 0 or air < required_root_air_mm:
            raise ArithmeticError("directed material distance does not pay the actual root floor")
        result.update({"status":"PROVED","root_air_lower_mm":air,
                       "reason":"complete cutter-gapped material sweep with actual finite caps and containment"})
    except (ArithmeticError,ValueError) as exc:
        result["reason"] = f"directed root-material proof unresolved: {exc}"
    return result


def finite_face_family(pair, source_domain):
    """Nested actual material and common physical support for all face widths.

    This is an enclosure theorem, not a manufactured minimum-width cap:
    only side/tip surfaces inside common support, or genuinely fixed faces,
    can carry. Complete maximum material supplies exclusion/containment.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    limits = source_domain["finite_face_width_limits_mm"]
    anchors = source_domain["finite_face_anchor_fraction"]
    if set(limits) != {"driver","driven"} or set(anchors) != {"driver","driven"}:
        raise ValueError("both physical finite-face width/anchor authorities are required")
    support,material = {},{}
    for body in ("driver","driven"):
        low,high = limits[body]
        fraction = anchors[body]
        old = getattr(pair.placement,f"{body}_face_mm")
        if (any(type(v) not in (float,int) or not math.isfinite(v) for v in (low,high,fraction))
                or not 0 < low <= old[1]-old[0] <= high or not 0 <= fraction <= 1):
            raise ValueError("actual finite-face reference/width/anchor is unbound")
        if low == high:
            support[f"{body}_face_mm"] = material[f"{body}_face_mm"] = old
            continue
        anchor = old[0]+fraction*(old[1]-old[0])
        inner_low = I.point(anchor)-I.point(fraction)*low
        inner_high = I.point(anchor)+I.point(1-fraction)*low
        outer_low = I.point(anchor)-I.point(fraction)*high
        outer_high = I.point(anchor)+I.point(1-fraction)*high
        support[f"{body}_face_mm"] = (inner_low.upper,inner_high.lower)
        material[f"{body}_face_mm"] = (outer_low.lower,outer_high.upper)
    band = source_domain.get("driver_retained_band_limits_mm")
    if math.isfinite(pair.placement.driver_shoulder_z_mm):
        if not isinstance(band,dict) or set(band) != {"shoulder_z","turned_radius"}:
            raise ValueError("actual driver shoulder/turned-radius family is unbound")
        for name,field in (("shoulder_z","driver_shoulder_z_mm"),("turned_radius","driver_turned_radius_mm")):
            lo,hi = band[name]
            if (any(type(value) not in (int,float) or not math.isfinite(value) for value in (lo,hi))
                    or not 0 < lo <= getattr(pair.placement,field) <= hi):
                raise ValueError("actual retained-material band does not enclose its reference geometry")
            support[field],material[field] = lo,hi
    elif band is not None:
        raise ValueError("unbanded physical driver cannot acquire a synthetic retained band")
    support_pair = replace(pair,placement=replace(pair.placement,**support))
    material_pair = replace(pair,placement=replace(pair.placement,**material))
    record = {
        "method":"nested actual finite-stock material with common physical side/tip support",
        "reference_placement":pair.placement.record(),
        "support_placement":support_pair.placement.record(),
        "material_placement":material_pair.placement.record(),
        "source_face_width_limits_mm":limits,"source_face_anchor_fraction":anchors,
        "source_driver_retained_band_limits_mm":band,
        "moving_band_cap_carrying":False,
        "moving_face_cap_carrying":False,"native_certificate":False,
    }
    return support_pair,material_pair,record


def _common_physical_face_chart(chart,material_pair):
    supported_placement = chart.pair.placement
    stratum = chart.driver_stratum
    if (stratum.axial_cap_source == "driver_shoulder"
            and supported_placement.driver_shoulder_z_mm != material_pair.placement.driver_shoulder_z_mm):
        return False
    if (stratum.radial_cap_radius_mm is not None
            and supported_placement.driver_turned_radius_mm != material_pair.placement.driver_turned_radius_mm):
        return False
    for body,stratum in (("driver",chart.driver_stratum),("driven",chart.driven_stratum)):
        if stratum.z_fixed is None or stratum.axial_cap_source != "face":
            continue
        supported = getattr(chart.pair.placement,f"{body}_face_mm")
        material = getattr(material_pair.placement,f"{body}_face_mm")
        if stratum.z_fixed not in supported:
            return False
        if material[supported.index(stratum.z_fixed)] != stratum.z_fixed:
            return False
    return True


def patch_boundary_separation(chart,proof,neighbourhood,patch_id,patch_domain,*,outside_air_mm):
    """One-sided derivative on THIS incident-side or radial-fan cap domain."""
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    pair = chart.pair
    names,_ = continuation.physical_patch_root_coordinates(proof,patch_id)
    refusal = continuation.patch_domain_refusal(proof,patch_id,names,patch_domain)
    if refusal:
        raise ArithmeticError(refusal)
    stratum = chart.driven_stratum
    suffix = next((v for v in (":end_face:-1",":end_face:+1") if patch_id.endswith(v)),"")
    side = patch_id[:-len(suffix)] if suffix else patch_id
    segments = {f"{stratum.tooth}:{stratum.segment.name}":(stratum.segment,None)}
    segments.update({f"{stratum.tooth}:{segment.name}":(segment,endpoint)
                     for segment,endpoint in stratum.incident_segments})
    segment,endpoint = segments[side]
    t,second = patch_domain
    geometry_cell = _geometry_cell_for_angle(proof.cell,"driven_material")
    if suffix:
        sign = 0 if suffix.endswith("-1") else 1
        z = I.point(pair.placement.driven_face_mm[sign])
        if stratum.z_fixed != z.midpoint:
            raise ArithmeticError("cap derivative is not at the actual supported face")
        rho = second
    else:
        if endpoint is None:
            raise ValueError("a main side neighbourhood uses its minimum, not a boundary exception")
        z,rho = second,None
    q,first,_,_,_,_,_,_ = _relative_surface_derivatives(
        pair,geometry_cell,neighbourhood.approach_driven_phase_rad,segment,stratum.tooth,t,z,
        finite_master_extension=segment == stratum.segment and stratum.implicit_tip,
        radial_fraction=rho)
    tangent = tuple(-value for value in first[1]) if suffix else tuple(
        (1 if endpoint == 0 else -1)*value for value in first[0])
    radius = continuation.sqrt_bounds(continuation._squared_norm(q[:2]))
    direction = chart.driver_stratum.segment._side
    slope,_ = _working_angle_derivatives(pair.driver,chart.driver_stratum.segment.kind,radius)
    er,et = (q[0]/radius,q[1]/radius),(-q[1]/radius,q[0]/radius)
    gradient = list(slope*er[i]-direction*et[i]/radius for i in range(2))+[I.point(0)]
    active = []
    for incident,_ in chart.driver_stratum.incident_segments:
        if incident.kind != "tip_arc" or not chart.driver_stratum.implicit_tip:
            raise ArithmeticError("incident boundary has no actual native radial constraint")
        active.append(("radial",pair.driver.blank_radius_mm))
    cap = chart.driver_stratum.radial_cap_radius_mm
    padding = (I.point(chart.geometry_error_bound_mm)
               +continuation.periodicity_displacement_bound_mm(pair,proof.cell.source_pose)).upper
    padding = (I.point(padding)*_frame_operator_norm_upper(
        continuation.frame_inverse_bounds(pair.placement.driver_frame))).upper
    if cap is not None:
        if (q[2]-padding).lower <= pair.placement.driver_shoulder_z_mm:
            raise ArithmeticError("incident/cap neighbourhood crosses the retained-material union")
        active.append(("radial",cap))
    driver_face = chart.driver_stratum.z_fixed
    if driver_face is not None:
        if (chart.driver_stratum.axial_cap_source == "driver_shoulder"
                and (radius-padding).lower <= pair.placement.driver_turned_radius_mm):
            raise ArithmeticError("incident/cap neighbourhood reaches the reentrant shoulder/cylinder join")
        active.append(("axial",driver_face))
    multipliers = _root_objective_multipliers(chart,proof,direction)["driver"]
    for multiplier,(kind,station) in zip(multipliers,active,strict=True):
        if kind == "radial":
            for index in range(2):
                gradient[index] += multiplier*er[index]
        else:
            sign = -1 if station == pair.placement.driver_face_mm[0] else 1
            gradient[2] += multiplier*sign
    inward = _interval_dot(gradient,tangent)
    if inward.lower <= 0:
        raise ArithmeticError("actual whole-patch one-sided separating derivative remains unresolved")
    return continuation.BoundarySeparation(
        patch_id,chart.name,inward.lower,outside_air_mm,neighbourhood,names,patch_domain)


def _source_centre_pair(pair,cell,beta):
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    centre = _geometry_cell_for_angle(cell.centre(),"driven_material")
    values = dict(centre.source_pose.axes)
    poses = {body:continuation.body_pose_bounds(pair,centre.source_pose,centre.driver_phase_rad,
                                              I.point(beta),body=body) for body in ("driver","driven")}
    fields = {}
    for body,pose in poses.items():
        fields[f"{body}_origin_mm"] = tuple(value.midpoint for value in pose.origin_mm)
        fields[f"{body}_frame"] = np.array([[value.midpoint for value in row] for row in pose.frame])
    fields["driver_clocking_rad"] = pair.placement.driver_clocking_rad+values.get("driver_clock_rad",I.point(0)).midpoint
    return replace(pair,placement=replace(pair.placement,**fields))


def _polish_stock_chart(chart,cell):
    """Numerical initialization, then a REAL uniform Krawczyk root enclosure.

    This is intentionally not a first-contact/root-air certificate. The
    complete material proofs below must precede public branch admission.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    centre = cell.centre()
    initial = np.array([value.midpoint for value in chart.unknown_box])
    def evaluated(values):
        return chart.evaluate(centre,tuple(I.point(float(value)) for value in values))
    def residual(values):
        return np.array([value.midpoint for value in evaluated(values).residual])
    def jacobian(values):
        return np.array([[value.midpoint for value in row] for row in evaluated(values).jacobian])
    solved = root(residual,initial,jac=jacobian,tol=1e-11)
    if not solved.success or not np.all(np.isfinite(solved.x)):
        raise ArithmeticError(f"supported common-normal numerical initialization failed: {solved.message}")
    at_point = evaluated(solved.x)
    jac = np.array([[value.midpoint for value in row] for row in at_point.jacobian])
    parameters = np.array([[value.midpoint for value in row] for row in at_point.parameter_jacobian])
    sensitivities = np.linalg.solve(jac,-parameters)
    deviations = np.array([max(abs(value.lower-value.midpoint),abs(value.upper-value.midpoint))
                           for value in cell.parameter_bounds])
    motion = np.abs(sensitivities)@deviations
    baseline = np.array([(value.upper-value.lower)/2 for value in chart.unknown_box])
    reason = "no uniform initial box"
    for factor in (1.0,2.0,4.0):
        radii = factor*(baseline+motion)
        box = tuple(I(math.nextafter(float(value-radius),-math.inf),
                      math.nextafter(float(value+radius),math.inf))
                    for value,radius in zip(solved.x,radii))
        candidate = replace(chart,unknown_box=box)
        enclosure,gradient,contraction,reason = continuation._krawczyk(candidate.evaluate,cell,box)
        if enclosure is None:
            continue
        support = candidate.evaluate(cell,enclosure)
        if any(value.lower <= 0 for _,value in support.margins):
            reason = "whole-source finite stratum/normal-cone support is unresolved"
            continue
        a,b = support.driver_moment,support.driven_moment
        if a.lower <= 0 <= a.upper or b.lower <= 0 <= b.upper or (a*b).upper >= 0:
            reason = "whole-source opposing nonzero normal moments are unresolved"
            continue
        return candidate,tuple(float(v) for v in solved.x),enclosure
    raise ArithmeticError(reason)


def _supported_normal_candidates(pair,material_pair,cell,closing_sense,maximum_error_mm):
    """All physical teeth supply seeds; only exhaustive exclusions can finish."""
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    phi = cell.driver_phase_rad.midpoint
    ratio = pair.driver.teeth/pair.driven.teeth
    seed_beta = pair.placement.driven_clocking_rad-ratio*phi
    direction = -closing_sense
    found,failures = {},[]
    # Cull numerical seeds, never the exhaustive physical proof inventory.
    half_pitch = pair.driven.angular_pitch_rad/2
    seed_domain = I(seed_beta-half_pitch,seed_beta+half_pitch)
    seed_search,_ = pose_cell_search(pair,cell,seed_domain,angle_coordinate="driven_material")
    seed_metric = _frame_operator_norm_upper(seed_search.placement.driven_frame)
    station = sum(pair.placement.driven_face_mm)/2
    half_face = (pair.placement.driven_face_mm[1]-pair.placement.driven_face_mm[0])/2
    geometry_centre = _geometry_cell_for_angle(cell.centre(),"driven_material")
    for tooth in range(pair.driven.teeth):
        for segment in pair.driven.external_boundary_segments():
            if segment.kind not in ("flank","radial","tip_arc"):
                continue
            _,local = seed_search.point(segment,tooth,.5,station)
            extent = seed_metric*(segment.speed_bound_mm/2+seed_search.second_speed(segment)*half_face)
            radial = extent+seed_search.radial_error_mm+pair.driven.geometry_error_bound_mm
            axial = extent+seed_search.axial_error_mm+pair.driven.geometry_error_bound_mm
            if (math.hypot(local[0],local[1])-radial > pair.driver.blank_radius_mm
                    or local[2]+axial < pair.placement.driver_face_mm[0]
                    or local[2]-axial > pair.placement.driver_face_mm[1]):
                continue
            beta,initial = seed_beta,None
            try:
                contact,settled = None,False
                for _ in range(16):
                    centre_pair = _source_centre_pair(pair,cell,beta)
                    search = ContactSearch(centre_pair,phi,driven_phase_rad=beta)
                    fitted = search.optimise(segment,tooth,(0.0,1.0,*pair.placement.driven_face_mm),
                                             direction,initial=initial)
                    if fitted is None:
                        break
                    _,contact = fitted
                    initial = [contact.parameter,contact.station_mm]
                    q,_,_,velocity,_,_,_,_ = _relative_surface_derivatives(
                        pair,geometry_centre,I.point(beta),segment,tooth,
                        I.point(contact.parameter),I.point(contact.station_mm))
                    radius = math.hypot(q[0].midpoint,q[1].midpoint)
                    er = np.array([q[0].midpoint/radius,q[1].midpoint/radius,0.0])
                    et = np.array([-er[1],er[0],0.0])
                    gradient = search.gap.exact_slope(radius)*er-direction*et/radius
                    derivative = direction*float(gradient@np.array([value.midpoint for value in velocity]))
                    if not math.isfinite(derivative) or derivative == 0:
                        break
                    correction = -contact.phase_offset_rad/derivative
                    if abs(correction)*pair.driven.pitch_radius_mm <= maximum_error_mm/32:
                        beta += correction
                        centre_pair = _source_centre_pair(pair,cell,beta)
                        search = ContactSearch(centre_pair,phi,driven_phase_rad=beta)
                        fitted = search.optimise(segment,tooth,(0.0,1.0,*pair.placement.driven_face_mm),
                                                 direction,initial=initial)
                        contact = fitted[1] if fitted is not None else None
                        settled = contact is not None
                        break
                    beta += max(-pair.driven.angular_pitch_rad/4,min(pair.driven.angular_pitch_rad/4,correction))
                    if not seed_domain.contains(I.point(beta)):
                        break
                if not settled or contact is None or not grounded_contact(contact):
                    continue
                for seed in continuation.chart_candidates(centre_pair,contact,phi,beta):
                    candidate = replace(seed,pair=pair)
                    if candidate.driver_stratum.segment._side != direction or not _common_physical_face_chart(candidate,material_pair):
                        continue
                    try:
                        chart,point,enclosure = _polish_stock_chart(candidate,cell)
                    except (ArithmeticError,ValueError,np.linalg.LinAlgError) as exc:
                        failures.append({"chart":candidate.name,"reason":str(exc)})
                        continue
                    old = found.get(chart.name)
                    if old is not None and not all(a.intersection(b) is not None for a,b in zip(old[2],enclosure)):
                        raise ArithmeticError("distinct roots on one physical stratum require separate global exclusion domains")
                    found[chart.name] = (chart,point,enclosure)
            except (ArithmeticError,ValueError,np.linalg.LinAlgError) as exc:
                failures.append({"physical_tooth":tooth,"segment":segment.name,"reason":str(exc)})
    return tuple(found.values()),failures


class ContinuousContactRefusal(ValueError):
    """An unresolved numerical enclosure, never a manufacturing no-solution."""

    def __init__(self,reason,evidence):
        super().__init__(reason)
        self.evidence = evidence


@dataclass(frozen=True)
class _ContactCell:
    cell: continuation.PhaseCell
    charts: tuple
    proofs: tuple
    numerical_points: tuple
    cover: continuation.FirstContactCover
    root_proof: dict
    driven_root_material_proof: dict
    surface_exclusions: tuple
    free_reference_exclusions: tuple

    def record(self):
        return {
            "proof_schema":"finite-stock-first-contact-cell/1","status":"PROVED","native_certificate":False,
            "phase_cell_rad":self.cell.driver_phase_rad.record(),
            "same_source_pose":self.cell.source_pose.record(),
            "branch_proofs":[proof.record() for proof in self.proofs],
            "first_contact_cover":self.cover.record(),
            "root_proof":self.root_proof,
            "driven_root_material_proof":self.driven_root_material_proof,
            "surface_exclusion_receipts":list(self.surface_exclusions),
            "free_reference_exclusion_receipts":list(self.free_reference_exclusions),
            "numerical_initializations":{name:list(point) for name,point in self.numerical_points},
        }


def _branch_neighbourhood(chart,proof,material_pair,approach,*,length_mm):
    """Bound each actual patch in its OWN native coordinates."""
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    stratum = chart.driven_stratum
    root_t,root_z = proof.driven_surface_root_box
    dt = max(root_t.upper-root_t.lower,length_mm/stratum.segment.speed_bound_mm)
    dz = max(root_z.upper-root_z.lower,length_mm)
    t = root_t+I(-dt,dt)
    if not stratum.implicit_tip:
        t = t.intersection(I(0,1))
    z = (root_z+I(-dz,dz)).intersection(I(*material_pair.placement.driven_face_mm))
    if t is None or z is None or t.lower == t.upper or z.lower == z.upper:
        raise ArithmeticError("actual local material rectangle is degenerate")
    neighbourhood = continuation.ProofNeighbourhood(
        proof.cell,chart.unknown_box,approach,(t,z),"driven_material")
    main = f"{stratum.tooth}:{stratum.segment.name}"
    domains = {main:(("native_t","z_mm"),(t,z))}
    for segment,endpoint in stratum.incident_segments:
        width = min(1.0,max(length_mm,dt*stratum.segment.speed_bound_mm)/segment.speed_bound_mm)
        incident_t = I(0,width) if endpoint == 0 else I(1-width,1)
        domains[f"{stratum.tooth}:{segment.name}"] = (("native_t","z_mm"),(incident_t,z))
    if stratum.z_fixed is not None:
        face = material_pair.placement.driven_face_mm
        if stratum.z_fixed not in face:
            raise ArithmeticError("moving/artificial support face cannot supply a material cap")
        suffix = ":end_face:-1" if stratum.z_fixed == face[0] else ":end_face:+1"
        depth = min(1.0,max(length_mm,dt*stratum.segment.speed_bound_mm,dz)/chart.pair.driven.blank_radius_mm)
        for patch,(_,rectangle) in tuple(domains.items()):
            domains[patch+suffix] = (("native_t","radial_fraction"),(rectangle[0],I(1-depth,1)))
    return neighbourhood,domains


def _reference_air(material_pair,cell,reference,*,maximum_error_mm,periodic_padding_mm):
    inventory,_,_ = _physical_surface_inventory(material_pair)
    receipts = []
    for patch in inventory:
        receipt = finite_surface_patch_air(
            material_pair,cell,reference,patch,required_air_mm=0.0,
            maximum_error_mm=maximum_error_mm,additional_geometry_error_mm=periodic_padding_mm)
        receipts.append(receipt)
        if receipt["status"] != "PROVED":
            return None,tuple(receipts)
    # The two directed material/containment proofs are still REQUIRED before
    # this boundary clearance becomes an actual free-volume anchor.
    return min(receipt["air_lower_mm"] for receipt in receipts),tuple(receipts)


def _prove_contact_side(pair,material_pair,cell,candidates,reference,reference_air,
                        reference_receipts,source_domain,*,closing_sense,
                        maximum_error_mm,maximum_jump_mm,periodic_padding_mm):
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    contenders = []
    for chart,point,enclosure in candidates:
        beta = enclosure[chart.offset_index]
        if (closing_sense == 1 and beta.lower > reference.upper
                or closing_sense == -1 and beta.upper < reference.lower):
            contenders.append((chart,point,enclosure))
    if not contenders:
        raise ContinuousContactRefusal("no uniformly supported root beyond the actual free reference",
                                      {"phase_cell_rad":cell.driver_phase_rad.record(),"closing_sense":closing_sense})
    earliest_upper = min((closing_sense*entry[2][entry[0].offset_index]).upper for entry in contenders)
    retain_band = (I.point(maximum_jump_mm+maximum_error_mm)/pair.driven.pitch_radius_mm).upper
    contenders = [entry for entry in contenders
                  if (closing_sense*entry[2][entry[0].offset_index]).lower <= earliest_upper+retain_band]
    beta_hull = I(min([reference.lower]+[entry[2][entry[0].offset_index].lower for entry in contenders]),
                  max([reference.upper]+[entry[2][entry[0].offset_index].upper for entry in contenders]))
    pad = (I.point(maximum_error_mm)/pair.driven.pitch_radius_mm).upper
    approach = beta_hull+I(-pad,pad)
    floors = source_domain["root_air_requirements_mm"]
    root = root_free_pose_cell(
        material_pair,cell,approach,maximum_error_mm=maximum_error_mm,
        required_root_air_mm=floors["driver"],angle_coordinate="driven_material",
        additional_geometry_error_mm=periodic_padding_mm)
    reverse = driven_root_material_clearance(
        material_pair,cell,approach,maximum_error_mm=maximum_error_mm,
        required_root_air_mm=floors["driven"],additional_geometry_error_mm=periodic_padding_mm)
    if root["status"] != "PROVED" or reverse["status"] != "PROVED":
        raise ContinuousContactRefusal("complete directed root MATERIAL/containment is unresolved",
                                      {"root_proof":root,"driven_root_material_proof":reverse})
    components = tuple(I(*value) for value in root["root_free_driven_components_rad"])
    charts = tuple(entry[0] for entry in contenders)
    proofs = tuple(continuation.prove_branch_cell(
        chart,cell,root_free_driven_components_rad=components,root_free_coordinate="driven_material")
        for chart in charts)
    if any(proof.status != "PROVED" for proof in proofs):
        raise ContinuousContactRefusal("uniform supported common-normal branch inclusion is unresolved",
                                      {"branch_proofs":[proof.record() for proof in proofs]})
    inventory,roots,noncarrying = _physical_surface_inventory(material_pair)
    axes = dict(cell.source_pose.axes)
    eccentricity = continuation.sqrt_bounds(continuation._squared_norm(tuple(
        axes.get(f"driven_ecc_{axis}_mm",I.point(0)) for axis in ("x","y")))).upper
    speed = (I.point(_frame_operator_norm_upper(material_pair.placement.driven_frame))
             *(I.point(material_pair.driven.blank_radius_mm)+eccentricity)).upper
    backlash = (I.point(2)*reference_air*pair.driven.pitch_radius_mm/speed).lower
    last_failure = {}
    # Grow the PROVED local convex regions, not the unshrinkable source balls
    # or a box budget. Every accepted enlargement is re-proved over its full
    # rectangle x approach and all source coordinates.
    for scale in (1,2,4,8,16,32,64):
        neighbourhoods,patches = {},{}
        for chart,proof in zip(charts,proofs):
            neighbourhood,domains = _branch_neighbourhood(
                chart,proof,material_pair,approach,length_mm=16*maximum_error_mm*scale)
            neighbourhoods[chart.name] = neighbourhood
            patches[chart.name] = domains
        owners = {patch:tuple(chart.name for chart in charts if patch in patches[chart.name])
                  for patch in inventory}
        receipts,air = [],{}
        for patch in inventory:
            domains = tuple(tuple(value.record() for value in patches[name][patch][1])
                            for name in owners[patch])
            receipt = finite_surface_patch_air(
                material_pair,cell,approach,patch,
                required_air_mm=floors["driven"] if patch in roots else 0.0,
                maximum_error_mm=maximum_error_mm,patch_parameter_domains=domains,
                additional_geometry_error_mm=periodic_padding_mm)
            receipts.append(receipt)
            if receipt["status"] != "PROVED":
                last_failure = {"scale":scale,"surface_exclusion":receipt}
                break
            air[patch] = I.point(receipt["air_lower_mm"])
        else:
            minima,boundaries = [],[]
            try:
                for chart,proof in zip(charts,proofs):
                    neighbourhood = neighbourhoods[chart.name]
                    outside = I.point(min(air[patch].lower for patch in patches[chart.name]))
                    minimum = chart_neighbourhood_minimum(
                        pair,chart,proof,*neighbourhood.driven_surface_domain,
                        direction=-closing_sense,outside_air_mm=outside,
                        approach_driven_phase_rad=approach,neighbourhood=neighbourhood)
                    refusal = minimum.refusal()
                    if refusal:
                        raise ArithmeticError(refusal)
                    if continuation.branch_geometry_error_rad(
                            proof,minimum,additional_geometry_error_mm=periodic_padding_mm) > pad:
                        raise ArithmeticError("actual geometry payment exceeds the retained loaded-approach padding")
                    minima.append(minimum)
                    main = f"{chart.driven_tooth}:{chart.driven_stratum.segment.name}"
                    for patch,(_,rectangle) in patches[chart.name].items():
                        if patch != main:
                            boundaries.append(patch_boundary_separation(
                                chart,proof,neighbourhood,patch,rectangle,outside_air_mm=air[patch]))
                remainders = tuple(continuation.PatchRemainderBound(
                    patch,names,air[patch],tuple((name,neighbourhoods[name]) for name in names),
                    patches[names[0]][patch][0],tuple((name,patches[name][patch][1]) for name in names))
                    for patch,names in owners.items() if len(names) > 1)
                cover = continuation.FirstContactCover(
                    cell,components,backlash,approach,inventory,
                    tuple((chart.name,tuple(patches[chart.name])) for chart in charts),
                    tuple((patch,air[patch]) for patch in inventory if not owners[patch]),
                    noncarrying,floors["driven"],tuple(minima),roots,tuple(boundaries),remainders,
                    reference,I.point(reference_air),closing_sense,"driven_material",
                    additional_geometry_error_mm=periodic_padding_mm)
                refusal = cover.refusal(proofs)
                if refusal:
                    raise ArithmeticError(refusal)
                return _ContactCell(
                    cell,charts,proofs,tuple((chart.name,point) for chart,point,_ in contenders),
                    cover,root,reverse,tuple(receipts),reference_receipts)
            except (ArithmeticError,ValueError) as exc:
                last_failure = {"scale":scale,"minimum_or_boundary_refusal":str(exc)}
    raise ContinuousContactRefusal("actual finite-surface first-contact exclusion is unresolved",
                                  {"phase_cell_rad":cell.driver_phase_rad.record(),
                                   "closing_sense":closing_sense,**last_failure})


def _contact_cell_pair(pair,material_pair,cell,source_domain,*,maximum_error_mm,maximum_jump_mm):
    """Both physical closing directions share one independently proved free pose.

    Choosing a clearance anchor is NOT a manufactured datum change: all beta
    roots and TE retain the caller's original physical axes and index zeros.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    candidates,seed_failures = {},{}
    for name,sense in (("lower",-1),("upper",1)):
        candidates[name],seed_failures[name] = _supported_normal_candidates(
            pair,material_pair,cell,sense,maximum_error_mm)
    choices = set()
    for a in candidates["lower"]:
        lower = a[2][a[0].offset_index]
        for b in candidates["upper"]:
            upper = b[2][b[0].offset_index]
            if lower.upper < upper.lower:
                choices.add(lower.upper/2+upper.lower/2)
    nominal = pair.placement.driven_clocking_rad-cell.driver_phase_rad.midpoint*pair.driver.teeth/pair.driven.teeth
    periodic_padding = continuation.periodicity_displacement_bound_mm(material_pair,cell.source_pose)
    refusals = []
    for beta in sorted(choices,key=lambda value:abs(value-nominal)):
        reference = I.point(beta)
        air,receipts = _reference_air(
            material_pair,cell,reference,maximum_error_mm=maximum_error_mm,
            periodic_padding_mm=periodic_padding)
        if air is None:
            refusals.append({"reference_driven_phase_rad":reference.record(),
                             "surface_exclusion":receipts[-1]})
            continue
        try:
            return {
                name:_prove_contact_side(
                    pair,material_pair,cell,candidates[name],reference,air,receipts,source_domain,
                    closing_sense=sense,maximum_error_mm=maximum_error_mm,
                    maximum_jump_mm=maximum_jump_mm,periodic_padding_mm=periodic_padding)
                for name,sense in (("lower",-1),("upper",1))}
        except ContinuousContactRefusal as exc:
            refusals.append({"reference_driven_phase_rad":reference.record(),
                             "reason":str(exc),"evidence":exc.evidence})
    raise ContinuousContactRefusal(
        "no complete common-source first-contact pair was proved",
        {"phase_cell_rad":cell.driver_phase_rad.record(),"same_source_pose":cell.source_pose.record(),
         "numerical_seed_refusals":seed_failures,"free_reference_attempts":refusals,
         "supported_candidate_counts":{name:len(value) for name,value in candidates.items()}})


def _uniform_first_charts(item):
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    minima = {value.chart_name:value for value in item.cover.chart_minimum_bounds}
    result = set()
    for selected in item.proofs:
        for other in item.proofs:
            if other.chart_name == selected.chart_name:
                continue
            delta = item.cover.closing_driven_sense*continuation.difference_from_branch_proofs(selected,other)
            error = (I.point(continuation.branch_geometry_error_rad(selected,minima[selected.chart_name],
                      additional_geometry_error_mm=item.cover.additional_geometry_error_mm))
                     +continuation.branch_geometry_error_rad(other,minima[other.chart_name],
                      additional_geometry_error_mm=item.cover.additional_geometry_error_mm))
            if (delta-error).lower < 0:
                break
        else:
            result.add(selected.chart_name)
    return frozenset(result)


def _contact_topology(item,maximum_jump_mm):
    from diagnostics import stock_form_contact_continuation as continuation
    first = _uniform_first_charts(item)
    if first:
        return (first,first),None
    failures = []
    for a in item.charts:
        for b in item.charts:
            if a.name == b.name:
                continue
            proof = continuation.prove_paid_handover(
                a,b,item.cell,item.cover,driven_pitch_radius_mm=a.pair.driven.pitch_radius_mm,
                maximum_jump_mm=maximum_jump_mm,driven_sense=item.cover.closing_driven_sense,
                first_contact_branch_proofs=item.proofs)
            if proof["status"] == "PROVED":
                return (frozenset((a.name,)),frozenset((b.name,))),proof
            failures.append(proof)
    raise ContinuousContactRefusal("possible first-root exchange lacks a paid same-source continuous bracket",
                                  {"phase_cell_rad":item.cell.driver_phase_rad.record(),
                                   "closing_sense":item.cover.closing_driven_sense,"attempts":failures})


def _endpoint_root(item,name,phase):
    from diagnostics import stock_form_contact_continuation as continuation
    chart = next(chart for chart in item.charts if chart.name == name)
    cell = continuation.PhaseCell(continuation.Interval.point(phase),item.cell.source_pose)
    proof = continuation.prove_branch_cell(
        chart,cell,root_free_driven_components_rad=item.cover.root_free_driven_components_rad,
        root_free_coordinate=item.cover.angle_coordinate)
    if proof.status != "PROVED":
        raise ContinuousContactRefusal("actual common-source endpoint root is unresolved",proof.record())
    return proof


def _strictly_contains_root(domain,root):
    return len(domain) == len(root) and all(a.lower < b.lower <= b.upper < a.upper for a,b in zip(domain,root))


def _boundary_continuation(left,right,left_first,right_first,index):
    phase = left.cell.driver_phase_rad.upper
    if phase != right.cell.driver_phase_rad.lower or left.cell.source_pose != right.cell.source_pose:
        raise ValueError("continuation boundary must have one identical physical phase/source")
    for name in sorted(left_first & right_first):
        a,b = _endpoint_root(left,name,phase),_endpoint_root(right,name,phase)
        if a.physical_strata != b.physical_strata:
            continue
        if (_strictly_contains_root(a.unknown_domain,b.root_box)
                or _strictly_contains_root(b.unknown_domain,a.root_box)):
            return {"left_cell_index":index,"right_cell_index":index+1,"phase_rad":phase,"chart":name,
                    "left_branch_proof":a.record(),"right_branch_proof":b.record()}
    raise ContinuousContactRefusal(
        "adjacent first-contact branches have no common-boundary root uniqueness proof",
        {"phase_rad":phase,"left_first_charts":sorted(left_first),"right_first_charts":sorted(right_first)})


def _row_branch_spans(items,boundaries,material_pair):
    """Continuous INNER images of one actually first physical contact branch."""
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    first_sets = tuple(_uniform_first_charts(item) for item in items)
    spans,intervals = [],[]
    for name in sorted(set().union(*first_sets)):
        index = 0
        while index < len(items):
            if name not in first_sets[index]:
                index += 1
                continue
            start = end = index
            while (end+1 < len(items) and name in first_sets[end+1]
                   and boundaries[end]["chart"] == name):
                end += 1
            lo,hi = items[start].cell.driver_phase_rad.lower,items[end].cell.driver_phase_rad.upper
            left,right = _endpoint_root(items[start],name,lo),_endpoint_root(items[end],name,hi)
            a,b = left.driven_surface_root_box[1],right.driven_surface_root_box[1]
            inner = ((a.upper,b.lower) if a.upper < b.lower else
                     (b.upper,a.lower) if b.upper < a.lower else None)
            if inner is not None:
                intervals.append(inner)
                spans.append({"chart":name,"first_cell_index":start,"last_cell_index":end,
                              "phase_endpoints_rad":[lo,hi],"left_branch_proof":left.record(),
                              "right_branch_proof":right.record(),"inner_station_interval_mm":list(inner)})
            index = end+1
    merged = merge_intervals(intervals)
    width = sum((I.point(hi)-lo for lo,hi in merged),I.point(0))
    face = material_pair.placement.driven_face_mm
    fraction = (width/(I.point(face[1])-face[0])).lower
    return spans,merged,max(0.0,fraction)


def _actual_periodic_seam(pair,material_pair,items,source_domain,*,maximum_error_mm,maximum_jump_mm):
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    start,end = items[0],items[-1]
    bounds = []
    for item,phase,shift in ((start,0.0,-pair.driven.angular_pitch_rad),
                             (end,pair.driver.angular_pitch_rad,0.0)):
        for chart in item.charts:
            bounds.append(_endpoint_root(item,chart.name,phase).driven_material_phase_rad+shift)
    domain = I(min(value.lower for value in bounds),max(value.upper for value in bounds))
    # The end approach includes a genuine clear anchor as well as every mapped
    # source-relabelled root. Retain it in both complete material sweeps.
    domain = I(min(domain.lower,end.cover.approach_driven_phase_rad.lower),
               max(domain.upper,end.cover.approach_driven_phase_rad.upper))
    cell = continuation.PhaseCell(I.point(pair.driver.angular_pitch_rad),start.cell.source_pose)
    padding = continuation.periodicity_displacement_bound_mm(material_pair,cell.source_pose)
    floors = source_domain["root_air_requirements_mm"]
    root = root_free_pose_cell(
        material_pair,cell,domain,maximum_error_mm=maximum_error_mm,
        required_root_air_mm=floors["driver"],angle_coordinate="driven_material",
        additional_geometry_error_mm=padding)
    reverse = driven_root_material_clearance(
        material_pair,cell,domain,maximum_error_mm=maximum_error_mm,
        required_root_air_mm=floors["driven"],additional_geometry_error_mm=padding)
    proof = continuation.prove_periodic_seam(
        start.charts,start.cell,start.cover,end.charts,end.cell,end.cover,
        start_branch_proofs=start.proofs,end_branch_proofs=end.proofs,
        source_eccentricity_disks=source_domain["source_eccentricity_disks"],
        root_receipt=root,driven_root_material_receipt=reverse,
        root_air_requirements_mm=floors,driven_pitch_radius_mm=pair.driven.pitch_radius_mm,
        maximum_jump_mm=maximum_jump_mm)
    if proof["status"] != "PROVED":
        raise ContinuousContactRefusal("actual whole-period physical source-relabelled seam is unresolved",proof)
    return proof


def _continuous_side(pair,material_pair,items,source_domain,*,maximum_error_mm,maximum_jump_mm):
    from diagnostics import stock_form_contact_continuation as continuation
    topology = [_contact_topology(item,maximum_jump_mm) for item in items]
    boundaries = [_boundary_continuation(
        left,right,topology[index][0][1],topology[index+1][0][0],index)
        for index,(left,right) in enumerate(zip(items,items[1:]))]
    coverage = continuation.retained_phase_coverage(
        tuple((item.cell,item.proofs,item.cover) for item in items),
        driver_pitch_rad=pair.driver.angular_pitch_rad,
        driven_pitch_radius_mm=pair.driven.pitch_radius_mm,maximum_jump_mm=maximum_jump_mm)
    if coverage["status"] != "PROVED":
        raise ContinuousContactRefusal("continuous same-source supported-tooth coverage is unresolved",coverage)
    rows,intervals,fraction = _row_branch_spans(items,boundaries,material_pair)
    seam = _actual_periodic_seam(
        pair,material_pair,items,source_domain,maximum_error_mm=maximum_error_mm,maximum_jump_mm=maximum_jump_mm)
    return {
        "proof_schema":"finite-stock-continuous-envelope/1","status":"PROVED","native_certificate":False,
        "same_source_pose":items[0].cell.source_pose.record(),
        "phase_domain_rad":[0.0,pair.driver.angular_pitch_rad],
        "closing_driven_sense":items[0].cover.closing_driven_sense,
        "phase_cells":[{**item.record(),**carrier} for item,carrier in zip(items,coverage["carrier_cells"])],
        "stock_form_coverage_lower":coverage["stock_form_coverage_lower"],
        "uncovered_phase_rad":coverage["uncovered_phase_rad"],
        "coverage_definition":coverage["coverage_definition"],
        "boundary_continuations":boundaries,
        "row_branch_spans":rows,"row_available_intervals_mm":[list(value) for value in intervals],
        "row_available_fraction_lower":fraction,
        "handovers":[proof for _,proof in topology if proof is not None],
        "periodic_seam":seam,
    }


def _contact_partition(pair,material_pair,source_domain,pose,*,phases,maximum_error_mm,maximum_jump_mm):
    """Refine phase error only after a fixed-phase whole-source proof succeeds.

    A source-domain refusal is not repaired by indefinitely splitting phase.
    A first-root exchange needs a bracket covering its SOURCE spread; adjacent
    cells are merged for that proof rather than substituting two point roots.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    pitch = pair.driver.angular_pitch_rad
    cache = {}

    def prove(lo,hi):
        key = lo,hi
        if key not in cache:
            cache[key] = _contact_cell_pair(
                pair,material_pair,continuation.PhaseCell(I(lo,hi),pose),source_domain,
                maximum_error_mm=maximum_error_mm,maximum_jump_mm=maximum_jump_mm)
        return cache[key]

    grid = [pitch*i/(phases-1) for i in range(phases)]
    pending = list(reversed(list(zip(grid,grid[1:]))))
    cells = []
    while pending:
        lo,hi = pending.pop()
        try:
            proved = prove(lo,hi)
        except ContinuousContactRefusal as whole:
            mid = lo/2+hi/2
            if not lo < mid < hi or len(cells)+len(pending) >= 32*(phases-1):
                raise ContinuousContactRefusal(
                    "phase enclosure refinement unresolved at its finite partition limit",
                    {"phase_cell_rad":[lo,hi],"whole_cell_refusal":whole.evidence}) from whole
            try:
                prove(mid,mid)
            except ContinuousContactRefusal as point:
                raise ContinuousContactRefusal(
                    "fixed-phase physical-source proof is unresolved; phase subdivision cannot certify this cell",
                    {"phase_cell_rad":[lo,hi],"fixed_driver_phase_rad":mid,
                     "whole_cell_refusal":whole.evidence,"fixed_phase_refusal":point.evidence,
                     "physical_no_solution":False}) from point
            pending.extend(((mid,hi),(lo,mid)))
            continue
        cells.append(proved)

    while True:
        problem = None
        topology = []
        for index,cell in enumerate(cells):
            try:
                topology.append({side:_contact_topology(item,maximum_jump_mm)[0] for side,item in cell.items()})
            except ContinuousContactRefusal as exc:
                problem = index,index,exc
                break
            if index:
                try:
                    for side in ("lower","upper"):
                        _boundary_continuation(cells[index-1][side],cell[side],
                                               topology[index-1][side][1],topology[index][side][0],index-1)
                except ContinuousContactRefusal as exc:
                    problem = index-1,index,exc
                    break
        if problem is None:
            return cells
        first,last,reason = problem
        ranges = ([(first,last)] if first != last else
                  [(a,b) for a,b in ((first-1,last),(first,last+1)) if 0 <= a <= b < len(cells)])
        failures = []
        for first,last in sorted(ranges,key=lambda indices:
                                 cells[indices[1]]["lower"].cell.driver_phase_rad.upper
                                 -cells[indices[0]]["lower"].cell.driver_phase_rad.lower):
            lo = cells[first]["lower"].cell.driver_phase_rad.lower
            hi = cells[last]["lower"].cell.driver_phase_rad.upper
            try:
                merged = prove(lo,hi)
                for item in merged.values():
                    _contact_topology(item,maximum_jump_mm)
            except ContinuousContactRefusal as exc:
                failures.append({"phase_cell_rad":[lo,hi],"reason":str(exc),"evidence":exc.evidence})
                continue
            cells[first:last+1] = [merged]
            break
        else:
            raise ContinuousContactRefusal(
                "whole-source branch exchange or boundary continuation remains unresolved",
                {"reason":str(reason),"continuation_refusal":reason.evidence,"merged_cell_attempts":failures})


def _branch_phase_envelope(item,proof,pair,material_pair,mechanical_zero):
    """Same-q signed mechanical TE; cancel ideal phase before propagation."""
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    ratio = I.point(pair.driver.teeth)/pair.driven.teeth
    centre = proof.cell.centre()
    phi0,beta0 = mechanical_zero["driver"],mechanical_zero["driven"]
    minimum = next(value for value in item.cover.chart_minimum_bounds if value.chart_name == proof.chart_name)
    geometry = continuation.branch_geometry_error_rad(proof,minimum,additional_geometry_error_mm=0.0)
    displacement = item.cover.additional_geometry_error_mm
    required_displacement = continuation.periodicity_displacement_bound_mm(material_pair,proof.cell.source_pose)
    if (displacement < required_displacement
            or minimum.objective_gradient_padding_mm < (I.point(proof.geometry_error_bound_mm)+displacement).upper):
        raise ContinuousContactRefusal("whole-period TE lacks its full geometric-plus-periodic Lipschitz region",
                                      {"chart":proof.chart_name,"minimum":minimum.record()})
    periodic = (I.point(displacement)*minimum.objective_gradient_magnitude_upper_per_mm
                /minimum.approach_derivative_magnitude_lower).upper
    payment = continuation.branch_geometry_error_rad(
        proof,minimum,additional_geometry_error_mm=displacement)
    te = proof.center_driven_phase_rad-beta0+ratio*(centre.driver_phase_rad-phi0)
    for name,bounds,derivative in zip(proof.cell.parameter_names,proof.cell.parameter_bounds,proof.source_gradient_rad):
        slope = derivative+ratio if name == "driver_phase_rad" else derivative
        te += slope*(bounds-I.point(bounds.midpoint))
    te += I(-payment,payment)
    physical = proof.driven_phase_rad+I(-payment,payment)
    material = proof.driven_material_phase_rad+I(-payment,payment)
    return {
        "chart":proof.chart_name,"signed_running_te_interval_rad":te.record(),
        "physical_driven_phase_interval_rad":physical.record(),
        "material_driven_phase_interval_rad":material.record(),
        "physical_geometry_payment_rad":geometry,"joint_period_displacement_upper_mm":displacement,
        "joint_period_error_payment_rad":periodic,"total_geometric_payment_rad":payment,
        "mechanical_zero_rad":dict(mechanical_zero),
        "definition":"physical beta-beta0 + exact tooth-count ratio*(actual phi-phi0); shared parameter derivatives",
    }


def _side_phase_envelopes(item,pair,material_pair,mechanical_zero):
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    first = _uniform_first_charts(item)
    branches = [proof for proof in item.proofs if not first or proof.chart_name in first]
    records = [_branch_phase_envelope(item,proof,pair,material_pair,mechanical_zero) for proof in branches]

    def envelope(field):
        intervals = [I(*record[field]) for record in records]
        # Closing downwards meets the greatest root; upwards meets the least.
        select = max if item.cover.closing_driven_sense == -1 else min
        return I(select(value.lower for value in intervals),select(value.upper for value in intervals))

    return {
        "signed_running_te_interval_rad":envelope("signed_running_te_interval_rad"),
        "physical_driven_phase_interval_rad":envelope("physical_driven_phase_interval_rad"),
        "material_driven_phase_interval_rad":envelope("material_driven_phase_interval_rad"),
        "branch_envelopes":records,
    }


def _correlated_backlash(lower,upper,pair,lower_envelope,upper_envelope):
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    if lower.cell != upper.cell:
        raise ValueError("backlash requires one identical physical source/phase cell")
    left_payments = {record["chart"]:record["total_geometric_payment_rad"] for record in lower_envelope["branch_envelopes"]}
    right_payments = {record["chart"]:record["total_geometric_payment_rad"] for record in upper_envelope["branch_envelopes"]}
    left = [proof for proof in lower.proofs if proof.chart_name in left_payments]
    right = [proof for proof in upper.proofs if proof.chart_name in right_payments]
    pairs = []
    for a in left:
        for b in right:
            difference = continuation.difference_from_branch_proofs(a,b)
            error = (I.point(left_payments[a.chart_name])+right_payments[b.chart_name]).upper
            paid = difference+I(-error,error)
            pairs.append({"lower_chart":a.chart_name,"upper_chart":b.chart_name,
                          "same_pose_root_difference_rad":difference.record(),
                          "geometry_and_period_payment_rad":error,"paid_root_difference_rad":paid.record()})
    # min_j beta_upper_j - max_i beta_lower_i = min_(i,j)(beta_upper_j-beta_lower_i).
    angle = I(min(value["paid_root_difference_rad"][0] for value in pairs),
              min(value["paid_root_difference_rad"][1] for value in pairs))
    return {
        "same_source_pose":lower.cell.source_pose.record(),"phase_cell_rad":lower.cell.driver_phase_rad.record(),
        "branch_pairs":pairs,"backlash_interval_rad":angle.record(),
        "backlash_interval_mm":(angle*pair.driven.pitch_radius_mm).record(),
        "pitch_radius_mm":pair.driven.pitch_radius_mm,
        "definition":"min of same-q upper-minus-lower root differences; source derivatives subtracted before propagation",
    }


def _period_cell_record(items,pair,material_pair,source_domain,driver_sense):
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    zero = source_domain["mechanical_zero_rad"]
    envelopes = {side:_side_phase_envelopes(item,pair,material_pair,zero) for side,item in items.items()}
    running_side = "lower" if driver_sense == -1 else "upper"
    running = items[running_side]
    root,reverse = running.root_proof,running.driven_root_material_proof
    backlash = _correlated_backlash(items["lower"],items["upper"],pair,envelopes["lower"],envelopes["upper"])
    return {
        "phase_cell_rad":running.cell.driver_phase_rad.record(),
        "actual_driver_interval_rad":(running.cell.driver_phase_rad-zero["driver"]).record(),
        "actual_driven_lower_interval_rad":(envelopes["lower"]["physical_driven_phase_interval_rad"]-zero["driven"]).record(),
        "actual_driven_upper_interval_rad":(envelopes["upper"]["physical_driven_phase_interval_rad"]-zero["driven"]).record(),
        "material_driven_lower_interval_rad":envelopes["lower"]["material_driven_phase_interval_rad"].record(),
        "material_driven_upper_interval_rad":envelopes["upper"]["material_driven_phase_interval_rad"].record(),
        "signed_running_te_interval_rad":envelopes[running_side]["signed_running_te_interval_rad"].record(),
        "mechanical_zero_rad":dict(zero),"operating_driver_sense":driver_sense,
        "side_branch_envelopes":{side:value["branch_envelopes"] for side,value in envelopes.items()},
        "correlated_backlash":backlash,
        "correlated_backlash_interval_mm":backlash["backlash_interval_mm"],
        "root_air":{
            "qualified":(root["status"] == reverse["status"] == "PROVED"
                         and root["physical_root_air_lower_bound_mm"] > 0 and reverse["root_air_lower_mm"] > 0),
            "root_is_carrying":False,"root_air_requirements_mm":dict(source_domain["root_air_requirements_mm"]),
            "driver_root_air_lower_mm":root["physical_root_air_lower_bound_mm"],
            "driven_root_air_lower_mm":reverse["root_air_lower_mm"],
            "driver_root_proof":root,"driven_root_material_proof":reverse,
        },
        "same_source_pose":running.cell.source_pose.record(),
        "whole_joint_period_scope":{
            "tooth_steps":math.lcm(pair.driver.teeth,pair.driven.teeth),
            "source_relabel":"actual rotation-invariant body eccentricity disks; all physical tooth identities",
            "displacement_payment_mm":continuation.periodicity_displacement_bound_mm(material_pair,running.cell.source_pose),
        },
    }


def _actual_read_phase(pair,material_pair,source_domain,pose,phase,*,driver_sense,maximum_error_mm,maximum_jump_mm,face_enclosure):
    """Query the actual requested driver angle, not a periodic endpoint alias."""
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    cell = continuation.PhaseCell(I.point(phase),pose)
    items = _contact_cell_pair(pair,material_pair,cell,source_domain,
                               maximum_error_mm=maximum_error_mm,maximum_jump_mm=maximum_jump_mm)
    row = _period_cell_record(items,pair,material_pair,source_domain,driver_sense)
    side = "lower" if driver_sense == -1 else "upper"
    running = items[side]
    centre_clock = dict(pose.centre().axes).get("driven_clock_rad",I.point(0)).midpoint
    proofs = {proof.chart_name:proof for proof in running.proofs}
    charts = {chart.name:chart for chart in running.charts}
    minima = {minimum.chart_name:minimum for minimum in running.cover.chart_minimum_bounds}
    direct = {key:item.record() for key,item in items.items()}
    records = {proof["chart"]:proof for proof in direct[side]["branch_proofs"]}
    centres = {}
    for name,proof in proofs.items():
        # This is a bounded numerical representative of the certified centre
        # ROOT, never the midpoint of the manufacturing source or an old seed.
        point = tuple(value.midpoint for value in proof.center_root_box)
        evaluation = charts[name].evaluate(cell.centre(),tuple(I.point(value) for value in point))
        records[name]["center_point"] = list(point)
        records[name]["center_point_residual_intervals"] = [value.record() for value in evaluation.residual]
        root_evaluation = charts[name].evaluate(cell.centre(),proof.center_root_box)
        records[name]["center_root_residual_intervals"] = [value.record() for value in root_evaluation.residual]
        payment = continuation.branch_geometry_error_rad(
            proof,minima[name],additional_geometry_error_mm=running.cover.additional_geometry_error_mm)
        centres[name] = proof.center_driven_phase_rad+I(-payment,payment)
    choose = max if running.cover.closing_driven_sense == -1 else min
    first = I(choose(value.lower for value in centres.values()),
              choose(value.upper for value in centres.values()))
    # Overlapping/tied roots remain eligible. The extreme certified bound
    # selects a deterministic representative, NOT a claim of unique ordering.
    _,name = choose(((value.lower if side == "lower" else value.upper),name)
                    for name,value in centres.items())
    eligible = sorted(name for name,value in centres.items()
                      if value.lower <= first.upper and value.upper >= first.lower)
    point = records[name]["center_point"]
    beta = point[proofs[name].driven_angle_unknown_index]-centre_clock
    zero = source_domain["mechanical_zero_rad"]
    reference = math.fsum((beta,-zero["driven"],pair.driver.teeth/pair.driven.teeth*(phase-zero["driver"])))
    actual = I(*row["signed_running_te_interval_rad"])
    error = (actual-I.point(reference)).magnitude
    centre_error = first-I.point(beta)
    centre_te = first-I.point(zero["driven"])+(I.point(pair.driver.teeth)/pair.driven.teeth)*(I.point(phase)-zero["driver"])
    if not first.contains(beta) or not actual.contains(centre_te):
        raise ContinuousContactRefusal("certified centre first-root reference is outside the paid actual envelope",
                                      {"centre_first_root_rad":first.record(),"actual_te_rad":actual.record()})
    return {
        **row,"actual_driver_phase_rad":phase,"reference_signed_running_te_rad":reference,
        "reference_driven_phase_rad":beta,"reference_source_pose":pose.centre().record(),
        "reference_chart":name,"reference_common_normal_point":point,
        "reference_residual_intervals":records[name]["center_point_residual_intervals"],
        "reference_root_proof":records[name],"reference_error_bound_rad":error,
        "reference_center_first_root_interval_rad":first.record(),
        "reference_center_first_candidates":eligible,
        "reference_center_first_root_error_rad":centre_error.record(),
        "reference_center_first_root_error_bound_rad":centre_error.magnitude,
        "actual_interval_error_from_reference_rad":(actual-I.point(reference)).record(),
        "direct_first_contact_sides":direct,
        "reference_definition":"canonical certified centre-root midpoint eligible for the paid first-contact envelope; residual and midpoint-to-true-root error retained, not an exact zero-residual root or a source midpoint",
        "direct_actual_phase_query":True,"periodic_point_substitution":False,
        "finite_face_material_enclosure":face_enclosure,
    }


def analyse_3d_mesh(
    case: ContactPair, *, continuous_source_domain: dict,
    phases: int = 129, maximum_error_mm: float = 0.001,
    coverage_min: float = 0.62, row_min: float = 0.85,
    handover_max_mm: float = 0.005, positive_backlash_min_mm: float = 0.0,
    driver_sense: int = 1, read_driver_phases_rad=(),
) -> dict:
    """Produce actual continuous common-source material/contact evidence.

    There is no point-row fallback. Unresolved first contact, source spread,
    branch exchange, finite cap or root containment raises a receipt-bearing
    refusal; none means that the physical mechanism is infeasible.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    if type(phases) is not int or phases < 3:
        raise ValueError("a whole-pitch study requires at least three phase nodes")
    if type(driver_sense) is not int or driver_sense not in (-1,1):
        raise ValueError("driver sense must be the actual signed physical axis direction")
    criteria = maximum_error_mm,coverage_min,row_min,handover_max_mm,positive_backlash_min_mm
    if (any(type(value) not in (float,int) or not math.isfinite(value) for value in criteria)
            or maximum_error_mm <= 0 or coverage_min < 0 or not 0 <= row_min <= 1
            or handover_max_mm <= 0 or positive_backlash_min_mm < 0):
        raise ValueError("continuous contact criteria must be finite physical bounds")
    domain = continuous_source_domain
    if domain.get("unbound_sources") or domain.get("source_domain_status") == "UNKNOWN":
        raise ContinuousContactRefusal("physical source domain contains an unbound manufacturing degree of freedom",
                                      {"continuous_source_domain":domain,"physical_no_solution":False})
    pose = source_pose(domain["correlated_pose_parameters"])
    zero = domain["mechanical_zero_rad"]
    if (set(zero) != {"driver","driven"} or any(
            type(value) not in (float,int) or not math.isfinite(value) for value in zero.values())
            or zero["driver"] != 0.0):
        raise ValueError("whole-pitch coordinate zero must bind actual manufactured driver/driven datums")
    floors = domain["root_air_requirements_mm"]
    if (set(floors) != {"driver","driven"} or any(
            type(value) not in (float,int) or not math.isfinite(value) or value < 0 for value in floors.values())):
        raise ValueError("both directed root-material floors are required")
    requested = tuple(read_driver_phases_rad)
    if any(type(value) not in (float,int) or not math.isfinite(value) for value in requested):
        raise ValueError("direct read phases must be actual finite signed driver angles")
    support,material,face_receipt = finite_face_family(case,domain)
    cells = _contact_partition(
        support,material,domain,pose,phases=phases,
        maximum_error_mm=maximum_error_mm,maximum_jump_mm=handover_max_mm)
    sides = {side:_continuous_side(
        support,material,[cell[side] for cell in cells],domain,
        maximum_error_mm=maximum_error_mm,maximum_jump_mm=handover_max_mm) for side in ("lower","upper")}
    running_side = "lower" if driver_sense == -1 else "upper"
    running = sides[running_side]
    rows = [_period_cell_record(cell,support,material,domain,driver_sense) for cell in cells]
    reads = [_actual_read_phase(
        support,material,domain,pose,float(phase),driver_sense=driver_sense,
        maximum_error_mm=maximum_error_mm,maximum_jump_mm=handover_max_mm,
        face_enclosure=face_receipt) for phase in requested]
    tight = min(row["correlated_backlash_interval_mm"][0] for row in rows)
    loose = max(row["correlated_backlash_interval_mm"][1] for row in rows)
    lag = I(min(row["signed_running_te_interval_rad"][0] for row in rows),
            max(row["signed_running_te_interval_rad"][1] for row in rows))
    # A prospective driver material clock -delta corresponds to ideal physical
    # beta at TE=-ratio*delta. This is a DESIGN window, not a selected datum or
    # a transport of the certificate to an unqueried installed clock.
    ratio = I.point(case.driver.teeth)/case.driven.teeth
    lower,upper = -math.inf,math.inf
    for cell in cells:
        bounds = {side:_side_phase_envelopes(item,support,material,zero)["signed_running_te_interval_rad"]
                  for side,item in cell.items()}
        lower = max(lower,(-I.point(bounds["upper"].lower)/ratio).upper)
        upper = min(upper,(-I.point(bounds["lower"].upper)/ratio).lower)
    common = [[lower,upper]] if lower < upper else []
    gates = (tight > positive_backlash_min_mm and running["stock_form_coverage_lower"] >= coverage_min
             and running["row_available_fraction_lower"] >= row_min
             and all(row["root_air"]["qualified"] for row in rows))
    production = (domain.get("scope") == "FULL_PRODUCTION_SOURCE_DOMAIN"
                  and domain.get("production_source_domain") is True)
    certificate = {
        "proof_schema":"finite-stock-continuous-envelope/1","status":"PROVED","native_certificate":False,
        "same_source_pose":pose.record(),"phase_domain_rad":[0.0,case.driver.angular_pitch_rad],
        "finite_face_material_enclosure":face_receipt,"sides":sides,
        "joint_period_tooth_steps":math.lcm(case.driver.teeth,case.driven.teeth),
        "whole_period_signed_running_te_interval_rad":lag.record(),
        "whole_period_signed_running_te_scope":{
            "operating_driver_sense":driver_sense,"source_domain":domain,
            "phase_cells":len(rows),"all_physical_tooth_identities":True,
            "periodicity_authority":"both actual source-relabelled periodic_seam receipts",
            "bound_authority":"same-q branch derivatives plus actual geometry and full joint-period displacement",
        },
    }
    return {
        "case":case.name,"metric":"STOCK-FORM COVERAGE","is_conjugate":False,
        "driver_profile":profile_record(case.driver),"driven_profile":profile_record(case.driven),
        "placement":case.placement.record(),"operating_driver_sense":driver_sense,
        "continuous_source_domain":domain,"continuous_contact_certificate":certificate,
        "continuous_carrying_contact":True,"full_period_cells":rows,"actual_read_phases":reads,
        "source_domain_proved":gates,"production_source_qualified":gates and production,
        "qualified":gates and production,"native_certificate":False,"physical_no_solution":False,
        "stock_form_coverage_lower":running["stock_form_coverage_lower"],
        "coverage_definition":running["coverage_definition"],"uncovered_phase_rad":running["uncovered_phase_rad"],
        "row_available_fraction_lower":running["row_available_fraction_lower"],
        "row_available_intervals_mm":running["row_available_intervals_mm"],
        "handovers":running["handovers"],"periodic_seam":running["periodic_seam"],
        "tight_backlash_lower_mm":tight,"loose_backlash_upper_mm":loose,
        "whole_period_signed_running_te_interval_rad":lag.record(),
        "phase_components_rad":common,"phase_window_rad":common[0] if common else None,
        "phase_window_scope":"prospective driver material clock DESIGN only; installed phase requires actual source qualification",
        "numerical_error_bounds":{"surface_mm":maximum_error_mm},
    }


def read_actual_phases(case: ContactPair,*,continuous_source_domain,driver_phases_rad,
                       driver_sense,maximum_error_mm=.001,maximum_jump_mm=.005):
    """Fresh complete material/contact queries at explicitly requested angles.

    This point packet is not a whole-period certificate. A selected-phase
    publisher must separately bind its actual phase transport to a complete
    continuous source certificate.
    """
    if (type(driver_sense) is not int or driver_sense not in (-1,1)
            or any(type(value) not in (float,int) or not math.isfinite(value) or value <= 0
                   for value in (maximum_error_mm,maximum_jump_mm))):
        raise ValueError("actual read query requires a physical sense and finite positive numerical bounds")
    domain = continuous_source_domain
    if domain.get("unbound_sources") or domain.get("source_domain_status") == "UNKNOWN":
        raise ContinuousContactRefusal("actual read query has an unbound physical source",
                                      {"continuous_source_domain":domain,"physical_no_solution":False})
    pose = source_pose(domain["correlated_pose_parameters"])
    requested = tuple(driver_phases_rad)
    if not requested or any(type(value) not in (float,int) or not math.isfinite(value) for value in requested):
        raise ValueError("actual read queries require their finite physical driver angles")
    support,material,faces = finite_face_family(case,domain)
    rows = [_actual_read_phase(
        support,material,domain,pose,float(phase),driver_sense=driver_sense,
        maximum_error_mm=maximum_error_mm,maximum_jump_mm=maximum_jump_mm,face_enclosure=faces)
        for phase in requested]
    return {
        "case":case.name,"proof_schema":"finite-stock-actual-read-points/1",
        "point_source_domain_proved":True,"production_source_qualified":False,"native_certificate":False,
        "placement":case.placement.record(),"driver_profile":profile_record(case.driver),
        "driven_profile":profile_record(case.driven),"continuous_source_domain":domain,
        "operating_driver_sense":driver_sense,"numerical_error_bounds":{"surface_mm":maximum_error_mm},
        "actual_read_phases":rows,
    }


def selected_driver_clock_transport(case,selected_pair,result,*,selected_phase_offset_deg,
                                    base_geometry_sha256,measurement_engine_sha256):
    """Exact same-q material-clock change, then the already-paid physical seam.

    The commanded degree setting is not pretended to be an exact radian
    subtraction. The effective delta encloses the actual two source clocks.
    No source translation/tilt box is rotated; only the existing seam may
    relabel its proved eccentricity DISKS and actual physical tooth identities.
    """
    import hashlib
    import json
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    if (type(selected_phase_offset_deg) not in (float,int) or not math.isfinite(selected_phase_offset_deg)
            or result.get("source_domain_proved") is not True
            or result["placement"] != case.placement.record()
            or selected_pair.driver is not case.driver or selected_pair.driven is not case.driven):
        raise ValueError("selected material clock needs its actual whole-source physical base proof")
    base,selected = case.placement.record(),selected_pair.placement.record()
    if any(selected[key] != value for key,value in base.items() if key != "driver_clocking_rad"):
        raise ValueError("phase transport may change ONLY the actual manufactured driver material clock")
    certificate = result["continuous_contact_certificate"]
    if any(certificate["sides"][side]["periodic_seam"]["status"] != "PROVED" for side in ("lower","upper")):
        raise ValueError("selected clock lacks both actual paid source-relabelled seam proofs")
    domain = result["continuous_source_domain"]
    source = source_pose(domain["correlated_pose_parameters"])
    delta = I.point(base["driver_clocking_rad"])-selected["driver_clocking_rad"]
    ratio = I.point(case.driver.teeth)/case.driven.teeth
    conversion = ratio*delta
    base_lag = I(*result["whole_period_signed_running_te_interval_rad"])
    def digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    record = {
        "proof_schema":"finite-stock-selected-driver-clock/1","native_certificate":False,
        "base_geometry_sha256":base_geometry_sha256,"measurement_engine_sha256":measurement_engine_sha256,
        "base_certificate_sha256":digest(certificate),"base_placement":base,"selected_placement":selected,
        "selected_phase_offset_deg":selected_phase_offset_deg,
        "effective_driver_material_delta_rad":delta.record(),
        "source_map_before_period_reduction":{name:name for name,_ in source.axes},
        "driver_parameter_relation":"psi = physical_driver_phi - effective_driver_material_delta",
        "driven_parameter_relation":"physical_beta unchanged",
        "unchanged_rectangular_source_axes":[name for name,_ in source.axes if "_ecc_" not in name],
        "period_relabelling_authority":{
            side:digest(certificate["sides"][side]["periodic_seam"]) for side in ("lower","upper")},
        "source_eccentricity_disks":domain["source_eccentricity_disks"],
        "joint_period_tooth_steps":math.lcm(case.driver.teeth,case.driven.teeth),
        "signed_running_te_conversion_rad":conversion.record(),
        "base_whole_period_signed_running_te_interval_rad":base_lag.record(),
        "selected_whole_period_signed_running_te_interval_rad":(base_lag+conversion).record(),
        "geometry_payment":"the SAME geometry and joint-period displacement already paid in every first-contact cell; not added again",
        "selected_read_requirement":"fresh complete material/first-contact queries at every actual requested selected-placement angle",
    }
    record["selected_source_identity_sha256"] = digest(record)
    return record
