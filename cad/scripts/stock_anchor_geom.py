r"""McMaster-Carr 9489T111 / 9490T1 -- stock routing eyebolts, pure geometry.

The two lower spring anchors: 9489T111 (#6-32, eye + hex nut, channel-spring
end) and 9490T1 (#10-24, open-eye, counter-spring end).  Both thread directly
into the summing lever, so both are production-trimmed to the seat they
engage -- see :func:`trim` -- and the first also drops its supplied nut.

Every number below is either a dimension the vendor's own SolidWorks tree
carries (harvest ``cad/out/reports/mcmaster-<sku>-dump.json``, written by
``diag_dump_part.py``), a vendor *equation* transcribed verbatim, or an exact
consequence of those.  Nothing is fitted, nothing is measured off a mesh and
nothing here touches COM: import it from a builder, a spec, an assembly
placement or a test with no SolidWorks session.

Vendor frame (kept verbatim by ``diag_build_9489T111.py`` /
``diag_build_9490T1.py`` -- the replicas need no COM remap; whoever places the
anchor applies the installation transform):

* eye centre at the ORIGIN, eye plane = model XY (the ``Front`` plane), eye
  axis = +Z;
* shank axis = the model -Y axis EXACTLY (no radial offset: the wire bends
  back onto the eye's own axis line), threaded end at the most negative Y;
* the eye's open end (9490T1) / wire tip (9489T111) sits at +X, so the eye
  opening faces away from the shank.

Vendor equations, transcribed (``Sketch1`` is each part's master layout):

=========================  =============================================
9489T111                   law
=========================  =============================================
``D1@Fillet1``             ``Thread OD / 4``        -> wire tip fillet
``D1@Chamfer1``            ``Thread OD * 0.13``     -> 45 deg end chamfer
``D1@Sketch8``             ``Shank Lg. * 0.2``      -> bend radius
``Nut Wd.@Sketch9``        ``Thread OD * 1.5``      -> across flats
``Nut Ht.@Boss-Extrude2``  ``Thread OD * 0.875``
``Offset@Boss-Extrude2``   ``Thread Lg. * 0.44``    -> nut seat from the end
``D3@Sketch10``            ``Pitch / 8``            -> bore chamfer
=========================  =============================================

=========================  =============================================
9490T1                     law
=========================  =============================================
``D1@Dome1``               ``Thread OD / 2``        -> hemispherical tip
=========================  =============================================

Shared by both (the repo's McMaster thread family):

* ``D3@Helix/Spiral1 = Pitch + Thread Lg.`` -- the helix is seeded on the
  thread datum (the shank's free end) and runs ONE PITCH past the advertised
  thread length, i.e. :data:`HELIX_REVOLUTION_LAW`;
* ``D1@Sketch4 = Pitch`` and ``D2@Sketch4 = Pitch / 8`` -- the UN cutter's
  sharp-V height and its root flat.  The cutter is capped at ``15P/16`` and
  parked ``7P/16`` past the datum in air (:func:`thread_cutter_profile_mm`).
  That park is not a fudge: the cutter's axial half width at the thread major
  radius is ``P/16 + (3 sqrt3 P / 8) tan30 = 7P/16`` exactly, so the first
  turn is fully formed in the end face and none of it is left uncut.

Length parameters
-----------------
``shank_length_mm`` is the FINISHED shank length measured from
:attr:`StockAnchor.advertised_shank_start_y_mm` -- the plane where the bend
becomes straight (on 9490T1 the thread starts there too; on 9489T111 a
3.175 mm neck follows) -- to the cut end:

    ``shank_end_y = advertised_shank_start_y - shank_length``   (:data:`SHANK_LENGTH_LAW`)

Trimming physically cuts the complete factory solid at the requested end
plane, then restores its 45-degree deburr.  The original helix, cutter and
surviving thread surfaces do not move.  :func:`trim` describes only that
physical removal; finished mass properties come from the resulting native
solid, not a re-seeded thread or an exact per-length mass claim.

Both anchors are trimmed in production, each to the seat it threads into
(9490T1 to the summation-anchor boss height, 9489T111 to its neck plus the
engaged depth of the coefficient plate), so neither protrudes past the summing
lever.
The cut is POST-PURCHASE: the vendor's ``Shank Lg.`` -- which on 9489T111
also drives the bend radius through ``D1@Sketch8`` -- keeps its stock value,
the stock solid is built from it, and only the free end is removed.  ORDERING
a shorter 9489T111 would be a different part (its bend would change);
CUTTING one is not.  :attr:`StockAnchor.min_shank_length_mm` keeps the cut
end in threaded metal, clear of that neck.  9489T111's other production
variation is the nut (built or not), and a trim requires it omitted: the
captive nut seats past any cut this project makes.

Cross-checks (analytic, no COM)
-------------------------------
Closing the geometry back onto the vendor's mass properties, using only the
values in this module:

* 9489T111 nut: hex ring 43.83141 - corner cones 0.315560 - bore chamfers
  0.110450 = 43.405397 mm^3 against the vendor's 43.405400 (5e-8 relative);
* 9489T111 bolt: shank 153.1896 + wire 255.0248 - tip fillet 1.4411 - end
  chamfer 1.0442 - groove 40.3922 = 365.3369 against 365.7780 (-0.12 %).  The
  residue is the groove's runout into the neck, where the cutter climbs out
  of the Dia 3.175 wire gradually and the per-mm law over-removes, plus
  ~0.12 mm^3 where the tube around the wire tip overlaps the tube around the
  bend (Weyl counts it twice; a 24M-sample Monte-Carlo union reads 254.90
  against 255.02);
* 9490T1: shank 1074.4346 - end chamfer 4.3355 - groove 270.7812 + wire
  586.1823 + dome 29.4260 = 1414.9262 against 1414.8951 (+0.0022 %).

Both groove figures net off :func:`end_chamfer_groove_overlap_mm3`, without
which they double-count the 45 deg deburr.  One more identity worth keeping:
because a helical groove at height y is the groove at y + dy turned by
2 pi dy / pitch, its cross-section does not vary along the shank, so
:func:`thread_groove_volume_per_mm_mm3` IS that cross-sectional area --
4.65432, against the 4.6559 mm^2 seam face the vendor's 9490T1 ships where
the groove meets the eye sweep (0.03 %, SolidWorks' own area tolerance).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "ANCHORS",
    "ANCHOR_9489T111",
    "ANCHOR_9490T1",
    "CUTTER_CENTRE_OFFSET_TURNS",
    "HELIX_REVOLUTION_LAW",
    "HELIX_START_ANGLE_DEG",
    "SHANK_LENGTH_LAW",
    "UN_CREST_WIDTH_TURNS",
    "UN_FLANK_HALF_ANGLE_DEG",
    "UN_ROOT_FLAT_TURNS",
    "BodyTruth",
    "HexNut",
    "PathArc",
    "PathLine",
    "ShankTrim",
    "StockAnchor",
    "anchor",
    "end_chamfer_groove_overlap_mm3",
    "eye_path_mm",
    "nut_bore_chamfer_contours_mm",
    "nut_corner_chamfer_contour_mm",
    "nut_hex_profile_mm",
    "thread_cutter_profile_mm",
    "thread_groove_volume_per_mm_mm3",
    "trim",
    "validate_shank_length_mm",
]

# --- the UN form the vendor cuts with one helical sweep -------------------
UN_FLANK_HALF_ANGLE_DEG = 30.0  # flank measured from the radial direction
UN_CREST_WIDTH_TURNS = 15.0 / 16.0  # cutter cap width / pitch
UN_ROOT_FLAT_TURNS = 1.0 / 8.0  # vendor "D2@Sketch4" = Pitch / 8
CUTTER_CENTRE_OFFSET_TURNS = 7.0 / 16.0  # cutter parked past the datum, in air
HELIX_START_ANGLE_DEG = 90.0  # vendor "D7@Helix/Spiral1"

HELIX_REVOLUTION_LAW = "revolutions = (thread_length + pitch) / pitch"
SHANK_LENGTH_LAW = "shank_end_y = advertised_shank_start_y - shank_length"

_TAN30 = math.tan(math.radians(UN_FLANK_HALF_ANGLE_DEG))


@dataclass(frozen=True, slots=True)
class BodyTruth:
    """Vendor mass properties of one solid body (or the whole part)."""

    volume_mm3: float
    area_mm2: float
    com_mm: tuple[float, float, float]
    face_count: int


@dataclass(frozen=True, slots=True)
class HexNut:
    """9489T111's captive hex nut: a hex ring with conical end chamfers.

    The bore is a plain cylinder at the thread major radius (the vendor does
    not thread it), coincident with the shank OD.
    """

    across_flats_mm: float
    across_corners_mm: float
    height_mm: float
    seat_y_mm: float  # the end nearest the shank's free end
    bore_dia_mm: float
    bore_chamfer_mm: float  # 45 deg, both ends
    corner_chamfer_from_axis_deg: float  # cone half-angle, both ends
    cut_outer_radius_mm: float  # vendor revolve-cut profile's air boundary
    truth: BodyTruth

    @property
    def top_y_mm(self) -> float:
        return self.seat_y_mm + self.height_mm

    @property
    def flat_radius_mm(self) -> float:
        return self.across_flats_mm / 2.0

    @property
    def corner_radius_mm(self) -> float:
        return self.across_corners_mm / 2.0

    @property
    def bore_radius_mm(self) -> float:
        return self.bore_dia_mm / 2.0


@dataclass(frozen=True, slots=True)
class PathArc:
    """Sweep-path arc in the eye plane (model XY), in sweep order."""

    centre_mm: tuple[float, float]
    start_mm: tuple[float, float]
    end_mm: tuple[float, float]
    ccw: bool

    @property
    def radius_mm(self) -> float:
        cx, cy = self.centre_mm
        return math.hypot(self.start_mm[0] - cx, self.start_mm[1] - cy)

    @property
    def sweep_deg(self) -> float:
        cx, cy = self.centre_mm
        a0 = math.atan2(self.start_mm[1] - cy, self.start_mm[0] - cx)
        a1 = math.atan2(self.end_mm[1] - cy, self.end_mm[0] - cx)
        turn = (a1 - a0) if self.ccw else (a0 - a1)
        return math.degrees(turn % (2.0 * math.pi))


@dataclass(frozen=True, slots=True)
class PathLine:
    """Straight sweep-path segment in the eye plane (model XY)."""

    start_mm: tuple[float, float]
    end_mm: tuple[float, float]

    @property
    def length_mm(self) -> float:
        return math.hypot(
            self.end_mm[0] - self.start_mm[0], self.end_mm[1] - self.start_mm[1]
        )


@dataclass(frozen=True, slots=True)
class ShankTrim:
    """Finished length, end plane and material length removed from stock."""

    shank_length_mm: float
    shank_end_y_mm: float
    removed_length_mm: float


@dataclass(frozen=True, slots=True)
class StockAnchor:
    """One stock anchor, in the vendor's own frame and units (mm, degrees)."""

    sku: str
    role: str
    description: str
    thread_size: str

    # --- frame ----------------------------------------------------------
    eye_centre_mm: tuple[float, float, float]
    eye_plane_normal: tuple[float, float, float]
    shank_axis_direction: tuple[float, float, float]
    shank_axis_point_mm: tuple[float, float, float]

    # --- eye ------------------------------------------------------------
    eye_mean_radius_mm: float
    eye_id_mm: float
    eye_od_mm: float
    eye_open_tip_mm: tuple[float, float, float]
    eye_open_tip_normal: tuple[float, float, float]
    eye_bend_tangency_mm: tuple[float, float]

    # --- wire / bend ----------------------------------------------------
    wire_dia_mm: float
    bend_radius_mm: float
    bend_centre_mm: tuple[float, float]

    # --- shank ----------------------------------------------------------
    advertised_shank_start_y_mm: float
    shank_length_mm: float
    neck_dia_mm: float | None
    neck_start_y_mm: float | None
    neck_end_y_mm: float | None

    # --- thread ---------------------------------------------------------
    thread_pitch_mm: float
    thread_major_dia_mm: float
    thread_length_mm: float
    thread_start_y_mm: float

    # --- end treatment --------------------------------------------------
    end_chamfer_mm: float  # 45 deg, off the shank's free end
    end_chamfer_flat_radius_mm: float
    tip_fillet_mm: float | None  # 9489T111's wire-tip round
    dome_height_mm: float | None  # 9490T1's hemispherical wire tip

    nut: HexNut | None
    truth: BodyTruth  # the part as the vendor ships it
    body_truth: tuple[tuple[str, BodyTruth], ...]  # per solid body

    # --- derived: radii -------------------------------------------------
    @property
    def wire_radius_mm(self) -> float:
        return self.wire_dia_mm / 2.0

    @property
    def thread_major_radius_mm(self) -> float:
        return self.thread_major_dia_mm / 2.0

    @property
    def thread_root_radius_mm(self) -> float:
        """UN root: the sharp-V truncated by ``0.75 * H`` (vendor cutter)."""
        h_sharp = self.thread_pitch_mm * math.sqrt(3.0) / 2.0
        return self.thread_major_radius_mm - 0.75 * h_sharp

    @property
    def thread_minor_dia_mm(self) -> float:
        return 2.0 * self.thread_root_radius_mm

    @property
    def thread_root_flat_mm(self) -> float:
        return self.thread_pitch_mm * UN_ROOT_FLAT_TURNS

    @property
    def thread_crest_width_mm(self) -> float:
        """Axial width of the cutter's cap (its widest, in air)."""
        return self.thread_pitch_mm * UN_CREST_WIDTH_TURNS

    @property
    def thread_cutter_top_radius_mm(self) -> float:
        """Where the 30 deg flanks reach the cutter's cap width."""
        return self.thread_root_radius_mm + (
            (self.thread_crest_width_mm - self.thread_root_flat_mm) / 2.0
        ) * math.sqrt(3.0)

    # --- derived: axial stations ----------------------------------------
    @property
    def shank_end_y_mm(self) -> float:
        """Thread datum: the vendor's free end, where the helix is seeded."""
        return self.advertised_shank_start_y_mm - self.shank_length_mm

    @property
    def thread_end_y_mm(self) -> float:
        return self.shank_end_y_mm

    @property
    def thread_cutter_centre_y_mm(self) -> float:
        return self.shank_end_y_mm - (CUTTER_CENTRE_OFFSET_TURNS * self.thread_pitch_mm)

    @property
    def thread_helix_revolutions(self) -> float:
        return (self.thread_length_mm + self.thread_pitch_mm) / self.thread_pitch_mm

    @property
    def thread_helix_height_mm(self) -> float:
        return self.thread_length_mm + self.thread_pitch_mm

    @property
    def thread_helix_end_y_mm(self) -> float:
        return self.shank_end_y_mm + self.thread_helix_height_mm

    @property
    def thread_runout_y_mm(self) -> float:
        """Where the groove finally leaves the metal (cutter cap, top end)."""
        return (
            self.thread_cutter_centre_y_mm
            + self.thread_helix_height_mm
            + (self.thread_crest_width_mm / 2.0)
        )

    @property
    def overall_length_mm(self) -> float:
        return self.eye_od_mm / 2.0 - self.shank_end_y_mm

    @property
    def unthreaded_shank_length_mm(self) -> float:
        """Shank above the thread start: 9489T111's straight neck, 0 on 9490T1."""
        return self.advertised_shank_start_y_mm - self.thread_start_y_mm

    @property
    def min_shank_length_mm(self) -> float:
        """Shortest shank this geometry still expresses: the unthreaded neck,
        plus the 45 deg deburr chamfer and one full thread turn below it.
        A shorter cut would land in the neck (or the bend), where the deburr
        revolve has no shank to cut."""
        return (
            self.unthreaded_shank_length_mm
            + self.end_chamfer_mm
            + 2.0 * self.thread_pitch_mm
        )


