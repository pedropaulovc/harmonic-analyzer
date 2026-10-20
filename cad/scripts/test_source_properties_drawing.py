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
when the build calls it. Supplier-state wrappers additionally trace the actual
builder's required-property branch and the source build's canonical property
mapping through reusable builders to its custom-property write. SolidWorks-free.
"""

from __future__ import annotations

import ast
import sys
from functools import cache
from pathlib import Path

import pytest

import _config
import _purchased_fastener_drawing as purchased
from _part_properties import part_properties
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


@cache
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _call_names(tree: ast.AST) -> set[str]:
    return {
        getattr(node.func, "id", getattr(node.func, "attr", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }


def _property_names(
    tree: ast.Module, value: ast.expr, assigned: dict[str, ast.expr]
) -> set[str]:
    """Resolve literal property sequences, including imported/starred tuples."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return {value.value}
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        return set().union(
            *(
                _property_names(
                    tree,
                    element.value if isinstance(element, ast.Starred) else element,
                    assigned,
                )
                for element in value.elts
            )
        )
    if isinstance(value, ast.Name):
        if value.id in assigned:
            return _property_names(tree, assigned[value.id], assigned)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            for alias in node.names:
                if (alias.asname or alias.name) != value.id:
                    continue
                imported = _tree(SCRIPTS / f"{node.module.replace('.', '/')}.py")
                constants = {
                    target.id: statement.value
                    for statement in imported.body
                    if isinstance(statement, ast.Assign)
                    for target in statement.targets
                    if isinstance(target, ast.Name)
                }
                return _property_names(imported, ast.Name(id=alias.name), constants)
    raise AssertionError(f"unresolved required property sequence: {ast.unparse(value)}")


def _supplier_builder_call(tree: ast.Module) -> ast.Call | None:
    names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "_supplier_spring_drawing"
        for alias in node.names
        if alias.name == "build_supplier_spring_drawing"
    }
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in names
    ]
    if not calls:
        return None
    assert len(calls) == 1, "supplier drawing must have one source-property contract"
    return calls[0]


def _selected_nodes(node: ast.AST, options: dict[str, bool]):
    """Follow known boolean options; retain both sides of other conditions."""
    yield node
    if isinstance(node, ast.If) and isinstance(node.test, ast.Name):
        if node.test.id in options:
            for statement in node.body if options[node.test.id] else node.orelse:
                yield from _selected_nodes(statement, options)
            return
    for child in ast.iter_child_nodes(node):
        yield from _selected_nodes(child, options)


