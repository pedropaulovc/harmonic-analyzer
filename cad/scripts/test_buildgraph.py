r"""Static tests for the build-graph enumeration (no SolidWorks required).

``_buildgraph`` is pure filesystem/string logic, so this runs in plain CI:

    python cad/scripts/test_buildgraph.py        # or: pytest cad/scripts/test_buildgraph.py
"""

from __future__ import annotations

import sys
import ast
from collections import Counter
import tempfile
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


def _helper_names(stem_script: str) -> set[str]:
    return {Path(p).stem for p in module_deps_of(SCRIPTS_DIR / stem_script)}


# Audited against each builder's insertion calls, local tuple/batch manifests,
# generated spring family and top-level SUBASSEMBLIES (not the old regex output).
_INSERTED_SOURCES = {
    "frame": "fillister_screw frame_side_screw gooseneck_set_screw harmonic_base "
    "lag_screw nameplate rocker_arm_support top_frame tube_frame",
    "drive_train": "alignment_pinion arbor_pedestal cone_gear cone_gear_shaft "
    "cone_lock_knob cone_pivot_post cone_pivot_screw cone_swing_platform "
    "cone_tip_adjuster cone_tip_block cone_tip_bushing cone_tip_pinch_screw "
    "crank_arm crank_drive_gear crank_handle crank_pin crank_pin_eye crank_pin_ring "
    "crank_pinion crankshaft cylinder_end_disc cylinder_gear cylinder_gear_shaft "
    "dome_cap_screw fillister_screw foot_screw pinion_arbor pinion_bracket pinion_cam "
    "pinion_cam_pin pinion_handle pinion_lever pinion_lift_rod pinion_pivot_block "
    "pinion_pivot_shaft pinion_spring slotted_screw swing_stop_screw",
    "channel": "amplitude_bar channel_lever channel_spring_installed connecting_rod "
    "frame_side_screw fulcrum_keeper fulcrum_shaft pivot_bracket pivot_shaft "
    "rocker_arm spring_hook",
    "summing": "boss_hook counter_spring gooseneck knife_hanger_stud knife_mount summing_lever",
    "magnifier": "clamp_screw column_clamp_back column_clamp_front lever_wire "
    "magnifying_bracket magnifying_clamp magnifying_lever magnifying_vertical_rod "
    "magnifying_wheel output_fixture thumb_screw wheel_axle wheel_axle_nut wheel_bar",
    "pen": "hanger_screw pen_frame pen_hanger pen_marker pen_rod pen_set_screw pen_v_block pen_wire",
    "paper_drive": "bracket_screw chain_inner_link chain_outer_link clamp_screw "
    "column_clamp_back column_clamp_front fillister_screw guide_lock latch_hook "
    "platen platen_clip platen_guide platen_paper platen_rack rack_pinion support_bar "
    "transgear_bracket transgear_feed_pinion transgear_knob_shaft transgear_latch "
    "transgear_pinion transgear_removable transgear_stub transgear_thumbnut",
    "harmonic_analyzer": "measuring_stick measuring_stick_stop frame drive_train "
    "channel summing magnifier pen paper_drive",
}


@pytest.mark.parametrize("assembly", ASSEMBLY_ORDER)
def test_all_assembly_references_match_inserted_source_manifests(assembly):
    assert set(references_of(assembly)) == set(_INSERTED_SOURCES[assembly].split())


def _source_references(tmp_path, monkeypatch, source, parts=("rocker_arm",)):
    script = tmp_path / "build_parent_assembly.py"
    script.write_text(source, encoding="utf-8")
    monkeypatch.setattr(bg, "script_for", lambda _stem: script)
    monkeypatch.setattr(bg, "part_stems", lambda: list(parts))
    monkeypatch.setattr(bg, "ASSEMBLY_ORDER", ("parent", "channel"))
    return set(bg.references_of("parent"))


def test_reference_parser_ignores_prose_comments_and_non_source_literals(
    tmp_path, monkeypatch
):
    source = '''"""The "channel" assembly does not belong here."""
# Previously "channel" was mentioned by a diagnostic.
raise AssertionError("channel station_z0 does not carry the fixed-post recenter")
log("channel")
label = "rocker-arm"
'''
    assert _source_references(tmp_path, monkeypatch, source) == set()


def test_exact_source_name_does_not_reference_shorter_stem(tmp_path, monkeypatch):
    source = "await place_component(adapter, 'rocker-arm-support', pos, rot, rows)"
    assert _source_references(
        tmp_path, monkeypatch, source, ("rocker_arm", "rocker_arm_support")
    ) == {"rocker_arm_support"}


