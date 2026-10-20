"""Offline shared-vendor occurrence, balloon and associative-Number contracts.

The doubles expose only the COM members these helpers consume. They do not
construct an adapter, connect to SOLIDWORKS or read production native files.
"""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace

import pytest

import _assembly as assembly
import _com
import _component_references as references
import _drawing_balloons as balloons
import _drawing_tables as tables

WIRE = "sh-vn-music-wire"
SCREW = "sh-vn-fillister-screw-90280a108"
NUMBER = "MHA-SH-VN-56"
ROWS = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _component(
    name="sh-vn-music-wire--LeverWire-73",
    *,
    stem=WIRE,
    configuration="LeverWire",
    reference="LeverWire:1",
    properties=None,
):
    reads = []

    def property_value(member, property_name):
        reads.append((member, property_name))
        return (properties or {}).get((member, property_name), "")

    document = SimpleNamespace(GetCustomInfoValue=property_value)
    return SimpleNamespace(
        Name2=name,
        ReferencedConfiguration=configuration,
        ComponentReference=reference,
        GetPathName=lambda: f"C:\\native\\{stem}.SLDPRT",
        GetModelDoc2=lambda: document,
        property_reads=reads,
    )


def _model(*components):
    queries = []

    def get_components(top_level):
        queries.append(top_level)
        return components

    return SimpleNamespace(GetComponents=get_components, queries=queries)


@pytest.fixture
def unwrapped_com(monkeypatch):
    for module in (references, balloons, assembly, _com):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        tables._sw_type_info,
        "early_bound_or_flag",
        lambda value, *_members: value,
    )


@pytest.mark.parametrize("suffix", ["", " Simplified"])
def test_reference_binds_arbitrary_native_index_and_exact_member(unwrapped_com, suffix):
    component = _component(
        "unrelated-native-basename-207",
        stem=WIRE.upper(),
        configuration="LeverWire" + suffix,
    )
    model = _model(component)
    assert references.component_reference_names(
        model,
        {"@LeverWire:1": (WIRE, "LeverWire")},
    ) == {"@LeverWire:1": "unrelated-native-basename-207"}
    assert model.queries == [False]


@pytest.mark.parametrize(
    "declared",
    [
        ("sh-vn-chain-link", "OuterLink"),
        ("other-native-file", "InnerLink"),
    ],
)
def test_reference_declaration_cannot_redefine_a_fixed_role_identity(
    unwrapped_com, declared
):
    model = _model()
    with pytest.raises(ValueError, match="not declared identity"):
        references.component_reference_names(model, {"@InnerLink:1": declared})
    assert model.queries == []


def test_reference_binding_keeps_parent_scope_and_local_ordinals(unwrapped_com):
    wanted = _component("parent-17/native-wire-83")
    other_scope = _component("parent-29/native-wire-1")
    second = _component("parent-17/native-wire-302", reference="LeverWire:2")
    model = _model(other_scope, second, wanted)
    assert references.component_reference_names(
        model,
        {
            "parent-17/@LeverWire:1": (WIRE, "LeverWire"),
            "parent-17/@LeverWire:2": (WIRE, "LeverWire"),
            "parent-29/@LeverWire:1": (WIRE, "LeverWire"),
        },
    ) == {
        "parent-17/@LeverWire:1": wanted.Name2,
        "parent-17/@LeverWire:2": second.Name2,
        "parent-29/@LeverWire:1": other_scope.Name2,
    }
    assert references.component_reference_names(
        model,
        {
            "parent-17\\@LeverWire:1": (WIRE, "LeverWire Simplified"),
        },
    ) == {"parent-17\\@LeverWire:1": wanted.Name2}


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"stem": WIRE + "-copy"}, "selects"),
        ({"configuration": "PenWire"}, "selects"),
        ({"configuration": "leverwire"}, "selects"),
        ({"configuration": "LeverWire extra"}, "selects"),
        ({"configuration": "LeverWire Simplified Simplified"}, "selects"),
        ({"reference": "PenWire:1"}, "missing native component references"),
        ({"reference": ""}, "missing native component references"),
    ],
)
def test_reference_refuses_wrong_file_member_or_role(unwrapped_com, changes, message):
    # Even a plausible old Name2 cannot supply missing physical/reference data.
    component = _component("sh-vn-music-wire--LeverWire-1", **changes)
    with pytest.raises(RuntimeError, match=message):
        references.component_reference_names(
            _model(component),
            {"@LeverWire:1": (WIRE, "LeverWire")},
        )


