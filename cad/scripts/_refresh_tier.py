"""Which incremental tier can bring a saved assembly up to its current inputs.

``dodo.build_or_refresh`` records, beside every successful ``.SLDASM``, the
digest of each input its cache key folds (the recipe files plus every referenced
artefact and execution token). The next run compares that ledger with the
current digests and picks the cheapest tier that provably reproduces a FULL
build:

* ``PARTS``   -- only referenced parts/subassemblies changed: reopen and reload
  (``_assembly.refresh_assembly``);
* ``EXPLODE`` -- only the assembly's explode closure changed: reopen, delete the
  named explodes and re-author them with the builder's own function
  (``_explode_refresh.refresh_explode``);
* ``FULL``    -- anything else: insert and mate from scratch.

The explode closure is decided statically from the builder's source. It is the
``_<stem>_explode`` module plus its own local imports, minus everything the
rest of the builder reaches without it. An assembly qualifies only when the
builder's sole use of that module is the canonical
``author_in_drawing_configurations(adapter, ASM_NAME, lambda configuration:
<fn>(adapter, configuration))`` call: an explode that takes other build-time
state (``dt_drive_train``'s collar-pin roles) or lives inline in the builder is
entangled with the build and always declines to FULL.

Kept outside every builder's import closure: dodo.py and refresh_assembly.py
are its only importers, so editing it re-keys no artefact.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from _buildgraph import (
    POST_ASSEMBLY,
    _direct_local_imports,
    _local_modules,
    _resolved,
    read_source,
    script_for,
)

AUTHOR_CALL = "author_in_drawing_configurations"
# How many changed inputs a decision's reason names before eliding the rest.
_REASON_PATHS = 4


class RefreshTier(Enum):
    """The incremental tier that brings an assembly to its current inputs.

    The values are also refresh_assembly.py's tier argument."""

    PARTS = "parts"
    EXPLODE = "explode"
    FULL = "full"


@dataclass(frozen=True)
class ExplodePlan:
    """How an assembly's named explodes can be re-authored in place.

    ``closure`` holds the resolved paths only the explode reaches; it is empty,
    with ``decline`` saying why, when the assembly cannot take the EXPLODE tier."""

    module: str = ""
    function: str = ""
    closure: frozenset[str] = frozenset()
    decline: str = ""


class _Entangled(Exception):
    """The builder uses its explode module outside the canonical authoring call."""


def _reachable(seeds: frozenset[str], excluded: str) -> frozenset[str]:
    """Local modules transitively imported from ``seeds``, never entering
    ``excluded`` (it is still reported when something reaches it). Same edges as
    ``_buildgraph._module_closure``, so the difference below is exact."""
    modules = _local_modules()
    found: set[str] = set()
    frontier = set(seeds)
    while frontier:
        module = frontier.pop()
        if module in found:
            continue
        found.add(module)
        if module == excluded:
            continue
        frontier |= set(_direct_local_imports(_resolved(modules[module]))) - found
    return frozenset(found)


def _imported_names(tree: ast.Module, module: str) -> dict[str, str]:
    """Local binding -> exported name for every ``from <module> import ...``."""
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == module for a in node.names):
            raise _Entangled(f"imports the {module} module object")
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == module
        ):
            for alias in node.names:
                if alias.name == "*":
                    raise _Entangled(f"star-imports {module}")
                names[alias.asname or alias.name] = alias.name
    if not names:
        raise _Entangled(f"imports nothing from {module}")
    return names


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _canonical_author(
    call: ast.Call, imported: Mapping[str, str]
) -> tuple[ast.Lambda, str] | None:
    """The authoring lambda and the binding it calls when ``call`` is
    ``author_in_drawing_configurations(<adapter>, <name>, lambda c: f(<adapter>, c))``
    with ``f`` from the explode module; None for any other call."""
    if _call_name(call) != AUTHOR_CALL or call.keywords or len(call.args) != 3:
        return None
    adapter, _name, author = call.args
    if not isinstance(adapter, ast.Name) or not isinstance(author, ast.Lambda):
        return None
    params = author.args
    if (
        len(params.args) != 1
        or params.posonlyargs
        or params.kwonlyargs
        or params.vararg
        or params.kwarg
        or params.defaults
    ):
        return None
    body = author.body
    if not isinstance(body, ast.Call) or body.keywords or len(body.args) != 2:
        return None
    if not isinstance(body.func, ast.Name) or body.func.id not in imported:
        return None
    first, second = body.args
    if not isinstance(first, ast.Name) or first.id != adapter.id:
        return None
    if not isinstance(second, ast.Name) or second.id != params.args[0].arg:
        return None
    return author, body.func.id


