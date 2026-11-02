r"""Static tests for the build-graph enumeration (no SolidWorks required).

``_buildgraph`` is pure filesystem/string logic, so this runs in plain CI:

    python cad/scripts/test_buildgraph.py        # or: pytest cad/scripts/test_buildgraph.py
"""

from __future__ import annotations

import sys
import ast
from collections import Counter
from dataclasses import asdict, field, make_dataclass, replace
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _buildgraph as bg  # noqa: E402
from _buildgraph import (  # noqa: E402
    ASSEMBLY_ORDER,
    REFERENCES_DIR,
    SCRIPTS_DIR,
    config_files_of,
    data_deps_of,
    dependents_of,
    module_deps_of,
    part_stems,
    references_of,
    script_for,
    stamps_part_properties,
    stamps_title_block_properties,
)
from _assembly import assembly_title_properties  # noqa: E402
from _part_properties import part_properties  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_syntax_facts(tmp_path_factory, monkeypatch):
    """Each test starts from an EMPTY machine-wide facts store of its own, so a
    parse-count assertion never depends on what an earlier run left behind."""
    monkeypatch.setenv(bg._FACTS_ENV, str(tmp_path_factory.mktemp("facts")))
    monkeypatch.setattr(bg, "_FACTS", bg._FactStore())


@pytest.mark.parametrize(
    "declaration",
    [
        "",
        "DRAWINGS = ()\nDRAWINGS = ()\n",
        "DRAWINGS = build_drawings()\n",
        "DRAWINGS = tuple(rows)\n",
        "DRAWINGS = (*extra_rows,)\n",
        "DRAWINGS = (DrawingSpec(name=choose_name()),)\n",
        "DRAWINGS = (DrawingSpec(**row),)\n",
    ],
    ids=[
        "missing",
        "duplicate",
        "factory",
        "computed-tuple",
        "spread",
        "computed-field",
        "kwargs",
    ],
)
def test_drawing_registry_projection_rejects_executable_row_declarations(declaration):
    from _drawing_registry import DRAWINGS_BY_NAME

    with pytest.raises(ValueError):
        bg.drawing_registry_recipe(declaration, DRAWINGS_BY_NAME["pd_platen_guide"])


def test_drawing_registry_projection_tracks_new_selected_dataclass_fields():
    from _drawing_registry import DRAWINGS_BY_NAME, DrawingSpec

    source = (SCRIPTS_DIR / "_drawing_registry.py").read_text(encoding="utf-8")
    extended_spec = make_dataclass(
        "ExtendedDrawingSpec",
        [("finish_note", str, field(default="plain"))],
        bases=(DrawingSpec,),
        frozen=True,
    )(**asdict(DRAWINGS_BY_NAME["pd_platen_guide"]))
    before = bg.drawing_registry_recipe(source, extended_spec)
    after = bg.drawing_registry_recipe(
        source, replace(extended_spec, finish_note="black oxide")
    )
    assert before != after


def _helper_names(stem_script: str) -> set[str]:
    return {Path(p).stem for p in module_deps_of(SCRIPTS_DIR / stem_script)}


# Audited against each builder's insertion calls, local tuple/batch manifests,
# generated spring family and top-level SUBASSEMBLIES (not the old regex output).
_INSERTED_SOURCES = {
    "fr_frame": "sh_vn_brass_fillister_screw fr_vn_frame_cross_screw fr_vn_gooseneck_set_screw fr_harmonic_base "
    "fr_vn_lag_screw fr_nameplate fr_rocker_arm_support fr_top_frame fr_tube_frame fr_vn_tube_frame_cap",
    "dt_drive_train": "dt_alignment_pinion dt_arbor_pedestal sh_vn_arbor_set_screw dt_cone_gear dt_cone_gear_shaft "
    "dt_vn_cone_lock_knob dt_cone_pivot_post dt_vn_cone_pivot_screw dt_cone_swing_platform "
    "dt_vn_cone_tip_adjuster dt_cone_tip_block dt_vn_cone_tip_block_screw dt_vn_cone_tip_collar dt_vn_cone_tip_pinch_screw "
    "dt_crank_arm dt_crank_drive_gear dt_crank_handle dt_crank_handle_butt_cup dt_crank_handle_ferrule "
    "dt_crank_handle_pivot_screw dt_crank_hub dt_vn_crank_hub_pin dt_crank_pin "
    "dt_crank_pin_eye dt_crank_pin_ring dt_vn_crank_seat_drive_pin "
    "dt_crank_pinion dt_crank_pinion_pin dt_crankshaft dt_cylinder_end_disc dt_cylinder_gear "
    "dt_vn_cylinder_bank_spring dt_cylinder_gear_shaft "
    "sh_vn_brass_fillister_screw sh_vn_fillister_screw_90280a108 dt_vn_keeper_chain dt_vn_keeper_chain_link dt_vn_pedestal_hold_down_screw dt_pinion_arbor dt_pinion_arbor_collar dt_pinion_bracket dt_pinion_cam "
    "dt_pinion_cam_pin dt_pinion_handle dt_pinion_lever dt_pinion_lever_pin dt_pinion_lift_rod "
    "dt_pinion_pivot_block dt_pinion_pivot_shaft dt_pinion_spring dt_vn_pinion_strap_pin dt_vn_post_mount_screw dt_vn_slotted_screw",
    "ch_channel": "ch_amplitude_bar ch_bar_pivot_pin ch_channel_lever ch_vn_channel_spring_installed ch_connecting_rod "
    "ch_vn_frame_side_screw ch_fulcrum_keeper ch_vn_fulcrum_set_screw ch_fulcrum_shaft ch_vn_bracket_hold_down_screw ch_pivot_bracket "
    "ch_pivot_shaft ch_rocker_arm ch_vn_rocker_bank_spring ch_vn_rocker_thrust_washer ch_rod_pivot_pin ch_vn_spring_hook "
    "ch_anchor_jam_nut sh_vn_arbor_set_screw",
    "sm_summing": "sm_vn_boss_hook sm_vn_boss_hook_jam_nut sm_vn_counter_spring sm_gooseneck sm_gooseneck_spring_screw sm_vn_knife_hanger_stud sm_vn_knife_hanger_washer sm_vn_knife_mount_dowel sm_knife_mount sm_summing_lever",
    "mg_magnifier": "sh_vn_clamp_screw sh_column_clamp_back sh_column_clamp_front sh_vn_music_wire "
    "mg_magnifying_bracket mg_vn_magnifying_bracket_screw mg_magnifying_clamp mg_magnifying_lever mg_magnifying_vertical_rod "
    "mg_magnifying_wheel mg_output_fixture sh_vn_thumb_screw mg_wheel_axle mg_wheel_axle_spacer mg_vn_wheel_axle_back_washer "
    "mg_vn_wheel_axle_front_washer mg_vn_wheel_axle_nut mg_wheel_bar mg_wheel_drum",
    "pn_pen": "pn_vn_hanger_screw pn_pen_adjust_screw pn_vn_pen_adjust_nut pn_pen_frame pn_pen_hanger "
    "pn_vn_pen_hanger_jam_nut pn_vn_pen_hanger_nut pn_vn_pen_marker "
    "pn_pen_rod pn_vn_pen_rod_set_screw pn_vn_pen_set_screw pn_pen_v_block sh_vn_music_wire",
    "pd_paper_drive": "pd_vn_chain_connecting_link sh_vn_chain_link sh_vn_clamp_screw "
    "sh_column_clamp_back sh_column_clamp_front sh_vn_brass_fillister_screw pd_guide_lock pd_vn_guide_lock_screw pd_latch_hook "
    "sh_vn_fillister_screw_90280a108 pd_vn_platen_clip_screw "
    "pd_platen pd_platen_clip pd_platen_guide pd_platen_paper pd_platen_rack pd_rack_pinion pd_support_bar "
    "pd_transgear_arm pd_transgear_arm_plate pd_vn_transgear_arm_plate_locating_pin pd_vn_transgear_arm_plate_screw "
    "pd_transgear_disc_hub pd_vn_transgear_disc_screw pd_transgear_drive_collar pd_transgear_feed_pinion "
    "pd_transgear_knob_cup pd_vn_transgear_knob_cup_pin pd_vn_transgear_knob_drive_pin "
    "pd_transgear_knob_shaft pd_transgear_knob_thrust_ring pd_vn_transgear_latch_pin pd_vn_transgear_pivot_screw "
    "pd_transgear_pin pd_transgear_pivot_spacer pd_vn_transgear_pivot_spring pd_transgear_rear_bushing "
    "pd_transgear_front_bushing "
    "pd_transgear_removable pd_vn_transgear_retaining_ring pd_vn_transgear_cluster_shim "
    "pd_transgear_thumbnut",
    "ms_measuring_stick": "ms_stick ms_stop_block ms_stop_plate ms_vn_stop_plate_screw sh_vn_thumb_screw",
    "ch_rocker_arm_tl_oblique_jig": "ch_rocker_arm_tl_oblique_base_bar ch_rocker_arm_tl_oblique_carrier "
    "ch_rocker_arm_tl_oblique_feed_lever ch_rocker_arm_tl_oblique_feed_block "
    "ch_rocker_arm_tl_oblique_end_bracket "
    "ch_rocker_arm_tl_oblique_pivot_block ch_rocker_arm_tl_oblique_riser "
    "ch_rocker_arm_tl_vn_oblique_rail ch_rocker_arm_tl_vn_oblique_carriage "
    "ch_rocker_arm_tl_vn_oblique_cl_dowel ch_rocker_arm_tl_vn_oblique_leadscrew "
    "ch_rocker_arm_tl_vn_oblique_leadscrew_nut ch_rocker_arm_tl_vn_oblique_pillow_block "
    "ch_rocker_arm_tl_vn_oblique_handwheel sh_vn_clamping_kit_hardware "
    "ch_rocker_arm_tl_vn_oblique_rail_screw ch_rocker_arm_tl_vn_oblique_bracket_screw "
    "ch_rocker_arm_tl_vn_oblique_carriage_screw "
    "ch_rocker_arm_tl_vn_oblique_kp08_screw ch_rocker_arm_tl_vn_oblique_nut_screw "
    "ch_rocker_arm_tl_vn_oblique_riser_screw ch_rocker_arm_tl_vn_oblique_clamp_screw "
    "ch_rocker_arm_tl_vn_oblique_lever_screw ch_rocker_arm_tl_vn_oblique_lever_washer "
    "ch_rocker_arm_tl_vn_oblique_pivot_screw ch_rocker_arm_tl_vn_oblique_pivot_spacer "
    "ch_rocker_arm_tl_vn_oblique_pivot_shim ch_rocker_arm_tl_vn_oblique_hub_pin",
    "ha_harmonic_analyzer": "fr_frame dt_drive_train ch_channel sm_summing mg_magnifier pn_pen "
    "pd_paper_drive ms_measuring_stick",
}


@pytest.mark.parametrize("assembly", ASSEMBLY_ORDER)
def test_all_assembly_references_match_inserted_source_manifests(assembly):
    assert set(references_of(assembly)) == set(_INSERTED_SOURCES[assembly].split())


@pytest.mark.parametrize(
    ("producer", "consumers"),
    [
        ("sh_vn_chain_link", {"pd_paper_drive"}),
        ("sh_vn_brass_fillister_screw", {"fr_frame", "dt_drive_train", "pd_paper_drive"}),
        ("sh_vn_fillister_screw_90280a108", {"dt_drive_train", "pd_paper_drive"}),
        ("sh_vn_clamp_screw", {"mg_magnifier", "pd_paper_drive"}),
        ("sh_vn_arbor_set_screw", {"ch_channel", "dt_drive_train"}),
        ("sh_vn_thumb_screw", {"mg_magnifier", "ms_measuring_stick"}),
        ("sh_vn_music_wire", {"mg_magnifier", "pn_pen"}),
        ("sh_vn_clamping_kit_hardware", {"ch_rocker_arm_tl_oblique_jig"}),
    ],
)
def test_shared_vendor_producers_have_exact_direct_consumers(producer, consumers):
    assert producer in part_stems()
    assert {
        assembly for assembly in ASSEMBLY_ORDER if producer in references_of(assembly)
    } == consumers
    for assembly in consumers:
        assert references_of(assembly).count(producer) == 1
    expected_dependents = consumers
    if any(not bg.is_shop_fixture(assembly) for assembly in consumers):
        expected_dependents = consumers | {"ha_harmonic_analyzer"}
    assert set(dependents_of(producer)) == expected_dependents


@pytest.mark.parametrize(
    ("stem", "scope", "expected"),
    [
        ("sh_vn_clamping_kit_hardware", None, False),
        ("sh_vn_clamping_kit_hardware", "machine", False),
        ("sh_vn_clamping_kit_hardware", "tooling", True),
        ("ch_rocker_arm_tl_oblique_base_bar", None, True),
        ("ch_rocker_arm_tl_oblique_base_bar", "machine", True),
        ("ch_rocker_arm_tl_oblique_base_bar", "tooling", True),
    ],
)
def test_shop_fixture_scope_preserves_tl_and_defaults_shared_parts_to_machine(
    tmp_path, monkeypatch, stem, scope, expected,
):
    parts = tmp_path / "parts"
    parts.mkdir()
    dashed = stem.replace("_", "-")
    row = f"{dashed}:\n  number: MHA-SH-VN-57\n"
    if scope is not None:
        row += f"  usage_scope: {scope}\n"
    (parts / f"{dashed}.yaml").write_text(row, encoding="utf-8")
    monkeypatch.setattr(bg, "CONFIG_DIR", tmp_path)
    assert bg.is_shop_fixture(stem) is expected


@pytest.mark.parametrize("scope", ["fixture", "Tooling", "null", "true", "7", "[]"])
@pytest.mark.parametrize(
    "stem", ["sh_vn_clamping_kit_hardware", "ch_rocker_arm_tl_oblique_base_bar"],
)
def test_shop_fixture_scope_rejects_invalid_enums_even_for_tl_stems(
    tmp_path, monkeypatch, scope, stem,
):
    parts = tmp_path / "parts"
    parts.mkdir()
    dashed = stem.replace("_", "-")
    (parts / f"{dashed}.yaml").write_text(
        f"{dashed}:\n  usage_scope: {scope}\n", encoding="utf-8",
    )
    monkeypatch.setattr(bg, "CONFIG_DIR", tmp_path)
    with pytest.raises(ValueError, match="invalid usage_scope"):
        bg.is_shop_fixture(stem)


def test_registered_shared_kit_is_tooling_without_a_tl_identity():
    assert "_tl_" not in "sh_vn_clamping_kit_hardware"
    assert bg.is_shop_fixture("sh_vn_clamping_kit_hardware")
    assert not bg.is_shop_fixture("sh_vn_brass_fillister_screw")


def test_arm_plate_locating_pin_has_real_assembly_dependents() -> None:
    """The inserted locating dowels must be produced before the paper drive."""
    stem = "pd_vn_transgear_arm_plate_locating_pin"
    assert stem in part_stems(), "dependency census requires a real producer"
    assert stem in references_of("pd_paper_drive")
    assert set(dependents_of(stem)) == {"pd_paper_drive", "ha_harmonic_analyzer"}


