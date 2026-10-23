"""Static ownership contracts for legacy mappings, profile bands and typed PMI.

Typed projections must retain the imported part's immutable GeometricControl
rows through an unshadowed, bounded loop. Parse recipes/specs only: importing
either would turn a source-provenance check into a native/build dependency.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).parent
FCF_HELPER = "add_feature_control_frame"
TOLERANCE_MAPPING = "GEOMETRIC_TOLERANCES_MM"


def _fcf_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == FCF_HELPER
    ]


def _keyword(call: ast.Call, name: str) -> ast.AST:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    raise AssertionError(f"{FCF_HELPER} call on line {call.lineno} lacks {name}=")


def _part_mapping(spec_path: Path) -> dict[str, str] | None:
    tree = ast.parse(spec_path.read_text(encoding="utf-8"), filename=str(spec_path))
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if node.target.id != TOLERANCE_MAPPING:
            continue
        assert isinstance(node.value, ast.Dict)
        raw_keys = [ast.literal_eval(key) for key in node.value.keys]
        assert all(isinstance(key, str) for key in raw_keys)
        assert len(raw_keys) == len(set(raw_keys)), (
            f"{spec_path}: duplicate {TOLERANCE_MAPPING} keys"
        )
        mapping = ast.literal_eval(node.value)
        assert isinstance(mapping, dict)
        return mapping
    return None


def _loop_string_bindings(tree: ast.AST) -> dict[str, tuple[str, ...]]:
    """Resolve tuple-loop variables whose every row binds a static string."""
    bindings: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.For) or not isinstance(node.target, ast.Tuple):
            continue
        if not isinstance(node.iter, (ast.Tuple, ast.List)):
            continue
        rows = node.iter.elts
        if not rows or not all(isinstance(row, (ast.Tuple, ast.List)) for row in rows):
            continue
        for index, target in enumerate(node.target.elts):
            if not isinstance(target, ast.Name):
                continue
            values: list[str] = []
            for row in rows:
                assert isinstance(row, (ast.Tuple, ast.List))
                if index >= len(row.elts):
                    values = []
                    break
                value = row.elts[index]
                if not isinstance(value, ast.Constant) or not isinstance(
                    value.value, str
                ):
                    values = []
                    break
                values.append(value.value)
            if values:
                bindings[target.id] = tuple(values)
    return bindings


def _mapping_reference_keys(
    node: ast.Subscript, loop_bindings: dict[str, tuple[str, ...]]
) -> tuple[str, ...]:
    assert isinstance(node.value, ast.Name)
    assert node.value.id == TOLERANCE_MAPPING
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return (node.slice.value,)
    if isinstance(node.slice, ast.Name) and node.slice.id in loop_bindings:
        return loop_bindings[node.slice.id]
    raise AssertionError(
        f"line {node.lineno}: cannot prove {TOLERANCE_MAPPING} key set"
    )


def _require_part_band_profile(
    tree: ast.Module, call: ast.Call, spec_tree: ast.Module, spec_module: str,
) -> None:
    """Allow a profile zone projected from a part's positive one-sided band."""
    characteristic = _keyword(call, "characteristic")
    assert isinstance(characteristic, ast.Constant)
    assert characteristic.value == "profile_surface"
    tolerance = _keyword(call, "tolerance")
    seen: set[str] = set()
    while isinstance(tolerance, ast.Name):
        name = tolerance.id
        assert name not in seen, "cyclic profile tolerance assignment"
        seen.add(name)
        definitions = [
            node.value for node in tree.body
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name
            ) or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == name
            )
        ]
        assert len(definitions) == 1, "profile tolerance needs one module assignment"
        stores = [
            node for node in ast.walk(tree)
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == name)
            or (isinstance(node, ast.arg) and node.arg == name)
        ]
        assert len(stores) == 1, "profile tolerance assignment is shadowed"
        tolerance = definitions[0]
    assert isinstance(tolerance, ast.JoinedStr) and len(tolerance.values) == 1
    formatted = tolerance.values[0]
    assert isinstance(formatted, ast.FormattedValue) and formatted.conversion == -1
    assert isinstance(formatted.format_spec, ast.JoinedStr)
    assert len(formatted.format_spec.values) == 1
    format_value = formatted.format_spec.values[0]
    assert isinstance(format_value, ast.Constant) and format_value.value == "g"
    band = formatted.value
    assert isinstance(band, ast.Subscript) and isinstance(band.value, ast.Name)
    assert isinstance(band.slice, ast.Constant) and type(band.slice.value) is int
    assert band.slice.value == 0, "profile total zone must use the upper endpoint"
    local_name = band.value.id
    imports = [
        (node, alias) for node in tree.body if isinstance(node, ast.ImportFrom)
        for alias in node.names if (alias.asname or alias.name) == local_name
    ]
    assert len(imports) == 1, "profile band needs one direct part-spec import"
    imported, alias = imports[0]
    assert imported.level == 0 and imported.module == spec_module
    assert alias.name.endswith("_BAND")
    assert not any(
        (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == local_name)
        or (isinstance(node, ast.arg) and node.arg == local_name)
        for node in ast.walk(tree)
    ), "part band import is shadowed"
    definitions = [
        node.value for node in spec_tree.body
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == alias.name
        ) or (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == alias.name
        )
    ]
    assert len(definitions) == 1
    value = definitions[0]
    assert isinstance(value, ast.Tuple) and len(value.elts) == 2
    assert all(isinstance(endpoint, ast.Constant) for endpoint in value.elts)
    upper, lower = (endpoint.value for endpoint in value.elts)
    assert type(upper) in (int, float) and type(lower) in (int, float)
    assert upper > 0 and lower == 0