# --------------------------------------------------------------------------
# the two parts
# --------------------------------------------------------------------------
ANCHOR_9489T111 = StockAnchor(
    sku="9489T111",
    role="channel-spring lower anchor",
    description=(
        "Routing eyebolt with nut, #6-32, black-oxide steel "
        "(catalogue PDF; the vendor part file names no finish: "
        "Routing Eyebolt with Nut - Not for Lifting)"
    ),
    thread_size="#6-32",
    eye_centre_mm=(0.0, 0.0, 0.0),
    eye_plane_normal=(0.0, 0.0, 1.0),
    shank_axis_direction=(0.0, -1.0, 0.0),
    shank_axis_point_mm=(0.0, 0.0, 0.0),
    # Eye Dia. 6.35 (ID) / OD 12.7 -> mean radius = (ID + wire) / 2.
    eye_mean_radius_mm=4.7625,
    eye_id_mm=6.35,
    eye_od_mm=12.7,
    # Vendor Sketch8/Arc1 endpoints: the wire tip's cap centre, and the cap
    # normal = -(path tangent).  sin = -17/18, cos = sqrt(35)/18 exactly.
    eye_open_tip_mm=(1.565296, -4.497917, 0.0),
    eye_open_tip_normal=(-0.944444444, -0.328671099, 0.0),
    eye_bend_tangency_mm=(-2.116667, -4.266278),
    wire_dia_mm=3.175,
    bend_radius_mm=3.81,  # "D1@Sketch8" = Shank Lg. * 0.2
    bend_centre_mm=(-3.81, -7.679301),
    advertised_shank_start_y_mm=-6.35,  # eye OD tangent = where Shank Lg. starts
    shank_length_mm=19.05,  # "Shank Lg.@Sketch1"
    neck_dia_mm=3.175,  # bend + straight wire above the thread
    neck_start_y_mm=-6.35,
    neck_end_y_mm=-9.525,
    thread_pitch_mm=0.79375,
    thread_major_dia_mm=3.5052,
    thread_length_mm=15.875,
    thread_start_y_mm=-9.525,
    end_chamfer_mm=0.455676,  # "D1@Chamfer1" = Thread OD * 0.13
    end_chamfer_flat_radius_mm=1.296924,  # major radius - chamfer (45 deg)
    tip_fillet_mm=0.8763,  # "D1@Fillet1" = Thread OD / 4
    dome_height_mm=None,
    nut=HexNut(
        across_flats_mm=5.2578,  # Thread OD * 1.5
        across_corners_mm=6.071184,  # across flats * 2 / sqrt(3)
        height_mm=3.06705,  # Thread OD * 0.875
        seat_y_mm=-18.415,  # shank end + Thread Lg. * 0.44
        bore_dia_mm=3.5052,
        bore_chamfer_mm=0.099219,  # "D3@Sketch10" = Pitch / 8
        corner_chamfer_from_axis_deg=60.0,  # "D1@Sketch10"
        cut_outer_radius_mm=3.442284,  # vendor Sketch10's air boundary
        truth=BodyTruth(
            volume_mm3=43.40539957493869,
            area_mm2=114.71946844501473,
            com_mm=(0.0, -16.881475, 0.0),
            face_count=23,
        ),
    ),
    truth=BodyTruth(
        volume_mm3=409.1834,
        area_mm2=707.778,
        com_mm=(-0.034104, -6.990789, -0.000353),
        face_count=36,
    ),
    body_truth=(
        (
            "bolt",
            BodyTruth(
                volume_mm3=365.7779547278692,
                area_mm2=593.058514360966,
                com_mm=(
                    -0.03815087374561101,
                    -5.817101587362784,
                    -0.0003949488410413348,
                ),
                face_count=13,
            ),
        ),
        (
            "nut",
            BodyTruth(
                volume_mm3=43.40539957493869,
                area_mm2=114.71946844501473,
                com_mm=(0.0, -16.881475, 0.0),
                face_count=23,
            ),
        ),
    ),
)

