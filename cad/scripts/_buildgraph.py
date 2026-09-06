r"""Pure build-graph enumeration shared by the doit ``dodo.py`` and the legacy
``build_all.py`` shim.

This module holds only filesystem/string logic -- no SolidWorks, no COM -- so the
part/assembly enumeration and the part->assembly dependency scan are unit-testable
in plain CI. ``references_of`` is the inverse of ``dependents_of``: the former
yields a build script's prerequisites (the DAG edges doit consumes as
``file_dep``), the latter yields a part's downstream assemblies (what the legacy
``--rebuild`` deleted).

Assembly artefact edges come from source-consuming call arguments and manifests,
not occurrences of part names in prose. Unknown source expressions fail loudly.
"""

from __future__ import annotations

import ast
import functools
import re
from enum import Enum
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
CAD_OUT = SCRIPTS_DIR.parent / "out"
CONFIG_DIR = SCRIPTS_DIR.parent / "config"
REFERENCES_DIR = SCRIPTS_DIR.parent / "references"

# Vendored input artefacts (DXF/DWG) a build imports at run time. A build that
# imports one (e.g. build_nameplate -> nameplate-engraving.dxf) must depend on the
# FILE so an edit rebuilds the part and busts its remote-cache key -- see
# data_deps_of, honored by dodo._part_file_deps.
_DATA_EXTENSIONS = (".dxf", ".dwg")
_DATA_LITERAL_RE = re.compile(r"""["']([^"']+\.(?:dxf|dwg))["']""", re.IGNORECASE)

# Sub-assemblies in build order; the top-level harmonic-analyzer references the
# six subs, so it is last. doit derives ordering from file_dep, but this tuple
# still enumerates the assembly tasks. The former monolithic ``output`` is split
# by function into summing -> magnifier -> pen (the value chain) + paper-drive.
ASSEMBLY_ORDER = (
    "frame",
    "drive_train",
    "channel",
    "summing",
    "magnifier",
    "pen",
    "paper_drive",
    "harmonic_analyzer",
)

# Scripts that match build_*.py but produce no .SLDPRT part in the SolidWorks
# queue -- excluded from the part list: motion/diagnostic deliverables that
# consume/probe the saved assemblies (Basic Motion sweeps, mobility probes).
# None builds the machine.
NON_PART_SCRIPTS = frozenset(
    {
        "build_motion_study.py",
        "build_motion_study_springs.py",
        "build_motion_setup_drives.py",
        "build_mobility_probe.py",
        "build_kinematic_probe.py",
    }
)

# Post-assembly hooks: scripts that mutate an already-built assembly IN PLACE (no
# new artefact), run after their base assembly rather than in the part queue.
# Keyed by assembly stem; run in listed order.
#
# Empty: the engagement-CONFIGURATION mutators (cone_disengaged / operating) were
# removed -- every assembly now carries only its Default configuration. Re-add a
# stem -> (script, ...) entry here if a future in-place post-build step is needed.
POST_ASSEMBLY: dict[str, tuple[str, ...]] = {}
_POST_SCRIPT_NAMES = frozenset(s for v in POST_ASSEMBLY.values() for s in v)


def part_scripts() -> list[Path]:
    """Every build_*.py except the assemblies, config hooks, motion/diagnostic
    scripts and the orchestrator."""
    out = []
    for path in sorted(SCRIPTS_DIR.glob("build_*.py")):
        if (
            path.name in NON_PART_SCRIPTS
            or path.name in _POST_SCRIPT_NAMES
            or path.name.endswith("_assembly.py")
        ):
            continue
        out.append(path)
    return out


def part_stems() -> list[str]:
    """Part stems (``build_<stem>.py`` -> ``<stem>``), undashed."""
    return [p.stem.removeprefix("build_") for p in part_scripts()]


def artefact_for(script: Path) -> Path:
    """The .SLDPRT/.SLDASM a build script produces (dashed artefact name)."""
    stem = script.stem.removeprefix("build_")
    if stem.endswith("_assembly"):
        name = stem.removesuffix("_assembly").replace("_", "-")
        return CAD_OUT / "sldasm" / f"{name}.SLDASM"
    return CAD_OUT / "sldprt" / f"{stem.replace('_', '-')}.SLDPRT"


def script_for(stem: str) -> Path:
    """The build script for a part/assembly stem (assemblies get _assembly)."""
    if stem in ASSEMBLY_ORDER:
        return SCRIPTS_DIR / f"build_{stem}_assembly.py"
    return SCRIPTS_DIR / f"build_{stem}.py"


