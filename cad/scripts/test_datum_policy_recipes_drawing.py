"""Functional pilot reuses unchanged recipes and scoped native ownership."""

from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_datum_policy_recipes as probe
from test_benchmark_drawing_recipes import recipe


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
    assert [path.name for _, path in adapter.drawn] == [
        name.replace("_", "-") + ".SLDPRT" for name in probe.ORDER[: len(adapter.drawn)]
    ]
    assert report["status"] == ("passed" if mode == "normal" else "failed")
    assert len(report["sources_after"]) == 4
    assert all(
        outputs.slddrw.is_relative_to(output_root) for outputs, _ in adapter.drawn
    )
    assert len({outputs.slddrw for outputs, _ in adapter.drawn}) == len(adapter.drawn)
    assert adapter.ownership.creating_document.call_count == len(adapter.drawn)


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
