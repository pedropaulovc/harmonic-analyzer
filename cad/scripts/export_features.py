"""Write adjacent drawing requirements bound to the just-exported raw STEP.

No SolidWorks document is opened or saved. The exporter calls
``write_manifest(stem, step, revision=release_revision())`` after naming and
exporting the part's requirement faces. Face sets come from that STEP's labels;
its unmodified bytes supply ``step_sha256``.

Construction is one_piece unless the actual drawing notes explicitly supply
BUILT_UP_PERMISSION_NOTE, whose exact, nonempty text must occur in DRAWING_NOTES.
A material/process alternative (casting or solid stock) is not built-up permission.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
from functools import lru_cache
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import _config
import _part_properties
import _surface_finish
from _feature_requirements import declaration_calls, discover_parts, metadata_for, requirements_for, source_tree
from _gtol_face import FaceSpec
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    drilled_undersize_mm,
    edge_break_chamfer_display,
    edge_break_chamfer_mm,
    edge_break_radius_display,
    edge_break_radius_mm,
    printed_band_mm,
)

SUPPORTED_PARTS = discover_parts(Path(__file__).resolve().parent)
REPO = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO / "cad" / "config"
OUT = REPO / "cad" / "out"
UNKNOWN = "unknown"


def _stem(stem: str) -> str:
    normalized = stem.replace("-", "_")
    if normalized not in SUPPORTED_PARTS:
        raise ValueError(f"unsupported feature-manifest part: {stem!r}")
    return normalized


def _drawing_module(stem: str) -> ModuleType:
    return importlib.import_module(f"draw_{stem}")


def _spec_module_name(stem: str, scripts: Path) -> str:
    """Read a literal member-spec owner; ordinary drawings keep <stem>_spec.

    A configured shared producer need not invent a monolithic spec or re-export
    the saved/default member's facts. This lookup never imports a drawing.
    """
    drawing = _source_module_path(f"draw_{stem}", scripts)
    owners = [
        node.value for node in source_tree(drawing).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "FEATURE_SPEC_MODULE" for target in node.targets)
    ]
    if not owners:
        return f"{stem}_spec"
    if len(owners) != 1 or not isinstance(owners[0], ast.Constant) or not isinstance(owners[0].value, str):
        raise ValueError(f"draw_{stem}: FEATURE_SPEC_MODULE must be one literal module name")
    name = owners[0].value
    _source_module_path(name, scripts)
    return name


def _spec_module(stem: str) -> ModuleType:
    name = _spec_module_name(stem, Path(__file__).resolve().parent)
    module = importlib.import_module(name)
    if name != f"{stem}_spec":
        # A feature bundle uses the producer's bare/default STEP, not another
        # member that merely lives in the same native file.
        default = _config.parts(stem.replace("_", "-")).get("default_configuration")
        if not default or getattr(module, "CONFIGURATION", None) != default:
            raise ValueError(f"{stem}: feature spec must own the saved default configuration")
    return module


def _notes_module(stem: str) -> ModuleType:
    name = f"{stem}_notes"
    if importlib.util.find_spec(name) is not None:
        return importlib.import_module(name)
    return _spec_module(stem)


def _declarations(module: ModuleType) -> dict[str, str]:
    """Resolve cached, current AST declarations rather than hand-entered spans."""
    path = Path(module.__file__).resolve()
    return _source_declarations(path, source_tree(path))


def _target_names(target: ast.AST) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(name for item in target.elts for name in _target_names(item))
    return ()


@lru_cache(maxsize=256)
def _source_declarations(path: Path, tree: ast.Module) -> dict[str, str]:
    relative = path.relative_to(REPO).as_posix()
    result = {}
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        result["__frame__"] = f"harmonic-analyzer/{relative}:{tree.body[0].lineno}-{tree.body[0].end_lineno}"
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [name for target in node.targets for name in _target_names(target)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        else:
            continue
        for name in names:
            result[name] = f"harmonic-analyzer/{relative}:{node.lineno}-{node.end_lineno}"
    return result


def _cite(module: ModuleType, *names: str) -> list[str]:
    declarations = _declarations(module)
    missing = [name for name in names if name not in declarations]
    if missing:
        raise ValueError(f"{module.__name__}: missing citation symbol(s): {', '.join(missing)}")
    return [declarations[name] for name in names]


def _spec_cite(module: ModuleType, sources: tuple[str | tuple[str, str], ...]) -> list[str]:
    citations = []
    for source in sources:
        owner, name = (importlib.import_module(source[0]), source[1]) if isinstance(source, tuple) else (module, source)
        citations.extend(_cite(owner, name))
    return list(dict.fromkeys(citations))


@lru_cache(maxsize=256)
def _call_spans(tree: ast.Module) -> frozenset[tuple[int, int]]:
    return frozenset(
        (call.lineno, call.end_lineno)
        for api in ("requirement", "part_metadata")
        for call in declaration_calls(tree, api)
    )


def _call_cite(path: Path, span: tuple[int, int]) -> list[str]:
    tree = source_tree(path)
    if span not in _call_spans(tree):
        raise ValueError(f"missing declaration call at {path}:{span[0]}-{span[1]}")
    return [f"harmonic-analyzer/{path.relative_to(REPO).as_posix()}:{span[0]}-{span[1]}"]


def _title_cite(*keys: str) -> list[str]:
    """Stable YAML paths to the title-block facts, validated as they are read."""
    citations = []
    for key in keys:
        row, _, field = key.partition(".")
        value = _config.title_block(row)
        for component in field.split("."):
            value = value[component]
        citations.append(f"harmonic-analyzer/cad/config/title_block.yaml:{key}")
    return citations


def _source_module_path(name: str, scripts: Path) -> Path:
    if not name or any(not component.isidentifier() for component in name.split(".")):
        raise ValueError(f"invalid citation source module: {name!r}")
    base = scripts.joinpath(*name.split("."))
    for path in (base.with_suffix(".py"), base / "__init__.py"):
        if path.is_file():
            return path.resolve()
    raise ValueError(f"missing citation source module: {name}")


def _source_modules(tree: ast.Module) -> set[str]:
    """Collect explicit (module, NAME) roots, including helper/runtime sources."""
    assignments = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for name in _target_names(target):
                    assignments[name] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            assignments[node.target.id] = node.value

    def resolve(node: ast.AST, seen: frozenset[str] = frozenset()) -> ast.AST:
        if isinstance(node, ast.Name) and node.id in assignments and node.id not in seen:
            return resolve(assignments[node.id], seen | {node.id})
        return node

    modules = set()

    def add_sources(node: ast.AST) -> None:
        node = resolve(node)
        if not isinstance(node, (ast.Tuple, ast.List)):
            return
        for source in node.elts:
            if isinstance(source, ast.Starred):
                add_sources(source.value)
                continue
            source = resolve(source)
            if isinstance(source, ast.Tuple) and len(source.elts) == 2:
                owner, symbol = (resolve(item) for item in source.elts)
                if all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in (owner, symbol)):
                    modules.add(owner.value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            # Also covers sourced values returned by declaration helpers.
            add_sources(node.elts[1])
        elif isinstance(node, ast.keyword) and node.arg in {"model_sources", "precision_sources"}:
            add_sources(node.value)
    return modules


def source_paths(stem: str) -> tuple[Path, ...]:
    """Statically cover this draw and its source closures; never import them."""
    from _buildgraph import module_deps_of

    stem = _stem(stem)
    scripts = Path(__file__).resolve().parent
    drawing = _source_module_path(f"draw_{stem}", scripts)
    spec = _source_module_path(_spec_module_name(stem, scripts), scripts)
    notes = scripts / f"{stem}_notes.py"
    roots = {Path(__file__).resolve(), drawing, spec}
    if notes.is_file():
        roots.add(notes.resolve())
    roots.update(_source_module_path(name, scripts) for name in _source_modules(source_tree(drawing)))
    paths = set(roots)
    for path in roots:
        paths.update(Path(dependency).resolve() for dependency in module_deps_of(path))
    paths.add(CONFIG_DIR / "parts" / f"{stem.replace('_', '-')}.yaml")
    return tuple(sorted(paths))


def feature_selectors(stem: str) -> dict[str, tuple[FaceSpec, ...]]:
    """Resolve all STEP patches using each drawing's geometric feature domains."""
    drawing = _drawing_module(_stem(stem))
    return {name: declared.faces for name, declared in requirements_for(drawing).items()}


