"""Every part drawing's source part stamps the properties its title block needs.

A drawing reads its title block from the source part's custom properties and
fails at build time when a required one is missing (``read_required_properties``).
The warm build of integ 9a0f50b1c lost ``drawing:dt_cylinder_end_disc`` that way:
the #743 rebuild of MHA-DT-026 never called ``apply_drawing_properties``, so
Material Specification / Finish / Quantity were never stamped.  This contract
catches the same gap offline, across every registered part drawing.

"Stamped" is static and deliberately generous: the keys ``part_properties``
returns for the part, every string literal in the part's build script and in
the repo-local modules it imports (``_drawing_marks`` aside, whose literals only
count through a call to ``apply_drawing_properties``), plus that helper's keys
when the build calls it.  A property no path can name is certainly missing.
SolidWorks-free.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config
import _purchased_fastener_drawing as purchased
from _common import part_properties
from _drawing_registry import DRAWINGS

SCRIPTS = Path(__file__).resolve().parent

# The keys _drawing_marks.apply_drawing_properties stamps, and the registry
# fields it reads them from.
_DRAWING_MARK_FIELDS = {
    "Material Specification": "material_specification",
    "Finish": "finish",
    "Quantity": "quantity",
}
_DRAWING_MARK_KEYS = {*_DRAWING_MARK_FIELDS, "Drawn By", "Revision Description"}
_SPRING_EXTRA = {"Material Specification", "Finish", "Manufacturing Notes"}

PART_DRAWINGS = sorted(
    (drawing for drawing in DRAWINGS if drawing.source_kind == "part"),
    key=lambda drawing: drawing.name,
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _call_names(tree: ast.AST) -> set[str]:
    return {
        getattr(node.func, "id", getattr(node.func, "attr", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }


def _imported_string(tree: ast.Module, name: str) -> str:
    """A module-level string constant ``name`` imported from a repo-local module."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not any(alias.name == name and alias.asname is None for alias in node.names):
            continue
        for statement in _tree(SCRIPTS / f"{node.module.replace('.', '/')}.py").body:
            if (
                isinstance(statement, ast.Assign)
                and [getattr(target, "id", None) for target in statement.targets] == [name]
            ):
                value = ast.literal_eval(statement.value)
                if isinstance(value, str):
                    return value
    raise AssertionError(f"required property {name} is not an imported string constant")


def _required(draw: Path) -> set[str]:
    """The properties the drawing refuses to build without."""
    tree = _tree(draw)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    if "build_purchased_fastener_drawing" in imported:
        return set(purchased._PROPERTIES)
    if "build_purchased_spring_drawing" in imported:
        return set(purchased._PROPERTIES) | _SPRING_EXTRA
    # The non-fastener purchased builder reads the spring builder's set.
    if "build_purchased_part_drawing" in imported:
        return set(purchased._PROPERTIES) | _SPRING_EXTRA
    assigned = {
        target.id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", getattr(node.func, "attr", "")) != "read_required_properties":
            continue
        for keyword in node.keywords:
            if keyword.arg != "required":
                continue
            value = keyword.value
            if isinstance(value, ast.Name):
                value = assigned[value.id]
            # A drawing may name a property by its spec's constant.
            return {
                _imported_string(tree, element.id)
                if isinstance(element, ast.Name)
                else ast.literal_eval(element)
                for element in value.elts
            }
    raise AssertionError(f"{draw.name}: no required property set found")


def _build_trees(build: Path) -> list[ast.Module]:
    trees = [_tree(build)]
    for node in ast.walk(trees[0]):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.module == "_drawing_marks":
            continue
        module = SCRIPTS / f"{node.module.replace('.', '/')}.py"
        if module.is_file():
            trees.append(_tree(module))
    return trees


def _stamped(stem: str, build: Path) -> tuple[set[str], bool]:
    stamped = set(part_properties(stem))
    marks = False
    for tree in _build_trees(build):
        stamped |= {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        marks = marks or "apply_drawing_properties" in _call_names(tree)
    if marks:
        stamped |= _DRAWING_MARK_KEYS
    return stamped, marks


def test_every_part_drawing_is_under_test() -> None:
    assert len(PART_DRAWINGS) >= 90


@pytest.mark.parametrize("drawing", PART_DRAWINGS, ids=lambda drawing: drawing.name)
def test_source_part_stamps_every_required_property(drawing) -> None:
    stem = drawing.part.replace("_", "-")
    build = SCRIPTS / f"build_{drawing.part}.py"
    assert build.is_file(), f"{drawing.name}: no build script {build.name}"
    required = _required(SCRIPTS / drawing.script_name)
    stamped, marks = _stamped(stem, build)
    assert not required - stamped, (
        f"{drawing.name}: {build.name} never stamps {sorted(required - stamped)}"
    )
    if not marks:
        return
    row = _config.parts(stem)
    blank = [field for field in _DRAWING_MARK_FIELDS.values() if row.get(field) in (None, "")]
    assert not blank, f"{stem}: apply_drawing_properties reads blank registry fields {blank}"
