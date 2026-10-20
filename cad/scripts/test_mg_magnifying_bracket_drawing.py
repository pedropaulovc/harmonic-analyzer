"""Offline manufactured-interval and native-print contracts for the L bracket."""

from __future__ import annotations

import asyncio
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
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _layout_geometry import Box, Segment, segment_box_overlap_length
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
    maps = (drawing.FRONT_KEEP, drawing.BOTTOM_KEEP, drawing.SIDE_KEEP, drawing.MOUTH_KEEP, drawing.MOUNTING_KEEP, drawing.TAP_KEEP)
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


class _CalloutsComplete(Exception):
    """Stop the real recipe after all dimension imports, before hole picking."""


class _DrawingDisplay:
    def __init__(self, name, view, imported):
        self.dimension = SimpleNamespace(Name=name)
        self.view = view
        self.imported = imported
        self.text = {}

    def GetDimension(self):
        return self.dimension

    def SetText(self, location, text):
        assert self.dimension.Name in self.imported[self.view]
        assert location not in self.text, "a required callout was applied twice"
        self.text[location] = text


@pytest.mark.parametrize("missing", (None, "NeckThickness", "FlangeDepth", "RootR", "FootCornerR", "MouthChamfer", "ThreadRootEnvelope"))
def test_recipe_applies_every_callout_only_to_its_imported_owning_view(monkeypatch, tmp_path, missing) -> None:
    """Exercise the actual build loop and strict callout writer, not copied maps."""
    source = tmp_path / "bracket.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    imported = {}
    displays = {}

    async def open_model(_path):
        return SimpleNamespace(is_success=True, data=None)

    adapter = SimpleNamespace(
        currentModel=object(), open_model=open_model,
        _attempt=lambda fn, default=None: fn(),
        _get_attr_or_call=lambda obj, name: getattr(obj, name)() if callable(getattr(obj, name)) else getattr(obj, name),
    )

    def place(_adapter, _source, orientation, *_xy, scale):
        imported[orientation] = set()
        return orientation

    def curate(_adapter, view, *, keep, view_label, dimensions_by_feature):
        assert set(keep) <= set().union(*dimensions_by_feature.values())
        annotations = []
        for name in keep:
            # Native R5: the chamfer's axial leg collapses in the end view.
            if name == missing or (name == "MouthChamfer" and view != "section A-A"):
                continue
            assert name not in displays, "a dimension was imported into two homes"
            imported[view].add(name)
            display = displays[name] = _DrawingDisplay(name, view, imported)
            annotations.append(SimpleNamespace(GetSpecificAnnotation=lambda display=display: display))
        return annotations

    def mouth_section(_adapter, parent):
        assert parent == "*Right"
        imported["section A-A"] = set()
        return "section A-A"

    def complete(_view):
        raise _CalloutsComplete

    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_a, **_kw: (object(), object()))
    for name in ("read_required_properties", "stamp_drawing_summary", "set_hidden_lines_removed", "_project_side_view"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    monkeypatch.setattr(drawing, "_mouth_section", mouth_section)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "curate_hidden_dimensions", curate)
    monkeypatch.setattr(drawing, "_mounting_rims", complete)
    if missing is not None:
        # The strict writer still fails when an owning import lacks its callout
        # carrier; filtering against what happened to arrive must not hide it.
        with pytest.raises(RuntimeError, match=f"dimension callouts not applied:.*{missing}"):
            asyncio.run(drawing.build(adapter))
        return
    with pytest.raises(_CalloutsComplete):
        asyncio.run(drawing.build(adapter))
    expected = {
        "NeckThickness": ("*Top", spec.NECK_THICKNESS_CALLOUT),
        "FlangeDepth": ("*Top", spec.FLANGE_DEPTH_CALLOUT),
        "RootR": ("*Top", spec.ROOT_CALLOUT),
        "FootCornerR": ("*Front", spec.FOOT_CORNER_CALLOUT),
        "MouthChamfer": ("section A-A", spec.MOUTH_CALLOUT),
        "ThreadRootEnvelope": ("*Right", spec.THREAD_ENVELOPE_CALLOUT),
    }
    actual = {
        name: (display.view, display.text[4])
        for name, display in displays.items() if display.text
    }
    assert actual == expected
    assert set(displays) == set().union(*spec.DRAWING_DIMENSIONS.values())


