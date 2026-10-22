"""Offline native-identity regressions shared by the five supplier-nut consumers.

These doubles distinguish model members, view-mapped members and attachment
wrappers. They exercise production proofs, not native farm/COM coverage.
"""

from __future__ import annotations

import math
from types import SimpleNamespace as NS

import pytest

import _drawing_layout_audit as layout_audit
import _drawing_edge_dimensions as edge_dimensions
import _supplier_dimensions as supplier_dimensions
import _supplier_nut_drawing as nuts
import _supplier_screw_dimensions as screws
import mg_vn_wheel_axle_nut_spec as axle
import pn_vn_pen_adjust_nut_spec as adjust
import pn_vn_pen_hanger_jam_nut_spec as jam
import pn_vn_pen_hanger_nut_spec as hanger
import sm_vn_boss_hook_jam_nut_spec as bossjam


CONSUMERS = [
    pytest.param(spec, id=name)
    for name, spec in (
        ("jam", jam), ("axle", axle), ("adjust", adjust),
        ("hanger", hanger), ("bossjam", bossjam),
    )
]
FEATURE = nuts.FEATURE_BY_PLANE["Front"]
NOMINAL_NAME = f"ThreadNominalMajor@{FEATURE}@nut.SLDPRT"


def _point(x=0.0, *, identity=None, context="model"):
    return NS(X=x, Y=0.0, Z=0.0, context=context,
              native_identity=object() if identity is None else identity)


def _wrapper(point):
    return _point(point.X, identity=point.native_identity, context=point.context)


def _raise(error):
    def unreadable(*_args, **_kwargs):
        raise error
    return unreadable


class NativeNut:
    """Small mutable native graph; all identity decisions use native tokens."""

    def __init__(self, spec):
        self.spec = spec
        self.source = tuple(_point(x) for x in (
            -spec.SUPPLIER_NOMINAL_MAJOR_MM / 2000.0,
            spec.SUPPLIER_NOMINAL_MAJOR_MM / 2000.0,
        ))
        self.mapped = tuple(_point(context="drawing") for _ in range(2))
        self.attachments = tuple(_wrapper(point) for point in self.mapped)
        self.inventory = tuple(reversed(self.source))
        self.mapping = {id(source): mapped for source, mapped in
                        zip(self.source, self.mapped, strict=True)}
        self.mapping_reads = []
        self.comparisons = []
        self.segment = NS(
            GetType=lambda: 0, ConstructionGeometry=True,
            GetStartPoint2=lambda: _wrapper(self.source[0]),
            GetEndPoint2=lambda: _wrapper(self.source[1]),
        )
        self.sketch = NS(GetSketchSegments=lambda: (self.segment,),
                         GetSketchPoints2=lambda: self.inventory)
        self.feature = NS(GetSpecificFeature2=lambda: self.sketch)
        self.model = NS(FeatureByName=lambda name: self.feature if name == FEATURE else None)
        self.native = NS(
            FullName=NOMINAL_NAME, SystemValue=spec.SUPPLIER_NOMINAL_MAJOR_MM / 1000.0,
            GetFeatureOwner=lambda: self.feature, Tolerance=NS(Type=0),
        )
        self.front = NS(ReferencedDocument=self.model,
                        GetCorresponding=self.corresponding,
                        GetOutline=lambda: (0.02, 0.02, 0.06, 0.06))
        self.right = NS(GetOutline=lambda: (0.08, 0.02, 0.12, 0.06))
        self.display = self.make_display()
        self.source_display = NS(Type2=2)
        self.source_native = NS(FullName=NOMINAL_NAME)
        self.adapter = NS(swApp=NS(IsSame=self.same))

    def corresponding(self, source):
        # No inverse, source-sketch, annotation or coordinate fallback.
        assert any(source is point for point in self.source)
        self.mapping_reads.append(source)
        return self.mapping.get(id(source))

    def same(self, left, right):
        self.comparisons.append((left, right))
        return int(getattr(left, "native_identity", left)
                   is getattr(right, "native_identity", right))

    def make_display(self):
        annotation = NS(
            entities=tuple(reversed(self.attachments)), kinds=(11, 11),
            GetType=lambda: 4, Visible=1,
        )
        annotation.GetAttachedEntities3 = lambda: annotation.entities
        annotation.GetAttachedEntityTypes = lambda: annotation.kinds
        display = NS(Type2=2, GetDimension2=lambda _index: self.native,
                     GetAnnotation=lambda: annotation)
        annotation.GetSpecificAnnotation = lambda: display
        return display

    def prove(self, display=None):
        nuts._assert_nominal_carrier(
            self.adapter, self.front, self.display if display is None else display,
            self.spec.SUPPLIER_NOMINAL_MAJOR_MM,
        )

    def census(self):
        annotation = self.display.GetAnnotation()
        return screws._attachment_correspondence(
            self.adapter, self.front, source_sketch=self.sketch,
            entities=annotation.entities, types=annotation.kinds,
        )


