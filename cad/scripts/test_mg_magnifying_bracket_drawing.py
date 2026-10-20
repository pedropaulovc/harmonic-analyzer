"""Offline manufactured-interval and native-print contracts for the L bracket."""

from __future__ import annotations

import itertools
import math
from types import SimpleNamespace

import pytest

import build_mg_magnifying_bracket as part
import draw_mg_magnifying_bracket as drawing
import magnifying_bracket_joint_layout as mounting
import mg_lever_thread_joint as joint
import mg_magnifying_bracket_spec as spec
from _drawing_edges import ViewEdge, ViewEdges
from _printed_tolerance import printed_band_mm


def test_ordinary_locations_bound_the_actual_radial_wall() -> None:
    # A hole is located from the physical side and nose tip, NOT from an exact
    # centre datum. Independently enumerate those actual dimension corners.
    walls = []
    for radius, from_side, from_tip in itertools.product(
        (joint.NOSE_R - joint.NOSE_R_TOL, joint.NOSE_R + joint.NOSE_R_TOL),
        (joint.NOSE_R - joint.HOLE_LOCATION_TOL, joint.NOSE_R + joint.HOLE_LOCATION_TOL),
        (joint.NOSE_R - joint.HOLE_LOCATION_TOL, joint.NOSE_R + joint.HOLE_LOCATION_TOL),
    ):
        axis = (from_side - radius, from_tip - radius)
        walls.append(radius - math.hypot(*axis) - joint.THREAD_BORE_WANDER - joint.THREAD_ROOT_ENVELOPE / 2.0 - joint.MOUTH_CHAMFER_MAX)
    assert joint.WALL_MIN == pytest.approx(min(walls))
    assert 1.5 < min(walls) < 2.0  # floor versus target, not an invented 1.925
    assert joint.AXIS_OFFSET_MAX > joint.HOLE_LOCATION_TOL
    stated = float(spec.WALL_CALLOUT.split()[-2])
    assert stated <= min(walls) < stated + 0.001