def _author_function(source: str, module: str) -> str:
    """The explode module's function the builder authors through, or raise
    ``_Entangled`` naming the use that ties the explode to the rest of the build."""
    tree = ast.parse(source)
    imported = _imported_names(tree, module)
    authors = [
        found
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (found := _canonical_author(node, imported)) is not None
    ]
    if len(authors) != 1:
        raise _Entangled(
            f"needs exactly one {AUTHOR_CALL}(adapter, name, lambda configuration: "
            f"<explode>(adapter, configuration)) call, found {len(authors)}"
        )
    ((author, binding),) = authors
    inside = {id(node) for node in ast.walk(author)}
    stray = sorted(
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in imported and id(node) not in inside
    )
    if stray:
        raise _Entangled(f"uses {', '.join(stray)} outside the explode authoring call")
    return imported[binding]


def explode_plan(stem: str) -> ExplodePlan:
    """The EXPLODE-tier plan for assembly ``stem`` (see the module docstring)."""
    module = f"_{stem}_explode"
    modules = _local_modules()
    if module not in modules:
        return ExplodePlan(decline=f"no {module}.py explode module")
    if POST_ASSEMBLY.get(stem):
        return ExplodePlan(decline="post-assembly hooks author after the build")
    script = _resolved(script_for(stem))
    direct = _direct_local_imports(script)
    if module not in direct:
        return ExplodePlan(decline=f"{script.name} does not import {module}")
    try:
        function = _author_function(read_source(script), module)
    except _Entangled as entangled:
        return ExplodePlan(decline=f"{script.name} {entangled}")
    rest = _reachable(direct - {module}, module)
    if module in rest:
        return ExplodePlan(
            decline=f"{module} is also imported by the builder's other helpers"
        )
    own = _reachable(frozenset({module}), "") - rest
    builder = _resolved(script)
    closure = frozenset(
        str(path) for path in (_resolved(modules[m]) for m in own) if path != builder
    )
    return ExplodePlan(module=module, function=function, closure=closure)


def _named(paths: set[str]) -> str:
    shown = sorted(paths)[:_REASON_PATHS]
    more = len(paths) - len(shown)
    return ", ".join(shown) + (f" (+{more} more)" if more else "")


def classify_refresh(
    recorded: Mapping[str, str] | None,
    current: Mapping[str, str],
    recipe: frozenset[str],
    explode: frozenset[str],
) -> tuple[RefreshTier, str]:
    """The tier that brings a saved assembly built from ``recorded`` up to
    ``current`` (both ``input -> digest``), and why.

    ``recipe`` names the current inputs that are build instructions (scripts,
    helper modules, config); every other input is a referenced artefact or its
    execution token. ``explode`` is the part of ``recipe`` only the assembly's
    explode reaches (empty when it does not qualify). ``recorded`` is None when
    there is no saved assembly or no ledger for it."""
    if recorded is None:
        return RefreshTier.FULL, "no recorded build inputs"
    changed = {
        path
        for path in current.keys() | recorded.keys()
        if current.get(path) != recorded.get(path)
    }
    references = current.keys() - recipe
    # A path the current inputs no longer list counts as a recipe change outside
    # the explode closure.
    changed_recipe = changed - references
    if not changed_recipe:
        if not changed:
            return RefreshTier.PARTS, "no build input changed"
        return RefreshTier.PARTS, f"referenced artefact changed: {_named(changed)}"
    outside = changed_recipe - (explode & recipe)
    if outside:
        return RefreshTier.FULL, f"recipe changed: {_named(outside)}"
    changed_references = changed & references
    if changed_references:
        return RefreshTier.FULL, (
            f"explode and referenced artefacts changed: {_named(changed_references)}"
        )
    return RefreshTier.EXPLODE, f"only the explode changed: {_named(changed_recipe)}"