@pytest.fixture
def native_nut(monkeypatch):
    def bind(obj, _interface):
        return obj

    for module in (nuts, screws, supplier_dimensions, edge_dimensions, layout_audit):
        monkeypatch.setattr(module, "_early_bound", bind)
    monkeypatch.setattr(screws, "_bind", bind)
    monkeypatch.setattr(edge_dimensions._sw_type_info, "early_bound_or_flag",
                        lambda obj, _interface, *_methods: obj)

    def create(spec=jam):
        case = NativeNut(spec)

        def named(_adapter, feature_name, names, *, feature):
            assert feature_name == FEATURE
            assert names == {"ThreadNominalMajor"}
            assert feature is case.feature
            return {"ThreadNominalMajor": (case.source_display, case.source_native)}

        monkeypatch.setattr(nuts, "_named_dimensions", named)
        return case
    return create


@pytest.mark.parametrize("spec", CONSUMERS)
def test_nominal_carrier_proves_two_distinct_view_mapped_endpoints(native_nut, spec):
    case = native_nut(spec)
    assert all(case.same(attached, source) == 0
               for attached in case.attachments for source in case.source)
    assert case.same(*case.mapped) == 0
    assert all(attached is not mapped and case.same(attached, mapped) == 1
               for attached, mapped in zip(case.attachments, case.mapped, strict=True))
    case.comparisons.clear()
    case.prove()
    assert case.mapping_reads == list(case.inventory)
    assert not any(
        getattr(left, "context", None) != getattr(right, "context", None)
        for left, right in case.comparisons
    ), "drawing attachments must never be compared directly with model endpoints"
    assert case.native.SystemValue * 1000.0 == pytest.approx(spec.SUPPLIER_NOMINAL_MAJOR_MM)


@pytest.mark.parametrize("target,attribute,value,message", [
    ("native", "GetFeatureOwner", lambda: object(), "native source owner"),
    ("native", "GetFeatureOwner", lambda: None, "native source owner"),
    ("native", "FullName", "Wrong@Other@nut.SLDPRT", "native source owner"),
    ("source_native", "FullName", "Wrong@Other@nut.SLDPRT", "native source owner"),
    ("display", "Type2", 6, "native source owner"),
    ("source_display", "Type2", 11, "native source owner"),
    ("segment", "GetType", lambda: 1, "construction line"),
    ("segment", "ConstructionGeometry", False, "construction line"),
    ("segment", "GetStartPoint2", lambda: None, "no endpoint"),
    ("segment", "GetEndPoint2", lambda: None, "no endpoint"),
    ("sketch", "GetSketchSegments", lambda: (), "one chord"),
    ("sketch", "GetSketchSegments", lambda: (object(), object()), "one chord"),
    ("model", "FeatureByName", lambda _name: None, "source sketch is missing"),
    ("front", "ReferencedDocument", None, "no referenced source part"),
])
def test_nominal_carrier_rejects_invalid_native_source(
    native_nut, target, attribute, value, message,
):
    case = native_nut()
    setattr(getattr(case, target), attribute, value)
    with pytest.raises(RuntimeError, match=message):
        case.prove()


def test_nominal_carrier_rejects_native_tolerance(native_nut):
    case = native_nut()
    case.native.Tolerance.Type = 1
    with pytest.raises(RuntimeError, match="native source owner"):
        case.prove()


@pytest.mark.parametrize("endpoint,axis", [(0, "X"), (1, "X"), (0, "Y"), (1, "Z")])
@pytest.mark.parametrize("offset", [1e-8, float("nan")])
def test_nominal_carrier_requires_exact_centred_source_coordinates(native_nut, endpoint, axis, offset):
    case = native_nut()
    point = case.source[endpoint]
    setattr(point, axis, getattr(point, axis) + offset)
    # Keep line wrappers faithful to the changed source, including Y and Z.
    case.segment.GetStartPoint2 = lambda: case.source[0]
    case.segment.GetEndPoint2 = lambda: case.source[1]
    with pytest.raises(RuntimeError, match="exact source"):
        case.prove()


@pytest.mark.parametrize("inventory,message", [
    (lambda c: (), "lost a chord endpoint"),
    (lambda c: (None, c.source[1]), "lost a chord endpoint"),
    (lambda c: (c.source[0], _point()), "lost a chord endpoint"),
    (lambda c: (c.source[0], c.source[0]), "lost a chord endpoint"),
    (lambda c: (*c.source, _wrapper(c.source[0])), "lost a chord endpoint"),
    (lambda c: (*c.source, _point()), "unexpected sketch points"),
])
def test_nominal_carrier_requires_exhaustive_distinct_source_inventory(native_nut, inventory, message):
    case = native_nut()
    case.inventory = inventory(case)
    with pytest.raises(RuntimeError, match=message):
        case.prove()