def _scope_nodes(scope: ast.AST) -> Iterator[ast.AST]:
    """Walk one lexical scope, not a nested function's independent locals."""
    yield scope
    for child in ast.iter_child_nodes(scope):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield child
        else:
            yield from _scope_nodes(child)


def _bindings(nodes: Iterable[ast.AST], name: str) -> list[ast.AST]:
    bindings = []
    for node in nodes:
        if (
            isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
            and node.id == name
        ) or (isinstance(node, ast.arg) and node.arg == name):
            bindings.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bindings.extend(
                alias for alias in node.names
                if (alias.asname or alias.name.split(".")[0]) == name
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                bindings.append(node)
        elif isinstance(node, ast.ExceptHandler) and node.name == name:
            bindings.append(node)
        elif isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            bindings.append(node)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name == name:
            bindings.append(node)
        elif isinstance(node, ast.MatchMapping) and node.rest == name:
            bindings.append(node)
    return bindings


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _require_no_member_writes(nodes: Iterable[ast.AST], name: str) -> None:
    for node in nodes:
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(
            node.ctx, (ast.Store, ast.Del)
        ):
            assert _root_name(node) != name, f"{name}: drawing mutates part-owned controls"
        if isinstance(node, ast.Call):
            assert not (
                isinstance(node.func, ast.Attribute) and _root_name(node.func) == name
            ), f"{name}: unproven method call on part-owned controls"
            assert not (
                isinstance(node.func, ast.Name) and node.func.id in {"setattr", "delattr"}
                and node.args and _root_name(node.args[0]) == name
            ), f"{name}: drawing mutates part-owned controls"


def _single_assignment(scope: ast.AST, name: str) -> tuple[ast.stmt, ast.AST]:
    definitions = []
    for node in scope.body:
        if (
            isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name
        ):
            definitions.append((node, node.targets[0], node.value))
        elif (
            isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            and node.target.id == name and node.value is not None
        ):
            definitions.append((node, node.target, node.value))
    assert len(definitions) == 1, f"{name}: needs one direct assignment"
    statement, target, value = definitions[0]
    nodes = list(_scope_nodes(scope))
    assert _bindings(nodes, name) == [target], f"{name}: assignment is shadowed/rebound"
    assert not any(
        isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names
        for node in ast.walk(scope)
    ), f"{name}: nested scope can rebind the ownership chain"
    _require_no_member_writes(ast.walk(scope), name)
    return statement, value


def _require_import(
    tree: ast.Module, name: str, module: str, member: str | None = None,
) -> None:
    imports = [
        alias for node in tree.body
        if (
            member is None and isinstance(node, ast.Import)
        ) or (
            member is not None and isinstance(node, ast.ImportFrom)
            and node.level == 0 and node.module == module
        )
        for alias in node.names
        if (alias.asname or alias.name) == name and alias.name == (member or module)
    ]
    assert len(imports) == 1, f"{name}: needs one direct import from {module}"
    nodes = list(ast.walk(tree))
    assert _bindings(nodes, name) == imports, f"{name}: import is shadowed/rebound"
    assert not any(
        isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
        for node in nodes
    ), "star import makes typed control ownership ambiguous"
    _require_no_member_writes(nodes, name)
    if member is None:
        parents = {child: parent for parent in nodes for child in ast.iter_child_nodes(parent)}
        assert all(
            isinstance(parents[node], ast.Attribute) and parents[node].value is node
            for node in nodes if isinstance(node, ast.Name) and node.id == name
        ), f"{name}: module alias escapes the proven ownership chain"


def _require_typed_controls(spec_tree: ast.Module) -> None:
    """Prove the part owns a nonempty tuple of the real immutable row type.

    Tolerance expressions stay in the spec; this ownership check neither
    evaluates them nor invents a second registry of manufacturing limits.
    """
    _, controls = _single_assignment(spec_tree, "GEOMETRIC_CONTROLS")
    assert isinstance(controls, ast.Tuple) and controls.elts, "empty/unproven typed controls"
    for row in controls.elts:
        assert isinstance(row, ast.Call) and isinstance(row.func, ast.Name)
        _require_import(spec_tree, row.func.id, "_gtol_controls", "GeometricControl")
        assert not any(isinstance(arg, ast.Starred) for arg in row.args)
        assert all(keyword.arg is not None for keyword in row.keywords)
        assert len(row.args) >= 3 or any(
            keyword.arg == "tolerance" for keyword in row.keywords
        ), "typed control lacks a part-owned tolerance"


def _require_part_control_projection(
    tree: ast.Module, call: ast.Call, spec_tree: ast.Module, spec_module: str,
) -> None:
    """Recognize the existing indexed-loop projection, not arbitrary Python.

    Each link must be a direct, dominating binding in its lexical scope:
    imported spec -> controls tuple -> range(len(controls)) -> controls[index].
    Nested readback functions may have their own index/control locals.
    """
    tolerance = _keyword(call, "tolerance")
    assert (
        isinstance(tolerance, ast.Attribute) and tolerance.attr == "tolerance"
        and isinstance(tolerance.value, ast.Name)
    ), "typed FCF tolerance must project control.tolerance"
    control_name = tolerance.value.id
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    ancestors = []
    node = call
    while node in parents:
        node = parents[node]
        ancestors.append(node)
    scope = next(
        node for node in ancestors
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module, ast.Lambda))
    )
    assert isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)), "typed FCF needs a function scope"
    loops = [node for node in ancestors[:ancestors.index(scope)] if isinstance(node, ast.For)]
    assert loops, "typed control is not bound by an enclosing loop"
    loop = loops[0]
    assert loop in scope.body and isinstance(loop.target, ast.Name)
    index_name = loop.target.id
    assert _bindings(_scope_nodes(scope), index_name) == [loop.target], "loop index is shadowed/rebound"
    index_range = loop.iter
    assert (
        isinstance(index_range, ast.Call) and isinstance(index_range.func, ast.Name)
        and index_range.func.id == "range" and len(index_range.args) == 1
        and not index_range.keywords
    ), "typed control needs range(len(controls))"
    length = index_range.args[0]
    assert (
        isinstance(length, ast.Call) and isinstance(length.func, ast.Name)
        and length.func.id == "len" and len(length.args) == 1
        and isinstance(length.args[0], ast.Name) and not length.keywords
    ), "typed control needs range(len(controls))"
    for builtin in ("range", "len"):
        assert not _bindings(ast.walk(tree), builtin), f"{builtin}: builtin is shadowed"
    controls_name = length.args[0].id
    assignments = [
        node for node in loop.body if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id == control_name
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        )
    ]
    assert len(assignments) == 1, "control needs one direct loop assignment"
    assignment = assignments[0]
    targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
    assert len(targets) == 1
    assert _bindings(_scope_nodes(scope), control_name) == targets, "control is shadowed/rebound"
    _require_no_member_writes(_scope_nodes(scope), control_name)
    value = assignment.value
    assert (
        isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name)
        and value.value.id == controls_name and isinstance(value.slice, ast.Name)
        and value.slice.id == index_name
    ), "control must be the current part-owned tuple row"
    statement = next(node for node in ancestors if node in loop.body)
    assert loop.body.index(assignment) < loop.body.index(statement), "control binding must precede FCF"
    controls_assignment, source = _single_assignment(scope, controls_name)
    assert scope.body.index(controls_assignment) < scope.body.index(loop)
    if isinstance(source, ast.Attribute):
        assert source.attr == "GEOMETRIC_CONTROLS" and isinstance(source.value, ast.Name)
        _require_import(tree, source.value.id, spec_module)
    else:
        assert isinstance(source, ast.Name)
        _require_import(tree, source.id, spec_module, "GEOMETRIC_CONTROLS")
    _require_typed_controls(spec_tree)