class _AssemblySources:
    """Bounded enumeration of source arguments, not log/error/documentation text.

    Local assignments, literal loop manifests, wrapper parameters and batch part
    fields are supported. Unresolved source expressions fail task discovery; an
    all-assembly fallback could create cycles. Builders are never executed.

    Source sinks must remain in the builder: place_component, its batch form, or
    InsertComponentParameters. Moving a sink into an imported helper requires
    extending this contract and the complete eight-builder insertion manifest
    regression. This is not a general Python/dataflow interpreter.
    """

    def __init__(self, source: str):
        self.tree = ast.parse(source)
        self.scopes: dict[ast.AST, ast.AST] = {}
        self.parents: dict[ast.AST, ast.AST] = {}
        self.nodes: dict[ast.AST, list[ast.AST]] = {}
        self.aliases: dict[str, str] = {}
        self._index(self.tree, self.tree)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                self.aliases.update({a.asname or a.name: a.name for a in node.names})

    def _index(self, node: ast.AST, scope: ast.AST) -> None:
        self.scopes[node] = scope
        self.nodes.setdefault(scope, []).append(node)
        child_scope = (
            node if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else scope
        )
        for child in ast.iter_child_nodes(node):
            self.parents[child] = node
            self._index(child, child_scope)

    def call_name(self, node: ast.Call) -> str:
        name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else getattr(node.func, "attr", "")
        )
        return self.aliases.get(name, name)

    @staticmethod
    def fail(node: ast.AST):
        raise ValueError(
            f"Unresolved assembly source at line {getattr(node, 'lineno', '?')}: "
            f"{ast.unparse(node)}; extend the source-expression contract explicitly"
        )

    @staticmethod
    def argument(call: ast.Call, index: int, keyword: str) -> ast.AST:
        if len(call.args) > index:
            return call.args[index]
        for item in call.keywords:
            if item.arg == keyword:
                return item.value
        return _AssemblySources.fail(call)

    def scope_nodes(self, node: ast.AST) -> list[ast.AST]:
        scope = self.scopes[node]
        if scope is self.tree:
            return self.nodes[scope]
        return [*self.nodes[scope], *self.nodes[self.tree]]

    def bindings(self, node: ast.Name, trail: frozenset[ast.AST]) -> list[ast.AST]:
        found = []
        scope = self.scopes[node]
        for item in self.scope_nodes(node):
            late_global = scope is not self.tree and self.scopes[item] is self.tree
            if not late_global and (
                getattr(item, "lineno", 0),
                getattr(item, "col_offset", 0),
            ) >= (node.lineno, node.col_offset):
                continue
            if (
                isinstance(item, ast.AugAssign)
                and isinstance(item.target, ast.Name)
                and item.target.id == node.id
            ):
                self.fail(item)
            targets = (
                item.targets
                if isinstance(item, ast.Assign)
                else ([item.target] if isinstance(item, ast.AnnAssign) else [])
            )
            for target in targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == node.id
                    and item.value is not None
                ):
                    found.append(item.value)
            if (
                isinstance(item, ast.NamedExpr)
                and isinstance(item.target, ast.Name)
                and item.target.id == node.id
            ):
                found.append(item.value)
            if not isinstance(item, (ast.For, ast.AsyncFor)):
                continue
            if isinstance(item.target, ast.Name) and item.target.id == node.id:
                found.extend(self.items(item.iter, trail))
            if isinstance(item.target, (ast.Tuple, ast.List)):
                for index, target in enumerate(item.target.elts):
                    if not isinstance(target, ast.Name) or target.id != node.id:
                        continue
                    for row in self.items(item.iter, trail):
                        if not isinstance(row, (ast.Tuple, ast.List)) or index >= len(
                            row.elts
                        ):
                            self.fail(row)
                        found.append(row.elts[index])
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [*scope.args.posonlyargs, *scope.args.args]
            for index, arg in enumerate(args):
                if arg.arg != node.id:
                    continue
                for call in ast.walk(self.tree):
                    if (
                        isinstance(call, ast.Call)
                        and self.call_name(call) == scope.name
                    ):
                        found.append(self.argument(call, index, node.id))
        if not found:
            self.fail(node)
        return found

    def items(self, node: ast.AST, trail: frozenset[ast.AST]) -> list[ast.AST]:
        if node in trail:
            self.fail(node)
        trail = trail | {node}
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return list(node.elts)
        if not isinstance(node, ast.Name):
            return self.fail(node)
        values = [
            item
            for binding in self.bindings(node, trail)
            for item in self.items(binding, trail)
        ]
        for item in self.scope_nodes(node):
            available = getattr(item, "lineno", 0) < node.lineno or (
                self.scopes[node] is not self.tree and self.scopes[item] is self.tree
            )
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == node.id
                        and len(item.targets) != 1
                    ):
                        self.fail(item)
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == node.id
                    ):
                        self.fail(item)
            if (
                isinstance(item, ast.Assign)
                and isinstance(item.value, ast.Name)
                and item.value.id == node.id
                and available
            ):
                self.fail(item)  # mutable collection aliasing is not enumerated
            if (
                isinstance(item, ast.Call)
                and available
                and node not in item.args
                and self.call_name(item) not in {"len", "enumerate"}
                and any(
                    isinstance(arg, ast.Name) and arg.id == node.id for arg in item.args
                )
            ):
                self.fail(item)  # an opaque consumer could mutate the manifest
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and isinstance(item.func.value, ast.Name)
                and item.func.value.id == node.id
                and available
            ):
                if item.func.attr != "append":
                    self.fail(item)
                values.append(self.argument(item, 0, "object"))
        return values

    def validate_row_uses(self, loop: ast.For) -> None:
        """Batch rows may receive non-source metadata, never opaque part edits."""
        row = loop.target.id
        for item in ast.walk(loop):
            if isinstance(item, ast.Assign):
                if isinstance(item.value, ast.Name) and item.value.id == row:
                    self.fail(item)
                for target in item.targets:
                    if (
                        not isinstance(target, ast.Subscript)
                        or not isinstance(target.value, ast.Name)
                        or target.value.id != row
                    ):
                        continue
                    if (
                        not isinstance(target.slice, ast.Constant)
                        or target.slice.value == "part"
                    ):
                        self.fail(item)
            if isinstance(item, ast.Call):
                if any(
                    isinstance(arg, ast.Name) and arg.id == row for arg in item.args
                ):
                    self.fail(item)
                if (
                    isinstance(item.func, ast.Attribute)
                    and isinstance(item.func.value, ast.Name)
                    and item.func.value.id == row
                    and item.func.attr not in {"get", "items"}
                ):
                    self.fail(item)

    def field_writes(
        self, node: ast.AST, owner: ast.AST, key: ast.AST | None
    ) -> list[ast.AST]:
        found = []
        if key is None:
            if not isinstance(owner, ast.Name):
                self.fail(node)
            for initial in self.bindings(owner, frozenset()):
                if not isinstance(initial, ast.Dict) or any(
                    value is None for value in initial.keys
                ):
                    self.fail(initial)
                found.extend(initial.values)
        for item in self.scope_nodes(node):
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and ast.dump(item.func.value) == ast.dump(owner)
                and item.func.attr not in {"get", "items"}
            ):
                self.fail(item)
            if (
                isinstance(item, (ast.AnnAssign, ast.AugAssign))
                and isinstance(item.target, ast.Subscript)
                and ast.dump(item.target.value) == ast.dump(owner)
            ):
                self.fail(item)
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if not isinstance(target, ast.Subscript) or ast.dump(
                    target.value
                ) != ast.dump(owner):
                    continue
                if key is not None and ast.dump(target.slice) != ast.dump(key):
                    continue
                if key is not None and item.lineno >= node.lineno:
                    continue
                found.append(item.value)
        if not found:
            self.fail(node)
        return found

    def strings(
        self, node: ast.AST, trail: frozenset[ast.AST] = frozenset()
    ) -> set[str]:
        if node in trail:
            # A loop's dictionary memo can feed itself. Only an anchored name
            # elsewhere in that cycle permits collection to succeed.
            return set()
        trail = trail | {node}
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, ast.Name):
            return {
                s
                for binding in self.bindings(node, trail)
                for s in self.strings(binding, trail)
            }
        if isinstance(node, ast.IfExp):
            return self.strings(node.body, trail) | self.strings(node.orelse, trail)
        if isinstance(node, ast.JoinedStr):
            prefix = node.values[0] if node.values else None
            if (
                not isinstance(prefix, ast.Constant)
                or not isinstance(prefix.value, str)
                or not prefix.value
            ):
                return self.fail(node)
            return {prefix.value + ("*" if len(node.values) > 1 else "")}
        if isinstance(node, ast.Call) and self.call_name(node) in {
            "_part",
            "_subassembly",
        }:
            self.validate_path_wrapper(node)
            return self.strings(self.argument(node, 0, "name"), trail)
        if isinstance(node, ast.Call) and self.call_name(node) == "part_path":
            return self.strings(self.argument(node, 0, "name"), trail)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
        ):
            values = self.field_writes(node, node.func.value, None)
            defaults = [
                *node.args[1:],
                *(item.value for item in node.keywords if item.arg == "default"),
            ]
            values.extend(
                value
                for value in defaults
                if not isinstance(value, ast.Constant) or value.value is not None
            )
            return {s for value in values for s in self.strings(value, trail)}
        if isinstance(node, ast.Subscript):
            values = self.field_writes(node, node.value, node.slice)
            return {s for value in values for s in self.strings(value, trail)}
        return self.fail(node)

    def validate_path_wrapper(self, call: ast.Call) -> None:
        """Prove the two local path wrappers preserve the supplied stem.

        The existence guard may change without changing source identity; changing
        the path expression/return/parameter requires explicit enumeration work.
        """
        name = self.call_name(call)
        functions = [
            node
            for node in self.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        if len(functions) != 1:
            self.fail(call)
        function = functions[0]
        if len(function.args.args) != 1 or function.args.args[0].arg != "name":
            self.fail(function)
        extension = "SLDPRT" if name == "_part" else "SLDASM"
        expected = ast.parse(
            f'path = (OUT_{extension} / f"{{name}}.{extension}").resolve()'
        ).body[0]
        assignments = [
            node
            for node in ast.walk(function)
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
        ]
        returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
        if len(assignments) != 1 or ast.dump(assignments[0]) != ast.dump(expected):
            self.fail(function)
        if len(returns) != 1 or ast.dump(returns[0]) != ast.dump(
            ast.parse("return str(path)").body[0]
        ):
            self.fail(function)

    def collect(self) -> frozenset[str]:
        expressions = []
        source_calls = {
            "place_component",
            "place_components_batch",
            "InsertComponentParameters",
        }
        for node in ast.walk(self.tree):
            name = node.id if isinstance(node, ast.Name) else getattr(node, "attr", "")
            if self.aliases.get(name, name) not in source_calls or not isinstance(
                getattr(node, "ctx", None), ast.Load
            ):
                continue
            parent = self.parents.get(node)
            if not isinstance(parent, ast.Call) or parent.func is not node:
                self.fail(node)  # do not lose indirect callable aliases
        for call in ast.walk(self.tree):
            if not isinstance(call, ast.Call):
                continue
            name = self.call_name(call)
            if name == "place_component":
                expressions.append(self.argument(call, 1, "part"))
            if name == "InsertComponentParameters":
                expressions.append(self.argument(call, 0, "file_path"))
            if name == "insert_component":
                parameters = self.argument(call, 0, "parameters")
                if (
                    not isinstance(parameters, ast.Call)
                    or self.call_name(parameters) != "InsertComponentParameters"
                ):
                    self.fail(call)
            if name != "place_components_batch":
                continue
            manifest = self.argument(call, 1, "specs")
            if isinstance(manifest, ast.Name):
                for item in self.scope_nodes(manifest):
                    if (
                        isinstance(item, ast.For)
                        and isinstance(item.iter, ast.Name)
                        and item.iter.id == manifest.id
                        and isinstance(item.target, ast.Name)
                    ):
                        self.validate_row_uses(item)
            for item in self.items(manifest, frozenset()):
                if not isinstance(item, ast.Dict) or any(
                    key is None for key in item.keys
                ):
                    self.fail(item)
                fields = [
                    value
                    for key, value in zip(item.keys, item.values)
                    if isinstance(key, ast.Constant) and key.value == "part"
                ]
                if len(fields) != 1:
                    self.fail(item)
                expressions.extend(fields)
        names = set()
        for expression in expressions:
            resolved = self.strings(expression)
            if not resolved:
                self.fail(expression)
            names.update(resolved)
        return frozenset(names)


@functools.lru_cache(maxsize=128)
def _assembly_source_names(source: str) -> frozenset[str]:
    """Reuse syntax by content, never file time or a previously resolved DAG."""
    return _AssemblySources(source).collect()


def references_of(asm_stem: str) -> list[str]:
    """Part + sub-assembly stems this assembly's build script references.

    These are the prerequisite artefacts (the DAG edges): each output sub
    (summing/magnifier/pen/paper_drive) references its leaf parts;
    ``harmonic_analyzer`` references the six sub-assemblies
    (build_harmonic_analyzer_assembly.SUBASSEMBLIES). doit turns each into a
    ``file_dep`` on the referenced ``.SLDPRT``/sub-``.SLDASM`` target, so order
    and the refresh/full decision fall out of the graph.
    """
    candidates = part_stems() + [a for a in ASSEMBLY_ORDER if a != asm_stem]
    by_name = {stem.replace("_", "-"): stem for stem in candidates}
    found = set()
    source = script_for(asm_stem).read_text(encoding="utf-8")
    for name in _assembly_source_names(source):
        name = name.replace("\\", "/").rsplit("/", 1)[-1]
        name = re.sub(r"\.(?:SLDPRT|SLDASM)$", "", name, flags=re.IGNORECASE)
        if name in by_name:
            found.add(by_name[name])
            continue
        if name.endswith("*"):
            prefix = name[:-1]
            matches = {
                stem for dashed, stem in by_name.items() if dashed.startswith(prefix)
            }
            # In-script variants inherit the longest existing producer family,
            # not the shorter 'channel' assembly prefix.
            parents = [dashed for dashed in by_name if prefix.startswith(dashed + "-")]
            if parents:
                matches.add(by_name[max(parents, key=len)])
            if matches:
                found.update(matches)
                continue
        raise ValueError(
            f"Unresolved assembly source {name!r} in {script_for(asm_stem)}"
        )
    return [stem for stem in candidates if stem in found]


@functools.lru_cache(maxsize=1)
def _local_modules() -> dict[str, Path]:
    """Every local importable module a build script may pull in transitively, by
    module name: the ``_*.py`` helpers, sibling ``build_*.py`` scripts, AND any
    other sibling module a build script imports (e.g. ``pen_driver`` ->
    ``truth_model``, which ``build_pen_assembly`` pulls in and which read
    ``_config``).

    A part/assembly can reuse another module -- e.g.
    ``build_channel_spring_installed`` imports ``build_channel_spring.build_spring``,
    or ``build_pen_assembly`` imports ``pen_driver.install`` -- so the closure must
    follow those edges, or an edit to that reused module (or the config IT reads)
    would leave the dependent target reported up to date (codex review). Following
    ALL sibling modules (not just ``_*``/``build_*``) closes a config
    under-invalidation: ``pen_driver``/``truth_model`` embed machine/output +
    channels values into the saved pen assembly, but were previously invisible to
    ``module_deps_of``/``config_files_of``.

    Excludes the build-GRAPH tooling (``_buildgraph`` + one-shot extraction
    scripts) and the test modules, which are never a geometry input. Standalone CLI
    tools (verify/cut_release/...) stay in the map but are harmless: they are never
    imported by a build script, so ``_direct_local_imports`` never selects them.

    ``_telemetry`` is excluded too: ``_common`` imports it, so leaving it in would
    pull it into every part/assembly's ``file_dep`` + artefact-cache key, and a
    logging-only edit would then invalidate the whole remote cache and force every
    SolidWorks part to rebuild. Telemetry output can never change saved CAD bytes,
    so dropping it cannot under-invalidate (the one cardinal sin here) -- it only
    stops a spurious over-rebuild. ``_watchdog`` is excluded for the same reason:
    also imported by ``_common``, it only ever aborts-or-logs (crash/idle/hung
    detection) -- a build it kills produces NO artefact at all, so its content can
    never change saved CAD bytes either (codex #344).
    """
    skip = {
        "_buildgraph.py",
        "_extract.py",
        "_rewrite_imports.py",
        "_telemetry.py",
        "_watchdog.py",
    }
    out: dict[str, Path] = {}
    for p in sorted(SCRIPTS_DIR.glob("*.py")):
        if p.name not in skip and not p.name.startswith("test_"):
            out[p.stem] = p
    return out


@functools.lru_cache(maxsize=None)
def _direct_local_imports(path: Path) -> frozenset[str]:
    """Local module names (helpers + build scripts) imported ANYWHERE in ``path``
    -- top-level or lazily inside a function, e.g. ``_common``'s ``import
    _config`` or ``build_channel_spring_installed``'s ``from build_channel_spring
    import ...``. A dotted import keeps only its leading segment so ``import
    _common`` and ``from _common import x`` both resolve to ``_common``.

    Only the import MODULE is matched against the local set; imported NAMES are
    ignored, so ``from _gear import build_fixed_gear`` resolves to ``_gear`` (a
    helper) and never mistakes the ``build_fixed_gear`` function for a module.
    """
    mods = _local_modules()
    found: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                found.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return frozenset(found & mods.keys())


def module_deps_of(script: Path) -> list[str]:
    """Resolved paths of every local module (``_*.py`` helper or sibling
    ``build_*.py`` script) ``script`` transitively imports -- the EXACT
    geometry-input edges for doit's ``file_dep``.

    This replaces the old blanket "every ``_*.py`` is a dep of every build"
    rule: a leaf part that imports only ``_common`` no longer rebuilds when an
    assembly-only helper (``_assembly``) or an unrelated one (``_gear``) changes.
    Because it follows REAL Python imports transitively (``_chain_link -> _chain
    -> _common``; ``_common -> _config``; ``build_channel_spring_installed ->
    _spring -> _features``), it can never under-invalidate so long as
    a script imports what it uses -- which Python enforces at run time. The BFS is
    cycle-safe (``build_motion_study`` <-> ``build_motion_study_springs``).
    """
    mods = _local_modules()
    result: set[str] = set()
    frontier = set(_direct_local_imports(script.resolve()))
    while frontier:
        mod = frontier.pop()
        if mod in result:
            continue
        result.add(mod)
        frontier |= set(_direct_local_imports(mods[mod].resolve())) - result
    return sorted(str(mods[m].resolve()) for m in result)


def data_deps_of(script: Path) -> list[str]:
    """Resolved paths of every vendored DXF/DWG artefact ``script`` (or a helper
    it imports) references by filename -- the run-time-imported input edges doit
    must treat as ``file_dep`` (and fold into the remote-cache key).

    ``module_deps_of`` only follows Python imports; a build that imports a data
    file (``build_nameplate`` -> ``cad/references/nameplate-engraving.dxf`` via
    ``adapter.import_dxf_dwg``) has no import edge to it, so an edit to the DXF
    would otherwise not rebuild the part. This scans the script's transitive
    module closure source for quoted ``*.dxf``/``*.dwg`` literals and resolves
    each basename under ``cad/references``.

    A named artefact is listed **whether or not it currently exists on disk**: a
    referenced input that is accidentally deleted or renamed after a build is a
    MISSING runtime dependency, and keeping it in ``file_dep`` makes doit/the
    build fail loud on it rather than silently report the stale ``.SLDPRT`` up to
    date. It is CONSERVATIVE (can over- but never under-invalidate): only files
    named by a literal in the script's own import closure are ever listed.
    """
    sources = [script.resolve(), *(Path(p) for p in module_deps_of(script))]
    found: set[str] = set()
    for src in sources:
        try:
            text = src.read_text(encoding="utf-8")
        except OSError:
            continue
        for literal in _DATA_LITERAL_RE.findall(text):
            candidate = REFERENCES_DIR / Path(literal).name
            found.add(str(candidate.resolve()))
    return sorted(found)


# --- Per-script CONFIG read-set: which cad/config FILES a build script actually
# reads, so doit can depend each part/assembly on ONLY those files instead of the
# blanket "every *.yaml is a dep of every build". A whole-config dep meant one
# value edit to any YAML (e.g. machine channels.active_count, one part's registry
# row, or even the 98 KB narrative dimensions.yaml that NO part reads) marked all
# ~76 parts stale -> a ~25 min full rebuild on the single SolidWorks seat.
#
# The two largest data files are SPLIT into per-concern files (see _config.py,
# which re-aggregates them transparently), so the dependency can be per-subsystem
# / per-part rather than per-file:
# ``config_files_of`` returns config-relative TOKENS: a concrete path
# (``"channels.yaml"``, ``"machine/gear_train.yaml"``, ``"parts/cone-gear.yaml"``)
# or one of four dynamic tokens -- ``"machine/*"`` (whole machine family, for a
# dynamic subsystem), ``"parts/*"`` (whole parts registry, for the dynamic part
# name in ``_common.part_properties``), ``"title_block"`` (title_block.yaml,
# but only for tasks that stamp part properties), ``"**"`` (whole config, the
# fallback). dodo.py expands these, narrowing ``"parts/*"``/``"title_block"``
# per task: a part to its OWN row, an assembly to the rows it actually stamps
# (see _config_deps in dodo.py).

# Accessors that read a FIXED file (no argument resolution needed). Derived from
# _config.py; kept in sync by test_config_accessor_coverage. Note active_count
# reads machine("channels", ...) -> machine/channels.yaml (the machine subsystem),
# which is a DIFFERENT file from the top-level channels.yaml (the channel table).
_FIXED_ACCESSOR_TOKENS: dict[str, frozenset[str]] = {
    "channels": frozenset({"channels.yaml"}),
    "cone_teeth": frozenset({"channels.yaml"}),
    "amplitudes": frozenset({"channels.yaml"}),
    "poses": frozenset({"poses.yaml"}),
    "active_count": frozenset({"machine/channels.yaml"}),
    "active_channels": frozenset({"channels.yaml", "machine/channels.yaml"}),
    "fit": frozenset({"tolerances.yaml"}),
    "release_revision": frozenset({"release.yaml"}),
    # title_block is read only by _common.part_properties (the TOL_* stamping),
    # so it emits a DYNAMIC token dodo narrows per task exactly like "parts/*":
    # parts (and stamping assemblies) -> title_block.yaml; a non-stamping
    # assembly drops it (a title-block edit re-stamps the parts, whose new
    # digests REFRESH the assembly — folding it into the assembly recipe would
    # escalate to a spurious ~500 s FULL rebuild).
    "title_block": frozenset({"title_block"}),
    "materials": frozenset({"materials.yaml"}),
    "palette": frozenset({"materials.yaml"}),
}
# Accessors whose file(s) are named by their FIRST positional argument:
#   machine(<subsystem>, ...) -> machine/<subsystem>.yaml   (dynamic -> machine/*)
#   parts(<dashed-name>)      -> parts/<name>.yaml+_defaults (dynamic -> parts/*)
#   provenance/_doc(<doc>)    -> that doc's file family      (dynamic -> "**")
_FAMILY_ACCESSORS: frozenset[str] = frozenset(
    {"machine", "parts", "provenance", "_doc"}
)


class _UnknownConfigUse(Exception):
    """A ``_config`` usage we cannot statically classify -> fall back to the whole
    config (never under-invalidate)."""


@functools.lru_cache(maxsize=1)
def _top_level_docs() -> frozenset[str]:
    """Single-file config doc stems (channels, tolerances, materials, dimensions)."""
    return frozenset(p.stem for p in CONFIG_DIR.glob("*.yaml"))


@functools.lru_cache(maxsize=1)
def _machine_subsystems() -> frozenset[str]:
    """Machine subsystem stems (``machine/<sub>.yaml`` minus the units _base)."""
    d = CONFIG_DIR / "machine"
    return (
        frozenset(p.stem for p in d.glob("*.yaml") if p.stem != "_base")
        if d.is_dir()
        else frozenset()
    )


@functools.lru_cache(maxsize=1)
def _part_registry_names() -> frozenset[str]:
    """Per-part registry stems (``parts/<dashed-name>.yaml`` minus _defaults)."""
    d = CONFIG_DIR / "parts"
    return (
        frozenset(p.stem for p in d.glob("*.yaml") if p.stem != "_defaults")
        if d.is_dir()
        else frozenset()
    )


def _doc_family_tokens(doc: str) -> frozenset[str] | None:
    """The token(s) covering a whole doc by name (for provenance/_doc): the split
    docs map to their family glob, single-file docs to their file. None = unknown
    doc name."""
    if doc == "machine":
        return frozenset({"machine/*"})
    if doc == "parts":
        return frozenset({"parts/*"})
    if doc in _top_level_docs():
        return frozenset({f"{doc}.yaml"})
    return None


def _family_tokens(accessor: str, arg: str | None) -> frozenset[str]:
    """Resolve a family accessor at one call site. ``arg`` is the literal first-arg
    string, or None when there is no positional arg OR it is non-literal."""
    if accessor == "machine":
        if arg is None:
            return frozenset({"machine/*"})  # dynamic subsystem -> whole family
        if arg in _machine_subsystems():
            return frozenset({f"machine/{arg}.yaml"})
        raise _UnknownConfigUse  # unknown subsystem
    if accessor == "parts":
        if arg is None:
            return frozenset({"parts/*"})  # dynamic part name (the _common path)
        if arg in _part_registry_names():
            return frozenset({f"parts/{arg}.yaml", "parts/_defaults.yaml"})
        raise _UnknownConfigUse  # unknown registry row
    # provenance / _doc: a non-literal doc name is unresolvable -> whole config.
    if arg is None:
        raise _UnknownConfigUse
    fam = _doc_family_tokens(arg)
    if fam is None:
        raise _UnknownConfigUse
    return fam


# The config-accessor modules the read-set analysis tracks. (``_config_asm``,
# the assembly-only module that held the M6.8 ``placement`` accessor, was
# deleted with the mirror layer -- #151.)
_CONFIG_MODULES: frozenset[str] = frozenset({"_config"})


def _literal_first_arg(call: ast.Call) -> str | None:
    """The first positional arg of ``call`` if it is a string literal, else None
    (no arg, or a non-literal/dynamic arg)."""
    arg = call.args[0] if call.args else None
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


class _ConfigUse(Enum):
    CALL = "call"
    REFERENCE = "reference"


@functools.lru_cache(maxsize=512)
def _config_references_in_text(
    text: str, config_modules: frozenset[str]
) -> tuple[tuple[str, _ConfigUse, str | None], ...] | None:
    """Extract immutable syntax facts once per source content, not per consumer.

    Shared helpers occur in many task closures. Repeating their AST walks made
    config analysis dominate task loading. Do not cache resolved config tokens
    here: family membership and accessor mappings are evaluated by the caller.
    None denotes an unclassifiable bare-name import, never an empty read set.
    """
    nodes = tuple(ast.walk(ast.parse(text)))
    aliases = set(config_modules)
    for node in nodes:
        if isinstance(node, ast.ImportFrom) and node.module in config_modules:
            return None
        if isinstance(node, ast.Import):
            aliases.update(
                alias.asname for alias in node.names
                if alias.name in config_modules and alias.asname
            )
    calls: dict[int, str | None] = {}
    for node in nodes:
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in aliases
        ):
            calls[id(node.func)] = _literal_first_arg(node)
    references = []
    for node in nodes:
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
        ):
            use = _ConfigUse.CALL if id(node) in calls else _ConfigUse.REFERENCE
            references.append((node.attr, use, calls.get(id(node))))
    return tuple(references)


