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
from _drawing_layout_check import DrawableRegion, LeaderSegment, find_leader_leader_crossings
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
        walls.append(radius - math.hypot(*axis) - joint.THREAD_BORE_WANDER - joint.THREAD_ROOT_ENVELOPE / 2.0 - joint.CHAMFER_LEG_MAX)
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


@pytest.mark.parametrize("missing", (None, "NeckThickness", "FlangeDepth", "RootR", "ThreadRootEnvelope"))
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
            if name == missing:
                continue
            assert name not in displays, "a dimension was imported into two homes"
            imported[view].add(name)
            display = displays[name] = _DrawingDisplay(name, view, imported)
            annotations.append(SimpleNamespace(GetSpecificAnnotation=lambda display=display: display))
        return annotations

    def mouth_section(_adapter, parent, _iso):
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
        "RootR": ("*Top", drawing.ROOT_PRINT_CALLOUT),
        "ThreadRootEnvelope": ("*Right", spec.THREAD_ENVELOPE_CALLOUT),
    }
    actual = {
        name: (display.view, display.text[4])
        for name, display in displays.items() if display.text
    }
    assert actual == expected
    assert " ".join(displays["RootR"].text[4].split()) == " ".join(spec.ROOT_CALLOUT.split())
    assert "MouthChamfer" not in displays and "FootCornerR" not in displays
    assert set(displays) == set().union(*spec.DRAWING_DIMENSIONS.values())


# R8 native GetOutline, 3:1, before any recipe repair. Its full-model box is
# much taller than the actual Z=0 cut. Keep both, rather than inventing a
# tiny outline around the visible mouth and thereby hiding the original bug.
_R8_SECTION_OUTLINE = (0.203362, 0.000537, 0.252638, 0.159463)
_R8_ISO_OUTLINE = (0.3169855, 0.1059865, 0.3830145, 0.1540135)
_R8_REGION = DrawableRegion(0.0127, 0.0127, 0.4191, 0.2667)


class _MouthSection:
    def __init__(self, *, fault=None, angle=0.0, extra_width=0.0):
        self.fault = fault
        self.Position = (0.228, 0.080)
        self.Angle = angle
        self.extra_width = extra_width
        self.cut_only = False
        self.notes = []
        self.marks = []
        self.moves = []

    def turn(self, point):
        c, s = math.cos(self.Angle), math.sin(self.Angle)
        return (c * point[0] - s * point[1], s * point[0] + c * point[1])

    def GetOutline(self):
        points = [
            self.turn((x - 0.228, y - 0.080))
            for x in (_R8_SECTION_OUTLINE[0] - self.extra_width, _R8_SECTION_OUTLINE[2] + self.extra_width)
            for y in (_R8_SECTION_OUTLINE[1], _R8_SECTION_OUTLINE[3])
        ]
        return (
            self.Position[0] + min(p[0] for p in points), self.Position[1] + min(p[1] for p in points),
            self.Position[0] + max(p[0] for p in points), self.Position[1] + max(p[1] for p in points),
        )

    def project(self, point):
        x, y, _z = point
        # The R8 mouth's visible ends were Y6.125/43.625; the origin is
        # therefore Y24.875, 55.125 mm below the whole-model outline centre.
        dx, dy = self.turn((-3.0 * y, (0.0 if self.fault == "end_on" else 3.0 * x) - 0.055125))
        return self.Position[0] + dx, self.Position[1] + dy

    def SetViewPosition(self, position, move_children):
        assert move_children is False
        self.moves.append(tuple(position))
        if self.fault == "move_refused":
            return False
        if self.fault != "move_ignored":
            self.Position = (self.Position[0] if self.fault == "still_aligned" else position[0], position[1])
        return True

    def GetSection(self):
        return self

    def SetDisplayOnlySurfaceCut(self, value):
        if self.fault != "uncut_geometry":
            self.cut_only = value
        # Native void; no success Boolean.

    def GetDisplayOnlySurfaceCut(self):
        return self.cut_only

    def GetNotes(self):
        return self.notes

    def GetAnnotationsByType(self, kind):
        assert kind == 13
        return self.marks


