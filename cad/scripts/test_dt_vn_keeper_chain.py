"""Keeper chain (MHA-DT-VN-65): 3603T354 jack-chain strand contracts, SolidWorks-free."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import _config
import _mcmaster_3603t354 as catalogue
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
import _supplier_keeper_dimensions as keeper_dimensions
import build_dt_vn_keeper_chain as part
import dt_crank_arm_spec as arm
import dt_crank_hub_geometry as hub_geometry
import dt_crank_hub_spec as hub
import dt_crank_pin_ring_spec as ring
import dt_crank_pin_spec as pin
import dt_vn_keeper_chain_screw_spec as screw
import dt_vn_keeper_chain_spec as chain

IN = 25.4


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


# --- the purchased chain -------------------------------------------------------


def test_catalogue_link_geometry() -> None:
    assert chain.CHAIN_SKU == "3603T354"
    assert _config.parts("dt-vn-keeper-chain")["supplier_skus"] == [chain.CHAIN_SKU]
    assert chain.WIRE_DIA == pytest.approx(0.047 * IN)
    assert chain.INSIDE_LENGTH == pytest.approx(0.39 * IN)
    assert (chain.EYE_ID_MIN, chain.EYE_ID, chain.EYE_ID_MAX) == pytest.approx(
        (0.110 * IN, 0.115 * IN, 0.1535 * IN)
    )
    # Taut perpendicular eyes interlock one ID apart: A = c + ID.
    assert chain.EYE_CENTRE_SPACING == pytest.approx(chain.INSIDE_LENGTH - chain.EYE_ID)
    assert chain.EYE_CENTRE_SPACING == pytest.approx(0.275 * IN)
    assert chain.EYE_MEAN_R == pytest.approx((chain.EYE_ID + chain.WIRE_DIA) / 2.0)
    assert chain.NECK_LEN == pytest.approx(chain.EYE_CENTRE_SPACING - 2.0 * chain.EYE_MEAN_R)
    assert chain.NECK_LEN > 0.0
    assert catalogue.eye_centre_spacing(chain.EYE_ID_MAX) == pytest.approx(0.2365 * IN)


# --- the anchor: fit at the published eye limits --------------------------------


def test_screw_shank_passes_the_smallest_eye() -> None:
    air = (chain.EYE_ID_MIN - screw.SHANK_DIA) / 2.0
    assert air == pytest.approx(0.012 * IN)
    assert chain.SHANK_AIR_MIN == pytest.approx(air)
    assert air >= chain.EYE_PASS_AIR


@pytest.mark.parametrize("eye_id", [catalogue.EYE_ID, catalogue.EYE_ID_MIN])
def test_head_reaches_past_the_wire_centreline(eye_id: float) -> None:
    centreline_r = (eye_id + chain.WIRE_DIA) / 2.0
    assert screw.HEAD_DIA_MIN / 2.0 >= centreline_r
    assert chain.head_cover(eye_id) == pytest.approx(screw.HEAD_DIA_MIN / 2.0 - centreline_r)


def test_largest_published_eye_needs_the_washer() -> None:
    # D2: at .1535 the head stops short of the centreline (.1003 in); a gauged
    # eye over .134 takes a #2 washer.
    assert chain.HEAD_COVER_MAX_EYE < 0.0
    assert (chain.EYE_ID_MAX + chain.WIRE_DIA) / 2.0 == pytest.approx(0.10025 * IN)
    assert chain.WASHER_EYE_ID == pytest.approx(0.134 * IN)
    assert chain.EYE_ID_MIN < chain.EYE_ID < chain.WASHER_EYE_ID < chain.EYE_ID_MAX
    # D3: there the flat screw eye's outside overhangs the arm's -X edge at its
    # nearest printed distance (harmless; stated, not prevented).
    overhang = chain.EYE_ID_MAX / 2.0 + chain.WIRE_DIA - arm.ANCHOR_EDGE_DIST_MIN
    assert chain.SCREW_EYE_OVERHANG_MAX_EYE == pytest.approx(overhang)
    assert 0.0 < overhang < chain.WIRE_DIA


def test_ring_wire_passes_the_smallest_eye() -> None:
    air = (chain.EYE_ID_MIN - ring.WIRE_DIA) / 2.0
    assert air == pytest.approx(0.035 * IN)
    assert chain.RING_EYE_AIR_MIN == pytest.approx(air)
    assert air >= chain.EYE_PASS_AIR


def _corner_air(eye_id: float, edge_dist: float) -> float:
    """The standing eye against the arm's front -X corner, in closed form."""
    spacing = catalogue.eye_centre_spacing(eye_id)
    mean_r = (eye_id + chain.WIRE_DIA) / 2.0
    eye_z = -(chain.WIRE_DIA / 2.0 + chain.ANCHOR_AIR)
    return math.hypot(spacing - edge_dist, eye_z) - mean_r - chain.WIRE_DIA / 2.0


