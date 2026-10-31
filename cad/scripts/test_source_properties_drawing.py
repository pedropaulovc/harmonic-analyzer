"""Every part drawing's source part stamps the properties its title block needs.

A drawing reads its title block from the source part's custom properties and
fails at build time when a required one is missing (``read_required_properties``).
The warm build of integ 9a0f50b1c lost ``drawing:dt_cylinder_end_disc`` that way:
the #743 rebuild of MHA-DT-26 never called ``apply_drawing_properties``, so
Material Specification / Finish / Quantity were never stamped.  This contract
catches the same gap offline, across every registered part drawing.

"Stamped" is static and deliberately generous: the keys ``part_properties``
returns for the part, every string literal in the part's build script and in
the direct repo-local modules it imports (``_drawing_marks`` aside, whose literals only
count through a call to ``apply_drawing_properties``), plus that helper's keys
when the build calls it.  Configured document properties are stricter: only
keys in the mapping actually passed to ``apply_drawing_properties`` count,
not unused metadata or readback requirements. Their finite metadata tuples,
tables and prefix comprehensions are inspected without importing producers or
executing Python. Unknown shapes fail closed. SolidWorks-free.
"""

from __future__ import annotations

import ast
import functools
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


def _metadata(tree: ast.Module, value: ast.expr) -> tuple[ast.Module, ast.expr]:
    """Follow constant aliases/imports only; never evaluate producer code."""
    for _ in range(12):
        if isinstance(value, ast.Name):
            assigned = [
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Name) and target.id == value.id
            ]
            if assigned:
                assert len(assigned) == 1, f"ambiguous metadata {value.id}"
                value = assigned[0]
                continue
            imported = [
                (node.module, alias.name)
                for node in tree.body
                if isinstance(node, ast.ImportFrom) and node.module
                for alias in node.names
                if (alias.asname or alias.name) == value.id
            ]
            assert len(imported) == 1, f"unresolved metadata {value.id}"
            module, name = imported[0]
        elif isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name):
            imported = [
                alias.name
                for node in tree.body
                if isinstance(node, ast.Import)
                for alias in node.names
                if (alias.asname or alias.name) == value.value.id
            ]
            assert len(imported) == 1, f"unresolved metadata {ast.unparse(value)}"
            module, name = imported[0], value.attr
        else:
            return tree, value
        path = SCRIPTS / f"{module.replace('.', '/')}.py"
        assert path.is_file(), f"metadata import is not repo-local: {module}"
        tree, value = _tree(path), ast.Name(id=name, ctx=ast.Load())
    raise AssertionError("metadata alias chain is too deep or cyclic")


def _metadata_string(tree: ast.Module, value: ast.expr) -> str:
    _, value = _metadata(tree, value)
    assert isinstance(value, ast.Constant) and isinstance(value.value, str), (
        f"not a metadata string: {ast.unparse(value)}"
    )
    return value.value


def _metadata_dict(
    tree: ast.Module, value: ast.expr
) -> tuple[ast.Module, ast.Dict]:
    tree, value = _metadata(tree, value)
    assert isinstance(value, ast.Dict), f"not a metadata table: {ast.unparse(value)}"
    return tree, value


def _prefix_key(value: ast.expr, names: dict[str, str]) -> str:
    assert isinstance(value, ast.JoinedStr), "expected a generated property name"
    pieces = []
    for piece in value.values:
        if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
            pieces.append(piece.value)
        else:
            assert (
                isinstance(piece, ast.FormattedValue)
                and isinstance(piece.value, ast.Name)
                and piece.value.id in names
                and piece.conversion == -1
                and piece.format_spec is None
            ), f"unsupported property-name format: {ast.unparse(value)}"
            pieces.append(names[piece.value.id])
    return "".join(pieces)


def _pair_target(target: ast.expr) -> tuple[str, str]:
    assert (
        isinstance(target, ast.Tuple)
        and len(target.elts) == 2
        and all(isinstance(element, ast.Name) for element in target.elts)
    ), "expected a metadata key/value target"
    return target.elts[0].id, target.elts[1].id


