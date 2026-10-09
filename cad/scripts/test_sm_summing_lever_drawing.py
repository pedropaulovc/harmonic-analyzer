"""Offline contracts for the summing-lever drawing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _drawing_common as common
import draw_sm_summing_lever as drawing
import sm_summing_lever_spec
from _drawing_common import ViewEdge, ViewEdges, assert_dimension_measures
from _hole_spec import blind_cut_dia_mm
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1


def test_anchor_seats_are_the_purchased_anchors_own_threads() -> None:
    """Both lower spring anchors are purchased eyebolts threaded straight into
    this casting -- there is no nut -- so a seat that does not match its
    anchor, or a boss its anchor cannot span, is an unassemblable part."""
    plate, boss = sm_summing_lever_spec.HOLE_SPEC, sm_summing_lever_spec.COUNTER_HOLE_SPEC
    assert (plate.kind, plate.end) == ("tapped", "through_all")
    assert (boss.kind, boss.end) == ("tapped", "through_all")
    assert plate.size == ANCHOR_9489T111.thread_size
    assert boss.size == ANCHOR_9490T1.thread_size
    # Each anchor's thread must span the seat it screws into.
    assert ANCHOR_9489T111.thread_length_mm > sm_summing_lever_spec.PLATE_T
    assert ANCHOR_9490T1.thread_length_mm >= sm_summing_lever_spec.ANCHOR_H
    # ...and each tap must fit the feature it passes through.
    assert blind_cut_dia_mm(boss) < 2.0 * sm_summing_lever_spec.ANCHOR_R
    assert blind_cut_dia_mm(plate) < sm_summing_lever_spec.HOLE_EDGE_OFFSET


def _line(start, end):
    return ViewEdge(object(), (start, end), None, None)


def test_end_face_edge_is_the_rib_top_edge_not_the_flange_or_underside() -> None:
    """Datum B and the start-Z BASIC hang on the +Z END face: the rib flange
    5.08 mm inboard reads 3.35 for 8.43 (#1105), and the rib's underside edge
    shares the end plane but is hidden under the plate."""
    z = sm_summing_lever_spec.PLATE_L / 2.0
    top = _line((0.0, 15.24, z), (sm_summing_lever_spec.PLATE_W, 0.0, z))
    flange = _line((0.0, 15.24, z - sm_summing_lever_spec.PLATE_T), (44.45, 0.0, z - 5.08))
    underside = _line((sm_summing_lever_spec.PLATE_W, 0.0, z), (0.0, -15.24, z))
    plate_end = _line((37.04, 2.54, z), (sm_summing_lever_spec.PLATE_W, 2.54, z))
    edges = ViewEdges(label="plan", edges=(flange, underside, plate_end, top))
    assert drawing._end_face_edge(edges, x_mm=10.0) is top
    # The plate's own end edge only shows past the rib taper: two lines there.
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._end_face_edge(edges, x_mm=40.0)
    with pytest.raises(RuntimeError, match="expected one visible line"):
        drawing._end_face_edge(ViewEdges(label="plan", edges=(flange, underside)), x_mm=10.0)


def _dimension(mm: float, attached: tuple[object, ...]):
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: attached,
        GetAttachedEntityTypes=lambda: tuple(1 for _ in attached),
        IsDangling=lambda: False,
    )
    return SimpleNamespace(
        GetDimension2=lambda _index: SimpleNamespace(SystemValue=mm / 1000.0),
        GetAnnotation=lambda: annotation,
    )


@pytest.fixture
def identity(monkeypatch):
    monkeypatch.setattr(common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        common._sw_type_info, "early_bound_or_flag", lambda value, *_args: value
    )
    return SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))


def test_pitch_proof_rejects_an_equal_pitch_between_other_holes(identity) -> None:
    """Nineteen hole pairs measure CHANNEL_PITCH: the value cannot tell the
    seed/second pair from the next one down, only the attached rims can."""
    seed, second, third = object(), object(), object()
    pitch = sm_summing_lever_spec.CHANNEL_PITCH
    assert assert_dimension_measures(
        identity, _dimension(pitch, (second, seed)), expected_mm=pitch,
        label="spring-hole pitch", entities=(seed, second),
    ) == pytest.approx(pitch)
    with pytest.raises(RuntimeError, match=r"unmatched picks=\[0\]") as info:
        assert_dimension_measures(
            identity, _dimension(pitch, (second, third)), expected_mm=pitch,
            label="spring-hole pitch", entities=(seed, second),
        )
    assert "not the dimension between its named entities" in str(info.value)
    # One entity attached twice is not a span between two.
    with pytest.raises(RuntimeError, match=r"unmatched picks=\[1\]"):
        assert_dimension_measures(
            identity, _dimension(pitch, (seed, seed)), expected_mm=pitch,
            label="spring-hole pitch", entities=(seed, second),
        )
    # A third attachment or a dangling leader is not the named span either.
    with pytest.raises(RuntimeError, match=r"extra attachments=1"):
        assert_dimension_measures(
            identity, _dimension(pitch, (seed, second, third)), expected_mm=pitch,
            label="spring-hole pitch", entities=(seed, second),
        )
    # Identity passes, the value still has to match.
    with pytest.raises(RuntimeError, match=r"measures 7\.0565 mm, expected 8\.43"):
        assert_dimension_measures(
            identity, _dimension(pitch, (seed, second)), expected_mm=8.43,
            label="spring-hole start Z", entities=(seed, second),
        )


def test_bracket_receiver_is_blind_and_authored_after_ribs() -> None:
    from pathlib import Path
    import build_sm_summing_lever as part
    import magnifying_bracket_joint_layout as joint
    assert part.LEVER_HOLE_POINTS is joint.LEVER_HOLE_POINTS
    assert part.TAP_SPEC is joint.TAP_SPEC
    assert (part.TAP_SPEC.kind, part.TAP_SPEC.end) == ("tapped_bottoming", "blind")
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.index("await _middle_rib(adapter, drive_jobs)") < source.index(
        "await _bracket_mounting_taps(adapter)"
    )
    assert "DRILL_DEPTH + DRILL_POINT_DEPTH / 3.0" in source
    assert 'name="BracketMountingTaps"' in source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "mounting_rims[0].edge" in drawing_source
    assert "FULL THREAD DEPTH / TAP DRILL DEPTH" in drawing_source
    assert "BOTTOMING TAP -" in drawing_source
    assert '"hw-threaddepth": THREAD_DEPTH' in drawing_source
    assert '"hw-tapdrldepth": DRILL_DEPTH' in drawing_source
    assert "bracket tap callout omits native depths" in drawing_source
    assert part.TAP_SPEC.size == "#2-56"
    assert part.TAP_SPEC.depth_mm == 6.05
    assert part.TAP_SPEC.overrides_mm["ThreadDepth"] == 4.95
    assert joint.THREAD_DEPTH_BAND == 0.05
    assert joint.DRILL_DEPTH_BAND == 0.10
    assert joint.RECEIVER_DIMENSION_BANDS == {
        "CoefficientsPlate": {"D1": 0.05},
        "EdgeRibBack": {"D1": 0.05},
    }
    assert "variable.ToleranceMin" in drawing_source
    assert "variable.ToleranceMax" in drawing_source
    assert "variable = dynamic_dispatch(raw._oleobj_)" in drawing_source
    assert '_early_bound(raw, "ICalloutVariable")' not in drawing_source
    assert "ReceiverY0" in drawing_source
    assert "PlateThickness" in drawing.FRONT_KEEP
    assert "RibDepth" in drawing.TOP_KEEP
    assert "Bracket Receiver Note" in drawing_source
    assert "BRACKET TAP DRILL LATERAL WALL {DRILL_LATERAL_WALL_MIN:.3f} MIN." in source
    final_proof = source.index('"summing lever after native receiver bands"')
    assert source.index("_receiver_model_bands(adapter)") < final_proof
    assert source.index("_receiver_coordinate_dimensions(adapter)") < final_proof
    assert final_proof < source.index("artefacts = await save_part_and_images")
    assert "v_built, 1e-5 * v_built" in source


def test_receiver_rim_scan_uses_back_entry_face(monkeypatch) -> None:
    import magnifying_bracket_joint_layout as joint
    back = object()
    calls = []

    def circle_at(center, radius, *, axis, label):
        calls.append((center, radius, axis))
        return SimpleNamespace(edge=object())

    def scan(view, *, label):
        assert view is back
        return SimpleNamespace(circle_at=circle_at)

    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    assert len(drawing._mounting_rims(back)) == len(joint.LEVER_HOLE_POINTS)
    assert [call[0] for call in calls] == list(joint.LEVER_HOLE_POINTS)
    assert all(call[1] == joint.TAP_DRILL_DIA / 2.0 for call in calls)
    assert drawing._back_xy(joint.LEVER_HOLE_POINTS[0][0], 0.0)[0] > (
        drawing._back_xy(joint.LEVER_HOLE_POINTS[1][0], 0.0)[0]
    )


def test_receiver_view_is_on_a_back_view_sheet_with_real_binding() -> None:
    import ast
    from pathlib import Path
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "from _sw_type_info import" not in source
    assert '"*Back", *BACK_CENTER' in source
    assert "expected_sheet_names=SHEET_NAMES" in source
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "scan_view_edges":
                assert len(node.args) == 1
    assert 'length = _early_bound(raw, "ICalloutLengthVariable")' in source


def test_receiver_depth_bands_follow_owned_dimensions_without_native_name_guesses(monkeypatch) -> None:
    import _common
    import _drawing_marks
    import build_sm_summing_lever as part
    import pytest

    class Dimension:
        def __init__(self, name, owner, nominal, kind=0):
            self._name = name
            self.owner = owner
            self._value = nominal / 1000.0
            self.kind = kind

        @property
        def Name(self):
            return self._name

        @Name.setter
        def Name(self, value):
            if self.owner in {"BracketMountingTaps", "CosmeticThread1", "ReferencePlane"}:
                raise AssertionError("native Wizard dimension names must not be rewritten")
            self._name = value

        @property
        def FullName(self):
            return f"{self.Name}@{self.owner}"

        @property
        def SystemValue(self):
            return self._value

        def GetType(self):
            return self.kind

    def display(dimension):
        def get_dimension(index):
            assert index == 0
            return dimension
        return SimpleNamespace(GetDimension2=get_dimension)

    class Feature:
        def __init__(self, name, dimensions=(), children=()):
            self.Name = name
            self.displays = [display(dim) for dim in dimensions]
            self.children = children
            self.next_subfeature = None
            for current, following in zip(children, children[1:]):
                current.next_subfeature = following

        def Parameter(self, name):
            return next(
                (item.GetDimension2(0) for item in self.displays if item.GetDimension2(0).Name == name),
                None,
            )

        def GetFirstDisplayDimension(self):
            return self.displays[0] if self.displays else None

        def GetNextDisplayDimension(self, current):
            index = self.displays.index(current) + 1
            return self.displays[index] if index < len(self.displays) else None

        def GetFirstSubFeature(self):
            return self.children[0] if self.children else None

        def GetNextSubFeature(self):
            return self.next_subfeature

    # Native shape observed on the farm (2026-10-09): the tap drill depth lives
    # on a sketch subfeature, and each hole gets its own cosmetic thread.
    drill = Dimension("Tap Drill Depth", "Sketch14", 6.05)
    thread = Dimension("D1", "Hole Thread22", 4.95)
    thread_b = Dimension("D1", "Hole Thread23", 4.95)
    unrelated = Dimension("Depth", "ReferencePlane", 4.95)
    angular = Dimension("D3", "BracketMountingTaps", 4.95, kind=1)
    sketch_feature = Feature("Sketch14", [drill])
    thread_feature = Feature("Hole Thread22", [thread])
    thread_feature_b = Feature("Hole Thread23", [thread_b])
    taps = Feature(
        "BracketMountingTaps",
        [drill, thread, thread_b, unrelated, angular],
        [sketch_feature, thread_feature, thread_feature_b],
    )
    features = {
        name: Feature(name, [Dimension("D1", name, 5.08)])
        for name in part.RECEIVER_DIMENSION_BANDS
    }
    features["BracketMountingTaps"] = taps
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get))

    def invoke(value, interface, member, *args):
        attribute = getattr(value, member)
        if callable(attribute):
            return attribute(*args)
        assert not args
        return attribute

    monkeypatch.setattr(_common, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_common, "_com_invoke", invoke)
    monkeypatch.setattr(_drawing_marks, "_com_invoke", invoke)
    bands = []
    monkeypatch.setattr(
        part, "set_dimension_symmetric_tolerance",
        lambda adapter, feature, name, band: bands.append((feature, name, band)),
    )
    monkeypatch.setattr(part, "set_dimension_display_precision", lambda *args: None)
    monkeypatch.setattr(part, "mark_dimensions_for_drawing", lambda *args: None)
    inventory = []
    monkeypatch.setattr(part._telemetry, "info", inventory.append)
    part._receiver_model_bands(adapter)
    assert bands == [
        ("CoefficientsPlate", "PlateThickness", 0.05),
        ("EdgeRibBack", "RibDepth", 0.05),
        ("Hole Thread22", "D1", 0.05),
        ("Hole Thread23", "D1", 0.05),
        ("Sketch14", "Tap Drill Depth", 0.10),
    ]
    assert (drill.Name, thread.Name, thread_b.Name, unrelated.Name) == (
        "Tap Drill Depth", "D1", "D1", "Depth"
    )
    assert angular.Name == "D3"
    assert any("D3@BracketMountingTaps = 0.00495 SI" in row for row in inventory)
    assert any("D1@Hole Thread22 = 4.95 mm (feature Hole Thread22)" in row for row in inventory)
    assert any("Depth@ReferencePlane = 4.95 mm" in row for row in inventory)

    # Parent-only traversal: dimensions owned by subfeatures must not be
    # mistaken for parent parameters.
    taps.children = ()
    inventory.clear()
    for name in part.RECEIVER_DIMENSION_BANDS:
        features[name].displays[0].GetDimension2(0).Name = "D1"
    with pytest.raises(RuntimeError, match="expected 2 native FullThreadDepth .*found 0"):
        part._receiver_model_bands(adapter)
    assert inventory and any("D1@Hole Thread22" in row for row in inventory)
    # Two depths on ONE cosmetic thread (one hole uncovered) is ambiguous.
    taps.children = (sketch_feature, thread_feature)
    thread_feature.next_subfeature = None
    sketch_feature.next_subfeature = thread_feature
    thread_feature.displays.append(display(Dimension("D9", thread_feature.Name, 4.95)))
    for name in part.RECEIVER_DIMENSION_BANDS:
        features[name].displays[0].GetDimension2(0).Name = "D1"
    with pytest.raises(RuntimeError, match="expected 2 native FullThreadDepth \\(one per owner\\), found 2"):
        part._receiver_model_bands(adapter)


def test_receiver_lateral_wall_includes_lower_face_coordinate_band() -> None:
    import magnifying_bracket_joint_layout as joint

    drill_radius_max = (joint.TAP_DRILL_DIA + 0.10) / 2.0
    row = sm_summing_lever_spec.PLATE_T / 2.0
    lower_wall = row - joint.POSITION_BAND - drill_radius_max
    upper_wall = (
        sm_summing_lever_spec.PLATE_T - joint.LEVER_PLATE_THICKNESS_BAND
        - row - joint.POSITION_BAND - drill_radius_max
    )
    assert lower_wall >= 1.5
    assert upper_wall >= 1.5