def _mouth_layout_fixture(monkeypatch, *, fault=None, angle=0.0, extra_width=0.0):
    parent = object()
    section = _MouthSection(fault=fault, angle=angle, extra_width=extra_width)
    iso = SimpleNamespace(GetOutline=lambda: _R8_ISO_OUTLINE)
    adapter = SimpleNamespace()

    def project(_adapter, view, point, *, label):
        if view is parent:
            return -point[1], -point[2]
        assert view is section
        return section.project(point)

    def create(_adapter, view, *, line_start, line_end, **kwargs):
        assert view is parent
        extent = (joint.NOSE_R + 3.0) / 1000.0
        assert line_start == pytest.approx((-extent, 0.0))
        assert line_end == pytest.approx((extent, 0.0))
        assert kwargs["scale"] == (3, 1)
        return section

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "create_section_view", create)
    monkeypatch.setattr(drawing, "sheet_region", lambda _a: _R8_REGION)
    for name in ("set_hidden_lines_removed", "rebuild_drawing"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    return adapter, parent, section, iso


@pytest.mark.parametrize("angle, extra_width", ((0.0, 0.0), (0.37, 0.0001), (-1.1, -0.0002)))
def test_section_rotates_and_fits_real_native_extent_without_rescaling_or_cropping(monkeypatch, angle, extra_width):
    adapter, parent, section, iso = _mouth_layout_fixture(monkeypatch, angle=angle, extra_width=extra_width)
    assert _R8_SECTION_OUTLINE[1] < _R8_REGION.ymin  # Frozen failure control.
    assert drawing._mouth_section(adapter, parent, iso) is section
    outline = Box(*section.GetOutline())
    assert outline.escape(_R8_REGION) is None
    assert outline.ymin - _R8_ISO_OUTLINE[3] >= 0.003
    assert outline.xmin > 0.250 and outline.ymax < 0.207
    assert outline.width == pytest.approx(0.158926)
    assert outline.height == pytest.approx(0.049276 + 2 * extra_width)
    origin = section.project((0.0, 0.0, 0.0))
    assert origin[0] > outline.center()[0]
    for point in ((0.01, 0.0, 0.0), (0.0, 0.01, 0.0)):
        assert math.dist(origin, section.project(point)) == pytest.approx(0.030)
    profile = Box(*drawing._mouth_profile_box(adapter, section))
    assert profile.escape(_R8_REGION) is None
    assert profile.width == pytest.approx(3.0 * joint.NECK_THICKNESS / 1000.0)
    assert profile.height == pytest.approx(6.0 * joint.NOSE_R / 1000.0)
    assert section.cut_only and len(section.moves) == 1


@pytest.mark.parametrize("fault, message", (
    ("uncut_geometry", "geometry beyond the cutting plane"),
    ("end_on", "both chamfer legs in true profile"),
    ("move_refused", "refused its measured placement"),
    ("move_ignored", "placement/alignment did not persist"),
    ("still_aligned", "placement/alignment did not persist"),
))
def test_section_refuses_native_display_projection_and_alignment_failures(monkeypatch, fault, message):
    adapter, parent, _section, iso = _mouth_layout_fixture(monkeypatch, fault=fault)
    with pytest.raises(RuntimeError, match=message):
        drawing._mouth_section(adapter, parent, iso)


def test_section_refuses_a_real_extent_that_cannot_fit_instead_of_shrinking_it(monkeypatch):
    adapter, parent, section, iso = _mouth_layout_fixture(monkeypatch, extra_width=0.002)
    with pytest.raises(RuntimeError, match="native outline does not fit"):
        drawing._mouth_section(adapter, parent, iso)
    assert not section.moves


def _native_text(text, x, y, width, *, height=0.0035):
    return {"t": text, "pos": (x, y, 0.0), "h": height, "w": width, "ref": 1, "ang": 0.0}


def _native_line(x0, y0, x1, y1):
    return (0.0, 0.0, 0.0, 0.0, x0, y0, 0.0, x1, y1, 0.0)


class _LayoutCaption:
    PropertyLinkedText = "<VLNAME> <VLLABEL>\n<VLSCALE> <VLSCALEV>"

    def __init__(self, *, fault=None, width=0.070):
        self.position = (0.209, 0.048, 0.0)
        self.fault = fault
        self.width = width

    def GetAnnotation(self):
        return self

    def GetPosition(self):
        return self.position

    def SetPosition2(self, x, y, z):
        if self.fault != "caption_ignored":
            self.position = (x, y, z)
        return True

    def GetExtent(self):
        # Frozen R8 height/anchor; width simulates the added ROTATED word.
        x, y, _z = self.position
        return (x - 0.0231238, y - 0.0160045, 0.0, x - 0.0231238 + self.width, y + 0.0001988, 0.0)


def _caption_layout_fixture(monkeypatch, *, fault=None, width=0.070):
    import _section_axis

    adapter, parent, section, iso = _mouth_layout_fixture(monkeypatch)
    drawing._mouth_section(adapter, parent, iso)
    caption = _LayoutCaption(fault=fault, width=width)
    section.notes = [caption]
    monkeypatch.setattr(_section_axis, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_section_axis, "rebuild_drawing", lambda *_a, **_kw: None)
    return adapter, section, iso, caption


@pytest.mark.parametrize("width", (0.070, 0.085))
def test_rotated_linked_caption_fits_beside_native_section_without_chamfer_size(monkeypatch, width):
    adapter, section, iso, caption = _caption_layout_fixture(monkeypatch, width=width)
    fields = caption.PropertyLinkedText
    drawing._layout_mouth_caption(adapter, section, iso)
    profile = Box(*drawing._mouth_profile_box(adapter, section))
    extent = caption.GetExtent()
    box = Box(extent[0], extent[1], extent[3], extent[4])
    assert profile.xmin - box.xmax == pytest.approx(0.004)
    assert profile.ymax == pytest.approx(box.ymax)
    assert box.escape(_R8_REGION) is None and box.ymin > _R8_ISO_OUTLINE[3] + 0.003
    assert caption.PropertyLinkedText == fields.replace("<VLLABEL>", "<VLLABEL> (ROTATED)")


@pytest.mark.parametrize("fault, width, message", (
    ("caption_ignored", 0.070, "caption position did not persist"),
    (None, 0.150, "crosses the zone frame"),
))
def test_caption_layout_refuses_ignored_moves_and_unfit_extent(monkeypatch, fault, width, message):
    adapter, section, iso, _caption = _caption_layout_fixture(monkeypatch, fault=fault, width=width)
    with pytest.raises(RuntimeError, match=message):
        drawing._layout_mouth_caption(adapter, section, iso)


@pytest.mark.parametrize("fault", ("missing_width", "nan_width", "missing_lines", "read_error"))
def test_native_text_layout_never_substitutes_nominal_boxes_for_missing_readbacks(monkeypatch, fault):
    adapter, annotation = object(), object()
    display = {"texts": [_native_text("12.50", 0.100, 0.200, 0.010)], "lines": [_native_line(0.100, 0.200, 0.110, 0.200)]}
    errors = {}
    if fault == "missing_width":
        display["texts"][-1].pop("w")
    elif fault == "nan_width":
        display["texts"][-1]["w"] = math.nan
    elif fault == "missing_lines":
        display.pop("lines")
    else:
        errors["GetTextPositionAtIndex"] = 1
    monkeypatch.setattr(drawing, "annotation_display", lambda *_a: (display, errors))
    with pytest.raises(RuntimeError, match="native"):
        drawing._dimension_layout_ink(adapter, annotation, label="mouth")


@pytest.mark.parametrize("wrapped", (False, True))
def test_inside_corner_callout_wrap_keeps_all_words_and_fits_actual_border_lane(monkeypatch, wrapped):
    text = drawing.ROOT_PRINT_CALLOUT if wrapped else spec.ROOT_CALLOUT
    # Simulated font advances use R8's measured full-row width. This tests
    # layout behavior; it is not proof of newly rendered native glyphs.
    advance = 0.0767764 / len(spec.ROOT_CALLOUT)
    rows = [_native_text("R0.25 max.", 0.0328618, 0.145, 0.0242764)]
    for index, row in enumerate(text.splitlines()):
        width = len(row) * advance
        rows.append(_native_text(row, 0.045 - width / 2.0, 0.1394437 - index * 0.0055563, width))
    shoulder_y = rows[-1]["pos"][1]
    left = min(row["pos"][0] for row in rows)
    right = max(row["pos"][0] + row["w"] for row in rows)
    display = {"texts": rows, "lines": [
        _native_line(left, shoulder_y, right, shoulder_y),
        _native_line(right, shoulder_y, 0.0908152, 0.115719),
    ]}
    monkeypatch.setattr(drawing, "annotation_display", lambda *_a: (display, {}))
    monkeypatch.setattr(drawing, "dimension_name", lambda *_a: "RootR")
    monkeypatch.setattr(drawing, "sheet_region", lambda *_a: _R8_REGION)
    monkeypatch.setattr(drawing, "model_point_in_view", lambda _a, _v, p, **_kw: (0.097375 + p[0], 0.2124488))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    assert " ".join(text.split()) == " ".join(spec.ROOT_CALLOUT.split())
    if wrapped:
        drawing._require_root_callout_inside(object(), object(), [object()])
        assert left > _R8_REGION.xmin and right + 0.003 < 0.091125
    else:
        assert left == pytest.approx(0.0066118)
        with pytest.raises(RuntimeError, match="crosses the zone frame"):
            drawing._require_root_callout_inside(object(), object(), [object()])


def test_annotation_rebuild_cannot_restore_the_r8_off_sheet_section_extent(monkeypatch):
    adapter, section, iso, _caption = _caption_layout_fixture(monkeypatch)
    monkeypatch.setattr(section, "GetOutline", lambda: _R8_SECTION_OUTLINE)
    with pytest.raises(RuntimeError, match="final complete thread-mouth outline.*crosses the zone frame"):
        drawing._layout_mouth_caption(adapter, section, iso)


def test_caption_layout_refuses_regenerated_orphan_marks_even_when_text_is_clear(monkeypatch):
    adapter, section, iso, _caption = _caption_layout_fixture(monkeypatch)
    section.marks = [object()]
    with pytest.raises(RuntimeError, match="centre marks returned"):
        drawing._layout_mouth_caption(adapter, section, iso)


def _tap_name_adapter(monkeypatch, *, count=1, fault=None, definition=None, resolved=None, native_class=" - 2B"):
    """Model distinct returned dispatch metadata and concrete string interfaces."""
    from win32com.client import dynamic

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
    native_by_dispatch, native_by_wrapper = {}, {}
    state.metadata_reads, state.variable_bindings = [], []
    returned = []
    for variable in variables:
        pointer = object()
        wrapper = SimpleNamespace(_oleobj_=pointer)
        native_by_dispatch[pointer] = variable
        native_by_wrapper[id(wrapper)] = variable
        returned.append(wrapper)

    def dispatch(pointer):
        variable = native_by_dispatch[pointer]
        state.metadata_reads.append(variable.VariableName)
        return variable

    original_bind = drawing._early_bound

    def bind(value, interface):
        if id(value) in native_by_wrapper:
            # R7: merely relabelling this concrete dispatch as the base
            # interface invokes an incompatible VariableName DISPID.
            assert interface == "ICalloutStringVariable", "unsafe base-interface DISPID on returned variable dispatch"
            state.variable_bindings.append(interface)
            return native_by_wrapper[id(value)]
        return original_bind(value, interface)

    monkeypatch.setattr(dynamic, "Dispatch", dispatch)
    monkeypatch.setattr(drawing, "_early_bound", bind)
    callout = SimpleNamespace(
        GetText=get_text, SetText=set_text, IsHoleCallout=lambda: True,
        GetHoleCalloutVariables=lambda: tuple(returned),
    )
    return adapter, view, callout, state, required


@pytest.mark.parametrize("count", (0, 1, 2))
def test_automatic_tap_name_cleanup_keeps_the_associative_thread_and_required_notes(monkeypatch, count) -> None:
    adapter, view, callout, state, required = _tap_name_adapter(monkeypatch, count=count)
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
    assert state.metadata_reads == ["hw-threaddesc", "hw-threadclass"]
    assert state.variable_bindings == ["ICalloutStringVariable"]


@pytest.mark.parametrize("missing", ("<hw-threaddesc>", "<hw-threadclass>", "<hw-thru>"))
def test_tap_name_is_not_removed_without_an_authoritative_native_thread_callout(monkeypatch, missing) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch)
    definition = callout.GetText(5).replace(missing, "")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="native thread description/class/extent"):
        drawing._curate_tap_callout(adapter, view, SimpleNamespace(GetText=lambda _location: definition))
    assert not state.deleted
    assert any(note.GetText() == f"{joint.THREAD} Tapped Hole" for note in state.notes)