def _items_table(value: ast.expr) -> ast.expr:
    assert (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr == "items"
        and not value.args
        and not value.keywords
    ), "expected metadata.items()"
    return value.func.value


def _prefix_keys(
    tree: ast.Module,
    key: ast.expr,
    generators: list[ast.comprehension],
    sequences: dict[str, tuple[str, ...]],
) -> set[str]:
    """Only the existing one-member and per-member note-table shapes.

    Values are deliberately opaque. In particular the second wire iteration
    stays inside its own member's table, never a union of every member's keys.
    """
    assert 1 <= len(generators) <= 2
    assert all(not generator.ifs and not generator.is_async for generator in generators)
    first = generators[0]
    if isinstance(first.target, ast.Name):
        configurations = _metadata_strings(tree, first.iter, sequences)
        if len(generators) == 1:
            return {
                _prefix_key(key, {first.target.id: configuration})
                for configuration in configurations
            }
        second = generators[1]
        assert (
            isinstance(second.iter, ast.Subscript)
            and isinstance(second.iter.slice, ast.Name)
            and second.iter.slice.id == first.target.id
            and isinstance(second.target, ast.Tuple)
            and len(second.target.elts) == 3
            and all(isinstance(element, ast.Name) for element in second.target.elts)
        ), "expected per-member note-position rows"
        table_tree, table = _metadata_dict(tree, second.iter.value)
        rows = {
            _metadata_string(table_tree, name): value
            for name, value in zip(table.keys, table.values, strict=True)
        }
        keys = set()
        for configuration in configurations:
            assert configuration in rows, f"missing note table for {configuration}"
            _, positions = _metadata(table_tree, rows[configuration])
            assert isinstance(positions, (ast.Tuple, ast.List))
            for position in positions.elts:
                assert isinstance(position, (ast.Tuple, ast.List)) and len(position.elts) == 3
                keys.add(_prefix_key(key, {
                    first.target.id: configuration,
                    second.target.elts[0].id: _metadata_string(table_tree, position.elts[0]),
                }))
        return keys
    configuration_name, properties_name = _pair_target(first.target)
    table_tree, table = _metadata_dict(tree, _items_table(first.iter))
    if len(generators) == 1:
        return {
            _prefix_key(key, {configuration_name: _metadata_string(table_tree, name)})
            for name in table.keys
        }
    second = generators[1]
    property_name, _ = _pair_target(second.target)
    member_table = _items_table(second.iter)
    assert isinstance(member_table, ast.Name) and member_table.id == properties_name, (
        "property keys must come from the current member, not another table"
    )
    return {
        _prefix_key(key, {
            configuration_name: _metadata_string(table_tree, configuration),
            property_name: name,
        })
        for configuration, properties in zip(table.keys, table.values, strict=True)
        for name in _property_keys(table_tree, properties)
    }