@pytest.mark.parametrize(
    "expression", ["lookup_part()", "runtime_name", 'f"{runtime_name}"']
)
def test_unresolved_source_argument_fails_without_all_assembly_fallback(
    tmp_path, monkeypatch, expression
):
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path,
            monkeypatch,
            f"await place_component(adapter, {expression}, pos, rot, rows)",
        )


@pytest.mark.parametrize(
    "source",
    [
        "from _assembly import place_component as put\nawait put(adapter, part='rocker-arm', position=p, rotation=r, rows=q)",
        "part = 'rocker-arm'; await place_component(adapter, part, p, r, q)",
        "for part in ('rocker-arm',):\n    await place_component(adapter, part, p, r, q)",
        "riders = [('rocker-arm', p)]\nfor part, pos in riders:\n    await place_component(adapter, part, pos, r, q)",
        "async def place(adapter, part):\n    await place_component(adapter, part, p, r, q)\nawait place(adapter, 'rocker-arm')",
        "await adapter.insert_component(InsertComponentParameters(file_path='C:/cad/rocker-arm.SLDPRT'))",
        "parts = [{'part': 'rocker-arm'}]\nawait place_components_batch(adapter, parts)",
        "parts = []\nparts.append({'part': 'rocker-arm'})\nawait place_components_batch(adapter, parts)",
        "parts = [{'part': 'rocker-arm'}]\nawait place_components_batch(adapter, specs=parts)",
    ],
)
def test_reference_source_call_shapes(tmp_path, monkeypatch, source):
    assert _source_references(tmp_path, monkeypatch, source) == {"rocker_arm"}


def test_ambiguous_dynamic_source_family_keeps_every_possible_producer(
    tmp_path, monkeypatch
):
    source = "await place_component(adapter, f'rocker-arm{suffix}', p, r, q)"
    assert _source_references(
        tmp_path, monkeypatch, source, ("rocker_arm", "rocker_arm_support")
    ) == {"rocker_arm", "rocker_arm_support"}


@pytest.mark.parametrize(
    "source",
    [
        "parts = []\nparts.extend(runtime_parts())\nawait place_components_batch(adapter, parts)",
        "parts = []\nparts += runtime_parts()\nawait place_components_batch(adapter, parts)",
        "parts = []\nalias = parts\nalias.append({'part': 'rocker-arm'})\nawait place_components_batch(adapter, parts)",
        "parts = alias = []\nalias.append({'part': 'rocker-arm'})\nawait place_components_batch(adapter, parts)",
        "parts = []\nparts[0] = {'part': 'rocker-arm'}\nawait place_components_batch(adapter, parts)",
        "parts = [{'part': 'rocker-arm'}]\nfor spec in parts:\n    spec['part'] = runtime_part()\nawait place_components_batch(adapter, parts)",
        "parts = []\nmutate(parts)\nawait place_components_batch(adapter, parts)",
        "await place_components_batch(adapter, runtime_parts())",
        "await place_components_batch(adapter, [{'part': 'rocker-arm', **runtime_fields()}])",
        "await adapter.insert_component(runtime_parameters())",
        "part = 'rocker-arm'\npart += runtime_suffix()\nawait place_component(adapter, part, p, r, q)",
        "await place_component(adapter, 'rocker-arm-misspelled', p, r, q)",
        "put = place_component\nawait put(adapter, 'rocker-arm', p, r, q)",
    ],
)
def test_unsupported_source_manipulation_fails_loud(tmp_path, monkeypatch, source):
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(tmp_path, monkeypatch, source)


def test_reference_syntax_cache_detects_source_edits_and_resolves_current_registry(
    tmp_path, monkeypatch
):
    source = "await place_component(adapter, 'rocker-arm', p, r, q)"
    assert _source_references(tmp_path, monkeypatch, source) == {"rocker_arm"}
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(tmp_path, monkeypatch, source, ("rocker_arm_support",))
    changed = "await place_component(adapter, 'rocker-arm-support', p, r, q)"
    assert _source_references(
        tmp_path, monkeypatch, changed, ("rocker_arm_support",)
    ) == {"rocker_arm_support"}


def test_local_path_wrapper_must_prove_it_preserves_source_name(tmp_path, monkeypatch):
    source = """def _part(name):
    path = (OUT_SLDPRT / f"{name}.SLDPRT").resolve()
    return str(path)
await adapter.insert_component(InsertComponentParameters(file_path=_part("rocker-arm")))
"""
    assert _source_references(tmp_path, monkeypatch, source) == {"rocker_arm"}
    changed = source.replace('f"{name}.SLDPRT"', '"rocker-arm-support.SLDPRT"')
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, changed, ("rocker_arm", "rocker_arm_support")
        )


