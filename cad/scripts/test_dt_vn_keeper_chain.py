"""Keeper chain (MHA-DT-VN-65) and loop link (MHA-DT-VN-66) contracts, SolidWorks-free."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import _config
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
import _supplier_keeper_dimensions as keeper_dimensions
import dt_crank_arm_spec as arm
import dt_crank_hub_geometry as hub_geometry
import dt_crank_hub_spec as hub
import dt_crank_pin_ring_spec as ring
import dt_crank_pin_spec as pin
import dt_vn_keeper_chain_spec as chain


def test_every_link_is_one_pitch() -> None:
    assert max(chain.pitch_errors()) < 1e-9


def test_chain_clears_every_part_it_passes() -> None:
    worst = chain.clearance_report()
    assert min(worst.values()) >= 0.0, {k: v for k, v in worst.items() if v < 0.0}
    # The wraps bear on the wire through the rod, with the solve's air.
    assert worst["rod-eye"] == pytest.approx(chain.AIR, abs=2e-3)
    assert worst["rod-ring"] == pytest.approx(chain.AIR, abs=2e-3)


def test_each_strand_reaches_the_withdrawn_pin() -> None:
    # Drawing the pin out pulls both strands straight side by side.
    assert chain.INNER_LENGTH >= chain.INNER_REACH + chain.PITCH
    assert chain.OUTER_LENGTH >= chain.OUTER_REACH + chain.PITCH
    # The pin comes all the way out of the hub, not just loose in it.
    assert chain.PIN_X0 + chain.PIN_LENGTH - chain.PIN_WITHDRAWAL < -chain.HUB_R


def _band(places: int) -> float:
    return printed_band_mm(places)


def _corner_air(
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
    station = hub.DRAWING_PRECISION["ServicePinStationReference"]
    places = station["ServicePinFromShoulder"]
    shoulder = arm.ARM_THICKNESS  # the hub's shoulder is the arm's inboard face
    from_shoulder = hub_geometry.SERVICE_PIN_FROM_SHOULDER
    assert chain.PIN_Z == pytest.approx(shoulder + from_shoulder)
    assert chain.PIN_Z_ARMWARD == pytest.approx(chain.PIN_Z - _band(places))


def test_ring_crowned_hub_side_clears_the_arm_at_the_adverse_corner() -> None:
    # Codex xhigh, PR #1466 round 3: the largest accepted ring, crowned against
    # the hole's hub-side wall in a hole at its station's hub-side limit, on a
    # pin at the hub's arm-side station limit, is the worst pose in the A1
    # plane.  The #290 inch ring (.43 ID) clears the arm's corner even there.
    mean_r = (ring.RING_ID_MAX + ring.WIRE_DIA) / 2.0
    crown = pin.RING_HOLE_DIA / 2.0 - ring.WIRE_DIA / 2.0
    hole_x = chain.RING_X + ring.PIN_BAND
    air, nearest = _corner_air(hole_x, chain.PIN_Z_ARMWARD, mean_r, crown)
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
    air, nearest = _corner_air(hole_x, chain.PIN_Z_ARMWARD, mean_r, crown)
    assert nearest[0] < -arm.HALF_WIDTH and nearest[1] > arm.ARM_THICKNESS
    assert air >= 0.0
    assert chain.RING_FREE_AIR_WORST == pytest.approx(air, abs=5e-3)
    # Crowned against the hub-side wall it keeps less air: the slide is the
    # better pose, and the witness never claims more than it.
    assert _corner_air(hole_x, chain.PIN_Z_ARMWARD, mean_r, hole_r - wire_r)[0] < air


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


def test_one_closed_loop_through_both_wires() -> None:
    beads = chain.BEAD_CENTRES
    # The two ends are the link's end beads, a joint's spacing apart on its axis.
    ends = beads[0], beads[-1]
    assert chain._dist(*ends) == pytest.approx(chain.LINK_BEAD_SPACING)
    for end in ends:
        axial, radial, _ = chain._link_local(end)
        assert abs(axial) == pytest.approx(chain.LINK_END_BEAD_X)
        assert radial == pytest.approx(0.0, abs=1e-9)
    # The rods leave the domes along the axis.
    for end, next_bead in ((beads[0], beads[1]), (beads[-1], beads[-2])):
        _, radial, _ = chain._link_local(next_bead)
        assert radial == pytest.approx(0.0, abs=1e-9)
        assert chain._dist(end, next_bead) == pytest.approx(chain.PITCH)
    # It wraps both the eye and the ring, a bead either side of each wire.
    for outer, inner in ((chain.EYE_OUTER, chain.EYE_INNER), (chain.RING_OUTER, chain.RING_INNER)):
        index = beads.index(inner)
        assert outer in (beads[index - 1], beads[index + 1])


def test_strands_nest_without_crossing() -> None:
    # The inner strand hangs below the outer one, so the two U's never cross.
    inner_bottom = min(p[1] for p in chain.INNER_BEADS)
    assert inner_bottom <= chain.OUTER_BOTTOM_Y - chain.STRAND_GAP
    assert chain.INNER_SIDE_X - chain.OUTER_SIDE_X >= chain.BEAD_DIA


def test_link_goes_on_and_holds_its_end_beads() -> None:
    # Each dome's side mouth is narrower than a bead: the end bead snaps in as
    # the wall flexes and cannot fall back out, while its rod rides the slot
    # to the tip hole. Axially the tip hole and the far dome hold it too.
    assert chain.LINK_MOUTH_WIDTH < chain.BEAD_DIA
    assert chain.LINK_MOUTH_LENGTH < chain.BEAD_DIA
    assert chain.ROD_DIA < chain.LINK_SLOT_WIDTH
    assert chain.LINK_TIP_HOLE < chain.BEAD_DIA
    assert chain.ROD_DIA < chain.LINK_TIP_HOLE
    assert chain.LINK_END_BEAD_X + chain.BEAD_R < chain.LINK_LENGTH / 2.0
    assert chain.LINK_OD / 2.0 - chain.LINK_WALL > chain.BEAD_R
    # The crimp is modelled as an outside groove; it leaves wall under it.
    assert chain.LINK_WALL - chain.LINK_CRIMP_DEPTH >= 0.1


def test_link_volume_matches_its_shape() -> None:
    ro, ri = chain.LINK_OD / 2.0, chain.LINK_OD / 2.0 - chain.LINK_WALL
    e = chain.LINK_END_BEAD_X
    shell = math.pi * (ro**2 - ri**2) * 2.0 * e + 4.0 / 3.0 * math.pi * (ro**3 - ri**3)
    # Grooves, tip holes, the bead mouths and the rod slot come off the shell.
    assert 0.7 * shell < chain.link_volume() < shell


def test_chain_edges_fit_the_balloon_walk() -> None:
    # Its beads draw only silhouettes, so the drawings balloon the chain from
    # its rod/bead circles, two per link; the walk samples at most this many.
    from _drawing_balloons import _VISIBLE_EDGES_PER_INSTANCE

    assert 2 * (chain.BEAD_COUNT - 1) <= _VISIBLE_EDGES_PER_INSTANCE


def test_purchased_parts_name_their_skus() -> None:
    assert _config.parts("dt-vn-keeper-chain")["supplier_skus"] == [chain.CHAIN_SKU]
    assert _config.parts("dt-vn-keeper-chain-link")["supplier_skus"] == [chain.LINK_SKU]
    assert int(_config.parts("dt-vn-keeper-chain-link")["quantity"]) == 1


def test_catalogue_bead_diameter_preserves_the_installed_sphere() -> None:
    assert chain.BEAD_DIA == pytest.approx(2.38125, abs=1e-12)
    assert chain.BEAD_DIA / chain.MM_PER_IN == pytest.approx(3 / 32, abs=1e-12)
    assert 2 * chain.BEAD_R == pytest.approx(chain.BEAD_DIA, abs=1e-12)


# Lightweight callback doubles below are not native SOLIDWORKS-result evidence.
_VIEWED_CONFIGURATION = "Keeper catalogue viewed configuration"
_ACTIVE_CONFIGURATION = "Different active installed configuration"
_SOURCE_PATH = "D:/native/keeper-chain.SLDPRT"
_NAME = "CatalogueBeadDiameter"
_FULL_NAME = f"{_NAME}@SeedProfile@keeper-chain.SLDPRT"
_BEAD_MM = 2.38125


class _NativeDimension:
    def __init__(self, *, values=(_BEAD_MM / 1000.0,)):
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
        assert name == f"{_NAME}@SeedProfile"
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
        assert view is views["*Front"]
        assert keep == {_NAME: (0.156, 0.166)}
        assert view_label == "keeper catalogue bead diameter"
        assert dimensions_by_feature == {"SeedProfile": {_NAME}}
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
    settled = keeper_dimensions.annotate_keeper_bead(adapter, views)
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
    front = sheet.views["*Front"]
    assert sheet.source.ConfigurationManager.ActiveConfiguration.Name != (
        front.ReferencedConfiguration
    )
    assert sheet.presented[0].options == {
        "label": f"{_NAME}@SeedProfile",
        "units": "in",
        "configuration": _VIEWED_CONFIGURATION,
        "precision": 0,
        "expected_mm": pytest.approx(_BEAD_MM, rel=0, abs=1e-12),
        "presentation": "diameter",
        "fraction_denominator": 32,
        "callout": "CATALOGUE BEAD SIZE",
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
        front.annotations = [_Annotation(replacement)]
        front.ReferencedDocument = new_source
        sheet.settled()
        assert sheet.asserted[-1] is replacement
        assert new_source.parameter_calls == [f"{_NAME}@SeedProfile"]
        assert new_owner.calls == [(3, _VIEWED_CONFIGURATION)]
        assert new_owner.active_reads == 0
        assert replacement.native.calls == []
        assert replacement.native.active_reads == 0
        assert old_source.parameter_calls == old_parameter_calls
        assert old_owner.calls == old_value_calls
        assert front.GetDisplayDimensionCount() == 1
        assert all(
            view.GetDisplayDimensionCount() == 0
            for orientation, view in sheet.views.items()
            if orientation != "*Front"
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
        pytest.param(_BEAD_MM / 1000.0, id="scalar-not-array"),
        pytest.param("0.00238125", id="string-not-array"),
        pytest.param((_BEAD_MM / 1000.0, _BEAD_MM / 1000.0), id="multiple-values"),
        pytest.param((1.3 / 1000.0,), id="wrong-native-diameter"),
        pytest.param((-_BEAD_MM / 1000.0,), id="negative-native-diameter"),
        pytest.param(((_BEAD_MM + 2e-5) / 1000.0,), id="outside-existing-tolerance"),
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
    keeper_sheet.owner.values = ((_BEAD_MM + offset_mm) / 1000.0,)
    keeper_sheet.settled()
    assert keeper_sheet.owner.calls == [(3, _VIEWED_CONFIGURATION)]


@pytest.mark.parametrize(
    "fault",
    [
        "configuration",
        "source-path",
        "source-owner",
        "dimension-name",
        "seed-profile",
        "diameter-type",
        "missing-owner-dimension",
        "unprovided-tolerance",
        "missing-front-reference",
        "duplicate-front-reference",
        "missing-annotation-with-count",
        "foreign-annotation-with-count",
        "foreign-front-reference",
    ],
)
def test_final_source_and_inventory_drift_fail_closed(keeper_sheet, fault):
    sheet = keeper_sheet
    front = sheet.views["*Front"]
    display = front.annotations[0].display
    if fault == "configuration":
        front.ReferencedConfiguration = _ACTIVE_CONFIGURATION
    elif fault == "source-path":
        front.ReferencedDocument = _Source(_NativeDimension())
        front.ReferencedDocument.path = "D:/native/foreign-chain.SLDPRT"
    elif fault == "source-owner":
        sheet.owner.FullName = f"{_NAME}@SeedProfile@foreign-chain.SLDPRT"
    elif fault == "dimension-name":
        display.native.Name = "RodDiameter"
    elif fault == "seed-profile":
        display.native.FullName = f"{_NAME}@InstalledRod@keeper-chain.SLDPRT"
    elif fault == "diameter-type":
        display.Type2 = 2
    elif fault == "missing-owner-dimension":
        sheet.source.owner_dimension = None
    elif fault == "unprovided-tolerance":
        display.native.Tolerance.Type = 2
    elif fault == "missing-front-reference":
        front.annotations = []
    elif fault == "duplicate-front-reference":
        front.annotations.append(_Annotation(_Display()))
    elif fault == "missing-annotation-with-count":
        front.annotations = []
        front.count_override = 1
    elif fault == "foreign-annotation-with-count":
        front.annotations[0].annotation_type = 1
        front.count_override = 1
    elif fault == "foreign-front-reference":
        display.native.FullName = f"{_NAME}@SeedProfile@foreign-chain.SLDPRT"
    else:
        raise AssertionError(f"Unhandled fault {fault}")
    with pytest.raises(RuntimeError):
        sheet.settled()
    assert sheet.asserted == []


@pytest.mark.parametrize("orientation", ["*Top", "*Right", "*Isometric"])
def test_reference_in_any_other_view_is_rejected(keeper_sheet, orientation):
    keeper_sheet.views[orientation].annotations = [_Annotation(_Display())]
    with pytest.raises(RuntimeError, match="inventory"):
        keeper_sheet.settled()