def test_plain_pivot_components_are_first_class_jig_only_targets() -> None:
    import json

    import _config
    from _assembly_contract import assembly_contract
    from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
    from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

    identities = {
        "ch_rocker_arm_tl_oblique_feed_block": ("MHA-CH-06-TL-32", 1),
        "ch_rocker_arm_tl_vn_oblique_pivot_screw": ("MHA-CH-06-TL-VN-77", 2),
        "ch_rocker_arm_tl_vn_oblique_pivot_spacer": ("MHA-CH-06-TL-VN-78", 2),
        "ch_rocker_arm_tl_vn_oblique_pivot_shim": ("MHA-CH-06-TL-VN-79", 10),
        "ch_rocker_arm_tl_vn_oblique_hub_pin": ("MHA-CH-06-TL-VN-80", 1),
    }
    jig = "ch_rocker_arm_tl_oblique_jig"
    contract = assembly_contract(jig.replace("_", "-"))
    source_rows = json.loads(
        (bg.CONFIG_DIR / "current-identity-map.json").read_text(encoding="utf-8")
    )["parts_and_assemblies"]
    for stem, (number, quantity) in identities.items():
        dashed = stem.replace("_", "-")
        assert stem in part_stems(), f"{stem}: missing native part producer"
        assert script_for(stem).name == f"build_{stem}.py"
        assert script_for(stem).is_file()
        assert set(dependents_of(stem)) == {jig}
        assert stem in references_of(jig)
        assert all(stem not in references_of(machine) for machine in bg.MACHINE_ASSEMBLIES)
        assert dashed in contract.allowed_free_stems
        assert dashed in contract.required_free_stems
        drawing = DRAWINGS_BY_NAME[stem]
        assert (drawing.part, drawing.artifact_stem) == (stem, dashed)
        assert drawing.source_kind == "part"
        assert drawing.script_name == f"draw_{stem}.py" and drawing.script.is_file()
        assert drawing.layout is DrawingLayout.LANDSCAPE
        row = _config.parts(dashed)
        assert (row["number"], int(row["quantity"])) == (number, quantity)
        mapped = [
            (source, identity)
            for source in source_rows
            for identity in source["new_identities"]
            if identity["stem"] == dashed
        ]
        assert len(mapped) == 1
        source, identity = mapped[0]
        assert identity["number"] == number
        assert source["old_stem"] == dashed and source["old_number"] is None
        assert source["introduced"] == "2026-10-23"
        if "_vn_" in stem:
            assert identity["parent"] == jig.replace("_", "-")
        assert drawing.script_name in PRECISION_MIGRATED_DRAWINGS


@pytest.mark.parametrize(
    ("stem", "number"),
    [
        ("pd_chain_sprocket", "MHA-PD-01"),
        ("ch_rocker_arm_tl_vn_oblique_nut_washer", "MHA-CH-06-TL-VN-72"),
        ("ch_rocker_arm_tl_oblique_pivot_pin", "MHA-CH-06-TL-23"),
        ("ch_rocker_arm_tl_oblique_hub_pin", "MHA-CH-06-TL-25"),
        ("ch_rocker_arm_tl_oblique_nut_bracket", "MHA-CH-06-TL-29"),
        ("ch_rocker_arm_tl_oblique_pivot_cap", "MHA-CH-06-TL-30"),
        ("ch_rocker_arm_tl_oblique_pivot_retainer", "MHA-CH-06-TL-31"),
        ("ch_rocker_arm_tl_vn_oblique_bearing", "MHA-CH-06-TL-VN-52"),
        ("ch_rocker_arm_tl_vn_oblique_block_screw", "MHA-CH-06-TL-VN-63"),
        ("ch_rocker_arm_tl_vn_oblique_block_washer", "MHA-CH-06-TL-VN-70"),
        ("ch_rocker_arm_tl_vn_oblique_pivot_cap_screw", "MHA-CH-06-TL-VN-73"),
        ("ch_rocker_arm_tl_vn_oblique_pivot_clevis_pin", "MHA-CH-06-TL-VN-74"),
        ("ch_rocker_arm_tl_vn_oblique_pivot_cotter", "MHA-CH-06-TL-VN-75"),
        ("ch_rocker_arm_tl_vn_oblique_pivot_lock_wire", "MHA-CH-06-TL-VN-76"),
        ("pd_vn_transgear_pivot_shim", "MHA-PD-VN-67"),
    ],
)
def test_retired_orphan_families_are_not_allocated(stem, number) -> None:
    import yaml
    from _drawing_registry import DRAWINGS_BY_NAME
    from _fastener_catalog import FASTENERS

    assert stem not in part_stems()
    assert stem not in DRAWINGS_BY_NAME
    assert stem.replace("_", "-") not in FASTENERS
    assert not (bg.CONFIG_DIR / "parts" / f"{stem.replace('_', '-')}.yaml").exists()
    assert not (SCRIPTS_DIR / f"build_{stem}.py").exists()
    assert not (SCRIPTS_DIR / f"draw_{stem}.py").exists()
    for assembly in ASSEMBLY_ORDER:
        assert stem not in references_of(assembly)
    for registry in (bg.CONFIG_DIR / "parts").glob("*.yaml"):
        for row in yaml.safe_load(registry.read_text(encoding="utf-8")).values():
            if isinstance(row, dict):
                assert row.get("number") != number, registry


def test_retired_front_pin_is_not_allocated_but_rear_cup_pin_is() -> None:
    from _drawing_registry import DRAWINGS_BY_NAME
    from _fastener_catalog import FASTENERS
    from _test_stock_recipes import discovered_recipes

    obsolete = "vn_transgear_collar_cross_pin"
    retained = "pd_vn_transgear_knob_cup_pin"
    parts = set(part_stems())
    assert retained in parts
    assert retained in DRAWINGS_BY_NAME
    assert FASTENERS[retained.replace("_", "-")].skus == ("98296A031",)
    assert "98296A031" in discovered_recipes()
    assert obsolete not in parts
    assert obsolete not in DRAWINGS_BY_NAME
    assert obsolete.replace("_", "-") not in FASTENERS
    assert "98296A026" not in discovered_recipes()
    assert not (
        bg.CONFIG_DIR / "parts" / f"{obsolete.replace('_', '-')}.yaml"
    ).exists()
    for name in (
        f"build_{obsolete}.py",
        f"draw_{obsolete}.py",
        f"{obsolete}_spec.py",
        f"test_{obsolete}_drawing.py",
    ):
        assert not (SCRIPTS_DIR / name).exists()
    for source in (
        "build_pd_paper_drive_assembly.py",
        "draw_pd_paper_drive_assembly.py",
        f"build_{retained}.py",
    ):
        dependencies = _helper_names(source)
        assert f"{retained}_spec" in dependencies
        assert f"{obsolete}_spec" not in dependencies


def _source_references(tmp_path, monkeypatch, source, parts=("ch_rocker_arm",)):
    script = tmp_path / "build_parent_assembly.py"
    script.write_text(source, encoding="utf-8")
    monkeypatch.setattr(bg, "script_for", lambda _stem: script)
    monkeypatch.setattr(bg, "part_stems", lambda: list(parts))
    monkeypatch.setattr(bg, "ASSEMBLY_ORDER", ("parent", "ch_channel"))
    return set(bg.references_of("parent"))


def test_reference_parser_ignores_prose_comments_and_non_source_literals(
    tmp_path, monkeypatch
):
    source = '''"""The "channel" assembly does not belong here."""
# Previously "channel" was mentioned by a diagnostic.
raise AssertionError("channel station_z0 does not carry the fixed-post recenter")
log("channel")
label = "ch-rocker-arm"
'''
    assert _source_references(tmp_path, monkeypatch, source) == set()


def test_exact_source_name_does_not_reference_shorter_stem(tmp_path, monkeypatch):
    source = "await place_component(adapter, 'fr-rocker-arm-support', pos, rot, rows)"
    assert _source_references(
        tmp_path, monkeypatch, source, ("fr_rocker_arm", "fr_rocker_arm_support")
    ) == {"fr_rocker_arm_support"}


@pytest.mark.parametrize(
    "stem",
    (
        "sh_vn_brass_fillister_screw",
        "sh_vn_fillister_screw_90280a108",
        "sh_vn_chain_link",
        "pd_vn_chain_connecting_link",
    ),
)
def test_vendor_source_matching_selects_only_the_exact_current_producer(
    tmp_path, monkeypatch, stem,
):
    parts = (
        "sh_vn_brass_fillister_screw",
        "sh_vn_fillister_screw_90280a108",
        "sh_vn_chain_link",
        "pd_vn_chain_connecting_link",
    )
    source = (
        f"await place_component(adapter, '{stem.replace('_', '-')}', pos, rot, rows)"
    )
    assert _source_references(tmp_path, monkeypatch, source, parts) == {stem}


def test_distinct_chain_member_configurations_reference_one_native_producer(
    tmp_path, monkeypatch,
):
    source = (
        "await place_component(adapter, 'sh-vn-chain-link', p, r, q, "
        "configuration='InnerLink')\n"
        "await place_component(adapter, 'sh-vn-chain-link', p, r, q, "
        "configuration='OuterLink')\n"
    )
    assert _source_references(
        tmp_path, monkeypatch, source,
        ("sh_vn_chain_link", "pd_vn_chain_connecting_link"),
    ) == {"sh_vn_chain_link"}


def test_generated_vendor_variant_resolves_only_its_stock_family(
    tmp_path, monkeypatch,
):
    source = (
        "await place_component(adapter, "
        "f'ch-vn-channel-spring-installed-stretch{index:02d}', pos, rot, rows)"
    )
    assert _source_references(
        tmp_path,
        monkeypatch,
        source,
        ("ch_vn_channel_spring_installed", "dt_vn_cylinder_bank_spring"),
    ) == {"ch_vn_channel_spring_installed"}


@pytest.mark.parametrize(
    "expression", ["lookup_part()", "runtime_name", 'f"{runtime_name}"']
)
def test_unresolved_source_argument_fails_without_all_assembly_fallback(
    tmp_path, monkeypatch, expression
):
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(
            tmp_path,
            monkeypatch,
            f"await place_component(adapter, {expression}, pos, rot, rows)",
        )


@pytest.mark.parametrize(
    "source",
    [
        "from _assembly import place_component as put\nawait put(adapter, part='ch-rocker-arm', position=p, rotation=r, rows=q)",
        "part = 'ch-rocker-arm'; await place_component(adapter, part, p, r, q)",
        "for part in ('ch-rocker-arm',):\n    await place_component(adapter, part, p, r, q)",
        "riders = [('ch-rocker-arm', p)]\nfor part, pos in riders:\n    await place_component(adapter, part, pos, r, q)",
        "async def place(adapter, part):\n    await place_component(adapter, part, p, r, q)\nawait place(adapter, 'ch-rocker-arm')",
        "await adapter.insert_component(InsertComponentParameters(file_path='C:/cad/ch-rocker-arm.SLDPRT'))",
        "parts = [{'part': 'ch-rocker-arm'}]\nawait place_components_batch(adapter, parts)",
        "parts = []\nparts.append({'part': 'ch-rocker-arm'})\nawait place_components_batch(adapter, parts)",
        "parts = [{'part': 'ch-rocker-arm'}]\nawait place_components_batch(adapter, specs=parts)",
    ],
)
def test_reference_source_call_shapes(tmp_path, monkeypatch, source):
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


@pytest.mark.parametrize(
    "placement",
    [
        "await place_component(adapter, physical, p, r, q, label=logical)",
        "await place_components_batch(adapter, [{'part': physical, 'label': logical}])",
    ],
)
def test_tuple_member_manifests_track_physical_sources_not_logical_row_keys(
    tmp_path, monkeypatch, placement,
):
    source = (
        "_PARTS = (\n"
        "    ('sh-vn-clamping-kit-hardware', "
        "'sh-vn-clamping-kit-hardware--HoldDownStud'),\n"
        "    ('sh-vn-clamping-kit-hardware', "
        "'sh-vn-clamping-kit-hardware--TNut'),\n"
        "    ('sh-vn-clamping-kit-hardware', "
        "'sh-vn-clamping-kit-hardware--FlangeNut'),\n"
        "    ('ch-rocker-arm-tl-vn-oblique-rail', "
        "'ch-rocker-arm-tl-vn-oblique-rail'),\n"
        ")\n"
        "async def _place_family(adapter, physical, logical):\n"
        f"    {placement}\n"
        "for physical, logical in _PARTS:\n"
        "    await _place_family(adapter, physical, logical)\n"
    )
    assert _source_references(
        tmp_path, monkeypatch, source,
        (
            "sh_vn_clamping_kit_hardware",
            "ch_rocker_arm_tl_vn_oblique_rail",
            "pd_vn_chain_connecting_link",
        ),
    ) == {"sh_vn_clamping_kit_hardware", "ch_rocker_arm_tl_vn_oblique_rail"}


def test_ambiguous_dynamic_source_family_keeps_every_possible_producer(
    tmp_path, monkeypatch
):
    source = "await place_component(adapter, f'fr-rocker-arm{suffix}', p, r, q)"
    assert _source_references(
        tmp_path, monkeypatch, source, ("fr_rocker_arm", "fr_rocker_arm_support")
    ) == {"fr_rocker_arm", "fr_rocker_arm_support"}


@pytest.mark.parametrize(
    "source",
    [
        "parts = []\nparts.extend(runtime_parts())\nawait place_components_batch(adapter, parts)",
        "parts = []\nparts += runtime_parts()\nawait place_components_batch(adapter, parts)",
        "parts = []\nalias = parts\nalias.append({'part': 'ch-rocker-arm'})\nawait place_components_batch(adapter, parts)",
        "parts = alias = []\nalias.append({'part': 'ch-rocker-arm'})\nawait place_components_batch(adapter, parts)",
        "parts = []\nparts[0] = {'part': 'ch-rocker-arm'}\nawait place_components_batch(adapter, parts)",
        "parts = [{'part': 'ch-rocker-arm'}]\nfor spec in parts:\n    spec['part'] = runtime_part()\nawait place_components_batch(adapter, parts)",
        "parts = []\nmutate(parts)\nawait place_components_batch(adapter, parts)",
        "await place_components_batch(adapter, runtime_parts())",
        "await place_components_batch(adapter, [{'part': 'ch-rocker-arm', **runtime_fields()}])",
        "await adapter.insert_component(runtime_parameters())",
        "part = 'ch-rocker-arm'\npart += runtime_suffix()\nawait place_component(adapter, part, p, r, q)",
        "await place_component(adapter, 'rocker-arm-misspelled', p, r, q)",
        "put = place_component\nawait put(adapter, 'ch-rocker-arm', p, r, q)",
    ],
)
def test_unsupported_source_manipulation_fails_loud(tmp_path, monkeypatch, source):
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(tmp_path, monkeypatch, source)


def test_reference_syntax_cache_detects_source_edits_and_resolves_current_registry(
    tmp_path, monkeypatch
):
    source = "await place_component(adapter, 'ch-rocker-arm', p, r, q)"
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(tmp_path, monkeypatch, source, ("fr_rocker_arm_support",))
    changed = "await place_component(adapter, 'fr-rocker-arm-support', p, r, q)"
    assert _source_references(
        tmp_path, monkeypatch, changed, ("fr_rocker_arm_support",)
    ) == {"fr_rocker_arm_support"}


def test_local_path_wrapper_must_prove_it_preserves_source_name(tmp_path, monkeypatch):
    source = """def _part(name):
    path = (OUT_SLDPRT / f"{name}.SLDPRT").resolve()
    return str(path)
await adapter.insert_component(InsertComponentParameters(file_path=_part("ch-rocker-arm")))
"""
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}
    changed = source.replace('f"{name}.SLDPRT"', '"fr-rocker-arm-support.SLDPRT"')
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, changed, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


def test_later_module_bindings_are_conservative_for_function_sources(
    tmp_path, monkeypatch
):
    source = """PART = 'ch-rocker-arm'
async def build(adapter):
    await place_component(adapter, PART, p, r, q)
PART = 'fr-rocker-arm-support'
"""
    assert _source_references(
        tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
    ) == {"ch_rocker_arm", "fr_rocker_arm_support"}