def test_reference_refuses_duplicate_reference_in_one_parent(unwrapped_com):
    with pytest.raises(RuntimeError, match="duplicated"):
        references.component_reference_names(
            _model(_component("parent-1/native-7"), _component("parent-1/native-99")),
            {"parent-1/@LeverWire:1": (WIRE, "LeverWire")},
        )
    with pytest.raises(RuntimeError, match="missing native component references"):
        references.component_reference_names(
            _model(_component("parent-2/native-7")),
            {"parent-1/@LeverWire:1": (WIRE, "LeverWire")},
        )


@pytest.mark.parametrize(
    "selector",
    [
        "@LeverWire:0",
        "@LeverWire:01",
        "@LeverWire:-1",
        "@LeverWire",
        "@LeverWire:1extra",
        "@UnknownRole:1",
        "parent-1/@FootScrew:0",
    ],
)
def test_malformed_reference_fails_before_native_enumeration(unwrapped_com, selector):
    model = _model()
    with pytest.raises(ValueError, match="invalid shared-component reference"):
        references.component_reference_names(model, {selector: (WIRE, "LeverWire")})
    assert model.queries == []


def test_explicit_binding_leaves_ordinary_native_names_untouched(unwrapped_com):
    component = _component()
    assert references.bind_component_selectors(
        _model(component),
        ["ordinary-part-11", "@LeverWire:1", "@LeverWire:1"],
    ) == {"ordinary-part-11": "ordinary-part-11", "@LeverWire:1": component.Name2}
    with pytest.raises(ValueError, match="not an explicit"):
        references.component_reference_names(
            _model(component),
            {component.Name2: (WIRE, "LeverWire")},
        )


def _leaf(component, *, visible=True, drawing_name=None):
    adapter = SimpleNamespace(_attempt=lambda callback, default=None: callback())
    drawing_component = SimpleNamespace(
        Component=component,
        Name=drawing_name or f"view-root/{component.Name2}@Drawing View1",
    )
    return balloons._component_leaf(adapter, drawing_component, visible=visible)


@pytest.mark.parametrize("suffix", ["", " Simplified"])
def test_balloon_configured_key_is_case_normalized_from_physical_member(
    unwrapped_com, suffix
):
    leaf = _leaf(_component(stem=WIRE.upper(), configuration="LeverWire" + suffix))
    requested = frozenset({WIRE, (WIRE + "--LeverWire").upper(), WIRE + "--PenWire"})
    assert balloons._stems_matching(leaf.identities, requested) == {
        WIRE,
        (WIRE + "--LeverWire").upper(),
    }


def test_balloon_cannot_match_wrong_member_through_a_stale_occurrence_name(
    unwrapped_com,
):
    leaf = _leaf(
        _component(
            "sh-vn-music-wire--LeverWire-1",
            configuration="PenWire",
            reference="",
        )
    )
    assert balloons._stems_matching(
        leaf.identities,
        frozenset({WIRE + "--LeverWire", WIRE + "--PenWire"}),
    ) == {WIRE + "--PenWire"}
    with pytest.raises(RuntimeError, match="has no shown instance"):
        balloons._shown_instances(
            [leaf],
            WIRE + "--LeverWire",
            balloons.BalloonAnchor(),
            label="wire",
        )


def test_balloon_rejects_reference_attached_to_wrong_physical_member(unwrapped_com):
    with pytest.raises(RuntimeError, match="requires"):
        _leaf(_component(configuration="PenWire", reference="LeverWire:1"))
    with pytest.raises(RuntimeError, match="requires"):
        _leaf(_component(reference="FootScrew:1"))


