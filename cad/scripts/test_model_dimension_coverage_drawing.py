"""Declared dimension-only coverage must prove native identity, not a row count."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _recipe_acceptance_targets as targets
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics import probe_drawing_attachments as attachments
from test_probe_drawing_attachments import (
    Annotation,
    Model,
    View,
    dimension,
    display_dimension,
)


def test_only_fillister_declares_exact_model_dimension_coverage():
    from diagnostics._model_dimension_coverage import SemanticCoverage

    assert len(targets.TARGETS) == 17
    for name, manifest in targets.TARGETS.items():
        expected = SemanticCoverage.GEOMETRY
        if name == "fillister_screw":
            expected = SemanticCoverage.MODEL_DIMENSIONS_ONLY
        assert manifest.coverage is expected
    rows = targets.TARGETS["fillister_screw"].model_dimensions
    assert {
        (row.feature, row.name, row.orientation, row.display_type, row.attachments)
        for row in rows
    } == {
        ("HeadProfile", "HeadDia", "*Back", 6, (10,)),
        ("ShankProfile", "ShankDia", "*Right", 6, (10,)),
        ("Head", "HeadHt", "*Right", 2, ()),
        ("Shank", "ShankLg", "*Right", 2, ()),
    }


@pytest.fixture
def context(monkeypatch, tmp_path):
    from diagnostics import _model_dimension_coverage as coverage

    for module in (coverage, attachments, pilot):
        monkeypatch.setattr(module, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(coverage.source_reads, "_early_bound", lambda value, _: value)
    path = tmp_path / "owned.SLDPRT"
    path.write_bytes(b"immutable source")
    manifest = targets.TARGETS["fillister_screw"]

    def scene():
        parameters, source_displays, annotations = {}, {}, {}
        for index, role in enumerate(manifest.model_dimensions):
            key = f"{role.name}@{role.feature}"
            parameter = dimension(
                role.name, f"{key}@{path.stem}.Part", (index + 1) / 1000, 4
            )
            parameter.GetToleranceType = lambda: 4
            parameter.Tolerance.GetMinValue = lambda: -0.0001
            parameter.Tolerance.GetMaxValue = lambda: 0.0001
            parameters[key] = parameter
            texts = {str(i): "" for i in range(1, 9)}
            if role.name == "ShankDia":
                texts["1"] = texts["5"] = "#4-40 UNC-2A"
            if role.name == "ShankLg":
                texts["4"] = texts["8"] = "UNDERHEAD LENGTH"

            def display():
                item = display_dimension(parameter, kind=role.display_type)
                item.text = dict(texts)
                item.ShowDimensionValue = role.name != "ShankDia"
                item.IsHoleCallout = lambda: False
                item.GetText = lambda index, item=item: item.text[str(index)]
                item.GetPrimaryPrecision2 = lambda: 2
                item.GetPrimaryTolPrecision2 = lambda: 1
                return item

            source_displays[key] = display()
            item = Annotation(
                role.name,
                entities=tuple(object() for _ in role.attachments),
                kinds=role.attachments,
            )
            item.display = display()
            item.display.GetAnnotation = lambda item=item: item
            item.OwnerType, item.Visible = 0, 1
            item.GetAttachedEntityCount3 = lambda item=item: len(item.entities)
            annotations[key] = item
        source = NS(
            GetPathName=lambda: str(path),
            GetType=lambda: 1,
            GetSaveFlag=lambda: False,
            Parameter=lambda key: parameters[key],
            ConfigurationManager=NS(ActiveConfiguration=NS(Name="Default")),
        )

        class NativeView(View):
            @property
            def ReferencedDocument(self):
                return self.native_source

        views = []
        for index, orientation in enumerate(("*Right", "*Back", "*Isometric"), 1):
            items = [
                annotations[f"{r.name}@{r.feature}"]
                for r in manifest.model_dimensions
                if r.orientation == orientation
            ]
            view = NativeView(f"Drawing View{index}", path, items)
            view.native_source = source
            view.GetOrientationName = lambda orientation=orientation: orientation
            for item in items:
                item.Owner = view
            views.append(view)
        model = Model(views)
        model.GetType, model.GetSaveFlag = lambda: 3, lambda: True
        return source, model, parameters, source_displays, annotations

    source, model, parameters, source_displays, annotations = scene()
    app = NS(IsSame=lambda a, b: int(a is b), ActiveDoc=source)
    app.GetOpenDocumentByName = lambda value: (
        current.source if Path(value) == path else None
    )
    adapter = NS(
        swApp=app, currentModel=source, ownership=NS(assert_current_owned=Mock())
    )
    current = NS(
        source=source,
        model=model,
        parameters=parameters,
        source_displays=source_displays,
        annotations=annotations,
    )

    def named(reader, feature, name):
        assert reader.currentModel is current.source
        key = f"{name}@{feature}"
        return current.source_displays[key], current.parameters[key]

    monkeypatch.setattr(coverage, "_named_dimension", named)
    trial = {}
    control = coverage.ModelDimensionCoverage(adapter, manifest, source, path, trial)
    adapter.currentModel = app.ActiveDoc = model

    def reopen():
        (
            current.source,
            current.model,
            current.parameters,
            current.source_displays,
            current.annotations,
        ) = scene()
        adapter.currentModel = app.ActiveDoc = current.model

    def rebind(new_path):
        nonlocal path
        path = new_path
        reopen()
        adapter.currentModel = app.ActiveDoc = current.source

    def printed():
        return {
            f"{a.Owner.GetName2()}/{a.name}": {
                "generic": {
                    "texts": [
                        {"value": line}
                        for line in next(
                            r.printed
                            for r in manifest.model_dimensions
                            if r.name == a.name
                        )
                    ]
                }
            }
            for a in current.annotations.values()
        }

    return NS(
        coverage=coverage,
        control=control,
        adapter=adapter,
        app=app,
        current=current,
        path=path,
        manifest=manifest,
        trial=trial,
        reopen=reopen,
        rebind=rebind,
        printed=printed,
        named=named,
    )


def capture(c):
    semantics, bank = c.control.capture(
        c.adapter, source=c.path, configuration="Default"
    )
    c.control.require_printed(c.printed(), bank)
    return semantics, bank


def test_real_generic_inventory_keeps_exclusions_but_declared_bank_is_complete(context):
    c = context
    semantics, before = capture(c)
    assert semantics["checked"] == {}
    assert len(semantics["dimensions"]) == len(before["dimensions"]) == 4
    assert {tuple(row["kinds"]) for row in semantics["excluded"].values()} == {
        (),
        (10,),
    }
    assert before["source"] == c.trial["model_dimension_source_before"]
    c.reopen()
    _, after = capture(c)
    assert after == before
    assert (
        c.control.live_handles == {}
    )  # No pre-close handles consulted on cold capture.


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "active",
        "owner",
        "parameter",
        "roundtrip",
        "reference",
        "hidden",
        "dangling",
        "orientation",
        "missing",
        "extra",
        "geometry",
        "null_sketch",
        "kind",
        "count",
        "source_value",
        "source_tolerance",
        "source_text",
        "numeric",
        "text",
        "malformed_bool",
    ],
)
def test_declared_bank_rejects_wrong_or_incomplete_native_witness(context, change):
    c = context
    a = c.current.annotations["ShankDia@ShankProfile"]
    if change == "source":
        a.Owner.native_source = NS(GetPathName=lambda: str(c.path))
    if change == "active":
        c.app.ActiveDoc = object()
    if change == "owner":
        a.Owner = object()
    if change == "parameter":
        a.display.GetDimension2 = lambda _: deepcopy(
            c.current.parameters["ShankDia@ShankProfile"]
        )
    if change == "roundtrip":
        a.display.GetAnnotation = lambda: object()
    if change == "reference":
        a.display.IsReferenceDim = lambda: True
    if change == "hidden":
        a.Visible = 3
    if change == "dangling":
        a.state = "dangling"
    if change == "orientation":
        a.Owner.GetOrientationName = lambda: "*Front"
    if change == "missing":
        a.Owner.annotations.remove(a)
    if change == "extra":
        a.Owner.annotations.append(a)
    if change == "geometry":
        a.Owner.annotations.append(Annotation("UnexpectedGTol", kind=5))
    if change == "null_sketch":
        a.entities = (None,)
    if change == "kind":
        a.kinds = (11,)
    if change == "count":
        a.GetAttachedEntityCount3 = lambda: 2
    if change == "source_value":
        c.current.parameters["HeadHt@Head"].GetSystemValue3.return_value = (
            0.003000000000000001,
        )
    if change == "source_tolerance":
        c.current.parameters["HeadHt@Head"].Tolerance.GetMaxValue = lambda: (
            0.000100000000001
        )
    if change == "source_text":
        c.current.source_displays["HeadHt@Head"].text["2"] = "changed"
    if change == "numeric":
        a.display.ShowDimensionValue = True
    if change == "text":
        a.display.text["6"] = "changed"
    if change == "malformed_bool":
        a.display.ShowDimensionValue = 0
    with pytest.raises((RuntimeError, ValueError)):
        capture(c)


def test_reopened_parameter_checks_use_only_fresh_handles(context):
    c = context
    _, before = capture(c)
    old_source, old_parameters = c.current.source, tuple(c.current.parameters.values())
    c.reopen()
    old_same = c.app.IsSame

    def same(a, b):
        assert all(
            a is not old and b is not old for old in (old_source, *old_parameters)
        )
        return old_same(a, b)

    c.app.IsSame = same
    _, after = capture(c)
    assert after == before


@pytest.mark.parametrize("change", ["value", "precision", "text", "missing_print"])
def test_cold_and_printed_comparisons_are_exact(context, change):
    c = context
    _, before = capture(c)
    c.reopen()
    item = c.current.annotations["ShankDia@ShankProfile"]
    if change == "value":
        c.current.parameters["ShankDia@ShankProfile"].GetSystemValue3.return_value = (
            0.002000000000000001,
        )
    if change == "precision":
        item.display.GetPrimaryPrecision2 = lambda: 3
    if change == "text":
        item.display.text["1"] = "wrong"
    if change == "missing_print":
        c.printed = lambda: {}
    with pytest.raises(RuntimeError):
        _, after = capture(c)
        c.coverage.compare({"model_dimensions": before}, {"model_dimensions": after})


def test_manifest_cannot_hide_required_geometry_roles(context):
    c = context
    for manifest in (
        replace(c.manifest, entity_labels={"missing": "face"}),
        replace(c.manifest, model_dimensions=c.manifest.model_dimensions[:-1]),
    ):
        with pytest.raises(ValueError):
            c.coverage.ModelDimensionCoverage(
                c.adapter, manifest, c.current.source, c.path, {}
            )


def test_default_checked_empty_contract_remains_rejected(context):
    with pytest.raises(pilot.DrawingSemanticCoverageError, match="checked_empty"):
        pilot._drawing_semantics(
            context.adapter, source=context.path, configuration="Default"
        )


@pytest.mark.parametrize(
    "failure", ["read_dirty", "primary_and_dirty", "active_after_read"]
)
def test_failed_reads_retain_dirty_banks_and_do_not_mask_primary(context, failure):
    c = context
    original = c.current.annotations["HeadHt@Head"].display.GetDimension2

    def reading(index):
        if failure == "active_after_read":
            c.app.ActiveDoc = object()
        else:
            c.current.source.GetSaveFlag = lambda: True
        if failure == "primary_and_dirty":
            raise RuntimeError("original parameter reader failed")
        return original(index)

    c.current.annotations["HeadHt@Head"].display.GetDimension2 = reading
    with pytest.raises(RuntimeError) as caught:
        capture(c)
    row = c.trial["model_dimension_coverage"]["captures"][-1]
    assert row["source_dirty_before"] is False
    assert row["source_dirty_after"] is (failure != "active_after_read")
    assert row["drawing_dirty_before"] is row["drawing_dirty_after"] is True
    assert "guard_error" in row
    if failure == "primary_and_dirty":
        assert str(caught.value) == "original parameter reader failed"
        assert row["error"] == repr(caught.value)


def test_source_initial_failure_preserves_its_dirty_exit_evidence(context, monkeypatch):
    c = context
    c.adapter.currentModel = c.app.ActiveDoc = c.current.source

    def failing(*_):
        c.current.source.GetSaveFlag = lambda: True
        raise RuntimeError("original initial reader failed")

    monkeypatch.setattr(c.coverage, "_named_dimension", failing)
    trial = {}
    with pytest.raises(RuntimeError, match="original initial reader failed"):
        c.coverage.ModelDimensionCoverage(
            c.adapter, c.manifest, c.current.source, c.path, trial
        )
    row = trial["model_dimension_coverage"]["initial_source_read"]
    assert row["dirty_before"] is False and row["dirty_after"] is True
    assert "original initial reader failed" in row["error"]
    assert "dirty state" in row["guard_error"]


@pytest.mark.parametrize("kind", [2, 5, 7, 13, 15, 6])
def test_dimension_only_policy_cannot_hide_an_extra_annotation_role(context, kind):
    c = context
    extra = Annotation("Unexpected", kind=kind)
    extra.GetAttachedEntityCount3 = lambda: 1
    c.current.model.drawing_views[0].annotations.append(extra)
    with pytest.raises(RuntimeError, match="unexpected.*role"):
        capture(c)


@pytest.mark.parametrize(
    "values",
    [
        [" #4-40 UNC-2A "],
        ["#4-40 UNC-2A", "2.00"],
        ["#4-40 UNC-2A", "#4-40 UNC-2A"],
        ["#4-40  UNC-2A"],
    ],
)
def test_native_padded_printed_run_is_retained_without_numeric_or_text_waiver(
    context, values
):
    c = context
    _, bank = c.control.capture(c.adapter, source=c.path, configuration="Default")
    records = c.printed()
    records["Drawing View1/ShankDia"]["generic"]["texts"] = [
        {"value": value} for value in values
    ]
    if values == [" #4-40 UNC-2A "]:
        c.control.require_printed(records, bank)
        assert (
            bank["dimensions"]["ShankDia@ShankProfile"]["native_text_values"] == values
        )
    else:
        with pytest.raises(RuntimeError, match="printed"):
            c.control.require_printed(records, bank)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["normal", "wrong_parameter", "cold_raw_drift", "build_failure"]
)
async def test_actual_pilot_composes_declared_bank_and_fresh_cold_readers(
    context, monkeypatch, tmp_path, mode
):
    from contextlib import nullcontext
    import json
    import _drawing_build
    from diagnostics import probe_source_basic_dimensions as source_probe
    from test_benchmark_drawing_recipes import recipe

    c = context
    source_root = tmp_path / "protected"
    source_root.mkdir()
    originals = {}
    for target in (*pilot.ORDER, "fillister_screw"):
        path = source_root / (target.replace("_", "-") + ".SLDPRT")
        path.write_bytes(target.encode())
        originals[path] = path.read_bytes()
        monkeypatch.setitem(
            pilot.EXPECTED_PART_HASHES, target, attachments.file_digest(path)
        )
    monkeypatch.setattr(
        pilot.benchmark, "recipe_source", lambda *_: recipe(Path("unread.SLDPRT"))
    )
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "frozen"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"adapter": "frozen"})
    monkeypatch.setattr(source_probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(source_probe, "_named_dimension", c.named)
    monkeypatch.setattr(_drawing_build.sheet_setup, "new_project_drawing", Mock())
    c.adapter.ownership.register_directory = Mock()
    c.adapter.ownership.register_source = Mock()
    c.adapter.ownership.creating_document = lambda *_: nullcontext()
    opened, closed = [], []

    def printed(adapter):
        assert adapter is c.adapter
        records = c.printed()
        return records, {key: object() for key in records}

    monkeypatch.setattr(pilot.shoulder, "all_annotation_layout", printed)
    monkeypatch.setattr(pilot, "retain_failed_drawing", Mock())

    async def close():
        closed.append(c.adapter.currentModel)
        c.adapter.currentModel = c.app.ActiveDoc = None

    async def opening(path):
        opened.append(Path(path))
        if Path(path).suffix == ".SLDPRT":
            c.rebind(Path(path))
        else:
            c.reopen()
            if mode == "cold_raw_drift":
                c.current.parameters["HeadHt@Head"].Tolerance.GetMaxValue = lambda: (
                    0.000100000000001
                )
        return NS(is_success=True, data={})

    async def draw(outputs, source):
        assert c.adapter.currentModel is c.current.source
        if mode == "build_failure":
            raise RuntimeError("unchanged production gate failed")
        c.adapter.currentModel = c.app.ActiveDoc = c.current.model
        if mode == "wrong_parameter":
            item = c.current.annotations["HeadHt@Head"]
            item.display.GetDimension2 = lambda _: deepcopy(
                c.current.parameters["HeadHt@Head"]
            )
        artifacts = {"drawing": outputs.slddrw, "pdf": outputs.pdf, "png": outputs.png}
        for path in artifacts.values():
            path.write_bytes(b"fixture output")
        return {kind: str(path) for kind, path in artifacts.items()}

    c.adapter.close_owned_documents = close
    c.adapter.open_model = opening
    c.adapter.draw = draw
    reports = tmp_path / "reports"
    if mode == "normal":
        await pilot.pilot(
            c.adapter,
            "frozen",
            source_root,
            source_root,
            reports,
            targets=("fillister_screw",),
        )
    else:
        with pytest.raises(
            RuntimeError,
            match="imported source parameter|raw source bank|production gate",
        ):
            await pilot.pilot(
                c.adapter,
                "frozen",
                source_root,
                source_root,
                reports,
                targets=("fillister_screw",),
            )
    (receipt,) = reports.glob("*/pilot.json")
    report = json.loads(receipt.read_text())
    trial = report["trials"][0]
    assert all(path.read_bytes() == data for path, data in originals.items())
    assert report["sources_before"] == report["sources_after"]
    assert report["runtime_final_guard_errors"] == []
    assert all(path not in originals for path in opened)
    if mode == "normal":
        assert trial["built"]["semantics"]["checked"] == {}
        assert (
            trial["built"]["model_dimensions"] == trial["reopened"]["model_dimensions"]
        )
        assert len(trial["model_dimension_coverage"]["captures"]) == 2
        assert trial["status"] == "passed" and c.adapter.currentModel is None
        assert len(opened) == 2 and len(closed) == 3
    if mode == "cold_raw_drift":
        assert trial["status"] == "failed" and "built" in trial
        assert "raw source bank changed" in trial["error"]