@pytest.mark.parametrize("entities,kinds,message", [
    (lambda c: (), (), "both endpoint attachments"),
    (lambda c: None, (11, 11), "both endpoint attachments"),
    (lambda c: c.attachments[:1], (11,), "both endpoint attachments"),
    (lambda c: (*c.attachments, _point()), (11, 11, 11), "both endpoint attachments"),
    (lambda c: c.attachments, (), "both endpoint attachments"),
    (lambda c: c.attachments, None, "both endpoint attachments"),
    (lambda c: c.attachments, (11,), "both endpoint attachments"),
    (lambda c: c.attachments, (11, 11, 11), "both endpoint attachments"),
    (lambda c: c.attachments, (10, 11), "both endpoint attachments"),
    (lambda c: (None, c.attachments[1]), (11, 11), "view-mapped source endpoint"),
    (lambda c: (c.attachments[0], _wrapper(c.attachments[0])), (11, 11), "view-mapped source endpoint"),
    (lambda c: (c.attachments[0], _point(context="drawing")), (11, 11), "view-mapped source endpoint"),
])
def test_nominal_carrier_requires_both_exact_attachment_members(native_nut, entities, kinds, message):
    case = native_nut()
    annotation = case.display.GetAnnotation()
    annotation.entities, annotation.kinds = entities(case), kinds
    with pytest.raises(RuntimeError, match=message):
        case.prove()


@pytest.mark.parametrize("mapping", ["missing", "null", "foreign", "duplicate"])
def test_nominal_carrier_requires_complete_injective_view_mapping(native_nut, mapping):
    case = native_nut()
    if mapping == "missing":
        del case.mapping[id(case.source[0])]
    else:
        case.mapping[id(case.source[0])] = {
            "null": None, "foreign": _point(context="drawing"),
            "duplicate": case.mapped[1],
        }[mapping]
    with pytest.raises(RuntimeError, match="view-mapped source endpoint"):
        case.prove()


@pytest.mark.parametrize("comparison", [
    "source-self", "mapped-self", "attachment-self", "positive", "negative",
    "source-distinctness", "mapped-distinctness",
])
@pytest.mark.parametrize("result", [2, "error"])
def test_nominal_carrier_requires_supported_positive_self_and_negative_controls(
    native_nut, comparison, result,
):
    case = native_nut()
    pairs = {
        "source-self": (case.source[0], case.source[0]),
        "mapped-self": (case.mapped[0], case.mapped[0]),
        "attachment-self": (case.attachments[0], case.attachments[0]),
        "positive": (case.attachments[0], case.mapped[0]),
        "negative": (case.attachments[0], case.mapped[1]),
        "source-distinctness": tuple(case.inventory),
        "mapped-distinctness": tuple(reversed(case.mapped)),
    }
    left_target, right_target = pairs[comparison]

    def same(left, right):
        if left is left_target and right is right_target:
            if result == "error":
                raise OSError("native comparison unreadable")
            return result  # swObjectUnsupported is neither positive nor negative.
        return case.same(left, right)

    case.adapter.swApp.IsSame = same
    with pytest.raises(RuntimeError, match="view-mapped source endpoint"):
        case.prove()
    if result == "error":
        assert "native comparison unreadable" in str(case.census())


@pytest.mark.parametrize("target,attribute", [
    ("feature", "GetSpecificFeature2"), ("sketch", "GetSketchSegments"),
    ("sketch", "GetSketchPoints2"), ("segment", "GetStartPoint2"),
    ("annotation", "GetAttachedEntities3"), ("annotation", "GetAttachedEntityTypes"),
])
def test_nominal_carrier_preserves_source_and_attachment_read_errors(native_nut, target, attribute):
    case = native_nut()
    obj = case.display.GetAnnotation() if target == "annotation" else getattr(case, target)
    error = OSError(f"{target}.{attribute} unreadable")
    setattr(obj, attribute, _raise(error))
    with pytest.raises(OSError, match="unreadable") as caught:
        case.prove()
    assert caught.value is error


def test_nominal_carrier_refuses_lost_source_sketch_without_fallback(native_nut):
    case = native_nut()
    case.feature.GetSpecificFeature2 = lambda: None
    with pytest.raises((AttributeError, RuntimeError), match="GetSketchSegments|source sketch"):
        case.prove()
    assert not case.mapping_reads