def test_semantic_balloon_anchor_selects_unique_native_name_in_its_scope(unwrapped_com):
    wanted = _leaf(_component("parent-17/native-wire-83"))
    other_scope = _leaf(_component("parent-29/native-wire-1"))
    other_ordinal = _leaf(
        _component("parent-17/native-wire-1", reference="LeverWire:2")
    )
    shown = balloons._shown_instances(
        [other_scope, other_ordinal, wanted],
        WIRE + "--LeverWire",
        balloons.BalloonAnchor(instance="parent-17/@LeverWire:1"),
        label="wire",
    )
    assert len(shown) == 1 and shown[0] is wanted
    assert shown[0].path == "parent-17/native-wire-83"


@pytest.mark.parametrize("fault", ["hidden", "duplicate", "missing"])
def test_semantic_balloon_anchor_refuses_hidden_duplicate_or_missing_occurrence(
    unwrapped_com,
    fault,
):
    wanted = _leaf(_component("parent-17/native-wire-83"), visible=fault != "hidden")
    leaves = [] if fault == "missing" else [wanted]
    if fault == "duplicate":
        # A hidden duplicate is still ambiguous native identity, not permission
        # to silently choose whichever occurrence the view happens to show.
        leaves.append(_leaf(_component("parent-17/native-wire-92"), visible=False))
    with pytest.raises(RuntimeError, match="has no shown instance|native occurrences"):
        balloons._shown_instances(
            leaves,
            WIRE + "--LeverWire",
            balloons.BalloonAnchor(instance="parent-17/@LeverWire:1"),
            label="wire",
        )


class _NumberTable:
    def __init__(self, components, *, displayed=NUMBER):
        self.cells = [["ITEM NO.", "PART NUMBER", "QTY."], ["1", displayed, "1"]]
        self.components = tuple(components)
        self.ColumnCount = 3
        self.RowCount = 2
        self.type_status = 0
        self.accept_property = True
        self.property_readback = "Number"
        self.accept_title = True
        self.column_property = ""
        self.calls = []

    def DisplayedText(self, row, column):
        return self.cells[row][column]

    def SetColumnType3(self, column, kind, all_configurations, property_name):
        self.calls.append(("type", column, kind, all_configurations, property_name))
        return self.type_status

    def SetColumnCustomProperty(self, column, property_name):
        self.calls.append(("property", column, property_name))
        self.column_property = property_name
        return self.accept_property

    def GetColumnCustomProperty(self, column):
        self.calls.append(("property-read", column))
        return self.property_readback

    def SetColumnTitle2(self, column, title, include_hidden):
        self.calls.append(("title", column, title, include_hidden))
        self.cells[0][column] = title
        return self.accept_title

    def GetComponents2(self, row, configuration):
        self.calls.append(("components", row, configuration))
        return self.components


@pytest.fixture
def number_binding(unwrapped_com, monkeypatch):
    rebuilds = []
    adapter = SimpleNamespace(currentModel=object())

    def rebuild(actual_adapter, *, label):
        assert actual_adapter is adapter
        rebuilds.append(label)

    monkeypatch.setattr(tables, "rebuild_drawing", rebuild)
    return adapter, rebuilds


@pytest.mark.parametrize("member", ["LeverWire", "LeverWire Simplified"])
def test_number_column_binds_native_property_and_reads_actual_configuration(
    number_binding, member
):
    adapter, rebuilds = number_binding
    component = _component(
        properties={
            (member, "Number"): NUMBER,
            ("", "Number"): "WRONG-GLOBAL-NUMBER",
        },
        configuration=member,
    )
    table = _NumberTable([component])
    tables._bind_bom_number_property(
        adapter,
        table,
        configuration="Default Simplified",
        label="wire",
    )
    assert table.calls[:4] == [
        ("type", 1, 204, True, "Number"),
        ("property", 1, "Number"),
        ("property-read", 1),
        ("title", 1, "PART NUMBER", True),
    ]
    assert ("components", 1, "Default Simplified") in table.calls
    assert component.property_reads == [(member, "Number")]
    assert table.cells[0][1] == "PART NUMBER"
    assert table.cells[1][1] == NUMBER
    assert rebuilds == ["bind_bom_number_property"]


