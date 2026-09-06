"""Shoulder controls change only native leader policy, never the datum feature."""

from types import SimpleNamespace

import pytest

from diagnostics import probe_datum_shoulder as probe


def owned_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    directory = tmp_path / "owned"
    directory.mkdir()
    source = tmp_path / "rocker-arm.SLDPRT"
    source.write_bytes(b"source")
    state = SimpleNamespace(documents=[], closes=[], active=None)
    app = SimpleNamespace(
        GetDocuments=lambda: tuple(state.documents),
        IsSame=lambda a, b: int(a is b),
        GetOpenDocumentByName=lambda path: next(
            (doc for doc in state.documents if doc.GetPathName() == path), None
        ),
        ActiveDoc=None,
    )
    adapter = SimpleNamespace(swApp=app, currentModel=None)

    async def close_model(*, save):
        state.closes.append((adapter.currentModel, save))
        state.documents.remove(adapter.currentModel)
        adapter.currentModel = app.ActiveDoc = None
        return SimpleNamespace(is_success=True, data=None)

    adapter.close_model = close_model

    def document(path):
        return SimpleNamespace(
            GetPathName=lambda: str(path.resolve()),
            GetTitle=lambda: path.name,
            GetType=lambda: 3 if path.suffix == ".SLDDRW" else 1,
        )

    def activate(doc):
        state.documents.append(doc)
        app.ActiveDoc = adapter.currentModel = doc

    return adapter, state, directory, source, document, activate


def test_cleanup_closes_only_exact_owned_copy_without_saving(monkeypatch, tmp_path):
    import asyncio

    adapter, state, directory, source, document, activate = owned_setup(
        monkeypatch, tmp_path
    )
    owned = probe.OwnedDrawingCopy(adapter, directory, source)
    path = directory / "trial.SLDDRW"
    owned.expect_open(path)
    copy = document(path)
    activate(copy)
    reference = document(source)
    state.documents.append(reference)
    owned.claim()
    asyncio.run(owned.close())
    assert state.closes == [(copy, False)]
    assert state.documents == [reference]  # never explicitly close the source


def test_owned_title_is_native_window_title_not_inferred_filename(monkeypatch, tmp_path):
    import asyncio

    adapter, state, directory, source, document, activate = owned_setup(monkeypatch, tmp_path)
    owned = probe.OwnedDrawingCopy(adapter, directory, source)
    path = directory / "trial.SLDDRW"
    owned.expect_open(path)
    copy = document(path)
    copy.GetTitle = lambda: "trial - Sheet1"
    activate(copy)
    owned.claim()
    asyncio.run(owned.close())
    assert state.closes == [(copy, False)]


@pytest.mark.parametrize("stage", ["normal", "failure"])
def test_unrelated_active_document_survives_normal_and_failed_cleanup(
    monkeypatch, tmp_path, stage
):
    import asyncio

    adapter, state, directory, source, document, activate = owned_setup(
        monkeypatch, tmp_path
    )
    owned = probe.OwnedDrawingCopy(adapter, directory, source)
    owned.expect_open(directory / "trial.SLDDRW")
    copy = document(directory / "trial.SLDDRW")
    activate(copy)
    owned.claim()
    unrelated = document(tmp_path / "user.SLDPRT")
    activate(unrelated)

    async def finish():
        try:
            if stage == "failure":
                raise ValueError("probe operation failed")
        finally:
            await owned.close()

    with pytest.raises(RuntimeError, match="unrelated|active"):
        asyncio.run(finish())
    assert state.closes == []
    assert adapter.swApp.ActiveDoc is unrelated
    assert copy in state.documents and unrelated in state.documents


def test_existing_source_or_user_document_refuses_setup_without_cleanup(
    monkeypatch, tmp_path
):
    adapter, state, directory, source, document, activate = owned_setup(
        monkeypatch, tmp_path
    )
    original = document(source)
    activate(original)
    with pytest.raises(RuntimeError, match="empty"):
        probe.OwnedDrawingCopy(adapter, directory, source)
    assert state.closes == [] and adapter.swApp.ActiveDoc is original