@pytest.mark.parametrize("eye_id", [catalogue.EYE_ID, catalogue.EYE_ID_MAX])
def test_standing_eye_clears_the_arm_edge(eye_id: float) -> None:
    # The edge at its farthest printed distance from the screw is the worst.
    edge = arm.ANCHOR_EDGE_DIST_MAX
    assert edge >= arm.ANCHOR_EDGE_DIST
    air = chain.standing_eye_edge_air(eye_id, edge)
    assert air >= 0.0
    # The arm's front -X corner governs; the sampled air matches its closed form.
    assert air == pytest.approx(_corner_air(eye_id, edge), abs=1e-4)
    assert air < chain.standing_eye_edge_air(eye_id, arm.ANCHOR_EDGE_DIST)


def test_standing_eye_edge_airs_are_the_reported_ones() -> None:
    assert chain.STANDING_EYE_EDGE_AIR == pytest.approx(
        chain.standing_eye_edge_air(chain.EYE_ID, arm.ANCHOR_EDGE_DIST_MAX)
    )
    assert chain.STANDING_EYE_EDGE_AIR_MAX_EYE == pytest.approx(
        chain.standing_eye_edge_air(chain.EYE_ID_MAX, arm.ANCHOR_EDGE_DIST_MAX)
    )
    assert chain.STANDING_EYE_EDGE_AIR_MAX_EYE < chain.STANDING_EYE_EDGE_AIR


def test_end_link_lies_flat_round_the_screw() -> None:
    assert chain.SCREW_XY == (-arm.ANCHOR_SCREW_Y, -arm.ANCHOR_SCREW_X)
    assert chain.SCREW_XY[0] - arm.ANCHOR_EDGE_DIST == pytest.approx(-arm.HALF_WIDTH)
    eye_z = -(chain.WIRE_DIA / 2.0 + chain.ANCHOR_AIR)
    assert chain.ANCHOR_EYE_CENTRE == (*chain.SCREW_XY, eye_z)
    assert chain.SCREW_HEAD_Z == pytest.approx(-(chain.WIRE_DIA + chain.ANCHOR_AIR))
    first = chain.LINKS[0]
    assert chain.near_eye(first) == pytest.approx(chain.ANCHOR_EYE_CENTRE)
    assert first.axis == pytest.approx((-1.0, 0.0, 0.0))
    assert first.near_normal == pytest.approx((0.0, 0.0, 1.0))
    assert first.far_normal == pytest.approx((0.0, 1.0, 0.0))
    # The head's under-plane sits on the wire's outboard side.
    assert eye_z - chain.WIRE_DIA / 2.0 == pytest.approx(chain.SCREW_HEAD_Z)


# --- the strand ------------------------------------------------------------------


def test_link_count_is_the_reach_plus_two_slack_links() -> None:
    assert chain.STRAND_SLACK_PITCHES == 2
    assert chain.PITCH == pytest.approx(chain.INSIDE_LENGTH - chain.AIR)
    reach_links = chain.REACH_LINKS
    # The fewest links whose straight strand spans the withdrawn reach.
    assert (reach_links - 1) * chain.PITCH >= chain.REACH
    assert (reach_links - 2) * chain.PITCH < chain.REACH
    assert chain.LINK_COUNT == reach_links + 2
    assert len(chain.LINKS) == len(chain.CHAIN_PART_LINKS) == chain.LINK_COUNT
    assert chain.SLACK == pytest.approx((chain.LINK_COUNT - 1) * chain.PITCH - chain.REACH)
    assert chain.SLACK >= 2 * chain.PITCH


