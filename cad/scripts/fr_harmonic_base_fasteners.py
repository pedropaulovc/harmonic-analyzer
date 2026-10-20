"""Pure retained-material and fastener contracts for the harmonic base.

Deck holes are native through taps. Depths below are material intervals measured
DOWN from the finished deck, not drilling/thread-depth requirements. The native
builder independently reads those intervals back before and after cutting.
Horizontal frame cross taps retain their original blind manufacturing contract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import fr_nameplate_spec
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from dt_arbor_pedestal_spec import FOOT_HEIGHT as PEDESTAL_FLANGE_THICKNESS
from dt_vn_pedestal_hold_down_screw_spec import SHANK_LEN as PEDESTAL_SCREW_LEN
from fr_vn_lag_screw_spec import (
    BEARING_OFFSET as HOLD_DOWN_BEARING_OFFSET,
    SHANK_LEN as HOLD_DOWN_SCREW_LEN,
)
from fr_rocker_arm_support_section_spec import FOOT_THICKNESS as SUPPORT_FOOT_THICKNESS
from fr_frame_attachment_spec import CASTING_FULL_THREAD_DEPTH, CASTING_TAP_DRILL_DEPTH
from fr_harmonic_base_spec import (
    COLUMN_SOCKET_XZ, CROSS_TAP_LUG_BOTTOM_Y, CROSS_TAP_LUG_INNER_X,
    CROSS_TAP_LUG_LENGTH, CROSS_TAP_LUG_WIDTH, DECK_HALF_X, DECK_HALF_Z,
    POCKET_CEILING_Y, POCKET_CORNER_FILLET_R, POCKET_HALF_X,
    POCKET_HALF_Z, RIB_RELIEF, RIB_THICKNESS, SOCKET_BOSS_DIA, STACK_HEIGHT,
)

IN = 25.4


def title_block_band_mm(kind: str) -> float:
    """Use the printed millimetre limit, not its rounded inch equivalent."""
    return float(str(_config.title_block(kind)["display"]).lstrip("±"))


EDGE_BREAK_MAX_MM = max(
    float(_config.title_block("edge_break")[key])
    for key in ("radius_mm", "chamfer_max_mm")
)
# The deck elevation is GreenTopHeight + DeckRise; the ceiling is PocketDepth.
# All three print .X independently. Skin is currently a reference difference,
# not a directly toleranced skin dimension. Do not book only one of these bands.
DECK_HEIGHT_BAND_MM = 2.0 * title_block_band_mm("linear_1pl")
POCKET_CEILING_BAND_MM = title_block_band_mm("linear_1pl")

BASE_CROSS_TAP_SPEC = HoleSpec(
    "tapped_bottoming", "#10-32", end="blind", depth_mm=CASTING_TAP_DRILL_DEPTH,
    thread_class="2B", overrides_mm={"ThreadDepth": CASTING_FULL_THREAD_DEPTH},
)
BASE_CROSS_TAP_DRILL_DIA = TAP_DRILL_MM[BASE_CROSS_TAP_SPEC.size]
if CASTING_TAP_DRILL_DEPTH - (
    CASTING_FULL_THREAD_DEPTH + title_block_band_mm("linear_2pl")
) < 2.0 * IN / 32.0 - 1e-9:
    raise AssertionError("base cross tap lacks two-pitch bottoming-tap lead")

HOLD_DOWN_THREAD = "1/4-20"
HOLD_DOWN_THREAD_CLASS = "2B"
HOLD_DOWN_PITCH = IN / 20.0
# Physical insertion from the real under-head washer bearing plane. A through
# joint's useful engagement is the overlap below, not this insertion length.
HOLD_DOWN_ENGAGEMENT = (
    HOLD_DOWN_SCREW_LEN - SUPPORT_FOOT_THICKNESS - HOLD_DOWN_BEARING_OFFSET
)
HOLD_DOWN_SEAT_SPEC = HoleSpec("tapped", HOLD_DOWN_THREAD, thread_class=HOLD_DOWN_THREAD_CLASS)
HOLD_DOWN_TAP_DRILL_DIA = TAP_DRILL_MM[HOLD_DOWN_THREAD]
PEDESTAL_SCREW_ENGAGEMENT = PEDESTAL_SCREW_LEN - PEDESTAL_FLANGE_THICKNESS
NAMEPLATE_SCREW_XZ = fr_nameplate_spec.MOUNT_HOLE_XZ
NAMEPLATE_SEAT_SPEC = HoleSpec("tapped_bottoming", "#4-40", thread_class="2B")

# Retained footprint primitives, shared with the builder's exact sketch shapes.
# (kind, coordinates..., lower Y). Every primitive joins the pocket ceiling.
_RETAINED_REGIONS = (
    ("rect", -POCKET_HALF_X, POCKET_HALF_X, -RIB_THICKNESS / 2,
     RIB_THICKNESS / 2, RIB_RELIEF),
    ("rect", -RIB_THICKNESS / 2, RIB_THICKNESS / 2, -POCKET_HALF_Z,
     POCKET_HALF_Z, RIB_RELIEF),
    *(("disc", x, z, SOCKET_BOSS_DIA / 2, 0.0) for x, z in COLUMN_SOCKET_XZ),
    *(("rect", *sorted((math.copysign(CROSS_TAP_LUG_INNER_X, x),
                       math.copysign(CROSS_TAP_LUG_INNER_X + CROSS_TAP_LUG_WIDTH, x))),
       *sorted((z - math.copysign(CROSS_TAP_LUG_LENGTH, z), z)),
       CROSS_TAP_LUG_BOTTOM_Y) for x, z in COLUMN_SOCKET_XZ),
)


def _inside_polygon(x: float, z: float, vertices: tuple) -> bool:
    inside = False
    for (ax, az), (bx, bz) in zip(vertices, (*vertices[1:], vertices[0]), strict=True):
        if (az > z) != (bz > z) and x < ax + (z - az) * (bx - ax) / (bz - az):
            inside = not inside
    return inside


def _round_junction_contains(
    x: float, z: float, cx: float, cz: float, radius: float,
    *, along_x: bool, wall: float, air_sign: float, fillet_r: float,
) -> bool:
    """Exact added patch at a disc/straight-face reentrant junction.

    Local v points from the disc centre towards the wall (air is below it).
    The patch is the centre/fillet-centre/wall-tangent/corner polygon less
    both circles. Both tangent branches are considered, then clipped by the
    caller's finite adjoining face. Existing solid is accounted separately.
    """
    if fillet_r <= 0.0:
        return False
    across, along = (z - cz, x - cx) if along_x else (x - cx, z - cz)
    origin_across = cz if along_x else cx
    inset = -air_sign * (wall - origin_across)
    v = -air_sign * across
    if abs(inset) >= radius:
        return False
    cv = inset - fillet_r
    cu = math.sqrt((radius + fillet_r) ** 2 - cv ** 2)
    wu = math.sqrt(radius ** 2 - inset ** 2)
    u = abs(along)
    polygon = ((0.0, 0.0), (cu, cv), (cu, inset), (wu, inset))
    return (
        _inside_polygon(u, v, polygon)
        and u * u + v * v >= radius * radius
        and (u - cu) ** 2 + (v - cv) ** 2 >= fillet_r ** 2
    )


def _fillet_bottoms(x: float, z: float, radius: float) -> list[float]:
    bottoms = []
    if radius <= 0.0:
        return bottoms
    half = RIB_THICKNESS / 2.0
    # Each square reentrant corner adds the square outside its tangent circle.
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            for corner_x, corner_z, air_x, air_z in (
                (sx * POCKET_HALF_X, sz * half, -sx, sz),
                (sx * half, sz * POCKET_HALF_Z, sx, -sz),
                (sx * half, sz * half, sx, sz),
            ):
                u, v = (x - corner_x) * air_x, (z - corner_z) * air_z
                if 0 <= u <= radius and 0 <= v <= radius and (
                    (u - radius) ** 2 + (v - radius) ** 2 >= radius ** 2
                ):
                    bottoms.append(RIB_RELIEF)
    for cx, cz in COLUMN_SOCKET_XZ:
        sx, sz = math.copysign(1.0, cx), math.copysign(1.0, cz)
        # Socket to end/side walls. End junction is hidden by the lug above
        # its bottom; material below is still present down to the underside.
        for along_x, wall, air_sign in (
            (False, sx * POCKET_HALF_X, -sx),
            (True, sz * POCKET_HALF_Z, -sz),
        ):
            if _round_junction_contains(
                x, z, cx, cz, SOCKET_BOSS_DIA / 2,
                along_x=along_x, wall=wall, air_sign=air_sign, fillet_r=radius,
            ):
                bottoms.append(0.0)
        inner_z = cz - sz * CROSS_TAP_LUG_LENGTH
        u, v = (x - sx * POCKET_HALF_X) * -sx, (z - inner_z) * -sz
        if 0 <= u <= radius and 0 <= v <= radius and (
            (u - radius) ** 2 + (v - radius) ** 2 >= radius ** 2
        ):
            bottoms.append(CROSS_TAP_LUG_BOTTOM_Y)
        # Disc to the lug's inner X face, and to its inner Z face if crossed.
        for along_x, wall, air_sign, lo, hi in (
            (False, sx * CROSS_TAP_LUG_INNER_X, -sx, min(inner_z, cz), max(inner_z, cz)),
            (True, inner_z, -sz, min(sx * CROSS_TAP_LUG_INNER_X,
                                    sx * (CROSS_TAP_LUG_INNER_X + CROSS_TAP_LUG_WIDTH)),
             max(sx * CROSS_TAP_LUG_INNER_X,
                 sx * (CROSS_TAP_LUG_INNER_X + CROSS_TAP_LUG_WIDTH))),
        ):
            along = x if along_x else z
            if lo < along < hi and _round_junction_contains(
                x, z, cx, cz, SOCKET_BOSS_DIA / 2,
                along_x=along_x, wall=wall, air_sign=air_sign, fillet_r=radius,
            ):
                bottoms.append(CROSS_TAP_LUG_BOTTOM_Y)
    return bottoms


def retained_material_segments_mm(
    x_mm: float, z_mm: float, *, fillet_radius_mm: float = POCKET_CORNER_FILLET_R,
) -> tuple[tuple[float, float], ...]:
    """Uncut retained casting at a deck station, as downward depth intervals.

    Covers the entire deck, including partial rib/wall/fillet intersections
    and the transferred pedestal envelope. Horizontal socket/cross cavities
    are outside the deck seats; callers outside the deck are refused rather
    than extrapolated into the green land or the flange.
    """
    if not all(math.isfinite(v) for v in (x_mm, z_mm, fillet_radius_mm)):
        raise ValueError("retained material coordinates/radius must be finite")
    if abs(x_mm) >= DECK_HALF_X or abs(z_mm) >= DECK_HALF_Z:
        raise ValueError("through-seat material query must be inside the deck")
    if not 0 <= fillet_radius_mm <= POCKET_CORNER_FILLET_R:
        raise ValueError("pocket fillet radius outside its printed MAX limit")
    bottoms = [POCKET_CEILING_Y]
    if abs(x_mm) >= POCKET_HALF_X or abs(z_mm) >= POCKET_HALF_Z:
        bottoms.append(0.0)
    for region in _RETAINED_REGIONS:
        if region[0] == "rect":
            _, x0, x1, z0, z1, bottom = region
            contains = x0 <= x_mm <= x1 and z0 <= z_mm <= z1
        else:
            _, cx, cz, r, bottom = region
            contains = math.hypot(x_mm - cx, z_mm - cz) <= r
        if contains:
            bottoms.append(bottom)
    bottoms.extend(_fillet_bottoms(x_mm, z_mm, fillet_radius_mm))
    return ((0.0, STACK_HEIGHT - min(bottoms)),)


@dataclass(frozen=True)
class ThroughSeatMaterial:
    """Actual axis metal plus guaranteed full-circumference female thread.

    guaranteed_segments_mm includes ALL printed height/location bands and
    both edge breaks. R MAX permits sharp corners, so added fillet metal is
    deliberately not credited there. nominal_segments_mm retains real axis
    intersections for volume/readback, not a uniform skin-thickness assumption.
    """

    station_xz: tuple[float, float]
    envelope_xz: tuple[float, float]
    nominal_segments_mm: tuple[tuple[float, float], ...]
    guaranteed_segments_mm: tuple[tuple[float, float], ...]
    exit_depth_min_mm: float
    exit_depth_max_mm: float
    deck_height_min_mm: float


def through_seat_material(
    seat: HoleSpec, xz: tuple[float, float], *, envelope_xz: tuple[float, float] = (0.0, 0.0),
) -> ThroughSeatMaterial:
    """Bound retained metal over the whole thread and transfer rectangle.

    A bounding rectangle encloses the circular thread plus station and cast
    outline allowances. Containment in any retained primitive proves its full
    axial extent; partial/interrupted ribs cannot count as complete threads.
    """
    if seat.kind not in ("tapped", "tapped_bottoming") or seat.end != "through_all":
        raise AssertionError("base deck seat must be a native through-all tap")
    if seat.depth_mm or seat.overrides_mm:
        raise AssertionError("through seat must not retain blind depth overrides")
    if len(xz) != 2 or len(envelope_xz) != 2 or not all(
        math.isfinite(v) for v in (*xz, *envelope_xz)
    ) or min(envelope_xz) < 0:
        raise ValueError("finite station and nonnegative transfer bounds required")
    band = title_block_band_mm("linear_1pl")
    radius = THREAD_MAJOR_MM[seat.size] / 2.0
    hx, hz = (radius + band + bound for bound in envelope_xz)
    x, z = xz
    if abs(x) + hx >= DECK_HALF_X or abs(z) + hz >= DECK_HALF_Z:
        raise AssertionError("through-seat thread/transfer envelope reaches deck edge")
    bottom_high = POCKET_CEILING_Y + POCKET_CEILING_BAND_MM
    bottom_low = POCKET_CEILING_Y - POCKET_CEILING_BAND_MM
    # No fillet credit at printed limits. Full containment is exact for each
    # rectangular primitive; corner distances bound a circle over the box.
    for region in _RETAINED_REGIONS:
        if region[0] == "rect":
            _, x0, x1, z0, z1, bottom = region
            outline = 1.5 * band  # .X location plus half the .X size band
            contains = x - hx >= x0 + outline and x + hx <= x1 - outline and (
                z - hz >= z0 + outline and z + hz <= z1 - outline
            )
            intersects = x + hx >= x0 - outline and x - hx <= x1 + outline and (
                z + hz >= z0 - outline and z - hz <= z1 + outline
            )
        else:
            _, cx, cz, r, bottom = region
            contains = math.hypot(abs(x - cx) + hx, abs(z - cz) + hz) <= r - 1.5 * band
            intersects = math.hypot(max(0.0, abs(x - cx) - hx),
                                    max(0.0, abs(z - cz) - hz)) <= r + 1.5 * band
        if contains:
            bottom_high = min(bottom_high, bottom + band)
        if intersects:
            bottom_low = min(bottom_low, max(0.0, bottom - band))
    if abs(z) - hz >= POCKET_HALF_Z + 1.5 * band or abs(x) - hx >= POCKET_HALF_X + 1.5 * band:
        bottom_high = 0.0
    if abs(z) + hz >= POCKET_HALF_Z - 1.5 * band or abs(x) + hx >= POCKET_HALF_X - 1.5 * band:
        bottom_low = 0.0
    depth_min = STACK_HEIGHT - DECK_HEIGHT_BAND_MM - bottom_high
    depth_max = STACK_HEIGHT + DECK_HEIGHT_BAND_MM - bottom_low
    return ThroughSeatMaterial(
        xz, envelope_xz, retained_material_segments_mm(*xz),
        ((EDGE_BREAK_MAX_MM, depth_min - EDGE_BREAK_MAX_MM),),
        depth_min, depth_max, STACK_HEIGHT - DECK_HEIGHT_BAND_MM,
    )


@dataclass(frozen=True)
class ThroughSeatFit:
    full_thread_engagement_min_mm: float
    protrusion_max_mm: float
    clearance_min_mm: float


def require_through_seat_fit(
    label: str, seat: HoleSpec, material: ThroughSeatMaterial, *,
    insertion_min_mm: float, insertion_max_mm: float,
    tip_loss_mm: float = 0.0, full_thread_start_mm: float = 0.0,
    minimum_engagement_diameters: float = 1.5, clearance_floor_y_mm: float = 0.0,
) -> ThroughSeatFit:
    """Intersect actual external full form with guaranteed female segments.

    insertion is physical tip depth below the deck; full_thread_start_mm is
    the deepest possible head-end runout below it (after subtracting grip).
    Unknown supplier limits are NOT synthesized here: callers must distinguish
    nominal source-model checks from qualified stock or installed inspection.
    A passed fit is not a new supplier tolerance or a retention qualification.
    """
    if seat.kind not in ("tapped", "tapped_bottoming") or seat.end != "through_all":
        raise AssertionError(f"{label}: expected native through-all tapped seat")
    if seat.depth_mm or seat.overrides_mm:
        raise AssertionError(f"{label}: through tap retains obsolete depth overrides")
    if not material.guaranteed_segments_mm or not material.nominal_segments_mm:
        raise ValueError(f"{label}: retained material intervals are missing")
    previous_end = -math.inf
    for start, end in material.guaranteed_segments_mm:
        if not all(math.isfinite(v) for v in (start, end)) or not (
            0 <= start < end and start >= previous_end
        ):
            raise ValueError(f"{label}: invalid guaranteed material interval")
        previous_end = end
    if not all(math.isfinite(v) for v in (
        material.exit_depth_min_mm, material.exit_depth_max_mm,
        material.deck_height_min_mm,
    )) or not 0 < material.exit_depth_min_mm <= material.exit_depth_max_mm:
        raise ValueError(f"{label}: invalid material exit/clearance bounds")
    values = (insertion_min_mm, insertion_max_mm, tip_loss_mm, full_thread_start_mm,
              minimum_engagement_diameters, clearance_floor_y_mm)
    if not all(math.isfinite(value) for value in values) or not (
        0 < insertion_min_mm <= insertion_max_mm and tip_loss_mm >= 0
        and full_thread_start_mm >= 0 and minimum_engagement_diameters > 0
    ):
        raise ValueError(f"{label}: invalid insertion/full-thread bounds")
    external_end = insertion_min_mm - tip_loss_mm
    engagement = sum(max(0.0, min(end, external_end) - max(start, full_thread_start_mm))
                     for start, end in material.guaranteed_segments_mm)
    required = minimum_engagement_diameters * THREAD_MAJOR_MM[seat.size]
    if engagement < required - 1e-9:
        raise AssertionError(
            f"{label}: guaranteed full-form overlap {engagement:.4f} mm "
            f"< {minimum_engagement_diameters:g}D ({required:.4f}); "
            f"female {material.guaranteed_segments_mm}, external "
            f"[{full_thread_start_mm:.4f}, {external_end:.4f}]"
        )
    clearance = material.deck_height_min_mm - insertion_max_mm - clearance_floor_y_mm
    if clearance <= 0:
        raise AssertionError(f"{label}: screw tip reaches clearance floor ({clearance:.4f} mm)")
    return ThroughSeatFit(engagement, max(0.0, insertion_max_mm - material.exit_depth_min_mm), clearance)
