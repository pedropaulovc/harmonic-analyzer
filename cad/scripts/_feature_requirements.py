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
``model_sources`` supplements the shared model frame; ``precision_sources``
names the drawing's precision declarations for each feature precision field.

Numeric ``limits`` and ``drilled_limits`` belong to ``_printed_limits`` and
drawings import them directly. Both modules stay out of native part and assembly
closures; native geometry guard bounds use the unchanged
``_printed_tolerance.printed_deviations`` instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ast
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
    module: str
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
def _declaration_calls(text: str, api: str) -> tuple[ast.Call, ...]:
    tree = ast.parse(text)
    names = {api}
    modules = {"_feature_requirements"}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "_feature_requirements":
            names.update(alias.asname or alias.name for alias in node.names if alias.name == api)
        elif isinstance(node, ast.Import):
            modules.update(alias.asname or alias.name for alias in node.names if alias.name == "_feature_requirements")
    calls = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        if isinstance(node, ast.Call):
            function = node.func
            if (
                isinstance(function, ast.Name) and function.id in names
                or isinstance(function, ast.Attribute) and function.attr == api
                and isinstance(function.value, ast.Name) and function.value.id in modules
            ):
                calls.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return tuple(calls)


def discover_parts(scripts: Path) -> tuple[str, ...]:
    """Find drawing-owned requirements by AST alone; never import a drawing."""
    return tuple(
        path.stem.removeprefix("draw_")
        for path in sorted(Path(scripts).glob("draw_*.py"))
        if _declaration_calls(path.read_text(encoding="utf-8"), "requirement")
    )


def _call_site(frame: Any, api: str) -> tuple[Path, tuple[int, int]]:
    if frame.f_code.co_name != "<module>":
        raise ValueError(f"{api} must be called at drawing module level")
    path = Path(frame.f_code.co_filename).resolve()
    if not path.stem.startswith("draw_"):
        raise ValueError(f"{api} must be declared in a draw_<stem> module")
    calls = [
        call for call in _declaration_calls(path.read_text(encoding="utf-8"), api)
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
    """Register and return one requirement at its drawing-owned call site."""
    frame = inspect.currentframe().f_back
    try:
        path, span = _call_site(frame, "requirement")
        declared = Requirement(
            name, kind, tuple(faces), tuple(requirements), fields,
            dict(precision or {}), frame.f_globals["__name__"], path, span,
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
