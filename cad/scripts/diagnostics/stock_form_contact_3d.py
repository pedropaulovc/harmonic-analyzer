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


def handovers(
    case: ContactPair, rows: list[dict], error_mm: float, *,
    position_error_mm: float = 0.0, maximum_jump_mm: float = 0.005,
    radial_error_mm: float = 0.0, axial_error_mm: float = 0.0,
    required_root_air_mm: float = 0.0,
) -> list[dict]:
    """Compare independently rooted driven branches at one fixed driver pose."""
    result = []
    ratio = case.driver.teeth/case.driven.teeth
    for side,sense,index in (("lower",1,1),("upper",-1,2)):
        for left,right in zip(rows,rows[1:]):
            a,b = left[f"{side}_contact"]["driven_tooth"],right[f"{side}_contact"]["driven_tooth"]
            if a == b:
                continue
            low,high = left["driver_phase_rad"],right["driver_phase_rad"]
            original = [low,high]
            crossing = None
            for _ in range(28):
                phase = (low+high)/2.0
                measured = ContactSearch(
                    case,phase,position_error_mm=position_error_mm,
                    radial_error_mm=radial_error_mm,axial_error_mm=axial_error_mm,
                ).window(error_mm,required_root_air_mm=required_root_air_mm)
                pairs = {entry[0]:entry[index] for entry in measured.branch_intervals}
                if a not in pairs or b not in pairs:
                    break
                crossing = phase,(pairs[a]+pairs[b])/2.0,measured
                if abs(pairs[a]-pairs[b])*case.driver.pitch_radius_mm < maximum_jump_mm/20.0:
                    break
                a_carries = pairs[a] > pairs[b] if sense == 1 else pairs[a] < pairs[b]
                if a_carries:
                    low = phase
                else:
                    high = phase
            if crossing is None:
                result.append({"continuous":False,"side":side,"pair":[a,b],
                               "phase_bracket_rad":original,"reason":"supported branch overlap absent"})
                continue
            phase,offset,measured = crossing
            # Same worlddriver pose for both independent actual driven roots.
            fixed_driver = phase-offset
            nominal_driven = case.placement.driven_clocking_rad-phase*ratio
            bracket = (nominal_driven-case.driven.angular_pitch_rad/8,
                       nominal_driven+case.driven.angular_pitch_rad/8)
            try:
                roots = [loaded_driven_contact(
                    case,fixed_driver,driver_sense=sense,driven_bracket_rad=bracket,
                    maximum_error_mm=min(error_mm,maximum_jump_mm/16),
                    driven_teeth=(tooth,),position_error_mm=position_error_mm,
                    radial_error_mm=radial_error_mm,axial_error_mm=axial_error_mm,
                    required_root_air_mm=required_root_air_mm,
                ) for tooth in (a,b)]
            except ValueError as exc:
                result.append({"continuous":False,"side":side,"pair":[a,b],
                               "phase_bracket_rad":original,"reason":str(exc)})
                continue
            separation = abs(roots[0]["driven_phase_rad"]-roots[1]["driven_phase_rad"])
            bound = roots[0]["bound_rad"]+roots[1]["bound_rad"]
            jump = case.driven.pitch_radius_mm*(separation+bound)
            contact = roots[0]["contact"]
            point_delta = np.asarray(roots[1]["contact"]["world_point_mm"])-np.asarray(contact["world_point_mm"])
            normal = np.asarray(contact["driven_normal_world"])
            result.append({
                "continuous":jump <= maximum_jump_mm,"side":side,"pair":[a,b],
                "phase_rad":phase,"phase_bracket_rad":original,
                "fixed_driver_phase_rad":fixed_driver,
                "pitch_displacement_jump_upper_mm":jump,
                "driven_phase_roots_rad":[root["driven_phase_rad"] for root in roots],
                "driven_phase_error_bounds_rad":[root["bound_rad"] for root in roots],
                "normal_projected_contact_transfer_mm":float(point_delta@normal),
                "contact_site_distance_mm":float(np.linalg.norm(point_delta)),
                "contact":contact,
            })
    return result