@pytest.mark.parametrize("failure", ["inventory", "mapping"])
def test_correspondence_preserves_read_failure_in_refused_census(native_nut, failure):
    case = native_nut()
    error = OSError(f"{failure} native read failed")
    if failure == "inventory":
        # The exact-chord inventory read succeeds; the mapping census must
        # refuse its own failed reacquisition rather than reuse stale members.
        calls = []

        def inventory():
            calls.append(1)
            if len(calls) == 1:
                return case.inventory
            raise error

        case.sketch.GetSketchPoints2 = inventory
    else:
        case.front.GetCorresponding = _raise(error)
    with pytest.raises(RuntimeError, match="view-mapped source endpoint"):
        case.prove()
    census = case.census()
    assert census["proven"] is False
    row = census["sources"][0]
    detail = row["inventory_error"] if failure == "inventory" else row["members"][0]["forward"]
    assert detail == {"error_type": "OSError", "message": str(error)}


def _physical_display(case, name, value_mm, edges, *, precision, denominator=None, callout=""):
    """Persisted physical-edge state consumed by both production validators."""
    native = NS(FullName=name, SystemValue=value_mm / 1000.0)
    annotation = NS(
        GetAttachedEntities3=lambda: tuple(edge.edge for edge in edges),
        GetAttachedEntityTypes=lambda: (1, 1), GetAttachedEntityCount3=lambda: 2,
        IsDangling=lambda: False, Visible=1, OwnerType=0, Owner=case.front,
        GetType=lambda: 4,
    )
    display = NS(
        Type2=2, GetDimension2=lambda _index: native,
        GetAnnotation=lambda: annotation, ShowParenthesis=False, ShowDimensionValue=True,
        GetUseDocUnits=lambda: False, GetUnits=lambda: 3,
        GetPrimaryPrecision2=lambda: precision, GetFractionBase=lambda: 2 if denominator else 1,
        GetFractionValue=lambda: denominator, GetRoundToFraction=lambda: False,
        GetOverride=lambda: False, GetText=lambda part: {1: "(", 2: " in)", 4: callout}[part],
    )
    annotation.GetSpecificAnnotation = lambda: display
    return display


def _author_public(monkeypatch, case, *, callback_count=1, shelf_failure=None):
    """Stub only physical geometry/authoring and the model-reference importer."""
    flats, ends = [tuple(NS(edge=object()) for _ in range(2)) for _ in range(2)]
    monkeypatch.setattr(nuts, "_physical_edges", lambda *_args, **_kwargs: (flats, ends))
    physical = {}
    import _supplier_reference_text as reference_text

    monkeypatch.setattr(reference_text, "_early_bound", lambda obj, _interface: obj)
    case.rebuilds = []

    def rebuild(*_args, **_kwargs):
        case.rebuilds.append("native graph settle")
        for ink in case.shelf_ink.values():
            if ink.failure == "offset-reset":
                ink.offset = False

    monkeypatch.setattr(reference_text, "rebuild_drawing", rebuild)
    case.shelf_ink = {}
    case.shelf_before = {}

    def with_ink(display, kind):
        # AF can fit its complete text, but the nut contract force-shelves it.
        ink = NativeShelfInk(case, display, kind=kind,
                             span=0.060 if kind == "flats" else None)
        name = display.GetDimension2(0).FullName
        case.shelf_ink[name] = ink
        case.shelf_before[name] = (
            tuple(ink.origin), tuple(ink.physical_lines()), tuple(ink.text_boxes()),
        )
        if shelf_failure is not None and kind == "nominal":
            shelf_failure(ink)
        return ShelfDisplay(display, ink)

    case.display = with_ink(case.display, "nominal")
    case.front.GetAnnotations = lambda: tuple(
        display.GetAnnotation() for display in
        (case.display, *[display for name, display in physical.items()
                        if name == "AcrossFlats@drawing"])
    )
    case.right.GetAnnotations = lambda: tuple(
        display.GetAnnotation() for name, display in physical.items()
        if name == "Height@drawing"
    )

    def author_edges(_adapter, _view, edges, **settings):
        name = "AcrossFlats@drawing" if edges is flats else "Height@drawing"
        physical[name] = with_ink(_physical_display(
            case, name, settings["expected_mm"], edges, precision=settings["precision"],
            denominator=settings.get("fraction_denominator"), callout=settings.get("callout", ""),
        ), "flats" if edges is flats else "height")
        return name

    monkeypatch.setattr(nuts, "_reference_between_edges", author_edges)
    callback_calls = []
    case.importer_callbacks = callback_calls

    def imported_check():
        callback_calls.append("nominal settled")

    def importer(adapter, views, **settings):
        assert adapter is case.adapter
        assert views["*Front"] is case.front
        assert settings["dimensions"] is case.spec.SUPPLIER_REFERENCE_DIMENSIONS
        assert settings["starts"] is case.spec.SUPPLIER_REFERENCE_STARTS
        settings["settled_checks"].extend([imported_check] * callback_count)
        return {"ThreadNominalMajor": case.display}

    monkeypatch.setattr(nuts, "annotate_supplier_screw", importer)
    settled = nuts.add_supplier_nut_dimensions(
        case.adapter, {"*Front": case.front, "*Right": case.right},
        across_flats_mm=case.spec.ACROSS_FLATS, thickness_mm=case.spec.THICKNESS,
        bore_diameter_mm=case.spec.BORE_DIA, thread=case.spec.THREAD,
        precision=case.spec.DRAWING_REFERENCE_PRECISION,
        fraction_denominator=case.spec.SUPPLIER_FRACTION_DENOMINATOR,
        reference_dimensions=case.spec.SUPPLIER_REFERENCE_DIMENSIONS,
        reference_starts=case.spec.SUPPLIER_REFERENCE_STARTS,
    )
    return settled, physical, callback_calls


