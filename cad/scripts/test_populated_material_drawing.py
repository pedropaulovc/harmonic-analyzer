"""Fresh local material sources are explicit, never historical pilot enrollment."""

import asyncio
from copy import deepcopy
from dataclasses import replace
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_populated_template as probe


def test_material_targets_are_three_local_inputs_without_changing_pilot_registry():
    from diagnostics import _material_template_sources as sources
    from diagnostics._recipe_acceptance_targets import TARGETS
    import tube_frame_spec

    assert tuple(sources.TARGETS) == ("rocker_arm", "channel_lever", "tube_frame")
    assert "tube_frame" not in TARGETS
    for target in ("rocker_arm", "channel_lever"):
        assert sources.TARGETS[target].source_sha256 != TARGETS[target].source_sha256
        assert sources.TARGETS[target].dimensions == TARGETS[target].dimensions
    assert (
        sources.TARGETS["tube_frame"].dimensions == tube_frame_spec.DRAWING_DIMENSIONS
    )


@pytest.mark.parametrize("mode", ["accepted", "bytes", "token", "missing"])
def test_local_sources_require_pinned_bytes_and_matching_execution_tokens(
    tmp_path, monkeypatch, mode
):
    from diagnostics import _material_template_sources as sources

    paths, manifest = {}, {}
    for target, row in sources.TARGETS.items():
        path = tmp_path / f"{target.replace('_', '-')}.SLDPRT"
        path.write_bytes(target.encode())
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_name(f".{path.stem}.execution").write_text(
            sha + "\n", encoding="utf-8"
        )
        paths[target], manifest[target] = path, replace(row, source_sha256=sha)
    monkeypatch.setattr(sources, "TARGETS", manifest)
    tube = paths["tube_frame"]
    if mode == "bytes":
        tube.write_bytes(b"same name, foreign bytes")
    if mode == "token":
        tube.with_name(f".{tube.stem}.execution").write_text("a" * 64, encoding="utf-8")
    if mode == "missing":
        paths.pop("tube_frame")
    if mode == "accepted":
        result = sources.require_sources(paths)
        assert len(result) == 6  # Protect source AND token files throughout the trial.
        assert result[str(tube)] == manifest["tube_frame"].source_sha256
        return
    with pytest.raises(RuntimeError, match="material source"):
        sources.require_sources(paths)


def test_unregistered_trial_still_rejects_before_copy_but_explicit_hash_is_checked(
    tmp_path,
):
    from diagnostics import _material_template_sources as sources

    kwargs = dict(source_target="tube_frame", source_title="tube-frame")
    args = (
        SimpleNamespace(),
        probe.title.Variant.BASELINE,
        tmp_path / "tube.SLDPRT",
        tmp_path / "uncreated",
        {"trials": []},
        Mock(),
        {},
    )
    with pytest.raises(ValueError, match="unsupported title trial"):
        asyncio.run(probe.title.one_trial(*args, **kwargs))
    with pytest.raises(RuntimeError, match="explicit source manifest hash"):
        asyncio.run(
            probe.title.one_trial(
                *args, **kwargs, source_manifest=sources.TARGETS["tube_frame"]
            )
        )
    assert not (tmp_path / "uncreated").exists()


@pytest.mark.parametrize("mode", ["accepted", "foreign_owner", "missing_basic"])
def test_explicit_source_witness_keeps_exact_owner_and_basic_guards(
    tmp_path, monkeypatch, mode
):
    from diagnostics import _material_template_sources as sources

    pilot = probe.title.pilot
    path = tmp_path / "owned.SLDPRT"
    target = "channel_lever" if mode == "missing_basic" else "tube_frame"
    manifest = sources.TARGETS[target]
    model = SimpleNamespace(
        GetType=lambda: 1,
        GetPathName=lambda: str(
            tmp_path / "foreign.SLDPRT" if mode == "foreign_owner" else path
        ),
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
    )
    monkeypatch.setattr(pilot, "_early_bound", lambda value, _: value)
    rows = {
        f"{name}@{feature}": {"tolerance_type": 0}
        for feature, names in manifest.dimensions.items()
        for name in names
    }

    def dimensions(adapter, actual_path, configuration, *, targets):
        assert adapter.currentModel is model
        assert actual_path == path and configuration == "Default"
        assert targets is manifest.dimensions
        return rows, {"native": model}

    capture = Mock(side_effect=dimensions)
    monkeypatch.setattr(pilot, "part_dimensions", capture)
    if mode == "accepted":
        result, handles = pilot.source_dimensions(
            model, target, path, manifest=manifest
        )
        assert result == {"configuration": "Default", "dimensions": rows}
        assert handles == {"native": model}
        assert set(rows) == {"OuterDia@AnnulusProfile", "CapApexY@CapProfile"}
        return
    with pytest.raises(
        RuntimeError, match="wrong exact native owner|BASIC designation missing"
    ):
        pilot.source_dimensions(model, target, path, manifest=manifest)
    if mode == "foreign_owner":
        capture.assert_not_called()