def test_number_column_uses_document_property_only_when_actual_member_has_none(
    number_binding,
):
    adapter, _rebuilds = number_binding
    component = _component(
        configuration="LeverWire Simplified",
        properties={
            ("LeverWire", "Number"): "UNSIMPLIFIED-PROPERTY-MUST-NOT-WIN",
            ("", "Number"): NUMBER,
        },
    )
    tables._bind_bom_number_property(
        adapter,
        _NumberTable([component]),
        configuration="Default Simplified",
        label="wire",
    )
    assert component.property_reads == [
        ("LeverWire Simplified", "Number"),
        ("", "Number"),
    ]


@pytest.mark.parametrize(
    "fault, message",
    [
        ("column-type", "column type failed"),
        ("property-write", "rejected the Number property"),
        ("property-readback", "binding did not persist"),
        ("title", "header could not be restored"),
        ("header", "no PART NUMBER column"),
    ],
)
def test_number_column_binding_refuses_native_metadata_failures(
    number_binding, fault, message
):
    adapter, rebuilds = number_binding
    table = _NumberTable([_component(properties={("LeverWire", "Number"): NUMBER})])
    if fault == "column-type":
        table.type_status = 1
    elif fault == "property-write":
        table.accept_property = False
    elif fault == "property-readback":
        table.property_readback = "Description"
    elif fault == "title":
        table.accept_title = False
    else:
        table.cells[0][1] = "UNRELATED PROPERTY"
    with pytest.raises(RuntimeError, match=message):
        tables._bind_bom_number_property(
            adapter, table, configuration="Default", label="wire"
        )
    assert rebuilds == []


@pytest.mark.parametrize(
    "fault, message",
    [
        ("blank-property", "has no Number property"),
        ("blank-display", "associative Number"),
        ("wrong-display", "associative Number"),
        ("merged-numbers", "associative Number"),
        ("no-components", "no native components"),
        ("unresolved-document", "document is not resolved"),
    ],
)
def test_number_column_refuses_blank_wrong_or_merged_native_numbers(
    number_binding, fault, message
):
    adapter, _rebuilds = number_binding
    component = _component(properties={("LeverWire", "Number"): NUMBER})
    table = _NumberTable([component])
    if fault == "blank-property":
        table.components = (_component(properties={("LeverWire", "Number"): "  "}),)
    elif fault == "blank-display":
        table.cells[1][1] = ""
    elif fault == "wrong-display":
        table.cells[1][1] = "MHA-SH-VN-57"
    elif fault == "merged-numbers":
        table.components += (
            _component(properties={("LeverWire", "Number"): "MHA-SH-VN-57"}),
        )
    elif fault == "no-components":
        table.components = ()
    else:
        component.GetModelDoc2 = lambda: None
    with pytest.raises(RuntimeError, match=message):
        tables._bind_bom_number_property(
            adapter, table, configuration="Default", label="wire"
        )


@pytest.fixture
def placement_scene(unwrapped_com, monkeypatch, tmp_path):
    # Patch every native boundary and the global pose ledger, not the metadata
    # helpers whose readback contract these tests exercise.
    (tmp_path / f"{WIRE}.SLDPRT").touch()
    (tmp_path / f"{SCREW}.SLDPRT").touch()
    monkeypatch.setattr(assembly, "OUT_SLDPRT", tmp_path)
    monkeypatch.setattr(assembly, "part_path", lambda stem: tmp_path / f"{stem}.SLDPRT")
    monkeypatch.setattr(assembly, "check", lambda _label, result: result)
    placements = []
    monkeypatch.setattr(
        assembly, "assert_component_placed", lambda *args: placements.append(args)
    )
    monkeypatch.setattr(assembly, "_ledger_record", lambda *_args: None)
    monkeypatch.setattr(assembly, "_POSE_LEDGER", {})
    component = _component()
    rebuilds = []

    def rebuild(top_only):
        rebuilds.append(top_only)
        return True

    model = SimpleNamespace(
        GetComponentByName=lambda name: component if name == component.Name2 else None,
        ForceRebuild3=rebuild,
        EditRebuild3=lambda: rebuild(False),
    )

    async def insert(_parameters):
        return {"name": component.Name2, "fixed": False}

    adapter = SimpleNamespace(
        currentModel=model,
        insert_component=insert,
        _attempt=lambda callback, default=None: callback(),
    )
    return adapter, component, rebuilds, placements


