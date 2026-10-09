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
from _common import part_properties  # noqa: E402


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
    "fr_frame": "vn_fillister_screw vn_frame_cross_screw vn_gooseneck_set_screw fr_harmonic_base "
    "vn_lag_screw fr_nameplate fr_rocker_arm_support fr_top_frame fr_tube_frame vn_tube_frame_cap",
    "dt_drive_train": "dt_alignment_pinion dt_arbor_pedestal vn_arbor_set_screw dt_cone_gear dt_cone_gear_shaft "
    "vn_cone_lock_knob dt_cone_pivot_post vn_cone_pivot_screw dt_cone_swing_platform "
    "vn_cone_tip_adjuster dt_cone_tip_block vn_cone_tip_block_screw vn_cone_tip_collar vn_cone_tip_pinch_screw "
    "dt_crank_arm dt_crank_drive_gear dt_crank_handle dt_crank_handle_butt_cup dt_crank_handle_ferrule "
    "dt_crank_handle_pivot_screw dt_crank_hub vn_crank_hub_pin dt_crank_pin "
    "dt_crank_pin_eye dt_crank_pin_ring vn_crank_seat_drive_pin dt_crank_seat_washer "
    "dt_crank_pinion dt_crank_pinion_pin dt_crankshaft dt_cylinder_end_disc dt_cylinder_gear "
    "dt_cylinder_gear_shaft "
    "vn_fillister_screw vn_foot_screw vn_keeper_chain vn_keeper_chain_link vn_pedestal_hold_down_screw dt_pinion_arbor dt_pinion_arbor_collar dt_pinion_bracket dt_pinion_cam "
    "dt_pinion_cam_pin dt_pinion_handle dt_pinion_lever dt_pinion_lever_pin dt_pinion_lift_rod "
    "dt_pinion_pivot_block dt_pinion_pivot_shaft dt_pinion_spring vn_pinion_strap_pin vn_post_mount_screw vn_slotted_screw "
    "vn_swing_stop_screw",
    "ch_channel": "ch_amplitude_bar ch_bar_pivot_pin ch_channel_lever vn_channel_spring_installed ch_connecting_rod "
    "vn_frame_side_screw ch_fulcrum_keeper ch_fulcrum_shaft vn_pedestal_hold_down_screw ch_pivot_bracket "
    "ch_pivot_shaft ch_rocker_arm ch_rocker_thrust_washer ch_rod_pivot_pin vn_spring_hook",
    "sm_summing": "vn_boss_hook vn_counter_spring sm_gooseneck vn_knife_hanger_stud vn_knife_hanger_washer sm_knife_mount sm_summing_lever",
    "mg_magnifier": "vn_clamp_screw sh_column_clamp_back sh_column_clamp_front mg_lever_wire "
    "mg_magnifying_bracket vn_magnifying_bracket_screw mg_magnifying_clamp mg_magnifying_lever mg_magnifying_vertical_rod "
    "mg_magnifying_wheel mg_output_fixture vn_thumb_screw mg_wheel_axle vn_wheel_axle_nut mg_wheel_bar",
    "pn_pen": "vn_hanger_screw pn_pen_frame pn_pen_hanger pn_pen_marker pn_pen_rod vn_pen_set_screw pn_pen_v_block pn_pen_wire",
    "pd_paper_drive": "vn_chain_inner_link vn_chain_outer_link vn_clamp_screw "
    "sh_column_clamp_back sh_column_clamp_front vn_fillister_screw pd_guide_lock vn_guide_lock_screw pd_latch_hook "
    "vn_latch_hook_bracket_screw "
    "pd_platen pd_platen_clip pd_platen_guide pd_platen_paper pd_platen_rack pd_rack_pinion pd_support_bar "
    "pd_transgear_arm pd_transgear_arm_plate vn_transgear_arm_plate_screw vn_transgear_collar_cross_pin "
    "pd_transgear_disc_hub vn_transgear_disc_screw pd_transgear_drive_collar pd_transgear_feed_pinion "
    "pd_transgear_knob_cup vn_transgear_knob_cup_pin vn_transgear_knob_drive_pin "
    "pd_transgear_knob_shaft pd_transgear_knob_thrust_ring vn_transgear_latch_pin vn_transgear_pivot_screw "
    "pd_transgear_pin pd_transgear_pivot_spacer vn_transgear_pivot_spring pd_transgear_rear_bushing "
    "pd_transgear_front_bushing "
    "pd_transgear_removable vn_transgear_retaining_ring "
    "pd_transgear_thumbnut",
    "ha_harmonic_analyzer": "ha_measuring_stick ha_measuring_stick_stop fr_frame dt_drive_train "
    "ch_channel sm_summing mg_magnifier pn_pen pd_paper_drive",
}


