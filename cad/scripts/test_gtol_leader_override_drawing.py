"""The one-property control never claims or cleans up unrelated native docs."""

import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import probe_gtol_leader_override as probe
from test_datum_shoulder_drawing import owned_setup


def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    adapter, state, directory, part, make_document, activate = owned_setup(
        monkeypatch, tmp_path
    )

    def document(path):
        result = make_document(path)
        result.GetSaveFlag = lambda: False
        result.Visible = True
        return result

    unrelated = document(tmp_path / "other.SLDPRT")
    activate(unrelated)
    unsaved = document(tmp_path / "not-saved.SLDDRW")
    unsaved.GetPathName = lambda: ""
    unsaved.GetTitle = lambda: "Draw2 - Sheet1"
    unsaved.GetSaveFlag = lambda: True
    activate(unsaved)
    source = tmp_path / "rocker-arm.SLDDRW"
    source.write_bytes(b"original drawing")
    return (
        adapter,
        state,
        directory,
        part,
        document,
        activate,
        unrelated,
        unsaved,
        source,
    )


@pytest.mark.parametrize("stage", ["normal", "failure"])
def test_existing_saved_and_unsaved_docs_survive_owned_cleanup(
    monkeypatch, tmp_path, stage
):
    adapter, state, directory, part, document, activate, unrelated, unsaved, source = (
        setup(monkeypatch, tmp_path)
    )
    owned = probe.ExistingSessionCopy(adapter, directory, part, source)
    path = directory / "trial.SLDDRW"
    owned.expect_open(path)
    copy = document(path)
    copy.GetTitle = lambda: "trial - Sheet1"
    activate(copy)
    reference = document(part)
    state.documents.append(reference)
    owned.claim()

    async def finish():
        try:
            if stage == "failure":
                raise ValueError("setter failed")
        finally:
            await owned.close()

    if stage == "failure":
        with pytest.raises(ValueError, match="setter failed"):
            asyncio.run(finish())
    else:
        asyncio.run(finish())
    assert state.closes == [(copy, False)]
    assert state.documents == [unrelated, unsaved, reference]
    assert unsaved.GetSaveFlag() and unsaved.GetTitle() == "Draw2 - Sheet1"


@pytest.mark.parametrize(
    "change", ["identity", "dirty", "hidden", "unknown", "owned_path", "owned_title"]
)
def test_scope_refuses_changed_baseline_or_replaced_owned_copy(
    monkeypatch, tmp_path, change
):
    adapter, state, directory, part, document, activate, unrelated, unsaved, source = (
        setup(monkeypatch, tmp_path)
    )
    owned = probe.ExistingSessionCopy(adapter, directory, part, source)
    path = directory / "trial.SLDDRW"
    owned.expect_open(path)
    copy = document(path)
    activate(copy)
    owned.claim()
    if change == "identity":
        state.documents.remove(unrelated)
        state.documents.append(document(tmp_path / "other.SLDPRT"))
    if change == "dirty":
        unrelated.GetSaveFlag = lambda: True
    if change == "hidden":
        unsaved.Visible = False
    if change == "unknown":
        state.documents.append(document(tmp_path / "new-user.SLDPRT"))
    if change == "owned_path":
        copy.GetPathName = lambda: str(source)
    if change == "owned_title":
        copy.GetTitle = lambda: unsaved.GetTitle()
    with pytest.raises(RuntimeError):
        asyncio.run(owned.close())
    assert state.closes == []
    assert unsaved in state.documents


@pytest.mark.parametrize("case", ["hidden", "part", "drawing"])
def test_setup_refuses_hidden_docs_and_source_filename_collision(
    monkeypatch, tmp_path, case
):
    adapter, state, directory, part, document, activate, unrelated, _, source = setup(
        monkeypatch, tmp_path
    )
    if case == "hidden":
        unrelated.Visible = False
    if case == "part":
        activate(document(tmp_path / "other-root" / part.name))
    if case == "drawing":
        activate(document(source))
    with pytest.raises(RuntimeError, match="hidden|already open"):
        probe.ExistingSessionCopy(adapter, directory, part, source)
    assert state.closes == []