def _scan_drawing_fcf_sources(scripts: Path) -> tuple[int, int]:
    projected = typed_projected = 0
    drawings = sorted(scripts.glob("draw_*.py"))
    assert drawings, f"{scripts}: no drawing recipes matched"
    for drawing in drawings:
        tree = ast.parse(drawing.read_text(encoding="utf-8"), filename=str(drawing))
        calls = _fcf_calls(tree)
        if not calls:
            continue

        spec_path = scripts / f"{drawing.stem.removeprefix('draw_')}_spec.py"
        declared_mapping = _part_mapping(spec_path)
        mapping = declared_mapping if declared_mapping is not None else {}
        if declared_mapping is not None:
            assert mapping, f"{spec_path}: empty {TOLERANCE_MAPPING}"
            assert all(re.fullmatch(r"\d+(?:\.\d+)?", value) for value in mapping.values())
            assert all(float(value) > 0.0 for value in mapping.values())
        loop_bindings = _loop_string_bindings(tree)
        spec_tree = ast.parse(spec_path.read_text(encoding="utf-8"))

        for call in calls:
            tolerance = _keyword(call, "tolerance")
            if (
                isinstance(tolerance, ast.Subscript)
                and isinstance(tolerance.value, ast.Name)
                and tolerance.value.id == TOLERANCE_MAPPING
            ):
                assert all(
                    key in mapping
                    for key in _mapping_reference_keys(tolerance, loop_bindings)
                )
            elif isinstance(tolerance, ast.Attribute):
                _require_part_control_projection(tree, call, spec_tree, spec_path.stem)
                typed_projected += 1
            else:
                assert declared_mapping is not None, f"{spec_path} lacks {TOLERANCE_MAPPING}"
                _require_part_band_profile(tree, call, spec_tree, spec_path.stem)
            projected += 1

        references: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            if not isinstance(node.value, ast.Name):
                continue
            if node.value.id != TOLERANCE_MAPPING:
                continue
            references.extend(_mapping_reference_keys(node, loop_bindings))
        assert Counter(references) == Counter(mapping.keys()), (
            f"{drawing}: spec/reference key mismatch: "
            f"spec={Counter(mapping.keys())!r}, references={Counter(references)!r}"
        )

    assert projected > 0, "no drawing FCF calls matched"
    assert typed_projected > 0, "no current typed FCF projections matched"
    return projected, typed_projected