def _metadata_strings(
    tree: ast.Module,
    value: ast.expr,
    sequences: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    if isinstance(value, ast.Name) and value.id in sequences:
        return sequences[value.id]
    tree, value = _metadata(tree, value)
    if isinstance(value, (ast.Tuple, ast.List)):
        strings = []
        for element in value.elts:
            if isinstance(element, ast.Starred):
                expanded_tree, expanded = _metadata(tree, element.value)
                assert isinstance(expanded, (ast.Tuple, ast.List)), (
                    f"metadata expansion is not a literal sequence: "
                    f"{ast.unparse(element.value)}"
                )
                strings.extend(
                    _metadata_string(expanded_tree, item) for item in expanded.elts
                )
            else:
                strings.append(_metadata_string(tree, element))
        return tuple(strings)
    assert (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "tuple"
        and len(value.args) == 1
        and not value.keywords
        and isinstance(value.args[0], ast.GeneratorExp)
    ), f"unsupported property sequence: {ast.unparse(value)}"
    generator = value.args[0]
    return tuple(_prefix_keys(tree, generator.elt, generator.generators, sequences))


def _property_keys(tree: ast.Module, value: ast.expr) -> set[str]:
    tree, value = _metadata(tree, value)
    if isinstance(value, ast.Dict):
        keys = set()
        for key, extra in zip(value.keys, value.values, strict=True):
            if key is None:
                keys |= _property_keys(tree, extra)
            else:
                keys.add(_metadata_string(tree, key))
        return keys
    assert isinstance(value, ast.DictComp), (
        f"unsupported stamped property mapping: {ast.unparse(value)}"
    )
    return _prefix_keys(tree, value.key, value.generators, {})


def _variant_sequences(tree: ast.Module, call: ast.Call) -> dict[str, tuple[str, ...]]:
    arguments = [keyword.value for keyword in call.keywords if keyword.arg == "variants"]
    assert len(arguments) == 1, "configured drawing must name its variants"
    _, value = _metadata(tree, arguments[0])
    variants = ast.literal_eval(value)
    assert isinstance(variants, tuple) and variants
    assert all(
        isinstance(variant, tuple)
        and len(variant) == 2
        and all(isinstance(item, str) and item for item in variant)
        for variant in variants
    )
    helper = _tree(SCRIPTS / "_purchased_variant_drawing.py")
    _, projection = _metadata(helper, ast.Name(id="configurations", ctx=ast.Load()))
    assert (
        isinstance(projection, ast.Call)
        and isinstance(projection.func, ast.Name)
        and projection.func.id == "tuple"
        and len(projection.args) == 1
        and not projection.keywords
        and isinstance(projection.args[0], ast.GeneratorExp)
    ), "unsupported helper configuration projection"
    generator = projection.args[0]
    assert len(generator.generators) == 1
    loop = generator.generators[0]
    configuration, _ = _pair_target(loop.target)
    assert (
        isinstance(generator.elt, ast.Name)
        and generator.elt.id == configuration
        and isinstance(loop.iter, ast.Name)
        and loop.iter.id == "variants"
        and not loop.ifs
        and not loop.is_async
    ), "helper configurations must be projected from its variants argument"
    configurations = tuple(variant[0] for variant in variants)
    assert len(configurations) == len(set(configurations))
    return {"configurations": configurations}


def _read_required(
    tree: ast.Module, sequences: dict[str, tuple[str, ...]]
) -> set[str]:
    assigned = {
        target.id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    required = set()
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", getattr(node.func, "attr", "")) != "read_required_properties":
            continue
        for keyword in node.keywords:
            if keyword.arg != "required":
                continue
            found = True
            value = keyword.value
            if isinstance(value, ast.Name):
                if value.id not in assigned:
                    required.update(_metadata_strings(tree, value, sequences))
                    continue
                value = assigned[value.id]
            assert isinstance(value, (ast.Tuple, ast.List)), "unsupported required properties"
            for element in value.elts:
                if isinstance(element, ast.Starred):
                    required.update(_metadata_strings(tree, element.value, sequences))
                elif isinstance(element, ast.Name):
                    required.add(_imported_string(tree, element.id))
                else:
                    name = ast.literal_eval(element)
                    assert isinstance(name, str)
                    required.add(name)
    assert found and required, "no required property set found"
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
    if "build_purchased_variant_drawing" in imported:
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "build_purchased_variant_drawing"
        ]
        assert len(calls) == 1, f"{draw.name}: expected one configured drawing call"
        return _read_required(
            _tree(SCRIPTS / "_purchased_variant_drawing.py"),
            _variant_sequences(tree, calls[0]),
        )
    if "build_supplier_spring_drawing" in imported:
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "build_supplier_spring_drawing"
        ]
        assert len(calls) == 1, f"{draw.name}: expected one supplier diagram call"
        metadata = [
            keyword.value
            for keyword in calls[0].keywords
            if keyword.arg == "spring_metadata"
        ]
        assert len(metadata) <= 1
        spring_metadata = False
        if metadata:
            assert isinstance(metadata[0], ast.Constant) and isinstance(
                metadata[0].value, bool
            ), f"{draw.name}: supplier metadata selection is not a literal boolean"
            spring_metadata = metadata[0].value
        helper = _tree(SCRIPTS / "_supplier_spring_drawing.py")
        consuming = [
            node
            for node in ast.walk(helper)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "spring_metadata"
        ]
        assert len(consuming) == 1, "supplier diagram metadata branch is missing"
        return _read_required(
            ast.Module(
                body=[
                    node
                    for node in helper.body
                    if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign))
                ]
                + (consuming[0].body if spring_metadata else consuming[0].orelse),
                type_ignores=[],
            ),
            {},
        )
    if "build_purchased_fastener_drawing" in imported:
        return set(purchased._PROPERTIES)
    if "build_purchased_spring_drawing" in imported:
        return set(purchased._PROPERTIES) | _SPRING_EXTRA
    # The non-fastener purchased builder reads the spring builder's set.
    if "build_purchased_part_drawing" in imported:
        return set(purchased._PROPERTIES) | _SPRING_EXTRA
    return _read_required(tree, {})