@pytest.mark.parametrize("fault", (None, "uncut_geometry", "end_on"))
def test_mouth_section_shows_both_chamfer_legs_on_the_axis_plane(monkeypatch, fault) -> None:
    """The real section recipe must cut Z=0 and preserve axial/radial lengths."""
    parent = object()
    state = SimpleNamespace(cut_only=False)

    def set_cut_only(value):
        if fault != "uncut_geometry":
            state.cut_only = value
        # Native SetDisplayOnlySurfaceCut returns void, not a success boolean.

    definition = SimpleNamespace(
        SetDisplayOnlySurfaceCut=set_cut_only,
        GetDisplayOnlySurfaceCut=lambda: state.cut_only,
    )
    section = SimpleNamespace(GetSection=lambda: definition)

    def project(_adapter, view, point, *, label):
        x, y, z = point
        if view is parent:
            return -y, -z
        assert view is section
        scale = drawing.MOUTH_SECTION_SCALE[0] / drawing.MOUTH_SECTION_SCALE[1]
        return (0.0 if fault == "end_on" else scale * x), scale * y

    def create(_adapter, view, *, line_start, line_end, **kwargs):
        assert view is parent
        # The end view's projected horizontal cut is the model XY plane:
        # both endpoints have Z=0, and it spans beyond both neck sides.
        extent = (joint.NOSE_R + 3.0) / 1000.0
        assert line_start == pytest.approx((-extent, 0.0))
        assert line_end == pytest.approx((extent, 0.0))
        assert kwargs["scale"] == drawing.MOUTH_SECTION_SCALE
        return section

    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "create_section_view", create)
    for name in ("set_hidden_lines_removed", "rebuild_drawing", "position_section_caption"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    if fault is None:
        assert drawing._mouth_section(object(), parent) is section
        assert state.cut_only is True
    else:
        message = "geometry beyond the cutting plane" if fault == "uncut_geometry" else "both chamfer legs in true profile"
        with pytest.raises(RuntimeError, match=message):
            drawing._mouth_section(object(), parent)


def _tap_name_adapter(*, count=1, fault=None, definition=None, resolved=None, native_class=" - 2B"):
    state = SimpleNamespace(selected=None, notes=[], deleted=[])

    def clear(_all):
        state.selected = None

    def delete():
        if fault != "deletion_ignored":
            state.notes.remove(state.selected)
            state.deleted.append(state.selected)
        # IModelDoc2.EditDelete returns void.

    def note(text):
        native = SimpleNamespace(GetText=lambda: text)

        def select(append, mark):
            assert append is False and mark == 0
            state.selected = native
            return fault != "selection_refused"

        native.GetAnnotation = lambda: SimpleNamespace(Select2=select)
        return native

    state.notes = [note(f"{joint.THREAD} Tapped Hole") for _ in range(count)]
    required = (note(spec.WALL_CALLOUT), note("MATES MHA-MG-03 LEVER"))
    state.notes.extend(required)
    view = SimpleNamespace(GetNotes=lambda: tuple(state.notes))
    adapter = SimpleNamespace(currentModel=SimpleNamespace(ClearSelection2=clear, EditDelete=delete))
    native_definition = "THRU\nMATES MHA-MG-03 LEVER <hw-threaddesc> <hw-threadclass> <hw-thru>" if definition is None else definition
    state.definition = native_definition
    state.native_class = SimpleNamespace(VariableName="hw-threadclass", Type=3, String=native_class)
    state.native_description = SimpleNamespace(VariableName="hw-threaddesc", Type=3, String=f"{joint.THREAD} UNC")
    state.set_text = []

    def get_text(location):
        if location == 5:
            return state.definition
        if location != 1:
            return ""
        if resolved is not None:
            return resolved
        text = state.definition.replace("<hw-threaddesc>", state.native_description.String)
        text = text.replace("<hw-threadclass>", state.native_class.String).replace("<hw-thru>", "THRU")
        if fault == "stale_resolved_class" and state.set_text:
            return text + " 2B"
        if fault == "lost_resolved_size" and state.set_text:
            return ""
        return text

    def set_text(location, text):
        assert location == 1
        state.set_text.append(text)
        if fault != "class_definition_ignored":
            state.definition = text
        if fault == "native_class_changed":
            state.native_class.String = "3B"
        # IDisplayDimension.SetText returns void.

    variables = (state.native_description, state.native_class)
    if fault == "missing_class_variable":
        variables = (state.native_description,)
    elif fault == "duplicate_class_variable":
        variables = (*variables, state.native_class)
    elif fault == "non_string_class":
        state.native_class.Type = 1
    callout = SimpleNamespace(
        GetText=get_text, SetText=set_text, IsHoleCallout=lambda: True,
        GetHoleCalloutVariables=lambda: variables,
    )
    return adapter, view, callout, state, required


@pytest.mark.parametrize("count", (0, 1, 2))
def test_automatic_tap_name_cleanup_keeps_the_associative_thread_and_required_notes(monkeypatch, count) -> None:
    adapter, view, callout, state, required = _tap_name_adapter(count=count)
    definition = callout.GetText(5)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    assert drawing._curate_tap_callout(adapter, view, callout) == count
    assert tuple(state.notes) == required
    assert len(state.deleted) == count and state.selected is None
    assert callout.GetText(5) == definition.replace(" <hw-threadclass>", "")
    assert state.native_class.String == " - 2B"
    assert state.native_description.String == f"{joint.THREAD} UNC"
    assert "<hw-threaddesc>" in callout.GetText(5) and "<hw-thru>" in callout.GetText(5)
    assert "MATES MHA-MG-03 LEVER" in callout.GetText(1)
    assert joint.THREAD in callout.GetText(1) and "2B" not in callout.GetText(1)


@pytest.mark.parametrize("missing", ("<hw-threaddesc>", "<hw-threadclass>", "<hw-thru>"))
def test_tap_name_is_not_removed_without_an_authoritative_native_thread_callout(monkeypatch, missing) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter()
    definition = callout.GetText(5).replace(missing, "")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="native thread description/class/extent"):
        drawing._curate_tap_callout(adapter, view, SimpleNamespace(GetText=lambda _location: definition))
    assert not state.deleted
    assert any(note.GetText() == f"{joint.THREAD} Tapped Hole" for note in state.notes)