def test_reach_is_to_the_ring_with_the_pin_out() -> None:
    moved = (
        chain.FAR_EYE_CENTRE[0] - chain.PIN_WITHDRAWAL,
        *chain.FAR_EYE_CENTRE[1:],
    )
    # Both ends stand outboard of the arm's -X edge, so the line is the reach.
    assert max(chain.STANDING_EYE_CENTRE[0], moved[0]) < -arm.HALF_WIDTH
    assert chain.REACH == pytest.approx(math.dist(chain.STANDING_EYE_CENTRE, moved))
    # The pin comes all the way out of the hub, not just loose in it.
    assert chain.PIN_X0 + chain.PIN_LENGTH - chain.PIN_WITHDRAWAL < -chain.HUB_R


def test_links_are_rigid_orthonormal_figure_eights() -> None:
    for link in chain.LINKS:
        for v in (link.axis, link.near_normal, link.far_normal):
            assert math.hypot(*v) == pytest.approx(1.0)
        assert _dot(link.axis, link.near_normal) == pytest.approx(0.0, abs=1e-12)
        assert _dot(link.axis, link.far_normal) == pytest.approx(0.0, abs=1e-12)
        # The two eyes at 90 deg.
        assert _dot(link.near_normal, link.far_normal) == pytest.approx(0.0, abs=1e-12)
        assert math.dist(chain.near_eye(link), chain.far_eye(link)) == pytest.approx(
            chain.EYE_CENTRE_SPACING
        )


def test_every_joint_is_threaded_with_air() -> None:
    for a, b in zip(chain.LINKS, chain.LINKS[1:]):
        # The next near eye's centre lies inside the far eye's wire circle
        # reach, so the eyes are hooked, not merely touching.
        assert math.dist(chain.far_eye(a), chain.near_eye(b)) < 2.0 * chain.EYE_MEAN_R
        assert chain.thread_air(a, b) == pytest.approx(chain.AIR, abs=2e-3)
    # The joints' even twist stays a modest share of the play.
    assert abs(chain.JOINT_TWIST_DEG) < 20.0


def test_far_eye_hangs_on_the_ring_wire() -> None:
    last = chain.LINKS[-1]
    assert chain.far_eye(last) == pytest.approx(chain.FAR_EYE_CENTRE, abs=1e-6)
    # The ring's outboard wire runs along z there; the eye lies square to it.
    assert abs(last.far_normal[2]) == pytest.approx(
        math.sqrt(1.0 - last.axis[2] ** 2), abs=1e-9
    )
    wire = (chain.RING_OUT_X, 0.0, chain.RING_PLANE_Z)
    assert math.dist(chain.FAR_EYE_CENTRE, wire) == pytest.approx(
        chain.EYE_ID / 2.0 - ring.WIRE_DIA / 2.0 - chain.AIR
    )
    assert chain.RING_OUT_X == pytest.approx(chain.RING_X - ring.RING_FAR_X)


def test_chain_clears_every_part_it_passes() -> None:
    worst = chain.clearance_report()
    assert set(worst) == {
        "arm", "hub", "pin", "screw", "screw-shank", "ring", "ring-thread",
        "link-link", "link-thread",
    }
    assert min(worst.values()) >= 0.0, {k: v for k, v in worst.items() if v < 0.0}
    # The designed contacts keep the solve's air.
    assert worst["arm"] == pytest.approx(chain.ANCHOR_AIR, abs=1e-9)
    assert worst["ring-thread"] == pytest.approx(chain.AIR, abs=2e-3)
    assert worst["link-thread"] == pytest.approx(chain.AIR, abs=2e-3)
    # The centred screw eye keeps the shank's air on every side.
    nominal = (chain.EYE_ID - screw.SHANK_DIA) / 2.0
    assert worst["screw-shank"] == pytest.approx(nominal, abs=1e-6)


def test_strand_drapes_outboard_of_the_arm_edge() -> None:
    for link in chain.LINKS[1:]:
        assert link.centre[0] < -arm.HALF_WIDTH - chain.EYE_MEAN_R