@pytest.fixture(params=["single", "batch"])
def insertion_api(placement_scene, monkeypatch, request):
    adapter, component, rebuilds, placements = placement_scene
    position = [1.0, 2.0, 3.0]
    if request.param == "batch":
        component.Transform2 = SimpleNamespace(
            ArrayData=assembly._placement_transform(ROWS, position),
        )
        adapter.currentModel.AddComponents3 = lambda *_arrays: (component,)
        pythoncom = ModuleType("pythoncom")
        pythoncom.VT_ARRAY, pythoncom.VT_BSTR, pythoncom.VT_R8 = 0x2000, 8, 5
        client = ModuleType("win32com.client")
        client.VARIANT = lambda _kind, values: list(values)
        monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
        monkeypatch.setitem(sys.modules, "win32com.client", client)

    def place(part, *, configuration=None):
        options = {} if configuration is None else {"configuration": configuration}
        if request.param == "single":
            return [
                asyncio.run(
                    assembly.place_component(
                        adapter,
                        part,
                        position,
                        [0.0, 0.0, 0.0],
                        ROWS,
                        ground=False,
                        **options,
                    )
                )
            ]
        return asyncio.run(
            assembly.place_components_batch(
                adapter,
                [
                    {
                        "part": part,
                        "position": position,
                        "rows": ROWS,
                        "ground": False,
                        **options,
                    }
                ],
                label="shared configuration guard",
            )
        )

    return place, adapter, component, rebuilds, placements


@pytest.mark.parametrize(
    "active_member",
    [
        "LeverWire",
        "PenWire",
        "LeverWire Simplified",
        "Default Simplified",
        "default",
        "",
    ],
)
def test_implicit_shared_insertion_rejects_accidentally_active_member(
    insertion_api,
    active_member,
):
    place, _adapter, component, _rebuilds, placements = insertion_api
    component.ReferencedConfiguration = active_member
    component.ComponentReference = ""
    with pytest.raises(
        RuntimeError, match="selected configuration .*expected 'Default'"
    ):
        place(WIRE)
    # Refusal must not silently choose another body or certify the bad member.
    assert component.ReferencedConfiguration == active_member
    assert component.ComponentReference == ""
    assert placements == []


def test_implicit_ordinary_shared_insertion_accepts_exact_native_default(insertion_api):
    place, _adapter, component, _rebuilds, _placements = insertion_api
    component.Name2 = SCREW + "-83"
    component.GetPathName = lambda: f"C:/native/{SCREW}.SLDPRT"
    component.ReferencedConfiguration = "Default"
    component.ComponentReference = ""
    assert place(SCREW) == [SCREW + "-83"]
    assert component.ReferencedConfiguration == "Default"
    assert component.ComponentReference == ""


@pytest.mark.parametrize("drift", [False, True])
def test_explicit_member_without_reference_is_read_back_after_rebuild(
    insertion_api, drift
):
    place, adapter, component, rebuilds, placements = insertion_api
    component.ReferencedConfiguration = "LeverWire"
    component.ComponentReference = ""

    def rebuild(top_only):
        rebuilds.append(top_only)
        if drift:
            component.ReferencedConfiguration = "PenWire"
        return True

    adapter.currentModel.ForceRebuild3 = rebuild
    adapter.currentModel.EditRebuild3 = lambda: rebuild(False)
    if drift:
        with pytest.raises(RuntimeError, match="rebuild changed.*member"):
            place(WIRE, configuration="LeverWire")
        assert component.ReferencedConfiguration == "PenWire"
        assert placements == []
    else:
        assert place(WIRE, configuration="LeverWire") == [component.Name2]
        assert component.ReferencedConfiguration == "LeverWire"
    assert rebuilds
    assert component.ComponentReference == ""