@pytest.mark.parametrize("wrong", ["path", "name", "identity", "hidden_other"])
def test_owned_close_refuses_wrong_path_name_native_handle_or_extra_doc(
    monkeypatch, tmp_path, wrong
):
    import asyncio

    adapter, state, directory, source, document, activate = owned_setup(
        monkeypatch, tmp_path
    )
    owned = probe.OwnedDrawingCopy(adapter, directory, source)
    path = directory / "trial.SLDDRW"
    owned.expect_open(path)
    copy = document(path)
    activate(copy)
    owned.claim()
    if wrong == "path":
        copy.GetPathName = lambda: str(tmp_path / "user.SLDDRW")
    if wrong == "name":
        copy.GetTitle = lambda: "user.SLDDRW"
    if wrong == "identity":
        adapter.swApp.ActiveDoc = document(path)
    if wrong == "hidden_other":
        state.documents.append(document(tmp_path / "hidden.SLDPRT"))
    with pytest.raises(RuntimeError):
        asyncio.run(owned.close())
    assert state.closes == []


def test_authorized_save_as_path_keeps_same_owned_identity(monkeypatch, tmp_path):
    import asyncio

    adapter, state, directory, source, document, activate = owned_setup(
        monkeypatch, tmp_path
    )
    owned = probe.OwnedDrawingCopy(adapter, directory, source)
    path = directory / "trial.SLDDRW"
    owned.expect_open(path)
    copy = document(path)
    activate(copy)
    owned.claim()
    output = directory / "after.SLDDRW"
    owned.authorize_save(output)
    copy.GetPathName, copy.GetTitle = lambda: str(output.resolve()), lambda: output.name
    asyncio.run(owned.close())
    assert state.closes == [(copy, False)]


def test_failure_cleanup_still_checks_original_hashes_and_writes_report(
    monkeypatch, tmp_path
):
    import asyncio
    import json

    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"original")
    report = {"source_hashes": {str(source): probe.file_digest(source)}}
    source.write_bytes(b"changed")

    async def refuse():
        raise RuntimeError("unrelated active document; refusing cleanup")

    path = tmp_path / "report.json"
    with pytest.raises(RuntimeError, match="changed an original"):
        asyncio.run(probe.finalize_probe(SimpleNamespace(close=refuse), report, path))
    actual = json.loads(path.read_text())
    assert "unrelated active" in actual["cleanup_error"]
    assert actual["source_hashes_after"] != actual["source_hashes"]


def test_all_manufacturing_snapshots_supply_exact_native_application():
    import ast
    import inspect

    calls = [
        node
        for node in ast.walk(ast.parse(inspect.getsource(probe.probe)))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "attachments"
        and node.func.attr == "snapshot"
    ]
    assert len(calls) == 3
    assert all(
        any(
            keyword.arg == "app"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "app"
            for keyword in call.keywords
        )
        for call in calls
    )


def test_standalone_default_runs_positive_document_route_with_explicit_part(
    monkeypatch, tmp_path
):
    import sys

    drawing, part = tmp_path / "archived-source.SLDDRW", tmp_path / "rocker-arm.SLDPRT"
    drawing.write_bytes(b"drawing")
    part.write_bytes(b"part")
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "dodo",
        SimpleNamespace(_run=lambda *args, **kwargs: calls.append((args, kwargs))),
    )
    monkeypatch.setattr(sys, "argv", ["probe", str(drawing), "--part", str(part)])
    assert probe.main() == 0
    (arguments, title), keywords = calls[0]
    assert arguments[-2:] == ["--part", str(part.resolve())]
    assert arguments[arguments.index("--mode") + 1] == "document_length"
    assert "--worker" in arguments and keywords["com"] is True


def test_native_reference_unload_does_not_make_next_copy_own_the_source(
    monkeypatch, tmp_path
):
    import asyncio

    adapter, state, directory, source, document, activate = owned_setup(
        monkeypatch, tmp_path
    )
    owned = probe.OwnedDrawingCopy(adapter, directory, source)
    copies = []
    for index in range(2):
        path = directory / f"trial{index}.SLDDRW"
        owned.expect_open(path)
        copy = document(path)
        copies.append(copy)
        activate(copy)
        reference = document(source)
        state.documents.append(reference)
        owned.claim()
        state.documents.remove(reference)
        asyncio.run(owned.close())
    assert state.closes == [(copy, False) for copy in copies]


