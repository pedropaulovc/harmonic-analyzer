"""Cheap recipe/SDK binding contracts; no recipe, SDK or COM imports.

The published 4e9a4df11f3067a0c107d42d295622b2abf3c4dc native run reached
``create_extrude`` in both recipes, but PyWin32Adapter has no such method.
Census every direct adapter call against its actual source-derived MRO, then
pin the blank boss and finite-gap cut semantics. These are offline contracts,
not evidence that the final-source native geometry or readback passes.
"""

from __future__ import annotations

import ast
import copy
import inspect
from functools import cache
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parent
SDK = SCRIPTS.parents[1] / "SolidworksMCP-python" / "src" / "solidworks_mcp"
ADAPTER = SDK / "adapters" / "pywin32_adapter.py"
RECIPES = (
    "build_pd_transgear_knob_shaft.py",
    "build_pd_transgear_feed_pinion.py",
)
ClassRef = tuple[Path, str]
Function = ast.FunctionDef | ast.AsyncFunctionDef


@cache
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@cache
def _resolve_class(path: Path, name: str) -> ClassRef | None:
    """Follow actual imports/re-exports; never infer a mixin from its name."""
    for node in _tree(path).body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return path, name
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            if (alias.asname or alias.name) != name:
                continue
            if node.module == "abc" and alias.name == "ABC":
                # The declared stdlib ABC terminus contributes no adapter API.
                return None
            assert node.level, f"Unresolved external SDK base: {path}:{name}"
            directory = path.parent
            for _ in range(node.level - 1):
                directory = directory.parent
            target = directory.joinpath(*(node.module or "").split("."))
            module = target.with_suffix(".py")
            if not module.is_file():
                module = target / "__init__.py"
            assert module.is_file(), f"Missing SDK import source: {module}"
            return _resolve_class(module, alias.name)
    raise AssertionError(f"SDK class/import not declared: {path}:{name}")


@cache
def _class(ref: ClassRef) -> ast.ClassDef:
    path, name = ref
    return next(
        node for node in _tree(path).body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


@cache
def _mro(ref: ClassRef) -> tuple[ClassRef, ...]:
    """C3 source linearization, including the adapter's declared mixin order."""
    bases = []
    for base in _class(ref).bases:
        assert isinstance(base, ast.Name), f"Unsupported SDK base: {ast.unparse(base)}"
        resolved = _resolve_class(ref[0], base.id)
        if resolved is not None:
            bases.append(resolved)
    pending = [list(_mro(base)) for base in bases] + [list(bases)]
    result = [ref]
    while pending := [items for items in pending if items]:
        candidate = next(
            (items[0] for items in pending
             if all(items[0] not in other[1:] for other in pending)),
            None,
        )
        assert candidate is not None, f"Inconsistent SDK MRO: {ref}"
        result.append(candidate)
        for items in pending:
            if items[0] == candidate:
                items.pop(0)
    return tuple(result)


@cache
def _adapter_methods() -> dict[str, tuple[Path, Function]]:
    ref = _resolve_class(ADAPTER, "PyWin32Adapter")
    assert ref is not None
    methods = {}
    seen = set()
    for owner in _mro(ref):
        for node in _class(owner).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in seen:
                    continue
                seen.add(node.name)
                decorators = {ast.unparse(item) for item in node.decorator_list}
                if not decorators & {"abstractmethod", "property"}:
                    methods[node.name] = owner[0], node
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                seen.add(node.target.id)
            elif isinstance(node, ast.Assign):
                seen.update(target.id for target in node.targets if isinstance(target, ast.Name))
    assert methods, "No concrete adapter methods were discovered"
    return methods


def _adapter_calls(tree: ast.AST) -> list[ast.Call]:
    return sorted(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.Call)
         and isinstance(node.func, ast.Attribute)
         and isinstance(node.func.value, ast.Name)
         and node.func.value.id == "adapter"),
        key=lambda node: (node.lineno, node.col_offset),
    )


def _missing(tree: ast.AST) -> set[str]:
    return {call.func.attr for call in _adapter_calls(tree)} - _adapter_methods().keys()


