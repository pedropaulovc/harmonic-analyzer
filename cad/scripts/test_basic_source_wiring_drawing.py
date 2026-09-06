"""Three source manifests govern imported BASIC dimensions without fleet coupling."""

import ast
import importlib
from pathlib import Path

import pytest

from _buildgraph import module_deps_of, part_scripts


SCRIPTS = Path(__file__).resolve().parent
MANIFESTS = {
    "channel_lever": {
        "LeverOutline": {"BarLength", "TipCentreX", "NoseRadius", "TipRadius"}
    },
    "arbor_pedestal": {
        "FootProfile": {"Width", "Depth"},
        "Foot": {"FootHt"},
        "DomeProfile": {"DomeDia"},
    },
    "pen_v_block": {"BoreProfile": {"Bore0X", "Bore1X"}},
}


def calls(path, name):
    return [
        node
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


@pytest.mark.parametrize("stem", MANIFESTS)
def test_source_manifest_is_shared_exact_marked_subset(stem):
    specification = importlib.import_module(f"{stem}_spec")
    builder = importlib.import_module(f"build_{stem}")
    assert specification.SOURCE_BASIC_DIMENSIONS == MANIFESTS[stem]
    assert builder.SOURCE_BASIC_DIMENSIONS is specification.SOURCE_BASIC_DIMENSIONS
    assert SCRIPTS / f"{stem}_spec.py" in {
        Path(path) for path in module_deps_of(SCRIPTS / f"draw_{stem}.py")
    }
    for feature, names in specification.SOURCE_BASIC_DIMENSIONS.items():
        assert names <= specification.DRAWING_DIMENSIONS[feature]


@pytest.mark.parametrize("stem", MANIFESTS)
def test_every_builder_authors_source_metadata_once_before_native_save(stem):
    path = SCRIPTS / f"build_{stem}.py"
    (author,) = calls(path, "author_basic_dimensions")
    assert [arg.id for arg in author.args] == ["adapter", "SOURCE_BASIC_DIMENSIONS"]
    assert author.lineno < min(
        call.lineno for call in calls(path, "save_part_and_images")
    )
    assert not calls(path, "require_basic_dimension")


@pytest.mark.parametrize("stem", MANIFESTS)
def test_imported_drawing_checks_are_read_only_and_native_reference_writes_stay(stem):
    path = SCRIPTS / f"draw_{stem}.py"
    assert calls(path, "require_basic_dimension")
    assert not calls(path, "author_basic_dimensions")
    setters = calls(path, "set_basic_dimension")
    assert [call.args[1].id for call in setters] == {
        "channel_lever": ["bar_pin_c2c", "spring_c2c", "bar_height"],
        "arbor_pedestal": [
            "display"
        ],  # inside _add_circle_basic, not imported model dimensions
        "pen_v_block": [],
    }[stem]


def test_basic_helper_does_not_enter_any_unaffected_part_closure():
    consumers = {
        path.stem.removeprefix("build_")
        for path in part_scripts()
        if any(
            Path(dependency).name == "_basic_dimensions.py"
            for dependency in module_deps_of(path)
        )
    }
    assert consumers == set(MANIFESTS)


@pytest.mark.parametrize("stem", MANIFESTS)
def test_basic_wiring_keeps_drawing_runtime_out_of_source_part_closure(stem):
    part = SCRIPTS / f"build_{stem}.py"
    names = {Path(path).name for path in module_deps_of(part)}
    assert "_basic_dimensions.py" in names
    assert not names & {
        "_drawing_common.py",
        "_drawing_project_layout.py",
        "_drawing_native_layout.py",
        "_drawing_native_gtol.py",
        "_drawing_annotation_bounds.py",
    }