@pytest.mark.parametrize("spec", CONSUMERS)
@pytest.mark.parametrize("drift", [False, True], ids=["fresh-wrappers", "settled-attachment-drift"])
def test_public_nut_boundary_reacquires_and_proves_settled_attachments(
    monkeypatch, native_nut, spec, drift,
):
    case = native_nut(spec)
    settled, physical, callbacks = _author_public(monkeypatch, case)
    assert callbacks and set(callbacks) == {"nominal settled"}
    callbacks_before = list(callbacks)
    assert len(case.mapping_reads) >= 2  # Initial public proof really ran.
    old_display = case.display
    fresh = case.make_display()
    case.shelf_ink[NOMINAL_NAME].attach(fresh)
    fresh = ShelfDisplay(fresh, case.shelf_ink[NOMINAL_NAME])
    assert fresh is not old_display
    fresh.GetAnnotation().entities = tuple(_wrapper(point) for point in case.mapped)
    if drift:
        fresh.GetAnnotation().entities = (case.attachments[0], _point(context="drawing"))
    reads = []

    def front_annotations():
        reads.append("front")
        return (fresh.GetAnnotation(), physical["AcrossFlats@drawing"].GetAnnotation())

    case.front.GetAnnotations = front_annotations
    case.right.GetAnnotations = lambda: (physical["Height@drawing"].GetAnnotation(),)
    # Reusing the creation display would fail, even in the positive test.
    old_display.GetAnnotation = _raise(AssertionError("stale creation display reused"))
    mapping_reads_before = len(case.mapping_reads)
    if drift:
        with pytest.raises(RuntimeError, match="view-mapped source endpoint"):
            settled()
    else:
        settled()  # Also runs production physical presentation/value/edge proofs.
    assert reads and set(reads) == {"front"}
    assert callbacks[:len(callbacks_before)] == callbacks_before
    assert callbacks[len(callbacks_before):] == ["nominal settled"]
    assert len(case.mapping_reads) >= mapping_reads_before + 2
    assert case.native.SystemValue == spec.SUPPLIER_NOMINAL_MAJOR_MM / 1000.0


def test_public_nut_boundary_rejects_invalid_initial_attachments(monkeypatch, native_nut):
    case = native_nut()
    case.display.GetAnnotation().entities = (case.attachments[0],) * 2
    with pytest.raises(RuntimeError, match="view-mapped source endpoint"):
        _author_public(monkeypatch, case)


@pytest.mark.parametrize("callback_count", [0, 2])
def test_public_nut_boundary_requires_exactly_one_nominal_settled_callback(
    monkeypatch, native_nut, callback_count,
):
    case = native_nut()
    with pytest.raises(RuntimeError, match="proof must be authored exactly once"):
        _author_public(monkeypatch, case, callback_count=callback_count)
    assert case.importer_callbacks == []


@pytest.mark.parametrize("kind", [2, 11, 12])
def test_nominal_carrier_accepts_matching_native_linear_types(native_nut, kind):
    case = native_nut()
    case.display.Type2 = case.source_display.Type2 = kind
    case.prove()


@pytest.mark.parametrize("endpoint_method", ["GetStartPoint2", "GetEndPoint2"])
def test_nominal_carrier_does_not_invent_a_missing_endpoint(native_nut, endpoint_method):
    case = native_nut()
    delattr(case.segment, endpoint_method)
    with pytest.raises(AttributeError, match=endpoint_method):
        case.prove()


def test_nominal_carrier_rejects_ambiguous_positive_attachment_identity(native_nut):
    case = native_nut()

    def same(left, right):
        if left is case.attachments[0] and right is case.mapped[1]:
            return 1
        return case.same(left, right)

    case.adapter.swApp.IsSame = same
    with pytest.raises(RuntimeError, match="view-mapped source endpoint"):
        case.prove()
    assert case.census()["attachments"][1]["matched_mapped_members"] == [0, 1]