def _signature(method: Function) -> inspect.Signature:
    """Bind symbolic AST arguments; never execute annotations or defaults."""
    args = method.args
    positional = args.posonlyargs + args.args
    defaults = [inspect.Parameter.empty] * (len(positional) - len(args.defaults)) + args.defaults
    parameters = [
        inspect.Parameter(
            arg.arg,
            inspect.Parameter.POSITIONAL_ONLY if index < len(args.posonlyargs)
            else inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=default,
        )
        for index, (arg, default) in enumerate(zip(positional, defaults))
    ]
    if args.vararg:
        parameters.append(inspect.Parameter(args.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
    parameters.extend(
        inspect.Parameter(
            arg.arg, inspect.Parameter.KEYWORD_ONLY,
            default=default if default is not None else inspect.Parameter.empty,
        )
        for arg, default in zip(args.kwonlyargs, args.kw_defaults)
    )
    if args.kwarg:
        parameters.append(inspect.Parameter(args.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
    return inspect.Signature(parameters)


@pytest.mark.parametrize("recipe", RECIPES)
def test_every_direct_adapter_call_exists_and_binds_on_the_actual_sdk(recipe: str) -> None:
    tree = _tree(SCRIPTS / recipe)
    calls = _adapter_calls(tree)
    assert calls, f"{recipe}: empty adapter-call census"
    # Positive controls for both the whole-file scanner and inherited lookup.
    assert {"create_part", "create_sketch", "exit_sketch", "create_extrusion", "create_cut_extrude"} <= {
        call.func.attr for call in calls
    }
    assert not _missing(tree), f"{recipe}: undeclared adapter calls: {sorted(_missing(tree))}"
    for call in calls:
        path, method = _adapter_methods()[call.func.attr]
        assert not any(isinstance(arg, ast.Starred) for arg in call.args)
        assert all(keyword.arg is not None for keyword in call.keywords)
        receiver = [] if any(
            isinstance(item, ast.Name) and item.id == "staticmethod"
            for item in method.decorator_list
        ) else [call.func.value]
        try:
            _signature(method).bind(
                *receiver, *call.args,
                **{keyword.arg: keyword.value for keyword in call.keywords},
            )
        except TypeError as error:
            pytest.fail(f"{recipe}:{call.lineno}: {call.func.attr} cannot bind {path}:{method.lineno}: {error}")


@pytest.mark.parametrize("recipe", RECIPES)
def test_census_rejects_the_observed_bad_binding_without_running_a_recipe(recipe: str) -> None:
    tree = copy.deepcopy(_tree(SCRIPTS / recipe))
    bosses = [call for call in _adapter_calls(tree) if call.func.attr == "create_extrusion"]
    assert len(bosses) == 1
    bosses[0].func.attr = "create_extrude"
    assert _missing(tree) == {"create_extrude"}


@pytest.mark.parametrize("recipe", RECIPES)
def test_straight_stock_pass_keeps_blind_boss_cut_direction_and_native_guards(recipe: str) -> None:
    straight = next(
        node for node in _tree(SCRIPTS / recipe).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_straight_stock_gaps"
    )
    operations = [call for call in _adapter_calls(straight) if call.func.attr.startswith("create_")]
    extrusions = [call for call in operations if call.func.attr in {"create_extrusion", "create_cut_extrude"}]
    assert [call.func.attr for call in extrusions] == ["create_extrusion", "create_cut_extrude"]
    parameter_class = _resolve_class(SDK / "adapters" / "base.py", "ExtrusionParameters")
    assert parameter_class is not None
    fields = {
        node.target.id: node.value for node in _class(parameter_class).body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    defaults = {name: value for name, value in fields.items() if value is not None}
    for call, depth in zip(extrusions, ("FACE_WIDTH", "FULL_DEPTH")):
        assert len(call.args) == 1 and not call.keywords
        params = call.args[0]
        assert isinstance(params, ast.Call) and isinstance(params.func, ast.Name)
        assert params.func.id == "ExtrusionParameters" and not params.args
        supplied = {keyword.arg: keyword.value for keyword in params.keywords}
        assert supplied.keys() <= fields.keys()
        assert ast.unparse(supplied["depth"]) == depth
        effective = defaults | supplied
        for flag, expected in {
            "end_condition": "Blind", "reverse_direction": False,
            "both_directions": False, "thin_feature": False,
            "merge_result": True, "start_offset": 0.0,
        }.items():
            assert ast.literal_eval(effective[flag]) == expected, (recipe, call.func.attr, flag)
        parents = {id(child): node for node in ast.walk(straight) for child in ast.iter_child_nodes(node)}
        awaited = parents[id(call)]
        assert isinstance(awaited, ast.Await)
        checked = parents[id(awaited)]
        assert isinstance(checked, ast.Call) and isinstance(checked.func, ast.Name)
        assert checked.func.id == "check" and checked.args[1] is awaited

    calls = [node for node in ast.walk(straight) if isinstance(node, ast.Call)]
    defined = sorted(node.lineno for node in calls if isinstance(node.func, ast.Name) and node.func.id == "ensure_fully_defined")
    exited = [node.lineno for node in _adapter_calls(straight) if node.func.attr == "exit_sketch"]
    native = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "cut_order_native_segments"]
    assert len(defined) == len(exited) == 2 and len(native) == 1
    boss, cut = extrusions
    assert defined[0] < exited[0] < boss.lineno < native[0].lineno < defined[1] < exited[1] < cut.lineno
    volumes = sorted(
        node.lineno for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id in {"_native_volume_check", "check_one_solid_body_volume"}
    )
    assert len(volumes) == 3
    assert boss.lineno < volumes[0] < native[0].lineno
    pattern = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id in {"pattern_stock_feature", "pattern_about_z"}]
    assert len(pattern) == 1
    assert cut.lineno < volumes[1] < pattern[0].lineno < volumes[2]


def test_extrusion_binding_is_concrete_native_boss_and_cut_delegation() -> None:
    for name, native_name in (("create_extrusion", "FeatureExtrusion3"), ("create_cut_extrude", "FeatureCut4")):
        path, method = _adapter_methods()[name]
        assert isinstance(method, ast.AsyncFunctionDef)
        assert [arg.arg for arg in method.args.args] == ["self", "params"]
        assert ast.unparse(method.args.args[1].annotation) == "ExtrusionParameters"
        assert ast.unparse(method.returns) == "AdapterResult[SolidWorksFeature]"
        assert len(method.body) == 1 and isinstance(method.body[0], ast.Return)
        delegated = method.body[0].value
        assert isinstance(delegated, ast.Call) and isinstance(delegated.func, ast.Name)
        assert [ast.unparse(arg) for arg in delegated.args] == ["self", "params"]
        implementation = next(
            node for node in _tree(path).body
            if isinstance(node, ast.FunctionDef) and node.name == delegated.func.id
        )
        native = [
            node for node in ast.walk(implementation)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == native_name
        ]
        assert native, f"{path}:{implementation.name} never calls {native_name}"
        for call in native:
            assert ast.unparse(call.args[2]) == "normalized.reverse_direction"
        if name == "create_extrusion":
            assert len(native) == 1 and len(native[0].args) == 23
            call = native[0]
            assert [ast.literal_eval(arg) for arg in call.args[:2]] == [True, False]
            assert ast.unparse(call.args[3]) == "t1"
            assert ast.unparse(call.args[5]) == "normalized.depth / 1000.0"
            assert ast.unparse(call.args[17]) == "normalized.merge_result"
            conditions = [
                node.value for node in ast.walk(implementation)
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "t1" for target in node.targets)
            ]
            assert conditions
            for condition in conditions:
                assert isinstance(condition, ast.IfExp)
                assert ast.unparse(condition.test) == "normalized.both_directions"
                assert ast.unparse(condition.body) == "adapter.constants['swEndCondMidPlane']"
                assert ast.unparse(condition.orelse) == "adapter.constants['swEndCondBlind']"