ANCHOR_9490T1 = StockAnchor(
    sku="9490T1",
    role="counter-spring lower anchor",
    description=(
        "Zinc-plated steel routing eyebolt, #10-24, open eye "
        "(vendor title: Zinc-Plated Steel Routing Eyebolt-Not for Lifting)"
    ),
    thread_size="#10-24",
    eye_centre_mm=(0.0, 0.0, 0.0),
    eye_plane_normal=(0.0, 0.0, 1.0),
    shank_axis_direction=(0.0, -1.0, 0.0),
    shank_axis_point_mm=(0.0, 0.0, 0.0),
    eye_mean_radius_mm=6.38175,
    eye_id_mm=7.9375,
    eye_od_mm=17.5895,  # 2 * mean radius + wire
    # Vendor Sketch7/Arc1 start = the Dome1 source face's root, and that
    # planar cap's own normal, both read back natively.
    eye_open_tip_mm=(6.370279, -0.382459, 0.0),
    eye_open_tip_normal=(-0.059930187, -0.998202571, 0.0),
    eye_bend_tangency_mm=(-1.979307, -6.067048),
    wire_dia_mm=4.826,  # "A@Sketch1" = Thread OD: wire IS the shank stock
    # Solved, not read: the bend is tangent to the eye circle AND to the shank
    # axis, with its centre one (mean radius + wire radius) below the origin,
    # so r = wire_r + wire_r^2 / (2 * mean radius) -- 2.8691890547, which is
    # the vendor's sketch radius (2.869189) to 5e-8.
    bend_radius_mm=2.8691890547263683,
    bend_centre_mm=(-2.8691890547263683, -8.79475),
    advertised_shank_start_y_mm=-8.79475,  # = -(mean radius + wire radius)
    shank_length_mm=58.7375,  # "Thread Lg.@Sketch1": threaded end to end
    neck_dia_mm=None,
    neck_start_y_mm=None,
    neck_end_y_mm=None,
    thread_pitch_mm=1.0583333333333333,  # vendor 1.058333 = 25.4 / 24
    thread_major_dia_mm=4.826,
    thread_length_mm=58.7375,
    thread_start_y_mm=-8.79475,
    end_chamfer_mm=0.801976,  # Cut-Extrude1: 45 deg draft to r 1.611024
    end_chamfer_flat_radius_mm=1.611024,
    tip_fillet_mm=None,
    dome_height_mm=2.413,  # "D1@Dome1" = Thread OD / 2 -> hemisphere
    nut=None,
    truth=BodyTruth(
        volume_mm3=1414.895079304684,
        area_mm2=1871.2849151993785,
        com_mm=(
            -0.3689212075353452,
            -21.159769419492225,
            -0.00031741799407240546,
        ),
        face_count=10,
    ),
    body_truth=(
        (
            "eyebolt",
            BodyTruth(
                volume_mm3=1414.895079304684,
                area_mm2=1871.2849151993785,
                com_mm=(
                    -0.3689212075353452,
                    -21.159769419492225,
                    -0.00031741799407240546,
                ),
                face_count=10,
            ),
        ),
    ),
)