def test_individual_insertion_reads_member_and_persists_reference(placement_scene):
    adapter, component, rebuilds, placements = placement_scene
    component.ComponentReference = ""
    actual = asyncio.run(
        assembly.place_component(
            adapter,
            WIRE,
            [1.0, 2.0, 3.0],
            [0.0, 0.0, 0.0],
            ROWS,
            ground=False,
            configuration="LeverWire",
            component_reference="LeverWire:1",
            occurrence_basename=WIRE + "--LeverWire",
        )
    )
    assert actual == component.Name2 == WIRE + "--LeverWire-73"
    assert component.ComponentReference == "LeverWire:1"
    assert rebuilds == [False]
    assert [call[1] for call in placements] == [actual]


@pytest.mark.parametrize(
    "actual_member", ["PenWire", "Default", "LeverWire Simplified"]
)
def test_individual_insertion_refuses_configuration_substitution(
    placement_scene, actual_member
):
    adapter, component, rebuilds, placements = placement_scene
    component.ReferencedConfiguration = actual_member
    component.ComponentReference = ""
    with pytest.raises(RuntimeError, match="selected configuration"):
        asyncio.run(
            assembly.place_component(
                adapter,
                WIRE,
                [1.0, 2.0, 3.0],
                [0.0, 0.0, 0.0],
                ROWS,
                ground=False,
                configuration="LeverWire",
                component_reference="LeverWire:1",
            )
        )
    assert component.ComponentReference == ""
    assert rebuilds == [] and placements == []


@pytest.mark.parametrize("fault", ["reference-loss", "configuration-drift"])
def test_individual_insertion_refuses_metadata_lost_during_rebuild(
    placement_scene, fault
):
    adapter, component, _rebuilds, placements = placement_scene

    def rebuild(_top_only):
        if fault == "reference-loss":
            component.ComponentReference = ""
        else:
            component.ReferencedConfiguration = "PenWire"
        return True

    adapter.currentModel.ForceRebuild3 = rebuild
    with pytest.raises(
        RuntimeError,
        match="rebuild lost component reference|rebuild changed component reference",
    ):
        asyncio.run(
            assembly.place_component(
                adapter,
                WIRE,
                [1.0, 2.0, 3.0],
                [0.0, 0.0, 0.0],
                ROWS,
                ground=False,
                configuration="LeverWire",
                component_reference="LeverWire:1",
            )
        )
    assert placements == []


@pytest.mark.parametrize("fault", ["none", "configuration-drift", "reference-loss"])
def test_batch_insertion_keeps_reordered_member_metadata_and_native_names(
    placement_scene,
    monkeypatch,
    fault,
):
    adapter, first, rebuilds, placements = placement_scene
    second = _component(WIRE + "--PenWire-91", configuration="Default", reference="")
    first.ReferencedConfiguration = "Default"
    first.ComponentReference = ""
    components = (first, second)
    positions = ([1.0, 2.0, 3.0], [41.0, 52.0, 63.0])
    for component, position in zip(components, positions, strict=True):
        component.Transform2 = SimpleNamespace(
            ArrayData=assembly._placement_transform(ROWS, position)
        )

    def add_components(_names, _transforms, _coordinate_systems):
        return second, first

    def rebuild(top_only):
        rebuilds.append(top_only)
        if fault == "configuration-drift":
            second.ReferencedConfiguration = "LeverWire"
        elif fault == "reference-loss":
            second.ComponentReference = ""
        return True

    adapter.currentModel.AddComponents3 = add_components
    adapter.currentModel.ForceRebuild3 = rebuild
    adapter.currentModel.GetComponentByName = lambda name: next(
        (component for component in components if component.Name2 == name),
        None,
    )
    # The local import receives inert SAFEARRAY stand-ins, never pywin32 COM.
    pythoncom = ModuleType("pythoncom")
    pythoncom.VT_ARRAY, pythoncom.VT_BSTR, pythoncom.VT_R8 = 0x2000, 8, 5
    client = ModuleType("win32com.client")
    client.VARIANT = lambda _kind, values: list(values)
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    specs = [
        {
            "part": WIRE,
            "position": position,
            "rows": ROWS,
            "ground": False,
            "configuration": member,
            "component_reference": member + ":1",
            "occurrence_basename": WIRE + "--" + member,
        }
        for position, member in zip(positions, ("LeverWire", "PenWire"), strict=True)
    ]
    if fault != "none":
        with pytest.raises(RuntimeError, match="rebuild changed|rebuild lost"):
            asyncio.run(
                assembly.place_components_batch(adapter, specs, label="wire members")
            )
        assert rebuilds == [False]
        return
    actual = asyncio.run(
        assembly.place_components_batch(adapter, specs, label="wire members")
    )
    assert actual == [first.Name2, second.Name2]
    assert [(c.ReferencedConfiguration, c.ComponentReference) for c in components] == [
        ("LeverWire", "LeverWire:1"),
        ("PenWire", "PenWire:1"),
    ]
    assert rebuilds == [False]
    assert [call[1] for call in placements] == actual