def test_partial_open_cannot_claim_unrelated_active_document(monkeypatch, tmp_path):
    import asyncio

    adapter, state, directory, source, document, activate = owned_setup(
        monkeypatch, tmp_path
    )
    owned = probe.OwnedDrawingCopy(adapter, directory, source)
    owned.expect_open(directory / "trial.SLDDRW")
    unrelated = document(tmp_path / "user.SLDPRT")
    state.documents.append(unrelated)
    adapter.swApp.ActiveDoc = unrelated
    with pytest.raises(RuntimeError, match="unclaimed active"):
        asyncio.run(owned.close())
    assert state.closes == [] and adapter.swApp.ActiveDoc is unrelated


def test_cleanup_refusal_preserves_source_hash_witness_in_report(tmp_path):
    import asyncio
    import json

    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"original")
    report = {"source_hashes": {str(source): probe.file_digest(source)}}

    async def refuse():
        raise RuntimeError("unrelated active document; refusing cleanup")

    path = tmp_path / "report.json"
    with pytest.raises(RuntimeError, match="unrelated active"):
        asyncio.run(probe.finalize_probe(SimpleNamespace(close=refuse), report, path))
    actual = json.loads(path.read_text())
    assert actual["source_hashes_after"] == actual["source_hashes"]


def test_diagnostic_never_calls_close_all_documents():
    import inspect

    assert "CloseAllDocuments" not in inspect.getsource(probe)


def row():
    return {
        "label": "B",
        "owner_type": 0,
        "visible": 1,
        "dangling": False,
        "attachment_types": (2,),
        "null_attachments": (False,),
        "geometry": ("face",),
        "configuration": "Default",
        "style": 1,
        "label_render": ("B",),
        "shoulder": False,
        "forced_shoulder": False,
        "frame_relation": {"frame": (0.1, 0.2, 0.107, 0.207)},
    }


@pytest.mark.parametrize("policy", tuple(probe.ShoulderPolicy))
def test_explicit_shoulder_policy_has_exact_readback(policy):
    tag = SimpleNamespace(Shoulder=False, ForcedShoulder=False)
    result = probe.set_shoulder(tag, policy)
    assert result["actual"] is (policy is probe.ShoulderPolicy.BENT)


def test_rejected_native_shoulder_policy_fails_loud():
    class RejectedTag:
        ForcedShoulder = False

        @property
        def Shoulder(self):
            return False

        @Shoulder.setter
        def Shoulder(self, _value):
            pass

    with pytest.raises(RuntimeError, match="rejected requested policy"):
        probe.set_shoulder(RejectedTag(), probe.ShoulderPolicy.BENT)


@pytest.mark.parametrize(
    "field,value",
    [
        ("shoulder", True),
        ("forced_shoulder", True),
        ("style", 2),
        ("attachment_types", (1,)),
        ("null_attachments", (True,)),
    ],
)
def test_control_must_start_with_exact_nonforced_straight_face(field, value):
    with pytest.raises(RuntimeError):
        probe.find_target({"datum": {**row(), field: value}})


def test_shoulder_property_change_is_not_a_semantic_feature_change():
    before = row()
    probe.same_target(
        before,
        {
            **before,
            "shoulder": True,
            "frame_relation": {"frame": (0.2, 0.3, 0.207, 0.307)},
        },
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("geometry", ("other face",)),
        ("label", "A"),
        ("label_render", ("C",)),
        ("style", 2),
        ("frame_relation", {"frame": (0.1, 0.2, 0.108, 0.207)}),
    ],
)
def test_geometry_label_or_frame_mutation_is_not_accepted(field, value):
    with pytest.raises(RuntimeError):
        probe.same_target(row(), {**row(), field: value})


def bent_record():
    return {
        "position": (0.29875, 0.1683376494921567, 0),
        "frame_relation": {
            "frame": (0.3051, 0.1648376494921567, 0.3121, 0.1718376494921567)
        },
        "measurement": {
            "body": {
                "xmin": 0.3051,
                "ymin": 0.1648376494921567,
                "xmax": 0.3121,
                "ymax": 0.1718376494921567,
            }
        },
        "view_outline": (0.290883750008, 0.15274964949, 0.309116249992, 0.19322028962),
        "generic": {
            "lines": [
                (
                    0,
                    0,
                    0,
                    0,
                    0.29875,
                    0.1683376494921567,
                    0,
                    0.3051,
                    0.1683376494921567,
                    0,
                )
            ]
        },
    }


