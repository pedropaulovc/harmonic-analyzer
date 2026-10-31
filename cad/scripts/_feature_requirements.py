r"""Drawing-owned, import-inert requirement declarations for ``export_features``.

Place module-level ``requirement(name, kind=..., faces=..., requirements=...,
fields=..., precision=...)`` calls beside the drawing's dimension/callout helpers.
``requirements_for(draw_module)`` returns their registered, named declarations.
Each field is ``(value, sources)``: a string names a declaration in the part's
``<stem>_spec``; ``(module, NAME)`` names a declaration in another module.
The exporter cites both the requirement call's AST span and every named source,
failing loudly if a source disappeared. Discovery scans these calls without
importing drawings or connecting to SolidWorks.

``part_metadata`` uses the same sourced-value pairs for part-level ``fields``
(``precision``, ``material.thickness``, ``volume_mm3``), named ``frames`` and
``datums``. Multiple colocated calls merge without overwriting prior facts.
``model_sources`` supplements the shared model frame. Every feature precision
dict requires nonempty ``precision_sources`` naming its actual printed maps,
callout helpers or formatter; a module docstring is not precision authority.

Numeric ``limits`` and ``drilled_limits`` belong to ``_printed_limits`` and
drawings import them directly. Both modules stay out of native part and assembly
closures; native geometry guard bounds use the unchanged
``_printed_tolerance.printed_deviations`` instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ast
import unicodedata
import inspect
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from _gtol_face import FaceSpec

# Strings name declarations in the part spec; pairs explicitly name another module.
Source = str | tuple[str, str]


@dataclass(frozen=True)
class Requirement:
    name: str
    kind: str
    faces: tuple[FaceSpec, ...]
    requirements: tuple[str, ...]
    fields: dict[str, tuple[Any, tuple[Source, ...]]]
    precision: dict[str, int | str]
    path: Path
    call_span: tuple[int, int]

    def __post_init__(self) -> None:
        if not self.name or not self.faces:
            raise ValueError(f"{self.kind} requirement feature needs a name and STEP face")
        missing = [name for name in self.requirements if name != "unknown" and name not in self.fields]
        if missing:
            raise ValueError(f"requirements without a field: {missing}")
        _require_sources(self.fields)


@dataclass(frozen=True)
class PartMetadata:
    fields: dict[str, tuple[Any, tuple[Source, ...]]] = field(default_factory=dict)
    frames: dict[str, tuple[dict[str, Any], tuple[Source, ...]]] = field(default_factory=dict)
    datums: dict[str, tuple[dict[str, Any], tuple[Source, ...]]] = field(default_factory=dict)
    model_sources: tuple[Source, ...] = ()
    precision_sources: tuple[Source, ...] = ()
    path: Path | None = None
    call_span: tuple[int, int] | None = None


def _require_sources(fields: dict[str, tuple[Any, tuple[Source, ...]]]) -> None:
    unsourced = [name for name, (_value, sources) in fields.items() if not sources]
    if unsourced:
        raise ValueError(f"fields without a source declaration: {unsourced}")


@lru_cache(maxsize=256)
def _source_tree(path: Path, text: str) -> ast.Module:
    return ast.parse(text, filename=str(path))


def source_tree(path: Path) -> ast.Module:
    """Parse current source, caching only an exact resolved-path/content pair."""
    path = Path(path).resolve()
    with path.open(encoding="utf-8", newline="") as source:
        return _source_tree(path, source.read())


@lru_cache(maxsize=512)
def declaration_calls(tree: ast.Module, api: str) -> tuple[ast.Call, ...]:
    """Find import-bound API calls in executable module code, without execution."""
    bindings: dict[str, str] = {}
    calls: list[ast.Call] = []

    class Visitor(ast.NodeVisitor):
        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                name = alias.asname or alias.name
                bindings.pop(name, None)
                if node.module == "_feature_requirements" and node.level == 0 and alias.name == api:
                    bindings[name] = api

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                bindings.pop(name, None)
                if alias.name == "_feature_requirements":
                    bindings[name] = "module"

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            bindings.pop(node.name, None)

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef

        def visit_Lambda(self, node: ast.Lambda) -> None:
            pass

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                bindings.pop(node.id, None)

        def visit_Assign(self, node: ast.Assign) -> None:
            self.visit(node.value)
            for target in node.targets:
                self.visit(target)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            self.visit(node.value)
            self.visit(node.target)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if node.value is not None:
                self.visit(node.value)
                self.visit(node.target)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            self.visit(node.value)
            self.visit(node.target)

        def visit_If(self, node: ast.If) -> None:
            self.visit(node.test)
            before = dict(bindings)
            for statement in node.body:
                self.visit(statement)
            body = dict(bindings)
            bindings.clear()
            bindings.update(before)
            for statement in node.orelse:
                self.visit(statement)
            merged = {name: owner for name, owner in body.items() if bindings.get(name) == owner}
            bindings.clear()
            bindings.update(merged)

        def visit_For(self, node: ast.For) -> None:
            self.visit(node.iter)
            before = dict(bindings)
            self.visit(node.target)
            for statement in node.body:
                self.visit(statement)
            merged = {name: owner for name, owner in before.items() if bindings.get(name) == owner}
            bindings.clear()
            bindings.update(merged)
            for statement in node.orelse:
                self.visit(statement)

        visit_AsyncFor = visit_For

        def visit_While(self, node: ast.While) -> None:
            self.visit(node.test)
            before = dict(bindings)
            for statement in node.body:
                self.visit(statement)
            merged = {name: owner for name, owner in before.items() if bindings.get(name) == owner}
            bindings.clear()
            bindings.update(merged)
            for statement in node.orelse:
                self.visit(statement)

        def visit_Try(self, node: ast.Try) -> None:
            before = dict(bindings)
            for statement in (*node.body, *node.orelse):
                self.visit(statement)
            branches = [dict(bindings)]
            for handler in node.handlers:
                bindings.clear()
                bindings.update(before)
                if handler.type is not None:
                    self.visit(handler.type)
                if handler.name is not None:
                    bindings.pop(handler.name, None)
                for statement in handler.body:
                    self.visit(statement)
                if handler.name is not None:
                    bindings.pop(handler.name, None)
                branches.append(dict(bindings))
            merged = {
                name: owner for name, owner in branches[0].items()
                if all(branch.get(name) == owner for branch in branches[1:])
            }
            bindings.clear()
            bindings.update(merged)
            for statement in node.finalbody:
                self.visit(statement)

        visit_TryStar = visit_Try

        def visit_Match(self, node: ast.Match) -> None:
            self.visit(node.subject)
            before = dict(bindings)
            branches = [before]
            for case in node.cases:
                bindings.clear()
                bindings.update(before)
                self.visit(case.pattern)
                if case.guard is not None:
                    self.visit(case.guard)
                for statement in case.body:
                    self.visit(statement)
                branches.append(dict(bindings))
            merged = {
                name: owner for name, owner in before.items()
                if all(branch.get(name) == owner for branch in branches[1:])
            }
            bindings.clear()
            bindings.update(merged)

        def visit_MatchAs(self, node: ast.MatchAs) -> None:
            if node.name is not None:
                bindings.pop(node.name, None)
            if node.pattern is not None:
                self.visit(node.pattern)

        def visit_MatchStar(self, node: ast.MatchStar) -> None:
            if node.name is not None:
                bindings.pop(node.name, None)

        def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
            if node.rest is not None:
                bindings.pop(node.rest, None)
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            function = node.func
            if (
                isinstance(function, ast.Name) and bindings.get(function.id) == api
                or isinstance(function, ast.Attribute) and function.attr == api
                and isinstance(function.value, ast.Name) and bindings.get(function.value.id) == "module"
            ):
                calls.append(node)
            self.generic_visit(node)

    Visitor().visit(tree)
    return tuple(calls)


def _may_declare(path: Path) -> bool:
    """Whether ``path`` can bind the declaration API at all.

    ``declaration_calls`` only follows names imported from
    ``_feature_requirements``, so a source that never spells the module name
    declares nothing and is not parsed. Python NFKC-normalizes identifiers,
    so non-ASCII text is searched normalized.
    """
    text = Path(path).read_text(encoding="utf-8")
    if not text.isascii():
        text = unicodedata.normalize("NFKC", text)
    return "_feature_requirements" in text


def discover_parts(scripts: Path) -> tuple[str, ...]:
    """Find drawing-owned requirements by AST alone; never import a drawing."""
    return tuple(
        path.stem.removeprefix("draw_")
        for path in sorted(Path(scripts).glob("draw_*.py"))
        if _may_declare(path) and declaration_calls(source_tree(path), "requirement")
    )


def _call_site(frame: Any, api: str) -> tuple[Path, tuple[int, int]]:
    if frame.f_code.co_name != "<module>":
        raise ValueError(f"{api} must be called at drawing module level")
    path = Path(frame.f_code.co_filename).resolve()
    if not path.stem.startswith("draw_"):
        raise ValueError(f"{api} must be declared in a draw_<stem> module")
    calls = [
        call for call in declaration_calls(source_tree(path), api)
        if call.lineno <= frame.f_lineno <= call.end_lineno
    ]
    if len(calls) != 1:
        raise ValueError(f"cannot resolve {api} call at {path}:{frame.f_lineno}")
    return path, (calls[0].lineno, calls[0].end_lineno)


def requirement(
    name: str, *, kind: str, faces: tuple[FaceSpec, ...],
    requirements: tuple[str, ...], fields: dict[str, tuple[Any, tuple[Source, ...]]],
    precision: dict[str, int | str] | None = None,
) -> Requirement:
    """Register a requirement; return a registry descriptor for optional inspection.

    Registration does not make drawing print paths consume this descriptor.
    Those paths retain their printed spec/notes authority unless explicitly read
    from the returned fields or precision.
    """
    frame = inspect.currentframe().f_back
    try:
        path, span = _call_site(frame, "requirement")
        declared = Requirement(
            name, kind, tuple(faces), tuple(requirements), fields,
            dict(precision or {}), path, span,
        )
        registry = frame.f_globals.setdefault("_FEATURE_REQUIREMENTS", {})
        if name in registry:
            raise ValueError(f"duplicate requirement {name!r} in {path.name}")
        registry[name] = declared
        return declared
    finally:
        del frame


def requirements_for(module: ModuleType) -> dict[str, Requirement]:
    """Return one imported drawing's declarations, preserving declaration order."""
    declared = getattr(module, "_FEATURE_REQUIREMENTS", {})
    if not declared or not all(isinstance(item, Requirement) for item in declared.values()):
        raise ValueError(f"{module.__name__} has no registered drawing requirements")
    return dict(declared)