def test_foot_joins_flush_without_changing_mounting_grip_or_pattern() -> None:
    assert part.FLANGE_X[1] == joint.NECK_THICKNESS / 2.0
    assert part.FLANGE_X[0] < -joint.NECK_THICKNESS / 2.0
    assert part.FLANGE_Z[1] - part.FLANGE_Z[0] == pytest.approx(mounting.SIDE_PLATE_THICKNESS)
    assert mounting.BRACKET_HOLE_POINTS[1][0] - mounting.BRACKET_HOLE_POINTS[0][0] == pytest.approx(mounting.SCREW_MACHINE_X[1] - mounting.SCREW_MACHINE_X[0])
    assert printed_band_mm(spec.DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"]) == mounting.FLANGE_THICKNESS_BAND
    assert all(point[1] == 0.0 and point[2] == part.FLANGE_Z[0] for point in mounting.BRACKET_HOLE_POINTS)
    # Both foot corner rounds fit the minimum side margin without a taper.
    minimum_half_foot = (mounting.SIDE_PLATE_HEIGHT - printed_band_mm(2)) / 2.0
    assert spec.ROOT_R + spec.FOOT_CORNER_R < minimum_half_foot - (joint.NOSE_R + joint.NOSE_R_TOL)


def test_every_marked_requirement_has_one_printed_home() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    maps = (drawing.FRONT_KEEP, drawing.BOTTOM_KEEP, drawing.SIDE_KEEP, drawing.MOUNTING_KEEP, drawing.TAP_KEEP)
    kept = [name for keep in maps for name in keep]
    assert len(kept) == len(set(kept))
    assert set(kept) == marked
    assert marked == set().union(*(set(names) for names in spec.DRAWING_PRECISION.values()))
    assert spec.SINGLE_LIMITS["ThreadEnvelope", "ThreadRootEnvelope"][0] > joint.THREAD_MAJOR


def test_mounting_callout_selects_the_visible_exit_not_the_hidden_entry(monkeypatch) -> None:
    visible = ViewEdges(
        label="front HLR mounting face",
        edges=tuple(
            ViewEdge(edge=object(), line=None, circle=(point[0], point[1], mounting.SIDE_PLATE_Z[1], 0.0, 0.0, 1.0, mounting.CLEARANCE_DIA / 2.0), vertices=None)
            for point in mounting.BRACKET_HOLE_POINTS
        ),
    )
    monkeypatch.setattr(drawing, "scan_view_edges", lambda _view, *, label: visible)
    assert drawing._mounting_rims(object()) == visible.edges
    # Mutation/pre-fix control: the real visible-edge matcher rejects an entry
    # rim even though its XY position, radius and normal all match.
    with pytest.raises(RuntimeError):
        visible.circle_at(mounting.BRACKET_HOLE_POINTS[1], mounting.CLEARANCE_DIA / 2.0, axis=(0.0, 0.0, 1.0), label="hidden entry")


class _Tolerance:
    def __init__(self, persist: bool) -> None:
        self.persist = persist
        self.kind = 0
        self.values = None

    @property
    def Type(self):
        return self.kind

    @Type.setter
    def Type(self, value):
        if self.persist:
            self.kind = value

    def SetValues(self, lower, upper):
        self.values = (lower, upper)
        return True


@pytest.mark.parametrize("persist", (True, False))
def test_native_max_requirements_are_set_and_read_back(monkeypatch, persist) -> None:
    dimensions = {key: SimpleNamespace(SystemValue=value / 1000.0, Tolerance=_Tolerance(persist)) for key, (value, _kind) in spec.SINGLE_LIMITS.items()}
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_named_dimension", lambda _adapter, feature, name: (None, dimensions[feature, name]))
    if not persist:
        with pytest.raises(RuntimeError, match="single limit"):
            part._single_limits(None)
    else:
        part._single_limits(None)
        assert all(d.Tolerance.Type == 6 and d.Tolerance.values == (0.0, 0.0) for d in dimensions.values())


def _placement_adapter(monkeypatch, statuses):
    reads = []
    features = {}
    for name, status in statuses.items():
        def native_status(name=name, status=status):
            reads.append(name)
            if isinstance(status, Exception):
                raise status
            return status

        sketch = SimpleNamespace(
            GetSketchPoints2=lambda: (object(),),
            GetSketchSegments=lambda: (),
            GetConstrainedStatus=native_status,
        )
        profile = SimpleNamespace(
            Name=f"{name}Placement",
            GetTypeName2=lambda: "ProfileFeature",
            GetSpecificFeature2=lambda sketch=sketch: sketch,
            GetNextSubFeature=lambda: None,
        )
        features[name] = SimpleNamespace(GetFirstSubFeature=lambda profile=profile: profile)
    model = SimpleNamespace(FeatureByName=features.get)
    bindings = []

    def bind(value, interface):
        bindings.append(interface)
        if value is model:
            assert interface == "IPartDoc"
        return value

    def lossy_named_status(*_args):
        raise AssertionError("must read the retained ISketch, not named SDK status")

    monkeypatch.setattr(part, "_early_bound", bind)
    return SimpleNamespace(currentModel=model, check_sketch_fully_defined=lossy_named_status), reads, bindings


def test_closed_native_wizard_placement_status_is_read_for_both_holes(monkeypatch) -> None:
    adapter, reads, bindings = _placement_adapter(monkeypatch, {"MountingHoles": 3, "LeverTap": 3})
    part._assert_placement_sketches_fully_defined(adapter)
    assert reads == ["MountingHoles", "LeverTap"]
    assert bindings[0] == "IPartDoc" and bindings.count("ISketch") == 2


@pytest.mark.parametrize("status", (None, "unknown", "3", True, 0, 1, 2, 4, RuntimeError("native read unavailable")))
@pytest.mark.parametrize("feature", ("MountingHoles", "LeverTap"))
def test_native_wizard_placement_refuses_every_non_fully_defined_result(monkeypatch, feature, status) -> None:
    states = {"MountingHoles": 3, "LeverTap": 3}
    states[feature] = status
    adapter, reads, _bindings = _placement_adapter(monkeypatch, states)
    with pytest.raises(RuntimeError):
        part._assert_placement_sketches_fully_defined(adapter)
    assert reads[-1] == feature


def test_native_wizard_placement_refuses_a_missing_feature(monkeypatch) -> None:
    adapter, _reads, _bindings = _placement_adapter(monkeypatch, {"MountingHoles": 3})
    with pytest.raises(RuntimeError, match="LeverTap: native part feature not found"):
        part._assert_placement_sketches_fully_defined(adapter)