def test_later_module_bindings_are_conservative_for_function_sources(
    tmp_path, monkeypatch
):
    source = """PART = 'rocker-arm'
async def build(adapter):
    await place_component(adapter, PART, p, r, q)
PART = 'rocker-arm-support'
"""
    assert _source_references(
        tmp_path, monkeypatch, source, ("rocker_arm", "rocker_arm_support")
    ) == {"rocker_arm", "rocker_arm_support"}


def test_memo_lookup_keeps_initial_values_and_explicit_default(tmp_path, monkeypatch):
    source = """memo = {'old': 'rocker-arm'}
part = memo.get(key, 'rocker-arm-support')
memo[key] = 'rocker-arm-support'
await place_component(adapter, part, p, r, q)
"""
    assert _source_references(
        tmp_path, monkeypatch, source, ("rocker_arm", "rocker_arm_support")
    ) == {"rocker_arm", "rocker_arm_support"}


def test_later_module_manifest_appends_are_not_silently_lost(tmp_path, monkeypatch):
    source = """parts = []
async def build(adapter):
    await place_components_batch(adapter, parts)
parts.append({'part': 'rocker-arm'})
"""
    assert _source_references(tmp_path, monkeypatch, source) == {"rocker_arm"}


@pytest.mark.parametrize(
    "source",
    [
        "specs = [{'part': 'rocker-arm'}]\nmutate(items=specs)\nawait place_components_batch(adapter, specs)",
        "specs = [{'part': 'rocker-arm'}]\nfor spec in specs:\n    spec['part']: str = 'rocker-arm-support'\nawait place_components_batch(adapter, specs)",
        "specs = [{'part': 'rocker-arm'}]\nfor spec in specs:\n    mutate(row=spec)\nawait place_components_batch(adapter, specs)",
        "memo = {'k': 'rocker-arm'}\nalias = memo\nalias['k'] = 'rocker-arm-support'\npart = memo.get(key)\nawait place_component(adapter, part, p, r, q)",
        "memo = {'k': 'rocker-arm'}\nmutate(items=memo)\npart = memo.get(key)\nawait place_component(adapter, part, p, r, q)",
        "memo = {'k': 'rocker-arm'}\nalias: dict = memo\nalias['k'] = 'rocker-arm-support'\npart = memo.get(key)\nawait place_component(adapter, part, p, r, q)",
        "memo = alias = {'k': 'rocker-arm'}\nalias['k'] = 'rocker-arm-support'\npart = memo.get(key)\nawait place_component(adapter, part, p, r, q)",
        "specs = [{'part': 'rocker-arm'}]\nfor spec in specs:\n    alias: dict = spec\n    alias['part'] = 'rocker-arm-support'\nawait place_components_batch(adapter, specs)",
    ],
)
def test_review_keyword_and_annotated_mutations_never_drop_sources(
    tmp_path, monkeypatch, source
):
    with pytest.raises(ValueError, match="[Uu]nresolved assembly source"):
        _source_references(
            tmp_path, monkeypatch, source, ("rocker_arm", "rocker_arm_support")
        )


