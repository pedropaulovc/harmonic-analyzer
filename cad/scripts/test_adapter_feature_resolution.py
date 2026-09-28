r"""SolidWorks-free contract for the adapter's raw feature-tree reads.

``solidworks_mcp`` finds the feature a creation call made by diffing the
top-level tree before and after the call, and scores body edges/faces with
``GetClosestPointOn``, all through ``raw_dispatch.invoke``: one ``InvokeTypes``
per member on a bare ``PyIDispatch``, dispid and signature taken from the
checked-in wrapper. Every build leaf runs these calls, so this pins them:

* the raw call is the call the generated member sends (dispid, flags, return
  and argument types), and object results come back unwrapped;
* a before-tree that could not be read completely never stands in as the
  before-set -- the diff refuses instead of naming an old feature as new;
* when a call adds an auxiliary feature next to the one it creates, the
  expected ``GetTypeName2`` picks the created feature, and a missing or
  ambiguous match raises -- unless the call declares it creates several
  (evenly distributed reference points), when the newest is returned.

The raw-call tests use ``RawDispatch``, which answers ``InvokeTypes`` only and
asserts the whole header. Every header is read as DATA from the checked-in
wrapper source (``_generated/sldworks_2026.py``: each generated method's
``InvokeTypes`` call and each ``_prop_map_get_`` entry), so the contract runs on
any host, pywin32 or not. Two checks need pywin32 itself -- that
``raw_dispatch`` records exactly those headers from the imported wrapper, and
the end-to-end edge selection, which binds ``IEntity`` through it -- so they
run on Windows only, where a missing wrapper FAILS instead of skipping. The diff
tests use plain Python doubles, which ``raw_dispatch.invoke`` answers through
``getattr``.

Run: ``uv run python -m pytest cad/scripts/test_adapter_feature_resolution.py -q``
"""

from __future__ import annotations

import ast
import functools
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from solidworks_mcp.adapters import raw_dispatch, sw_type_info
from solidworks_mcp.adapters.base import CreateReferencePointParameters
from solidworks_mcp.adapters.solidworks import features, reference_geometry

# (dispid, lcid, flags, return type, argument types) from the SolidWorks 2026
# type library. flags 1 = method call, 2 = property get; 9 = IDispatch,
# 12 = VARIANT, 8 = BSTR, 11 = bool, 5 = double, 3 = int.
FIRST_FEATURE = (65801, 0, 1, (9, 0), ())
FEATURE_BY_POSITION_REVERSE = (66006, 0, 1, (9, 0), ((3, 1),))
GET_NEXT_FEATURE = (3, 0, 1, (9, 0), ())
FEATURE_NAME = (1, 0, 2, (8, 0), ())
GET_TYPE_NAME2 = (103, 0, 1, (8, 0), ())
BODY_GET_EDGES = (125, 0, 1, (12, 0), ())
EDGE_GET_CLOSEST_POINT_ON = (18, 0, 1, (12, 0), ((5, 1), (5, 1), (5, 1)))
ENTITY_SELECT2 = (65552, 0, 1, (11, 0), ((11, 1), (3, 1)))

PINNED = {
    ("IModelDoc2", "FirstFeature"): FIRST_FEATURE,
    ("IModelDoc2", "FeatureByPositionReverse"): FEATURE_BY_POSITION_REVERSE,
    ("IFeature", "GetNextFeature"): GET_NEXT_FEATURE,
    ("IFeature", "Name"): FEATURE_NAME,
    ("IFeature", "GetTypeName2"): GET_TYPE_NAME2,
    ("IBody2", "GetEdges"): BODY_GET_EDGES,
    ("IEdge", "GetClosestPointOn"): EDGE_GET_CLOSEST_POINT_ON,
    ("IEntity", "Select2"): ENTITY_SELECT2,
}

WRAPPER_SOURCE = Path(sw_type_info.__file__).parent / "_generated" / "sldworks_2026.py"