def test_memo_lookup_keeps_initial_values_and_explicit_default(tmp_path, monkeypatch):
    source = """memo = {'old': 'ch-rocker-arm'}
part = memo.get(key, 'fr-rocker-arm-support')
memo[key] = 'fr-rocker-arm-support'
await place_component(adapter, part, p, r, q)
"""
    assert _source_references(
        tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
    ) == {"ch_rocker_arm", "fr_rocker_arm_support"}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "SPECS = {}\nSPECS['main'] = 'ch-rocker-arm'\n"
            "async def build(adapter):\n"
            "    await place_component(adapter, SPECS['main'], p, r, q)\n"
            "SPECS['main'] = 'fr-rocker-arm-support'\n",
            {"ch_rocker_arm", "fr_rocker_arm_support"},
        ),
        (
            "SPECS = {}\nSPECS['main'] = 'ch-rocker-arm'\n"
            "await place_component(adapter, SPECS['main'], p, r, q)\n"
            "SPECS['main'] = 'fr-rocker-arm-support'\n",
            {"ch_rocker_arm"},
        ),
        (
            "async def build(adapter):\n"
            "    specs = {}\n    specs['main'] = 'ch-rocker-arm'\n"
            "    await place_component(adapter, specs['main'], p, r, q)\n"
            "    specs['main'] = 'fr-rocker-arm-support'\n",
            {"ch_rocker_arm"},
        ),
        (
            "specs = {}\nspecs['main'] = 'ch-rocker-arm'\n"
            "specs['main'] = 'fr-rocker-arm-support'; "
            "await place_component(adapter, specs['main'], p, r, q)\n",
            {"ch_rocker_arm", "fr_rocker_arm_support"},
        ),
        (
            "specs = {}\nspecs['main'] = 'ch-rocker-arm'\n"
            "await place_component(adapter, specs['main'], p, r, q); "
            "specs['main'] = 'fr-rocker-arm-support'\n",
            {"ch_rocker_arm"},
        ),
    ],
)
def test_keyed_source_writes_respect_scope_and_statement_order(
    tmp_path, monkeypatch, source, expected
):
    assert (
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )
        == expected
    )


@pytest.fixture(
    params=[
        (
            "part = 'ch-rocker-arm'",
            "await place_component(adapter, part, p, r, q)",
            "part = 'fr-rocker-arm-support'",
        ),
        (
            "specs = {}; specs['main'] = 'ch-rocker-arm'",
            "await place_component(adapter, specs['main'], p, r, q)",
            "specs['main'] = 'fr-rocker-arm-support'",
        ),
        (
            "specs = [{'part': 'ch-rocker-arm'}]",
            "await place_components_batch(adapter, specs)",
            "specs.append({'part': 'fr-rocker-arm-support'})",
        ),
    ],
    ids=["name", "keyed-field", "manifest-append"],
)
def loop_source_form(request):
    return request.param


@pytest.mark.parametrize("loop", ["for index in (0, 1):", "while remaining:"])
def test_loop_carried_source_writes_keep_next_iteration_edges(
    tmp_path, monkeypatch, loop_source_form, loop
):
    initial, sink, mutation = loop_source_form
    source = (
        "async def build(adapter):\n"
        f"    {initial}\n"
        "    remaining = 2\n"
        f"    {loop}\n"
        f"        {sink}\n"
        f"        {mutation}\n"
        "        remaining -= 1\n"
    )
    assert _source_references(
        tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
    ) == {"ch_rocker_arm", "fr_rocker_arm_support"}


@pytest.mark.parametrize("loop", ["for index in (0, 1):", "while remaining:"])
def test_writes_after_loop_do_not_change_earlier_source_sink(
    tmp_path, monkeypatch, loop_source_form, loop
):
    initial, sink, mutation = loop_source_form
    source = (
        "async def build(adapter):\n"
        f"    {initial}\n"
        "    remaining = 2\n"
        f"    {loop}\n"
        f"        {sink}\n"
        "        remaining -= 1\n"
        f"    {mutation}\n"
    )
    assert _source_references(
        tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
    ) == {"ch_rocker_arm"}


@pytest.mark.parametrize(
    ("write_key", "read_key"),
    [("key", "'main'"), ("'main'", "key"), ("other_key", "key")],
)
def test_potentially_aliasing_keyed_source_writes_fail_closed(
    tmp_path, monkeypatch, write_key, read_key
):
    source = (
        "async def build(adapter):\n"
        "    specs = {}\n"
        "    key = 'main'\n"
        "    other_key = 'main'\n"
        f"    specs[{read_key}] = 'ch-rocker-arm'\n"
        f"    specs[{write_key}] = 'fr-rocker-arm-support'\n"
        f"    await place_component(adapter, specs[{read_key}], p, r, q)\n"
    )
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


def test_distinct_literal_keyed_writes_do_not_add_other_source(tmp_path, monkeypatch):
    source = (
        "async def build(adapter):\n"
        "    specs = {}\n"
        "    specs['main'] = 'ch-rocker-arm'\n"
        "    specs['other'] = 'fr-rocker-arm-support'\n"
        "    await place_component(adapter, specs['main'], p, r, q)\n"
    )
    assert _source_references(
        tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
    ) == {"ch_rocker_arm"}


def test_potential_key_alias_written_after_source_sink_is_not_available(
    tmp_path, monkeypatch
):
    source = (
        "async def build(adapter):\n"
        "    specs = {}\n"
        "    specs['main'] = 'ch-rocker-arm'\n"
        "    key = 'main'\n"
        "    await place_component(adapter, specs['main'], p, r, q)\n"
        "    specs[key] = 'fr-rocker-arm-support'\n"
    )
    assert _source_references(
        tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
    ) == {"ch_rocker_arm"}


@pytest.mark.parametrize(
    "mutation",
    [
        "specs |= {'main': 'fr-rocker-arm-support'}",
        "specs = runtime_sources()",
        "specs: dict = runtime_sources()",
    ],
    ids=["dict-union-assignment", "opaque-rebind", "annotated-opaque-rebind"],
)
def test_keyed_source_owner_mutation_or_unknown_rebind_fails_closed(
    tmp_path, monkeypatch, mutation
):
    source = (
        "async def build(adapter):\n"
        "    specs = {}\n"
        "    specs['main'] = 'ch-rocker-arm'\n"
        f"    {mutation}\n"
        "    await place_component(adapter, specs['main'], p, r, q)\n"
    )
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


@pytest.mark.parametrize(
    ("assignments", "expected"),
    [
        (
            "specs = {'main': 'ch-rocker-arm', 'unused': 'not-a-part'}\n"
            "specs['main'] = 'fr-rocker-arm-support'",
            {"ch_rocker_arm", "fr_rocker_arm_support"},
        ),
        (
            "specs = {}\n"
            "specs['main'] = 'ch-rocker-arm'\n"
            "specs = {'main': 'fr-rocker-arm-support', 'unused': 'not-a-part'}",
            {"ch_rocker_arm", "fr_rocker_arm_support"},
        ),
        (
            "specs = {'main': 'ch-rocker-arm', 'unused': 'not-a-part'}\n"
            "specs = {'main': 'fr-rocker-arm-support', 'unused': 'still-not-a-part'}\n"
            "specs['main'] = 'pn-pen-rod'",
            {"ch_rocker_arm", "fr_rocker_arm_support", "pn_pen_rod"},
        ),
        (
            "specs: dict = {'main': 'ch-rocker-arm', 'unused': 'not-a-part'}\n"
            "specs: dict = {'main': 'fr-rocker-arm-support', 'unused': 'still-not-a-part'}\n"
            "specs['main'] = 'pn-pen-rod'",
            {"ch_rocker_arm", "fr_rocker_arm_support", "pn_pen_rod"},
        ),
    ],
    ids=[
        "initial-literal",
        "rebound-literal",
        "initial-and-rebound",
        "annotated-literals",
    ],
)
def test_keyed_source_initial_and_rebound_literals_keep_matching_values(
    tmp_path, monkeypatch, assignments, expected
):
    source = (
        "async def build(adapter):\n"
        + "".join(f"    {line}\n" for line in assignments.splitlines())
        + "    await place_component(adapter, specs['main'], p, r, q)\n"
    )
    assert (
        _source_references(
            tmp_path,
            monkeypatch,
            source,
            ("ch_rocker_arm", "fr_rocker_arm_support", "pn_pen_rod"),
        )
        == expected
    )


def test_keyed_source_literal_initialization_ignores_distinct_literal_keys(
    tmp_path, monkeypatch
):
    source = (
        "async def build(adapter):\n"
        "    specs = {'main': 'ch-rocker-arm', 'unused': 'not-a-part'}\n"
        "    specs['other'] = 'also-not-a-part'\n"
        "    await place_component(adapter, specs['main'], p, r, q)\n"
    )
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


def test_generated_row_selection_preserves_prepared_source_provenance(
    tmp_path, monkeypatch
):
    source = (
        "async def build(adapter):\n"
        "    rows = make_rows()\n"
        "    for spec in rows:\n"
        "        spec['part'] = 'ch-rocker-arm'\n"
        "    spec = rows[index]\n"
        "    await place_component(adapter, spec['part'], p, r, q)\n"
    )
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


def test_keyed_field_loop_cannot_hide_actual_inserted_source(tmp_path, monkeypatch):
    import asyncio

    source = """async def build(adapter):
    specs = {"main": "ch-rocker-arm"}
    for specs["main"] in ("fr-rocker-arm-support",):
        await place_component(adapter, specs["main"], p, r, q)
"""
    consumed = []

    async def record(_adapter, part, *_args):
        consumed.append(part)

    namespace = {"place_component": record, "p": None, "r": None, "q": None}
    exec(source, namespace)
    asyncio.run(namespace["build"](None))
    assert consumed == ["fr-rocker-arm-support"]
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


@pytest.fixture(
    params=[
        "for specs['main'] in ('fr-rocker-arm-support',):\n    pass",
        "async for specs['main'] in runtime_rows():\n    pass",
        "for ignored, specs['main'] in runtime_rows():\n    pass",
        "ignored, specs['main'] = runtime_pair()",
        "with runtime_source() as specs['main']:\n    pass",
        "async with runtime_source() as specs['main']:\n    pass",
        "[None for specs['main'] in ('fr-rocker-arm-support',)]",
        "del specs['main']",
    ],
    ids=[
        "for",
        "async-for",
        "unpacked-for",
        "unpacked-assignment",
        "with",
        "async-with",
        "comprehension",
        "delete",
    ],
)
def unsupported_keyed_field_binding(request):
    return request.param


def test_unsupported_keyed_field_bindings_fail_closed(
    tmp_path, monkeypatch, unsupported_keyed_field_binding
):
    source = (
        "async def build(adapter):\n"
        "    specs = {'main': 'ch-rocker-arm'}\n"
        + "".join(
            f"    {line}\n" for line in unsupported_keyed_field_binding.splitlines()
        )
        + "    await place_component(adapter, specs['main'], p, r, q)\n"
    )
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


def test_unavailable_keyed_field_bindings_do_not_change_earlier_sink(
    tmp_path, monkeypatch, unsupported_keyed_field_binding
):
    source = (
        "async def build(adapter):\n"
        "    specs = {'main': 'ch-rocker-arm'}\n"
        "    await place_component(adapter, specs['main'], p, r, q)\n"
        + "".join(
            f"    {line}\n" for line in unsupported_keyed_field_binding.splitlines()
        )
    )
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


def test_different_keyed_field_bindings_leave_source_field_unchanged(
    tmp_path, monkeypatch, unsupported_keyed_field_binding
):
    source = (
        "async def build(adapter):\n"
        "    specs = {'main': 'ch-rocker-arm'}\n"
        + "".join(
            f"    {line}\n"
            for line in unsupported_keyed_field_binding.replace(
                "'main'", "'other'"
            ).splitlines()
        )
        + "    await place_component(adapter, specs['main'], p, r, q)\n"
    )
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


def test_later_keyed_field_loop_binding_can_reach_next_iteration(tmp_path, monkeypatch):
    source = (
        "async def build(adapter):\n"
        "    specs = {'main': 'ch-rocker-arm'}\n"
        "    for index in (0, 1):\n"
        "        await place_component(adapter, specs['main'], p, r, q)\n"
        "        for specs['main'] in ('fr-rocker-arm-support',):\n"
        "            pass\n"
    )
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


def test_keyed_source_loop_owner_cannot_hide_actual_inserted_source(
    tmp_path, monkeypatch
):
    import asyncio

    source = """async def build(adapter):
    specs = {"main": "ch-rocker-arm"}
    for specs in ({"main": "fr-rocker-arm-support"},):
        await place_component(adapter, specs["main"], p, r, q)
"""
    consumed = []

    async def record(_adapter, part, *_args):
        consumed.append(part)

    namespace = {"place_component": record, "p": None, "r": None, "q": None}
    exec(source, namespace)
    asyncio.run(namespace["build"](None))
    assert consumed == ["fr-rocker-arm-support"]
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


@pytest.fixture(
    params=[
        "for specs in ({'main': 'fr-rocker-arm-support'},):\n    pass",
        "async for specs in runtime_rows():\n    pass",
        "for ignored, specs in runtime_rows():\n    pass",
        "for ignored, (specs,) in runtime_rows():\n    pass",
        "ignored, specs = runtime_pair()",
        "ignored, (specs,) = runtime_pair()",
        "ignored, *specs = runtime_pair()",
        "with runtime_mapping() as specs:\n    pass",
        "async with runtime_mapping() as specs:\n    pass",
        "try:\n    raise RuntimeError\nexcept RuntimeError as specs:\n    pass",
        "import unknown_mapping as specs",
        "from unknown_module import mapping as specs",
        "def specs():\n    pass",
        "class specs:\n    pass",
        "match runtime_value:\n    case specs:\n        pass",
    ],
    ids=[
        "for",
        "async-for",
        "unpacked-for",
        "nested-for",
        "unpacked-assignment",
        "nested-assignment",
        "starred-assignment",
        "with",
        "async-with",
        "except",
        "import",
        "from-import",
        "function",
        "class",
        "match",
    ],
)
def opaque_mapping_owner_binding(request):
    return request.param


def test_keyed_source_opaque_owner_rebindings_fail_closed(
    tmp_path, monkeypatch, opaque_mapping_owner_binding
):
    source = (
        "async def build(adapter):\n"
        "    specs = {'main': 'ch-rocker-arm'}\n"
        + "".join(f"    {line}\n" for line in opaque_mapping_owner_binding.splitlines())
        + "    await place_component(adapter, specs['main'], p, r, q)\n"
    )
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


def test_keyed_source_unavailable_owner_rebindings_do_not_change_earlier_sink(
    tmp_path, monkeypatch, opaque_mapping_owner_binding
):
    source = (
        "async def build(adapter):\n"
        "    specs = {'main': 'ch-rocker-arm'}\n"
        "    await place_component(adapter, specs['main'], p, r, q)\n"
        + "".join(f"    {line}\n" for line in opaque_mapping_owner_binding.splitlines())
    )
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


def test_keyed_source_other_owner_bindings_do_not_change_unchanged_mapping(
    tmp_path, monkeypatch, opaque_mapping_owner_binding
):
    source = (
        "async def build(adapter):\n"
        "    specs = {'main': 'ch-rocker-arm'}\n"
        + "".join(
            f"    {line}\n"
            for line in opaque_mapping_owner_binding.replace(
                "specs", "other"
            ).splitlines()
        )
        + "    await place_component(adapter, specs['main'], p, r, q)\n"
    )
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


@pytest.mark.parametrize("argument", ["specs", "*specs", "**specs"])
def test_keyed_source_parameter_shadowing_cannot_reuse_module_initializer(
    tmp_path, monkeypatch, argument
):
    source = (
        "specs = {'main': 'ch-rocker-arm'}\n"
        f"async def build(adapter, {argument}):\n"
        "    await place_component(adapter, specs['main'], p, r, q)\n"
    )
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(tmp_path, monkeypatch, source)


def test_mapping_get_keeps_existing_literal_loop_owner_enumeration(
    tmp_path, monkeypatch
):
    source = (
        "for specs in ({'main': 'ch-rocker-arm'},):\n"
        "    await place_component(adapter, specs.get('main'), p, r, q)\n"
    )
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