def test_all_drawing_fcf_values_come_from_part_specs() -> None:
    projected, typed_projected = _scan_drawing_fcf_sources(SCRIPTS)
    print(f"FCF census: {projected} calls, {typed_projected} typed projections")


_TYPED_SPEC_SOURCE = """
from _gtol_controls import GeometricControl
MODEL_LIMIT = 0.125
GEOMETRIC_CONTROLS = (
    GeometricControl("stop", "total_runout", f"{MODEL_LIMIT:.3f}", face, ("A",)),
)
"""
_TYPED_DRAWING_SOURCE = """
import sample_spec as part_spec
def draw():
    controls = part_spec.GEOMETRIC_CONTROLS
    for index in range(len(controls)):
        control = controls[index]
        add_feature_control_frame(characteristic=control.characteristic, tolerance=control.tolerance)
    def settled():
        for index in range(len(controls)):
            control = controls[index]
            readback(control.tolerance)
"""


@pytest.mark.parametrize(("old", "new"), [
    ("part_spec", "model"),
    ("controls", "rows"),
    ("control", "row"),
    ("index", "slot"),
    ("controls =", "controls: tuple ="),
    ("control =", "control: object ="),
    (
        "import sample_spec as part_spec",
        "from sample_spec import GEOMETRIC_CONTROLS as imported_rows",
    ),
])
def test_typed_projection_accepts_bound_aliases(old: str, new: str) -> None:
    source = _TYPED_DRAWING_SOURCE.replace(old, new)
    if "imported_rows" in source:
        source = source.replace("part_spec.GEOMETRIC_CONTROLS", "imported_rows")
    tree = ast.parse(source)
    _require_part_control_projection(
        tree, _fcf_calls(tree)[0], ast.parse(_TYPED_SPEC_SOURCE), "sample_spec",
    )