@functools.cache
def wrapper_headers() -> dict[tuple[str, str], tuple]:
    """The header the checked-in wrapper sends for every ``PINNED`` member,
    parsed from its source without importing it (the import needs pywin32).

    A generated method either sends ``self._oleobj_.InvokeTypes(dispid, LCID,
    flags, ret, args, ...)`` itself or hands ``(dispid, flags, ret, args)`` to
    ``DispatchBaseClass._ApplyTypes_`` (VARIANT results); a property is read
    through ``_prop_map_get_[member] = (dispid, flags, ret, args, ...)``, also
    via ``_ApplyTypes_``, which sends LCID 0. A method shadows a property of the
    same name, as on the class."""
    source = WRAPPER_SOURCE.read_text(encoding="utf-8")
    lcid = ast.literal_eval(re.search(r"^LCID = (.+)$", source, re.M).group(1))
    apply_types_lcid = 0  # pywin32's _ApplyTypes_ hard-codes it

    def header(nodes, call_lcid):
        dispid, flags, ret, args = (ast.literal_eval(node) for node in nodes)
        return (dispid, call_lcid, flags, ret, args)

    headers: dict[tuple[str, str], tuple] = {}
    for interface in {interface for interface, _ in PINNED}:
        start = re.search(rf"^class {interface}\(", source, re.M)
        assert start, f"{interface} is not in the checked-in wrapper"
        following = re.compile(r"^class ", re.M).search(source, start.end())
        end = following.start() if following else None
        (cls,) = ast.parse(source[start.start() : end]).body
        methods, properties = {}, {}
        for item in cls.body:
            if isinstance(item, ast.FunctionDef):
                for node in ast.walk(item):
                    if not (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                    ):
                        continue
                    if node.func.attr == "InvokeTypes":
                        dispid, _lcid, *rest = node.args[:5]
                        methods[item.name] = header([dispid, *rest], lcid)
                        break
                    if node.func.attr == "_ApplyTypes_":
                        methods[item.name] = header(node.args[:4], apply_types_lcid)
                        break
            elif (
                isinstance(item, ast.Assign)
                and getattr(item.targets[0], "id", None) == "_prop_map_get_"
            ):
                for key, value in zip(item.value.keys, item.value.values):
                    properties[ast.literal_eval(key)] = header(
                        value.elts[:4], apply_types_lcid
                    )
        for owner, member in PINNED:
            if owner == interface:
                found = methods.get(member, properties.get(member))
                assert found, f"{interface}.{member} is not in the wrapper"
                headers[(owner, member)] = found
    return headers


@pytest.mark.parametrize(("interface", "member"), sorted(PINNED))
def test_pinned_header_is_the_checked_in_wrappers(interface, member):
    assert wrapper_headers()[(interface, member)] == PINNED[(interface, member)]


@pytest.fixture
def raw_headers(monkeypatch):
    """``raw_dispatch``'s header cache, filled from the wrapper SOURCE, so the
    raw path runs without importing the wrapper."""
    for key, header in wrapper_headers().items():
        monkeypatch.setitem(raw_dispatch._HEADERS, key, header)


windows_only = pytest.mark.skipif(
    sys.platform != "win32",
    reason="pywin32 (and the imported wrapper) exist only on Windows",
)


@pytest.fixture
def generated_wrapper():
    """The imported wrapper. On Windows missing it FAILS: every build leaf runs
    the raw path through it."""
    sw_type_info._ensure_loaded()
    assert sw_type_info.PYWIN32_AVAILABLE, "pywin32 is required on Windows"
    assert sw_type_info._wrapper_module is not None, "generated wrapper not loaded"


def _raise(message):
    def fail(*_args):
        raise RuntimeError(message)

    return fail


class Adapter:
    def __init__(self, model):
        self.currentModel = model

    def _attempt(self, callback, default=None):
        try:
            return callback()
        except Exception:
            return default

    def _handle_com_operation(self, _name, callback):
        return callback()

    def _get_feature_id(self, feature):
        return feature.Name