ANCHORS: dict[str, StockAnchor] = {
    ANCHOR_9489T111.sku: ANCHOR_9489T111,
    ANCHOR_9490T1.sku: ANCHOR_9490T1,
}


def anchor(sku: str) -> StockAnchor:
    """Return one stock anchor, failing loud if it is not one of ours."""
    try:
        return ANCHORS[sku]
    except KeyError as exc:
        raise KeyError(f"not a stock spring anchor: {sku}") from exc


# --------------------------------------------------------------------------
# thread: cutter, helix seed and the per-length laws
# --------------------------------------------------------------------------
def thread_cutter_profile_mm(
    a: StockAnchor,
) -> tuple[
    tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]
]:
    """The vendor's UN cutter as ``(radius, y)`` corners, sweep-ready.

    A 60 deg V truncated to a ``P/8`` root flat at the root radius and capped
    at ``15P/16`` in air, centred ``7P/16`` past the thread datum.  That park
    is exact rather than chosen: the profile's axial half width at the thread
    major radius is ``P/16 + (3 sqrt3 P / 8) tan30 = 7P/16``, so the cutter's
    leading edge meets the major radius exactly in the datum plane and the
    first turn is fully formed in the end face.  Read back verbatim off
    9489T111's Sketch4: (1.795563, -25.375195) (1.237044, -25.697656)
    (1.237044, -25.796875) (1.795563, -26.119336).
    """
    cy = a.thread_cutter_centre_y_mm
    top_r = a.thread_cutter_top_radius_mm
    root_r = a.thread_root_radius_mm
    half_cap = a.thread_crest_width_mm / 2.0
    half_flat = a.thread_root_flat_mm / 2.0
    return (
        (top_r, cy + half_cap),
        (root_r, cy + half_flat),
        (root_r, cy - half_flat),
        (top_r, cy - half_cap),
    )