def _config_tokens_in_source(path: Path) -> frozenset[str]:
    """Resolve ONE source's config reads; reject every unclassified use.

    Only syntax is reused. Reading source content on each call detects edits even
    when timestamps are unchanged; accessor/family resolution is not memoized by
    this function. Callers retain their existing per-invocation graph snapshot.
    """
    references = _config_references_in_text(path.read_text(encoding="utf-8"), _CONFIG_MODULES)
    if references is None:
        raise _UnknownConfigUse
    tokens: set[str] = set()
    for attr, use, argument in references:
        if attr in _FIXED_ACCESSOR_TOKENS:
            tokens |= _FIXED_ACCESSOR_TOKENS[attr]
            continue
        if attr in _FAMILY_ACCESSORS and use is _ConfigUse.CALL:
            tokens |= _family_tokens(attr, argument)
            continue
        raise _UnknownConfigUse
    return frozenset(tokens)


@functools.lru_cache(maxsize=None)
def config_files_of(script: Path) -> frozenset[str]:
    """Config file TOKENS a build script reads, across its transitive import
    closure (see the module comment for the token vocabulary).

    The conservative complement of ``module_deps_of``: scans the script plus every
    local module it imports for ``_config`` accessor calls and unions the tokens
    they read. Returns ``frozenset({"**"})`` if any source uses ``_config``
    unclassifiably or fails to parse -- so doit over-rebuilds rather than ever
    skipping a real change.
    """
    sources = [script.resolve(), *(Path(p) for p in module_deps_of(script))]
    tokens: set[str] = set()
    for src in sources:
        try:
            tokens |= _config_tokens_in_source(src)
        except (_UnknownConfigUse, SyntaxError, OSError):
            return frozenset({"**"})  # conservative: the whole config
    return frozenset(tokens)


