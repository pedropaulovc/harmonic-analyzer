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
        ".SetUserPreferenceDouble(",
        "run_build(",
        ".CloseAllDocuments(",
    ):
        assert forbidden not in source
    assert "return run_owned_diagnostic(" in source


def test_live_worker_preserves_source_hashes_even_if_cleanup_refuses(tmp_path):
    source = tmp_path / "rocker-arm.SLDPRT"
    source.write_bytes(b"original")
    report = {"source_hashes": {str(source): probe.file_digest(source)}}

    async def refuse():
        raise RuntimeError("pre-existing document state changed")

    report_path = tmp_path / "report.json"
    with pytest.raises(RuntimeError, match="pre-existing"):
        asyncio.run(
            probe.shoulder.finalize_probe(
                SimpleNamespace(close=refuse), report, report_path
            )
        )
    assert report["source_hashes"] == report["source_hashes_after"]
    assert Path(report_path).is_file()