def test_keyed_source_later_loop_owner_binding_can_reach_next_iteration(
    tmp_path, monkeypatch
):
    source = (
        "async def build(adapter):\n"
        "    specs = {'main': 'ch-rocker-arm'}\n"
        "    for index in (0, 1):\n"
        "        await place_component(adapter, specs['main'], p, r, q)\n"
        "        for specs in ({'main': 'fr-rocker-arm-support'},):\n"
        "            pass\n"
    )
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


def test_prepared_mapping_owner_cannot_be_rebound_by_another_loop(
    tmp_path, monkeypatch
):
    source = (
        "async def build(adapter):\n"
        "    rows = make_rows()\n"
        "    for spec in rows:\n"
        "        spec['part'] = 'ch-rocker-arm'\n"
        "    spec = rows[index]\n"
        "    for spec in ({'part': 'fr-rocker-arm-support'},):\n"
        "        pass\n"
        "    await place_component(adapter, spec['part'], p, r, q)\n"
    )
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "rows.append({'part': 'fr-rocker-arm-support'})",
        "mutate(rows)",
        "mutate(items=rows)",
        "alias = rows",
        "alias: list = rows",
        "rows = make_rows()",
        "rows[0]['part'] = 'fr-rocker-arm-support'",
        "mutate(rows[0])",
        "alias = rows[0]",
    ],
    ids=[
        "append",
        "opaque-consumer",
        "keyword-consumer",
        "alias",
        "annotated-alias",
        "rebind",
        "selected-field-write",
        "selected-opaque-consumer",
        "selected-alias",
    ],
)
def test_generated_row_selection_rejects_lost_collection_provenance(
    tmp_path, monkeypatch, mutation
):
    source = (
        "async def build(adapter):\n"
        "    rows = make_rows()\n"
        "    for spec in rows:\n"
        "        spec['part'] = 'ch-rocker-arm'\n"
        f"    {mutation}\n"
        "    spec = rows[index]\n"
        "    await place_component(adapter, spec['part'], p, r, q)\n"
    )
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


def test_late_global_keyed_source_write_cannot_hide_unknown_value(
    tmp_path, monkeypatch
):
    source = (
        "SPECS = {}\nSPECS['main'] = 'ch-rocker-arm'\n"
        "async def build(adapter):\n"
        "    await place_component(adapter, SPECS['main'], p, r, q)\n"
        "SPECS['main'] = runtime_part()\n"
    )
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(tmp_path, monkeypatch, source)


def test_later_module_manifest_appends_are_not_silently_lost(tmp_path, monkeypatch):
    source = """parts = []
async def build(adapter):
    await place_components_batch(adapter, parts)
parts.append({'part': 'ch-rocker-arm'})
"""
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


@pytest.mark.parametrize("separator", ["\n", "; "])
def test_manifest_appends_before_use_preserve_source_edges(
    tmp_path, monkeypatch, separator
):
    source = separator.join(
        [
            "parts = []",
            "parts.append({'part': 'ch-rocker-arm'})",
            "await place_components_batch(adapter, parts)",
        ]
    )
    assert _source_references(tmp_path, monkeypatch, source) == {"ch_rocker_arm"}


@pytest.mark.parametrize("separator", ["\n", "; "])
def test_manifest_appends_after_module_use_do_not_add_sources(
    tmp_path, monkeypatch, separator
):
    source = separator.join(
        [
            "parts = []",
            "await place_components_batch(adapter, parts)",
            "parts.append({'part': 'ch-rocker-arm'})",
        ]
    )
    assert _source_references(tmp_path, monkeypatch, source) == set()


@pytest.mark.parametrize("separator", ["\n", "; "])
@pytest.mark.parametrize(
    "mutation",
    [
        "alias = parts",
        "alias: list = parts",
        "mutate(parts)",
        "mutate(items=parts)",
        "parts.extend(runtime_parts())",
    ],
)
def test_manifest_mutations_before_use_fail_closed(
    tmp_path, monkeypatch, separator, mutation
):
    source = separator.join(
        [
            "parts = [{'part': 'ch-rocker-arm'}]",
            mutation,
            "await place_components_batch(adapter, parts)",
        ]
    )
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(tmp_path, monkeypatch, source)


@pytest.mark.parametrize(
    "source",
    [
        "specs = [{'part': 'ch-rocker-arm'}]\nmutate(items=specs)\nawait place_components_batch(adapter, specs)",
        "specs = [{'part': 'ch-rocker-arm'}]\nfor spec in specs:\n    spec['part']: str = 'fr-rocker-arm-support'\nawait place_components_batch(adapter, specs)",
        "specs = [{'part': 'ch-rocker-arm'}]\nfor spec in specs:\n    mutate(row=spec)\nawait place_components_batch(adapter, specs)",
        "memo = {'k': 'ch-rocker-arm'}\nalias = memo\nalias['k'] = 'fr-rocker-arm-support'\npart = memo.get(key)\nawait place_component(adapter, part, p, r, q)",
        "memo = {'k': 'ch-rocker-arm'}\nmutate(items=memo)\npart = memo.get(key)\nawait place_component(adapter, part, p, r, q)",
        "memo = {'k': 'ch-rocker-arm'}\nalias: dict = memo\nalias['k'] = 'fr-rocker-arm-support'\npart = memo.get(key)\nawait place_component(adapter, part, p, r, q)",
        "memo = alias = {'k': 'ch-rocker-arm'}\nalias['k'] = 'fr-rocker-arm-support'\npart = memo.get(key)\nawait place_component(adapter, part, p, r, q)",
        "specs = [{'part': 'ch-rocker-arm'}]\nfor spec in specs:\n    alias: dict = spec\n    alias['part'] = 'fr-rocker-arm-support'\nawait place_components_batch(adapter, specs)",
    ],
)
def test_review_keyword_and_annotated_mutations_never_drop_sources(
    tmp_path, monkeypatch, source
):
    with pytest.raises(ValueError, match=r"[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
        )


_SOURCE_VALUE_IMPORTS = {
    ("build_mg_magnifier_assembly", "build_sm_summing_assembly"): {
        "KNIFE",
        "KNIFE_CONTACT_Y",
    },
    ("build_pd_paper_drive_assembly", "build_dt_drive_train_assembly"): {
        "X_CRANK",
        "Y_CRANK",
    },
}


def _source_operation(name):
    return name in {
        "place_component",
        "place_components_batch",
        "InsertComponentParameters",
        "insert_component",
        "part_path",
    } or name.startswith("AddComponent")


def _source_operations(scan):
    operations = {}
    for node in ast.walk(scan.tree):
        if not isinstance(node, ast.Call) or not _source_operation(
            scan.call_name(node)
        ):
            continue
        owner = getattr(scan.scopes[node], "name", "<module>")
        operations.setdefault(owner, []).append((scan.call_name(node), node))
    # Callable aliases are source-bearing too; don't hide one behind `put = ...`.
    for node in ast.walk(scan.tree):
        name = node.id if isinstance(node, ast.Name) else getattr(node, "attr", "")
        if (
            name == "part_path"
            or not _source_operation(scan.aliases.get(name, name))
            or not isinstance(getattr(node, "ctx", None), ast.Load)
        ):
            continue
        parent = scan.parents.get(node)
        if isinstance(parent, ast.Call) and parent.func is node:
            continue
        owner = getattr(scan.scopes[node], "name", "<module>")
        operations.setdefault(owner, []).append(("indirect source callable", node))
    return operations


def _assignment_expressions(function, target):
    values = []
    for node in ast.walk(function):
        if not isinstance(
            node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)
        ):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(item, ast.Name) and item.id == target for item in targets):
            values.append(ast.unparse(node.value))
    return values


def _assert_canonical_source_passthrough(scan, operations):
    """Pin source-critical expressions, not unrelated placement/telemetry code."""
    assert {
        name: Counter(op for op, _ in calls) for name, calls in operations.items()
    } == {
        "place_component": Counter(
            {"insert_component": 1, "InsertComponentParameters": 1}
        ),
        "place_components_batch": Counter({"part_path": 1, "AddComponents3": 1}),
    }, "canonical assembly source operations changed"
    functions = {
        node.name: node
        for node in scan.tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    path_expression = "(OUT_SLDPRT / f'{part}.SLDPRT').resolve()"
    for name in ("part_path", "place_component"):
        function = functions[name]
        assert "part" in {arg.arg for arg in function.args.args}
        assert not any(
            isinstance(node, ast.Name)
            and node.id == "part"
            and isinstance(node.ctx, ast.Store)
            for node in ast.walk(function)
        ), name
        assert _assignment_expressions(function, "path") == [path_expression], name
        assert (
            sum(
                isinstance(node, ast.Name)
                and node.id == "path"
                and isinstance(node.ctx, ast.Store)
                for node in ast.walk(function)
            )
            == 1
        ), name
    path_returns = [
        ast.unparse(node.value)
        for node in ast.walk(functions["part_path"])
        if isinstance(node, ast.Return)
    ]
    assert path_returns == ["str(path)"]
    single = dict(operations["place_component"])
    assert (
        ast.unparse(scan.argument(single["InsertComponentParameters"], 0, "file_path"))
        == "str(path)"
    )
    assert (
        scan.argument(single["insert_component"], 0, "parameters")
        is single["InsertComponentParameters"]
    )

    batch = functions["place_components_batch"]
    assert batch.args.args[1].arg == "specs"
    assert _assignment_expressions(batch, "part") == ["spec['part']"]
    assert _assignment_expressions(batch, "names") == ["[]"]
    assert _assignment_expressions(batch, "names_arg") == [
        "VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, names)"
    ]
    name_calls = [
        node
        for node in ast.walk(batch)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "names"
    ]
    assert [ast.unparse(node) for node in name_calls] == [
        "names.append(str(part_path(part)))"
    ]
    source_append = scan.parents[name_calls[0]]
    assert isinstance(source_append, ast.Expr)
    part_write = next(
        node
        for node in ast.walk(batch)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "part"
            for target in node.targets
        )
    )
    source_loops = [
        node
        for node in batch.body
        if isinstance(node, ast.For)
        and part_write in node.body
        and source_append in node.body
    ]
    assert len(source_loops) == 1, "batch source and path must share one input-row loop"
    source_loop = source_loops[0]
    assert ast.unparse(source_loop.target) == "spec"
    assert ast.unparse(source_loop.iter) == "specs"
    assert source_loop.body.index(part_write) < source_loop.body.index(source_append)
    assert sum(
        isinstance(node, ast.Name)
        and node.id == "spec"
        and isinstance(node.ctx, ast.Store)
        for node in ast.walk(source_loop)
    ) == 1, "batch source row rebound inside path-construction loop"
    # Later member-selection/readback loops do not participate in physical paths.
    source_prefix = ast.Module(
        body=batch.body[:batch.body.index(source_loop) + 1], type_ignores=[],
    )
    source_nodes = set(ast.walk(source_prefix))
    assert not _assignment_expressions(source_prefix, "specs")
    assert not any(
        isinstance(node, ast.Name)
        and node.id == "specs"
        and isinstance(node.ctx, ast.Store)
        for node in source_nodes
    ), "batch input manifest rebound before path construction"
    for name, count in {
        "part": 1,
        "names": 1,
        "names_arg": 1,
    }.items():
        assert (
            sum(
                isinstance(node, ast.Name)
                and node.id == name
                and isinstance(node.ctx, ast.Store)
                for node in ast.walk(batch)
            )
            == count
        ), name
    for node in ast.walk(batch):
        source_variables = {"names", "names_arg"}
        if node in source_nodes:
            source_variables.update(("specs", "spec"))
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert not any(
                isinstance(target, (ast.Subscript, ast.Attribute))
                and any(
                    isinstance(item, ast.Name) and item.id in source_variables
                    for item in ast.walk(target)
                )
                for target in targets
            ), "batch source item mutation"
            assert (
                not isinstance(node.value, ast.Name)
                or node.value.id not in source_variables
            ), "batch source alias"
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ({"spec", "specs"} & source_variables)
        ):
            assert node.func.attr == "get", "batch source mutation method"
        if isinstance(node, ast.Call) and any(
            isinstance(arg, ast.Name) and arg.id in source_variables
            for arg in scan.arguments(node)
        ):
            name = scan.call_name(node)
            assert name in {"len", "VARIANT", "AddComponents3"}, (
                "opaque batch source consumer"
            )
            if name == "VARIANT":
                assert (
                    ast.unparse(node)
                    == "VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, names)"
                )
    native = dict(operations["place_components_batch"])["AddComponents3"]
    assert ast.unparse(native.args[0]) == "names_arg"


def _assert_source_import_contract(sources):
    """check:graph guard only: not a runtime/whole-program interpreter."""
    scans = {name: bg._AssemblySources(source) for name, source in sources.items()}
    operations = {name: _source_operations(scan) for name, scan in scans.items()}
    if "_assembly" in scans:
        _assert_canonical_source_passthrough(
            scans["_assembly"], operations["_assembly"]
        )
    providers = {name for name, values in operations.items() if values}
    for name, scan in scans.items():
        for node in ast.walk(scan.tree):
            if isinstance(node, ast.Import):
                forbidden = {alias.name for alias in node.names} & (
                    providers - {"_assembly"}
                )
                assert not forbidden, (
                    f"imported assembly source module: {name} -> {forbidden}"
                )
            if (
                not isinstance(node, ast.ImportFrom)
                or node.module not in providers
                or node.module == "_assembly"
            ):
                continue
            allowed = _SOURCE_VALUE_IMPORTS.get((name, node.module), set())
            assert {alias.name for alias in node.names} <= allowed, (
                f"imported assembly source helper: {name} -> {ast.unparse(node)}"
            )
            for alias in node.names:
                declaration = [
                    item
                    for item in scans[node.module].tree.body
                    if isinstance(item, (ast.Assign, ast.AnnAssign))
                    and any(
                        isinstance(target, ast.Name) and target.id == alias.name
                        for target in (
                            item.targets
                            if isinstance(item, ast.Assign)
                            else [item.target]
                        )
                    )
                ]
                assert len(declaration) == 1, (
                    f"constant-only source import changed: {alias.name}"
                )
                assert not any(
                    isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Name)
                    and item.func.id == (alias.asname or alias.name)
                    for item in ast.walk(scan.tree)
                ), f"source constant used as callable: {alias.name}"


def test_assembly_source_sinks_have_enforced_import_and_passthrough_contracts():
    paths = {script_for(stem) for stem in ASSEMBLY_ORDER}
    paths.update(
        Path(path)
        for stem in ASSEMBLY_ORDER
        for path in module_deps_of(script_for(stem))
    )
    _assert_source_import_contract(
        {path.stem: path.read_text(encoding="utf-8") for path in paths}
    )


def test_new_source_in_imported_helper_fails_even_when_old_manifest_still_matches(
    tmp_path, monkeypatch
):
    source = "from _extra import insert_extra\nawait place_component(adapter, 'ch-rocker-arm', p, r, q)\nawait insert_extra(adapter)"
    helper = "async def insert_extra(adapter):\n    await place_component(adapter, 'fr-rocker-arm-support', p, r, q)"
    # This is exactly the old coverage hole: the parent manifest alone stays A.
    assert _source_references(
        tmp_path, monkeypatch, source, ("ch_rocker_arm", "fr_rocker_arm_support")
    ) == {"ch_rocker_arm"}
    with pytest.raises(AssertionError, match="imported assembly source helper"):
        _assert_source_import_contract(
            {"build_parent_assembly": source, "_extra": helper}
        )