@pytest.mark.parametrize(("old", "new"), [
    ("control.tolerance)", "'0.125')"),
    ("control.tolerance)", "0.125)"),
    ("control.tolerance)", "fake.tolerance)"),
    ("control.tolerance)", "control.tolerance_override)"),
    ("control.tolerance)", "str(control.tolerance))"),
    ("sample_spec as part_spec", "other_spec as part_spec"),
    ("import sample_spec as part_spec", "from other_spec import part_spec"),
    ("def draw():", "def draw(part_spec):"),
    ("def draw():", "def draw(controls):"),
    ("def draw():", "def draw(control):"),
    ("def draw():", "def draw(index):"),
    ("controls = part_spec.GEOMETRIC_CONTROLS", "controls = local_controls"),
    ("controls = part_spec.GEOMETRIC_CONTROLS", "controls = part_spec.OTHER_CONTROLS"),
    ("control = controls[index]", "control = local_controls[index]"),
    ("control = controls[index]", "control = controls[0]"),
    ("control = controls[index]", "control = fake_control"),
    ("control = controls[index]", "control = controls[index]\n        control = fake_control"),
    ("control = controls[index]", "control = controls[index]\n        control.tolerance = '0.125'"),
    ("control = controls[index]", "control = controls[index]\n        del control.tolerance"),
    ("control = controls[index]", "control = controls[index]\n        setattr(control, 'tolerance', '0.125')"),
    ("control = controls[index]", "control = controls[index]\n        import other as control"),
    ("control = controls[index]", "control = controls[index]\n        index = 0"),
    ("for index in range(len(controls)):", "for index in range(1):"),
    ("for index in range(len(controls)):", "for index in range(len(local_controls)):"),
    ("for index in range(len(controls)):", "for index in range(len(controls), 2):"),
    ("controls = part_spec.GEOMETRIC_CONTROLS", "controls = part_spec.GEOMETRIC_CONTROLS\n    controls = local_controls"),
    ("controls = part_spec.GEOMETRIC_CONTROLS", "controls = part_spec.GEOMETRIC_CONTROLS\n    controls[0] = fake_control"),
    ("controls = part_spec.GEOMETRIC_CONTROLS", "controls = part_spec.GEOMETRIC_CONTROLS\n    controls.append(fake_control)"),
    ("import sample_spec as part_spec", "import sample_spec as part_spec\npart_spec = local_spec"),
    ("import sample_spec as part_spec", "import sample_spec as part_spec\nimport other as part_spec"),
    ("import sample_spec as part_spec", "import sample_spec as part_spec\ndef part_spec(): pass"),
    ("import sample_spec as part_spec", "import sample_spec as part_spec\npart_spec.GEOMETRIC_CONTROLS = local_controls"),
    ("import sample_spec as part_spec", "import sample_spec as part_spec\nalias = part_spec"),
    ("import sample_spec as part_spec", "import sample_spec as part_spec\nfrom other import *"),
    ("import sample_spec as part_spec", "import sample_spec as part_spec\nrange = custom_range"),
    ("import sample_spec as part_spec", "import sample_spec as part_spec\nfrom other import len"),
    (
        "    controls = part_spec.GEOMETRIC_CONTROLS",
        "    controls = part_spec.GEOMETRIC_CONTROLS\n"
        "    def replace():\n        nonlocal controls\n        controls = local_controls\n"
        "    replace()",
    ),
    (
        "    controls = part_spec.GEOMETRIC_CONTROLS",
        "    controls = part_spec.GEOMETRIC_CONTROLS\n"
        "    def replace():\n        controls[0] = fake_control\n"
        "    replace()",
    ),
    (
        "        control = controls[index]\n"
        "        add_feature_control_frame(characteristic=control.characteristic, tolerance=control.tolerance)",
        "        add_feature_control_frame(characteristic=control.characteristic, tolerance=control.tolerance)\n"
        "        control = controls[index]",
    ),
])
def test_typed_projection_rejects_drawing_owned_or_unbound_rows(old: str, new: str) -> None:
    tree = ast.parse(_TYPED_DRAWING_SOURCE.replace(old, new))
    with pytest.raises(AssertionError):
        _require_part_control_projection(
            tree, _fcf_calls(tree)[0], ast.parse(_TYPED_SPEC_SOURCE), "sample_spec",
        )