# --- Token -> concrete file expansion helpers (pure; dodo.py adds per-task
# narrowing of the "parts/*" token).
def all_config_files() -> list[str]:
    """Every config file (recursive) -- the ``"**"`` whole-config expansion."""
    return sorted(str(p.resolve()) for p in CONFIG_DIR.rglob("*.yaml"))


def machine_family_files() -> list[str]:
    """Every machine/*.yaml (incl _base) -- the ``"machine/*"`` expansion."""
    d = CONFIG_DIR / "machine"
    return sorted(str(p.resolve()) for p in d.glob("*.yaml")) if d.is_dir() else []


def parts_registry_files() -> list[str]:
    """Every parts/*.yaml (incl _defaults) -- the conservative ``"parts/*"``
    expansion (dodo.py narrows this per task)."""
    d = CONFIG_DIR / "parts"
    return sorted(str(p.resolve()) for p in d.glob("*.yaml")) if d.is_dir() else []


def part_row_files(dashed_name: str) -> list[str]:
    """The registry files a single part reads when it stamps its own properties:
    its row + the shared defaults. Empty if the part is unregistered (then
    ``part_properties`` reads neither -- see _common)."""
    row = CONFIG_DIR / "parts" / f"{dashed_name}.yaml"
    if not row.exists():
        return []
    defaults = CONFIG_DIR / "parts" / "_defaults.yaml"
    return sorted({str(row.resolve()), str(defaults.resolve())})


