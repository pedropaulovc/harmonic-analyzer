"""Offline drawing requirements, exact datum domains and raw STEP binding."""

from __future__ import annotations

import asyncio
import ast
import builtins
from collections import Counter
from dataclasses import replace
import hashlib
import importlib
import importlib.util
import math
import sys
import tomllib
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import yaml
from prechips.model import Features

import export_features as exporter
import _config
import ch_pivot_shaft_spec as shaft
import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_spec as rocker
import _rocker_interface as rocker_interface
import dt_cone_pivot_post_spec as cone
import rocker_bank_layout as bank
from _export_feature_faces import FeatureFaceError, face_name
from _feature_requirements import declaration_calls, discover_parts, metadata_for, requirements_for, source_tree
from _gtol_face import FaceGeometry


def _fresh_draw(monkeypatch, stem: str):
    import _session
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    def refuse(*_args, **_kwargs):
        pytest.fail("drawing import attempted a SolidWorks session or output write")

    monkeypatch.setattr(_session, "run_build", refuse)
    monkeypatch.setattr(PyWin32Adapter, "__init__", refuse)
    monkeypatch.setattr(PyWin32Adapter, "connect", refuse)
    monkeypatch.setattr(Path, "write_bytes", refuse)
    monkeypatch.setattr(Path, "write_text", refuse)
    name = f"draw_{stem}"
    path = exporter.REPO / "cad" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _step_labels(stem: str) -> list[str]:
    labels = [face_name(feature, 1) for feature in exporter.feature_selectors(stem)]
    if stem == "ch_rocker_arm":
        labels.insert(0, face_name("pivot_bore", 1))
    return labels


def _step(tmp_path: Path, stem: str) -> Path:
    labels = _step_labels(stem)
    rows = ["ISO-10303-21;", "HEADER;", "ENDSEC;", "DATA;"]
    rows += [f"#{index} = ADVANCED_FACE('{label}',(#1),#2,.T.);" for index, label in enumerate(labels, start=10)]
    rows += ["ENDSEC;", "END-ISO-10303-21;"]
    path = tmp_path / stem / f"{stem.replace('_', '-')}.STEP"
    path.parent.mkdir(parents=True)
    path.write_bytes("\r\n".join(rows).encode("utf-8"))
    return path


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _plane(
    normal: tuple[float, float, float], point_mm: tuple[float, float, float]
) -> FaceGeometry:
    return FaceGeometry(None, 4001, (*normal, *(v / 1000 for v in point_mm)), normal, ())


def _owners(stem: str, geometry: FaceGeometry) -> list[str]:
    return [
        feature for feature, selectors in exporter.feature_selectors(stem).items()
        if any(selector.matches(geometry) for selector in selectors)
    ]


def test_adding_a_draw_declaration_is_discovered_without_importing(tmp_path: Path) -> None:
    path = tmp_path / "draw_synthetic_part.py"
    original = (
        "from _feature_requirements import requirement\n"
        "from _gtol_cylinder import CylinderFace\n"
        "raise RuntimeError('discovery must not import this drawing')\n"
        "TEXT = \"requirement('not_a_declaration')\"\n"
        "def drawing_helper():\n"
        "    requirement('not_module_level', kind='hole', faces=(CylinderFace(5.0),),\n"
        "                requirements=('dia',), fields={'dia': ([4.9, 5.1], ('BORE_DIA',))})\n"
    )
    path.write_text(original, encoding="utf-8")
    assert discover_parts(tmp_path) == ()
    path.write_text(
        original
        + "BORE = requirement('bore', kind='hole', faces=(CylinderFace(5.0),),\n"
        + "                   requirements=('dia',), fields={'dia': ([4.9, 5.1], ('BORE_DIA',))})\n",
        encoding="utf-8",
    )
    assert discover_parts(tmp_path) == ("synthetic_part",)
    assert "draw_synthetic_part" not in sys.modules


@pytest.mark.parametrize("source", [
    "requirement('unbound')",
    "import unrelated\nunrelated.requirement('wrong_module')",
    "from unrelated import requirement\nrequirement('wrong_import')",
    "from _feature_requirements import part_metadata as requirement\nrequirement('wrong_api')",
    "from _feature_requirements import requirement\nrequirement = lambda *args: None\nrequirement('rebound')",
    "from _feature_requirements import requirement\nif condition:\n    requirement = None\nrequirement('possibly_rebound')",
    "while condition:\n    from _feature_requirements import requirement\nrequirement('unbound_after_loop')",
    "try:\n    from _feature_requirements import requirement\nexcept ImportError:\n    requirement('unbound_in_handler')",
    "match candidate:\n    case 1:\n        from _feature_requirements import requirement\n    case 2:\n        requirement('unbound_in_other_case')",
    "from _feature_requirements import requirement\nmatch candidate:\n    case {'key': requirement}:\n        requirement('shadowed_by_pattern')",
])
def test_wrong_or_unbound_api_does_not_discover_a_part(tmp_path: Path, source: str) -> None:
    (tmp_path / "draw_not_enrolled.py").write_text(source, encoding="utf-8")
    assert discover_parts(tmp_path) == ()


@pytest.mark.parametrize("source", [
    "from _feature_requirements import requirement as declare\nfor item in things:\n    declare(item)",
    "import _feature_requirements as features\nwith context:\n    features.requirement('bound')",
    "if condition:\n    from _feature_requirements import requirement\n    requirement('bound_in_branch')",
])
def test_import_bound_api_in_module_control_flow_discovers_a_part(tmp_path: Path, source: str) -> None:
    (tmp_path / "draw_enrolled.py").write_text(source, encoding="utf-8")
    assert discover_parts(tmp_path) == ("enrolled",)


def test_source_paths_never_import_draw_spec_or_citation_modules(monkeypatch) -> None:
    importlib.import_module("_buildgraph")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("draw_") or name.endswith(("_spec", "_notes")):
            pytest.fail(f"source_paths imported a declaration input: {name}")
        return original_import(name, *args, **kwargs)

    def refuse_import_module(name, *_args, **_kwargs):
        pytest.fail(f"source_paths dynamically imported {name}")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(importlib, "import_module", refuse_import_module)
    for stem in exporter.SUPPORTED_PARTS:
        paths = exporter.source_paths(stem)
        assert paths and all(path.is_file() for path in paths), stem
        assert any(path.name == f"draw_{stem}.py" for path in paths), stem


@pytest.mark.parametrize("member_owner", [False, True])
def test_source_paths_cover_unimported_runtime_tuple_sources_and_their_closure(tmp_path: Path, monkeypatch, member_owner) -> None:
    import _buildgraph

    scripts = tmp_path / "cad" / "scripts"
    scripts.mkdir(parents=True)
    spec_name = "shared_member_spec" if member_owner else "synthetic_spec"
    files = {
        "export_features.py": "",
        "draw_synthetic.py": (
            "from _feature_requirements import requirement, part_metadata\n"
            + ("FEATURE_SPEC_MODULE = 'shared_member_spec'\n" if member_owner else "")
            + "raise RuntimeError('source discovery must not execute this')\n"
            "_AUTHORITY = ('unimported_authority', 'PRINTED_NOTE')\n"
            "def _fields():\n"
            "    return {'note': ('printed', (_AUTHORITY,))}\n"
            "requirement('synthetic', fields=_fields())\n"
            "part_metadata(precision_sources=(('unimported_precision', 'PLACES'),))\n"
        ),
        f"{spec_name}.py": "import authority_dependency\nraise RuntimeError('must not import the spec')\n",
        "synthetic_notes.py": "raise RuntimeError('must not import the notes')\n",
        "unimported_authority.py": "import authority_dependency\nPRINTED_NOTE = 'printed'\n",
        "unimported_precision.py": "PLACES = 2\n",
        "authority_dependency.py": "raise RuntimeError('must not import the cited closure')\n",
    }
    for name, content in files.items():
        (scripts / name).write_text(content, encoding="utf-8")
    monkeypatch.setattr(exporter, "__file__", str(scripts / "export_features.py"))
    monkeypatch.setattr(exporter, "CONFIG_DIR", tmp_path / "cad" / "config")
    monkeypatch.setattr(exporter, "SUPPORTED_PARTS", ("synthetic",))
    with monkeypatch.context() as graph:
        graph.setattr(_buildgraph, "SCRIPTS_DIR", scripts)
        _buildgraph.clear_import_caches()
        try:
            paths = set(exporter.source_paths("synthetic"))
            assert {scripts / name for name in files} <= paths
            for name in ("draw_synthetic", spec_name, "synthetic_notes", "unimported_authority", "unimported_precision", "authority_dependency"):
                assert name not in sys.modules
            (scripts / "unimported_precision.py").unlink()
            with pytest.raises(ValueError, match="missing citation source module: unimported_precision"):
                exporter.source_paths("synthetic")
        finally:
            _buildgraph.clear_import_caches()