_SOURCE_VALUE_IMPORTS = {
    ("build_magnifier_assembly", "build_summing_assembly"): {
        "KNIFE",
        "KNIFE_CONTACT_Y",
    },
    ("build_paper_drive_assembly", "build_drive_train_assembly"): {
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
    source = "from _extra import insert_extra\nawait place_component(adapter, 'rocker-arm', p, r, q)\nawait insert_extra(adapter)"
    helper = "async def insert_extra(adapter):\n    await place_component(adapter, 'rocker-arm-support', p, r, q)"
    # This is exactly the old coverage hole: the parent manifest alone stays A.
    assert _source_references(
        tmp_path, monkeypatch, source, ("rocker_arm", "rocker_arm_support")
    ) == {"rocker_arm"}
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
        source += "\nasync def insert_extra(adapter):\n    await place_component(adapter, 'rocker-arm-support', p, r, q)\n"
    if change == "single source":
        source = source.replace(
            "file_path=str(path)", 'file_path="rocker-arm-support.SLDPRT"'
        )
    if change == "batch source":
        source = source.replace('part = spec["part"]', 'part = "rocker-arm-support"')
    if change == "batch row mutation":
        source = source.replace(
            'part = spec["part"]',
            'spec["part"] = "rocker-arm-support"\n        part = spec["part"]',
        )
    if change == "single loop binding":
        source = source.replace(
            "label = label or part",
            'for part in ["rocker-arm-support"]:\n        pass\n    label = label or part',
        )
    if change == "single path loop binding":
        source = source.replace(
            "        if not path.exists():",
            '        for path in [Path("rocker-arm-support.SLDPRT")]:\n            pass\n        if not path.exists():',
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
            '    names_arg.value = ["rocker-arm-support.SLDPRT"]\n    xforms_arg = VARIANT',
        )
    with pytest.raises(AssertionError):
        _assert_source_import_contract({"_assembly": source})


def test_references_is_inverse_of_dependents():
    """``references_of`` is the DIRECT inverse of the legacy ``dependents_of``.

    ``dependents_of`` adds a transitive ``harmonic_analyzer`` edge whenever a part
    flows into any sub-assembly (the old --rebuild's "rebuild the top too"). The
    doit graph propagates that through ``<sub>.SLDASM -> harmonic-analyzer.SLDASM``
    instead, so ``references_of`` carries only direct edges. The two must agree
    exactly once that documented transitive add is accounted for.
    """
    candidates = part_stems() + list(ASSEMBLY_ORDER)
    for s in candidates:
        direct = {a for a in ASSEMBLY_ORDER if s in references_of(a)}
        legacy = set(dependents_of(s))
        if direct and "harmonic_analyzer" not in direct:
            assert legacy == direct | {"harmonic_analyzer"}, (
                f"{s}: legacy {legacy} != direct {direct} + transitive top"
            )
        else:
            assert legacy == direct, f"{s}: legacy {legacy} != direct {direct}"


def test_output_subs_reference_their_parts_only():
    """Each output sub inserts leaf parts, never another sub-assembly."""
    for stem in ("summing", "magnifier", "pen", "paper_drive"):
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
    refs = set(references_of("harmonic_analyzer"))
    subs = {
        "frame",
        "drive_train",
        "channel",
        "summing",
        "magnifier",
        "pen",
        "paper_drive",
    }
    loose = {"measuring_stick", "measuring_stick_stop"}
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


def test_module_deps_are_transitive():
    """The closure follows imports through helper chains: a chain-link part pulls
    _chain_link -> _chain -> _common, and _config arrives via _common's lazy
    import (so parts.yaml-driven custom properties stay correctly tracked)."""
    links = _helper_names("build_chain_inner_link.py")
    assert {"_chain_link", "_chain", "_common"} <= links, links
    assert "_config" in _helper_names("build_cone_tip_bushing.py"), (
        "lazy _config edge lost"
    )


def test_closure_follows_reused_build_scripts():
    """A part that reuses a shared helper inherits that helper's own closure:
    channel-spring-installed imports _spring (the shared spring builder, which
    imports _features), so an edit to _features must mark it stale (codex
    review #2)."""
    deps = _helper_names("build_channel_spring_installed.py")
    assert "_spring" in deps, deps
    assert "_features" in deps, deps


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
    deps = data_deps_of(SCRIPTS_DIR / "build_nameplate.py")
    assert any(d.endswith("nameplate-engraving.dxf") for d in deps), deps
    # A build that imports no DXF/DWG has no data deps.
    assert data_deps_of(SCRIPTS_DIR / "build_platen.py") == []


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
    cone = config_files_of(SCRIPTS_DIR / "build_cone_gear.py")
    assert "machine/gear_train.yaml" in cone
    assert "machine/channels.yaml" not in cone, (
        "gear must NOT depend on active_count's file"
    )
    assert "parts/*" in cone, "stamps its own properties -> parts registry token"
    assert "channels.yaml" in config_files_of(script_for("drive_train"))
    assert "channels.yaml" in config_files_of(script_for("channel"))


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
    back into module_deps_of/config_files_of -- that would rebuild assembly:pen on
    every amplitude edit for an equation the saved model does not even contain. The
    guard for the transient equation moved to dodo.task_verify's kinematics
    file_dep (pinned in test_dodo_recipe.py)."""
    closure = {Path(p).stem for p in module_deps_of(script_for("pen"))}
    assert closure.isdisjoint({"pen_driver", "truth_model"}), closure
    pen_cfg = config_files_of(script_for("pen"))
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
    assert part_stampers == {"channel"}

    leaf = SCRIPTS_DIR / "build_fillister_screw.py"
    assert stamps_part_properties(leaf)
    assert stamps_title_block_properties(leaf)


def test_assembly_title_properties_never_read_part_registry_fields():
    props = assembly_title_properties("frame")
    assert set(props) == {
        "Title",
        "Revision",
        "Generator",
        "TOL_LIN_XX",
        "TOL_LIN_XXX",
        "TOL_ANG",
        "TOL_SURFACE",
        "TOL_HOLE_MINUS",
        "TOL_HOLE_PLUS",
    }
    assert props["Title"] == "frame"
    import _config

    assert props["Revision"] == _config.release_revision()
    assert props["Generator"].startswith("harmonic-analyzer @ ")


def test_part_properties_use_release_revision():
    import _config

    assert part_properties("platen-guide")["Revision"] == _config.release_revision()


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