@pytest.mark.parametrize("resolved", ("", "THRU MATES MHA-MG-03 LEVER", "10-32 UNF 2B THRU"))
def test_tap_name_cleanup_requires_the_actual_resolved_thread_size(monkeypatch, resolved) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch, resolved=resolved)
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
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch, fault=fault)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match=message):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted


def test_tap_curation_preserves_a_nondefault_native_class_instead_of_hiding_it(monkeypatch) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch, native_class="3B")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="not the title-block default 2B"):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted and not state.set_text
    assert state.native_class.String == "3B"


@pytest.mark.parametrize("fault", ("selection_refused", "deletion_ignored"))
def test_tap_name_cleanup_requires_native_selection_and_actual_deletion(monkeypatch, fault) -> None:
    adapter, view, callout, state, _required = _tap_name_adapter(monkeypatch, fault=fault)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="redundant tap feature-name note"):
        drawing._curate_tap_callout(adapter, view, callout)
    assert not state.deleted


@pytest.mark.parametrize("fault", (None, "ignored_wrap", "leader_overshoot", "changed_template"))
def test_mounting_callout_reflows_native_size_clear_of_the_current_title_block(monkeypatch, fault):
    from dataclasses import replace

    edge, view = object(), object()
    native_definition = "2X <MOD-DIAM><hw-diam> <hw-thru>"
    state = SimpleNamespace(definition=native_definition, edge=None, view=None, value=mounting.CLEARANCE_DIA / 1000.0)
    display = SimpleNamespace(
        GetAnnotation=lambda: state, IsHoleCallout=lambda: True,
        GetText=lambda part: state.definition if part == 5 else "",
        SetText=lambda part, text: setattr(state, "definition", text),
    )
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    if fault == "changed_template":
        template = replace(template, title_block_left_m=0.205)
        monkeypatch.setitem(drawing.DRAWING_TEMPLATES, drawing.SPEC.layout, template)

    def insert(_adapter, actual_view, *, edge, callout_xy, label):
        state.edge, state.view, state.position = edge, actual_view, callout_xy
        return display

    def native_ink(_adapter, annotation):
        assert annotation is state
        if fault == "ignored_wrap":
            # Exact R9 text runs and shoulder: the last native size row
            # reaches X226.2288 into the title block. No rerun needed.
            texts = [
                _native_text("2 HOLES THRU", 0.1507677, 0.0540267, 0.0304646),
                _native_text("MATES MHA-SM-03 TAPPED HOLES 2X ", 0.1057712, 0.0484705, 0.0834215),
                _native_text("<MOD-DIAM>", 0.1891927, 0.048417, 0.0052784),
                _native_text(" 2.59 THRU ALL", 0.1944712, 0.0484705, 0.0317576),
            ]
            left, right, shoulder = 0.1041837, 0.2262288, 0.048417
        else:
            # Simulated native process/mate reflow. Conservatively retain
            # the old mate+2X width; this is not new rendered glyph evidence.
            x, y = state.position
            texts = [
                _native_text("DRILL 2X <MOD-DIAM> 2.59 THRU ALL", x - 0.060 / 2.0, y, 0.060),
                _native_text(spec.MOUNTING_HOLE_PROCESS, x - 0.0834215 / 2.0, y - 0.0055295, 0.0834215),
            ]
            left = x - 0.0834215 / 2.0 - 0.0015875
            right = x + 0.0834215 / 2.0
            shoulder = 0.048417
            if fault == "leader_overshoot":
                right = 0.2262288
        return {"texts": texts, "lines": [
            _native_line(0.0729985, 0.0790916, left, shoulder),
            _native_line(0.0711515, 0.0809084, 0.0729985, 0.0790916),
            _native_line(left, shoulder, right, shoulder),
        ]}, {}

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "add_native_hole_callout", insert)
    monkeypatch.setattr(drawing, "annotation_display", native_ink)
    monkeypatch.setattr(drawing, "sheet_region", lambda _a: _R8_REGION)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    if fault is None:
        assert drawing._add_mounting_callout(object(), view, edge) is display
        ink = drawing._dimension_layout_ink(object(), state, label="mounting")
        assert ink.text[2] + 0.002 <= template.title_block_left_m
        assert all(max(line.x0, line.x1) + 0.002 <= template.title_block_left_m for line in ink.leader)
    else:
        target = "mounting-hole line/leader" if fault == "leader_overshoot" else "mounting-hole callout"
        with pytest.raises(RuntimeError, match=target + ".*crowds.*title block"):
            drawing._add_mounting_callout(object(), view, edge)
    # Process/mate rows preserve the selected edge and every native variable.
    assert state.edge is edge and state.view is view
    assert state.value == mounting.CLEARANCE_DIA / 1000.0
    assert state.position == (0.166, 0.054)
    assert state.definition == "DRILL " + native_definition + "\n" + spec.MOUNTING_HOLE_PROCESS