@pytest.mark.parametrize("declaration", [
    "FEATURE_SPEC_MODULE = name",
    "FEATURE_SPEC_MODULE = 42",
    "FEATURE_SPEC_MODULE = 'member_spec'\nFEATURE_SPEC_MODULE = 'member_spec'",
    "FEATURE_SPEC_MODULE = 'missing_spec'",
    "FEATURE_SPEC_MODULE = '../member_spec'",
])
def test_feature_spec_owner_refuses_dynamic_duplicate_missing_or_invalid_modules(tmp_path, declaration):
    (tmp_path / "draw_synthetic.py").write_text(declaration, encoding="utf-8")
    (tmp_path / "member_spec.py").write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        exporter._spec_module_name("synthetic", tmp_path)


def test_shared_stud_features_use_actual_default_member_spec_and_rework_provenance() -> None:
    import sh_vn_clamping_kit_hold_down_stud_spec as stud

    stem = "sh_vn_clamping_kit_hardware"
    assert stem in exporter.SUPPORTED_PARTS
    assert exporter._spec_module(stem) is stud
    assert _config.parts(stem.replace("_", "-"))["default_configuration"] == stud.CONFIGURATION == "HoldDownStud"
    paths = exporter.source_paths(stem)
    assert Path(stud.__file__).resolve() in paths
    assert any(path.name == "ch_rocker_arm_tl_oblique_fasteners_spec.py" for path in paths)
    assert not any(path.name == f"{stem}_spec.py" for path in paths)
    assert exporter.step_configurations(stem) == ()
    manifest = exporter.requirement_manifest(stem)
    assert manifest["drawing"]["number"] == "MHA-SH-VN-57"
    assert manifest["volume_mm3"] == stud.VOLUME_MM3
    assert manifest["material"]["finish"] == stud.FINISH
    assert manifest["notes"]["process"] == stud.PROCESS
    assert manifest["notes"]["manufacturing"] == stud.DRAWING_NOTES.splitlines()
    assert set(manifest["features"]) == {"finished_upper_end", "cut_end_chamfer"}
    assert manifest["features"]["finished_upper_end"]["length"] == [56.4, 58.0]
    assert manifest["features"]["cut_end_chamfer"]["length"] == [0.0, 1.0]
    assert set(exporter._cite(stud, "FINISH")) <= set(manifest["material"]["cite"])
    assert set(exporter._cite(stud, "PROCESS")) <= set(manifest["notes"]["cite"])
    registry = "harmonic-analyzer/cad/config/parts/sh-vn-clamping-kit-hardware.yaml:sh-vn-clamping-kit-hardware"
    assert f"{registry}.finish" not in manifest["material"]["cite"]
    assert f"{registry}.process" not in manifest["notes"]["cite"]
    # Common purchase metadata and untouched configurations never become rework.
    assert _config.parts(stem.replace("_", "-"))["process"] == "purchased"


@pytest.mark.parametrize("default", [None, "TNut", "FlangeNut"])
def test_shared_stud_feature_owner_refuses_a_different_saved_default(monkeypatch, default):
    original = _config.parts

    def parts(stem):
        row = original(stem)
        return {**row, "default_configuration": default} if stem == "sh-vn-clamping-kit-hardware" else row

    monkeypatch.setattr(_config, "parts", parts)
    with pytest.raises(ValueError, match="saved default configuration"):
        exporter.requirement_manifest("sh_vn_clamping_kit_hardware")


def test_source_tree_cache_reads_current_contents_even_at_the_same_path(tmp_path: Path) -> None:
    path = tmp_path / "source.py"
    path.write_text("FIRST = 1\n", encoding="utf-8", newline="\n")
    first = source_tree(path)
    assert source_tree(path) is first
    path.write_text("OTHER = 2\n", encoding="utf-8", newline="\n")
    second = source_tree(path)
    assert second is not first
    assert second.body[0].targets[0].id == "OTHER"
    path.write_bytes(b"OTHER = 2\r\n")
    assert source_tree(path) is not second