def test_part_frame_is_the_end_link() -> None:
    assert chain.CHAIN_PART_ORIGIN == chain.LINKS[0].centre
    assert chain.CHAIN_PART_LINKS[0].centre == (0.0, 0.0, 0.0)
    for local, placed in zip(chain.CHAIN_PART_LINKS, chain.LINKS):
        assert tuple(
            c + o for c, o in zip(local.centre, chain.CHAIN_PART_ORIGIN)
        ) == pytest.approx(placed.centre)
        assert local.axis == placed.axis
        assert local.near_normal == placed.near_normal
        assert local.far_normal == placed.far_normal


# --- the builder's analytic checks ------------------------------------------------


def test_builder_volume_and_centre_of_mass_are_analytic() -> None:
    r = chain.WIRE_DIA / 2.0
    eye = 2.0 * math.pi**2 * chain.EYE_MEAN_R * r**2
    neck = math.pi * r**2 * chain.NECK_LEN
    assert part.V_CHAIN == pytest.approx(chain.LINK_COUNT * (2.0 * eye + neck))
    assert part.BODY_COUNT == 3 * chain.LINK_COUNT
    centres = [link.centre for link in chain.CHAIN_PART_LINKS]
    want = tuple(sum(c[k] for c in centres) / len(centres) for k in range(3))
    assert part._com_expected() == pytest.approx(want)


