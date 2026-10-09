"""Exact finite RootArc material intervals; no ideal actual-N root circle.

The driver is straight. Driven screw sections use the engine's existing
normal-section transform before this angular material query. Root arcs bound
collision only: they are never eligible working/contact-coverage branches.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sys
from typing import Protocol

from stock_form_cutter import StockFormProfile


class FlankInverse(Protocol):
    error_rad: float

    def branch_range(self, lower_radius: float, upper_radius: float) -> tuple[float,float]: ...


def intersect_intervals(left, right) -> tuple[tuple[float,float], ...]:
    return tuple((max(a,c),min(b,d)) for a,b in left for c,d in right
                 if max(a,c) < min(b,d))


def merge_intervals(intervals) -> tuple[tuple[float,float], ...]:
    merged = []
    for lo,hi in sorted((float(a),float(b)) for a,b in intervals if a < b):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0],max(merged[-1][1],hi))
        else:
            merged.append((lo,hi))
    return tuple(merged)


@dataclass(frozen=True)
class AngularMaterialBounds:
    """Inner and outer enclosures of FREE angular components, in radians."""
    inner: tuple[tuple[float,float], ...]
    outer: tuple[tuple[float,float], ...]
    radial_interval_mm: tuple[float,float]
    reaches_root_strip: bool
    root_boundary_angle_range_rad: tuple[float,float] | None
    root_is_carrying: bool = False


class RootAngularDomain:
    """Finite translated RootArc, paid through tangencies and root joins.

    Radius variation is enclosed using exact monotone RootArc endpoints, not
    a derivative at a square-root tangency. The flank inverse is the existing
    core-qualified angular interpolant including its separate error bound.
    """
    def __init__(self, profile: StockFormProfile, flank_inverse: FlankInverse):
        if profile.helix_angle_deg != 0.0:
            raise ValueError("RootAngularDomain driver must be straight; driven screw sections are transformed by the contact engine")
        self.profile = profile
        self.flank = flank_inverse
        self.shift = profile.radial_translation_mm
        self.tool_root = profile.template.root_radius_mm
        self.alpha = profile.root_half_angle_rad
        self.half_pitch = profile.angular_pitch_rad/2
        self.root_min = profile.root_radius_min_mm
        self.root_max = profile.root_radius_max_mm
        if self.shift < 0 and abs(self.shift) >= self.tool_root:
            raise ValueError("negative RootArc translation reaches the tool root origin; no single finite polar arc")
        if self.shift >= 0 and self.tool_root+self.shift*math.cos(self.alpha) <= 0:
            raise ValueError("finite RootArc has a polar fold")
        self.end_angle = math.atan2(*reversed(profile.root_point(self.alpha)))
        if not 0 <= self.end_angle < self.half_pitch:
            raise ValueError("finite RootArc crosses the physical pitch seam")

    def root_angle(self, radius: float) -> float:
        """Exact source RootArc intersection clipped to its ACTUAL arc span."""
        if self.shift == 0:
            return self.end_angle
        r = min(self.root_max,max(self.root_min,float(radius)))
        # Circle/ray intersection expressed in reference-arc angle. Factored
        # differences avoid subtracting nearly equal squared root radii.
        cosine = ((r-self.tool_root)*(r+self.tool_root)-self.shift*self.shift)/(2*self.shift*self.tool_root)
        reference = min(self.alpha,max(0.0,math.acos(min(1.0,max(-1.0,cosine)))))
        x,y = self.profile.root_point(reference)
        return math.atan2(y,x)

    def _paid(self, lo: float, hi: float) -> tuple[float,float,float]:
        if not math.isfinite(lo) or not math.isfinite(hi) or lo < 0 or lo > hi:
            raise ValueError("finite ordered nonnegative radial interval required")
        guard = self.profile.geometry_error_bound_mm+64*sys.float_info.epsilon*(1+hi+self.tool_root+abs(self.shift))
        return max(0.0,lo-guard),hi+guard,guard

    def _root_range(self, lo: float, hi: float, guard: float) -> tuple[float,float]:
        if self.shift == 0:
            return 0.0,self.end_angle
        values = (self.root_angle(lo),self.root_angle(hi))
        angular = math.asin(min(1.0,guard/max(self.root_min-guard,guard)))
        return max(0.0,min(values)-angular),min(self.end_angle,max(values)+angular)

    def _central(self, half: float) -> tuple[tuple[float,float], ...]:
        half = min(self.half_pitch,max(0.0,half))
        return ((-half,half),) if half > 0 else ()

    def _outside(self, inner: float, outer: float) -> tuple[tuple[float,float], ...]:
        lo,hi = max(0.0,inner),min(self.half_pitch,outer)
        return ((-hi,-lo),(lo,hi)) if hi > lo else ()

    def root_only_bounds(self, lower_radius: float, upper_radius: float) -> AngularMaterialBounds:
        """Free components imposed ONLY by actual floor/lobe material."""
        lo,hi,guard = self._paid(lower_radius,upper_radius)
        full = ((-self.half_pitch,self.half_pitch),)
        reaches = lo <= self.root_max and hi >= self.root_min
        root_range = self._root_range(lo,hi,guard) if reaches else None
        if hi < self.root_min:
            return AngularMaterialBounds((),(),(lo,hi),reaches,root_range)
        if lo > self.root_max:
            return AngularMaterialBounds(full,full,(lo,hi),False,None)
        if self.shift == 0:
            return AngularMaterialBounds(full if lo>self.root_max else (),
                                         full if hi>self.root_min else (),
                                         (lo,hi),reaches,root_range)
        bmin,bmax = self._root_range(lo,hi,guard)
        if self.shift > 0:
            inner = self._outside(bmax,self.half_pitch) if lo>self.root_min else ()
            outer = full if hi>self.root_max else self._outside(bmin,self.half_pitch)
        else:
            inner = self._central(bmin) if lo>self.root_min else ()
            outer = full if hi>self.root_max else self._central(bmax)
        return AngularMaterialBounds(inner,outer,(lo,hi),reaches,root_range)

    def bounds(self, lower_radius: float, upper_radius: float) -> AngularMaterialBounds:
        """Full finite gap: root material AND real radial/involute branches."""
        lo,hi,guard = self._paid(lower_radius,upper_radius)
        full = ((-self.half_pitch,self.half_pitch),)
        blank = self.profile.blank_radius_mm
        reaches = lo <= self.root_max and hi >= self.root_min
        root_range = self._root_range(lo,hi,guard) if reaches else None
        if lo > blank:
            return AngularMaterialBounds(full,full,(lo,hi),False,None)
        if hi < self.root_min:
            return AngularMaterialBounds((),(),(lo,hi),reaches,root_range)
        high = min(hi,blank)
        branch_start = math.hypot(*self.profile.root_point(self.alpha))
        a_range = None
        if high >= branch_start:
            a_range = self.flank.branch_range(max(lo,branch_start),high)
        error = self.flank.error_rad
        if self.shift > 0:
            a_min,a_max = a_range if a_range is not None else (0.0,0.0)
            bmin,bmax = self._root_range(lo,high,guard)
            inner = (self._central(a_min-error) if lo>self.root_max else
                     self._outside(bmax,a_min-error) if lo>self.root_min else ())
            outer = (self._central(a_max+error) if high>self.root_max else
                     self._outside(bmin,a_max+error))
        elif self.shift < 0:
            pieces_min,pieces_max = [],[]
            if lo <= self.root_max:
                bmin,bmax = self._root_range(lo,min(high,self.root_max),guard)
                pieces_min.append(bmin)
                pieces_max.append(bmax)
            if a_range is not None:
                pieces_min.append(max(0.0,a_range[0]-error))
                pieces_max.append(a_range[1]+error)
            inner = self._central(min(pieces_min,default=0.0)) if lo>self.root_min else ()
            outer = self._central(max(pieces_max,default=0.0))
        else:
            a_min,a_max = a_range if a_range is not None else (0.0,0.0)
            inner = self._central(a_min-error) if lo>self.root_max else ()
            outer = self._central(a_max+error)
        if hi > blank:
            outer = full
        return AngularMaterialBounds(inner,outer,(lo,hi),reaches,root_range)

    def offset_bounds(self, lower_radius: float, upper_radius: float,
                      centre_angle_rad: float, angle_error_rad: float,
                      *, root_only: bool = False) -> AngularMaterialBounds:
        """Periodically shift gap components to the engine's inverse offset."""
        if not math.isfinite(centre_angle_rad) or not math.isfinite(angle_error_rad) or angle_error_rad < 0:
            raise ValueError("finite angle and nonnegative angular enclosure required")
        domain = (self.root_only_bounds if root_only else self.bounds)(lower_radius,upper_radius)
        pitch,h = self.profile.angular_pitch_rad,self.half_pitch
        def shifted(components,inner):
            if any(hi-lo >= pitch for lo,hi in components):
                return ((-h,h),)
            # Join the periodic material topology BEFORE angular erosion.
            # A pitch seam is not a physical facet or an extra root lobe.
            periodic = merge_intervals((lo+k*pitch,hi+k*pitch)
                                       for lo,hi in components for k in (-1,0,1))
            centre = (centre_angle_rad+h)%pitch-h
            result = []
            for lo,hi in periodic:
                a = lo-centre+(angle_error_rad if inner else -angle_error_rad)
                b = hi-centre+(-angle_error_rad if inner else angle_error_rad)
                if a >= b:
                    continue
                if b-a >= pitch:
                    return ((-h,h),)
                left,right = max(-h,a),min(h,b)
                if left < right:
                    result.append((left,right))
            return merge_intervals(result)
        return AngularMaterialBounds(shifted(domain.inner,True),shifted(domain.outer,False),
            domain.radial_interval_mm,domain.reaches_root_strip,domain.root_boundary_angle_range_rad)