def test_assignment_subscript_and_attribute_targets_cannot_hijack_symbol_citations(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "authority.py"
    path.write_text(
        "KEY = 'printed authority'\nTABLE = {}\nTABLE[KEY] = 'not the authority'\n"
        "TABLE.KEY = 'not a declaration'\nFIRST, [SECOND, THIRD] = values\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(exporter, "REPO", tmp_path)
    module = ModuleType("authority")
    module.__file__ = str(path)
    tree = source_tree(path)
    expected = f"harmonic-analyzer/authority.py:{tree.body[0].lineno}-{tree.body[0].end_lineno}"
    assert exporter._cite(module, "KEY") == [expected]
    assert {"FIRST", "SECOND", "THIRD"} <= exporter._declarations(module).keys()
    path.write_text("\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    updated = source_tree(path).body[0]
    assert exporter._cite(module, "KEY") == [f"harmonic-analyzer/authority.py:{updated.lineno}-{updated.end_lineno}"]


@pytest.mark.parametrize("stem", exporter.SUPPORTED_PARTS)
def test_draw_declarations_cite_current_calls_and_declared_sources(stem: str) -> None:
    draw = importlib.import_module(f"draw_{stem}")
    declarations = requirements_for(draw)
    features = exporter.requirement_manifest(stem)["features"]
    path = Path(draw.__file__).resolve()
    calls = declaration_calls(source_tree(path), "requirement")
    assert calls, f"{path.name} has no module-level requirement calls"
    relative = path.relative_to(exporter.REPO).as_posix()
    call_citations = {
        f"harmonic-analyzer/{relative}:{call.lineno}-{call.end_lineno}"
        for call in calls
    }
    spec = exporter._spec_module(stem)
    for name, declared in declarations.items():
        feature = features[name]
        assert declared.path == path
        call_citation = f"harmonic-analyzer/{relative}:{declared.call_span[0]}-{declared.call_span[1]}"
        assert call_citation in call_citations, (stem, name, call_citation)
        for field, (value, sources) in declared.fields.items():
            assert feature[field] == (list(value) if isinstance(value, tuple) else value), (stem, name, field)
            citations = set(feature["cite"][field])
            assert call_citation in citations, (stem, name, field, citations)
            for source in sources:
                module, symbol = (
                    (importlib.import_module(source[0]), source[1])
                    if isinstance(source, tuple) else (spec, source)
                )
                assert set(exporter._cite(module, symbol)) <= citations, (stem, name, field, source)
        if declared.precision:
            precision_sources = [
                source for metadata in metadata_for(draw)
                for source in metadata.precision_sources
            ]
            assert precision_sources, (stem, name, "no printed precision authority")
            for source in precision_sources:
                module, symbol = (
                    (importlib.import_module(source[0]), source[1])
                    if isinstance(source, tuple) else (spec, source)
                )
                assert symbol != "__frame__", (stem, name, source)
                assert set(exporter._cite(module, symbol)) <= set(feature["cite"]["precision"]), (stem, name, source)


@pytest.mark.parametrize(
    ("feature_name", "field", "tip_sign"),
    [
        ("top_edge", "radius", None),
        ("top_edge", "radius_nominal", None),
        ("profile_outer", "radial_tip_end", 1),
        ("tip_land_pos_x", "radial_tip_end", 1),
        ("tip_land_neg_x", "radial_tip_end", -1),
    ],
)
def test_rocker_shared_profile_radius_exports_interface_authority(
    feature_name: str, field: str, tip_sign: int | None,
) -> None:
    """Resolve real metadata, not declarations echoed back by a test fake."""
    feature = exporter.requirement_manifest("ch_rocker_arm")["features"][feature_name]
    citations = set(feature["cite"][field])
    assert set(exporter._cite(rocker_interface, "CURVE_RADIUS")) <= citations
    assert citations.isdisjoint(exporter._cite(rocker, "R_TOP"))
    if tip_sign is None:
        assert feature[field] == rocker_interface.CURVE_RADIUS
    else:
        alpha = rocker.TOP_ARC_LEN / (2.0 * rocker_interface.CURVE_RADIUS)
        expected = [
            tip_sign * (rocker_interface.CURVE_RADIUS + rocker.TIP_FACE) * math.sin(alpha),
            rocker_interface.CENTER_Y - (rocker_interface.CURVE_RADIUS + rocker.TIP_FACE) * math.cos(alpha),
        ]
        assert feature[field] == pytest.approx(expected)


@pytest.mark.parametrize("source", ["MISSING_TEST_DIMENSION", ("ch_rocker_arm_spec", "MISSING_TEST_DIMENSION")])
def test_missing_citation_symbol_fails_instead_of_exporting_unsourced_requirements(monkeypatch, source) -> None:
    draw = importlib.import_module("draw_ch_rocker_arm")
    declared = requirements_for(draw)["rod_hole"]
    value, sources = declared.fields["dia"]
    monkeypatch.setitem(declared.fields, "dia", (value, (*sources, source)))
    with pytest.raises(ValueError, match="MISSING_TEST_DIMENSION"):
        exporter.requirement_manifest("ch_rocker_arm")


@pytest.mark.parametrize("sources", [(), ("__frame__",)])
def test_feature_precision_without_explicit_printed_sources_fails(monkeypatch, sources) -> None:
    draw = importlib.import_module("draw_ch_rocker_arm")
    monkeypatch.setattr(
        draw, "_FEATURE_METADATA",
        [replace(metadata, precision_sources=sources) for metadata in metadata_for(draw)],
    )
    with pytest.raises(ValueError, match="precision_sources"):
        exporter.requirement_manifest("ch_rocker_arm")


def _assert_rocker_print_authority() -> None:
    features = exporter.requirement_manifest("ch_rocker_arm")["features"]
    pivot = features["pivot_bore"]
    draw = importlib.import_module("draw_ch_rocker_arm")
    tree = source_tree(Path(draw.__file__))
    dressing = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_dress_detail_dimensions")
    assignments = {
        target.id: node.value
        for node in ast.walk(dressing) if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }
    prefix = eval(compile(ast.Expression(assignments["ream_prefix"]), draw.__file__, "eval"), {}, {"prefix": ""})
    suffix = eval(compile(ast.Expression(assignments["through_suffix"]), draw.__file__, "eval"), {}, {"suffix": ""})
    assert prefix.split()[0] == pivot["process"].upper(), "pivot process drifted from its native dimension text"
    assert pivot["thru"] and "THRU" in suffix, "hole end drifted from its native dimension text"
    # Both ends are dimensioned on the views (J and K LAND rows, both tapers,
    # 2X 5.59): the symmetry is cited to those natives, not a mirror note.
    assert features["profile_outer"]["mirror_symmetric"] and "MIRROR" not in rocker_notes.DRAWING_NOTES
    native_text = set(exporter._cite(draw, "_dress_detail_dimensions"))
    for field in ("process", "thru"):
        assert native_text <= set(pivot["cite"][field])
    for source in ("_add_rocker_outline_dimensions", "_dress_detail_dimensions"):
        assert set(exporter._cite(draw, source)) <= set(features["profile_outer"]["cite"]["mirror_symmetric"])


def test_rocker_requirements_match_their_current_printed_authorities() -> None:
    _assert_rocker_print_authority()


def test_changed_process_is_detected_instead_of_accepting_stale_native_text(monkeypatch) -> None:
    draw = importlib.import_module("draw_ch_rocker_arm")
    declared = requirements_for(draw)["pivot_bore"]
    _value, sources = declared.fields["process"]
    monkeypatch.setitem(declared.fields, "process", ("hone", sources))
    with pytest.raises(AssertionError, match="pivot process drifted"):
        _assert_rocker_print_authority()


@pytest.mark.parametrize("stem", exporter.SUPPORTED_PARTS)
def test_draw_import_registers_declarations_without_starting_solidworks(monkeypatch, stem: str) -> None:
    module = _fresh_draw(monkeypatch, stem)
    assert requirements_for(module), f"{module.__name__}: import did not register declarations"
    assert callable(module.build)


def test_rocker_land_clock_is_the_printed_two_place_basic_nominal(monkeypatch) -> None:
    nominal = 10.516
    monkeypatch.setattr(math, "degrees", lambda _value: nominal)
    _fresh_draw(monkeypatch, "ch_rocker_arm")
    features = exporter.requirement_manifest("ch_rocker_arm")["features"]
    for name in ("tip_land_pos_x", "tip_land_neg_x"):
        assert features[name]["land_angle_nominal_deg"] == nominal
        assert features[name]["precision"]["land_angle_deg"] == 2
        assert features[name]["land_angle_deg"] == round(nominal, 2)
        assert features[name]["dimension_type"] == "basic"


def test_rocker_bands_respect_native_nominals_and_displayed_general_rows() -> None:
    manifest = exporter.requirement_manifest("ch-rocker-arm")
    features = manifest["features"]
    assert manifest["general_tolerances"]["linear_1pl"] == 0.8
    assert manifest["general_tolerances"]["linear_2pl"] == 0.51
    assert manifest["general_tolerances"]["linear_3pl"] == 0.13
    assert features["hub_od"]["dia"] == [9.69, 10.71]
    assert features["hub_faces"]["length"] == [7.0565, 7.1065]
    assert features["hub_faces"]["length_nominal"] == 7.0565
    for name in ("tip_land_pos_x", "tip_land_neg_x"):
        # BASIC: the J↔K profile zone is its band.
        assert features[name]["tip_land"] == rocker.TIP_FACE
        assert features[name]["land_angle_deg"] == round(math.degrees(rocker._ALPHA_TOP), 2)
        assert features[name]["precision"]["land_angle_deg"] == 2
        assert features[name]["dimension_type"] == "basic"
        citations = features[name]["cite"]["land_angle_deg"]
        assert "harmonic-analyzer/cad/config/title_block.yaml:angular.value_deg" not in citations
        assert not any("linear_" in citation for citation in citations)
        assert set(exporter._cite(rocker, "_ALPHA_TOP")) <= set(citations)
        native = set(exporter._cite(importlib.import_module("draw_ch_rocker_arm"), "_dress_detail_dimensions"))
        assert native <= set(citations)
        assert native <= set(features[name]["cite"]["dimension_type"])
        assert native <= set(features[name]["cite"]["top_edge_feature"])
        # Each land's own BASIC LAND row from A (the J row, main-r1 Opus).
        assert features[name]["station"] == rocker.ROD_TIP_X
        assert set(exporter._cite(importlib.import_module("draw_ch_rocker_arm"), "_add_rocker_outline_dimensions")) <= set(features[name]["cite"]["station"])
    assert manifest["material"]["thickness"] == 2.5
    assert exporter._cite(rocker, "ARM_THICKNESS")[0] in manifest["material"]["cite"]
    # The strap's native 2.500 +/-0.025 (Main ruling 2026-10, option b).
    for name in ("strap_datum_b", "strap_faces"):
        assert features[name]["thickness"] == [2.475, 2.525]
        assert features[name]["precision"]["thickness"] == 3
    assert features["rod_hole"]["dia"] == [1.994, 2.094]
    assert features["rod_hole"]["nominal_dia"] == 1.994
    assert features["rod_hole"]["precision"]["dia"] == 2
    assert features["pivot_bore"]["dia"] == [6.50, 6.53]
    assert features["rod_hole"]["at"] == pytest.approx([133.06740213488345, 16.456064115939025, 0.0])


def test_unknown_requirements_and_references_do_not_acquire_acceptance_bands() -> None:
    features = exporter.requirement_manifest("ch_rocker_arm")["features"]
    for name in ("tip_land_pos_x", "tip_land_neg_x"):
        # The land length is BASIC with no band of its own: a field, not a requirement.
        assert features[name]["requirements"] == ["land_angle_deg", "station", "surface_profile"]
    assert features["profile_outer"]["requirements"] == ["bottom_radius", "mirror_symmetric", "surface_profile"]
    assert features["top_edge"]["requirements"] == ["height_above_pivot", "radius", "surface_profile"]
    assert not any("unknown" in fields.get("requirements", ()) for fields in features.values())
    assert "bottom_arc_len" not in features["profile_outer"]["requirements"]
    assert "arc_len" not in features["top_edge"]["requirements"]
    assert features["top_edge"]["radius"] == rocker.R_TOP
    assert features["top_edge"]["height_above_pivot"] == rocker.TOP_EDGE_ABOVE_PIVOT
    assert features["profile_outer"]["bottom_radius"] == rocker_interface.R_BOTTOM
    assert features["top_edge"]["arc_len"] == rocker.TOP_ARC_LEN
    assert features["profile_outer"]["bottom_arc_len"] == rocker.BOT_ARC_LEN
    for name, outside, suffix in (
        ("top_edge", rocker.TOP_EDGE_BAND[0], ""),
        ("profile_outer", rocker.TOP_EDGE_BAND[1], ", BETWEEN J AND K"),
    ):
        assert features[name]["dimension_type"] == "basic"
        assert features[name]["surface_profile_u"] == outside
        assert features[name]["note"] == f"SURFACE PROFILE {rocker.TOP_EDGE_BAND[0]:g} U{outside:g} TO A|B|C{suffix}"
        assert set(exporter._cite(rocker, "TOP_EDGE_BAND")) <= set(features[name]["cite"]["note"])
    assert "depth_ref" not in features["profile_outer"]["requirements"]
    assert "centre_from_pivot_ref" not in features["top_edge"]["requirements"]
    shaft = exporter.requirement_manifest("ch_pivot_shaft")
    assert "length" not in shaft["features"]["pivot_bearing"]["requirements"]
    assert shaft["datums"] == {}
    assert set(shaft["features"]) == {"pivot_bearing", "north_flat", "south_flat", "north_dome", "south_dome"}
    assert shaft["features"]["pivot_bearing"]["requirements"] == ["dia", "finish_ra"]


def test_rocker_profile_zones_export_the_printed_frames_and_govern_their_own_basics() -> None:
    draw = importlib.import_module("draw_ch_rocker_arm")
    features = exporter.requirement_manifest("ch_rocker_arm")["features"]
    zone_fields = ("surface_profile", "surface_profile_u", "surface_profile_datums")
    for name, frame in (("top_edge", "TopRadius"), ("profile_outer", "BottomRadius"), ("tip_land_pos_x", "BottomRadius"), ("tip_land_neg_x", "BottomRadius")):
        fields = features[name]
        assert fields["surface_profile"] == float(draw.ARC_PROFILE_ZONE_MM) == rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]
        assert fields["surface_profile_u"] == float(draw.ARC_PROFILE_OUTSIDE_MM[frame])
        assert fields["surface_profile_datums"] == list(draw.ARC_PROFILE_DATUMS)
        # Each governed key is one of the feature's own BASIC requirements.
        assert set(fields["surface_profile_governs"]) <= set(fields["requirements"]) - {"surface_profile"}
        assert set(exporter._cite(rocker, "TOP_EDGE_BAND")) <= set(fields["cite"]["surface_profile"])
    # The J-to-K zone covers both lands: each declares profile_outer's identical frame.
    lower = {field: features["profile_outer"][field] for field in zone_fields}
    for name in ("tip_land_pos_x", "tip_land_neg_x"):
        assert {field: features[name][field] for field in zone_fields} == lower
        assert features[name]["surface_profile_governs"]["land_angle_deg"] == {"tilt_across": draw.TIP_LAND_LEAST_MM}
        assert features[name]["surface_profile_governs"]["station"] == {"sense": "increases", "obliquity_deg": math.degrees(rocker._ALPHA_TOP)}
    assert features["top_edge"]["surface_profile_governs"] == {"radius": "decreases", "height_above_pivot": "increases"}
    assert features["profile_outer"]["surface_profile_governs"] == {"bottom_radius": "increases"}


def test_shaft_flats_are_coplanar_faces_named_by_their_stations() -> None:
    features = exporter.requirement_manifest("ch_pivot_shaft")["features"]
    selectors = exporter.feature_selectors("ch_pivot_shaft")
    flat_y = shaft.FLAT_AF - shaft.SHAFT_DIA / 2
    half_chord = shaft.flat_chord(shaft.FLAT_DEPTH) / 2
    for side, station in zip(("south", "north"), bank.PIVOT_SHAFT_FLAT_STATIONS):
        name = f"{side}_flat"
        assert features[name]["kind"] == "face"
        # Printed from its own end's tip (BOTH ENDS); the face sits at the
        # layout's station from the north cylinder end.
        assert features[name]["station_nominal"] == shaft.FLAT_TIP_STATION
        assert features[name]["note"] == shaft.FLAT_STATION_CALLOUT
        assert features[name]["height_nominal"] == shaft.FLAT_AF
        assert selectors[name][0].contains_z_mm == -station
        box = (
            -half_chord / 1000, flat_y / 1000, (-station - shaft.FLAT_LENGTH / 2) / 1000,
            half_chord / 1000, flat_y / 1000, (-station + shaft.FLAT_LENGTH / 2) / 1000,
        )
        face = FaceGeometry(None, 4001, (0, 1, 0, 0, flat_y / 1000, -station / 1000), (0, 1, 0), box)
        assert _owners("ch_pivot_shaft", face) == [name]


def test_rocker_datum_domains_are_only_the_drawing_bore_broad_face_and_rod_pin_hole() -> None:
    manifest = exporter.requirement_manifest("ch_rocker_arm")
    assert manifest["datums"]["A"]["feature"] == "pivot_bore"
    assert manifest["datums"]["B"]["feature"] == "strap_datum_b"
    # Option 4: C is the rod-pin hole; the lands sit in the J↔K profile zone.
    assert manifest["datums"]["C"]["feature"] == "rod_hole"
    assert manifest["features"]["rod_hole"]["datum"] == "C"
    assert manifest["features"]["rod_hole"]["position_datums"] == ["A", "B"]
    assert manifest["features"]["profile_outer"]["note"].endswith(", BETWEEN J AND K")
    assert _owners("ch_rocker_arm", _plane((0, 0, 1), (0, 0, rocker.ARM_THICKNESS / 2))) == ["strap_datum_b"]
    assert _owners("ch_rocker_arm", _plane((0, 0, -1), (0, 0, -rocker.ARM_THICKNESS / 2))) == ["strap_faces"]
    # The authored land is radial from the top arc's endpoint. Its surface
    # normal is perpendicular to that radius, independently of selector code.
    radial_x = rocker.TOP_END_X / rocker.R_TOP
    radial_y = (rocker.TOP_END_Y - rocker_interface.CENTER_Y) / rocker.R_TOP
    tip = (rocker.ROD_TIP_X, rocker.TOP_END_Y + rocker.TIP_FACE * radial_y, 0.0)
    assert _owners("ch_rocker_arm", _plane((-radial_y, radial_x, 0), tip)) == ["tip_land_pos_x"]
    assert _owners("ch_rocker_arm", _plane((radial_y, radial_x, 0), (-tip[0], tip[1], 0))) == ["tip_land_neg_x"]
    bottom = (rocker.BOT_END_X, rocker_interface.CENTER_Y - math.sqrt(rocker_interface.R_BOTTOM**2 - rocker.BOT_END_X**2))
    dx, dy = bottom[0] - tip[0], bottom[1] - tip[1]
    length = math.hypot(dx, dy)
    assert _owners("ch_rocker_arm", _plane((-dy / length, dx / length, 0), tip)) == ["profile_outer"]
    assert "datum" not in manifest["features"]["profile_outer"]
    assert "datum" not in manifest["features"]["strap_faces"]
    assert "datum" not in manifest["features"]["tip_land_neg_x"]
    assert "datum" not in manifest["features"]["tip_land_pos_x"]


def _torus(centre_mm: tuple[float, float, float], major_mm: float, minor_mm: float) -> FaceGeometry:
    return FaceGeometry(None, 4005, (*(v / 1000 for v in centre_mm), 0, 0, 1, major_mm / 1000, minor_mm / 1000), None, ())


def test_rocker_hub_root_names_both_root_fillets_with_the_printed_max_limit() -> None:
    features = exporter.requirement_manifest("ch_rocker_arm")["features"]
    root = features["hub_root"]
    radius = rocker.HUB_ROOT_RADIUS_MAX
    # View F's "2X R0.2 MAX": sharp up to the modelled radius, at its one place.
    assert root["requirements"] == ["radius"]
    assert root["radius"] == [0.0, radius] == [radius + rocker_notes.HUB_ROOT_R_BAND[1], radius + rocker_notes.HUB_ROOT_R_BAND[0]]
    assert root["radius_nominal"] == root["corner_radius_max_design"] == radius
    assert root["precision"] == {"radius": rocker_notes.DRAWING_PRECISION["HubRoot"]["HubRootRadius"]} == {"radius": 1}
    assert root["note"] == rocker_notes.HUB_ROOT_NOTE == "2X R0.2 MAX"
    assert set(exporter._cite(rocker_notes, "HUB_ROOT_R_BAND")) <= set(root["cite"]["radius"])
    assert set(exporter._cite(rocker, "HUB_ROOT_RADIUS_MAX")) <= set(root["cite"]["corner_radius_max_design"])
    assert set(exporter._cite(rocker_notes, "DRAWING_PRECISION")) <= set(root["cite"]["precision.radius"])
    # Each fillet's tube centre stands one radius off the hub wall and the strap face.
    major = rocker.HUB_DIA / 2 + radius
    for sign in (-1, 1):
        centre = (0.0, rocker_interface.PIVOT_MID_Y, sign * (rocker.ARM_THICKNESS / 2 + radius))
        assert _owners("ch_rocker_arm", _torus(centre, major, radius)) == ["hub_root"]
        assert _owners("ch_rocker_arm", _torus((0.0, rocker_interface.PIVOT_MID_Y, sign * rocker.ARM_THICKNESS / 2), major, radius)) == []
    assert _owners("ch_rocker_arm", _torus((0.0, rocker_interface.PIVOT_MID_Y, rocker.ARM_THICKNESS / 2 + radius), major, 2 * radius)) == []


def test_cone_native_tolerances_angularity_and_exact_datums() -> None:
    manifest = exporter.requirement_manifest("dt_cone_pivot_post")
    features = manifest["features"]
    crank = features["crank_bore"]
    for feature, nominal, (bore_upper, bore_lower) in (
        (crank, cone.CRANK_BORE_DIA, cone.RUNNING_BORE_BAND),
        (features["journal_bore"], cone.BORE_DIA, cone.JOURNAL_BORE_BAND),
    ):
        assert feature["dia"] == pytest.approx(
            [nominal + bore_lower, nominal + bore_upper], rel=0.0, abs=1e-12
        )
    height_band = cone.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM
    assert features["journal_bore"]["height"] == pytest.approx(
        [cone.BORE_HEIGHT - height_band, cone.BORE_HEIGHT + height_band],
        rel=0.0,
        abs=1e-12,
    )
    assert features["journal_bore"]["at"] == pytest.approx([0.0, cone.BORE_HEIGHT, 0.0])
    assert features["journal_bore"]["precision"]["height"] == (
        cone.DRAWING_PRECISION_BY_NAME["JournalAxisY"]
    )
    assert cone.CRANK_ABOVE_CONE_BAND == (0.3556, 0.0)
    upper, lower = cone.CRANK_ABOVE_CONE_BAND
    assert crank["separation"] == pytest.approx(
        [cone.CRANK_ABOVE_CONE + lower, cone.CRANK_ABOVE_CONE + upper],
        rel=0.0,
        abs=1e-12,
    )
    assert crank["height_from"] == "journal_bore"
    assert crank["height_nominal"] == pytest.approx(cone.CRANK_BORE_HEIGHT)
    assert crank["at"] == pytest.approx([0.0, cone.CRANK_BORE_HEIGHT, 0.0])
    angularity = cone.GEOMETRIC_CONTROLS[0]
    # The FCF prints inch (#2096); the manifest carries the mm zone.
    assert crank["angularity_dia"] == cone.CRANK_BORE_ANGULARITY_MM
    assert crank["angularity_dia"] == pytest.approx(float(angularity.tolerance) * 25.4)
    assert crank["angularity_datums"] == list(angularity.datums)
    assert "angularity_dia" in crank["requirements"]
    assert "angle_tol_deg" not in crank["requirements"]
    assert "position_dia" not in crank
    assert "height" not in crank["requirements"]
    assert "unknown" in features["journal_bore"]["requirements"]
    drilled = _config.title_block("drilled_hole")
    assert features["mount_west"]["dia"] == pytest.approx(
        [
            cone.ATTACHMENT_THRU_DIA - float(drilled["minus_mm"]),
            cone.ATTACHMENT_THRU_DIA + float(drilled["plus_mm"]),
        ],
        rel=0.0,
        abs=1e-12,
    )
    assert features["mount_west"]["nominal_dia"] == cone.ATTACHMENT_THRU_DIA
    assert features["mount_west"]["precision"]["dia"] == (
        cone.DRAWING_PRECISION_BY_NAME["MountWestX"]
    )
    selectors = exporter.feature_selectors("dt_cone_pivot_post")
    for datum in cone.PART_DATUMS:
        assert selectors[manifest["datums"][datum.letter]["feature"]] == (datum.face,)
    # A same-diameter face away from the drawing journal must not become A.
    diameter = cone.BORE_DIA / 1000
    remote = FaceGeometry(
        None,
        4002,
        (0, 0, 0, 0, 0, 1, diameter / 2),
        None,
        (-diameter, 0, -0.1, diameter, 0.005, 0.1),
    )
    assert not selectors["journal_bore"][0].matches(remote)


def test_mount_stations_lie_in_their_own_signed_bands_and_mirror() -> None:
    features = exporter.requirement_manifest("dt_cone_pivot_post")["features"]
    west, east = features["mount_west"], features["mount_east"]
    for hole in (west, east):
        low, high = hole["station"]
        assert low < hole["station_nominal"] < high
        assert hole["station_nominal"] == hole["at"][0]
    assert west["station_nominal"] < 0 < east["station_nominal"]
    assert west["station"] == [-value for value in reversed(east["station"])]


def test_shaft_axial_extents_tile_the_turned_axis() -> None:
    features = exporter.requirement_manifest("ch_pivot_shaft")["features"]
    selectors = exporter.feature_selectors("ch_pivot_shaft")
    order = ("south_dome", "pivot_bearing", "north_dome")
    spans = {name: features[name]["z_mm"] for name in order}
    assert all(features[name]["frame"] == "model" and low < high for name, (low, high) in spans.items())
    for below, above in zip(order, order[1:]):
        assert spans[below][1] == pytest.approx(spans[above][0]), (below, above)
    # The O.D. runs the whole cylinder; its named patch lies inside it.
    assert spans["pivot_bearing"] == pytest.approx([-bank.PIVOT_SHAFT_LENGTH, 0.0])
    low, high = spans["pivot_bearing"]
    assert low < selectors["pivot_bearing"][0].contains_z_mm < high
    # Domes run from the end circle of the O.D. to the sphere's apex.
    for name, apex_index, base_index in (("north_dome", 1, 0), ("south_dome", 0, 1)):
        sphere = selectors[name][0]
        radius, centre = sphere.diameter_mm / 2, sphere.center_mm[2]
        apex, base = spans[name][apex_index], spans[name][base_index]
        assert abs(apex - centre) == pytest.approx(radius)
        assert features[name]["base_radius"] ** 2 + (base - centre) ** 2 == pytest.approx(radius**2)
        assert features[name]["base_radius"] * 2 == pytest.approx(features["pivot_bearing"]["dia_nominal"])


def _on_axis(point: list[float], at: list[float], axis: list[float]) -> bool:
    offset = [p - a for p, a in zip(point, at)]
    along = sum(o * v for o, v in zip(offset, axis))
    return all(abs(o - along * v) < 1e-9 for o, v in zip(offset, axis))


def _on_plane(point: list[float], face) -> bool:
    return abs(sum(p * n for p, n in zip(point, face.normal)) - face.offset_mm) < 1e-9


def test_cone_axial_extents_map_through_source_frames_onto_authored_faces() -> None:
    from prechips.rules.coordinates import model_point

    manifest = exporter.requirement_manifest("dt_cone_pivot_post")
    features, frames = manifest["features"], manifest["frames"]
    selectors = exporter.feature_selectors("dt_cone_pivot_post")
    assert frames["setup"] == "unknown"

    def ends(name: str) -> list[list[float]]:
        frame = frames[features[name]["frame"]]
        return [model_point([0.0, 0.0, z], frame) for z in features[name]["z_mm"]]

    foot, body_top = ends("body")
    head_base, head_top = ends("head")
    assert head_base == pytest.approx([0.0, cone.HEAD_BASE_Y, 0.0])
    assert head_top == pytest.approx([0.0, cone.BLOCK_HEIGHT, 0.0])
    assert foot == pytest.approx([0.0, 0.0, 0.0]) and _on_plane(foot, selectors["foot_seat"][0])
    assert body_top == pytest.approx(head_base)
    assert _on_plane(head_top, selectors["head"][1])
    crank = features["crank_bore"]
    for point, face in zip(ends("crank_boss"), selectors["crank_boss_faces"]):
        assert _on_axis(point, crank["at"], crank["axis"]) and _on_plane(point, face)
    journal = features["journal_bore"]
    north, south = ends("cone_boss")
    for point, face in ((north, selectors["cone_boss_north_face"][0]), (south, selectors["cone_boss_south_face"][0])):
        assert _on_axis(point, journal["at"], journal["axis"]) and _on_plane(point, face)


def test_turned_profile_resolves_only_spans_coaxial_with_its_setup() -> None:
    from prechips.rules.turned_profile import _axial_span

    manifest = exporter.requirement_manifest("dt_cone_pivot_post")
    features, frames = manifest["features"], manifest["frames"]
    # A spindle on the post axis facing the head top: setup +Z runs model -Y.
    spindle = {"origin": [0.0, cone.BLOCK_HEIGHT, 0.0], "x": [1.0, 0.0, 0.0], "y": [0.0, 0.0, 1.0], "z": [0.0, -1.0, 0.0]}
    assert _axial_span(features["head"], spindle, frames, 1.0) == pytest.approx((0.0, cone.HEAD_HEIGHT))
    assert _axial_span(features["body"], spindle, frames, 1.0) == pytest.approx((cone.HEAD_HEIGHT, cone.BLOCK_HEIGHT))
    assert _axial_span(features["crank_boss"], spindle, frames, 1.0) is None
    assert _axial_span(features["cone_boss"], spindle, frames, 1.0) is None


@pytest.mark.parametrize("stem", exporter.SUPPORTED_PARTS)
def test_bundle_paths_use_canonical_stems_and_existing_filenames(tmp_path: Path, stem: str) -> None:
    expected = (
        tmp_path / "features" / stem / "features.toml",
        tmp_path / "features" / stem / f"{stem.replace('_', '-')}.STEP",
    )
    assert exporter.bundle_paths(stem, out=tmp_path) == expected
    assert exporter.bundle_paths(stem.replace("_", "-"), out=tmp_path) == expected
    manifest, step = exporter.bundle_paths(stem)
    assert manifest.parent == exporter.OUT / "features" / stem
    assert manifest.name == "features.toml"
    assert step.name == exporter.requirement_manifest(stem)["step"]


def test_bundle_paths_reject_unsupported_parts(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        exporter.bundle_paths("unrelated_part", out=tmp_path)


@pytest.mark.parametrize("stem", exporter.SUPPORTED_PARTS)
def test_raw_step_face_sets_and_values_satisfy_installed_consumer_schema(tmp_path: Path, stem: str) -> None:
    step = _step(tmp_path, stem)
    content = step.read_bytes()
    path = exporter.write_manifest(stem.replace("_", "-"), step, revision="v40")
    assert path == step.with_name("features.toml")
    manifest = _load(path)
    loaded = Features.model_validate(manifest)
    if stem == "ch_rocker_arm":
        labels = _step_labels(stem)

        def expected_faces(label: str) -> list[str]:
            return [
                f"#{ordinal + 9}/ADVANCED_FACE[{ordinal}]/{label}"
                for ordinal, emitted_label in enumerate(labels, start=1)
                if emitted_label == label
            ]

        pivot_faces = expected_faces("HAF_PIVOT_BORE__P01")
        assert len(pivot_faces) == 2
        assert loaded.features["pivot_bore"].faces == pivot_faces
        for datum, label in (("B", "HAF_STRAP_DATUM_B__P01"), ("C", "HAF_ROD_HOLE__P01")):
            datum_faces = expected_faces(label)
            assert len(datum_faces) == 1
            assert loaded.features[loaded.datums[datum].feature].faces == datum_faces
    assert loaded.step == step.name
    assert loaded.step_sha256 == hashlib.sha256(content).hexdigest()
    assert loaded.drawing.revision == "v40"
    assert manifest["cite"]["step_sha256"] == [f"harmonic-analyzer/cad/out/features/{stem}/{step.name}"]
    assert {file.name for file in path.parent.iterdir()} == {step.name, "features.toml"}
    assert step.read_bytes() == content


def test_rocker_hub_root_carries_both_native_fillets_each_split_in_two(tmp_path: Path) -> None:
    # One native face per strap side (P01, P02); STEP splits each periodic
    # torus into two ADVANCED_FACEs, so the manifest lists each label twice.
    step = _step(tmp_path, "ch_rocker_arm")
    one = face_name("hub_root", 1)
    rows = step.read_bytes().decode("utf-8").split("\r\n")
    at = next(index for index, row in enumerate(rows) if f"'{one}'" in row)
    split = [one, one, face_name("hub_root", 2), face_name("hub_root", 2)]
    rows[at : at + 1] = [f"#{900 + index} = ADVANCED_FACE('{label}',(#1),#2,.T.);" for index, label in enumerate(split)]
    step.write_bytes("\r\n".join(rows).encode("utf-8"))
    faces = _load(exporter.write_manifest("ch_rocker_arm", step, revision="v40"))["features"]["hub_root"]["faces"]
    assert Counter(face.rsplit("/", 1)[1] for face in faces) == {one: 2, face_name("hub_root", 2): 2}


def test_raw_step_ansi_metadata_and_line_endings_are_never_rewritten(tmp_path: Path) -> None:
    step = _step(tmp_path, "ch_rocker_arm")
    content = step.read_bytes().replace(b"HEADER;\r\n", b"HEADER;\r\nFILE_DESCRIPTION(('M\xe9tal \x80 metadata'),'2;1');\r\n")
    step.write_bytes(content)
    path = exporter.write_manifest("ch_rocker_arm", step, revision="v40")
    assert _load(path)["step_sha256"] == hashlib.sha256(content).hexdigest()
    assert step.read_bytes() == content


def test_writer_uses_supplied_revision_and_replaces_adjacent_manifest(tmp_path: Path, monkeypatch) -> None:
    step = _step(tmp_path, "ch_rocker_arm")
    monkeypatch.setattr(exporter._config, "release_revision", lambda: "v999")
    path = exporter.write_manifest("ch_rocker_arm", step, revision="v40")
    old_digest = _load(path)["step_sha256"]
    step.write_bytes(step.read_bytes() + b"\r\n/* raw export header changed */\r\n")
    assert exporter.write_manifest("ch_rocker_arm", step, revision="v41") == path
    manifest = _load(path)
    assert manifest["drawing"]["revision"] == "v41"
    assert manifest["step_sha256"] == hashlib.sha256(step.read_bytes()).hexdigest() != old_digest
    assert "harmonic-analyzer/cad/config/release.yaml:next_revision" in manifest["drawing"]["cite"]


def test_missing_label_fails_before_installing_requirements(tmp_path: Path) -> None:
    step = _step(tmp_path, "ch_pivot_shaft")
    step.write_bytes(step.read_bytes().replace(face_name("north_dome", 1).encode(), b"NONE"))
    with pytest.raises(FeatureFaceError, match="north_dome"):
        exporter.write_manifest("ch_pivot_shaft", step, revision="v40")
    assert not step.with_name("features.toml").exists()


def test_unsupported_part_is_rejected_without_a_bundle(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        exporter.write_manifest("unrelated_part", tmp_path / "missing.STEP", revision="v40")


@pytest.mark.parametrize("stem,module", [("ch_pivot_shaft", shaft), ("dt_cone_pivot_post", cone)])
def test_construction_uses_the_actual_drawing_notes_and_explicit_permission(monkeypatch, stem, module) -> None:
    original = exporter.requirement_manifest(stem)
    assert original["construction"] == "one_piece"
    assert original["notes"]["manufacturing"] == module.DRAWING_NOTES.splitlines()
    citation = original["cite"]["construction"]
    assert set(exporter._cite(module, "DRAWING_NOTES")) <= set(citation)
    permission = "BUILT-UP CONSTRUCTION IS PERMITTED."
    monkeypatch.setattr(module, "BUILT_UP_PERMISSION_NOTE", permission, raising=False)
    with pytest.raises(ValueError, match="explicit text in DRAWING_NOTES"):
        exporter.requirement_manifest(stem)
    monkeypatch.setattr(module, "DRAWING_NOTES", module.DRAWING_NOTES + "\n" + permission)
    manifest = exporter.requirement_manifest(stem)
    assert manifest["construction"] == "built_up_permitted"
    assert manifest["notes"]["manufacturing"][-1] == permission
    assert manifest["cite"]["construction"] == citation


def test_rocker_permits_its_hub_and_strap_construction_from_its_actual_notes() -> None:
    manifest = exporter.requirement_manifest("ch_rocker_arm")
    assert manifest["construction"] == "built_up_permitted"
    assert rocker_notes.BUILT_UP_PERMISSION_NOTE in manifest["notes"]["manufacturing"]
    assert set(exporter._cite(rocker_notes, "DRAWING_NOTES")) <= set(manifest["cite"]["construction"])


@pytest.mark.parametrize("stem", exporter.SUPPORTED_PARTS)
def test_all_emitted_citations_resolve_current_python_ast_and_yaml_scalar_sources(stem: str) -> None:
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)

    citations = {
        citation for citation in strings(exporter.requirement_manifest(stem))
        if citation.startswith("harmonic-analyzer/")
    }
    assert citations, f"{stem}: no citations emitted"
    dashed = stem.replace("_", "-")
    assert f"harmonic-analyzer/cad/config/parts/{dashed}.yaml:{dashed}.number" in citations
    assert any(".py:" in citation for citation in citations), f"{stem}: no Python sources cited"
    source_text = {}
    python_spans = {}
    yaml_documents = {}
    for reference in citations:
        filename, separator, location = reference.removeprefix("harmonic-analyzer/").partition(":")
        assert separator and location, reference
        path = exporter.REPO / filename
        assert path.is_file(), f"{reference}: missing source file"
        if path not in source_text:
            source_text[path] = path.read_text(encoding="utf-8")
        if path.suffix == ".yaml":
            if path not in yaml_documents:
                yaml_documents[path] = yaml.safe_load(source_text[path])
            value = yaml_documents[path]
            for key in location.split("."):
                assert isinstance(value, dict) and key in value, f"{reference}: missing key {key!r}"
                value = value[key]
            assert value is not None and not isinstance(value, (dict, list)), f"{reference}: not a scalar value"
        elif path.suffix == ".py":
            low, dash, high = location.partition("-")
            assert low.isdecimal() and dash and high.isdecimal(), f"{reference}: invalid AST span"
            span = int(low), int(high)
            assert 1 <= span[0] <= span[1] <= len(source_text[path].splitlines()), reference
            if path not in python_spans:
                python_spans[path] = {
                    (node.lineno, node.end_lineno)
                    for node in ast.walk(ast.parse(source_text[path]))
                    if hasattr(node, "lineno") and hasattr(node, "end_lineno")
                }
            assert span in python_spans[path], f"{reference}: not a current AST declaration/call span"
        else:
            pytest.fail(f"{reference}: unsupported citation source")


class _GearProfileAdapter:
    """Record authored equations and paths without COM or a geometric substitute."""

    def __init__(self) -> None:
        self.curves = []
        self.planes = []
        self.active_plane = None
        self.constraints = []
        self.path_length = None
        self.path_name = None
        self.sweep = None

    @staticmethod
    def _result(data=None):
        return SimpleNamespace(is_success=True, data=data, error=None)

    async def create_sketch(self, plane):
        assert self.active_plane is None
        assert plane in ("Front", "Top")
        self.planes.append(plane)
        self.active_plane = plane
        return self._result()

    async def create_equation_driven_curve(self, params):
        assert self.active_plane == "Front"
        assert (params.range_start, params.range_end) == ("0", "1")
        assert not params.z_expression
        self.curves.append(params)
        return self._result(f"Curve{len(self.curves)}")

    async def check_sketch_fully_defined(self):
        assert self.active_plane is not None
        return self._result({"definition_state": "fully_defined"})

    async def exit_sketch(self):
        assert self.active_plane is not None
        self.active_plane = None
        return self._result()

    async def add_line(self, x1, y1, x2, y2):
        assert self.active_plane == "Top"
        assert (x1, y1, x2) == (0.0, 0.0, 0.0)
        assert y2 < 0.0
        self.path_length = -y2
        return self._result("Line1")

    async def add_sketch_constraint(self, entity, other, kind):
        assert self.active_plane == "Top"
        assert (entity, other, kind) in (
            ("Line1", None, "vertical"),
            ("Line1.start", "origin", "coincident"),
        )
        self.constraints.append((entity, other, kind))
        return self._result()

    async def add_sketch_dimension(self, first, second, kind, value):
        assert (first, second, kind) == (
            "Line1.start",
            "Line1.end",
            "vertical_distance",
        )
        assert value == self.path_length
        return self._result("D1@ToothPath")

    def name_last_feature(self, name):
        assert self.active_plane is None
        assert self.planes == ["Front", "Top"]
        assert name == "ToothPath"
        self.path_name = name
        return name

    async def create_sweep(self, params):
        assert self.active_plane is None
        assert len(self.curves) == 6
        assert len(self.constraints) == 2
        assert params.path == self.path_name == "ToothPath"
        assert params.twist_along_path and params.merge_result
        self.sweep = params
        return self._result(SimpleNamespace(name="ToothSweep"))

    async def create_cut_extrude(self, params):
        assert self.active_plane is None
        assert self.planes == ["Front"]
        assert params.depth > 0.0
        return self._result(SimpleNamespace(name="ToothGap"))


@pytest.fixture
def gear_profile_adapter(monkeypatch):
    import _gear

    adapter = _GearProfileAdapter()
    monkeypatch.setattr(
        _gear,
        "name_last_feature",
        lambda seat, name: seat.name_last_feature(name),
    )
    return adapter


def _curve_point(curve, t):
    # Evaluate the actual numeric radian expressions handed to the adapter,
    # rather than inspecting source strings or rebuilding a second profile.
    scope = {"__builtins__": {}, "cos": math.cos, "sin": math.sin, "t": t}
    return (
        eval(curve.x_expression, scope),
        eval(curve.y_expression, scope),
    )


def _profile_points(curves, walk, *, samples=64, radial_clip=None):
    points = []
    for index, reverse in walk:
        segment = [
            _curve_point(curves[index], (samples - i if reverse else i) / samples)
            for i in range(samples + 1)
        ]
        if points:
            assert segment[0] == pytest.approx(points[-1], rel=0.0, abs=3e-11)
        points.extend(segment if not points else segment[1:])
    assert points[-1] == pytest.approx(points[0], rel=0.0, abs=3e-11)
    points[-1] = points[0]
    if radial_clip is not None:
        lo, hi = radial_clip
        points = [
            (
                x * min(hi, max(lo, math.hypot(x, y))) / math.hypot(x, y),
                y * min(hi, max(lo, math.hypot(x, y))) / math.hypot(x, y),
            )
            for x, y in points
        ]
    return points


def _polygon_area(points):
    return (
        abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:])))
        / 2.0
    )