def test_exact_owned_path_cannot_close_a_colliding_native_title(monkeypatch, tmp_path):
    adapter, state, directory, part, document, activate, _, unsaved, source = setup(
        monkeypatch, tmp_path
    )
    owned = probe.ExistingSessionCopy(adapter, directory, part, source)
    path = directory / "trial.SLDDRW"
    owned.expect_open(path)
    copy = document(path)
    copy.GetTitle = lambda: unsaved.GetTitle()
    activate(copy)
    with pytest.raises(RuntimeError, match="uniquely"):
        owned.claim()
    assert state.closes == []


def observed(length):
    return {
        "key": "Drawing View1/GTol1",
        "inventory_key": "Drawing View1/GTol1",
        "views": {"front": {"scale": 3}},
        "style": 2,
        "side": 1,
        "perpendicular": False,
        "all_around": False,
        "dashed": False,
        "position": (0.2, 0.1, 0),
        "leader_points": (0.2, 0.1, 0, 0.2 - length, 0.1, 0, 0.05, 0.06, 0),
        "horizontal_length_m": length,
        "length_readback_m": length,
        "measurement": {
            "body": {"xmin": 0.2, "ymin": 0.1, "xmax": 0.21, "ymax": 0.107}
        },
    }


def test_only_native_elbow_can_move_when_length_changes():
    probe.verify_override(
        observed(probe.DOCUMENT_LENGTH_M),
        observed(probe.OVERRIDE_LENGTH_M),
        probe.DOCUMENT_LENGTH_M,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("length_readback_m", -1),
        ("length_readback_m", float("nan")),
        ("horizontal_length_m", probe.DOCUMENT_LENGTH_M),
        ("style", 1),
        ("position", (0.21, 0.1, 0)),
        ("views", {}),
        ("leader_points", (0.2, 0.1, 0, 0.19365, 0.1, 0, 0.05, 0.07, 0)),
        (
            "measurement",
            {"body": {"xmin": 0.21, "ymin": 0.1, "xmax": 0.22, "ymax": 0.107}},
        ),
    ],
)
def test_getter_rejection_or_actual_geometry_context_change_fails(field, value):
    after = {**observed(probe.OVERRIDE_LENGTH_M), field: value}
    with pytest.raises(RuntimeError):
        probe.verify_override(
            observed(probe.DOCUMENT_LENGTH_M), after, probe.DOCUMENT_LENGTH_M
        )


def test_document_policy_must_not_change():
    with pytest.raises(RuntimeError, match="document"):
        probe.verify_override(
            observed(probe.DOCUMENT_LENGTH_M),
            observed(probe.OVERRIDE_LENGTH_M),
            0.00635,
        )


def test_full_inventory_allowance_uses_native_view_key_not_sheet_qualified_key():
    target = {
        "key": "Sheet1/Drawing View1/GTol1",
        "inventory_key": "Drawing View1/GTol1",
    }
    probe.verify_layout_changes({"Drawing View1/GTol1": {}}, target)
    with pytest.raises(RuntimeError, match="other annotation"):
        probe.verify_layout_changes({"Drawing View1/GTol2": {}}, target)


def test_update_boundary_keeps_original_control_and_runs_one_checked_rebuild():
    calls = []
    model = SimpleNamespace(EditRebuild3=lambda: calls.append("rebuild") or True)
    assert probe.update_boundary(model, probe.UpdateBoundary.IMMEDIATE) == {
        "operation": "immediate"
    }
    assert calls == []
    assert probe.update_boundary(model, probe.UpdateBoundary.EDIT_REBUILD) == {
        "operation": "edit_rebuild",
        "returned": True,
    }
    assert calls == ["rebuild"]
    with pytest.raises(RuntimeError, match="rejected"):
        probe.update_boundary(
            SimpleNamespace(EditRebuild3=lambda: False),
            probe.UpdateBoundary.EDIT_REBUILD,
        )