# A generic custom-property write says nothing about registry ownership.  Part
# generation and assembly-title stamping therefore have distinct primitives.
_PART_STAMP_PRIMITIVES = frozenset({"part_properties", "save_part_and_images"})
_TITLE_BLOCK_STAMP_PRIMITIVES = frozenset(
    {*_PART_STAMP_PRIMITIVES, "assembly_title_properties"}
)


def _function_call_names(node: ast.AST) -> tuple[set[str], set[tuple[str, str]]]:
    """Within ``node`` (a function or module), the names it calls: bare-name calls
    ``f(...)`` -> ``{"f"}`` and attribute calls ``m.f(...)`` -> ``{("m", "f")}``."""
    simple: set[str] = set()
    attrs: set[tuple[str, str]] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            fn = n.func
            if isinstance(fn, ast.Name):
                simple.add(fn.id)
            elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                attrs.add((fn.value.id, fn.attr))
    return simple, attrs


@functools.lru_cache(maxsize=None)
def _stamping_modules(primitives: frozenset[str]) -> frozenset[str]:
    """Module stems that contain a function which TRANSITIVELY calls a stamping
    primitive -- a whole-program, function-level call graph over every local
    module. ``primitives`` selects the property contract being classified.

    For part-registry classification this is precise where a module-level
    "is it imported" test is not: an assembly
    that imports a part builder only for CONSTANTS (``build_summing_assembly`` <-
    ``build_boss_hook`` values), or that calls only a builder's MATH helpers
    (``build_paper_drive_assembly`` -> ``_gear`` -> ``build_cone_gear.gap_area_in_disc``),
    never reaches a stamping primitive and is correctly NOT a stamper -- so a
    registry-row edit rebuilds the relevant PART and merely REFRESHES the assembly,
    no FULL (codex review). An assembly that genuinely generates+stamps an in-script
    part (``build_channel_assembly`` -> ``_spring.build_spring`` ->
    ``save_part_and_images``) IS a stamper. Stamping is always a by-name call, so
    name-based edges capture every real path (no under-detection)."""
    mods = _local_modules()
    local_names = frozenset(mods)
    # Per module: each top-level function's call names, plus import resolution.
    func_calls: dict[tuple[str, str], tuple[set[str], set[tuple[str, str]]]] = {}
    imp_name: dict[str, dict[str, tuple[str, str]]] = {}  # stem -> name -> (mod, orig)
    imp_alias: dict[str, dict[str, str]] = {}  # stem -> alias -> mod
    for stem, path in mods.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        n2q: dict[str, tuple[str, str]] = {}
        a2m: dict[str, str] = {}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module in local_names
            ):
                for a in node.names:
                    n2q[a.asname or a.name] = (node.module, a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in local_names:
                        a2m[a.asname or a.name] = a.name
        imp_name[stem], imp_alias[stem] = n2q, a2m
        for fn in tree.body:
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_calls[(stem, fn.name)] = _function_call_names(fn)

    # Fixpoint: a function stamps if it calls a primitive, a stamping function in
    # its own module, or an imported name that resolves to a stamping function.
    stamping: set[tuple[str, str]] = set()
    changed = True
    while changed:
        changed = False
        for key, (simple, attrs) in func_calls.items():
            if key in stamping:
                continue
            stem, _ = key
            hit = bool(simple & primitives)
            if not hit:
                for s in simple:
                    if (stem, s) in stamping or imp_name[stem].get(s) in stamping:
                        hit = True
                        break
            if not hit:
                for v, attr in attrs:
                    m = imp_alias[stem].get(v)
                    if m and (m, attr) in stamping:
                        hit = True
                        break
            if hit:
                stamping.add(key)
                changed = True
    return frozenset(stem for stem, _ in stamping)


def stamps_part_properties(script: Path) -> bool:
    """True when this script generates and stamps a part-registry-owned part.

    For assemblies this is intentionally narrower than title-block stamping:
    only channel generates stretched spring variants in-script.  The predicate
    controls referenced part-row and part-template recipe dependencies.
    """
    return script.stem in _stamping_modules(_PART_STAMP_PRIMITIVES)


def stamps_title_block_properties(script: Path) -> bool:
    """True when this script stamps the general-tolerance title-block fields."""
    return script.stem in _stamping_modules(_TITLE_BLOCK_STAMP_PRIMITIVES)


def dependents_of(stem: str) -> list[str]:
    """Assembly stems whose build script references this part/assembly (legacy).

    The inverse of ``references_of``, preserved verbatim from ``build_all.py`` for
    parity (and the ``--rebuild`` shim). Includes the transitive top-add: any part
    pulled into a sub-assembly also flows up to harmonic_analyzer, so the top is
    appended whenever a direct dependent exists. The doit graph does not need this
    transitive edge -- it propagates through ``<sub>.SLDASM -> harmonic-analyzer
    .SLDASM`` -- so ``references_of`` is the DIRECT inverse only.
    """
    deps = [asm for asm in ASSEMBLY_ORDER if asm != stem and stem in references_of(asm)]
    if deps and "harmonic_analyzer" not in deps:
        deps.append("harmonic_analyzer")
    return deps