def _assert_simple_profile(points):
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    edges = list(zip(points, points[1:]))
    for i, (a, b) in enumerate(edges):
        assert math.dist(a, b) > 1e-12
        for j in range(i + 2, len(edges)):
            if i == 0 and j == len(edges) - 1:
                continue
            c, d = edges[j]
            if (
                max(a[0], b[0]) < min(c[0], d[0])
                or max(c[0], d[0]) < min(a[0], b[0])
                or max(a[1], b[1]) < min(c[1], d[1])
                or max(c[1], d[1]) < min(a[1], b[1])
            ):
                continue
            assert not (
                cross(a, b, c) * cross(a, b, d) <= 0.0
                and cross(c, d, a) * cross(c, d, b) <= 0.0
            ), f"non-adjacent profile edges {i}, {j} intersect"


_TOOTH_WALK = ((0, False), (1, False), (2, True), (3, False), (4, False), (5, False))


def _above_base_helical_regression_profile():
    """Independent sample for the retained ideal-involute helper algorithms.

    This is not the physical 64T stock-form crank gear: that uses the finite
    cutter's translated root envelope, printed tangent span and corner set,
    qualified in the native crank/core tests. Keep these endpoint/area controls
    independent of its specification so they cannot claim native qualification.
    """
    from involute_gear import gear_facts

    teeth, normal_dp, normal_pa = 64, 24.0, 20.0
    helix = math.radians(13.0)
    face = 7.0
    dp = normal_dp * math.cos(helix)
    pa = math.degrees(math.atan(math.tan(math.radians(normal_pa)) / math.cos(helix)))
    extra = 1.0 / normal_dp - 1.0 / dp
    facts = gear_facts(teeth, dp, pa, addendum_extra_in=extra)
    pitch_r = teeth / (2.0 * dp)
    root = pitch_r - 1.25 / normal_dp
    eps = 0.001  # algorithmic flank rotation, not an assembled backlash claim
    twist = face * math.tan(helix) / (pitch_r * 25.4)
    return facts, root, eps, twist, face, extra, dp, pa