@pytest.mark.parametrize(
    "metadata",
    [
        "    for spec in specs:\n        spec.get('configuration')\n",
        "    any(spec.get('component_reference') for spec in specs)\n",
        (
            "    for spec, name in zip(specs, out_names, strict=True):\n"
            "        spec.get('configuration')\n"
            "        spec.get('component_reference')\n"
        ),
    ],
)
def test_batch_source_proof_ignores_later_readonly_member_metadata_loops(metadata):
    source = (SCRIPTS_DIR / "_assembly.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "place_components_batch"
    ]
    assert len(functions) == 1
    metadata_function = ast.parse("async def readonly_metadata():\n" + metadata).body[0]
    functions[0].body.extend(metadata_function.body)
    _assert_source_import_contract({"_assembly": ast.unparse(tree)})


@pytest.mark.parametrize(
    "change",
    [
        "new helper",
        "single source",
        "batch source",
        "batch row mutation",
        "batch source row rebinding",
        "batch source iterator",
        "batch separate source loops",
        "single loop binding",
        "single path loop binding",
        "batch keyword consumer",
        "batch variant property",
    ],
)
def test_canonical_assembly_is_not_a_blanket_source_exemption(change):
    source = (SCRIPTS_DIR / "_assembly.py").read_text(encoding="utf-8")
    if change == "new helper":
        source += "\nasync def insert_extra(adapter):\n    await place_component(adapter, 'fr-rocker-arm-support', p, r, q)\n"
    if change == "single source":
        source = source.replace(
            "file_path=str(path)", 'file_path="fr-rocker-arm-support.SLDPRT"'
        )
    if change == "batch source":
        source = source.replace('part = spec["part"]', 'part = "fr-rocker-arm-support"')
    if change == "batch row mutation":
        source = source.replace(
            'part = spec["part"]',
            'spec["part"] = "fr-rocker-arm-support"\n        part = spec["part"]',
        )
    if change == "batch source row rebinding":
        marker = '        part = spec["part"]'
        assert source.count(marker) == 1
        source = source.replace(
            marker,
            '        spec = {"part": "fr-rocker-arm-support"}\n' + marker,
            1,
        )
    if change == "batch source iterator":
        marker = '    for spec in specs:\n        part = spec["part"]'
        assert source.count(marker) == 1
        source = source.replace(
            marker,
            '    for spec in unrelated_specs:\n        part = spec["part"]',
            1,
        )
    if change == "batch separate source loops":
        marker = "        names.append(str(part_path(part)))"
        assert source.count(marker) == 1
        source = source.replace(
            marker, "    for spec in specs:\n" + marker, 1,
        )
    if change == "single loop binding":
        source = source.replace(
            "label = label or part",
            'for part in ["fr-rocker-arm-support"]:\n        pass\n    label = label or part',
        )
    if change == "single path loop binding":
        source = source.replace(
            "        if not path.exists():",
            '        for path in [Path("fr-rocker-arm-support.SLDPRT")]:\n            pass\n        if not path.exists():',
            1,
        )
    if change == "batch keyword consumer":
        source = source.replace(
            "    xforms_arg = VARIANT",
            "    mutate(var=names_arg)\n    xforms_arg = VARIANT",
        )
    if change == "batch variant property":
        source = source.replace(
            "    xforms_arg = VARIANT",
            '    names_arg.value = ["fr-rocker-arm-support.SLDPRT"]\n    xforms_arg = VARIANT',
        )
    with pytest.raises(AssertionError):
        _assert_source_import_contract({"_assembly": source})


def test_references_is_inverse_of_dependents():
    """``references_of`` is the DIRECT inverse of the legacy ``dependents_of``.

    ``dependents_of`` adds a transitive ``harmonic_analyzer`` edge whenever a part
    flows into any sub-assembly (the old --rebuild's "rebuild the top too"). The
    doit graph propagates that through ``<sub>.SLDASM -> ha-harmonic-analyzer.SLDASM``
    instead, so ``references_of`` carries only direct edges. The two must agree
    exactly once that documented transitive add is accounted for.
    """
    candidates = part_stems() + list(ASSEMBLY_ORDER)
    references = {a: set(references_of(a)) for a in ASSEMBLY_ORDER}
    for s in candidates:
        direct = {a for a in ASSEMBLY_ORDER if s in references[a]}
        legacy = set(dependents_of(s))
        # Only a machine sub flows up to the top; a shop-fixture jig never does.
        machine_direct = {a for a in direct if not bg.is_shop_fixture(a)}
        if machine_direct and "ha_harmonic_analyzer" not in direct:
            assert legacy == direct | {"ha_harmonic_analyzer"}, (
                f"{s}: legacy {legacy} != direct {direct} + transitive top"
            )
        else:
            assert legacy == direct, f"{s}: legacy {legacy} != direct {direct}"


def test_output_subs_reference_their_parts_only():
    """Each output sub inserts leaf parts, never another sub-assembly."""
    for stem in ("sm_summing", "mg_magnifier", "pn_pen", "pd_paper_drive", "ms_measuring_stick"):
        refs = references_of(stem)
        assert refs, f"{stem} should reference its parts"
        parts = set(part_stems())
        assert set(refs) <= parts, f"{stem} references non-parts: {set(refs) - parts}"
        assert not (set(refs) & set(ASSEMBLY_ORDER)), (
            f"{stem} must not reference a sub-assembly"
        )


def test_top_references_only_subassemblies():
    """harmonic-analyzer mates the eight subs and no loose part: the measuring
    stick and its clamped stop moved into their own ms-measuring-stick sub
    (2026-10-09), so nothing stands directly on the base any more. The spare
    transgear-removable rides inside paper-drive (a flat sibling of its mounted
    T24), not here -- at the top level its leaf name would collide with the
    T12/T24 instances nested in drive-train / paper-drive."""
    refs = set(references_of("ha_harmonic_analyzer"))
    subs = set(bg.MACHINE_ASSEMBLIES) - {"ha_harmonic_analyzer"}
    assert len(subs) == 8
    assert refs == subs, refs
    assert not (refs & set(part_stems())), refs & set(part_stems())


def test_leaf_parts_do_not_depend_on_assembly_helpers():
    """Assembly-only placement/reference edits must not re-key any leaf part."""
    for stem in part_stems():
        helpers = _helper_names(f"build_{stem}.py")
        assert "_assembly" not in helpers, f"{stem} wrongly depends on _assembly"
        assert "_transforms" not in helpers, f"{stem} wrongly depends on _transforms"
        assert "_component_references" not in helpers, (
            f"{stem} wrongly depends on assembly component references"
        )
        assert "_session" in helpers, f"{stem} lost its _session dependency"


def test_assemblies_depend_on_assembly_helpers():
    """The focused reference helper joins the fleet through core assembly placement."""
    for stem in ASSEMBLY_ORDER:
        helpers = _helper_names(script_for(stem).name)
        assert {"_assembly", "_session", "_component_references"} <= helpers, (
            f"{stem}: {helpers}"
        )


@pytest.mark.parametrize(
    ("helper", "consumers"),
    [
        (
            "_assembly_patterns",
            {
                "ch_channel",
                "dt_drive_train",
                "fr_frame",
                "mg_magnifier",
                "pd_paper_drive",
                "ms_measuring_stick",
                "pn_pen",
                "sm_summing",
                # its explode selects the global axes (_ha_harmonic_analyzer_explode)
                "ha_harmonic_analyzer",
                "ch_rocker_arm_tl_oblique_jig",
            },
        ),
        ("_assembly_couplings", {"dt_drive_train", "pd_paper_drive"}),
        # paper_drive reads its crank axis from cone_line, not the builder.
        ("_dt_drive_train_explode", {"dt_drive_train"}),
    ],
)
def test_specialized_assembly_helpers_have_exact_transitive_consumers(
    helper, consumers
):
    actual = {
        stem
        for stem in ASSEMBLY_ORDER
        if helper in _helper_names(script_for(stem).name)
    }
    assert actual == consumers
    assert helper not in _helper_names("_assembly.py"), (
        "core must not re-export specialized helpers and reconnect all recipes"
    )
    for stem in part_stems():
        assert helper not in _helper_names(f"build_{stem}.py"), stem


def test_cone_line_consumers_do_not_import_the_drive_train_script():
    """The base's pivot seat and the paper-drive crank sprocket read the pure
    cone_line module; importing build_drive_train_assembly instead would put the
    whole drive-train recipe on their cache keys (#880)."""
    for script in ("build_fr_harmonic_base.py", "build_pd_paper_drive_assembly.py"):
        deps = _helper_names(script)
        assert "cone_line" in deps, script
        assert "build_dt_drive_train_assembly" not in deps, script


def test_swing_platform_consumers_read_geometry_not_the_builder():
    """The base and the drive train read the platform's plan geometry, not its
    builder or its print data: a sketch, precision or caption edit on MHA-DT-20
    re-keys the platform and its sheet only (#880)."""
    builder = _helper_names("build_dt_cone_swing_platform.py")
    assert {"dt_cone_swing_platform_geometry", "dt_cone_swing_platform_drawing_spec"} <= builder
    for script in ("build_fr_harmonic_base.py", "build_dt_drive_train_assembly.py"):
        deps = _helper_names(script)
        assert "dt_cone_swing_platform_geometry" in deps, script
        assert "build_dt_cone_swing_platform" not in deps, script
        assert "dt_cone_swing_platform_drawing_spec" not in deps, script




# Direct imports of one build script by another, grandfathered at #880 and
# owned by the follow-up that burns them down.  Importing a BUILDER puts its
# whole recipe (sketch code, drawing marks, the config it reads) on the
# importer's cache key; the numbers belong in the part's pure spec.  The list
# only shrinks: an unlisted edge fails, and so does a listed edge that no longer
# exists.  Each entry is "<owner>: <what it reads>".
_GRANDFATHERED_BUILDER_EDGES = {
    ("build_dt_drive_train_assembly.py", "build_dt_arbor_pedestal"): (
        "dtrefactor: reads FOOT_HEIGHT, FOOT_WIDTH, SCREW_Z"
    ),
    ("build_dt_drive_train_assembly.py", "build_dt_cone_pivot_post"): (
        "dtrefactor: reads BORE_HEIGHT, CONE_BOSS_LENGTH, CRANK_BORE_HEIGHT, CRANK_BOSS_LENGTH, CRANK_BOSS_START_Z"
    ),
    ("build_dt_drive_train_assembly.py", "build_dt_crankshaft"): (
        "dtrefactor: reads PINION_PIN_STATION_Y, SEAT_PINION, SHAFT_LENGTH"
    ),
    ("build_dt_drive_train_assembly.py", "build_fr_harmonic_base"): (
        "dtrefactor: reads BLOCK_SCREW_XZ, BLOCK_SEAT_SPEC, FOOT_SCREW_XZ, FOOT_SEAT_SPEC, LOCK_KNOB_XZ, LOCK_SEAT_SPEC, LOCK_STUD_ENGAGEMENT, PEDESTAL_SCREW_XZ, PEDESTAL_SEAT_SPEC, PIVOT_SCREW_XZ, PIVOT_SEAT_SPEC, STOP_SCREW_XZ, STOP_SEAT_SPEC, SWING_HARDWARE_GEOMETRY; finite through-seat material and engagement from fr_harmonic_base_fasteners"
    ),
    ("build_fr_frame_assembly.py", "build_fr_top_frame"): (
        "dtrefactor: reads SIDE_TAP_SPEC"
    ),
    ("build_kinematic_probe.py", "build_pd_paper_drive_assembly"): (
        "dtrefactor: reads CHAIN_CRANK_CENTRE, DISC_TEETH, FEED_PD, KNOB_SHAFT_XY, NET_RACK_TRAVEL_PER_CRANK_REV, SPARE_GEAR_POS, THIRD_TEETH"
    ),
    ("build_mobility_probe.py", "build_motion_study"): (
        "dtrefactor: reads ANGLE, DISTANCE, _family, _iter_mates, _real_parts"
    ),
    ("build_motion_setup_drives.py", "build_motion_study"): (
        "dtrefactor: reads ANGLE, DISTANCE, _comp_xform, _entity_ref, _family, _find_one, _iter_mates, _real_parts, _reset_to_assembled, _rot_angle, assert_motion_progressed"
    ),
    ("build_motion_study.py", "build_motion_study_springs"): (
        "dtrefactor: reads add_springs, add_wires_gravity"
    ),
    ("build_motion_study_springs.py", "build_motion_study"): (
        "dtrefactor: reads ANGLE, DISTANCE, SPRING_KCH, SPRING_KCT, STOCK_KCH, STOCK_KCT, _by_z_rank, _components, _entity_ref, _family, _find_one, _iter_mates, _lone_real, _read_member, _sub_model, _suppress_named"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_guide_lock"): (
        "dtrefactor: reads HOLE_DIA, LOCK_THICK, LOCK_WIDTH"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_platen_clip"): (
        "dtrefactor: reads CLIP_LENGTH, CLIP_THICKNESS, HOLE_DIA, HOLE_INSET, HOLE_Y"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_platen_guide"): (
        "dtrefactor: reads GUIDE_DEPTH, GUIDE_HEIGHT, GUIDE_LENGTH, GUIDE_SCREW_BOTTOM_CLEARANCE, GUIDE_SCREW_PASSAGE, GUIDE_SCREW_THREAD_ENGAGEMENT, HOLE_X, LOCK_SCREW_PASSAGE, LOCK_SCREW_THREAD_ENGAGEMENT, LOCK_SCREW_TIP_INSIDE_MIN, LOCK_STATION_X, SCREW_STATION_X"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_support_bar"): (
        "dtrefactor: reads BAR_HEIGHT, CLAMP_CBORE_DEPTH, CLAMP_CBORE_DIA, CLAMP_HEAD_RECESS, CLAMP_HOLE_DIA, CLAMP_HOLE_X"
    ),
    ("build_sm_summing_assembly.py", "build_sm_knife_mount"): (
        "dtrefactor: reads CASTING_UNDERSIDE_Y, MOUNT_GAP"
    ),
}
# Entry tools that open built models and therefore import their builders; they
# are run, never imported by a build recipe's pure helpers.
_ENTRY_TOOLS = frozenset({"verify.py", "preflight_release.py"})