def _required_in(tree: ast.Module, options: dict[str, bool]) -> set[str]:
    nodes = tuple(_selected_nodes(tree, options))
    assigned = {
        target.id: node.value
        for node in nodes
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    required = set()
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", getattr(node.func, "attr", "")) != "read_required_properties":
            continue
        for keyword in node.keywords:
            if keyword.arg == "required":
                required |= _property_names(tree, keyword.value, assigned)
    return required


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
    supplier_call = _supplier_builder_call(tree)
    if supplier_call is not None:
        helper = _tree(SCRIPTS / "_supplier_spring_drawing.py")
        builder = next(
            node
            for node in helper.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "build_supplier_spring_drawing"
        )
        defaults = dict(
            zip(
                (argument.arg for argument in builder.args.kwonlyargs),
                builder.args.kw_defaults,
            )
        )
        metadata = next(
            (
                keyword.value
                for keyword in supplier_call.keywords
                if keyword.arg == "spring_metadata"
            ),
            defaults["spring_metadata"],
        )
        assert isinstance(metadata, ast.Constant) and isinstance(metadata.value, bool), (
            f"{draw.name}: source-property branch must be statically known"
        )
        required = _required_in(helper, {"spring_metadata": metadata.value})
    else:
        required = _required_in(tree, {})
    assert required, f"{draw.name}: no required property set found"
    return required


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


def _canonical_part_names(build: Path) -> set[str | None]:
    """Trace canonical identity writes; reject rebinding and possible overwrites.

    Only named local/imported functions with a ``part_name`` parameter are
    followed. Mapping parameters retain their statically known keys, and a
    mapping-producing helper is credited only for its actual literal returns.
    Unknown writes or noncanonical Number/Title writes invalidate ownership.
    """
    stamped = set()
    seen = set()

    def literal_keys(expression: ast.expr | None) -> frozenset[str] | None:
        if not isinstance(expression, ast.Dict):
            return None
        keys = set()
        for key, value in zip(expression.keys, expression.values):
            if key is None:
                unpacked = literal_keys(value)
                if unpacked is None:
                    return None
                keys.update(unpacked)
            elif isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
            else:
                return None
        return frozenset(keys)

    def visit(
        path: Path,
        function: str,
        part_name: str | None = None,
        mapping_arguments: tuple[tuple[str, frozenset[str] | None], ...] = (),
    ) -> None:
        identity = (path, function, part_name, mapping_arguments)
        if identity in seen:
            return
        seen.add(identity)
        tree = _tree(path)
        definition = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function
        )
        nodes = tuple(ast.walk(definition))
        local_stores = {
            node.id
            for node in nodes
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }
        assignments: dict[str, list[ast.expr]] = {}
        for node in (*tree.body, *nodes):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments.setdefault(target.id, []).append(node.value)
        mutated = {
            node.value.id
            for node in nodes
            if isinstance(node, ast.Subscript)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and isinstance(node.value, ast.Name)
        } | {
            node.func.value.id
            for node in nodes
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.attr in {
                "update", "clear", "pop", "popitem", "setdefault",
                "__setitem__", "__delitem__",
            }
        } | {
            node.target.id
            for node in nodes
            if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name)
        }
        imported = {
            alias.asname or alias.name: (node.module, alias.name)
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
            for alias in node.names
        }
        bound_mappings = dict(mapping_arguments)

        def assigned(expression: ast.expr | None) -> ast.expr | None:
            visited = set()
            while isinstance(expression, ast.Name):
                name = expression.id
                values = assignments.get(name, ())
                if name in visited or name in mutated or len(values) != 1:
                    return None
                visited.add(name)
                expression = values[0]
            return expression

        def value(expression: ast.expr | None) -> str | None:
            if isinstance(expression, ast.Name) and expression.id == "part_name":
                return None if "part_name" in local_stores else part_name
            expression = assigned(expression)
            if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
                return expression.value
            return None

        def callee(call: ast.Call):
            if not isinstance(call.func, ast.Name):
                return None
            module, name = imported.get(call.func.id, (None, call.func.id))
            target = SCRIPTS / f"{module.replace('.', '/')}.py" if module else path
            if not target.is_file():
                return None
            called = next(
                (
                    node
                    for node in _tree(target).body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == name
                ),
                None,
            )
            return (target, called) if called is not None else None

        def mapping_keys(
            expression: ast.expr | None, resolving: frozenset[str] = frozenset()
        ) -> frozenset[str] | None:
            if isinstance(expression, ast.Name):
                name = expression.id
                if name in mutated or name in resolving:
                    return None
                if name in bound_mappings:
                    return None if name in local_stores else bound_mappings[name]
                values = assignments.get(name, ())
                if len(values) != 1:
                    return None
                return mapping_keys(values[0], resolving | {name})
            if isinstance(expression, ast.Constant) and expression.value is None:
                return frozenset()
            if isinstance(expression, ast.Dict):
                keys = set()
                for key, item in zip(expression.keys, expression.values):
                    if key is None:
                        unpacked = mapping_keys(item, resolving)
                        if unpacked is None:
                            return None
                        keys.update(unpacked)
                    elif isinstance(key, ast.Constant) and isinstance(key.value, str):
                        keys.add(key.value)
                    else:
                        return None
                return frozenset(keys)
            if isinstance(expression, ast.BoolOp) and isinstance(expression.op, ast.Or):
                alternatives = [mapping_keys(item, resolving) for item in expression.values]
                if any(keys is None for keys in alternatives):
                    return None
                return frozenset().union(*alternatives)
            if isinstance(expression, ast.Call):
                if (
                    isinstance(expression.func, ast.Name)
                    and expression.func.id == "dict"
                    and not expression.keywords
                    and len(expression.args) <= 1
                ):
                    return (
                        mapping_keys(expression.args[0], resolving)
                        if expression.args else frozenset()
                    )
                target = callee(expression)
                if target is not None:
                    returns = [
                        literal_keys(node.value)
                        for node in ast.walk(target[1])
                        if isinstance(node, ast.Return)
                    ]
                    if returns and all(keys is not None for keys in returns):
                        return frozenset().union(*returns)
            return None

        for call in nodes:
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            module, name = imported.get(call.func.id, (None, call.func.id))
            if module == "_custom_properties" and name == "apply_custom_properties":
                properties = (
                    call.args[1]
                    if len(call.args) > 1
                    else next(
                        (kw.value for kw in call.keywords if kw.arg == "properties"),
                        None,
                    )
                )
                canonical = assigned(properties)
                if (
                    isinstance(canonical, ast.Call)
                    and isinstance(canonical.func, ast.Name)
                    and imported.get(canonical.func.id)
                    == ("_part_properties", "part_properties")
                ):
                    argument = canonical.args[0] if canonical.args else next(
                        (kw.value for kw in canonical.keywords if kw.arg == "part_name"),
                        None,
                    )
                    stamped.add(value(argument))
                else:
                    keys = mapping_keys(properties)
                    if keys is None or keys & {"Number", "Title"}:
                        stamped.add(None)
                continue
            target = callee(call)
            if target is None:
                continue
            target_path, called = target
            positional = [*called.args.posonlyargs, *called.args.args]
            parameters = [*positional, *called.args.kwonlyargs]
            if not any(argument.arg == "part_name" for argument in parameters):
                continue
            defaults = dict(zip(
                (argument.arg for argument in positional[-len(called.args.defaults):]),
                called.args.defaults,
            )) if called.args.defaults else {}
            defaults.update(zip(
                (argument.arg for argument in called.args.kwonlyargs),
                called.args.kw_defaults,
            ))
            arguments = {argument.arg: item for argument, item in zip(positional, call.args)}
            arguments.update(
                (kw.arg, kw.value) for kw in call.keywords if kw.arg is not None
            )
            bound = {
                argument.arg: arguments.get(argument.arg, defaults.get(argument.arg))
                for argument in parameters
            }
            visit(
                target_path,
                called.name,
                value(bound["part_name"]),
                tuple((name, mapping_keys(item)) for name, item in bound.items()),
            )

    visit(build, "build")
    return stamped


