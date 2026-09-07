"""Diagnostic SaveAs3 routing; these doubles establish no native persistence."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_common as common
from diagnostics import _native_drawing_save_control as control


@pytest.fixture
def scene(monkeypatch, tmp_path):
    events, records = [], []

    class Model:
        path = ""

        def GetPathName(self):
            return self.path

        def GetType(self):
            return 3

        def SaveAs3(self, path, version, options):
            events.append(("legacy", Path(path).suffix, version, options))
            Path(path).write_bytes(b"legacy export")
            return 0

    model = Model()

    def modern(path, *args):
        events.append(("modern", args))
        Path(path).write_bytes(b"native drawing")
        model.path = path
        return True, 0, 2

    model.Extension = SimpleNamespace(SaveAs3=modern)
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(ActiveDoc=model)
    )

    class Ownership:
        def assert_current_owned(self):
            assert adapter.currentModel is model
            if adapter.swApp.ActiveDoc is not model:
                raise RuntimeError(
                    "native write requires the exact owned active document"
                )
            events.append("owned")

        @contextmanager
        def saving_as(self, path):
            assert Path(path).parent == tmp_path
            events.append("scope.enter")
            try:
                yield
            finally:
                events.append("scope.exit")

    adapter.ownership = Ownership()

    def bind(value, interface):
        events.append(("bind", interface))
        return value

    monkeypatch.setattr(control, "_early_bound", bind)
    return SimpleNamespace(
        adapter=adapter,
        model=model,
        events=events,
        records=records,
        native=tmp_path / "owned.SLDDRW",
        pdf=tmp_path / "owned.pdf",
        png=tmp_path / "owned.png",
    )


def test_legacy_is_exact_noop_even_on_exception(scene):
    original = common.save_drawing
    with pytest.raises(ValueError, match="caller"):
        with control.native_drawing_save_control(
            scene.adapter, control.DrawingSave.LEGACY, records=scene.records
        ):
            assert common.save_drawing is original
            raise ValueError("caller")
    assert common.save_drawing is original
    assert scene.events == scene.records == []


def test_only_drawing_uses_typed_modern_call_with_context_order(scene):
    original = common.save_drawing
    for path in (scene.native, scene.pdf, scene.png):
        path.write_bytes(b"stale")

    @contextmanager
    def context(kind, path):
        scene.events.append(("context.enter", kind))
        assert Path(path).read_bytes() == b"stale"
        yield
        scene.events.append(("context.exit", kind))

    with control.native_drawing_save_control(
        scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
    ):
        result = common.save_drawing(
            scene.adapter,
            str(scene.native),
            pdf_path=str(scene.pdf),
            png_path=str(scene.png),
            artifact_context=context,
        )
    assert common.save_drawing is original
    assert result == dict(
        drawing=str(scene.native), pdf=str(scene.pdf), png=str(scene.png)
    )
    important = [
        item for item in scene.events if isinstance(item, tuple) and item[0] != "bind"
    ]
    assert important == [
        ("context.enter", "drawing"),
        ("modern", (0, 1, None, None, 0, 0)),
        ("context.exit", "drawing"),
        ("context.enter", "pdf"),
        ("legacy", ".pdf", 0, 0),
        ("context.exit", "pdf"),
        ("context.enter", "png"),
        ("legacy", ".png", 0, 0),
        ("context.exit", "png"),
    ]
    row = scene.records[0]
    assert row["status"] == "passed"
    assert row["returned"] == (True, 0, 2)
    assert row["warnings"] == 2
    assert row["errors"] == 0
    assert row["native_path_after"] == str(scene.native)
    assert row["native_file"]["bytes"] == len(b"native drawing")
    assert row["seconds"] >= 0
    assert ("bind", "IModelDocExtension") in scene.events
    assert (
        scene.events.index(("context.enter", "drawing"))
        < scene.events.index("scope.enter")
        < scene.events.index(("modern", (0, 1, None, None, 0, 0)))
        < scene.events.index("scope.exit")
        < scene.events.index(("context.exit", "drawing"))
        < scene.events.index(("context.enter", "pdf"))
    )
    assert scene.events.count("scope.enter") == scene.events.count("scope.exit") == 1


def test_real_owned_inventory_reconciles_native_rename_before_pdf(scene, monkeypatch):
    from diagnostics import _owned_native_documents as owned

    monkeypatch.setattr(owned, "_early_bound", lambda value, _: value)
    app = scene.adapter.swApp
    app.documents = []
    app.ActiveDoc = scene.adapter.currentModel = None
    app.GetDocuments = lambda: tuple(app.documents)
    app.IsSame = lambda first, second: int(first is second)
    app.GetOpenDocumentByName = lambda path: next(
        (model for model in app.documents if model.GetPathName() == path), None
    )
    model = scene.model
    model.Visible = True
    model.GetSaveFlag = lambda: not bool(model.path)
    model.GetTitle = lambda: (
        f"{Path(model.path).stem} - Sheet1" if model.path else "Unsaved drawing"
    )
    model.GetViews = lambda: ((object(),),)
    adapter = owned.DiagnosticAdapter(scene.adapter)
    adapter.ownership.register_directory(scene.native.parent)
    boundaries = []

    @contextmanager
    def artifact(kind, path):
        # Match the source observer's checkpoint at entry and exit. Its own
        # observations must see a fully reconciled authorized rename.
        adapter.ownership.checkpoint()
        boundaries.append(("before", kind, adapter.ownership.current.state["path"]))
        yield
        adapter.ownership.assert_current_owned()
        adapter.ownership.checkpoint()
        boundaries.append(("after", kind, adapter.ownership.current.state["path"]))

    with adapter.ownership.creating_document(owned.DocumentKind.DRAWING, scene.native):
        app.documents.append(model)
        app.ActiveDoc = model
        adapter.currentModel = model
        with control.native_drawing_save_control(
            adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
        ):
            result = common.save_drawing(
                adapter,
                str(scene.native),
                pdf_path=str(scene.pdf),
                png_path=str(scene.png),
                artifact_context=artifact,
            )

    expected = str(scene.native)
    assert boundaries == [
        ("before", "drawing", ""),
        ("after", "drawing", expected),
        ("before", "pdf", expected),
        ("after", "pdf", expected),
        ("before", "png", expected),
        ("after", "png", expected),
    ]
    assert result == {"drawing": expected, "pdf": str(scene.pdf), "png": str(scene.png)}
    assert adapter.ownership.current.state["title"] == f"{scene.native.stem} - Sheet1"
    assert scene.records[0]["status"] == "passed"
    assert adapter.ownership.assert_current_owned().handle is model


@pytest.mark.parametrize(
    "returned",
    [
        (False, 0, 0),
        (True, 8, 0),
        True,
        (True, 0),
        (1, 0, 0),
        (True, False, 0),
        (True, 0, 0.0),
    ],
)
def test_failed_or_malformed_native_tuple_stops_exports_and_retains_output(
    scene, returned
):
    def save(path, *args):
        scene.native.write_bytes(b"partial native output")
        scene.model.path = path
        return returned

    scene.model.Extension.SaveAs3 = save
    original = common.save_drawing
    with pytest.raises(RuntimeError):
        with control.native_drawing_save_control(
            scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
        ):
            common.save_drawing(
                scene.adapter, str(scene.native), pdf_path=str(scene.pdf)
            )
    assert common.save_drawing is original
    assert scene.native.read_bytes() == b"partial native output"
    assert not scene.pdf.exists()
    assert scene.records[0]["returned"] == returned
    assert scene.records[0]["status"] == "failed"
    assert scene.records[0]["native_file"]["bytes"] > 0


@pytest.mark.parametrize("output", ["absent", "empty", "wrong_path"])
def test_success_cannot_accept_stale_empty_or_wrong_path_native_file(scene, output):
    scene.native.write_bytes(b"stale")

    def save(path, *args):
        assert not scene.native.exists()
        scene.model.path = str(scene.pdf) if output == "wrong_path" else path
        if output != "absent":
            scene.native.write_bytes(b"" if output == "empty" else b"new")
        return True, 0, 0

    scene.model.Extension.SaveAs3 = save
    with pytest.raises(RuntimeError):
        with control.native_drawing_save_control(
            scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
        ):
            common.save_drawing(
                scene.adapter, str(scene.native), pdf_path=str(scene.pdf)
            )
    assert not scene.pdf.exists()
    assert scene.records[0]["status"] == "failed"


def test_native_exception_reaches_artifact_context_and_is_retained(scene):
    failure = RuntimeError("native call failed")
    seen = []

    def save(*args):
        raise failure

    @contextmanager
    def context(*args):
        try:
            yield
        except Exception as error:
            seen.append(error)
            raise

    scene.model.Extension.SaveAs3 = save
    original = common.save_drawing
    with pytest.raises(RuntimeError, match="native call failed") as caught:
        with control.native_drawing_save_control(
            scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
        ):
            common.save_drawing(
                scene.adapter, str(scene.native), artifact_context=context
            )
    assert caught.value is failure
    assert seen == [failure]
    assert common.save_drawing is original
    assert scene.records[0]["status"] == "failed"
    assert "native call failed" in scene.records[0]["failures"][0]


@pytest.mark.parametrize(
    "bad", ["part", "adapter", "extension", "foreign_output", "alias"]
)
def test_refuses_outside_drawing_control_before_deleting_files(scene, bad):
    scene.native.write_bytes(b"preserve")
    adapter, native, pdf = scene.adapter, scene.native, scene.pdf
    if bad == "part":
        scene.model.GetType = lambda: 1
    if bad == "adapter":
        adapter = object()
    if bad == "extension":
        native = scene.native.with_suffix(".SLDPRT")
    if bad == "foreign_output":
        pdf = scene.pdf.parent.parent / "unowned.pdf"
    if bad == "alias":
        pdf = scene.native
    with pytest.raises((RuntimeError, ValueError)):
        with control.native_drawing_save_control(
            scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
        ):
            common.save_drawing(adapter, str(native), pdf_path=str(pdf))
    assert scene.native.read_bytes() == b"preserve"
    assert not any(
        isinstance(row, tuple) and row[0] in {"modern", "legacy"}
        for row in scene.events
    )


def test_native_failure_and_ownership_exit_failure_both_survive(scene):
    native_failure = RuntimeError("native rejection")
    cleanup_failure = RuntimeError("ownership checkpoint rejection")

    def save(*args):
        raise native_failure

    @contextmanager
    def scope(path):
        try:
            yield
        finally:
            raise cleanup_failure

    scene.model.Extension.SaveAs3 = save
    scene.adapter.ownership.saving_as = scope
    original = common.save_drawing
    with pytest.raises(ExceptionGroup) as caught:
        with control.native_drawing_save_control(
            scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
        ):
            common.save_drawing(scene.adapter, str(scene.native))
    assert caught.value.exceptions == (native_failure, cleanup_failure)
    assert common.save_drawing is original
    assert scene.records[0]["failures"] == [repr(native_failure), repr(cleanup_failure)]


def test_failed_pdf_does_not_retry_native_or_attempt_png(scene):
    def legacy(path, *args):
        scene.events.append(("pdf.failed", args))
        assert Path(path) == scene.pdf
        assert not scene.pdf.exists()

    scene.model.SaveAs3 = legacy
    scene.pdf.write_bytes(b"stale")
    with pytest.raises(RuntimeError, match="produced no file"):
        with control.native_drawing_save_control(
            scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
        ):
            common.save_drawing(
                scene.adapter,
                str(scene.native),
                pdf_path=str(scene.pdf),
                png_path=str(scene.png),
            )
    assert (
        len(
            [
                row
                for row in scene.events
                if isinstance(row, tuple) and row[0] == "modern"
            ]
        )
        == 1
    )
    assert not scene.png.exists()
    assert scene.records[0]["returned"] == (True, 0, 2)
    assert scene.records[0]["status"] == "failed"


def test_saving_as_guard_rejects_before_any_stale_file_removal(scene):
    scene.native.write_bytes(b"protected")

    @contextmanager
    def denied(path):
        raise RuntimeError("not registered")
        yield  # pragma: no cover - contextmanager contract

    scene.adapter.ownership.saving_as = denied
    with pytest.raises(RuntimeError, match="not registered"):
        with control.native_drawing_save_control(
            scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
        ):
            common.save_drawing(scene.adapter, str(scene.native))
    assert scene.native.read_bytes() == b"protected"
    assert scene.records[0]["status"] == "failed"


@pytest.mark.parametrize("changed_at", ["drawing", "pdf", "png"])
def test_artifact_context_active_doc_change_refuses_before_delete_or_save(
    scene, changed_at
):
    paths = {"drawing": scene.native, "pdf": scene.pdf, "png": scene.png}
    for path in paths.values():
        path.write_bytes(b"retained stale artifact")

    @contextmanager
    def context(kind, path):
        if kind == changed_at:
            # The source observer/checkpoint runs after the outer SaveAs guard.
            # Its activation must not be mistaken for owned currentModel state.
            scene.adapter.swApp.ActiveDoc = object()
            assert scene.adapter.currentModel is scene.model
        yield

    original = common.save_drawing
    with pytest.raises(RuntimeError, match="exact owned active document"):
        with control.native_drawing_save_control(
            scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
        ):
            common.save_drawing(
                scene.adapter,
                str(scene.native),
                pdf_path=str(scene.pdf),
                png_path=str(scene.png),
                artifact_context=context,
            )
    assert common.save_drawing is original
    assert scene.records[0]["status"] == "failed"
    changed_index = tuple(paths).index(changed_at)
    for kind in tuple(paths)[changed_index:]:
        assert paths[kind].read_bytes() == b"retained stale artifact"
    actual_saves = [
        row
        for row in scene.events
        if isinstance(row, tuple) and row[0] in {"modern", "legacy"}
    ]
    assert len(actual_saves) == changed_index


def test_unknown_variant_does_not_replace_alias(scene):
    original = common.save_drawing
    with pytest.raises(ValueError, match="explicit DrawingSave"):
        with control.native_drawing_save_control(
            scene.adapter, "extension_silent", records=scene.records
        ):
            pytest.fail("must not enter")
    assert common.save_drawing is original
    assert scene.events == []


def test_context_composes_with_source_observer_without_losing_artifact_spans(
    scene, monkeypatch
):
    @contextmanager
    def caller_context(kind, path):
        scene.events.append(("caller.before", kind))
        yield
        scene.events.append(("caller.after", kind))

    @contextmanager
    def observer():
        selected_save = common.save_drawing

        def observe(adapter, *args, artifact_context=None, **kwargs):
            @contextmanager
            def combined(kind, path):
                with artifact_context(kind, path):
                    scene.events.append(("source.before", kind))
                    try:
                        yield
                    finally:
                        scene.events.append(("source.after", kind))

            return selected_save(adapter, *args, artifact_context=combined, **kwargs)

        with monkeypatch.context() as local:
            local.setattr(common, "save_drawing", observe)
            yield

    original = common.save_drawing
    with control.native_drawing_save_control(
        scene.adapter, control.DrawingSave.EXTENSION_SILENT, records=scene.records
    ):
        with observer():
            common.save_drawing(
                scene.adapter,
                str(scene.native),
                pdf_path=str(scene.pdf),
                artifact_context=caller_context,
            )
    assert common.save_drawing is original
    events = [
        row for row in scene.events if isinstance(row, tuple) and row[0] != "bind"
    ]
    assert events == [
        ("caller.before", "drawing"),
        ("source.before", "drawing"),
        ("modern", (0, 1, None, None, 0, 0)),
        ("source.after", "drawing"),
        ("caller.after", "drawing"),
        ("caller.before", "pdf"),
        ("source.before", "pdf"),
        ("legacy", ".pdf", 0, 0),
        ("source.after", "pdf"),
        ("caller.after", "pdf"),
    ]


def test_actual_generated_extension_abi_has_dispatch_null_and_tuple_out_slots():
    # No importing/constructing the COM wrapper: pin the exact makepy contract
    # which makes None and 0 the correct Python arguments, not VARIANT wrappers.
    import ast
    import solidworks_mcp

    path = Path(solidworks_mcp.__file__).parent / "adapters/_generated/sldworks_2026.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    extension = next(
        row
        for row in module.body
        if isinstance(row, ast.ClassDef) and row.name == "IModelDocExtension"
    )
    method = next(
        row
        for row in extension.body
        if isinstance(row, ast.FunctionDef) and row.name == "SaveAs3"
    )
    call = next(
        row
        for row in ast.walk(method)
        if isinstance(row, ast.Call)
        and isinstance(row.func, ast.Attribute)
        and row.func.attr == "_ApplyTypes_"
    )
    assert [ast.literal_eval(row) for row in call.args[:4]] == [
        315,
        1,
        (11, 0),
        ((8, 1), (3, 1), (3, 1), (9, 1), (9, 1), (16387, 3), (16387, 3)),
    ]