def _finish_precision() -> int:
    return len(_surface_finish.ra(_surface_finish.MACHINED_UM).partition(".")[2])


def _drawing_features(
    stem: str, declarations: dict[str, Any], calls: dict[str, list[str]],
    precision_cite: list[str],
) -> dict[str, dict[str, Any]]:
    module = _spec_module(stem)
    result = {}
    for name, declared in declarations.items():
        call = calls[name]
        feature = {"kind": declared.kind, "frame": "model", "requirements": list(declared.requirements)}
        citations = {}
        for key, (value, sources) in declared.fields.items():
            feature[key] = list(value) if isinstance(value, tuple) else value
            citations[key] = list(dict.fromkeys([*call, *_spec_cite(module, sources)]))
        if declared.precision:
            feature["precision"] = dict(declared.precision)
            if not precision_cite:
                raise ValueError(f"draw_{stem}: feature precision needs nonempty metadata precision_sources")
            citations["precision"] = list(dict.fromkeys([*call, *precision_cite]))
        feature["cite"] = citations
        result[name] = feature
    return result



def _construction(module: ModuleType) -> tuple[str, list[str]]:
    permission = getattr(module, "BUILT_UP_PERMISSION_NOTE", None)
    if permission is None:
        return "one_piece", _cite(module, "DRAWING_NOTES")
    if not isinstance(permission, str) or not permission.strip() or permission not in module.DRAWING_NOTES:
        raise ValueError(f"{module.__name__}.BUILT_UP_PERMISSION_NOTE must be explicit text in DRAWING_NOTES")
    return "built_up_permitted", _cite(module, "DRAWING_NOTES")