def thread_groove_volume_per_mm_mm3(
    a: StockAnchor, clip_radius_mm: float | None = None
) -> float:
    """Metal the groove removes per mm of threaded length -- EXACT.

    A screw motion is volume preserving and, at any fixed height and radius,
    the groove occupies a ``2 * w(r) / pitch`` fraction of the circumference
    regardless of phase, so the removal per unit length is the revolved
    integral ``(2 pi / P) * int 2 w(r) * r dr`` with no helix correction and
    no dependence on where the window starts.

    ``clip_radius_mm`` clips the cut to a thinner section than the thread
    major radius (9489T111's groove runs one pitch past the shank, into the
    Ø3.175 neck).
    """
    root_r = a.thread_root_radius_mm
    hi = a.thread_major_radius_mm
    if clip_radius_mm is not None:
        hi = min(hi, clip_radius_mm)
    if hi <= root_r:
        return 0.0
    lead = a.thread_root_flat_mm / 2.0 - _TAN30 * root_r
    return (4.0 * math.pi / a.thread_pitch_mm) * (
        lead * (hi * hi - root_r * root_r) / 2.0 + _TAN30 * (hi**3 - root_r**3) / 3.0
    )


# --------------------------------------------------------------------------
# trimming (both anchors, post-purchase)
# --------------------------------------------------------------------------
def validate_shank_length_mm(a: StockAnchor, shank_length_mm: float | None) -> float:
    """Resolve and range-check a finished shank length in mm."""
    if shank_length_mm is None:
        return a.shank_length_mm
    length = float(shank_length_mm)
    if length > a.shank_length_mm:
        raise ValueError(
            f"{a.sku} shank_length_mm {length} exceeds the stock "
            f"{a.shank_length_mm} -- stock cannot be lengthened"
        )
    if length < a.min_shank_length_mm:
        raise ValueError(
            f"{a.sku} shank_length_mm {length} is below the geometric floor "
            f"{a.min_shank_length_mm:.6f} (unthreaded neck + deburr chamfer + "
            f"one full turn)"
        )
    return length