def test_length_target_comes_from_native_segment_and_actual_view_deficit():
    result = probe.bent_length_target(bent_record())
    assert result["native_measured_m"] == pytest.approx(0.00635)
    assert result["deficit_m"] == pytest.approx(0.007016249992)
    assert result["requested_m"] == pytest.approx(0.013366249992)


@pytest.mark.parametrize("lines", [[], [(0,) * 10, (0,) * 10]])
def test_length_control_requires_actual_unique_elbow_frame_segment(lines):
    record = bent_record()
    record["generic"]["lines"] = lines
    with pytest.raises(RuntimeError, match="not unique"):
        probe.bent_length_target(record)


def test_minus_one_length_is_recorded_not_a_fallback_or_feature_verdict():
    native = {
        "variant": "native_bent",
        "length": {
            "initial_readback_m": -1,
            "after_readback_m": -1,
            "reopened_readback_m": -1,
        },
        "styled": bent_record(),
        "after": bent_record(),
    }
    probe.verify_length_change(native)
    candidate = {
        **native,
        "variant": "extended_bent",
        "length": {**native["length"], "requested_m": 0.013},
    }
    with pytest.raises(RuntimeError, match="did not retain requested value"):
        probe.verify_length_change(candidate)


def test_document_length_uses_document_extension_and_exact_installed_enum(monkeypatch):
    monkeypatch.setattr(
        probe,
        "_installed_swconst",
        lambda: SimpleNamespace(
            swDetailingAnnotationBentLeaderLength=113,
            swDetailingNoOptionSpecified=0,
        ),
    )
    state = {"value": 0.00635}
    calls = []

    def setter(preference, option, value):
        calls.append((preference, option, value))
        state["value"] = value
        return True

    extension = SimpleNamespace(
        GetUserPreferenceDouble=lambda preference, option: state["value"],
        SetUserPreferenceDouble=setter,
    )
    result = probe.set_document_length(extension, 0.01336625)
    assert calls == [(113, 0, 0.01336625)]
    assert result == {
        "before_m": 0.00635,
        "returned": True,
        "requested_m": 0.01336625,
        "after_m": 0.01336625,
    }


def test_document_property_rejection_is_not_hidden_by_the_length_getter():
    with pytest.raises(RuntimeError, match="setter rejected"):
        probe.verify_document_length({"document_length": {"returned": False}})


def test_global_control_reports_intended_body_movement_without_waiving_semantics():
    initial = {
        "semantic": {"texts": ("A",)},
        "generic": {"lines": ((0, 0),)},
        "position": (0, 0),
    }
    actual = {**initial, "generic": {"lines": ((1, 0),)}, "position": (1, 0)}
    changes = probe.compare_all_annotation_layout(
        None, {"datum": initial}, {"datum": actual}
    )
    assert changes["datum"]["position_after"] == (1, 0)
    with pytest.raises(RuntimeError, match="semantics"):
        probe.compare_all_annotation_layout(
            None,
            {"datum": initial},
            {"datum": {**actual, "semantic": {"texts": ("B",)}}},
        )


def test_global_control_requires_same_exact_native_handles():
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    row = {"semantic": {}, "generic": {}, "position": (0, 0)}
    with pytest.raises(RuntimeError, match="identity changed"):
        probe.compare_all_annotation_layout(
            app, {"a": row}, {"a": row}, {"a": (object(),)}, {"a": (object(),)}
        )


def test_global_control_keeps_missing_measurement_exclusions_explicit():
    row = {
        "semantic": {},
        "generic": {},
        "position": (0, 0),
        "measurement_exclusion": "unsupported font",
    }
    assert not probe.compare_all_annotation_layout(None, {"a": row}, {"a": row})
    with pytest.raises(RuntimeError, match="bounds support"):
        probe.compare_all_annotation_layout(
            None, {"a": row}, {"a": {**row, "measurement_exclusion": "missing body"}}
        )