@pytest.mark.parametrize("mutation", ["xml", "label", "entity"])
def test_existing_full_inventory_gate_rejects_content_or_attachment_replacement(
    mutation,
):
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    original, entity = object(), object()
    before = {
        "gtol": {
            "semantic": {"frames": ("<xml/>",), "texts": ("A",)},
            "generic": {},
            "position": (0, 0),
        }
    }
    after = deepcopy(before)
    handles = {"gtol": (original, entity)}
    after_handles = handles
    if mutation == "xml":
        after["gtol"]["semantic"]["frames"] = ("<changed/>",)
    if mutation == "label":
        after["gtol"]["semantic"]["texts"] = ("B",)
    if mutation == "entity":
        after_handles = {"gtol": (original, object())}
    with pytest.raises(RuntimeError, match="semantics|identity"):
        probe.shoulder.compare_all_annotation_layout(
            app, before, after, handles, after_handles
        )


def test_control_has_one_property_setter_and_no_layout_setters_or_build_runner():
    import ast
    import inspect

    source = inspect.getsource(probe)
    setters = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute) and target.attr == "BentLeaderLength"
            for target in node.targets
        )
    ]
    assert len(setters) == 1
    for forbidden in (
        ".SetLeader3(",
        ".SetPosition2(",
        "run_build(",
        ".CloseAllDocuments(",
    ):
        assert forbidden not in source
    assert "return run_owned_diagnostic(" in source


def family_extension(monkeypatch):
    monkeypatch.setattr(
        probe.shoulder,
        "_installed_swconst",
        lambda: SimpleNamespace(
            swDetailingNoOptionSpecified=0,
            swDetailingGtolUseDocBentLeaderLength=1001,
            swDetailingGtolBentLeaderLength=2001,
        ),
    )
    state = {"toggle": True, "length": 0.01}
    calls = []

    def toggle(pref, option, value):
        assert (pref, option) == (1001, 0)
        calls.append(("toggle", pref, option, value))
        state["toggle"] = value
        return value  # documented resulting-state form: false is requested OFF

    def length(pref, option, value):
        assert (pref, option) == (2001, 0)
        calls.append(("length", pref, option, value))
        state["length"] = value
        return True

    extension = SimpleNamespace(
        GetUserPreferenceDouble=lambda pref, option: state["length"],
        GetUserPreferenceToggle=lambda pref, option: state["toggle"],
        SetUserPreferenceToggle=toggle,
        SetUserPreferenceDouble=length,
    )
    return extension, state, calls


def test_family_defaults_never_write_annotation_and_use_exact_type_options(monkeypatch):
    extension, state, calls = family_extension(monkeypatch)
    result = probe.apply_length_scope(
        object(), extension, probe.LengthScope.GTOL_DEFAULT
    )
    assert calls == [("toggle", 1001, 0, False), ("length", 2001, 0, 0.00635)]
    assert state == {"toggle": False, "length": 0.00635}
    assert result["toggle_returned"] is False and result["toggle_actual"] is False
    assert result["length_returned"] is True


@pytest.mark.parametrize(
    "failure", ["toggle_ignored", "double_rejected", "double_wrong"]
)
def test_family_defaults_reject_native_getter_or_setter_failure(monkeypatch, failure):
    extension, state, calls = family_extension(monkeypatch)
    if failure == "toggle_ignored":
        extension.SetUserPreferenceToggle = lambda *args: False
    if failure == "double_rejected":
        extension.SetUserPreferenceDouble = lambda *args: False
    if failure == "double_wrong":
        extension.SetUserPreferenceDouble = lambda *args: True
    with pytest.raises(RuntimeError):
        probe.apply_length_scope(object(), extension, probe.LengthScope.GTOL_DEFAULT)