@pytest.mark.parametrize("assembly", ASSEMBLY_ORDER)
def test_all_assembly_references_match_inserted_source_manifests(assembly):
    assert set(references_of(assembly)) == set(_INSERTED_SOURCES[assembly].split())


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
    assert not _assignment_expressions(batch, "specs")
    assert _assignment_expressions(batch, "part") == ["spec['part']"]
    assert _assignment_expressions(batch, "names") == ["[]"]
    assert _assignment_expressions(batch, "names_arg") == [
        "VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, names)"
    ]
    for name, count in {
        "specs": 0,
        "spec": 1,
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
    source_variables = {"specs", "spec", "names", "names_arg"}
    for node in ast.walk(batch):
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
            and node.func.value.id in {"spec", "specs"}
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
    name_calls = [
        ast.unparse(node)
        for node in ast.walk(batch)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "names"
    ]
    assert name_calls == ["names.append(str(part_path(part)))"]
    loops = [
        node
        for node in ast.walk(batch)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "spec"
    ]
    assert len(loops) == 1 and ast.unparse(loops[0].iter) == "specs"
    part_write = next(
        node
        for node in ast.walk(batch)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "part"
            for target in node.targets
        )
    )
    assert part_write in set(ast.walk(loops[0]))
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
    "change",
    [
        "new helper",
        "single source",
        "batch source",
        "batch row mutation",
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
    for s in candidates:
        direct = {a for a in ASSEMBLY_ORDER if s in references_of(a)}
        legacy = set(dependents_of(s))
        if direct and "ha_harmonic_analyzer" not in direct:
            assert legacy == direct | {"ha_harmonic_analyzer"}, (
                f"{s}: legacy {legacy} != direct {direct} + transitive top"
            )
        else:
            assert legacy == direct, f"{s}: legacy {legacy} != direct {direct}"


def test_output_subs_reference_their_parts_only():
    """Each output sub inserts leaf parts, never another sub-assembly."""
    for stem in ("sm_summing", "mg_magnifier", "pn_pen", "pd_paper_drive"):
        refs = references_of(stem)
        assert refs, f"{stem} should reference its parts"
        parts = set(part_stems())
        assert set(refs) <= parts, f"{stem} references non-parts: {set(refs) - parts}"
        assert not (set(refs) & set(ASSEMBLY_ORDER)), (
            f"{stem} must not reference a sub-assembly"
        )


def test_top_references_subassemblies_and_loose_parts():
    """harmonic-analyzer mates the seven subs plus the two loose top-level parts:
    the generic measuring-stick and its sliding stop stand directly on the base
    (the stick propped on the stop block, 2026-09-02). The spare
    transgear-removable rides inside paper-drive (a flat sibling of its mounted
    T24), not here -- at the top level its leaf name would collide with the
    T12/T24 instances nested in drive-train / paper-drive."""
    refs = set(references_of("ha_harmonic_analyzer"))
    subs = {
        "fr_frame",
        "dt_drive_train",
        "ch_channel",
        "sm_summing",
        "mg_magnifier",
        "pn_pen",
        "pd_paper_drive",
    }
    loose = {"ha_measuring_stick", "ha_measuring_stick_stop"}
    assert refs == subs | loose, refs


def test_leaf_parts_do_not_depend_on_assembly_helpers():
    """A leaf part must NOT pull in _assembly/_transforms -- the whole point of
    splitting them out of _common is that assembly-only edits skip every part."""
    for stem in part_stems():
        helpers = _helper_names(f"build_{stem}.py")
        assert "_assembly" not in helpers, f"{stem} wrongly depends on _assembly"
        assert "_transforms" not in helpers, f"{stem} wrongly depends on _transforms"
        assert "_common" in helpers, f"{stem} lost its _common dependency"


def test_assemblies_depend_on_assembly_helpers():
    """Every assembly imports _assembly (mates/placement) and _common."""
    for stem in ASSEMBLY_ORDER:
        helpers = _helper_names(script_for(stem).name)
        assert {"_assembly", "_common"} <= helpers, f"{stem}: {helpers}"


@pytest.mark.parametrize(
    ("helper", "consumers"),
    [
        ("_assembly_patterns", {"dt_drive_train", "fr_frame", "mg_magnifier", "pd_paper_drive"}),
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
    builder or its print data: a sketch, precision or caption edit on MHA-DT-020
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
    ("build_ch_channel_assembly.py", "build_ch_fulcrum_keeper"): (
        "dtrefactor: reads CBORE_DEPTH_MM, FOOT_H"
    ),
    ("build_dt_drive_train_assembly.py", "build_dt_alignment_pinion"): (
        "dtrefactor: reads BORE_DIA"
    ),
    ("build_dt_drive_train_assembly.py", "build_dt_arbor_pedestal"): (
        "dtrefactor: reads FOOT_HEIGHT, FOOT_WIDTH, SCREW_Z"
    ),
    ("build_dt_drive_train_assembly.py", "build_dt_cone_pivot_post"): (
        "dtrefactor: reads BLOCK_DIA, BORE_HEIGHT, CONE_BOSS_LENGTH, CRANK_BORE_HEIGHT, CRANK_BOSS_LENGTH, CRANK_BOSS_START_Z"
    ),
    ("build_dt_drive_train_assembly.py", "build_vn_cone_tip_adjuster"): (
        "dtrefactor: reads BODY_LEN, CUP_DEPTH, CUP_DIA, THREAD"
    ),
    ("build_dt_drive_train_assembly.py", "build_vn_cone_tip_pinch_screw"): (
        "dtrefactor: reads SHANK_LEN, THREAD"
    ),
    ("build_dt_drive_train_assembly.py", "build_dt_crankshaft"): (
        "dtrefactor: reads PINION_PIN_STATION_Y, SEAT_PINION, SHAFT_LENGTH"
    ),
    ("build_dt_drive_train_assembly.py", "build_dt_cylinder_end_disc"): (
        "dtrefactor: reads DISC_DIA, DISC_THICK"
    ),
    ("build_dt_drive_train_assembly.py", "build_fr_harmonic_base"): (
        "dtrefactor: reads BLOCK_SCREW_HOLE_DEPTH, BLOCK_SCREW_XZ, BLOCK_SEAT_SPEC, FOOT_SCREW_HOLE_DEPTH, FOOT_SCREW_XZ, FOOT_SEAT_SPEC, LOCK_KNOB_XZ, LOCK_SEAT_SPEC, LOCK_STUD_ENGAGEMENT, PEDESTAL_SCREW_HOLE_DEPTH, PEDESTAL_SCREW_XZ, PEDESTAL_SEAT_SPEC, PIVOT_SCREW_XZ, PIVOT_SEAT_SPEC, STOP_SCREW_XZ, STOP_SEAT_SPEC, SWING_HARDWARE_GEOMETRY, require_blind_seat_fit"
    ),
    ("build_fr_frame_assembly.py", "build_vn_gooseneck_set_screw"): (
        "dtrefactor: reads SHANK_LEN"
    ),
    ("build_fr_frame_assembly.py", "build_fr_top_frame"): (
        "dtrefactor: reads SIDE_TAP_SPEC"
    ),
    ("build_ha_harmonic_analyzer_assembly.py", "build_ha_measuring_stick"): (
        "dtrefactor: reads BODY_THICKNESS, BODY_WIDTH, DIVISION_SPACING, SCALE_START_X"
    ),
    ("build_ha_harmonic_analyzer_assembly.py", "build_ha_measuring_stick_stop"): (
        "dtrefactor: reads HEAD_H, SLOT_FLOOR, SLOT_H, SLOT_W"
    ),
    ("build_kinematic_probe.py", "build_pd_paper_drive_assembly"): (
        "dtrefactor: reads CHAIN_CRANK_CENTRE, DISC_TEETH, FEED_PD, KNOB_SHAFT_XY, NET_RACK_TRAVEL_PER_CRANK_REV, SPARE_GEAR_POS, THIRD_TEETH"
    ),
    ("build_mg_magnifier_assembly.py", "build_vn_thumb_screw"): (
        "dtrefactor: reads HEAD_STACK_LEN, SHANK_LEN"
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
    ("build_pd_paper_drive_assembly.py", "build_sh_column_clamp_back"): (
        "dtrefactor: reads DEPTH, HOLE_SPEC"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_guide_lock"): (
        "dtrefactor: reads HOLE_DIA, LOCK_THICK, LOCK_WIDTH"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_platen_clip"): (
        "dtrefactor: reads CLIP_LENGTH, CLIP_THICKNESS, HOLE_DIA, HOLE_INSET, HOLE_Y, SCREW_SEAT_BOSS_H, SCREW_SEAT_DIA, SCREW_SEAT_STACK"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_platen_guide"): (
        "dtrefactor: reads GUIDE_DEPTH, GUIDE_HEIGHT, GUIDE_LENGTH, GUIDE_SCREW_BOTTOM_CLEARANCE, GUIDE_SCREW_PASSAGE, GUIDE_SCREW_THREAD_ENGAGEMENT, HOLE_X, LOCK_SCREW_PASSAGE, LOCK_SCREW_THREAD_ENGAGEMENT, LOCK_SCREW_TIP_INSIDE_MIN, LOCK_STATION_X, SCREW_STATION_X"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_platen_paper"): (
        "dtrefactor: reads PAPER_HEIGHT, PAPER_WIDTH"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_platen_rack"): (
        "dtrefactor: reads ADDENDUM, BAR_HEIGHT, BAR_LENGTH, FIRST_GAP_X, PITCH"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_rack_pinion"): (
        "dtrefactor: reads DP, FACE_WIDTH, TEETH"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_support_bar"): (
        "dtrefactor: reads BAR_DEPTH, BAR_HEIGHT, CLAMP_CBORE_DEPTH, CLAMP_CBORE_DIA, CLAMP_HEAD_RECESS, CLAMP_HOLE_DIA, CLAMP_HOLE_X"
    ),
    ("build_pd_paper_drive_assembly.py", "build_pd_transgear_feed_pinion"): (
        "dtrefactor: reads DP, FACE_WIDTH, TEETH"
    ),
    ("build_pn_pen_assembly.py", "build_pn_pen_frame"): (
        "dtrefactor: reads FRAME_DEPTH, OUTER_HEIGHT, OUTER_WIDTH, RAIL_END, RAIL_SIDE"
    ),
    ("build_pn_pen_assembly.py", "build_pn_pen_hanger"): (
        "dtrefactor: reads SCREW_HOLE_XY, STRAP_Z"
    ),
    ("build_pn_pen_assembly.py", "build_vn_pen_set_screw"): (
        "dtrefactor: reads HEAD_STACK_LEN, SHANK_DIA, SHANK_LEN, TIP_CHAMFER"
    ),
    ("build_sm_summing_assembly.py", "build_vn_knife_hanger_stud"): (
        "dtrefactor: reads SHANK_DIA, UNDERHEAD_LEN"
    ),
    ("build_sm_summing_assembly.py", "build_vn_knife_hanger_washer"): (
        "dtrefactor: reads INNER_DIA, OUTER_DIA, THICKNESS"
    ),
    ("build_sm_summing_assembly.py", "build_sm_knife_mount"): (
        "dtrefactor: reads CASTING_UNDERSIDE_Y, MOUNT_GAP, STUD_TAP_DEPTH"
    ),
    ("build_sm_summing_assembly.py", "build_fr_top_frame"): (
        "dtrefactor: reads RING_HEIGHT, STUD_HOLE_DIA"
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
    assert {"dt_cone_swing_platform_geometry.py", "vn_fillister_screw_spec.py"} <= names
    reached = {
        path.name: builders for path in library if (builders := _reached_builders(path))
    }
    assert not reached, f"read the part's spec, not its builder: {reached}"


def test_a_builder_import_in_a_pure_module_goes_red(tmp_path):
    """Fail-first for the guard above: a synthetic spec that imports a builder
    is caught through the same closure the build graph uses."""
    planted = tmp_path / "planted_spec.py"
    planted.write_text("from build_vn_foot_screw import THREAD\n", encoding="utf-8")
    assert _reached_builders(planted) == ["build_vn_foot_screw"]
    clean = tmp_path / "clean_spec.py"
    clean.write_text("from vn_foot_screw_spec import THREAD\n", encoding="utf-8")
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
    _chain_link -> _chain -> _common, and _config arrives via _common's lazy
    import (so parts.yaml-driven custom properties stay correctly tracked)."""
    links = _helper_names("build_vn_chain_inner_link.py")
    assert {"_chain_link", "_chain", "_common"} <= links, links
    assert "_config" in _helper_names("build_vn_cone_tip_collar.py"), (
        "lazy _config edge lost"
    )


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
    """The read-set follows the actual _config calls, at SUB-FILE granularity:
    a gear reads machine("gear_train", ...) -> machine/gear_train.yaml ONLY, so a
    machine channels.active_count edit (machine/channels.yaml) skips it -- the
    original problem. The channel/drive-train assemblies read channels.yaml
    (amplitudes/cone_teeth); every part needs the parts registry via _common."""
    cone = config_files_of(SCRIPTS_DIR / "build_dt_cone_gear.py")
    assert "machine/gear_train.yaml" in cone
    assert "machine/channels.yaml" not in cone, (
        "gear must NOT depend on active_count's file"
    )
    assert "parts/*" in cone, "stamps its own properties -> parts registry token"
    assert "channels.yaml" in config_files_of(script_for("dt_drive_train"))
    assert "channels.yaml" in config_files_of(script_for("ch_channel"))


def test_config_files_subset_of_known_tokens():
    """Every real script resolves to known tokens (concrete files that exist, or
    the machine/* | parts/* | title_block | ** dynamic tokens). The set can only
    NARROW the old whole-config dep, never invent a missing-file dependency."""
    globs = {"machine/*", "parts/*", "title_block", "**"}
    for stem in part_stems():
        for tok in config_files_of(SCRIPTS_DIR / f"build_{stem}.py"):
            assert tok in globs or (bg.CONFIG_DIR / tok).is_file(), f"{stem}: {tok}"


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
    assert _tokens("import _config\nx = _config.fit('g', 'k')\n") == frozenset(
        {"tolerances.yaml"}
    )
    assert _tokens("import _config\nx = _config.release_revision()\n") == frozenset(
        {"release.yaml"}
    )
    assert _tokens("import _config\nx = _config.channels()\n") == frozenset(
        {"channels.yaml"}
    )
    assert _tokens("import _config\nx = _config._doc('tolerances')\n") == frozenset(
        {"tolerances.yaml"}
    )
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
    wrapper = scripts / "build_vn_frame_side_screw.py"
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

    leaf = SCRIPTS_DIR / "build_vn_fillister_screw.py"
    assert stamps_part_properties(leaf)
    assert stamps_title_block_properties(leaf)


def test_git_executable_is_resolved_absolute(tmp_path, monkeypatch):
    import _common

    discovered = tmp_path / "bin" / "git"
    monkeypatch.setattr(_common.shutil, "which", lambda command: str(discovered))
    _common._git_executable.cache_clear()
    try:
        executable = Path(_common._git_executable())
        assert executable == discovered.resolve()
        assert executable.is_absolute()
    finally:
        _common._git_executable.cache_clear()


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

    import _common
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
            [_common._git_executable(), *args],
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

    monkeypatch.setattr(_common, "CAD_ROOT", origin)
    full_id = _common._build_id()
    monkeypatch.setattr(_common, "CAD_ROOT", leaf)
    leaf_id = _common._build_id()

    assert full_id == leaf_id == "v9"

    git(leaf, "config", "status.showUntrackedFiles", "no")
    (leaf / "uncommitted.txt").write_text("operator edit\n", encoding="utf-8")
    assert _common._build_id() == "v9-dirty"


def test_build_id_translates_a_failed_dirty_probe(monkeypatch):
    import subprocess

    import pytest

    import _common

    def fake_run(command, **_kwargs):
        raise subprocess.CalledProcessError(128, command, stderr="not a git repo")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(
        RuntimeError, match="cannot determine Git working-tree state"
    ) as error:
        _common._build_id()
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
    selected = frozenset({"vn-frame-side-screw"})
    before = bg.dict_table_recipe(_CATALOG, "FASTENERS", selected)
    assert bg.dict_table_recipe(
        _row_edited(_CATALOG, "vn-clamp-screw"), "FASTENERS", selected
    ) == before, "another row's edit must not move this row's recipe"
    assert (
        bg.dict_table_recipe(
            _row_edited(_CATALOG, "vn-frame-side-screw"), "FASTENERS", selected
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
    marker = '"vn-frame-side-screw": _stock('
    assert _CATALOG.count(marker) == 1
    removed = _CATALOG.replace(marker, '"vn-frame-side-screw-x": _stock(', 1)
    assert bg.dict_table_recipe(_CATALOG, "FASTENERS", ghost) == bg.dict_table_recipe(
        removed, "FASTENERS", ghost
    )
    assert bg.dict_table_recipe(
        _CATALOG, "FASTENERS", frozenset({"vn-frame-side-screw"})
    ) != bg.dict_table_recipe(removed, "FASTENERS", frozenset({"vn-frame-side-screw"}))


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


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        # Listed themselves: the root script is not in its own import closure
        # (Codex #1035, PRRT_kwDOPHDy386mV11b).
        ("build_mg_wheel_bar.py", True),
        ("build_vn_swing_stop_screw.py", True),
        # Reads through an imported listed module.
        ("build_vn_boss_hook.py", True),
        ("build_vn_spring_hook.py", True),
        # R9-48: judges its lock taps at the printed worst case.
        ("build_pd_platen_guide.py", True),
    ],
)
def test_reads_title_block_geometry_covers_root_and_closure(script, expected):
    assert bg.reads_title_block_geometry(SCRIPTS_DIR / script) is expected

