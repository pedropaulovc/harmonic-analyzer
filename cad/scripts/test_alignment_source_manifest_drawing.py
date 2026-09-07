"""Explicit production-source enrollment; replay never reauthors the copied part."""

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _recipe_acceptance_targets as manifest
from diagnostics import _recipe_template_factory as factory
from diagnostics import _source_callout_authoring as authoring
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics._native_drawing_save_control import DrawingSave
from diagnostics._source_save_boundaries import SourceObservation


AUTHORED_SOURCE = "9e09613dcdfeadcd76cfa4e28f2c9b6035ea1736bdb1bbcca1a7ecc3239c0632"
OLD_SOURCE = "858dc759943c2f739b3081fd02f313c26ead01eb837e08f9c79d59caac388920"
UNCHANGED = {
    "rocker_arm": "3bfb6da45b91e5a73b24c74baf81141899149e3c327aa943930baed3fba4d4a0",
    "channel_lever": "6a994561f19487029c938cd7cca5047acbdfbf686020514be538ef5a632e0841",
    "fulcrum_shaft": "73eeb75dcb1f24ca70b5f5ad2212d7b829a94af3a518b7c3830ff6c58e47d740",
    "pivot_shaft": "e5bcdb79849aac9ce6068188ccf0c6e2fd1222e82f1d8b4d75e0fd2723f01dc5",
    "cone_gear_shaft": "8df108cb4053bd47bcc1acc8b83fede6e3a52a9d3c4f6341c1ab3702d512b0ab",
    "crank_drive_gear": "2cd81cf44def13c0bbd298617d16769206e4931eac41a04642ac6217e4880cb5",
    "crank_pinion": "08ea59d153d8801792a8b611981702d0b584b9e8a04a33e4b9cb322a3d9df6fc",
    "crankshaft": "3c0224617322e3a10cca4a5c52e2b0a3b4c82e7be7969c0b21faf4db58b4cd94",
    "cylinder_gear": "46fcb66a87fd35f8862e4a01e2225688b91ab7182608bce26159f59c5b14f120",
    "rack_pinion": "96f57e663d04d745e8ad67d36a5f9ea4ddbaece4c82b2dc312bca69d4d8005b8",
    "spring_hook": "29c04a0919e0f720915527bd62cdb90eed909de6d14e74b9068c106baa42ace5",
    "transgear_feed_pinion": "f9b033d0026ef26996a52f73fad3b3147c6f5e5b15333a306004dcaf435a0d77",
    "transgear_pinion": "4c079ba522ccf79fa90e75afa23303ba4c2f6541232e608525368e4cbb56d335",
}

AUTHORED_GEARS = {
    "crank_drive_gear": "a5a2e0882336d622a7e93fae4d326cb059e7d91758e536488fcc6bf6de4ce93f",
    "crank_pinion": "1b3a9dc571e1256459a10dd7e2d0815d35d41c284bf8665a9546751ac242ef24",
    "cylinder_gear": "b436e33215ced1c3791cfd4095f49b376258edc1d4896f86656cd1b569a966f9",
    "rack_pinion": "6591e6a5abf67a5a541ae8d4ee9542795bf37b5bfcb18121ee4636e963096fa7",
    "transgear_feed_pinion": "93bc3466e0066f267d66223fc6ac2eed020ebdc10b665981f6685f1947f33d74",
    "transgear_pinion": "989b42c133984a367517dfeb43f96bdf4201a2c899c4b2c9801d8ab7cb41e6c0",
}


def test_source_pins_match_explicit_actual_production_output_migrations():
    # Keep the original source inventory as provenance. Only named, observed
    # production builds replace those inputs; replay cannot discover new pins.
    expected = UNCHANGED | AUTHORED_GEARS | {
        "alignment_pinion": AUTHORED_SOURCE,
        "cone_tip_adjuster": "18d0c1669c8de923420655d621f58d24afe404bc1d3a5a787930ebeeb2fefbf2",
        "cone_pivot_screw": "515019088b41d329b45f0487b9241123751ecac7d6c116481930ae9c45e89c36",
        "fillister_screw": "e7b48995c9f2e87af473219edfca1500a14e77bd353a330c64883011ab4fb60d",
    }
    assert {key: row.source_sha256 for key, row in manifest.TARGETS.items()} == expected
    assert pilot.EXPECTED_PART_HASHES == expected
    assert len(expected) == 17