def end_chamfer_groove_overlap_mm3(a: StockAnchor) -> float:
    """Metal the 45 deg end chamfer and the thread groove BOTH claim -- exact.

    Whichever is cut first, the finished solid is the same, but the two
    removals are not additive: at height ``t`` above the end face the chamfer
    has taken everything beyond radius ``end_chamfer_flat_radius + t``, and
    the groove's share of that is the part of its per-mm cross-section
    outside that radius.  Integrating over the chamfer's height (the 45 deg
    cone reaches the thread major exactly at its top) closes both parts'
    analytic volumes: 0.693877 mm^3 on 9489T111, 2.601966 on 9490T1.
    """
    root_r = a.thread_root_radius_mm
    major_r = a.thread_major_radius_mm
    low = a.end_chamfer_flat_radius_mm
    total = thread_groove_volume_per_mm_mm3(a)
    # Below the root the groove is entirely outside the cone.
    overlap = max(0.0, min(root_r, major_r) - low) * total
    start = max(low, root_r)
    if start >= major_r:
        return overlap
    lead = a.thread_root_flat_mm / 2.0 - _TAN30 * root_r
    k = 4.0 * math.pi / a.thread_pitch_mm

    def _int_groove(u: float) -> float:
        """Integral of the clipped groove law from the root radius to u."""
        return k * (
            lead * (u**3 / 3.0 - root_r * root_r * u) / 2.0
            + _TAN30 * (u**4 / 4.0 - root_r**3 * u) / 3.0
        )

    return (
        overlap
        + total * (major_r - start)
        - (_int_groove(major_r) - _int_groove(start))
    )