def test_above_base_helical_regression_starts_at_root_and_never_crosses(
    gear_profile_adapter,
):
    import _gear
    from involute_gear import involute_point

    facts, root, eps, twist, face, extra, dp, pa = _above_base_helical_regression_profile()
    assert root > facts["Rb"]
    assert root - _gear._TOOTH_EMBED_MM / 25.4 > facts["Rb"]
    rho = -twist / 2.0
    name = asyncio.run(
        _gear.boss_tooth_swept(
            gear_profile_adapter,
            facts,
            face,
            twist_deg=math.degrees(twist),
            rotate_rad=rho,
            widen_rad=eps,
            root_r_in=root,
        )
    )
    assert name == "ToothSweep"
    assert gear_profile_adapter.sweep.twist_angle == pytest.approx(math.degrees(twist))
    curves = gear_profile_adapter.curves
    points = _profile_points(curves, _TOOTH_WALK)
    _assert_simple_profile(points)

    u0 = math.sqrt((root / facts["Rb"]) ** 2 - 1.0)
    assert _gear._root_start_parameter(facts["Rb"], root) == pytest.approx(u0)
    inv0 = u0 - math.atan(u0)
    foot_angles = (
        facts["Gamma"] - facts["Delta"] + eps + rho + inv0,
        facts["Gamma"] + facts["Delta"] - eps + rho - inv0,
    )
    # Reparameterising the same involute must not alter geometry outside
    # the root, including the diagnostic mesh domain.
    for i in range(17):
        t = i / 16.0
        u = u0 + (facts["Tmax"] - u0) * t
        for index, upper, rotation in (
            (0, True, eps + rho),
            (2, False, facts["Gamma"] - eps + rho),
        ):
            x, y = involute_point(facts, u, upper=upper)
            reference = (
                x * math.cos(rotation) - y * math.sin(rotation),
                x * math.sin(rotation) + y * math.cos(rotation),
            )
            assert _curve_point(curves[index], t) == pytest.approx(
                reference, rel=0.0, abs=3e-11
            )
    for index, angle in zip((0, 2), foot_angles):
        assert _curve_point(curves[index], 0.0) == pytest.approx(
            (root * math.cos(angle), root * math.sin(angle)), rel=0.0, abs=3e-11
        )
        radii = [math.hypot(*_curve_point(curves[index], i / 64.0)) for i in range(65)]
        assert all(a < b for a, b in zip(radii, radii[1:]))
        assert radii[-1] == pytest.approx(facts["Ra"], rel=0.0, abs=3e-11)
    embed = root - _gear._TOOTH_EMBED_MM / 25.4
    for index, reverse in ((3, False), (5, True)):
        radii = [
            math.hypot(*_curve_point(curves[index], (64 - i if reverse else i) / 64.0))
            for i in range(65)
        ]
        assert radii[0] == pytest.approx(root, rel=0.0, abs=3e-11)
        assert radii[-1] == pytest.approx(embed, rel=0.0, abs=3e-11)
        assert all(a > b for a, b in zip(radii, radii[1:]))

    # The embedded sliver adds no material to the root-cylinder union.
    physical = _profile_points(
        curves, _TOOTH_WALK, samples=2000, radial_clip=(root, facts["Ra"])
    )
    gap = _gear.gap_area_in_disc_ext(64, dp, pa, eps, root, addendum_extra_in=extra)
    tooth = math.pi * (facts["Ra"] ** 2 - root**2) / 64.0 - gap
    assert _polygon_area(physical) == pytest.approx(tooth, rel=0.0, abs=2e-9)