@pytest.mark.parametrize("mode", ["baseline", "center"])
def test_three_source_mode_reuses_owned_trial_with_explicit_manifest_and_tube_scale(
    tmp_path, monkeypatch, mode
):
    from diagnostics import _material_template_sources as sources

    template, original = tmp_path / "derived.DRWDOT", tmp_path / "original.DRWDOT"
    template.write_bytes(b"derived")
    original.write_bytes(b"original")
    symbol = tmp_path / "gtol.sym"
    symbol.write_text(
        "#GGTOL,GOST\n*ANGULAR,Angularity\nA,LINE .0,.0,1.6,1.\nA,LINE .0,.0,1.6,.0\n",
        encoding="utf-8",
    )
    parts = tmp_path / "parts"
    parts.mkdir()
    expected = {}
    for target in sources.TARGETS:
        path = parts / f"{target.replace('_', '-')}.SLDPRT"
        path.write_bytes(target.encode())
        expected[str(path)] = probe.title.pilot.attachments.file_digest(path)
    monkeypatch.setattr(sources, "require_sources", lambda _: dict(expected))
    monkeypatch.setattr(probe.sheet_setup, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(
        probe.title.pilot,
        "require_sources",
        Mock(side_effect=AssertionError("historical pins used")),
    )
    monkeypatch.setattr(probe.title.pilot, "helper_fingerprints", lambda: {})
    monkeypatch.setattr(probe.title.pilot, "adapter_fingerprints", lambda: {})
    monkeypatch.setattr(probe.title.pilot.benchmark, "revision", lambda _: "frozen")
    calls = []

    async def trial(
        adapter, variant, source, directory, report, checkpoint, inputs, **kwargs
    ):
        calls.append(kwargs)
        assert kwargs["source_manifest"] is sources.TARGETS[kwargs["source_target"]]
        assert kwargs["view_scale"] == (
            (1.0, 10.0)
            if kwargs["source_target"] == "tube_frame"
            else probe.title.SCALE
        )
        assert kwargs["factory"].__self__.population is policy
        result = {
            "linked_fields": {
                "built": {"fit": {"issues": [{"kind": "kept_native_defect"}]}},
                "cold": {"fit": {"issues": []}},
            },
            "cold_delta": {"changed_leaf_count": 0},
            "printed": {"classification": "unchanged"},
            "png_delta": {"changed_pixel_count": 0},
        }
        report["trials"].append(result)
        return result

    monkeypatch.setattr(probe.title, "one_trial", trial)

    async def close():
        pass

    adapter = SimpleNamespace(
        ownership=SimpleNamespace(register_directory=Mock(), register_source=Mock()),
        close_owned_documents=close,
    )
    policy = (
        probe.Population.MATERIAL_BASELINE
        if mode == "baseline"
        else probe.Population.MATERIAL_CENTER
    )
    with pytest.raises(ExceptionGroup, match="populated template control failed"):
        asyncio.run(
            probe.probe(
                adapter,
                template,
                probe.title.pilot.attachments.file_digest(template),
                parts,
                tmp_path / "reports",
                symbol,
                population=policy,
            )
        )
    assert [call["source_target"] for call in calls] == list(sources.TARGETS)
    assert tuple(probe.TARGETS) == ("rocker_arm", "channel_lever")


@pytest.mark.parametrize(
    "mode", ["accepted", "wrong_value", "wrong_vertical", "blank_value"]
)
def test_material_observer_checks_actual_source_value_and_explicit_vertical_mode(mode):
    from diagnostics import _material_template_sources as sources
    from test_baked_template_material_drawing import scene

    before, _ = scene()
    row = deepcopy(before["notes"]["value"])
    value = "ASTM A513 Type 5 SAE 1020 DOM tube, 1.000 x 0.120 in"
    row.update(text=value, vertical=1)
    if mode == "wrong_value":
        row["text"] = "shorter substitute"
    if mode == "wrong_vertical":
        row["vertical"] = 0
    if mode == "blank_value":
        value = ""
    if mode == "accepted":
        sources.require_material_value(row, value, expected_vertical=1)
        return
    with pytest.raises(RuntimeError, match="material"):
        sources.require_material_value(row, value, expected_vertical=1)


@pytest.mark.parametrize(
    "mode", ["baseline", "center", "shortened_value", "wrong_alignment"]
)
def test_actual_observer_records_material_and_keeps_independent_fit_failures(
    tmp_path, monkeypatch, mode
):
    from test_populated_template_drawing import populated

    notes, lines, _ = populated()
    material = probe.layout.unique_note(
        notes, link=probe.fields.VALUE_LINKS["material"]
    )
    value = "ASTM A513 Type 5 SAE 1020 DOM tube, 1.000 x 0.120 in"
    notes[material].update(
        text=value, horizontal=1, vertical=0 if mode == "baseline" else 1
    )
    if mode == "shortened_value":
        notes[material]["text"] = "DOM tube"
    if mode == "wrong_alignment":
        notes[material]["vertical"] = 0
    for name in ("title", "dwg", "rev"):
        notes[name]["horizontal"] = 1
    notes["dwg"]["font"]["CharHeight"] = notes["rev"]["font"]["CharHeight"] = 0.0035
    path = tmp_path / "owned.SLDPRT"
    source = SimpleNamespace(
        GetPathName=lambda: str(path),
        GetType=lambda: 1,
        SummaryInfo=lambda _: "rocker-arm",
        GetCustomInfoValue=lambda _, key: {
            "Number": "MHA-071",
            "Revision": "v32",
            "Material": value,
        }[key],
    )
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCustomInfoValue=lambda *_: ""),
        swApp=SimpleNamespace(GetOpenDocumentByName=lambda _: source),
    )
    monkeypatch.setattr(probe.layout.cells, "required", lambda value, _: value)
    monkeypatch.setattr(
        probe.layout, "note_inventory", lambda _: (deepcopy(notes), {}, ["same SF"])
    )
    monkeypatch.setattr(
        probe.layout.cells, "template_lines", lambda _: (lines, {"same": "rules"})
    )
    prefs = {"sheet_properties": [2, 12, 1, 2, 0, 0.4318, 0.2794, 0]}
    monkeypatch.setattr(probe, "preferences", lambda _: deepcopy(prefs))
    monkeypatch.setattr(
        probe, "property_source", lambda *_: {"identity": "exact_native_source"}
    )
    independent = {
        "field": material,
        "kind": "native_fit",
        "error": "crosses real rule",
    }
    monkeypatch.setattr(
        probe.fields,
        "field_audit",
        lambda *_args, **_kwargs: {
            "fields": {},
            "issues": [deepcopy(independent)],
        },
    )
    policy = (
        probe.Population.MATERIAL_BASELINE
        if mode == "baseline"
        else probe.Population.MATERIAL_CENTER
    )
    controller = probe.PopulatedControl(
        tmp_path / "derived.DRWDOT", "0" * 64, Mock(), {}, population=policy
    )
    controller.setup["normalized_blank_defaults"] = deepcopy(prefs)
    controller.setup["normalized_blank_defaults"]["sheet_properties"][7] = 1
    trial = {"source_copy": str(path), "source_before": {"configuration": "Default"}}
    controller.observe(adapter, "built", trial, tmp_path / "first.pdf")
    controller.observe(adapter, "cold", trial, tmp_path / "cold.pdf")
    for phase in ("built", "cold"):
        row = trial["linked_fields"][phase]
        assert (
            row["expected_link_values"][probe.fields.VALUE_LINKS["material"]] == value
        )
        assert independent in row["fit"]["issues"]
        assert row["fit"]["status"] == "failed"
        material_issues = [
            issue
            for issue in row["fit"]["issues"]
            if issue["kind"] == "explicit_material_contract"
        ]
        assert bool(material_issues) == (mode in ("shortened_value", "wrong_alignment"))