def test_document_driven_minus_one_is_scope_specific_not_geometry_waiver():
    after = {**observed(probe.OVERRIDE_LENGTH_M), "length_readback_m": -1.0}
    probe.verify_override(
        observed(probe.DOCUMENT_LENGTH_M),
        after,
        probe.DOCUMENT_LENGTH_M,
        scope=probe.LengthScope.GTOL_DEFAULT,
    )
    with pytest.raises(RuntimeError, match="scope"):
        probe.verify_override(
            observed(probe.DOCUMENT_LENGTH_M), after, probe.DOCUMENT_LENGTH_M
        )
    with pytest.raises(RuntimeError, match="horizontal"):
        probe.verify_override(
            observed(probe.DOCUMENT_LENGTH_M),
            {**after, "horizontal_length_m": 0.073},
            probe.DOCUMENT_LENGTH_M,
            scope=probe.LengthScope.GTOL_DEFAULT,
        )


def test_individual_override_never_changes_document_defaults():
    annotation = SimpleNamespace(BentLeaderLength=-1)
    probe.apply_length_scope(annotation, object(), probe.LengthScope.ANNOTATION)
    assert annotation.BentLeaderLength == 0.00635


def test_live_worker_preserves_source_hashes_even_if_cleanup_refuses(tmp_path):
    source = tmp_path / "rocker-arm.SLDPRT"
    source.write_bytes(b"original")
    report = {"source_hashes": {str(source): probe.file_digest(source)}}

    async def refuse():
        raise RuntimeError("pre-existing document state changed")

    report_path = tmp_path / "report.json"
    with pytest.raises(RuntimeError, match="pre-existing"):
        asyncio.run(probe.shoulder.finalize_probe(refuse, report, report_path))
    assert report["source_hashes"] == report["source_hashes_after"]
    assert Path(report_path).is_file()


def test_sf_scope_writes_only_sf_defaults_and_no_annotation_property(monkeypatch):
    monkeypatch.setattr(
        probe.shoulder,
        "_installed_swconst",
        lambda: SimpleNamespace(
            swDetailingNoOptionSpecified=0,
            swDetailingSFSymbolUseDocBentLeaderLength=1002,
            swDetailingSFSymbolBentLeaderLength=2002,
        ),
    )
    state = {"toggle": True, "length": probe.DOCUMENT_LENGTH_M}
    calls = []

    def toggle(pref, option, value):
        assert (pref, option) == (1002, 0)
        calls.append(("toggle", value))
        state["toggle"] = value
        return True

    def length(pref, option, value):
        assert (pref, option) == (2002, 0)
        calls.append(("length", value))
        state["length"] = value
        return True

    extension = SimpleNamespace(
        GetUserPreferenceDouble=lambda pref, option: state["length"],
        GetUserPreferenceToggle=lambda pref, option: state["toggle"],
        SetUserPreferenceToggle=toggle,
        SetUserPreferenceDouble=length,
    )
    probe.apply_length_scope(object(), extension, probe.LengthScope.SF_DEFAULT)
    assert calls == [("toggle", False), ("length", 0.00635)]
    assert state == {"toggle": False, "length": 0.00635}


def sf_observed(length):
    # Native saved rocker: SF leader starts1.75mm left of GetPosition, with
    # document length from symbol anchor to elbow. These are observed fixture
    # values only, not constants used by the production/control geometry reader.
    anchor = (0.12394376819090107, 0.19889662958647428, -0.003528249992)
    start = (0.12219376819090107, anchor[1], anchor[2])
    elbow = (anchor[0] + length, anchor[1], anchor[2])
    endpoint = (0.1239437681909011, 0.17853977139432853, anchor[2])
    return {
        **observed(length),
        "kind": 7,
        "position": anchor,
        "key": "Sheet1/Drawing View1/DetailItem350",
        "inventory_key": "Drawing View1/DetailItem350",
        "sf_properties": {"symbol": 1, "orientation": 1, "texts": ("Ra 1.6",)},
        "length_readback_m": -1.0,
        "horizontal_length_m": length + 0.00175,
        "effective_length_m": length,
        "symbol_stub_m": 0.00175,
        "leader_points": (*start, *elbow, *endpoint),
    }