@pytest.mark.parametrize("extra", [
    "imported_rows = local_controls",
    "import other as imported_rows",
    "def shadow(imported_rows): pass",
    "del imported_rows",
])
def test_typed_projection_rejects_shadowed_direct_control_import(extra: str) -> None:
    source = _TYPED_DRAWING_SOURCE.replace(
        "import sample_spec as part_spec",
        "from sample_spec import GEOMETRIC_CONTROLS as imported_rows\n" + extra,
    ).replace("part_spec.GEOMETRIC_CONTROLS", "imported_rows")
    tree = ast.parse(source)
    with pytest.raises(AssertionError):
        _require_part_control_projection(
            tree, _fcf_calls(tree)[0], ast.parse(_TYPED_SPEC_SOURCE), "sample_spec",
        )


@pytest.mark.parametrize(("old", "new"), [
    ("_gtol_controls import GeometricControl", "local_controls import GeometricControl"),
    ("MODEL_LIMIT = 0.125", "MODEL_LIMIT = 0.125\nGeometricControl = fake"),
    ("MODEL_LIMIT = 0.125", "MODEL_LIMIT = 0.125\nimport other as GeometricControl"),
    ("GEOMETRIC_CONTROLS = (", "LOCAL_CONTROLS = ("),
    (
        'GeometricControl("stop", "total_runout", f"{MODEL_LIMIT:.3f}", face, ("A",)),',
        "",
    ),
    (
        'GeometricControl("stop", "total_runout", f"{MODEL_LIMIT:.3f}", face, ("A",)),',
        "fake_control,",
    ),
    (
        'GeometricControl("stop", "total_runout", f"{MODEL_LIMIT:.3f}", face, ("A",)),',
        'GeometricControl(key="stop", characteristic="total_runout", face=face),',
    ),
    ("MODEL_LIMIT = 0.125", "MODEL_LIMIT = 0.125\nfrom other import *"),
])
def test_typed_projection_requires_actual_part_owned_row_type(old: str, new: str) -> None:
    tree = ast.parse(_TYPED_DRAWING_SOURCE)
    with pytest.raises(AssertionError):
        _require_part_control_projection(
            tree, _fcf_calls(tree)[0], ast.parse(_TYPED_SPEC_SOURCE.replace(old, new)), "sample_spec",
        )


