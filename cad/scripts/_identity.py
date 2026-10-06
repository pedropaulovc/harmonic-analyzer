"""Offline validation of frozen CAD identities and their producer graph.

The per-part and per-assembly YAML files own Numbers. This module checks them;
it never assigns, derives or renumbers an identity, and never imports builders.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from _identity_shapes import CATEGORIES, NUMBER, STEM

if TYPE_CHECKING:
    from _drawing_registry import DrawingSpec


def validate_registries(
    parts: Mapping[str, Any], assemblies: Mapping[str, Any]
) -> None:
    """Reject malformed identities and duplicate Numbers, including cross-kind.

    Sequence gaps are legal: these are frozen identifiers, not row positions.
    """
    errors: list[str] = []
    overlap = set(parts) & set(assemblies)
    if overlap:
        errors.append(f"part/assembly task stem collision: {sorted(overlap)}")
    numbers: dict[str, str] = {}
    for kind, registry in (("part", parts), ("assembly", assemblies)):
        for stem, row in registry.items():
            label = f"{kind} {stem!r}"
            if not isinstance(row, Mapping):
                errors.append(f"{label}: expected metadata mapping")
                continue
            category = row.get("category")
            number = row.get("number")
            if isinstance(number, str):
                if number in numbers:
                    errors.append(f"duplicate Number {number!r}: {numbers[number]} and {label}")
                else:
                    numbers[number] = label
            if not isinstance(category, str) or category not in CATEGORIES:
                errors.append(f"{label}: invalid category {category!r}")
            if (
                not isinstance(stem, str)
                or not STEM.fullmatch(stem)
                or not stem.startswith(f"{category}-")
            ):
                errors.append(f"{label}: stem/category mismatch ({category!r})")
            match = NUMBER.fullmatch(number) if isinstance(number, str) else None
            if match is None:
                errors.append(f"{label}: invalid Number {number!r}; expected MHA-XX-NNN")
                continue
            if match[1].lower() != category:
                errors.append(f"{label}: Number/category mismatch ({number!r}, {category!r})")
            sequence = int(match[2])
            if kind == "assembly" and sequence != 0:
                errors.append(f"{label}: assembly Number must end in 000")
            if kind == "part" and sequence == 0:
                errors.append(f"{label}: part Number must be 001 or greater; 000 is reserved for assemblies")
    if errors:
        raise ValueError("Identity registry errors:\n" + "\n".join(errors))


class _UniqueKeyLoader(yaml.SafeLoader):
    """Do not let YAML silently erase a duplicate identity or metadata field."""


def _unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}")
        result[key] = loader.construct_object(value_node)
    return result


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def load_registries(config_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the unmerged authorities, preserving filename/key consistency."""
    registries = []
    for family in ("parts", "assemblies"):
        registry: dict[str, Any] = {}
        for path in sorted((config_dir / family).glob("*.yaml")):
            if family == "parts" and path.name == "_defaults.yaml":
                continue
            try:
                doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
            except (ValueError, yaml.YAMLError) as exc:
                raise ValueError(f"{path}: {exc}") from exc
            if not isinstance(doc, dict):
                raise ValueError(f"{path}: expected metadata mapping")
            if family == "parts":
                if set(doc) != {path.stem}:
                    raise ValueError(f"{path}: registry key must match filename stem exactly")
                registry[path.stem] = doc[path.stem]
            else:
                registry[path.stem] = doc
        if not registry:
            raise ValueError(f"{config_dir / family}: empty identity registry")
        registries.append(registry)
    return registries[0], registries[1]


def _declared_identity(script: Path, symbol: str) -> str:
    values = []
    for node in ast.parse(script.read_text(encoding="utf-8"), filename=str(script)).body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == symbol for target in targets):
            if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                raise ValueError(f"{script}: {symbol} must be a frozen string literal")
            values.append(node.value.value)
    if len(values) != 1:
        raise ValueError(f"{script}: expected exactly one {symbol} declaration")
    return values[0]


