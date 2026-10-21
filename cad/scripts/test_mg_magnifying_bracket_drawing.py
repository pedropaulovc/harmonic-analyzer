"""Offline manufactured-interval and native-print contracts for the L bracket."""

from __future__ import annotations

import asyncio
import itertools
import math
from types import SimpleNamespace
import copy

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
        "FootCornerR": ("*Front", spec.FOOT_CORNER_CALLOUT),
        "MouthChamfer": ("section A-A", drawing.MOUTH_PRINT_CALLOUT),
        "ThreadRootEnvelope": ("*Right", spec.THREAD_ENVELOPE_CALLOUT),
    }
    actual = {
        name: (display.view, display.text[4])
        for name, display in displays.items() if display.text
    }
    assert actual == expected
    assert " ".join(displays["RootR"].text[4].split()) == " ".join(spec.ROOT_CALLOUT.split())
    assert " ".join(displays["MouthChamfer"].text[4].split()) == " ".join(spec.MOUTH_CALLOUT.split())
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


class _LayoutDimension:
    def __init__(self, name, position, *, width=0.034, centered=False, fault=None):
        self.name = name
        self.position = (*position, 0.0)
        self.width = width
        self.centered = centered
        self.fault = fault
        self.value = 0.0002
        self.tolerance = (-0.00005, 0.00005)
        self.qualifier = drawing.MOUTH_PRINT_CALLOUT
        self.attachments = (object(), object())

    def GetPosition(self):
        return self.position

    def SetPosition2(self, x, y, z):
        if self.fault == "move_refused":
            return False
        if self.fault != "move_ignored":
            self.position = (x, y, z)
        return True

    def display(self, section):
        x, y, _z = self.position
        left = x - self.width / 2.0 if self.centered else x
        base = y - 0.0073038
        qualifier_rows = self.qualifier.splitlines()
        shoulder = base - (len(qualifier_rows) - 1) * 0.0055563
        a = section.project((joint.NECK_HALF_X / 1000.0, joint.TAP_DRILL_DIA / 2000.0, 0.0))
        b = section.project(((joint.NECK_HALF_X - joint.MOUTH_CHAMFER) / 1000.0, joint.TAP_DRILL_DIA / 2000.0, 0.0))
        # Simulated post-rotation display: fixed model-attached witnesses,
        # horizontal size line, and R8's native tolerance/qualifier row pitch.
        return {
            "texts": [
                _native_text("0.20 ", left + self.width / 2.0 - 0.0103444, y - 0.0016941, 0.0103444),
                _native_text("+0.05", left + self.width / 2.0, y + 0.0027781, 0.0118806),
                _native_text("-0.05", left + self.width / 2.0, y - 0.0017476, 0.0112413),
                *(_native_text(row, left, base - index * 0.0055563, self.width)
                  for index, row in enumerate(qualifier_rows)),
            ],
            "lines": [
                _native_line(*a, a[0], shoulder),
                _native_line(*b, b[0], shoulder),
                _native_line(left, shoulder, b[0], shoulder),
            ],
        }


class _LayoutCaption:
    PropertyLinkedText = "<VLNAME> <VLLABEL>\n<VLSCALE> <VLSCALEV>"

    def __init__(self, *, fault=None):
        self.position = (0.209, 0.048, 0.0)
        self.fault = fault

    def GetAnnotation(self):
        return self

    def GetPosition(self):
        return self.position

    def SetPosition2(self, x, y, z):
        if self.fault != "caption_ignored":
            self.position = (x, y, z)
        return True

    def GetExtent(self):
        # R8 native six-value note extent relative to its actual GetPosition.
        x, y, _z = self.position
        return (x - 0.0231238, y - 0.0160045, 0.0, x + 0.0226268, y + 0.0001988, 0.0)


