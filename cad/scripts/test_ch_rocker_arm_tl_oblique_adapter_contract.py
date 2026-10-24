"""Source-only census of the plain-pivot native recipe boundary.

Reuse the transgear test's AST-only SDK/MRO/signature machinery. No native
recipe, SDK, COM or stock discovery module is imported. Fixed tuple expansion
is resolved from source, so projected-coordinate calls bind rather than skip.
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

import test_pd_transgear_adapter_contract as sdk


SCRIPTS = Path(__file__).resolve().parent
RECIPES = (
    "build_ch_rocker_arm_tl_oblique_carrier.py",
    "build_ch_rocker_arm_tl_oblique_pivot_block.py",
    "build_ch_rocker_arm_tl_oblique_feed_block.py",
    "build_ch_rocker_arm_tl_vn_oblique_pivot_screw.py",
    "build_ch_rocker_arm_tl_vn_oblique_pivot_spacer.py",
    "build_ch_rocker_arm_tl_vn_oblique_pivot_shim.py",
    "build_ch_rocker_arm_tl_vn_oblique_hub_pin.py",
    "build_ch_rocker_arm_tl_oblique_jig_assembly.py",
    "build_sh_vn_clamping_kit_hardware.py",
)
HARDWARE_RECIPES = RECIPES[3:7]


def _local_nodes(scope: ast.AST):
    """Walk one lexical scope, retaining but not entering nested definitions."""
    for child in ast.iter_child_nodes(scope):
        yield child
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield from _local_nodes(child)


def _target_values(target: ast.AST, value: ast.AST, name: str) -> list[ast.AST]:
    if isinstance(target, ast.Name):
        return [value] if target.id == name else []
    if isinstance(target, (ast.Tuple, ast.List)):
        if isinstance(value, (ast.Tuple, ast.List)) and len(target.elts) == len(value.elts):
            return [item for left, right in zip(target.elts, value.elts) for item in _target_values(left, right, name)]
        if isinstance(value, ast.GeneratorExp):
            return [item for left in target.elts for item in _target_values(left, value.elt, name)]
    return []


class _Sources:
    """Resolve source literals, lexical aliases, tuple loops and mapper closures.

    This is intentionally not an evaluator. Unsupported dynamic *args fail the
    census rather than guessing a length from the adapter's expected signature.
    """

    def __init__(self, path: Path, tree: ast.Module):
        self.overrides = {path: tree}
        self.parents: dict[Path, dict[ast.AST, ast.AST]] = {}

    def tree(self, path: Path) -> ast.Module:
        return self.overrides[path] if path in self.overrides else sdk._tree(path)

    def scopes(self, path: Path, node: ast.AST) -> list[ast.AST]:
        if path not in self.parents:
            self.parents[path] = {child: parent for parent in ast.walk(self.tree(path)) for child in ast.iter_child_nodes(parent)}
        scopes = []
        current = node
        while current in self.parents[path]:
            current = self.parents[path][current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.Module)):
                scopes.append(current)
        return scopes or [self.tree(path)]

    def module(self, path: Path, module: str) -> Path:
        # Recipe/helper imports are rooted at cad/scripts, SDK resolution remains
        # the existing helper's responsibility. Never import a recipe to resolve it.
        target = SCRIPTS.joinpath(*module.split(".")).with_suffix(".py")
        assert target.is_file(), f"{path.name}: missing static helper source {module}"
        return target

    def lookup(self, path: Path, node: ast.AST, name: str) -> list[tuple[Path, ast.AST]]:
        for scope in self.scopes(path, node):
            found = []
            for item in _local_nodes(scope):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name:
                    found.append((path, item))
                elif isinstance(item, ast.Assign) and item.lineno < getattr(node, "lineno", float("inf")):
                    found.extend((path, value) for target in item.targets for value in _target_values(target, item.value, name))
                elif isinstance(item, ast.AnnAssign) and item.value is not None:
                    found.extend((path, value) for value in _target_values(item.target, item.value, name))
                elif isinstance(item, (ast.For, ast.AsyncFor)) and item.lineno <= getattr(node, "lineno", float("inf")):
                    if isinstance(item.iter, (ast.Tuple, ast.List)):
                        found.extend((path, value) for row in item.iter.elts for value in _target_values(item.target, row, name))
                elif isinstance(item, ast.ImportFrom) and item.module:
                    for alias in item.names:
                        if (alias.asname or alias.name) == name:
                            target = self.module(path, item.module)
                            found.extend(self.export(target, alias.name))
            if found:
                return found
        raise AssertionError(f"{path.name}:{getattr(node, 'lineno', '?')}: unresolved source name {name}")

    def export(self, path: Path, name: str) -> list[tuple[Path, ast.AST]]:
        # Use an unattached symbolic use AFTER all module declarations.
        use = ast.Name(id=name)
        use.lineno = 10**9
        return self.lookup(path, use, name)

    def values(self, path: Path, node: ast.AST) -> list[tuple[Path, ast.AST]]:
        if isinstance(node, ast.Name):
            return self.lookup(path, node, node.id)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            imports = [item for item in self.tree(path).body if isinstance(item, ast.Import)]
            for item in imports:
                for alias in item.names:
                    if (alias.asname or alias.name) == node.value.id:
                        return self.export(self.module(path, alias.name), node.attr)
        return [(path, node)]

    def callable(self, path: Path, node: ast.AST, trail: frozenset = frozenset()) -> list[tuple[Path, ast.AST]]:
        key = (path, id(node), "callable")
        assert key not in trail, f"{path.name}: cyclic callable source"
        trail = trail | {key}
        result = []
        for source, value in self.values(path, node):
            if isinstance(value, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                result.append((source, value))
            elif isinstance(value, ast.Call):
                # A mapper factory returns an actual nested function/lambda.
                for owner, factory in self.callable(source, value.func, trail):
                    returns = [item.value for item in _local_nodes(factory) if isinstance(item, ast.Return) and item.value is not None]
                    assert returns, f"{owner.name}: factory has no source return"
                    for returned in returns:
                        result.extend(self.callable(owner, returned, trail))
            else:
                raise AssertionError(f"{source.name}: unsupported callable source {ast.unparse(value)}")
        assert result
        return result

    def tuple_size(self, path: Path, node: ast.AST, trail: frozenset = frozenset()) -> int:
        key = (path, id(node), "tuple")
        assert key not in trail, f"{path.name}: cyclic tuple source"
        trail = trail | {key}
        if isinstance(node, (ast.Tuple, ast.List)):
            assert not any(isinstance(item, ast.Starred) for item in node.elts)
            return len(node.elts)
        if isinstance(node, (ast.Name, ast.Attribute)):
            sizes = {self.tuple_size(source, value, trail) for source, value in self.values(path, node)}
        elif isinstance(node, ast.Call):
            sizes = set()
            for source, function in self.callable(path, node.func):
                returns = [function.body] if isinstance(function, ast.Lambda) else [item.value for item in _local_nodes(function) if isinstance(item, ast.Return) and item.value is not None]
                assert returns, f"{source.name}: tuple-producing helper has no return"
                sizes.update(self.tuple_size(source, value, trail) for value in returns)
        elif isinstance(node, ast.Subscript):
            sizes = set()
            for source, container in self.values(path, node.value):
                # Follow aliases such as carrier.PIN_HOLES -> trammel.PIN_HOLES.
                if isinstance(container, (ast.Name, ast.Attribute)):
                    containers = self.values(source, container)
                else:
                    containers = [(source, container)]
                for owner, actual in containers:
                    if isinstance(actual, ast.Dict):
                        entries = actual.values
                        if isinstance(node.slice, ast.Constant):
                            entries = [value for key_node, value in zip(actual.keys, actual.values) if isinstance(key_node, ast.Constant) and key_node.value == node.slice.value]
                    elif isinstance(actual, (ast.Tuple, ast.List)) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                        entries = [actual.elts[node.slice.value]]
                    else:
                        raise AssertionError(f"{owner.name}: unsupported tuple container {ast.unparse(actual)}")
                    assert entries, f"{owner.name}: empty tuple-source census"
                    sizes.update(self.tuple_size(owner, entry, trail) for entry in entries)
        else:
            raise AssertionError(f"{path.name}: cannot prove *argument arity from {ast.unparse(node)}")
        assert len(sizes) == 1, f"{path.name}: inconsistent *argument tuple lengths {sizes}"
        return sizes.pop()


def _bind_calls(path: Path, tree: ast.Module) -> list[ast.Call]:
    sources = _Sources(path, tree)
    methods = sdk._adapter_methods()
    calls = sdk._adapter_calls(tree)
    missing = {call.func.attr for call in calls} - methods.keys()
    assert not missing, f"{path.name}: undeclared adapter calls {sorted(missing)}"
    for call in calls:
        owner, method = methods[call.func.attr]
        args = []
        for arg in call.args:
            if isinstance(arg, ast.Starred):
                args.extend([arg.value] * sources.tuple_size(path, arg.value))
            else:
                args.append(arg)
        assert all(keyword.arg is not None for keyword in call.keywords), f"{path.name}:{call.lineno}: unresolved **kwargs"
        assert len({keyword.arg for keyword in call.keywords}) == len(call.keywords)
        receiver = [] if any(isinstance(item, ast.Name) and item.id == "staticmethod" for item in method.decorator_list) else [call.func.value]
        try:
            sdk._signature(method).bind(*receiver, *args, **{keyword.arg: keyword.value for keyword in call.keywords})
        except TypeError as error:
            raise AssertionError(f"{path.name}:{call.lineno}: {call.func.attr} cannot bind {owner}:{method.lineno}: {error}") from error
    return calls


def _census_units(recipe: str) -> tuple[Path, ...]:
    """Follow actual adapter-forwarding imports through thin entrypoints."""
    units = []
    pending = [SCRIPTS / recipe]
    while pending:
        path = pending.pop()
        if path in units:
            continue
        units.append(path)
        tree = sdk._tree(path)
        native_calls = sdk._adapter_calls(tree)
        imported = {
            alias.asname or alias.name: alias.name
            for node in tree.body if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        delegates = []
        sources = _Sources(path, tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in imported or not node.args:
                continue
            if not isinstance(node.args[0], ast.Name) or node.args[0].id != "adapter":
                continue
            # Follow substantive build authors, not save/property guards:
            # those utilities can touch COM without authoring any geometry.
            if not imported[node.func.id].startswith("build_"):
                continue
            resolved = sources.callable(path, node.func)
            assert resolved, f"{path.name}: unresolved native delegate"
            delegates.extend(source for source, _function in resolved)
        assert native_calls or delegates, f"{path.name}: empty native boundary without a source delegate"
        pending.extend(delegates)
    assert any(sdk._adapter_calls(sdk._tree(path)) for path in units), f"{recipe}: no native calls reached"
    return tuple(units)


@pytest.mark.parametrize("recipe", RECIPES)
def test_all_affected_native_recipe_calls_exist_and_bind_to_initialized_sdk(recipe: str) -> None:
    units = _census_units(recipe)
    total = 0
    for path in units:
        total += len(_bind_calls(path, sdk._tree(path)))
    assert total, f"{recipe}: no adapter methods reached in its source census"


def test_census_covers_every_new_physical_interface() -> None:
    assert len(RECIPES) == len(set(RECIPES)) == 9
    for recipe in RECIPES[1:3]:
        calls = {call.func.attr for path in _census_units(recipe) for call in sdk._adapter_calls(sdk._tree(path))}
        assert {"create_sketch", "create_cut_extrude"} <= calls
    for recipe in HARDWARE_RECIPES:
        calls = {call.func.attr for call in sdk._adapter_calls(sdk._tree(SCRIPTS / recipe))}
        assert {"create_part", "create_sketch", "create_extrusion"} <= calls
    stud = "build_sh_vn_clamping_kit_hardware.py"
    assert _census_units(stud) == (SCRIPTS / stud,)
    helper = SCRIPTS / "_oblique_pivot_block_model.py"
    for recipe in RECIPES[1:3]:
        assert helper in _census_units(recipe)


@pytest.mark.parametrize(
    "recipe, method",
    (
        ("build_ch_rocker_arm_tl_oblique_pivot_block.py", "create_cut_extrude"),
        ("build_sh_vn_clamping_kit_hardware.py", "create_revolve"),
    ),
)
def test_real_direct_method_rename_is_rejected_without_importing_recipe(
    recipe: str, method: str,
) -> None:
    path = next(path for path in _census_units(recipe) if any(
        call.func.attr == method for call in sdk._adapter_calls(sdk._tree(path))
    ))
    tree = copy.deepcopy(sdk._tree(path))
    actual = next(call for call in sdk._adapter_calls(tree) if call.func.attr == method)
    actual.func.attr = "retention_undeclared_method"
    with pytest.raises(AssertionError, match="undeclared adapter calls.*retention_undeclared_method"):
        _bind_calls(path, tree)


@pytest.mark.parametrize(
    "recipe",
    (
        "build_ch_rocker_arm_tl_oblique_pivot_block.py",
        "build_sh_vn_clamping_kit_hardware.py",
    ),
)
def test_actual_call_with_wrong_keyword_is_rejected_by_sdk_signature(recipe: str) -> None:
    path = next(path for path in _census_units(recipe) if any(
        call.func.attr == "create_sketch" for call in sdk._adapter_calls(sdk._tree(path))
    ))
    tree = copy.deepcopy(sdk._tree(path))
    actual = next(call for call in sdk._adapter_calls(tree) if call.func.attr == "create_sketch")
    method = sdk._adapter_methods()[actual.func.attr][1]
    assert method.args.kwarg is None, "mutation needs a concrete SDK signature"
    actual.keywords.append(ast.keyword(arg="retention_wrong_keyword", value=ast.Constant(value=True)))
    with pytest.raises(AssertionError, match="cannot bind.*retention_wrong_keyword"):
        _bind_calls(path, tree)


def test_projected_tuple_arity_mutation_is_not_skipped() -> None:
    path = SCRIPTS / "build_ch_rocker_arm_tl_oblique_jig_assembly.py"
    tree = copy.deepcopy(sdk._tree(path))
    actual = next(call for call in sdk._adapter_calls(tree) if call.func.attr == "add_line" and any(isinstance(arg, ast.Starred) for arg in call.args))
    starred = next(arg for arg in actual.args if isinstance(arg, ast.Starred))
    starred.value = ast.Tuple(elts=[ast.Constant(value=0.0)] * 3, ctx=ast.Load())
    with pytest.raises(AssertionError, match="cannot bind"):
        _bind_calls(path, tree)


def test_actual_stud_call_with_excess_positional_arity_is_rejected() -> None:
    path = SCRIPTS / "build_sh_vn_clamping_kit_hardware.py"
    tree = copy.deepcopy(sdk._tree(path))
    actual = next(call for call in sdk._adapter_calls(tree) if call.func.attr == "create_sketch")
    method = sdk._adapter_methods()[actual.func.attr][1]
    assert method.args.vararg is None, "mutation needs a concrete SDK signature"
    positional = len(method.args.posonlyargs) + len(method.args.args)
    actual.args = [ast.Constant(value=0.0) for _ in range(positional + 1)]
    with pytest.raises(AssertionError, match="cannot bind"):
        _bind_calls(path, tree)