def test_typed_projection_accepts_imported_constructor_alias_and_keyword_tolerance() -> None:
    spec = _TYPED_SPEC_SOURCE.replace(
        "import GeometricControl", "import GeometricControl as Row",
    ).replace(
        'GeometricControl("stop", "total_runout", f"{MODEL_LIMIT:.3f}", face, ("A",))',
        'Row(key="stop", characteristic="total_runout", tolerance=f"{MODEL_LIMIT:.3f}", face=face)',
    )
    tree = ast.parse(_TYPED_DRAWING_SOURCE)
    _require_part_control_projection(tree, _fcf_calls(tree)[0], ast.parse(spec), "sample_spec")


@pytest.mark.parametrize("extra", [
    "\nGEOMETRIC_CONTROLS = ()",
    "\nGEOMETRIC_CONTROLS += (fake_control,)",
    "\nGEOMETRIC_CONTROLS[0] = fake_control",
])
def test_typed_projection_rejects_rebound_spec_controls(extra: str) -> None:
    tree = ast.parse(_TYPED_DRAWING_SOURCE)
    with pytest.raises(AssertionError):
        _require_part_control_projection(
            tree, _fcf_calls(tree)[0], ast.parse(_TYPED_SPEC_SOURCE + extra), "sample_spec",
        )


def _write_typed_scan_fixture(scripts: Path) -> None:
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "sample_spec.py").write_text(_TYPED_SPEC_SOURCE, encoding="utf-8")
    (scripts / "draw_sample.py").write_text(_TYPED_DRAWING_SOURCE, encoding="utf-8")


def test_fcf_scan_covers_every_typed_drawing_and_legacy_mapping(tmp_path: Path) -> None:
    _write_typed_scan_fixture(tmp_path)
    (tmp_path / "other_spec.py").write_text(_TYPED_SPEC_SOURCE, encoding="utf-8")
    (tmp_path / "draw_other.py").write_text(
        _TYPED_DRAWING_SOURCE.replace("sample_spec", "other_spec"), encoding="utf-8",
    )
    (tmp_path / "legacy_spec.py").write_text(
        "GEOMETRIC_TOLERANCES_MM: dict[str, str] = {'face': '0.25'}", encoding="utf-8",
    )
    (tmp_path / "draw_legacy.py").write_text(
        "add_feature_control_frame(tolerance=GEOMETRIC_TOLERANCES_MM['face'])", encoding="utf-8",
    )
    assert _scan_drawing_fcf_sources(tmp_path) == (3, 2)
    (tmp_path / "draw_other.py").write_text(
        _TYPED_DRAWING_SOURCE.replace("sample_spec", "other_spec").replace("control.tolerance)", "'0.125')"),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _scan_drawing_fcf_sources(tmp_path)


@pytest.mark.parametrize("pattern", ["nowhere/draw_*.py", "nested/draw_*.py"])
def test_fcf_scan_rejects_empty_or_one_directory_deep_glob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pattern: str,
) -> None:
    _write_typed_scan_fixture(tmp_path)
    original_glob = Path.glob

    def repointed_glob(path: Path, requested: str):
        assert requested == "draw_*.py"
        return original_glob(path, pattern)

    monkeypatch.setattr(Path, "glob", repointed_glob)
    with pytest.raises(AssertionError, match="no drawing recipes matched"):
        _scan_drawing_fcf_sources(tmp_path)


@pytest.mark.parametrize("source", [
    "pass",
    "add_feature_control_frame(tolerance=GEOMETRIC_TOLERANCES_MM['face'])",
])
def test_fcf_scan_requires_nonempty_fcf_and_current_typed_census(tmp_path: Path, source: str) -> None:
    (tmp_path / "draw_legacy.py").write_text(source, encoding="utf-8")
    (tmp_path / "legacy_spec.py").write_text(
        "GEOMETRIC_TOLERANCES_MM: dict[str, str] = {'face': '0.25'}", encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="no (drawing FCF calls|current typed FCF projections) matched"):
        _scan_drawing_fcf_sources(tmp_path)


