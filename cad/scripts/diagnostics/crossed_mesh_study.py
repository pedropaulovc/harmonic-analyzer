"""Actual stock-form crossed-axis geometry, without native CAD imports.

The only tooth authority is ``stock_form_cutter.StockFormProfile``.  The
64T section is the exact transverse image of the normal-tool screw sweep,
not an ideal 64T involute and not a Tredgold equivalent gear.  Tooth zero is
on +X; the core's canonical gap therefore receives a half-pitch rotation.

The companion backlash study measures three-dimensional first contact.
Neither this geometry adapter nor an offline point cloud is a native
SolidWorks interference certificate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cone_line
import crank_mesh_geometry as geometry
import dt_crank_drive_gear_spec as gear64_spec
import dt_crank_pinion_spec as pinion_spec
from dt_cone_pivot_post_installation import GEAR_AXIS_SHIFT
from dt_cone_pivot_post_spec import CRANK_BOSS_START_Z
from stock_form_cutter import StockFormProfile

IN = 25.4
HELIX_DEG = gear64_spec.HELIX_ANGLE_DEG
GEAR64_CENTRE_STATION = (
    gear64_spec.LAYOUT_CENTRE_STATION + GEAR_AXIS_SHIFT
    + gear64_spec.CENTRE_SHIFT_NORTH
)
GEAR64_SEAT = np.asarray(cone_line.cone_station(GEAR64_CENTRE_STATION))
GEAR64_FACE = gear64_spec.FACE_WIDTH
PINION_FACE = pinion_spec.FACE_WIDTH
PINION_SHOULDER = pinion_spec.SHOULDER_LENGTH
PINION_TURNED_R = pinion_spec.TURNED_DIA / 2.0
X_CRANK, Y_CRANK = cone_line.X_CRANK, cone_line.Y_CRANK
Y_DRIVE = cone_line.Y_DRIVE
SIN_I, COS_I = cone_line.SIN_I, cone_line.COS_I
U = np.array([SIN_I, 0.0, COS_I])
EX = np.array([COS_I, 0.0, -SIN_I])
EY = np.array([0.0, 1.0, 0.0])
FRAME64 = np.column_stack((EX, EY, U))
R64, R16 = gear64_spec.PITCH_DIA / 2.0, pinion_spec.PITCH_DIA / 2.0
SLACK = math.hypot((GEAR64_SEAT[0] - X_CRANK) * COS_I, Y_CRANK - Y_DRIVE) - R64 - R16
PINION_TOOTH_Z = (
    cone_line.cone_station(cone_line.POST_STATION)[2] - CRANK_BOSS_START_Z
    + pinion_spec.SEAT_FEELER_MM + PINION_FACE / 2.0
)


class GapLookup:
    """Array adapter to the actual material oracle, with no ideal-N fallback.

    The name survives only as the diagnostic's material-query object: there
    is no quantised theta/r table, nor a second tooth-master implementation.
    Coordinates are tooth-centred, matching the native parts.
    """

    def __init__(self, profile: StockFormProfile):
        self.profile = profile
        self.gamma = profile.angular_pitch_rad
        self.ra = profile.blank_radius_mm
        self.rmin = profile.root_radius_min_mm

    def material(self, theta: np.ndarray, r: np.ndarray) -> np.ndarray:
        theta, r = np.broadcast_arrays(theta, r)
        return np.fromiter(
            (self.profile.contains_material(
                float(rr * math.cos(tt)), float(rr * math.sin(tt)),
                rotate_rad=self.gamma / 2.0,
            ) for tt, rr in zip(theta.flat, r.flat)),
            dtype=bool, count=theta.size,
        ).reshape(theta.shape)


def pinion_material(
    g16: GapLookup, theta: np.ndarray, r: np.ndarray, z: np.ndarray,
    *, face: float = PINION_FACE, shoulder: float = PINION_SHOULDER,
    turned_radius: float = PINION_TURNED_R,
) -> np.ndarray:
    """Actual teeth plus the independently turned north band and axial ends."""
    turned = (z > shoulder) & (r > turned_radius)
    return (z >= 0.0) & (z <= face) & ~turned & g16.material(theta, r)


def frame_axis(extra: float) -> tuple[float, float]:
    dx = (GEAR64_SEAT[0] - X_CRANK) * COS_I
    centre = R64 + R16 + extra
    return X_CRANK, Y_DRIVE + math.sqrt(centre * centre - dx * dx)


def seed_angle(axis: tuple[float, float]) -> float:
    """Raw tooth-in-gap datum, in radians, before measured phase correction."""
    dx = GEAR64_SEAT[0] - axis[0]
    dy = axis[1] - Y_DRIVE
    alpha64 = math.atan2(dy, dx * COS_I)
    alpha16 = math.atan2(dy, dx)
    pitch64 = 2.0 * math.pi / gear64_spec.TEETH
    delta64 = round(alpha64 / pitch64) * pitch64 - alpha64
    pitch16 = 2.0 * math.pi / pinion_spec.TEETH
    return (alpha16 + math.pi - delta64 * gear64_spec.TEETH / pinion_spec.TEETH - pitch16 / 2.0) % pitch16


@dataclass(frozen=True)
class Placement:
    """Physical crossed pose, including finite faces, shoulder and fit-up band."""

    extra_mm: float = SLACK
    yaw_deg: float = 0.0
    tilt_deg: float = 0.0
    cone_float_mm: float = 0.0
    pinion_north_mm: float = 0.0
    pinion_face_mm: float = PINION_FACE
    shoulder_mm: float = PINION_SHOULDER
    turned_radius_mm: float = PINION_TURNED_R
    gear_face_mm: float = GEAR64_FACE
    dx_mm: float = 0.0
    dy_mm: float = 0.0
    cone_dy_mm: float = 0.0

    @property
    def pinion_axis(self) -> tuple[float, float]:
        x, y = frame_axis(self.extra_mm)
        return x + self.dx_mm, y + self.dy_mm

    @property
    def pinion_frame(self) -> np.ndarray:
        return np.asarray(geometry.placement_record(asdict(self))["driver_frame"])

    @property
    def pinion_centre(self) -> np.ndarray:
        record = geometry.placement_record(asdict(self))
        return np.asarray(record["driver_origin_mm"])+np.asarray(record["driver_frame"])[:,2]*PINION_FACE/2

    @property
    def gear_centre(self) -> np.ndarray:
        return np.asarray(geometry.placement_record(asdict(self))["driven_origin_mm"])

    def to_pinion(self, world: np.ndarray) -> np.ndarray:
        record = geometry.placement_record(asdict(self))
        return (world-np.asarray(record["driver_origin_mm"])) @ np.asarray(record["driver_frame"])


def screw_point(
    profile: StockFormProfile, point: tuple[float, float], station: float,
    tooth: int, phase_rad: float, placement: Placement,
) -> np.ndarray:
    """Core transverse point -> exact 3D normal-tool screw-swept surface.

    ``point`` is already tooth-centred (material-sector convention). The
    real physical tooth count sets the indexing, never the virtual count.
    """
    twist = math.tan(math.radians(profile.helix_angle_deg)) / profile.pitch_radius_mm
    angle = tooth * profile.angular_pitch_rad + phase_rad + station * twist
    c, s = math.cos(angle), math.sin(angle)
    x, y = point
    return placement.gear_centre + FRAME64 @ np.array([c*x - s*y, s*x + c*y, station])