class RawDispatch:
    """A bare ``PyIDispatch`` stand-in: only ``InvokeTypes``, keyed by dispid.

    A dispid it does not know, or a known dispid sent with any other header,
    fails the test."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def InvokeTypes(self, dispid, lcid, flags, ret_type, arg_types, *args):  # noqa: N802
        header = (dispid, lcid, flags, ret_type, arg_types)
        self.calls.append((header, args))
        assert dispid in self.answers, f"unexpected dispid {dispid}"
        expected, answer = self.answers[dispid]
        assert header == expected
        return answer(*args) if callable(answer) else answer


INVOKED = [
    ("IModelDoc2", "FirstFeature", ()),
    ("IModelDoc2", "FeatureByPositionReverse", (2,)),
    ("IFeature", "GetNextFeature", ()),
    ("IFeature", "Name", ()),
    ("IFeature", "GetTypeName2", ()),
    ("IBody2", "GetEdges", ()),
    ("IEdge", "GetClosestPointOn", (0.001, 0.002, 0.003)),
]


@pytest.mark.usefixtures("raw_headers")
@pytest.mark.parametrize(("interface", "member", "args"), INVOKED)
def test_invoke_sends_the_wrappers_header(interface, member, args):
    header = PINNED[(interface, member)]
    raw = RawDispatch({header[0]: (header, "answer")})

    assert raw_dispatch.invoke(raw, interface, member, *args) == "answer"
    assert raw.calls == [(header, args)]


@windows_only
@pytest.mark.usefixtures("generated_wrapper")
@pytest.mark.parametrize(("interface", "member", "args"), INVOKED)
def test_recorded_header_is_the_generated_members_call(
    monkeypatch, interface, member, args
):
    monkeypatch.delitem(raw_dispatch._HEADERS, (interface, member), raising=False)
    header = PINNED[(interface, member)]
    raw = RawDispatch({header[0]: (header, "answer")})
    raw_dispatch.invoke(raw, interface, member, *args)
    generated = RawDispatch({header[0]: (header, None)})
    wrapper = sw_type_info.early_bound(SimpleNamespace(_oleobj_=generated), interface)
    value = getattr(wrapper, member)
    if callable(value):
        value(*args)
    assert raw.calls == generated.calls == [(header, args)]


@pytest.mark.usefixtures("raw_headers")
def test_invoke_returns_object_results_unwrapped():
    first = RawDispatch({})
    model = RawDispatch({FIRST_FEATURE[0]: (FIRST_FEATURE, first)})
    assert raw_dispatch.invoke(model, "IModelDoc2", "FirstFeature") is first

    edges = (RawDispatch({}), RawDispatch({}))
    body = RawDispatch({BODY_GET_EDGES[0]: (BODY_GET_EDGES, edges)})
    assert raw_dispatch.invoke(body, "IBody2", "GetEdges") is edges

    point = (0.25, 0.5, 0.75, 1.0, 0.0, 0.0)
    edge = RawDispatch(
        {EDGE_GET_CLOSEST_POINT_ON[0]: (EDGE_GET_CLOSEST_POINT_ON, point)}
    )
    assert (
        raw_dispatch.invoke(edge, "IEdge", "GetClosestPointOn", 0.2, 0.5, 0.8) == point
    )


@windows_only
@pytest.mark.usefixtures("generated_wrapper")
def test_edge_selection_selects_the_nearest_edge_through_ientity():
    def edge(closest):
        return RawDispatch(
            {
                EDGE_GET_CLOSEST_POINT_ON[0]: (
                    EDGE_GET_CLOSEST_POINT_ON,
                    lambda x, y, z: closest,
                ),
                ENTITY_SELECT2[0]: (ENTITY_SELECT2, True),
            }
        )

    far = edge((0.0103, 0.0, 0.0))
    near = edge((0.0101, 0.0, 0.0))
    missed = edge((0.5, 0.5, 0.5))
    body = RawDispatch({BODY_GET_EDGES[0]: (BODY_GET_EDGES, (far, near, missed))})
    model = SimpleNamespace(
        GetBodies2=lambda _type, _visible: (body,), ClearSelection2=lambda _a: True
    )

    assert features._select_edges_geometric(Adapter(model), [[10.0, 0.0, 0.0]])

    probe = (EDGE_GET_CLOSEST_POINT_ON, (0.01, 0.0, 0.0))
    assert far.calls == [probe] and missed.calls == [probe]
    assert near.calls == [probe, (ENTITY_SELECT2, (True, 0))]


@pytest.mark.usefixtures("raw_headers")
def test_raw_tree_diff_resolves_the_created_feature():
    tree = []

    def raw_feature(name, type_name):
        feat = RawDispatch({})
        feat.answers = {
            GET_NEXT_FEATURE[0]: (
                GET_NEXT_FEATURE,
                lambda: (
                    tree[tree.index(feat) + 1]
                    if tree.index(feat) + 1 < len(tree)
                    else None
                ),
            ),
            FEATURE_NAME[0]: (FEATURE_NAME, name),
            GET_TYPE_NAME2[0]: (GET_TYPE_NAME2, type_name),
        }
        return feat

    def by_position_reverse(position):
        # Zero-based, as SOLIDWORKS documents it: 0 is the last feature.
        index = len(tree) - 1 - position
        return tree[index] if 0 <= index < len(tree) else None

    tree += [raw_feature(name, type_name) for name, type_name in PART]
    model = RawDispatch(
        {
            FIRST_FEATURE[0]: (FIRST_FEATURE, lambda: tree[0]),
            FEATURE_BY_POSITION_REVERSE[0]: (
                FEATURE_BY_POSITION_REVERSE,
                by_position_reverse,
            ),
        }
    )
    adapter = Adapter(model)
    before = features._tree_snapshot(adapter)
    assert before.error is None and before.positional
    tree.append(raw_feature("Plane1", "RefPlane"))
    tree.append(raw_feature("Sketch2", "ProfileFeature"))
    paths = []
    features.set_tree_path_observer(lambda lookup, path: paths.append((lookup, path)))
    try:
        found = features._resolve_feature(
            adapter, None, before, frozenset({"RefPlane"})
        )
    finally:
        features.set_tree_path_observer(None)

    assert getattr(found, "_oleobj_", found) is tree[-2]
    assert raw_dispatch.invoke(found, "IFeature", "Name") == "Plane1"
    assert paths == [("diff", "positional")]


# --- diff logic: plain doubles, any host ---------------------------------------


class Feature:
    """A top-level feature, read through ``getattr`` by ``raw_dispatch.invoke``."""

    def __init__(self, tree, name, type_name):
        self.tree = tree
        self.name = name
        self.type_name = type_name
        self.next_error = None
        self.name_error = None

    @property
    def Name(self):  # noqa: N802
        if self.name_error:
            raise RuntimeError(self.name_error)
        return self.name

    def GetTypeName2(self):  # noqa: N802
        return self.type_name

    def GetNextFeature(self):  # noqa: N802
        if self.next_error:
            raise RuntimeError(self.next_error)
        index = self.tree.features.index(self) + 1
        return self.tree.features[index] if index < len(self.tree.features) else None


class Tree:
    """A part's model: its top-level feature tree plus whatever a test adds."""

    def __init__(self, *features, positional=True, first_position=0):
        self.features = [Feature(self, name, type_name) for name, type_name in features]
        self.positional = positional
        self.first_position = first_position

    def append(self, name, type_name):
        self.features.append(Feature(self, name, type_name))

    def insert(self, index, name, type_name):
        self.features.insert(index, Feature(self, name, type_name))

    @property
    def FirstFeature(self):  # noqa: N802
        return self.features[0] if self.features else None

    def FeatureByPositionReverse(self, position):  # noqa: N802
        if not self.positional:
            raise RuntimeError("FeatureByPositionReverse unavailable")
        index = len(self.features) - 1 - (position - self.first_position)
        return self.features[index] if 0 <= index < len(self.features) else None


