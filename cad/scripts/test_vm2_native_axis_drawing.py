"""Behavioral datum-placement regressions; all COM boundaries are test doubles.

The original requested-position failures below are copied from the published
candidate-2d-datum-retry-full.log. Native cases exercise the separately approved
two-recipe helper; the existing general datum helper is unchanged.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_common as common
import _native_axis_datum as axis


LIMITS = (0.00002, 0.0001)
RADIUS = 0.0025


class Annotation:
    def __init__(self, edge):
        self.position = (0.21, 0.167, 0.0015)
        self.attached = (edge,)
        self.types = (1,)
        self.dangling = False
        self.set_calls = []
        self.set_result = True
        self.requested_readback = None

    def GetPosition(self):
        return self.position

    def SetPosition2(self, x, y, z):
        self.set_calls.append((x, y, z))
        self.position = self.requested_readback or (x, y, z)
        return self.set_result

    def GetAttachedEntities3(self):
        return self.attached

    def GetAttachedEntityTypes(self):
        return self.types

    def IsDangling(self):
        return self.dangling


class Tag:
    def __init__(self, annotation):
        self.annotation = annotation
        self.label = ""
        self.label_mode = "retain"
        self.label_result = True
        self.shoulder_mode = "retain"
        self._shoulder = False
        self.text_result = True
        self.text_calls = []

    def GetAnnotation(self):
        return self.annotation

    def SetLabel(self, label):
        if self.label_mode == "retain":
            self.label = label
        return self.label_result

    def GetLabel(self):
        return self.label

    @property
    def Shoulder(self):
        return self._shoulder

    @Shoulder.setter
    def Shoulder(self, value):
        if self.shoulder_mode == "retain":
            self._shoulder = value

    def SetText(self, code, text):
        self.text_calls.append((code, text))
        return self.text_result


@pytest.fixture
def harness(monkeypatch, tmp_path):
    """Exercise the real helper; replace bindings, selection and native objects."""
    params = (0.0, 0.0, 0.003, 0.0, 0.0, -1.0, RADIUS)
    circle = SimpleNamespace(CircleParams=params, IsCircle=lambda: True)
    cylinder = SimpleNamespace(CylinderParams=params, IsCylinder=lambda: True)
    plane = SimpleNamespace(IsCylinder=lambda: False)
    cylinder_face = SimpleNamespace(GetSurface=lambda: cylinder)
    plane_face = SimpleNamespace(GetSurface=lambda: plane)
    body = object()
    edge = SimpleNamespace(
        GetBody=lambda: object(),  # drawing-context body is not the source body
        GetCurve=lambda: circle,
        GetTwoAdjacentFaces2=lambda: (cylinder_face, plane_face),
    )
    canonical_edge = SimpleNamespace(
        GetBody=lambda: body,
        GetCurve=lambda: edge.GetCurve(),
        GetTwoAdjacentFaces2=lambda: edge.GetTwoAdjacentFaces2(),
    )
    annotation = Annotation(edge)
    tag = Tag(annotation)
    state = SimpleNamespace(
        edge=edge, canonical_edge=canonical_edge, body=body,
        circle=circle, cylinder=cylinder, plane=plane,
        cylinder_face=cylinder_face, plane_face=plane_face,
        annotation=annotation, tag=tag, selected=edge,
        selection_calls=[], equality_calls=[], rebuild_calls=0,
        insert_calls=0, rebuild_result=True, on_rebuild=lambda: None,
        equality_mode="identity", tags=[], insertion_mode="create",
        selected_count=1, on_insert=lambda: None,
    )

    def select(*_args, **kwargs):
        state.selection_calls.append(kwargs)
        return state.selected

    def same(first, second):
        state.equality_calls.append((first, second))
        if state.equality_mode == "unknown_edge" and first is edge and second is edge:
            return -1
        return int(first is second)

    def insert():
        state.insert_calls += 1
        if state.insertion_mode == "create" and state.tag is not None:
            state.tags.append(state.tag)
        state.on_insert()
        return state.tag

    def rebuild():
        state.rebuild_calls += 1
        state.on_rebuild()
        return state.rebuild_result

    state.adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            GetType=lambda: 3,
            SelectionManager=SimpleNamespace(
                GetSelectedObjectCount2=lambda _mark: state.selected_count,
            ),
            InsertDatumTag2=insert,
            ClearSelection2=lambda _all: None,
            EditRebuild3=rebuild,
        ),
        swApp=SimpleNamespace(IsSame=same),
    )
    state.source_path = tmp_path / "rack-pinion.SLDPRT"
    state.source_path.write_bytes(b"offline source identity fixture")
    state.reference = SimpleNamespace(
        Extension=SimpleNamespace(GetCorrespondingEntity2=lambda _edge: canonical_edge),
        GetType=lambda: 1,
        GetPathName=lambda: str(state.source_path),
        GetBodies2=lambda kind, visible: (body,),
    )
    state.view = SimpleNamespace(
        ReferencedDocument=state.reference, GetDatumTags=lambda: state.tags,
        GetCorrespondingEntity=lambda _edge: edge,
    )
    monkeypatch.setattr(common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(axis, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        common._sw_type_info, "early_bound_or_flag",
        lambda value, *_args: value,
    )
    monkeypatch.setattr(common, "_select_annotation_entity", select)
    return state


def native(harness, **changes):
    kwargs = dict(
        entity=harness.edge, source_path=harness.source_path,
        radius_m=RADIUS, datum="A", label="VM2 axis",
        stability_tolerance_m=0.0001,
    )
    kwargs.update(changes)
    return axis.add_native_axis_datum(harness.adapter, harness.view, **kwargs)


@pytest.mark.parametrize(
    "label,requested,actual,limit",
    (
        ("lift rod axis", (0.055, 0.22899999999999998),
         (0.05499999999999966, 0.22897646401719635, 0.0), 0.00002),
        ("rack pinion bore axis", (0.22, 0.20099999999999998),
         (0.21999999999999942, 0.20083662770023045, 0.0015), 0.0001),
    ),
)
def test_original_requested_failures_still_reject(
    harness, label, requested, actual, limit,
):
    receipt = Path(__file__).parents[1] / (
        "docs/pipeline/evidence/vm2-datum-placement/raw/"
        "candidate-2d-datum-retry-full.log"
    )
    raw = receipt.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "a7ec86f9a83f2ff9bc7717f940e19c238a494f0352e0c613ddab89853184061f"
    )
    text = raw.decode("utf-8")
    assert f"({label}): {actual[:2]}; requested={requested}" in text
    harness.annotation.requested_readback = actual
    with pytest.raises(RuntimeError, match="position did not persist"):
        common.add_datum_feature(
            harness.adapter, harness.view, edge_xy=(0.1, 0.1),
            symbol_xy=requested, datum="A", label=label,
            position_tolerance_m=limit,
        )
    assert harness.annotation.set_calls == [(*requested, 0.0)]
    assert harness.rebuild_calls == 0


def test_requested_default_still_positions_once(harness):
    tag = common.add_datum_feature(
        harness.adapter, harness.view, edge_xy=(0.1, 0.1),
        symbol_xy=(0.2, 0.25), datum="A", label="requested control",
    )
    assert tag is harness.tag
    assert harness.annotation.set_calls == [(0.2, 0.25, 0.0)]
    assert harness.rebuild_calls == 1


@pytest.mark.parametrize("limit", LIMITS)
def test_native_keeps_position_and_never_calls_setposition(harness, limit):
    initial = harness.annotation.position
    assert native(harness, stability_tolerance_m=limit, shoulder=True) is harness.tag
    assert harness.annotation.position == initial
    assert harness.annotation.set_calls == []
    assert harness.rebuild_calls == 1
    assert harness.tag.GetLabel() == "A"
    assert harness.tag.Shoulder is True
    assert sum(a is harness.edge and b is harness.edge
               for a, b in harness.equality_calls) == 5


@pytest.mark.parametrize("limit", LIMITS)
@pytest.mark.parametrize("drift", ("below", "exact", "above", "diagonal"))
def test_native_enforces_unchanged_xy_drift_boundary(harness, limit, drift):
    # An origin baseline permits an exact floating-point threshold test.
    harness.annotation.position = (0.0, 0.0, 0.0015)
    x, y = limit, 0.0
    if drift == "below":
        x = math.nextafter(limit, 0.0)
    if drift == "above":
        x = math.nextafter(limit, math.inf)
    if drift == "diagonal":
        x = y = limit * 0.8
    harness.on_rebuild = lambda: setattr(harness.annotation, "position", (x, y, 0.0015))
    if drift in {"above", "diagonal"}:
        with pytest.raises(RuntimeError, match="native position did not persist"):
            native(harness, stability_tolerance_m=limit)
        return
    assert native(harness, stability_tolerance_m=limit) is harness.tag
    assert harness.annotation.set_calls == []


@pytest.mark.parametrize("field", ("stability_tolerance_m", "radius_m"))
@pytest.mark.parametrize("value", (
    0.0, -1.0, math.nan, math.inf, -math.inf, True, False, "0.0001", None,
))
def test_native_rejects_invalid_numeric_contract_before_com(harness, field, value):
    with pytest.raises(ValueError, match="finite and positive"):
        native(harness, **{field: value})
    assert harness.selection_calls == []
    assert harness.insert_calls == 0


@pytest.mark.parametrize(
    "changes",
    (
        {"entity": None}, {"entity_type": "FACE"},
        {"edge_xy": (0.1, 0.1)}, {"edge_entity": object()},
        {"annotation": object()}, {"symbol_xy": (0.2, 0.2)},
    ),
)
def test_native_rejects_nonsemantic_or_conflicting_selectors(harness, changes):
    expected = ValueError if "entity" in changes else TypeError
    with pytest.raises(expected, match="explicit EDGE entity|unexpected keyword"):
        native(harness, **changes)
    assert harness.selection_calls == []
    assert harness.insert_calls == 0


def test_native_requires_expected_radius(harness):
    with pytest.raises(ValueError, match="radius.*finite and positive"):
        native(harness, radius_m=None)
    assert harness.insert_calls == 0


@pytest.mark.parametrize("geometry", ("circle", "cylinder"))
@pytest.mark.parametrize(
    "index,value",
    ((0, 0.01), (1, -0.01), (3, 1.0), (4, 1.0),
     (5, 0.0), (6, RADIUS * 2), (2, math.nan), (6, math.inf)),
)
def test_native_rejects_wrong_axis_radius_or_nonfinite_geometry(
    harness, geometry, index, value,
):
    target = getattr(harness, geometry)
    field = "CircleParams" if geometry == "circle" else "CylinderParams"
    params = list(getattr(target, field))
    params[index] = value
    setattr(target, field, params)
    with pytest.raises(RuntimeError, match="invalid datum axis|intended Z axis"):
        native(harness)
    assert harness.insert_calls == 0


@pytest.mark.parametrize("geometry", ("circle", "cylinder"))
@pytest.mark.parametrize("params", (None, (), (0.0,) * 6, (0.0,) * 8))
def test_native_rejects_missing_or_malformed_geometry(harness, geometry, params):
    field = "CircleParams" if geometry == "circle" else "CylinderParams"
    setattr(getattr(harness, geometry), field, params)
    with pytest.raises(RuntimeError, match="invalid datum axis"):
        native(harness)
    assert harness.insert_calls == 0


@pytest.mark.parametrize("axis_sign", (-1.0, 1.0))
def test_native_accepts_both_axis_directions_and_axial_origin(harness, axis_sign):
    harness.circle.CircleParams = (0, 0, 0.202, 0, 0, axis_sign, RADIUS)
    harness.cylinder.CylinderParams = (0, 0, -0.45, 0, 0, -axis_sign, RADIUS)
    assert native(harness) is harness.tag


@pytest.mark.parametrize(
    "defect,expected",
    (
        ("curve_missing", "no curve"), ("not_circle", "not circular"),
        ("face_missing", "exactly two adjacent faces"),
        ("surface_missing", "no surface"),
        ("no_cylinder", "bounds 0 cylinders"),
        ("two_cylinders", "bounds 2 cylinders"),
    ),
)
def test_native_rejects_missing_or_ambiguous_topology(harness, defect, expected):
    if defect == "curve_missing":
        harness.edge.GetCurve = lambda: None
    if defect == "not_circle":
        harness.circle.IsCircle = lambda: False
    if defect == "face_missing":
        harness.edge.GetTwoAdjacentFaces2 = lambda: (harness.cylinder_face, None)
    if defect == "surface_missing":
        harness.plane_face.GetSurface = lambda: None
    if defect == "no_cylinder":
        harness.cylinder.IsCylinder = lambda: False
    if defect == "two_cylinders":
        second_cylinder = SimpleNamespace(GetSurface=lambda: harness.cylinder)
        harness.edge.GetTwoAdjacentFaces2 = lambda: (
            harness.cylinder_face, second_cylinder,
        )
    with pytest.raises(RuntimeError, match=expected):
        native(harness)
    assert harness.insert_calls == 0


@pytest.mark.parametrize("equality", ("different", "unknown"))
def test_native_rejects_selected_edge_mismatch_before_insertion(harness, equality):
    if equality == "different":
        harness.selected = object()
    if equality == "unknown":
        harness.equality_mode = "unknown_edge"
    with pytest.raises(RuntimeError, match="selected a different datum edge|roundtrip"):
        native(harness)
    assert harness.insert_calls == 0


@pytest.mark.parametrize("stage", ("initial", "rebuild"))
@pytest.mark.parametrize(
    "defect,expected",
    (
        ("empty", "one attached edge"), ("multiple", "one attached edge"),
        ("null", "one attached edge"), ("wrong_type", "one attached edge"),
        ("wrong_edge", "different edge"), ("unknown", "different edge|roundtrip"),
        ("dangling", "dangling"), ("label", "label did not persist"),
    ),
)
def test_native_revalidates_attachment_and_label(harness, stage, defect, expected):
    def corrupt():
        if defect == "empty":
            harness.annotation.attached = ()
        if defect == "multiple":
            harness.annotation.attached = (harness.edge, harness.edge)
        if defect == "null":
            harness.annotation.attached = (None,)
        if defect == "wrong_type":
            harness.annotation.types = (2,)
        if defect == "wrong_edge":
            harness.annotation.attached = (object(),)
        if defect == "unknown":
            harness.equality_mode = "unknown_edge"
        if defect == "dangling":
            harness.annotation.dangling = True
        if defect == "label":
            harness.tag.label = "B"
            harness.tag.label_mode = "ignore"

    if stage == "rebuild":
        harness.on_rebuild = corrupt
    if stage == "initial" and defect != "unknown":
        corrupt()
    if stage == "initial" and defect == "unknown":
        harness.on_insert = corrupt
    with pytest.raises(RuntimeError, match=expected):
        native(harness)
    assert harness.annotation.set_calls == []


@pytest.mark.parametrize("stage", ("initial", "rebuild"))
@pytest.mark.parametrize(
    "position", (None, (), (0.1, 0.2), (0.1, 0.2, math.nan), (math.inf, 0.2, 0.0)),
)
def test_native_rejects_invalid_position_at_both_readbacks(harness, stage, position):
    if stage == "initial":
        harness.annotation.position = position
    if stage == "rebuild":
        harness.on_rebuild = lambda: setattr(harness.annotation, "position", position)
    with pytest.raises(RuntimeError, match="invalid position"):
        native(harness)


@pytest.mark.parametrize("stage", ("initial", "rebuild"))
def test_native_requires_requested_shoulder_to_persist(harness, stage):
    if stage == "initial":
        harness.tag.shoulder_mode = "ignore"
    if stage == "rebuild":
        harness.on_rebuild = lambda: setattr(harness.tag, "Shoulder", False)
    with pytest.raises(RuntimeError, match="shoulder.*persist|shoulder changed"):
        native(harness, shoulder=True)


def test_native_accepts_solidworks_forced_shoulder_without_explicit_request(harness):
    harness.tag.Shoulder = True
    assert native(harness) is harness.tag
    assert harness.tag.Shoulder is True


def test_native_rejects_rebuild_failure(harness):
    harness.rebuild_result = False
    with pytest.raises(RuntimeError, match="rebuild failed"):
        native(harness)
    assert harness.annotation.set_calls == []


def test_native_rejects_insert_failure(harness):
    harness.tag = None
    with pytest.raises(RuntimeError, match="failed to insert datum"):
        native(harness)


def test_native_rejects_setlabel_failure(harness):
    harness.tag.label_result = False
    with pytest.raises(RuntimeError, match="failed to label datum"):
        native(harness)


def test_native_helper_does_not_expose_unneeded_generic_callouts(harness):
    with pytest.raises(TypeError, match="unexpected keyword"):
        native(harness, callout_below="AXIS")


def test_native_rejects_missing_annotation(harness):
    harness.tag.annotation = None
    with pytest.raises(RuntimeError, match="no annotation"):
        native(harness)


@pytest.mark.parametrize("count", (0, 1, 3))
def test_native_requires_exactly_two_adjacent_entries(harness, count):
    harness.edge.GetTwoAdjacentFaces2 = lambda: (harness.cylinder_face,) * count
    with pytest.raises(RuntimeError, match="exactly two adjacent faces"):
        native(harness)
    assert harness.insert_calls == 0


@pytest.mark.parametrize("equality", ("duplicate", "unknown"))
def test_native_rejects_ambiguous_face_identity(harness, equality):
    if equality == "duplicate":
        harness.edge.GetTwoAdjacentFaces2 = lambda: (harness.cylinder_face,) * 2
    if equality == "unknown":
        original = harness.adapter.swApp.IsSame
        harness.adapter.swApp.IsSame = lambda a, b: (
            -1 if a is harness.cylinder_face and b is harness.plane_face
            else original(a, b)
        )
    with pytest.raises(RuntimeError, match="adjacent faces are duplicate or unknown"):
        native(harness)


@pytest.mark.parametrize("stage", ("initial", "rebuild"))
@pytest.mark.parametrize(
    "defect,expected",
    (
        ("wrong_path", "wrong source path"),
        ("empty_path", "wrong source path"),
        ("no_reference", "no referenced source part"),
        ("not_part", "does not reference a part"),
        ("empty_body_set", "exactly one solid body"),
        ("multiple_bodies", "exactly one solid body"),
        ("null_body", "exactly one solid body"),
        ("edge_body_missing", "different source body"),
        ("edge_wrong_body", "different source body"),
        ("body_equality_unknown", "different source body"),
        ("cylinder_changed", "intended Z axis"),
    ),
)
def test_native_verifies_source_and_body_again_after_rebuild(
    harness, stage, defect, expected,
):
    def corrupt():
        if defect == "wrong_path":
            harness.reference.GetPathName = lambda: str(
                harness.source_path.with_name("other-part.SLDPRT")
            )
        if defect == "empty_path":
            harness.reference.GetPathName = lambda: ""
        if defect == "no_reference":
            harness.view.ReferencedDocument = None
        if defect == "not_part":
            harness.reference.GetType = lambda: 2
        if defect == "empty_body_set":
            harness.reference.GetBodies2 = lambda *_args: ()
        if defect == "multiple_bodies":
            harness.reference.GetBodies2 = lambda *_args: (harness.body, object())
        if defect == "null_body":
            harness.reference.GetBodies2 = lambda *_args: (None,)
        if defect == "edge_body_missing":
            harness.canonical_edge.GetBody = lambda: None
        if defect == "edge_wrong_body":
            harness.canonical_edge.GetBody = lambda: object()
        if defect == "body_equality_unknown":
            original = harness.adapter.swApp.IsSame
            harness.adapter.swApp.IsSame = lambda a, b: (
                -1 if a is harness.body and b is harness.body else original(a, b)
            )
        if defect == "cylinder_changed":
            harness.cylinder.CylinderParams = (0.01, 0, 0, 0, 0, 1, RADIUS)

    if stage == "initial":
        corrupt()
    if stage == "rebuild":
        harness.on_rebuild = corrupt
    with pytest.raises(RuntimeError, match=expected):
        native(harness)
    if stage == "initial":
        assert harness.insert_calls == 0


def test_native_requests_all_solid_bodies_not_only_visible(harness):
    requests = []

    def bodies(kind, visible):
        requests.append((kind, visible))
        return (harness.body,)

    harness.reference.GetBodies2 = bodies
    assert native(harness) is harness.tag
    assert requests == [(0, False), (0, False)]


@pytest.mark.parametrize("count", (0, 2))
def test_native_rejects_noop_or_multiple_selection(harness, count):
    harness.selected_count = count
    with pytest.raises(RuntimeError, match="exactly one selected datum edge"):
        native(harness)
    assert harness.insert_calls == 0


def test_native_rejects_preexisting_datum_instead_of_reusing_it(harness):
    harness.tags.append(harness.tag)
    with pytest.raises(RuntimeError, match="already has datum tags"):
        native(harness)
    assert harness.insert_calls == 0


@pytest.mark.parametrize("stage", ("initial", "rebuild"))
@pytest.mark.parametrize("defect", ("missing", "multiple", "null", "other_tag"))
def test_native_reenumerates_and_rejects_stale_or_missing_insertion(
    harness, stage, defect,
):
    def corrupt():
        if defect == "missing":
            harness.tags = []
        if defect == "multiple":
            harness.tags = [harness.tag, harness.tag]
        if defect == "null":
            harness.tags = [None]
        if defect == "other_tag":
            harness.tags = [Tag(harness.annotation)]

    if stage == "initial":
        harness.on_insert = corrupt
    if stage == "rebuild":
        harness.on_rebuild = corrupt
    with pytest.raises(RuntimeError, match="insertion is missing or stale"):
        native(harness)


def test_native_rejects_noop_insertion_returning_an_unregistered_proxy(harness):
    harness.insertion_mode = "ignore"
    with pytest.raises(RuntimeError, match="insertion is missing or stale"):
        native(harness)


def test_native_rejects_non_drawing_active_document(harness):
    harness.adapter.currentModel.GetType = lambda: 1
    with pytest.raises(RuntimeError, match="requires an active drawing"):
        native(harness)
    assert harness.insert_calls == 0


@pytest.mark.parametrize("datum", ("", "ABC"))
def test_native_rejects_invalid_label_before_com(harness, datum):
    with pytest.raises(ValueError, match="one or two characters"):
        native(harness, datum=datum)
    assert harness.selection_calls == []


def test_native_source_path_must_name_an_existing_part(harness):
    with pytest.raises(FileNotFoundError):
        native(harness, source_path=harness.source_path.with_name("missing.SLDPRT"))
    with pytest.raises(ValueError, match="existing SLDPRT file"):
        native(harness, source_path=harness.source_path.parent)


def test_native_maps_view_edge_through_source_and_back_at_both_stages(harness):
    mappings = []

    def to_source(edge):
        assert edge is harness.edge
        mappings.append("source")
        return harness.canonical_edge

    def to_view(edge):
        assert edge is harness.canonical_edge
        mappings.append("view")
        return harness.edge

    harness.reference.Extension.GetCorrespondingEntity2 = to_source
    harness.view.GetCorrespondingEntity = to_view
    assert harness.edge.GetBody() is not harness.body
    assert harness.canonical_edge.GetBody() is harness.body
    assert native(harness) is harness.tag
    assert mappings == ["source", "view", "source", "view"]
    assert harness.annotation.attached == (harness.edge,)


@pytest.mark.parametrize("stage", ("initial", "rebuild"))
@pytest.mark.parametrize("defect", (
    "source_missing", "view_missing", "wrong_view_edge", "roundtrip_unknown",
    "wrong_source_body",
))
def test_native_rejects_missing_or_wrong_correspondence(harness, stage, defect):
    def corrupt():
        if defect == "source_missing":
            harness.reference.Extension.GetCorrespondingEntity2 = lambda _edge: None
        if defect == "view_missing":
            harness.view.GetCorrespondingEntity = lambda _edge: None
        if defect == "wrong_view_edge":
            # Same geometric attributes are not a substitute for exact identity.
            other = SimpleNamespace(**vars(harness.edge))
            harness.view.GetCorrespondingEntity = lambda _edge: other
        if defect == "roundtrip_unknown":
            harness.equality_mode = "unknown_edge"
        if defect == "wrong_source_body":
            other = SimpleNamespace(**vars(harness.canonical_edge))
            other.GetBody = lambda: object()
            harness.reference.Extension.GetCorrespondingEntity2 = lambda _edge: other

    if stage == "initial":
        corrupt()
    if stage == "rebuild":
        harness.on_rebuild = corrupt
    with pytest.raises(RuntimeError, match="correspondence|roundtrip|different source body"):
        native(harness)
    if stage == "initial":
        assert harness.insert_calls == 0


@pytest.mark.parametrize("geometry", ("circle", "cylinder"))
@pytest.mark.parametrize("index,value", ((0, False), (5, True), (6, "0.0025")))
def test_native_rejects_boolean_or_string_geometry(harness, geometry, index, value):
    field = "CircleParams" if geometry == "circle" else "CylinderParams"
    target = getattr(harness, geometry)
    params = list(getattr(target, field))
    params[index] = value
    setattr(target, field, params)
    with pytest.raises(RuntimeError, match="invalid datum axis"):
        native(harness)
    assert harness.insert_calls == 0


@pytest.mark.parametrize("stage", ("initial", "rebuild"))
@pytest.mark.parametrize("value", (True, False, "0.21"))
def test_native_rejects_boolean_or_string_positions(harness, stage, value):
    position = (value, 0.167, 0.0015)
    if stage == "initial":
        harness.annotation.position = position
    if stage == "rebuild":
        harness.on_rebuild = lambda: setattr(harness.annotation, "position", position)
    with pytest.raises(RuntimeError, match="invalid position"):
        native(harness)