def _direct_builder_edges() -> set[tuple[str, str]]:
    """(importer, imported) for every build script importing another, anywhere
    in the file (top level or lazily)."""
    edges: set[tuple[str, str]] = set()
    for path in sorted(SCRIPTS_DIR.glob("build_*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            edges.update((path.name, n) for n in names if n.startswith("build_"))
    return edges


def _library_modules() -> list[Path]:
    """Every module a build or drawing recipe imports that is not itself an
    entry script: specs, geometry, layouts, helpers, interference contracts."""
    entries = sorted([*SCRIPTS_DIR.glob("build_*.py"), *SCRIPTS_DIR.glob("draw_*.py")])
    library = {
        Path(dep)
        for entry in entries
        for dep in module_deps_of(entry)
        if not Path(dep).name.startswith(("build_", "draw_", "test_"))
        and Path(dep).name not in _ENTRY_TOOLS
    }
    return sorted(library)


def _reached_builders(path: Path) -> list[str]:
    """``build_*`` modules in ``path``'s transitive import closure, itself excluded."""
    return sorted(
        Path(dep).stem
        for dep in module_deps_of(path)
        if Path(dep).name.startswith("build_") and Path(dep).stem != path.stem
    )


def test_library_modules_reach_no_builder():
    """#880: a spec, geometry, layout, helper or interference-contract module
    reaches no build script, however indirectly.  There is no allowance: the
    numbers a sibling needs move into the part's pure spec."""
    library = _library_modules()
    names = {path.name for path in library}
    assert {"fr_harmonic_base_fasteners.py", "_interference_contracts.py"} <= names
    assert {
        "dt_cone_swing_platform_geometry.py", "sh_vn_brass_fillister_screw_spec.py",
    } <= names
    reached = {
        path.name: builders for path in library if (builders := _reached_builders(path))
    }
    assert not reached, f"read the part's spec, not its builder: {reached}"


def test_a_builder_import_in_a_pure_module_goes_red(tmp_path):
    """Fail-first for the guard above: a synthetic spec that imports a builder
    is caught through the same closure the build graph uses."""
    planted = tmp_path / "planted_spec.py"
    planted.write_text(
        "from build_sh_vn_fillister_screw_90280a108 import THREAD\n",
        encoding="utf-8",
    )
    assert _reached_builders(planted) == ["build_sh_vn_fillister_screw_90280a108"]
    clean = tmp_path / "clean_spec.py"
    clean.write_text(
        "from sh_vn_fillister_screw_90280a108_spec import THREAD\n",
        encoding="utf-8",
    )
    assert _reached_builders(clean) == []


def test_builder_to_builder_edges_only_shrink():
    """Every direct build-script edge is listed with its owner and reason; a new
    one fails, and a listed one that is gone must be deleted."""
    found = _direct_builder_edges()
    listed = set(_GRANDFATHERED_BUILDER_EDGES)
    assert not found - listed, f"new builder imports; read a spec: {sorted(found - listed)}"
    assert not listed - found, f"edges gone; delete them: {sorted(listed - found)}"
    for edge, note in _GRANDFATHERED_BUILDER_EDGES.items():
        owner, _, reason = note.partition(": ")
        assert owner and reason.strip(), edge


def test_part_builders_reach_no_other_part_builder():
    """#880: the part-to-part edges on the assembly re-key path are burned down;
    a part builder reads a sibling's numbers from its spec."""
    parts = [path for path in bg.part_scripts() if not path.name.endswith("_assembly.py")]
    reached = {
        path.name: builders for path in parts if (builders := _reached_builders(path))
    }
    assert not reached, reached

def test_module_deps_are_transitive():
    """The closure follows imports through helper chains: a chain-link part pulls
    _chain_link -> _part_save -> _part_properties, and _config arrives via
    _part_properties' lazy import (registry-driven properties stay tracked)."""
    links = _helper_names("build_sh_vn_chain_link.py")
    assert {"_chain_link", "_chain", "_part_save", "_part_properties"} <= links, links
    assert "_config" in _helper_names("build_dt_vn_cone_tip_collar.py"), (
        "lazy _config edge lost"
    )


def test_swing_stop_stock_builder_does_not_reach_receiver_validation():
    """Track stock authority without re-keying the native screw for base edits."""
    stock_authorities = {"sh_vn_fillister_screw_90280a108_spec"}
    receiver_inputs = {
        "fr_harmonic_base_fasteners",
        "fr_harmonic_base_spec",
        "dt_swing_stop_screw_spec",
    }
    native = _helper_names("build_sh_vn_fillister_screw_90280a108.py")
    assert stock_authorities <= native, native
    assert native.isdisjoint(receiver_inputs), native & receiver_inputs

    # Receiver validation remains a real assembly input, not a graph exclusion.
    assembly = _helper_names("build_dt_drive_train_assembly.py")
    assert stock_authorities | receiver_inputs <= assembly, assembly


def test_specialized_helper_blast_radius_is_narrow():
    """_gear reaches only its real importers, not the fleet."""
    gear_users = [s for s in part_stems() if "_gear" in _helper_names(f"build_{s}.py")]
    feat_users = [
        s for s in part_stems() if "_features" in _helper_names(f"build_{s}.py")
    ]
    assert 0 < len(gear_users) < len(part_stems()), gear_users
    # spring/screw/nameplate feature builders reach only their handful of parts
    # (their direct importers + any part that reuses one of those build scripts)
    assert 0 < len(feat_users) <= 8, feat_users


def test_data_deps_of_nameplate_lists_engraving_dxf():
    """The nameplate build's imported DXF is a data dependency of the part."""
    deps = data_deps_of(SCRIPTS_DIR / "build_fr_nameplate.py")
    assert any(d.endswith("fr-nameplate-engraving.dxf") for d in deps), deps
    # A build that imports no DXF/DWG has no data deps.
    assert data_deps_of(SCRIPTS_DIR / "build_pd_platen.py") == []


def test_data_deps_of_keeps_missing_referenced_artefact():
    """A referenced DXF is listed even when absent, so doit fails loud on it
    (a deleted runtime input must not read as up-to-date)."""
    missing_name = "does-not-exist-xyz.dxf"
    assert not (REFERENCES_DIR / missing_name).exists()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", dir=SCRIPTS_DIR, delete=False
    ) as fh:
        fh.write(f'PATH = REFERENCES_DIR / "{missing_name}"\n')
        script = Path(fh.name)
    try:
        deps = data_deps_of(script)
        assert [Path(d).name for d in deps] == [missing_name], deps
    finally:
        script.unlink()


def test_data_deps_of_follows_a_same_tick_rewrite():
    """Source texts are memoized per process, but an edit must still move the
    graph: once the script names new.dxf, a stale old.dxf edge would leave the
    real input out of the cache key. Same-length names AND a pinned identical
    mtime reproduce two writes landing in one file-time tick (~15.6 ms on
    Windows), where (mtime_ns, size) cannot tell the texts apart; this raced
    on the farm (run 20260928T124706229Z)."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", dir=SCRIPTS_DIR, delete=False
    ) as fh:
        fh.write('PATH = REFERENCES_DIR / "old-xyz.dxf"\n')
        script = Path(fh.name)
    tick = (time.time_ns(),) * 2
    try:
        os.utime(script, ns=tick)
        assert [Path(d).name for d in data_deps_of(script)] == ["old-xyz.dxf"]
        script.write_text('PATH = REFERENCES_DIR / "new-xyz.dxf"\n', encoding="utf-8")
        os.utime(script, ns=tick)
        assert [Path(d).name for d in data_deps_of(script)] == ["new-xyz.dxf"]
    finally:
        script.unlink()


def _tokens(text: str) -> frozenset[str]:
    """Run ``_config_tokens_in_source`` on an inline source snippet (single file)."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(text)
        path = Path(fh.name)
    try:
        return bg._config_tokens_in_source(path)
    finally:
        path.unlink()


def test_config_files_no_part_reads_dimensions():
    """The 98 KB narrative dimensions.yaml is read by NO part/assembly build
    script (only the offline DIMENSIONS gate touches it), so the fine-grained
    dependency must never list it -- editing dimensions.yaml rebuilds nothing."""
    for stem in part_stems():
        assert "dimensions.yaml" not in config_files_of(
            SCRIPTS_DIR / f"build_{stem}.py"
        ), stem
    for stem in ASSEMBLY_ORDER:
        assert "dimensions.yaml" not in config_files_of(script_for(stem)), stem


def test_config_files_track_real_reads():
    """Track actual reads at sub-file granularity, without inheriting world
    placement for a part-local pitch. Cone face width needs gear_train and
    cone_incline; its stamped mesh screen also needs tolerances. Neither needs
    channels.active_count or station_z0. Assemblies that place channel stations
    do read that grid; every part also needs its registry via _part_properties."""
    cone = config_files_of(SCRIPTS_DIR / "build_dt_cone_gear.py")
    assert "machine/gear_train.yaml" in cone
    assert "machine/cone_incline.yaml" in cone, "face width follows the cone seat pitch"
    assert "tolerances/cone_drum_oblique_mesh.yaml" in cone, (
        "stamped mesh screen uses edge slack/journal float"
    )
    assert "machine/channels.yaml" not in cone, (
        "gear must NOT depend on active_count's file"
    )
    assert "parts/*" in cone, "stamps its own properties -> parts registry token"
    assert "channels.yaml" in config_files_of(script_for("dt_drive_train"))
    assert "channels.yaml" in config_files_of(script_for("ch_channel"))
    assert config_files_of(SCRIPTS_DIR / "cone_pitch.py") == frozenset(
        {"machine/gear_train.yaml", "machine/cone_incline.yaml"}
    )
    cone_modules = {
        Path(path).name
        for path in module_deps_of(SCRIPTS_DIR / "build_dt_cone_gear.py")
    }
    assert "cone_pitch.py" in cone_modules
    assert "cone_line.py" not in cone_modules, (
        "part-local data must not import world datums"
    )


def test_config_files_subset_of_known_tokens():
    """Every real script resolves to known tokens (concrete files that exist, or
    the machine/* | tolerances/* | parts/* | title_block | ** dynamic tokens). The set can only
    NARROW the old whole-config dep, never invent a missing-file dependency."""
    globs = {"machine/*", "tolerances/*", "parts/*", "title_block", "**", bg.ASSEMBLY_CONTRACTS_TOKEN}
    scripts = [
        *bg.part_scripts(),
        *(script_for(stem) for stem in ASSEMBLY_ORDER),
        *SCRIPTS_DIR.glob("draw_*.py"),
        SCRIPTS_DIR / "export_features.py",
    ]
    for script in scripts:
        for tok in config_files_of(script):
            assert tok in globs or (bg.CONFIG_DIR / tok).is_file(), f"{script.name}: {tok}"


def test_config_files_conservative_on_unknown_use():
    """CORRECTNESS > speed: any _config use we can't classify -- an unmapped
    accessor, an unresolvable provenance/_doc doc arg, or a bare-name import --
    must raise so the caller falls back to the WHOLE config (never
    under-invalidate). Note machine()/parts() with a dynamic arg are NOT errors:
    they widen to the whole family (machine/* | parts/*), still conservative."""
    raise_cases = [
        "import _config\nx = _config.frobnicate()\n",  # unmapped accessor
        "import _config\nd = 'machine'\nx = _config._doc(d)\n",  # dynamic doc arg
        "import _config\nx = _config.provenance(name)\n",  # dynamic provenance
        "import _config\nf = _config._doc\n",  # family accessor, not a literal call
        "import _config\nx = _config._doc('nope')\n",  # literal but unknown doc
        "import _config\nx = _config.machine('no_such_sub')\n",  # unknown machine subsystem
        "from _config import machine\nx = machine()\n",  # bare-name import (untracked)
    ]
    for src in raise_cases:
        try:
            _tokens(src)
        except bg._UnknownConfigUse:
            continue
        raise AssertionError(f"expected _UnknownConfigUse for: {src!r}")


def test_config_files_resolve_known_forms():
    """The classifiable forms resolve to exactly the right file token(s)."""
    assert _tokens(
        "import _config\nx = _config.machine('gear_train', 'k')\n"
    ) == frozenset({"machine/gear_train.yaml"})
    assert _tokens("import _config\nx = _config.active_count()\n") == frozenset(
        {"machine/channels.yaml"}
    )
    assert _tokens("import _config\nx = _config.fit('gear_mesh', 'k')\n") == frozenset(
        {"tolerances/gear_mesh.yaml"}
    )
    assert _tokens("import _config\nx = _config.release_revision()\n") == frozenset(
        {"release.yaml"}
    )
    assert _tokens("import _config\nx = _config.channels()\n") == frozenset(
        {"channels.yaml"}
    )
    assert _tokens("import _config\nx = _config._doc('tolerances')\n") == frozenset(
        {"tolerances/*"}
    )
    for expression in (
        "fit(group, 'k')",
        "fit('unknown', 'k')",
        "fit",
        "fit(group='gear_mesh')",
    ):
        assert _tokens(f"import _config\nx = _config.{expression}\n") == frozenset(
            {"tolerances/*"}
        )
    with pytest.raises(bg._UnknownConfigUse):
        _tokens("import _config\nx = _config.tolerances()\n")
    # a dynamic machine/parts arg widens to the whole family (conservative, not an error).
    assert _tokens("import _config\nx = _config.machine(sub, 'k')\n") == frozenset(
        {"machine/*"}
    )
    assert _tokens("import _config\nx = _config.parts(name)\n") == frozenset(
        {"parts/*"}
    )
    # an aliased module import is still tracked.
    assert _tokens("import _config as cfg\nx = cfg.machine('output')\n") == frozenset(
        {"machine/output.yaml"}
    )
    # no _config use at all -> empty read-set (no config dependency).
    assert _tokens("WIDTH = 3.0\n") == frozenset()


@pytest.mark.parametrize(
    "source",
    [
        "import _config\nx = getattr(_config, name)\n",
        "import _config\nx = helper(_config)\n",
        "import _config as cfg\nx = helper(cfg)\n",
        "import _config\ncfg = _config\nx = cfg.machine('output')\n",
        "import _config\nx = [_config]\n",
        "import _config\nx = _config.fit('g', 'k')\ny = helper(_config)\n",
    ],
)
def test_bare_config_module_references_fail_closed(monkeypatch, tmp_path, source):
    """An escaped module can read any config, including beside known accessors."""
    script = tmp_path / "build_config_escape.py"
    script.write_text(source, encoding="utf-8")
    monkeypatch.setattr(bg, "module_deps_of", lambda _: ())
    bg.config_files_of.cache_clear()
    try:
        assert bg.config_files_of(script) == frozenset({"**"})
        with pytest.raises(bg._UnknownConfigUse):
            bg._config_tokens_in_source(script)
    finally:
        bg.config_files_of.cache_clear()


def test_config_accessor_coverage():
    """Every accessor defined in _config.py is classified here (fixed-file or
    family). A new accessor added without an entry reads as 'unknown' and falls
    back to the whole config -- safe, but this test fails loud so the perf benefit
    is restored deliberately, not lost silently."""
    import inspect

    import _config

    accessors = {
        name
        for mod in (_config,)
        for name, fn in inspect.getmembers(mod, inspect.isfunction)
        if fn.__module__ == mod.__name__
        and not name.startswith("__")
        and name != "_load"
    }
    classified = set(bg._FIXED_ACCESSOR_TOKENS) | set(bg._FAMILY_ACCESSORS)
    missing = accessors - classified
    assert not missing, (
        f"unclassified config accessors (map them in _buildgraph): {missing}"
    )


def test_pen_assembly_free_of_pen_driver_closure():
    """Post-#221: the park-driver machinery is gone -- build_pen_assembly no longer
    imports pen_driver/truth_model, since the F5 chained-Fourier equation is now
    authored TRANSIENTLY by verify:kinematics (see dodo.task_verify's kinematics
    file_dep) rather than baked into the saved assembly. The build recipe must NOT
    drag pen_driver/truth_model (and their channels.yaml/machine/output.yaml reads)
    back into module_deps_of/config_files_of -- that would rebuild assembly:pn_pen on
    every amplitude edit for an equation the saved model does not even contain. The
    guard for the transient equation moved to dodo.task_verify's kinematics
    file_dep (pinned in test_dodo_recipe.py)."""
    closure = {Path(p).stem for p in module_deps_of(script_for("pn_pen"))}
    assert closure.isdisjoint({"pen_driver", "truth_model"}), closure
    pen_cfg = config_files_of(script_for("pn_pen"))
    assert "machine/output.yaml" not in pen_cfg, pen_cfg
    assert "channels.yaml" not in pen_cfg, pen_cfg


def test_module_deps_follow_non_helper_siblings():
    """POSITIVE direction of the traversal the retired pen test used to exercise
    (codex #224): ``module_deps_of`` must follow ORDINARY sibling modules, not just
    the ``_*``/``build_*`` helpers, and ``config_files_of`` must see the config
    reads behind them -- else a script importing a non-helper module would silently
    drop its Python/config deps. Real chain: pen_driver imports truth_model (both
    plain siblings), which reads machine/output + channels through _config."""
    closure = {Path(p).stem for p in module_deps_of(SCRIPTS_DIR / "pen_driver.py")}
    assert "truth_model" in closure, closure
    cfg = config_files_of(SCRIPTS_DIR / "pen_driver.py")
    assert "machine/output.yaml" in cfg, cfg
    assert "channels.yaml" in cfg, cfg


def test_module_deps_follow_dotted_package_recipe_chain(tmp_path, monkeypatch):
    """A production-style dotted wrapper import reaches the exact recipe module
    and its transitive package helper, rather than stopping at ``diagnostics``.

    The temporary scripts root keeps this independent of fastener-wrapper rollout
    order while exercising real package files and both supported dotted-import
    forms.  An external import must not be traversed.
    """
    scripts = tmp_path / "scripts"
    diagnostics = scripts / "diagnostics"
    diagnostics.mkdir(parents=True)
    wrapper = scripts / "build_ch_vn_frame_side_screw.py"
    package_init = diagnostics / "__init__.py"
    entry = diagnostics / "diag_build_90280A194.py"
    helper = diagnostics / "diag_mcmaster_fillister.py"

    wrapper.write_text(
        "from diagnostics.diag_build_90280A194 import build_90280A194\n",
        encoding="utf-8",
    )
    package_init.write_text("", encoding="utf-8")
    entry.write_text(
        "import diagnostics.diag_mcmaster_fillister\n",
        encoding="utf-8",
    )
    helper.write_text("import external_site_package\n", encoding="utf-8")

    monkeypatch.setattr(bg, "SCRIPTS_DIR", scripts)
    bg.clear_import_caches()
    try:
        deps = {Path(dep) for dep in module_deps_of(wrapper)}
    finally:
        # Do not leave cached temporary paths behind after monkeypatch restores
        # the production scripts root.
        bg.clear_import_caches()

    assert entry.resolve() in deps
    assert helper.resolve() in deps
    assert package_init.resolve() in deps
    assert all(path.is_relative_to(scripts) for path in deps)


def test_identical_module_text_resolves_against_its_own_package(tmp_path, monkeypatch):
    """Source SYNTAX is reused by content, but a relative import is anchored to
    the importing module's own package.

    Two packages whose entry modules hold byte-identical source -- the same
    ``from . import helper`` -- must each pull in THEIR OWN helper.  Reusing a
    RESOLVED closure by text (rather than only the unresolved syntax) would
    collapse the two onto whichever package was analysed first and silently drop
    a real recipe edge from the other, leaving that part reported up to date
    after its helper changed.
    """
    scripts = tmp_path / "scripts"
    shared = "from . import helper\n"
    for package in ("alpha", "beta"):
        directory = scripts / package
        directory.mkdir(parents=True)
        (directory / "__init__.py").write_text("", encoding="utf-8")
        (directory / "entry.py").write_text(shared, encoding="utf-8")
        (directory / "helper.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(bg, "SCRIPTS_DIR", scripts)
    bg.clear_import_caches()
    try:
        closures = {
            package: {
                Path(dep)
                for dep in module_deps_of(scripts / package / "entry.py")
            }
            for package in ("alpha", "beta")
        }
    finally:
        bg.clear_import_caches()

    for package, other in (("alpha", "beta"), ("beta", "alpha")):
        assert (scripts / package / "helper.py").resolve() in closures[package]
        assert (scripts / package / "__init__.py").resolve() in closures[package]
        assert (scripts / other / "helper.py").resolve() not in closures[package]


def test_stamping_classification_rereads_sources_between_contracts(
    tmp_path, monkeypatch
):
    """Each stamping CONTRACT classifies against the sources as they are NOW.

    Part and title-block classification share one whole-program scan, but they
    are separate cache entries: the second contract to be asked is a miss, and a
    miss has always re-read the tree.  A source rewritten in-process between the
    two -- a generated module, a test fixture, an edit during a long ``doit``
    session -- must therefore be visible to the second, or a module that started
    stamping would be classified from the first contract's stale reading and its
    registry dependency would go missing.
    """
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    module = scripts / "widget.py"
    module.write_text("def go():\n    pass\n", encoding="utf-8")

    monkeypatch.setattr(bg, "SCRIPTS_DIR", scripts)
    bg._local_modules.cache_clear()
    bg._module_by_path.cache_clear()
    bg._stamping_modules.cache_clear()
    try:
        assert bg._stamping_modules(bg._PART_STAMP_PRIMITIVES) == frozenset()
        module.write_text("def go():\n    part_properties()\n", encoding="utf-8")
        assert "widget" in bg._stamping_modules(bg._TITLE_BLOCK_STAMP_PRIMITIVES)
    finally:
        bg._stamping_modules.cache_clear()
        bg._module_by_path.cache_clear()
        bg._local_modules.cache_clear()


def test_part_and_title_property_stampers_are_distinct():
    """Assembly identity must not masquerade as in-script part generation."""
    title_stampers = {
        stem
        for stem in ASSEMBLY_ORDER
        if stamps_title_block_properties(script_for(stem))
    }
    part_stampers = {
        stem for stem in ASSEMBLY_ORDER if stamps_part_properties(script_for(stem))
    }
    assert title_stampers == set(ASSEMBLY_ORDER)
    assert part_stampers == {"ch_channel"}

    leaf = SCRIPTS_DIR / "build_sh_vn_brass_fillister_screw.py"
    assert stamps_part_properties(leaf)
    assert stamps_title_block_properties(leaf)


def test_git_executable_is_resolved_absolute(tmp_path, monkeypatch):
    import _source_identity
    import shutil

    discovered = tmp_path / "bin" / "git"
    monkeypatch.setattr(shutil, "which", lambda command: str(discovered))
    _source_identity._git_executable.cache_clear()
    try:
        executable = Path(_source_identity._git_executable())
        assert executable == discovered.resolve()
        assert executable.is_absolute()
    finally:
        _source_identity._git_executable.cache_clear()


def test_build_id_is_the_release_revision_in_full_and_depth_1_checkouts(
    tmp_path, monkeypatch
):
    """Real Git checkouts of the SAME commit, one full and one depth-1.

    The depth-1 clone is what a farm leaf gets: its history is truncated, so
    anything derived from a tag, a commit count or a walk is either different
    or unavailable there. Both must stamp the release revision, and an
    uncommitted edit must still mark the sheet.
    """
    import os
    import subprocess

    import _source_identity
    import _config

    # Never execute a developer's hooks, filters, signer, or filesystem monitor.
    for name in tuple(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    template = tmp_path / "empty-template"
    template.mkdir()
    monkeypatch.setenv("GIT_TEMPLATE_DIR", str(template))

    def git(cwd, *args: str) -> str:
        return subprocess.run(
            [_source_identity._git_executable(), *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "--quiet")
    git(origin, "config", "user.email", "build-id@example.invalid")
    git(origin, "config", "user.name", "build id test")
    for revision, message in enumerate(("base", "second", "third")):
        (origin / "part.txt").write_text(f"{revision}\n", encoding="utf-8")
        git(origin, "add", "part.txt")
        git(origin, "commit", "--quiet", "--no-gpg-sign", "-m", message)
        if not revision:
            # A reachable release tag: the history a release-relative id would
            # have counted from, present here and absent from the leaf clone.
            git(origin, "tag", "v8")

    leaf = tmp_path / "leaf"
    git(tmp_path, "clone", "--quiet", "--depth", "1", origin.as_uri(), str(leaf))
    # Guard the fixture itself: a local clone silently ignores --depth unless
    # fetched over file://, and a full clone here would prove nothing.
    assert git(leaf, "rev-parse", "--is-shallow-repository") == "true"
    assert git(leaf, "rev-parse", "HEAD") == git(origin, "rev-parse", "HEAD")

    monkeypatch.setattr(_config, "release_revision", lambda: "v9")

    monkeypatch.setattr(_source_identity, "CAD_ROOT", origin)
    full_id = _source_identity._build_id()
    monkeypatch.setattr(_source_identity, "CAD_ROOT", leaf)
    leaf_id = _source_identity._build_id()

    assert full_id == leaf_id == "v9"

    git(leaf, "config", "status.showUntrackedFiles", "no")
    (leaf / "uncommitted.txt").write_text("operator edit\n", encoding="utf-8")
    assert _source_identity._build_id() == "v9-dirty"


def test_build_id_translates_a_failed_dirty_probe(monkeypatch):
    import subprocess

    import pytest

    import _source_identity

    def fake_run(command, **_kwargs):
        raise subprocess.CalledProcessError(128, command, stderr="not a git repo")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(
        RuntimeError, match="cannot determine Git working-tree state"
    ) as error:
        _source_identity._build_id()
    assert isinstance(error.value.__cause__, subprocess.CalledProcessError)


def test_assembly_title_properties_use_the_frozen_contract(monkeypatch):
    import _config
    from _assembly_contract import assembly_contract

    def refuse_part_registry(*_args):
        raise AssertionError("an assembly must not read a part's metadata")

    monkeypatch.setattr(_config, "parts", refuse_part_registry)
    props = assembly_title_properties("fr-frame")
    assert props["Number"] == assembly_contract("fr-frame").number
    assert props["Title"] == "fr-frame"
    assert props["Revision"] == _config.release_revision()


def test_part_properties_use_release_revision():
    import _config

    assert part_properties("pd-platen-guide")["Revision"] == _config.release_revision()


@pytest.mark.parametrize(
    ("properties", "name"),
    [
        (part_properties, "pd-platen-guide"),
        (part_properties, "unregistered-title-block-test-part"),
        (assembly_title_properties, "fr-frame"),
    ],
)
def test_title_properties_propagate_inside_corner_config(properties, name, monkeypatch):
    import _config

    title_block = _config.title_block

    def changed_title_block(section, *, unit="mm"):
        if section == "inside_corner":
            return {"radius_mm": 0.8, "digits": 1}
        return title_block(section, unit=unit)

    monkeypatch.setattr(_config, "title_block", changed_title_block)
    expected = "R0.8 MAX"
    assert properties(name)["TOL_INSIDE_CORNER"] == expected


# The title block's PART cell prints the part's slug, never a registry title
# (user ruling 2026-09-26, via Main): one convention on every part sheet.  The
# cell resolves the linked model's summary Title, which save_part_and_images
# stamps from part_properties()["Title"]; a registry ``title:`` stays in the
# registry for its other readers but must not reach that cell.
def _drawing_stems(source_kind: str) -> list[str]:
    from _drawing_registry import DRAWINGS

    return sorted(
        {d.part.replace("_", "-") for d in DRAWINGS if d.source_kind == source_kind}
    )


def _registry_title(stem: str) -> str | None:
    import _config

    try:
        return _config.parts(stem).get("title")
    except KeyError:
        return None


_PART_DRAWING_STEMS = _drawing_stems("part")
_TITLED_PART_STEMS = [
    stem for stem in _PART_DRAWING_STEMS if _registry_title(stem) not in (None, stem)
]


def test_titled_part_sheets_are_under_test():
    # 49 part sheets carried a registry title at the ruling; an empty list
    # would let the parametrized checks below pass vacuously.
    assert len(_TITLED_PART_STEMS) >= 40


@pytest.mark.parametrize("stem", _PART_DRAWING_STEMS)
def test_part_cell_prints_the_slug(stem):
    assert part_properties(stem)["Title"] == stem


@pytest.mark.parametrize("stem", _TITLED_PART_STEMS)
def test_no_registry_title_reaches_the_part_cell(stem):
    assert _registry_title(stem) not in part_properties(stem).values()




# Assembly sheets follow the same ruling: the PART cell prints the assembly's
# slug ("drive-train"), not "drive-train assembly".  The one stamp is the
# shared save path; no builder stamps its own.
_ASSEMBLY_DRAWING_STEMS = _drawing_stems("assembly")


def test_every_assembly_sheet_is_under_test():
    assert len(_ASSEMBLY_DRAWING_STEMS) >= 8


@pytest.mark.parametrize("stem", _ASSEMBLY_DRAWING_STEMS)
def test_assembly_part_cell_prints_the_slug(stem):
    assert assembly_title_properties(stem)["Title"] == stem




def test_config_syntax_is_reused_by_content_not_source_path():
    bg._config_references_in_text.cache_clear()
    first = "import _config as cfg\nx = cfg.machine('gear_train')\n"
    changed = "import _config as cfg\nx = cfg.machine('output')\n"
    with patch.object(bg.ast, "parse", wraps=bg.ast.parse) as parse:
        assert _tokens(first) == frozenset({"machine/gear_train.yaml"})
        assert _tokens(first) == frozenset({"machine/gear_train.yaml"})
        assert _tokens(changed) == frozenset({"machine/output.yaml"})
    assert parse.call_count == 2, "identical shared helper syntax must be analyzed once"


def test_cached_config_syntax_still_resolves_current_family_membership():
    source = "import _config\nx = _config.machine('gear_train')\n"
    with patch.object(
        bg, "_family_tokens", side_effect=[frozenset({"before"}), frozenset({"after"})]
    ) as resolve:
        assert _tokens(source) == frozenset({"before"})
        assert _tokens(source) == frozenset({"after"})
    assert resolve.call_count == 2, "filesystem/config resolution is not a syntax fact"


def test_cached_config_syntax_preserves_unknown_reference_rejection():
    source = "import _config as cfg\nx = cfg.machine\n"
    bg._config_references_in_text.cache_clear()
    with patch.object(bg.ast, "parse", wraps=bg.ast.parse) as parse:
        for _ in range(2):
            try:
                _tokens(source)
            except bg._UnknownConfigUse:
                continue
            raise AssertionError(
                "unclassified config reference must remain conservative"
            )
    assert parse.call_count == 1


def _run() -> int:
    return int(pytest.main([__file__, "-q"]))


if __name__ == "__main__":
    sys.exit(_run())


# --- Machine-wide syntax facts store (_FactStore / _persisted_facts) ---------------


def _fresh_store(monkeypatch, directory: Path) -> bg._FactStore:
    """A store as a NEW process would see it, rooted in ``directory``."""
    monkeypatch.setenv(bg._FACTS_ENV, str(directory))
    store = bg._FactStore()
    monkeypatch.setattr(bg, "_FACTS", store)
    return store


def test_syntax_facts_are_reused_by_the_next_process(tmp_path, monkeypatch):
    calls: list[str] = []

    @bg._persisted_facts("probe")
    def probe(text: str) -> frozenset[str]:
        calls.append(text)
        return frozenset(text.split())

    _fresh_store(monkeypatch, tmp_path)
    assert probe("a b") == frozenset({"a", "b"})
    bg._FACTS.save()
    _fresh_store(monkeypatch, tmp_path)
    assert probe("a b") == frozenset({"a", "b"})
    assert calls == ["a b"]


def test_syntax_facts_are_keyed_by_content_not_by_file(tmp_path, monkeypatch):
    calls: list[str] = []

    @bg._persisted_facts("probe")
    def probe(text: str) -> frozenset[str]:
        calls.append(text)
        return frozenset(text.split())

    _fresh_store(monkeypatch, tmp_path)
    probe("import a")
    bg._FACTS.save()
    _fresh_store(monkeypatch, tmp_path)
    assert probe("import b") == frozenset({"import", "b"})
    assert calls == ["import a", "import b"]


def test_module_syntax_round_trips_through_the_store(tmp_path, monkeypatch):
    source = "import os\nfrom . import x\n\ndef f():\n    g()\n    m.h()\n"
    _fresh_store(monkeypatch, tmp_path)
    bg._module_syntax.cache_clear()
    expected = bg._module_syntax(source)
    bg._FACTS.save()
    _fresh_store(monkeypatch, tmp_path)
    bg._module_syntax.cache_clear()
    with patch.object(bg.ast, "parse", side_effect=AssertionError("re-parsed")):
        assert bg._module_syntax(source) == expected
    bg._module_syntax.cache_clear()


def test_config_references_round_trip_through_the_store(tmp_path, monkeypatch):
    source = "import _config\n\ndef f():\n    return _config.tolerances()\n"
    modules = frozenset({"_config"})
    _fresh_store(monkeypatch, tmp_path)
    bg._config_references_in_text.cache_clear()
    expected = bg._config_references_in_text(source, modules)
    assert expected and isinstance(expected[0][1], bg._ConfigUse)
    bg._FACTS.save()
    _fresh_store(monkeypatch, tmp_path)
    bg._config_references_in_text.cache_clear()
    with patch.object(bg.ast, "parse", side_effect=AssertionError("re-parsed")):
        assert bg._config_references_in_text(source, modules) == expected
    bg._config_references_in_text.cache_clear()


def test_syntax_errors_are_never_stored(tmp_path, monkeypatch):
    _fresh_store(monkeypatch, tmp_path)
    bg._module_syntax.cache_clear()
    with pytest.raises(SyntaxError):
        bg._module_syntax("def (:\n")
    bg._FACTS.save()
    assert not list(tmp_path.glob("*.pickle"))


def test_a_corrupt_or_foreign_store_reads_as_empty(tmp_path, monkeypatch):
    import pickle

    store = _fresh_store(monkeypatch, tmp_path)
    path = store._location()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a pickle")
    assert store.get(b"k") == (False, None)

    # A pathlib object is picklable but not a builtin container of strings.
    path.write_bytes(pickle.dumps({b"k": Path("foreign")}))
    assert _fresh_store(monkeypatch, tmp_path).get(b"k") == (False, None)


def test_the_store_can_be_switched_off(tmp_path, monkeypatch):
    calls: list[str] = []

    @bg._persisted_facts("probe")
    def probe(text: str) -> str:
        calls.append(text)
        return text

    monkeypatch.setenv(bg._FACTS_ENV, "off")
    monkeypatch.setattr(bg, "_FACTS", bg._FactStore())
    probe("x")
    bg._FACTS.save()
    monkeypatch.setattr(bg, "_FACTS", bg._FactStore())
    probe("x")
    assert calls == ["x", "x"]
    assert not list(tmp_path.rglob("*.pickle"))


def test_the_store_file_is_named_for_this_analyzer(tmp_path, monkeypatch):
    import hashlib

    location = _fresh_store(monkeypatch, tmp_path)._location()
    analyzer = hashlib.sha256(Path(bg.__file__).read_bytes()).hexdigest()[:16]
    assert location.parent == tmp_path
    assert analyzer in location.name
    assert f"-v{bg._FACTS_SCHEMA}-" in location.name
    assert sys.implementation.cache_tag in location.name


def test_a_malformed_entry_is_overwritten_by_the_recomputed_fact(tmp_path, monkeypatch):
    store = _fresh_store(monkeypatch, tmp_path)
    bg._module_syntax.cache_clear()
    source = "import json\n"
    bg._module_syntax(source)
    (key,) = [k for k in store._entries]
    store._entries[key] = ("garbage",)
    bg._module_syntax.cache_clear()
    bg._module_syntax(source)
    assert bg._ModuleSyntax(*store._entries[key]) == bg._module_syntax(source)
    bg._module_syntax.cache_clear()


def test_no_nameable_home_disables_the_store_instead_of_failing(monkeypatch):
    # A farm leaf runs under a filtered environment: with no LOCALAPPDATA and
    # no home, Path.home() raises RuntimeError; the graph load must go on.
    for name in (
        "HARMONIC_BUILDGRAPH_CACHE",
        "LOCALAPPDATA",
        "USERPROFILE",
        "HOMEPATH",
        "HOMEDRIVE",
        "HOME",
    ):
        monkeypatch.delenv(name, raising=False)

    def no_home(cls):
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(bg, "_FACTS", bg._FactStore())
    monkeypatch.setattr(bg.Path, "home", classmethod(no_home))
    bg._module_syntax.cache_clear()
    assert bg._module_syntax("import os\n").imports == (("os", None),)
    assert bg._FACTS._path is None
    bg._module_syntax.cache_clear()


def test_a_malformed_stored_entry_is_recomputed(tmp_path, monkeypatch):
    store = _fresh_store(monkeypatch, tmp_path)
    bg._module_syntax.cache_clear()
    source = "import os\n"
    expected = bg._module_syntax(source)
    for key in list(store._entries):
        store._entries[key] = ("not", "a", "module", "syntax")
    bg._module_syntax.cache_clear()
    assert bg._module_syntax(source) == expected
    bg._module_syntax.cache_clear()


# --- Fastener catalog per-row digest (dict-table projection) -------------------

_CATALOG = (SCRIPTS_DIR / "_fastener_catalog.py").read_text(encoding="utf-8")


def _row_edited(source: str, row: str) -> str:
    """``source`` with one catalog row's stock name changed."""
    marker = f'    "{row}": _stock(\n        "{row}",\n        "'
    assert marker in source, row
    return source.replace(marker, marker + "Edited ", 1)


def test_fastener_recipe_ignores_other_rows_and_tracks_its_own():
    selected = frozenset({"ch-vn-frame-side-screw"})
    before = bg.dict_table_recipe(_CATALOG, "FASTENERS", selected)
    assert bg.dict_table_recipe(
        _row_edited(_CATALOG, "sh-vn-clamp-screw"), "FASTENERS", selected
    ) == before, "another row's edit must not move this row's recipe"
    assert (
        bg.dict_table_recipe(
            _row_edited(_CATALOG, "ch-vn-frame-side-screw"), "FASTENERS", selected
        )
        != before
    ), "the selected row's edit must move it"
    shared_edit = _CATALOG.replace(
        'supplier: str = "McMaster-Carr"', 'supplier: str = "McMaster"'
    )
    assert shared_edit != _CATALOG
    assert bg.dict_table_recipe(shared_edit, "FASTENERS", selected) != before, (
        "shared code (the dataclass, _stock, fastener) must stay in every recipe"
    )


def test_fastener_recipe_records_an_absent_selected_row():
    """A selected key that does not exist yet is part of the recipe, so adding it
    moves the key of every task that asked for it."""
    ghost = frozenset({"not-yet-catalogued"})
    marker = '"ch-vn-frame-side-screw": _stock('
    assert _CATALOG.count(marker) == 1
    removed = _CATALOG.replace(marker, '"ch-vn-frame-side-screw-x": _stock(', 1)
    assert bg.dict_table_recipe(_CATALOG, "FASTENERS", ghost) == bg.dict_table_recipe(
        removed, "FASTENERS", ghost
    )
    assert bg.dict_table_recipe(
        _CATALOG, "FASTENERS", frozenset({"ch-vn-frame-side-screw"})
    ) != bg.dict_table_recipe(removed, "FASTENERS", frozenset({"ch-vn-frame-side-screw"}))


@pytest.mark.parametrize(
    "declaration",
    [
        "X = 1\n",
        "FASTENERS = dict(a=1)\n",
        "FASTENERS = {}\nFASTENERS = {}\n",
        "FASTENERS = {KEY: 1}\n",
        "FASTENERS = {'a': 1, 'a': 2}\n",
    ],
    ids=["missing", "call", "reassigned", "computed-key", "duplicate"],
)
def test_dict_table_projection_rejects_non_declarative_tables(declaration):
    with pytest.raises(ValueError):
        bg.dict_table_recipe(declaration, "FASTENERS", frozenset())


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('from _fastener_catalog import fastener\nS = fastener("a")\n', (["a"], False)),
        (
            'from _fastener_catalog import fastener\nNAME = "b"\nS = fastener(NAME)\n',
            (["b"], False),
        ),
        (
            "from _fastener_catalog import fastener\n"
            "def f(name):\n    return fastener(name)\n",
            ([], True),
        ),
        (
            'from _fastener_catalog import fastener\nNAME = "b"\nNAME = "c"\n'
            "S = fastener(NAME)\n",
            ([], True),
        ),
        ("from _fastener_catalog import PurchasedFastenerSpec\n", ([], False)),
        ("import os\n", ([], False)),
    ],
    ids=["literal", "constant", "dynamic", "reassigned-constant", "type-only", "unrelated"],
)
def test_fastener_reads_classify_literal_and_dynamic_rows(source, expected):
    reads = bg.table_reads(source, *bg.FASTENER_TABLE)
    assert reads is not None
    assert (sorted(reads.keys), reads.dynamic) == expected


@pytest.mark.parametrize(
    "source",
    [
        "from _fastener_catalog import FASTENERS\n",
        "import _fastener_catalog\n",
        "from _fastener_catalog import fastener as f\n",
        "from _fastener_catalog import *\n",
        "import importlib\nm = importlib.import_module('_fastener_catalog')\n",
        "from _fastener_catalog import fastener\nlookup = fastener\n",
        "from _fastener_catalog import fastener\nS = fastener(name='a')\n",
        "from x import FASTENERS\nFASTENERS['a']\n",
        "from _fastener_catalog import fastener\nS = eval('fastener(\"a\")')\n",
    ],
    ids=[
        "table-import",
        "module-import",
        "alias",
        "star",
        "string-alias",
        "passed-around",
        "keyword-call",
        "table-name",
        "eval",
    ],
)
def test_unclassified_catalog_use_keeps_the_whole_file(source):
    """The fallback the per-row digest rests on: any use the reader cannot prove
    narrow returns None, and the task keeps the whole _fastener_catalog.py."""
    assert bg.table_reads(source, *bg.FASTENER_TABLE) is None
    assert bg.fastener_rows_selected((source,), "a", frozenset({"a"})) is None


def test_dynamic_reads_resolve_to_the_tasks_own_row_only():
    dynamic = "from _fastener_catalog import fastener\ndef f(n):\n    return fastener(n)\n"
    literal = 'from _fastener_catalog import fastener\nS = fastener("b")\n'
    rows = frozenset({"a", "b"})
    assert bg.fastener_rows_selected((dynamic, literal), "a", rows) == {"a", "b"}
    # No own row: the dynamic read adds nothing, and the run-time guard refuses it.
    assert bg.fastener_rows_selected((dynamic, literal), None, rows) == {"b"}
    assert bg.fastener_rows_selected((dynamic,), "not-a-row", rows) == frozenset()


def test_every_catalog_consumer_in_the_tree_is_classified():
    """Pins the fallback surface: today every consumer reads the catalog through
    ``fastener(...)``. A new consumer that the reader cannot classify makes its
    tasks silently fall back to the whole file (still correct, just no longer
    narrow); this test makes that visible instead."""
    consumers = [
        path
        for path in sorted(SCRIPTS_DIR.rglob("*.py"))
        if "_fastener_catalog" in path.read_text(encoding="utf-8")
        and path.name not in {"_fastener_catalog.py", "_buildgraph.py"}  # owner, analyzer
        and not path.name.startswith("test_")
    ]
    assert consumers
    unclassified = [
        path.name
        for path in consumers
        if bg.table_reads(path.read_text(encoding="utf-8"), *bg.FASTENER_TABLE) is None
    ]
    assert unclassified == []


def test_interference_contracts_do_not_depend_on_the_crankshaft_spec() -> None:
    # Every assembly imports _interference_contracts, so a crankshaft length or
    # station edit must not re-key them all (W15, Main 2026-09-25): the shaft
    # diameter comes from its owner, crank_hub_geometry.
    closure = _helper_names("_interference_contracts.py")
    assert "dt_crank_hub_geometry" in closure
    assert "dt_crankshaft_spec" not in closure


def test_interference_contracts_do_not_depend_on_magnifier_fit_or_pose() -> None:
    # Shared interference oracles restate pinned literals; importing either
    # magnifier owner would re-key unrelated assemblies on a fixture/fit edit.
    closure = _helper_names("_interference_contracts.py")
    assert "_hole_spec" in closure
    assert "mg_output_fixture_geom" not in closure


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        # Listed themselves: the root script is not in its own import closure
        # (Codex #1035, PRRT_kwDOPHDy386mV11b).
        ("build_mg_wheel_bar.py", True),
        # Canonical stock does not own the stop application's printed fit.
        ("build_sh_vn_fillister_screw_90280a108.py", False),
        # Reads through an imported listed module.
        ("build_sm_vn_boss_hook.py", True),
        ("build_ch_vn_spring_hook.py", True),
        # R9-48: judges its lock taps at the printed worst case.
        ("build_pd_platen_guide.py", True),
        # Stock limits do not read a manufactured receiver's platform allowance.
        ("dt_swing_stop_screw_spec.py", False),
    ],
)
def test_reads_title_block_geometry_covers_root_and_closure(script, expected):
    assert bg.reads_title_block_geometry(SCRIPTS_DIR / script) is expected