@pytest.mark.parametrize("initial_preference", [False, True])
@pytest.mark.parametrize("fault", ["none", "rename-rejected", "selection-cleanup"])
def test_pattern_seed_rename_preserves_native_index_pose_and_name_preference(
    unwrapped_com,
    monkeypatch,
    initial_preference,
    fault,
):
    import _preferences

    old_name = "parent-17/original-native-wire-83"
    new_name = "parent-17/sh-vn-music-wire--LeverWire-83"
    state = {"preference": initial_preference, "selected": False}

    class Component:
        ReferencedConfiguration = "LeverWire"
        ComponentReference = ""

        def __init__(self):
            self._name = old_name

        @property
        def Name2(self):
            return self._name

        @Name2.setter
        def Name2(self, basename):
            assert state["preference"] is False
            assert state["selected"] is True
            if fault == "rename-rejected":
                raise RuntimeError("native rename rejected")
            parent, _separator, leaf = self._name.rpartition("/")
            index = leaf.rsplit("-", 1)[-1]
            self._name = f"{parent}/{basename}-{index}"

        def GetPathName(self):
            return f"C:/native/{WIRE}.SLDPRT"

        def Select2(self, _append, _mark):
            state["selected"] = True
            return True

    component = Component()

    def set_preference(_identifier, value):
        state["preference"] = value
        return True

    def clear_selection(_all):
        state["selected"] = False
        if fault == "selection-cleanup":
            raise RuntimeError("selection cleanup failed")

    model = SimpleNamespace(
        GetComponentByName=lambda name: component if name == component.Name2 else None,
        ClearSelection2=clear_selection,
        ForceRebuild3=lambda _top_only: True,
    )
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(
            GetUserPreferenceToggle=lambda _identifier: state["preference"],
            SetUserPreferenceToggle=set_preference,
        ),
    )
    pose = ([1.0, 2.0, 3.0], [list(row) for row in ROWS])
    unrelated_pose = ([7.0, 8.0, 9.0], [list(row) for row in ROWS])
    ledger = {old_name: pose, "unrelated-part-4": unrelated_pose}
    monkeypatch.setattr(assembly, "_POSE_LEDGER", ledger)
    monkeypatch.setattr(_preferences, "_preference_id", lambda *_args: 77)

    def rename():
        return assembly.set_component_reference(
            adapter,
            old_name,
            "LeverWire:1",
            occurrence_basename=WIRE + "--LeverWire",
        )

    if fault != "none":
        message = (
            "native rename rejected"
            if fault == "rename-rejected"
            else "selection cleanup failed"
        )
        with pytest.raises(RuntimeError, match=message):
            rename()
        assert component.Name2 == (old_name if fault == "rename-rejected" else new_name)
        assert ledger == {old_name: pose, "unrelated-part-4": unrelated_pose}
    else:
        assert rename() == new_name
        assert component.Name2 == new_name
        assert component.ComponentReference == "LeverWire:1"
        assert old_name not in ledger
        assert ledger[new_name] is pose
        assert ledger["unrelated-part-4"] is unrelated_pose
        assert len(ledger) == 2
    assert state == {"preference": initial_preference, "selected": False}