@pytest.mark.parametrize("spring_metadata", (False, True))
def test_supplier_requirements_follow_the_actual_consuming_branch(
    tmp_path, spring_metadata
) -> None:
    drawing = tmp_path / "draw_supplier.py"
    drawing.write_text(
        "from _supplier_spring_drawing import build_supplier_spring_drawing\n"
        "async def build(adapter):\n"
        "    await build_supplier_spring_drawing("
        f"adapter, spring_metadata={spring_metadata!r})\n",
        encoding="utf-8",
    )
    expected = set(purchased._PROPERTIES)
    if spring_metadata:
        expected |= _SPRING_EXTRA
    assert _required(drawing) == expected


def test_unknown_supplier_metadata_selection_fails_closed(tmp_path) -> None:
    drawing = tmp_path / "draw_supplier.py"
    drawing.write_text(
        "from _supplier_spring_drawing import build_supplier_spring_drawing\n"
        "async def build(adapter):\n"
        "    await build_supplier_spring_drawing(adapter, spring_metadata=choose())\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="literal"):
        _required(drawing)


def _build_sources(build: Path) -> list[Path]:
    """The producer and its direct local imports, without executing or recursing."""
    sources = [build]
    for node in ast.walk(_tree(build)):
        if isinstance(node, ast.ImportFrom):
            modules = (node.module,) if node.module else ()
        elif isinstance(node, ast.Import):
            modules = tuple(alias.name for alias in node.names)
        else:
            continue
        for module_name in modules:
            if module_name == "_drawing_marks":
                continue
            module = SCRIPTS / f"{module_name.replace('.', '/')}.py"
            if module.is_file():
                sources.append(module)
    return sources


@functools.lru_cache(maxsize=None)
def _source_strings_and_marks(text: str) -> tuple[frozenset[str], bool]:
    """Every string literal in ``text``, and whether it calls the mark stamper.

    Keyed by content: the shared helpers that most producers import are
    parsed once per session instead of once per drawing, and only these small
    facts are kept, never the trees."""
    tree = ast.parse(text)
    strings = frozenset(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )
    return strings, "apply_drawing_properties" in _call_names(tree)


def _configured_stamped(tree: ast.Module) -> set[str]:
    """Count document extras only where they reach the stamping helper."""
    stamped = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "apply_drawing_properties"
        ):
            continue
        extras = list(node.args[2:])
        extras.extend(keyword.value for keyword in node.keywords if keyword.arg == "extra")
        assert len(extras) <= 1, "ambiguous drawing-property extras"
        if extras:
            stamped |= _property_keys(tree, extras[0])
    return stamped


def _stamped(stem: str, build: Path) -> tuple[set[str], bool]:
    stamped = set(part_properties(stem))
    build_tree = _tree(build)
    configured = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "_purchased_part_variants"
        for node in build_tree.body
    )
    prefixes = ()
    if configured:
        configurations = _metadata_strings(
            build_tree, ast.Name(id="CONFIGURATIONS", ctx=ast.Load()), {}
        )
        assert configurations, f"{build.name}: no configured members inspected"
        prefixes = tuple(f"{configuration} " for configuration in configurations)
    marks = False
    for source in _build_sources(build):
        strings, calls_marks = _source_strings_and_marks(
            source.read_text(encoding="utf-8")
        )
        stamped |= strings
        marks = marks or calls_marks
    if marks:
        stamped |= _DRAWING_MARK_KEYS
    if configured:
        # Neither a saved-state guard nor an unused literal is a producer.
        stamped = {key for key in stamped if not key.startswith(prefixes)}
        stamped |= _configured_stamped(build_tree)
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