def _annotation_layout_fixture(monkeypatch, *, width=0.034, centered=False, fault=None):
    import _section_axis

    adapter, parent, section, iso = _mouth_layout_fixture(monkeypatch)
    drawing._mouth_section(adapter, parent, iso)
    annotation = _LayoutDimension("MouthChamfer", (0.330, 0.190), width=width, centered=centered, fault=fault)
    caption = _LayoutCaption(fault=fault)
    section.notes = [caption]

    def mark_display(view, original_y):
        dx, dy = view.turn((0.0, original_y - 0.080))
        x, y = view.Position[0] + dx, view.Position[1] + dy
        # Outer extents of R8's eight native line runs, kept as two complete
        # crosses. No annotation is deleted and no source identity is guessed.
        return {"lines": [
            _native_line(x - 0.0113862, y, x + 0.0113862, y),
            _native_line(x, y - 0.0113862, x, y + 0.0113862),
        ]}

    section.marks = [
        SimpleNamespace(display=lambda view, y=y: mark_display(view, y))
        for y in (0.100775, 0.141875)
    ]
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, item: item.name)
    monkeypatch.setattr(drawing, "annotation_display", lambda _a, item: (item.display(section), {}))
    monkeypatch.setattr(_section_axis, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_section_axis, "rebuild_drawing", lambda *_a, **_kw: None)

    def move(_adapter, item, dx, dy, *, label):
        x, y, z = item.GetPosition()
        if not item.SetPosition2(x + dx, y + dy, z):
            raise RuntimeError(f"failed to move {label}")

    monkeypatch.setattr(drawing, "move_annotation", move)
    return adapter, section, iso, annotation, caption


@pytest.mark.parametrize("width, centered", ((0.034, False), (0.036, True), (0.030, False)))
def test_native_text_and_caption_fit_beside_complete_mouth_profile(monkeypatch, width, centered):
    adapter, section, iso, annotation, caption = _annotation_layout_fixture(monkeypatch, width=width, centered=centered)
    physical = (annotation.value, annotation.tolerance, annotation.attachments, annotation.qualifier)
    fields = caption.PropertyLinkedText
    marks = tuple(section.marks)
    old_ink = Box(0.290, 0.0876962, 0.3514153, 0.1012781)
    iso_scale = Box(0.3204, 0.0884, 0.3796, 0.0920)
    assert old_ink.overlaps(iso_scale, tol=0.0) is not None
    drawing._layout_mouth_annotations(adapter, section, iso, [annotation])
    ink = drawing._dimension_layout_ink(adapter, annotation, label="mouth")
    profile = Box(*drawing._mouth_profile_box(adapter, section))
    extent = caption.GetExtent()
    caption_box = Box(extent[0], extent[1], extent[3], extent[4])
    text = Box(*ink.text)
    assert profile.xmin - text.xmax == pytest.approx(0.006)
    assert text.ymin - caption_box.ymax == pytest.approx(0.004)
    for box in (text, profile, caption_box):
        assert box.escape(_R8_REGION) is None
        assert box.ymin > _R8_ISO_OUTLINE[3] + 0.002
        assert box.gap(iso_scale) > 0.002
        assert box.ymin > 0.066
    for line in ink.leader:
        assert segment_box_overlap_length(Segment(line.x0, line.y0, line.x1, line.y1), caption_box) == 0.0
    assert (annotation.value, annotation.tolerance, annotation.attachments, annotation.qualifier) == physical
    assert tuple(section.marks) == marks
    assert caption.PropertyLinkedText == fields


@pytest.mark.parametrize("fault, width, message", (
    ("move_refused", 0.0614153, "failed to move"),
    ("move_ignored", 0.0614153, "callout placement did not persist"),
    ("caption_ignored", 0.0614153, "caption position did not persist"),
    (None, 0.150, "crosses the zone frame"),
))
def test_annotation_layout_refuses_ignored_moves_and_unfit_text(monkeypatch, fault, width, message):
    adapter, section, iso, annotation, _caption = _annotation_layout_fixture(monkeypatch, fault=fault, width=width)
    with pytest.raises(RuntimeError, match=message):
        drawing._layout_mouth_annotations(adapter, section, iso, [annotation])