def test_builder_eye_paths_follow_the_eye_circle() -> None:
    link = chain.CHAIN_PART_LINKS[3]
    centre = chain.far_eye(link)
    segments = part._eye_segments(centre, link.far_normal, link.axis)
    assert len(segments) == 4
    # Closed and tangent-continuous, in the eye's plane, on its circle.
    assert segments[-1][-1] == pytest.approx(segments[0][0])
    for (p0, p1, p2, p3) in segments:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            point = tuple(
                (1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t**2 * c + t**3 * d
                for a, b, c, d in zip(p0, p1, p2, p3)
            )
            rel = tuple(p - c for p, c in zip(point, centre))
            assert _dot(rel, link.far_normal) == pytest.approx(0.0, abs=1e-9)
            assert math.hypot(*rel) == pytest.approx(chain.EYE_MEAN_R, rel=3e-4)


def test_chain_edges_fit_the_balloon_walk() -> None:
    # The drawings balloon the chain from its visible edges: each link's three
    # swept bodies draw at most two seam or end circles each.
    from _drawing_balloons import _VISIBLE_EDGES_PER_INSTANCE

    assert 6 * chain.LINK_COUNT <= _VISIBLE_EDGES_PER_INSTANCE


# --- the ring's pose (owner ruling 2026-10-15 A1, unchanged) ---------------------


def _band(places: int) -> float:
    """The hub's printed band at ``places``, read in the hub sheet's unit."""
    return printed_band_mm(places, unit=hub_geometry.UNIT)


def _ring_corner_air(
    hole_x: float, pin_z: float, mean_r: float, crown: float
) -> tuple[float, tuple[float, float]]:
    """A ring in the A1 plane (y = 0) against the arm's -X inboard corner
    edge, in closed form: its air and the wire-centreline point nearest it."""
    cx, cz = hole_x - (mean_r - crown), pin_z
    qx, qz = -arm.HALF_WIDTH, arm.ARM_THICKNESS
    reach = math.hypot(qx - cx, qz - cz)
    nearest = (cx + mean_r * (qx - cx) / reach, cz + mean_r * (qz - cz) / reach)
    return reach - mean_r - ring.WIRE_DIA / 2.0, nearest


def _flat_side_air(swing_deg: float, mean_r: float, crown: float) -> float:
    """The nominal ring swung toward -Y against the arm's straight -X side
    and its inboard face, from 3600 points of its centreline. (The few points
    past the hole axis, at +Y, are the crown's, high over the face.)"""
    a = math.radians(swing_deg)
    least = math.inf
    for k in range(3600):
        t = 2.0 * math.pi * k / 3600
        out = mean_r - crown + mean_r * math.cos(t)  # along the hang
        x = chain.RING_X - math.cos(a) * out
        z = chain.PIN_Z + mean_r * math.sin(t)
        side = max(0.0, -arm.HALF_WIDTH - x)
        above = max(0.0, z - arm.ARM_THICKNESS)
        least = min(least, math.hypot(side, above))
    return least - ring.WIRE_DIA / 2.0


def test_pin_station_reads_the_hub_print() -> None:
    # The hub prints the station from its faced outboard end, flush with the
    # arm's outboard face (z 0); the arm's inboard face sits wherever the
    # thickest 5/16 stock puts it, so the arm-side corner adds that excess.
    places = hub.DRAWING_PRECISION["ServicePinStationReference"]["ServicePinStation"]
    assert chain.PIN_Z == pytest.approx(hub_geometry.SERVICE_PIN_STATION)
    thick = hub_geometry.ARM_STOCK_THICKNESS_MAX - arm.ARM_THICKNESS
    assert chain.PIN_Z_ARMWARD == pytest.approx(chain.PIN_Z - _band(places) - thick)
    # The inch sheet's .XX: +/-.01 in (Codjiflo review of 831be7869).
    assert _band(places) == pytest.approx(0.254)


def test_ring_crowned_hub_side_clears_the_arm_at_the_adverse_corner() -> None:
    # Codex xhigh, PR #1466 round 3: the largest accepted ring, crowned against
    # the hole's hub-side wall in a hole at its station's hub-side limit, on a
    # pin at the hub's arm-side station limit, is the worst pose in the A1
    # plane.  The #290 inch ring (.43 ID) clears the arm's corner even there.
    mean_r = (ring.RING_ID_MAX + ring.WIRE_DIA) / 2.0
    crown = pin.RING_HOLE_DIA / 2.0 - ring.WIRE_DIA / 2.0
    hole_x = chain.RING_X + ring.PIN_BAND
    air, nearest = _ring_corner_air(hole_x, chain.PIN_Z_ARMWARD, mean_r, crown)
    # The nearest wire point is outboard of the arm and above its face, so the
    # corner edge is the arm's nearest point and the closed form is exact.
    assert nearest[0] < -arm.HALF_WIDTH and nearest[1] > arm.ARM_THICKNESS
    assert air >= 0.0
    helper = chain.ring_arm_air(0.0, mean_r, crown, hole_x, chain.PIN_Z_ARMWARD)
    assert helper == pytest.approx(air, abs=2.5e-3)  # the helper samples the arc


def test_every_printed_ring_has_a_pose_clear_of_the_arm() -> None:
    # The largest ring governs: slid outboard in the hole as far as the hole's
    # outboard edges (on the pin's fattest printed section) let it, it clears
    # the arm at the adverse corner, so the arm cannot clamp it.
    mean_r = (ring.RING_ID_MAX + ring.WIRE_DIA) / 2.0
    pin_r = ring.PIN_DIA_AT_HOLE_MAX / 2.0
    hole_r = pin.RING_HOLE_DIA / 2.0
    wire_r = ring.WIRE_DIA / 2.0

    def outboard_edge_air(crown: float) -> float:
        return mean_r - math.hypot(mean_r - crown - hole_r, pin_r) - wire_r

    low, high = 0.0, hole_r - wire_r  # crown on the axis, crown on the hub-side wall
    assert outboard_edge_air(low) < 0.0 <= outboard_edge_air(high)
    for _ in range(60):
        mid = (low + high) / 2.0
        low, high = (mid, high) if outboard_edge_air(mid) < 0.0 else (low, mid)
    crown = high
    # The hole admits that pose: the hub-side edges stay outside the arc.
    assert math.hypot(mean_r - crown + hole_r, pin_r) - mean_r >= wire_r
    hole_x = chain.RING_X + ring.PIN_BAND
    air, nearest = _ring_corner_air(hole_x, chain.PIN_Z_ARMWARD, mean_r, crown)
    assert nearest[0] < -arm.HALF_WIDTH and nearest[1] > arm.ARM_THICKNESS
    assert air >= 0.0
    assert chain.RING_FREE_AIR_WORST == pytest.approx(air, abs=5e-3)
    # Crowned against the hub-side wall it keeps less air: the slide is the
    # better pose, and the witness never claims more than it.
    assert _ring_corner_air(hole_x, chain.PIN_Z_ARMWARD, mean_r, hole_r - wire_r)[0] < air


def test_arm_is_the_ring_swing_stop_and_withdrawal_lifts_it_off() -> None:
    crown = ring.ARC_SAGITTA / 2.0
    # Hanging plumb, the nominal ring's plane is x = RING_X, inside the arm's
    # half-width, and its low arc dips below the arm's inboard face: under its
    # own weight it comes to rest on the arm.
    assert abs(chain.RING_X) < arm.HALF_WIDTH
    assert chain.PIN_Z - ring.MEAN_R < arm.ARM_THICKNESS
    assert 0.0 < chain.RING_STOP_SWING_DEG < 90.0
    assert _flat_side_air(chain.RING_STOP_SWING_DEG - 1.0, ring.MEAN_R, crown) > 0.0
    assert _flat_side_air(chain.RING_STOP_SWING_DEG + 1.0, ring.MEAN_R, crown) < 0.0
    # No accepted ring reaches the arm's mid-plane x = 0: its hub-most point is
    # the oversize hole's hub-side wall at the station's hub-side limit. So
    # the arm's outward normal at any contact points -X or along its face.
    drilled_plus = drilled_oversize_mm(unit=pin.UNIT)
    reach = chain.RING_X + ring.PIN_BAND + (pin.RING_HOLE_DIA + drilled_plus) / 2.0
    assert chain.RING_REACH_X_MAX == pytest.approx(reach)
    assert reach < 0.0


def test_nominal_ring_threads_the_hole_edges_in_its_posed_plane() -> None:
    # In the pin's axial plane the wire leaves the hole along the pin's top
    # line, so the hole's edges are tighter than its wall.
    assert 0.0 < chain.A1_HOLE_AIR < ring.HOLE_AIR


# --- the purchased-part sheet's catalogue wire reference ------------------------
# Lightweight callback doubles below are not native SOLIDWORKS-result evidence.
_VIEWED_CONFIGURATION = "Keeper catalogue viewed configuration"
_ACTIVE_CONFIGURATION = "Different active installed configuration"
_SOURCE_PATH = "D:/native/keeper-chain.SLDPRT"
_NAME = "CatalogueWireDiameter"
_FEATURE = "CatalogueReference"
_FULL_NAME = f"{_NAME}@{_FEATURE}@keeper-chain.SLDPRT"
_WIRE_MM = 0.047 * IN


def test_catalogue_wire_reference_names_match_the_spec() -> None:
    assert chain.CATALOGUE_WIRE_DIMENSION == _NAME
    assert chain.CATALOGUE_REFERENCE == _FEATURE
    assert chain.DRAWING_DIMENSIONS == {_FEATURE: {_NAME}}
    assert chain.WIRE_DIA == pytest.approx(_WIRE_MM, abs=1e-12)
    assert keeper_dimensions.VIEW == "*Right"


class _NativeDimension:
    def __init__(self, *, values=(_WIRE_MM / 1000.0,)):
        self.Name = _NAME
        self.FullName = _FULL_NAME
        self.Tolerance = SimpleNamespace(Type=0)
        self.values = values
        self.calls = []
        self.active_reads = 0

    def GetSystemValue3(self, which, configuration):
        self.calls.append((which, configuration))
        assert type(which) is int and which == 3
        # Enforce the scalar BSTR boundary selected to match the shared
        # supplier getter; this double makes no native ABI-validity claim.
        assert type(configuration) is str
        assert configuration == _VIEWED_CONFIGURATION
        return self.values

    @property
    def SystemValue(self):
        self.active_reads += 1
        raise AssertionError("Active-configuration SystemValue is not owner proof")


class _Source:
    def __init__(self, owner_dimension):
        self.path = _SOURCE_PATH
        self.owner_dimension = owner_dimension
        self.parameter_calls = []
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name=_ACTIVE_CONFIGURATION)
        )

    def GetPathName(self):
        return self.path

    def Parameter(self, name):
        self.parameter_calls.append(name)
        assert name == f"{_NAME}@{_FEATURE}"
        return self.owner_dimension