PART = (
    ("Origin", "OriginProfileFeature"),
    ("Front Plane", "RefPlane"),
    ("Top Plane", "RefPlane"),
    ("Sketch1", "ProfileFeature"),
    ("Boss-Extrude1", "Extrusion"),
)


# The before-snapshot fails closed.


@pytest.mark.parametrize("positional", [True, False])
def test_truncated_before_walk_refuses_to_diff(positional):
    tree = Tree(*PART, positional=positional)
    tree.features[1].next_error = "RPC_E_DISCONNECTED"
    adapter = Adapter(tree)

    before = features._tree_snapshot(adapter)
    # InsertRefPlane created nothing. Diffed against the two features the walk
    # reached, the untouched Top Plane would pass for the created plane.
    with pytest.raises(RuntimeError, match="incomplete"):
        features._resolve_feature(adapter, None, before, frozenset({"RefPlane"}))


def test_unreadable_feature_name_refuses_to_diff():
    tree = Tree(*PART)
    tree.features[3].name_error = "E_FAIL"
    adapter = Adapter(tree)

    before = features._tree_snapshot(adapter)
    tree.append("Plane1", "RefPlane")

    with pytest.raises(RuntimeError, match="incomplete"):
        features._resolve_feature(adapter, None, before, frozenset({"RefPlane"}))


def test_returned_feature_wins_over_an_incomplete_snapshot():
    tree = Tree(*PART)
    tree.features[0].next_error = "RPC_E_DISCONNECTED"
    adapter = Adapter(tree)
    before = features._tree_snapshot(adapter)
    returned = SimpleNamespace(Name="Chamfer1")

    assert (
        features._resolve_feature(adapter, returned, before, frozenset({"Chamfer"}))
        is returned
    )


# The created feature is chosen by type.


@pytest.mark.parametrize("positional", [True, False])
def test_created_feature_is_found_by_type_past_an_auxiliary_feature(positional):
    tree = Tree(*PART, positional=positional)
    adapter = Adapter(tree)
    before = features._tree_snapshot(adapter)
    tree.append("Plane1", "RefPlane")
    tree.append("Sketch2", "ProfileFeature")  # auxiliary, newest

    found = features._resolve_feature(adapter, None, before, frozenset({"RefPlane"}))

    assert found is tree.features[-2]