class NativeShelfInk:
    """Bounded native display primitives, not an exact printed-glyph model.

    Text offsets are per-fragment measurements. The authored annotation origin
    deliberately differs from the physical arrow station for multiline text.
    False-mode positioning translates the physical dimension; enabling offset
    anchors its station to that origin, while true-mode positioning moves text.
    """

    def __init__(self, case, display, *, kind, span=None):
        self.case = case
        self.display = display
        self.kind = kind
        self.origin = [0.04 if kind != "height" else 0.10, 0.035, 0.0]
        self.station = 0.031 if kind == "nominal" else 0.035
        self.left, self.right = (self.origin[0] - 0.003, self.origin[0] + 0.003)
        if span is not None:
            self.left, self.right = self.origin[0] - span / 2, self.origin[0] + span / 2
        self.witness_start = 0.018
        self.witness_end = self.station + 0.003
        self.tail = 0.004
        self.offset = False
        self.failure = None
        self.writes = []
        self.seeded = False
        # x/y relative to text origin, measured width and height in metres.
        self.fragments = {
            "nominal": [
                ["(", -0.013, 0.000, 0.0015, 0.003],
                ["⌀", -0.011, 0.000, 0.003, 0.003],
                [f"{case.spec.SUPPLIER_NOMINAL_MAJOR_MM / 25.4:.3f} in)", -0.008, 0.000, 0.0242, 0.003],
                [f"{case.spec.THREAD.removeprefix('#')} THREAD", -0.014, -0.004, 0.030, 0.003],
                ["NOMINAL MAJOR", -0.020, -0.008, 0.040075, 0.003],
            ],
            "flats": [
                ["(", -0.008, 0.000, 0.0015, 0.003],
                ["1", -0.006, 0.0015, 0.002, 0.002],
                [str(case.spec.SUPPLIER_FRACTION_DENOMINATOR), -0.006, -0.0015, 0.004, 0.002],
                [" in)", -0.001, 0.000, 0.006, 0.003],
                ["ACROSS FLATS", -0.018, -0.006, 0.036, 0.003],
            ],
            "height": [[f"({case.spec.THICKNESS / 25.4:.3f} in)", -0.010, 0.000, 0.020, 0.003]],
        }[kind]
        self.attach(display)

    def attach(self, display):
        annotation = display.GetAnnotation()
        annotation.OwnerType = 0
        annotation.Owner = self.case.front
        annotation.Layer = ""
        annotation.GetName = lambda: display.GetDimension2(0).FullName
        annotation.GetLeaderCount = lambda: 0
        annotation.GetPosition = lambda: tuple(self.origin)
        annotation.SetPosition2 = self.set_position
        annotation.GetDisplayData = lambda: self
        annotation.GetSpecificAnnotation = lambda: ShelfDisplay(display, self)
        display.GetDisplayData = lambda: self
        display.GetNameForSelection = lambda: display.GetDimension2(0).FullName
        display.IsHoleCallout = lambda: False

    def set_position(self, x, y, z):
        self.writes.append(("position", self.offset, x, y, z))
        if self.failure == "position-refused":
            return False
        if self.failure == "position-ignored":
            return True
        if not self.offset:
            if self.failure == "seed-ignored":
                return True
            self.station += y - self.origin[1]
            self.witness_end += y - self.origin[1]
            self.seeded = True
        self.origin[:] = [x, y, z]
        return True

    def set_offset(self, value):
        self.writes.append(("offset", value))
        if value and self.failure == "offset-refused":
            return
        if value and not self.offset:
            self.station = self.origin[1]
            self.witness_end = self.station + 0.003
        self.offset = value

    def text_boxes(self):
        return [(self.origin[0] + x, self.origin[1] + y,
                 self.origin[0] + x + width, self.origin[1] + y + height)
                for _text, x, y, width, height in self.fragments]

    def physical_lines(self):
        y = self.station
        return [
            (self.left, self.witness_start, self.left, self.witness_end),
            (self.right, self.witness_start, self.right, self.witness_end),
            (self.left - self.tail, y, self.left, y),
            (self.left, y, self.right, y),
            (self.right, y, self.right + self.tail, y),
        ]

    def lines(self):
        rows = self.physical_lines()
        if self.offset:
            rows += [(self.right + self.tail, self.station,
                      self.origin[0], self.origin[1])]
        if self.kind == "flats":
            rows += [(self.origin[0] - 0.0065, self.origin[1] + 0.001,
                      self.origin[0] - 0.0015, self.origin[1] + 0.001)]
        return rows

    def GetTextCount(self):
        return len(self.fragments)

    def GetTextAtIndex(self, index):
        return self.fragments[index][0]

    def GetTextPositionAtIndex(self, index):
        _text, x, y, _width, _height = self.fragments[index]
        return (self.origin[0] + x, self.origin[1] + y, 0.0)

    def GetTextHeightAtIndex(self, index):
        return self.fragments[index][4]

    def GetTextInBoxWidthAtIndex(self, index):
        return self.fragments[index][3]

    def GetTextRefPositionAtIndex(self, _index):
        return 0

    def GetTextAngleAtIndex(self, _index):
        return 0.0

    def GetTextFontAtIndex(self, _index):
        return "Arial"

    def GetTextLineSpacingAtIndex(self, _index):
        return 0.004

    def GetLineCount(self):
        return len(self.lines())

    def GetLineAtIndex3(self, index):
        x0, y0, x1, y1 = self.lines()[index]
        return (0, 0, 0, 0, x0, y0, 0, x1, y1, 0)

    GetLineAtIndex2 = GetLineAtIndex3

    def GetArrowHeadCount(self):
        return 2

    def GetArrowHeadAtIndex2(self, index):
        return (self.left if index == 0 else self.right, self.station, 0,
                1 if index == 0 else -1, 0, 0, 0.002, 0.001, 0, 0, 0, 1)

    def GetArcCount(self):
        return 0

    GetPolyLineCount = GetArcCount
    GetPolygonCount = GetArcCount
    GetTriangleCount = GetArcCount


