"""Printed tolerance providers keep independent source-content cache boundaries."""

from pathlib import Path

import pytest

import _config
import _printed_angular_tolerance as angular
import _printed_drilled_tolerance as drilled
import _printed_tolerance as linear
from test_dodo_recipe import (  # noqa: F401 -- pytest discovers imported fixtures
    isolated_assembly_helper_keys,
    local_executor,
)

pytestmark = pytest.mark.usefixtures("local_executor")


def test_printed_band_providers_preserve_their_numeric_rows(monkeypatch):
    rows = {
        "linear_2pl": {"display": "±0.51", "value_in": 99.0},
        "angular": {"value_deg": "1.25", "display": "±99°"},
        "drilled_hole": {"plus_mm": "0.17", "minus_mm": 99.0},
    }
    reads = []

    def title_block(row):
        reads.append(row)
        return rows[row]

    monkeypatch.setattr(_config, "title_block", title_block)
    assert linear.printed_band_mm(2) == 0.51
    assert angular.angular_band_deg() == 1.25
    assert drilled.drilled_oversize_mm() == 0.17
    assert linear.printed_deviations(10.254, 2) == pytest.approx((-0.514, 0.506))
    assert linear.printed_deviations(10.254, 2, (-0.1, 0.2)) == pytest.approx(
        (-0.104, 0.196)
    )
    assert reads == ["linear_2pl", "angular", "drilled_hole", "linear_2pl"]


def test_linear_tolerance_does_not_reexport_other_band_providers():
    assert not ({"angular_band_deg", "drilled_oversize_mm"} & vars(linear).keys())


def test_printed_band_source_and_config_edits_change_only_real_part_keys(
    isolated_assembly_helper_keys,
):
    """Pin positive and negative consumers independently of discovered deps."""
    dodo, root, _ = isolated_assembly_helper_keys
    parts = {
        "pd_transgear_thumbnut",
        "dt_crank_pin",
        "ch_rocker_arm",
        "ch_rocker_arm_tl_oblique_riser",
    }
    # The live thumbnut uses angular + linear; crank pin uses drilled + linear;
    # rocker uses linear alone; riser uses all three band providers.
    expected_consumers = {
        "_printed_angular_tolerance": {
            "pd_transgear_thumbnut",
            "ch_rocker_arm_tl_oblique_riser",
        },
        "_printed_drilled_tolerance": {
            "dt_crank_pin",
            "ch_rocker_arm_tl_oblique_riser",
        },
        "_printed_tolerance": parts,
        "_config": parts,
        "title_block.yaml": parts,
    }
    part_tasks = {task["name"]: task for task in dodo.task_part()}
    assert parts <= part_tasks.keys(), "samples must be registered native leaves"
    deps = {stem: part_tasks[stem]["file_dep"] for stem in parts}
    for stem, paths in deps.items():
        assert paths and all(
            Path(path).resolve().is_relative_to(root.resolve()) for path in paths
        ), stem

    def part_keys():
        dodo._ARTEFACT_DIGEST_MEMO.clear()
        return {
            stem: (dodo._digest_files(paths), dodo._cache_key(paths))
            for stem, paths in deps.items()
        }

    before = part_keys()
    scripts = root / "cad" / "scripts"
    mutations = [
        (
            name,
            scripts / f"{name}.py",
            b"return float(",
            b"return 2.0 * float(",
        )
        for name in (
            "_printed_angular_tolerance",
            "_printed_drilled_tolerance",
            "_printed_tolerance",
        )
    ]
    mutations.extend(
        [
            (
                "_config",
                scripts / "_config.py",
                None,
                b"\n# isolated shared configuration source mutation\n",
            ),
            (
                "title_block.yaml",
                root / "cad" / "config" / "title_block.yaml",
                b"value_deg: 1.0",
                b"value_deg: 1.5",
            ),
        ]
    )
    # The providers split, not title_block.yaml: its angular row edit must
    # still invalidate the drilled + linear and linear-only sample parts.
    for name, source, old, new in mutations:
        original = source.read_bytes()
        if old is None:
            mutated = original + new
        else:
            assert original.count(old) == 1, name
            mutated = original.replace(old, new, 1)
        assert mutated != original, f"the {name} mutation must not be vacuous"
        try:
            source.write_bytes(mutated)
            after = part_keys()
            for index, group in enumerate(("recipe", "cache_key")):
                assert {
                    stem for stem in parts if before[stem][index] != after[stem][index]
                } == expected_consumers[name], (name, group)
        finally:
            source.write_bytes(original)