@pytest.mark.parametrize("fault", ("missing_width", "nan_width", "missing_lines", "read_error"))
def test_native_text_layout_never_substitutes_nominal_boxes_for_missing_readbacks(monkeypatch, fault):
    adapter, section, _iso, annotation, _caption = _annotation_layout_fixture(monkeypatch)
    display = copy.deepcopy(annotation.display(section))
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
    adapter, section, iso, annotation, _caption = _annotation_layout_fixture(monkeypatch)
    monkeypatch.setattr(section, "GetOutline", lambda: _R8_SECTION_OUTLINE)
    with pytest.raises(RuntimeError, match="final complete thread-mouth outline.*crosses the zone frame"):
        drawing._layout_mouth_annotations(adapter, section, iso, [annotation])


def test_unwrapped_mouth_text_is_rejected_against_retained_native_center_marks(monkeypatch):
    adapter, section, iso, annotation, _caption = _annotation_layout_fixture(monkeypatch, width=0.0614153)
    annotation.qualifier = spec.MOUTH_CALLOUT
    marks = tuple(section.marks)
    with pytest.raises(RuntimeError, match="mouth callout.*crowds.*section centre mark"):
        drawing._layout_mouth_annotations(adapter, section, iso, [annotation])
    assert tuple(section.marks) == marks


def test_unreadable_center_mark_ink_is_not_treated_as_an_empty_caption_lane(monkeypatch):
    adapter, section, iso, annotation, _caption = _annotation_layout_fixture(monkeypatch)
    section.marks[0].display = lambda _view: {}
    with pytest.raises(RuntimeError, match="centre mark 0 has unreadable native ink"):
        drawing._layout_mouth_annotations(adapter, section, iso, [annotation])


@pytest.mark.parametrize("line, intersects", (
    ((0.310, 0.170, 0.310, 0.190), True),
    ((0.310, 0.190, 0.310, 0.170), True),
    ((0.295, 0.170, 0.295, 0.190), False),
    ((0.305, 0.180, 0.315, 0.180), True),
))
def test_retained_mark_dimension_line_intersection_is_independent_of_text_clearance(monkeypatch, line, intersects):
    adapter, section, iso, annotation, caption = _annotation_layout_fixture(monkeypatch)
    mark = SimpleNamespace(display=lambda _view: {
        "lines": [_native_line(0.300, 0.180, 0.320, 0.180)],
    })
    section.marks = [mark]
    original_display = annotation.display

    def display(view):
        native = original_display(view)
        native["lines"].append(_native_line(*line))
        return native

    annotation.display = display
    if intersects:
        with pytest.raises(RuntimeError, match="dimension line intersects section centre mark"):
            drawing._layout_mouth_annotations(adapter, section, iso, [annotation])
    else:
        drawing._layout_mouth_annotations(adapter, section, iso, [annotation])
    # Both text blocks are clear in EVERY case. Only the extra dimension
    # segment changes the verdict; a text/mark collision cannot mask the bug.
    mark_box = Box(0.300, 0.180, 0.320, 0.180)
    ink = drawing._dimension_layout_ink(adapter, annotation, label="mouth")
    extent = caption.GetExtent()
    caption_box = Box(extent[0], extent[1], extent[3], extent[4])
    assert Box(*ink.text).gap(mark_box) >= 0.002
    assert caption_box.gap(mark_box) >= 0.002
    assert section.marks == [mark]


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
    for name in ("read_required_properties", "stamp_drawing_summary", "set_hidden_lines_removed", "_project_side_view", "set_dimension_callouts", "rebuild_drawing", "add_property_linked_note", "_require_root_callout_inside", "_layout_mouth_annotations"):
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