class ShelfDisplay:
    """Fresh wrapper forwarding all native reads while intercepting OffsetText."""

    def __init__(self, display, ink):
        object.__setattr__(self, "_display", display)
        object.__setattr__(self, "_ink", ink)

    def __getattr__(self, name):
        if name == "OffsetText":
            return self._ink.offset
        return getattr(self._display, name)

    def __setattr__(self, name, value):
        if name == "OffsetText":
            self._ink.set_offset(value)
        else:
            setattr(self._display, name, value)


@pytest.mark.parametrize("spec", CONSUMERS)
def test_public_nut_shelves_complete_native_blocks_without_moving_physical_stations(
    monkeypatch, native_nut, spec,
):
    case = native_nut(spec)
    source_before = tuple((point.native_identity, point.X, point.Y, point.Z)
                          for point in case.source)
    attachment_before = tuple(point.native_identity for point in case.attachments)
    value_before = case.native.SystemValue
    settled, physical, callbacks = _author_public(monkeypatch, case)
    assert set(case.shelf_ink) == {NOMINAL_NAME, "AcrossFlats@drawing", "Height@drawing"}
    assert case.shelf_before[NOMINAL_NAME][0][1] != 0.031
    for name, ink in case.shelf_ink.items():
        origin, lines, boxes = case.shelf_before[name]
        assert ink.offset is True
        assert ink.origin[0] > origin[0], name
        assert ink.origin[1] == pytest.approx(origin[1]), name
        for actual, expected in zip(ink.physical_lines(), lines, strict=True):
            assert actual == pytest.approx(expected), name
        assert len(ink.text_boxes()) == len(boxes)
        # Every measured fragment, not just the numerical row, clears both
        # witness runs and the outside arrow's complete physical line reach.
        physical_reach = ink.right + ink.tail
        for before, after in zip(boxes, ink.text_boxes(), strict=True):
            assert after[0] >= physical_reach + 0.002, (name, before, after)
            assert after[2] > after[0] and after[3] > after[1]
            assert all(math.isfinite(value) for value in after)
            assert after[1:] == pytest.approx(
                (before[1], before[2] + ink.origin[0] - origin[0], before[3])
            )
        if ink.kind == "flats":
            assert max(box[2] for box in boxes) - min(box[0] for box in boxes) < ink.right - ink.left
            assert len(ink.lines()) > len(ink.physical_lines())  # fraction bar remains ink
    nominal = case.shelf_ink[NOMINAL_NAME]
    assert max(fragment[3] for fragment in nominal.fragments) == 0.040075
    assert any(fragment[0] == "NOMINAL MAJOR" for fragment in nominal.fragments)
    assert any(fragment[0] == "⌀" for fragment in nominal.fragments)
    assert tuple((point.native_identity, point.X, point.Y, point.Z)
                 for point in case.source) == source_before
    assert tuple(point.native_identity for point in case.attachments) == attachment_before
    assert case.native.SystemValue == value_before
    writes = {name: list(ink.writes) for name, ink in case.shelf_ink.items()}
    rebuilds = list(case.rebuilds)
    callbacks_before = list(callbacks)
    # The returned presentation guard is repeatable and entirely read-only.
    for _ in range(3):
        settled()
    assert callbacks[len(callbacks_before):] == ["nominal settled"] * 3
    assert {name: ink.writes for name, ink in case.shelf_ink.items()} == writes
    assert case.rebuilds == rebuilds
    assert physical["AcrossFlats@drawing"].GetDimension2(0).SystemValue == spec.ACROSS_FLATS / 1000.0
    assert physical["Height@drawing"].GetDimension2(0).SystemValue == spec.THICKNESS / 1000.0
    assert not any(
        getattr(left, "context", None) != getattr(right, "context", None)
        for left, right in case.comparisons
    ), "presentation must not reintroduce model/drawing endpoint comparisons"