def requirement_manifest(stem: str) -> dict[str, Any]:
    """Pure drawing requirement data, before binding it to STEP face names."""
    stem = _stem(stem)
    dashed = stem.replace("_", "-")
    module = _spec_module(stem)
    drawing = _drawing_module(stem)
    declarations = requirements_for(drawing)
    call_cites = {}

    def call_cite(declared: Any) -> list[str]:
        site = declared.path, declared.call_span
        if site not in call_cites:
            call_cites[site] = _call_cite(*site)
        return call_cites[site]

    calls = {name: call_cite(declared) for name, declared in declarations.items()}
    metadata = [(declared, call_cite(declared)) for declared in metadata_for(drawing)]
    facts = {}
    fact_citations = {}
    precision_cite = []
    frame_cite = [*_cite(module, "__frame__"), *_cite(drawing, "build")]
    for declared, call in metadata:
        for key, (value, sources) in declared.fields.items():
            facts[key] = value
            fact_citations[key] = [*call, *_spec_cite(module, sources)]
        if declared.model_sources:
            frame_cite += [*call, *_spec_cite(module, declared.model_sources)]
        if declared.precision_sources:
            if any((source[1] if isinstance(source, tuple) else source) == "__frame__" for source in declared.precision_sources):
                raise ValueError(f"draw_{stem}: precision_sources must cite printed precision, not a module docstring")
            precision_cite += [*call, *_spec_cite(module, declared.precision_sources)]
    features = _drawing_features(stem, declarations, calls, precision_cite)
    notes_module = _notes_module(stem)
    construction, construction_cite = _construction(notes_module)
    row = _config.parts(dashed)
    registry = _config._doc("parts")
    registry_row = registry["parts"][dashed]
    registry_reference = f"harmonic-analyzer/cad/config/parts/{dashed}.yaml:{dashed}"
    defaults_reference = "harmonic-analyzer/cad/config/parts/_defaults.yaml"

    def registry_cite(*keys: str) -> list[str]:
        citations = []
        for key in keys:
            if key in {"material", "material_specification"} and "material_family" in registry_row:
                family = registry_row["material_family"]
                citations += [
                    f"{registry_reference}.material_family",
                    f"{defaults_reference}:material_families.{family}.{key}",
                ]
            elif key in registry_row:
                citations.append(f"{registry_reference}.{key}")
            elif key in registry.get("defaults", {}):
                citations.append(f"{defaults_reference}:defaults.{key}")
        return list(dict.fromkeys(citations))

    general = {
        f"linear_{places}pl": printed_band_mm(places) for places in (1, 2, 3)
    }
    general.update({"angular_deg": angular_band_deg(), "drilled_hole_plus": drilled_oversize_mm(), "drilled_hole_minus": drilled_undersize_mm(), "edge_break_r": edge_break_radius_mm(), "chamfer_max": edge_break_chamfer_mm()})
    general["cite"] = {
        key: _title_cite(source)
        for key, source in (
            ("linear_1pl", "linear_1pl.band_mm"), ("linear_2pl", "linear_2pl.band_mm"),
            ("linear_3pl", "linear_3pl.band_mm"), ("angular_deg", "angular.value_deg"),
            ("drilled_hole_plus", "drilled_hole.plus_mm"), ("drilled_hole_minus", "drilled_hole.minus_mm"),
            ("edge_break_r", "edge_break.radius_mm"), ("chamfer_max", "edge_break.chamfer_max_mm"),
        )
    }
    for name, feature in features.items():
        call = calls[name]
        for key in feature.get("precision", {}) if isinstance(feature.get("precision"), dict) else ():
            if precision_cite:
                feature["cite"][f"precision.{key}"] = list(dict.fromkeys([*call, *precision_cite]))
            if key in feature["cite"] and isinstance(feature.get(key), list) and len(feature[key]) == 2:
                tolerance = "angular.value_deg" if key.endswith("_deg") else f"linear_{feature['precision'][key]}pl.band_mm"
                feature["cite"][key] += _title_cite(tolerance, "drilled_hole.plus_mm", "drilled_hole.minus_mm")
        if "finish_ra" in feature:
            if isinstance(feature.get("precision"), dict):
                feature["precision"]["finish_ra"] = _finish_precision()
                feature["cite"]["precision.finish_ra"] = [*call, *_cite(_surface_finish, "ra")]
        feature["faces"] = UNKNOWN
    notes = notes_module.DRAWING_NOTES
    for feature in features.values():
        for key in ("axis", "at", "normal", "plane"):
            if key in feature:
                feature["cite"][key] += frame_cite
        if "z_mm" in feature:
            # Source frames are rigid copies of model; cite each shared fact once.
            feature["cite"]["z_mm"] = list(dict.fromkeys([*feature["cite"]["z_mm"], *frame_cite]))
    frames: dict[str, Any] = {"model": {"origin": [0.0, 0.0, 0.0], "x": [1.0, 0.0, 0.0], "y": [0.0, 1.0, 0.0], "z": [0.0, 0.0, 1.0], "cite": frame_cite}, "setup": UNKNOWN}
    datums: dict[str, Any] = {}
    for declared, call in metadata:
        for values, target in ((declared.frames, frames), (declared.datums, datums)):
            for name, (value, sources) in values.items():
                target[name] = {**value, "cite": [*call, *_spec_cite(module, sources)]}
    volume = {"volume_mm3": facts["volume_mm3"], "volume_cite": fact_citations["volume_mm3"]} if "volume_mm3" in facts else {}
    return {
        "part": dashed, "units": "mm", "precision": facts.get("precision", UNKNOWN),
        "step": bundle_paths(stem)[1].name, "step_sha256": UNKNOWN, "construction": construction, **volume, "cite_root": "harmonic-analyzer",
        "cite": {"construction": construction_cite, "units": frame_cite, "precision": fact_citations.get("precision", frame_cite), "frames": frame_cite},
        "drawing": {"number": row["number"], "revision": UNKNOWN, "cite": [*registry_cite("number"), "harmonic-analyzer/cad/config/release.yaml:next_revision", *_cite(_part_properties, "part_properties")]},
        "material": {"spec": row.get("material_specification", UNKNOWN), "name": row.get("material", UNKNOWN), "finish": facts.get("material.finish", row.get("finish", UNKNOWN)), "thickness": facts.get("material.thickness", UNKNOWN), "cite": [*registry_cite("material_specification", "material"), *fact_citations.get("material.finish", registry_cite("finish")), *fact_citations.get("material.thickness", [])]},
        "notes": {"manufacturing": notes.splitlines(), "process": facts.get("notes.process", row.get("process", UNKNOWN)), "edge_break": f"REMOVE BURRS AND BREAK SHARP EDGES {edge_break_radius_display()} OR CHAMFER {edge_break_chamfer_display()} MAX", "cite": [*fact_citations.get("notes.process", registry_cite("process")), *_title_cite("edge_break.radius_mm", "edge_break.chamfer_max_mm", "edge_break.digits"), *_cite(notes_module, "DRAWING_NOTES")]},
        "general_tolerances": general, "frames": frames, "datums": datums, "features": features,
    }