def trim(a: StockAnchor, shank_length_mm: float | None = None) -> ShankTrim:
    """Describe a physical cut of the factory shank, without moving its thread.

    The native builder makes the complete stock anchor before cutting at the
    returned end plane and restoring the deburr.  Its finished volume, area
    and centre of mass must be measured on that solid.
    """
    length = validate_shank_length_mm(a, shank_length_mm)
    return ShankTrim(
        shank_length_mm=length,
        shank_end_y_mm=a.advertised_shank_start_y_mm - length,
        removed_length_mm=a.shank_length_mm - length,
    )


# --------------------------------------------------------------------------
# eye: the vendor's sweep path
# --------------------------------------------------------------------------
def eye_path_mm(a: StockAnchor) -> tuple[PathArc | PathLine, ...]:
    """The wire centreline, tip first, as the vendor sketched it (model XY).

    9489T111: eye arc -> bend arc -> straight neck down to the thread start.
    9490T1:   eye arc -> bend arc, which lands tangent on the shank axis at
    the thread start (no straight neck).
    """
    tip = (a.eye_open_tip_mm[0], a.eye_open_tip_mm[1])
    segments: list[PathArc | PathLine] = [
        PathArc(
            centre_mm=(a.eye_centre_mm[0], a.eye_centre_mm[1]),
            start_mm=tip,
            end_mm=a.eye_bend_tangency_mm,
            ccw=True,
        ),
        PathArc(
            centre_mm=a.bend_centre_mm,
            start_mm=a.eye_bend_tangency_mm,
            end_mm=(0.0, a.bend_centre_mm[1]),
            ccw=False,
        ),
    ]
    if a.bend_centre_mm[1] > a.thread_start_y_mm:
        segments.append(
            PathLine(
                start_mm=(0.0, a.bend_centre_mm[1]),
                end_mm=(0.0, a.thread_start_y_mm),
            )
        )
    return tuple(segments)