@pytest.mark.parametrize("resolved", ("", "THRU MATES MHA-MG-03 LEVER", "10-32 UNF 2B THRU"))
def test_tap_name_cleanup_requires_the_actual_resolved_thread_size(monkeypatch, resolved) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(resolved=resolved)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="no resolved native thread size"):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted and not state.set_text


@pytest.mark.parametrize("fault, message", (
    ("missing_class_variable", "one native string thread-class"),
    ("duplicate_class_variable", "one native string thread-class"),
    ("non_string_class", "one native string thread-class"),
    ("class_definition_ignored", "kept its thread class"),
    ("native_class_changed", "changed its native variable"),
    ("stale_resolved_class", "still prints 2B"),
    ("lost_resolved_size", "lost its resolved thread size"),
))
def test_tap_curation_refuses_lost_or_modified_native_thread_metadata(monkeypatch, fault, message) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(fault=fault)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match=message):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted


def test_tap_curation_preserves_a_nondefault_native_class_instead_of_hiding_it(monkeypatch) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(native_class="3B")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="not the title-block default 2B"):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted and not state.set_text
    assert state.native_class.String == "3B"


@pytest.mark.parametrize("fault", ("selection_refused", "deletion_ignored"))
def test_tap_name_cleanup_requires_native_selection_and_actual_deletion(monkeypatch, fault) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(fault=fault)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="redundant tap feature-name note"):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted


def test_real_recipe_routes_wall_clear_of_frozen_r6_thread_leaders_without_moving_its_tip(monkeypatch, tmp_path) -> None:
    """Replay observed collisions; relocated native ink still needs seat proof."""
    adapter, side, callout, state, required = _tap_name_adapter()
    source = tmp_path / "bracket.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    captured = {}

    async def open_model(_path):
        return SimpleNamespace(is_success=True, data=None)

    async def finalize(*_args, **kwargs):
        captured["finalize"] = kwargs
        return {"slddrw": "bracket.SLDDRW"}

    def project(_adapter, view, point, *, label):
        assert view is side
        assert point == pytest.approx((joint.NECK_HALF_X / 1000.0, 0.0, -0.0045))
        return (0.2280, 0.2169)  # Frozen R6 manufactured-wall landing.

    def leader(_adapter, text, **kwargs):
        captured["wall"] = (text, kwargs)

    adapter.open_model = open_model
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_a, **_kw: (adapter.currentModel, object()))
    monkeypatch.setattr(drawing, "place_view", lambda _a, _source, orientation, *_xy, **_kw: side if orientation == "*Right" else object())
    monkeypatch.setattr(drawing, "_mouth_section", lambda *_a: object())
    for name in ("read_required_properties", "stamp_drawing_summary", "set_hidden_lines_removed", "_project_side_view", "set_dimension_callouts", "rebuild_drawing", "add_property_linked_note"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    for name in ("curate_view_dimensions", "curate_hidden_dimensions"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: [])
    monkeypatch.setattr(drawing, "_mounting_rims", lambda _view: (SimpleNamespace(edge=object()), SimpleNamespace(edge=object())))
    monkeypatch.setattr(drawing, "scan_view_edges", lambda *_a, **_kw: SimpleNamespace(circle_at=lambda *_a, **_kw: SimpleNamespace(edge=object())))
    monkeypatch.setattr(drawing, "add_native_hole_callout", lambda *_a, **_kw: callout)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "add_leader_note", leader)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    assert asyncio.run(drawing.build(adapter)) == {"slddrw": "bracket.SLDDRW"}
    text, wall = captured["wall"]
    assert text == spec.WALL_CALLOUT and wall["view"] is side
    assert wall["attach_xy"] == (0.2280, 0.2169)
    assert tuple(state.notes) == required  # Only the duplicate name disappeared.
    assert "redundant_note_substrings" not in captured["finalize"]

    tap = LeaderSegment("tap", "hole-callout", 0.2305, 0.2131, 0.2856, 0.2276)
    automatic = LeaderSegment("automatic name", "note", 0.2344, 0.2274, 0.2280, 0.2156)
    old_wall = LeaderSegment("wall", "note", 0.2993, 0.1797, *wall["attach_xy"])
    assert len(find_leader_leader_crossings([tap, automatic, old_wall])) == 2
    assert segment_box_overlap_length(Segment(tap.x0, tap.y0, tap.x1, tap.y1), Box(0.2421, 0.2247, 0.2857, 0.2291)) > 0.011
    # Exercise both possible note-side junctions, not a single assumed side.
    # This is a route control, not fabricated post-move native display data.
    for junction_x in (wall["text_xy"][0] - 0.0007, wall["text_xy"][0] + 0.120):
        moved = LeaderSegment("wall", "note", junction_x, wall["text_xy"][1] - 0.0013, *wall["attach_xy"])
        assert not find_leader_leader_crossings([tap, moved])