def _toml(data: dict[str, Any]) -> str:
    # All manifest containers are dictionaries or scalar/list values; inline
    # tables retain per-value citations without a TOML runtime dependency.
    def value(item: Any) -> str:
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False)
        if isinstance(item, bool):
            return "true" if item else "false"
        if isinstance(item, (int, float)):
            if not math.isfinite(item):
                raise ValueError("non-finite manifest number")
            return repr(item)
        if isinstance(item, (list, tuple)):
            return "[" + ", ".join(value(entry) for entry in item) + "]"
        if isinstance(item, dict):
            return "{ " + ", ".join(f"{value(key)} = {value(entry)}" for key, entry in item.items()) + " }"
        raise TypeError(f"unsupported TOML value: {type(item).__name__}")
    lines = ["# Generated from CAD drawing contracts and adjacent raw STEP bytes; do not hand edit."]
    def table(node: dict[str, Any], path: tuple[str, ...] = ()) -> None:
        if path:
            lines.extend(("", "[" + ".".join(value(key) for key in path) + "]"))
        for key, item in node.items():
            if not isinstance(item, dict) or key in {"cite", "precision", "plane", "bounds"}:
                lines.append(f"{value(key)} = {value(item)}")
        for key, item in node.items():
            if isinstance(item, dict) and key not in {"cite", "precision", "plane", "bounds"}:
                table(item, (*path, key))
    table(data)
    return "\n".join(lines) + "\n"