@pytest.mark.parametrize("stamp_notes", (False, True))
def test_configured_notes_must_reach_the_stamping_call(
    tmp_path, monkeypatch, stamp_notes
) -> None:
    # Purchased reference sheets no longer consume per-member notes. Exercise
    # the producer contract independently of which sheets currently need them.
    build = tmp_path / "build_configured.py"
    build.write_text(
        "from _purchased_part_variants import save_member_part\n"
        'CONFIGURATIONS = ("First", "Second")\n'
        'notes = {f"{name} Notes": "note" for name in CONFIGURATIONS}\n'
        'SAVED_PROPERTIES = ("First Notes", "Second Notes")\n'
        f"apply_drawing_properties(adapter, stem, {'notes' if stamp_notes else '{}'})\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(globals(), "part_properties", lambda stem: {})
    stamped, _ = _stamped("configured", build)
    configured_notes = {"First Notes", "Second Notes"}
    assert stamped & configured_notes == (configured_notes if stamp_notes else set())


def test_unsupported_configured_property_comprehension_fails_closed() -> None:
    tree = ast.parse(
        'CONFIGURATIONS = ("First", "Second")\n'
        'notes = {f"{name} Notes": "note" for name in CONFIGURATIONS if name}\n'
    )
    with pytest.raises(AssertionError):
        _property_keys(tree, ast.Name(id="notes", ctx=ast.Load()))


@pytest.mark.parametrize(
    "source",
    (
        'PROPERTIES = ("Number", *MISSING_PROPERTIES)\n',
        'PROPERTIES = ("Number", *make_properties())\n',
        'PROPERTIES = ("Number", *PROPERTIES)\n',
    ),
    ids=("unresolved", "dynamic", "cyclic"),
)
def test_property_sequence_expansion_fails_closed(source: str) -> None:
    tree = ast.parse(source)
    with pytest.raises(AssertionError):
        _metadata_strings(tree, ast.Name(id="PROPERTIES", ctx=ast.Load()), {})


@pytest.mark.parametrize(
    ("source", "included"),
    (
        ("from stock import PROPERTIES\n", True),
        ("import stock\n", True),
        ("import stock as supplier_metadata\n", True),
        ("import absent_module, stock\n", True),
        ("import metadata.stock as supplier_metadata\n", True),
        ("pass\n", False),
        ("import bridge\n", False),
        ("import external_stock\n", False),
        ("import _drawing_marks\n", False),
        ("from _drawing_marks import PROPERTIES\n", False),
    ),
    ids=(
        "from-import",
        "plain-import",
        "aliased-import",
        "multiple-imports",
        "dotted-import",
        "unimported",
        "transitive",
        "outside-repo",
        "drawing-marks-import",
        "drawing-marks-from-import",
    ),
)
def test_stock_metadata_uses_only_direct_repo_local_imports(
    source: str, included: bool, tmp_path: Path, monkeypatch
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "metadata").mkdir()
    metadata = (
        'raise RuntimeError("metadata must only be parsed")\n'
        'PROPERTIES = {"Stock Name": "stock", "Supplier": "catalog", '
        '"Supplier SKUs": "sku"}\n'
    )
    for path in (
        scripts / "stock.py",
        scripts / "metadata" / "stock.py",
        scripts / "_drawing_marks.py",
        tmp_path / "external_stock.py",
    ):
        path.write_text(metadata, encoding="utf-8")
    (scripts / "bridge.py").write_text("import stock\n", encoding="utf-8")
    build = scripts / "build_fixture.py"
    build.write_text(source, encoding="utf-8")
    monkeypatch.setitem(globals(), "SCRIPTS", scripts)
    monkeypatch.setitem(globals(), "part_properties", lambda _stem: {})

    stamped, _ = _stamped("fixture", build)
    required = {"Stock Name", "Supplier", "Supplier SKUs"}
    assert required & stamped == (required if included else set())
