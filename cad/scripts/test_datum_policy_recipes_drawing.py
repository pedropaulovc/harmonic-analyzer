"""Functional pilot reuses unchanged recipes and scoped native ownership."""

from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_datum_policy_recipes as probe
from diagnostics import _owned_native_documents as owned
from test_benchmark_drawing_recipes import recipe
from test_owned_native_documents_drawing import Model, native  # noqa: F401


def fixture_sources(tmp_path, monkeypatch):
    source_root, guard_root = tmp_path / "sources", tmp_path / "guards"
    source_root.mkdir()
    guard_root.mkdir()
    hashes = {}
    for target in probe.ORDER:
        name = target.replace("_", "-") + ".SLDPRT"
        for directory in (source_root, guard_root):
            (directory / name).write_bytes(target.encode())
        hashes[target] = probe.attachments.file_digest(source_root / name)
    monkeypatch.setattr(probe, "EXPECTED_PART_HASHES", hashes)
    return source_root, guard_root


class Adapter:
    def __init__(self, mode):
        self.mode, self.drawn, self.opened = mode, [], []
        self.currentModel = object()
        self.swApp = SimpleNamespace(
            IsSame=lambda a, b: int(a is b), GetOpenDocumentByName=lambda path: path
        )
        self.ownership = SimpleNamespace(
            register_directory=Mock(),
            register_source=Mock(),
            assert_current_owned=Mock(),
            creating_document=Mock(side_effect=lambda *_: nullcontext()),
        )

    async def close_owned_documents(self):
        self.currentModel = None

    async def open_model(self, path):
        self.opened.append(path)
        self.currentModel = path
        return SimpleNamespace(is_success=True, data={})

    async def draw(self, outputs, source):
        self.drawn.append((outputs, source))
        if self.mode == "build_failure":
            raise RuntimeError("real recipe gate failed")
        if self.mode == "source_drift":
            source.write_bytes(b"changed")
        artifacts = {"drawing": outputs.slddrw, "pdf": outputs.pdf, "png": outputs.png}
        for path in artifacts.values():
            path.write_bytes(b"native output")
        self.currentModel = str(outputs.slddrw)
        return {kind: str(path) for kind, path in artifacts.items()}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["normal", "build_failure", "source_drift", "reopen_drift", "adapter_drift"]
)
async def test_one_fresh_recipe_each_in_order_and_stop_first_failure(
    tmp_path, monkeypatch, mode
):
    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(
        probe.benchmark,
        "recipe_source",
        lambda *_: recipe(Path("unread/alternate.SLDPRT")),
    )
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "frozen-candidate")
    monkeypatch.setattr(probe, "helper_fingerprints", lambda: {"helper": "frozen"})
    fingerprint_calls = []

    def adapter_fingerprints():
        fingerprint_calls.append(1)
        return {
            "native": "changed"
            if mode == "adapter_drift" and len(fingerprint_calls) > 1
            else "same"
        }

    monkeypatch.setattr(probe, "adapter_fingerprints", adapter_fingerprints)
    source_handle = object()
    monkeypatch.setattr(
        probe,
        "source_dimensions",
        lambda *_: ({"source": "same"}, {"dimension": source_handle}),
    )
    snapshots = []

    def drawing_witness(adapter):
        snapshots.append(adapter.currentModel)
        return {"observed": len(snapshots) if mode == "reopen_drift" else "same"}

    monkeypatch.setattr(probe, "drawing_witness", drawing_witness)

    def compare(_app, before, after):
        if before != after:
            raise RuntimeError("saved annotation changed")

    monkeypatch.setattr(probe, "compare_drawing", compare)
    adapter = Adapter(mode)
    output_root = tmp_path / "reports"
    if mode == "normal":
        result = await probe.pilot(
            adapter, "candidate", source_root, guard_root, output_root
        )
        report_path = Path(result["report"])
    else:
        with pytest.raises(RuntimeError):
            await probe.pilot(
                adapter, "candidate", source_root, guard_root, output_root
            )
        (report_path,) = output_root.glob("*/pilot.json")
    report = json.loads(report_path.read_text())
    assert len(adapter.drawn) == (2 if mode == "normal" else 1)
    # Source files are now unique owned copies. Reusing the original source
    # would mutate an already-visible user's model dimension callout text.
    for target, (outputs, source) in zip(probe.ORDER, adapter.drawn):
        assert source.parent == outputs.slddrw.parent
        assert source.name.startswith(target.replace("_", "-") + "-source-")
        assert source.name != target.replace("_", "-") + ".SLDPRT"
        assert source_root not in source.parents and guard_root not in source.parents
    assert all(
        probe.attachments.file_digest(
            source_root / (target.replace("_", "-") + ".SLDPRT")
        )
        == probe.EXPECTED_PART_HASHES[target]
        for target in probe.ORDER
    )
    assert report["status"] == ("passed" if mode == "normal" else "failed")
    assert len(report["sources_after"]) == 4
    assert all(
        outputs.slddrw.is_relative_to(output_root) for outputs, _ in adapter.drawn
    )
    assert len({outputs.slddrw for outputs, _ in adapter.drawn}) == len(adapter.drawn)
    assert adapter.ownership.creating_document.call_count == len(adapter.drawn)
    registered_sources = {
        call.args[0] for call in adapter.ownership.register_source.call_args_list
    }
    assert not registered_sources.intersection(source for _, source in adapter.drawn)
    assert len(registered_sources) == 4
    if mode == "normal":
        assert all(
            trial["copy_final"] == probe.EXPECTED_PART_HASHES[trial["target"]]
            for trial in report["trials"]
        )


