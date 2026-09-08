"""Viewport observations cannot authorize content changes or hide restoration errors."""

import asyncio
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _populated_extent_viewport as extent
from diagnostics import probe_populated_template as probe


@pytest.fixture
def scene(tmp_path, monkeypatch):
    calls, faults = [], {}

    class View:
        scale = 1.0
        translation = [0.1, 0.2, 0.0]

        @property
        def Scale2(self):
            return self.scale

        @Scale2.setter
        def Scale2(self, value):
            calls.append(("scale", value))
            if faults.get("clamp") and value == 2:
                return
            self.scale = value
            self.translation = [0.9, 0.8, 0.0]

        @property
        def Translation3(self):
            return SimpleNamespace(ArrayData=self.translation)

        @Translation3.setter
        def Translation3(self, value):
            calls.append(("translation", self.scale))
            if faults.get("restore") and self.scale == 1:
                raise faults["restore"]
            self.translation = list(value.ArrayData)

        @property
        def Orientation3(self):
            return SimpleNamespace(ArrayData=[1.0] * 16)

        @property
        def Transform(self):
            return SimpleNamespace(ArrayData=[self.scale] * 13 + self.translation)

        def GetVisibleBox(self):
            return (0, 0, 1200, 800)

    view = View()
    model = SimpleNamespace(
        ActiveView=view,
        Visible=True,
        GetType=lambda: 3,
        GraphicsRedraw2=lambda: calls.append(("redraw", view.scale)),
    )
    app = SimpleNamespace(
        ActiveDoc=model,
        IsSame=lambda a, b: int(a is b),
        GetMathUtility=lambda: SimpleNamespace(
            CreateVector=lambda values: SimpleNamespace(ArrayData=tuple(values))
        ),
    )
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=app,
        ownership=SimpleNamespace(
            assert_current_owned=Mock(), register_directory=Mock()
        ),
    )
    marker = object()

    def snapshot(current, state):
        assert current is adapter
        calls.append(("snapshot", view.scale))
        text = (
            "changed"
            if faults.get("text") and view.scale == 2
            else "full required value"
        )
        position = [0.1, 0.2, 0.0]
        if faults.get("anchor") and view.scale == 2:
            position[1] += 1e-12
        return (
            {
                "notes": {
                    "material": {
                        "text": text,
                        "font": {
                            "height": 0.004
                            if faults.get("font") and view.scale == 2
                            else 0.0035
                        },
                        "position": position,
                        "display": {"texts": [{"position": position, "text": text}]},
                        "extent": [0.0, 0.0, 0.0, view.scale * 0.01, 0.0035, 0.0],
                    }
                },
                "preferences": {"sheet_scale": [1, 2]},
                "views": [{"scale": 0.1}],
                "template_geometry": [
                    "changed"
                    if faults.get("geometry") and view.scale == 2
                    else "unchanged"
                ],
            },
            {
                "model": model,
                "note": object()
                if faults.get("identity") and view.scale == 2
                else marker,
            },
        )

    def printed(*_args):
        calls.append(("pdf", view.scale))
        if "primary" in faults:
            raise faults["primary"]
        return {"pixels": "same", "glyphs": "same"}

    def compare(a, b):
        if faults.get("pdf") and view.scale == 2:
            raise RuntimeError("independent PDF glyph drift")
        assert a == b
        return {"changed_pixel_count": 0}

    monkeypatch.setattr(extent, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(extent.viewport, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(extent.viewport, "double_array", lambda value: value)
    monkeypatch.setattr(extent, "snapshot", snapshot)
    monkeypatch.setattr(
        extent,
        "screen_basis",
        lambda *_: [[0, 0, 0], [view.scale, 0, 0], [0, -view.scale, 0]],
    )
    monkeypatch.setattr(extent.prepared, "printed_snapshot", printed)
    monkeypatch.setattr(extent.prepared, "compare_appearance", compare)
    monkeypatch.setattr(extent.prepared, "compare_vectors", lambda a, b: None)
    record, checkpoints = {}, []

    def checkpoint():
        checkpoints.append(deepcopy(record))
        if "checkpoint" in faults:
            raise faults["checkpoint"]

    def run(state=extent.State.POPULATED):
        return extent.observe(adapter, state, tmp_path / "arms", record, checkpoint)

    return SimpleNamespace(**locals())


@pytest.mark.parametrize("state", list(extent.State))
def test_actual_aba_allows_only_zoom_extent_changes_and_restores_original_pan(
    scene, state
):
    initial = extent.viewport.capture(scene.model)
    scene.run(state)
    assert [row["viewport"]["scale2"] for row in scene.record["arms"]] == [
        1.0,
        2.0,
        1.0,
    ]
    assert scene.record["arms"][0]["native"] == scene.record["arms"][2]["native"]
    assert scene.record["arms"][1]["native"] != scene.record["initial"]
    assert extent.viewport.capture(scene.model) == initial
    assert scene.record["restoration"]["status"] == "passed"
    assert scene.record["status"] == "observed"
    assert len([call for call in scene.calls if call[0] == "pdf"]) == 3
    assert "no material-fit acceptance" in scene.record["scope"]


@pytest.mark.parametrize(
    "fault,message",
    [
        ("text", "changed non-extent drawing state"),
        ("anchor", "changed non-extent drawing state"),
        ("font", "changed non-extent drawing state"),
        ("geometry", "changed non-extent drawing state"),
        ("identity", "native drawing/view/note/source identity changed"),
        ("pdf", "independent PDF glyph drift"),
        ("clamp", "native viewport scale assignment did not persist"),
    ],
)
def test_rejected_b_arm_restores_and_retains_actionable_failure(scene, fault, message):
    initial = extent.viewport.capture(scene.model)
    scene.faults[fault] = "injected"
    with pytest.raises(RuntimeError, match=message):
        scene.run()
    assert extent.viewport.capture(scene.model) == initial
    assert scene.record["restoration"]["status"] == "passed"
    assert scene.record["status"] == "failed"
    if fault == "clamp":
        rejected = scene.calls.index(("scale", 2.0))
        assert scene.calls[rejected + 1] == ("scale", 1.0)


@pytest.mark.parametrize(
    "primary",
    [RuntimeError("original PDF failure"), KeyboardInterrupt("original interruption")],
)
def test_primary_and_distinct_restore_failure_keep_exact_exception_objects(
    scene, primary
):
    secondary = RuntimeError("restore rejected")
    scene.faults.update(primary=primary, restore=secondary)
    with pytest.raises(
        BaseExceptionGroup, match="viewport observation and restoration failures"
    ) as raised:
        scene.run()
    assert raised.value.exceptions == (primary, secondary)
    assert scene.record["restoration"]["status"] == "failed"
    assert scene.record["errors"] == [repr(primary), repr(secondary)]
    assert ("scale", 1.0) in scene.calls


def test_same_exception_object_is_not_duplicated_when_restore_repeats_it(scene):
    primary = RuntimeError("same underlying failure")
    scene.faults.update(primary=primary, restore=primary)
    with pytest.raises(RuntimeError, match="same underlying failure") as raised:
        scene.run()
    assert raised.value is primary
    assert scene.record["errors"] == [repr(primary)]
    assert any(
        "recurred during viewport restoration" in note for note in primary.__notes__
    )


def test_checkpoint_failure_still_attempts_restore_and_keeps_original_error(scene):
    primary = OSError("checkpoint unavailable")
    scene.faults["checkpoint"] = primary
    with pytest.raises(OSError, match="checkpoint unavailable") as raised:
        scene.run()
    assert raised.value is primary
    assert scene.record["restoration"]["status"] == "passed"
    assert scene.record["errors"] == [repr(primary)]
    assert len(scene.checkpoints) == 2


def test_replaced_native_viewport_is_not_written_during_failed_restoration(
    scene, monkeypatch
):
    def replace_view(*_args):
        scene.model.ActiveView = scene.View()
        return {"pixels": "same"}

    monkeypatch.setattr(extent.prepared, "printed_snapshot", replace_view)
    with pytest.raises(
        ExceptionGroup, match="viewport observation and restoration failures"
    ) as raised:
        scene.run()
    assert len(raised.value.exceptions) == 2
    assert all(type(error) is RuntimeError for error in raised.value.exceptions)
    assert all(
        str(error) == "viewport control exact owned drawing/viewport handle changed"
        for error in raised.value.exceptions
    )
    assert not any(call[0] == "scale" for call in scene.calls)
    assert scene.record["status"] == "failed"
    assert scene.record["restoration"]["status"] == "failed"


def test_actual_snapshot_keeps_exact_drawing_transform_and_surface_finish_handles(
    monkeypatch,
):
    owner, note = object(), object()
    source = SimpleNamespace(GetPathName=lambda: "C:/retained/tube.SLDPRT")
    view = SimpleNamespace(
        GetName2=lambda: "Front",
        Position=[0.1, 0.2],
        ScaleDecimal=0.1,
        ModelToViewTransform=SimpleNamespace(ArrayData=[1.0] * 16),
        ReferencedConfiguration="Default",
        ReferencedDocument=source,
    )
    finish = SimpleNamespace(GetName=lambda: "SF", GetType=lambda: 7)
    sheet_view = SimpleNamespace(GetAnnotations=lambda: [finish])
    model = SimpleNamespace(GetViews=lambda: ((sheet_view, view),))
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=app,
        ownership=SimpleNamespace(assert_current_owned=Mock()),
    )
    monkeypatch.setattr(extent, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(
        extent.layout,
        "note_inventory",
        lambda _: (
            {"N": {"extent": [0.0] * 6, "text": "same"}},
            {"N": (note, owner)},
            ["same SF geometry"],
        ),
    )
    monkeypatch.setattr(
        extent.layout.cells, "template_lines", lambda _: ([], {"frame": "same"})
    )
    monkeypatch.setattr(probe, "preferences", lambda _: {"sheet_scale": [1, 2]})
    before, bank = extent.snapshot(adapter, extent.State.POPULATED)
    assert before["views"][0]["model_to_view_transform"] == [1.0] * 16
    assert bank["surface_finish:SF"] is finish
    assert bank["source:0"] is source
    view.ModelToViewTransform.ArrayData[0] += 1e-12
    after, _ = extent.snapshot(adapter, extent.State.POPULATED)
    assert extent.semantics(before) != extent.semantics(after)
    replacement = SimpleNamespace(GetName=lambda: "SF", GetType=lambda: 7)
    sheet_view.GetAnnotations = lambda: [replacement]
    _, replaced_bank = extent.snapshot(adapter, extent.State.POPULATED)
    with pytest.raises(
        RuntimeError, match="native drawing/view/note/source identity changed"
    ):
        extent.require_identity(app, bank, replaced_bank)
    with pytest.raises(RuntimeError, match="wrong exact blank/populated view count"):
        extent.snapshot(adapter, extent.State.BLANK)


@pytest.mark.parametrize("fault", ["none", "create_null", "transform_null"])
def test_actual_screen_basis_uses_native_point_transform_without_setter(
    monkeypatch, fault
):
    inputs = []
    transform = object()

    def create(values):
        inputs.append(tuple(values))
        if fault == "create_null":
            return None

        def multiply(actual):
            assert actual is transform
            if fault == "transform_null":
                return None
            return SimpleNamespace(ArrayData=[value * 1000 for value in values])

        return SimpleNamespace(MultiplyTransform=multiply)

    app = SimpleNamespace(GetMathUtility=lambda: SimpleNamespace(CreatePoint=create))
    view = SimpleNamespace(Transform=transform)
    monkeypatch.setattr(extent, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(extent, "double_array", lambda value: value)
    if fault == "none":
        assert extent.screen_basis(app, view) == [
            [0.0, 0.0, 0.0],
            [1000.0, 0.0, 0.0],
            [0.0, 1000.0, 0.0],
        ]
        assert inputs == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        return
    name = "CreatePoint" if fault == "create_null" else "MultiplyTransform"
    with pytest.raises(RuntimeError, match=f"{name} returned null"):
        extent.screen_basis(app, view)


@pytest.fixture
def receipts(tmp_path, monkeypatch):
    import _drawing_sheet_setup as setup

    root = tmp_path / "retained"
    root.mkdir()
    template, source = root / "derived.DRWDOT", root / "tube-copy.SLDPRT"
    original = tmp_path / "templates" / "harmonic-analyzer.DRWDOT"
    original.parent.mkdir()
    template.write_bytes(b"derived")
    source.write_bytes(b"tube retained exact copy")
    original.write_bytes(b"original")

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    monkeypatch.setattr(setup, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(extent, "DERIVED_SHA256", sha(template))
    targets = dict(extent.sources.TARGETS)
    targets["tube_frame"] = replace(targets["tube_frame"], source_sha256=sha(source))
    monkeypatch.setattr(extent.sources, "TARGETS", targets)
    # Deliberately nonexistent producer and token: the validator must never read them.
    inputs = {
        str(original): sha(original),
        str(template): sha(template),
        str(tmp_path / "missing-producer.SLDPRT"): sha(source),
        str(tmp_path / ".missing-producer.execution"): "a" * 64,
    }
    tube = {
        "target": "tube_frame",
        "status": "observed",
        "source_copy": str(source),
        "copy_hashes": {"initial": sha(source), "final": sha(source)},
        "explicit_source_manifest": {"sha256": sha(source)},
        "view_scale": [1.0, 10.0],
        "cold_delta": {"changed_leaf_count": 0},
        "cold_export_delta": {"changed_leaf_count": 0},
        "png_delta": {"changed_pixel_count": 0},
        "printed": {"classification": "unchanged"},
        "linked_fields": {"built": {"notes": {}}, "cold": {"notes": {}}},
        "source_before": {"dimensions": "same"},
        "source_after": {"dimensions": "same"},
        "source_reopened": {"dimensions": "same"},
        "source_after_cold_pdf": {"dimensions": "same"},
        "acceptance_issues": [{"kind": "native_fit", "error": "known overrun"}],
    }
    report = {
        "revision": extent.RETAINED_REVISION,
        "population": "material-finish",
        "status": "failed",
        "inputs_before": inputs,
        "inputs_after": deepcopy(inputs),
        "targets": list(targets),
        "trials": [{"target": "rocker_arm"}, {"target": "channel_lever"}, tube],
        "setups": {"tube_frame": {"normalized_blank_defaults": {"original": "blank"}}},
    }
    owner = {
        "cleanup_error": None,
        "baseline_initial": [],
        "final_inventory": [],
        "source_hashes": {
            path: {"before": digest, "after": digest, "unchanged": True}
            for path, digest in inputs.items()
        },
    }
    blank = {
        "revision": extent.RETAINED_REVISION,
        "status": "passed",
        "layout_policy": "material-finish",
        "derived_template": str(template),
        "derived_sha256": sha(template),
        "inputs_before": {},
        "inputs_after": {},
    }
    paths = [
        root / "populated-template.json",
        root / "ownership.json",
        root / "template-layout.json",
    ]

    def args():
        for path, value in zip(paths, (report, owner, blank), strict=True):
            path.write_text(json.dumps(value), encoding="utf-8")
        return (template, sha(template), paths[0], *(sha(path) for path in paths))

    return SimpleNamespace(**locals())


def test_retained_copy_proof_does_not_read_or_protect_missing_producer_tokens(receipts):
    result = extent.read_inputs(*receipts.args())
    assert result["source"] == str(receipts.source)
    assert len(result["expected"]) == 4
    assert not any("missing-producer" in path for path in result["expected"])
    assert result["original_issues"] == receipts.tube["acceptance_issues"]


def test_actual_derived_template_bytes_must_match_pin_before_native_calls(receipts):
    args = receipts.args()
    receipts.template.write_bytes(b"different DRWDOT bytes")
    with pytest.raises(RuntimeError, match="derived template SHA256 differs"):
        extent.read_inputs(*args)


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "copy_hash",
        "cold",
        "source_geometry",
        "owner",
        "blank",
        "template",
        "running",
        "target",
        "missing",
    ],
)
def test_retained_copy_proof_rejects_incomplete_or_wrong_native_evidence(
    receipts, fault
):
    if fault == "source":
        receipts.source.write_bytes(b"changed")
    if fault == "copy_hash":
        receipts.tube["copy_hashes"]["final"] = "0" * 64
    if fault == "cold":
        receipts.tube["linked_fields"]["cold"]["notes"] = {"other": "changed"}
    if fault == "source_geometry":
        receipts.tube["source_reopened"]["dimensions"] = "changed"
    if fault == "owner":
        receipts.owner["cleanup_error"] = "failed close"
    if fault == "blank":
        receipts.blank["status"] = "failed"
    if fault == "template":
        receipts.blank["derived_sha256"] = "0" * 64
    if fault == "running":
        receipts.report["status"] = "running"
    if fault == "target":
        receipts.tube["target"] = "rocker_arm"
    if fault == "missing":
        del receipts.tube["source_after"]
    with pytest.raises(RuntimeError, match="retained"):
        extent.read_inputs(*receipts.args())


def test_wrong_receipt_sha_stops_cli_before_any_owned_seat_launch(
    receipts, monkeypatch
):
    import dodo

    args = receipts.args()
    for key, value in {
        "HARMONIC_SW_AUTOSTART": "0",
        "HARMONIC_REMOTE_CACHE_MODE": "off",
        "HARMONIC_DIAGNOSTIC_SW_PID": "123",
    }.items():
        monkeypatch.setenv(key, value)
    launch = Mock()
    monkeypatch.setattr(dodo, "_run", launch)
    with pytest.raises(RuntimeError, match="SHA256 differs"):
        probe.main(
            [
                "--template",
                str(args[0]),
                "--template-sha256",
                args[1],
                "--population",
                "tube-extent-viewport",
                "--symbol-library",
                str(args[0]),
                "--retained-population",
                str(args[2]),
                "--retained-population-sha256",
                "0" * 64,
                "--retained-ownership-sha256",
                args[4],
                "--retained-blank-sha256",
                args[5],
            ]
        )
    launch.assert_not_called()


@pytest.mark.parametrize("fault", ["none", "interrupt"])
def test_actual_single_tube_composition_uses_retained_copy_and_keeps_fit_observations(
    receipts, monkeypatch, fault
):
    args = receipts.args()
    monkeypatch.setattr(probe.title.pilot, "helper_fingerprints", lambda: {})
    monkeypatch.setattr(probe.title.pilot, "adapter_fingerprints", lambda: {})
    monkeypatch.setattr(probe.title.pilot.benchmark, "revision", lambda _: "candidate")
    monkeypatch.setattr(extent.prepared, "runtime_inputs", lambda *_: {})
    monkeypatch.setattr(
        extent.sources,
        "require_sources",
        Mock(side_effect=AssertionError("producer tokens touched")),
    )
    monkeypatch.setattr(
        probe.title.pilot,
        "require_sources",
        Mock(side_effect=AssertionError("old pilot pins touched")),
    )
    symbol = receipts.tmp_path / "gtol.sym"
    symbol.write_bytes(b"symbols")
    monkeypatch.setattr(
        probe.symbols, "symbol_library", lambda _: {"sha256": receipts.sha(symbol)}
    )
    calls = []
    primary, secondary = (
        KeyboardInterrupt("owned viewport interrupted"),
        OSError("owned close failed"),
    )

    def observe(adapter, state, directory, record, checkpoint):
        calls.append(state)
        if fault == "interrupt":
            raise primary
        record.update(status="observed", restoration={"status": "passed"})

    def factory(self, adapter, **kwargs):
        self.setup["normalized_blank_defaults"] = deepcopy(
            self.evidence["original_blank"]
        )
        calls.append("normal factory")
        return adapter.currentModel

    def output(self, adapter, phase, trial, pdf):
        trial.setdefault("linked_fields", {})[phase] = deepcopy(
            self.evidence["original_loaded"]
        )
        trial["linked_fields"][phase]["fit"] = {
            "issues": deepcopy(receipts.tube["acceptance_issues"])
        }

    monkeypatch.setattr(extent, "observe", observe)
    monkeypatch.setattr(probe.PopulatedControl, "factory", factory)
    monkeypatch.setattr(probe.PopulatedControl, "observe", output)
    monkeypatch.setattr(extent.prepared, "semantic_defaults", deepcopy)
    loaded = receipts.tube["linked_fields"]["built"]
    for key in (
        "surface_finishes",
        "template_geometry",
        "preferences",
        "expected_link_values",
    ):
        loaded[key] = {}
    receipts.tube["linked_fields"]["cold"] = deepcopy(loaded)
    args = receipts.args()

    async def one_trial(
        adapter, variant, source, directory, report, checkpoint, inputs, **kwargs
    ):
        assert source == receipts.source
        assert kwargs["source_target"] == "tube_frame"
        assert kwargs["source_manifest"] is extent.sources.TARGETS["tube_frame"]
        assert kwargs["view_scale"] == (1.0, 10.0)
        assert not any("missing-producer" in path for path in inputs)
        trial = {
            "cold_delta": {"changed_leaf_count": 0},
            "printed": {"classification": "unchanged"},
            "png_delta": {"changed_pixel_count": 0},
        }
        report["trials"].append(trial)
        kwargs["factory"](adapter, scale=(1.0, 2.0))
        for phase in ("built", "cold"):
            kwargs["observe_output"](adapter, phase, trial, directory / "test.pdf")
        return trial

    async def close():
        if fault == "interrupt":
            raise secondary

    monkeypatch.setattr(probe.title, "one_trial", one_trial)
    adapter = SimpleNamespace(
        currentModel=object(),
        ownership=SimpleNamespace(register_directory=Mock(), register_source=Mock()),
        close_owned_documents=close,
    )
    output_root = receipts.tmp_path / "output"

    def run():
        return asyncio.run(
            probe.probe(
                adapter,
                args[0],
                args[1],
                None,
                output_root,
                symbol,
                population=probe.Population.TUBE_EXTENT_VIEWPORT,
                retained_receipts=args[2:],
            )
        )

    if fault == "interrupt":
        with pytest.raises(
            BaseExceptionGroup, match="populated template control failed"
        ) as raised:
            run()
        assert raised.value.exceptions == (primary, secondary)
    if fault == "none":
        result = run()
        assert result["outcome"] == "tube_viewport_observed_not_fit_accepted"
        assert calls == ["normal factory", extent.State.BLANK, extent.State.POPULATED]
    (report_path,) = output_root.glob("*/populated-template.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["targets"] == ["tube_frame"]
    assert report["status"] == ("failed" if fault == "interrupt" else "observed")
    if fault == "interrupt":
        assert report["errors"] == [repr(primary), repr(secondary)]
    if fault == "none":
        assert len(report["trials"][0]["acceptance_issues"]) == 2
        assert all(
            issue["kind"] == "native_fit"
            for issue in report["trials"][0]["acceptance_issues"]
        )


@pytest.mark.parametrize("fault", ["none", "coordinate", "transform", "font"])
def test_actual_geometry_reader_and_super_observer_cross_json_boundary_without_hiding_drift(
    tmp_path, monkeypatch, fault
):
    from test_populated_template_drawing import populated

    notes, _, _ = populated()
    notes["title"]["text"] = "tube-frame"
    notes["material"]["horizontal"] = 1
    notes["material"]["vertical"] = 1
    for name in ("title", "dwg", "rev"):
        notes[name]["horizontal"] = 1
    notes["dwg"]["font"]["CharHeight"] = notes["rev"]["font"]["CharHeight"] = 0.0035
    source_path = tmp_path / "tube-copy.SLDPRT"
    source = SimpleNamespace(
        GetPathName=lambda: str(source_path),
        GetType=lambda: 1,
        SummaryInfo=lambda _: "tube-frame",
        GetCustomInfoValue=lambda _, key: {
            "Number": "MHA-071",
            "Revision": "v32",
            "Material": "Steel",
            "Finish": "Plain",
        }[key],
    )
    matrix = (
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    )
    inverse = SimpleNamespace(ArrayData=matrix)
    transform = SimpleNamespace(ArrayData=matrix, Inverse=lambda: inverse)
    start, end = (
        SimpleNamespace(X=0.1, Y=0.2, Z=0.0),
        SimpleNamespace(X=0.2, Y=0.2, Z=0.0),
    )
    line = SimpleNamespace(
        GetType=lambda: 0,
        GetID=lambda: (1, 0),
        ConstructionGeometry=False,
        GetStartPoint2=lambda: start,
        GetEndPoint2=lambda: end,
    )
    sketch = SimpleNamespace(
        ModelToSketchTransform=transform, GetSketchSegments=lambda: (line,)
    )
    sheet = SimpleNamespace(GetTemplateSketch=lambda: sketch)

    def create_point(values):
        xyz = tuple(values.value)

        def multiply(actual):
            assert actual is inverse
            return SimpleNamespace(ArrayData=xyz)

        return SimpleNamespace(MultiplyTransform=multiply)

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            GetCurrentSheet=lambda: sheet, GetCustomInfoValue=lambda *_: ""
        ),
        swApp=SimpleNamespace(
            GetOpenDocumentByName=lambda _: source,
            GetMathUtility=lambda: SimpleNamespace(CreatePoint=create_point),
        ),
    )
    # Keep the real template_lines reader and real superclass observer. Only
    # the COM-facing interfaces and independent PDF/ownership seams are faked.
    monkeypatch.setattr(probe.layout.cells, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(
        probe.layout, "note_inventory", lambda _: (deepcopy(notes), {}, [])
    )
    preferences = {"sheet_properties": [2, 12, 1, 2, 0, 0.4318, 0.2794, 0]}
    monkeypatch.setattr(probe, "preferences", lambda _: deepcopy(preferences))
    monkeypatch.setattr(
        probe, "property_source", lambda *_: {"identity": "exact_native_source"}
    )
    known = {"kind": "native_fit", "field": "material", "error": "retained overrun"}
    monkeypatch.setattr(
        probe.fields,
        "field_audit",
        lambda *_args, **_kwargs: {"fields": {}, "issues": [deepcopy(known)]},
    )
    baseline = probe.PopulatedControl(
        tmp_path / "derived.DRWDOT",
        "0" * 64,
        Mock(),
        {},
        population=probe.Population.MATERIAL_FINISH,
    )
    baseline.setup["normalized_blank_defaults"] = deepcopy(preferences)
    baseline.setup["normalized_blank_defaults"]["sheet_properties"][7] = 1
    before_trial = {
        "source_copy": str(source_path),
        "source_before": {"configuration": "Default"},
    }
    baseline.observe(adapter, "built", before_trial, tmp_path / "prior.pdf")
    live = before_trial["linked_fields"]["built"]
    assert isinstance(live["template_geometry"]["model_to_sketch"], tuple)
    assert isinstance(
        live["template_geometry"]["segments"][0]["sheet_points"][0], tuple
    )
    archived = json.loads(json.dumps(live))
    assert isinstance(archived["template_geometry"]["model_to_sketch"], list)
    control = probe.TubeViewportControl(
        tmp_path / "derived.DRWDOT",
        "0" * 64,
        Mock(),
        {},
        tmp_path,
        {"original_loaded": archived},
    )
    control.setup["normalized_blank_defaults"] = deepcopy(
        baseline.setup["normalized_blank_defaults"]
    )
    observation = Mock()
    monkeypatch.setattr(extent, "observe", observation)
    if fault == "coordinate":
        end.X += 1e-12
    if fault == "transform":
        transform.ArrayData = (matrix[0] + 1e-12, *matrix[1:])
    if fault == "font":
        notes["material"]["font"]["CharHeight"] += 1e-12
    trial = {
        "source_copy": str(source_path),
        "source_before": {"configuration": "Default"},
    }
    if fault != "none":
        field = "notes" if fault == "font" else "template_geometry"
        with pytest.raises(
            RuntimeError, match=f"retained tube loaded non-extent {field} differ"
        ):
            control.observe(adapter, "built", trial, tmp_path / "fresh.pdf")
        observation.assert_not_called()
        return
    control.observe(adapter, "built", trial, tmp_path / "fresh.pdf")
    observation.assert_called_once()
    assert observation.call_args.args[1] is extent.State.POPULATED
    assert trial["linked_fields"]["built"]["fit"]["issues"] == [known]
    assert trial["linked_fields"]["built"]["fit"]["status"] == "failed"