def test_above_base_helical_regression_gap_matches_root_and_volume_oracle(
    gear_profile_adapter,
):
    import _gear

    facts, root, eps, twist, face, extra, dp, pa = _above_base_helical_regression_profile()
    asyncio.run(
        _gear.cut_tooth_gap(
            gear_profile_adapter,
            facts,
            face + 1.0,
            rotate_rad=-twist / 2.0,
            widen_rad=eps,
            root_r_in=root,
        )
    )
    curves = gear_profile_adapter.curves
    assert len(curves) == 6  # no zero-length or outward base-to-root extensions
    walk = ((0, False), (2, False), (3, False), (4, False), (1, True), (5, False))
    _assert_simple_profile(_profile_points(curves, walk))
    for index in (0, 1):
        assert math.hypot(*_curve_point(curves[index], 0.0)) == pytest.approx(
            root, rel=0.0, abs=3e-11
        )
    clipped = _profile_points(
        curves, walk, samples=2000, radial_clip=(root, facts["Ra"])
    )
    expected = _gear.gap_area_in_disc_ext(
        64, dp, pa, eps, root, addendum_extra_in=extra
    )
    assert _polygon_area(clipped) == pytest.approx(expected, rel=0.0, abs=2e-10)
    u0 = math.sqrt((root / facts["Rb"]) ** 2 - 1.0)
    inv0 = u0 - math.atan(u0)
    root_span = facts["Gamma"] - 2.0 * facts["Delta"] + 2.0 * eps + 2.0 * inv0
    tip_span = facts["ThetaU"] - facts["ThetaL"] + 2.0 * eps
    exact = (
        facts["Ra"] ** 2 * tip_span
        - root**2 * root_span
        - 2.0 * facts["Rb"] ** 2 * (facts["Tmax"] ** 3 - u0**3) / 3.0
    ) / 2.0
    assert expected == pytest.approx(exact, rel=0.0, abs=2e-9)