def part_metadata(
    *, fields: dict[str, tuple[Any, tuple[Source, ...]]] | None = None,
    frames: dict[str, tuple[dict[str, Any], tuple[Source, ...]]] | None = None,
    datums: dict[str, tuple[dict[str, Any], tuple[Source, ...]]] | None = None,
    model_sources: tuple[Source, ...] = (), precision_sources: tuple[Source, ...] = (),
) -> PartMetadata:
    """Register sourced part facts beside the drawing helpers that expose them."""
    frame = inspect.currentframe().f_back
    try:
        path, span = _call_site(frame, "part_metadata")
        declared = PartMetadata(
            fields or {}, frames or {}, datums or {},
            model_sources, precision_sources, path, span,
        )
        for values in (declared.fields, declared.frames, declared.datums):
            _require_sources(values)
        registry = frame.f_globals.setdefault("_FEATURE_METADATA", [])
        for previous in registry:
            for attribute in ("fields", "frames", "datums"):
                duplicate = getattr(previous, attribute).keys() & getattr(declared, attribute).keys()
                if duplicate:
                    raise ValueError(f"duplicate part metadata in {path.name}: {sorted(duplicate)}")
        registry.append(declared)
        return declared
    finally:
        del frame


def metadata_for(module: ModuleType) -> tuple[PartMetadata, ...]:
    """Return colocated metadata declarations, or no overrides for shared facts."""
    return tuple(getattr(module, "_FEATURE_METADATA", ()))
