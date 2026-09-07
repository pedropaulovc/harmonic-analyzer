"""Fresh two-note population preserves complete source properties and guards."""

import asyncio
from copy import deepcopy
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_populated_template as probe


@pytest.mark.parametrize(
    "mode", ["accepted", "short_material", "short_finish", "top_material"]
)
def test_actual_new_observer_requires_complete_material_and_finish_properties(
    tmp_path, monkeypatch, mode
):
    from test_populated_template_drawing import populated

    notes, lines, _ = populated()
    material = probe.layout.unique_note(
        notes, link=probe.fields.VALUE_LINKS["material"]
    )
    finish = probe.layout.unique_note(notes, link=probe.fields.VALUE_LINKS["finish"])
    values = {
        "Material": "ASTM A513 Type 5 SAE 1020 DOM tube, 1.000 x 0.120 in",
        "Finish": "OD polished Ra 1.6; corrosion-preventive oil after inspection; ends faced; ID as-procured",
    }
    notes[material].update(text=values["Material"], horizontal=1, vertical=1)
    notes[finish].update(text=values["Finish"])
    if mode == "short_material":
        notes[material]["text"] = "DOM tube"
    if mode == "short_finish":
        notes[finish]["text"] = "polished"
    if mode == "top_material":
        notes[material]["vertical"] = 0
    for name in ("title", "dwg", "rev"):
        notes[name]["horizontal"] = 1
    notes["dwg"]["font"]["CharHeight"] = notes["rev"]["font"]["CharHeight"] = 0.0035
    source_path = tmp_path / "owned.SLDPRT"
    source = SimpleNamespace(
        GetPathName=lambda: str(source_path),
        GetType=lambda: 1,
        SummaryInfo=lambda _: "rocker-arm",
        GetCustomInfoValue=lambda _, key: {
            "Number": "MHA-071",
            "Revision": "v32",
            **values,
        }[key],
    )
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCustomInfoValue=lambda *_: ""),
        swApp=SimpleNamespace(GetOpenDocumentByName=lambda _: source),
    )
    monkeypatch.setattr(probe.layout.cells, "required", lambda value, _: value)
    monkeypatch.setattr(
        probe.layout,
        "note_inventory",
        lambda _: (deepcopy(notes), {}, ["same finish symbols"]),
    )
    monkeypatch.setattr(
        probe.layout.cells, "template_lines", lambda _: (lines, {"same": "rules"})
    )
    preferences = {"sheet_properties": [2, 12, 1, 2, 0, 0.4318, 0.2794, 0]}
    monkeypatch.setattr(probe, "preferences", lambda _: deepcopy(preferences))
    monkeypatch.setattr(
        probe, "property_source", lambda *_: {"identity": "exact_native_source"}
    )
    independent = {
        "field": material,
        "kind": "native_fit",
        "error": "retained independent field defect",
    }
    monkeypatch.setattr(
        probe.fields,
        "field_audit",
        lambda *_args, **_kwargs: {"fields": {}, "issues": [deepcopy(independent)]},
    )
    control = probe.PopulatedControl(
        tmp_path / "derived.DRWDOT",
        "0" * 64,
        Mock(),
        {},
        population=probe.Population.MATERIAL_FINISH,
    )
    control.setup["normalized_blank_defaults"] = deepcopy(preferences)
    control.setup["normalized_blank_defaults"]["sheet_properties"][7] = 1
    trial = {
        "source_copy": str(source_path),
        "source_before": {"configuration": "Default"},
    }
    for phase in ("built", "cold"):
        control.observe(adapter, phase, trial, tmp_path / f"{phase}.pdf")
        row = trial["linked_fields"][phase]
        for role in ("material", "finish"):
            assert (
                row["expected_link_values"][probe.fields.VALUE_LINKS[role]]
                == values[role.title()]
            )
        assert independent in row["fit"]["issues"]
        assert row["fit"]["status"] == "failed"
        introduced = [issue for issue in row["fit"]["issues"] if issue != independent]
        assert bool(introduced) == (mode != "accepted")


def test_new_population_uses_same_three_manifest_objects_and_only_diagnostic_tube_scale(
    tmp_path, monkeypatch
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
        expected[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(sources, "require_sources", lambda _: dict(expected))
    monkeypatch.setattr(probe.sheet_setup, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(
        probe.title.pilot,
        "require_sources",
        Mock(side_effect=AssertionError("historical source pins used")),
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
        assert kwargs["factory"].__self__.population is probe.Population.MATERIAL_FINISH
        result = {
            "linked_fields": {
                "built": {"fit": {"issues": [{"kind": "retained"}]}},
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
    with pytest.raises(ExceptionGroup, match="populated template control failed"):
        asyncio.run(
            probe.probe(
                adapter,
                template,
                hashlib.sha256(template.read_bytes()).hexdigest(),
                parts,
                tmp_path / "reports",
                symbol,
                population=probe.Population.MATERIAL_FINISH,
            )
        )
    assert [call["source_target"] for call in calls] == list(sources.TARGETS)
    assert tuple(probe.TARGETS) == ("rocker_arm", "channel_lever")