@pytest.mark.asyncio
async def test_wrong_exact_source_fails_before_open_or_recipe_execution(
    tmp_path, monkeypatch
):
    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    (source_root / "rocker-arm.SLDPRT").write_bytes(b"different identity")
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "candidate")
    adapter = Adapter("normal")
    with pytest.raises(RuntimeError, match="immutable source hash mismatch"):
        await probe.pilot(
            adapter, "candidate", source_root, guard_root, tmp_path / "reports"
        )
    assert adapter.drawn == adapter.opened == []
    (report_path,) = (tmp_path / "reports").glob("*/pilot.json")
    assert json.loads(report_path.read_text())["status"] == "failed"


def test_imported_adapter_content_not_empty_worktree_submodule_is_fingerprinted(
    tmp_path, monkeypatch
):
    import solidworks_mcp

    package = tmp_path / "imported-package"
    (package / "adapters").mkdir(parents=True)
    entry = package / "__init__.py"
    entry.write_text("# imported adapter")
    core = package / "adapters/pywin32_adapter.py"
    core.write_text("# original")
    monkeypatch.setattr(solidworks_mcp, "__file__", str(entry))
    before = probe.adapter_fingerprints()
    core.write_text("# changed")
    assert probe.adapter_fingerprints() != before
    assert before["package_path"] == str(package)
    assert len(before["files"]) == 2


def test_actual_adapter_origin_missing_core_fails_instead_of_empty_provenance(
    tmp_path, monkeypatch
):
    import solidworks_mcp

    entry = tmp_path / "__init__.py"
    entry.write_text("# incomplete")
    monkeypatch.setattr(solidworks_mcp, "__file__", str(entry))
    with pytest.raises(RuntimeError, match="incomplete"):
        probe.adapter_fingerprints()


def test_source_dimension_native_replacement_is_not_hidden_by_equal_values():
    with pytest.raises(RuntimeError, match="dimension identity changed"):
        probe.require_same_source(
            {},
            {},
            "recipe",
            app=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
            handles_before={"D": object()},
            handles_after={"D": object()},
        )