def analyse_3d_mesh(
    case: ContactPair, *, phases: int = 129, maximum_error_mm: float = 0.001,
    coverage_min: float = 0.62, row_min: float = 0.85,
    handover_max_mm: float = 0.005, positive_backlash_min_mm: float = 0.0,
    position_error_mm: float = 0.0,
    radial_error_mm: float = 0.0, axial_error_mm: float = 0.0,
    driver_sense: int = 1,
    required_root_air_mm: float = 0.0,
) -> dict:
    if phases < 3:
        raise ValueError("a whole-pitch study requires endpoints and interior phases")
    if driver_sense not in (-1,1):
        raise ValueError("driver_sense must be +1 or -1 about the declared driver axis")
    pitch = case.driver.angular_pitch_rad
    rows = []
    for phase in np.linspace(0.0, pitch, phases):
        measured = ContactSearch(
            case,float(phase),position_error_mm=position_error_mm,
            radial_error_mm=radial_error_mm,axial_error_mm=axial_error_mm,
        ).window(maximum_error_mm,phase_half_width_rad=pitch/(phases-1)/2,
                 required_root_air_mm=required_root_air_mm)
        rows.append(asdict(measured))
        if measured.lower_contact is None or measured.upper_contact is None:
            raise ValueError(f"{case.name}: missing supported carrying contact at phase {phase}")
    radius = case.driver.pitch_radius_mm
    ratio = case.driver.teeth / case.driven.teeth
    # The radial inverse's slope and polar-angle differential bound motion
    # of each feasible branch. Pay both endpoints of every backlash window.
    inverse = GapAngles(case.driver)
    phase_lipschitz = 1.0+ratio*case.driven.blank_radius_mm*math.hypot(1.0/inverse.minimum,inverse.radial_slope_bound())
    phase_step = pitch/(phases-1)
    phase_bound = radius*phase_lipschitz*phase_step/2.0
    lower = max(row["lower_rad"]+row["error_rad"] for row in rows)+phase_bound/radius
    upper = min(row["upper_rad"]-row["error_rad"] for row in rows)-phase_bound/radius
    common = ((-pitch/2,pitch/2),)
    for row in rows:
        common = intersect_intervals(common,row["free_intervals_rad"])
    selected = max(common,key=lambda interval:interval[1]-interval[0]) if common else None
    backlash = [(row["upper_rad"]-row["lower_rad"]-2*row["error_rad"])*radius for row in rows]
    edge = "lower_rad" if driver_sense == 1 else "upper_rad"
    carrying = [row[edge] for row in rows]
    # Actual input is phase-offset; output is seed-ratio*phase. The
    # mechanical-datum world-angle TE is -ratio*offset, with NO home tare.
    # This is not the direct held-driver stall reader.
    te = [-value*ratio for value in carrying]
    counts = []
    no_gap = True
    reserve = math.inf
    noncarrying_gap = 0.0
    for row in rows[:-1]:
        reserves = dict(row["branch_phase_reserves_rad"])
        active = []
        for tooth,low,high in row["branch_intervals"]:
            free_reserve = (high-low-2*row["error_rad"])/(2*phase_lipschitz)
            branch_reserve = min(reserves.get(tooth,0.0),free_reserve)
            if branch_reserve >= phase_step/2:
                active.append(branch_reserve)
            if math.isfinite(low) and math.isfinite(row["lower_rad"]):
                angular_gap = row["lower_rad"]-low+2*row["error_rad"]+2*phase_bound/radius
                noncarrying_gap = max(noncarrying_gap,angular_gap*case.driver.blank_radius_mm)
        counts.append(len(active))
        contact_kinds = (row["lower_contact"]["kind"],row["upper_contact"]["kind"])
        no_gap &= (bool(active) and row["surface_numerical_resolved"] and not row["root_contact"]
                   and all(not any(feature in kind for feature in ("axial_face","root_arc","root_corner")) for kind in contact_kinds)
                   and all(row[side]["common_normal_supported"]
                           and math.isfinite(row[side]["driven_per_driver_velocity"])
                           and row[side]["opposed_normal_residual"] <= row[side]["common_normal_error_bound"]
                           for side in ("lower_contact","upper_contact")))
        reserve = min(reserve,max(active,default=0.0)-phase_step/2)
    exchanges = handovers(
        case,rows,maximum_error_mm,position_error_mm=position_error_mm,
        radial_error_mm=radial_error_mm,axial_error_mm=axial_error_mm,
        maximum_jump_mm=handover_max_mm,
        required_root_air_mm=required_root_air_mm,
    )
    row_intervals = merge_intervals(interval for row in rows for interval in row["row_intervals_mm"])
    row_fraction = sum(high-low for low,high in row_intervals)/(case.placement.driven_face_mm[1]-case.placement.driven_face_mm[0])
    coverage = sum(counts)/(phases-1)
    no_gap &= all(
        row["surface_numerical_resolved"] and not row["root_contact"] and all(
            row[side]["common_normal_supported"]
            and not any(feature in row[side]["kind"] for feature in ("axial_face","root_arc","root_corner"))
            and math.isfinite(row[side]["driven_per_driver_velocity"])
            and row[side]["opposed_normal_residual"] <= row[side]["common_normal_error_bound"]
            for side in ("lower_contact","upper_contact"))
        for row in rows
    )
    qualified = (min(backlash)-2*phase_bound > positive_backlash_min_mm and bool(common) and no_gap
                 and coverage >= coverage_min and row_fraction >= row_min
                 and all(exchange["continuous"] and exchange["pitch_displacement_jump_upper_mm"] <= handover_max_mm for exchange in exchanges))
    return {
        "case": case.name, "metric": "STOCK-FORM COVERAGE", "is_conjugate": False,
        "operating_driver_sense":driver_sense,
        "driver_profile":profile_record(case.driver),"driven_profile":profile_record(case.driven),
        "placement":case.placement.record(),"phase_rows":rows,
        "phase_components_rad":common,
        "flank_phase_window_rad":[lower,upper],
        "phase_window_rad":list(selected) if selected is not None else None,
        "phase_seed_rad":sum(selected)/2 if selected is not None else None,
        "stock_form_coverage_lower":coverage,
        "coverage_definition":"supported pair branch-existence span / one physical driver pitch, with interval-paid phase cells",
        "continuous_carrying_contact":no_gap and all(exchange["continuous"] for exchange in exchanges),
        "phase_reserve_rad":reserve,
        "uncovered_phase_rad":sum(phase_step for count in counts if count == 0),
        "noncarrying_pair_normal_gap_upper_mm":noncarrying_gap,
        "noncarrying_gap_definition":"normal projection bounded by actual driver point rotation arc at maximum material radius, including phase and inverse errors",
        "sampled_carrying_corner_fraction":sum(
            any(label in row["lower_contact" if driver_sense == 1 else "upper_contact"]["kind"]
                for label in ("corner","edge","tip_arc")) for row in rows[:-1])/(phases-1),
        "handovers":exchanges,
        "row_available_fraction_lower":row_fraction,
        "row_available_intervals_mm":row_intervals,
        "qualified":qualified,
        "tight_backlash_lower_mm": min(backlash)-2*phase_bound,
        "loose_backlash_upper_mm": max((row["upper_rad"]-row["lower_rad"]+2*row["error_rad"])*radius for row in rows)+2*phase_bound,
        "no_overlap_at_samples": all(row["upper_rad"]-row["lower_rad"] > 2*row["error_rad"] and not row["root_contact"] for row in rows),
        "parametric_driven_mechanical_datum_te_rad":te,
        "parametric_actual_driver_phase_rad":[row["driver_phase_rad"]-row[edge] for row in rows],
        "numerical_error_bounds": {"surface_mm":maximum_error_mm,"phase_motion_mm":phase_bound,
                                   "geom_ball_mm":position_error_mm,
                                   "radial_mm":position_error_mm+radial_error_mm,
                                   "axial_mm":position_error_mm+axial_error_mm,
                                   "root_surface_mm":max(row["root_sweep"]["geometric_uncertainty_mm"] for row in rows),
                                   "te_rad":(2*max(row["error_rad"] for row in rows)+phase_bound/radius)*ratio},
        "native_certificate": False,
    }


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


