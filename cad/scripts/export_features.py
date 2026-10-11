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
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import _config
import _part_properties
import _surface_finish
from _feature_requirements import _declaration_calls, discover_parts, metadata_for, requirements_for
from _gtol_face import FaceSpec
from _printed_tolerance import printed_band_mm

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


def _spec_module(stem: str) -> ModuleType:
    return importlib.import_module(f"{stem}_spec")


def _notes_module(stem: str) -> ModuleType:
    name = f"{stem}_notes"
    if importlib.util.find_spec(name) is not None:
        return importlib.import_module(name)
    return _spec_module(stem)


def _declarations(module: ModuleType) -> dict[str, str]:
    """Resolve current AST declarations, never stale, hand-entered line spans."""
    path = Path(module.__file__).resolve()
    relative = path.relative_to(REPO).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = {}
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        result["__frame__"] = f"harmonic-analyzer/{relative}:{tree.body[0].lineno}-{tree.body[0].end_lineno}"
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [
                item.id for target in node.targets for item in ast.walk(target)
                if isinstance(item, ast.Name)
            ]
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


def _call_cite(path: Path, span: tuple[int, int]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    calls = (*_declaration_calls(text, "requirement"), *_declaration_calls(text, "part_metadata"))
    if not any((call.lineno, call.end_lineno) == span for call in calls):
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


def source_paths(stem: str) -> tuple[Path, ...]:
    """Only this drawing, its citation closures, registry row and shared sources."""
    from _buildgraph import module_deps_of

    stem = _stem(stem)
    drawing = _drawing_module(stem)
    spec = _spec_module(stem)
    modules = {drawing, spec, _notes_module(stem)}
    for declared in requirements_for(drawing).values():
        for _value, sources in declared.fields.values():
            modules.update(importlib.import_module(source[0]) for source in sources if isinstance(source, tuple))
    for metadata in metadata_for(drawing):
        sources = [*metadata.model_sources, *metadata.precision_sources]
        for values in (metadata.fields, metadata.frames, metadata.datums):
            sources.extend(source for _value, names in values.values() for source in names)
        modules.update(importlib.import_module(source[0]) for source in sources if isinstance(source, tuple))
    roots = {Path(__file__).resolve(), *(Path(module.__file__).resolve() for module in modules)}
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


def _drawing_features(stem: str, drawing: ModuleType) -> dict[str, dict[str, Any]]:
    module = _spec_module(stem)
    precision_name = next(
        (name for name in ("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME") if name in _declarations(module)),
        "__frame__",
    )
    result = {}
    for name, declared in requirements_for(drawing).items():
        call = _call_cite(declared.path, declared.call_span)
        feature = {"kind": declared.kind, "frame": "model", "requirements": list(declared.requirements)}
        citations = {}
        for key, (value, sources) in declared.fields.items():
            feature[key] = list(value) if isinstance(value, tuple) else value
            citations[key] = list(dict.fromkeys([*call, *_spec_cite(module, sources)]))
        if declared.precision:
            feature["precision"] = dict(declared.precision)
            citations["precision"] = [*call, *_cite(module, precision_name)]
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
    features = _drawing_features(stem, drawing)
    metadata = metadata_for(drawing)
    facts = {}
    fact_citations = {}
    precision_cite = []
    frame_cite = _cite(module, "__frame__")
    for declared in metadata:
        call = _call_cite(declared.path, declared.call_span)
        for key, (value, sources) in declared.fields.items():
            facts[key] = value
            fact_citations[key] = [*call, *_spec_cite(module, sources)]
        if declared.model_sources:
            frame_cite += [*call, *_spec_cite(module, declared.model_sources)]
        if declared.precision_sources:
            precision_cite += [*call, *_spec_cite(module, declared.precision_sources)]
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
    general.update({"angular_deg": float(_config.title_block("angular")["value_deg"]), "drilled_hole_plus": float(_config.title_block("drilled_hole")["plus_mm"]), "drilled_hole_minus": float(_config.title_block("drilled_hole")["minus_mm"]), "edge_break_r": float(_config.title_block("edge_break")["radius_mm"]), "chamfer_max": float(_config.title_block("edge_break")["chamfer_max_mm"])})
    general["cite"] = {
        key: _title_cite(source)
        for key, source in (
            ("linear_1pl", "linear_1pl.display"), ("linear_2pl", "linear_2pl.display"),
            ("linear_3pl", "linear_3pl.display"), ("angular_deg", "angular.value_deg"),
            ("drilled_hole_plus", "drilled_hole.plus_mm"), ("drilled_hole_minus", "drilled_hole.minus_mm"),
            ("edge_break_r", "edge_break.radius_mm"), ("chamfer_max", "edge_break.chamfer_max_mm"),
        )
    }
    declarations = requirements_for(drawing)
    for name, feature in features.items():
        call = _call_cite(declarations[name].path, declarations[name].call_span)
        for key in feature.get("precision", {}) if isinstance(feature.get("precision"), dict) else ():
            if precision_cite:
                feature["cite"][f"precision.{key}"] = list(dict.fromkeys([*call, *precision_cite]))
            if key in feature["cite"] and isinstance(feature.get(key), list) and len(feature[key]) == 2:
                tolerance = "angular.value_deg" if key.endswith("_deg") else f"linear_{feature['precision'][key]}pl.display"
                feature["cite"][key] += _title_cite(tolerance, "drilled_hole.plus_mm", "drilled_hole.minus_mm")
        if "finish_ra" in feature:
            feature["cite"]["finish_ra"] += _cite(
                _surface_finish,
                "MACHINED_UM" if feature["finish_ra"] == _surface_finish.MACHINED_UM else "SEAT_UM",
            )
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
    for declared in metadata:
        call = _call_cite(declared.path, declared.call_span)
        for values, target in ((declared.frames, frames), (declared.datums, datums)):
            for name, (value, sources) in values.items():
                target[name] = {**value, "cite": [*call, *_spec_cite(module, sources)]}
    volume = {"volume_mm3": facts["volume_mm3"], "volume_cite": fact_citations["volume_mm3"]} if "volume_mm3" in facts else {}
    return {
        "part": dashed, "units": "mm", "precision": facts.get("precision", UNKNOWN),
        "step": bundle_paths(stem)[1].name, "step_sha256": UNKNOWN, "construction": construction, **volume, "cite_root": "harmonic-analyzer",
        "cite": {"construction": construction_cite, "units": frame_cite, "precision": fact_citations.get("precision", frame_cite), "frames": frame_cite},
        "drawing": {"number": row["number"], "revision": UNKNOWN, "cite": [*registry_cite("number"), "harmonic-analyzer/cad/config/release.yaml:next_revision", *_cite(_part_properties, "part_properties")]},
        "material": {"spec": row.get("material_specification", UNKNOWN), "name": row.get("material", UNKNOWN), "finish": row.get("finish", UNKNOWN), "thickness": facts.get("material.thickness", UNKNOWN), "cite": [*registry_cite("material_specification", "material", "finish"), *fact_citations.get("material.thickness", [])]},
        "notes": {"manufacturing": notes.splitlines(), "process": row.get("process", UNKNOWN), "edge_break": f"REMOVE BURRS AND BREAK SHARP EDGES {_config.title_block('edge_break')['display_r']} OR CHAMFER {_config.title_block('edge_break')['display_chamfer']} MAX", "cite": [*registry_cite("process"), *_title_cite("edge_break.display_r", "edge_break.display_chamfer"), *_cite(notes_module, "DRAWING_NOTES")]},
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


def write_manifest(stem: str, step: Path, *, revision: str) -> Path:
    """Bind all labelled STEP faces and write the adjacent requirements TOML."""
    from prechips.model import Features

    from _export_feature_faces import step_face_sets

    stem = _stem(stem)
    step = Path(step)
    content = step.read_bytes()
    manifest = requirement_manifest(stem)
    selectors = feature_selectors(stem)
    if selectors.keys() != manifest["features"].keys():
        raise ValueError(f"feature selector/requirement domains differ: {stem}")
    faces = step_face_sets(content.decode("latin-1"), selectors.keys())
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