def test_real_recipe_routes_wall_clear_of_frozen_r6_thread_leaders_without_moving_its_tip(monkeypatch, tmp_path) -> None:
    """Replay observed collisions; relocated native ink still needs seat proof."""
    adapter, side, callout, state, required = _tap_name_adapter(monkeypatch)
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
    for name in ("read_required_properties", "stamp_drawing_summary", "set_hidden_lines_removed", "_project_side_view", "set_dimension_callouts", "rebuild_drawing", "add_property_linked_note", "_require_root_callout_inside", "_layout_mouth_caption", "_set_hole_process", "_show_mouth_thread", "_remove_out_of_cut_mounting_marks", "_layout_linear_annotations"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    callout.GetAnnotation = lambda: object()
    monkeypatch.setattr(drawing, "_add_mounting_callout", lambda *_a: callout)
    monkeypatch.setattr(drawing, "_neck_to_foot_side", lambda *_a: object())
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


@pytest.mark.parametrize("fault", (None, "missing_edge", "ambiguous_edge", "wrong_attachment", "wrong_value", "basic", "precision"))
def test_neck_to_foot_location_uses_actual_fillet_tangent_edges_and_plain_native_dimension(monkeypatch, fault):
    import _drawing_edge_dimensions as edge_dimensions

    neck_edge, foot_edge = object(), object()
    neck = ViewEdge(neck_edge, ((joint.NECK_HALF_X, -joint.NOSE_R, 0.0), (joint.NECK_HALF_X, -joint.NOSE_R, mounting.SIDE_PLATE_Z[0] - spec.ROOT_R)), None, None)
    # The real foot edge is displaced inward in X by its physical corner
    # radius. Selecting X=NECK_HALF_X would pick no straight foot edge.
    foot = ViewEdge(foot_edge, ((joint.NECK_HALF_X - spec.FOOT_CORNER_R, mounting.SIDE_PLATE_Y[0], mounting.SIDE_PLATE_Z[0]), (joint.NECK_HALF_X - spec.FOOT_CORNER_R, mounting.SIDE_PLATE_Y[0], mounting.SIDE_PLATE_Z[1])), None, None)
    edges = [neck] if fault == "missing_edge" else [neck, foot]
    if fault == "ambiguous_edge":
        edges.append(ViewEdge(object(), foot.line, None, None))
    attached = (neck_edge, object() if fault == "wrong_attachment" else foot_edge)
    annotation = SimpleNamespace(GetAttachedEntities3=lambda: attached, GetAttachedEntityTypes=lambda: (1, 1), IsDangling=lambda: False)
    expected = -joint.NOSE_R - mounting.SIDE_PLATE_Y[0]
    native = SimpleNamespace(Name="RD1", SystemValue=(expected + (0.1 if fault == "wrong_value" else 0.0)) / 1000.0, Tolerance=SimpleNamespace(Type=1 if fault == "basic" else 0))
    display = SimpleNamespace(GetAnnotation=lambda: annotation, GetDimension2=lambda _i: native, ShowParenthesis=True, precision=0)
    display.SetPrecision3 = lambda primary, *_rest: setattr(display, "precision", 0 if fault == "precision" else primary)
    display.GetPrimaryPrecision2 = lambda: display.precision
    selected = {}

    def insert(_adapter, _view, **kwargs):
        selected.update(kwargs)
        return display

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(edge_dimensions, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(edge_dimensions._sw_type_info, "early_bound_or_flag", lambda value, *_args: value)
    monkeypatch.setattr(drawing, "add_edge_dimension", insert)
    monkeypatch.setattr(drawing, "model_point_in_view", lambda _a, _v, p, **_kw: (0.228 - p[1], 0.2124488 - p[2]))
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    side = SimpleNamespace(GetOutline=lambda: (0.216062, 0.1064632, 0.239938, 0.2235368))
    if fault:
        with pytest.raises(RuntimeError):
            drawing._neck_to_foot_side(adapter, side, ViewEdges("physical side edges", tuple(edges)))
    else:
        assert drawing._neck_to_foot_side(adapter, side, ViewEdges("physical side edges", tuple(edges))) is annotation
        assert selected["entities"] == (neck_edge, foot_edge)
        assert selected["orientation"] == "horizontal"
        assert abs(selected["p0"][0] - selected["p1"][0]) * 1000.0 == pytest.approx(expected)
        assert native.Name == "NeckToFootSide" and native.Tolerance.Type == 0
        assert display.precision == 2 and display.ShowParenthesis is False


@pytest.mark.parametrize("fault", (
    None, "in_cut_circle", "wrong_axis", "dangling", "selection_refused", "deletion_ignored",
    "wrong_document", "wrong_feature", "missing_correspondence", "roundtrip", "unresolved_id",
))
def test_section_mark_removal_requires_actual_out_of_cut_mounting_source(monkeypatch, fault):
    state = SimpleNamespace(selected=None, removed=[])
    bottom_marks = [object(), object()]
    marks = []
    source_edges = []
    for index, point in enumerate(mounting.BRACKET_HOLE_POINTS):
        circle = (*tuple(value / 1000.0 for value in (*point[:2], mounting.SIDE_PLATE_Z[1])), 0.0, 0.0, 1.0, mounting.CLEARANCE_DIA / 2000.0)
        if index == 1 and fault == "in_cut_circle":
            circle = (*circle[:2], 0.0, *circle[3:])
        if index == 1 and fault == "wrong_axis":
            circle = (*circle[:3], 1.0, 0.0, 0.0, circle[6])
        canonical = SimpleNamespace(identifier=(index + 1,), GetCurve=lambda circle=circle: SimpleNamespace(IsCircle=lambda: True, CircleParams=circle))
        source_edges.append(canonical)
        if index == 1 and fault == "wrong_feature":
            # Identical circle, different physical source feature: geometry
            # alone would accept this and must not authorize deletion.
            canonical = SimpleNamespace(identifier=(99,), GetCurve=canonical.GetCurve)
        edge = SimpleNamespace(canonical=canonical)
        mark = SimpleNamespace(GetAttachedEntities3=lambda edge=edge: (edge,), GetAttachedEntityTypes=lambda: (1,), IsDangling=lambda: fault == "dangling")
        def select(_append, _number, mark=mark):
            state.selected = mark
            return fault != "selection_refused"
        mark.Select2 = select
        marks.append(mark)

    def delete():
        if fault != "deletion_ignored":
            state.removed.append(state.selected)
            marks.remove(state.selected)

    model = SimpleNamespace(ClearSelection2=lambda _all: setattr(state, "selected", None), EditDelete=delete)
    def corresponding(entity):
        canonical = entity.canonical
        return None if fault == "missing_correspondence" and canonical.identifier == (2,) else canonical

    extension = SimpleNamespace(
        GetCorrespondingEntity2=corresponding,
        GetPersistReference3=lambda entity: entity.identifier,
        IsSamePersistentID=lambda a, b: -1 if fault == "unresolved_id" else int(a == b),
    )
    # Duplicate faces repeat shared edges; native ID deduplication must not
    # turn one physical edge into two competing source-inventory matches.
    feature = SimpleNamespace(GetFaces=lambda: (
        SimpleNamespace(GetEdges=lambda: tuple(source_edges)),
        SimpleNamespace(GetEdges=lambda: tuple(source_edges)),
    ))
    source = SimpleNamespace(
        GetType=lambda: 1,
        GetPathName=lambda: str(drawing.SOURCE.with_name("other.SLDPRT") if fault == "wrong_document" else drawing.SOURCE),
        FeatureByName=lambda name: feature if name == "MountingHoles" else None,
        Extension=extension,
    )
    section = SimpleNamespace(
        GetAnnotationsByType=lambda _kind: tuple(marks),
        GetSection=lambda: SimpleNamespace(GetDisplayOnlySurfaceCut=lambda: True),
        GetBaseView=lambda: SimpleNamespace(ReferencedDocument=source),
        GetCorrespondingEntity=lambda canonical: SimpleNamespace(canonical=source_edges[0] if fault == "roundtrip" else canonical),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    if fault:
        with pytest.raises(RuntimeError):
            drawing._remove_out_of_cut_mounting_marks(SimpleNamespace(currentModel=model), section)
        if fault not in ("selection_refused", "deletion_ignored"):
            assert not state.removed  # All identities must pass before deletion.
    else:
        drawing._remove_out_of_cut_mounting_marks(SimpleNamespace(currentModel=model), section)
        assert not marks and len(state.removed) == 2
    assert len(bottom_marks) == 2


@pytest.mark.parametrize("representation", ("lines", "polylines", "subdivided_polylines"))
@pytest.mark.parametrize("fault", (
    None, "empty", "null_data", "one_flank", "duplicate_flank", "outside", "hidden",
    "dangling", "no_import", "short_ticks", "broken_flank", "arc_chords", "bent_polyline",
    "malformed", "read_error",
))
def test_section_thread_requires_real_native_longitudinal_ink(monkeypatch, representation, fault):
    lines = [
        _native_line(0.300, 0.176, 0.3375, 0.176),
        _native_line(0.300, 0.197, 0.3375, 0.197),
    ]
    if fault == "empty":
        lines = []
    elif fault == "one_flank":
        lines[1] = _native_line(0.300, 0.176, 0.300, 0.197)
    elif fault == "duplicate_flank":
        lines[1] = lines[0]
    elif fault == "outside":
        lines[1] = _native_line(0.300, 0.207, 0.3375, 0.207)
    elif fault == "short_ticks":
        lines = [_native_line(0.300, y, 0.305, y) for y in (0.176, 0.197)]
    elif fault == "broken_flank":
        lines = [_native_line(a, y, b, y) for y in (0.176, 0.197)
                 for a, b in ((0.300, 0.310), (0.3275, 0.3375))]
    polylines = []
    if representation != "lines" or fault in ("arc_chords", "bent_polyline"):
        for line in lines:
            start, end = line[4:7], line[7:10]
            if representation == "subdivided_polylines":
                points = [tuple(a + fraction * (b - a) for a, b in zip(start, end))
                          for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)]
            else:
                points = [start, end]
            if fault == "bent_polyline":
                points = [start, ((start[0] + end[0]) / 2.0, start[1] + 0.001, start[2]), end]
            # SDK record: type, DataSize, colour, font, unused, unused,
            # point count, then XYZ triples. Geometry is native fixture ink.
            polylines.append((1 if fault == "arc_chords" else 0, 0, 0, 0, 0, 0, len(points),
                              *(value for point in points for value in point)))
        lines = []
    if fault == "malformed":
        if polylines:
            polylines[0] = polylines[0][:-1]
        else:
            lines[0] = lines[0][:-1]

    def polyline_count():
        if fault == "read_error":
            raise RuntimeError("native polyline count unavailable")
        return len(polylines)

    data = SimpleNamespace(
        GetLineCount=lambda: len(lines), GetLineAtIndex2=lambda i: lines[i],
        GetPolyLineCount=polyline_count, GetPolylineAtIndex2=lambda i: polylines[i],
        GetArcCount=lambda: 0,
    )
    # A readable annotation counterpart is diagnostic evidence, not permission
    # to rescue missing primary ICThread ink.
    counterpart = SimpleNamespace(
        GetLineCount=lambda: 2,
        GetLineAtIndex2=lambda i: _native_line(0.300, (0.176, 0.197)[i], 0.3375, (0.176, 0.197)[i]),
        GetPolyLineCount=lambda: 0, GetArcCount=lambda: 0,
    )
    thread = SimpleNamespace(
        GetDisplayData=lambda: None if fault == "null_data" else data,
        GetAnnotation=lambda: SimpleNamespace(
            Visible=3 if fault == "hidden" else 1, IsDangling=lambda: fault == "dangling",
            GetDisplayData=lambda: counterpart,
        ),
    )
    section = SimpleNamespace(GetCThreads=lambda: (thread,), GetDisplayMode2=lambda: 2, GetCThreadQuality=lambda: True)
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", messages.append)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "import_cosmetic_threads", lambda *_a: (0, 0) if fault == "no_import" else (1, 1))
    monkeypatch.setattr(drawing, "_mouth_profile_box", lambda *_a: (0.300, 0.170, 0.3375, 0.203))
    for name in ("set_hidden_lines_removed", "rebuild_drawing"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    if fault:
        with pytest.raises(RuntimeError) as failure:
            drawing._show_mouth_thread(object(), section)
        if fault == "null_data":
            assert "no display-data object" in str(failure.value)
            assert any("dataPresent=False" in message for message in messages)
            assert not any("native ink: GetLineCount=" in message for message in messages)
            assert any("annotation diagnostic: GetLineCount=2" in message for message in messages)
        elif fault == "empty":
            assert any("dataPresent=True" in message for message in messages)
            assert any("GetLineCount=0" in message for message in messages)
            assert any("GetPolyLineCount=0" in message for message in messages)
            assert "both longitudinal flanks" in str(failure.value)
            assert any("annotation diagnostic: GetLineCount=2" in message for message in messages)
        elif fault == "read_error":
            assert "IDisplayData.GetPolyLineCount" in str(failure.value)
            assert any("native polyline count unavailable" in message for message in messages)
    else:
        drawing._show_mouth_thread(object(), section)
        assert any("longitudinal_runs=" in message for message in messages)
        if representation != "lines":
            assert any("GetLineCount=0" in message for message in messages)
            assert any("GetPolyLineCount=2" in message for message in messages)
            assert any("native ink: GetPolylineAtIndex2(0)=" in message for message in messages)


@pytest.mark.parametrize("faults", (
    (), ("view.mode",), ("view.quality",), ("primary.data",), ("primary.line_count",),
    ("primary.line[0]",), ("primary.polyline[0]",), ("primary.arc[0]",),
    ("annotation.data",), ("annotation.line_count",), ("annotation.line[0]",),
    ("annotation.polyline[0]",),
    ("view.mode", "primary.line_count", "annotation.line[0]"),
))
def test_thread_diagnostics_collect_independent_readers_before_failure(monkeypatch, faults):
    calls = []
    messages = []
    lines = [_native_line(0.300, y, 0.3375, y) for y in (0.176, 0.197)]
    polylines = [(0, 0, 0, 0, 0, 0, 2, *line[4:]) for line in lines]
    arc = (*lines[0], 0.31875, 0.1865, 0.0, 0.0, 0.0, 1.0, 1.0)

    def probe(key, value):
        calls.append(key)
        if key in faults:
            raise RuntimeError(f"injected {key}")
        return value

    def display(scope):
        return SimpleNamespace(
            GetLineCount=lambda: probe(f"{scope}.line_count", 2),
            GetLineAtIndex2=lambda i: probe(f"{scope}.line[{i}]", lines[i]),
            GetPolyLineCount=lambda: probe(f"{scope}.polyline_count", 2),
            GetPolylineAtIndex2=lambda i: probe(f"{scope}.polyline[{i}]", polylines[i]),
            GetArcCount=lambda: probe(f"{scope}.arc_count", 1),
            GetArcAtIndex2=lambda i: probe(f"{scope}.arc[{i}]", arc),
        )

    primary, counterpart = display("primary"), display("annotation")
    annotation = SimpleNamespace(
        Visible=1, IsDangling=lambda: False,
        GetDisplayData=lambda: probe("annotation.data", counterpart),
    )
    thread = SimpleNamespace(
        GetAnnotation=lambda: annotation,
        GetDisplayData=lambda: probe("primary.data", primary),
    )
    section = SimpleNamespace(
        GetCThreads=lambda: (thread,),
        GetDisplayMode2=lambda: probe("view.mode", 2),
        GetCThreadQuality=lambda: probe("view.quality", True),
    )
    monkeypatch.setattr(drawing._telemetry, "info", messages.append)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "import_cosmetic_threads", lambda *_a: (1, 1))
    monkeypatch.setattr(drawing, "_mouth_profile_box", lambda *_a: (0.300, 0.170, 0.3375, 0.203))
    for name in ("set_hidden_lines_removed", "rebuild_drawing"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    required_errors = [key for key in faults if not key.startswith("annotation.")]
    if required_errors:
        with pytest.raises(RuntimeError, match="native ink read failed") as failure:
            drawing._show_mouth_thread(object(), section)
        assert all(key in str(failure.value) for key in required_errors)
    else:
        # Diagnostic counterpart errors do not change primary acceptance.
        drawing._show_mouth_thread(object(), section)
    assert "view.mode" in calls and "view.quality" in calls
    assert "primary.data" in calls and "annotation.data" in calls
    for scope in ("primary", "annotation"):
        if f"{scope}.data" in faults:
            assert not any(f"{scope}.{family}_count" in calls for family in ("line", "polyline", "arc"))
            continue
        for family, count in (("line", 2), ("polyline", 2), ("arc", 1)):
            assert f"{scope}.{family}_count" in calls
            for index in range(count):
                if f"{scope}.{family}_count" in faults:
                    assert f"{scope}.{family}[{index}]" not in calls
                else:
                    assert f"{scope}.{family}[{index}]" in calls
    assert all(any(f"injected {key}" in message for message in messages) for key in faults)
    if "view.quality" not in faults:
        assert any("GetCThreadQuality=True" in message for message in messages)


@pytest.mark.parametrize("case", ("flat", "roundoff", "gap", "y_chain"))
def test_thread_flank_union_is_order_independent_and_does_not_bridge(monkeypatch, case):
    import ast
    from itertools import permutations

    if case == "gap":
        intervals = ((0.300, 0.3075), (0.3075, 0.315), (0.3225, 0.330), (0.330, 0.3375))
    else:
        count = 5 if case == "y_chain" else 4
        endpoints = [0.300 + 0.0375 * index / count for index in range(count + 1)]
        intervals = tuple(zip(endpoints, endpoints[1:]))
    step = {"flat": 0.0, "roundoff": 1e-12, "gap": 1e-12, "y_chain": 6e-8}[case]
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", messages.append)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "import_cosmetic_threads", lambda *_a: (1, 1))
    monkeypatch.setattr(drawing, "_mouth_profile_box", lambda *_a: (0.300, 0.170, 0.3375, 0.203))
    for name in ("set_hidden_lines_removed", "rebuild_drawing"):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)

    for order in permutations(range(len(intervals))):
        messages.clear()
        # Actual counterexample: touching quarter spans in X, but each next
        # segment's Y decreases by 1e-12. Raw-Y sorting reverses their X order.
        lines = [
            _native_line(intervals[index][0], base_y - index * step,
                         intervals[index][1], base_y - index * step)
            for index in order for base_y in (0.176, 0.197)
        ]
        data = SimpleNamespace(
            GetLineCount=lambda: len(lines), GetLineAtIndex2=lambda i: lines[i],
            GetPolyLineCount=lambda: 0, GetArcCount=lambda: 0,
        )
        annotation = SimpleNamespace(Visible=1, IsDangling=lambda: False, GetDisplayData=lambda: None)
        thread = SimpleNamespace(GetAnnotation=lambda: annotation, GetDisplayData=lambda: data)
        section = SimpleNamespace(GetCThreads=lambda: (thread,), GetDisplayMode2=lambda: 2, GetCThreadQuality=lambda: True)
        if case in ("gap", "y_chain"):
            # The gap leaves two 15-mm islands; the Y chain's adjacent offsets
            # fit the tolerance but its complete spread does not. Neither may
            # become a full-width flank through interval or tolerance chaining.
            with pytest.raises(RuntimeError, match="both longitudinal flanks"):
                drawing._show_mouth_thread(object(), section)
        else:
            drawing._show_mouth_thread(object(), section)
            runs = ast.literal_eval(next(message.split("longitudinal_runs=", 1)[1]
                                         for message in messages if "longitudinal_runs=" in message))
            assert len(runs) == 2
            for _y, xmin, xmax in runs:
                assert (xmin, xmax) == pytest.approx((0.300, 0.3375), abs=1e-12)


@pytest.mark.parametrize("tapped", (False, True))
@pytest.mark.parametrize("fault", (None, "missing_diameter", "ignored_write"))
def test_native_process_rows_preserve_all_hole_variables_and_mate(monkeypatch, tapped, fault):
    import re

    # Established native callout slots: drill above, thread in prefix.
    drill_token = "<hw-thrutapdrldia>" if tapped else "<hw-diam>"
    definitions = {5: "<hw-threaddesc> <hw-thru>" if tapped else "", 6: "", 7: f"2X <MOD-DIAM>{drill_token} <hw-thru>", 8: ""}
    if fault == "missing_diameter":
        definitions[7] = definitions[7].replace(drill_token, "")
    original = dict(definitions)
    def set_text(part, text):
        if fault != "ignored_write":
            definitions[part + 4] = text
    display = SimpleNamespace(IsHoleCallout=lambda: True, GetText=definitions.get, SetText=set_text)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    mate = spec.TAP_PROCESS if tapped else spec.MOUNTING_HOLE_PROCESS
    if fault:
        with pytest.raises(RuntimeError):
            drawing._set_hole_process(display, mate=mate, tapped=tapped)
    else:
        drawing._set_hole_process(display, mate=mate, tapped=tapped)
        text = "\n".join(definitions.values())
        assert re.findall(r"<hw-[^>]+>", text) == re.findall(r"<hw-[^>]+>", "\n".join(original.values()))
        assert text.count("DRILL") == 1 and len(re.findall(r"\bTAP\b", text)) == int(tapped)
        assert text.count(mate) == 1
        assert "THRU" not in text.splitlines()  # No standalone literal repeat.
        if tapped:
            assert "45°" in text and "BOTH ENDS" in text and "BOTH LEGS" not in text


@pytest.mark.parametrize("fault", (None, "ignored_move", "own_crossing", "neighbour_crossing"))
def test_reviewed_linear_ink_is_placed_from_geometry_and_guards_actual_segments(monkeypatch, fault):
    """Frozen R10 primitives plus explicit simulated native move responses."""
    rows = {
        "NeckThickness": [("12.50 ±0.1", .1070212, .185, .0219576), (spec.NECK_THICKNESS_CALLOUT, .0726118, .1794437, .0907764)],
        "FlangeDepth": [("3.175", .1667191, .123, .0116375), (spec.FLANGE_DEPTH_CALLOUT, .140, .1174437, .0650757)],
        "MountingX0": [("4.00 ±0.05", .0327281, .0532219, .0245438)],
        "MountingX1": [("17.70 ±0.05", .0464351, .0432219, .0271299)],
        "MountingY0": [("6.35 ±0.05", .0177281, .0772219, .0245438)],
        "SeatToAxis": [("100.40", .1875951, .1622219, .0168097)],
        "FlangeWidth": [("49.25", .0718882, .0952219, .0142236)],
        # Newly authored dimension: simulated native ink, not frozen R10.
        "NeckToFootSide": [("0.85", .247, .096, .010)],
    }
    lines = {
        "NeckThickness": [(.091125, .2114488, .091125, .1784438), (.103625, .2114488, .103625, .1784438), (.091125, .1794438, .1633882, .1794438)],
        "FlangeDepth": [(.104625, .1120512, .141, .1120512), (.104625, .1152262, .141, .1152262), (.2050757, .1174438, .140, .1174438), (.140, .1174438, .140, .1152262), (.140, .1120512, .140, .1057012)],
        "MountingX0": [(.054375, .07265, .054375, .0522219), (.058375, .07265, .058375, .0522219), (.0327281, .0532219, .064725, .0532219)],
        "MountingX1": [(.054375, .07265, .054375, .0422219), (.072075, .07265, .072075, .0422219), (.048025, .0432219, .078425, .0432219)],
        "MountingY0": [(.057375, .07365, .029, .07365), (.0535796, .080, .029, .080), (.030, .07365, .030, .0673), (.030, .080, .030, .08635)],
        "SeatToAxis": [(.2215, .1120512, .195, .1120512), (.2340527, .2124488, .195, .2124488), (.196, .1120512, .196, .1622219), (.196, .2124488, .196, .1677781)],
        "FlangeWidth": [(.054375, .1110512, .054375, .0942219), (.103625, .1110512, .103625, .0942219), (.054375, .0952219, .103625, .0952219)],
        "NeckToFootSide": [(.2335, .110, .2335, .095), (.23435, .110, .23435, .095), (.2335, .096, .257, .096)],
    }
    items = {name: SimpleNamespace(name=name, dx=0.0, dy=0.0, CenterText=True, OffsetText=False) for name in rows}
    for item in items.values():
        item.GetSpecificAnnotation = lambda item=item: item

    def native_display(_adapter, item):
        native_lines = list(lines[item.name])
        if item.name == "NeckThickness":
            native_lines = [(a, b, c, d + item.dy) if i < 2 else (a, b + item.dy, c, d + item.dy) for i, (a, b, c, d) in enumerate(native_lines)]
        elif item.name == "FlangeDepth":
            native_lines = [(a if i < 2 else a + item.dx, b, c + item.dx, d) for i, (a, b, c, d) in enumerate(native_lines)]
        if item.name == "MountingY0" and item.OffsetText:
            native_lines.append((.030, .08635, rows[item.name][0][1] + item.dx, rows[item.name][0][2] + item.dy))
        if fault == "own_crossing" and item.name == "MountingX1" and item.dx:
            x = rows[item.name][0][1] + item.dx + .010
            native_lines.append((x, .041, x, .050))
        if fault == "neighbour_crossing" and item.name == "FlangeWidth" and items["MountingX1"].dx:
            x = rows["MountingX1"][0][1] + items["MountingX1"].dx + .010
            native_lines.append((x, .041, x, .050))
        return {
            "texts": [_native_text(text, x + item.dx, y + item.dy, width) for text, x, y, width in rows[item.name]],
            "lines": [_native_line(*line) for line in native_lines],
        }, {}

    def move(_adapter, item, dx, dy, *, label):
        if fault != "ignored_move":
            item.dx += dx
            item.dy += dy

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "annotation_display", native_display)
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, item: item.name)
    monkeypatch.setattr(drawing, "move_annotation", move)
    monkeypatch.setattr(drawing, "sheet_region", lambda _a: _R8_REGION)
    monkeypatch.setattr(drawing, "model_point_in_view", lambda _a, _v, p, **_kw: (.097375 + p[0], .080 + p[1]))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_kw: None)
    front = SimpleNamespace(GetOutline=lambda: (.048787, .1064632, .109213, .2235368))
    # Causal controls: actual frozen witnesses cross both horizontal size
    # text boxes, and the 6.35 row is struck at Y80 before placement.
    for name, line in (("MountingX0", lines["MountingX0"][0]), ("MountingX1", lines["MountingX1"][0]), ("MountingY0", lines["MountingY0"][1])):
        box = Box(*drawing._dimension_layout_ink(object(), items[name], label=name).text)
        assert segment_box_overlap_length(Segment(*line), box) > 0.0
    if fault:
        message = "did not settle" if fault == "ignored_move" else ("own native line" if fault == "own_crossing" else "neighbouring native line")
        with pytest.raises(RuntimeError, match=message):
            drawing._layout_linear_annotations(object(), front, object(), list(items.values()))
    else:
        drawing._layout_linear_annotations(object(), front, object(), list(items.values()))
        ink = {name: drawing._dimension_layout_ink(object(), item, label=name) for name, item in items.items()}
        assert ink["NeckThickness"].text[1] > .2235368
        assert ink["FlangeDepth"].text[2] < .196
        assert ink["MountingX0"].text[2] < .054375
        assert ink["MountingX1"].text[0] > .072075
        assert ink["MountingY0"].text[1] > .08635
        assert items["MountingY0"].OffsetText