def test_parent_requires_no_autostart_before_any_native_parent_wrapper(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    with pytest.raises(RuntimeError, match="AUTOSTART=0"):
        probe.main(["--source-root", str(tmp_path), "--guard-root", str(tmp_path)])


def test_real_candidate_recipes_have_pre_execution_source_and_output_contract(tmp_path):
    for target in probe.ORDER:
        source = tmp_path / f"{target}.SLDPRT"
        source.write_bytes(b"input only; never COM")
        trial = tmp_path / target
        trial.mkdir()
        module = probe.benchmark.load_recipe("2802e92a", target, trial, source=source)
        assert module.SOURCE == source
        assert module.OUTPUTS.slddrw.parent == trial
        if target == "channel_lever":
            assert module.build.__kwdefaults__["source"] == source
            assert module.build.__kwdefaults__["outputs"] == module.OUTPUTS


@pytest.mark.parametrize("target", probe.ORDER)
def test_source_dimensions_use_production_manifest_and_read_only_native_owner(
    tmp_path, monkeypatch, target
):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    path = tmp_path / f"{target}.SLDPRT"
    model = SimpleNamespace(
        GetType=lambda: 1,
        GetPathName=lambda: str(path),
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
    )
    expected = (
        probe.DRAWING_DIMENSIONS
        if target == "channel_lever"
        else probe.ROCKER_DIMENSIONS
    )

    def part_dimensions(adapter, actual_path, configuration, *, targets):
        assert adapter.currentModel is model
        assert actual_path == path and configuration == "Default"
        assert targets is expected
        rows = {
            f"{name}@{feature}": {"tolerance_type": 1}
            for feature, names in targets.items()
            for name in names
        }
        return rows, {}

    monkeypatch.setattr(probe, "part_dimensions", part_dimensions)
    actual, _ = probe.source_dimensions(model, target, path)
    assert actual["configuration"] == "Default"
    assert len(actual["dimensions"]) == sum(map(len, expected.values()))


def test_source_missing_basic_designation_fails_instead_of_reauthoring(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    path = tmp_path / "channel-lever.SLDPRT"
    model = SimpleNamespace(
        GetType=lambda: 1,
        GetPathName=lambda: str(path),
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
    )
    rows = {
        f"{name}@{feature}": {"tolerance_type": 0}
        for feature, names in probe.DRAWING_DIMENSIONS.items()
        for name in names
    }
    monkeypatch.setattr(probe, "part_dimensions", lambda *args, **kwargs: (rows, {}))
    with pytest.raises(RuntimeError, match="BASIC designation missing"):
        probe.source_dimensions(model, "channel_lever", path)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["normal", "build_failure", "copy_saved"])
async def test_owned_dirty_part_copies_preserve_real_baseline_lifecycle(
    native,  # noqa: F811 - imported pytest fixture
    tmp_path,
    monkeypatch,
    mode,
):
    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    original_lever = Model(source_root / "channel-lever.SLDPRT", kind=1)
    drawing2 = Model(None, title="Draw2 - Sheet1", dirty=True)
    native.app.documents.extend((original_lever, drawing2))
    native.app.ActiveDoc = drawing2
    monkeypatch.setattr(
        probe.benchmark, "recipe_source", lambda *_: recipe(Path("unused.SLDPRT"))
    )
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(probe, "helper_fingerprints", lambda: {"helper": "same"})
    monkeypatch.setattr(probe, "adapter_fingerprints", lambda: {"adapter": "same"})
    monkeypatch.setattr(
        probe,
        "source_dimensions",
        lambda model, target, path: (
            {
                "configuration": "Default",
                "values_tolerances_basic": "same",
                "owner": str(path),
            },
            {"dimension": model},
        ),
    )
    monkeypatch.setattr(
        probe,
        "drawing_witness",
        lambda adapter: {"reference": adapter.currentModel.references[0].path},
    )

    def compare(_app, before, after):
        assert before == after

    monkeypatch.setattr(probe, "compare_drawing", compare)
    references, built = {}, []
    initial_open = native.adapter.open_model

    async def opening(path):
        result = await initial_open(path)
        if Path(path).suffix.upper() == ".SLDDRW":
            source = references[path]
            part = native.app.GetOpenDocumentByName(source)
            if part is None:
                part = Model(source, kind=1)
                native.app.documents.append(part)
            native.adapter.currentModel.references = [part]
        return result

    native.adapter.open_model = opening

    async def callback(adapter):
        async def draw(outputs, source):
            built.append(source)
            part = native.app.GetOpenDocumentByName(str(source))
            assert part is not original_lever
            part.dirty = True  # Reproduced imported source-display mutation.
            drawing = Model(None, title=f"Owned drawing {len(built)}", dirty=True)
            drawing.references = [part]
            native.app.documents.append(drawing)
            native.app.ActiveDoc = drawing
            adapter.currentModel = drawing
            if mode == "build_failure":
                raise RuntimeError("production final gate failed")
            with adapter.ownership.saving_as(outputs.slddrw):
                drawing.path = str(outputs.slddrw)
                drawing.title = outputs.slddrw.name
                drawing.dirty = False
                outputs.slddrw.write_bytes(b"saved drawing only")
            if mode == "copy_saved":
                source.write_bytes(b"unintended source save")
            outputs.pdf.write_bytes(b"pdf")
            outputs.png.write_bytes(b"png")
            references[str(outputs.slddrw)] = str(source)
            return {
                "drawing": str(outputs.slddrw),
                "pdf": str(outputs.pdf),
                "png": str(outputs.png),
            }

        native.adapter.draw = draw
        return await probe.pilot(
            adapter, "frozen", source_root, guard_root, tmp_path / "reports"
        )

    if mode == "normal":
        await owned.owned_callback(native.adapter, callback)
    else:
        with pytest.raises(
            RuntimeError, match="production final gate|source copy changed"
        ):
            await owned.owned_callback(native.adapter, callback)
    assert len(built) == (2 if mode == "normal" else 1)
    assert native.app.documents == [original_lever, drawing2]
    assert not original_lever.dirty and original_lever.Visible
    assert drawing2.dirty and drawing2.Visible and drawing2.GetPathName() == ""
    assert all(
        source_root not in Path(path).parents and guard_root not in Path(path).parents
        for path in native.adapter.opens
    )
    assert all(item not in (original_lever, drawing2) for item in native.app.closes)
    (receipt,) = (tmp_path / "reports").glob("*/pilot.json")
    report = json.loads(receipt.read_text())
    assert report["sources_before"] == report["sources_after"]
    assert report["status"] == ("passed" if mode == "normal" else "failed")
    if mode == "copy_saved":
        assert (
            report["trials"][0]["copy_final"]
            != probe.EXPECTED_PART_HASHES["rocker_arm"]
        )
