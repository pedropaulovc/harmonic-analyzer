"""Where the cone set's running axis lies against its parts (#2473).

The cone set turns on a line from MHA-DT-04's journal, in MHA-DT-05's boss,
to MHA-DT-37's pivot, in MHA-DT-39's hole. MHA-DT-37's spigot is bonded with
LOCTITE 638 in MHA-DT-04's reamed socket. It can cure off-centre by up to
half its clearance and tilted in its short engagement, so its pivot can sit
off MHA-DT-04's axis by an offset p. MHA-DT-04 then wobbles about the
running axis. MHA-DT-00 reads 2 p on the bare pivot, MHA-DT-04 turning in a
V-block on its journal, before the post is assembled; cone_set_stack books
the limit.

* A gear on MHA-DT-04 is offset from the running axis by k * p. k is how far
  along the gear's plane is from the journal's fulcrum to the pivot; the
  fulcrum lies anywhere in the boss, so k has a range (``dt04_k_range``) and
  the stack takes its upper end.
* A gear on MHA-DT-37 (T012 and T018 on its spigot, T006 integral) rides
  MHA-DT-37's own axis. That axis meets the running axis at the pivot and
  stands off it at the socket mouth (``spigot_stand_off_mm``); the gear's
  share of that falls from 1 at the socket mouth to 0 at the pivot
  (``spigot_share``).

The pivot is taken to bear where it is read: the middle of its bare length
between MHA-DT-38 and its end. Pure geometry from the specs.
"""

from __future__ import annotations

import cone_tip_cluster as cluster
import dt_cone_gear_shaft_spec as shaft
import dt_cone_gear_spec as cone
import dt_cone_pivot_post_spec as post

# Seat order on the shaft, T120 at seat 0 to T006 at the tip.
_SEAT_ORDER = tuple(sorted(cone.CONE_TEETH, reverse=True))
# T006 is one part with the spigot and pivot; T012 and T018 are bonded on it.
DT37_TEETH = (min(cone.CONE_TEETH), *cone.SPIGOT_TEETH)
# T024, T018, T012 and T006 are modelled the tip set's shift north of their
# layout stations (cone_tip_cluster), as MHA-DT-04's end and the socket are.
_TIP_SET_TEETH = (*DT37_TEETH, *cone.LAND_2_TEETH)

# The journal's fulcrum: anywhere along the boss, in cone stations.
BOSS_NORTH_STATION = shaft.JOURNAL_END - shaft.FRONT_STUB
BOSS_SOUTH_STATION = BOSS_NORTH_STATION - post.CONE_BOSS_LENGTH

# The bare pivot: from MHA-DT-38's north face to the pivot's end.
_T006_NORTH_FACE = shaft.T006_NORTH_FACE_STATION + cluster.TIP_SET_SHIFT_MM
PIVOT_BARE_STATIONS = (
    _T006_NORTH_FACE + cluster.BUSHING_LENGTH_MM,
    _T006_NORTH_FACE + cluster.PIVOT_LENGTH_MM,
)
PIVOT_STATION = sum(PIVOT_BARE_STATIONS) / 2.0

SOCKET_MOUTH_STATION = shaft.TIP_END_STATION
# The spigot's offset in the socket: half its largest bonded clearance, at
# the mouth and at the spigot's inner end alike.
SPIGOT_FLOAT_MM = cluster.SPIGOT_BOND_CLEARANCE_MM[1] / 2.0
# The least engagement the shaft spec proves, over the mouth-to-pivot span:
# the shorter the engagement, the more the float tilts MHA-DT-37.
_ENGAGEMENT_RATIO = shaft.SPIGOT_ENGAGEMENT_MIN_MM / (
    PIVOT_STATION - SOCKET_MOUTH_STATION
)

if not (
    BOSS_SOUTH_STATION
    < BOSS_NORTH_STATION
    < SOCKET_MOUTH_STATION
    < PIVOT_BARE_STATIONS[0]
    < PIVOT_BARE_STATIONS[1]
):
    raise AssertionError("the cone set's journal, socket and pivot are out of order")


def seat_plane(teeth: int) -> float:
    """Cone station of gear ``teeth``'s mid-face plane, as modelled."""
    south, north = shaft.gear_faces(_SEAT_ORDER.index(teeth))
    shift = cluster.TIP_SET_SHIFT_MM if teeth in _TIP_SET_TEETH else 0.0
    return (south + north) / 2.0 + shift


def _k(station: float, fulcrum: float) -> float:
    return (station - fulcrum) / (PIVOT_STATION - fulcrum)


def k_range(station: float) -> tuple[float, float]:
    """(least, most) share of the pivot's offset at ``station`` on MHA-DT-04."""
    return _k(station, BOSS_NORTH_STATION), _k(station, BOSS_SOUTH_STATION)


def dt04_k_range(teeth: int) -> tuple[float, float]:
    """k at gear ``teeth``'s plane; the gear must sit on MHA-DT-04."""
    if teeth not in cone.CONE_TEETH or teeth in DT37_TEETH:
        raise ValueError(f"T{teeth:03d} does not sit on MHA-DT-04")
    return k_range(seat_plane(teeth))


K_MOUTH = k_range(SOCKET_MOUTH_STATION)[1]


def spigot_share(teeth: int) -> float:
    """How much of MHA-DT-37's stand-off at the socket mouth reaches gear
    ``teeth``."""
    if teeth not in DT37_TEETH:
        raise ValueError(f"T{teeth:03d} does not sit on MHA-DT-37")
    return (PIVOT_STATION - seat_plane(teeth)) / (PIVOT_STATION - SOCKET_MOUTH_STATION)


def spigot_stand_off_mm(pivot_offset_mm: float) -> float:
    """Largest stand-off of MHA-DT-37's axis from the running axis at the
    socket mouth, the pivot ``pivot_offset_mm`` off MHA-DT-04's axis.

    MHA-DT-37's axis passes through the pivot (offset p) and through the
    socket, where it lies within s = ``SPIGOT_FLOAT_MM`` of MHA-DT-04's axis
    at the mouth (offset u) and at the spigot's inner end (v). With r the
    engagement over the mouth-to-pivot span, v = (1 + r) u - r p, so u lies
    in a disc of radius s / (1 + r) about r p / (1 + r). The running axis
    is k_mouth p off MHA-DT-04 at the mouth, and the stand-off is the
    farthest point of that disc from it."""
    r = _ENGAGEMENT_RATIO
    return SPIGOT_FLOAT_MM / (1.0 + r) + abs(K_MOUTH - r / (1.0 + r)) * abs(
        pivot_offset_mm
    )


def seat_offset_mm(teeth: int, pivot_offset_mm: float) -> float:
    """Largest offset of gear ``teeth``'s seat axis from the running axis,
    the pivot up to ``pivot_offset_mm`` off MHA-DT-04's axis."""
    if teeth in DT37_TEETH:
        return spigot_share(teeth) * spigot_stand_off_mm(pivot_offset_mm)
    return dt04_k_range(teeth)[1] * abs(pivot_offset_mm)