# Independent algorithm regression samples, not production gear selections.
# These retain the below-base sweep branch alongside the above-base control.
@pytest.mark.parametrize(
    "teeth,dp,pa", ((16, 24.0, 20.0), (64, 24.74, 14.5), (12, 12.7, 14.5))
)
def test_below_base_sweep_keeps_original_profile(gear_profile_adapter, teeth, dp, pa):
    import _gear
    from involute_gear import gear_facts

    facts = gear_facts(teeth, dp, pa)
    root = teeth / (2.0 * dp) - 1.157 / dp
    assert 0.0 < root < facts["Rb"]
    assert _gear._root_start_parameter(facts["Rb"], root) == 0.0
    eps, rho = 0.001, -0.012
    asyncio.run(
        _gear.boss_tooth_swept(
            gear_profile_adapter,
            facts,
            7.2244,
            twist_deg=2.0,
            rotate_rad=rho,
            widen_rad=eps,
            root_r_in=root,
        )
    )
    rb, ra = facts["Rb"], facts["Ra"]
    embed = root - _gear._TOOTH_EMBED_MM / 25.4
    a_lo = facts["Gamma"] - facts["Delta"] + eps + rho
    a_hi = facts["Gamma"] + facts["Delta"] - eps + rho
    for i in range(17):
        t = i / 16.0
        u = facts["Tmax"] * t
        ph_a, ph_b = u + a_lo, u - a_hi
        tip = (
            facts["ThetaU"]
            + eps
            + rho
            + t * (facts["Gamma"] + facts["ThetaL"] - facts["ThetaU"] - 2.0 * eps)
        )
        arc = a_hi + t * (a_lo - a_hi)
        reference = (
            (
                rb * (math.cos(ph_a) + u * math.sin(ph_a)),
                rb * (math.sin(ph_a) - u * math.cos(ph_a)),
            ),
            (ra * math.cos(tip), ra * math.sin(tip)),
            (
                rb * (math.cos(ph_b) + u * math.sin(ph_b)),
                rb * (u * math.cos(ph_b) - math.sin(ph_b)),
            ),
            (
                (rb + t * (embed - rb)) * math.cos(a_hi),
                (rb + t * (embed - rb)) * math.sin(a_hi),
            ),
            (embed * math.cos(arc), embed * math.sin(arc)),
            (
                (embed + t * (rb - embed)) * math.cos(a_lo),
                (embed + t * (rb - embed)) * math.sin(a_lo),
            ),
        )
        for curve, point in zip(gear_profile_adapter.curves, reference, strict=True):
            assert _curve_point(curve, t) == pytest.approx(point, rel=0.0, abs=3e-11)