def test_feature_declarations_stay_out_of_all_native_build_closures():
    """Manifest-only edits must never cascade through native part/assembly recipes."""
    forbidden = {"_feature_requirements", "_printed_limits", "export_features"}
    for script in [*bg.part_scripts(), *(script_for(stem) for stem in ASSEMBLY_ORDER)]:
        closure = {Path(path).stem for path in module_deps_of(script)}
        assert not closure & forbidden, (script.name, closure & forbidden)
        assert not any(name.startswith("draw_") for name in closure), script.name


def test_generic_feature_driver_closure_contains_no_discovered_part_draw_or_spec():
    """Import-free discovery cannot become an all-part recipe dependency."""
    import export_features

    closure = {Path(path).name for path in module_deps_of(SCRIPTS_DIR / "export_features.py")}
    assert "_feature_requirements.py" in closure
    for stem in export_features.SUPPORTED_PARTS:
        assert f"draw_{stem}.py" not in closure
        assert f"{stem}_spec.py" not in closure


def test_features_source_closures_preserve_draw_and_spec_config_reads():
    import export_features

    globs = {"machine/*", "tolerances/*", "parts/*", "title_block", "**", bg.ASSEMBLY_CONTRACTS_TOKEN}
    # Shared configured producers cite the saved/default member's real spec,
    # not a synthetic aggregate spec. Keep this oracle independent of the resolver.
    member_specs = {
        "sh_vn_clamping_kit_hardware": "sh_vn_clamping_kit_hold_down_stud_spec",
    }
    for stem in export_features.SUPPORTED_PARTS:
        sources = {path.resolve() for path in export_features.source_paths(stem)}
        drawing = (SCRIPTS_DIR / f"draw_{stem}.py").resolve()
        spec_module = member_specs.get(stem, f"{stem}_spec")
        spec = (SCRIPTS_DIR / f"{spec_module}.py").resolve()
        assert spec.is_file(), stem
        assert {drawing, spec} <= sources, stem
        for root in (drawing, spec):
            assert {Path(path).resolve() for path in module_deps_of(root)} <= sources, (stem, root)
        assert {
            path.name for path in sources if path.name.startswith("draw_")
        } == {drawing.name}, stem
        for source in sources:
            if source.suffix == ".py":
                for token in config_files_of(source):
                    assert token in globs or (bg.CONFIG_DIR / token).is_file(), (stem, source, token)