@pytest.mark.parametrize("failure", [
    "seed-ignored", "position-refused", "position-ignored", "offset-refused", "offset-reset",
])
def test_public_nut_refuses_native_shelf_writes_that_do_not_persist(
    monkeypatch, native_nut, failure,
):
    case = native_nut()
    with pytest.raises(RuntimeError, match="(?i)station|offset|position|shelf|witness|text"):
        _author_public(monkeypatch, case, shelf_failure=lambda ink: setattr(ink, "failure", failure))


@pytest.mark.parametrize("field,value", [
    (3, 0.0), (3, -0.001), (3, float("nan")), (3, None),
    (4, 0.0), (4, float("inf")), (1, float("nan")), (2, float("inf")),
])
def test_public_nut_requires_geometry_for_the_longest_nominal_fragment(
    monkeypatch, native_nut, field, value,
):
    case = native_nut()

    def corrupt(ink):
        ink.fragments[-1][field] = value

    with pytest.raises(RuntimeError, match="(?i)text|fragment|native|geometry|measur"):
        _author_public(monkeypatch, case, shelf_failure=corrupt)


@pytest.mark.parametrize("drift", ["arrow-station", "witness-extent", "lost-witness", "offset"])
def test_public_nut_settled_proof_refuses_late_native_presentation_drift(
    monkeypatch, native_nut, drift,
):
    case = native_nut()
    settled, _physical, _callbacks = _author_public(monkeypatch, case)
    ink = case.shelf_ink[NOMINAL_NAME]
    if drift == "arrow-station":
        ink.station += 0.001
    elif drift == "witness-extent":
        ink.witness_start += 0.001
    elif drift == "lost-witness":
        lines = ink.physical_lines
        ink.physical_lines = lambda: lines()[1:]
    else:
        ink.offset = False
    writes = list(ink.writes)
    rebuilds = list(case.rebuilds)
    with pytest.raises(RuntimeError, match="(?i)station|witness|offset|text|shelf|line|reference"):
        settled()
    assert ink.writes == writes
    assert case.rebuilds == rebuilds


@pytest.mark.parametrize("drift", ["missing", "duplicate", "unrelated", "hidden"])
def test_public_nut_shelf_settled_reacquisition_requires_exact_visible_inventory(
    monkeypatch, native_nut, drift,
):
    case = native_nut()
    settled, physical, _callbacks = _author_public(monkeypatch, case)
    nominal = case.display.GetAnnotation()
    flats = physical["AcrossFlats@drawing"].GetAnnotation()
    if drift == "hidden":
        nominal.Visible = 0
        inventory = (nominal, flats)
    elif drift == "missing":
        inventory = (flats,)
    elif drift == "duplicate":
        inventory = (nominal, nominal, flats)
    else:
        foreign = case.make_display()
        foreign.GetDimension2 = lambda _index: NS(FullName="Foreign@drawing")
        inventory = (nominal, flats, foreign.GetAnnotation())
    case.front.GetAnnotations = lambda: inventory
    with pytest.raises(RuntimeError, match="hidden|inventory"):
        settled()


@pytest.mark.parametrize("drift", ["physical-value", "physical-format", "physical-attachment", "source"])
def test_public_nut_shelving_preserves_existing_settled_source_and_physical_guards(
    monkeypatch, native_nut, drift,
):
    case = native_nut()
    settled, physical, _callbacks = _author_public(monkeypatch, case)
    flats = physical["AcrossFlats@drawing"]
    if drift == "physical-value":
        flats.GetDimension2(0).SystemValue += 0.001
        message = "native value|measures"
    elif drift == "physical-format":
        flats.GetText = lambda _part: "changed"
        message = "presentation"
    elif drift == "physical-attachment":
        flats.GetAnnotation().GetAttachedEntities3 = lambda: (object(), object())
        message = "named entities"
    else:
        case.segment.ConstructionGeometry = False
        message = "construction line"
    with pytest.raises(RuntimeError, match=message):
        settled()


@pytest.mark.parametrize("getter", [
    "GetTextCount", "GetTextPositionAtIndex", "GetTextHeightAtIndex",
])
def test_public_nut_does_not_estimate_missing_native_text_geometry(
    monkeypatch, native_nut, getter,
):
    case = native_nut()

    def missing(ink):
        setattr(ink, getter, lambda *_args: None)

    with pytest.raises(RuntimeError, match="unreadable|native size|geometry"):
        _author_public(monkeypatch, case, shelf_failure=missing)


def test_public_nut_settled_proof_does_not_repair_transverse_text_drift(monkeypatch, native_nut):
    case = native_nut()
    settled, _physical, _callbacks = _author_public(monkeypatch, case)
    ink = case.shelf_ink[NOMINAL_NAME]
    ink.origin[1] += 0.001
    writes = list(ink.writes)
    rebuilds = list(case.rebuilds)
    with pytest.raises(RuntimeError, match="transverse position"):
        settled()
    assert ink.writes == writes
    assert case.rebuilds == rebuilds