def pose_cell_search(pair: ContactPair, cell: continuation.PhaseCell,
                     driven_phase_rad: continuation.Interval):
    """Enclose one correlated rigid-pose cell in the straight driver's frame.

    The shared coordinates remain fixed while both material eccentricities
    rotate with their own shafts. Pointwise radial/axial bounds are derived
    from those transforms only for the complete-surface/root queries; they
    are never subtracted to estimate a handover between two branches.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    interval = continuation.Interval
    phi,beta = cell.driver_phase_rad,driven_phase_rad
    sources = dict(cell.source_pose.axes)
    driver_clock = sources.get("driver_clock_rad",interval.point(0))
    driven_clock = sources.get("driven_clock_rad",interval.point(0))
    poses = {
        body:continuation.body_pose_bounds(pair,cell.source_pose,phi,beta,body=body)
        for body in ("driver","driven")
    }
    centres = {
        body:continuation.body_pose_bounds(
            pair,cell.source_pose.centre(),interval.point(phi.midpoint),
            interval.point(beta.midpoint),body=body,
        ) for body in ("driver","driven")
    }
    frames = {body:np.array([[value.midpoint for value in row] for row in pose.frame])
              for body,pose in centres.items()}
    origins = {body:np.array([value.midpoint for value in pose.origin_mm])
               for body,pose in centres.items()}
    driver,driven = poses["driver"],poses["driven"]
    relative = tuple(tuple(
        sum(driver.frame[k][i]*driven.frame[k][j] for k in range(3))
        for j in range(3)) for i in range(3))
    translation = tuple(sum(
        driver.frame[k][i]*(driven.origin_mm[k]-driver.origin_mm[k])
        for k in range(3)) for i in range(3))
    reference = frames["driver"].T@frames["driven"]
    reference_translation = (origins["driven"]-origins["driver"])@frames["driver"]
    support = (pair.driven.blank_radius_mm,pair.driven.blank_radius_mm,
               max(abs(value) for value in pair.placement.driven_face_mm))
    displacement = tuple((
        interval.point((translation[i]-float(reference_translation[i])).magnitude)
        +sum(interval.point((relative[i][j]-float(reference[i,j])).magnitude)*radius
             for j,radius in enumerate(support))
    ).upper for i in range(3))
    # R is orthogonal at every realization. The material rotation chord is
    # at most R*|delta beta| and at most 2R; no libm error assumption is used.
    angular = ((beta-interval.point(beta.midpoint))
               +(driven_clock-interval.point(driven_clock.midpoint))).magnitude
    rotation = min((interval.point(pair.driven.blank_radius_mm)*angular).upper,
                   (interval.point(pair.driven.blank_radius_mm)*2).upper)
    # Python hypot has <1 ulp error; round it outward before interval addition.
    radial_norm = math.nextafter(math.nextafter(math.hypot(displacement[0],displacement[1]),math.inf),math.inf)
    radial = (interval.point(radial_norm)+rotation).upper
    axial = (interval.point(displacement[2])+rotation).upper
    placement = replace(
        pair.placement,
        driver_origin_mm=tuple(map(float,origins["driver"])),
        driven_origin_mm=tuple(map(float,origins["driven"])),
        driver_frame=frames["driver"],driven_frame=frames["driven"],
        driver_clocking_rad=pair.placement.driver_clocking_rad+driver_clock.midpoint,
    )
    physical = replace(pair,placement=placement)
    search = ContactSearch(
        physical,phi.midpoint,driven_phase_rad=beta.midpoint+driven_clock.midpoint,
        radial_error_mm=radial,axial_error_mm=axial,
    )
    driver_motion = ((phi-interval.point(phi.midpoint))
                     +(driver_clock-interval.point(driver_clock.midpoint))).magnitude
    return search,driver_motion


def root_free_pose_cell(pair: ContactPair, cell: continuation.PhaseCell,
                        driven_phase_rad: continuation.Interval, *,
                        maximum_error_mm: float, required_root_air_mm: float):
    """Actual all-tooth/cap root proof over one physical driven-angle cell."""
    search,driver_motion = pose_cell_search(pair,cell,driven_phase_rad)
    bounded = root_free_intervals(
        search,maximum_error_mm=maximum_error_mm,
        required_root_air_mm=required_root_air_mm,
    )
    inner = erode_periodic_intervals(bounded.free_inner,driver_motion,search.pitch)
    resolved = bounded.status == "resolved" and any(lo <= 0.0 <= hi for lo,hi in inner)
    return {
        "status":"PROVED" if resolved else "UNKNOWN",
        "root_free_driven_components_rad":(driven_phase_rad,) if resolved else (),
        "inverse_offset_free_components_rad":inner,
        "driver_phase_motion_rad":driver_motion,
        "same_source_pose":cell.source_pose.record(),
        "source_frame_radial_error_mm":search.radial_error_mm,
        "source_frame_axial_error_mm":search.axial_error_mm,
        "root_sweep":asdict(bounded),
        "native_certificate":False,
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


def _relative_surface_derivatives(pair, cell, beta, segment, tooth, t, z):
    """Exact screw-map point, t/z derivatives, and held-driver beta velocity."""
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    point,tangent = continuation.segment_bounds(segment,t)
    second = continuation.segment_second_derivative_bounds(segment,t)
    parameters = dict(cell.source_pose.axes)
    clock = parameters.get("driven_clock_rad",I.point(0.0))
    twist = 0.0 if math.isinf(pair.driven.lead_per_radian_mm) else 1.0/pair.driven.lead_per_radian_mm
    sigma = beta+clock+tooth*pair.driven.angular_pitch_rad+z*twist
    c,s = continuation.cos_bounds(sigma),continuation.sin_bounds(sigma)
    zero = I.point(0.0)
    def rotate(x,y,axial=zero):
        return c*x-s*y,s*x+c*y,axial
    local = rotate(*point,z)
    first = (rotate(*tangent),rotate(-twist*point[1],twist*point[0],I.point(1.0)))
    seconds = ((rotate(*second),rotate(-twist*tangent[1],twist*tangent[0])),
               (rotate(-twist*tangent[1],twist*tangent[0]),
                rotate(-twist*twist*point[0],-twist*twist*point[1])))
    driver = continuation.body_pose_bounds(pair,cell.source_pose,cell.driver_phase_rad,beta,body="driver")
    driven = continuation.body_pose_bounds(pair,cell.source_pose,cell.driver_phase_rad,beta,body="driven")
    matrix = tuple(tuple(sum(driver.frame[k][i]*driven.frame[k][j] for k in range(3))
                         for j in range(3)) for i in range(3))
    shift = tuple(sum(driver.frame[k][i]*(driven.origin_mm[k]-driver.origin_mm[k])
                      for k in range(3)) for i in range(3))
    transform = lambda value:tuple(_interval_dot(row,value) for row in matrix)
    q = tuple(v+d for v,d in zip(transform(local),shift))
    qt = tuple(transform(v) for v in first)
    qtt = tuple(tuple(transform(v) for v in row) for row in seconds)
    ecc = (parameters.get("driven_ecc_x_mm",zero),parameters.get("driven_ecc_y_mm",zero))
    cb,sb = continuation.cos_bounds(beta+clock),continuation.sin_bounds(beta+clock)
    eccentric_velocity = (-cb*ecc[1]-sb*ecc[0],-sb*ecc[1]+cb*ecc[0],zero)
    beta_velocity = tuple(a+b for a,b in zip(rotate(-point[1],point[0]),eccentric_velocity))
    return q,qt,qtt,transform(beta_velocity),driver.frame,point,tangent,second


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
        return continuation.sqrt_bounds(_interval_square(S)+_interval_square(Q))
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


def chart_neighbourhood_minimum(pair, chart, proof, t, z, *,
                                direction, outside_air_mm, approach_driven_phase_rad):
    """Sufficient constrained local minimum on an entire real patch rectangle.

    A positive FULL 2D Lagrangian Hessian is deliberately stronger than a
    tangent-only test at an edge. Failure is UNKNOWN, never zero curvature or a
    fabricated support margin. Multipliers use the same implicit branch/source.
    """
    from diagnostics import stock_form_contact_continuation as continuation
    I = continuation.Interval
    if (chart.pair is not pair or pair.driver.helix_angle_deg != 0.0
            or chart.driver_stratum.segment.kind not in ("flank","radial")
            or direction not in (-1,1) or direction != chart.driver_stratum.segment._side):
        raise ValueError("local minimum does not use the actual straight driver's working side")
    beta = approach_driven_phase_rad
    if not beta.contains(proof.driven_phase_rad):
        raise ValueError("local minimum approach omits its actual contact root")
    q,qt,qtt,velocity,frame,p,dp,ddp = _relative_surface_derivatives(
        pair,proof.cell,beta,chart.driven_stratum.segment,chart.driven_tooth,t,z)
    radius = continuation.sqrt_bounds(_interval_square(q[0])+_interval_square(q[1]))
    slope,curvature = _working_angle_derivatives(pair.driver,chart.driver_stratum.segment.kind,radius)
    er = (q[0]/radius,q[1]/radius)
    et = (-er[1],er[0])
    gradient = tuple(slope*er[i]-direction*et[i]/radius for i in range(2))+(I.point(0.0),)
    hxy = tuple(tuple(curvature*er[i]*er[j]+slope/radius*et[i]*et[j]
                     +direction/_interval_square(radius)*(er[i]*et[j]+et[i]*er[j])
                     for j in range(2)) for i in range(2))
    hessian = [[sum(qt[i][a]*hxy[a][b]*qt[j][b] for a in range(2) for b in range(2))
                +_interval_dot(gradient,qtt[i][j]) for j in range(2)] for i in range(2)]
    gradient_world = tuple(sum(frame[i][j]*gradient[j] for j in range(3)) for i in range(3))
    multipliers = continuation.objective_kkt_multipliers(chart,proof,gradient_world)
    approach = _interval_dot(gradient,velocity)
    for body,stratum in (("driver",chart.driver_stratum),("driven",chart.driven_stratum)):
        constraints = list(stratum.incident_segments)
        if stratum.z_fixed is not None:
            constraints.append((None,stratum.z_fixed))
        for multiplier,(segment,station) in zip(multipliers[body],constraints):
            if segment is not None and segment.kind != "tip_arc":
                raise ArithmeticError("non-tip junction Lagrangian constraint is unresolved")
            if body == "driven":
                if segment is not None:
                    r = continuation.sqrt_bounds(_interval_square(p[0])+_interval_square(p[1]))
                    numerator = _interval_dot(dp,dp)+_interval_dot(p,ddp)-_interval_square(_interval_dot(p,dp)/r)
                    hessian[0][0] += multiplier*numerator/r
                continue  # Physical driven axial constraints are linear in z.
            # The moving active constraint contributes to the loaded envelope
            # derivative: dV/dbeta = partial_beta(h-sum(lambda*c)), with the
            # same per-source ROOT multiplier fixed over this entire approach.
            if segment is None:
                sign = -1 if station == pair.placement.driver_face_mm[0] else 1
                approach += multiplier*sign*velocity[2]
            else:
                approach += multiplier*_interval_dot(er,velocity[:2])
            for i in range(2):
                for j in range(2):
                    if segment is None:
                        sign = -1 if station == pair.placement.driver_face_mm[0] else 1
                        constraint_hessian = sign*qtt[i][j][2]
                    else:
                        constraint_hessian = ((_interval_dot(qt[i][:2],qt[j][:2])
                                               -_interval_dot(er,qt[i][:2])*_interval_dot(er,qt[j][:2]))/radius
                                              +_interval_dot(er,qtt[i][j][:2]))
                    hessian[i][j] += multiplier*constraint_hessian
    # Positive principal minor/determinant avoids a coordinate-scale-dependent
    # Gershgorin refusal (t is dimensionless while z is measured in mm).
    cross = max(hessian[0][1].magnitude,hessian[1][0].magnitude)
    determinant = I.point(hessian[0][0].lower)*hessian[1][1].lower-I.point(cross)*cross
    trace = hessian[0][0]+hessian[1][1]
    lower = ((determinant/I.point(trace.upper)).lower
             if hessian[0][0].lower > 0 and determinant.lower > 0 and trace.upper > 0 else -math.inf)
    transversality = max(0.0,(direction*approach).lower)
    return continuation.ChartMinimumBound(
        chart.name,2,lower,outside_air_mm,transversality,
        lagrangian_beta_derivative=approach,objective_direction=direction,
    )