@pytest.mark.parametrize("target", AUTHORED_GEARS)
@pytest.mark.parametrize("source_state", ["historical", "authored", "unknown"])
def test_gear_replay_rejects_old_or_unknown_bytes_without_repinning(
    monkeypatch, tmp_path, target, source_state
):
    path = tmp_path / (target.replace("_", "-") + ".SLDPRT")
    digest = {
        "historical": UNCHANGED[target],
        "authored": AUTHORED_GEARS[target],
        "unknown": "0" * 64,
    }[source_state]
    before = dict(pilot.EXPECTED_PART_HASHES)
    monkeypatch.setattr(pilot.attachments, "file_digest", lambda _: digest)
    sources = {target: path}
    if source_state == "authored":
        assert pilot.require_sources(sources, sources) == {str(path): digest}
    else:
        with pytest.raises(RuntimeError, match="exact immutable source hash mismatch"):
            pilot.require_sources(sources, sources)
    assert pilot.EXPECTED_PART_HASHES == before


@pytest.mark.parametrize("digest", [OLD_SOURCE, "0" * 64, AUTHORED_SOURCE])
def test_manifest_still_requires_the_exact_selected_bytes(
    monkeypatch, tmp_path, digest
):
    path = tmp_path / "alignment-pinion.SLDPRT"
    reader = Mock(return_value=digest)
    monkeypatch.setattr(pilot.attachments, "file_digest", reader)
    sources = {"alignment_pinion": path}
    if digest != AUTHORED_SOURCE:
        with pytest.raises(RuntimeError, match="exact immutable source hash mismatch"):
            pilot.require_sources(sources, sources)
        return
    assert pilot.require_sources(sources, sources) == {str(path): AUTHORED_SOURCE}
    assert reader.call_args_list == [((path,),), ((path,),)]


@pytest.mark.parametrize("route", ["parent", "worker"])
def test_prepared_alignment_replay_selects_observers_but_no_authoring(
    monkeypatch, tmp_path, route
):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "31860")
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    source = Path(__file__).with_name("draw_alignment_pinion.py").read_text()
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: source)
    forbidden = Mock(side_effect=AssertionError("replay must not author source again"))
    monkeypatch.setattr(authoring, "SourceCalloutControl", forbidden)
    parent, observed = Mock(), []
    monkeypatch.setitem(sys.modules, "dodo", SimpleNamespace(_run=parent))

    async def run(*args, **kwargs):
        observed.append(kwargs)
        return 0

    monkeypatch.setattr(pilot, "pilot", run)
    monkeypatch.setattr(
        pilot, "run_copy_diagnostic", lambda callback: asyncio.run(callback(object()))
    )
    argv = [
        "--source-root",
        str(tmp_path),
        "--guard-root",
        str(tmp_path),
        "--target",
        "alignment_pinion",
        "--factory",
        "prepared",
        "--source-observation",
        "alignment_save",
        "--drawing-save",
        "legacy",
    ]
    assert pilot.main([*argv, *(["--worker"] if route == "worker" else [])]) == 0
    forbidden.assert_not_called()
    if route == "worker":
        assert len(observed) == 1
        controller = observed[0].pop("setup_controller")
        assert controller.variant is factory.DrawingFactory.PREPARED
        assert observed == [
            {
                "targets": ("alignment_pinion",),
                "source_observation": SourceObservation.ALIGNMENT_SAVE,
                "drawing_save": DrawingSave.LEGACY,
            }
        ]
        parent.assert_not_called()
        return
    command = parent.call_args.args[0]
    assert command[command.index("--factory") + 1] == "prepared"
    assert command[command.index("--source-observation") + 1] == "alignment_save"
    assert command[command.index("--drawing-save") + 1] == "legacy"
    assert "--source-callout-authoring" not in command
    assert "--callout-storage" not in command
    assert parent.call_args.kwargs["com"] is True