def test_requirement_declarations_do_not_read_title_block_geometry():
    script = SCRIPTS_DIR / "_feature_requirements.py"
    assert script.stem not in bg.TITLE_BLOCK_GEOMETRY_MODULES
    assert not bg.reads_title_block_geometry(script)
    assert "title_block" not in config_files_of(script)


@pytest.mark.parametrize("module", ["_printed_tolerance"])
def test_numeric_tolerance_title_block_readers_are_classified(module):
    script = SCRIPTS_DIR / f"{module}.py"
    assert script.stem in bg.TITLE_BLOCK_GEOMETRY_MODULES
    assert bg.reads_title_block_geometry(script)
    assert "title_block" in config_files_of(script)


@pytest.mark.parametrize(
    "module", ["dt_vn_cone_lock_knob_spec", "dt_cone_tip_block_spec", "_printed_limits"]
)
def test_printed_band_readers_are_classified_through_the_reader(module):
    # Reads the printed rows only via _printed_tolerance, so its import closure,
    # not its own stem, keeps title_block.yaml on its recipes.
    script = SCRIPTS_DIR / f"{module}.py"
    assert script.stem not in bg.TITLE_BLOCK_GEOMETRY_MODULES
    assert bg.reads_title_block_geometry(script)
    assert "title_block" in config_files_of(script)


def test_feature_exporter_revision_call_keeps_config_analysis_classifiable():
    """A bare from-_config import must not widen every features leaf to '**'."""
    exporter = SCRIPTS_DIR / "export_models.py"
    assert "**" not in config_files_of(exporter)