@pytest.mark.parametrize("root_kind", ("chord", "below", "base"))
def test_below_base_gap_keeps_floor_and_involute_endpoints(
    gear_profile_adapter, root_kind
):
    import _gear
    from involute_gear import gap_area_in_disc, gear_facts, involute_point

    facts = gear_facts(16, 24.0, 20.0)
    root = {"chord": None, "below": 7.14375 / 25.4, "base": facts["Rb"]}[root_kind]
    assert _gear._root_start_parameter(facts["Rb"], root) == 0.0
    asyncio.run(_gear.cut_tooth_gap(gear_profile_adapter, facts, 8.0, root_r_in=root))
    curves = gear_profile_adapter.curves
    assert len(curves) == (8 if root_kind == "below" else 6)
    for i in range(17):
        t = i / 16.0
        for index, upper in ((0, False), (1, True)):
            assert _curve_point(curves[index], t) == pytest.approx(
                involute_point(facts, facts["Tmax"] * t, upper=upper),
                rel=0.0,
                abs=3e-11,
            )
    floor_walk = (
        ((5, False), (6, False), (7, False)) if root_kind == "below" else ((5, False),)
    )
    walk = ((0, False), (2, False), (3, False), (4, False), (1, True), *floor_walk)
    _assert_simple_profile(_profile_points(curves, walk))
    area = _gear.gap_area_in_disc_ext(16, 24.0, 20.0, root_r_in=root)
    if root_kind == "chord":
        assert area == pytest.approx(
            gap_area_in_disc(16, dp=24.0, pa_deg=20.0), abs=1e-12
        )
    clipped = _profile_points(
        curves, walk, samples=2000, radial_clip=(0.0, facts["Ra"])
    )
    assert _polygon_area(clipped) == pytest.approx(area, rel=0.0, abs=2e-10)


@pytest.mark.parametrize(
    "root_kind", ("negative", "zero", "tip", "above_tip", "embed_zero")
)
def test_invalid_root_is_refused_before_sweep_profile(gear_profile_adapter, root_kind):
    import _gear

    facts, _, eps, twist, face, extra, dp, pa = _above_base_helical_regression_profile()
    root = {
        "negative": -1.0,
        "zero": 0.0,
        "tip": facts["Ra"],
        "above_tip": facts["Ra"] + 0.01,
        "embed_zero": _gear._TOOTH_EMBED_MM / 25.4,
    }[root_kind]
    with pytest.raises(ValueError, match="root"):
        asyncio.run(
            _gear.boss_tooth_swept(
                gear_profile_adapter,
                facts,
                face,
                twist_deg=math.degrees(twist),
                rotate_rad=0.0,
                widen_rad=eps,
                root_r_in=root,
            )
        )
    assert not gear_profile_adapter.curves
    assert not gear_profile_adapter.planes
    if root_kind != "embed_zero":
        with pytest.raises(ValueError, match="root"):
            asyncio.run(
                _gear.cut_tooth_gap(
                    gear_profile_adapter,
                    facts,
                    face,
                    root_r_in=root,
                )
            )
        with pytest.raises(ValueError, match="root"):
            _gear.gap_area_in_disc_ext(
                64,
                dp,
                pa,
                eps,
                root,
                addendum_extra_in=extra,
            )


@pytest.mark.parametrize(
    "root,expected",
    ((None, 0.0), (0.2, 0.0), (0.25, 0.0), (0.3125, 0.75)),
    ids=("chord", "below_base", "on_base", "above_base"),
)
def test_canonical_root_start_selects_physical_involute_domain(root, expected):
    import _gear

    assert _gear._root_start_parameter(0.25, root) == pytest.approx(expected)


@pytest.mark.parametrize(
    "root", (-1.0, 0.0, math.inf, math.nan), ids=("negative", "zero", "infinite", "nan")
)
def test_canonical_root_start_rejects_nonphysical_radii(root):
    import _gear

    with pytest.raises(ValueError, match="positive and finite"):
        _gear._root_start_parameter(0.25, root)
