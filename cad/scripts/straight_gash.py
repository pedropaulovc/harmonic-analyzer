"""Straight tooth spaces inclined to the gear axis, in mm and radians.

MHA-DT-07, the 64T crank-drive gear, has straight teeth inclined to its axis
(owner ruling 2026-11-10 on issue #2332, option A): a disc form cutter fed in
a straight line cuts each tooth space, and plain indexing moves it to the
next. Each tooth space is therefore a PRISM: the cutter's own form, which is
the gear's normal section where the cutter's centre plane crosses the blank
axis, followed along a straight tooth line inclined to the axis in that
space's tangent plane. It is not a screw: the section translates along the
tooth line instead of turning about the axis.

Frame: the part's gear axis is +Z and its SOUTH (collar) face is z = 0. For
the tooth space whose bisector at the crossing station points along
r = (cos a, sin a, 0), with t = (-sin a, cos a, 0) its counter-clockwise
tangent and beta the inclination:

- the tooth line is d = cos(beta) z + sin(beta) t: a RIGHT-hand tooth, whose
  azimuth advances counter-clockwise about +Z as z grows (the helix
  convention ``_gear._TWIST_CCW`` names);
- the cutter's normal section holds r and n = cos(beta) t - sin(beta) z;
- a normal-section point (X, Y), the cutter form's radial and tangential
  coordinates, sits at C + X r + Y n, with C = (0, 0, crossing) on the axis.

Its transverse section at height z is (X, Y/cos(beta) + (z - crossing)
tan(beta)) in the (r, t) frame: a uniform 1/cos(beta) stretch and a radius-
independent tangential shift. At the crossing station it is the screw model's
normal section to within microns (``test_straight_gash``); elsewhere it leans
against that screw by (1 - rho/R) of the shift at radius rho, zero on the
pitch circle.

No CAD or config dependencies: the builder (``_straight_gash_gear``), the part spec and the
mesh stack all read this one geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from stock_form_cutter import StockFormProfile

Vector = tuple[float, float, float]


def midface_gap_azimuth_rad(
    teeth: int,
    pitch_radius_mm: float,
    inclination_deg: float,
    crossing_z_mm: float,
    face_width_mm: float,
) -> float:
    """Crossing-station bisector of the seed space that centres a TOOTH on +X
    on the pitch circle at mid-face.

    The assembly phases the 16T against a 64T tooth at azimuth 0 at mid-face
    (``build_dt_drive_train_assembly``'s authored phase). A space's centre line
    at mid-face is its crossing-station bisector shifted (face/2 - crossing)
    tan(beta) along that bisector's tangent, so it meets the pitch circle
    asin(shift / R) further round; the seed space sits half a pitch past the
    tooth.
    """
    if type(teeth) is not int or teeth < 3:
        raise ValueError("tooth count must be an integer >= 3")
    shift = (face_width_mm / 2.0 - crossing_z_mm) * math.tan(math.radians(inclination_deg))
    if not abs(shift) < pitch_radius_mm:
        raise ValueError("mid-face shift must stay inside the pitch circle")
    return math.pi / teeth - math.asin(shift / pitch_radius_mm)


@dataclass(frozen=True)
class StraightGash:
    """One RIGHT-hand straight tooth space through a ``face_width_mm`` blank."""

    inclination_deg: float
    crossing_z_mm: float
    azimuth_rad: float
    face_width_mm: float
    blank_radius_mm: float

    def __post_init__(self) -> None:
        values = (
            self.inclination_deg,
            self.crossing_z_mm,
            self.azimuth_rad,
            self.face_width_mm,
            self.blank_radius_mm,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("straight tooth space needs finite values")
        if not 0.0 < self.inclination_deg < 45.0:
            raise ValueError("tooth-line inclination must lie strictly between 0 and 45 degrees")
        if not (self.face_width_mm > 0.0 and self.blank_radius_mm > 0.0):
            raise ValueError("face width and blank radius must be positive")
        if not 0.0 <= self.crossing_z_mm <= self.face_width_mm:
            raise ValueError("the cutter's centre plane must cross the axis within the face")

    @property
    def _beta(self) -> float:
        return math.radians(self.inclination_deg)

    @property
    def radial(self) -> Vector:
        return (math.cos(self.azimuth_rad), math.sin(self.azimuth_rad), 0.0)

    @property
    def tangent(self) -> Vector:
        return (-math.sin(self.azimuth_rad), math.cos(self.azimuth_rad), 0.0)

    @property
    def tooth_line(self) -> Vector:
        """Unit feed direction d, the prism's generator."""
        c, s = math.cos(self._beta), math.sin(self._beta)
        tx, ty, _ = self.tangent
        return (s * tx, s * ty, c)

    @property
    def section_tangential(self) -> Vector:
        """Unit n: the normal section's tangential axis (Y grows along it)."""
        c, s = math.cos(self._beta), math.sin(self._beta)
        tx, ty, _ = self.tangent
        return (c * tx, c * ty, -s)

    @property
    def crossing_point(self) -> Vector:
        return (0.0, 0.0, self.crossing_z_mm)

    def section_point(self, x_mm: float, y_mm: float) -> Vector:
        """Model point of normal-section point (X, Y) in the cutter's plane."""
        r, n = self.radial, self.section_tangential
        return tuple(
            o + x_mm * a + y_mm * b
            for o, a, b in zip(self.crossing_point, r, n, strict=True)
        )

    def transverse_offset_mm(self, y_mm: float, z_mm: float) -> float:
        """Tangential coordinate at height z of the tooth line through (X, Y)."""
        beta = self._beta
        return y_mm / math.cos(beta) + (z_mm - self.crossing_z_mm) * math.tan(beta)

    def point(self, x_mm: float, y_mm: float, z_mm: float) -> Vector:
        """Where the tooth line through normal-section point (X, Y) is at height z."""
        u = (z_mm - self.section_point(x_mm, y_mm)[2]) / math.cos(self._beta)
        return tuple(
            p + u * d
            for p, d in zip(self.section_point(x_mm, y_mm), self.tooth_line, strict=True)
        )

    def removed_volume_mm3(self, section: StockFormProfile, samples: int = 256) -> float:
        """Volume one tooth space takes out of the solid blank cylinder.

        ``section`` is the cutter form in its own plane: a STRAIGHT stock
        profile (``helix_angle_deg`` 0) whose blank circle reaches past every
        normal-section point the blank cylinder can hold. Its transverse
        section at height z is (X, Y/cos + (z - crossing) tan); dV = dz dX dY /
        cos. Below ``full`` every tooth line runs the whole face inside the
        cylinder, so that part is the clipped area times face/cos; the thin
        band above it integrates the cylinder's chord in closed form along z.
        """
        if section.helix_angle_deg != 0.0:
            raise ValueError("the cutter form must be supplied in its own (straight) plane")
        polygon = section.gap_polygon(samples)
        beta = self._beta
        c, t = math.cos(beta), math.tan(beta)
        ra, face, zc = self.blank_radius_mm, self.face_width_mm, self.crossing_z_mm
        y_reach = max(abs(y) for _, y in polygon)
        if math.hypot(ra, y_reach) >= section.blank_radius_mm:
            raise ValueError("the cutter form must reach past the blank cylinder at every Y")
        reach = y_reach / c + max(zc, face - zc) * t
        if reach >= ra:
            raise ValueError("the tooth line leaves the blank cylinder below the root")
        full = math.sqrt(ra * ra - reach * reach)
        if full <= min(x for x, _ in polygon):
            raise ValueError("the full-length band leaves no tooth space below it")
        volume = _clipped_area(polygon, full) * face / c

        def z_length(y: float, q: float) -> float:
            # |Y/c + (z - zc) t| <= q, intersected with 0 <= z <= face.
            low = zc + (-q - y / c) / t
            high = zc + (q - y / c) / t
            return max(0.0, min(high, face) - max(low, 0.0))

        steps = 400
        band = ra - full
        total = 0.0
        for i in range(steps + 1):
            x = full + band * i / steps
            q = math.sqrt(max(ra * ra - x * x, 0.0))
            row = 0.0
            for y0, y1 in _chords(polygon, x):
                n = 64
                values = [z_length(y0 + (y1 - y0) * k / n, q) for k in range(n + 1)]
                row += (y1 - y0) / n * (sum(values) - (values[0] + values[-1]) / 2.0)
            weight = 1 if i in (0, steps) else (4 if i % 2 else 2)
            total += weight * row
        volume += total * band / (3.0 * steps) / c
        return volume


def _clipped_area(polygon: tuple[tuple[float, float], ...], x_max: float) -> float:
    """Shoelace area of ``polygon`` cut to x <= ``x_max`` (one half-plane)."""
    clipped = []
    count = len(polygon)
    for index in range(count):
        current, following = polygon[index], polygon[(index + 1) % count]
        inside_now, inside_next = current[0] <= x_max, following[0] <= x_max
        if inside_now:
            clipped.append(current)
        if inside_now != inside_next:
            fraction = (x_max - current[0]) / (following[0] - current[0])
            clipped.append((x_max, current[1] + fraction * (following[1] - current[1])))
    area = 0.0
    for index in range(len(clipped)):
        (x0, y0), (x1, y1) = clipped[index], clipped[(index + 1) % len(clipped)]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0


def _chords(
    polygon: tuple[tuple[float, float], ...], x: float
) -> list[tuple[float, float]]:
    """Y intervals of the closed ``polygon`` on the line X = ``x``."""
    crossings = []
    count = len(polygon)
    for index in range(count):
        (x0, y0), (x1, y1) = polygon[index], polygon[(index + 1) % count]
        if (x0 <= x < x1) or (x1 <= x < x0):
            crossings.append(y0 + (x - x0) * (y1 - y0) / (x1 - x0))
    crossings.sort()
    if len(crossings) % 2:
        raise ValueError(f"open chord set at X = {x}")
    return list(zip(crossings[0::2], crossings[1::2], strict=True))