@pytest.mark.parametrize("mapping", [
    "{}",
    "{'face': '0'}",
    "{'face': '-0.25'}",
    "{'face': 'unowned'}",
    "{'other': '0.25'}",
])
def test_typed_support_preserves_legacy_mapping_guards(tmp_path: Path, mapping: str) -> None:
    _write_typed_scan_fixture(tmp_path)
    (tmp_path / "legacy_spec.py").write_text(
        f"GEOMETRIC_TOLERANCES_MM: dict[str, str] = {mapping}", encoding="utf-8",
    )
    (tmp_path / "draw_legacy.py").write_text(
        "add_feature_control_frame(tolerance=GEOMETRIC_TOLERANCES_MM['face'])", encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _scan_drawing_fcf_sources(tmp_path)


@pytest.mark.parametrize("assignment", [
    "ZONE = f'{HEIGHT_BAND[0]:g}'",
    "BASE = f'{HEIGHT_BAND[0]:g}'\nZONE = BASE",
    "BASE: str = f'{HEIGHT_BAND[0]:g}'\nZONE: str = BASE",
])
def test_profile_zone_accepts_only_part_band_projection(assignment: str) -> None:
    tree = ast.parse(
        "from sample_spec import HEIGHT_BAND\n" + assignment
        + "\nadd_feature_control_frame(characteristic='profile_surface', tolerance=ZONE)"
    )
    _require_part_band_profile(
        tree, _fcf_calls(tree)[0], ast.parse("HEIGHT_BAND = (0.5, 0.0)"), "sample_spec",
    )


@pytest.mark.parametrize(("source", "spec"), [
    ("ZONE = '0.5'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("ZONE = f'{0.5:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("HEIGHT_BAND = (0.5, 0.0)\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from notes import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[1]:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:.1f}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'zone {HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", ""),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.5, -0.1)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = (0.0, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'", "HEIGHT_BAND = OTHER"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'\nZONE = '0.5'", "HEIGHT_BAND = (0.5, 0.0)"),
    ("from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'\ndef local(HEIGHT_BAND): pass", "HEIGHT_BAND = (0.5, 0.0)"),
    ("ZONE = OTHER\nOTHER = ZONE", "HEIGHT_BAND = (0.5, 0.0)"),
])
def test_profile_zone_rejects_unproven_or_invalid_band_sources(source: str, spec: str) -> None:
    tree = ast.parse(
        source + "\nadd_feature_control_frame(characteristic='profile_surface', tolerance=ZONE)"
    )
    with pytest.raises(AssertionError):
        _require_part_band_profile(tree, _fcf_calls(tree)[0], ast.parse(spec), "sample_spec")


@pytest.mark.parametrize("characteristic", ["position", "profile_line", "flatness"])
def test_part_band_projection_cannot_supply_other_characteristics(characteristic: str) -> None:
    tree = ast.parse(
        "from sample_spec import HEIGHT_BAND\nZONE = f'{HEIGHT_BAND[0]:g}'\n"
        f"add_feature_control_frame(characteristic={characteristic!r}, tolerance=ZONE)"
    )
    with pytest.raises(AssertionError):
        _require_part_band_profile(
            tree, _fcf_calls(tree)[0], ast.parse("HEIGHT_BAND = (0.5, 0.0)"), "sample_spec",
        )



def test_within_limits_are_not_literal_drawing_values() -> None:
    violations: list[str] = []
    for drawing in sorted(SCRIPTS.glob("draw_*.py")):
        tree = ast.parse(drawing.read_text(encoding="utf-8"), filename=str(drawing))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if re.search(r"\bWITHIN\s+\d", node.value, re.IGNORECASE):
                violations.append(f"{drawing}:{node.lineno}: {node.value!r}")
    assert not violations, "drawing-owned WITHIN limits:\n" + "\n".join(violations)