class _Display:
    def __init__(self):
        # Display dimension and source Parameter are deliberately different
        # proxies; only the latter provides configured owner-value readback.
        self.native = _NativeDimension(values=(-0.5,))
        self.Type2 = 6
        self.options = None

    def GetDimension2(self, index):
        assert index == 0
        return self.native


class _Annotation:
    def __init__(self, display):
        self.display = display
        self.annotation_type = 4

    def GetType(self):
        return self.annotation_type

    def GetSpecificAnnotation(self):
        return self.display


class _View:
    def __init__(self, source):
        self.ReferencedDocument = source
        self.ReferencedConfiguration = _VIEWED_CONFIGURATION
        self.annotations = []
        self.count_override = None

    def GetOutline(self):
        return (0.05, 0.12, 0.15, 0.16)

    def GetAnnotations(self):
        return tuple(self.annotations)

    def GetDisplayDimensionCount(self):
        if self.count_override is not None:
            return self.count_override
        return len(self.annotations)


@pytest.fixture
def keeper_sheet(monkeypatch):
    owner = _NativeDimension()
    source = _Source(owner)
    views = {
        orientation: _View(source)
        for orientation in ("*Front", "*Top", "*Right", "*Isometric")
    }
    adapter = object()
    presented = []
    asserted = []

    def curate(actual_adapter, view, *, keep, view_label, dimensions_by_feature):
        assert actual_adapter is adapter
        assert view is views["*Right"]
        # Right of the view, at mid-height.
        ((name, (x, y)),) = keep.items()
        assert name == _NAME
        assert x > view.GetOutline()[2]
        assert y == pytest.approx((0.12 + 0.16) / 2.0)
        assert view_label == "keeper catalogue wire diameter"
        assert dimensions_by_feature == {_FEATURE: {_NAME}}
        view.annotations = [_Annotation(_Display())]
        return view.annotations

    def present(actual_adapter, display, **options):
        assert actual_adapter is adapter
        display.options = dict(options)
        presented.append(display)

    def assert_presentation(actual_adapter, display, **options):
        assert actual_adapter is adapter
        assert display.options == options
        asserted.append(display)

    monkeypatch.setattr(keeper_dimensions, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(keeper_dimensions, "curate_view_dimensions", curate)
    monkeypatch.setattr(keeper_dimensions, "supplier_reference_dimension", present)
    monkeypatch.setattr(
        keeper_dimensions, "assert_supplier_reference_dimension", assert_presentation
    )
    settled = keeper_dimensions.annotate_keeper_wire(adapter, views)
    return SimpleNamespace(
        views=views,
        source=source,
        owner=owner,
        settled=settled,
        presented=presented,
        asserted=asserted,
    )


def test_scalar_viewed_configuration_owner_readback_repeated_reacquisition(keeper_sheet):
    sheet = keeper_sheet
    right = sheet.views["*Right"]
    assert sheet.source.ConfigurationManager.ActiveConfiguration.Name != (
        right.ReferencedConfiguration
    )
    assert sheet.presented[0].options == {
        "label": f"{_NAME}@{_FEATURE}",
        "units": "in",
        "configuration": _VIEWED_CONFIGURATION,
        "precision": 3,
        "expected_mm": pytest.approx(_WIRE_MM, rel=0, abs=1e-12),
        "presentation": "diameter",
        "callout": "CATALOGUE WIRE SIZE",
    }
    old_display = sheet.presented[0]
    old_source = sheet.source
    old_owner = sheet.owner
    # The harness invokes the callback twice, replacing both annotations and
    # source proxies each time. This does not model a post-save finalizer hook.
    for _invocation in range(2):
        replacement = _Display()
        replacement.options = dict(old_display.options)
        new_owner = _NativeDimension()
        new_source = _Source(new_owner)
        old_display.native.FullName = "Stale@Discarded@old.SLDPRT"
        old_owner.values = (-1.0,)
        old_parameter_calls = list(old_source.parameter_calls)
        old_value_calls = list(old_owner.calls)
        right.annotations = [_Annotation(replacement)]
        right.ReferencedDocument = new_source
        sheet.settled()
        assert sheet.asserted[-1] is replacement
        assert new_source.parameter_calls == [f"{_NAME}@{_FEATURE}"]
        assert new_owner.calls == [(3, _VIEWED_CONFIGURATION)]
        assert new_owner.active_reads == 0
        assert replacement.native.calls == []
        assert replacement.native.active_reads == 0
        assert old_source.parameter_calls == old_parameter_calls
        assert old_owner.calls == old_value_calls
        assert right.GetDisplayDimensionCount() == 1
        assert all(
            view.GetDisplayDimensionCount() == 0
            for orientation, view in sheet.views.items()
            if orientation != "*Right"
        )
        old_display, old_source, old_owner = replacement, new_source, new_owner
    assert len(sheet.presented) == 1
    assert len(sheet.asserted) == 2
    assert sheet.owner.calls == []


@pytest.mark.parametrize(
    "values",
    [
        pytest.param(None, id="no-return"),
        pytest.param((), id="empty-return"),
        pytest.param(_WIRE_MM / 1000.0, id="scalar-not-array"),
        pytest.param("0.0011938", id="string-not-array"),
        pytest.param((_WIRE_MM / 1000.0, _WIRE_MM / 1000.0), id="multiple-values"),
        pytest.param((1.3 / 1000.0,), id="wrong-native-diameter"),
        pytest.param((-_WIRE_MM / 1000.0,), id="negative-native-diameter"),
        pytest.param(((_WIRE_MM + 2e-5) / 1000.0,), id="outside-existing-tolerance"),
        pytest.param((float("nan"),), id="nan"),
        pytest.param((float("inf"),), id="positive-infinity"),
        pytest.param((float("-inf"),), id="negative-infinity"),
    ],
)
def test_configured_owner_values_fail_closed(keeper_sheet, values):
    keeper_sheet.owner.values = values
    with pytest.raises(RuntimeError):
        keeper_sheet.settled()
    assert keeper_sheet.owner.calls == [(3, _VIEWED_CONFIGURATION)]
    assert keeper_sheet.owner.active_reads == 0
    assert keeper_sheet.asserted == []


@pytest.mark.parametrize("offset_mm", [-0.5e-5, 0.0, 0.5e-5])
def test_existing_millimetre_comparison_tolerance_is_preserved(keeper_sheet, offset_mm):
    keeper_sheet.owner.values = ((_WIRE_MM + offset_mm) / 1000.0,)
    keeper_sheet.settled()
    assert keeper_sheet.owner.calls == [(3, _VIEWED_CONFIGURATION)]


@pytest.mark.parametrize(
    "fault",
    [
        "configuration",
        "source-path",
        "source-owner",
        "dimension-name",
        "reference-feature",
        "diameter-type",
        "missing-owner-dimension",
        "unprovided-tolerance",
        "missing-right-reference",
        "duplicate-right-reference",
        "missing-annotation-with-count",
        "foreign-annotation-with-count",
        "foreign-right-reference",
    ],
)
def test_final_source_and_inventory_drift_fail_closed(keeper_sheet, fault):
    sheet = keeper_sheet
    right = sheet.views["*Right"]
    display = right.annotations[0].display
    if fault == "configuration":
        right.ReferencedConfiguration = _ACTIVE_CONFIGURATION
    elif fault == "source-path":
        right.ReferencedDocument = _Source(_NativeDimension())
        right.ReferencedDocument.path = "D:/native/foreign-chain.SLDPRT"
    elif fault == "source-owner":
        sheet.owner.FullName = f"{_NAME}@{_FEATURE}@foreign-chain.SLDPRT"
    elif fault == "dimension-name":
        display.native.Name = "NeckDiameter"
    elif fault == "reference-feature":
        display.native.FullName = f"{_NAME}@Link00Neck@keeper-chain.SLDPRT"
    elif fault == "diameter-type":
        display.Type2 = 2
    elif fault == "missing-owner-dimension":
        sheet.source.owner_dimension = None
    elif fault == "unprovided-tolerance":
        display.native.Tolerance.Type = 2
    elif fault == "missing-right-reference":
        right.annotations = []
    elif fault == "duplicate-right-reference":
        right.annotations.append(_Annotation(_Display()))
    elif fault == "missing-annotation-with-count":
        right.annotations = []
        right.count_override = 1
    elif fault == "foreign-annotation-with-count":
        right.annotations[0].annotation_type = 1
        right.count_override = 1
    elif fault == "foreign-right-reference":
        display.native.FullName = f"{_NAME}@{_FEATURE}@foreign-chain.SLDPRT"
    else:
        raise AssertionError(f"Unhandled fault {fault}")
    with pytest.raises(RuntimeError):
        sheet.settled()
    assert sheet.asserted == []


@pytest.mark.parametrize("orientation", ["*Front", "*Top", "*Isometric"])
def test_reference_in_any_other_view_is_rejected(keeper_sheet, orientation):
    keeper_sheet.views[orientation].annotations = [_Annotation(_Display())]
    with pytest.raises(RuntimeError, match="inventory"):
        keeper_sheet.settled()