@pytest.mark.parametrize("positional", [True, False])
def test_created_feature_above_a_rollback_bar_is_found(positional):
    tree = Tree(*PART, positional=positional)
    adapter = Adapter(tree)
    before = features._tree_snapshot(adapter)
    tree.insert(3, "Axis1", "RefAxis")

    found = features._resolve_feature(adapter, None, before, frozenset({"RefAxis"}))

    assert found.Name == "Axis1"


@pytest.mark.parametrize("positional", [True, False])
def test_two_added_features_of_the_expected_type_are_ambiguous(positional):
    tree = Tree(*PART, positional=positional)
    adapter = Adapter(tree)
    before = features._tree_snapshot(adapter)
    tree.append("Plane1", "RefPlane")
    tree.append("Plane2", "RefPlane")

    with pytest.raises(RuntimeError, match="ambiguous"):
        features._resolve_feature(adapter, None, before, frozenset({"RefPlane"}))


@pytest.mark.parametrize("positional", [True, False])
def test_expect_many_returns_the_newest_match(positional):
    tree = Tree(*PART, positional=positional)
    adapter = Adapter(tree)
    before = features._tree_snapshot(adapter)
    tree.append("Point1", "RefPoint")
    tree.append("Point2", "RefPoint")
    tree.append("Point3", "RefPoint")
    tree.append("Sketch2", "ProfileFeature")  # auxiliary, newest

    found = features._resolve_feature(
        adapter, None, before, frozenset({"RefPoint"}), expect_many=True
    )

    assert found.Name == "Point3"


@pytest.mark.parametrize("positional", [True, False])
def test_added_features_without_the_expected_type_raise(positional):
    tree = Tree(*PART, positional=positional)
    adapter = Adapter(tree)
    before = features._tree_snapshot(adapter)
    tree.append("Sketch2", "ProfileFeature")

    with pytest.raises(
        RuntimeError, match=r"no Shell feature .*Sketch2 \(ProfileFeature\)"
    ):
        features._resolve_feature(
            adapter, None, before, frozenset({"Shell"}), expect_many=True
        )


@pytest.mark.parametrize("positional", [True, False])
def test_nothing_added_resolves_to_none(positional):
    tree = Tree(*PART, positional=positional)
    adapter = Adapter(tree)
    before = features._tree_snapshot(adapter)

    assert (
        features._resolve_feature(adapter, None, before, frozenset({"Fillet"})) is None
    )


# FeatureByPositionReverse is used only where it agrees with the forward walk.


@pytest.mark.parametrize(("first_position", "path"), [(0, "positional"), (1, "walk")])
def test_the_diff_counts_from_the_end_only_when_positions_match_the_walk(
    first_position, path
):
    # SOLIDWORKS documents position 0 as the last feature. A seat that counted
    # from 1 would fail the snapshot's two probes, and the diff walks instead
    # of trusting positions shifted by one.
    tree = Tree(*PART, first_position=first_position)
    adapter = Adapter(tree)
    before = features._tree_snapshot(adapter)
    tree.append("Fillet1", "Fillet")
    paths = []
    features.set_tree_path_observer(lambda lookup, taken: paths.append((lookup, taken)))
    try:
        found = features._resolve_feature(adapter, None, before, frozenset({"Fillet"}))
    finally:
        features.set_tree_path_observer(None)

    assert before.positional is (first_position == 0)
    assert found.Name == "Fillet1"
    assert paths == [("diff", path)]


# create_reference_point: "evenly" makes several points, one otherwise.


def _point_model(created):
    tree = Tree(*PART)
    tree.ClearSelection2 = lambda _all: True
    tree.Extension = SimpleNamespace(SelectByID2=lambda *_a, **_k: True)

    def insert_reference_point(_type, _along, _value, count):
        for index in range(1, (count if created is None else created) + 1):
            tree.append(f"Point{index}", "RefPoint")
        return None  # resolved by the tree diff

    tree.FeatureManager = SimpleNamespace(InsertReferencePoint=insert_reference_point)
    return tree


def test_evenly_distributed_points_return_the_last_point():
    adapter = Adapter(_point_model(created=None))

    result = reference_geometry._create_reference_point_impl(
        adapter,
        CreateReferencePointParameters(
            mode="along_curve", edge_point=[10.0, 0.0, 0.0], along="evenly", count=4
        ),
    )

    assert result.name == "Point4"


def test_a_single_point_call_that_adds_two_points_is_ambiguous():
    adapter = Adapter(_point_model(created=2))

    with pytest.raises(RuntimeError, match="ambiguous"):
        reference_geometry._create_reference_point_impl(
            adapter,
            CreateReferencePointParameters(
                mode="along_curve",
                edge_point=[10.0, 0.0, 0.0],
                along="percentage",
                percentage=50.0,
            ),
        )