def test_sf_effective_length_preserves_actual_symbol_stub_and_exact_endpoints():
    probe.verify_override(
        sf_observed(probe.DOCUMENT_LENGTH_M),
        sf_observed(0.00635),
        probe.DOCUMENT_LENGTH_M,
        scope=probe.LengthScope.SF_DEFAULT,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("symbol_stub_m", 0.002),
        ("effective_length_m", 0.073),
        ("horizontal_length_m", 0.00635),
        ("effective_length_m", float("nan")),
        ("sf_properties", {"symbol": 0, "orientation": 3, "texts": ("Ra 3.2",)}),
    ],
)
def test_sf_body_stub_or_value_change_cannot_be_hidden_by_document_getter(field, value):
    with pytest.raises(RuntimeError):
        probe.verify_override(
            sf_observed(probe.DOCUMENT_LENGTH_M),
            {**sf_observed(0.00635), field: value},
            probe.DOCUMENT_LENGTH_M,
            scope=probe.LengthScope.SF_DEFAULT,
        )


@pytest.mark.parametrize(
    "key",
    ["Sheet1/DetailItem324", "Sheet1/DetailItem325", "Drawing View1/DetailItem353"],
)
def test_sf_allowance_does_not_include_template_or_gtol_layout_changes(key):
    with pytest.raises(RuntimeError, match="other annotation"):
        probe.verify_layout_changes({key: {}}, sf_observed(0.00635))


@pytest.mark.parametrize("owner_type", [1, 2])
def test_sf_target_rejects_sheet_or_template_ownership(
    monkeypatch, tmp_path, owner_type
):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    part = tmp_path / "rocker-arm.SLDPRT"
    source = SimpleNamespace(GetPathName=lambda: str(part))
    view = SimpleNamespace(
        ReferencedDocument=source,
        Position=(0, 0),
        ScaleDecimal=1,
        GetOutline=lambda: (0, 0, 0.1, 0.1),
        ReferencedConfiguration="Default",
    )
    annotation = SimpleNamespace(
        GetType=lambda: 7, Visible=1, OwnerType=owner_type, Owner=view
    )
    specific = SimpleNamespace(GetAnnotation=lambda: annotation)
    annotation.GetSpecificAnnotation = lambda: specific
    view.GetAnnotationsByType = lambda kind: (annotation,)
    monkeypatch.setattr(probe.attachments, "views", lambda _: {"view": view})
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)), currentModel=object()
    )
    with pytest.raises(RuntimeError, match="owner roundtrip"):
        probe.capture_target(adapter, part, probe.LengthScope.SF_DEFAULT)


def test_sf_recipe_type_one_preserves_semantics_without_inapplicable_getter():
    symbol = SimpleNamespace(
        GetSymbol=lambda: 1,
        GetTextCount=lambda: 1,
        Orientation=1,
        GetAngle=lambda: 0.0,
        GetDirectionOfLay=lambda: 0,
        GetText=lambda field: "Ra 1.6" if field == 8 else "",
    )
    actual = probe.surface_finish_properties(symbol)
    assert actual == {
        "symbol": 1,
        "orientation": 1,
        "angle": 0.0,
        "lay": 0,
        "all_around": None,
        "all_around_status": "not_applicable_to_swSFJIS_Machining_Req",
        "semantic_text_fields": ("", "", "", "", "", "", "", "Ra 1.6", "", ""),
    }


@pytest.mark.parametrize("native_kind", [0, 2, 9, -1])
def test_sf_control_refuses_other_styles_with_actual_native_type(native_kind):
    symbol = SimpleNamespace(GetSymbol=lambda: native_kind)
    with pytest.raises(RuntimeError, match=f"got {native_kind}"):
        probe.surface_finish_properties(symbol)