# --------------------------------------------------------------------------
# nut (9489T111)
# --------------------------------------------------------------------------
def nut_hex_profile_mm(nut: HexNut) -> tuple[tuple[float, float], ...]:
    """The nut's hexagon as six ``(x, z)`` vertices in its own section plane.

    Vendor Sketch9: flats normal to ±X (vertices on the ±Z meridian), so the
    hex reads across-flats along X.
    """
    r = nut.corner_radius_mm
    return tuple(
        (r * math.sin(math.radians(60.0 * i)), r * math.cos(math.radians(60.0 * i)))
        for i in range(6)
    )


def nut_corner_chamfer_contour_mm(nut: HexNut) -> tuple[tuple[float, float], ...]:
    """Vendor Sketch10's outer revolve-cut contour, as ``(radius, y)``.

    One closed loop that carries BOTH end chamfers: a band from the
    across-flats radius out to the profile's air boundary, notched by the two
    60 deg cones that break the hex corners.
    """
    a_f = nut.flat_radius_mm
    corner = nut.corner_radius_mm
    depth = (corner - a_f) / math.tan(math.radians(nut.corner_chamfer_from_axis_deg))
    bot, top = nut.seat_y_mm, nut.top_y_mm
    return (
        (a_f, top),
        (nut.cut_outer_radius_mm, top),
        (nut.cut_outer_radius_mm, bot),
        (a_f, bot),
        (corner, bot + depth),
        (corner, top - depth),
    )


def nut_bore_chamfer_contours_mm(
    nut: HexNut,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """The two 45 deg bore chamfers as ``(radius, y)`` triangles.

    The vendor cuts these with the same revolve as the corner chamfers, from
    a contour whose inner edge runs one chamfer INSIDE the bore (air, for
    them, because their cut is scoped to the nut body).  Here the inner edge
    sits exactly on the bore, which removes the same metal without reaching
    the shank that shares that cylinder.
    """
    r = nut.bore_radius_mm
    c = nut.bore_chamfer_mm
    bot, top = nut.seat_y_mm, nut.top_y_mm
    return (
        ((r, bot), (r + c, bot), (r, bot + c)),
        ((r, top), (r + c, top), (r, top - c)),
    )