def bundle_paths(stem: str, out: Path = OUT) -> tuple[Path, Path]:
    """Return the requirements manifest and scoped STEP in their shared bundle."""
    stem = _stem(stem)
    directory = Path(out) / "features" / stem
    return directory / "features.toml", directory / f"{stem.replace('_', '-')}.STEP"


@lru_cache(maxsize=256)
def step_configurations(stem: str) -> tuple[str, ...]:
    """The configurations a multi-configuration part also exports, one STEP each.

    Opt-in: the part's spec declares ``FEATURE_STEP_CONFIGURATIONS`` as a
    literal tuple of configuration names, read statically so dodo never
    imports a spec. A part that declares nothing (or has no spec module)
    exports only its bundle STEP (the saved, active configuration).
    """
    stem = _stem(stem)
    path = Path(__file__).resolve().parent / f"{stem}_spec.py"
    if not path.is_file():
        return ()
    for node in source_tree(path).body:
        target = node.target if isinstance(node, ast.AnnAssign) else (
            node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else None
        )
        if not (isinstance(target, ast.Name) and target.id == "FEATURE_STEP_CONFIGURATIONS"):
            continue
        names = ast.literal_eval(node.value)
        if (
            not isinstance(names, tuple) or not names or len(set(names)) != len(names)
            or not all(isinstance(name, str) and name.isalnum() for name in names)
        ):
            raise ValueError(
                f"{stem}: FEATURE_STEP_CONFIGURATIONS must be a non-empty tuple of "
                f"distinct alphanumeric configuration names, found {names!r}"
            )
        return names
    return ()


def configuration_step_paths(stem: str, out: Path = OUT) -> dict[str, Path]:
    """Each declared configuration's STEP beside the bundle STEP, named by configuration."""
    _manifest, step = bundle_paths(stem, out)
    return {
        name: step.with_name(f"{step.stem}-{name}{step.suffix}")
        for name in step_configurations(stem)
    }


def write_manifest(stem: str, step: Path, *, revision: str) -> Path:
    """Bind all labelled STEP faces and write the adjacent requirements TOML."""
    from prechips.model import Features

    from _export_feature_faces import step_face_sets

    stem = _stem(stem)
    step = Path(step)
    content = step.read_bytes()
    manifest = requirement_manifest(stem)
    faces = step_face_sets(content.decode("latin-1"), manifest["features"].keys())
    step_cite = f"harmonic-analyzer/cad/out/features/{stem}/{step.name}"
    for name, feature in manifest["features"].items():
        feature["faces"] = faces[name]
        feature["cite"]["faces"] = [step_cite]
    manifest["step"] = step.name
    manifest["step_sha256"] = hashlib.sha256(content).hexdigest()
    manifest["cite"]["step_sha256"] = [step_cite]
    manifest["drawing"]["revision"] = revision
    Features.model_validate(manifest)
    path = step.with_name(bundle_paths(stem)[0].name)
    partial = path.with_suffix(".toml.partial")
    partial.write_text(_toml(manifest), encoding="utf-8", newline="\n")
    partial.replace(path)
    return path