@pytest.mark.parametrize("metadata", (False, True))
def test_supplier_required_properties_follow_selected_builder_branch(
    tmp_path, monkeypatch, metadata
) -> None:
    monkeypatch.setattr(sys.modules[__name__], "SCRIPTS", tmp_path)
    (tmp_path / "_property_contract.py").write_text(
        'BASE = ("Number", "Title")\n', encoding="utf-8"
    )
    (tmp_path / "_supplier_spring_drawing.py").write_text(
        "from _property_contract import BASE\n"
        "async def build_supplier_spring_drawing(adapter, spec, *, spring_metadata=False):\n"
        "    if spring_metadata:\n"
        '        names = (*BASE, "Finish", "Manufacturing Notes")\n'
        "        read_required_properties(adapter, names, required=names)\n"
        "    else:\n"
        "        read_required_properties(adapter, BASE, required=BASE)\n",
        encoding="utf-8",
    )
    draw = tmp_path / "draw_supplier.py"
    draw.write_text(
        "from _supplier_spring_drawing import build_supplier_spring_drawing as sheet\n"
        "async def build(adapter):\n"
        f"    return await sheet(adapter, None, spring_metadata={metadata!r})\n",
        encoding="utf-8",
    )
    expected = {"Number", "Title"}
    if metadata:
        expected |= {"Finish", "Manufacturing Notes"}
    assert _required(draw) == expected


@pytest.mark.parametrize(
    ("argument", "write", "rebind", "mutation", "expected"),
    [
        ("part_name", True, "", "", {"vn-own-part"}),
        ('"vn-foreign-part"', True, "", "", {"vn-foreign-part"}),
        ("part_name", False, "", "", set()),
        ("part_name", True, '    part_name = "vn-foreign-part"\n', "", {None}),
        ("part_name", True, '    part_name += "-foreign"\n', "", {None}),
        ("part_name", True, "", '    properties["Title"] = "foreign"\n', {None}),
        ("part_name", True, "", '    properties.update({"Number": "foreign"})\n', {None}),
    ],
)
def test_canonical_property_ownership_follows_forwarded_identity(
    tmp_path, monkeypatch, argument, write, rebind, mutation, expected
) -> None:
    monkeypatch.setattr(sys.modules[__name__], "SCRIPTS", tmp_path)
    helper = (
        "from _part_properties import part_properties\n"
        "from _custom_properties import apply_custom_properties\n"
        "async def reusable(adapter, part_name):\n"
        f"{rebind}"
        f"    properties = part_properties({argument})\n"
        f"{mutation}"
    )
    if write:
        helper += "    apply_custom_properties(adapter, properties)\n"
    (tmp_path / "_reusable.py").write_text(helper, encoding="utf-8")
    build = tmp_path / "build_supplier.py"
    build.write_text(
        "from _reusable import reusable as make_part\n"
        'PART_NAME = "vn-own-part"\n'
        "async def build(adapter):\n"
        "    return await make_part(adapter, part_name=PART_NAME)\n",
        encoding="utf-8",
    )
    assert _canonical_part_names(build) == expected