def validate_build_graph(
    parts: Mapping[str, Any],
    assemblies: Mapping[str, Any],
    *,
    drawings: Sequence[DrawingSpec] | None = None,
) -> None:
    """Check every registry producer, insertion edge, generated model and drawing.

    Uses the same source-expression resolver as doit, including direct native
    paths. No CAD output needs to exist and no build script is executed.
    """
    import _buildgraph as graph

    if drawings is None:
        from _drawing_registry import DRAWINGS

        drawings = DRAWINGS
    part_scripts = graph.part_scripts()
    assembly_scripts = list(graph.SCRIPTS_DIR.glob("build_*_assembly.py"))
    for kind, scripts in (("part", part_scripts), ("assembly", assembly_scripts)):
        for script in scripts:
            task = script.stem.removeprefix("build_")
            if not re.fullmatch(r"[a-z]{2}_[a-z0-9]+(?:_[a-z0-9]+)*", task):
                raise ValueError(f"{kind} producer has noncanonical task filename: {script.name}")
    part_producers = {path.stem.removeprefix("build_").replace("_", "-"): path for path in part_scripts}
    assembly_producers = {
        path.stem.removeprefix("build_").removesuffix("_assembly").replace("_", "-"): path
        for path in assembly_scripts
    }
    if len(part_producers) != len(part_scripts) or len(assembly_producers) != len(assembly_scripts):
        raise ValueError("duplicate native model producers")
    for kind, registry, producers, symbol in (
        ("part", parts, part_producers, "PART_NAME"),
        ("assembly", assemblies, assembly_producers, "ASM_NAME"),
    ):
        if set(registry) != set(producers):
            raise ValueError(
                f"{kind} producer completeness: missing producers {sorted(set(registry) - set(producers))}; "
                f"unregistered producers {sorted(set(producers) - set(registry))}"
            )
        for stem, script in producers.items():
            declared = _declared_identity(script, symbol)
            if declared != stem:
                raise ValueError(f"{script}: {symbol} {declared!r} disagrees with producer stem {stem!r}")
    ordered = [stem.replace("_", "-") for stem in graph.ASSEMBLY_ORDER]
    if (
        len(ordered) != len(set(ordered))
        or set(ordered) != set(assemblies)
        or any(task != stem.replace("-", "_") for task, stem in zip(graph.ASSEMBLY_ORDER, ordered))
    ):
        raise ValueError("assembly task enumeration does not match assembly registry")
    dependencies = {}
    for task in graph.ASSEMBLY_ORDER:
        source = graph.script_for(task).read_text(encoding="utf-8")
        for generated in graph.generated_source_names(source):
            graph.generated_source_owner(generated, parts)
        dependencies[task] = graph.references_of(task)
    try:
        tuple(TopologicalSorter(dependencies).static_order())
    except CycleError as exc:
        raise ValueError(f"assembly dependency cycle: {exc.args[1]}") from exc
    names: set[str] = set()
    artifacts: set[str] = set()
    for drawing in drawings:
        if drawing.name in names or drawing.artifact_stem in artifacts:
            raise ValueError(f"duplicate drawing task or artifact: {drawing.name}")
        names.add(drawing.name)
        artifacts.add(drawing.artifact_stem)
        registry = parts if drawing.source_kind == "part" else assemblies if drawing.source_kind == "assembly" else None
        stem = drawing.part.replace("_", "-")
        if registry is None or stem not in registry:
            raise ValueError(f"drawing {drawing.name}: unresolved {drawing.source_kind} source {drawing.part!r}")
        expected_name = drawing.part + ("_assembly" if drawing.source_kind == "assembly" else "")
        if (
            drawing.part != stem.replace("-", "_")
            or drawing.name != expected_name
            or drawing.artifact_stem != expected_name.replace("_", "-")
            or drawing.script_name != f"draw_{expected_name}.py"
        ):
            raise ValueError(f"drawing {drawing.name}: source/task/artifact identity mismatch")
        if not (graph.SCRIPTS_DIR / drawing.script_name).is_file():
            raise ValueError(f"drawing {drawing.name}: missing recipe {drawing.script_name}")


def validate_repository() -> None:
    """Offline gate for the checkout's frozen identity authorities and graph."""
    import _buildgraph as graph

    parts, assemblies = load_registries(graph.CONFIG_DIR)
    validate_registries(parts, assemblies)
    validate_build_graph(parts, assemblies)