@pytest.mark.parametrize(
    ("mapping", "stock_key", "invalid"),
    [
        ('{"Finish": "NONE"}', "Stock Name", False),
        ('{"Number": "foreign"}', "Stock Name", True),
        ('{"Title": "foreign"}', "Stock Name", True),
        ("external_properties()", "Stock Name", True),
        ('{"Finish": "NONE", **external_properties()}', "Stock Name", True),
        ("stock_properties(part_name)", "Stock Name", False),
        ("stock_properties(part_name)", "Number", True),
        ("stock_properties(part_name)", "Title", True),
    ],
)
def test_canonical_identity_rejects_unproven_or_identity_overwriting_side_writes(
    tmp_path, monkeypatch, mapping, stock_key, invalid
) -> None:
    monkeypatch.setattr(sys.modules[__name__], "SCRIPTS", tmp_path)
    (tmp_path / "_reusable.py").write_text(
        "from _part_properties import part_properties\n"
        "from _custom_properties import apply_custom_properties\n"
        "def stock_properties(part_name):\n"
        f"    return {{{stock_key!r}: part_name}}\n"
        "async def reusable(adapter, part_name):\n"
        "    apply_custom_properties(adapter, part_properties(part_name))\n"
        f"    apply_custom_properties(adapter, {mapping})\n",
        encoding="utf-8",
    )
    build = tmp_path / "build_supplier.py"
    build.write_text(
        "from _reusable import reusable\n"
        "async def build(adapter):\n"
        '    return await reusable(adapter, "vn-own-part")\n',
        encoding="utf-8",
    )
    expected = {"vn-own-part"}
    if invalid:
        expected.add(None)
    assert _canonical_part_names(build) == expected


@pytest.mark.parametrize("extra_key", ("Manufacturing Notes", "Title"))
def test_canonical_identity_inspects_forwarded_extra_mapping_keys(
    tmp_path, monkeypatch, extra_key
) -> None:
    monkeypatch.setattr(sys.modules[__name__], "SCRIPTS", tmp_path)
    (tmp_path / "_reusable.py").write_text(
        "from _part_properties import part_properties\n"
        "from _custom_properties import apply_custom_properties\n"
        "async def reusable(adapter, part_name, extra=None):\n"
        "    apply_custom_properties(adapter, part_properties(part_name))\n"
        '    apply_custom_properties(adapter, {"Finish": "NONE", **dict(extra or {})})\n',
        encoding="utf-8",
    )
    build = tmp_path / "build_supplier.py"
    build.write_text(
        "from _reusable import reusable\n"
        "async def build(adapter):\n"
        f'    return await reusable(adapter, "vn-own-part", extra={{{extra_key!r}: "note"}})\n',
        encoding="utf-8",
    )
    expected = {"vn-own-part"}
    if extra_key == "Title":
        expected.add(None)
    assert _canonical_part_names(build) == expected


def test_every_part_drawing_is_under_test() -> None:
    assert len(PART_DRAWINGS) >= 90


@pytest.mark.parametrize("drawing", PART_DRAWINGS, ids=lambda drawing: drawing.name)
def test_source_part_stamps_every_required_property(drawing) -> None:
    stem = drawing.part.replace("_", "-")
    build = SCRIPTS / f"build_{drawing.part}.py"
    assert build.is_file(), f"{drawing.name}: no build script {build.name}"
    required = _required(SCRIPTS / drawing.script_name)
    if _supplier_builder_call(_tree(SCRIPTS / drawing.script_name)) is not None:
        canonical = _canonical_part_names(build)
        assert canonical == {stem}, (
            f"{drawing.name}: canonical properties stamped for {canonical}, not {stem}"
        )
    stamped, marks = _stamped(stem, build)
    assert not required - stamped, (
        f"{drawing.name}: {build.name} never stamps {sorted(required - stamped)}"
    )
    if not marks:
        return
    row = _config.parts(stem)
    blank = [field for field in _DRAWING_MARK_FIELDS.values() if row.get(field) in (None, "")]
    assert not blank, f"{stem}: apply_drawing_properties reads blank registry fields {blank}"
